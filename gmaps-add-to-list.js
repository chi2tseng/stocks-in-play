// Playwright: 把百名店清單加入 Google Maps Saved List「百名店」
// 用 persistent context 維持 Google 登入
//
// First run (login):
//   node gmaps-add-to-list.js --login
//   → 打開瀏覽器，手動登入 Google + 確認看到 Google Maps
//   → 按 Enter 關閉，cookies 存進 PROFILE_DIR
//
// Test run (1 restaurant only):
//   node gmaps-add-to-list.js --test
//
// Full run:
//   node gmaps-add-to-list.js
//   node gmaps-add-to-list.js --start 5    # 從第 5 家開始
//   node gmaps-add-to-list.js --limit 10   # 只跑 10 家

const { chromium } = require('@playwright/test');
const fs = require('fs');
const readline = require('readline');

const PROFILE_DIR    = 'D:/Tabelog/chrome-profile';
const DETAILS_JSON   = 'D:/Tabelog/details.json';
const PROGRESS_JSON  = 'D:/Tabelog/gmaps-progress.json';

const args = process.argv.slice(2);
const LOGIN_ONLY = args.includes('--login');
const TEST       = args.includes('--test');
const START_IDX  = (() => { const i = args.indexOf('--start'); return i >= 0 ? parseInt(args[i+1], 10) : 0; })();
const LIMIT      = (() => { const i = args.indexOf('--limit'); return i >= 0 ? parseInt(args[i+1], 10) : Infinity; })();

function ask(q) {
  return new Promise(r => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    rl.question(q, ans => { rl.close(); r(ans); });
  });
}

function log(msg) { process.stdout.write(`[${new Date().toISOString().slice(11,19)}] ${msg}\n`); }

(async () => {
  const ctx = await chromium.launchPersistentContext(PROFILE_DIR, {
    headless: false,
    viewport: { width: 1400, height: 900 },
    locale: 'ja-JP',
    args: ['--disable-blink-features=AutomationControlled'],
  });

  const page = ctx.pages()[0] || await ctx.newPage();

  // ── login-only mode ─────────────────────────────────────────────
  if (LOGIN_ONLY) {
    await page.goto('https://www.google.com/maps');
    log('在瀏覽器中登入 Google + 確認看到 Google Maps');
    log('完成後按 Enter，cookies 會存進 ' + PROFILE_DIR);
    await ask('> ');
    await ctx.close();
    return;
  }

  // ── verify login ────────────────────────────────────────────────
  await page.goto('https://www.google.com/maps');
  await page.waitForTimeout(2500);
  const loggedIn = await page.evaluate(() => {
    return !!document.querySelector('a[href*="accounts.google.com/SignOutOptions"], [aria-label*="Google 帳戶"]');
  });
  if (!loggedIn) {
    log('❌ 未登入。請先跑: node gmaps-add-to-list.js --login');
    await ctx.close();
    return;
  }
  log('✅ 登入確認');

  // ── load CSV / progress ─────────────────────────────────────────
  const details = JSON.parse(fs.readFileSync(DETAILS_JSON, 'utf-8'));
  const filtered = details.filter(d => {
    if (d.dinnerLower !== null) return d.dinnerLower < 6000;
    if (d.lunchLower !== null) return d.lunchLower < 6000;
    return true;
  });

  let progress = { done: [], failed: [] };
  if (fs.existsSync(PROGRESS_JSON)) {
    progress = JSON.parse(fs.readFileSync(PROGRESS_JSON, 'utf-8'));
  }
  const doneSet = new Set(progress.done);

  const targets = TEST ? filtered.slice(0, 1) : filtered.slice(START_IDX, START_IDX + LIMIT);
  log(`Target: ${targets.length} 家 (filtered total ${filtered.length}, START=${START_IDX}, done=${doneSet.size})`);

  // ── main loop ───────────────────────────────────────────────────
  for (let i = 0; i < targets.length; i++) {
    const r = targets[i];
    if (doneSet.has(r.url)) { log(`[${i+1}/${targets.length}] SKIP (done) ${r.name}`); continue; }

    const query = encodeURIComponent(`${r.name} ${r.addr || ''}`);
    const url = `https://www.google.com/maps/search/?api=1&query=${query}`;
    log(`[${i+1}/${targets.length}] ${r.name}`);

    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 25000 });
      await page.waitForTimeout(4500); // allow time for redirect to place page

      // If we landed on a search results page, click the first result to drill into place
      const firstResult = page.locator('a[href*="/maps/place/"]').first();
      if (await firstResult.isVisible({ timeout: 1500 }).catch(() => false)) {
        const onPlace = page.url().includes('/maps/place/');
        if (!onPlace) {
          await firstResult.click();
          await page.waitForTimeout(2500);
        }
      }

      // try a sequence of selectors for the Save button (handles 繁中/簡中/日/英 + aria variants)
      let saveBtn = null;
      const saveCandidates = [
        () => page.getByRole('button', { name: /^儲存$|^保存$|^保存する$|^Save$/ }).first(),
        () => page.locator('button[data-value="Save"]').first(),
        () => page.locator('button[aria-label*="儲存"], button[aria-label*="保存"], button[aria-label*="Save"]').first(),
      ];
      for (const cand of saveCandidates) {
        const b = cand();
        if (await b.isVisible({ timeout: 2500 }).catch(() => false)) { saveBtn = b; break; }
      }
      if (!saveBtn) throw new Error('Save button not found on place page');

      await saveBtn.click();
      await page.waitForTimeout(900);

      // try to find 百名店 option in popup. Could be:
      //  - radio in list dialog
      //  - listitem
      //  - menuitem
      let hyakuOpt = page.getByRole('menuitemcheckbox', { name: /百名店/ }).first();
      if (!(await hyakuOpt.isVisible().catch(() => false))) {
        hyakuOpt = page.getByRole('menuitemradio', { name: /百名店/ }).first();
      }
      if (!(await hyakuOpt.isVisible().catch(() => false))) {
        hyakuOpt = page.getByRole('listitem').filter({ hasText: '百名店' }).first();
      }
      if (!(await hyakuOpt.isVisible().catch(() => false))) {
        hyakuOpt = page.getByText('百名店', { exact: false }).first();
      }
      await hyakuOpt.waitFor({ state: 'visible', timeout: 5000 });

      // CRITICAL: check if already in list (aria-checked=true) → skip to avoid toggle-removal
      const ariaChecked = await hyakuOpt.getAttribute('aria-checked').catch(() => null);
      if (ariaChecked === 'true') {
        log(`  ⊙ already in 百名店, skip`);
        // close dialog without modifying state — press Escape
        await page.keyboard.press('Escape');
        await page.waitForTimeout(400);
        progress.done.push(r.url);
        fs.writeFileSync(PROGRESS_JSON, JSON.stringify(progress, null, 2));
        await page.waitForTimeout(1000 + Math.random() * 800);
        continue;
      }

      await hyakuOpt.click();
      await page.waitForTimeout(700);

      // close dialog if "完了" / "Done" button appears
      const doneBtn = page.getByRole('button', { name: /^完了$|^Done$|^完成$/ }).first();
      if (await doneBtn.isVisible().catch(() => false)) {
        await doneBtn.click();
        await page.waitForTimeout(400);
      }

      progress.done.push(r.url);
      log(`  ✓ saved`);
    } catch (err) {
      log(`  ✗ ${err.message.slice(0, 80)}`);
      progress.failed.push({ url: r.url, name: r.name, error: err.message.slice(0, 100) });
      // save diagnostic screenshot
      try {
        const fname = `D:/Tabelog/fail_${i+1}_${(r.name||'x').replace(/[^a-z0-9　-鿿]/gi,'_').slice(0,20)}.png`;
        await page.screenshot({ path: fname, fullPage: false });
        log(`    [screenshot] ${fname}`);
      } catch {}
    }

    fs.writeFileSync(PROGRESS_JSON, JSON.stringify(progress, null, 2));
    await page.waitForTimeout(1200 + Math.random() * 1000);
  }

  log(`\nDone. ✓ ${progress.done.length}  ✗ ${progress.failed.length}`);
  log('progress saved → ' + PROGRESS_JSON);

  if (TEST) {
    await ask('Test 結束。觀察結果後按 Enter 關閉 > ');
  }
  await ctx.close();
})();
