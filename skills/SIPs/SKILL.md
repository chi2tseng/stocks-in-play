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
| 2. Catalyst hunt | ≤3 `general-purpose` Agents on **`model: "haiku"`** (§ 0.5) doing parallel WebSearches on **all** candidates | ~5 min | $0 | inline markdown table → updates `catalysts` dict in `build_report.py` |
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

**Total runtime:** ~5-10 min including news-detail curation. **Total cost:** $0.

**Key files in repo root (working directory):**
- `barchart-scrape.js` — Playwright Barchart scraper (XHR intercept on `/proxies/core-api/v1/quotes/get`)
- `tv-scrape.js` — Playwright TradingView FQ scraper (handles NASDAQ→NYSE→AMEX auto-detect)
- **`finviz-shorts.js`** — Playwright Finviz quote-page scraper (concurrency 2 + jitter to avoid Cloudflare). Reads tickers from `candidates.csv` and writes `shorts.json` with shortFloat / shortRatio / marketCap_M / floatShares_M / perf1M / perf3M / perf6M / perfYTD / perf12M per ticker. Powers the **N (Neglect)** + **5 (DTC)** MAGNA bits and the Short Squeeze page.
- `parse_tv.py` — extracts Reported + Estimate raw figures + YoY block from TradingView markdown
- `build_report.py` — merges candidates.csv + tv-summary.json + catalysts dict → final-candidates.csv
- `gen_tables.py` — produces 3 sorted markdown views (|%Chg| / Session / Price)
- **`fetch_candles.py`** — Yahoo Finance daily-bar scraper. Pulls last ~130 trading days (~6 months) for every ticker in today's candidates + claude/codex/gemini picks + saved studies. Parallel (8 workers), ~5-10s for 50-100 tickers. Output: `dashboard/candles.json` (~150-200KB) consumed by the stock-detail page's 股價走勢 TradingView-style chart.
- **`build_dashboard.py`** — assembles `dashboard/data/<DATE>.json` + writes the static SPA at `dashboard/index.html` (revolut design system, "Stocks In Play" branding). Merges `shorts.json` + `claude_picks.json` if present.
- **`news_detail.json`** — per-symbol detail + `publishedAt` (real news publication time). Optional input; spec at `NEWS_TIME_SPEC.md`.
- **`claude_picks.json`** — `{ "picks": [ {"symbol", "rank", "intent": "long"|"short", "rationale", "neglected"?: bool} ] }`. Drives the **default "Claude 精選"** subtab on Today's SIPs. **Direction-match rule:** longs must be gap-up, shorts must be gap-down — mismatches are silently filtered out by the dashboard. Symbols not in today's candidates also drop.
- **`NEWS_TIME_SPEC.md`** — contract for how to source + format real news timestamps. Read it BEFORE writing `news_detail.json` (see § 8 below for the integration).

**Dashboard URL:** http://127.0.0.1:5510/ (served by the `sips-dashboard` preview server, started by `mcp__Claude_Preview__preview_start` with name `sips-dashboard` and `port: 5510`). The server is always running once started; the dashboard auto-refreshes when `data/<DATE>.json` is rewritten.

---

## § 0.5 Model routing & token budget (READ FIRST — this is a COST rule, not a quality rule)

**Principle: cheap models GATHER, the smartest model JUDGES.** All final analysis — MiLan 深度拆解, Tier ratings, claude_picks rankings, the 繁中 brief — is composed by the MAIN model (Fable / Opus max). Everything mechanical (web searches, scraping, fact collection, table assembly) is delegated to cheap subagents. A previous run burned ~400k subagent tokens at main-model pricing because Agent calls inherited the parent model — never again.

**Hard routing table (when running under Claude Code — Agent tool `model` param):**

| Work | Who | Why |
|---|---|---|
| Phase 2.0 macro/policy pre-scan | 1 Agent, `model: "haiku"` | 5 WebSearches + cluster-map assembly is mechanical. Returns ≤600-token cluster map. |
| Phase 2.1 per-ticker catalyst hunt | ≤3 Agents, `model: "haiku"`, ~25 tickers each | One-line catalyst per ticker = summarization, not judgment. |
| Phase 8 fact-sheet gathering (top-10 deep-dive research) | 1-2 Agents, `model: "sonnet"` | 8-K parsing + segment/guidance numbers need care but not genius. Facts only, no verdicts. |
| MAGNA53 classification, day_resets judgment | MAIN model | Judgment calls on the already-compact table. |
| § 7.0 MiLan 深度拆解 + Tier ratings | **MAIN model — NEVER delegate** | This is the product. |
| claude_picks.json rankings + rationales | **MAIN model — NEVER delegate** | This is the product. |
| 繁中 brief composition | **MAIN model** | Final deliverable. |

**Subagent output caps (enforce in every Agent prompt):**
- Catalyst-hunt agents: return ONLY the markdown table, one line per ticker, ≤40 字 per catalyst, NO sources section, NO preamble. Sources are only needed for the top-10 (gathered later by the fact-sheet agents).
- Fact-sheet agents: return per-ticker structured fact sheets (see § 8.0), ≤500 tokens per ticker, raw numbers + URLs only — explicitly instruct "NO analysis, NO conclusions, NO tier opinions; those belong to the caller."
- Pre-scan agent: cluster map only, ≤600 tokens total.

**Main-context hygiene (applies to the MAIN model itself):**
- Run `py parse_tv.py`, `py fetch_earnings_dates.py`, `py fetch_candles.py`, `node finviz-shorts.js` with output suppressed or tail-ed (`| tail -3`). The full 170-row parse table is ~4k tokens of noise — query `tv-summary.json` selectively for candidate tickers via a small `py -c` filter instead.
- Never `cat`/Read whole JSON artifacts (`tv-summary.json`, `shorts.json`, `candles.json`, day files) into context. Use `py -c` one-liners that print only the tickers/fields needed.
- Don't re-read files you just wrote. Don't echo full file contents to "verify" — spot-check 1-2 fields.
- WebSearch/WebFetch in the main context is allowed ONLY during final analysis when a specific fact is missing from the fact sheets (target: ≤5 such calls per run).

**Cost math (why this matters):** gathering ≈ 400-500k tokens/run. At main-model pricing that dwarfs everything else; on haiku it's ~1/10th the cost, on sonnet ~1/3. Final analysis is ~30-60k tokens and stays premium. Net effect: same-quality picks at roughly 70-85% lower spend.

**When running under Gemini/Codex CLI** (`/SIPs-gemini-full`, `/SIPs-codex-full`): the Agent-model params don't exist there — keep the same structure (delegate gathering to whatever cheap sub-mechanism is available, or just do it inline) and keep the output caps + main-context hygiene rules, which save tokens on any runtime.

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

**Delegate it (§ 0.5 routing): spawn ONE Agent with `model: "haiku"`** whose prompt contains today's ISO date + the source table below + the candidate ticker list, and instructs it to run the searches in parallel and return ONLY the cluster map (≤600 tokens, format as in the example below). Do NOT run these 5 WebSearches in the main context — that's ~10k tokens of raw search results the main model doesn't need to see.

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

### 2.1 — Per-ticker catalyst hunt

**Efficient delegation pattern (§ 0.5 routing — MANDATORY, not optional):** delegate the per-ticker hunt to **at most 3 Agents with `model: "haiku"`**, ~25 tickers each (don't spawn 6+ agents — each carries prompt overhead). **Always pass the Phase 2.0 cluster map in each agent's prompt** so it can short-circuit by-cluster instead of researching each ticker from scratch. Ask each agent to return a structured markdown table with columns `Ticker | Type | Cluster | 繁體中文 catalyst` (Type ∈ {earnings, analyst, guidance, contract, M&A, FDA, news, momentum, macro, **policy**}). **Output caps in the prompt: table ONLY, ≤40 字 per catalyst, NO sources list, NO preamble, NO per-ticker EPS/Rev columns** (those come from tv-summary.json later — don't make a haiku search for numbers the pipeline already scrapes). Main model reads back 3 compact tables (~2k tokens total) instead of doing 60+ searches itself.

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

### 7.0 — 深度催化劑拆解架構 (MiLan_Trades 風格) — apply to top 3-5 SIPs + top 2-3 shorts

**Why this exists**: most catalyst write-ups stop at "Q1 beat by X%, stock +12%" — that's not analysis, that's restating the headline. The reference standard is MiLan_Trades's AVAV teardown (Tier 3/5, "沒有想像中那麼糟"): the $641M / +133% YoY headline is peeled apart into **44% from M&A roll-up vs. only ~31% organic**, the doubled adj-EBITDA against **+79% share count dilution** that kept adj-EPS flat, the **$240M goodwill impairment** that turned GAAP into a $(265)M loss, the segment split (legacy autonomous-systems carried the entire beat at 28% margin while the $4.1B BlueHalo acquisition delivered <1% margin), the FY27 guidance that **directly contradicts** the bullish backlog story (revenue +10%, adj-EPS 20% below consensus, FCF negative), AND the open **SCAR-disclosure securities class action**. End verdict: "stabilization, not triumph. The pop from 52-week lows is a backlog-supported relief rally, not proof of underlying earnings improvement."

That's the depth bar. Restate the headline = lazy. Peel it apart layer by layer = the user's signal.

**Apply this depth to**: every top 3-5 SIPs + every top 2-3 shorts (i.e., everything that goes into `news_detail.json`). The remaining ~70 candidates get the standard 2-3 sentence catalyst summary in the full-list table — that's fine, depth doesn't scale to 80 names.

**Required: 5-section structure. Each section must have specific $ figures, names, or %. No vague descriptors ("strong demand", "healthy guidance") — replace with the number.**

#### Section 1 — Headline 拆解 (哪些是真的、哪些被灌水)

For **earnings** movers:
- **Revenue organic vs. M&A**: `公布 Q[N] revenue $X.XB (+Y% YoY) — 其中 $Z (約 W%) 來自 [併入的 ACQ_NAME 業務 / 新通路上線 / 一次性訂單]，剝掉之後 organic 成長實際 ~V%`
- **EPS 與股數稀釋鴻溝**: `Adjusted EPS $X vs 去年 $Y — 但 share count 因 [併購對價 / SPO / SBC overhang] +Z%，每股經濟效益實際停滯/下降`
- **GAAP vs Adjusted**: `GAAP 全年 [虧損 / 微利] $(X)M / $(Y)/股，主因是 $Z 的 [商譽減損 / restatement / 庫存沖銷 / 訴訟和解]`

For **non-earnings** catalysts (policy / contract / FDA / M&A / analyst):
- **Headline 與 TAM 拆解**: `[$X 政府補助 / $Y 合約 / 加速核准] — 其中對 <TICKER> 直接可分配 ~$Z (W% of TAM)，剩下將分給 [競爭者 X/Y / 同族群 / 未來輪次 / 不確定]`
- **時間軸 (anticipation vs. fulfillment)**: `公告日 → 簽約日 → 收入認列日 → 完工日。今日 +X% 是 [尚未簽約的 anticipation / 已簽 deal 的 fulfillment / 收入仍在 N 季外]`
- **稀釋條款**: 政府補助常伴 warrant / minority stake / preferred shares / SBA-style dilution — 必須點出

#### Section 2 — 業務品質 (segment by segment)

`整個超預期幾乎集中在 [優質部門 A]（營收 $X、利潤率 Y%、YoY +Z%）；而 [併購進來的部門 B / 衰退中的部門 C] 在 $W 營收上只擠出 $V EBITDA、利潤率 U%（或實際虧損 $T）。`

然後一句點題（pick one）:
- **如果優質部門撐起亮點**: 「**那正是當初要拿來合理化 [收購價/估值/政策] 的部門，而它根本還沒開始賺錢養活自己。**」(AVAV pattern)
- **如果新部門加速**: 「**多頭故事的核心引擎正在加速、毛利率持續擴張，符合 thesis。**」
- **如果舊部門衰退**: 「**舊業務正在被取代，未來幾季的 organic 成長將完全靠 [新業務] 撐住。**」

#### Section 3 — 前瞻訊號 vs 公司指引 (兩者矛盾要點出)

- **前瞻需求 (Real demand 訊號)**:
  - 訂單 / orders intake $X (+Y% YoY)
  - book-to-bill ratio (>1 = 訂單跑贏出貨)
  - funded backlog $W (+Z% YoY)
  - 大客戶續約 / 新地理市場 / 新產品線 specifics
- **公司指引 (Management's own view)**:
  - FY[N+1] revenue guide +X% (vs consensus +Y%)
  - adjusted EPS $A (vs consensus $B, [+/-]C%)
  - EBITDA, FCF 預期、上下半年分配
- **點出矛盾或共振**:
  - 強訂單 + 弱指引 = 「**管理層自己沒那麼樂觀**，通常代表毛利率/cost mix 壓力、或 CFO 在 sandbag」
  - 強訂單 + 強指引 = 「**管理層加碼下注**，多頭續勢 thesis 成立」
  - 弱訂單 + 強指引 = 「**指引明顯偏激進**，FY 末 likely 需要下修」

#### Section 4 — 風險清單 (必列、即使表面利多)

至少 3 項，every 項要具體：
- **訴訟**: open securities fraud class action / SEC investigation / FTC review / IP infringement / 客戶仲裁
- **重編 / 減損**: restatement of [period N-X] / goodwill impairment $X / inventory write-down / DTA reversal
- **稀釋**: 已宣告但未發行的 ATM $X / convertible notes due [DATE] / unvested SBC $Y / warrant overhang
- **客戶集中**: top 3 客戶占 X% revenue / 大政府合約 [DATE] 到期 / 單一產品線占 Y%
- **規範改變**: 出口管制 / FDA black-box / DOJ antitrust review / 稅務裁定
- **競爭**: 新進入者 [NAME] / 大廠 [NAME] 降價 X% / 替代技術 ETA [DATE]

#### Section 5 — 誠實判定 (point of the whole exercise)

一句話 verdict + Tier 評等。模板:

> **這是 [止穩 / 解套反彈 / 趨勢轉折確認 / 多頭續勢 / pump-and-dump]，不是 [凱旋 / 拐點 / fundamental shift / 真實趨勢確認]。** 核心業務 [健康/受傷]，但 reported 成長靠 [併購/政策/一次性] 撐起，而 [稀釋/減損/訴訟/競爭] 把每股經濟效益 [吃掉/中和/補強]。今日這波 [+X%] 從 [近 52 週低 / 整理區間 / earnings gap] 是靠 [強勁訂單簿 / 政府訂單 / 沒有想像中那麼糟 / short squeeze] 撐起的 [解套反彈 / 趨勢確認 / 突破 / 多日延續]，並不是 [底層獲利能力真的改善 / underlying demand thesis 確認] 的證明。**Tier X/5 等級的財報/事件。**

**Tier scale (內部命名)**:
- **Tier 5/5** = fundamental shift confirmed by all 4 lenses — organic rev + segment quality + bullish guide + clean balance sheet. 多日延續期望值高。
- **Tier 4/5** = 強催化但有一個顯著瑕疵 (e.g., 強 organic + 強 segment 但 guide 保守, or 強 EPS 但 share count 稀釋大)
- **Tier 3/5** = 「沒有想像中那麼糟」型 — 部分業務健康但結構性問題未解。**AVAV 範例的等級。** 進場可以、但別 oversize、別預期多日延續。
- **Tier 2/5** = relief rally / dead-cat / 純空頭回補 — fade 機會 > 跟單機會
- **Tier 1/5** = pump-and-dump / 純技術面 / micro-float 拉抬 — 不碰，或反向找做空

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

### 深度催化劑拆解

**1. Headline 拆解 — 哪些是真的、哪些被灌水：**
- <organic vs M&A revenue split with specific $ figures>
- <share count dilution % + impact on per-share economics>
- <GAAP vs adjusted gap with the specific item causing it>

**2. 業務品質 — segment by segment：**
- [優質部門名] $X 營收 / Y% margin — <carried the beat>
- [問題部門名] $X 營收 / Y% margin — <still doesn't earn its keep>
- 點題: <one sentence naming the structural quality pattern>

**3. 前瞻訊號 vs 公司指引：**
- Real demand: 訂單 $X / book-to-bill Y / backlog +Z% to $W
- Management guide: FY[N+1] rev +X%, adj-EPS $A (vs consensus $B)
- 矛盾/共振: <one sentence naming which it is>

**4. 風險清單：**
- <Lawsuit / SEC inquiry with specifics>
- <Dilution overhang $ amount>
- <Customer concentration / regulatory / competition with specifics>

**5. 誠實判定:**
這是 [pattern]，不是 [pattern]。<one paragraph follow-through>. **Tier X/5 等級的[財報/事件]**。

---

**進場建議：**
- 標準進場：開盤市價單，2.5% 停損
- 若為 Tier 4-5 強催化：升級 5% 停損
- 後追蹤停利：$1 → $0.40 → $0.20 三階段
```

### 7.2 — Per-short template

```markdown
## 🔴 SHORT #N — <TICKER>  (-X.XX% / Vol Y.YM)

**一句話催化劑：** <one-sentence 繁體中文 explanation of the miss>

**EPS YoY：** -XX.X%　　**Revenue YoY：** -XX.X%  (latest reported quarter)
**MAGNA53 反向：** M(衰退)✓ G(下殺)✓ ...

**Forward YoY (TradingView FQ):** *(if available, same strict format)*

---

### 深度催化劑拆解 (same 5-section structure as SIP)

**1. Headline 拆解 — 為什麼這個 miss 是 real，不是 noise：**
**2. 業務品質 — 哪個 segment 流血：**
**3. 前瞻訊號 vs 公司指引 — 是否兩者都在惡化：**
**4. 風險清單 (反向 — short 的 risk = 多頭翻身要件)：**
**5. 誠實判定:**
這是 [真實 demand destruction / 一次性失誤 / 結構性衰退 / cyclical bottom]。<one paragraph>. **Tier X/5 等級的做空機會**。

---

**做空進場建議：**
- 標準進場：開盤市價單，3% 停損（空頭單較寬以避開 short-cover 噴）
- key risk levels: [pre-market 高點] / [50-day MA] / [analyst PT]
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

**`detail` content rules — apply the § 7.0 深度催化劑拆解 framework here:**
- Multi-paragraph 繁體中文 markdown, paragraphs separated by `\n\n` (single `\n` becomes `<br>` in the UI)
- **Required structure (5 paragraphs, mirrors § 7.0 sections 1-5):**
  1. **Headline 拆解** — organic vs M&A revenue split with specific $ figures, share count dilution %, GAAP vs adjusted gap with the specific cause
  2. **業務品質** — segment-by-segment quality check with specific margins, naming which segment carried the beat
  3. **前瞻訊號 vs 公司指引** — orders / backlog / book-to-bill vs FY guidance vs consensus, point out matrix or contradiction
  4. **風險清單** — at least 3 specific items (open lawsuits / dilution overhang / customer concentration / regulatory / restatement risk)
  5. **誠實判定** — "這是 X 不是 Y" one-paragraph verdict + **Tier X/5 等級的[財報/事件]**
- **Length: ~600-1200 字 (5 paragraphs, each 80-200 字)** — this is the user's "MiLan_Trades depth" bar. The old 150-400 char limit was too thin for proper analysis. The stock detail card scrolls; readability is fine.
- **Key numbers in `**bold**`** so they pop on the card (e.g., `**Q3 revenue $641M +133% YoY**`, `**44%(約 $282M)來自併購**`)
- Each claim must carry a specific $ / % / name. Vague phrases like "強勁需求", "管理層樂觀" must be replaced with the underlying number ("訂單 $2.7B / book-to-bill 1.4")

**Reference — AVAV teardown (the user's gold standard)**:
```
公布 Q4 revenue **$641.6M (+133% YoY)** — 但其中約 **$282M (約 44%)** 直接來自併進來的 BlueHalo 與 Empirical Systems 業務，不是本業真實需求。剝掉這兩塊，當季 organic 成長僅 ~31%、全年僅 ~26%。Adjusted EPS **$3.31 vs 去年 $3.28** 幾乎沒動 — 因股票對價併購 + 一次現金增資讓 share count **+79%**，每股經濟效益實際停滯。GAAP 全年虧損 **$(265)M / $(5.40)/股**，主因是 SCAR 太空計畫崩盤帶來的 **$240.7M 商譽減損**，其中含 $89.4M 前期數字 restatement。

業務品質參差不齊：整個超預期幾乎全在舊有 **Autonomous Systems** 招牌業務 ($492M 營收 / 28% margin)；而花 **$4.1B 併進的 BlueHalo Space/Cyber/Directed Energy 部門**在 $149M 營收上只擠出 $1.4M EBITDA、利潤率不到 1%。**那正是當初要拿來合理化收購價的部門，而在 SCAR 之後它根本還沒開始賺錢養活自己。**

前瞻需求真實且 organic：**訂單 $2.7B、book-to-bill 1.4、funded backlog +65% 到 $1.2B**，加上 Switchblade 400/LASSO 得標、Titan 反無人機訂單翻倍。但管理層 **FY27 指引直接打臉**：revenue 只 guide +10%、adj-EPS **$3.02-3.34 (比 consensus 低 ~20%)**、EBITDA 低 ~12%、FCF 全年負且重壓在下半年。

風險：**SCAR 揭露問題的 securities fraud 集體訴訟仍在進行**；股票對價併購讓未來幾年 SBC + dilution overhang 持續；新買的太空部門在 $240M 減損後仍不賺錢；客戶高度集中於美國國防部單一通路。

**這是一次自己搞砸後的「止穩」，不是凱旋。** 核心無人機業務健康，但公布出來的成長是靠併購撐起的、每股經濟效益因稀釋而停滯、被併進來的太空部門在 $240M 減損後幾乎不賺錢，且有 securities class action 懸在頭上。這波從接近 52 週低的彈升，是靠強勁訂單簿撐起的**解套式反彈**，並不是底層獲利能力真的改善的證明。**Tier 3/5 等級的財報。**
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

Powers the **股價走勢** TradingView-style chart on the stock-detail page. Pulls last ~130 trading days (~6 months) of OHLCV bars from Yahoo Finance for the **union of** today's candidates + claude/codex/gemini picks + every saved study.

**Run AFTER Phase 9 (claude_picks.json written) and AFTER studies refresh (Phase 10a-c), but BEFORE Phase 10 (build_dashboard.py)** so:
1. `fetch_candles.py` reads the latest `dashboard/data/<DATE>.json`, picks files, and `studies.json` to know which symbols to fetch.
2. `build_dashboard.py` runs after — it doesn't need to know about candles (dashboard loads `candles.json` directly via fetch).

**Command:**
```powershell
py fetch_candles.py
```

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
