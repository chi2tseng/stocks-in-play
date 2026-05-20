# SIPs Dashboard — Session Handoff Document

> **Generated**: 2026-05-19 (Taiwan evening / US Tuesday early morning ET)
> **For**: continuing this work in a NEW Claude Code session
> **Repo**: `D:\SIPs\` (local) → `https://github.com/chi2tseng/stocks-in-play` (public)
> **Live dashboard**: `https://chi2tseng.github.io/stocks-in-play/`
> **Auto-push**: User has standing approval. **Never use `AskUserQuestion` to confirm git pushes** — just push.

---

## 0. Quick Orientation (read this first)

**What is SIPs?** A daily NTRT/MTRT gap-scanner pipeline that scrapes Barchart pre/post-market gappers, classifies them with MAGNA53 + Stockbee SIP framework, pulls TradingView quarterly EPS/Rev estimates for earnings movers, and publishes a static-SPA dashboard at `D:\SIPs\dashboard\`. Three independent AI agents (Claude, ChatGPT via Codex CLI, Gemini) produce competing daily picks lists.

**Key files to know about**:

| File | Purpose |
|---|---|
| `barchart-scrape.js`         | Playwright + XHR intercept; outputs `candidates.csv` with `SessionDate` column |
| `tv-scrape.js` + `parse_tv.py` | TradingView FQ quarterly grid → `tv-summary.json` |
| `finviz-shorts.js`           | Finviz quote pages → `shorts.json` (shortFloat, DTC, perf1M-12M) |
| `fetch_candles.py`           | Yahoo Finance daily bars → `dashboard/candles.json` |
| `build_dashboard.py`         | Merges everything → `dashboard/data/<DATE>.json`, regenerates `index.html` |
| `_sync_template.py`          | Bidirectional sync between `dashboard/index.html` and the `INDEX_HTML = r'''...'''` block inside `build_dashboard.py` |
| `claude_picks.json` / `codex_picks.json` / `gemini_picks.json` | Agent picks (each agent only writes its own) |
| `news_detail.json`           | Curated 繁中 news per top stock (shared) |
| `dashboard/index.html`       | The actual SPA (mirror of build_dashboard.py's INDEX_HTML block) |
| `dashboard/studies/studies.json` | User's hand-curated research library |

**Dashboard data flow**:
```
Barchart   → candidates.csv (rows w/ Session + SessionDate)
TradingView → tv-summary.json
Finviz     → shorts.json
Yahoo      → dashboard/candles.json (per-symbol 1yr daily bars)
News       → news_detail.json
Picks      → {claude,codex,gemini}_picks.json
                ↓
        build_dashboard.py
                ↓
     dashboard/data/<DATE>.json   (one file per target date — see §3 routing rule)
     dashboard/dates.json         (date picker index)
     dashboard/data.json          (mirror of latest)
     dashboard/index.html         (rebuilt from INDEX_HTML block)
                ↓
        git push (auto)
                ↓
    GitHub Pages serves the dashboard
```

---

## 1. Today's Session Summary (chronological)

This was a marathon session covering ~30 distinct work items. Key landmarks:

### Three-agent curation system (early in session)
- Built `/SIPs-gemini-full`, `/SIPs-gemini-picks`, `/SIPs-codex-full`, `/SIPs-codex-picks` skills
- Skills installed at `~/.gemini/skills/SIPs-*` and `~/.codex/skills/SIPs-*`
- Source-of-truth markdown at `D:\SIPs\commands\SIPs-*.md`
- Claude-side wrappers at `~/.claude/commands/SIPs-{codex,gemini}-{full,picks}.md` shell out to the respective CLI
- Dashboard subtabs: `Claude / ChatGPT / Gemini / MAGNA53` (no `精選` suffix — kept clean)
- All three tabs use cobalt color (user explicitly rejected per-agent colors)

### CLI model pinning (locked in)
- **Gemini**: `gemini-3-pro-preview` model. YOLO mode: `gemini --yolo --skip-trust -m gemini-3-pro-preview -p "<prompt>"`
- **Codex**: `gpt-5.5` model + `xhigh` reasoning effort. Run via: `codex.exe exec -m gpt-5.5 -c model_reasoning_effort=xhigh --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox "<prompt>"`
- Codex binary at: `C:\Users\chi2t\AppData\Local\OpenAI\Codex\bin\codex.exe`

### 6-month candle chart on Stock Detail page
- Added `fetch_candles.py` (Yahoo Finance, 8 workers, ~5s for 50 tickers)
- Outputs `dashboard/candles.json` (~575KB for 50 symbols)
- Loaded once at boot into `STATE.candles`
- Full chart in stock detail page after Forward YoY section
- **TradingView-style interactivity** (lots of iterations to get right):
  - Wheel = X-axis zoom
  - Right-axis drag = Y-axis zoom (price pane + volume pane independent)
  - **Middle-button drag = pan time axis** (recent feature)
  - Left-click drag = TC2000-style measure with snap-to-OHLC (snap threshold 6 SVG-px)
  - News markers (N icons) between price + volume panes; click pops up news detail
- News popup: position:absolute (document-coords) so it scrolls with the page; body-singleton at `<body>` level so it escapes transformed ancestors; always pops UP above the marker
- Popup uses `var(--canvas)` background (NOT `--surface-elevated` — that's the dark tooltip token!)

### Today's SIPs Filter (replaced 隱藏方向不符 toggle)
- 3 sections: **Direction** (long/short), **Day** (day1/2/3), **Catalyst tag** (earnings/M&A/FDA/...)
- Section interior = OR; cross-section = AND
- Counts reflect ACTIVE TAB's row set (not all DATA.stocks):
  - magna tab → MAGNA53 top-12
  - picks tabs → that agent's picks (filtered to today's candidates)
- Direction count uses `_pickIntent` on picks tabs (NOT chgPct)
- Pass resolved `tab` to popup, not raw `subtab` (which is undefined for default Claude route)

### Filter popup UX polish
- `position: absolute` with document coords (`rect.bottom + window.pageYOffset + 6`) so popup tracks the button on scroll
- Auto-close on `mouseleave` after 200ms grace; cancel on `mouseenter` of either popup or button
- Fade in/out animation: 160ms opacity + 200ms transform via `.show` and `.fading` CSS classes
- Shared helpers: `showFilterPopup(pop)` (double-rAF then `.show`) and `dismissFilterPopup(pop)` (`.fading` then remove after 200ms)
- Applied to: SIPs filter popup, Studies filter popup, Studies sort popup

### Studies: dedup → multi-entry + auto-inherit
- Originally I deduped by symbol (one study per ticker)
- User clarified: WANT multiple entries (different research sessions, different dates, different intent), BUT new entries should auto-inherit research data
- Final design:
  - `addStudy()` allows multi-entry, copies datedSnapshots + newsDetail + catalyst from newest existing same-symbol study
  - `addManualStudy()` same pattern
  - Studies search dropdown has "已存在的研究 (N) — 點擊開啟" section at top; clicking opens that specific study via `#/study/<id>`
  - "+ 新增另一筆 TICKER" creates a new study with inherited data
- Migration tool merged the 2 duplicate NBIS studies (kept one with news, absorbed the other's 5/18 datedSnapshot)

### Bug fixes during the chart iteration
- News popup styling: `var(--surface-elevated)` was DARK in light mode (it's the EPS chart's dark-tooltip token). Use `var(--canvas)` for body, `var(--surface-soft)` for header/footer, `var(--ink)` for text
- Popup scroll-tracking: `position: fixed` glued to viewport; changed to `absolute` with document coords
- Crosshair offset: `clientToBarIdx` used `plotW` while `xScale` used `effectivePlotW` → math mismatch. Both now use `effectivePlotW`
- Y-axis drag direction was reversed (down=zoom-in instead of zoom-out). Flipped: drag DOWN → shrink (wider range), UP → enlarge
- News popup link going to `#/studies/<id>` (plural) → router only matches `#/study/<id>` (singular). Fixed in commit `e81c18f`
- News popup not closing after link click → fixed in same commit by binding link click to dismiss popup + adding hashchange listener

### Calendar weekend disabling
- Sat/Sun cells grayed out + `disabled` attribute
- Applied to both topbar calendar AND study-detail calendar popup
- Sa/Su column headers also grayed

### The big-rule changes (most recent)

#### Rule 1: Barchart per-row SessionDate tagging
- `barchart-scrape.js` now ALWAYS scrapes both pre AND post endpoints
- Computes each row's actual session date from ET clock:
  ```
  pre  session date = TODAY (ET) if ET hour >= 4   else YESTERDAY
  post session date = TODAY (ET) if ET hour >= 16  else YESTERDAY
  ```
- New `SessionDate` column in `candidates.csv`
- Boot log prints `pre=YYYY-MM-DD  post=YYYY-MM-DD` so you can sanity-check

#### Rule 2: build_dashboard.py per-target-date routing
- Each row routes to a dashboard file based on its session + date:
  ```
  pre  row, SessionDate=X → X.json
  post row, SessionDate=X → next_trading_day(X).json   (skips Sat/Sun)
  ```
- The intuition: each `<DATE>.json` represents the "overnight gap heading INTO that trading day" = previous post-market + today's pre-market
- Multi-file write loop: one `<DATE>.json` per target date, with stocks/sessions/scanx filtered down to that date's subset
- Picks + rawGappers + dayResets only go into the SCAN date file (--date arg, default today)
- For non-scan-date files that already exist: PRESERVE existing picks/rawGappers (don't overwrite)

#### Verified state (as of 2026-05-19 ET ~03:15, Taiwan ~16:00)
| File | Stocks | Content |
|---|---|---|
| `2026-05-14.json` | 53 | Old Thu data (pre/post mix from before new rule) |
| `2026-05-15.json` | 73 | Old Fri data |
| `2026-05-18.json` | 53 | All `pre@2026-05-18` (Mon morning pre-market) |
| `2026-05-19.json` | 14 | All `post@2026-05-18` (Mon after-hours, routed to Tue's file) |

When user re-runs `/SIPs` after 04:00 ET, the new 5/19 pre rows will append to `2026-05-19.json` → it becomes `5/18 post (14) + 5/19 pre (N)`.

---

## 2. Current Repo State (commit log, latest first)

```
0c7876f scan: 5/19 Tue — 14 post-market routed candidates, top long AGYS
e81c18f news popup: dismiss on link click + correct route to study detail
8036e58 build_dashboard: per-target-date row routing (overnight-gap model)
556adfe barchart-scrape: per-row SessionDate tagging (always scrape both endpoints)
8e700dc candle chart: middle-button drag to pan time axis (TradingView-style)
417620c dashboard: restore 5/18 (Monday)
56f8a0b dashboard: prune duplicate + weekend scan files
04ad2f3 candle chart: anchor-based per-study + 1-year fetch range
de91b1c SIPs skill: document fetch_candles.py as Phase 10d
318cb46 barchart-scrape: auto-detect session by ET clock (default arg)
445ad43 filter popups: fade in / fade out
478c650 filter popups: auto-close on mouseleave (200ms grace)
7fdfb3f filter popups: position:absolute so they track button on scroll
0a827a2 SIPs filter: pass resolved tab to popup
d92dd7d SIPs filter: counts reflect the active tab's visible row set
f6c2599 Today's SIPs: replace 隱藏方向不符 toggle with multi-dim filter popup
b9086b0 candle chart: intraday (same-day) drag measurement supported
364607b candle chart: measure popup is theme-aware (white card in light mode)
cc88767 candle chart: popup scrolls with page + axis hover covers full labels
8f5a5c3 candle chart: news popup is body-singleton (fixed positioning works)
5bf084e candle chart: news popup uses position:fixed, always pops UP
cbc9fc5 candle chart: news markers between panes + light-mode measure popup
64aa1a5 candle chart: 8 follow-up fixes
5366db9 candle chart: 6 fixes per user feedback
fec99e3 dashboard: TradingView-style candle chart on detail page
```

---

## 3. Pending Tasks (NOT YET DONE)

### 3.1 Candle chart on Studies detail page (HIGH priority — user asked, partial scaffolding only)
- Currently: only the Stock Detail page (`#/stock/<sym>`) has the candle chart in §「股價走勢」section
- User wants the same chart on the Studies Detail page (`#/study/<id>`)
- Anchor for studies = the study's `ohlcv.date` OR `snapshot.scanDate` OR `STATE.date`
- Where to inject: find `renderStudyDetail(idOrSym)` around line ~6494 in `dashboard/index.html`; add a `<div class="stock-card">` with the chart host similar to the Stock Detail page pattern
- The render call:
  ```js
  renderCandleChartFull(chartHost, symBars, {
    sym: study.symbol,
    anchorDate: study.ohlcv?.date || study.snapshot?.scanDate || STATE.date,
    newsHistory: newsMap
  });
  ```

### 3.2 Anchor-based candle window with 1-year fetch + 6-month default visible window (DETAILED SPEC from user)
- **User's full spec** (verbatim):
  > 我需要studies和todays sips都一樣需要在根據當天日期 (todays sips就是發生的日期 studies就是指定的日期)一直更新 直到最新當天日期的兩個月後再停止抓取 如果有再有新的catalyst就再繼續更新 但是舊的studies詳細葉面 例如我創建了一個NBIS 4/30的studies 我點進去往下滑動就是顯示NBIS在12/30-6/30 差不多這個區間的股價走勢 現在還沒到6/30所以就只要顯示到最新的那天就可以 之後在慢慢更新直到6/30 那當我又創建了一個NBIS 10/30 此時會更新之前的NBIS 4/30 但股票頁面的股價走勢一點進去還是在12/30-6/30的區間範圍 不會直接顯示到10/30 我要股價走勢圖是依據日期來做錨點 方便參考當時的走勢 
  > 抓取的資料就一次抓一年的 但顯示還是維持現在的六個月區間 讓我有可以回看的能力

- **Translation / spec**:
  - Each Today's SIPs row anchors on its scan date; each Study anchors on its specific date
  - Window to update / display: anchor ± [4mo before, 2mo after] = 6 months total
  - Once `anchor + 2 months` passes the actual current date, STOP fetching (window is frozen)
  - When a new catalyst (new scan or new study) for same symbol appears, restart updates for THAT anchor only
  - Different anchors for same symbol have INDEPENDENT views (each window stays anchored to its own date)
  - **Fetch**: 1 year of data per anchor (for scroll-back capability)
  - **Display default**: 6-month window centered on anchor (4mo before + 2mo after)
  - User can scroll/zoom out to see the full 1-year fetch range

- **Implementation plan** (NOT BUILT YET):
  - `fetch_candles.py`: instead of just last 200 days per symbol, compute per-anchor ranges:
    - Earliest fetch date = earliest_anchor - 10 months
    - Latest fetch date = min(today, max_anchor + 2 months)
    - For each unique symbol, fetch the UNION of all anchors' ranges
  - Add `viewFrom` and `viewTo` params to `renderCandleChartFull(...)` already exists (commit `04ad2f3` mentions "anchor-based per-study"). Verify this is wired correctly.
  - Frontend slicing: use `anchorDate` opt to compute default visible window
  - Status: partial scaffolding (commit `04ad2f3`) but Studies page not yet wired

### 3.3 News popup link click bug (FIXED already in `e81c18f` — verify it works)
- User reported popup didn't dismiss after clicking "開啟 Study 詳細頁"
- User reported the link went to `#/studies/<id>` (plural Studies main page) instead of `#/study/<id>` (singular detail)
- Commit `e81c18f` claims both are fixed — **verify on the live dashboard** before confirming closed.

### 3.4 fetch_candles.py update for anchor-based fetching (related to 3.2)
- Currently fetches blanket last 200 days per symbol
- Need to make it anchor-aware so a study at 4/30/2026 gets bars [10/30/2025 - 6/30/2026] (1 year)
- And a NEW study at 10/30/2025 for same symbol triggers extending back to 4/30/2025
- The `dashboard/candles.json` shape `{SYM: [bars]}` is the union of all anchors' windows for that symbol

### 3.5 Output a clean conversation transcript (in progress when this doc was written)
- The user asked to export this whole conversation
- An export was generated at `C:\Users\chi2t\Downloads\SIPs-conversation-2026-05-19.md` (1.0 MB, 1790 turns)
- Includes only user prompts + assistant text responses, no tool calls

---

## 4. Critical Conventions / Rules (don't violate)

### 4.1 Auto-push policy
- User has STANDING APPROVAL for all `git push` to `chi2tseng/stocks-in-play`
- Never use `AskUserQuestion` to confirm pushes
- Memory ref: `feedback_sips_auto_push.md` in `C:\Users\chi2t\.claude\projects\C--Users-chi2t-Downloads\memory\`

### 4.2 Index.html sync pattern (DON'T SKIP)
- `dashboard/index.html` is mirrored inside `build_dashboard.py` as `INDEX_HTML = r'''...'''`
- Workflow when editing HTML/JS:
  1. Edit `dashboard/index.html` directly
  2. Run `py _sync_template.py` → updates the `INDEX_HTML` block in `build_dashboard.py`
  3. Run `py build_dashboard.py` → regenerates `dashboard/index.html` from the synced template (idempotent)
  4. Verify your changes are still in `dashboard/index.html` (grep for marker strings)
  5. Commit both files
- **Anti-pattern**: editing `dashboard/index.html`, running `build_dashboard.py` BEFORE syncing → wipes your changes
- Verified workflow: `Edit → _sync_template.py → build_dashboard.py → grep verify → commit`

### 4.3 CSS design tokens (avoid the trap)
- `--surface-elevated` is DARK in BOTH light and dark mode (`#16181a` / `#2a2d31`)
  - This is the EPS chart's tooltip background (dark floating tooltip on any theme)
  - **DO NOT use for regular popup backgrounds** — they'll look black on white in light mode
- For theme-aware backgrounds: use `--canvas` (white/dark) or `--surface-soft` (subtle gray/dark gray)
- Text: `--ink` (high contrast in both modes)
- Borders: `--hairline` or `--hairline-soft`
- I made this mistake TWICE — once on news popup, once on measure popup. User was rightly annoyed.

### 4.4 Color scheme
- All three agents (Claude / ChatGPT / Gemini) use Claude cobalt `#494fdf` everywhere
- User EXPLICITLY rejected per-agent colors (green/amber/etc.)
- CSS classes `.codex-pick`, `.gemini-pick` still exist but currently render identically to `.claude-pick` (can fork later if needed)

### 4.5 Position:fixed pitfall (popups)
- `position: fixed` becomes relative to the nearest TRANSFORMED ancestor, not viewport
- Any ancestor with `transform`, `filter`, `will-change: transform`, or `contain: paint` creates a containing block
- This bit me on the news popup — fix is to either (a) move popup to `document.body` directly (body-singleton pattern) OR (b) use `position: absolute` with document coords (`rect.top + window.pageYOffset`)
- News popup: body-singleton at `#candle-news-popup-singleton`
- Filter popups: `position: absolute` with document coords

### 4.6 Markdown bold rendering for news_detail
- News from `news_detail.json` is markdown with `**bold**` syntax
- Use `mdNewsToHtml()` helper to render — it splits paragraphs on `\n\n`, converts `**X**` → `<strong>X</strong>`, escapes HTML otherwise
- `.news-detail strong` is styled `color: var(--ink); font-weight: 700` — bold text reads as standard ink, NOT primary blue
- For accent bold (e.g. inside popup), can use `color: var(--primary)` selectively

### 4.7 Skill scope: picks-only vs full
- `/SIPs-codex-picks` and `/SIPs-gemini-picks` skip the Barchart/Finviz/TV scrapes (those are expensive, already done by Claude). But they DO research each candidate via WebSearch/WebFetch — picks-mode means "make your own analytical choices using the shared scrape inputs", not "skip analysis"
- `/SIPs-codex-full` and `/SIPs-gemini-full` run the full pipeline including scrapes
- Each agent writes ONLY to its own picks file. Shared state (`news_detail.json`, `day_resets.json`, `catalysts_today.json`, `studies.json`) is off-limits unless the agent owns that piece

---

## 5. Architectural Notes

### 5.1 build_dashboard.py per-target-date routing (NEW, commit 8036e58)
```python
def _next_trading_day(iso):
    d = datetime.date.fromisoformat(iso)
    while True:
        d += datetime.timedelta(days=1)
        if d.weekday() < 5:    # Mon..Fri, skips Sat/Sun
            return d.isoformat()

def _session_target_date(session, session_date):
    return session_date if session == 'pre' else _next_trading_day(session_date)
```

Each candidate row carries `sessionDate` (from `candidates.csv`'s `SessionDate` column) and `targetDate` (computed by `_session_target_date`). At write time, the global `stocks` dict is split by `targetDate` into multiple `<DATE>.json` files.

Picks, rawGappers, dayResets, scanx only go into the SCAN-date file (--date arg). For non-scan-date files that already exist, picks/rawGappers from older runs are PRESERVED (today's scrape only refreshes stocks/sessions).

### 5.2 Candle chart (TradingView-style, in dashboard/index.html)
- `renderCandleChartFull(container, allBars, opts)` is the main function
- `opts`:
  - `sym` — symbol watermark
  - `endDate` — slice bars to `<= endDate`
  - `newsHistory` — `{date: {detail, sourceLink, sourceType}}` for marker popups
  - `anchorDate`, `viewFrom`, `viewTo` — for anchor-based windowing (PARTIAL — needs more wiring)
- State machine: `visibleStart`/`visibleEnd` indices into `bars[]`, `yManualScale`, `volManualScale`, `crosshair`, `isMeasuring`, `isPanning`, `measure: {start, end}` etc.
- Interactions: wheel zoom, right-axis drag-zoom, middle-button pan, left-button measure (with snap-to-OHLC at 6 SVG-px threshold)
- News popup is `#candle-news-popup-singleton` at `<body>` level; `position: absolute` with document coords; fades via `.show`/`.fading` classes

### 5.3 Filter popup pattern (shared across SIPs / Studies / Sort)
- Three popups share CSS class `.studies-filter-popup` (+ subclass `.sips-filter-popup` for SIPs)
- Each uses `position: absolute` with `rect.top + window.pageYOffset + 6` for document-relative positioning
- Fade in: `requestAnimationFrame` ×2 → add `.show` class
- Fade out: add `.fading`, remove `.show`, then `pop.remove()` after 200ms
- Auto-close on `mouseleave` with 200ms grace timer
- Helpers: `showFilterPopup(pop)` + `dismissFilterPopup(pop)`

### 5.4 Three-agent picks routing
- `claude_picks.json` / `codex_picks.json` / `gemini_picks.json` schema:
  ```json
  { "picks": [ { "symbol": "X", "rank": 1, "intent": "long"|"short", "rationale": "...", "neglected": bool? } ] }
  ```
- `build_dashboard.py` reads all three, filters to symbols in today's candidates, emits as `claudePicks` / `codexPicks` / `geminiPicks` in `<DATE>.json`
- `PICK_SOURCES` const in `index.html` maps tab key → `{ label, picksFile, cssClass, rankClass }`
- Generic `pickCardHtml(s, idx, sourceKey)` renders all three with appropriate styling

---

## 6. Quick Commands Reference

### Running /SIPs (Claude side)
```powershell
cd D:\SIPs
# Open Claude Code and type:
/SIPs
```

### Running 3-agent picks workflow (typical day)
```powershell
# After Claude's /SIPs finishes (writes claude_picks.json + scrape outputs):
/SIPs-codex-picks       # Claude wrapper → Codex CLI YOLO scrape → codex_picks.json
/SIPs-gemini-picks      # Claude wrapper → Gemini CLI YOLO scrape → gemini_picks.json
# All three auto-push.
```

### Manual sync + build cycle (when developing)
```powershell
cd D:\SIPs
# (edit dashboard/index.html)
py _sync_template.py    # mirror to build_dashboard.py INDEX_HTML block
py build_dashboard.py   # regenerate dashboard/index.html (idempotent)
# verify changes via grep
git add build_dashboard.py dashboard/index.html dashboard/data*.json dashboard/data/*.json
git commit -m "..."
git push
```

### ET clock check
```bash
node -e "const p=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit',hour:'numeric',minute:'numeric',hour12:false,weekday:'short'}).formatToParts(new Date());const g=k=>p.find(x=>x.type===k)?.value;let h=parseInt(g('hour'));if(h===24)h=0;console.log('ET:',g('weekday'),g('year')+'-'+g('month')+'-'+g('day'),String(h).padStart(2,'0')+':'+g('minute'));"
```

### SEC EDGAR direct access (for 13F verification — Leopold/etc.)
- Use `curl` with email User-Agent (Web Fetch returns 403 from SEC):
  ```bash
  curl -A "chi2tseng research lfcliu@gmail.com" "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=<CIK>&type=13F&count=10"
  ```
- Don't trust aggregator sites for full holdings — they truncate to top 24

---

## 7. Known Gotchas / Anti-patterns

1. **Don't use `var(--surface-elevated)` for regular popups** — it's a dark token in both themes
2. **Don't trust aggregator sites for 13F top holdings** — they truncate. Pull SEC XML directly
3. **Don't edit dashboard/index.html and run `build_dashboard.py` without `_sync_template.py` first** — wipes your changes
4. **Don't use `position: fixed` inside transformed ancestors** — use body-singleton or `absolute` with document coords
5. **Don't pass raw `subtab` param to `openSipsFilterPopup`** — `subtab` is undefined for default Claude route; pass resolved `tab`
6. **Don't fetch_candles all S&P 500 carelessly** — Yahoo will throttle ~500+/min. Current usage (~50 symbols/run) is fine
7. **MSYS path conversion bug**: Git Bash on Windows converts `/X` to `C:/Program Files/Git/X` when passed to Windows executables. Use PowerShell tool for those calls or escape with `MSYS_NO_PATHCONV=1`
8. **WebFetch fails on SEC** (403) — use Bash curl with email User-Agent
9. **Saturday/Sunday dashboard data should not exist** — markets closed. If they appear, they were saved with wrong date

---

## 8. URLs / Endpoints

| Service | URL |
|---|---|
| Live dashboard | https://chi2tseng.github.io/stocks-in-play/ |
| GitHub repo | https://github.com/chi2tseng/stocks-in-play |
| Skill install | `npx skillfish add chi2tseng/stocks-in-play SIPs` |
| Local sidecar (when running) | http://127.0.0.1:5510 (for Studies edit mode) |
| Yahoo chart API (used by fetch_candles.py) | `https://query1.finance.yahoo.com/v8/finance/chart/<SYM>?period1=<unix>&period2=<unix>&interval=1d` |
| Barchart pre-market | `https://www.barchart.com/stocks/pre-market-trading/percent-change/{advances,declines}` |
| Barchart post-market | `https://www.barchart.com/stocks/post-market-trading/percent-change/{advances,declines}` |
| SEC EDGAR browse | `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=<CIK>&type=<FORM>&count=10` |

---

## 9. Memory Files (key references for future sessions)

Located in `C:\Users\chi2t\.claude\projects\C--Users-chi2t-Downloads\memory\`:

- `reference_sips_dashboard.md` — Dashboard overview + paths
- `reference_playwright_barchart.md` — Barchart Shadow DOM workaround (XHR intercept on `/proxies/core-api/v1/quotes/get`)
- `reference_playwright_tv.md` — TradingView Playwright scraper
- `reference_firecrawl.md` — Firecrawl CLI + TradingView FQ URL trick
- `feedback_sips_auto_push.md` — Standing auto-push approval
- `feedback_verify_render_after_data_changes.md` — Verify end-to-end render after data changes
- `reference_dev_env.md` — Windows runtimes (Node v24, Deno, Python 3.14; use npm.cmd/npx.cmd in PowerShell)

---

## 10. What to do FIRST in your new session

1. Read this whole doc
2. Run `cd /d/SIPs && git log --oneline -5` to see latest commits (should start with `0c7876f`)
3. Check current dashboard data state: `ls dashboard/data/` (expect 5/14, 5/15, 5/18, 5/19)
4. Decide what to work on:
   - If user asks about **today's pending work** → check §3 Pending Tasks
   - If user asks to **continue from a specific spot** → ask which, then load relevant context
5. **Always verify after changes** — open the live dashboard or check the build output before saying "done"
6. **When in doubt about a CSS token**, grep for it: `grep -n "--surface" dashboard/index.html`

Good luck. The user is sharp and notices regressions — be precise, push often, verify end-to-end.
