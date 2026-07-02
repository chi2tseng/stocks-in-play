// Scrape lat/lng from each restaurant's JSON-LD
// Per-40 page browser restart to avoid memory crash, 4 workers
const { chromium } = require('@playwright/test');
const fs = require('fs');

const LISTINGS_JSON = 'D:/Tabelog/japan_listings.json';
const NDJSON_PATH   = 'D:/Tabelog/japan_coords.ndjson';
const WORKERS = 4;
const BATCH = 40;

const fetched = new Set();
if (fs.existsSync(NDJSON_PATH)) {
  for (const line of fs.readFileSync(NDJSON_PATH, 'utf-8').split('\n')) {
    if (!line.trim()) continue;
    try { const r = JSON.parse(line); if (r.lat) fetched.add(r.url); } catch {}
  }
}

const writeStream = fs.createWriteStream(NDJSON_PATH, { flags: 'a' });
function append(url, data) {
  writeStream.write(JSON.stringify({ url, ...data, fetchedAt: new Date().toISOString() }) + '\n');
}

async function fetchOne(page, url) {
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 22000 });
    await page.waitForTimeout(500);
    return await page.evaluate(() => {
      for (const el of document.querySelectorAll('script[type="application/ld+json"]')) {
        try {
          const obj = JSON.parse(el.textContent);
          const list = Array.isArray(obj) ? obj : [obj];
          for (const o of list) {
            const g = o?.geo || o?.location?.geo;
            if (g && g.latitude && g.longitude) return { lat: g.latitude, lng: g.longitude };
          }
        } catch {}
      }
      return { error: 'no geo' };
    });
  } catch (err) { return { error: err.message.slice(0, 60) }; }
}

async function worker(id, urls) {
  let n = 0, b = null, p = null;
  async function fresh() {
    if (b) try { await b.close(); } catch {}
    b = await chromium.launch({ headless: true });
    const ctx = await b.newContext({
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
      locale: 'ja-JP', viewport: { width: 1280, height: 800 },
    });
    p = await ctx.newPage();
  }
  await fresh();
  for (const url of urls) {
    n++;
    if (n > 1 && n % BATCH === 0) { process.stderr.write(`[W${id}] restart ${n}/${urls.length}\n`); await fresh(); }
    const d = await fetchOne(p, url);
    append(url, d);
    if (n % 50 === 0) process.stderr.write(`[W${id} ${n}/${urls.length}] ${d.lat ? 'OK' : 'ERR'}\n`);
    await p.waitForTimeout(500 + Math.random() * 300);
  }
  if (b) await b.close();
}

(async () => {
  const listings = JSON.parse(fs.readFileSync(LISTINGS_JSON, 'utf-8'));
  const urls = Object.keys(listings).filter(u => !fetched.has(u));
  process.stderr.write(`Total ${Object.keys(listings).length}, cached ${fetched.size}, todo ${urls.length}\n`);
  if (urls.length === 0) { writeStream.end(); return; }
  const chunks = Array.from({ length: WORKERS }, () => []);
  urls.forEach((u, i) => chunks[i % WORKERS].push(u));
  await Promise.all(chunks.map((u, i) => worker(i+1, u)));
  writeStream.end();
  process.stderr.write('✅ Done.\n');
})();
