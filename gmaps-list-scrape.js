// 完整 scrape user's 百名店 list (all 625 items)
// 透過「刪除」按鈕為錨點 → 提取 name + 位置
// 比對 Tabelog 預期名稱 → flag suspects (wrong-saves, non-restaurants, etc.)
// 輸出 D:/Tabelog/list-suspects.json (給使用者 review)

const { chromium } = require('@playwright/test');
const fs = require('fs');

const PROFILE_DIR = 'D:/Tabelog/chrome-profile';
const LIST_URL    = 'https://maps.app.goo.gl/ZiXXGRDMi1pDFkqa7';
const OUT_JSON    = 'D:/Tabelog/list-suspects.json';
const SCREENSHOT  = 'D:/Tabelog/list-final.png';

function log(msg) { process.stdout.write(`[${new Date().toISOString().slice(11,19)}] ${msg}\n`); }

// build Tabelog name set (Fukuoka details if present, else use detail/listings)
function buildExpectedNames() {
  const names = new Set();
  for (const p of ['D:/Tabelog/japan_details.json','D:/Tabelog/japan_filtered.json','D:/Tabelog/japan_listings.json']) {
    if (!fs.existsSync(p)) continue;
    const d = JSON.parse(fs.readFileSync(p,'utf-8'));
    for (const k of Object.keys(d)) {
      const r = d[k];
      if (r && r.name) names.add(r.name.replace(/\s+/g,'').toLowerCase());
    }
  }
  return names;
}

function nameFuzzyMatch(saved, expected) {
  const a = saved.replace(/\s+/g,'').toLowerCase();
  for (const e of expected) {
    if (e.length < 2) continue;
    if (a.includes(e) || e.includes(a)) return true;
    // sub-string of length >= 3
    if (e.length >= 4 && a.length >= 4) {
      let common = 0;
      for (let i = 0; i + 2 <= e.length; i++) if (a.includes(e.slice(i, i+3))) { common++; break; }
      if (common >= 1) return true;
    }
  }
  return false;
}

(async () => {
  const expected = buildExpectedNames();
  log(`Expected names from Tabelog: ${expected.size}`);

  const ctx = await chromium.launchPersistentContext(PROFILE_DIR, {
    headless: false, viewport: { width: 1400, height: 900 }, locale: 'ja-JP',
    args: ['--disable-blink-features=AutomationControlled'],
  });
  const page = ctx.pages()[0] || await ctx.newPage();
  log('Opening list...');
  await page.goto(LIST_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(8000);

  const target = await page.evaluate(() => {
    const m = document.body.textContent.match(/(\d{1,5})\s*個地點/);
    return m ? parseInt(m[1], 10) : 0;
  });
  log(`List size: ${target}`);

  // scroll via mouse wheel on the list panel (more reliable for virtual lists)
  log('Scrolling via mouse wheel...');
  // hover over left panel center first
  const panelBox = { x: 200, y: 450 };
  await page.mouse.move(panelBox.x, panelBox.y);
  let lastCount = 0, stable = 0;
  for (let i = 0; i < 2000; i++) {
    await page.mouse.wheel(0, 1200);
    if (i % 5 === 0) await page.waitForTimeout(200);
    if (i % 20 === 0) {
      const count = await page.evaluate(() => document.querySelectorAll('button[aria-label="刪除"]').length);
      if (count === lastCount) {
        stable++;
        if (stable >= 5 && count >= target * 0.98) break;
        if (stable >= 30) break;
      } else {
        stable = 0;
        lastCount = count;
      }
      log(`  ${i}: ${count}/${target}`);
    }
  }
  log(`Final scroll count: ${lastCount}`);

  await page.screenshot({ path: SCREENSHOT, fullPage: false });

  // extract items
  const rawItems = await page.evaluate(() => {
    const out = [];
    const deleteBtns = document.querySelectorAll('button[aria-label="刪除"]');
    for (const btn of deleteBtns) {
      let row = btn;
      for (let i = 0; i < 8 && row.parentElement; i++) {
        row = row.parentElement;
        if (row.textContent.length > 50 && row.querySelector('img, span[role="img"]')) break;
      }
      const texts = [];
      const walker = document.createTreeWalker(row, NodeFilter.SHOW_TEXT);
      let n;
      while ((n = walker.nextNode())) {
        const t = n.textContent.trim();
        if (t.length >= 2 && t.length <= 80 && !/^\d+\.\d+$|^\(?\d+\)?$|^¥|^\$|^添加|^新增|^附註|^刪除|^地點|^永久|閉店/.test(t)) texts.push(t);
      }
      // closed status
      const closed = row.textContent.includes('永久閉店') || row.textContent.includes('永久關閉');
      out.push({ name: texts[0] || '?', closed });
    }
    return out;
  });

  // dedupe by name
  const seen = new Set();
  const items = rawItems.filter(it => {
    const k = it.name;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
  log(`Extracted: ${rawItems.length} raw → ${items.length} unique`);

  // classify: look for clear-wrong patterns (administrative regions, prefectures, non-restaurant entities)
  const WRONG_PATTERNS = [
    /^(東京都?|大阪府?|京都府?|北海道|沖縄県?|福岡県?|愛知県?|神奈川県?|兵庫県?|広島県?|千葉県?|埼玉県?|静岡県?)$/,
    /^(.*?(?:都|道|府|県|市|区|町|村|郡))$/,
    /^(.{0,3}駅|.{0,3}空港|.{0,3}公園|.{0,3}病院|.{0,3}学校|.{0,3}大学|.{0,3}銀行|.{0,3}神社|.{0,3}寺|.{0,3}郵便局|.{0,3}交番|.{0,3}館)$/,
    /^Tokyo$|^Osaka$|^Kyoto$|^Japan$/i,
  ];

  const suspects = [];
  const closed = [];
  const oks = [];
  for (const it of items) {
    if (it.closed) {
      closed.push(it);
      continue;
    }
    let matched = false;
    for (const re of WRONG_PATTERNS) if (re.test(it.name)) { matched = true; break; }
    if (matched) suspects.push({ ...it, reason: 'place/area name not restaurant' });
    else if (!nameFuzzyMatch(it.name, expected)) suspects.push({ ...it, reason: 'no Tabelog match' });
    else oks.push(it);
  }

  log(`OK (match Tabelog): ${oks.length}`);
  log(`Suspects (wrong pattern / no match): ${suspects.length}`);
  log(`Closed (永久閉店): ${closed.length}`);

  fs.writeFileSync(OUT_JSON, JSON.stringify({ target, extractedRaw: rawItems.length, uniqueCount: items.length, oks: oks.length, suspects, closed }, null, 2));
  log(`→ ${OUT_JSON}`);
  log(`→ screenshot: ${SCREENSHOT}`);

  await ctx.close();
})();
