// Playwright scraper that hits multiple analyst-forecast aggregators and dumps each
// page's rendered text to a file. Goal: find which sites publish per-quarter forward
// EPS + Revenue estimates as plain text we can parse.
//
// Usage: node forecast-scrape.js AMD
//
// Strategy: each source is tried with a real Chromium browser (defeats most bot checks
// that simple curl can't pass). Stealth-style settings: real user-agent, real viewport,
// network-idle wait. Output: D:\SIPs\forecast-scrape\<source>-<TICKER>.txt
//
// Sources tested are blocked-or-thin under WebFetch — Playwright tries them via real
// browser to see if the data is actually there once JS renders.

const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const OUT_DIR = path.join(__dirname, 'forecast-scrape');

// Test URL list. Each entry: { name, urlFn(ticker), waitSelectorOrText }
// waitSelector: CSS selector that signals data is rendered. Optional.
// waitForText: substring (case-insensitive) we want to see in body before extracting.
const SOURCES = [
  { name: 'yahoo',          urlFn: t => `https://finance.yahoo.com/quote/${t}/analysis/`,           wait: 'Estimate' },
  { name: 'nasdaq',         urlFn: t => `https://www.nasdaq.com/market-activity/stocks/${t.toLowerCase()}/earnings`, wait: 'Estimate' },
  { name: 'marketbeat',     urlFn: t => `https://www.marketbeat.com/stocks/NASDAQ/${t}/forecast/`,  wait: 'Consensus' },
  { name: 'tipranks',       urlFn: t => `https://www.tipranks.com/stocks/${t.toLowerCase()}/forecast`, wait: 'Consensus' },
  { name: 'zacks',          urlFn: t => `https://www.zacks.com/stock/quote/${t}/detailed-estimates`, wait: 'Estimate' },
  { name: 'investing',      urlFn: t => `https://www.investing.com/equities/${t.toLowerCase() === 'amd' ? 'advanced-micro-devices' : t.toLowerCase()}-earnings`, wait: 'Forecast' },
  { name: 'stockanalysis-q',urlFn: t => `https://stockanalysis.com/stocks/${t.toLowerCase()}/forecast/?p=quarterly`, wait: 'Forecast' },
  { name: 'morningstar',    urlFn: t => `https://www.morningstar.com/stocks/xnas/${t.toLowerCase()}/forecast`, wait: 'Estimate' },
  { name: 'roic',           urlFn: t => `https://www.roic.ai/quote/${t}`,                            wait: null },
  { name: 'streetinsider',  urlFn: t => `https://www.streetinsider.com/earnings/${t}`,               wait: null },
  { name: 'estimize',       urlFn: t => `https://www.estimize.com/${t}/eps`,                         wait: null },
  { name: 'wsj',            urlFn: t => `https://www.wsj.com/market-data/quotes/${t}/financials`,    wait: null },
  { name: 'tipranks-earn',  urlFn: t => `https://www.tipranks.com/stocks/${t.toLowerCase()}/earnings`,wait: 'Estimate' },
  { name: 'gurufocus',      urlFn: t => `https://www.gurufocus.com/stock/${t}/forecast`,             wait: 'Estimate' },
  { name: 'simplywall',     urlFn: t => `https://simplywall.st/stocks/us/semiconductors/nasdaq-${t.toLowerCase()}/${t.toLowerCase() === 'amd' ? 'advanced-micro-devices' : t.toLowerCase()}/future`, wait: 'Estimate' },
  { name: 'discountingcf',  urlFn: t => `https://discountingcashflows.com/company/${t}/analyst-estimates/`, wait: 'Estimate' },
];

async function scrapeOne(browser, src, ticker) {
  const url = src.urlFn(ticker);
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    viewport: { width: 1366, height: 900 },
    locale: 'en-US',
  });
  const page = await ctx.newPage();
  let result = { name: src.name, url, status: 'unknown', size: 0, hasQuarterly: false };
  try {
    const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    result.status = resp ? resp.status() : 'no-response';
    if (!resp || resp.status() >= 400) {
      await ctx.close();
      return result;
    }
    // Soft wait — let JS render
    await page.waitForLoadState('networkidle', { timeout: 12000 }).catch(() => {});
    if (src.wait) {
      try {
        await page.waitForFunction(
          (needle) => document.body.innerText.toLowerCase().includes(String(needle).toLowerCase()),
          src.wait, { timeout: 8000 }
        );
      } catch {}
    }
    // Extra wait to let lazy content load
    await page.waitForTimeout(2500);

    // Auto-scroll to bottom and back to top to trigger lazy-load
    await page.evaluate(async () => {
      await new Promise(r => {
        let n = 0;
        const i = setInterval(() => {
          window.scrollBy(0, 600);
          n++;
          if (n > 6) { clearInterval(i); r(); }
        }, 200);
      });
      window.scrollTo(0, 0);
    }).catch(() => {});
    await page.waitForTimeout(1000);

    const text = await page.evaluate(() => document.body.innerText);
    result.size = text.length;

    // Heuristic: does the page contain per-quarter forward estimates?
    // We look for patterns like "Q1 2026" or "Q1 '26" along with numerical estimates.
    const quarterHits = (text.match(/Q[1-4]\s*['']?\s*20?2[6-9]/g) || []).length;
    const epsHits     = (text.match(/EPS\s+Estimate|Earnings\s+Estimate|EPS\s+Avg/gi) || []).length;
    const revHits     = (text.match(/Revenue\s+Estimate|Sales\s+Estimate|Revenue\s+Avg/gi) || []).length;
    result.quarterHits = quarterHits;
    result.epsHits = epsHits;
    result.revHits = revHits;
    result.hasQuarterly = (quarterHits >= 2 && (epsHits + revHits) >= 1);

    const outFile = path.join(OUT_DIR, `${src.name}-${ticker}.txt`);
    fs.writeFileSync(outFile, text, 'utf-8');
    result.outFile = outFile;
  } catch (e) {
    result.status = 'err';
    result.err = String(e).slice(0, 200);
  } finally {
    await ctx.close();
  }
  return result;
}

(async () => {
  const ticker = (process.argv[2] || 'AMD').toUpperCase();
  if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });
  console.error(`[forecast-scrape] running ${SOURCES.length} sources for ${ticker}`);
  const browser = await chromium.launch({ headless: true });
  const results = [];
  for (const src of SOURCES) {
    const r = await scrapeOne(browser, src, ticker);
    results.push(r);
    const ok = (typeof r.status === 'number' && r.status < 400);
    const flag = r.hasQuarterly ? '★' : (ok ? ' ' : '×');
    console.error(`${flag} ${r.name.padEnd(18)} status=${String(r.status).padEnd(4)} size=${String(r.size).padStart(6)} qHits=${r.quarterHits||0} eps=${r.epsHits||0} rev=${r.revHits||0}`);
  }
  await browser.close();
  fs.writeFileSync(path.join(OUT_DIR, `_index-${ticker}.json`), JSON.stringify(results, null, 2));
  // Print a clean console summary
  console.log('\n=== summary ===');
  for (const r of results) {
    const ok = (typeof r.status === 'number' && r.status < 400);
    const flag = r.hasQuarterly ? '★ FOUND' : (ok ? '· empty' : '× block');
    console.log(`${flag.padEnd(8)} ${r.name.padEnd(18)} status=${String(r.status).padEnd(4)} size=${String(r.size).padStart(6)} qHits=${r.quarterHits||0}`);
  }
})();
