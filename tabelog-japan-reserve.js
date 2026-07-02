// Scrape 予約可否 (reservation availability) from each restaurant's 店舗情報 table
// Per-40 page browser restart, 4 workers, append-only NDJSON
const { chromium } = require('@playwright/test');
const fs = require('fs');

const LISTINGS_JSON = 'D:/Tabelog/japan_listings.json';
const NDJSON_PATH   = 'D:/Tabelog/japan_reserve.ndjson';
const WORKERS = 4;
const BATCH = 40;

const fetched = new Set();
if (fs.existsSync(NDJSON_PATH)) {
  for (const line of fs.readFileSync(NDJSON_PATH, 'utf-8').split('\n')) {
    if (!line.trim()) continue;
    // only count rows that already carry the `net` field (older rsv-only rows get re-fetched)
    try { const r = JSON.parse(line); if (r.url && ('net' in r)) fetched.add(r.url); } catch {}
  }
}

const writeStream = fs.createWriteStream(NDJSON_PATH, { flags: 'a' });
function append(url, data) {
  writeStream.write(JSON.stringify({ url, ...data, fetchedAt: new Date().toISOString() }) + '\n');
}

async function fetchOne(page, url) {
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 22000 });
    await page.waitForTimeout(400);
    return await page.evaluate(() => {
      // 予約可否 from the restaurant-info table: <th>予約可否</th><td>…</td>
      let rsv = '';
      for (const th of document.querySelectorAll('th')) {
        if ((th.textContent || '').replace(/\s+/g, '').includes('予約可否')) {
          const td = th.closest('tr') && th.closest('tr').querySelector('td');
          rsv = td ? td.textContent.replace(/\s+/g, ' ').trim().slice(0, 80) : '';
          break;
        }
      }
      // net = instant online booking available (the global "ネット予約" nav link is on
      // every page, so detect the actual booking widget instead):
      //   .is-yoyaku-booking  or  a "予約する" modal trigger inside the reserve sidebar
      let net = 0;
      const yy = document.querySelector('.rstdtl-side-yoyaku');
      if (yy && yy.querySelector('.is-yoyaku-booking, [class*="js-show-yoyaku-modal-trigger"]')) net = 1;
      return { rsv, net };
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
    if (n % 50 === 0) process.stderr.write(`[W${id} ${n}/${urls.length}] ${d.rsv ? d.rsv.slice(0,12) : (d.error||'-')}\n`);
    await p.waitForTimeout(450 + Math.random() * 300);
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
  await Promise.all(chunks.map((u, i) => worker(i + 1, u)));
  writeStream.end();
  process.stderr.write('✅ Done.\n');
})();
