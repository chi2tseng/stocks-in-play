const { chromium } = require('@playwright/test');
const fs = require('fs');

(async () => {
  const ctx = await chromium.launchPersistentContext('D:/Tabelog/chrome-profile', {
    headless: false, viewport: { width: 1400, height: 900 }, locale: 'ja-JP',
    args: ['--disable-blink-features=AutomationControlled'],
  });
  const page = ctx.pages()[0] || await ctx.newPage();
  await page.goto('https://maps.app.goo.gl/ZiXXGRDMi1pDFkqa7', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(10000); // wait long

  await page.screenshot({ path: 'D:/Tabelog/list-debug.png', fullPage: false });

  const info = await page.evaluate(() => {
    const out = {
      url: location.href,
      title: document.title,
      placeAnchors: document.querySelectorAll('a[href*="/maps/place/"]').length,
      jsactionPlace: document.querySelectorAll('[jsaction*="placeCard"], [jsaction*="open"]').length,
      // dump all aria-labels in the left panel
      leftPanelLabels: [],
      dataResultIndex: document.querySelectorAll('[data-result-index]').length,
      buttonsWithJsaction: document.querySelectorAll('button[jsaction], div[jsaction][role="button"]').length,
    };
    const main = document.querySelector('[role="main"]');
    if (main) {
      // grab buttons/articles with aria-label
      const items = main.querySelectorAll('[aria-label]');
      const seen = new Set();
      for (const el of items) {
        const lbl = el.getAttribute('aria-label');
        if (!lbl || lbl.length < 2 || seen.has(lbl)) continue;
        seen.add(lbl);
        if (out.leftPanelLabels.length < 30) out.leftPanelLabels.push({ label: lbl.slice(0, 40), tag: el.tagName, role: el.getAttribute('role') });
      }
    }
    return out;
  });
  console.log(JSON.stringify(info, null, 2));

  // try scrolling main + check
  for (let i = 0; i < 5; i++) {
    await page.evaluate(() => {
      const m = document.querySelector('[role="main"]');
      if (m) m.scrollBy(0, 800);
    });
    await page.waitForTimeout(500);
  }
  // extract items using delete-button as anchor
  const items = await page.evaluate(() => {
    const out = [];
    const deleteBtns = document.querySelectorAll('button[aria-label="刪除"]');
    for (const btn of deleteBtns) {
      // walk up to find the row container
      let row = btn;
      for (let i = 0; i < 8 && row.parentElement; i++) {
        row = row.parentElement;
        // check if this container has more substance (image + name + rating)
        if (row.textContent.length > 50 && row.querySelector('img, span[role="img"]')) break;
      }
      // extract the name — typically the largest text element in the row
      const candidates = [...row.querySelectorAll('div, span')]
        .filter(e => e.children.length === 0 && e.textContent.trim().length > 2 && e.textContent.trim().length < 60)
        .filter(e => !/^\d+\.\d+$|^\(?\d+\)?$|^\¥|^\$|^添加|^新增/.test(e.textContent.trim()));
      const name = candidates.length > 0 ? candidates[0].textContent.trim() : '?';
      out.push({ name, rect: btn.getBoundingClientRect() });
    }
    return { count: deleteBtns.length, sample: out.slice(0, 12) };
  });
  console.log('Items via delete-btn:', JSON.stringify(items, null, 2));

  await page.waitForTimeout(3000);
  await ctx.close();
})();
