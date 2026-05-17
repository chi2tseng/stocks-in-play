---
name: update-studies
description: Daily local refresh of the Studies library (`D:\SIPs\dashboard\studies\studies.json`) — same flow as /SIPs but per-existing-study instead of new-candidate-discovery. For every study with an effective trading-day date (ohlcv.date, or snapshot.scanDate as fallback), refreshes OHLCV (Yahoo chart API), composes News Detail in 繁體中文 (same sourcing pattern as /SIPs Phase 7 — WebFetch / firecrawl / press release), syncs snapshot.last to the closing price, AND — for studies tagged with `earnings` in customTypes — re-runs the SIPs TV scrape pipeline (tv-scrape.js → parse_tv.py) to refresh EPS / Sales Reported+Estimate, Surp%, Forward YoY, and the chart for the editable MS table. Closes with `py build_dashboard.py` + `git add/commit/push` so the hosted Pages mirror stays current. Trigger phrases: `/update-studies`, "refresh studies", "update my studies", "pull today's data for my studies", "sync studies", "refresh OHLCV and news for studies". Companion to `/SIPs` — `/SIPs` discovers TODAY's candidates; this skill refreshes everything you've ALREADY saved.
allowed-tools: Bash, Read, Edit, Write, WebFetch, WebSearch
---

# update-studies — local daily refresh of the Studies library

**Runs locally on the user's Windows machine.** Mirrors the `/SIPs` workflow but scoped to
the existing `dashboard/studies/studies.json` library — i.e. price + news + (optional) TV
quarterly data for studies the user has already saved. End state: studies.json updated +
`build_dashboard.py` regenerated + git pushed.

Designed to be invoked manually (`/update-studies`) or wired into an end-of-day routine.
Not a cloud agent — TV scrape needs Playwright locally, and news composition needs
Claude's judgment.

## § Mode flags (arg parsing)

**Auto-rebuild + auto-push is the default.** Every successful run finishes with
`py build_dashboard.py` + `git add/commit/push` automatically (per the user's standing
"make everything push after executing both /SIPs and /update-studies" instruction). The
only way to skip git is `dry-run`.

| Arg | Effect |
|---|---|
| _(none)_ | **Default: blanks only + auto rebuild + auto push.** Skip studies whose OHLCV bar is fully filled. Skip TV scrape for earnings studies whose `snapshot.tv` is already present. Only `newsDetail` / `catalyst` blanks get composed. Manual data is sacred. Run finishes with `build_dashboard.py` + `git push`. |
| `safe` | Explicit alias for the default. Kept for backwards compatibility. |
| `refresh` | **Force overwrite.** Re-fetch every study's OHLCV at its `ohlcv.date` and OVERWRITE existing values. Re-run TV scrape for every earnings-tagged study (including ones with a filled `snapshot.tv`). Useful after the user changes a study's date pill, or after a company has reported a new quarter since the last refresh. News is still only filled if empty (manual user-edits to newsDetail are NEVER overwritten — even in refresh mode). Still auto-rebuilds + pushes. |
| `dry-run` | Print the planned diff but don't write back, don't rebuild, don't push. Useful for previewing what `refresh` would change before committing to it. |
| `sym SYM1 SYM2 ...` | Restrict to specific tickers. Combinable with the other modes (e.g. `/update-studies refresh sym AMD FIG`). |

The skill matches these flags in natural language (e.g. "refresh AMD", "update studies in safe mode for FIG and ARM").

---

## § Resources

Mirror `/SIPs`'s resource map exactly. Don't introduce new data sources unless the user
explicitly asks:

| Layer | Source | How |
|---|---|---|
| OHLCV (daily bars) | Yahoo Finance `chart` API | `https://query1.finance.yahoo.com/v8/finance/chart/<SYM>?...` — same as `/SIPs` Phase 10b |
| TradingView FQ (earnings only) | `tv-scrape.js` + `parse_tv.py` | Playwright scrape → markdown → `tv-summary.json` — same as `/SIPs` Phase 5–6 |
| News Detail (繁體中文) | WebFetch / WebSearch / firecrawl | Whatever surface you find the headline + body on (Yahoo Finance, Investor's Business Daily, Reuters, company IR pages, SEC filings, etc.) — same pattern as `/SIPs` Phase 7. Use `docs/NEWS_TIME_SPEC.md` for `publishedAt` formatting if you decide to include a timestamp |
| Static dashboard build | `D:\SIPs\build_dashboard.py` | Same as `/SIPs` Phase 10 |
| Git publish | `git add / commit / push` | Same as `/SIPs` Phase 11 |

The Playwright scrapers (`tv-scrape.js`, `barchart-scrape.js`) are already installed at the
repo root from the parent `/SIPs` skill — just call them.

---

## § Phase 1 — Read + classify

1. `Read` `D:\SIPs\dashboard\studies\studies.json`. If missing or unparseable, ABORT
   (do not write back).
2. For each study, determine the **effective target date**:
   - `study.ohlcv.date` if non-empty, else
   - `study.snapshot.scanDate` if non-empty (and plan to write it back into
     `ohlcv.date` so subsequent runs skip the fallback path), else
   - **skip this study** (no date to query).
3. Skip studies whose effective date is in the **future** UTC (Yahoo has no data yet).
4. Classify each remaining study:
   - **`earnings`** = has `"earnings"` (case-insensitive) in `customTypes` array.
     Triggers the full TV refresh in Phase 3 below.
   - **non-earnings** = everything else. Gets OHLCV + News only.
5. Announce in one line:
   `Refreshing N studies: M with earnings tag (full refresh), K non-earnings (OHLCV+news).`

## § Phase 2 — OHLCV refresh (default: blanks only, opt-in to overwrite)

**Default behaviour = safe / blanks only.** For each study, only fetch + write the OHLCV
bar if at least one of `ohlcv.{open,high,low,close,prev_close,volume}` is `null`. If the
study already has a complete bar, skip the Yahoo call — manual data is sacred and we
don't second-guess it. This matches `/SIPs` Phase 10b's "manual data is sacred" rule.

**To force a re-fetch on filled studies**, pass the `refresh` arg (e.g.
`/update-studies refresh` or `/update-studies for AMD refresh`). In refresh mode, every
study gets a fresh Yahoo bar pulled at its `ohlcv.date` and the result OVERWRITES the
existing values. Use this when the user manually changed `ohlcv.date` via the date pill
(so the old bar is for the wrong day) or when they want today's closing price written
back into a study that still holds a stale earlier-in-the-day quote.

**`safe` arg = explicit alias for the default** (kept for backwards compatibility with
phrases like "/update-studies safe mode").

Same code path as `/SIPs` Phase 10b but per-study, with the per-study target date instead
of "yesterday". For each target study (that qualifies under the mode above):

```bash
py -c "
from datetime import datetime, timezone
import urllib.request, json, sys
target = 'TARGET_DATE'   # YYYY-MM-DD
sym    = 'TICKER'
t = datetime.strptime(target, '%Y-%m-%d').replace(tzinfo=timezone.utc)
p1 = int(t.timestamp()) - 10*86400
p2 = int(t.timestamp()) + 2*86400
url = f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}&interval=1d'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=15) as r: d = json.load(r)
res = d['chart']['result'][0]
ts = res['timestamp']; q = res['indicators']['quote'][0]
bars = [{
    'date': datetime.fromtimestamp(t_, tz=timezone.utc).strftime('%Y-%m-%d'),
    'open': round(q['open'][i],2),  'high': round(q['high'][i],2),
    'low':  round(q['low'][i],2),   'close': round(q['close'][i],2),
    'volume': int(q['volume'][i]) if q['volume'][i] is not None else None
} for i, t_ in enumerate(ts) if q['open'][i] is not None and q['close'][i] is not None]
print(json.dumps(bars, indent=2))
"
```

Resolve target bar:
- Exact match `date == target` → use it.
- Else nearest bar with `date <= target` → use it. Log: `[info] SYM: no bar for TARGET; using nearest prior FALLBACK`.
- `prev_close` = close of the bar immediately before the matched bar in the returned array.
- Round prices to 2dp, volume to integer.

Write back to `study.ohlcv`: `{date, open, high, low, close, prev_close, volume}`.

**Also sync the price**: `study.snapshot.last = study.ohlcv.close`. The big price readout
in the header + every preview card uses this, so it should reflect the official daily
close (was previously the stale scan-time price). `study.price` (manual override) still
wins on display.

**Also sync chgPct**: `study.snapshot.chgPct = (close − prev_close) / prev_close * 100`.
The header chg %, the preview card chg %, and the intent-default rule (next paragraph)
all read this. Without the sync, fresh OHLCV would leave chgPct stale.

**Default the trade intent from the gap direction.** ONLY when `study.intent` is null /
undefined (the user hasn't manually set a direction) — never overwrite an existing
intent, even in `refresh` mode. The rule:

| chgPct after sync | study.intent default |
|---|---|
| > 0 (gap up) | `'long'` |
| < 0 (gap down) | `'short'` |
| 0 or null | leave unset |

This is what makes a fresh study auto-classify based on the scan day's gap direction.
Users who want to override (e.g., shorting a gap-up reversal) just click the LONG/SHORT
pill on the detail page — that becomes the manual override and we never touch it again.

```python
# Pseudo-code that runs right after writing ohlcv + snapshot.last + snapshot.chgPct:
if study.get('intent') is None and snap.get('chgPct') is not None:
    chg = snap['chgPct']
    if chg > 0:    study['intent'] = 'long'
    elif chg < 0:  study['intent'] = 'short'
    # zero is a no-op — wait for the user to decide
```

## § Phase 3 — TradingView FQ refresh (earnings studies, default: blanks only)

**Default behaviour = safe / blanks only.** For each study with `"earnings"` in
`customTypes`, only run the TV scrape if `snapshot.tv` is missing, empty, or carries
`snapshot._placeholder: true`. If `snapshot.tv` already has the full chart + summary
block, skip the scrape entirely — the user either filled it via a previous run or
manually curated it, both of which take precedence over a re-scrape.

**`refresh` arg also forces TV re-scrape** on filled earnings-tagged studies. Use this
when the company has reported a NEW quarter since the last refresh (e.g. AMD reported
Q1 '26 on May 5 — running `/update-studies refresh for AMD` after that pulls the new
quarter into the chart). Without `refresh`, an already-filled TV block is left alone.

For each qualifying earnings study, mirror `/SIPs` Phase 5–6:

```bash
cd /d/SIPs && node tv-scrape.js <SYM>          # Playwright, ~30-60s
cd /d/SIPs && py parse_tv.py <SYM>             # parses *.md → tv-summary.json
```

Then read `tv-summary.json`, find the row with `Ticker == SYM`, convert from the parse
script's Python keys to the JS schema used in `study.snapshot.tv`:

| Python (parse_tv) | JS (snapshot.tv) | Notes |
|---|---|---|
| `LatestEPS` | `latestEPS` | float |
| `LatestEPSConsensus` | `consensusEPS` | float |
| `PriorYrEPS` | `priorYrEPS` | float |
| `LatestEPSSurprise_pct` | `surpriseEPS_pct` | float |
| — | `surpriseEPS_dollar` | computed: `latestEPS − consensusEPS` |
| `LatestRev_M` | `latestRev_M` | float, millions |
| `LatestRevConsensus_M` | `consensusRev_M` | float, millions |
| `PriorYrRev_M` | `priorYrRev_M` | float, millions |
| `LatestRevSurprise_pct` | `surpriseRev_pct` | float |
| — | `yrYrRev_pct` | computed: `(latestRev_M − priorYrRev_M) / abs(priorYrRev_M) * 100` |
| — | `epsYoY_pct` | computed: `(latestEPS − priorYrEPS) / abs(priorYrEPS) * 100` |
| `EpsEst_Next4` | `epsEst_next4` | array of 4 floats |
| `RevEst_Next4` | `revEst_next4` | array of 4 floats |
| `YoYBlock` | `yoyBlock` | multi-line string, verbatim |
| `Chart` | `chart` | object verbatim — `{quarters, eps_reported, eps_estimate, rev_reported_M, rev_estimate_M, latest_idx}` |

Write the converted block to `study.snapshot.tv`. Also:

- If `study.snapshot._placeholder` is `true`, **remove the flag** (we now have real data).
- From `study.hiddenSections`, **remove** `eps_chart` / `rev_chart` / `ms_table` /
  `yoy_block` so the dashboard surfaces the freshly-filled sections.
- If `study.snapshot.name` is empty, set it from `parse_tv` row name (some scrape outputs
  include the company name in the header; otherwise leave blank — name isn't critical).

**Non-earnings studies skip this phase entirely.** TV scrape is expensive and irrelevant
to M&A / FDA / contract / technical / FBO / short-squeeze / etc.

## § Phase 3b — Historical-quarter rewind (CRITICAL for past earnings dates)

TradingView's FQ scrape always returns the **latest** quarter as `latest_idx`. If the
study's target date is in the **past** (e.g., AMD @ 2026-02-04 for Q4 '25 earnings), the
scrape will mark Q1 '26 as the reported latest — but at the time of the catalyst, **Q4
'25 was the latest reported quarter**. The MS table, EPS/Rev charts, and Forward YoY
must anchor at THAT historical quarter, not today's latest.

After Phase 3 writes the scraped `chart` block, **rewind**:

1. **Determine the target quarter** — the most-recent quarter that had been reported as
   of `study.ohlcv.date`. Heuristic: for each quarter label in `chart.quarters`, compute
   its end date (`Q1` → Mar 31, `Q2` → Jun 30, `Q3` → Sep 30, `Q4` → Dec 31). Then add
   the company's typical **report lag**:
   - **~30 days** for most large-caps (AMD, NVDA, INTC, AAPL, MSFT, GOOG, META)
   - **~45 days** for smaller / less-mature companies (ONDS, NBIS, etc.) — they have
     fewer auditors and report slower
   - When unsure, look at the **previous quarter's actual report date** for the same
     ticker (search news for `<TICKER> Q[1-4] 20[0-9][0-9] earnings`) and use that lag.
     Example: AMD reported Q3 '25 on Nov 4 2025 (35 days), Q2 '25 on Aug 5 2025 (36
     days) → use ~34 days for Q4 '25 estimate.

   A quarter is "reported by target" iff
   `(quarter_end + report_lag_days) <= study.ohlcv.date`.

   Choose the **highest-index** quarter that passes — call this `target_idx`.

2. **If `target_idx == chart.latest_idx`** (study date is current — most common case):
   no rewind needed. Skip the rest of this phase.

3. **Otherwise rewind**:
   - For every `i > target_idx`:
     - `chart.eps_reported[i] = null`
     - `chart.rev_reported_M[i] = null`
   - `chart.latest_idx = target_idx`
   - Set `study.focusQuarterIdx = target_idx` so the MS table window + bar chart
     highlight + Forward YoY all anchor there.

4. **Recompute the tv summary fields** from the rewound chart:
   - `latestEPS` = `eps_reported[target_idx]`
   - `consensusEPS` = `eps_estimate[target_idx]`
   - `priorYrEPS` = `eps_reported[target_idx - 4]` (same quarter, prior year)
   - `surpriseEPS_pct` = `(latestEPS − consensusEPS) / abs(consensusEPS) * 100`
   - `surpriseEPS_dollar` = `latestEPS − consensusEPS`
   - `latestRev_M`, `consensusRev_M`, `priorYrRev_M`, `surpriseRev_pct` — same pattern
   - `yrYrRev_pct` = `(latestRev_M − priorYrRev_M) / abs(priorYrRev_M) * 100`
   - `epsYoY_pct` = `(latestEPS − priorYrEPS) / abs(priorYrEPS) * 100`
   - `epsEst_next4` = `eps_estimate[target_idx+1 .. target_idx+4]` (forward 4)
   - `revEst_next4` = `rev_estimate_M[target_idx+1 .. target_idx+4]`
   - `yoyBlock`: rebuild with target_idx as the header line, then 4 forward lines

5. **Note on estimate accuracy** — Forward 4 estimates from TV are the CURRENT
   consensus, not the at-the-time consensus from the historical date. Document this
   limitation in newsDetail (use a `> ⚠️` blockquote like the AMD@2026-02-04 entry):
   `> 表格中的 forward 4 季 estimates 是 TradingView 目前的 consensus，並非 <DATE> 當時的數字`.
   The historical reported actuals are accurate; the forward estimates drift.

**Verified example — AMD @ 2026-02-04** (Q4 '25 earnings reported 2/3):
- Q4 '25 end = Dec 31 2025; lag ~34d → cutoff = Feb 3 ≤ Feb 4 ✓ (reported)
- Q1 '26 end = Mar 31 2026; lag ~34d → cutoff = May 4 > Feb 4 ✗ (not yet reported)
- → `target_idx = 6` (Q4 '25)
- → `eps_reported[6] = 1.53, rev_reported_M[6] = 10270`, `eps_reported[7+] = null`
- → `latestEPS = 1.53, consensusEPS = 1.32, priorYrEPS = 1.09` (Q4 '24)
- → `surpriseEPS_pct = +15.91%`, `epsYoY_pct = +40.37%`

## § Phase 4 — News Detail refresh + earnings auto-detect

Same sourcing approach as `/SIPs` Phase 7. The user explicitly asked for this — they
want the news to be FRESH per-study, not stale from when they first saved the study.

For each study (regardless of tag):

1. **Source**: pick whichever is most appropriate for the ticker + date:
   - `WebSearch` for `<TICKER> <date>` to find the day's headline
   - `WebFetch` on company IR pages, SEC filings, Yahoo Finance news, Reuters, etc.
   - `firecrawl` for paywalled / JS-heavy pages

2. **Earnings auto-detect** (NEW — runs BEFORE composing the newsDetail):
   Scan the headlines + summary text returned in step 1 for any of these signals:
   - `Q[1-4] 20\d\d earnings` / `Q[1-4] FY20\d\d earnings`
   - `reported earnings` / `posts Q[1-4]`
   - `earnings call` / `earnings report` / `earnings release`
   - `EPS beat` / `EPS miss` / `revenue beat` / `revenue miss`
   - `業績電話會議` / `Q[1-4] .* 業績` (繁體中文)
   - The TARGET DATE matching the company's known earnings calendar date (Alphabet,
     AMD, Microsoft, etc. — well-known reporters)

   If ANY of those signals fire AND `"earnings"` is NOT in `customTypes`:
   - **Add `"earnings"`** to the study's `customTypes` array
   - Log: `[info] SYM: news indicates earnings catalyst on TARGET_DATE — auto-tagging`
   - **Jump back to Phase 3** for THIS study and run the TV scrape (tv-scrape.js +
     parse_tv.py). Then continue with Phase 4 step 3 below.

   Do NOT auto-add the tag if the news is unrelated to earnings (e.g., M&A
   announcement, FDA news, contract win) — even if the date happens to coincide
   with the company's earnings calendar. The signal MUST be present in the actual
   headlines for the target date.

3. **Compose** a `newsDetail` block in **繁體中文 markdown** matching the /SIPs Phase 7
   style:
   - Lead: `<date> <時段> <event>` (e.g. "5/13 Q1 2026 業績電話會議後")
   - 1–3 supporting facts in **bold** (`**EPS $X** vs $Y`)
   - Short forward-looking analysis paragraph (downside / setup quality)
   - Paragraphs separated by `\n\n`

4. **Compose** a one-liner `catalyst` (≤200 chars) for the preview-card teaser.

5. **Record source URLs** in `study.snapshot.sources` (REQUIRED whenever you compose new
   `newsDetail`): an array of `{ label, url, publishedAt? }` objects pointing to the
   ORIGINAL articles / filings / press releases you consulted while writing the body.
   Same rules as /SIPs Phase 7's `sources` field:
   - 1-4 entries, most authoritative first
   - Priority order: company IR / SEC filings → Reuters/Bloomberg/WSJ → Briefing.com /
     TheFly → Yahoo Finance → industry trade press
   - NEVER use Reddit / Twitter / Stocktwits as primary
   - `label` should be human-readable (e.g. "Reuters — AMD Q4 2025 results"); hostname is
     the rendering fallback if `label` is missing
   - `url` must be a stable permalink, not a search result page

   The dashboard renders these as small clickable pills below the news-detail body
   (`新聞來源 · Sources` section, opens in new tab). When the user wants to verify a
   big-number claim like "+57.7% EPS surprise" or "Citi PT $169 → $287", one click on
   the source pill opens the original article.

6. **Respect user edits**: only WRITE `snapshot.newsDetail` / `snapshot.catalyst` /
   `snapshot.sources` if they're currently **empty** (`null` or `""` / empty array). If
   the user has manually edited either, log `[info] SYM: keeping existing news` and
   skip. The reason: the user's hand-curated version is usually better than auto-fetched.

`docs/NEWS_TIME_SPEC.md` is the canonical contract for news formatting. Read it before
writing news_detail-style content if you need to include `publishedAt`.

## § Phase 5 — Atomic write

**BEFORE writing back, mirror every updated study's flat date-bound fields into its
`datedSnapshots[ohlcv.date]` slot.** This is REQUIRED — without it, the dashboard's
"researched dates" chip won't see the freshly-refreshed date and the user can't
switch between research sessions for that ticker.

Why this step exists: the dashboard's JS auto-mirrors flat → datedSnapshots on every
edit (via `updateStudy()`), but this skill bypasses that by writing JSON directly to
disk. So we must replicate the mirror manually as part of the atomic write.

For every study that was touched in Phases 2-4:

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
    # customTypes counts as research ONLY when the user has diverged from the system
    # default. Switching to a fresh date pre-seeds ['earnings']; that alone isn't
    # research. Counts if: 2+ tags OR a single tag that isn't 'earnings'.
    ct = slot.get('customTypes') or []
    if isinstance(ct, list):
        if len(ct) >= 2: return True
        if len(ct) == 1 and str(ct[0]).lower() != 'earnings': return True
    if slot.get('newsDetail') and str(slot['newsDetail']).strip(): return True
    return False

# Per study:
od = (st.get('ohlcv') or {}).get('date','')
if od:
    st.setdefault('datedSnapshots', {})
    slot = build_dated_slot(st)
    if has_research_data(slot):
        st['datedSnapshots'][od] = slot   # MUST do this — chip reads from here
    elif od in st['datedSnapshots']:
        del st['datedSnapshots'][od]      # blank slots removed (no clutter)
```

This mirror logic is identical to what the dashboard's `updateStudy()` does on every
write — same `DATE_BOUND_FIELDS`, same `buildDatedSlot`, same `hasResearchData`. Keep
the two in sync if either ever changes.

THEN write the entire updated array back to
`D:\SIPs\dashboard\studies\studies.json` in one shot (Write tool with the full updated
JSON content, or per-study Edit operations). `ensure_ascii=false`, `indent=2` to keep
the same formatting as the input.

Print a per-study summary:
```
[OK] Refreshed N studies:
  · NBIS @ 2026-05-13  OHLCV + news + TV + last → 207.27 (placeholder → filled)
  · FIG  @ 2026-05-15  OHLCV + news + TV + last → 23.42
  · ONDS @ 2026-05-14  OHLCV + news + last → 11.21 (no earnings tag, TV skipped)
  · ARM  @ 2026-05-29  OHLCV + last → 213.42 (newsDetail already filled, kept)
```

## § Phase 6 — Rebuild dashboard

Run `py D:\SIPs\build_dashboard.py`. This regenerates `dashboard/index.html` with the
new OHLCV / TV / news embedded, AND backfills `prev_ohlcv.json` into existing studies
where ohlcv.open was null (the `/SIPs` Phase 10b backfill path — see SIPs SKILL.md).

If the build errors, log it but continue to Phase 7 — `studies.json` is still useful
even if the static build failed.

## § Phase 7 — Commit + push (AUTO, required)

**Auto-push is the default.** Mirror `/SIPs` Phase 11's behaviour: every run that mutated
studies.json closes with a commit + push so the hosted Pages mirror stays current.
Don't prompt — the user has standing approval per their explicit instruction "make
everything to push after executed both /SIPs and /update-studies". The only way to skip
is the `dry-run` arg.

```powershell
cd D:\SIPs
git add dashboard/studies/studies.json dashboard/studies/images dashboard/index.html `
        dashboard/data.json dashboard/dates.json
git commit -m "studies: daily refresh — <SYM1>, <SYM2>, ..."
git push
```

If zero studies changed, do NOT make an empty commit. Print
`[OK] No changes — all studies current.` and skip both commit and push.

If `dry-run` was passed, print the diff that WOULD be written but don't touch git.

GitHub Pages auto-deploys in ~30 seconds. Hosted dashboard URL:
`https://chi2tseng.github.io/stocks-in-play/`.

## § Phase 8 — Final summary

A tight 6–12 line markdown block:

- Total studies in library
- Effective date count (after fallback)
- Updated count (≥ 1 field change)
- TV-refreshed count (= earnings-tagged)
- News-refreshed count
- Skipped (no date / future / fetch failed)
- Placeholder studies that got fully filled this run
- Whether commit + push succeeded

Stop there — don't add paragraphs of explanation. The user can see the per-study
detail in Phase 5's output.

---

## Error handling

| Failure | Action |
|---|---|
| Yahoo HTTP 4xx/5xx for one ticker | `[warn] SYM: Yahoo HTTP <code>`, skip, continue |
| Empty bars in 14d window | retry once with 30d window; if still empty, warn + skip |
| TV scrape times out / fails | warn, **don't abort**, skip TV for this study; OHLCV + news still applied |
| News fetch fails | warn, leave newsDetail empty; user can fill it later |
| `studies.json` unparseable | ABORT entire run, no writes |
| `build_dashboard.py` errors | log, continue to git |
| `git push` fails | log error, exit non-zero so the run shows failed |

Per-ticker failures NEVER abort the run — finish the other tickers first.

---

## Schema reference

```json
{
  "id":     "NBIS-mp85qrpt9dk",
  "symbol": "NBIS",
  "savedAt": "2026-05-16T09:42:24.977Z",
  "snapshot": {
    "name":      "Nebius Group N.V.",
    "type":      "momentum",
    "chgPct":    null,
    "last":      207.27,                                     // Phase 2f: synced to ohlcv.close
    "catalyst":  "Q1 2026 業績 ...",                          // Phase 4: only if was empty
    "tv":        { "latestEPS": -0.32, ..., "chart": {...} }, // Phase 3: earnings only
    "sessions":  [],
    "newsDetail": "5/13 Q1 2026 業績...",                     // Phase 4: only if was empty
    "sources": [                                              // Phase 4: source URLs (clickable pills)
      { "label": "Nebius Q1 2026 IR release", "url": "https://group.nebius.com/...", "publishedAt": "2026-05-13T16:00:00-04:00" },
      { "label": "Reuters — Nebius +621% rev",  "url": "https://www.reuters.com/..." }
    ],
    "scanDate":  "2026-05-16"
  },
  "ohlcv": {                                                  // Phase 2: every dated study
    "date":       "2026-05-13",
    "open":       203.85,  "high": 217.34,  "low": 195.0,
    "close":      207.27,  "prev_close": 179.11,
    "volume":     38770000
  },
  "customTypes": ["earnings"],
  "notes":       "...",                                       // left alone
  "customChart": { },                                         // left alone
  "intent":      "long",                                      // left alone
  "price":       null,                                        // left alone (manual override)
  "screenshots": [],
  "hiddenSections": []
}
```

## Date normalisation

Accept `2026-05-15` / `05/15/2026` / `2026/05/15`. Always WRITE back in ISO `YYYY-MM-DD`.

## Why not a cloud routine?

`/SIPs` runs locally and so does this. Two hard reasons:
1. **`tv-scrape.js`** needs Playwright + Chromium, plus the Windows-specific install. The
   cloud Linux env doesn't have it by default and installing it on every run is slow.
2. **News composition** needs Claude's judgment + multi-source synthesis. The output is
   繁體中文 markdown that mirrors `/SIPs` Phase 7 — that's an LLM job, not a Python script.

If you want unattended daily runs, schedule a Windows Task Scheduler entry that opens
Claude Code + sends `/update-studies` as the first message. Then commit + push happens
locally and pushes to the same `chi2tseng/stocks-in-play` GitHub repo the hosted Pages
mirror serves from.
