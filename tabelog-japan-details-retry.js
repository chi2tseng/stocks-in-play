// Retry failed/missing URLs with fresh browser context every 50 pages
// 讀現有 ndjson → 找 error 或缺資料的 → 重抓 → append (新版本覆蓋舊版本)
//
//   node tabelog-japan-details-retry.js [--workers N] [--batch N]

const { chromium } = require('@playwright/test');
const fs = require('fs');

const LISTINGS_JSON = 'D:/Tabelog/japan_listings.json';
const NDJSON_PATH   = 'D:/Tabelog/japan_details.ndjson';

const args = process.argv.slice(2);
const WORKERS = (() => { const i = args.indexOf('--workers'); return i >= 0 ? parseInt(args[i+1],10) : 2; })();
const BATCH   = (() => { const i = args.indexOf('--batch');   return i >= 0 ? parseInt(args[i+1],10) : 40; })();

// load existing ndjson — keep latest per URL (last writer wins)
const existing = new Map();
if (fs.existsSync(NDJSON_PATH)) {
  for (const line of fs.readFileSync(NDJSON_PATH, 'utf-8').split('\n')) {
    if (!line.trim()) continue;
    try {
      const r = JSON.parse(line);
      existing.set(r.url, r);
    } catch {}
  }
}

// find URLs needing retry: errors or no name
const listings = JSON.parse(fs.readFileSync(LISTINGS_JSON, 'utf-8'));
const allUrls = Object.keys(listings);
const needsRetry = allUrls.filter(u => {
  const r = existing.get(u);
  return !r || r.error || !r.name; // missing or errored or no extracted name
});
process.stderr.write(`Total ${allUrls.length}, valid ${allUrls.length - needsRetry.length}, retry needed ${needsRetry.length}\n`);

const writeStream = fs.createWriteStream(NDJSON_PATH, { flags: 'a' });
function append(url, data) {
  writeStream.write(JSON.stringify({ url, ...data, fetchedAt: new Date().toISOString() }) + '\n');
}

async function fetchOne(page, url) {
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20000 });
    await page.waitForSelector('.rdheader-budget__price-target, h2.display-name', { timeout: 6000 }).catch(() => null);
    await page.waitForTimeout(700 + Math.random() * 500);
    return await page.evaluate(() => {
      const out = { name: null, addr: null, dinner: null, lunch: null, rating: null };
      const h2 = document.querySelector('h2.display-name span, h2.display-name, [class*="display-name"] span');
      if (h2) out.name = h2.textContent.trim();
      const targets = [...document.querySelectorAll('.rdheader-budget__price-target')];
      if (targets[0]) out.dinner = targets[0].textContent.trim();
      if (targets[1]) out.lunch  = targets[1].textContent.trim();
      if (out.dinner === '-' || out.dinner === '') out.dinner = null;
      if (out.lunch  === '-' || out.lunch  === '') out.lunch  = null;
      for (const el of document.querySelectorAll('script[type="application/ld+json"]')) {
        try {
          const data = JSON.parse(el.textContent);
          const list = Array.isArray(data) ? data : [data];
          for (const o of list) {
            const a = o?.address || o?.location?.address;
            if (a && a.addressRegion) {
              out.addr = [a.addressRegion, a.addressLocality, a.streetAddress].filter(Boolean).join('');
              break;
            }
          }
          if (out.addr) break;
        } catch {}
      }
      const r = document.querySelector('.rdheader-rating__score-val');
      if (r) out.rating = r.textContent.trim();
      return out;
    });
  } catch (err) {
    return { error: err.message.slice(0, 80) };
  }
}

async function worker(workerId, urls) {
  let n = 0;
  let browser = null, ctx = null, page = null;

  async function fresh() {
    if (browser) try { await browser.close(); } catch {}
    browser = await chromium.launch({ headless: true });
    ctx = await browser.newContext({
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
      locale: 'ja-JP',
      viewport: { width: 1280, height: 800 },
    });
    page = await ctx.newPage();
  }
  await fresh();

  for (const url of urls) {
    n++;
    if (n > 1 && n % BATCH === 0) {
      process.stderr.write(`[W${workerId}] restart browser at ${n}/${urls.length}\n`);
      await fresh();
    }
    const d = await fetchOne(page, url);
    append(url, d);
    if (n % 25 === 0) {
      process.stderr.write(`[W${workerId} ${n}/${urls.length}] ${(d.name||'?').slice(0,18)} 夜=${d.dinner||'-'} ${d.error ? '[ERR]' : ''}\n`);
    }
    await page.waitForTimeout(900 + Math.random() * 500);
  }
  if (browser) await browser.close();
}

(async () => {
  if (needsRetry.length === 0) {
    process.stderr.write('Nothing to retry. Done.\n');
    writeStream.end();
    return;
  }
  const chunks = Array.from({ length: WORKERS }, () => []);
  needsRetry.forEach((u, i) => chunks[i % WORKERS].push(u));
  await Promise.all(chunks.map((urls, i) => worker(i+1, urls)));
  writeStream.end();
  process.stderr.write(`\n✅ Retry done.\n`);
})();
