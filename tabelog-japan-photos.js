// Scrape photo gallery per restaurant from Tabelog /dtlphotolst/
// 4 workers, restart browser every 40 pages, resume-able, append-only NDJSON
//
//   node tabelog-japan-photos.js [--workers N] [--batch N]

const { chromium } = require('@playwright/test');
const fs = require('fs');

const LISTINGS_JSON = 'D:/Tabelog/japan_listings.json';
const NDJSON_PATH   = 'D:/Tabelog/japan_photos.ndjson';
const WORKERS = (() => { const i = process.argv.indexOf('--workers'); return i >= 0 ? parseInt(process.argv[i+1],10) : 4; })();
const BATCH   = (() => { const i = process.argv.indexOf('--batch');   return i >= 0 ? parseInt(process.argv[i+1],10) : 40; })();

// Resume: only skip URLs with SUCCESSFUL fetches (retry errors)
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

// extractPhotos is inlined inside page.evaluate() calls below

async function fetchOne(page, baseUrl) {
  // Normalize base URL (ensure trailing slash)
  const base = baseUrl.replace(/\/?$/, '/');
  const galleryUrl = base + 'dtlphotolst/';
  try {
    await page.goto(galleryUrl, { waitUntil: 'domcontentloaded', timeout: 25000 });
    // Wait for photo list or no-photo indicator
    await page.waitForSelector('.rstdtl-photo-list__item, .rstdtl-photo__no-photo', { timeout: 8000 }).catch(() => null);
    await page.waitForTimeout(400 + Math.random() * 400);

    const photos = await page.evaluate(() => {
      return [...document.querySelectorAll('.rstdtl-photo-list__item')]
        .map(li => {
          const a   = li.querySelector('a.rstdtl-photo-list__target, a.js-imagebox-trigger');
          const img = li.querySelector('img.rstdtl-photo-list__img');
          if (!a || !img) return null;
          const href = a.getAttribute('href') || '';
          const src = href.includes('tblg.k-img.com') || href.includes('tabelog') || href.includes('k-img')
            ? href.replace(/\/\d+x\d+_/, '/640x640_')
            : (img.src || '');
          if (!src) return null;
          return { src, alt: (img.alt || '').trim() };
        })
        .filter(Boolean);
    });

    // If fewer than 10 photos on first page AND there's a second page, fetch page 2
    // (page 1 gives up to 20 items so we rarely need page 2, but handle edge case)
    if (photos.length < 10) {
      const hasPg2 = await page.evaluate(() => !!document.querySelector('a[href*="PG=2"]'));
      if (hasPg2) {
        const pg2url = galleryUrl + '?PG=2';
        await page.goto(pg2url, { waitUntil: 'domcontentloaded', timeout: 25000 });
        await page.waitForSelector('.rstdtl-photo-list__item, .rstdtl-photo__no-photo', { timeout: 8000 }).catch(() => null);
        await page.waitForTimeout(400 + Math.random() * 400);
        const pg2Photos = await page.evaluate(() => {
          return [...document.querySelectorAll('.rstdtl-photo-list__item')]
            .map(li => {
              const a   = li.querySelector('a.rstdtl-photo-list__target, a.js-imagebox-trigger');
              const img = li.querySelector('img.rstdtl-photo-list__img');
              if (!a || !img) return null;
              const href = a.getAttribute('href') || '';
              const src = href.includes('tblg.k-img.com') || href.includes('tabelog') || href.includes('k-img')
                ? href.replace(/\/\d+x\d+_/, '/640x640_')
                : (img.src || '');
              if (!src) return null;
              return { src, alt: (img.alt || '').trim() };
            })
            .filter(Boolean);
        });
        photos.push(...pg2Photos);
      }
    }

    // Deduplicate by src
    const seen = new Set();
    const unique = photos.filter(p => {
      if (seen.has(p.src)) return false;
      seen.add(p.src);
      return true;
    });

    return { photos: unique };
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

    // Progress log every 20 pages
    if (n % 20 === 0 || n === 1) {
      const photoCount = result.photos ? result.photos.length : 0;
      const errFlag = result.error ? ' [ERR]' : '';
      process.stderr.write(`[W${workerId} ${n}/${urls.length}] ${photoCount} photos${errFlag} — ${url.slice(30, 70)}\n`);
    }

    // 800–1200ms random delay between requests
    await page.waitForTimeout(800 + Math.random() * 400);
  }

  if (browser) { try { await browser.close(); } catch {} }
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

  await Promise.all(chunks.map((urls, i) => worker(i + 1, urls)));
  writeStream.end();
  process.stderr.write('\nDone.\n');
})();
