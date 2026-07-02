// Probe script: find photo gallery selectors on Tabelog dtlphotolst page
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

  console.log('Navigating to:', PROBE_URL);
  await page.goto(PROBE_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(3000);

  const result = await page.evaluate(() => {
    // Dump page title + body snippet
    const title = document.title;
    const bodySnippet = document.body.innerHTML.slice(0, 500);

    // Try various selectors for photo containers
    const selectors = [
      '.rstdtl-photo-list__item',
      '.rstdtl-photo-list li',
      '.rstdtl-top-photo',
      '.js-rstdtl-photo-list-item',
      '.p-photo',
      '.thum-photo',
      '[class*="photo"]',
      '.js-photo-box',
      '.photo-list',
      '.photo-list__item',
    ];

    const selectorHits = {};
    for (const sel of selectors) {
      const els = document.querySelectorAll(sel);
      if (els.length > 0) selectorHits[sel] = els.length;
    }

    // Find all img tags and sample their attributes
    const imgs = [...document.querySelectorAll('img')].map(img => ({
      src: img.src || '',
      dataSrc: img.getAttribute('data-src') || '',
      dataOriginal: img.getAttribute('data-original') || '',
      alt: img.alt || '',
      className: img.className || '',
      parentClass: img.parentElement?.className || '',
    })).filter(i =>
      i.src.includes('tabelog') || i.src.includes('tblg') || i.src.includes('k-img') ||
      i.dataSrc.includes('tabelog') || i.dataSrc.includes('tblg') || i.dataSrc.includes('k-img') ||
      i.dataOriginal.includes('tabelog') || i.dataOriginal.includes('tblg') || i.dataOriginal.includes('k-img')
    ).slice(0, 30);

    // Find all anchor tags containing images with tabelog CDN
    const anchors = [...document.querySelectorAll('a[href*="dtlphotolst"] img, a img')].slice(0, 10).map(img => ({
      src: img.src,
      dataSrc: img.getAttribute('data-src') || '',
      href: img.closest('a')?.href || '',
      parentClass: img.parentElement?.className || '',
    }));

    // Look for lazy-load patterns: any element with data-src/data-original containing CDN
    const lazyEls = [...document.querySelectorAll('[data-src],[data-original]')]
      .filter(el => {
        const v = el.getAttribute('data-src') || el.getAttribute('data-original') || '';
        return v.includes('tblg') || v.includes('tabelog') || v.includes('k-img');
      })
      .slice(0, 20)
      .map(el => ({
        tag: el.tagName,
        dataSrc: el.getAttribute('data-src') || '',
        dataOriginal: el.getAttribute('data-original') || '',
        className: el.className,
      }));

    // Dump classes from first 5 photo-ish elements
    const photoishEls = [...document.querySelectorAll('[class*="photo"]')].slice(0, 5).map(el => ({
      tag: el.tagName,
      className: el.className,
      outerHTML: el.outerHTML.slice(0, 300),
    }));

    return { title, bodySnippet, selectorHits, imgs, anchors, lazyEls, photoishEls };
  });

  console.log('\n=== PAGE TITLE ===');
  console.log(result.title);

  console.log('\n=== BODY SNIPPET ===');
  console.log(result.bodySnippet.slice(0, 300));

  console.log('\n=== SELECTOR HITS ===');
  console.log(JSON.stringify(result.selectorHits, null, 2));

  console.log('\n=== IMG TAGS (tabelog CDN) ===');
  result.imgs.forEach((img, i) => console.log(i, JSON.stringify(img)));

  console.log('\n=== LAZY-LOAD ELEMENTS ===');
  result.lazyEls.forEach((el, i) => console.log(i, JSON.stringify(el)));

  console.log('\n=== PHOTO-ISH ELEMENTS ===');
  result.photoishEls.forEach((el, i) => {
    console.log(i, el.tag, el.className);
    console.log('   HTML:', el.outerHTML);
  });

  console.log('\n=== ANCHOR+IMG ===');
  result.anchors.forEach((a, i) => console.log(i, JSON.stringify(a)));

  await browser.close();
})();
