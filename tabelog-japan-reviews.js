// Scrape top 3 reviews per restaurant (title + body) from /dtlrvwlst/ page
// 4 workers, restart browser every 40 pages, save NDJSON incrementally

const { chromium } = require('@playwright/test');
const fs = require('fs');

const LISTINGS_JSON = 'D:/Tabelog/japan_listings.json';
const NDJSON_PATH   = 'D:/Tabelog/japan_reviews.ndjson';
const WORKERS = (() => { const i = process.argv.indexOf('--workers'); return i >= 0 ? parseInt(process.argv[i+1],10) : 2; })();
const BATCH = (() => { const i = process.argv.indexOf('--batch'); return i >= 0 ? parseInt(process.argv[i+1],10) : 20; })();

// only consider URLs with SUCCESSFUL fetches as cached (skip errors → retry them)
const fetched = new Set();
if (fs.existsSync(NDJSON_PATH)) {
  // dedupe: keep latest entry per url
  const last = new Map();
  for (const line of fs.readFileSync(NDJSON_PATH, 'utf-8').split('\n')) {
    if (!line.trim()) continue;
    try { const r = JSON.parse(line); last.set(r.url, r); } catch {}
  }
  for (const [url, r] of last) {
    if (!r.error) fetched.add(url); // retry errored ones
  }
}

const writeStream = fs.createWriteStream(NDJSON_PATH, { flags: 'a' });
function append(url, data) {
  writeStream.write(JSON.stringify({ url, ...data, fetchedAt: new Date().toISOString() }) + '\n');
}

async function fetchOne(page, baseUrl) {
  const url = baseUrl.replace(/\/?$/, '/') + 'dtlrvwlst/';
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForSelector('.rvw-item, .rvw-item__title', { timeout: 6000 }).catch(()=>null);
    await page.waitForTimeout(400);
    return await page.evaluate(() => {
      const reviews = [...document.querySelectorAll('.rvw-item')].slice(0, 3).map(rv => {
        const title = rv.querySelector('.rvw-item__title, .rvw-item__rvw-title')?.textContent.trim().slice(0,120) || '';
        const body = rv.querySelector('.rvw-item__rvw-body, .rvw-item__catch-review, .rvw-item__rvw-comment')?.textContent.replace(/\s+/g,' ').trim().slice(0,400) || '';
        return { title, body };
      }).filter(r => r.title || r.body);
      return { reviews };
    });
  } catch (err) {
    return { error: err.message.slice(0, 80) };
  }
}

async function worker(workerId, urls) {
  let n = 0;
  let browser = null, page = null;
  async function fresh() {
    if (browser) try { await browser.close(); } catch {}
    browser = await chromium.launch({ headless: true });
    const ctx = await browser.newContext({
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
      process.stderr.write(`[W${workerId}] restart at ${n}/${urls.length}\n`);
      await fresh();
    }
    const d = await fetchOne(page, url);
    append(url, d);
    if (n % 25 === 0) {
      const rc = d.reviews ? d.reviews.length : 0;
      process.stderr.write(`[W${workerId} ${n}/${urls.length}] ${rc} reviews ${d.error ? '[ERR]' : ''}\n`);
    }
    await page.waitForTimeout(700 + Math.random() * 400);
  }
  if (browser) await browser.close();
}

(async () => {
  const listings = JSON.parse(fs.readFileSync(LISTINGS_JSON, 'utf-8'));
  const allUrls = Object.keys(listings).filter(u => !fetched.has(u));
  process.stderr.write(`Total ${Object.keys(listings).length} listings, ${fetched.size} cached, ${allUrls.length} todo\n`);
  if (allUrls.length === 0) { writeStream.end(); return; }
  const chunks = Array.from({ length: WORKERS }, () => []);
  allUrls.forEach((u, i) => chunks[i % WORKERS].push(u));
  await Promise.all(chunks.map((urls, i) => worker(i+1, urls)));
  writeStream.end();
  process.stderr.write('\n✅ Done.\n');
})();
