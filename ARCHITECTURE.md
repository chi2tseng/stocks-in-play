# SIPs Dashboard — Architecture Deep-Dive

> **Companion to** `HANDOFF.md` (which covers WHAT to do next).
> This doc covers HOW the existing system works — every major feature explained from data flow to render path.
>
> Read both before continuing work in a new Claude Code session.

---

## Table of Contents

1. [Data Pipeline (10,000ft View)](#1-data-pipeline-10000ft-view)
2. [Backend Layer 1 — Scrapers](#2-backend-layer-1--scrapers)
   - 2.1 Barchart (gappers) + Session-Date rule
   - 2.2 TradingView (FQ quarterly grid)
   - 2.3 Finviz (shorts + perf)
   - 2.4 Yahoo Finance (candle bars)
3. [Backend Layer 2 — build_dashboard.py](#3-backend-layer-2--build_dashboardpy)
   - 3.1 Per-Target-Date Routing (the big rule)
   - 3.2 Stocks Dict Construction
   - 3.3 Picks Filtering
   - 3.4 Multi-File Write Logic
   - 3.5 INDEX_HTML Sync Pattern
4. [Three-Agent Curation System](#4-three-agent-curation-system)
5. [Frontend — Dashboard SPA](#5-frontend--dashboard-spa)
   - 5.1 Routing
   - 5.2 STATE Shape
   - 5.3 Theme & Design Tokens (the trap)
6. [Candle Chart Subsystem](#6-candle-chart-subsystem)
   - 6.1 Layout (SVG geometry)
   - 6.2 State Machine
   - 6.3 Interactions (5 modes)
   - 6.4 News Markers + Popup
7. [Filter Popup Pattern (3 popups, shared base)](#7-filter-popup-pattern-3-popups-shared-base)
8. [Today's SIPs Page](#8-todays-sips-page)
9. [My Studies System](#9-my-studies-system)
10. [Search Box (Studies)](#10-search-box-studies)
11. [Calendar Widgets](#11-calendar-widgets)
12. [Theme System (CSS Vars)](#12-theme-system-css-vars)
13. [MAGNA53 Classification](#13-magna53-classification)
14. [Catalyst Types System](#14-catalyst-types-system)
15. [Sidecar (Local Edit Mode)](#15-sidecar-local-edit-mode)
16. [Day Labels (day1/2/3) + Reset Logic](#16-day-labels-day123--reset-logic)
17. [News Curation Workflow](#17-news-curation-workflow)
18. [Auto-Push + Git Workflow](#18-auto-push--git-workflow)
19. [Common Anti-Patterns to Avoid](#19-common-anti-patterns-to-avoid)

---

## 1. Data Pipeline (10,000ft View)

```
                          ┌──────────────────┐
                          │   /SIPs slash    │
                          │     command      │
                          └────────┬─────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
        ▼                          ▼                          ▼
┌──────────────┐          ┌──────────────┐         ┌──────────────────┐
│  Barchart    │          │ TradingView  │         │  Finviz quote    │
│  Playwright  │          │   FQ grid    │         │     pages        │
│  + XHR       │          │ + parse_tv   │         │  + parse_finviz  │
│  intercept   │          │              │         │                  │
└──────┬───────┘          └──────┬───────┘         └────────┬─────────┘
       │                         │                          │
       ▼                         ▼                          ▼
 candidates.csv          tv-summary.json              shorts.json
 (+SessionDate)              (per sym)                (per sym)
       │                         │                          │
       └────────────┬────────────┴──────────────┬───────────┘
                    │                           │
                    ▼                           ▼
        ┌─────────────────────────────────────────────┐
        │           fetch_candles.py                  │
        │           (Yahoo, 8 workers)                │
        └────────────────────┬────────────────────────┘
                             │
                             ▼
                  dashboard/candles.json (1yr OHLCV per sym)
                             │
       ┌─────────────────────┴─────────────────────┐
       │                                           │
       ▼                                           ▼
news_detail.json                       claude_picks.json
day_resets.json                        codex_picks.json
catalysts_today.json                   gemini_picks.json
       │                                           │
       └────────────────┬──────────────────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │  build_dashboard.py   │   ← merges everything
            │  per-target-date      │
            │  routing logic        │
            └───────────┬───────────┘
                        │
                        ▼
        dashboard/data/<DATE>.json  (one per target date)
        dashboard/data.json         (mirror of latest)
        dashboard/dates.json        (date picker index)
        dashboard/index.html        (rebuilt from INDEX_HTML block)
                        │
                        ▼
                  git push (auto)
                        │
                        ▼
               GitHub Pages serves
```

**Output schema** (`dashboard/data/<DATE>.json`):
```json
{
  "date": "2026-05-19",
  "scanTime": "15:08",
  "scanTimestamp": "2026-05-19T15:08",
  "stocks": {
    "SYM": {
      "symbol": "SYM", "name": "...", "type": "earnings|M&A|FDA|contract|news|momentum|...",
      "catalyst": "繁中 catalyst summary", "newsDetail": "**markdown** body",
      "publishedAt": "ISO 8601", "publishedTimezone": "ET",
      "sources": [{ "label": "...", "url": "..." }],
      "sessions": [
        { "session": "pre|post", "direction": "up|down",
          "chgPct": 12.5, "last": 75.20, "volume": 1234567,
          "sessionDate": "2026-05-18", "targetDate": "2026-05-19",
          "name": "..." }
      ],
      "primarySession": "pre|post", "primaryDirection": "up|down",
      "last": 75.20, "chgPct": 12.5, "volume": 1234567,
      "tv": { "latestEPS": 0.57, "consensusEPS": 0.43, "surpriseEPS_pct": 33.0,
              "latestRev_M": 534, "consensusRev_M": 510, "surpriseRev_pct": 4.7,
              "epsYoY_pct": ..., "yrYrRev_pct": ...,
              "epsEst_next4": [...], "revEst_next4": [...],
              "yoyBlock": "multi-line string",
              "chart": { "quarters": [...], "eps_reported": [...], "eps_estimate": [...],
                         "rev_reported_M": [...], "rev_estimate_M": [...],
                         "latest_idx": 7 } },
      "shortFloat": 12.5, "shortRatio": 4.3, "marketCap_M": 1234,
      "floatShares_M": 89, "perf1M": -8.2, "perf3M": 14.5, "perf6M": 32.1,
      "perfYTD": 22.0, "perf12M": 88.5,
      "prevOhlcv": { "date": "2026-05-15", "open": 70.1, "high": 72.5,
                     "low": 69.8, "close": 71.5, "prev_close": 70.4, "volume": 5000000 }
    }
  },
  "rawGappers": [ ... ALL Barchart rows before ±4%/100k filter ... ],
  "rawGappersFilter": { "chgMin": 4.0, "volMin": 100000 },
  "claudePicks": [ { "symbol": "X", "rank": 1, "intent": "long", "rationale": "...", "neglected": false } ],
  "codexPicks":  [ ... ],
  "geminiPicks": [ ... ],
  "dayResets":   { "SYM": "reason for reset" },
  "scanx": {
    "gapUpEarnings":  [ { "symbol", "chg", "catalyst", "type" } ],
    "gapUpOther":     [ ... ],
    "gapDownEarnings": [ ... ],
    "gapDownOther":   [ ... ]
  }
}
```

---

## 2. Backend Layer 1 — Scrapers

### 2.1 Barchart (barchart-scrape.js) + Session-Date rule

**Why Playwright + XHR intercept**: Barchart renders the gapper table inside `<bc-data-grid>` Shadow DOM. Text scraping (Firecrawl markdown / `innerText`) misses the data. The clean approach is to listen for the `/proxies/core-api/v1/quotes/get` JSON response that the page fires on load.

**4 endpoints** (auto/both default scrapes all of them):
```
pre-market-trading/percent-change/advances   → pre + up
pre-market-trading/percent-change/declines   → pre + down
post-market-trading/percent-change/advances  → post + up
post-market-trading/percent-change/declines  → post + down
```

**Filters**: `abs(ChgPct) >= 4.0 AND Volume >= 100_000`

**Dedup**: by `(Symbol, Session, Direction)` tuple, keep largest `|ChgPct|`.

**Output: candidates.csv**
```csv
Symbol,Last,ChgPct,Volume,Session,SessionDate,Direction,Name
NBIS,75.20,+8.4,1234567,pre,2026-05-19,up,Nebius Group
SLE,9.35,+5.2,890123,post,2026-05-18,up,Super League Enterprise
```

**Session-Date rule** (NEW, commit 556adfe — the big rule):

Computed at scrape time from ET clock:

```javascript
function nowInET() {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: 'numeric', minute: 'numeric', hour12: false,
    weekday: 'short',
  }).formatToParts(new Date());
  const get = key => parts.find(p => p.type === key)?.value;
  let hour = parseInt(get('hour'), 10);
  if (hour === 24) hour = 0;
  return { date: `${y}-${mm}-${dd}`, hour, minute, totalMinutes };
}

function computeSessionDates(et) {
  const isoToday = et.date;
  const isoYest = subtractOneDay(isoToday);
  return {
    pre:  (et.totalMinutes >= 4 * 60) ? isoToday : isoYest,
    post: (et.totalMinutes >= 16 * 60) ? isoToday : isoYest,
  };
}
```

**Boot log** prints what dates got assigned:
```
[barchart-scrape] ET Tue 2026-05-19 03:15 · session-dates: pre=2026-05-18  post=2026-05-18  arg=auto
```

**Time-window examples**:
| ET clock | pre tag | post tag |
|---|---|---|
| 02:44 (overnight) | yest | yest |
| 05:00 (pre-mkt in progress) | today | yest |
| 11:00 (regular hours) | today | yest |
| 15:30 (regular hours) | today | yest |
| 16:00 (post-mkt opens) | today | today |
| 20:00 (post-mkt in progress) | today | today |

**Manual override args**:
```bash
node barchart-scrape.js auto    # default: scrape both, tag by ET clock
node barchart-scrape.js both    # alias of auto
node barchart-scrape.js pre     # only pre-market endpoint
node barchart-scrape.js post    # only post-market endpoint
```

### 2.2 TradingView (tv-scrape.js + parse_tv.py)

**Trick**: TradingView's `?earnings-period=FQ&revenues-period=FQ` URL parameter returns server-rendered quarterly tables without JS interaction. Bypass the SPA shell entirely.

```bash
node tv-scrape.js NBIS SLE AGYS   # writes <SYM>-earnings-fq.md per ticker
py parse_tv.py                    # parses *.md → tv-summary.json
```

**tv-summary.json shape** (one per symbol):
```json
{
  "Ticker": "NBIS",
  "LatestEPS": 0.57, "LatestEPSConsensus": 0.43, "LatestEPSSurprise_pct": 33.0,
  "PriorYrEPS": 0.40,
  "LatestRev_M": 534.6, "LatestRevConsensus_M": 510.0, "LatestRevSurprise_pct": 4.8,
  "PriorYrRev_M": 388.0,
  "EpsEst_Next4": [0.62, 0.71, 0.80, 0.92],
  "RevEst_Next4": [580, 620, 660, 720],
  "YoYBlock": "Q1 2026: EPS +42% YoY / Rev +37.7% YoY\n...",
  "Chart": {
    "quarters": ["Q1 2024", "Q2 2024", ..., "Q1 2026"],
    "eps_reported": [..., null], "eps_estimate": [..., null],
    "rev_reported_M": [..., null], "rev_estimate_M": [..., null],
    "latest_idx": 7
  }
}
```

**Historical-quarter rewind** (a parse_tv subtlety): TradingView always shows the LATEST quarter as `latest_idx`. For a study with a past date (e.g., AMD @ 2026-02-04 for Q4 '25), the chart needs to be rewound — see `D:\SIPs\skills\update-studies\SKILL.md` §3b for details.

### 2.3 Finviz (finviz-shorts.js)

Concurrency: 2 + jitter to dodge Cloudflare. Visits each ticker's Finviz quote page, parses the fundamentals snapshot. ~70-90s for 50 tickers.

**shorts.json shape**:
```json
{
  "NBIS": {
    "status": "ok",
    "shortFloat": 12.5, "shortRatio": 4.3, "marketCap_M": 1234,
    "floatShares_M": 89,
    "perf1M": -8.2, "perf3M": 14.5, "perf6M": 32.1,
    "perfYTD": 22.0, "perf12M": 88.5
  }
}
```

Used by:
- Dashboard's Short Squeeze page
- MAGNA `N` bit (Neglect) + `5` bit (DTC)
- Stock detail page's header pills

### 2.4 Yahoo Finance (fetch_candles.py)

Daily OHLCV bars via the free `query1.finance.yahoo.com/v8/finance/chart/<SYM>` API.

```python
def fetch_one(sym):
    end = int(time.time())
    start = end - 200 * 86400  # ~200 days back
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={start}&period2={end}&interval=1d'
    # ... parses response, returns list of bars
```

8 workers via ThreadPoolExecutor. No auth needed. Daily bars only (interval=1d) — no pre/post market data included.

**Symbol collection** (in `collect_symbols()`):
1. Today's `dashboard/data/<today>.json` stocks
2. claude/codex/gemini picks files
3. studies (`dashboard/studies/studies.json`)
→ Union, deduped, sorted

**Output**: `dashboard/candles.json` = `{SYM: [bars]}` where each bar is `{date, open, high, low, close, volume}`.

**Fetched in parallel with the rest of /SIPs**. Phase 10d.

---

## 3. Backend Layer 2 — build_dashboard.py

### 3.1 Per-Target-Date Routing (commit 8036e58, the model-changing one)

**Routing rule**:
```python
def _next_trading_day(iso):
    """Skip Sat/Sun. Note: doesn't yet handle US holidays."""
    d = datetime.date.fromisoformat(iso)
    while True:
        d += datetime.timedelta(days=1)
        if d.weekday() < 5:    # Mon..Fri
            return d.isoformat()

def _session_target_date(session, session_date):
    return session_date if session == 'pre' else _next_trading_day(session_date)
```

**Conceptual model**: each `<DATE>.json` represents the "gap view heading INTO that trading day". So:
- `pre row, X` → belongs to `X.json` (today's pre-market preparing for X's open)
- `post row, X` → belongs to `next_trading_day(X).json` (X's post-market preparing for next open)

**Result for typical Tuesday morning scan (ET 05:00)**:
- Mon `post` rows → `2026-05-19.json` (Tue file = overnight gap into Tue)
- Tue `pre` rows → `2026-05-19.json` (Tue's actual morning gap data)
- Together = the classic "overnight gap" view

**Each candidate row in cands_by_sym** carries:
```python
{
  'last': 75.20, 'chgPct': 12.5, 'volume': 1234567,
  'session': 'pre|post',
  'direction': 'up|down',
  'name': '...',
  'sessionDate': '2026-05-18',  # from CSV (commit 556adfe)
  'targetDate':  '2026-05-19',  # computed at load time
}
```

### 3.2 Stocks Dict Construction (the giant merge)

Order of merges:
1. Load `candidates.csv` → `cands_by_sym = {sym: [session_rows]}`
2. Load `tv-summary.json` → `tv = {sym: tv_block}`
3. Load `shorts.json` → `shorts_raw = {sym: shorts_block}`
4. Load `catalysts_today.json` → `catalyst = {sym: {type, catalyst, name}}`
5. Load `news_detail.json` → `news_detail_raw = {sym: {detail, publishedAt, sources, ...}}`
6. Load `prev_ohlcv.json` → `prev_ohlcv_raw = {sym: {date, OHLC, volume}}`
7. Load `day_resets.json` → `day_resets_map = {sym: reason}`

Then merge per symbol (union of all keys):
```python
for sym in all_syms:
    cands = cands_by_sym.get(sym, [])
    if not cands: continue   # skip if not in today's filter
    primary = max(cands, key=lambda c: abs(c['chgPct']))
    stocks[sym] = { 'symbol', 'name', 'type', 'catalyst', 'newsDetail',
                    'sessions', 'primarySession', 'primaryDirection',
                    'last', 'chgPct', 'volume', 'tv', 'shortFloat',
                    'shortRatio', 'marketCap_M', 'perf1M-12M',
                    'prevOhlcv', ... }
```

### 3.3 Picks Filtering

Each agent's picks file (`claude_picks.json` etc.) goes through `_clean_picks`:
```python
def _clean_picks(picks_list, propagate_neglected=False):
    out = []
    for p in picks_list:
        sym = p.get('symbol')
        if sym not in stocks: continue   # silently drop stale symbols
        out.append({
            'symbol': sym, 'rank': p.get('rank'),
            'intent': p.get('intent', 'long'),
            'rationale': p.get('rationale', ''),
            'neglected': p.get('neglected'),
        })
        if propagate_neglected and 'neglected' in p:
            stocks[sym]['neglected'] = p.get('neglected')
    return out
```

- `claude_picks_clean` propagates the `neglected` flag (Claude is canonical curator of the MAGNA `N` bit)
- `codex_picks_clean` and `gemini_picks_clean` don't propagate (other agents shouldn't override Claude's `N` judgment)

### 3.4 Multi-File Write Logic

```python
# Build target_dates from session targetDate fields
target_dates_set = set()
for sym, s in stocks.items():
    for sess in s['sessions']:
        target_dates_set.add(sess.get('targetDate') or DATE)
target_dates_set.add(DATE)   # always include scan date

def _build_data_for(td):
    """Filter stocks/sessions/scanx to those routing to td.
       Picks/dayResets/rawGappers only on scan date."""
    is_scan = (td == DATE)
    filtered_stocks = { ... only stocks with sessions routing to td ... }
    # ... build SCANX lists from filtered_stocks
    # ... include picks only if is_scan
    return data_dict

# Write each target date
for td in sorted(target_dates_set):
    new_data = _build_data_for(td)
    out_path = os.path.join(DATA_DIR, f'{td}.json')
    if td != DATE and os.path.exists(out_path):
        # Preserve existing picks/rawGappers from previous scans
        # (today's run only refreshes stocks/sessions for non-scan-date files)
        try:
            old = json.load(open(out_path, encoding='utf-8'))
            for key in ('claudePicks', 'codexPicks', 'geminiPicks', 'dayResets',
                        'rawGappers', 'rawGappersFilter', 'scanx'):
                if not new_data.get(key) and old.get(key):
                    new_data[key] = old[key]
        except Exception: pass
    if not new_data['stocks'] and td != DATE: continue   # skip empty files
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)
```

`dashboard/data.json` (the "latest" mirror) is copied from the scan-date file. `dashboard/dates.json` is regenerated by scanning `DATA_DIR` for all `<YYYY-MM-DD>.json` files.

### 3.5 INDEX_HTML Sync Pattern

`build_dashboard.py` embeds the entire dashboard SPA as a Python triple-quoted string:
```python
INDEX_HTML = r'''<!DOCTYPE html>
<html lang="zh-Hant">
... HUGE block (~400KB) ...
</html>'''
```

**Why dual file?** `dashboard/index.html` is the actual file Pages serves. The `INDEX_HTML` block in `build_dashboard.py` is the SOURCE OF TRUTH that gets re-emitted each build.

**Sync direction**:
- `_sync_template.py` reads `dashboard/index.html` → writes back into the `INDEX_HTML = r'''...'''` block
- `build_dashboard.py` writes `INDEX_HTML` → `dashboard/index.html` on each run

**The trap**: edit `dashboard/index.html`, then run `build_dashboard.py` BEFORE running `_sync_template.py` → changes wiped out.

**Correct workflow**:
```bash
# (Edit dashboard/index.html)
py _sync_template.py            # mirror to build_dashboard.py
py build_dashboard.py           # regenerate dashboard/index.html (idempotent)
grep "marker" dashboard/index.html   # verify your changes survived
git add ...
git commit
git push
```

---

## 4. Three-Agent Curation System

**Layout**:
```
~/.claude/commands/
   SIPs.md                            ← Claude's main /SIPs command
   SIPs-codex-full.md                 ← Claude → Codex CLI wrapper
   SIPs-codex-picks.md                ← same, picks-only
   SIPs-gemini-full.md                ← Claude → Gemini CLI wrapper
   SIPs-gemini-picks.md               ← same, picks-only

~/.gemini/skills/
   SIPs/SKILL.md                      ← reference (DO NOT run directly — writes to claude_picks.json)
   SIPs-gemini-full/SKILL.md          ← writes to gemini_picks.json
   SIPs-gemini-picks/SKILL.md         ← same, picks-only

~/.codex/skills/
   SIPs/SKILL.md                      ← reference (DO NOT run directly)
   SIPs-codex-full/SKILL.md           ← writes to codex_picks.json
   SIPs-codex-picks/SKILL.md          ← same, picks-only

D:\SIPs\commands\                     ← REPO source-of-truth for the skill files
   SIPs-codex-full.md
   SIPs-codex-picks.md
   SIPs-gemini-full.md
   SIPs-gemini-picks.md
```

**Picks file contract**:
```json
{ "picks": [
  { "symbol": "FIG", "rank": 1, "intent": "long",
    "rationale": "Q1 FY26 EPS $0.57 vs $0.43 est (+33% surp)...",
    "neglected": false }
] }
```

- `symbol`: uppercase ticker, must exist in today's `stocks` dict
- `rank`: 1-based ordering (1 = top long pick, 11+ = shorts)
- `intent`: `'long'` or `'short'` — dashboard hides mismatches unless `_pickDirMismatch` is toggled
- `rationale`: 1-3 sentences in 繁中 with specific numbers
- `neglected`: only Claude's picks propagate this flag

**Wrapper invocation** (e.g., `~/.claude/commands/SIPs-codex-picks.md`):
```powershell
cd D:\SIPs
& "C:\Users\chi2t\AppData\Local\OpenAI\Codex\bin\codex.exe" exec `
  -m gpt-5.5 `
  -c model_reasoning_effort=xhigh `
  --skip-git-repo-check `
  --dangerously-bypass-approvals-and-sandbox `
  "/SIPs-codex-picks"
```

Same pattern for Gemini:
```powershell
cd D:\SIPs
gemini --yolo --skip-trust -m gemini-3-pro-preview -p "/SIPs-gemini-picks"
```

**File boundaries (each agent writes ONLY to its own file)**:
- `claude_picks.json` → Claude's territory (also writes news_detail.json, day_resets.json, catalysts_today.json)
- `codex_picks.json` → ChatGPT's territory
- `gemini_picks.json` → Gemini's territory
- `studies.json` → user's hand-curated library; NEVER modified by /SIPs

---

## 5. Frontend — Dashboard SPA

### 5.1 Routing

Hash-based routing, single SPA. Hash structure: `#/[<date>/]<route>[/<arg>]`.

```javascript
function parseHash() {
  // Returns { date, route, arg }
}

function route() {
  const { date, route: r, arg } = parseHash();
  STATE.date = date || STATE.dates[0]?.date;   // default to latest
  if (r === 'sips')           return renderSips(arg);    // /sips/<tab>
  if (r === 'squeeze')        return renderSqueeze();
  if (r === 'earnings')       return renderEarnings();
  if (r === 'catalyst')       return renderCatalyst();
  if (r === 'scanx')          return renderScanx();
  if (r === 'gappers')        return renderGappers();
  if (r === 'studies')        return renderStudies();     // ⚠ plural = list
  if (r === 'study' && arg)   return renderStudyDetail(arg);  // ⚠ singular = detail
  if (r === 'stock' && arg)   return renderStock(arg);
  renderSips();
}

window.addEventListener('hashchange', route);
```

**Subtle**: `#/studies/<id>` goes to the studies list (plural). `#/study/<id>` goes to the detail page (singular). News popup link bug fixed in commit `e81c18f`.

**Building route hashes**:
```javascript
function buildRouteHash(routePath) {
  const isLatest = STATE.date === STATE.dates[0]?.date;
  return '#/' + (isLatest ? '' : STATE.date + '/') + routePath;
}
```

When viewing the latest date, the date prefix is omitted from the hash. Older dates keep the explicit prefix so refresh / bookmarks work.

### 5.2 STATE Shape

```javascript
const STATE = {
  date: null,                    // currently viewed date (ISO)
  dates: [],                     // [{ date, label }] — sorted newest first
  data: null,                    // current date's full data dict
  candles: {},                   // per-symbol candle bars (loaded once at boot)
  sidecar: { available, checked, info },   // local Python sidecar status
  imgIndex: null,                // studies images index
};
```

### 5.3 Theme & Design Tokens (the trap)

CSS custom properties defined at `:root` (light) and `body.dark` (dark). Major tokens:

```css
:root {
  --ink:           #191c1f;   /* primary text */
  --body:          #1f2226;   /* slightly softer body text */
  --mute:          #505a63;   /* secondary text */
  --stone:         #7a838c;   /* tertiary text */
  --primary:       #494fdf;   /* cobalt blue accent */
  --pos:           #00a87e;   /* green */
  --neg:           #e23b4a;   /* red */
  --canvas:        #ffffff;   /* page background / card background */
  --surface-soft:  #f4f4f4;   /* subtle gray (popup header/footer) */
  --surface-elevated: #16181a; /* ⚠ DARK in both themes — for tooltips */
  --hairline:      #e3e6ea;   /* borders */
  --hairline-soft: #eef0f3;   /* subtle borders */
  --r-sm: 6px; --r-md: 12px; --r-lg: 16px; --r-pill: 999px;
  --font-body: 'Inter', ...;
  --font-mono: 'JetBrains Mono', ...;
  --font-display: 'Inter', ...;
}

body.dark {
  --ink:           #f4f5f7;
  --body:          #d6d9dd;
  --mute:          #a3a8b0;
  --canvas:        #16181a;
  --surface-soft:  #1f2226;
  --surface-elevated: #2a2d31;   /* ⚠ still dark in dark mode (relative to canvas) */
  ...
}
```

**The trap**: `--surface-elevated` is INTENTIONALLY dark in BOTH themes — it's the EPS chart's `#chart-tooltip` background (dark floating tooltip on any theme). Don't use it for regular popups.

For theme-aware popup backgrounds:
- Body content: `var(--canvas)`
- Header / footer (subtle contrast): `var(--surface-soft)`
- Text: `var(--ink)` for high contrast, `var(--body)` for slightly softer
- Borders: `var(--hairline)` / `var(--hairline-soft)`

---

## 6. Candle Chart Subsystem

The big interactive chart on the Stock Detail page (`#/stock/<sym>` → `renderStock`).

### 6.1 Layout (SVG geometry)

```
        Stock detail page width (max 940px)
        ┌─────────────────────────────────────────┐
        │                                  │ ← padT=28
        │   ┌─────────────────────────┐    │
        │   │     MAIN PANE           │    │ ← mainTop to mainBottom
        │   │     (candles)           │    │   height = mainH
        │   │                         │    │   width  = effectivePlotW
        │   │   SYM watermark         │    │            = plotW - rightInset(56)
        │   │                         │    │
        │   └─────────────────────────┘    │ ← mainBottom = ~382
        │   [N marker row, h=22]           │ ← newsRowY
        │   ┌─────────────────────────┐    │ ← volTop = ~406
        │   │   VOLUME PANE           │    │
        │   │   (volume bars)         │    │   height = volH (88)
        │   └─────────────────────────┘    │ ← volBottom = ~492
        │   [date axis labels, y=506]      │ ← H - padB
        │                                  │
        └──────────────────────────────────┘
                                            ↑
                                         padR (64)
                                       (price axis labels)
```

**Layout constants** (in `renderCandleChartFull`):
```javascript
const W = 940, H = 520;
const padL = 4, padR = 64, padT = 28, padB = 28;
const volH = 88, newsRowH = 22;
const rightInset = 56;
const mainTop = padT;                    // 28
const volBottom = H - padB;              // 492
const volTop    = volBottom - volH;      // 404
const newsRowY  = volTop - newsRowH - 2; // 380
const mainBottom = newsRowY - 2;         // 378
const mainH = mainBottom - mainTop;      // 350
const plotW = W - padL - padR;           // 872
const effectivePlotW = plotW - rightInset; // 816 (where bars actually render)
```

### 6.2 State Machine

```javascript
const state = {
  // Visible time range (indices into bars[])
  visibleStart: 0, visibleEnd: bars.length - 1,
  // Y zoom (per pane)
  yManualScale: 1.0,        // price pane
  volManualScale: 1.0,      // volume pane
  // Crosshair (last cursor position)
  crosshair: null,          // { px, py, barIdx (relative to visible) }
  // Y-axis drag state
  isDraggingY: false, isDraggingVolY: false,
  yDragStartClientY: 0, yDragStartScale: 1,
  // Measure (TC2000) state
  isMeasuring: false,
  measure: null,            // { start: {idx, price, snap, snapLabel}, end: {...} }
  // Middle-button pan
  isPanning: false,
  panStartClientX: 0, panStartVisibleStart: 0, panStartVisibleEnd: 0,
};
```

### 6.3 Interactions (5 modes)

**Wheel zoom (X axis)**:
```javascript
function onSvgWheel(e) {
  e.preventDefault();
  const currentVisible = state.visibleEnd - state.visibleStart + 1;
  const factor = e.deltaY < 0 ? 0.82 : 1.22;
  let newVisible = Math.round(currentVisible * factor);
  newVisible = Math.max(8, Math.min(bars.length, newVisible));
  // Anchor zoom at right edge (most-recent bar stays visible)
  state.visibleStart = Math.max(0, state.visibleEnd - newVisible + 1);
  render();
}
```

**Right-axis Y-zoom drag** (left mouse button on right side):
- `.candle-y-axis-zone` rect covers `(W - padR, mainTop - 14)` to `(W, mainBottom + 10)` — extends past pane to cover topmost/bottommost label glyphs
- `.candle-vol-y-axis-zone` covers volume pane's right axis
- Drag direction: DOWN = shrink (larger range, smaller bars), UP = enlarge
- Math: `factor = Math.exp(dy / 250); manualScale = clamp(0.15, 8, startScale * factor)`

**Middle-button pan** (commit 8e700dc):
```javascript
if (e.button === 1) {   // middle button
  state.isPanning = true;
  state.panStartClientX = e.clientX;
  state.panStartVisibleStart = state.visibleStart;
  state.panStartVisibleEnd   = state.visibleEnd;
  svg.style.cursor = 'grabbing';
}
// On mousemove:
const dx = e.clientX - state.panStartClientX;
const pxPerBar = screenPlotW / Math.max(1, panStartVisibleCount);
const barShift = Math.round(dx / pxPerBar);
state.visibleStart = state.panStartVisibleStart - barShift;
state.visibleEnd   = state.panStartVisibleEnd   - barShift;
// Clamp to [0, bars.length - 1] keeping window width constant
```

**TC2000-style measure** (left mouse drag):
- SNAP_THRESHOLD = 6 SVG pixels
- On mousedown: compute `state.measure.start = computeMeasurePoint(barIdx, cursorPy)`
- `computeMeasurePoint` checks distance from cursor's SVG-Y to each OHLC value of the bar:
  - If within 6px → snap to that OHLC value, mark `snap: true` with label (`O`/`H`/`L`/`C`)
  - Else → free position (price = `_priceAtY(cursorPy)`, `snap: false`)
- During drag: same logic computes `end`
- `state.measure` cleared on mouseup
- Popup shows `start.date → end.date`, intraday hint if same bar (`盤中` label), days span, $start → $end with snap labels, change %
- Popup position: top-left if drag ends on right half of chart, top-right if on left half. ALL at `top: 52px` to clear OHLCV display

**Crosshair** (any hover inside chart area):
- Vertical line spans `mainTop` to `volBottom`
- Horizontal line in main pane only (when cursor in main)
- Price label box on right axis
- Date label box at bottom
- `clientToBarIdx` MUST use `effectivePlotW` (matches xScale) — using plotW causes the crosshair to drift away from the cursor

### 6.4 News Markers + Popup

**Markers**: Between main pane and volume pane (commit cbc9fc5). For each bar with a news entry in `opts.newsHistory`:
```javascript
parts.push(`<g class="news-marker-group" data-date="${b.date}">`);
parts.push(`  <circle cx="${x}" cy="${newsRowY + 11}" r="9" class="news-marker-circle"/>`);
parts.push(`  <text x="${x}" y="${newsRowY + 15}" text-anchor="middle" class="news-marker-label">N</text>`);
parts.push(`</g>`);
```

Click handler reads `circle.getAttribute('cx')` + `cy` for SVG coords, then opens popup.

**newsMap source** (built in renderStock):
```javascript
// 1. Scan archive (buildNewsHistory walks dashboard/data/<date>.json files)
hist.forEach(h => {
  if (h.detail || h.title) {
    newsMap[h.date] = {
      detail: h.detail || h.title,
      title: h.title,
      sourceType: 'scan',
      sourceLink: '#/' + h.date + '/stock/' + s.symbol,
    };
  }
});
// 2. My Studies — same-symbol studies' datedSnapshots
myStudies.filter(st => st.symbol === s.symbol).forEach(st => {
  Object.entries(st.datedSnapshots || {}).forEach(([date, slot]) => {
    const news = slot?.snapshot?.newsDetail || slot?.snapshot?.catalyst;
    if (!news || newsMap[date]) return;   // scan-archive version wins
    newsMap[date] = {
      detail: news,
      sourceType: 'study',
      sourceLink: '#/study/' + st.id,   // ← singular!
    };
  });
});
```

**Popup architecture** (commit 8f5a5c3):
- Singleton at `<body>` level: `#candle-news-popup-singleton`
- Lazy-created on first call to `showNewsPopup()`
- `position: absolute` with document coords (`window.pageYOffset` etc.)
- So popup scrolls WITH the page
- Always pops UP above marker (no fallback to below unless not enough room AT TOP of viewport)
- Body content uses `var(--canvas)` background + `var(--ink)` text (THEME-AWARE)
- Header/footer use `var(--surface-soft)`
- Arrow at bottom of popup, points down at marker
- Auto-dismisses on link click (commit e81c18f) + on hashchange

---

## 7. Filter Popup Pattern (3 popups, shared base)

CSS class `.studies-filter-popup` is shared between:
1. **Studies filter** (#studies-filter-btn) — tag filter
2. **Studies sort** (#studies-sort-btn) — sort options (gets `.sort-popup` subclass)
3. **SIPs filter** (#sips-filter-btn) — Direction / Day / Catalyst (gets `.sips-filter-popup` subclass)

**Common CSS**:
```css
.studies-filter-popup {
  position: absolute; z-index: 1500;
  background: var(--canvas); border: 1px solid var(--hairline); border-radius: var(--r-md);
  box-shadow: 0 14px 40px -10px rgba(15,15,25,0.18);
  width: 280px; padding: 10px;
  opacity: 0; transform: translateY(-4px);
  transition: opacity 160ms ease-out, transform 200ms cubic-bezier(0.16, 1, 0.3, 1);
  will-change: opacity, transform;
}
.studies-filter-popup.show {
  opacity: 1; transform: translateY(0);
}
.studies-filter-popup.fading {
  opacity: 0; transform: translateY(-4px);
  pointer-events: none;
}
```

**Show / dismiss helpers** (shared, defined near `renderSips`):
```javascript
function showFilterPopup(pop) {
  // Double rAF: first frame paints with opacity:0, second frame triggers transition
  requestAnimationFrame(() => {
    requestAnimationFrame(() => pop.classList.add('show'));
  });
}
function dismissFilterPopup(pop) {
  if (!pop || !pop.parentNode || pop.classList.contains('fading')) return;
  pop.classList.add('fading');
  pop.classList.remove('show');
  setTimeout(() => { try { pop.remove(); } catch (_) {} }, 200);
}
```

**Auto-close pattern** (applied to all three):
```javascript
let __leaveTimer = null;
const __scheduleClose = () => {
  if (__leaveTimer) clearTimeout(__leaveTimer);
  __leaveTimer = setTimeout(() => { dismissFilterPopup(pop); }, 200);
};
const __cancelClose = () => {
  if (__leaveTimer) { clearTimeout(__leaveTimer); __leaveTimer = null; }
};
pop.addEventListener('mouseleave', __scheduleClose);
pop.addEventListener('mouseenter', __cancelClose);
btn.addEventListener('mouseenter', __cancelClose);   // back-and-forth doesn't trigger close
```

**Position-tracking** (commit 7fdfb3f): use `rect.bottom + window.pageYOffset + 6` instead of just `rect.bottom + 6`. Position type is `absolute`, not `fixed`, so document scrolling moves the popup with the button.

---

## 8. Today's SIPs Page

URL: `#/sips/<tab>` (or just `#/sips` for default Claude tab).

**Tabs**: `claude` (default), `codex`, `gemini`, `magna` — declared at `validTabs`.

**Filter** (`SIPS_FILTER` Set + `sipsMatchesFilter` function):
- Sentinel keys: `__long`, `__short`, `__day1`, `__day2`, `__day3`
- Tag keys: `'earnings'`, `'M&A'`, `'FDA'`, etc. (matched against `stock.type` lowercase)
- Section interior = OR, cross-section = AND

```javascript
function sipsMatchesFilter(s, isPicksTab) {
  if (SIPS_FILTER.size === 0) return true;
  const dirOptions = ['__long', '__short'].filter(k => SIPS_FILTER.has(k));
  if (dirOptions.length > 0) {
    const dir = isPicksTab
      ? (s._pickIntent || (s.chgPct > 0 ? 'long' : 'short'))
      : (s.chgPct > 0 ? 'long' : 'short');
    if (!dirOptions.includes('__' + dir)) return false;
  }
  const dayOptions = ['__day1', '__day2', '__day3'].filter(k => SIPS_FILTER.has(k));
  if (dayOptions.length > 0) {
    const dl = '__' + (s._dayLabel || 'day1');
    if (!dayOptions.includes(dl)) return false;
  }
  const tagOptions = [...SIPS_FILTER].filter(k => !k.startsWith('__'));
  if (tagOptions.length > 0) {
    const t = (s.type || '').toLowerCase();
    if (!tagOptions.some(tag => (tag || '').toLowerCase() === t)) return false;
  }
  return true;
}
```

**Filter popup rendering** (`openSipsFilterPopup(btn, subtab)`):
- Reads `rowsForCount` based on current `subtab`:
  - `magna` → MAGNA53 top-12
  - `claude/codex/gemini` → that agent's picks (filtered to today's candidates)
- Counts direction using `_pickIntent` on picks tabs (not chgPct)
- Counts day using `__sipsFirstSeenCache` populated by `renderSips()` before paint
- Counts catalyst tag from each stock's `type` field

**MUST pass resolved `tab` to popup**, not raw `subtab` parameter — `subtab` is `undefined` for the default Claude route. (commit 0a827a2)

**`PICK_SOURCES` const** maps tab key → metadata:
```javascript
const PICK_SOURCES = {
  claude: { label: 'Claude',  picksFile: 'claude_picks.json', cssClass: 'claude-pick', rankClass: 'claude-rank' },
  codex:  { label: 'ChatGPT', picksFile: 'codex_picks.json',  cssClass: 'codex-pick',  rankClass: 'codex-rank'  },
  gemini: { label: 'Gemini',  picksFile: 'gemini_picks.json', cssClass: 'gemini-pick', rankClass: 'gemini-rank' },
};
```

Generic `pickCardHtml(s, idx, sourceKey)` renders any of the three using these tokens.

**Direction mismatch indicator**:
```javascript
const isMismatch = s => {
  if (s._pickIntent === 'long')  return !(s.chgPct > 0);
  if (s._pickIntent === 'short') return !(s.chgPct < 0);
  return false;
};
// Each enriched stock gets _pickDirMismatch: bool
// pickCardHtml adds .dir-mismatch class + ⚠️ banner when true
```

Note: mismatched picks are NO LONGER auto-hidden (commit f6c2599 removed SHOW_MISMATCHED_PICKS). User can filter by Direction explicitly to exclude mismatches.

---

## 9. My Studies System

URL: `#/studies` (list) or `#/study/<id>` (detail).

**studies.json shape** (array of objects):
```json
[
  {
    "id": "NBIS-mp85qrpt9dk",
    "symbol": "NBIS",
    "savedAt": "ISO 8601",
    "snapshot": {
      "name": "Nebius Group",
      "type": "earnings", "chgPct": 8.4, "last": 75.20,
      "catalyst": "Q1 2026 業績電話會議後",
      "tv": { ... },           // copy of TradingView quarterly data
      "sessions": [...],       // copy of scan-day sessions
      "shortFloat": 12.5, ...,
      "claudeRationale": "...",
      "newsDetail": "**markdown** body",
      "sources": [{label, url}],
      "scanDate": "2026-05-13",
      "_placeholder": true     // true if awaiting /SIPs auto-fill
    },
    "ohlcv": {
      "date": "2026-05-13",
      "open": ..., "high": ..., "low": ..., "close": ..., "prev_close": ..., "volume": ...
    },
    "notes": "user's free-form notes",
    "tags": ["earnings", "user-custom-tag"],
    "customTypes": ["earnings"],   // catalyst tags
    "targetPrice": 90, "stopLoss": 70, "conviction": 4,
    "intent": "long",               // manual override (else derived from chgPct)
    "hiddenSections": ["eps_chart", "rev_chart"],   // user-hidden chart cards
    "customChart": { ... },          // optional in-page edits to MS table
    "datedSnapshots": {
      "2026-05-13": { "snapshot": {...}, "ohlcv": {...}, "notes": "...", "customTypes": [...], "hiddenSections": [...] },
      "2026-05-18": { ... }
    },
    "screenshots": [{ id, label, caption, imgKey }]
  }
]
```

**Multi-entry per symbol** (commit cb1e03a):
- Multiple studies for the same ticker allowed — represent different research sessions / dates / intents
- `addStudy()` creates new entries even if same symbol exists, BUT auto-inherits:
  - `datedSnapshots` (deep copy from newest existing same-symbol study)
  - `snapshot.newsDetail` / `catalyst` / `tv` (if new doesn't provide them)
- `addManualStudy()` same pattern — new placeholder inherits prior research

**datedSnapshots model**:
- One study has ONE primary `snapshot` + `ohlcv` (the "current view") and a `datedSnapshots` map per ISO date
- Switching between dates via the calendar date pill (in study detail page) swaps the primary state with the dated slot
- The dashboard's JS `updateStudy(id, patch)` auto-mirrors flat → datedSnapshots on every edit
- The `/update-studies` skill writes directly to JSON, must mirror manually (see § 5 of `~/.claude/skills/update-studies/SKILL.md`)

**Sorting + filtering**:
```javascript
const STUDIES_FILTER = new Set();   // tag keys + sentinels (__long/__short)
let STUDIES_SORT = 'date-desc';     // sort key

const STUDIES_SORT_GROUPS = [
  { key: 'date',    label: 'Trade date',  defaultDir: 'desc' },
  { key: 'added',   label: 'Date added',  defaultDir: 'desc' },
  { key: 'symbol',  label: 'Symbol',      defaultDir: 'asc'  },
];

function studyMatchesFilter(st) { /* ... */ }
function sortStudies(arr) { /* ... */ }
```

---

## 10. Search Box (Studies)

The studies search input has 3 sections in its dropdown:

1. **"已存在的研究 (N) — 點擊開啟"**: list of EXISTING studies matching the query. Click navigates to `#/study/<id>` (singular!). Sorted newest-saved first, capped at 10.

2. **"過去的掃描資料 — 點擊新增為 study"**: tickers from the scan archive (`STATE.dates` + `loadDateData`). Click adds via `addStudy({...snap, symbol: sym}, { scanDate, force: true })` — inherits data from newest same-symbol study.

3. **"+ 新增另一筆 TICKER"** (if query is a valid ticker pattern): click creates a new manual study via `addManualStudy(sym)`. If existing same-symbol studies exist, the new one inherits their datedSnapshots / news / catalyst.

```javascript
async function buildSymbolIndex() {
  if (__symbolIndex) return __symbolIndex;
  const m = new Map();
  const sortedDates = [...STATE.dates].sort((a, b) => b.date.localeCompare(a.date));
  for (const d of sortedDates) {
    const data = await loadDateData(d.date);
    if (!data || !data.stocks) continue;
    for (const [sym, snap] of Object.entries(data.stocks)) {
      if (!m.has(sym)) m.set(sym, { snapshot: snap, scanDate: d.date });
    }
  }
  __symbolIndex = m;
  return m;
}
```

The index is built lazily on first focus + memoized.

---

## 11. Calendar Widgets

Two custom calendar popups (no native `<input type="date">`):

1. **Topbar date pill** (`renderCalendar()` near line 2361): shows only dates that have `dashboard/data/<DATE>.json` files. Restricted set.

2. **Study-detail date pill** (`renderStudyCalendar()` around line 5774): allows ANY date — user picks any historical date for the study's anchor.

**Both share `.cal-day` CSS** + same grid structure (7 columns × N rows).

**Weekend disabling** (`weekend` class + `disabled` attribute):
```javascript
const dow = new Date(year, month, day).getDay();
const isWeekend = (dow === 0 || dow === 6);   // Sun=0, Sat=6
if (isWeekend) classes.push('weekend');
// ...
html += `<button class="${classes.join(' ')}" ${isWeekend ? 'disabled' : ''}>${day}</button>`;
```

CSS:
```css
.cal-day.weekend { color: var(--stone); cursor: not-allowed; opacity: 0.35; }
.cal-day.weekend:hover { background: transparent; transform: none; }
.cal-dow.weekend { color: var(--stone); opacity: 0.55; }
```

Saturday/Sunday column headers (`Sa`/`Su`) get `.weekend` class too for visual consistency.

---

## 12. Theme System (CSS Vars)

See § 5.3 for the full token list and the trap.

**Theme toggle** lives in the topbar nav. Inverts `body.dark` class. Persisted to localStorage:
```javascript
function installThemeToggle() {
  const stored = localStorage.getItem('theme');
  if (stored === 'dark') document.body.classList.add('dark');
  // ... button toggles + saves
}
```

Most components are theme-aware via CSS vars. Specific components that hardcoded colors and have body.dark overrides:
- `.candle-up` / `.candle-down` (use brighter colors in dark mode)
- `.cal-day.active` (slightly different active state)
- The few inline-styled tags (e.g., direction pills inside filter popup)

---

## 13. MAGNA53 Classification

In-memory only — no file output. Each candidate gets a per-letter score:

| Letter | Bit | Meaning |
|---|---|---|
| **M** | Mag | Magnitude — gap % + volume vs avg |
| **A** | A | Acceleration — recent quarter EPS/Rev surprise |
| **G** | G | Growth — YoY EPS or Rev > X% |
| **N** | N | Neglect — low institutional ownership + recent decliners; manual flag via `claude_picks.json.neglected` |
| **A** | A | Annual Sales — high enough to be institutional-grade |
| **5** | DTC | Days to cover — short ratio threshold |
| **3** | RVol | 3x relative volume |

Setup classification: A / B / C / NULL (NULL = no clean setup, exclude from ranking).

Function lives in `magna53(stock)` returning `{ score: int, bits: {M, G, N, A, 5, 3} }`.

Used by:
- MAGNA53 subtab on Today's SIPs (sorts by score desc, shows top 12 with score ≥ 4)
- Stock detail page header

---

## 14. Catalyst Types System

**Preset types** (`CATALYST_PRESETS` const):
```javascript
const CATALYST_PRESETS = [
  { key: 'earnings',  label: 'earnings',  cls: 'catalyst-type-earnings'  },
  { key: 'analyst',   label: 'analyst',   cls: 'catalyst-type-analyst'   },
  { key: 'guidance',  label: 'guidance',  cls: 'catalyst-type-guidance'  },
  { key: 'contract',  label: 'contract',  cls: 'catalyst-type-contract'  },
  { key: 'm&a',       label: 'M&A',       cls: 'catalyst-type-ma'        },
  { key: 'fda',       label: 'FDA',       cls: 'catalyst-type-fda'       },
  { key: 'news',      label: 'news',      cls: 'catalyst-type-news'      },
  { key: 'momentum',  label: 'momentum',  cls: 'catalyst-type-momentum'  },
  { key: 'macro',     label: 'macro',     cls: 'catalyst-type-macro'     },
  { key: 'etf',       label: 'ETF',       cls: 'catalyst-type-etf'       },
];
```

**Custom types** can be added per-study (stored in `study.customTypes`). User can also hide presets they don't use via the gear icon (stored in localStorage).

**`getAllCatalystOptions()`** returns the union: visible presets + user-defined custom types.

Each Today's SIPs stock has a `type` field (from `catalysts_today.json`) used by the dashboard's badge rendering and filter.

---

## 15. Sidecar (Local Edit Mode)

A small Python sidecar (`D:\SIPs\sidecar.py`) runs on `127.0.0.1:5510`. When the dashboard detects it (`GET /api/health`), it switches Studies to "edit mode":
- Edits to studies write through to `dashboard/studies/studies.json` via `POST /api/studies/save`
- Image uploads to `dashboard/studies/images/<imgKey>.<ext>` via `POST /api/studies/image`
- Otherwise (hosted Pages without sidecar): view-only mode, all edit affordances disabled with a "🔒 View only" badge

**State**: `STATE.sidecar = { available, checked, info }`. Set by `detectSidecar()` at boot.

---

## 16. Day Labels (day1/2/3) + Reset Logic

For each stock in today's view, compute when it FIRST appeared in any scan:

```javascript
async function getSymbolFirstSeenMap() {
  if (__firstSeenMap) return __firstSeenMap;
  // Walk newest → oldest. For each (date, symbol), record first-seen date.
  const m = new Map();
  // ... walks STATE.dates in reverse, populates m
  __firstSeenMap = m;
  return m;
}
```

Day label:
- **day1** = first seen TODAY (i.e., this is the FIRST scan where it appears)
- **day2** = first seen on the immediately preceding date
- **day3** = first seen 2+ days before

**Resets** (`dayResets` field in dashboard data): symbols whose day-count "resets to day1" today due to a new major catalyst. The map is keyed by symbol → reason string. Curated manually via `day_resets.json` by Claude.

`dayLabelWithReset(symbol, firstSeenMap, today)` consults the resets map: if the symbol has an entry, force day1 regardless of past appearances.

Memory reference: `feedback_day_resets_judgment.md` (the "soft signal + same-driver heuristic" rule for when to mark a reset).

---

## 17. News Curation Workflow

`news_detail.json` is the curated 繁中 news layer (Claude writes; other agents don't touch).

**Schema**:
```json
{
  "SYM": {
    "detail": "**heading**\n\n5/18 盤前公布...\n\n**SIP 判斷：** Setup C 適用...",
    "publishedAt": "2026-05-18T07:00:00-04:00",
    "publishedTimezone": "ET",
    "sources": [
      { "label": "Reuters", "url": "https://..." },
      { "label": "SEC 10-K", "url": "https://..." }
    ]
  }
}
```

**Markdown features supported by `mdNewsToHtml()`**:
- `**bold**` → `<strong>` (renders as `--ink` color, NOT primary blue, in news-detail card; but inside popup it IS primary)
- Paragraphs separated by `\n\n`
- `> blockquote` lines → `<blockquote>` (used for caveats like "estimates are current, not historical")

**Time formatting**: see `NEWS_TIME_SPEC.md` for the `publishedAt` ISO 8601 format and how to source real publication times.

**Sources rendering**: pill row at the bottom of the news-detail card. Clicking opens in new tab. Encourages users to verify big-number claims (e.g., "+57.7% EPS surprise") against original press releases.

**Cross-references** (added during this session for HIVE/Leopold): newsDetail can include "**機構動向 — Leopold Q1 2026 13F 揭露持有 HIVE**" paragraphs that reference 13F holdings. Pulled directly from SEC EDGAR XML (not aggregator sites, which truncate top 24).

---

## 18. Auto-Push + Git Workflow

**Standing approval**: User has authorized auto-push to `chi2tseng/stocks-in-play`. NEVER use `AskUserQuestion` to confirm pushes.

**Typical commit pattern**:
```bash
cd /d/SIPs
py _sync_template.py        # if dashboard/index.html was edited
py build_dashboard.py       # regenerate dashboard/index.html
git add build_dashboard.py dashboard/index.html dashboard/data.json \
        dashboard/data/<date>.json dashboard/studies/studies.json \
        news_detail.json claude_picks.json codex_picks.json gemini_picks.json
git commit -m "$(cat <<'EOF'
short subject line under 70 chars

Longer body explaining the WHY (not the WHAT). Multiple paragraphs OK.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git push
```

`.gitignore` excludes: `node_modules`, `candidates.csv`, `shorts.json`, `tv-summary.json`, `*-earnings-fq.md`, `barchart-*-p*.json` (per-run scratch).

**Don't commit**: scratch files generated by /SIPs (e.g., `candidates.csv`, `*.earnings-fq.md`). They get regenerated each run.

**Do commit**: `dashboard/data/<date>.json` (the dashboard payload), `dashboard/candles.json`, `news_detail.json`, all picks files, studies.json, the build script + sync script.

---

## 19. Common Anti-Patterns to Avoid

1. **`var(--surface-elevated)` for normal popups** — it's the dark tooltip token, dark in both themes. Use `var(--canvas)`.

2. **`position: fixed` inside transformed ancestors** — fixed becomes relative to the transformed ancestor, not viewport. Use `position: absolute` with document coords OR a body-singleton.

3. **Editing index.html then running build_dashboard.py without _sync_template.py** — wipes your changes (build re-emits the stale INDEX_HTML block).

4. **Trusting aggregator sites for 13F top holdings** — they truncate at ~top 24. SEC EDGAR XML is source of truth.

5. **WebFetch on SEC** — returns 403 (User-Agent enforcement). Use Bash curl with email User-Agent: `curl -A "name email@x" "https://..."`

6. **Passing raw `subtab` to filter popup** — undefined for default Claude route. Pass resolved `tab`.

7. **`#/studies/<id>`** routes to the list (plural). Use `#/study/<id>` (singular) for detail.

8. **Skipping the markdown bold render check** — `mdNewsToHtml` is what makes `**bold**` actually bold. Without it, the literal asterisks render.

9. **`clientToBarIdx` using `plotW`** — bars are scaled to `effectivePlotW`. Mismatch causes crosshair drift.

10. **Yahoo daily bar = regular session only** — no pre/post market data. If you need overnight session data, that's a different API endpoint (not currently used).

11. **MSYS path conversion** — Git Bash converts `/X` to `C:/Program Files/Git/X` when passed to Windows executables. Use PowerShell tool or prefix `MSYS_NO_PATHCONV=1`.

12. **Saturday/Sunday dashboard data should not exist** — markets closed. If they appear, the scan was misdated. Delete + regenerate dates.json.

13. **Running fetch_candles for >500 symbols carelessly** — Yahoo will throttle at ~500/min. Current usage (~50/run) is comfortable.

14. **`SHOW_MISMATCHED_PICKS` toggle** — that's the OLD model (replaced by SIPS_FILTER in commit f6c2599). Don't reintroduce it.

15. **Inline emoji in popup labels** — user explicitly removed them ("不要有 emoji"). Plain text labels with centered alignment.

---

## End-of-Document Footer

**Last verified state**: 2026-05-19, ET 03:15 (Taiwan 16:15).
**Latest commit**: `0c7876f scan: 5/19 Tue — 14 post-market routed candidates, top long AGYS`
**Archive (4 dates)**: 5/14, 5/15, 5/18, 5/19
**Studies count**: 13
**candles.json size**: ~575KB (50 symbols)

For PENDING TASKS (what to do next), see `HANDOFF.md` §3.
