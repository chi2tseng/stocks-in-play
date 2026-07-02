// Phase B: 審核 + 刪除誤判 saves
// 對每個非福岡 URL：訪問 GM 搜尋 → 比對名稱 → 偵測 closed/非餐廳 → 必要時取消 100店清單勾選
//   node gmaps-audit-remove.js [--workers N] [--dry] [--start IDX]

const { chromium } = require('@playwright/test');
const fs = require('fs');

const PROFILE_DIR  = 'D:/Tabelog/chrome-profile';
const DETAILS_JSON = 'D:/Tabelog/japan_details.json';
const FILTERED_JSON = 'D:/Tabelog/japan_filtered.json';
const PROGRESS_JSON = 'D:/Tabelog/japan-gmaps-progress.json';
const AUDIT_JSON    = 'D:/Tabelog/japan-audit-progress.json';

const args = process.argv.slice(2);
const WORKERS = (() => { const i = args.indexOf('--workers'); return i >= 0 ? parseInt(args[i+1],10) : 3; })();
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

// fuzzy substring/char-overlap match between Tabelog name and Google place name
function nameMatches(expected, actual) {
  if (!expected || !actual) return false;
  const e = expected.toLowerCase().replace(/\s+/g, '');
  const a = actual.toLowerCase().replace(/\s+/g, '');
  // exact or contains
  if (a.includes(e) || e.includes(a)) return true;
  // strip suffix/branch indicators
  const eClean = e.replace(/(本店|店|本舗|支店|分店|総本店|別館).*$/g, '');
  const aClean = a.replace(/(本店|店|本舗|支店|分店|総本店|別館).*$/g, '');
  if (eClean.length >= 2 && aClean.length >= 2 && (aClean.includes(eClean) || eClean.includes(aClean))) return true;
  // char overlap >= 60% of shorter
  const shorter = e.length < a.length ? e : a;
  const longer  = e.length < a.length ? a : e;
  let common = 0;
  for (const ch of new Set(shorter.split(''))) if (longer.includes(ch)) common++;
  return common / new Set(shorter.split('')).size >= 0.7;
}

(async () => {
  const filtered = JSON.parse(fs.readFileSync(FILTERED_JSON, 'utf-8'));
  const details = JSON.parse(fs.readFileSync(DETAILS_JSON, 'utf-8'));
  const progress = JSON.parse(fs.readFileSync(PROGRESS_JSON, 'utf-8'));

  // candidates: non-Fukuoka URLs in done set
  const candidates = progress.done
    .filter(url => filtered[url] && filtered[url].prefecture !== 'fukuoka')
    .map(url => ({ url, listing: filtered[url], detail: details[url] || {} }));
  log(`Total candidates to audit: ${candidates.length}`);

  let audit = { keep: [], removed: [], errors: [], suspect_not_removed: [] };
  if (fs.existsSync(AUDIT_JSON)) audit = JSON.parse(fs.readFileSync(AUDIT_JSON,'utf-8'));
  const auditedSet = new Set([...audit.keep, ...audit.removed.map(x => x.url), ...audit.suspect_not_removed.map(x => x.url)]);

  const todo = candidates.slice(START_IDX).filter(c => !auditedSet.has(c.url));
  log(`Already audited: ${auditedSet.size}, remaining: ${todo.length}`);
  if (todo.length === 0) { log('Nothing to do.'); return; }

  const ctx = await chromium.launchPersistentContext(PROFILE_DIR, {
    headless: false, viewport: { width: 1280, height: 800 }, locale: 'ja-JP',
    args: ['--disable-blink-features=AutomationControlled'],
  });
  const page0 = ctx.pages()[0] || await ctx.newPage();
  await page0.goto('https://www.google.com/maps'); await page0.waitForTimeout(2500);
  const loggedIn = await page0.evaluate(() => !!document.querySelector('a[href*="accounts.google.com/SignOutOptions"]'));
  if (!loggedIn) { log('❌ 未登入'); await ctx.close(); return; }
  log(`✅ 登入確認, ${WORKERS} workers, DRY=${DRY_RUN}`);

  let queueIdx = 0;
  let processed = 0;

  function nextItem() {
    if (queueIdx >= todo.length) return null;
    return todo[queueIdx++];
  }

  async function inspect(page, c) {
    const prefJp = PREF_MAP[c.listing.prefecture] || '';
    const expectedName = c.detail.name || c.listing.name;
    const q = encodeURIComponent(`${c.listing.name} ${prefJp}`);
    const gmurl = `https://www.google.com/maps/search/?api=1&query=${q}`;

    await page.goto(gmurl, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(3000);
    const firstResult = page.locator('a[href*="/maps/place/"]').first();
    const onPlace = page.url().includes('/maps/place/');
    if (!onPlace && await firstResult.isVisible({ timeout: 1500 }).catch(()=>false)) {
      await firstResult.click(); await page.waitForTimeout(2000);
    }

    // extract Google Place info
    const info = await page.evaluate(() => {
      const h1 = document.querySelector('h1');
      const name = h1 ? h1.textContent.trim() : null;
      const closed = document.body.textContent.includes('永久閉店') ||
                     document.body.textContent.includes('永久關閉') ||
                     document.body.textContent.includes('Permanently closed') ||
                     document.body.textContent.includes('閉店') ;
      const category = document.querySelector('button[jsaction*="category"], [class*="category"]')?.textContent.trim() || '';
      const address = document.querySelector('[data-item-id="address"], button[data-item-id="address"]')?.textContent.trim() || '';
      // is this a place page? (h1 + 儲存 button present)
      const isPlace = !!h1;
      return { name, closed, category, address, isPlace };
    });

    return info;
  }

  async function unsave(page) {
    // click Save, find 百名店 checkbox, uncheck if checked
    try {
      const saveBtn = page.getByRole('button', { name: /^儲存$|^保存$|^Save$/ }).first();
      await saveBtn.waitFor({ state: 'visible', timeout: 5000 });
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
      if (c1 === 'true' && c2 === 'true') {
        await opt.click(); // toggle OFF
        await page.waitForTimeout(500);
        await page.keyboard.press('Escape');
        return 'unsaved';
      } else {
        await page.keyboard.press('Escape');
        return 'not_in_list';  // wasn't actually saved
      }
    } catch (err) {
      return 'error:' + err.message.slice(0, 40);
    }
  }

  async function worker(page, workerId) {
    let c;
    while ((c = nextItem())) {
      processed++;
      const expectedName = c.detail.name || c.listing.name;
      try {
        const info = await inspect(page, c);
        if (!info.isPlace) {
          // search yielded no place page — probably wasn't actually saved properly, leave alone
          audit.keep.push(c.url);
          if (processed % 20 === 0) log(`[W${workerId} ${processed}/${todo.length}] ${expectedName} : no place found (skip)`);
        } else {
          const match = nameMatches(expectedName, info.name);
          const wrong = !match || info.closed;
          if (wrong) {
            const reason = info.closed ? '已閉店' : `mismatch (expected:${expectedName} actual:${info.name})`;
            if (DRY_RUN) {
              audit.suspect_not_removed.push({ url: c.url, expected: expectedName, actual: info.name, reason });
              log(`[W${workerId} ${processed}/${todo.length}] ✗ ${expectedName} ≠ ${info.name} [${reason.slice(0,40)}]`);
            } else {
              const r = await unsave(page);
              audit.removed.push({ url: c.url, expected: expectedName, actual: info.name, reason, result: r });
              log(`[W${workerId} ${processed}/${todo.length}] 🗑 ${expectedName} ≠ ${info.name} → ${r}`);
            }
          } else {
            audit.keep.push(c.url);
            if (processed % 50 === 0) log(`[W${workerId} ${processed}/${todo.length}] ✓ ${expectedName}`);
          }
        }
      } catch (err) {
        audit.errors.push({ url: c.url, name: expectedName, error: err.message.slice(0, 80) });
        log(`[W${workerId} ${processed}/${todo.length}] ERR ${expectedName}: ${err.message.slice(0,40)}`);
      }
      if (processed % 25 === 0) fs.writeFileSync(AUDIT_JSON, JSON.stringify(audit, null, 2));
      await page.waitForTimeout(700 + Math.random() * 400);
    }
  }

  const pages = [page0];
  for (let i = 1; i < WORKERS; i++) pages.push(await ctx.newPage());
  await Promise.all(pages.map((p, i) => worker(p, i+1)));

  fs.writeFileSync(AUDIT_JSON, JSON.stringify(audit, null, 2));
  log(`\nDone. keep=${audit.keep.length} removed=${audit.removed.length} suspect=${audit.suspect_not_removed.length} errors=${audit.errors.length}`);
  await ctx.close();
})();
