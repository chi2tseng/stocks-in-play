---
name: update-studies
description: AI-driven daily Studies refresh for the Stocks In Play (SIPs) dashboard — OHLCV + News + TradingView quarterly forecasts (for earnings-tagged tickers). Reads `D:\SIPs\dashboard\studies\studies.json` and, for every study with `ohlcv.date` (or `snapshot.scanDate` fallback), pulls fresh Yahoo daily bars, recent Yahoo news headlines, and — if the study has the `earnings` catalyst tag — runs the same TradingView FQ scrape `/SIPs` uses (`tv-scrape.js` + `parse_tv.py`) to refresh EPS / Sales reported+estimate, Forward YoY, and the editable MS table. Writes back open/high/low/close/prev_close/volume, snapshot.last (= close), snapshot.newsDetail/catalyst (only if currently empty), and snapshot.tv (only for earnings studies). Use when the user types `/update-studies`, says "refresh studies", "update my OHLCV", "pull today's prices and news for my studies", "sync studies", or asks to schedule a daily Studies refresh. Companion to the larger `/SIPs` skill — `/SIPs` does the full daily candidate discovery + classification; `/update-studies` is the per-Study refresh of price + news + (optional) earnings data.
allowed-tools: Bash, Read, Edit, Write
---

# update-studies — daily Studies OHLCV refresh

You are running an unattended daily-refresh workflow over the user's Studies library at
`D:\SIPs\dashboard\studies\studies.json`. For every study with `ohlcv.date` filled (or a
non-empty `snapshot.scanDate` fallback if `ohlcv.date` is empty — see §1.4 below), fetch
fresh OHLCV from Yahoo Finance for that specific trading day and write it back.

Use the **Read / Edit / Bash** tools directly. **Do NOT shell out to a Python script** —
the user explicitly asked for an AI-driven workflow. Each step below is a tool call.

---

## § 1. Boot

1. **Read** `D:\SIPs\dashboard\studies\studies.json`.

2. Parse the JSON. The file is a top-level array of study objects:
   ```json
   [
     { "id": "FIG-...", "symbol": "FIG",
       "ohlcv": { "date": "2026-05-15", "open": ..., "high": ..., "low": ..., "close": ..., "prev_close": ..., "volume": ... },
       "snapshot": { "scanDate": "2026-05-15", ... }, "notes": ..., "customChart": ..., ... }
   ]
   ```

3. **Collect targets** — every study where either:
   - `ohlcv.date` is a non-empty string, OR
   - `ohlcv.date` is empty AND `snapshot.scanDate` is a non-empty string (fallback —
     see §1.4 below).

   Skip studies whose effective date is in the future (Yahoo has no data yet) — log
   `[warn] <SYM>: date <date> is in the future, skipping` and continue.

4. **Empty-date fallback** — if `ohlcv.date` is empty but `snapshot.scanDate` is set,
   use `snapshot.scanDate` as the target trading day AND write it back into
   `ohlcv.date` so subsequent runs hit the exact-date path. Log the fallback:
   `[info] <SYM>: empty ohlcv.date, falling back to snapshot.scanDate <date>`.

5. **Announce the run** in a single line:
   `Refreshing N studies (SYM₁ on date₁, SYM₂ on date₂, …)`.

## § 2. Fetch loop

For **each** target study, do the following:

### 2a. Compute the Yahoo URL

Yahoo Finance's chart endpoint takes Unix timestamps. For `target_date` (YYYY-MM-DD):

- `period1` = (target_date as UTC midnight) − 10 days, as Unix seconds. Gives ~7 trading
  days of prior context so `prev_close` is reliable even when target is the Monday after
  a long weekend.
- `period2` = (target_date as UTC midnight) + 2 days, as Unix seconds.

URL pattern:
```
https://query1.finance.yahoo.com/v8/finance/chart/<TICKER>?period1=<p1>&period2=<p2>&interval=1d
```

### 2b. Fetch via Bash

Use Python's `urllib` inline (`py -c "..."`) instead of `curl` + separate JSON parser
— Windows-friendly, no `jq` dependency, gets you a clean list of bars in one Bash call:

```bash
py -c "
from datetime import datetime, timezone
import urllib.request, json, sys
target = 'TARGET_DATE_HERE'        # e.g. '2026-05-14'
sym    = 'TICKER_HERE'             # e.g. 'ONDS'
t = datetime.strptime(target, '%Y-%m-%d').replace(tzinfo=timezone.utc)
p1 = int(t.timestamp()) - 10*86400
p2 = int(t.timestamp()) + 2*86400
url = f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}&interval=1d'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=15) as r: d = json.load(r)
res = d['chart']['result'][0]
ts = res['timestamp']
q  = res['indicators']['quote'][0]
bars = [{
    'date': datetime.fromtimestamp(t_, tz=timezone.utc).strftime('%Y-%m-%d'),
    'open': q['open'][i],  'high': q['high'][i],  'low': q['low'][i],
    'close': q['close'][i],'volume': q['volume'][i]
} for i, t_ in enumerate(ts)]
print(json.dumps(bars, indent=2))
"
```

(This is a JSON adapter, NOT a script — it reshapes the Yahoo response inline so you can
read it. No separate `.py` file involved.)

### 2c. Resolve the target bar

From the returned array of bars:

1. **Exact match** — find the bar where `date == target_date`. If found, use it.
2. **Weekend / holiday fallback** — if no bar matches the exact date, find the bar
   with the latest date ≤ target. Log: `[info] <SYM>: no bar for <target>; using
   nearest prior <fallback>`.
3. **prev_close** — the close of the bar IMMEDIATELY BEFORE the matched bar in the
   returned array. If the matched bar is the first one returned, `prev_close` stays null.
4. **Round** open/high/low/close/prev_close to 2 decimals (Yahoo returns float noise);
   keep volume as integer.

### 2d. Build the patch

Apply these field updates to `study.ohlcv`:

| Field         | New value |
|---------------|-----------|
| `date`        | the matched bar's date (normalized to `YYYY-MM-DD`) |
| `open`        | matched bar's `open`, rounded to 2 dp |
| `high`        | matched bar's `high`, rounded to 2 dp |
| `low`         | matched bar's `low`,  rounded to 2 dp |
| `close`       | matched bar's `close`, rounded to 2 dp |
| `prev_close`  | close of the bar immediately before, rounded to 2 dp |
| `volume`      | matched bar's `volume` (integer) |

**Never** modify any other study field. Leave alone: `notes`, `customChart`,
`customTypes`, `intent`, `price`, `snapshot`, `screenshots`, `id`, `savedAt`,
`hiddenSections`. **Only** the `ohlcv` subtree changes.

### 2e. Throttle

After each fetch wait ~250 ms before the next one so Yahoo doesn't rate-limit a 30+
ticker library. Either `sleep 0.25` in Bash or rely on Claude's natural per-tool-call
cadence — both are acceptable.

## § 2f. Sync display price

After successfully writing OHLCV, set `study.snapshot.last = study.ohlcv.close` so the
big price readout in the header + every preview card uses the official daily close.
This OVERWRITES any prior `snapshot.last` (it was the scan-time price, which is stale
by now). The user's manual override `study.price` is NOT touched — that still wins
on display.

## § 2g. News refresh (always)

For every study just processed, fetch fresh news headlines from Yahoo's search API:

```bash
py -c "
import urllib.request, json
sym = 'TICKER_HERE'
url = f'https://query1.finance.yahoo.com/v1/finance/search?q={sym}&newsCount=8&quotesCount=0&enableFuzzyQuery=false'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=15) as r: d = json.load(r)
for n in (d.get('news') or []):
    print(f\"  {n.get('publisher')} | {n.get('title')} | {n.get('link')}\")
"
```

From the headlines, compose a `newsDetail` block in **繁體中文** matching the /SIPs
format — see `/SIPs` Phase 7 + `docs/NEWS_TIME_SPEC.md` for the exact style. Roughly:

1. Lead with the catalyst (date + event): `"5/13 Q1 2026 業績電話會議 ..."`
2. 1–3 supporting facts in **bold** (EPS / Revenue surprise, analyst PT raises, etc.)
3. Short forward-looking analysis paragraph (downside risk + setup quality).

Also compose a one-liner `catalyst` (≤200 chars) suitable for the preview-card teaser.

**Respect user edits**: only WRITE `snapshot.catalyst` and `snapshot.newsDetail` if
they're currently EMPTY (`null` or `""`). If the user has manually edited the news
detail on the study page, DO NOT overwrite — log `[info] <SYM>: keeping existing
newsDetail` and continue.

## § 2h. TradingView FQ refresh (earnings studies only)

If the study has `"earnings"` in `customTypes` (case-insensitive), refresh its
TradingView FQ block — same flow `/SIPs` uses at Phase 5–6:

1. **Scrape**: `node tv-scrape.js <SYMBOL>` from the repo root. Writes
   `<SYMBOL>-earnings-fq.md` to the repo dir. Takes ~30-60 s per ticker via Playwright.
2. **Parse**: `py parse_tv.py <SYMBOL>` (or just `py parse_tv.py` to refresh all). Writes
   `tv-summary.json`.
3. **Extract**: read `tv-summary.json`, find the row with `Ticker == <SYMBOL>`.
4. **Convert** the Python keys to the JS schema used in `study.snapshot.tv`:
   ```
   LatestEPS              → latestEPS
   LatestEPSConsensus     → consensusEPS
   PriorYrEPS             → priorYrEPS
   LatestEPSSurprise_pct  → surpriseEPS_pct
   LatestEPS−Consensus    → surpriseEPS_dollar     (computed)
   LatestRev_M            → latestRev_M
   LatestRevConsensus_M   → consensusRev_M
   PriorYrRev_M           → priorYrRev_M
   LatestRevSurprise_pct  → surpriseRev_pct
   (rev YoY %)            → yrYrRev_pct            (computed)
   (eps YoY %)            → epsYoY_pct             (computed)
   EpsEst_Next4           → epsEst_next4
   RevEst_Next4           → revEst_next4
   YoYBlock               → yoyBlock
   Chart                  → chart                  (verbatim)
   ```
5. **Write** to `study.snapshot.tv`. Also:
   - If `study.snapshot._placeholder` was `true`, REMOVE that flag (we now have real data).
   - From `study.hiddenSections`, REMOVE `eps_chart` / `rev_chart` / `ms_table` /
     `yoy_block` so the dashboard surfaces the freshly-filled sections.

For NON-earnings studies, skip this step entirely — TV scrape is expensive (Playwright)
and unrelated to non-earnings catalysts (M&A, FDA, contract, technical, FBO, etc.).

A complete patch for an earnings study looks like:

```python
import json, subprocess
subprocess.run(['node', 'tv-scrape.js', SYM], check=True, cwd='D:/SIPs')
subprocess.run(['py', 'parse_tv.py', SYM], check=True, cwd='D:/SIPs')
with open('D:/SIPs/tv-summary.json', encoding='utf-8') as f:
    tv_rows = json.load(f)
tv_row = next((r for r in tv_rows if r['Ticker'] == SYM), None)
if tv_row:
    study['snapshot']['tv'] = build_js_schema(tv_row)
    study['snapshot'].pop('_placeholder', None)
    study['hiddenSections'] = [s for s in study.get('hiddenSections', [])
                                if s not in ('eps_chart','rev_chart','ms_table','yoy_block')]
```

## § 3. Write back

Use the **Edit** tool to update `studies.json` — one Edit per study's `ohlcv` block
(atomic per study), or one big Write of the full updated array. Either way it's a
single fs operation per study.

Then print a per-study summary (mention what was touched: OHLCV / news / TV / price):
```
[OK] Refreshed N studies:
  · FIG  @ 2026-05-15  OHLCV + news + TV + last → 23.42
  · ARM  @ 2026-05-29  OHLCV only (no earnings tag, newsDetail already filled)
  · ONDS @ 2026-05-14  last → 11.21 (everything else preserved)
  · NBIS @ 2026-05-13  OHLCV + news + TV + last → 207.27 (placeholder → filled)
```

## § 4. Optional follow-up

After the write, **ask the user** before doing either of these (don't auto-trigger):

- Regenerate the static dashboard: `py D:\SIPs\build_dashboard.py`. Needed if the
  hosted Pages mirror should pick up the new OHLCV in the next deploy.
- Commit + push:
  ```bash
  git add dashboard/studies/studies.json
  git commit -m "studies: daily OHLCV refresh"
  git push
  ```
  Pushes the new JSON to GitHub so the hosted dashboard shows fresh numbers on the
  user's phone too.

## § 5. Error handling

| Failure | Action |
|---|---|
| Yahoo HTTP 4xx/5xx for a single ticker | log `[warn] <SYM>: Yahoo HTTP <code>`, skip, continue |
| Empty bars array (delisted / suspended ticker) | log `[warn] <SYM>: no bars in window`, skip |
| No bar at-or-before target in the 10d window | retry once with `period1` further back (-30 d), then warn + skip |
| Connection timeout | retry once after 5 s, then warn + skip |
| `studies.json` missing or unparseable | abort the whole run, do NOT write back |

Per-ticker failures NEVER abort the run — finish all the other tickers first.

## § 6. Final summary

Report concisely (6–12 lines):
- Total studies in the library
- Number with effective date (after empty-date fallback)
- Number actually updated (had ≥ 1 field change)
- Of those, how many got TV refresh (= earnings-tagged) and how many got fresh news
- Number skipped (no date / future / fetch failed)
- Any placeholder studies that just got fully filled
- Any fallback / warning lines worth surfacing

---

## Schema reference

```json
{
  "id":     "FIG-lhc4x9zabc",
  "symbol": "FIG",
  "savedAt": "2026-05-15T18:00:00Z",
  "ohlcv": {
    "date":       "2026-05-15",
    "open":       22.60,
    "high":       24.10,
    "low":        22.45,
    "close":      23.85,
    "prev_close": 22.10,
    "volume":     18200000
  },
  "snapshot": {
    "scanDate": "2026-05-15",
    "...": "left alone"
  },
  "notes":       "<p>...</p>",   // left alone
  "customChart": { },            // left alone
  "intent":      "long",         // left alone
  "price":       null,           // left alone
  "...":         "everything else also left alone"
}
```

## Date format normalization

Accept these date formats from existing studies:
- `2026-05-15` (ISO — preferred)
- `05/15/2026` (US)
- `2026/05/15` (Asian)

Always WRITE back in ISO format (`YYYY-MM-DD`) regardless of what was there before.

## Companion to /SIPs

- **`/SIPs`** — the full daily scan: scrapes Barchart pre+post-market gappers, classifies
  MAGNA53, pulls TV quarterly forecasts, writes a 繁體中文 brief, regenerates dashboard.
  Heavy weight, ~5 minutes, hits 5 different data sources.
- **`/update-studies`** *(this skill)* — lightweight OHLCV-only refresh for studies the
  user has ALREADY saved. Doesn't touch newcandidates / catalysts / Claude picks.
  Schedule this daily, schedule `/SIPs` as the morning ritual.
