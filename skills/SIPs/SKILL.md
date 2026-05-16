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

You are running the user's daily **NTRT (News-Triggered) / MTRT (Momentum-Triggered)** trading routine to find **SIPs (Stocks In Play) / EPs (Earnings Plays)**. The final deliverable is a 繁體中文 morning brief ranking the day's best longs and shorts, with strict-format YoY estimate blocks for every earnings mover.

If `$ARGUMENTS` is non-empty (e.g. `NVDA,AAPL`), **skip Phase 1** and treat that list as the candidate set. Otherwise run Phase 1.

Use TodoWrite to track the phases. Surface progress aggressively — the user gets anxious when commands run silently.

---

## § 0. Daily-run quick reference (this is what runs each morning)

| Step | Tool | Time | Cost | Output |
|---|---|---|---|---|
| 1. Gap scan | `node ./barchart-scrape.js` (Playwright + XHR intercept) | ~7s | $0 | `candidates.csv` (84-ish rows) |
| 2. Catalyst hunt | Claude `general-purpose` agent doing parallel WebSearches on **all** candidates | ~5 min | $0 | inline markdown table → updates `catalysts` dict in `build_report.py` |
| 3. TradingView FQ | `node ./tv-scrape.js TICKER1 TICKER2 ...` | ~3-5s per ticker | $0 | `<TICKER>-earnings-fq.md` |
| 4. Parse TV | `py ./parse_tv.py` | <1s | $0 | `tv-summary.json` + `tv-summary.csv` |
| **5. Finviz shorts + perf** | `node ./finviz-shorts.js` (parallel, throttled) | ~70-90s | $0 | `shorts.json` (shortFloat / shortRatio / marketCap_M / perf1M-12M for every candidate) |
| 6. Build report | `py build_report.py` + `py gen_tables.py` | <1s | $0 | `final-candidates.csv` + `sorted-views.md` |
| 7. Final brief | Claude composes the 繁體中文 brief | — | — | inline in chat |
| **8. Write news_detail.json** | **Claude curates per-symbol `detail` + `publishedAt` for the top 10 SIPs** | ~3 min | $0 | `news_detail.json` (top-10 only; rest auto-fallback to catalyst sentence) |
| **9. Write claude_picks.json** | **Claude writes hand-picked rankings + 繁中 rationale + `intent: long\|short` for 5-10 highest-conviction picks** | ~2 min | $0 | `claude_picks.json` ([{symbol, rank, intent, rationale}]) — drives the **default "Claude 精選"** subtab on Today's SIPs. **Direction-match rule:** `intent: long` only for gap-up tickers (chgPct > 0); `intent: short` only for gap-down (chgPct < 0). Dashboard silently drops mismatches. |
| **10. Publish dashboard** | `py build_dashboard.py` (no args = today's ISO date) | <1s | $0 | `dashboard/data/<DATE>.json`, `dates.json`, `data.json`, `index.html` |

**Total runtime:** ~5-10 min including news-detail curation. **Total cost:** $0.

**Key files in repo root (working directory):**
- `barchart-scrape.js` — Playwright Barchart scraper (XHR intercept on `/proxies/core-api/v1/quotes/get`)
- `tv-scrape.js` — Playwright TradingView FQ scraper (handles NASDAQ→NYSE→AMEX auto-detect)
- **`finviz-shorts.js`** — Playwright Finviz quote-page scraper (concurrency 2 + jitter to avoid Cloudflare). Reads tickers from `candidates.csv` and writes `shorts.json` with shortFloat / shortRatio / marketCap_M / floatShares_M / perf1M / perf3M / perf6M / perfYTD / perf12M per ticker. Powers the **N (Neglect)** + **5 (DTC)** MAGNA bits and the Short Squeeze page.
- `parse_tv.py` — extracts Reported + Estimate raw figures + YoY block from TradingView markdown
- `build_report.py` — merges candidates.csv + tv-summary.json + catalysts dict → final-candidates.csv
- `gen_tables.py` — produces 3 sorted markdown views (|%Chg| / Session / Price)
- **`build_dashboard.py`** — assembles `dashboard/data/<DATE>.json` + writes the static SPA at `dashboard/index.html` (revolut design system, "Stocks In Play" branding). Merges `shorts.json` + `claude_picks.json` if present.
- **`news_detail.json`** — per-symbol detail + `publishedAt` (real news publication time). Optional input; spec at `NEWS_TIME_SPEC.md`.
- **`claude_picks.json`** — `{ "picks": [ {"symbol", "rank", "intent": "long"|"short", "rationale", "neglected"?: bool} ] }`. Drives the **default "Claude 精選"** subtab on Today's SIPs. **Direction-match rule:** longs must be gap-up, shorts must be gap-down — mismatches are silently filtered out by the dashboard. Symbols not in today's candidates also drop.
- **`NEWS_TIME_SPEC.md`** — contract for how to source + format real news timestamps. Read it BEFORE writing `news_detail.json` (see § 8 below for the integration).

**Dashboard URL:** http://127.0.0.1:5510/ (served by the `sips-dashboard` preview server, started by `mcp__Claude_Preview__preview_start` with name `sips-dashboard` and `port: 5510`). The server is always running once started; the dashboard auto-refreshes when `data/<DATE>.json` is rewritten.

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

### Step 1: scrape Barchart pre-market + post-market gappers — **Playwright with XHR intercept (default since 2026-05-13)**

Barchart renders the gapper table inside a `<bc-data-grid>` Shadow DOM custom element, with the actual ticker data fetched from `/proxies/core-api/v1/quotes/get` as JSON. Text scraping (Firecrawl markdown / Playwright `innerText`) misses the shadow DOM. **The clean approach is to intercept the API response directly.**

**Default command:**
```powershell
cd C:\Users\chi2t
node barchart-scrape.js
```

This script (at `./barchart-scrape.js`):
1. Launches headless Chromium with Playwright
2. Visits each of the 4 Barchart URLs (pre/post × advances/declines)
3. Listens for the `/proxies/core-api/v1/quotes/get` JSON response triggered by page load
4. Parses the JSON `data` array → ticker objects with `symbol, preMarketLastPrice, preMarketPercentChange, preMarketVolume` (or `postMarket*` equivalents)
5. Filters to `abs(ChgPct) >= 4.0 AND Volume >= 100_000`
6. Dedupes by `(Symbol, Session, Direction)` triple — keeps row with largest `|ChgPct|`
7. Writes:
   - `barchart-{session}-{direction}.json` — raw API responses (1 per source)
   - `candidates.csv` — final filtered + deduped list with BOM for Excel

**Verified 2026-05-13:** 84 unique candidates returned (23+34+21+6 from pre-adv/pre-dec/post-adv/post-dec), byte-for-byte matching the Firecrawl-based count.

**Speed/cost:** ~7 seconds total, 0 Firecrawl credits, no parsing of bidi-mark-wrapped markdown.

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

**Efficient delegation pattern:** if there are >25 candidates, delegate the catalyst hunt to a `general-purpose` Agent. Pass the full candidate list and ask the agent to return a structured markdown table with columns `Ticker | Type | 繁體中文 catalyst | EPS surprise | Rev surprise | EPS YoY | Rev YoY` (Type ∈ {earnings, analyst, guidance, contract, M&A, FDA, news, momentum, macro}). The agent parallelizes WebSearches internally, which keeps the main context lean.

For each candidate (parallelize in batches of ~5 in your own context, or delegate to the agent above), run all three in parallel:

1. **Finviz news block**
   ```powershell
   firecrawl.cmd scrape "https://finviz.com/quote.ashx?t=<TICKER>" --only-main-content --wait-for 3000
   ```
   Look for the news table + the fundamentals snapshot (EPS, Sales, Inst Own%, Short Float, etc.).

2. **WebSearch** the ticker:
   - If earnings season: `<TICKER> earnings beat surprise revenue`
   - Otherwise: `<TICKER> news today why stock up/down`

3. **X / Twitter cashtag**:
   ```powershell
   firecrawl.cmd search "$<TICKER> earnings OR news" --limit 5
   ```

Synthesize a **single 繁體中文 sentence** explaining why each stock moved, e.g.:
- 「Q3 財報每股盈餘 $0.82 超預期 42%，營收 +38% YoY，盤後 +12%。」
- 「FDA 完整核准糖尿病新藥 Tirzepatide，分析師調高目標價至 $XXX。」
- 「Q2 營收較預期短少 9%，下修 FY 指引，盤後 -18%。」

Capture in working memory per ticker: `catalyst_zh, eps_surprise_pct, rev_surprise_pct, annual_sales, inst_own_pct, short_float, days_to_cover, pt_raises_30d`.

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

### Per-stock template (use this verbatim)

```markdown
## 🟢 SIP #N — <TICKER>  (Price <$XX.XX> / <+/-X.XX%> / Vol <Y.YM> / <session>)

**催化劑：** <one-sentence 繁體中文 explanation, specific with $ figures + names>

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
```
+1366.67% / +130.37%
--------------------
+200.00% / +84.61%
+186.67% / +70.10%
+57.78% / +51.73%
```

**進場建議：**
- 標準進場：開盤市價單，2.5% 停損
- 若為強催化劑 (財報大超預期 + 上修指引)：升級 5% 停損
- 後追蹤停利：$1 → $0.40 → $0.20 三階段

**SIP 判斷：** <one paragraph 繁體中文 explaining why this is today's best long — neglect signals, growth scale, catalyst quality, scale of $ figures (10M→200M ✓ vs 1¢→4¢ ✗), and what to watch for in the first 15 min>
```

### Per-short template
```markdown
## 🔴 SHORT #N — <TICKER>  (-X.XX% / Vol Y.YM)

**催化劑：** <one-sentence 繁體中文 explanation of the miss>

**EPS YoY：** -XX.X%　　**Revenue YoY：** -XX.X%  (latest reported quarter)
**MAGNA53 反向：** M(衰退)✓ G(下殺)✓ ...

**Forward YoY (TradingView FQ):** *(if available, same strict format)*

**做空判斷：** <one paragraph 繁體中文 — why this is shortable today, key risk level, opening tactic>
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

### 8.1 Write `news_detail.json` (per-symbol detail with REAL news time)

**File path:** `./news_detail.json`

**Schema (canonical):**
```json
{
  "MU": {
    "detail": "Q3 FY26 EPS $12.20 +682%、營收 $23.86B +196%、HBM 已售罄至 fiscal 2026 年底。\n\nManagement 在電話會議上提到 ...\n\n分析師反應：Citi 升 PT 至 $X，Morgan Stanley overweight。",
    "publishedAt": "2026-05-13T16:05:00-04:00",
    "publishedTimezone": "ET"
  },
  "PSIX": {
    "detail": "Q1 2026 營收 $128.6M 大miss 預期 $160.8M (-20%) ...",
    "publishedAt": "2026-05-13T07:00:00-04:00",
    "publishedTimezone": "ET"
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

**`detail` content rules:**
- Multi-paragraph 繁體中文 markdown, paragraphs separated by `\n\n` (single `\n` becomes `<br>` in the UI)
- Cover (in order): the headline catalyst, key numbers vs consensus, management commentary, analyst reaction, what to watch next
- Keep total length ~150-400 chars (3-6 short paragraphs) — readable on a stock detail card

**`publishedAt` rules:** see NEWS_TIME_SPEC.md §3-§4. Always include the TZ offset.

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

### 8.7 Phase 11 — auto-publish to GitHub Pages (REQUIRED for hosted dashboard)

This repo is wired with `.github/workflows/pages.yml`. Every push that touches `dashboard/**` triggers an auto-deploy to **https://chi2tseng.github.io/stocks-in-play/** within ~30 seconds.

**Run this at the very end of every `/SIPs` scan:**

```bash
git add dashboard/data/<DATE>.json dashboard/data.json dashboard/dates.json dashboard/index.html \
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
