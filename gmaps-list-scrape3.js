// v4: scrollIntoView 配合 virtual list
const { chromium } = require('@playwright/test');
const fs = require('fs');

const PROFILE_DIR = 'D:/Tabelog/chrome-profile';
const LIST_URL    = 'https://maps.app.goo.gl/ZiXXGRDMi1pDFkqa7';
const OUT_JSON    = 'D:/Tabelog/list-inventory.json';

function log(msg) { process.stdout.write(`[${new Date().toISOString().slice(11,19)}] ${msg}\n`); }

(async () => {
  const ctx = await chromium.launchPersistentContext(PROFILE_DIR, {
    headless: false, viewport: { width: 1400, height: 900 }, locale: 'ja-JP',
    args: ['--disable-blink-features=AutomationControlled'],
  });
  const page = ctx.pages()[0] || await ctx.newPage();
  log('Opening list...');
  await page.goto(LIST_URL, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(8000);

  const target = await page.evaluate(() => {
    const m = document.body.textContent.match(/(\d{1,5})\s*個地點/);
    return m ? parseInt(m[1], 10) : 0;
  });
  log(`Target: ${target}`);

  // collect via repeated scrollIntoView on last
  const allItems = new Map();
  let stable = 0, lastSize = 0;

  for (let iter = 0; iter < 1000; iter++) {
    // extract current visible + scroll last into view
    const r = await page.evaluate(() => {
      const out = [];
      const deleteBtns = [...document.querySelectorAll('button[aria-label="刪除"]')];
      for (const btn of deleteBtns) {
        let row = btn;
        for (let i = 0; i < 8 && row.parentElement; i++) {
          row = row.parentElement;
          if (row.textContent.length > 50 && row.querySelector('img, span[role="img"]')) break;
        }
        const texts = [];
        const walker = document.createTreeWalker(row, NodeFilter.SHOW_TEXT);
        let n;
        while ((n = walker.nextNode())) {
          const t = n.textContent.trim();
          if (t.length >= 2 && t.length <= 100 && !/^\d+\.\d+$|^\(?\d+\)?$|^¥|^\$|^添加|^新增|^附註$|^刪除$|^地點|^永久|閉店/.test(t)) texts.push(t);
        }
        out.push({ name: texts[0] || '?', alts: texts.slice(0,3), closed: row.textContent.includes('永久閉店'), top: row.getBoundingClientRect().top });
      }
      // scroll last delete-btn into view at top of viewport
      if (deleteBtns.length > 0) {
        deleteBtns[deleteBtns.length - 1].scrollIntoView({ behavior: 'auto', block: 'start' });
      }
      return out;
    });
    for (const v of r) if (!allItems.has(v.name)) allItems.set(v.name, v);

    await page.waitForTimeout(400);

    if (iter % 5 === 0) {
      if (allItems.size === lastSize) {
        stable++;
        if (stable >= 10) break;
      } else {
        stable = 0;
        lastSize = allItems.size;
      }
      if (iter % 25 === 0) log(`  iter ${iter}: unique=${allItems.size}/${target}`);
    }
  }

  await page.screenshot({ path: 'D:/Tabelog/list-final.png' });
  log(`Total: ${allItems.size}`);
  fs.writeFileSync(OUT_JSON, JSON.stringify({ target, collected: allItems.size, items: [...allItems.values()] }, null, 2));
  log(`→ ${OUT_JSON}`);
  await ctx.close();
})();
