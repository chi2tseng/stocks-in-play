// Playwright scraper: 食べログ 福岡百名店 (夕食 ≤6000円)
// 出力: tabelog_fukuoka_hyakumeiten.csv  → Google マイマップ インポート用
//
// Usage:
//   node tabelog-hyakumeiten-fukuoka.js
//   node tabelog-hyakumeiten-fukuoka.js --headless   (Cloudflare に弾かれやすいが速い)

const { chromium } = require('@playwright/test');
const fs  = require('fs');
const path = require('path');

const OUT_DIR  = __dirname;
const OUT_CSV  = path.join(OUT_DIR, 'tabelog_fukuoka_hyakumeiten.csv');
const MAX_DINNER_YEN = 6000;
const BASE_URL = 'https://tabelog.com/fukuoka/rstLst/?SrtT=rt&hyakumeiten=1';
const MAX_PAGES     = 150;   // hard cap
const STOP_EMPTY    = 5;     // 連続してバッジなしページが続いたら終了
const HEADLESS = process.argv.includes('--headless');

function log(msg) { process.stderr.write(`[${new Date().toISOString().slice(11,19)}] ${msg}\n`); }

// 価格テキスト ("夕¥5,000〜¥5,999" / "¥5,000〜" / "〜¥5,999") から
// 下限値を返す。見つからなければ null。
function parseLowerPrice(txt) {
  if (!txt) return null;
  const clean = txt.replace(/[,，￥¥,]/g, '').replace(/[^\d〜~～\-]/g, ' ').trim();
  const m = clean.match(/(\d+)/);
  return m ? parseInt(m[1], 10) : null;
}

// 全カードを評価して結果を返す（ブラウザ内で実行）
function extractCards() {
  const results = [];

  // Tabelog のカードセレクタ (複数候補)
  const cardSels = [
    '.list-rst__item',
    '.js-rst-cassette-wrap',
    '[class*="list-rst__item"]',
  ];
  let cards = [];
  for (const sel of cardSels) {
    const found = [...document.querySelectorAll(sel)];
    if (found.length > 0) { cards = found; break; }
  }

  for (const card of cards) {
    // ─── 百名店バッジ ───
    const badgeEl = card.querySelector(
      '[class*="hyakumeiten"], [class*="award-badge"], [class*="award_badge"],' +
      '.list-rst__award-badge, .c-award-badge'
    );
    let badgeText = badgeEl ? badgeEl.textContent.trim() : null;
    // フォールバック: テキスト全体に「百名店」が含まれるか
    if (!badgeText && card.textContent.includes('百名店')) {
      // 百名店テキストを含む最小要素を探す
      const walker = document.createTreeWalker(card, NodeFilter.SHOW_TEXT);
      let node;
      while ((node = walker.nextNode())) {
        if (node.textContent.includes('百名店')) {
          badgeText = node.textContent.trim();
          break;
        }
      }
    }

    // ─── 店名・URL ───
    const nameEl = card.querySelector(
      '.list-rst__rst-name-main a, .list-rst__name a, h3 a, .rst-cassette__name a'
    );
    const name = nameEl ? nameEl.textContent.trim() : null;
    const rstUrl = nameEl ? nameEl.href : null;
    if (!name || !rstUrl) continue;

    // ─── 夕食価格 ───
    // Tabelog は「夕」「昼」アイコン付きで表示する場合と
    // ただの価格テキストだけの場合がある
    let dinnerPrice = null;
    // 夕食専用セレクタ
    const dinnerEl = card.querySelector(
      '[class*="dinner"], [class*="night"], .list-rst__price--dinner, ' +
      '[class*="price-dinner"], [data-dinner]'
    );
    if (dinnerEl) {
      dinnerPrice = dinnerEl.textContent.trim();
    } else {
      // 価格ブロック全体から「夕」を含む行を探す
      const priceEls = [...card.querySelectorAll('[class*="price"], [class*="cost"]')];
      for (const el of priceEls) {
        const txt = el.textContent;
        if (txt.includes('夕') || txt.includes('ディナー') || txt.includes('Dinner')) {
          dinnerPrice = txt.trim();
          break;
        }
      }
      // それでも取れなければ最初の価格要素を使う
      if (!dinnerPrice && priceEls.length > 0) {
        dinnerPrice = priceEls[0].textContent.trim();
      }
    }

    // ─── ジャンル ───
    const genreEl = card.querySelector(
      '.list-rst__genre, .list-rst__area-genre, [class*="genre"]'
    );
    const genre = genreEl ? genreEl.textContent.trim().replace(/\s+/g, ' ') : null;

    // ─── 評価スコア ───
    const ratingEl = card.querySelector(
      '.c-rating-v3__val, .c-rating__val, [class*="rating__val"], [class*="rating-v"]'
    );
    const rating = ratingEl ? ratingEl.textContent.trim() : null;

    // ─── リスティング上の住所（補助） ───
    const addrEl = card.querySelector(
      '.list-rst__address, .list-rst__area-text, [class*="address"]'
    );
    const listingAddr = addrEl ? addrEl.textContent.trim().replace(/\s+/g, ' ') : null;

    results.push({ name, rstUrl, badgeText, dinnerPrice, genre, rating, listingAddr });
  }
  return results;
}

// 詳細ページから完全住所を取得
async function fetchAddress(page, url) {
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(1200 + Math.random() * 800);

    return await page.evaluate(() => {
      // 1) JSON-LD の PostalAddress (最も信頼性が高い)
      for (const el of document.querySelectorAll('script[type="application/ld+json"]')) {
        try {
          const obj = JSON.parse(el.textContent);
          const candidates = Array.isArray(obj) ? obj : [obj];
          for (const c of candidates) {
            const addr = c?.address || c?.location?.address;
            if (addr && addr.addressRegion) {
              return [
                addr.addressRegion || '',
                addr.addressLocality || '',
                addr.streetAddress || '',
              ].join('');
            }
          }
        } catch {}
      }

      // 2) テーブル内「住所」行
      for (const row of document.querySelectorAll('tr, .p-rst-detail-map__address')) {
        const th = row.querySelector('th, dt');
        if (th && th.textContent.includes('住所')) {
          const td = row.querySelector('td, dd');
          if (td) return td.textContent.trim().replace(/\s+/g, '');
        }
      }

      // 3) 住所クラス直接
      const addrEl = document.querySelector(
        '.rstinfo-table__address, [class*="address--full"], .p-restaurant-detail__address'
      );
      if (addrEl) return addrEl.textContent.trim().replace(/\s+/g, '');

      return null;
    });
  } catch (err) {
    log(`  住所取得失敗 (${url}): ${err.message.slice(0, 60)}`);
    return null;
  }
}

(async () => {
  log(`開始 headless=${HEADLESS}  URL=${BASE_URL}`);

  const browser = await chromium.launch({
    headless: HEADLESS,
    slowMo: HEADLESS ? 0 : 400,
  });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    locale: 'ja-JP',
    viewport: { width: 1440, height: 900 },
  });
  const page = await ctx.newPage();

  // ── Phase 1: リスティングページを巡回 ────────────────────────────────
  const collected = new Map();   // rstUrl → data
  let emptyRun    = 0;
  let totalCards  = 0;
  let totalBadge  = 0;

  for (let p = 1; p <= MAX_PAGES; p++) {
    const url = p === 1 ? BASE_URL : `${BASE_URL}&p=${p}`;
    log(`[P${p}] ${url}`);

    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(2500);
    } catch (err) {
      log(`  goto 失敗: ${err.message.slice(0, 80)}`);
      break;
    }

    // 実際の件数をページ上から取得 (初回のみ)
    if (p === 1) {
      const countText = await page.$eval(
        '.c-page-count__all, [class*="count__all"], [class*="total-count"]',
        el => el.textContent
      ).catch(() => null);
      log(`  表示件数: ${countText || '(取得できず)'}`);
    }

    let cards;
    try {
      cards = await page.evaluate(extractCards);
    } catch (err) {
      log(`  evaluate 失敗: ${err.message.slice(0, 80)}`);
      break;
    }

    totalCards += cards.length;
    const badgeCards = cards.filter(c => c.badgeText && c.badgeText.includes('百名店'));
    totalBadge += badgeCards.length;

    log(`  カード=${cards.length}  バッジ付き=${badgeCards.length}`);

    if (badgeCards.length === 0) {
      emptyRun++;
      log(`  空ページ連続: ${emptyRun}/${STOP_EMPTY}`);
      if (emptyRun >= STOP_EMPTY) { log('早期終了 (バッジなし連続)'); break; }
    } else {
      emptyRun = 0;
    }

    for (const card of badgeCards) {
      if (collected.has(card.rstUrl)) continue;

      const lp = parseLowerPrice(card.dinnerPrice);
      if (lp !== null && lp > MAX_DINNER_YEN) {
        log(`  SKIP ${card.name} (¥${lp} > ¥${MAX_DINNER_YEN})`);
        continue;
      }
      // 価格情報がない場合は保留（詳細ページで確認）
      collected.set(card.rstUrl, { ...card, priceOk: lp !== null });
      log(`  ✓ ${card.name}  [${card.dinnerPrice || '価格未確認'}]  ${(card.badgeText || '').slice(0,50)}`);
    }

    // ページネーション: 次ページボタンの有無を確認
    const hasNext = await page.evaluate(() => {
      const btn = document.querySelector(
        '.c-pagination__item--next:not(.is-disabled), .pagination__next:not(.is-disabled), a[rel="next"]'
      );
      return !!btn;
    });
    if (!hasNext && badgeCards.length === 0) { log('次ページなし → 終了'); break; }

    await page.waitForTimeout(2000 + Math.random() * 2000);
  }

  log(`\nPhase 1 完了: スキャンカード=${totalCards}  バッジ発見=${totalBadge}  収集=${collected.size}`);

  // ── Phase 2: 詳細ページから住所取得 ─────────────────────────────────
  log(`\nPhase 2 開始: ${collected.size}件の住所を取得...`);
  const restaurants = [];
  let i = 0;
  for (const [url, data] of collected) {
    i++;
    log(`  [${i}/${collected.size}] ${data.name}`);
    const fullAddr = await fetchAddress(page, url);
    log(`    住所: ${fullAddr || '(取得失敗)'}`);
    restaurants.push({ ...data, fullAddr });
    await page.waitForTimeout(1800 + Math.random() * 1500);
  }

  await browser.close();

  // ── Phase 3: CSV出力 ─────────────────────────────────────────────────
  const q = v => `"${(v || '').replace(/"/g, '""').replace(/\n/g, ' ')}"`;

  const rows = restaurants.map(r => {
    const desc = [
      r.dinnerPrice ? `夕食: ${r.dinnerPrice}` : '夕食: 価格未掲載',
      r.genre       ? `ジャンル: ${r.genre}`   : '',
      r.badgeText   ? r.badgeText.replace(/\s+/g, ' ').slice(0, 80) : '',
      r.rating      ? `★${r.rating}`           : '',
    ].filter(Boolean).join(' / ');

    const addr = r.fullAddr || r.listingAddr || '';
    return [q(r.name), q(addr), q(desc), q(r.rstUrl)].join(',');
  });

  const header = '名前,住所,説明,食べログURL\n';
  fs.writeFileSync(OUT_CSV, '﻿' + header + rows.join('\n'), 'utf-8');

  log(`\n✅ 完了: ${restaurants.length}件 → ${OUT_CSV}`);
  console.log(JSON.stringify({
    total: restaurants.length,
    csv: OUT_CSV,
    note: 'Google マイマップ → インポート → CSV → 「名前」「住所」列を指定してください',
  }, null, 2));
})();
