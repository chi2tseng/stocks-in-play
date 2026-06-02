// Playwright: 抓全日本 2017-2026 百名店所有受獎店家
// 不分都道府県、不過濾價格 — 純收集 (name, url, prefecture, awards)
// 輸出 D:/Tabelog/japan_listings.json

const { chromium } = require('@playwright/test');
const fs = require('fs');

const OUT_JSON = 'D:/Tabelog/japan_listings.json';
const YEARS = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026];
const HEADLESS = !process.argv.includes('--headed');

// 全部分類 — 全國 + 各地域版
const CATEGORIES = [
  // 全国 (national)
  { slug: 'shokudo',              label: '食堂' },
  { slug: 'spanish',              label: 'スペイン料理' },
  { slug: 'hamburger',            label: 'ハンバーガー' },
  { slug: 'tonkatsu',             label: 'とんかつ' },
  { slug: 'toriryori',            label: '鳥料理' },
  { slug: 'tachinomi',            label: '立ち飲み' },
  { slug: 'okonomiyaki',          label: 'お好み焼き' },
  { slug: 'creative_innovative',  label: '創作料理' },
  { slug: 'pizza',                label: 'ピザ' },
  { slug: 'tempura',              label: '天ぷら' },
  { slug: 'sukiyaki_shabushabu',  label: 'すき焼き・しゃぶしゃぶ' },
  { slug: 'unagi',                label: 'うなぎ' },
  { slug: 'gyoza',                label: '餃子' },
  { slug: 'ice_gelato',           label: 'アイス・ジェラート' },
  { slug: 'bar',                  label: 'バー' },
  { slug: 'kissaten',             label: '喫茶店' },
  // ラーメン (region-specific)
  { slug: 'ramen_hokkaido',       label: 'ラーメン北海道' },
  { slug: 'ramen_tokyo',          label: 'ラーメン東京' },
  { slug: 'ramen_kanagawa',       label: 'ラーメン神奈川' },
  { slug: 'ramen_aichi',          label: 'ラーメン愛知' },
  { slug: 'ramen_osaka',          label: 'ラーメン大阪' },
  { slug: 'ramen_east',           label: 'ラーメン東' },
  { slug: 'ramen_west',           label: 'ラーメン西' },
  // 東日本 (East)
  { slug: 'chinese_tokyo',        label: '中国料理東京' },
  { slug: 'chinese_east',         label: '中国料理東' },
  { slug: 'yakitori_east',        label: '焼鳥東' },
  { slug: 'yakiniku_tokyo',       label: '焼肉東京' },
  { slug: 'yakiniku_east',        label: '焼肉東' },
  { slug: 'izakaya_east',         label: '居酒屋東' },
  { slug: 'steak_east',           label: 'ステーキ東' },
  { slug: 'soba_east',            label: 'そば東' },
  { slug: 'cafe_east',            label: 'カフェ東' },
  { slug: 'yoshoku_east',         label: '洋食東' },
  { slug: 'french_tokyo',         label: 'フレンチ東京' },
  { slug: 'french_east',          label: 'フレンチ東' },
  { slug: 'italian_tokyo',        label: 'イタリアン東京' },
  { slug: 'italian_east',         label: 'イタリアン東' },
  { slug: 'japanese_tokyo',       label: '日本料理東京' },
  { slug: 'japanese_east',        label: '日本料理東' },
  { slug: 'sushi_tokyo',          label: '寿司東京' },
  { slug: 'sushi_east',           label: '寿司東' },
  { slug: 'curry_tokyo',          label: 'カレー東京' },
  { slug: 'curry_east',           label: 'カレー東' },
  { slug: 'asia_ethnic_tokyo',    label: 'アジア東京' },
  { slug: 'asia_ethnic_east',     label: 'アジア東' },
  { slug: 'udon_kagawa',          label: 'うどん香川' },
  { slug: 'udon_east',            label: 'うどん東' },
  { slug: 'wagashi_tokyo',        label: '和菓子東京' },
  { slug: 'wagashi_east',         label: '和菓子東' },
  { slug: 'sweets_tokyo',         label: 'スイーツ東京' },
  { slug: 'sweets_east',          label: 'スイーツ東' },
  { slug: 'bread_tokyo',          label: 'パン東京' },
  { slug: 'bread_east',           label: 'パン東' },
  // 西日本 (West)
  { slug: 'chinese_west',         label: '中国料理西' },
  { slug: 'yakitori_west',        label: '焼鳥西' },
  { slug: 'yakiniku_west',        label: '焼肉西' },
  { slug: 'izakaya_west',         label: '居酒屋西' },
  { slug: 'steak_west',           label: 'ステーキ西' },
  { slug: 'soba_west',            label: 'そば西' },
  { slug: 'cafe_west',            label: 'カフェ西' },
  { slug: 'yoshoku_west',         label: '洋食西' },
  { slug: 'french_west',          label: 'フレンチ西' },
  { slug: 'italian_west',         label: 'イタリアン西' },
  { slug: 'japanese_west',        label: '日本料理西' },
  { slug: 'sushi_west',           label: '寿司西' },
  { slug: 'curry_west',           label: 'カレー西' },
  { slug: 'asia_ethnic_west',     label: 'アジア西' },
  { slug: 'udon_west',            label: 'うどん西' },
  { slug: 'wagashi_west',         label: '和菓子西' },
  { slug: 'sweets_west',          label: 'スイーツ西' },
  { slug: 'bread_west',           label: 'パン西' },
];

function log(msg) { process.stderr.write(`[${new Date().toISOString().slice(11,19)}] ${msg}\n`); }

(async () => {
  const browser = await chromium.launch({ headless: HEADLESS });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    locale: 'ja-JP',
    viewport: { width: 1440, height: 900 },
  });
  const page = await ctx.newPage();

  const restaurants = new Map(); // url → { name, prefecture, awards: [{year, category}] }
  let totalTried = 0, totalHits = 0;

  for (const cat of CATEGORIES) {
    for (const year of YEARS) {
      totalTried++;
      const url = `https://award.tabelog.com/hyakumeiten/${cat.slug}/${year}`;
      try {
        const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 25000 });
        if (!resp || resp.status() === 404) {
          continue;
        }
        await page.waitForTimeout(700 + Math.random() * 500);

        const items = await page.evaluate(() => {
          const out = [];
          // tabelog restaurant URL pattern: /{prefecture}/A.../A.../digits/
          for (const a of document.querySelectorAll('a[href*="tabelog.com/"]')) {
            const href = a.href.split('?')[0];
            const m = href.match(/tabelog\.com\/([a-z]+)\/A\d+\/A\d+\/(\d+)/);
            if (!m) continue;
            const prefecture = m[1];
            const cleanUrl = `https://tabelog.com/${prefecture}/${href.split('/').slice(-4, -1).join('/')}/`;
            const card = a.closest('.hyakumeiten-shop__list-item, .hyakumeiten-shop__list, [class*="shop__item"]') || a.parentElement;
            const nameEl = card?.querySelector('.hyakumeiten-shop__name, [class*="shop__name"], h3, h4');
            const name = nameEl ? nameEl.textContent.trim() : a.textContent.trim().replace(/^\d+/, '').trim();
            out.push({ url: cleanUrl, prefecture, name });
          }
          // dedupe within page
          const seen = new Set();
          return out.filter(o => {
            if (seen.has(o.url)) return false;
            seen.add(o.url);
            return true;
          });
        });

        totalHits += items.length;
        log(`  ${cat.label.padEnd(20)} ${year}: ${items.length}件 (run total ${totalHits})`);

        for (const it of items) {
          if (!restaurants.has(it.url)) {
            restaurants.set(it.url, { name: it.name, prefecture: it.prefecture, awards: [] });
          }
          const rec = restaurants.get(it.url);
          if (it.name && it.name.length > rec.name.length) rec.name = it.name;
          rec.awards.push({ year, category: cat.label, slug: cat.slug });
        }
      } catch (err) {
        log(`  [err] ${cat.label} ${year}: ${err.message.slice(0, 60)}`);
      }
      await page.waitForTimeout(300 + Math.random() * 300);
    }
    // save incrementally per category
    fs.writeFileSync(OUT_JSON, JSON.stringify(Object.fromEntries(restaurants), null, 2), 'utf-8');
  }

  await browser.close();
  log(`\n✅ tried=${totalTried} hits=${totalHits} unique=${restaurants.size}`);
  log(`→ ${OUT_JSON}`);

  // breakdown by prefecture
  const byPref = {};
  for (const [url, rec] of restaurants) byPref[rec.prefecture] = (byPref[rec.prefecture]||0) + 1;
  console.log('\n=== By prefecture ===');
  for (const [p, c] of Object.entries(byPref).sort((a,b) => b[1]-a[1])) {
    console.log(`  ${p.padEnd(15)} ${c}`);
  }
})();
