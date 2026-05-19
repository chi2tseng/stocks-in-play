// Playwright Barchart gappers scraper — intercepts the core-api JSON response.
// Auto-paginates: keeps fetching pages until a page returns 0 qualifying candidates.
//
// Usage:
//   node barchart-scrape.js              → AUTO-detect session by ET clock (default)
//   node barchart-scrape.js auto         → same as default
//   node barchart-scrape.js pre          → scrape pre-market only (2 URLs)
//   node barchart-scrape.js post         → scrape post-market only (2 URLs)
//   node barchart-scrape.js both         → scrape pre + post (4 URLs)
//
// AUTO session rule (US Eastern Time):
//   • 04:00 ET ≤ now < 16:00 ET → 'pre'    (pre-market or regular hours; today's
//                                          pre-market is the most recent gap data)
//   • else                       → 'post'  (post-market or overnight; today's
//                                          post-market is the most recent — OR
//                                          yesterday's if we're past midnight
//                                          before the next pre-market opens at 4 AM)
//
// Output:
//   .firecrawl/barchart-{session}-{direction}-pN.json  (raw API responses, one per page)
//   .firecrawl/candidates.csv                          (final filtered + deduped list)

const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

// ── ET clock helpers (handles DST automatically via Intl) ───────────────
function nowInET() {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: 'numeric', minute: 'numeric', hour12: false,
    weekday: 'short',
  }).formatToParts(new Date());
  const get = key => parts.find(p => p.type === key)?.value;
  let hour = parseInt(get('hour'), 10);
  if (hour === 24) hour = 0;   // Intl quirk: midnight is sometimes "24"
  return {
    date: `${get('year')}-${get('month')}-${get('day')}`,
    hour,
    minute: parseInt(get('minute'), 10),
    weekday: get('weekday'),
    totalMinutes: hour * 60 + parseInt(get('minute'), 10),
  };
}
function autoDetectSession() {
  const et = nowInET();
  const sess = (et.totalMinutes >= 4 * 60 && et.totalMinutes < 16 * 60) ? 'pre' : 'post';
  return { session: sess, et };
}

const rawArg = (process.argv[2] || 'auto').toLowerCase();
if (!['auto','pre','post','both'].includes(rawArg)) {
  console.error(`Invalid session arg: "${rawArg}". Must be one of: auto, pre, post, both`);
  process.exit(1);
}
let sessionArg = rawArg;
if (rawArg === 'auto') {
  const det = autoDetectSession();
  sessionArg = det.session;
  process.stderr.write(`[barchart-scrape] auto-detect: ET ${det.et.weekday} ${det.et.date} ${String(det.et.hour).padStart(2,'0')}:${String(det.et.minute).padStart(2,'0')} → session=${sessionArg}\n`);
}

// Location-agnostic: defaults to the directory containing this script. Override with SIPS_DIR env var.
const OUT_DIR  = process.env.SIPS_DIR ? path.resolve(process.env.SIPS_DIR) : __dirname;
const CHG_MIN  = 4.0;        // |%chg| threshold
const VOL_MIN  = 100_000;    // volume threshold
const MAX_PAGE = 5;          // hard safety cap (Barchart has ~200 rows per list = 2 pages typically)

const ALL_SOURCES = [
  { session: 'pre',  direction: 'advances', url: 'https://www.barchart.com/stocks/pre-market-trading/percent-change/advances?orderBy=preMarketPercentChange&orderDir=desc&viewName=main',  dirTag: 'up'   },
  { session: 'pre',  direction: 'declines', url: 'https://www.barchart.com/stocks/pre-market-trading/percent-change/declines?viewName=main&orderBy=preMarketPercentChange&orderDir=asc',  dirTag: 'down' },
  { session: 'post', direction: 'advances', url: 'https://www.barchart.com/stocks/post-market-trading/percent-change/advances?viewName=main&orderBy=postMarketPercentChange&orderDir=desc',dirTag: 'up'   },
  { session: 'post', direction: 'declines', url: 'https://www.barchart.com/stocks/post-market-trading/percent-change/declines?viewName=main&orderBy=postMarketPercentChange&orderDir=asc', dirTag: 'down' },
];
const SOURCES = sessionArg === 'both' ? ALL_SOURCES : ALL_SOURCES.filter(s => s.session === sessionArg);
process.stderr.write(`[barchart-scrape] session=${sessionArg}, scraping ${SOURCES.length} sources\n`);

function extractRow(row, session, dirTag) {
  const prefix = session === 'pre' ? 'preMarket' : 'postMarket';
  const last   = parseFloat((row[`${prefix}LastPrice`]      || row.lastPrice      || '0').replace(/,/g, ''));
  const chgStr = (row[`${prefix}PercentChange`] || row.percentChange || '+0').replace('%', '').replace(/,/g, '');
  const chg    = parseFloat(chgStr);
  const vol    = parseInt((row[`${prefix}Volume`]            || row.volume         || '0').replace(/,/g, ''), 10);
  return {
    Symbol: row.symbol,
    Name: row.symbolName || row.name || '',
    Last: last,
    ChgPct: dirTag === 'down' ? -Math.abs(chg) : Math.abs(chg),
    Volume: vol,
    Session: session,
    Direction: dirTag,
  };
}

function qualifies(r) { return Math.abs(r.ChgPct) >= CHG_MIN && r.Volume >= VOL_MIN; }

async function fetchPage(page, baseUrl, pageNum) {
  const pageUrl = pageNum === 1 ? baseUrl : `${baseUrl}&page=${pageNum}`;
  let captured = null;
  const handler = async (resp) => {
    if (resp.url().includes('/proxies/core-api/v1/quotes/get') && resp.status() === 200) {
      try {
        const json = await resp.json();
        if (json.data && Array.isArray(json.data) && json.data.length > 0) captured = json;
      } catch {}
    }
  };
  page.on('response', handler);
  try {
    await page.goto(pageUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
    const deadline = Date.now() + 25000;
    while (!captured && Date.now() < deadline) await page.waitForTimeout(500);
  } finally {
    page.off('response', handler);
  }
  return captured;
}

(async () => {
  if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
    viewport: { width: 1440, height: 2400 },
  });
  const page = await ctx.newPage();

  const allRows = [];
  const meta = [];

  for (const src of SOURCES) {
    let pageNum = 1;
    while (pageNum <= MAX_PAGE) {
      process.stderr.write(`[${new Date().toISOString().slice(11,19)}] ${src.session}-${src.direction} p${pageNum} ... `);
      const captured = await fetchPage(page, src.url, pageNum);
      if (!captured) {
        process.stderr.write(`FAIL (no API response)\n`);
        meta.push({ ...src, page: pageNum, status: 'fail', count: 0, qualifying: 0 });
        break;
      }

      // Save raw JSON
      fs.writeFileSync(path.join(OUT_DIR, `barchart-${src.session}-${src.direction}-p${pageNum}.json`), JSON.stringify(captured, null, 2));

      const rows = captured.data.map(r => extractRow(r, src.session, src.dirTag));
      const qual = rows.filter(qualifies);

      // Track min |chg| on this page for diagnostic
      const minChg = Math.min(...rows.map(r => Math.abs(r.ChgPct)));
      const maxChg = Math.max(...rows.map(r => Math.abs(r.ChgPct)));

      allRows.push(...rows);
      meta.push({
        session: src.session, direction: src.direction, page: pageNum,
        count: captured.count, total: captured.total,
        rowsThisPage: rows.length, minChg: +minChg.toFixed(2), maxChg: +maxChg.toFixed(2),
        qualifying: qual.length, status: 'ok',
      });
      process.stderr.write(`OK count=${captured.count}/${captured.total} |chg|=[${minChg.toFixed(2)},${maxChg.toFixed(2)}] qualifying=${qual.length}\n`);

      // Stop conditions:
      // (a) zero qualifying on this page → next page can't have any (Barchart sorts by %chg)
      // (b) all rows below the chg threshold → next page will also be below
      // (c) we've collected all `total` rows
      if (qual.length === 0) break;
      if (maxChg < CHG_MIN) break;
      const collected = pageNum * rows.length;
      if (captured.total && collected >= captured.total) break;

      pageNum++;
    }
  }

  await browser.close();

  // Filter + dedupe
  const filtered = allRows.filter(qualifies);
  const dedupe = {};
  for (const r of filtered) {
    const key = `${r.Symbol}|${r.Session}|${r.Direction}`;
    if (!dedupe[key] || Math.abs(r.ChgPct) > Math.abs(dedupe[key].ChgPct)) dedupe[key] = r;
  }
  const final = Object.values(dedupe).sort((a, b) => a.Symbol.localeCompare(b.Symbol));

  // Save CSV (UTF-8 BOM for Excel) — separate files per session so pre + post don't clobber
  const csvName = sessionArg === 'both' ? 'candidates.csv' : `candidates-${sessionArg}.csv`;
  const csvPath = path.join(OUT_DIR, csvName);
  const header = 'Symbol,Last,ChgPct,Volume,Session,Direction,Name\n';
  const lines  = final.map(r =>
    `${r.Symbol},${r.Last},${r.ChgPct},${r.Volume},${r.Session},${r.Direction},"${(r.Name||'').replace(/"/g,'""')}"`
  ).join('\n');
  fs.writeFileSync(csvPath, '﻿' + header + lines, 'utf-8');

  console.log(JSON.stringify({
    sessionArg,
    filters: { CHG_MIN, VOL_MIN, MAX_PAGE },
    pagesScraped: meta,
    totalUnique: final.length,
    csvPath,
  }, null, 2));
})();
