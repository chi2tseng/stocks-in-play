// Playwright TradingView FQ earnings scraper (plain JS, runs via `node tv-scrape.js TICKER1 TICKER2 ...`)
// Replaces Firecrawl for /mtrt-scan §6.1 scraping.
// Output: .firecrawl/<TICKER>-earnings-fq.md  (same path as Firecrawl, so existing parser works)

const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

// Location-agnostic: defaults to the directory containing this script. Override with SIPS_DIR env var.
const OUT_DIR = process.env.SIPS_DIR ? path.resolve(process.env.SIPS_DIR) : __dirname;
const EXCHANGES = ['NASDAQ', 'NYSE', 'AMEX'];

async function scrapeTicker(page, ticker) {
  for (const exch of EXCHANGES) {
    const url = `https://www.tradingview.com/symbols/${exch}-${ticker}/financials-earnings/?earnings-period=FQ&revenues-period=FQ`;
    try {
      const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
      if (!resp || resp.status() >= 400) continue;

      // Wait briefly for hydration
      await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});

      const title = await page.title();
      if (/not found|404|error/i.test(title)) continue;

      // Wait for the financial data to render — look for ACTUAL data, not just header labels.
      // The chart only fully renders when at least 4 quarter labels (Q1 '24 style) appear
      // AND at least 4 numeric data points (the reported/estimate values) are present.
      try {
        await page.waitForFunction(() => {
          const t = document.body.innerText;
          const quarterLabels = (t.match(/Q[1-4]\s+'\d{2}/g) || []).length;
          // Numeric values: look for either decimal EPS-style (0.46, -0.20) or revenue-style (3.81 B, 95.5 M)
          const numericValues = (t.match(/-?\d+\.\d+(?:\s*[MBK])?/g) || []).length;
          return quarterLabels >= 4 && numericValues >= 8;
        }, { timeout: 30000 });
      } catch {
        // Even if the strict wait fails, try one more time with a soft delay
        await page.waitForTimeout(5000);
      }

      // Also scroll the financial section into view in case lazy-render is gated on visibility
      await page.evaluate(() => {
        const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4'));
        const h = headings.find(el => /EPS and revenue|earnings|financials/i.test(el.textContent || ''));
        if (h) h.scrollIntoView({ behavior: 'instant', block: 'start' });
      }).catch(() => {});
      await page.waitForTimeout(2000);

      const content = await page.evaluate(() => {
        const main = document.querySelector('main') || document.body;
        return main.innerText;
      });

      // Sanity-check: content must contain at least one numeric reported value
      const numCount = (content.match(/-?\d+\.\d+/g) || []).length;
      if (numCount < 8) continue;

      if (content.length < 500) continue;
      if (/this symbol does not exist|not found/i.test(content)) continue;

      const outFile = path.join(OUT_DIR, `${ticker}-earnings-fq.md`);
      fs.writeFileSync(outFile, content, 'utf-8');
      return { ticker, exch, size: content.length, status: 'OK', outFile };
    } catch (e) {
      continue;
    }
  }
  return { ticker, exch: 'none', size: 0, status: 'all-404' };
}

(async () => {
  const tickers = process.argv.slice(2);
  if (tickers.length === 0) {
    console.error('Usage: node tv-scrape.js TICKER1 TICKER2 ...');
    process.exit(1);
  }
  if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
    viewport: { width: 1440, height: 900 },
  });
  const page = await ctx.newPage();

  const results = [];
  for (const t of tickers) {
    process.stderr.write(`[${new Date().toISOString().slice(11,19)}] ${t} ... `);
    const r = await scrapeTicker(page, t);
    results.push(r);
    process.stderr.write(`${r.status} (${r.exch}, ${r.size} bytes)\n`);
  }
  await browser.close();

  console.log(JSON.stringify(results, null, 2));
})();
