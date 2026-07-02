// 統合修復腳本：對所有 japan_filtered.json URL：
//   - 取 Google Place 資訊 (name, category, closed)
//   - 比對 Tabelog 名稱
//   - 對照清單狀態 (aria-checked)
//   - 修正：應在 → 補加；不該在 (wrong/closed/non-restaurant) → 移除
// 用 N 並行 tab + 雙重 aria-checked race protection
//
//   node gmaps-fix-all.js [--workers N] [--dry] [--start IDX]

const { chromium } = require('@playwright/test');
const fs = require('fs');

const PROFILE_DIR  = 'D:/Tabelog/chrome-profile';
const FILTERED_JSON = 'D:/Tabelog/japan_filtered.json';
const DETAILS_JSON  = 'D:/Tabelog/japan_details.json';
const PROGRESS_JSON = 'D:/Tabelog/gmaps-fix-progress.json';

const args = process.argv.slice(2);
const WORKERS = (() => { const i = args.indexOf('--workers'); return i >= 0 ? parseInt(args[i+1],10) : 20; })();
const DRY_RUN = args.includes('--dry');
const START_IDX = (() => { const i = args.indexOf('--start'); return i >= 0 ? parseInt(args[i+1],10) : 0; })();

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

function nameMatches(expected, actual) {
  if (!expected || !actual) return false;
  const norm = s => s.toLowerCase().replace(/[\s　・]/g, '').replace(/(本店|店|本舗|支店|分店|総本店|別館|店舗).*$/g, '');
  const e = norm(expected), a = norm(actual);
  if (e.length === 0 || a.length === 0) return false;
  if (a.includes(e) || e.includes(a)) return true;
  if (e.length >= 3 && a.length >= 3) {
    // overlap by chars
    let common = 0;
    const eSet = new Set(e.split(''));
    for (const ch of a) if (eSet.has(ch)) common++;
    if (common / Math.min(e.length, a.length) >= 0.7) return true;
  }
  return false;
}

function isRestaurantCategory(cat) {
  if (!cat) return null; // unknown
  const restaurant = /レストラン|食堂|寿司|鮨|焼肉|焼鳥|ラーメン|うどん|そば|居酒屋|カフェ|喫茶|バー|料理|食事|和食|洋食|中華|中国|フレンチ|イタリアン|スイーツ|パン|ベーカリー|店|処|ダイニング|Restaurant|Cafe|Bar|餐廳|咖啡|麵|麺|寿し|蕎麦|餃子|天ぷら|うなぎ|鰻|串焼|ピザ|ホルモン|ステーキ|肉|魚|海鮮|甘味|お好み焼|もつ|蕎|麺類|喫茶店|割烹|懐石|食|定食|デザート|スイーツ専門店|料亭/i;
  const nonRestaurant = /^(駅|公園|区役所|市役所|銀行|学校|大学|病院|オフィスビル|ホテル|薬局|コンビニ|郵便局|神社|寺|温泉|地下鉄|タクシー|空港|スーパー|商店街|百貨店|エリア|地域|都道府県)$/;
  if (nonRestaurant.test(cat)) return false;
  if (restaurant.test(cat)) return true;
  return null; // ambiguous
}

(async () => {
  const filtered = JSON.parse(fs.readFileSync(FILTERED_JSON,'utf-8'));
  const details = JSON.parse(fs.readFileSync(DETAILS_JSON,'utf-8'));
  const listingsAll = JSON.parse(fs.readFileSync('D:/Tabelog/japan_listings.json','utf-8'));

  // expand candidate set: filtered + all URLs that were ever processed (from progress files)
  const candidates = new Map();
  // 1. All filtered URLs (these SHOULD be in list)
  for (const [u, r] of Object.entries(filtered)) candidates.set(u, { ...r, expectedInList: true });
  // 2. All URLs touched by previous batches (might be wrong saves to audit)
  for (const pPath of ['D:/Tabelog/japan-gmaps-progress.json','D:/Tabelog/gmaps-progress.json']) {
    if (fs.existsSync(pPath)) {
      const p = JSON.parse(fs.readFileSync(pPath,'utf-8'));
      for (const u of (p.done || [])) {
        if (!candidates.has(u)) {
          const r = listingsAll[u] || { name: '?', prefecture: u.match(/tabelog\.com\/([a-z]+)/)?.[1] || 'tokyo', awards: [] };
          candidates.set(u, { ...r, expectedInList: false }); // not in filtered → high-price, SHOULD remove if saved
        }
      }
    }
  }

  let progress = { processed: [], added: [], unsaved: [], kept: [], errors: [], notFound: [] };
  if (fs.existsSync(PROGRESS_JSON)) progress = JSON.parse(fs.readFileSync(PROGRESS_JSON,'utf-8'));
  const doneSet = new Set(progress.processed);

  const entries = [...candidates.entries()].slice(START_IDX);
  const todo = entries.filter(([u]) => !doneSet.has(u));
  log(`Total: ${entries.length} | done: ${doneSet.size} | remaining: ${todo.length} | workers: ${WORKERS} | DRY: ${DRY_RUN}`);
  if (todo.length === 0) { log('Nothing to do.'); return; }

  const ctx = await chromium.launchPersistentContext(PROFILE_DIR, {
    headless: false, viewport: { width: 1100, height: 700 }, locale: 'ja-JP',
    args: ['--disable-blink-features=AutomationControlled'],
  });
  const page0 = ctx.pages()[0] || await ctx.newPage();
  await page0.goto('https://www.google.com/maps'); await page0.waitForTimeout(3500);
  const loggedIn = await page0.evaluate(() => {
    return !!document.querySelector('a[href*="accounts.google.com/SignOutOptions"]') ||
           !!document.querySelector('a[aria-label*="Google 帳戶"], a[aria-label*="Google Account"]') ||
           !!document.querySelector('[data-ogsr-up], [class*="gb_d"]') ||
           document.cookie.includes('SID=');
  });
  if (!loggedIn) { log('❌ 未登入 (selector miss — pause 10s and continue anyway)'); await page0.waitForTimeout(10000); }
  log('✅ Continue');

  let queueIdx = 0;
  let cnt = 0;
  let saveTimer = null;
  function scheduleSave() {
    if (saveTimer) return;
    saveTimer = setTimeout(() => { saveTimer = null; fs.writeFileSync(PROGRESS_JSON, JSON.stringify(progress, null, 2)); }, 5000);
  }

  async function workOne(page, workerId) {
    const myIdx = queueIdx++;
    if (myIdx >= todo.length) return false;
    const [url, rec] = todo[myIdx];
    const prefJp = PREF_MAP[rec.prefecture] || '';
    const expectedName = (details[url] && details[url].name) || rec.name || '';
    const q = encodeURIComponent(`${rec.name} ${prefJp}`);
    const gmurl = `https://www.google.com/maps/search/?api=1&query=${q}`;
    cnt++;
    try {
      await page.goto(gmurl, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(5000);
      const firstResult = page.locator('a[href*="/maps/place/"]').first();
      const onPlace = page.url().includes('/maps/place/');
      if (!onPlace && await firstResult.isVisible({ timeout: 1500 }).catch(()=>false)) {
        await firstResult.click(); await page.waitForTimeout(2000);
      }

      // extract place info
      const info = await page.evaluate(() => {
        const h1 = document.querySelector('h1');
        const name = h1 ? h1.textContent.trim() : null;
        const body = document.body.textContent;
        const closed = body.includes('永久閉店') || body.includes('永久關閉') || body.includes('Permanently closed');
        const catEl = document.querySelector('button[jsaction*="category"]') || document.querySelector('[class*="DkEaL"]') || document.querySelector('button.DkEaL');
        const category = catEl ? catEl.textContent.trim() : '';
        return { name, closed, category, isPlace: !!h1 };
      });

      if (!info.isPlace) {
        progress.notFound.push(url);
        progress.processed.push(url);
        return true;
      }

      const match = nameMatches(expectedName, info.name);
      const catCheck = isRestaurantCategory(info.category);
      // Conservative remove: clear signals (closed / non-restaurant)
      // If this URL is in filtered set (expectedInList=true): should be in list unless wrong
      // If not in filtered (high-price / never should have been added): remove if saved
      const clearlyWrong = info.closed || catCheck === false;
      const shouldBeInList = rec.expectedInList && !clearlyWrong;

      // open Save popup to check current state
      const saveBtn = page.getByRole('button', { name: /^儲存$|^保存$|^Save$/ }).first();
      await saveBtn.waitFor({ state: 'visible', timeout: 10000 });
      await saveBtn.click();
      await page.waitForTimeout(900);

      let opt = page.getByRole('menuitemcheckbox', { name: /百名店/ }).first();
      if (!(await opt.isVisible({ timeout: 1500 }).catch(()=>false))) {
        opt = page.getByRole('menuitemradio', { name: /百名店/ }).first();
      }
      await opt.waitFor({ state: 'visible', timeout: 4000 });
      await page.waitForTimeout(500);
      const c1 = await opt.getAttribute('aria-checked').catch(()=>null);
      await page.waitForTimeout(300);
      const c2 = await opt.getAttribute('aria-checked').catch(()=>null);
      // require unanimous state to act
      const currentlyIn = c1 === 'true' && c2 === 'true';
      const currentlyOut = c1 === 'false' && c2 === 'false';

      let action = 'noop';
      if (shouldBeInList && currentlyOut) {
        if (!DRY_RUN) { await opt.click(); await page.waitForTimeout(500); }
        action = 'ADD';
        progress.added.push({ url, name: expectedName });
      } else if (!shouldBeInList && currentlyIn) {
        if (!DRY_RUN) { await opt.click(); await page.waitForTimeout(500); }
        action = 'REMOVE';
        const reason = info.closed ? 'closed' : (catCheck === false ? 'non-restaurant' : 'name-mismatch');
        progress.unsaved.push({ url, expected: expectedName, actual: info.name, category: info.category, reason });
      } else if (currentlyIn) {
        progress.kept.push(url);
      } else if (!currentlyIn && !currentlyOut) {
        // ambiguous — close without action
        progress.errors.push({ url, name: expectedName, error: `ambiguous aria-checked c1=${c1} c2=${c2}` });
      }
      await page.keyboard.press('Escape');
      progress.processed.push(url);
      if (cnt % 15 === 0 || action !== 'noop') {
        log(`[W${workerId} ${cnt}/${todo.length}] ${action} ${expectedName.slice(0,18)} → ${(info.name||'').slice(0,18)} [${info.category||'?'}]${info.closed?' [CLOSED]':''}`);
      }
      scheduleSave();
    } catch (err) {
      progress.errors.push({ url, name: expectedName, error: err.message.slice(0, 80) });
      progress.processed.push(url);
      if (cnt % 25 === 0) log(`[W${workerId} ${cnt}/${todo.length}] ✗ ${expectedName.slice(0,18)} ${err.message.slice(0,40)}`);
      scheduleSave();
    }
    await page.waitForTimeout(500 + Math.random() * 400);
    return true;
  }

  async function worker(page, workerId) {
    while (await workOne(page, workerId)) {}
  }

  const pages = [page0];
  for (let i = 1; i < WORKERS; i++) pages.push(await ctx.newPage());
  await Promise.all(pages.map((p, i) => worker(p, i+1)));

  fs.writeFileSync(PROGRESS_JSON, JSON.stringify(progress, null, 2));
  log(`\n✅ Done. processed=${progress.processed.length} added=${progress.added.length} removed=${progress.unsaved.length} kept=${progress.kept.length} errors=${progress.errors.length} notFound=${progress.notFound.length}`);
  await ctx.close();
})();
