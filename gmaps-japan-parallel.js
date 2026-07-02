// 並行版：在同一個 persistent context 中開 N 個 tab，平行加進 百名店 清單
//   node gmaps-japan-parallel.js [--workers N]

const { chromium } = require('@playwright/test');
const fs = require('fs');

const PROFILE_DIR    = 'D:/Tabelog/chrome-profile';
const LISTINGS_JSON  = 'D:/Tabelog/japan_filtered.json';
const PROGRESS_JSON  = 'D:/Tabelog/japan-gmaps-progress.json';

const args = process.argv.slice(2);
const WORKERS = (() => { const i = args.indexOf('--workers'); return i >= 0 ? parseInt(args[i+1],10) : 5; })();

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

let progress = { done: [], failed: [] };
if (fs.existsSync(PROGRESS_JSON)) progress = JSON.parse(fs.readFileSync(PROGRESS_JSON,'utf-8'));
const doneSet = new Set(progress.done);

const data = JSON.parse(fs.readFileSync(LISTINGS_JSON,'utf-8'));
const queue = Object.entries(data).filter(([u]) => !doneSet.has(u));
log(`Queue: ${queue.length} (total ${Object.keys(data).length}, done ${doneSet.size})`);

let queueIdx = 0;
let processed = 0;
const total = queue.length;

let saveTimer = null;
function scheduleSave() {
  if (saveTimer) return;
  saveTimer = setTimeout(() => {
    saveTimer = null;
    fs.writeFileSync(PROGRESS_JSON, JSON.stringify(progress, null, 2));
  }, 3000);
}

async function processItem(page, url, rec, workerId) {
  const prefJp = PREF_MAP[rec.prefecture] || '';
  const query = encodeURIComponent(`${rec.name} ${prefJp}`);
  const gmurl = `https://www.google.com/maps/search/?api=1&query=${query}`;
  try {
    await page.goto(gmurl, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(3500);

    const firstResult = page.locator('a[href*="/maps/place/"]').first();
    const onPlace = page.url().includes('/maps/place/');
    if (!onPlace && await firstResult.isVisible({ timeout: 1500 }).catch(()=>false)) {
      await firstResult.click();
      await page.waitForTimeout(1800);
    }

    const saveBtn = page.getByRole('button', { name: /^儲存$|^保存$|^Save$/ }).first();
    await saveBtn.waitFor({ state: 'visible', timeout: 7000 });
    await saveBtn.click();
    await page.waitForTimeout(800);

    let hyakuOpt = page.getByRole('menuitemcheckbox', { name: /百名店/ }).first();
    if (!(await hyakuOpt.isVisible({ timeout: 1500 }).catch(()=>false))) {
      hyakuOpt = page.getByRole('menuitemradio', { name: /百名店/ }).first();
    }
    await hyakuOpt.waitFor({ state: 'visible', timeout: 4000 });

    const checked = await hyakuOpt.getAttribute('aria-checked').catch(()=>null);
    if (checked === 'true') {
      await page.keyboard.press('Escape');
      return 'skip';
    }
    await hyakuOpt.click();
    await page.waitForTimeout(500);
    return 'ok';
  } catch (err) {
    return { error: err.message.slice(0, 80) };
  }
}

async function worker(page, workerId) {
  while (true) {
    const myIdx = queueIdx++;
    if (myIdx >= queue.length) break;
    const [url, rec] = queue[myIdx];
    if (doneSet.has(url)) continue;
    const r = await processItem(page, url, rec, workerId);
    processed++;
    if (typeof r === 'string') {
      progress.done.push(url);
      doneSet.add(url);
      if (processed % 10 === 0) log(`[W${workerId} ${processed}/${total}] ${(rec.name||'').slice(0,18)} ${r}`);
    } else {
      progress.failed.push({ url, name: rec.name, pref: rec.prefecture, error: r.error });
      log(`[W${workerId} ${processed}/${total}] ${(rec.name||'').slice(0,18)} ✗ ${r.error.slice(0,40)}`);
    }
    scheduleSave();
    await page.waitForTimeout(600 + Math.random() * 400);
  }
}

(async () => {
  const ctx = await chromium.launchPersistentContext(PROFILE_DIR, {
    headless: false,
    viewport: { width: 1280, height: 800 },
    locale: 'ja-JP',
    args: ['--disable-blink-features=AutomationControlled'],
  });
  // verify login on first tab
  const page0 = ctx.pages()[0] || await ctx.newPage();
  await page0.goto('https://www.google.com/maps');
  await page0.waitForTimeout(2500);
  const loggedIn = await page0.evaluate(() => !!document.querySelector('a[href*="accounts.google.com/SignOutOptions"]'));
  if (!loggedIn) { log('❌ 未登入'); await ctx.close(); return; }
  log(`✅ 登入確認, ${WORKERS} workers`);

  const pages = [page0];
  for (let i = 1; i < WORKERS; i++) pages.push(await ctx.newPage());
  await Promise.all(pages.map((p,i) => worker(p, i+1)));

  fs.writeFileSync(PROGRESS_JSON, JSON.stringify(progress, null, 2));
  log(`\nDone. ✓ ${progress.done.length}  ✗ ${progress.failed.length}`);
  await ctx.close();
})();
