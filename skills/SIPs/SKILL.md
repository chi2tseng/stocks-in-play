---
name: SIPs
description: Daily NTRT/MTRT gap scanner — scrape Barchart pre+post-market gappers, classify with MAGNA53 + Stockbee SIP framework, pull TradingView quarterly forecasts for earnings movers and Finviz short interest for every candidate, then publish a 繁體中文 morning brief plus a static-SPA "Stocks In Play" dashboard. Use this skill when the user wants their daily SIP scan, types `/SIPs`, or asks for the day's best longs/shorts. Optional arg = comma-separated tickers to skip the screen (e.g. `/SIPs NVDA,AAPL`).
allowed-tools: Bash, Read, Write, WebSearch, WebFetch, Grep, Glob
---

> **Install (invited collaborators only):** export `GH_TOKEN`, then `npx skillfish add chi2tseng/stocks-in-play SIPs`
> **Code (private repo):** <https://github.com/chi2tseng/stocks-in-play>
> **Dashboard:** local-only — runs on `http://127.0.0.1:5510` after `mcp__Claude_Preview__preview_start`. No hosted URL.
>
> **Working directory:** this skill assumes you've cloned the repo and are running from its root. Scripts use `process.cwd()` / `__file__`-relative paths so they work regardless of where you cloned to. Override the data location with `SIPS_DIR` env var.

# /SIPs — Daily NTRT/MTRT gap scanner & SIP/EP report

> **⚠ 身分路由(先讀我):** 本檔是 **Claude 專用**的總指揮流程。
> 若你不是 Claude(你是 Codex/ChatGPT、Gemini/agy 或 Grok),而使用者只打了 `/SIPs`:
> **你的角色 = 自家評審,不是跑本檔。** 立刻改讀你自己的 picks skill 並照做:
> Codex → `C:\Users\chi2t\.codex\skills\SIPs-codex-picks\SKILL.md`;
> Gemini → `C:\Users\chi2t\.gemini\skills\SIPs-gemini-picks\SKILL.md`;
> Grok → `C:\Users\chi2t\.grok\skills\SIPs-grok-picks\SKILL.md`。
> 只有使用者明講「full / 全套掃描」時,非 Claude agent 才執行本檔全流程(另見 D:\SIPs\AGENTS.md)。

> **本檔為正本;`/SIPs` 實際注入 `~/.claude/commands/SIPs.md`(語意需同步,見硬規則四副本)。**

You are running the user's daily **NTRT (News-Triggered) / MTRT (Momentum-Triggered)** trading routine to find **SIPs (Stocks In Play) / EPs (Earnings Plays)**. The final deliverable is a 繁體中文 morning brief ranking the day's best longs and shorts, with strict-format YoY estimate blocks for every earnings mover.

If `$ARGUMENTS` is non-empty (e.g. `NVDA,AAPL`), **skip Phase 1** and treat that list as the candidate set. Otherwise run Phase 1.

Use TodoWrite to track the phases. Surface progress aggressively — the user gets anxious when commands run silently.

---

## § 0. Daily-run quick reference (this is what runs each morning)

| Step | Tool | Time | Cost | Output |
|---|---|---|---|---|
| 1. Gap scan | `node ./barchart-scrape.js` (Playwright + XHR intercept) | ~7s | $0 | `candidates.csv` (84-ish rows) |
| 2. Catalyst hunt | **4-6 個 `general-purpose` Agents** on **`model: "haiku"`** (§ 0.5), **6-8 檔 each**(依當日候選數動態分片,同一訊息一次全發)doing parallel WebSearches on **all** candidates | ~90s | $0 | inline markdown table → updates `catalysts` dict in `build_report.py` |
| 3. TradingView FQ | `node ./tv-scrape.js TICKER1 TICKER2 ...` | ~3-5s per ticker | $0 | `<TICKER>-earnings-fq.md` |
| 4. Parse TV | `py ./parse_tv.py` | <1s | $0 | `tv-summary.json` + `tv-summary.csv` |
| 4b. Backfill earnings dates | `py ./fetch_earnings_dates.py` | ~5-15s | $0 | Updates `tv-summary.json` in place. For tickers TV showed "Next report date" (no past date), queries NASDAQ's earnings-surprise endpoint for the most recent `dateReported`. Pushes coverage from ~70% → ~94%. |
| **5. Finviz shorts + perf** | `node ./finviz-shorts.js` (parallel, throttled) | ~70-90s | $0 | `shorts.json` (shortFloat / shortRatio / marketCap_M / perf1M-12M for every candidate) |
| 6. Build report | `py build_report.py` + `py gen_tables.py` | <1s | $0 | `final-candidates.csv` + `sorted-views.md` |
| 7. Final brief | Claude composes the 繁體中文 brief | — | — | inline in chat |
| **8. Write news_detail.json** | **Claude curates per-symbol `detail` + `publishedAt` for the top 10 SIPs** | ~3 min | $0 | `news_detail.json` (top-10 only; rest auto-fallback to catalyst sentence) |
| **9. Write claude_picks.json** | **Claude writes hand-picked rankings + 繁中 rationale + `intent: long\|short` for 5-10 highest-conviction picks** | ~2 min | $0 | `claude_picks.json` ([{symbol, rank, intent, rationale}]) — drives the **default "Claude 精選"** subtab on Today's SIPs. **Direction-match rule:** `intent: long` only for gap-up tickers (chgPct > 0); `intent: short` only for gap-down (chgPct < 0). Dashboard silently drops mismatches. |
| **9b. Fetch 6-month candles** | `py fetch_candles.py` (Yahoo Finance daily bars, parallel) | ~5-10s | $0 | `dashboard/candles.json` (~150-200KB; powers the 股價走勢 chart on stock-detail pages) |
| **10. Publish dashboard** | `py build_dashboard.py` (no args = today's ISO date) | <1s | $0 | `dashboard/data/<DATE>.json`, `dates.json`, `data.json`, `index.html` |
| **11. Push to GitHub Pages** | `git add dashboard/ + JSON state files; git commit; git push` | ~5s + 30s deploy | $0 | hosted dashboard at <https://chi2tseng.github.io/stocks-in-play/> auto-updates |
| ~~12. 發射其他評審~~ | **已取消(2026-07-13)** — Claude 不再自動發射;各 AI 各自在自己 CLI 打 /SIPs 獨立跑(§ 8.8) | — | — | 各家自己 scan/pick/publish |

**Total runtime:** 主線發布 ~8-10 min(順利日 ~8 分,補搜多/earnings 密集日 ~10-12 分;收尾補漏另計)including news-detail curation. 瓶頸 = fact-sheet 蒐集 + 主模型寫作。 **Total cost:** $0.

**Key files in repo root (working directory):**
- `barchart-scrape.js` — Playwright Barchart scraper (XHR intercept on `/proxies/core-api/v1/quotes/get`)
- `tv-scrape.js` — Playwright TradingView FQ scraper (handles NASDAQ→NYSE→AMEX auto-detect)
- **`finviz-shorts.js`** — Playwright Finviz quote-page scraper (concurrency 2 + jitter to avoid Cloudflare). Reads tickers from `candidates.csv` and writes `shorts.json` with shortFloat / shortRatio / marketCap_M / floatShares_M / perf1M / perf3M / perf6M / perfYTD / perf12M per ticker. Powers the **N (Neglect)** + **5 (DTC)** MAGNA bits and the Short Squeeze page.
- `parse_tv.py` — extracts Reported + Estimate raw figures + YoY block from TradingView markdown
- `build_report.py` — merges candidates.csv + tv-summary.json + catalysts dict → final-candidates.csv
- `gen_tables.py` — produces 3 sorted markdown views (|%Chg| / Session / Price)
- **`fetch_candles.py`** — Yahoo Finance daily-bar scraper. Pulls last ~130 trading days (~6 months) for every ticker in today's candidates + claude/codex/gemini/grok picks + saved studies. Parallel (8 workers), ~5-10s for 50-100 tickers. Output: `dashboard/candles.json` (~150-200KB) consumed by the stock-detail page's 股價走勢 TradingView-style chart. **⚠ 排序陷阱(2026-07-06 踩過):它從 `dashboard/data/<DATE>.json` 讀今日候選清單,而那檔是 `build_dashboard.py` 寫的 → 所以必須 `build_dashboard.py` 先跑寫出今日 data 檔,`fetch_candles.py` 再跑(candles.json 是 runtime fetch,build 後補跑不用再 build)。首跑順序若相反,fetch 讀到舊 data 檔 → 新候選缺 candle → 詳細頁「股價走勢」整段消失。完成前務必 `py` 比對 candidates vs candles keys 確認覆蓋率。支援選用日期參數 `py fetch_candles.py YYYY-MM-DD`(週末/隔日補跑必傳掃描日,否則讀錯日檔)。**
- **`build_dashboard.py`** — assembles `dashboard/data/<DATE>.json` + writes the static SPA at `dashboard/index.html` (revolut design system, "Stocks In Play" branding). Merges `shorts.json` + `claude_picks.json` if present.
- **`news_detail.json`** — per-symbol detail + `publishedAt` (real news publication time). Optional input; spec at `NEWS_TIME_SPEC.md`.
- **`claude_picks.json`** — `{ "picks": [ {"symbol", "rank", "intent": "long"|"short", "rationale", "neglected"?: bool} ] }`. Drives the **default "Claude 精選"** subtab on Today's SIPs. **Direction-match rule:** longs must be gap-up, shorts must be gap-down — mismatches are silently filtered out by the dashboard. Symbols not in today's candidates also drop.
- **`codex_picks.json` / `gemini_picks.json` / `grok_picks.json`** — 同 schema 的其他 agent picks 檔,各驅動自己的 subtab(ChatGPT / Gemini / Grok)。**多 agent 分工契約(2026-07-10 定版):機械掃描只做一次、新聞研究與判斷各自獨立** — 共享研究包 = 當日 `dashboard/data/<DATE>.json`(由 Claude `/SIPs`、Grok `/SIPs-grok-gather` 或 Gemini `/SIPs-gemini-gather` 產出,內含每檔 catalyst/newsDetail/tv/shorts);三個評審(`/SIPs-codex-picks`、`/SIPs-gemini-picks`、`/SIPs-grok-picks`)讀包後**各自上網查證、各自判斷,不共享新聞、不互看**。每個 agent 只准寫自己的 picks 檔。
- **`NEWS_TIME_SPEC.md`** — contract for how to source + format real news timestamps. Read it BEFORE writing `news_detail.json` (see § 8 below for the integration).

**Dashboard URL:** http://127.0.0.1:5510/ (served by the `sips-dashboard` preview server, started by `mcp__Claude_Preview__preview_start` with name `sips-dashboard` and `port: 5510`). The server is always running once started; the dashboard auto-refreshes when `data/<DATE>.json` is rewritten.

---

## § 0.5 Model routing & token budget (READ FIRST — this is a COST rule, not a quality rule)

**Principle: cheap models GATHER, the smartest model JUDGES.** All final analysis — MiLan 深度拆解, Tier ratings, claude_picks rankings, the 繁中 brief — is composed by the MAIN model (Fable / Opus max). Everything mechanical (web searches, scraping, fact collection, table assembly) is delegated to cheap subagents. A previous run burned ~400k subagent tokens at main-model pricing because Agent calls inherited the parent model — never again.

**主跑模型 = Opus 4.8(或當前 session 模型)** — 路由表不變:haiku 蒐集(催化劑/pre-scan)、sonnet 事實包、主模型判斷與寫作。

**Hard routing table (when running under Claude Code — Agent tool `model` param):**

| Work | Who | Why |
|---|---|---|
| Phase 2.0 macro/policy pre-scan | 1 Agent, `model: "haiku"` | 5 WebSearches + cluster-map assembly is mechanical. Returns ≤600-token cluster map. |
| Phase 2.1 per-ticker catalyst hunt | **4-6 個 haiku agents**, `model: "haiku"`, **6-8 檔 each**(依當日候選數動態分片) | One-line catalyst per ticker = summarization, not judgment. 更多更小的分片 → 同一訊息一次全發、目標 ~90 秒回齊。 |
| Phase 8 fact-sheet gathering (top-10 deep-dive research) | **每 2 檔一個 sonnet agent(約 5-7 個)**, `model: "sonnet"` | 8-K parsing + segment/guidance numbers need care but not genius. Facts only, no verdicts. 小分片 + 6 分鐘硬上限避免單一 agent 拖垮全 run。 |
| MAGNA53 classification, day_resets judgment | MAIN model | Judgment calls on the already-compact table. |
| § 7.0 MiLan 深度拆解 + Tier ratings | **MAIN model — NEVER delegate** | This is the product. |
| claude_picks.json rankings + rationales | **MAIN model — NEVER delegate** | This is the product. |
| 繁中 brief composition | **MAIN model** | Final deliverable. |

**Subagent output caps (enforce in every Agent prompt):**
- Catalyst-hunt agents: return ONLY the markdown table, one line per ticker, ≤40 字 per catalyst, NO sources section, NO preamble. Sources are only needed for the top-10 (gathered later by the fact-sheet agents).
- Fact-sheet agents: return per-ticker structured fact sheets (see § 8.0), ≤500 tokens per ticker, raw numbers + URLs only — explicitly instruct "NO analysis, NO conclusions, NO tier opinions; those belong to the caller." **每檔 ≤4 次搜尋、單 agent 硬上限 6 分鐘,到時交件、缺欄寫 not found。**
- Pre-scan agent: cluster map only, ≤600 tokens total.

**Main-context hygiene (applies to the MAIN model itself):**
- Run `py parse_tv.py`, `py fetch_earnings_dates.py`, `py fetch_candles.py`, `node finviz-shorts.js` with output suppressed or tail-ed (`| tail -3`). The full 170-row parse table is ~4k tokens of noise — query `tv-summary.json` selectively for candidate tickers via a small `py -c` filter instead.
- Never `cat`/Read whole JSON artifacts (`tv-summary.json`, `shorts.json`, `candles.json`, day files) into context. Use `py -c` one-liners that print only the tickers/fields needed.
- Don't re-read files you just wrote. Don't echo full file contents to "verify" — spot-check 1-2 fields.
- WebSearch/WebFetch in the main context is allowed ONLY during final analysis when a specific fact is missing from the fact sheets (target: ≤5 such calls per run).

**Cost math (why this matters):** gathering ≈ 400-500k tokens/run. At main-model pricing that dwarfs everything else; on haiku it's ~1/10th the cost, on sonnet ~1/3. Final analysis is ~30-60k tokens and stays premium. Net effect: same-quality picks at roughly 70-85% lower spend.

**When running under Gemini/Codex CLI** (`/SIPs-gemini-full`, `/SIPs-codex-full`): the Agent-model params don't exist there — keep the same structure (delegate gathering to whatever cheap sub-mechanism is available, or just do it inline) and keep the output caps + main-context hygiene rules, which save tokens on any runtime.

---

## § 0.6 Wall-clock parallelization (SPEED rule — launch order ≠ phase order)

> **主跑模型 = Opus 4.8(或當前 session 模型)。** 路由表不變:haiku 蒐集、sonnet 事實包、主模型判斷與寫作。以下的 fan-out/join 骨架就是要讓主模型的寫作時間蓋住其餘所有 I/O。

The § numbering below is the LOGICAL order, not the execution order. Phases 2 / 5 / 5b / 9b have **no data dependencies between each other** — only Phase 1's `candidates.csv` gates them. Run the pipeline as a fan-out, not a chain:

**T+0 — Phase 1**: `node barchart-scrape.js` (~7s, foreground — everything needs candidates.csv).

**T+7s — fan out EVERYTHING at once** (background bash + background agents, all launched in a single message):
1. **4-6 個 haiku catalyst agents (§ 2.1),每個 6-8 檔**(依當日候選數動態分片,同一訊息一次全發,目標 ~90 秒回齊)— do **NOT** wait for the cluster map
2. 1× haiku pre-scan agent (§ 2.0) — its cluster map gets applied later at the § 2.2 cross-check
3. `node finviz-shorts.js` (background bash, ~90s)
4. **投機 X 查證(§ 2.3):同一批 fan-out 就發 `node x-scrape.js`** 給「`|chgPct|` 最大的 5 檔低價/低市值候選」— **不等 haiku 標「查無」**,資料先到手;§ 2.3 的正式查證與一級源對照照舊。
5. **TV scrape(§ 6.1):先跑凍結快取檢查**;stale 且**疑似 earnings** 的 → **T+7s 就發 1 個分片**;其餘 tickers 等 Join #1 的 Type 標籤確定後,再開 **2 個分片**補跑(freshness cache 先套 — skip files <3 days old)。
6. `py fetch_candles.py` (background bash — candidates + studies are already known; picks ⊆ candidates by the direction-match rule, so no need to wait for picks)
7. `py bignames-scan.py` (background bash, ~30–45s — §2.0c 大型股 ≥2% 全掃;回來的漏網大股併進 §2.1 catalyst fan-out,以 `Session=headline` 補入)

**While the fan-out runs (~90s–2 min)**, the main model does zero-dependency work: day_resets context review, Phase 10b OHLCV prep, studies placeholder checks.

**Join #1** (catalyst tables + shorts.json back) → MAGNA53 ranking → top-10 known → **立即在背景發射 fact-sheet agents:每 2 檔一個 sonnet agent(約 5-7 個),每檔 ≤4 次搜尋、單 agent 硬上限 6 分鐘,到時交件、缺欄寫 not found**(§ 8.0;§ 8.0 3b 的每檔 ≤4 搜尋規範仍適用)。同時把 Join #1 才確定 `Type=earnings` 的 tickers 補進 TV scrape 的 2 分片。

**While fact-sheets run (~1-2 min)**, main model writes: `day_resets.json`, `catalysts_today.json`, the full-list 簡述 table, and runs `py build_report.py` / `py gen_tables.py` / `py parse_tv.py | tail -3` / `py fetch_earnings_dates.py | tail -3`.

**增量寫作 + 增量發布:** fact sheet 不必等全員 —**top 3 的 fact sheet 一到,就先寫它們的 `news_detail` / `claude_picks` 草稿**,其餘陸續補齊。發布照既有「先完成先上線」(feedback_incremental_publish):先寫好的先 `build_dashboard.py` + push,收尾只是補漏保險。

**Join #2** (剩餘 fact sheets back) → main model 補完 § 7.0 teardowns + `news_detail.json` + `claude_picks.json` → `py build_dashboard.py` → git push → chat brief.

**Net effect:** 目標 **主線 ~8-10 分鐘發布**(誠實區間:順利日 ~8 分、補搜多或 earnings 密集日 ~10-12 分)。**瓶頸 = fact-sheet 蒐集 + 主模型寫作**這兩段;其餘 I/O 全蓋在寫作時間下。(舊敘述宣稱 ~5-6 分已過時 — 昨天實測 25-40 分,主因單一 fact-sheet agent 跑到 23 分 + 序列化寫作;本次升級把 fact sheet 切成每 2 檔一個並加 6 分鐘硬上限、催化劑 fan-out 加寬到 4-6 agents、寫作改增量。)NEVER run finviz / tv-scrape / fetch_candles as blocking foreground steps.

---

## § 1. MAGNA53 + NTRT/MTRT cheatsheet (memorize before classifying)

A stock qualifies as an NTRT/MTRT candidate if **ANY** setup matches.

### Setup A — Growth Ignition (highest quality)
- Stock up ≥4%
- Volume ≥100k
- Sales growth ≥29% (latest qtr)
- Two quarters of sales growth ≥29%
- Annual sales ≥$25M
- Neglect present

### Setup B — Massive Earnings Shock
ONE of: EPS growth ≥100% **OR** Sales growth ≥100% **OR** EPS surprise ≥100%
PLUS: Sales growth ≥25% preferred (≥10% min), neglect present.

### Setup C — Analyst-Driven Move
- EPS surprise ≥100%
- Sales growth ≥10%
- Annual sales ≥$25M
- Neglect
- ≥3 analyst price-target raises (often multi-day runners)

### MAGNA53 letters
| Letter | Meaning | Test |
|---|---|---|
| **M**assive | Big growth shock | EPS growth ≥100% OR sales ≥100% OR EPS surprise ≥100% OR 2 qtrs sales ≥29%. Scale must be meaningful (10M→200M ✓, 1¢→4¢ ✗) |
| **G**ap Up | Earnings-day gap | ≥4% gap, 100k+ pre/post-mkt vol |
| **N**eglect | One of 5 forms | Financial (slow → sudden accel), Price (long base), Volume (low liquidity history), News (no coverage months/yrs), Ownership (<20–30 inst holders) |
| **A**cceleration | Sales accel | Sales accel ≥25% **OR** 2 qtrs ≥29%. *EPS growth without sales growth is weaker.* |
| **5** | Short Interest | >5 days to cover (optional, fuels squeezes) |
| **3** | Analyst Upgrades | ≥3 price-target raises (optional, fuels multi-day runs) |

### Entry rules (Phase 8 will reference these)
- **Aggressive** = after-hours → best price, high risk
- **Semi-aggressive** = pre-market → early entry, many fade
- **Standard** = at market open → **2.5% stop loss**
- **Conservative** = wait 15 min → lower risk, may miss spike

### Trailing stops
| Stage | Stop |
|---|---|
| Initial move | $1 trailing |
| Mid move | $0.40 trailing |
| Later move | $0.20 trailing |

Default mindset: **day trade first**. Upgrade to multi-day only if strong story + huge sales accel + institutional accumulation.

---

## § 2. Phase 1 — Gap scan (skip if `$ARGUMENTS` provided)

### Step 1: scrape Barchart gappers — **Playwright with XHR intercept + per-row session-date tagging**

Barchart renders the gapper table inside a `<bc-data-grid>` Shadow DOM custom element, with the actual ticker data fetched from `/proxies/core-api/v1/quotes/get` as JSON. Text scraping (Firecrawl markdown / Playwright `innerText`) misses the shadow DOM. **The clean approach is to intercept the API response directly.**

**Default command:**
```powershell
cd C:\Users\chi2t
node barchart-scrape.js
```

Default arg = `auto` (alias of `both`). The script **always scrapes BOTH pre-market and post-market endpoints**, then computes per-row session dates from the ET clock:

#### Session-date rule (US Eastern Time)

| Session  | Date assigned to row |
|----------|----------------------|
| `pre`    | TODAY (ET) if current ET hour ≥ 4  (4 AM); else YESTERDAY |
| `post`   | TODAY (ET) if current ET hour ≥ 16 (4 PM); else YESTERDAY |

**Why:** pre-market opens at 4 AM ET. Before that, the "current" pre-market endpoint still shows yesterday's morning session (frozen since 9:30 AM yesterday). Same logic for post-market with the 4 PM boundary.

Each row in `candidates.csv` carries a **`SessionDate`** column (ISO YYYY-MM-DD) so downstream tools can place rows in the correct day's view without re-inferring.

#### Examples (the rule's full coverage)

| ET clock at scrape | pre rows tagged | post rows tagged | Note |
|--------------------|-----------------|------------------|------|
| Tue 02:00 ET (overnight) | Mon | Mon | Both sessions are yesterday's (Mon pre + Mon post). 5/19 pre hasn't started yet. |
| Tue 05:00 ET (pre-market in progress) | Tue | Mon | The overnight-gap classic: Mon's after-hours + Tue's incoming open. |
| Tue 09:00 ET (still pre-market) | Tue | Mon | Same as above. |
| Tue 11:00 ET (regular hours) | Tue | Mon | Mon post-market still frozen on Barchart. |
| Tue 15:30 ET (regular hours) | Tue | Mon | Same as above. |
| Tue 16:00 ET (post-market opens) | Tue | Tue | Today's post-market starts; Mon's post-market scrolls off. |
| Tue 20:00 ET (post-market in progress) | Tue | Tue | Both sessions are today's. |

**Boot log** prints the resolved dates so the user can sanity-check:
```
[barchart-scrape] ET Tue 2026-05-19 05:00 · session-dates: pre=2026-05-19  post=2026-05-18  arg=auto
```

**JSON output** (printed to stdout) includes a `rowsByDateSession` breakdown:
```json
"rowsByDateSession": {
  "2026-05-19_pre": 23,   // Tue pre-market gappers
  "2026-05-18_post": 14   // Mon post-market gappers
}
```

**Manual override:**
```powershell
node barchart-scrape.js pre    # only pre-market endpoint (2 URLs) — still tagged with session date
node barchart-scrape.js post   # only post-market endpoint (2 URLs) — still tagged
```

This script (at `./barchart-scrape.js`):
1. Reads ET clock, computes pre/post session dates per the rule above
2. Launches headless Chromium with Playwright
3. Visits the relevant Barchart URLs (2 if pre/post; 4 if auto/both — default)
4. Listens for the `/proxies/core-api/v1/quotes/get` JSON response triggered by page load
5. Parses the JSON `data` array → ticker objects with `symbol, preMarketLastPrice, …`
6. Filters to `abs(ChgPct) >= 4.0 AND Volume >= 100_000`
7. Dedupes by `(Symbol, Session, Direction)` triple — keeps row with largest `|ChgPct|`
8. Writes:
   - `barchart-{session}-{direction}.json` — raw API responses (1 per source)
   - `candidates.csv` — final filtered + deduped list with `SessionDate` column, BOM for Excel

**Speed/cost:** ~5-7 seconds for the default (both endpoints). 0 Firecrawl credits.

**Pagination note:** API returns `total: 200` per source but `count: 100` per call. The 100 rows we get are sorted by `|%chg|` descending (for advances) or ascending (for declines), so rows 101-200 are below the 4% threshold and don't qualify. **No pagination needed** — page 1 captures all ±4% candidates.

**Dedupe across sessions:**
- Same `(Symbol, Session, Direction)` triple → keep the row with the largest `abs(change_pct)`. (handled inside script)
- Same `Symbol` in both pre AND post with same direction → kept as separate rows tagged by session (allows the user to see if a stock moved in both sessions); the report's dedupe can collapse these if desired.
- Opposite directions across sessions (rare) → both rows kept separately.

### Step 1b: Firecrawl fallback for Barchart

If Playwright Barchart fails (Node not installed, Chromium missing, bot detection), fall back to Firecrawl:
```powershell
firecrawl.cmd --% scrape "<URL>&page=1" --only-main-content --wait-for 6000 -o barchart-pre-advances-p1.md
```
Then run the legacy regex parser on the markdown. **This fallback is needed less than 1% of the time** — Playwright + XHR intercept is robust.

### Step 2: fallback to Finviz if Barchart entirely fails
Trigger fallback when both Playwright AND Firecrawl Barchart paths failed, OR fewer than 5 rows parsed combined.

```powershell
firecrawl.cmd scrape "https://finviz.com/screener.ashx?v=111&s=ta_topgainers&o=-change" --only-main-content --wait-for 4000 -o finviz-gainers.md

firecrawl.cmd scrape "https://finviz.com/screener.ashx?v=111&s=ta_toplosers&o=change" --only-main-content --wait-for 4000 -o finviz-losers.md
```

Parse the Finviz table (Ticker, Change, Volume) and apply the same filter.

### Step 3: build candidate list
Combine gainers + losers into one list. Mark each row as `direction = up | down`. If list is empty → output **「今日無符合條件的股票」** and stop.

---

## § 3. Phase 2 — Catalyst hunt (deep dive **per candidate — ALL of them, not just top N**)

**Critical:** %chg is the *filter*, not the *ranking*. The best SIP may be the +5% candidate with a clean earnings beat, not the +30% low-float pumper. Hunt catalysts on **every single candidate** that passed Phase 1's filter. Do NOT truncate to "top 20 by %chg" — that loses signal.

### 2.0 — Macro / policy / sector pre-scan (RUN THIS BEFORE PER-TICKER LOOKUPS)

**Why this exists:** RGTI on 2026-05-21 gapped +12.7% pre-market on a $2B Trump quantum-subsidy announcement (WSJ overnight). A naive per-ticker `RGTI news today` search returns generic Rigetti coverage and misses the sector driver. The catalyst is "ALL quantum stocks are up because of a White House policy" — so you have to look for the ROOT NEWS first, then map it back to the tickers that moved on it.

**Always start Phase 2 with this pre-scan** BEFORE touching individual tickers. The goal is a 5-10 row "policy / sector cluster map" of today's biggest catalysts.

**Delegate it (§ 0.5 routing): spawn ONE Agent with `model: "haiku"`** whose prompt contains today's ISO date + the source table below + the candidate ticker list, and instructs it to run the searches in parallel and return ONLY the cluster map (≤600 tokens, format as in the example below). Do NOT run these 5 WebSearches in the main context — that's ~10k tokens of raw search results the main model doesn't need to see. **Launch it in the SAME message as the § 2.1 catalyst agents (§ 0.6) — don't serialize.** The map lands ~30-60s later and gets applied at the § 2.2 cross-check.

Resolve today's date once at the top of the phase (e.g. `2026-05-21`) and inject it into EVERY query — the LLM will otherwise serve cached results from weeks ago.

| Source | What to look for | Query / URL |
|---|---|---|
| **WSJ / Reuters / Bloomberg overnight + premarket** | Policy actions, executive orders, government contracts, regulatory rulings, sector-wide M&A | `WebSearch: "site:wsj.com OR site:reuters.com OR site:bloomberg.com <YYYY-MM-DD> premarket movers OR overnight news"` |
| **White House / Treasury / SEC / FDA / DoD press releases** | Direct primary-source policy text (executive orders, drug approvals, defense contracts) | `WebSearch: "site:whitehouse.gov OR site:treasury.gov OR site:fda.gov OR site:defense.gov <YYYY-MM-DD>"` |
| **Briefing.com "What's Going On" / TheFly "Daily Movers"** | Aggregator of all today's tickers with single-sentence catalysts | `firecrawl.cmd scrape "https://www.briefing.com/InPlay" --wait-for 5000` |
| **Today's biggest market-themed Reuters story** | Sector-level macro (chips, AI, biotech, banks, energy) | `WebSearch: "what is moving stocks today <YYYY-MM-DD> sector"` |
| **CNBC / MarketWatch premarket recap** | A clean "today's pre-market movers" list with ticker-by-ticker reasons | `WebSearch: "premarket movers <YYYY-MM-DD>"` + `firecrawl.cmd scrape "https://www.cnbc.com/pre-markets/"` |

**Extract from this pre-scan a cluster map**:

```
quantum_policy  = { root: "White House $2B quantum subsidy + minority govt stake (WSJ 5/20 overnight)",
                    affected: ["RGTI","IONQ","QBTS","QUBT","ARQQ"] }
ai_infra        = { root: "DOE National AI Initiative grant cycle awards announced 5/21",
                    affected: ["NBIS","BNKK","CRWV"] }
fda_thursday    = { root: "FDA PDUFA decisions 5/21 — KRTX accelerated approval",
                    affected: ["KRTX"] }
```

Save this map to working memory. Use it in 2.1 below to short-circuit per-ticker lookups: if a candidate appears in an `affected` list, write the cluster's `root` as its catalyst and **only** chase ticker-specific details (sales numbers, magnitude of beat, etc.) — don't re-hunt the root story from scratch.

### 2.0b — 頭條大公司補列 (Headline big-name inclusion — 不受 ±4% gap 限制)

> **使用者 2026-07-09 明確指示:** 「如果有看到什麼公司出現在頭條新聞上、有名的公司,也要補上,不管有沒有 4% gap。」**這是硬性方針。**

**Why:** 有名的大公司(AAPL / NVDA / AVGO / TSLA / AMZN / MSFT / GOOGL / META / JPM …)常有**重大當日新聞**(財報、併購、大型分析師動作、產品發表、指引、法律/監管、重大合作),卻**未必** gap 到 ±4%,因此不會出現在 `candidates.csv`。只要知名公司登上當日頭條,**就算沒有 4% gap 也要補進來**。

**做什麼(在 §2.0 pre-scan 時一併產出):** 在 §2.0 的 haiku pre-scan agent prompt 內**加一項輸出** — 除了 cluster map,另回傳一份 **`headline_bignames` 清單**:當日**真正登上一級財經頭條**(WSJ / Reuters / Bloomberg / CNBC / Briefing.com)的知名/大型公司,每檔附一句 繁中 catalyst + Type + 消息面漲跌方向。**收錄門檻見下方兩條(2026-07-15 起:大公司不看漲跌幅 %,只看新聞夠不夠重大)。**

**頭條來源(pre-scan agent 實際要去掃的頁面 — firecrawl scrape 或 WebSearch,注入今日 ISO 日期):**
- **CNBC:** `https://www.cnbc.com/markets/`、`https://www.cnbc.com/pre-markets/`、CNBC 首頁 top stories
- **Wall Street Journal:** `https://www.wsj.com/news/markets`、WSJ Markets 首頁(headline + lede 免費可見)
- **Reuters:** `https://www.reuters.com/markets/`、`https://www.reuters.com/business/`
- **Bloomberg:** `https://www.bloomberg.com/markets`(headline 可見)
- **Briefing.com InPlay**(§2.0 已列)、**MarketWatch** `https://www.marketwatch.com/`、**Yahoo Finance trending tickers**
- 補搜:WebSearch `most talked about stocks today <今日ISO>` / `site:cnbc.com OR site:wsj.com <今日ISO> stock OR shares`

從這些頭條頁抓出反覆出現的**知名公司**,套下面**兩條**門檻(2026-07-15 使用者砍掉「%」那條):
1. **知名度/規模** — 家喻戶曉或大型股(市值 ≳ $10B)。
2. **有重大/實質的當日新聞** — 財報、併購、FDA、大型合約、重大分析師動作(升降評/大幅調 PT)、監管/法律、產品發表、指引 等。**漲跌幅 % 完全不列入判斷**:漲、跌、還是幾乎沒動都收,唯一要件是「新聞夠重大 + 一級源當日可查」(WSJ/Reuters/Bloomberg/CNBC/Briefing/公司 IR/SEC,不是傳聞)。
優先讀 CNBC / WSJ 的 markets 頭條(使用者指定)。

**寧可多收、別漏(2026-07-15 使用者:「大公司不用管 %,就都要抓新聞;重大新聞一樣放上 SCANX」)。** 不設硬性檔數上限 —— 只要是知名/大型公司 + 當日有**重大新聞**,一律收,**完全不看漲跌幅**。唯一過濾條件是「新聞不夠重大」(純股價小動、沒有實質新聞的才不收)。已在 gap 掃描裡的名字不用重複列。

**注入管線:** 對每檔 headline 名單:
- 抓**即時報價**(Yahoo `v8/finance/chart` 或 Finviz)取 Last / %Chg / Volume。
- **附加一列到 `candidates.csv`**:`Session=headline`、`Direction=up|down`(依當日漲跌)、`SessionDate=<今日 ISO>`、Name 補公司全名。
- 之後照常走 §2.1 catalyst 補強、Phase 5 TV、§8.1 `news_detail.json`、`claude_picks.json`、dashboard。
- **⚠ 大公司一律補 TV(2026-07-14 使用者硬性指示):** 只要是知名/大型股且當日報財報(earnings 類,如 GS/JPM/BAC/WFC/IBM),**務必 `node tv-scrape.js <SYM>` + `py parse_tv.py`**,讓個股詳細頁有季度 EPS/營收圖 + MarketSurge 表 + Forward YoY。headline 大公司只要是 earnings,就不能只有一句 catalyst 而缺 TV 資料。(這批 earnings 名字要一起在 §6.1 的 TV scrape 分片內;**publish 前用 §6.1 的完整性硬閘門驗證無漏**。)
- **⚠ 剛好卡在 ±4% 門檻下的知名大股會被硬濾掉(2026-07-15 實例:BABA 盤前 +3.97% 跳空,差 0.03% 被 4.0% 濾網刷掉,盤中才衝 +5.9%)。** BABA **確實在** barchart 盤前 feed(`barchart-pre-advances-*.json`,preMarketPercentChange +3.97%),只是被 `qualifies()` 的 `>=4.0` 切掉。§2.0 pre-scan 抓頭條時,**要順掃 barchart 原始 pre/post feed 裡卡在 ~3–4% 的知名/大型股**(直接讀 `barchart-*-advances-*.json` 找 megacap,或 Finviz movers / Yahoo trending),接近門檻 + 有新聞的 megacap 一律以 `Session=headline` 補入 —— 別讓 4.0% 硬切點漏掉正在 play 的大公司。非財報日的大動(如 China-AI 族群續漲)Type 標 `momentum`/`news`,不硬套 earnings TV。
- 這些**不需**通過 ±4% 濾網;仍照 §4 做 MAGNA53 分類。故事夠強可入 claude_picks(遵守 direction-match:只有 chgPct>0 才 `intent=long`,chgPct<0 才 `intent=short`)。

**視覺標記:** `Session=headline` 讓 dashboard 以「頭條」標籤與 4% gapper 區分。`build_dashboard.py` 已讀 `candidates.csv`,附加列自動納入;若某檔 MAGNA53 分數未達 SIP 卡門檻,仍會出現在完整候選清單 / SCANX / 個股詳細頁(即「有補上」)。

**AVGO 範例(2026-07-08):** AVGO 當日約 −3%(未達 4%)但登上頭條(Erste 降評至 Hold(估值);本週 Apple $30B 自研晶片合作延長至 2031)。舊流程漏掉 → 新流程以 `Session=headline`、`Direction=down`、catalyst「Erste 降評 Hold −3%;Apple $30B 合作延長至 2031」補入候選並寫 `news_detail`。

### 2.0c — 大型股 ≥2% 全掃(每日必跑;§2.0b「大公司不看 %」的機械執行版)

> **2026-07-15 使用者:「要真的有至少 2% 的 gap 的大公司都補上來。」** Barchart 只掃 pre/post ≥4%,盤中大動或卡在 2–4% 的大型股會整批漏掉(BABA、NVDA、JNJ、C… 都曾漏)。

1. **跑 `py bignames-scan.py`**(在 §2.0 pre-scan 同批發射,~30–45s)—— 掃 ~158 檔大型股宇宙(市值 >$10B),印出當日 `|chg| ≥ 2%` 且**不在 candidates.csv** 的名字。門檻可調:`py bignames-scan.py 3`。
2. 把漏掉的名字併進 §2.1 的 **haiku catalyst fan-out**(每 6–8 檔一個 haiku agent,每檔回一句 繁中 catalyst + Type + 標「有無個股新聞 Y/N」;逆勢大跌卻標「查無」的大股,主線自己補查一次,§2.2 distrust guard)。
3. **全部以 `Session=headline` 補進 `candidates.csv`**(direction 依當日漲跌):
   - **有個股新聞**(財報 / M&A / 指引 / 升降評 / FDA / 合約)→ 給真 catalyst;**earnings 類補 TV**(`node tv-scrape.js`,§6.1 完整性硬閘門會擋漏)+ 寫 `news_detail`。
   - **純隨大盤/族群**(當日科技 / 中概 rally,無個股消息)→ catalyst 誠實標「隨科技股/中概/醫材族群上漲,無個股重大新聞」,**不硬掰、不補 earnings TV**。
4. 宇宙可擴充:`bignames-scan.py` 的 `UNIVERSE` 是精選大型股清單;發現漏了某知名大股就把它加進清單,下次自動涵蓋。

### 2.1 — Per-ticker catalyst hunt

**Efficient delegation pattern (§ 0.5 routing — MANDATORY, not optional):** delegate the per-ticker hunt to **at most 3 Agents with `model: "haiku"`**, ~25 tickers each (don't spawn 6+ agents — each carries prompt overhead). **Launch these in the SAME message as the § 2.0 pre-scan agent (§ 0.6) — do NOT block waiting for the cluster map**; the § 2.2 cross-check applies clusters afterward. (If a same-day cluster map already exists from an earlier run, include it in the prompt so agents can short-circuit.) Ask each agent to return a structured markdown table with columns `Ticker | Type | Cluster | 繁體中文 catalyst` (Type ∈ {earnings, analyst, guidance, contract, M&A, FDA, news, momentum, macro, **policy**}). **Output caps in the prompt: table ONLY, ≤40 字 per catalyst, NO sources list, NO preamble, NO per-ticker EPS/Rev columns** (those come from tv-summary.json later — don't make a haiku search for numbers the pipeline already scrapes). Main model reads back 3 compact tables (~2k tokens total) instead of doing 60+ searches itself.

For each candidate (parallelize in batches of ~5 in your own context, or delegate to the agent above), run these in parallel:

1. **Cluster lookup (first — short-circuit if hit)** — if the ticker is in any `affected` list from Phase 2.0, the catalyst is the cluster `root`. Skip to fundamentals lookup; don't re-run the news search.

2. **Finviz news block** (always — gives fundamentals + a list of today's headlines)
   ```powershell
   firecrawl.cmd scrape "https://finviz.com/quote.ashx?t=<TICKER>" --only-main-content --wait-for 3000
   ```
   Look for the news table (sort by date — TODAY's entries first) + the fundamentals snapshot (EPS, Sales, Inst Own%, Short Float, etc.).

3. **WebSearch — multi-angle, date-anchored.** Use **3-4 queries** per ticker, not just 1, and ALWAYS include today's ISO date verbatim:

   | Catalyst hypothesis | Query template (substitute `<DATE>` = today's ISO date) |
   |---|---|
   | Earnings | `<TICKER> Q[1-4] earnings beat OR miss revenue <DATE>` |
   | Policy / government | `<TICKER> government policy OR executive order OR contract <DATE>` |
   | Contract / partnership | `<TICKER> contract OR partnership OR deal announcement <DATE>` |
   | Analyst action | `<TICKER> upgrade OR downgrade OR price target <DATE>` |
   | FDA / regulatory | `<TICKER> FDA OR approval OR clinical OR PDUFA <DATE>` (biotech only) |
   | Tier-1 catch-all | `<TICKER> news <DATE> site:reuters.com OR site:bloomberg.com OR site:wsj.com OR site:cnbc.com` |

   Pick the 3-4 most likely hypotheses based on the candidate's sector. **The "Tier-1 catch-all" should ALWAYS be one of them** — it filters out the SEO-spam result pages that dominate generic `<TICKER> news today` queries.

4. **SEC EDGAR 8-K filed today** (catches M&A, executive changes, material contracts that wire-services may not have indexed yet):
   ```
   https://efts.sec.gov/LATEST/search-index?q=%22<TICKER>%22&forms=8-K&dateRange=custom&startdt=<DATE>&enddt=<DATE>
   ```
   Or via the SEC submissions API (the `fetch_sec()` helper in `fetch_earnings_dates.py` already knows how to walk `data.sec.gov/submissions/CIK<cik>.json` — extend it if needed).

5. **X / Twitter cashtag (fallback only)** — only if 1-4 returned nothing:
   ```powershell
   firecrawl.cmd search "$<TICKER> <DATE>" --limit 5
   ```
   Twitter is unreliable as a primary source (rumors, copy-paste, bots) but can surface a story the wire services haven't published yet.

Synthesize a **single 繁體中文 sentence** explaining why each stock moved, e.g.:
- 「Q3 財報每股盈餘 $0.82 超預期 42%，營收 +38% YoY，盤後 +12%。」
- 「FDA 完整核准糖尿病新藥 Tirzepatide，分析師調高目標價至 $XXX。」
- 「Q2 營收較預期短少 9%，下修 FY 指引，盤後 -18%。」
- 「量子板塊集體跳漲 — 川普政府 $2B 量子計算補助方案 (WSJ 5/20 報導)，<TICKER> 隨族群 +12.7%。」 ← cluster pattern

Capture in working memory per ticker: `catalyst_zh, cluster_id (if any), eps_surprise_pct, rev_surprise_pct, annual_sales, inst_own_pct, short_float, days_to_cover, pt_raises_30d`.

### 2.2 — Cluster cross-check pass (after 2.1)

Once all per-ticker catalysts are written, **walk the list once more** and look for tickers that ended up with vague/generic catalysts (e.g. "<TICKER> 隨大盤上漲", "盤前無重大消息", "暫無明確催化劑"). For each of these:

1. Check if it sits in the same SECTOR as a cluster from 2.0 (use Finviz sector field).
2. If yes — confirm the cluster's catalyst applies (check the ticker's actual % move + correlation with the cluster).
3. Rewrite the catalyst with the cluster's root news. This is what catches the "RGTI ran +12% on the quantum policy because every quantum stock was up 8-15%" pattern that a per-ticker search misses.

The cluster cross-check is cheap (just rewrites text from already-fetched data) but high-yield — it's the difference between "RGTI: 暫無明確催化劑" and "RGTI: 量子族群集體跳漲 (政府 $2B 補助)".

**Big-mover distrust guard (quality backstop for § 0.5's haiku routing):** the MAIN model must NOT blindly trust a cheap agent's "momentum / 無明確催化 / micro-float 拉抬" label on any candidate with **|chgPct| ≥ 15% OR volume ≥ 5M**. For those (typically 2-4 per day), run ONE quick main-context WebSearch yourself to confirm there's genuinely no news before locking the label — a mislabeled big mover is exactly the ticker that would wrongly miss the top-10 deep-dive cut. This spends 2-3 of the ≤5 main-context search budget; small movers keep the haiku label as-is.

### 2.3 — X / 難觸及來源(Playwright 工具箱,WebSearch 到不了的地方)

**X(Twitter)cashtag 搜尋:`node D:\SIPs\x-scrape.js SYM1 SYM2 ...`**(≤8 檔/次,輸出 `x-posts.json`,每檔 live 搜尋前 ~15 則:作者/時間/內文/互動數)。

- **一次性設定:`node x-scrape.js --login`**(開視窗登入 X,cookie 存 `.x-profile/`,已 gitignore;未登入時腳本會自動 STOP 並指路,不會出假資料)
- **何時跑(選用,但這兩種情況必跑):**(a) distrust-guard 名單 — |chg|≥15% 且 haiku 標「查無/momentum」;(b) 疑似傳聞驅動、主流源查不到根源的大 mover
- 讀結果用 `py -c` 選讀 `x-posts.json`(禁整包 Read);X 找到的線索要回頭用 WebSearch 對一級源確認
- **紀律:X 內容=傳聞層** — 寫進 catalyst/news_detail/rationale 必標「X 傳聞未證實」,不得當一級源;腳本遇 captcha/驗證挑戰會自動 STOP,**禁止繞過**
- X 未登入或被擋 → 跳過此步照常出報告(X 是補充來源,不是依賴)

**其他 WebSearch 到不了的來源(同模式):** Stocktwits 情緒不用 Playwright — 公開 JSON `https://api.stocktwits.com/api/2/streams/symbol/<SYM>.json`;Reddit(requests 403 時)與其他 JS 牆頁面照 `reference_playwright_*` 記憶的既有 Playwright pattern 開;需要登入的站先問使用者拿授權。


---

## § 4. Phase 3 — MAGNA53 classification

For each candidate compute MAGNA53 letter-by-letter using § 1. Tag the setup as **A / B / C / NULL**. NULL = no clean setup → exclude from final ranking.

Track in working memory: `magna_score = {M, G, N, A, 5, 3}` with ✓/✗/? for each.

---

## § 5. Phase 4 — Short candidates (gap-down screen)

For every `direction = down` candidate: confirm latest reported quarter shows **EPS YoY ≤ -25% OR Revenue YoY ≤ -25%**. Compute from Finviz's "EPS Y/Y" + "Sales Y/Y" fields, or from the TradingView scrape in Phase 5 if Finviz is missing values. Those qualify as **shorting candidates** (🔴). Gap-downs that miss the 25% decline → drop unless there's a clean negative catalyst.

---

## § 6. Phase 5 — TradingView quarterly forecast → raw figures + YoY (**every candidate tagged `Type=earnings`**)

For every candidate whose Phase 2 `Type` is `earnings` (or who reported within last 5 trading days), scrape TradingView's FQ quarterly grid and extract BOTH:
1. **Raw figures section** (separate from YoY block) — Latest Reported EPS + Rev with units (e.g. `$534.6M`, `$0.57`), Prior-year same-quarter Reported EPS + Rev, and the next 4 quarterly estimates' EPS + Rev with units. This is critical context the user can sanity-check against headlines.
2. **Forward YoY block** — strict-format YoY percentages per §6.2 spec.

### 6.1 Fetch the TradingView quarterly grid

Use the **FQ URL trick** — `?earnings-period=FQ&revenues-period=FQ` returns SSR'd quarterly tables without JS interaction.

**Freshness cache (skip re-scrapes):** before scraping, list existing `*-earnings-fq.md` files — **skip any ticker whose file is <3 days old**, UNLESS today's catalyst Type for that ticker is `earnings` (it just reported — the grid changed). Most days this cuts the scrape list from ~30-40 tickers down to the 5-15 fresh reporters. Shard the remainder across **2-3 parallel background `node tv-scrape.js <shard>` processes** (§ 0.6) instead of one serial run.

**⚠ 完整性硬閘門(2026-07-15 使用者再次要求 — 大股票不能缺 TV):push 前必驗。** §2.0b 的頭條大公司常在 Phase 2 後段才加進候選,容易漏掉 TV scrape(BLK/MS 2026-07-15 就中招:headline earnings 卻無 EPS/Rev)。所以 **`build_dashboard.py` 之後、`git push` 之前**,對今日包跑這個檢查,有缺就補掃再 rebuild,**迴圈到清零**:
```bash
py -c "import json; d=json.load(open('dashboard/data/<今日ISO>.json',encoding='utf-8')); m=[k for k,v in d['stocks'].items() if v.get('type')=='earnings' and not v.get('tv')]; print('缺 TV 的 earnings:', m or '無')"
```
清單非空 → `node tv-scrape.js <那些SYM>` → `py parse_tv.py` → `py build_report.py` → `py build_dashboard.py` → 再驗。**涵蓋範圍 = 今日全部 `Type=earnings`(headline 大公司 + SCANX 出線的都算,不是只有 top-10)。** 唯一放行例外:TV 三交易所都 404(確實無頁),此時在該檔 catalyst 註明「無 TradingView 季度資料」。
**TV EPS 失真擋一下:** 少數 ADR/雙重口徑股(如 BABA,GAAP vs ADS)TV 會給出離譜的 EPS surprise(例 −89.9%);若 `|surpriseEPS_pct|` 大得不合理且與新聞不符,**寧可拿掉該檔 TV 區塊、把營收寫進 news_detail 散文**,也不要 publish 假的財報 miss。

#### Primary tool: **Playwright** (default since 2026-05-13)

Playwright (local, free, no API credits) replaces Firecrawl as the default TradingView scraper. The script is at `./tv-scrape.js` and is invoked as:

```powershell
cd C:\Users\chi2t
node tv-scrape.js <TICKER1> <TICKER2> ...
```

Output is saved to `<TICKER>-earnings-fq.md` (same path as Firecrawl, so the existing `parse_tv.py` works with no changes). The script handles **exchange auto-detect** (NASDAQ → NYSE → AMEX) internally and waits for both the EPS and Revenue tables to fully hydrate before extracting `document.querySelector('main').innerText`.

**Verified 2026-05-13:** SE/VELO/RAL/PSIX/AU all produced byte-for-byte identical YoY blocks vs Firecrawl. Output sizes typically 1.7-2.8 KB (cleaner than Firecrawl's 5 KB because no navigation/sidebar bloat).

**Key script details** (see `./tv-scrape.js` for full source):
- Headless Chromium via `@playwright/test`
- `waitUntil: 'domcontentloaded'` + then `waitForFunction` until ≥4 quarter labels AND ≥8 numeric values are present in `document.body.innerText` (this prevents extracting before chart hydration — the lesson learned: waiting only for `Reported`/`Estimate` labels triggers too early because those are static header text)
- Scrolls earnings section into view to defeat any visibility-gated lazy rendering
- Sanity-check: post-extract, count numeric matches (`-?\d+\.\d+`) — if <8 the page didn't hydrate, advance to next exchange
- User agent set to a real Chrome string to avoid bot detection

#### Fallback tool: Firecrawl

If Playwright is unavailable (Node/Playwright not installed, or all 3 exchange URLs failed via Playwright), fall back to Firecrawl REST API:

```powershell
$body = @{ url=$url; formats=@('markdown'); onlyMainContent=$true; waitFor=6000 } | ConvertTo-Json
$resp = Invoke-RestMethod -Uri 'https://api.firecrawl.dev/v1/scrape' -Method Post -Headers @{Authorization="Bearer $env:FIRECRAWL_API_KEY";'Content-Type'='application/json'} -Body $body
[System.IO.File]::WriteAllText($outPath, $resp.data.markdown, [System.Text.Encoding]::UTF8)
```

PowerShell loops can't reliably pass `&` in URLs to `firecrawl.cmd` (cmd.exe re-parses `&` as command separator even inside quoted strings), so the REST API is the way for batch runs. For interactive single-ticker calls, `firecrawl.cmd --% scrape "<URL>" ... -o <file>` works (the `--%` stop-parsing token freezes the URL for cmd.exe).

**Exchange auto-detect (for Firecrawl path) — try in order until response body length > 1000 (a 404 returns ~275 bytes):**
1. `NASDAQ-<TICKER>`
2. `NYSE-<TICKER>`
3. `AMEX-<TICKER>`

### 6.1b Parsing notes (TradingView quirks)

The saved markdown is wrapped in **Unicode bidi marks** (`‪`-`‬`, `⁦`-`⁩`) around every number, and uses **NARROW NO-BREAK SPACE** (` `) between number and unit (e.g. `3.81 B`). Strip these before parsing:
```python
content = re.sub(r'[​-‏‪-‮⁦-⁩﻿]', '', content)
content = re.sub(r'[  -   　]', ' ', content)
```

The file has **4 `Reported`/`Estimate` marker pairs** (legend labels appear before the data blocks). The real data blocks are those followed by a numeric line on lookahead. The first such block is EPS, the second is Revenue. Each `Reported` block has 8-12 values (recent 12 quarters with `—` for not-yet-reported future quarters); each `Estimate` block has 12 values including the forward estimates.

---

### 6.2 Embedded Financial-Data Extraction Agent (verbatim spec)

#### Role and Purpose

You are an expert financial data extraction and calculation agent. Your sole purpose is to extract quarterly EPS and Revenue figures from user-uploaded earnings charts (or pasted tables) and output Year-over-Year (YoY) growth rates in a highly specific, minimalist format.

#### Trigger

Activate this skill whenever the user uploads a financial earnings chart or pastes EPS/Revenue table data and asks for growth rates, a summary, or simply says "calculate" or "generate".

*(Inside this routine, the trigger is automatic — Phase 5 invokes this agent on the markdown saved from the firecrawl scrape above.)*

#### Step-by-Step Instructions

##### Step 1: Extract the Data

From the provided image or text, locate the quarterly timeline (e.g., Q3 '24, Q4 '24, Q1 '25, etc.). For each quarter, extract:

1. EPS Reported (Actuals)
2. EPS Estimate
3. Revenue Reported (Actuals)
4. Revenue Estimate

Identify the timeline crossover:

* **Most Recent Reported Quarter (Current):** The latest quarter that has actual *Reported* values for both EPS and Revenue.
* **Future Quarters (Estimates):** All subsequent quarters that only have *Estimate* values.
* *Note: Convert Revenue into common units for calculation if necessary (e.g., 1.18B = 1180M).*

##### Step 2: Calculate YoY Growth

For each quarter (Current + Future Estimates), calculate the Year-over-Year growth percentage using this formula:

```
((This Quarter Value / Same Quarter Last Year Value) - 1) * 100
```

**Calculation Rules:**

* **For the Current Quarter:** Calculate using *Reported* vs. *Reported* (same quarter prior year).
* **For Future Quarters:** Calculate using *Estimate* vs. *Reported* (same quarter prior year).
* Round all final percentages to exactly 2 decimal places.
* Always include a `+` prefix for positive numbers. Negative numbers will inherently have a `-` prefix.

**Edge Cases & Error Handling:**

* If the prior year's value is 0 or negative and the current value is positive (or vice versa), the math is not meaningful. Output `N/M` for that specific metric.
* If a quarter has no estimate available (often displayed as a dash `—`), skip that quarter entirely.

##### Step 3: Strict Output Formatting

Output ONLY the calculated numbers following the exact structure below. Do NOT include quarter labels, arrows, explanatory text, disclaimers, or conversational filler.

**Format Structure:**

```
[Current Qtr EPS YoY]% / [Current Qtr Rev YoY]%
--------------------
[Next Qtr EPS YoY]% / [Next Qtr Rev YoY]%
[Next Qtr+1 EPS YoY]% / [Next Qtr+1 Rev YoY]%
[Next Qtr+2 EPS YoY]% / [Next Qtr+2 Rev YoY]%
```

**Formatting Rules:**

1. The first line is ALWAYS the most recent reported quarter.
2. The second line is exactly 20 dashes (`--------------------`).
3. The lines below the dashes are the future estimated quarters in chronological order. Only output lines for the future quarters available in the data (e.g., if there are only 3 future quarters, only output 3 lines below the dashes).

**Example Perfect Output:**

```
+1366.67% / +130.37%
--------------------
+200.00% / +84.61%
+186.67% / +70.10%
+57.78% / +51.73%
+40.91% / +70.44%
```

---

### 6.3 What to do with the result

The per-stock template in Phase 6 has **two separate TradingView sections**:

1. **「TradingView 季度原始數據:」** — show the raw figures explicitly:
   ```
   最新 Q (報告): EPS $0.57 / Rev $534.6M
   去年同期 (報告): EPS $0.73 / Rev $481.8M
   未來 4Q (估計): EPS $0.55 → $0.63 → $0.71 → $0.58
                    Rev $534.7M → $546.6M → $577.2M → $545.4M
   ```
   This lets the user sanity-check the YoY math against headlines and absolute scale.

2. **「Forward YoY (TradingView FQ):」** — the strict-format YoY block produced by §6.2 verbatim:
   ```
   -21.92% / +10.96%
   --------------------
   -17.91% / +6.24%
   +5.00% / +3.30%
   ...
   ```

Do not add commentary inside either block. All narrative (新聞、SIP 判斷) lives outside the blocks in the surrounding 繁體中文 sections.

---

### 6.4 Historical-quarter rewind (when the target date is a PAST earnings date)

`/SIPs` normally scans TODAY's candidates, so `chart.latest_idx` naturally points at
the most-recent reported quarter. **But** if the user is studying a past earnings event
(via `/update-studies` for a saved study, or feeding `/SIPs` an historical date), the
raw TV scrape will mark TODAY's latest quarter as `latest_idx` — which is **wrong** for
the target date. Example: AMD scraped 2026-05-16 returns `latest_idx=7` (Q1 '26), but
for a study dated 2026-02-04 the latest reported quarter was **Q4 '25 (idx=6)**.

The full rewind procedure lives in `/update-studies` § Phase 3b (`D:\SIPs\skills\update-studies\SKILL.md`).
For /SIPs the rule is simply: **if the candidate's effective date is more than ~3 trading
days in the past, perform the same rewind before writing `tv` / `chart` blocks**:

1. For each quarter, compute end date (Q1→Mar 31, Q2→Jun 30, Q3→Sep 30, Q4→Dec 31).
2. Add the company's typical report lag — **~30d for large-caps** (AMD/NVDA/INTC/AAPL/MSFT/GOOG/META), **~45d for smaller names** (ONDS/NBIS/etc).
3. The highest-index quarter with `(quarter_end + lag) <= target_date` is the new
   `target_idx`. Clear `eps_reported[i] = rev_reported_M[i] = null` for every `i > target_idx`. Set `chart.latest_idx = target_idx` and `study.focusQuarterIdx = target_idx`.
4. Recompute the `tv` summary (latestEPS/consensusEPS/priorYrEPS/surprise/YoY/yoyBlock/epsEst_next4/revEst_next4) from the rewound chart anchored at `target_idx`.
5. Note in the newsDetail (>⚠️ blockquote) that forward 4 estimates are **today's**
   consensus, not at-the-time consensus — historical estimates drift after each report.

This rule applies to BOTH /SIPs (when fed a historical date) and /update-studies
(every time a study's `ohlcv.date` is in the past). The fact that `tv-summary.json`
is shared between the two flows means the rewind happens to the JSON before any
template renders — both skills produce correct historical views.

---

## § 7. Phase 6 — Final 繁體中文 deliverable

Compose the full report. Order: 🟢 SIPs first (ranked best→worst), then 🔴 short candidates. Skip NULL-setup candidates entirely.

**Chat-brief compaction (speed — the news lives on the dashboard, not in chat):** the per-stock 今日上漲新聞 goes into `news_detail.json` (dashboard detail pages). Do NOT duplicate all of them in the chat brief. Write news_detail.json FIRST, then compress for chat: **only the #1 pick gets its full § 7.1 template inline in chat**; every other pick gets the compact form — 一句話漲因 + MAGNA53/setup 行 + 1-2 條新聞重點. Everything else is one click away on the dashboard.

### 7.0 — 當日上漲新聞整理 (簡單直接，不做反向分析) — apply to top 3-5 SIPs

> **使用者 2026-07-06 明確指示(記憶檔 feedback_sips_news_not_analysis):**
> 「詳細催化劑不要用 milan 的 framework，你要去找當天的新聞給我就好，不要再用奇怪的分析，直接把上漲原因整理給我。todays sips 中只要給我當天上漲的新聞就好，不要再給我一些奇怪的理由。」
>
> **這是硬性方針,不是建議。** 舊的 MiLan 五段深度拆解 + Tier 評級 + 「這是 X 不是 Y」反向判定**已廢除**。不要重新引入。

**核心任務:找出今天(或最近盤/盤後)讓這檔股票上漲的真實新聞,直接整理給使用者看。**

**做什麼:**
- 去找**當天的實際新聞**(用 § 2.0/§ 2.1 已抓到的 catalyst,不夠再補一級源搜尋:issuer IR / 8-K / Reuters / CNBC / Bloomberg / Briefing.com)。
- 直接說:**今天漲多少 + 因為什麼具體事件 + 關鍵數字**。
- 事實整理,附來源。就這樣。

**不要做(使用者明令禁止):**
- ❌ 不做「這是 X 不是 Y」的反向判定句
- ❌ 不做 Tier 1-5 評級
- ❌ 不做「業務品質 / 前瞻 vs 指引 / 風險清單 / 誠實判定」五段拆解
- ❌ 不硬找「其實沒那麼好」的理由 — 使用者要的是「為什麼漲」,不是「為什麼別追」
- ❌ 不要把上漲說成「解套反彈 / pump / 灌水」除非那**就是當天新聞本身**(例如新聞明講是反向分割 / 稀釋增發)

**方向範圍:** Today's SIPs 頁面主打**上漲的股票**。news_detail 以 gainers(intent=long / gap-up)為主。下跌股若有明確當日利空新聞可保留一句話 catalyst,但**不套用**任何深度反向框架。

**允許保留的客觀風險提醒(≤1 句,只在有硬事實時):** 若當天新聞本身就帶利空(例如「同時宣布 $X 增發稀釋」「CEO 拿 $700M 限制股」),可在最後補一句客觀陳述 — 但那是**新聞的一部分**,不是你外加的判定。沒有硬事實就不要補。

### 7.1 — Per-stock template (use this verbatim, top 3-5 SIPs)

```markdown
## 🟢 SIP #N — <TICKER>  (Price <$XX.XX> / <+/-X.XX%> / Vol <Y.YM> / <session>)

**一句話催化劑：** <one-sentence 繁體中文 explanation, specific with $ figures + names>

**MAGNA53：** M✓ G✓ N? A✓ 5? 3✓  →  Setup B (Massive Earnings Shock)
**EPS Surprise：** +XX.X%　　**Revenue Surprise：** +XX.X%
**年營收：** $XXXM　　**機構持股：** XX%　　**Short Float：** XX% (X.X days to cover)
**分析師目標價調升 (30天)：** N 次

**TradingView 季度原始數據:**
- 最新 Q (報告): EPS $X.XX / Rev $XXX.XM
- 去年同期 (報告): EPS $X.XX / Rev $XXX.XM
- 未來 4Q EPS (估計): $X.XX → $X.XX → $X.XX → $X.XX
- 未來 4Q Rev (估計): $XXXM → $XXXM → $XXXM → $XXXM

**Forward YoY (TradingView FQ):**
\`\`\`
+1366.67% / +130.37%
--------------------
+200.00% / +84.61%
+186.67% / +70.10%
+57.78% / +51.73%
\`\`\`

---

### 今日上漲新聞

**今日漲因(一句話):** <今天漲多少 + 因為什麼具體事件>

**新聞重點(2-4 條,每條真實事件 + 具體數字 + 時間):**
- <當日事件 1,含 $ / % / 日期,例:7/6 盤前公布 Q3 FY26 營收 $3.34B (+45% YoY)、非 GAAP EPS $2.72 超預期 $2.36>
- <當日事件 2,例:CEO 電話會議稱 CY2026 產能幾乎售罄、LTA 已簽到 2027-2029>
- <族群/宏觀連動(若適用),例:AI 儲存超級週期帶動 SNDK/WDC 同步走強>

<若當天新聞本身帶硬性利空,補一句客觀陳述(選填,≤1 句):例「同一份公告含 850 萬股增發稀釋」>

**來源:** 見 news_detail.json sources(一級源優先)。
```

### 7.2 — Per-short / 下跌股(簡短,不做深度反向框架)

> Today's SIPs 主打上漲股。下跌股只給**一句話當日利空新聞**,不套用任何五段/Tier 框架。

```markdown
## 🔴 <TICKER>  (-X.XX% / Vol Y.YM)

**今日跌因(一句話):** <今天跌多少 + 因為什麼具體當日利空,含 $ / % / 日期>
**來源:** <一級源 URL>
```

### End the report with:
```markdown
---
## 📊 今日結論

**最強做多 (按優先順序)：**
1. <TICKER1> — <one-line reason>
2. <TICKER2> — <one-line reason>
3. <TICKER3> — <one-line reason>

**最強做空：**
1. <TICKER> — <one-line reason>

**今日策略提醒：** <one or two sentence reminder relevant to today's market — e.g., FOMC day → 縮小部位、避免進場到 14:00 後>
```

### Full-list section (every candidate, sortable views)

After the SIP/SHORT sections, include a comprehensive list with **all candidates** that passed Phase 1 — not just the SIPs/shorts. Each row gets a **2-3 sentence 簡述 in 繁體中文**, NOT a one-liner. The 簡述 should mention: catalyst type, specific $ figure or % beat, and any notable risk/opportunity tag.

**Provide THREE sorted views** (the user wants to be able to view by different sorts; markdown can't add interactive sort, so render each view explicitly):

1. **按 |%Chg| 排序 (波動度最大的在前)** — descending by absolute change
2. **按 Session 排序** — group by `pre` / `post` / `both`, then by |%Chg|
3. **按 Price 排序** — ascending by Last price (lowest-price first, since low-price names have different risk profile)

Each view is a markdown table with columns: `# | Ticker | Price | %Chg | Vol | Session | Direction | Type | 簡述 (2-3 sentences)`.

Also save the full row data to `final-candidates.csv` with columns:
`Symbol,Last,ChgPct,Volume,Session,Direction,Type,Name,Catalyst,TV_LatestEPS,TV_PriorYrEPS,TV_LatestRev_M,TV_PriorYrRev_M,TV_YoYBlock`
so the user can sort/filter externally in Excel/Numbers.

---

## § 7.5 Phase 6.5 — Curate `day_resets.json` (judgment-based, no hard threshold)

Before publishing the dashboard, decide for each candidate whether today's catalyst is a **NEW major catalyst** (= reset day-count to `day1`) or a **continuation** of an older move (= leave at `day2/day3` per the natural walk).

**This is JUDGMENT-BASED. There is no hard threshold to mechanically apply.**

Read [`./docs/DAY_RESETS_JUDGMENT.md`](../../docs/DAY_RESETS_JUDGMENT.md) — it covers Stockbee SIP criteria + the soft-signal rules for prior price action + worked examples.

**Quick checklist per ticker:**
1. Identify today's catalyst from `catalysts_today.json` + `news_detail.json`.
2. Look at prior-scan presence + `|chgPct|` in past 1-3 scans.
3. Look at 1M / 3M perf for cumulative trend.
4. **Ask:** are the prior moves the SAME driver (= continuation/leak/anticipation) or UNRELATED (= today's catalyst is genuinely fresh)?
   - Same driver → `day3` (continuation, do NOT add to resets)
   - Unrelated → `day1` (add to resets)

**Soft signals** (worth examining, NOT auto-disqualifying):
- Prior-scan day `|chgPct| ≥ 4%` → investigate whether it was a leak/preview
- `1M cumulative > +100%` → likely already running, but not always disqualifying
- Catalyst published ≥ 2 trading days ago → usually means continuation

**Special cases:**
- **Reverse splits / corporate actions** = `day1` if no prior run-up (the corporate action itself is the catalyst)
- **Biotech FDA / PDUFA** = always `day1` on announcement day even if biotech has been speculative

Write the file as:
```json
{
  "resets": {
    "FIG":  "5/14 PM Q1 +46% YoY 財報大超預期 — fresh earnings; prior +4.5% scans were unrelated pre-earnings noise, not catalyst leak",
    "ELPW": "5/14 PM 公告 1-for-80 反向分割 — fresh corporate action, 1M +7.8% 無 prior spike"
  },
  "_no_reset_reasons": {
    "AIIO": "5/13/5/14 各 +64.8%, 1M +810% — same AI/M&A theme already pump-and-dumping; today's M&A is fulfillment + unwind, not fresh"
  }
}
```

`build_dashboard.py` reads `./day_resets.json` and emits `data.dayResets` in the per-day JSON. The dashboard JS's `dayLabelWithReset(sym, firstSeenMap, currentIso)` checks this map and returns `'day1'` for any listed symbol.

---

## § 8. Phase 7 — Publish to the "Stocks In Play" dashboard

After the 繁體中文 brief is written to chat, publish today's scan to the static dashboard at **http://127.0.0.1:5510/**. The dashboard is a single-page app under `./dashboard/` with the **revolut** design system, branded "Stocks In Play".

### 8.0 Fact-sheet gathering for the deep-dive tickers (§ 0.5 routing — run BEFORE composing)

The § 7.0 MiLan 拆解 needs segment numbers, organic-vs-M&A splits, guidance-vs-consensus deltas, lawsuit status, dilution overhang — 4-6 web lookups per ticker. Doing that in the main context for 10+ tickers is the second-biggest token sink after Phase 2. **Split gathering from judging:**

1. After the top 3-5 SIPs + top 2-3 shorts are chosen (post-MAGNA53 ranking), spawn **1-2 Agents with `model: "sonnet"`** covering the deep-dive list (~5 tickers each).
2. Each agent returns a **per-ticker FACT SHEET** — raw material only, capped ~500 tokens per ticker:

```
## <TICKER> fact sheet
- headline: <event, exact date/time ET, source URL>
- revenue: total $X (+Y% YoY); M&A/one-off portion $Z from <acquisition name + close date>; organic ≈ V%
- eps: adj $A vs consensus $B vs prior-yr $C; share count Δ ±D% and why
- gaap_vs_adj: <impairment / restatement / write-down item + $ amount, or "clean">
- segments: <name> $X rev / Y% margin; <name> $X rev / Y% margin
- forward: orders/backlog/book-to-bill numbers; FY guide vs consensus (rev + EPS deltas)
- risks: <lawsuit w/ case name or "none found">; <dilution: ATM/converts/warrants $ amounts>; <customer concentration / regulatory / competition — specific>
- chart_context: perf1M/perf6M, distance from 52wk high/low, short float + DTC (from shorts.json — do NOT re-search these)
- sources: 2-4 stable URLs, most authoritative first
```

3. **Agent prompt MUST say**: "Facts and numbers ONLY. NO analysis, NO opinions, NO tier ratings, NO trade recommendations — those belong to the caller. If a number can't be found, write 'not found' rather than estimating."
3b. **速度上限(2026-07-11,使用者嫌慢):** prompt 內明訂 — 每檔 **≤4 次搜尋**、整個 agent 目標 **≤8 分鐘**;時間到就把查到的交出來,缺欄寫 not found。遲交的完美 fact sheet 不如準時的八成品(今日 B 組跑了 23 分鐘 = 全 run 最慢環節)。
4. **The MAIN model then writes every § 7.0 five-section teardown + Tier rating itself** from these fact sheets — this is the judgment work that stays on Fable/Opus. Fill gaps with at most ~5 targeted main-context searches per run.

This keeps the expensive model's tokens on synthesis (~3-5k per ticker write-up) instead of burning them on search-result wading (~15-20k per ticker when done inline).

### 8.1 Write `news_detail.json` (per-symbol detail with REAL news time)

**File path:** `./news_detail.json`

**Schema (canonical):**
```json
{
  "MU": {
    "detail": "Q3 FY26 EPS $12.20 +682%、營收 $23.86B +196%、HBM 已售罄至 fiscal 2026 年底。\n\nManagement 在電話會議上提到 ...\n\n分析師反應：Citi 升 PT 至 $X，Morgan Stanley overweight。",
    "publishedAt": "2026-05-13T16:05:00-04:00",
    "publishedTimezone": "ET",
    "sources": [
      { "label": "Micron Q3 FY26 8-K", "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000723125&type=8-K", "publishedAt": "2026-05-13T16:05:00-04:00" },
      { "label": "Reuters — Micron HBM sold out", "url": "https://www.reuters.com/technology/micron-q3-fy26-hbm-sold-out-2026-05-13/" },
      { "label": "Yahoo Finance — earnings call transcript", "url": "https://finance.yahoo.com/news/micron-mu-q3-2026-earnings-call.html" }
    ]
  },
  "PSIX": {
    "detail": "Q1 2026 營收 $128.6M 大miss 預期 $160.8M (-20%) ...",
    "publishedAt": "2026-05-13T07:00:00-04:00",
    "publishedTimezone": "ET",
    "sources": [
      { "label": "Power Solutions International press release", "url": "https://www.psiengines.com/news/2026/q1-2026-results.html", "publishedAt": "2026-05-13T07:00:00-04:00" }
    ]
  }
}
```

**Read `./docs/NEWS_TIME_SPEC.md` BEFORE writing.** The spec covers:
- Where to source real publication times for each catalyst type (issuer IR > Briefing.com > TheFly > 8-K > Yahoo)
- ISO 8601 format with TZ offset (EDT `-04:00` / EST `-05:00`)
- Typical pre-market (06:00 / 06:30 / 07:00 / 08:00 ET) and post-market (16:05 / 16:15 / 16:30 ET) release windows
- Edge cases (foreign issuers, unknown times, multi-event days)
- A worked MU example

**Scope:** write entries for the **top 10 SIPs** + **top 4 short candidates** identified in the Phase 6 brief. The remaining ~70 candidates auto-fall back to their `catalyst` 1-sentence summary (already in `final-candidates.csv`); they don't need a `news_detail.json` entry unless they have notable depth.

**`detail` content rules — 整理當日上漲新聞,不做反向分析(見 § 7.0 硬性方針):**
- Multi-paragraph 繁體中文 markdown, paragraphs separated by `\n\n` (single `\n` becomes `<br>` in the UI)
- **REQUIRED LEAD — 今日漲因 blockquote (第一段,擺最前面):** 一個 `> **今日漲因:** ...` blockquote,1-2 句 (≤80 字):**今天漲多少 + 因為什麼具體事件**。讀者掃一眼就懂為什麼漲。Dashboard 把 `>` 渲染成紫框摘要卡,視覺上與內文分開。範例:
  `> **今日漲因:** 盤前 +5% — 7/6 公布 Q3 FY26 營收 $3.34B (+45% YoY)、EPS $2.72 超預期,CEO 稱 2026 年 HDD 產能幾乎售罄。`
- **接著是當日新聞細節(2-4 段或條列):**
  - 每一條是**當天(或最近盤/盤後)的真實新聞事件** + 具體 $ / % / 日期 + 誰說的。
  - 純事實整理:發生什麼、關鍵數字、族群/宏觀連動(若適用)、分析師動作(若當天有)。
  - **禁止**:「這是 X 不是 Y」判定句、Tier 評級、「業務品質/前瞻vs指引/風險/誠實判定」五段標題、硬找「其實別追」的理由。
- **長度: ~150-450 字**(摘要 + 2-4 條新聞)。比舊的 Milan 600-1200 字短很多 — 使用者要的是「當天新聞」不是深度拆解。
- **關鍵數字用 `**bold**`** 讓它在卡片上跳出來(例:`**Q3 營收 $3.34B (+45% YoY)**`)。
- 每個主張要有具體 $ / % / 名稱或日期;空詞「強勁需求」「前景看好」換成底層數字。
- **⚠ 合約型催化劑要換算年營收(2026-07-14 使用者硬性指示):** 只要 catalyst 是合約 / 訂單 / 租約 / backlog 型(Type=contract 或新聞給的是「總合約值 $X、為期 N 年」),**務必在 catalyst 一句話與 news_detail 內把總值換算成年化營收**:`合約總值 $X ÷ N 年 ≈ ~$Y/年`,並點出何時開始認列(交付/生效日)、以及相對公司現有年營收的量級。範例(CLSK):`$6.6B ÷ 20 年 ≈ 年化租金營收 ~$330M/年(2027 Q4 起認列,NNN 近 100% 落地)`。目的是讓讀者能把一次性大數字跟經常性營收做對比,而不是被 $6.6B 這種總額嚇到卻不知道每年進帳多少。之後每一檔合約型催化劑都照做。
- **客觀利空(選填,≤1 句):** 只有當天新聞本身帶硬事實利空(增發稀釋、內部人賣股、CEO 大額限制股)才補一句客觀陳述,放最後。沒有硬事實就不補 — 不要自己發明「風險」。

**Reference — 新格式範例 (WDC 2026-07-06):**
```
> **今日漲因:** 盤前 +4~6% — AI 資料中心近線 HDD 需求旺、庫存售罄題材延續,族群(SNDK/STX)同步走強。

WDC 為 SanDisk 分拆後的純 HDD 業者。最近一季 Q3 FY26(4/30 公布)營收 **$3.34B (+45% YoY)**、非 GAAP EPS **$2.72** 超預期 $2.36;CEO Irving Tan 在電話會議稱 **CY2026 HDD 產能『幾乎售罄』**、前七大客戶已下實單、部分長約(LTA)簽到 **2027-2029**。

漲價題材具體:消費級硬碟 5 個月漲約 **50%**、平均 HDD 售價自 2025/9 起 **+46%**;公司指引 Q4 FY26 非 GAAP 毛利率 51-52%。

今日無單一新聞事件,屬 AI 儲存超級週期的族群動能延續(SNDK 6 個月 +626%、WDC +206%)。下一個關鍵是 **7/29 財報**。
```

**`publishedAt` rules:** see NEWS_TIME_SPEC.md §3-§4. Always include the TZ offset.

**`sources` rules (REQUIRED for top-10 SIPs and top-4 shorts):**
- Array of `{ label, url, publishedAt? }` objects pointing to the ORIGINAL articles/filings/press releases that the `detail` field is summarizing.
- 1-4 sources per ticker — pick the most authoritative + most accessible. Order matters: most authoritative first.
- **Source priority** (mirror NEWS_TIME_SPEC.md §3 order):
  1. **Issuer / company sources** — IR press release URLs, SEC filings (8-K / 10-Q permalinks), official investor presentations
  2. **Tier-1 financial news** — Reuters, Bloomberg, WSJ, FT (avoid paywalled deeper pages unless headline+lede are public)
  3. **Briefing.com / TheFly** — for analyst-action stories
  4. **Yahoo Finance** — for earnings call transcripts and consensus aggregations
  5. **Industry trade press** — only when the above don't carry the story (e.g. STAT News for FDA decisions, Janes/Defense News for defense contracts)
- **NEVER** use Reddit / Twitter / Stocktwits / aggregator-only headlines as the primary source. They can supplement but not stand alone.
- `label` should be human-readable (e.g. "Reuters — Micron HBM sold out", not the raw URL). Hostname-only is the rendering fallback if `label` is missing.
- `url` MUST be a stable permalink. Skip ephemeral search-result URLs, session-id query params, etc.
- Optional `publishedAt` on each source (ISO 8601 with TZ) — useful when the entry-level `publishedAt` is the EVENT time but a specific source's article publish time differs (e.g. the company filed at 4:05pm but Reuters posted at 5:23pm). If unsure, omit.

The dashboard renders these as small clickable pills below the news-detail body
(`新聞來源 · Sources` section, opens in new tab). User clicks to verify the underlying
research, especially for big-number claims like "+682% EPS YoY" or "HBM sold out".

### 8.2 Run the build

```powershell
cd <repo-root>
py parse_tv.py            # regenerates tv-summary.json with the latest YoY math
py build_dashboard.py     # default --date = today's local date
```

What gets written:
- `dashboard/data/<DATE>.json` — full per-day snapshot (this is the source the dashboard reads)
- `dashboard/data.json` — copy of latest (backward-compat)
- `dashboard/dates.json` — regenerated by scanning `data/*.json` (controls the date strip + calendar)
- `dashboard/index.html` — regenerated from the `INDEX_HTML` template in `build_dashboard.py`

To publish a different date (e.g. backfill yesterday's scan from a stale Barchart cache), pass `--date 2026-05-12`.

### 8.3 Start / verify the preview server

If not already running:
```
mcp__Claude_Preview__preview_start  name=sips-dashboard
```

Then open http://127.0.0.1:5510/ in the user's browser. Confirm:
- **Header** reads **"Stocks In Play"** with the brief description below
- **Date strip** shows today's pill (e.g. `5/13, Wed`) active in violet; the **white** `選擇日期` calendar button opens a month picker showing only dates with data
- **Today's SIPs** page lists 10-12 cards ranked by MAGNA53 score, each showing: ticker / chg / catalyst / **colored Forward YoY block** (green positives, red negatives, no N/M except when prior=0)
- **Click any SIP card** → stock detail page renders 6 sections: News Detail (with `Published May 13, 4:05 PM ET` real-time pill), Catalyst Summary, EPS/Rev quarterly charts, MarketSurge-style quarterly table, Forward YoY (with Copy button), Company News history (grouped by Today/Yesterday/weekday names)
- **Earnings Results** — shift+click both subtabs combines into ONE sheet with Session column, sortable by `YoY Rev`. Whole row is clickable.
- **Catalyst Deep Dive** — whole row is clickable (cursor: pointer).
- **SCANX** — gap-up entries green, gap-down red; each entry is one clickable chip going to the stock detail.

### 8.4 Dashboard data contract

When writing `news_detail.json`, remember these fields are consumed by the dashboard:

| Field | Path | Used at |
|---|---|---|
| `publishedAt` | `stocks[SYM].publishedAt` | News Detail pill ("Published May 13, 4:05 PM ET"); Company News list timestamps |
| `publishedTimezone` | `stocks[SYM].publishedTimezone` | Display label after the time (e.g. " ET") |
| `detail` | `stocks[SYM].newsDetail` | News Detail card body (multi-paragraph) |
| `catalyst` (from `final-candidates.csv`, not news_detail.json) | `stocks[SYM].catalyst` | 1-line Catalyst Summary card + Company News title + SCANX item description + fallback when `newsDetail` missing |
| MAGNA53 hits (computed by dashboard JS) | `stocks[SYM]._m53` | SIP card score + M/G/N/A/5/3 bits |

The dashboard's auto-selection logic (`magna53()` in `index.html`) scores each candidate as:
- M (Massive): +5 if EPS surprise ≥100% OR Rev surprise ≥100% OR Rev YoY ≥100% OR EPS YoY ≥100%
- G (Gap): +2 if |%chg| ≥ 4
- A (Acceleration): +3 if Rev YoY ≥ 25%
- Type bonuses: earnings +4, guidance +3, contract/M&A/FDA +3, analyst +2
- Type penalties: momentum -6, news without M -2
- Bonus: +1 if |%chg| ≥ 15%, +1 if appears in both pre AND post sessions
Cards shown if score ≥ 4. Top 12 displayed.

### 8.5 What to tell the user at the end of Phase 7

After publishing, end the chat response with a single line:

> Dashboard updated → http://127.0.0.1:5510/#/sips (5/13, Wed scan, N stocks, top SIP = TICKER)

Replace N with the candidate count and TICKER with the #1 ranked SIP.

### 8.5b Phase 10a — One-time news fetch for placeholder studies (NEW)

The dashboard lets the user manually create a "placeholder" study via **Studies → search box → "Create new <TICKER>"**. Those entries land in `dashboard/studies/studies.json` with:

```json
{ "symbol": "XYZ",
  "snapshot": { "_placeholder": true, "newsDetail": "", "catalyst": "", ... },
  "ohlcv": { "open": null, ... }, "notes": "", ... }
```

If the ticker turns up in **today's** scan, Phase 10b's existing logic (below) will replace the snapshot with rich data and un-hide the chart sections automatically — nothing extra to do.

If the ticker is **NOT** in today's scan, do a **one-time** online news scrape so the user has something to read while they wait for the ticker to appear in a future scan. After the fetch, mark `_newsFetched: true` on the snapshot so we don't keep re-fetching every day.

**Algorithm (Python pseudo-code):**

```python
import json, requests, os
studies_path = 'dashboard/studies/studies.json'
if not os.path.exists(studies_path): return
with open(studies_path, encoding='utf-8') as f:
    studies = json.load(f)

todays_syms = set(stocks.keys())  # from current /SIPs scan
changed = False
for st in studies:
    sym = st.get('symbol')
    snap = st.get('snapshot') or {}
    if not snap.get('_placeholder'):
        continue          # already filled
    if sym in todays_syms:
        continue          # Phase 10b will handle this — skip
    if snap.get('_newsFetched'):
        continue          # already done a one-time fetch — don't repeat
    # One-time fetch: pull recent news for this ticker.
    # Source order: Yahoo Finance news API → Finviz news section → Barchart news tab.
    # Pick the latest 1-3 headlines + bodies, concat into newsDetail.
    news = fetch_recent_news(sym)   # returns dict {headline, publishedAt, body} list, or []
    if not news:
        snap['_newsFetched'] = True   # mark even on empty so we don't retry next run
        changed = True
        continue
    snap['catalyst'] = news[0]['headline'][:200]
    snap['newsDetail'] = '\n\n'.join(f"[{n['publishedAt']}] {n['headline']}\n{n['body']}" for n in news)
    snap['_newsFetched'] = True
    snap['scanDate'] = DATE
    changed = True

if changed:
    with open(studies_path, 'w', encoding='utf-8') as f:
        json.dump(studies, f, ensure_ascii=False, indent=2)
```

**Fetch sources for `fetch_recent_news`** (in order of reliability — stop at first success):

1. **Yahoo Finance news API** (no key): `https://query1.finance.yahoo.com/v1/finance/search?q=<TICKER>&newsCount=5` — returns JSON with `news[].title`, `news[].link`, `news[].providerPublishTime` (Unix timestamp), `news[].publisher`.
2. **Finviz news section**: scrape `https://finviz.com/quote.ashx?t=<TICKER>` → `<table class="fullview-news-outer">`. Rows have `td` containing the headline link + published-time text.
3. **Barchart news tab**: Playwright at `https://www.barchart.com/stocks/quotes/<TICKER>/news` — intercept the news XHR.

For body text, follow each headline URL and extract `<article>` / `<div class="caas-body">` / equivalent. Skip if the URL is paywalled or returns < 100 chars.

**Critical invariants:**

- **One-time only**: `_newsFetched: true` guarantees this won't fire again. Manual catalyst edits by the user (`study.catalyst` override) are never touched — we only write into `snapshot.catalyst` / `snapshot.newsDetail`.
- **Skip tickers already in today's scan**: 8.6 Phase 10b will populate them with much richer data (TV quarterly, sessions, MAGNA, claude rationale). Don't duplicate work.
- **Empty result is final**: if a ticker has no news anywhere, `_newsFetched: true` still gets stamped so we don't retry every run. User can manually trigger a refresh by removing `_newsFetched` from the JSON.

Run this BEFORE Phase 10b so the prev_ohlcv fetch can see the same target ticker set.

### 8.6 Phase 10b — Fetch OHLCV per-target-date for every candidate + every existing Study

After the trading day closes (~5pm ET), fetch OHLCV bars for two populations, **each at its
own target date**:

1. **Today's scan candidates** — target date = yesterday's trading day. Saves "Save to
   Studies" clicks pre-populating with yesterday's bar.
2. **Every study in `dashboard/studies/studies.json`** — target date = each study's own
   `ohlcv.date` field. If `ohlcv.date` is empty (or in the future), fall back to yesterday.
   **Skip studies whose `ohlcv.open` is already filled** — manual data is sacred, only
   blank rows get auto-filled.

**Why per-study dates matter:** a saved study at `ohlcv.date = 2026-02-04` (e.g. AMD's
Q4 '25 earnings catalyst) should fetch **2/4's bar**, not yesterday's. If 2/3 was a
weekend / holiday, `prev_close` should fall back to the most recent trading day BEFORE
2/4 (so e.g. for a Monday earnings, prev_close = the prior Friday's close). The dashboard's
day-%Chg readout `(close − prev_close) / prev_close · 100` only makes sense when both
sides come from consecutive trading days — never a calendar-day diff.

Write the merged result to `./prev_ohlcv.json` at repo root.

**Schema** (`prev_ohlcv.json`):
```json
{
  "FIG":  { "date": "2026-05-14", "open": 22.60, "high": 24.10, "low": 22.45, "close": 23.85, "prev_close": 22.10, "volume": 18200000 },
  "AMD":  { "date": "2026-02-04", "open": 215.00, "high": 218.58, "low": 199.15, "close": 200.19, "prev_close": 242.11, "volume": 107173300 }
}
```

Note `AMD` here is the *historical-date* fill — the bar is dated 2026-02-04 because that's
the study's saved `ohlcv.date`, not the "current yesterday".

**`prev_close` is required** and is the close of the trading day **immediately before the
matched bar** in Yahoo's returned chart array — NOT calendar day - 1. Holidays + weekends
are auto-skipped because Yahoo's chart endpoint only returns trading-day bars.

**Build sequence (Python pseudo-code):**
```python
# 1. Read existing studies to know which tickers need filling + at what date
import json, os
from datetime import datetime, timedelta, timezone
import urllib.request

studies = []
studies_path = 'dashboard/studies/studies.json'
if os.path.exists(studies_path):
    with open(studies_path, encoding='utf-8') as f: studies = json.load(f)

# 2. Build (ticker, target_date) work list.
#    candidates: target_date = yesterday's trading day (Yahoo will fall back if non-trading)
#    studies:    target_date = study.ohlcv.date (filled) else yesterday
yesterday_iso = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
work = []
for sym in todays_tickers:
    work.append((sym, yesterday_iso))
for st in studies:
    if (st.get('ohlcv') or {}).get('open') is not None:
        continue   # manually-filled — sacred
    sym  = st['symbol']
    sdate = (st.get('ohlcv') or {}).get('date') or yesterday_iso
    # Skip future dates (Yahoo won't have data yet)
    if sdate > datetime.utcnow().strftime('%Y-%m-%d'):
        continue
    work.append((sym, sdate))

# 3. Per (ticker, date), fetch a 14-day window around the date and resolve the matching bar
def fetch_bar_at(sym, target_iso):
    t  = datetime.strptime(target_iso, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    p1 = int(t.timestamp()) - 10*86400
    p2 = int(t.timestamp()) +  2*86400
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}&interval=1d'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as r: d = json.load(r)
    res = d['chart']['result'][0]
    ts  = res['timestamp']; q = res['indicators']['quote'][0]
    bars = []
    for i, t_ in enumerate(ts):
        if q['open'][i] is None or q['close'][i] is None: continue
        bars.append({
            'date': datetime.fromtimestamp(t_, tz=timezone.utc).strftime('%Y-%m-%d'),
            'open': round(q['open'][i],2),  'high': round(q['high'][i],2),
            'low':  round(q['low'][i],2),   'close': round(q['close'][i],2),
            'volume': int(q['volume'][i]) if q['volume'][i] is not None else None,
        })
    if not bars: return None
    # Pick the bar matching the target, else nearest prior (handles weekend/holiday targets)
    matched = next((b for b in bars if b['date'] == target_iso), None)
    if matched is None:
        priors = [b for b in bars if b['date'] <= target_iso]
        if not priors: return None
        matched = priors[-1]
    # prev_close = the bar immediately BEFORE the matched bar in the chart array
    idx = bars.index(matched)
    prev_close = bars[idx-1]['close'] if idx > 0 else None
    return {**matched, 'prev_close': prev_close}

out = {}
for sym, target_iso in work:
    bar = fetch_bar_at(sym, target_iso)
    if bar: out[sym] = bar

with open('prev_ohlcv.json', 'w') as f: json.dump(out, f, indent=2)
```

**Key behaviors of `fetch_bar_at`:**

- **Exact-date match wins.** If Yahoo's array contains the target_iso, use it directly.
- **Weekend/holiday fallback.** If target_iso falls on a non-trading day (or Yahoo simply
  has no bar for it), use the **nearest prior trading day** in the window. The 10-day
  preceding buffer in the URL guarantees we have several priors to fall back through.
- **`prev_close` = previous bar in the array.** Holidays/weekends are naturally skipped
  because Yahoo's chart endpoint only returns trading-day bars. So for a Monday target,
  `prev_close` is automatically the prior Friday's close — not "calendar-day minus one".
- **Per-ticker fetch.** Each (sym, date) pair gets its own HTTP request. The 14-day window
  is wide enough that 99% of cases resolve in one call. For each ticker, only ONE call is
  made even when the study and the candidate scan both want it (dedupe by sym+date before
  the loop if perf matters).

**How to source** (in order of reliability):
1. **Yahoo Finance** `https://query1.finance.yahoo.com/v8/finance/chart/<TICKER>?period1=<P1>&period2=<P2>&interval=1d` — public JSON endpoint, no API key. Use `period1` / `period2` to define a 14-day window around the target date (not `range=5d`, which only gives the LATEST 5 bars and can't reach historical targets like 2026-02-04).
2. **Barchart `https://www.barchart.com/stocks/quotes/<TICKER>/price-history/historical`** — daily OHLCV table. Playwright scrape, XHR intercept on `/proxies/core-api/v1/historical/get?symbol=<TICKER>&type=eod` returns clean JSON.
3. **Finviz quote page** — only has the latest snapshot, no historical lookup. Avoid for studies.

**`build_dashboard.py` behaviour:**
- For **today's stocks** (in `stocks` dict): exposes `stocks[sym].prevOhlcv = prev_ohlcv_raw.get(sym)`.
- For **existing studies that need filling**: writes the matching entries into
  `dashboard/studies/studies.json` directly under each study's `ohlcv` field — but ONLY
  if `ohlcv.open` is null. Critically, when a study's existing `ohlcv.date` already had
  a value (e.g. 2026-02-04), the writeback preserves that date — since `fetch_bar_at`
  returned the bar for that exact date (or the nearest prior trading day), the date in
  `prev_ohlcv.json` will already match.
- Also syncs `snapshot.last = ohlcv.close` per the schema (header price-readout uses
  `snapshot.last` for the big number).

If `prev_ohlcv.json` doesn't exist, the rest of the pipeline runs fine — this step is
purely an enhancement that saves the user from re-typing yesterday's bar (or a historical
bar) for every Study every day.

### 8.6b Phase 10c — Deep Studies refresh (TV + news + earnings auto-detect + rewind)

Phase 10b only handled OHLCV. This phase covers the rest of the per-study refresh that
the standalone `/update-studies` skill normally performs, so running `/SIPs` alone gives
a complete Studies-library update. Walk every study in `dashboard/studies/studies.json`
and apply the relevant sub-phases below. Skip studies whose date is in the future and
respect manual edits throughout (never overwrite a non-empty `newsDetail`, `tv`, or
`customTypes` entry that was filled by the user).

**Full per-phase specs live at `D:\SIPs\skills\update-studies\SKILL.md`** — this section
is the integration checklist, not a re-copy of the algorithms. Read that file for
edge-case handling, Python→JS schema-conversion tables, and the universal YoY formula.

#### 10c.1 — News refresh + earnings auto-detect (all studies, blanks only)

**Default behaviour = blanks only.** Manual edits to `newsDetail` / `catalyst` are NEVER
overwritten — the user's hand-curated 繁體中文 prose is more valuable than what we'd
auto-fetch. The user can force a re-fetch by clearing the field in the dashboard
(Studies → study → news-detail card → delete contents) then re-running /SIPs.

For each study, only process if `snapshot.newsDetail` is empty AND `snapshot.catalyst`
is empty:

1. **Source** the news for `<TICKER>` near `study.ohlcv.date` via WebSearch / WebFetch /
   firecrawl. Same sourcing pattern as `/SIPs § 7` (the news-detail composer).
2. **Earnings auto-detect** — scan the headlines + body text for any of these signals:
   - `Q[1-4] 20\d\d earnings` / `Q[1-4] FY20\d\d earnings`
   - `reported earnings` / `posts Q[1-4]` / `earnings call` / `earnings release`
   - `EPS beat` / `EPS miss` / `revenue beat` / `revenue miss`
   - `業績電話會議` / `Q[1-4] .* 業績`
   - The target date matching a well-known reporter's known earnings calendar
3. If ANY signal fires AND `"earnings"` is not in `study.customTypes`:
   - Add `"earnings"` to `customTypes`
   - Jump to Phase 10c.2 for THIS study (TV scrape) before composing the newsDetail
4. **Compose** the `newsDetail` in **繁體中文 markdown**, same format as `/SIPs § 7`:
   - Lead: `<date> <時段> <event>`
   - 1–3 supporting facts in **bold** (`**EPS $X** vs $Y`)
   - Short forward-looking analysis paragraph
   - Paragraphs separated by `\n\n`
5. **Compose** a `catalyst` one-liner (≤200 chars) for the preview-card teaser.
6. **Respect user edits**: only write `newsDetail` / `catalyst` if they're empty.

#### 10c.2 — TradingView FQ refresh (earnings-tagged studies, blanks only)

**Default behaviour = blanks only.** Don't re-scrape filled TV data — the user may have
manually corrected the figures, or the historical-quarter rewind from a previous run
may have anchored `latest_idx` to a past quarter that we don't want to clobber with
today's latest.

For each study with `"earnings"` in `customTypes` AND `snapshot.tv` missing/empty/
`_placeholder: true`:

```bash
cd D:\SIPs && node tv-scrape.js <SYM>       # Playwright, ~30-60s
cd D:\SIPs && py parse_tv.py <SYM>          # writes tv-summary.json
```

Read `tv-summary.json`, find the row with `Ticker == SYM`, convert Python keys to the
JS schema used in `study.snapshot.tv`. The conversion table lives at
`update-studies/SKILL.md § Phase 3` — do not re-derive it here.

After writing `study.snapshot.tv`:
- Remove `_placeholder: true` from `study.snapshot` if present
- Remove `eps_chart` / `rev_chart` / `ms_table` / `yoy_block` from `study.hiddenSections`
  so the dashboard surfaces the freshly-filled sections

**Non-earnings studies skip this phase entirely.**

#### 10c.3 — Historical-quarter rewind (earnings studies dated in the past)

For each earnings-tagged study whose `ohlcv.date` is more than ~3 trading days old, the
fresh TV scrape from 10c.2 returns TODAY's latest quarter as `chart.latest_idx` — which
is WRONG for a historical earnings event. Apply the rewind:

1. For each quarter, compute its end date (Q1→Mar 31, Q2→Jun 30, Q3→Sep 30, Q4→Dec 31).
2. Add the company's typical **report lag** (~30d large-caps / ~45d smaller names) to get
   the reporting date. The highest-index quarter where `(qend + lag) <= ohlcv.date` is
   the new `target_idx`.
3. Clear `chart.eps_reported[i]` and `chart.rev_reported_M[i]` for every `i > target_idx`.
4. Set `chart.latest_idx = target_idx` and `study.focusQuarterIdx = target_idx`.
5. Recompute the `tv` summary (`latestEPS` / `consensusEPS` / `priorYrEPS` / surprise /
   YoY / `yoyBlock` / `epsEst_next4` / `revEst_next4`) from the rewound chart anchored at
   `target_idx`. See `update-studies/SKILL.md § Phase 3b` for the exact formulas + the
   verified AMD @ 2026-02-04 example.

Add a `>⚠️` blockquote to the composed `newsDetail` noting that forward 4 estimates are
TradingView's CURRENT consensus, not the at-the-time consensus.

#### 10c.4 — Atomic writeback

**BEFORE writing back, mirror every touched study's flat date-bound fields into its
`datedSnapshots[ohlcv.date]` slot.** REQUIRED — the dashboard's "researched dates" chip
reads from this map, so a refresh that only updates the flat fields leaves the new date
invisible in the UI. The dashboard's `updateStudy()` does this mirror automatically on
every edit, but skill writes bypass it by hitting JSON directly. Replicate the mirror
here. Same exact rule as `/update-studies` Phase 5:

```python
DATE_BOUND_FIELDS = ['snapshot','ohlcv','hiddenSections','notes','customTypes',
                     'customChart','focusQuarterIdx','newsDetail']

def build_dated_slot(st):
    return {
        'snapshot':       dict(st.get('snapshot') or {}),
        'ohlcv':          dict(st.get('ohlcv') or {}),
        'hiddenSections': list(st.get('hiddenSections') or []),
        'notes':          st.get('notes') or '',
        'customTypes':    list(st.get('customTypes') or []),
        'customChart':    (dict(st['customChart']) if st.get('customChart') else None),
        'focusQuarterIdx': st.get('focusQuarterIdx'),
        'newsDetail':     st.get('newsDetail'),
    }

def has_research_data(slot):
    s = slot.get('snapshot') or {}
    o = slot.get('ohlcv') or {}
    if s.get('newsDetail') or s.get('catalyst') or s.get('tv'): return True
    if o.get('open') is not None or o.get('close') is not None: return True
    if (slot.get('notes') or '').strip(): return True
    # customTypes default ['earnings'] alone doesn't count — pre-seeded so /update-studies
    # auto-runs the TV scrape, not user research. 2+ tags OR a single non-earnings tag
    # means the user diverged from the default and the date should archive.
    ct = slot.get('customTypes') or []
    if isinstance(ct, list):
        if len(ct) >= 2: return True
        if len(ct) == 1 and str(ct[0]).lower() != 'earnings': return True
    if slot.get('newsDetail') and str(slot['newsDetail']).strip(): return True
    return False

for st in studies:
    od = (st.get('ohlcv') or {}).get('date','')
    if not od: continue
    st.setdefault('datedSnapshots', {})
    slot = build_dated_slot(st)
    if has_research_data(slot):
        st['datedSnapshots'][od] = slot
    elif od in st['datedSnapshots']:
        del st['datedSnapshots'][od]
```

Keep `DATE_BOUND_FIELDS` / `build_dated_slot` / `has_research_data` in sync with the JS
versions in `dashboard/index.html` — both `/SIPs` Phase 10c.4 and `/update-studies`
Phase 5 use this same logic.

THEN write the updated array back to
`dashboard/studies/studies.json` in one shot (`ensure_ascii=false`, `indent=2`).

Also sync `snapshot.last = ohlcv.close` (header big-price-readout source). Phase 10b's
backfill loop already did this for studies it filled — this is just a defensive pass for
studies whose ohlcv was already manually filled but whose `snapshot.last` drifted.

Also sync `snapshot.chgPct = (close − prev_close) / prev_close * 100` so the header
chg %, preview-card chg %, and intent-default rule (next paragraph) all read fresh
values.

**Default the trade intent from the gap direction.** Mirror `/update-studies` Phase 2's
rule exactly: ONLY when `study.intent` is null / undefined (the user hasn't manually set
a direction), derive a default from the synced chgPct. Never overwrite an existing
intent — manual choice is sacred.

| chgPct after sync | study.intent default |
|---|---|
| > 0 (gap up) | `'long'` |
| < 0 (gap down) | `'short'` |
| 0 or null | leave unset |

Implementation mirrors the Python pseudo-code in `update-studies/SKILL.md § Phase 2` —
this is one rule that applies identically to both skills so a study auto-classified by
/SIPs at scan time and a study auto-classified by /update-studies at refresh time end
up with the same intent.

```python
if study.get('intent') is None and snap.get('chgPct') is not None:
    chg = snap['chgPct']
    if chg > 0:    study['intent'] = 'long'
    elif chg < 0:  study['intent'] = 'short'
```

#### 10c.5 — Error handling

Per-ticker failures NEVER abort the run. Finish the other tickers first.

| Failure | Action |
|---|---|
| TV scrape times out / fails | `[warn] SYM: tv-scrape failed`; skip TV, continue |
| News fetch returns nothing | leave `newsDetail` empty; user can fill it manually |
| Yahoo HTTP error during a rewind double-check | log + skip the rewind, keep current tv |
| `studies.json` unparseable | ABORT (don't corrupt the user's library) |

### 8.7b Phase 10d — Fetch 6-month daily candles (Yahoo)

Powers the **股價走勢** TradingView-style chart on the stock-detail page. Pulls last ~130 trading days (~6 months) of OHLCV bars from Yahoo Finance for the **union of** today's candidates + claude/codex/gemini/grok picks + every saved study.

**Run AFTER Phase 9 (claude_picks.json written) and AFTER studies refresh (Phase 10a-c), but BEFORE Phase 10 (build_dashboard.py)** so:
1. `fetch_candles.py` reads the latest `dashboard/data/<DATE>.json`, picks files, and `studies.json` to know which symbols to fetch.
2. `build_dashboard.py` runs after — it doesn't need to know about candles (dashboard loads `candles.json` directly via fetch).

**Command:**
```powershell
py fetch_candles.py
```

**支援選用日期參數:** `py fetch_candles.py YYYY-MM-DD` — 週末/隔日補跑時必須傳當次掃描日,否則腳本預設讀「今天」的 `dashboard/data/<DATE>.json` 會讀錯日期的候選清單(讀到隔日或空檔)。

The script (at `./fetch_candles.py`):
1. Walks the 3 sources to collect a unique symbol set
2. Parallelizes Yahoo Finance `query1.finance.yahoo.com/v8/finance/chart/<SYM>?interval=1d` calls (8 workers)
3. Slices each ticker to the last 130 bars (~6 months) and writes `dashboard/candles.json`

**Speed/cost:** ~5-10s for 50-100 tickers. $0 (Yahoo's chart endpoint is unauthenticated and rate-limit-friendly at this scale).

**Failure mode:** if a symbol returns < 10 bars or 404s (typically delisted / not in Yahoo's coverage), it's silently skipped. Logged at the end as `[skipped] N symbols (Yahoo lookup failed): SYM1, SYM2, ...`. The chart on the stock-detail page falls back to "沒有歷史 K 線資料" for those symbols.

**Note on session-agnostic data:** Yahoo's `interval=1d` returns one OHLC bar per trading day (regular session only, 9:30 AM - 4:00 PM ET). It does NOT include pre-market or post-market trades. So the candle chart's latest bar always represents the last completed regular session, regardless of when the scrape runs.

---

### 8.7 Phase 11 — auto-publish to GitHub Pages (REQUIRED for hosted dashboard)

This repo is wired with `.github/workflows/pages.yml`. Every push that touches `dashboard/**` triggers an auto-deploy to **https://chi2tseng.github.io/stocks-in-play/** within ~30 seconds.

**Run this at the very end of every `/SIPs` scan:**

```bash
git add dashboard/data/<DATE>.json dashboard/data.json dashboard/dates.json dashboard/index.html \
        dashboard/candles.json \
        dashboard/studies/studies.json dashboard/studies/images \
        claude_picks.json news_detail.json day_resets.json catalysts_today.json
git commit -m "scan: <DATE> — top SIP <TICKER>, <N> candidates"
git push
```

`dashboard/studies/` is the **personal Studies library** — `studies.json` plus the screenshot binaries the user pasted into Notes/Screenshots panels. The local sidecar (`D:/SIPs/sidecar.py`) writes these files in real time while the user edits at `127.0.0.1:5510`. Committing them here makes the hosted GitHub Pages dashboard act as a **read-only mirror on phone/other devices** (sidecar-less = view-only mode, all edit buttons hidden by `body.readonly-mode` CSS). If the `studies/` directory is empty (user hasn't added any), the `git add` for it is a no-op — that's fine.

Use the date `<DATE>` from the scan, the #1 ranked Claude pick as `<TICKER>`, and the total candidate count as `<N>`. Example commit message:

```
scan: 2026-05-15 — top SIP FIG, 29 candidates
```

After ~30 seconds, the public dashboard at https://chi2tseng.github.io/stocks-in-play/ reflects the new data. Calendar picker picks up the new date automatically.

**Verification (optional):**
```bash
# Watch the Pages deploy status
gh run watch
# Or list recent deploys
gh run list --workflow=pages.yml --limit 3
```

---

## § 8.8 Phase 12 已取消 — 各 AI 各自獨立工作(2026-07-13 使用者指令)

**Claude 的 /SIPs 到 Phase 11(build + push)就結束,不再自動發射 Codex/Gemini/Grok。**
使用者要的是「各個 AI 各自工作」:每家各自在自己的 CLI 打 `/SIPs`(讀 `D:\SIPs\AGENTS.md` → 跑自己的 picks skill),
**自己 scan(掃描包舊了/沒有就重掃 barchart)/ 自己 judge / 自己 build+push**。四個 tab 由四次獨立執行各自更新。
**Claude 只管 `claude_picks.json` 這一席 —— 不發射、不等其他三席、不做收尾。**

**分工原則不變:機械掃描各自做(掃描包共享但可各自重掃),新聞研究與判斷各自獨立** —
Grok 用 X 即時搜尋、Gemini 用 Google、Codex 用自家 WebSearch,各查各的、各判各的、各寫各的 picks 檔。

---

### 手動發射(選用 — 只有使用者**明確**說「順便也幫我跑其他 AI / 一次全部跑」才用)

平時**不要**跑這段。要手動發射時,三個同時 `run_in_background: true`(timeout 600000;Gemini 席 900000)、
一律用 **Bash tool**(git-bash 背景掛隱藏 console,桌面零視窗;**禁用 PowerShell tool 發 console CLI** —
會留可見灰視窗常駐,grok leader 尤其賴著不走)。各家 skill / 發射鏈自己 build+push,先完成先上線、絕不互等:

```bash
# Codex (ChatGPT) — 旗標已實測(Bash tool 發射)。註:免費額度已耗盡至 2026-07-31,期間此席會 fail-fast — 屬預期,收尾照樣出其他家
cd /d/SIPs && "/c/Users/chi2t/AppData/Local/OpenAI/Codex/bin/codex.exe" exec -m gpt-5.5 -c model_reasoning_effort=xhigh --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox "/SIPs-codex-picks"
```
```bash
# Gemini — 經 agy(Antigravity CLI)發射,已實測 2026-07-10(gemini CLI 免費層被 Google 下線;agy 共用 IDE 登入)。
# agy 的 accept-edits 不放行 git → **同一條發射鏈**在 agy 寫完 picks 後自動接手 build+push(Gemini 席自給自足,不靠 Claude);prompt 保持零雙引號零撇號
cd /d/SIPs && "/c/Users/chi2t/AppData/Local/agy/bin/agy.exe" -p 'Run the SIPs-gemini-picks skill: read C:\Users\chi2t\.gemini\skills\SIPs-gemini-picks\SKILL.md and follow it end to end. Do your own web research for each candidate you consider. The launcher chain runs build and push after you finish - just write your picks file and stop.' --model "Gemini 3.1 Pro (High)" --mode accept-edits --print-timeout 15m && py build_dashboard.py | tail -2 && git add gemini_picks.json dashboard/data/*.json dashboard/data.json dashboard/dates.json dashboard/index.html && git commit -m "gemini picks: $(date +%F)" && { git push || { git pull --rebase && git push; }; }
```
```bash
# Grok — 旗標已實測(2026-07-10;Bash 發射則 leader 隱形常駐,無視窗)
cd /d/SIPs && "$HOME/.grok/bin/grok.exe" -m grok-4.5 --always-approve --cwd 'D:\SIPs' -p "Run the SIPs-grok-picks skill from your skills directory, end to end."
```

**回收規則(只有上面手動發射時才適用 —— 平時 Claude 不發射,就沒有收尾這回事):**
- 每個完成通知回來時驗證:對應 `*_picks.json` 的 mtime 是今天 + JSON parse 過 + picks 非空。失敗 → 讀該任務 stderr 尾巴、回報使用者哪家掛了,**不自動重試**(免費額度別燒在重跑)。
- **三個都回收後(或 timeout)做收尾(此步不擋任何一家上線 — 各家早已自行發布)**:`git pull --rebase` → `py build_dashboard.py` → `git add codex_picks.json gemini_picks.json grok_picks.json dashboard/data/*.json dashboard/data.json dashboard/dates.json` → commit `"judges: <DATE> — codex/gemini/grok"` → push。收尾最後**清殭屍 CLI**(工作完成但程序常駐會吃記憶體/掛視窗):`taskkill //IM grok.exe //F 2>/dev/null; taskkill //IM codex.exe //F 2>/dev/null`(bash 語法;殺 leader 無害,下次發射自動重生)。三家都**自己發布**(Codex/Grok 由 skill、Gemini 由發射鏈),此步只是**保險**:補漏任何發布失敗的評審,無漏則只是空轉一次 build。
- 併發 push 衝突是預期內的:Codex/Grok skill 內建 pull-rebase 重試,Claude 收尾的 `git pull --rebase` 是最後保險。
- 給使用者的完成訊息:四個 tab 各自的 #1 pick 一行(讀各 picks 檔的 rank 1)。

---

## § 9. Edge cases & execution notes

- **Windows shell:** always `firecrawl.cmd` (not `firecrawl`) — the `.ps1` shim is blocked by ExecutionPolicy
- **Firecrawl key:** already persisted at User scope as `FIRECRAWL_API_KEY`. Verify with `firecrawl.cmd --status` if scrapes start failing
- **TradingView 404:** if all three exchanges (NASDAQ/NYSE/AMEX) 404, mark `Forward YoY` block as **「無 TradingView 季度估計資料」** and continue
- **Finviz rate-limit:** if scrapes start returning empty bodies, add `--wait-for 8000` and reduce batch parallelism to 3
- **No earnings catalyst:** stocks moving on M&A, FDA, contracts, etc., still get the MAGNA53 + 進場建議 sections but skip Phase 5–7 (no YoY block)
- **Empty result set:** if Phase 1 yields zero qualifying candidates → print **「今日無符合條件的股票（沒有 ±4% 且成交量 ≥100k 的 gap）」** and exit cleanly
- **Status updates:** at the start of each phase, emit a one-line status (e.g. "Phase 3/8 — MAGNA53 classification on 14 candidates"). User wants visible progress

---

## § 10. Reference & related skills

- **`update-studies` skill** (at `./skills/update-studies/SKILL.md`) — Claude-driven daily refresh of every Study's OHLCV (open/high/low/close/prev_close/volume) based on each study's `ohlcv.date`. Walks the studies file, hits Yahoo's chart API via inline Python, writes back. All Read/Edit/Bash tool calls — no separate Python file. Installable via skillfish: `npx skillfish add chi2tseng/stocks-in-play update-studies`. Triggers on `/update-studies` or natural phrases like "refresh studies" / "update my OHLCV".
- `/ep9m-trading` skill — deeper Stockbee context (sugar babies, DEP, FHP, institutional quality, OLC). Read on demand if the user asks follow-up questions like "should I treat this as a sugar baby?"
- `reference_firecrawl.md` in auto-memory — confirms the FQ URL trick + CLI quirks on this machine
- `reference_playwright_tv.md` + `reference_playwright_barchart.md` in auto-memory — Playwright scraper setup
- **`./docs/NEWS_TIME_SPEC.md`** — full spec for sourcing & formatting real news publication times (read before writing `news_detail.json` in Phase 7)
- Dashboard source: `./build_dashboard.py` — contains the static-SPA template (`INDEX_HTML` string). Re-run after any data refresh.
- Source PDF: `./docs/stockbee-sip.pdf` — MAGNA53 + entry/exit definitions
