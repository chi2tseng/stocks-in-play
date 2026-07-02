// 直接讀「百名店」清單，scroll 全部 load → 逐個檢查 Google Place 狀態
// 對每個 saved item：
//   - 取 name + category + closed status
//   - 若 category 非餐廳 / 已閉店 → 點 list 旁的「移除」按鈕
//   - 若 name 完全找不到對應 Tabelog 名稱 (在 expected set 中) → flag for manual review
// 輸出 D:/Tabelog/list-audit.json (full inventory + actions taken)

const { chromium } = require('@playwright/test');
const fs = require('fs');

const PROFILE_DIR = 'D:/Tabelog/chrome-profile';
const LIST_URL    = 'https://maps.app.goo.gl/ZiXXGRDMi1pDFkqa7';
const OUT_JSON    = 'D:/Tabelog/list-audit.json';

const args = process.argv.slice(2);
const DRY_RUN = args.includes('--dry');

function log(msg) { process.stdout.write(`[${new Date().toISOString().slice(11,19)}] ${msg}\n`); }

(async () => {
  const ctx = await chromium.launchPersistentContext(PROFILE_DIR, {
    headless: false, viewport: { width: 1400, height: 900 }, locale: 'ja-JP',
    args: ['--disable-blink-features=AutomationControlled'],
  });
  const page = ctx.pages()[0] || await ctx.newPage();

  log('Opening 百名店 list...');
  await page.goto(LIST_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(5000);

  // count current items
  const initialCount = await page.evaluate(() => {
    const m = document.body.textContent.match(/(\d{1,5})\s*個地點/);
    return m ? parseInt(m[1], 10) : null;
  });
  log(`Current list size: ${initialCount}`);

  // find scroll container — Google Maps list panel uses div[role="feed"] or [aria-label="百名店"]
  log('Locating scroll container...');
  const findScrollHandle = async () => await page.evaluateHandle(() => {
    // candidates ordered by likelihood
    const candidates = [
      'div[role="feed"]',
      'div[aria-label*="百名店"]',
      'div[aria-label*="清單"]',
      'div[aria-label][tabindex]',
    ];
    for (const sel of candidates) {
      const els = document.querySelectorAll(sel);
      for (const el of els) {
        // pick element that has scrollable content
        if (el.scrollHeight > el.clientHeight + 100) return el;
      }
    }
    // fallback: largest scrollable in left half
    const all = document.querySelectorAll('div');
    let best = null, bestArea = 0;
    for (const el of all) {
      const r = el.getBoundingClientRect();
      if (r.left > 600) continue; // left panel only
      if (el.scrollHeight <= el.clientHeight + 50) continue;
      const area = r.width * r.height;
      if (area > bestArea) { bestArea = area; best = el; }
    }
    return best;
  });

  log('Scrolling to load all items...');
  let lastCount = 0, stableRounds = 0;
  for (let i = 0; i < 300; i++) {
    const handle = await findScrollHandle();
    await handle.evaluate(el => { if (el) el.scrollTop = el.scrollHeight; });
    await handle.dispose();
    await page.waitForTimeout(700);
    const count = await page.evaluate(() => {
      return document.querySelectorAll('a[href*="/maps/place/"]').length;
    });
    if (count === lastCount) {
      stableRounds++;
      if (stableRounds >= 5) break;
    } else {
      stableRounds = 0;
      lastCount = count;
    }
    if (i % 5 === 0) log(`  scroll ${i}: ${count} visible`);
  }

  // extract — robust pass
  const places = await page.evaluate(() => {
    const out = [];
    const seen = new Set();
    for (const a of document.querySelectorAll('a[href*="/maps/place/"]')) {
      const href = a.href.split('?')[0];
      if (!href.includes('/place/')) continue;
      if (seen.has(href)) continue;
      seen.add(href);
      // try various ways to get a clean name
      let name = a.getAttribute('aria-label') || '';
      if (!name || name.length < 2) {
        // climb up to find nearest title-like element
        let p = a;
        for (let i = 0; i < 4 && p && !name; i++) {
          const titleEl = p.querySelector('h3, [role="heading"], [class*="fontHeadlineSmall"]');
          if (titleEl) { name = titleEl.textContent.trim(); break; }
          p = p.parentElement;
        }
      }
      out.push({ href, name: name.trim().slice(0, 100) });
    }
    return out;
  });

  log(`Extracted ${places.length} places from list`);
  fs.writeFileSync(OUT_JSON, JSON.stringify({ initialCount, scraped: places.length, places }, null, 2));
  log(`→ ${OUT_JSON}`);

  await ctx.close();
})();
