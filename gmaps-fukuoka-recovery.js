// 修復用：單 worker 順序重跑福岡 233 家，補回被 race condition 移除的
// aria-checked 安全 → 已在清單跳過 / 不在清單才加
const { chromium } = require('@playwright/test');
const fs = require('fs');

const PROFILE_DIR = 'D:/Tabelog/chrome-profile';
const LISTINGS   = 'D:/Tabelog/fukuoka_recovery.json';
const PROGRESS   = 'D:/Tabelog/fukuoka-recovery-progress.json';

const PREF_MAP = { fukuoka: '福岡' };

function log(msg) { process.stdout.write(`[${new Date().toISOString().slice(11,19)}] ${msg}\n`); }

(async () => {
  const data = JSON.parse(fs.readFileSync(LISTINGS, 'utf-8'));
  const entries = Object.entries(data);
  let progress = { done: [], skip: [], failed: [], added: [] };
  if (fs.existsSync(PROGRESS)) progress = JSON.parse(fs.readFileSync(PROGRESS, 'utf-8'));
  const doneSet = new Set(progress.done);
  log(`Total ${entries.length}, already done ${doneSet.size}`);

  const ctx = await chromium.launchPersistentContext(PROFILE_DIR, {
    headless: false, viewport: { width: 1400, height: 900 }, locale: 'ja-JP',
    args: ['--disable-blink-features=AutomationControlled'],
  });
  const page = ctx.pages()[0] || await ctx.newPage();
  await page.goto('https://www.google.com/maps'); await page.waitForTimeout(2500);
  const loggedIn = await page.evaluate(() => !!document.querySelector('a[href*="accounts.google.com/SignOutOptions"]'));
  if (!loggedIn) { log('❌ 未登入'); await ctx.close(); return; }
  log('✅ 登入確認');

  let i = 0;
  for (const [url, rec] of entries) {
    i++;
    if (doneSet.has(url)) continue;
    const q = encodeURIComponent(`${rec.name} 福岡`);
    const gmurl = `https://www.google.com/maps/search/?api=1&query=${q}`;
    log(`[${i}/${entries.length}] ${rec.name}`);
    try {
      await page.goto(gmurl, { waitUntil: 'domcontentloaded', timeout: 25000 });
      await page.waitForTimeout(4500);
      const firstResult = page.locator('a[href*="/maps/place/"]').first();
      const onPlace = page.url().includes('/maps/place/');
      if (!onPlace && await firstResult.isVisible({ timeout: 1500 }).catch(()=>false)) {
        await firstResult.click(); await page.waitForTimeout(2000);
      }
      const saveBtn = page.getByRole('button', { name: /^儲存$|^保存$|^Save$/ }).first();
      await saveBtn.waitFor({ state: 'visible', timeout: 8000 });
      await saveBtn.click(); await page.waitForTimeout(900);

      // ── EXTRA SAFETY: wait for popup to render & aria-checked to settle ──
      let hyakuOpt = page.getByRole('menuitemcheckbox', { name: /百名店/ }).first();
      if (!(await hyakuOpt.isVisible({ timeout: 2000 }).catch(()=>false))) {
        hyakuOpt = page.getByRole('menuitemradio', { name: /百名店/ }).first();
      }
      await hyakuOpt.waitFor({ state: 'visible', timeout: 5000 });
      await page.waitForTimeout(600); // let aria-checked settle

      // re-read aria-checked TWICE to confirm
      const c1 = await hyakuOpt.getAttribute('aria-checked').catch(()=>null);
      await page.waitForTimeout(300);
      const c2 = await hyakuOpt.getAttribute('aria-checked').catch(()=>null);

      if (c1 === 'true' || c2 === 'true') {
        log(`  ⊙ already in 百名店, skip`);
        await page.keyboard.press('Escape');
        progress.skip.push(url);
      } else if (c1 === 'false' && c2 === 'false') {
        await hyakuOpt.click();
        log(`  ✓ ADDED (was missing)`);
        progress.added.push(url);
        await page.waitForTimeout(500);
      } else {
        // ambiguous state — DO NOT click (avoid toggle damage)
        log(`  ⚠ aria-checked ambiguous (c1=${c1} c2=${c2}), SKIP to be safe`);
        await page.keyboard.press('Escape');
        progress.failed.push({ url, name: rec.name, reason: 'ambiguous aria-checked' });
      }
      progress.done.push(url);
    } catch (err) {
      log(`  ✗ ${err.message.slice(0, 60)}`);
      progress.failed.push({ url, name: rec.name, error: err.message.slice(0, 100) });
    }
    if (i % 10 === 0) fs.writeFileSync(PROGRESS, JSON.stringify(progress, null, 2));
    await page.waitForTimeout(900 + Math.random() * 500);
  }
  fs.writeFileSync(PROGRESS, JSON.stringify(progress, null, 2));
  log(`\nDone. added=${progress.added.length} skip=${progress.skip.length} failed=${progress.failed.length}`);
  await ctx.close();
})();
