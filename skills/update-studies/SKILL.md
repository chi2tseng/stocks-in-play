---
name: update-studies
description: AI-driven daily Studies OHLCV refresh for the Stocks In Play (SIPs) dashboard. Reads `D:\SIPs\dashboard\studies\studies.json`, fetches Yahoo Finance daily bars for every study with `ohlcv.date` filled, and writes back open/high/low/close/prev_close/volume so each Study's day-chg, move, gain, stop, and chart-focus stay current. Use when the user types `/update-studies`, says "refresh studies", "update my OHLCV", "pull today's prices for my studies", "sync studies", or asks to schedule a daily Studies refresh. Companion to the larger `/SIPs` skill — `/SIPs` does the full scrape + classification of new candidates; `/update-studies` is the lightweight daily price-only refresh of already-saved Studies.
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

## § 3. Write back

Use the **Edit** tool to update `studies.json` — one Edit per study's `ohlcv` block
(atomic per study), or one big Write of the full updated array. Either way it's a
single fs operation per study.

Then print a per-study summary:
```
[OK] Refreshed N studies:
  · FIG  @ 2026-05-15  open 22.60 → 23.10  close 22.85 → 23.42  prev_close — → 22.10
  · ARM  @ 2026-05-29  (no changes — already current)
  · ONDS @ 2026-05-14  (fallback from empty date → snapshot.scanDate)
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
- Number skipped (no date / future / fetch failed)
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
