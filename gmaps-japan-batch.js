// Playwright: 把 japan_listings.json 12,280 家分縣份加進 Google Maps
// 清單命名: "{prefecture-zh} 百名店" (e.g., "東京 百名店", "福岡 百名店")
// 並在每家「附註」填入分類字串 (e.g., "寿司 / 焼鳥")
//
//   node gmaps-japan-batch.js --test       # 只跑前 2 家測試
//   node gmaps-japan-batch.js --pref tokyo  # 只跑指定縣
//   node gmaps-japan-batch.js              # 全部跑
//   node gmaps-japan-batch.js --start 100  # 從第 100 家開始 (resume)

const { chromium } = require('@playwright/test');
const fs = require('fs');
const readline = require('readline');

const PROFILE_DIR    = 'D:/Tabelog/chrome-profile';
const LISTINGS_JSON  = 'D:/Tabelog/japan_listings.json';
const PROGRESS_JSON  = 'D:/Tabelog/japan-gmaps-progress.json';

const args = process.argv.slice(2);
const TEST = args.includes('--test');
const PREF_FILTER = (() => { const i = args.indexOf('--pref'); return i >= 0 ? args[i+1] : null; })();
const START_IDX = (() => { const i = args.indexOf('--start'); return i >= 0 ? parseInt(args[i+1], 10) : 0; })();
const LIMIT = (() => { const i = args.indexOf('--limit'); return i >= 0 ? parseInt(args[i+1], 10) : Infinity; })();

// 都道府県英→日 (use Japanese display name + 「百名店」suffix)
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

function listName(pref) {
  const jp = PREF_MAP[pref] || pref;
  return `${jp} 百名店`;
}

function genreNote(rec) {
  const cats = [...new Set(rec.awards.map(a => a.category.replace(/(東京|東|西|北海道|神奈川|愛知|大阪|香川)$/, '')))];
  return cats.join(' / ');
}

function log(msg) { process.stdout.write(`[${new Date().toISOString().slice(11,19)}] ${msg}\n`); }
function ask(q) {
  return new Promise(r => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    rl.question(q, ans => { rl.close(); r(ans); });
  });
}

(async () => {
  // ── load data ──
  const data = JSON.parse(fs.readFileSync(LISTINGS_JSON, 'utf-8'));
  let entries = Object.entries(data); // [url, {name, prefecture, awards}]

  if (PREF_FILTER) entries = entries.filter(([u, r]) => r.prefecture === PREF_FILTER);

  let progress = { done: [], failed: [] };
  if (fs.existsSync(PROGRESS_JSON)) progress = JSON.parse(fs.readFileSync(PROGRESS_JSON, 'utf-8'));
  const doneSet = new Set(progress.done);

  const targets = TEST ? entries.slice(0, 2) :
    entries.slice(START_IDX, START_IDX + LIMIT).filter(([u]) => !doneSet.has(u));
  log(`Targets: ${targets.length} (of total ${entries.length} entries, ${doneSet.size} done so far)`);

  // ── launch ──
  const ctx = await chromium.launchPersistentContext(PROFILE_DIR, {
    headless: false,
    viewport: { width: 1400, height: 900 },
    locale: 'ja-JP',
    args: ['--disable-blink-features=AutomationControlled'],
  });
  const page = ctx.pages()[0] || await ctx.newPage();

  // verify login
  await page.goto('https://www.google.com/maps');
  await page.waitForTimeout(2500);
  const loggedIn = await page.evaluate(() => !!document.querySelector('a[href*="accounts.google.com/SignOutOptions"]'));
  if (!loggedIn) { log('❌ 未登入'); await ctx.close(); return; }
  log('✅ 登入確認');

  // ── per-place flow ──
  for (let i = 0; i < targets.length; i++) {
    const [url, rec] = targets[i];
    const listLabel = listName(rec.prefecture);
    const note = genreNote(rec);
    const query = encodeURIComponent(`${rec.name} ${PREF_MAP[rec.prefecture] || ''}`);
    const gmurl = `https://www.google.com/maps/search/?api=1&query=${query}`;

    log(`[${i+1}/${targets.length}] [${listLabel}] ${rec.name} (note: ${note.slice(0,30)})`);

    try {
      await page.goto(gmurl, { waitUntil: 'domcontentloaded', timeout: 25000 });
      await page.waitForTimeout(4500);

      // drill into place if landed on search results
      const firstResult = page.locator('a[href*="/maps/place/"]').first();
      const onPlace = page.url().includes('/maps/place/');
      if (!onPlace && await firstResult.isVisible({ timeout: 1500 }).catch(() => false)) {
        await firstResult.click();
        await page.waitForTimeout(2500);
      }

      // find Save button
      const saveBtn = page.getByRole('button', { name: /^儲存$|^保存$|^Save$/ }).first();
      await saveBtn.waitFor({ state: 'visible', timeout: 8000 });
      await saveBtn.click();
      await page.waitForTimeout(900);

      // look for {pref} 百名店 in popup
      let listOption = page.getByRole('menuitemcheckbox', { name: new RegExp(listLabel) }).first();
      let listExists = await listOption.isVisible({ timeout: 1500 }).catch(() => false);

      if (!listExists) {
        // try menuitemradio
        listOption = page.getByRole('menuitemradio', { name: new RegExp(listLabel) }).first();
        listExists = await listOption.isVisible({ timeout: 800 }).catch(() => false);
      }

      if (listExists) {
        const checked = await listOption.getAttribute('aria-checked').catch(() => null);
        if (checked === 'true') {
          log(`  ⊙ already in ${listLabel}, skip`);
          await page.keyboard.press('Escape');
        } else {
          await listOption.click();
          log(`  ✓ saved → ${listLabel}`);
          await page.waitForTimeout(700);
        }
      } else {
        // need to create new list
        log(`  + creating new list: ${listLabel}`);
        const createOpt = page.getByText(/新しいリスト|新增清單|新規リスト|Create.*list|建立.*清單/).first();
        await createOpt.waitFor({ state: 'visible', timeout: 4000 });
        await createOpt.click();
        await page.waitForTimeout(800);

        // fill list name
        const nameInput = page.getByRole('textbox').first();
        await nameInput.waitFor({ state: 'visible', timeout: 3000 });
        await nameInput.fill(listLabel);
        await page.waitForTimeout(400);

        // click 建立/作成/Create
        const createBtn = page.getByRole('button', { name: /^建立$|^作成$|^Create$|^保存$/ }).first();
        await createBtn.click();
        await page.waitForTimeout(1000);
        log(`  ✓ created + saved → ${listLabel}`);
      }

      // ── note step ──
      // Try to find the note edit area near the just-saved list item
      try {
        const noteBtn = page.getByText(/^附註を追加|^附註$|^Add note$|^メモを追加|^メモ$/i).first();
        if (await noteBtn.isVisible({ timeout: 1500 }).catch(() => false)) {
          await noteBtn.click();
          await page.waitForTimeout(500);
          // textarea/input
          const noteInput = page.getByRole('textbox').filter({ hasNot: page.locator('[disabled]') }).first();
          if (await noteInput.isVisible({ timeout: 1500 }).catch(() => false)) {
            await noteInput.fill(note);
            await page.waitForTimeout(400);
            // save the note
            const saveNoteBtn = page.getByRole('button', { name: /^保存|^完成|^Save|^Done|^完了/ }).first();
            if (await saveNoteBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
              await saveNoteBtn.click();
              log(`    📝 note saved`);
            }
          }
        }
      } catch (e) {
        log(`    [note skipped: ${e.message.slice(0,40)}]`);
      }

      // close any remaining dialog
      await page.keyboard.press('Escape').catch(() => {});
      await page.waitForTimeout(300);

      progress.done.push(url);
    } catch (err) {
      log(`  ✗ ${err.message.slice(0, 80)}`);
      progress.failed.push({ url, name: rec.name, pref: rec.prefecture, error: err.message.slice(0, 100) });
    }

    if ((i+1) % 5 === 0) fs.writeFileSync(PROGRESS_JSON, JSON.stringify(progress, null, 2));
    await page.waitForTimeout(900 + Math.random() * 700);
  }

  fs.writeFileSync(PROGRESS_JSON, JSON.stringify(progress, null, 2));
  log(`\nDone. ✓ ${progress.done.length}  ✗ ${progress.failed.length}`);

  if (TEST) await ask('Test 結束。觀察後按 Enter 關閉 > ');
  await ctx.close();
})();
