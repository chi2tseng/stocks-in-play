// 盤中 (regular session) gapper scan — 10:00 ET 補掃用。
// 攔截 barchart /proxies/core-api/v1/quotes/get,取 regular-session percentChange。
const { chromium } = require('@playwright/test');
const fs = require('fs');

const CHG_MIN = 4.0, VOL_MIN = 100_000;
const SOURCES = [
  { dir: 'up',   url: 'https://www.barchart.com/stocks/performance/percent-change/advances?viewName=main&orderBy=percentChange&orderDir=desc' },
  { dir: 'down', url: 'https://www.barchart.com/stocks/performance/percent-change/declines?viewName=main&orderBy=percentChange&orderDir=asc' },
];

async function fetchPage(page, baseUrl, pageNum) {
  const url = pageNum === 1 ? baseUrl : `${baseUrl}&page=${pageNum}`;
  let captured = null;
  const handler = async (resp) => {
    if (resp.url().includes('/proxies/core-api/v1/quotes/get') && resp.status() === 200) {
      try { const j = await resp.json(); if (j.data && j.data.length) captured = j; } catch {}
    }
  };
  page.on('response', handler);
  try {
    try { await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 90000 }); } catch {}
    const deadline = Date.now() + 45000;
    while (!captured && Date.now() < deadline) await page.waitForTimeout(500);
  } finally { page.off('response', handler); }
  return captured;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
    viewport: { width: 1440, height: 2400 },
  });
  const page = await ctx.newPage();
  const rows = [];
  for (const src of SOURCES) {
    for (let p = 1; p <= 2; p++) {
      const cap = await fetchPage(page, src.url, p);
      if (!cap) { process.stderr.write(`${src.dir} p${p} FAIL\n`); break; }
      let n = 0;
      for (const r of cap.data) {
        const last = parseFloat(String(r.lastPrice || '0').replace(/,/g, ''));
        const chg  = parseFloat(String(r.percentChange || '0').replace(/[%,]/g, ''));
        const vol  = parseInt(String(r.volume || '0').replace(/,/g, ''), 10);
        if (Math.abs(chg) >= CHG_MIN && vol >= VOL_MIN) {
          rows.push({ Symbol: r.symbol, Name: r.symbolName || '', Last: last, ChgPct: chg, Volume: vol, Direction: src.dir });
          n++;
        }
      }
      process.stderr.write(`${src.dir} p${p}: ${cap.data.length} rows, ${n} qualify\n`);
      if (cap.data.length < 100) break;
    }
  }
  const seen = new Set(); const out = [];
  for (const r of rows) { if (!seen.has(r.Symbol)) { seen.add(r.Symbol); out.push(r); } }
  fs.writeFileSync('_intraday_0807.json', JSON.stringify(out, null, 1));
  process.stderr.write(`TOTAL ${out.length} unique intraday movers -> _intraday_0807.json\n`);
  await browser.close();
})();
