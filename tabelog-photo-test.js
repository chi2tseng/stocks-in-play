// Quick test of the fixed fetchOne logic on 2 known-good URLs
const { chromium } = require('@playwright/test');

const TEST_URLS = [
  'https://tabelog.com/fukuoka/A4001/A400103/40040601/',
  'https://tabelog.com/kagoshima/A4601/A460101/46000812/',
];

async function fetchOne(page, baseUrl) {
  const base = baseUrl.replace(/\/?$/, '/');
  const galleryUrl = base + 'dtlphotolst/';
  try {
    await page.goto(galleryUrl, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForSelector('.rstdtl-photo-list__item, .rstdtl-photo__no-photo', { timeout: 8000 }).catch(() => null);
    await page.waitForTimeout(600);

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

    return { photos };
  } catch (err) {
    return { error: err.message.slice(0, 120) };
  }
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    locale: 'ja-JP',
    viewport: { width: 1280, height: 900 },
  });
  const page = await ctx.newPage();
  for (const url of TEST_URLS) {
    const result = await fetchOne(page, url);
    if (result.error) {
      console.log('ERROR:', result.error);
    } else {
      console.log(`OK: ${result.photos.length} photos from ${url}`);
      result.photos.slice(0, 3).forEach((p, i) => console.log(`  ${i}: ${p.src}`));
    }
  }
  await browser.close();
})();
