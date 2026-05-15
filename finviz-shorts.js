// Playwright Finviz scraper — pulls short interest + recent price performance for each ticker
// in today's candidates.csv. Output: D:\SIPs\shorts.json
//
// Fields extracted from the Finviz quote-page snapshot table:
//   - Short Float        (% of float that's short)
//   - Short Ratio        (days to cover)
//   - Market Cap         (parsed to millions USD)
//   - Shs Float          (parsed to millions of shares)
//   - Perf Quarter       (3M)
//   - Perf Half Y        (6M)
//   - Perf YTD
//   - Perf Year          (12M)
//
// Usage:
//   node finviz-shorts.js                     → read tickers from candidates.csv
//   node finviz-shorts.js AAPL MSFT NVDA      → scrape specific tickers
//
// The Finviz quote page is mostly static HTML — no client-side rendering — so we can use
// Playwright's `page.content()` and parse the snapshot table directly. Concurrency: 5 pages
// in parallel to keep total runtime under ~30s for ~80 tickers.

const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

// Location-agnostic: defaults to the directory containing this script. Override with SIPS_DIR env var.
const OUT_DIR = process.env.SIPS_DIR ? path.resolve(process.env.SIPS_DIR) : __dirname;
// Concurrency 2 + small jitter between requests. Finviz serves a Cloudflare-style empty
// snapshot when it suspects bot traffic, so we slow down to stay below the threshold.
const CONCURRENCY = 2;
const REQUEST_JITTER_MS = [400, 900];   // sleep range between successive requests on the same page
const RETRY_ON_EMPTY = true;

// Parse a Finviz value cell. Returns a number or null.
//   "12.34%"     → 12.34
//   "1.23B"      → 1230  (millions)
//   "456.7M"     → 456.7
//   "-"          → null
function parseValue(raw, kind) {
  if (raw == null) return null;
  const s = String(raw).trim();
  if (!s || s === '-' || s === '—') return null;
  const m = s.match(/^(-?[\d,]+\.?\d*)\s*([%KMB])?$/i);
  if (!m) return null;
  let n = parseFloat(m[1].replace(/,/g, ''));
  if (Number.isNaN(n)) return null;
  const unit = (m[2] || '').toUpperCase();
  if (kind === 'cap' || kind === 'float') {
    // Normalize to millions
    if (unit === 'B') n *= 1000;
    else if (unit === 'K') n /= 1000;
    // M or empty → already in millions (for cap/float)
  }
  // pct values: just return the number as-is (12.34 = 12.34%)
  return n;
}

async function scrapeOnce(page, url) {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
  // Wait briefly for the snapshot table to be present (it's in the static HTML, but give the parser time).
  try { await page.waitForSelector('table.snapshot-table2', { timeout: 3000 }); } catch {}
  return page.evaluate(() => {
    const out = {};
    const rows = document.querySelectorAll('table.snapshot-table2 tr');
    rows.forEach(tr => {
      const cells = tr.querySelectorAll('td');
      for (let i = 0; i + 1 < cells.length; i += 2) {
        const k = cells[i].innerText.trim();
        const v = cells[i + 1].innerText.trim();
        if (k) out[k] = v;
      }
    });
    return out;
  });
}

async function scrapeTicker(page, ticker) {
  const url = `https://finviz.com/quote.ashx?t=${ticker}&p=d`;
  try {
    let data = await scrapeOnce(page, url);
    if ((!data || Object.keys(data).length === 0) && RETRY_ON_EMPTY) {
      // Cloudflare/empty response — back off and try once more.
      await page.waitForTimeout(2000 + Math.random() * 1500);
      data = await scrapeOnce(page, url);
    }
    if (!data || Object.keys(data).length === 0) return { ticker, status: 'empty' };
    return {
      ticker,
      status: 'ok',
      shortFloat:     parseValue(data['Short Float'],   'pct'),
      shortRatio:     parseValue(data['Short Ratio'],   'num'),
      marketCap_M:    parseValue(data['Market Cap'],    'cap'),
      floatShares_M:  parseValue(data['Shs Float'],     'float'),
      perf1M:         parseValue(data['Perf Month'],    'pct'),
      perf3M:         parseValue(data['Perf Quarter'],  'pct'),
      perf6M:         parseValue(data['Perf Half Y'],   'pct'),
      perfYTD:        parseValue(data['Perf YTD'],      'pct'),
      perf12M:        parseValue(data['Perf Year'],     'pct'),
      raw: { sf: data['Short Float'], sr: data['Short Ratio'], mc: data['Market Cap'] },
    };
  } catch (e) {
    return { ticker, status: 'error', error: e.message };
  }
}

function loadTickersFromCsv() {
  const csvPath = path.join(OUT_DIR, 'candidates.csv');
  if (!fs.existsSync(csvPath)) {
    console.error(`[finviz-shorts] ${csvPath} not found. Run barchart-scrape.js first or pass tickers as args.`);
    process.exit(1);
  }
  const text = fs.readFileSync(csvPath, 'utf-8').replace(/^﻿/, '');
  const lines = text.trim().split('\n').slice(1); // skip header
  const tickers = new Set();
  for (const line of lines) {
    const [sym] = line.split(',');
    if (sym && sym.trim()) tickers.add(sym.trim());
  }
  return Array.from(tickers);
}

(async () => {
  const argTickers = process.argv.slice(2).filter(Boolean);
  const tickers = argTickers.length ? argTickers : loadTickersFromCsv();
  process.stderr.write(`[finviz-shorts] scraping ${tickers.length} tickers (concurrency=${CONCURRENCY})\n`);

  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
    viewport: { width: 1440, height: 1200 },
  });

  const results = {};
  const queue = tickers.slice();
  let done = 0;
  const t0 = Date.now();

  async function worker(workerId) {
    const page = await ctx.newPage();
    while (queue.length) {
      const t = queue.shift();
      if (!t) break;
      const r = await scrapeTicker(page, t);
      results[t] = r;
      done++;
      if (done % 5 === 0 || done === tickers.length) {
        const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
        process.stderr.write(`[finviz-shorts] ${done}/${tickers.length} (${elapsed}s)\n`);
      }
      // Jitter sleep before next request on this worker to stay below Finviz's rate limit.
      const [lo, hi] = REQUEST_JITTER_MS;
      await page.waitForTimeout(lo + Math.random() * (hi - lo));
    }
    await page.close();
  }

  await Promise.all(Array.from({ length: CONCURRENCY }, (_, i) => worker(i)));
  await browser.close();

  const outPath = path.join(OUT_DIR, 'shorts.json');
  fs.writeFileSync(outPath, JSON.stringify(results, null, 2), 'utf-8');
  const okCount = Object.values(results).filter(r => r.status === 'ok').length;
  console.log(JSON.stringify({
    total: tickers.length,
    ok: okCount,
    failed: tickers.length - okCount,
    elapsed_s: ((Date.now() - t0) / 1000).toFixed(1),
    outPath,
  }, null, 2));
})();
