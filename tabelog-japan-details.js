// Playwright: 2-worker 順序穩定抓 12,280 家詳情頁
// 每頁立即寫入 NDJSON (japan_details.ndjson) 避免 buffer 丟失
// 完成後再合併成 japan_details.json
//
//   node tabelog-japan-details.js [--workers N] [--start IDX] [--limit N]

const { chromium } = require('@playwright/test');
const fs = require('fs');

const LISTINGS_JSON = 'D:/Tabelog/japan_listings.json';
const NDJSON_PATH   = 'D:/Tabelog/japan_details.ndjson';

const args = process.argv.slice(2);
const WORKERS  = (() => { const i = args.indexOf('--workers'); return i >= 0 ? parseInt(args[i+1],10) : 2; })();
const START_I  = (() => { const i = args.indexOf('--start');   return i >= 0 ? parseInt(args[i+1],10) : 0; })();
const LIMIT    = (() => { const i = args.indexOf('--limit');   return i >= 0 ? parseInt(args[i+1],10) : Infinity; })();

// load already-fetched URLs from ndjson (resume)
const fetched = new Set();
if (fs.existsSync(NDJSON_PATH)) {
  for (const line of fs.readFileSync(NDJSON_PATH, 'utf-8').split('\n')) {
    if (!line.trim()) continue;
    try { fetched.add(JSON.parse(line).url); } catch {}
  }
}

async function fetchOne(page, url) {
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 25000 });
    // wait for the budget block to actually render
    await page.waitForSelector('.rdheader-budget__price-target, h2.display-name', { timeout: 8000 }).catch(() => null);
    await page.waitForTimeout(800 + Math.random() * 700);

    return await page.evaluate(() => {
      const out = { name: null, addr: null, dinner: null, lunch: null, rating: null };
      // name
      const h2 = document.querySelector('h2.display-name span, h2.display-name, [class*="display-name"] span');
      if (h2) out.name = h2.textContent.trim();
      // price
      const targets = [...document.querySelectorAll('.rdheader-budget__price-target')];
      if (targets[0]) out.dinner = targets[0].textContent.trim();
      if (targets[1]) out.lunch  = targets[1].textContent.trim();
      if (out.dinner === '-' || out.dinner === '') out.dinner = null;
      if (out.lunch  === '-' || out.lunch  === '') out.lunch  = null;
      // addr from JSON-LD
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
      // rating
      const r = document.querySelector('.rdheader-rating__score-val');
      if (r) out.rating = r.textContent.trim();
      return out;
    });
  } catch (err) {
    return { error: err.message.slice(0, 80) };
  }
}

const writeStream = fs.createWriteStream(NDJSON_PATH, { flags: 'a' });
function append(url, data) {
  writeStream.write(JSON.stringify({ url, ...data, fetchedAt: new Date().toISOString() }) + '\n');
}

async function worker(workerId, urls) {
  const b = await chromium.launch({ headless: true });
  const ctx = await b.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    locale: 'ja-JP',
    viewport: { width: 1280, height: 800 },
  });
  const page = await ctx.newPage();
  let n = 0;
  for (const url of urls) {
    n++;
    if (fetched.has(url)) continue;
    const d = await fetchOne(page, url);
    append(url, d);
    fetched.add(url);
    if (n % 25 === 0 || d.name) {
      process.stderr.write(`[W${workerId} ${n}/${urls.length}] ${(d.name||'?').slice(0,20)} 夜=${d.dinner||'-'} 昼=${d.lunch||'-'}\n`);
    }
    // gentler pace to avoid rate limit
    await page.waitForTimeout(1200 + Math.random() * 600);
  }
  await b.close();
}

(async () => {
  const listings = JSON.parse(fs.readFileSync(LISTINGS_JSON, 'utf-8'));
  let allUrls = Object.keys(listings).slice(START_I, START_I + LIMIT).filter(u => !fetched.has(u));
  process.stderr.write(`Total to fetch: ${allUrls.length} (resume from ${fetched.size} already done)\n`);

  const chunks = Array.from({ length: WORKERS }, () => []);
  allUrls.forEach((u, i) => chunks[i % WORKERS].push(u));

  await Promise.all(chunks.map((urls, i) => worker(i+1, urls)));
  writeStream.end();
  process.stderr.write(`\n✅ Done.\n`);
})();
