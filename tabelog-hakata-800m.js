// Playwright: 抓 Tabelog 博多駅 800m 內、按評分高到低
// 輸出 D:/Tabelog/hakata_top.csv
//
//   node tabelog-hakata-800m.js [--pages N] [--min-rating 3.5]

const { chromium } = require('@playwright/test');
const fs = require('fs');

const OUT_CSV  = 'D:/Tabelog/hakata_top.csv';
const PAGES = (() => { const i = process.argv.indexOf('--pages'); return i >= 0 ? parseInt(process.argv[i+1], 10) : 5; })();
const MIN_RT = (() => { const i = process.argv.indexOf('--min-rating'); return i >= 0 ? parseFloat(process.argv[i+1]) : 3.5; })();
const BASE = 'https://tabelog.com/fukuoka/A4001/A400101/rstLst/?sa=%E5%8D%9A%E5%A4%9A%E9%A7%85&LstRng=2&SrtT=rt';

function log(msg) { process.stderr.write(`[${new Date().toISOString().slice(11,19)}] ${msg}\n`); }

(async () => {
  const b = await chromium.launch({ headless: true });
  const ctx = await b.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    locale: 'ja-JP',
    viewport: { width: 1440, height: 900 },
  });
  const page = await ctx.newPage();

  const all = [];
  for (let p = 1; p <= PAGES; p++) {
    const url = p === 1 ? BASE : `${BASE}&page=${p}`;
    log(`[P${p}] ${url}`);
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(2500);

    const rows = await page.evaluate(() => {
      const out = [];
      for (const card of document.querySelectorAll('.list-rst__wrap')) {
        const a = card.querySelector('a[href*="/fukuoka/A"]');
        if (!a) continue;
        const url = a.href.split('?')[0];
        if (!url.match(/\/fukuoka\/A\d+\/A\d+\/\d+/)) continue;

        // rating (NOT .c-rating-v3 which is price; rating uses .c-rating__val)
        const rEl = card.querySelector('.list-rst__rating-val, .c-rating__val');
        const rating = rEl ? parseFloat(rEl.textContent.trim()) : null;

        // name = first non-empty anchor text (sometimes "1にしむら" because of leading rank number)
        let name = a.textContent.trim().replace(/^\d+/, '').trim();

        // parse the full card text — pattern:
        //   [rank][name] [駅] [distance] / [genre] [tagline] [rating] [review_count] [save_count] [dinner_price] [lunch_price] ...
        const text = card.textContent.replace(/\s+/g, ' ').trim();
        // station + distance pattern: "(駅名) 数字m"
        const stMatch = text.match(/([^\s]+駅)\s+(\d+m)/);
        const station = stMatch ? stMatch[1] : '';
        const distance = stMatch ? stMatch[2] : '';

        // genre after "/" before tagline
        let genre = '';
        if (stMatch) {
          const after = text.slice(text.indexOf(stMatch[0]) + stMatch[0].length);
          const gm = after.match(/^\s*\/\s*([^4-9\d]+?)(?=[ ]+[一-龯]|[ ]+\d|$)/);
          if (gm) genre = gm[1].trim().slice(0, 40);
        }

        // dinner / lunch — find blocks with c-rating-v3__time--dinner / lunch
        const priceBlocks = [...card.querySelectorAll('.c-rating-v3')];
        let dinner = '', lunch = '';
        for (const blk of priceBlocks) {
          const isDinner = blk.querySelector('.c-rating-v3__time--dinner');
          const isLunch  = blk.querySelector('.c-rating-v3__time--lunch');
          const v = blk.querySelector('.c-rating-v3__val')?.textContent.trim() || '';
          if (isDinner) dinner = v;
          if (isLunch)  lunch  = v;
        }

        const hyaku = card.querySelector('.list-rst__award-badge') ? '✓' : '';

        out.push({ name, url, rating, station, distance, genre, dinner, lunch, hyaku });
      }
      return out;
    });

    log(`  got ${rows.length}, total ${all.length + rows.length}`);
    all.push(...rows);
    await page.waitForTimeout(1500);
  }
  await b.close();

  // dedupe + filter
  const seen = new Map();
  for (const r of all) {
    if (!seen.has(r.url)) seen.set(r.url, r);
  }
  let list = [...seen.values()];

  list = list.filter(r => r.rating !== null && r.rating >= MIN_RT);
  list.sort((a, b) => (b.rating || 0) - (a.rating || 0));

  // load existing 百名店 set
  let hyakuSet = new Set();
  try {
    const det = JSON.parse(fs.readFileSync('D:/Tabelog/details.json', 'utf-8'));
    hyakuSet = new Set(det.map(d => d.url));
  } catch {}

  // write CSV
  const q = v => `"${String(v ?? '').replace(/"/g, '""').replace(/\n/g, ' ')}"`;
  const header = '名前,評分,駅,距離,ジャンル,夜,昼,百名店?,食べログURL\n';
  const rows = list.map(r => {
    const inHyaku = hyakuSet.has(r.url) ? '✓' : '';
    return [q(r.name), q(r.rating), q(r.station), q(r.distance), q(r.genre), q(r.dinner), q(r.lunch), q(inHyaku), q(r.url)].join(',');
  });
  fs.writeFileSync(OUT_CSV, '﻿' + header + rows.join('\n'), 'utf-8');

  log(`\n✅ ${list.length} restaurants (rating ≥ ${MIN_RT}) → ${OUT_CSV}`);
  console.log('\nTop 30:');
  console.log('# | ★    | 百 | 名前                          | 駅 距離 / ジャンル');
  list.slice(0, 30).forEach((r, i) => {
    const flag = hyakuSet.has(r.url) ? '✓' : ' ';
    console.log(`${String(i+1).padStart(2)}| ${r.rating} | ${flag} | ${(r.name||'').padEnd(30).slice(0,30)} | ${r.station} ${r.distance} / ${(r.genre||'').slice(0,30)}`);
  });
})();
