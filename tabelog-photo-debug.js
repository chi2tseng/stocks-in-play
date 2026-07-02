// Quick debug: test first URL from listings
const { chromium } = require('@playwright/test');
const fs = require('fs');

const LISTINGS_JSON = 'D:/Tabelog/japan_listings.json';
const listings = JSON.parse(fs.readFileSync(LISTINGS_JSON, 'utf-8'));
const urls = Object.keys(listings).slice(0, 3);
console.log('Testing URLs:', urls);

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    locale: 'ja-JP',
    viewport: { width: 1280, height: 900 },
  });
  const page = await ctx.newPage();

  for (const baseUrl of urls) {
    const base = baseUrl.replace(/\/?$/, '/');
    const galleryUrl = base + 'dtlphotolst/';
    console.log('\nTrying:', galleryUrl);
    try {
      const resp = await page.goto(galleryUrl, { waitUntil: 'domcontentloaded', timeout: 25000 });
      console.log('Status:', resp?.status());
      await page.waitForTimeout(1500);
      const title = await page.title();
      const count = await page.$$eval('.rstdtl-photo-list__item', els => els.length).catch(() => 0);
      console.log('Title:', title);
      console.log('Photo items:', count);
    } catch (err) {
      console.log('ERROR:', err.message.slice(0, 200));
    }
  }
  await browser.close();
})();
