// Playwright X (Twitter) cashtag scraper for /SIPs Phase 2.3.
// WebSearch 到不了 X — 用登入後的持久 profile 直接開搜尋頁。
//
//   一次性設定:  node x-scrape.js --login     (開視窗手動登入,cookie 存 .x-profile/,已 gitignore)
//   每日使用:    node x-scrape.js GMM JLHL WOK  (headless,每檔抓 live 搜尋前 ~15 則)
//
// Output: x-posts.json  { _fetched, _authOk, items: { SYM: [ {name, handle, time, text, metrics} ] } }
// 紀律:X 內容=傳聞層,主流程寫進 catalyst/rationale 必標「X 傳聞未證實」。
// 遇到 captcha / 驗證挑戰:直接結束回報,禁止繞過。

const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const DIR = process.env.SIPS_DIR ? path.resolve(process.env.SIPS_DIR) : __dirname;
const PROFILE = path.join(DIR, '.x-profile');
const OUT = path.join(DIR, 'x-posts.json');
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36';
const MAX_TICKERS = 8;
const MAX_POSTS = 15;

async function launch(headless) {
  const opts = { headless, userAgent: UA, viewport: { width: 1280, height: 900 } };
  try {
    return await chromium.launchPersistentContext(PROFILE, { ...opts, channel: 'chrome' });
  } catch (e) {
    return await chromium.launchPersistentContext(PROFILE, opts); // bundled chromium fallback
  }
}

async function doLogin() {
  const ctx = await launch(false);
  const page = ctx.pages()[0] || (await ctx.newPage());
  await page.goto('https://x.com/login', { waitUntil: 'domcontentloaded' });
  console.log('請在開啟的視窗完成 X 登入(含兩步驟驗證)。登入成功導向首頁後視窗會自動關閉,最多等 5 分鐘…');
  try {
    await page.waitForURL(u => `${u}`.includes('x.com/home'), { timeout: 300000 });
    console.log('[OK] 已登入,cookie 存於 .x-profile/。之後可 headless 使用。');
  } catch (e) {
    console.log('[WARN] 5 分鐘內未偵測到登入完成。若其實已登入,直接重跑抓取試試。');
  }
  await ctx.close();
}

async function scrapeSym(page, sym) {
  const q = encodeURIComponent('$' + sym);
  await page.goto(`https://x.com/search?q=${q}&src=typed_query&f=live`, { waitUntil: 'domcontentloaded', timeout: 45000 });
  // auth wall?
  const u = page.url();
  if (u.includes('/i/flow/login') || u.includes('/login') || u.includes('mode=login') || u.includes('/onboarding/')) return { needsLogin: true, posts: [] };
  const wallCheck = async () => {
    const u2 = page.url();
    if (u2.includes('mode=login') || u2.includes('/onboarding/') || u2.includes('/i/flow/login')) return true;
    return page.evaluate(() => !!document.querySelector(
      '[data-testid="loginButton"], [data-testid="signupButton"], [data-testid="google_sign_in_container"], a[href="/i/flow/signup"], a[href="/login"], input[autocomplete="username"]'));
  };
  try {
    await page.waitForSelector('article[data-testid="tweet"]', { timeout: 20000 });
  } catch (e) {
    const challenge = await page.evaluate(() => /verify|challenge|unusual/i.test(document.body.innerText.slice(0, 2000)));
    if (challenge) return { challenge: true, posts: [] };
    return { needsLogin: await wallCheck(), posts: [] };
  }
  await page.mouse.wheel(0, 2500);
  await page.waitForTimeout(1200);
  const posts = await page.evaluate((MAX) => {
    const out = [];
    for (const a of document.querySelectorAll('article[data-testid="tweet"]')) {
      if (out.length >= MAX) break;
      const text = a.querySelector('[data-testid="tweetText"]')?.innerText || '';
      if (!text) continue;
      const user = a.querySelector('[data-testid="User-Name"]')?.innerText || '';
      const [name, handle] = user.split('\n');
      const time = a.querySelector('time')?.getAttribute('datetime') || '';
      const metrics = a.querySelector('[role="group"]')?.getAttribute('aria-label') || '';
      out.push({ name: name || '', handle: handle || '', time, text: text.slice(0, 400), metrics });
    }
    return out;
  }, MAX_POSTS);
  if (!posts.length && (await wallCheck())) return { needsLogin: true, posts: [] };
  return { posts };
}

(async () => {
  const args = process.argv.slice(2);
  if (args.includes('--login')) return doLogin();
  const syms = args.map(s => s.toUpperCase().replace(/^\$/, '')).filter(Boolean).slice(0, MAX_TICKERS);
  if (!syms.length) { console.log('用法: node x-scrape.js SYM1 SYM2 ...   (首次先 node x-scrape.js --login)'); process.exit(1); }

  const ctx = await launch(true);
  const page = ctx.pages()[0] || (await ctx.newPage());
  const items = {};
  let authOk = true;
  for (const sym of syms) {
    try {
      const r = await scrapeSym(page, sym);
      if (r.challenge) { console.log(`[STOP] ${sym}: X 丟出驗證挑戰 — 請手動跑 node x-scrape.js --login 處理,不自動繞過`); authOk = false; break; }
      if (r.needsLogin) { console.log(`[STOP] 未登入 — 先跑: node x-scrape.js --login`); authOk = false; break; }
      items[sym] = r.posts;
      console.log(`${sym}: ${r.posts.length} posts`);
    } catch (e) {
      console.log(`[warn] ${sym}: ${e.message.slice(0, 120)}`);
      items[sym] = [];
    }
    await page.waitForTimeout(1500 + Math.random() * 1500);
  }
  await ctx.close();
  fs.writeFileSync(OUT, JSON.stringify({ _fetched: new Date().toISOString(), _authOk: authOk, items }, null, 2), 'utf-8');
  console.log(`[OK] x-posts.json: ${Object.keys(items).length} tickers, authOk=${authOk}`);
})();
