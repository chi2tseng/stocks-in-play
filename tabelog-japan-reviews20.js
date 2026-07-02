// Scrape 20+ reviews per restaurant from /dtlrvwlst/ page
// 4 workers, restart browser every 40 pages, resume-able, append-only NDJSON

const { chromium } = require('@playwright/test');
const fs = require('fs');

const LISTINGS_JSON = 'D:/Tabelog/japan_listings.json';
const NDJSON_PATH   = 'D:/Tabelog/japan_reviews20.ndjson';
const WORKERS  = (() => { const i = process.argv.indexOf('--workers'); return i >= 0 ? parseInt(process.argv[i+1],10) : 4; })();
const BATCH    = (() => { const i = process.argv.indexOf('--batch');   return i >= 0 ? parseInt(process.argv[i+1],10) : 40; })();
const TARGET   = 20; // min reviews we want

// Load already-done URLs (skip successful ones, retry errors)
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

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function extractReviews(page) {
  return page.evaluate(() => {
    const items = [...document.querySelectorAll('.rvw-item')];
    return items.map(rv => {
      const title = rv.querySelector('.rvw-item__title')?.textContent.trim().slice(0, 120) || '';
      const body  = rv.querySelector('.rvw-item__rvw-comment, .rvw-item__catch-review, .rvw-item__rvw-body')
                      ?.textContent.replace(/\s+/g, ' ').trim().slice(0, 400) || '';
      // Rating: strong val inside .rvw-item__ratings
      const ratingEl = rv.querySelector('.rvw-item__ratings b.c-rating-v3__val, .rvw-item__ratings .c-rating-v3__val--strong, .rvw-item__ratings .c-rating-v3__val');
      const rating = ratingEl ? ratingEl.textContent.trim() : '';
      const dateEl = rv.querySelector('.rvw-item__date');
      const date   = dateEl ? dateEl.textContent.trim().slice(0, 40) : '';
      return { title, body, rating, date };
    }).filter(r => r.body || r.title);
  });
}

async function fetchOne(page, baseUrl) {
  const cleanBase = baseUrl.replace(/\/?$/, '/');
  const url1 = cleanBase + 'dtlrvwlst/';

  try {
    await page.goto(url1, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForSelector('.rvw-item', { timeout: 8000 }).catch(() => null);
    await sleep(300 + Math.random() * 200);

    let reviews = await extractReviews(page);

    // If page 1 has fewer than TARGET, try page 2
    if (reviews.length > 0 && reviews.length < TARGET) {
      const url2 = cleanBase + 'dtlrvwlst/COND-2/smp1/?lc=2&rvw_part=all&PG=2';
      try {
        await page.goto(url2, { waitUntil: 'domcontentloaded', timeout: 25000 });
        await page.waitForSelector('.rvw-item', { timeout: 8000 }).catch(() => null);
        await sleep(300 + Math.random() * 200);
        const more = await extractReviews(page);
        // merge, dedupe by body snippet
        const seen = new Set(reviews.map(r => r.body.slice(0, 50)));
        for (const r of more) {
          if (!seen.has(r.body.slice(0, 50))) { reviews.push(r); seen.add(r.body.slice(0, 50)); }
        }
      } catch (_) { /* page 2 optional */ }
    }

    if (reviews.length === 0) {
      // Check if it's a "no reviews" page vs a block
      const text = await page.evaluate(() => document.body.innerText.slice(0, 200));
      return { error: 'no_reviews: ' + text.replace(/\n/g, ' ').slice(0, 80) };
    }

    return { reviews };
  } catch (err) {
    return { error: err.message.slice(0, 100) };
  }
}

async function worker(workerId, urls) {
  let n = 0;
  let browser = null, page = null;
  let successCount = 0, errorCount = 0;

  async function fresh() {
    if (browser) try { await browser.close(); } catch {}
    browser = await chromium.launch({ headless: true });
    const ctx = await browser.newContext({
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
      locale: 'ja-JP',
      viewport: { width: 1280, height: 900 },
      extraHTTPHeaders: { 'Accept-Language': 'ja-JP,ja;q=0.9,en;q=0.8' },
    });
    page = await ctx.newPage();
  }

  await fresh();

  for (const url of urls) {
    n++;
    if (n > 1 && (n - 1) % BATCH === 0) {
      process.stderr.write(`[W${workerId}] restart at page ${n}\n`);
      await fresh();
    }

    const d = await fetchOne(page, url);
    append(url, d);

    if (d.error) {
      errorCount++;
    } else {
      successCount++;
    }

    // Log every 10 URLs per worker
    if (n % 10 === 0 || n === 1) {
      const rc = d.reviews ? d.reviews.length : 0;
      const tag = d.error ? `[ERR: ${d.error.slice(0,40)}]` : `[${rc} reviews]`;
      process.stderr.write(`[W${workerId} ${n}/${urls.length}] ok=${successCount} err=${errorCount} last=${tag}\n`);
    }

    // Random delay 800-1200ms
    await sleep(800 + Math.random() * 400);
  }

  if (browser) try { await browser.close(); } catch {}
  process.stderr.write(`[W${workerId}] DONE: ${successCount} ok, ${errorCount} errors\n`);
}

(async () => {
  const listings = JSON.parse(fs.readFileSync(LISTINGS_JSON, 'utf-8'));
  const allUrls = Object.keys(listings).filter(u => !fetched.has(u));
  process.stderr.write(`Listings: ${Object.keys(listings).length} total, ${fetched.size} cached, ${allUrls.length} todo | workers=${WORKERS} batch=${BATCH}\n`);

  if (allUrls.length === 0) {
    writeStream.end();
    process.stderr.write('Nothing to do.\n');
    return;
  }

  // Distribute round-robin across workers
  const chunks = Array.from({ length: WORKERS }, () => []);
  allUrls.forEach((u, i) => chunks[i % WORKERS].push(u));

  await Promise.all(chunks.map((urls, i) => worker(i + 1, urls)));
  writeStream.end();
  process.stderr.write('\nAll workers done.\n');
})();
