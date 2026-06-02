// Playwright: 把 japan_listings.json 12,280 家全部加進「百名店」單一清單
//   node gmaps-japan-single.js --test      # 只跑 1 家驗證
//   node gmaps-japan-single.js --start 100 # resume
//   node gmaps-japan-single.js             # 全跑

const { chromium } = require('@playwright/test');
const fs = require('fs');
const readline = require('readline');

const PROFILE_DIR    = 'D:/Tabelog/chrome-profile';
const LISTINGS_JSON  = 'D:/Tabelog/japan_listings.json';
const PROGRESS_JSON  = 'D:/Tabelog/japan-gmaps-progress.json';

const args = process.argv.slice(2);
const TEST = args.includes('--test');
const START_IDX = (() => { const i = args.indexOf('--start'); return i >= 0 ? parseInt(args[i+1], 10) : 0; })();
const LIMIT = (() => { const i = args.indexOf('--limit'); return i >= 0 ? parseInt(args[i+1], 10) : Infinity; })();

const PREF_MAP = {
  tokyo: '東京', osaka: '大阪', aichi: '愛知', kanagawa: '神奈川', kyoto: '京都',
  hokkaido: '北海道', hyogo: '兵庫', fukuoka: '福岡', saitama: '埼玉', chiba: '千葉',
  hiroshima: '広島', kagawa: '香川', shizuoka: '静岡', gifu: '岐阜', nagano: '長野',
  miyagi: '宮城', okinawa: '沖縄', ishikawa: '石川', miyazaki: '宮崎', nara: '奈良',
  mie: '三重', ibaraki: '茨城', tochigi: '栃木', niigata: '新潟', kumamoto: '熊本',
  akita: '秋田', gunma: '群馬', fukushima: '福島', shiga: '滋賀', kagoshima: '鹿児島',
  nagasaki: '長崎', toyama: '富山', ehime: '愛媛', okayama: '岡山', yamagata: '山形',
  yamanashi: '山梨', aomori: '青森', iwate: '岩手', tokushima: '徳島', oita: '大分',
  kochi: '高知', wakayama: '和歌山', saga: '佐賀', fukui: '福井', yamaguchi: '山口',
  shimane: '島根', tottori: '鳥取',
};

function log(msg) { process.stdout.write(`[${new Date().toISOString().slice(11,19)}] ${msg}\n`); }
function ask(q) {
  return new Promise(r => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    rl.question(q, ans => { rl.close(); r(ans); });
  });
}

(async () => {
  const data = JSON.parse(fs.readFileSync(LISTINGS_JSON, 'utf-8'));
  const allEntries = Object.entries(data);

  let progress = { done: [], failed: [] };
  if (fs.existsSync(PROGRESS_JSON)) progress = JSON.parse(fs.readFileSync(PROGRESS_JSON, 'utf-8'));
  const doneSet = new Set(progress.done);

  const slice = TEST ? allEntries.slice(0, 1) : allEntries.slice(START_IDX, START_IDX + LIMIT);
  const targets = slice.filter(([u]) => !doneSet.has(u));
  log(`Targets: ${targets.length} (total ${allEntries.length}, already done ${doneSet.size})`);

  const ctx = await chromium.launchPersistentContext(PROFILE_DIR, {
    headless: false,
    viewport: { width: 1400, height: 900 },
    locale: 'ja-JP',
    args: ['--disable-blink-features=AutomationControlled'],
  });
  const page = ctx.pages()[0] || await ctx.newPage();

  await page.goto('https://www.google.com/maps');
  await page.waitForTimeout(2500);
  const loggedIn = await page.evaluate(() => !!document.querySelector('a[href*="accounts.google.com/SignOutOptions"]'));
  if (!loggedIn) { log('❌ 未登入'); await ctx.close(); return; }
  log('✅ 登入確認');

  for (let i = 0; i < targets.length; i++) {
    const [url, rec] = targets[i];
    const prefJp = PREF_MAP[rec.prefecture] || '';
    const query = encodeURIComponent(`${rec.name} ${prefJp}`);
    const gmurl = `https://www.google.com/maps/search/?api=1&query=${query}`;

    log(`[${i+1}/${targets.length}] [${prefJp}] ${rec.name}`);

    try {
      await page.goto(gmurl, { waitUntil: 'domcontentloaded', timeout: 25000 });
      await page.waitForTimeout(4000);

      // drill into place if landed on search results
      const firstResult = page.locator('a[href*="/maps/place/"]').first();
      const onPlace = page.url().includes('/maps/place/');
      if (!onPlace && await firstResult.isVisible({ timeout: 1500 }).catch(() => false)) {
        await firstResult.click();
        await page.waitForTimeout(2000);
      }

      const saveBtn = page.getByRole('button', { name: /^儲存$|^保存$|^Save$/ }).first();
      await saveBtn.waitFor({ state: 'visible', timeout: 7000 });
      await saveBtn.click();
      await page.waitForTimeout(800);

      // find 百名店 list option
      let hyakuOpt = page.getByRole('menuitemcheckbox', { name: /百名店/ }).first();
      if (!(await hyakuOpt.isVisible({ timeout: 1500 }).catch(() => false))) {
        hyakuOpt = page.getByRole('menuitemradio', { name: /百名店/ }).first();
      }
      if (!(await hyakuOpt.isVisible({ timeout: 1500 }).catch(() => false))) {
        hyakuOpt = page.getByText(/^百名店$/, { exact: false }).first();
      }
      await hyakuOpt.waitFor({ state: 'visible', timeout: 4000 });

      const checked = await hyakuOpt.getAttribute('aria-checked').catch(() => null);
      if (checked === 'true') {
        log(`  ⊙ already in 百名店, skip`);
        await page.keyboard.press('Escape');
      } else {
        await hyakuOpt.click();
        log(`  ✓ saved`);
        await page.waitForTimeout(500);
      }

      progress.done.push(url);
    } catch (err) {
      log(`  ✗ ${err.message.slice(0, 80)}`);
      progress.failed.push({ url, name: rec.name, pref: rec.prefecture, error: err.message.slice(0, 100) });
    }

    if ((i+1) % 10 === 0) fs.writeFileSync(PROGRESS_JSON, JSON.stringify(progress, null, 2));
    await page.waitForTimeout(700 + Math.random() * 500);
  }

  fs.writeFileSync(PROGRESS_JSON, JSON.stringify(progress, null, 2));
  log(`\nDone. ✓ ${progress.done.length}  ✗ ${progress.failed.length}`);

  if (TEST) await ask('Test 結束。按 Enter 關閉 > ');
  await ctx.close();
})();
