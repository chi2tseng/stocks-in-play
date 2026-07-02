// v3: 用 keyboard Tab + Arrow 遍歷 list，每個 item 確實 read 一次
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

  // Click on the left list panel area to focus it
  await page.mouse.click(200, 400);
  await page.waitForTimeout(500);

  // collect items: scroll repeatedly + extract DOM each pass
  const allNames = new Map(); // key=name, val=positions seen
  let lastTotal = 0, stableCount = 0;

  for (let iter = 0; iter < 600; iter++) {
    // scroll panel via Page Down on focused list / mouse wheel
    await page.mouse.move(200, 450);
    await page.mouse.wheel(0, 700);
    await page.waitForTimeout(150);

    if (iter % 5 === 0) {
      // extract currently visible items
      const visible = await page.evaluate(() => {
        const out = [];
        const deleteBtns = document.querySelectorAll('button[aria-label="刪除"]');
        for (const btn of deleteBtns) {
          let row = btn;
          for (let i = 0; i < 8 && row.parentElement; i++) {
            row = row.parentElement;
            if (row.textContent.length > 50 && row.querySelector('img, span[role="img"]')) break;
          }
          const rect = row.getBoundingClientRect();
          // collect leaf text nodes
          const texts = [];
          const walker = document.createTreeWalker(row, NodeFilter.SHOW_TEXT);
          let n;
          while ((n = walker.nextNode())) {
            const t = n.textContent.trim();
            if (t.length >= 2 && t.length <= 80 && !/^\d+\.\d+$|^\(?\d+\)?$|^¥|^\$|^添加|^新增|^附註|^刪除|^地點|^永久|閉店/.test(t)) texts.push(t);
          }
          const closed = row.textContent.includes('永久閉店');
          out.push({ name: texts[0] || '?', alts: texts.slice(0, 3), closed, top: rect.top });
        }
        return out;
      });
      for (const v of visible) {
        if (!allNames.has(v.name) || allNames.get(v.name).top > v.top) {
          allNames.set(v.name, v);
        }
      }
      if (iter % 20 === 0) {
        if (allNames.size === lastTotal) {
          stableCount++;
          if (stableCount >= 6 && allNames.size >= target * 0.95) break;
          if (stableCount >= 30) break;
        } else {
          stableCount = 0;
          lastTotal = allNames.size;
        }
        log(`  iter ${iter}: unique=${allNames.size}/${target}`);
      }
    }
  }

  await page.screenshot({ path: 'D:/Tabelog/list-final.png' });
  log(`Total unique items collected: ${allNames.size}`);

  const items = [...allNames.values()];
  fs.writeFileSync(OUT_JSON, JSON.stringify({ target, collected: items.length, items }, null, 2));
  log(`→ ${OUT_JSON}`);
  await ctx.close();
})();
