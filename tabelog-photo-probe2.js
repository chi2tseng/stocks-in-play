// Probe 2: inspect li structure for category + alt details
const { chromium } = require('@playwright/test');

const PROBE_URL = 'https://tabelog.com/fukuoka/A4001/A400103/40040601/dtlphotolst/';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    locale: 'ja-JP',
    viewport: { width: 1280, height: 900 },
  });
  const page = await ctx.newPage();
  await page.goto(PROBE_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(2000);

  const result = await page.evaluate(() => {
    // Dump first 3 li items in full
    const items = [...document.querySelectorAll('.rstdtl-photo-list li')].slice(0, 5);
    const liDumps = items.map(li => li.outerHTML.slice(0, 600));

    // Count total photos
    const total = document.querySelectorAll('.rstdtl-photo-list li').length;

    // Extract all photos as we plan to do in main script
    const photos = [...document.querySelectorAll('.rstdtl-photo-list li')].map(li => {
      const img = li.querySelector('img.rstdtl-photo-list__img');
      const a = li.querySelector('a.rstdtl-photo-list__img-wrap');
      const caption = li.querySelector('.rstdtl-photo-list__caption, .rstdtl-photo-list__category, [class*="caption"], [class*="category"]');
      if (!img) return null;
      // prefer 640x640 from anchor href, fallback to img src; then upgrade to larger
      const thumb = img.src || '';
      const larger = a?.href || thumb;
      const fullSize = larger.replace(/\/\d+x\d+_/, '/original_');
      return {
        src: larger,  // 640x640
        thumb,
        fullAttempt: fullSize,
        alt: img.alt || '',
        caption: caption?.textContent.trim() || '',
        liClass: li.className,
      };
    }).filter(Boolean);

    // Check for pagination
    const pagination = document.querySelector('.c-pagination, .rstdtl-photo__pagenation, [class*="paginat"]');
    const paginationHTML = pagination ? pagination.outerHTML.slice(0, 400) : null;

    // Check category tabs
    const tabs = [...document.querySelectorAll('#phototype-change li, .rstdtl-photo__tab li')].map(t => t.textContent.trim());

    return { total, liDumps, photos: photos.slice(0, 5), allPhotos: photos.length, paginationHTML, tabs };
  });

  console.log('Total li items:', result.total);
  console.log('Photos extracted:', result.allPhotos);
  console.log('\n=== TABS ===', result.tabs);
  console.log('\n=== PAGINATION ===', result.paginationHTML);
  console.log('\n=== FIRST LI DUMPS ===');
  result.liDumps.forEach((h, i) => { console.log(`\n--- LI ${i} ---`); console.log(h); });
  console.log('\n=== FIRST 5 PHOTOS ===');
  result.photos.forEach((p, i) => console.log(i, JSON.stringify(p)));

  await browser.close();
})();
