// Scrape og:image cover + homepage photo strip per restaurant from Tabelog main page.
// 4 workers, restart browser every 60 pages, resume-able, append-only NDJSON.
//
//   node tabelog-japan-header.js [--workers N] [--batch N]

const { chromium } = require('@playwright/test');
const fs = require('fs');

const LISTINGS_JSON = 'D:/Tabelog/japan_listings.json';
const NDJSON_PATH   = 'D:/Tabelog/japan_header_photos.ndjson';
const WORKERS = (() => { const i = process.argv.indexOf('--workers'); return i >= 0 ? parseInt(process.argv[i+1],10) : 4; })();
const BATCH   = (() => { const i = process.argv.indexOf('--batch');   return i >= 0 ? parseInt(process.argv[i+1],10) : 60; })();

// Resume: skip URLs already in ndjson without an error field
const fetched = new Set();
if (fs.existsSync(NDJSON_PATH)) {
  const last = new Map();
  for (const line of fs.readFileSync(NDJSON_PATH, 'utf-8').split('\n')) {
    if (!line.trim()) continue;
    try { const r = JSON.parse(line); last.set(r.url, r); } catch {}
  }
  for (const [url, r] of last) {
    if (!r.error) fetched.add(url);
  }
}

const writeStream = fs.createWriteStream(NDJSON_PATH, { flags: 'a' });
function append(url, data) {
  writeStream.write(JSON.stringify({ url, ...data, fetchedAt: new Date().toISOString() }) + '\n');
}

async function fetchOne(page, baseUrl) {
  try {
    await page.goto(baseUrl, { waitUntil: 'domcontentloaded', timeout: 20000 });
    // Small wait to let inline images settle
    await page.waitForTimeout(300 + Math.random() * 200);

    const result = await page.evaluate(() => {
      // Cover = og:image meta tag (canonical showcase photo)
      const cover = document.querySelector('meta[property="og:image"]')?.content || null;

      // Homepage photo strip: imgs inside .rstdtl-top-postphoto__photo containers
      // These are the food/restaurant photos visible on the detail page header area.
      // Upsize from 150x150_square_ to 640x640c for quality.
      const seen = new Set();
      const photos = [];
      for (const el of document.querySelectorAll('.rstdtl-top-postphoto__photo img')) {
        let src = el.src || el.dataset?.original || '';
        if (!src || !src.includes('tblg.k-img.com')) continue;
        // Upsize thumbnails
        src = src.replace(/\/\d+x\d+_square_/, '/640x640_square_');
        if (seen.has(src)) continue;
        seen.add(src);
        photos.push(src);
        if (photos.length >= 6) break;
      }

      return { cover, photos };
    });

    if (!result.cover && result.photos.length === 0) {
      return { error: 'no images' };
    }
    return result;
  } catch (err) {
    return { error: err.message.slice(0, 120) };
  }
}

async function worker(workerId, urls) {
  let n = 0;
  let browser = null, page = null;

  async function fresh() {
    if (browser) { try { await browser.close(); } catch {} }
    browser = await chromium.launch({ headless: true });
    const ctx = await browser.newContext({
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
      locale: 'ja-JP',
      viewport: { width: 1280, height: 900 },
    });
    page = await ctx.newPage();
  }

  await fresh();

  for (const url of urls) {
    n++;
    // Restart browser every BATCH pages to prevent memory leaks
    if (n > 1 && (n - 1) % BATCH === 0) {
      process.stderr.write(`[W${workerId}] restart at page ${n}/${urls.length}\n`);
      await fresh();
    }

    const result = await fetchOne(page, url);
    append(url, result);

    // Progress log every 25 pages and on first page
    if (n % 25 === 0 || n === 1) {
      const photoCount = result.photos ? result.photos.length : 0;
      const coverFlag = result.cover ? ' cover=OK' : ' cover=MISS';
      const errFlag = result.error ? ` [ERR: ${result.error.slice(0,40)}]` : '';
      process.stderr.write(`[W${workerId} ${n}/${urls.length}]${coverFlag} photos=${photoCount}${errFlag} — ${url.slice(0, 70)}\n`);
    }

    // 600–900ms random delay (lightweight main page)
    await page.waitForTimeout(600 + Math.random() * 300);
  }

  if (browser) { try { await browser.close(); } catch {} }
  process.stderr.write(`[W${workerId}] DONE (${n} pages)\n`);
}

(async () => {
  const listings = JSON.parse(fs.readFileSync(LISTINGS_JSON, 'utf-8'));
  const allUrls = Object.keys(listings).filter(u => !fetched.has(u));

  process.stderr.write(`Listings: ${Object.keys(listings).length} total, ${fetched.size} cached, ${allUrls.length} todo\n`);
  process.stderr.write(`Workers: ${WORKERS}, Batch size: ${BATCH}\n`);

  if (allUrls.length === 0) {
    process.stderr.write('Nothing to do — all URLs already fetched.\n');
    writeStream.end();
    return;
  }

  // Interleave URLs across workers (not sequential chunks)
  const chunks = Array.from({ length: WORKERS }, () => []);
  allUrls.forEach((u, i) => chunks[i % WORKERS].push(u));

  process.stderr.write(`Per-worker counts: ${chunks.map(c => c.length).join(', ')}\n`);

  // Estimate runtime
  const totalDelay = 750; // ms avg per page
  const pagesPerWorker = Math.ceil(allUrls.length / WORKERS);
  const estMinutes = Math.ceil((pagesPerWorker * totalDelay) / 60000);
  process.stderr.write(`ETA: ~${estMinutes} min at avg ${totalDelay}ms/page × ${WORKERS} workers\n`);

  await Promise.all(chunks.map((urls, i) => worker(i + 1, urls)));
  writeStream.end();
  process.stderr.write('\nAll workers done.\n');
})();
