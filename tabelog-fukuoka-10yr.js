// Playwright scraper: 食べログ 福岡百名店 (過去10年・2017-2026・夕食≤¥6,000)
// 出力: D:/Tabelog/fukuoka_hyakumeiten_10yr.csv  (Google マイマップ インポート用)
//
//   node tabelog-fukuoka-10yr.js              # headed (default, less Cloudflare hit)
//   node tabelog-fukuoka-10yr.js --headless   # faster but may trip CF
//   node tabelog-fukuoka-10yr.js --phase1-only # only collect listings
//   node tabelog-fukuoka-10yr.js --resume      # skip phase1 if listings.json exists

const { chromium } = require('@playwright/test');
const fs   = require('fs');
const path = require('path');

const OUT_DIR  = 'D:/Tabelog';
const LISTINGS_JSON = path.join(OUT_DIR, 'listings.json');
const DETAILS_JSON  = path.join(OUT_DIR, 'details.json');
const OUT_CSV       = path.join(OUT_DIR, 'fukuoka_hyakumeiten_10yr.csv');
const OUT_CSV_ALL   = path.join(OUT_DIR, 'fukuoka_hyakumeiten_10yr_all.csv');

const MAX_DINNER_YEN = 6000;
const YEARS = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026];
const HEADLESS = process.argv.includes('--headless');
const PHASE1_ONLY = process.argv.includes('--phase1-only');
const RESUME = process.argv.includes('--resume');

// 福岡が含まれ得るカテゴリ (全国 + _west) ───────────────────────────────────
const CATEGORIES = [
  // 全国 (national)
  { slug: 'shokudo',            label: '食堂' },
  { slug: 'spanish',            label: 'スペイン料理' },
  { slug: 'hamburger',          label: 'ハンバーガー' },
  { slug: 'tonkatsu',           label: 'とんかつ' },
  { slug: 'toriryori',          label: '鳥料理' },
  { slug: 'tachinomi',          label: '立ち飲み' },
  { slug: 'okonomiyaki',        label: 'お好み焼き' },
  { slug: 'creative_innovative',label: '創作料理' },
  { slug: 'pizza',              label: 'ピザ' },
  { slug: 'tempura',            label: '天ぷら' },
  { slug: 'sukiyaki_shabushabu',label: 'すき焼き・しゃぶしゃぶ' },
  { slug: 'unagi',              label: 'うなぎ' },
  { slug: 'gyoza',              label: '餃子' },
  { slug: 'ice_gelato',         label: 'アイス・ジェラート' },
  { slug: 'bar',                label: 'バー' },
  { slug: 'kissaten',           label: '喫茶店' },
  // 西日本 (West)
  { slug: 'chinese_west',       label: '中国料理' },
  { slug: 'ramen_west',         label: 'ラーメン' },
  { slug: 'yakitori_west',      label: '焼き鳥' },
  { slug: 'yakiniku_west',      label: '焼肉' },
  { slug: 'izakaya_west',       label: '居酒屋' },
  { slug: 'steak_west',         label: 'ステーキ・鉄板焼き' },
  { slug: 'soba_west',          label: 'そば' },
  { slug: 'cafe_west',          label: 'カフェ' },
  { slug: 'yoshoku_west',       label: '洋食' },
  { slug: 'french_west',        label: 'フレンチ' },
  { slug: 'italian_west',       label: 'イタリアン' },
  { slug: 'japanese_west',      label: '日本料理' },
  { slug: 'sushi_west',         label: '寿司' },
  { slug: 'curry_west',         label: 'カレー' },
  { slug: 'asia_ethnic_west',   label: 'アジア・エスニック' },
  { slug: 'udon_west',          label: 'うどん' },
  { slug: 'wagashi_west',       label: '和菓子・甘味処' },
  { slug: 'sweets_west',        label: 'スイーツ' },
  { slug: 'bread_west',         label: 'パン' },
];

function log(msg) { process.stderr.write(`[${new Date().toISOString().slice(11,19)}] ${msg}\n`); }

// 価格テキストから下限・上限を抽出 ("¥5,000～¥5,999" → {lower:5000, upper:5999})
function parsePriceRange(txt) {
  if (!txt) return { lower: null, upper: null };
  const clean = txt.replace(/[,，]/g, '');
  const nums = [...clean.matchAll(/¥?\s*(\d{3,6})/g)].map(m => parseInt(m[1], 10));
  if (nums.length === 0) return { lower: null, upper: null };
  if (nums.length === 1) {
    // "¥5,000～" or "～¥5,999"
    if (clean.includes('～') || clean.includes('〜') || clean.includes('~')) {
      // determine if it's "x以上" or "x以下" by position
      if (clean.match(/[\d]\s*[～〜~]\s*$/)) return { lower: nums[0], upper: null }; // "5000～"
      return { lower: null, upper: nums[0] }; // "～5999"
    }
    return { lower: nums[0], upper: nums[0] };
  }
  return { lower: nums[0], upper: nums[1] };
}

// ── Phase 1: 受賞リスト収集 ─────────────────────────────────────────────
async function collectListings(page) {
  const restaurants = new Map(); // url → { name, area, awards: [{year, category}] }
  let totalTried = 0, totalHits = 0, totalCount = 0;

  for (const cat of CATEGORIES) {
    for (const year of YEARS) {
      totalTried++;
      const url = `https://award.tabelog.com/hyakumeiten/${cat.slug}/${year}?pref=fukuoka`;
      try {
        const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 25000 });
        if (!resp || resp.status() === 404) {
          log(`  [skip] ${cat.label} ${year} (404)`);
          continue;
        }
        await page.waitForTimeout(800 + Math.random() * 600);

        const cards = await page.evaluate(() => {
          const out = [];
          // award.tabelog.com restaurant card selectors
          const sels = [
            'a[href*="tabelog.com/fukuoka"]',
          ];
          const seen = new Set();
          for (const sel of sels) {
            for (const a of document.querySelectorAll(sel)) {
              const href = a.href.split('?')[0];
              if (!href.match(/tabelog\.com\/fukuoka\/A\d+\/A\d+\/\d+/)) continue;
              if (seen.has(href)) continue;
              seen.add(href);
              // bubble up to find the card container with name+area
              let card = a;
              for (let i = 0; i < 6 && card.parentElement; i++) {
                card = card.parentElement;
                if (card.textContent.length > 30 && card.textContent.length < 500) break;
              }
              const txt = card.textContent.replace(/\s+/g, ' ').trim();
              // try to extract name from link text or nearby
              let name = a.textContent.trim();
              if (!name || name.length < 2) {
                const nameEl = card.querySelector('[class*="name"], h3, h4');
                if (nameEl) name = nameEl.textContent.trim();
              }
              out.push({ url: href, name, cardText: txt.slice(0, 200) });
            }
          }
          return out;
        });

        totalHits += cards.length;
        log(`  ${cat.label.padEnd(20)} ${year}: ${cards.length}件`);

        for (const c of cards) {
          totalCount++;
          if (!restaurants.has(c.url)) {
            restaurants.set(c.url, { name: c.name, cardText: c.cardText, awards: [] });
          }
          const rec = restaurants.get(c.url);
          // pick longer name if better
          if (c.name && c.name.length > rec.name.length) rec.name = c.name;
          rec.awards.push({ year, category: cat.label, slug: cat.slug });
        }
      } catch (err) {
        log(`  [err] ${cat.label} ${year}: ${err.message.slice(0, 60)}`);
      }
      await page.waitForTimeout(400 + Math.random() * 400);
    }
  }

  log(`\nPhase1: tried=${totalTried} hits=${totalHits} unique=${restaurants.size}`);
  return restaurants;
}

// ── Phase 2: 詳細ページから住所・価格を取得 ─────────────────────────────
async function fetchDetail(page, url) {
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(900 + Math.random() * 700);

    return await page.evaluate(() => {
      const out = { addr: null, dinner: null, lunch: null, genre: null, rating: null, name: null };

      // ── 店名 ──
      const nameEl = document.querySelector(
        'h2.display-name, .rstinfo-table__name-wrap span, [class*="display-name"] span'
      );
      if (nameEl) out.name = nameEl.textContent.trim();
      if (!out.name) {
        const h2 = document.querySelector('h2');
        if (h2) out.name = h2.textContent.trim().split('\n')[0];
      }

      // ── 住所 (JSON-LD 優先) ──
      for (const el of document.querySelectorAll('script[type="application/ld+json"]')) {
        try {
          const data = JSON.parse(el.textContent);
          const list = Array.isArray(data) ? data : [data];
          for (const o of list) {
            const a = o?.address || o?.location?.address;
            if (a && a.addressRegion) {
              out.addr = [a.addressRegion, a.addressLocality, a.streetAddress].filter(Boolean).join('');
              break;
            }
          }
          if (out.addr) break;
        } catch {}
      }
      if (!out.addr) {
        // table row "住所"
        for (const row of document.querySelectorAll('tr, dl > div')) {
          const th = row.querySelector('th, dt');
          if (th && th.textContent.includes('住所')) {
            const td = row.querySelector('td, dd');
            if (td) {
              out.addr = td.textContent.trim().replace(/\s+/g, '').replace(/大きな地図.*$/, '');
              break;
            }
          }
        }
      }

      // ── 価格 ──
      // Primary: rdheader-budget__price-target (header area, 2 targets: dinner, lunch)
      const hdrTargets = [...document.querySelectorAll('.rdheader-budget__price-target')];
      if (hdrTargets.length >= 1) out.dinner = hdrTargets[0].textContent.trim();
      if (hdrTargets.length >= 2) out.lunch  = hdrTargets[1].textContent.trim();

      // Fallback: gly-b-dinner / gly-b-lunch classes anywhere
      if (!out.dinner) {
        const e = document.querySelector('em.gly-b-dinner, .gly-b-dinner');
        if (e) out.dinner = e.textContent.trim();
      }
      if (!out.lunch) {
        const e = document.querySelector('em.gly-b-lunch, .gly-b-lunch');
        if (e) out.lunch = e.textContent.trim();
      }

      // Fallback: 予算 row in rstinfo-table
      if (!out.dinner || !out.lunch) {
        for (const row of document.querySelectorAll('tr')) {
          const th = row.querySelector('th');
          if (!th || !th.textContent.includes('予算')) continue;
          const dEl = row.querySelector('em.gly-b-dinner, .gly-b-dinner');
          const lEl = row.querySelector('em.gly-b-lunch, .gly-b-lunch');
          if (dEl && !out.dinner) out.dinner = dEl.textContent.trim();
          if (lEl && !out.lunch)  out.lunch  = lEl.textContent.trim();
          break;
        }
      }

      // Clean: "-" or empty
      if (out.dinner === '-' || out.dinner === '') out.dinner = null;
      if (out.lunch  === '-' || out.lunch  === '') out.lunch  = null;

      // ── ジャンル ──
      for (const row of document.querySelectorAll('tr')) {
        const th = row.querySelector('th');
        if (th && th.textContent.includes('ジャンル')) {
          const td = row.querySelector('td');
          if (td) out.genre = td.textContent.trim().replace(/\s+/g, ' ');
          break;
        }
      }

      // ── 評価 ──
      const rEl = document.querySelector(
        '.rdheader-rating__score-val, .c-rating-v3__val, [class*="rating-v3__val"]'
      );
      if (rEl) out.rating = rEl.textContent.trim();

      return out;
    });
  } catch (err) {
    log(`    detail err: ${err.message.slice(0, 60)}`);
    return null;
  }
}

// ── main ────────────────────────────────────────────────────────────────
(async () => {
  if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

  let listings;
  if (RESUME && fs.existsSync(LISTINGS_JSON)) {
    log(`Resume: load ${LISTINGS_JSON}`);
    listings = new Map(Object.entries(JSON.parse(fs.readFileSync(LISTINGS_JSON, 'utf-8'))));
  } else {
    log(`開始 Phase1 (headless=${HEADLESS})`);
    const browser = await chromium.launch({ headless: HEADLESS, slowMo: HEADLESS ? 0 : 100 });
    const ctx = await browser.newContext({
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
      locale: 'ja-JP',
      viewport: { width: 1440, height: 900 },
    });
    const page = await ctx.newPage();
    listings = await collectListings(page);
    await browser.close();

    const obj = Object.fromEntries(listings);
    fs.writeFileSync(LISTINGS_JSON, JSON.stringify(obj, null, 2), 'utf-8');
    log(`Phase1 出力: ${LISTINGS_JSON}  (${listings.size}店)`);
  }

  if (PHASE1_ONLY) {
    log('--phase1-only 指定のため終了');
    return;
  }

  // ── Phase 2 ──
  log(`\nPhase 2: 詳細ページ取得 (${listings.size}店)`);
  const browser = await chromium.launch({ headless: HEADLESS, slowMo: HEADLESS ? 0 : 50 });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    locale: 'ja-JP',
    viewport: { width: 1440, height: 900 },
  });
  const page = await ctx.newPage();

  const details = [];
  let i = 0;
  for (const [url, rec] of listings) {
    i++;
    log(`  [${i}/${listings.size}] ${rec.name || '(no name)'}`);
    const d = await fetchDetail(page, url);
    if (d) {
      const dp = parsePriceRange(d.dinner);
      const lp = parsePriceRange(d.lunch);
      details.push({
        url,
        name: d.name || rec.name,
        addr: d.addr,
        dinner: d.dinner,
        dinnerLower: dp.lower, dinnerUpper: dp.upper,
        lunch: d.lunch,
        lunchLower: lp.lower, lunchUpper: lp.upper,
        genre: d.genre,
        rating: d.rating,
        awards: rec.awards,
      });
      log(`    addr=${(d.addr || '').slice(0,30)} 夜=${d.dinner || '-'} 昼=${d.lunch || '-'} ★${d.rating || '-'}`);
    }
    // save incremental every 10
    if (i % 10 === 0) {
      fs.writeFileSync(DETAILS_JSON, JSON.stringify(details, null, 2), 'utf-8');
    }
    await page.waitForTimeout(1200 + Math.random() * 800);
  }
  await browser.close();
  fs.writeFileSync(DETAILS_JSON, JSON.stringify(details, null, 2), 'utf-8');

  // ── Phase 3: CSV出力 (Google マイマップ形式) ─────────────────────────
  const q = v => `"${String(v ?? '').replace(/"/g, '""').replace(/\n/g, ' ')}"`;

  const yearsOf = (awards) => [...new Set(awards.map(a => a.year))].sort().join(',');
  const catsOf  = (awards) => [...new Set(awards.map(a => a.category))].join('/');

  // filter rule: dinner lower < 6000, fallback to lunch lower if no dinner
  const ok = d => {
    if (d.dinnerLower !== null) return d.dinnerLower < MAX_DINNER_YEN;
    if (d.lunchLower  !== null) return d.lunchLower  < MAX_DINNER_YEN;
    return true; // unknown price → keep
  };

  const buildRow = (d) => {
    const desc = [
      `[${catsOf(d.awards)}]`,
      `受賞: ${yearsOf(d.awards)}`,
      d.dinner ? `夜 ${d.dinner}` : '',
      d.lunch  ? `昼 ${d.lunch}`  : '',
      d.rating ? `★${d.rating}`   : '',
      d.genre  ? `ジャンル: ${d.genre}` : '',
    ].filter(Boolean).join(' / ');
    return [q(d.name), q(d.addr || ''), q(desc), q(d.url)].join(',');
  };

  const filtered = details.filter(ok);
  const header = '名前,住所,説明,食べログURL\n';
  fs.writeFileSync(OUT_CSV,     '﻿' + header + filtered.map(buildRow).join('\n'), 'utf-8');
  fs.writeFileSync(OUT_CSV_ALL, '﻿' + header + details .map(buildRow).join('\n'), 'utf-8');

  log(`\n✅ 完了`);
  log(`  全件 ${details.length} → ${OUT_CSV_ALL}`);
  log(`  ≤¥${MAX_DINNER_YEN}: ${filtered.length} → ${OUT_CSV}`);
  console.log(JSON.stringify({
    all: details.length,
    filtered: filtered.length,
    csv: OUT_CSV,
    csvAll: OUT_CSV_ALL,
    hint: 'Google マイマップ → 新しい地図 → インポート → CSV → 位置=「住所」, タイトル=「名前」',
  }, null, 2));
})();
