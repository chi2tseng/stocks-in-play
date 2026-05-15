# Dashboard pages reference

The Stocks In Play SPA lives at `dashboard/index.html`. It's a single-file vanilla-JS app — no build step, no framework. Each `/SIPs` run regenerates this file from the `INDEX_HTML` template inside `build_dashboard.py`.

## Routes (hash-based)

| Route | Renderer | Description |
|---|---|---|
| `#/sips` | `renderSips('magna')` | **Default landing.** MAGNA53-ranked top 12 SIP cards (score ≥ 4). |
| `#/sips/claude` | `renderSips('claude')` | "Claude 精選" subtab. Hand-picked top 10 with 繁中 rationale, sourced from `claude_picks.json`. |
| `#/squeeze` | `renderSqueeze` | Short Squeeze sortable table — Short Float / DTC / Pre % / YoY Rev / YoY EPS / Cap / Catalyst. Default sort = DTC desc. |
| `#/earnings` | `renderEarnings` | Earnings Results table — split into Pre-Market / Post-Market subtabs. Shift+click to combine into one sheet. New columns: EPS Surp $ / EPS Surp % / EPS YoY / Rev Surp % / YoY Rev. Default sort = YoY Rev desc. |
| `#/catalyst` | `renderCatalyst` | Catalyst Deep Dive — every candidate with type tag + 1-line 繁中 catalyst. Sortable by Day (desc puts `day1` first). Row click → stock detail. |
| `#/scanx` | `renderScanx` | Briefing-style "gapping up / gapping down" two-section view. Earnings reactions show `(Rev +N%)` inline after %chg. |
| `#/gappers` | `renderGappers` | Raw Barchart universe (every row, ±4% / 100k filter shown but not applied). Useful for seeing what didn't make the cut. |
| `#/stock/<SYMBOL>` | `renderStock(sym)` | Per-stock detail page — News Detail, Catalyst Summary, EPS/Rev quarterly bar charts (hover tooltip), MS-style quarterly table (with Surprise % rows), Forward YoY block + Copy button, Company News history. |
| `#/<YYYY-MM-DD>/<route>` | (any) | View historical date. Calendar picker lists only dates with `data/<DATE>.json` present. |

## Per-day JSON data contract (`dashboard/data/<DATE>.json`)

```js
{
  "date": "2026-05-15",                          // ISO date of this scan
  "scanTime": "20:30",                           // HH:MM local time when build_dashboard.py ran
  "scanTimestamp": "2026-05-15T20:30+08:00",     // full ISO timestamp
  "stocks": {                                    // dict keyed by ticker
    "FIG": {
      "symbol": "FIG",
      "name": "Figma Inc Cl A",
      "type": "earnings",                        // earnings|guidance|analyst|contract|M&A|FDA|news|momentum|macro
      "catalyst": "Q1 +46% YoY ...",             // 1-line 繁中 (from catalysts_today.json)
      "newsDetail": "Multi-paragraph 繁中 ...",   // optional, from news_detail.json
      "publishedAt": "2026-05-14T16:05-04:00",   // optional, ISO 8601 with TZ
      "publishedTimezone": "ET",                 // human-readable label
      "sessions": [                              // pre/post moves
        { "session": "post", "direction": "up", "chgPct": 11.66, "volume": 16200000, ... }
      ],
      "last": 22.60, "chgPct": 11.66, "volume": 16200000,
      "primarySession": "post", "primaryDirection": "up",
      "tv": {                                    // TradingView FQ data (only for earnings/guidance)
        "latestEPS": 0.10, "consensusEPS": 0.06, "priorYrEPS": 0.18,
        "surpriseEPS_pct": 67, "surpriseEPS_dollar": 0.04,
        "latestRev_M": 333.4, "consensusRev_M": 316, "priorYrRev_M": 228.2,
        "surpriseRev_pct": 6, "yrYrRev_pct": 46, "epsYoY_pct": -44,
        "yoyBlock": "+46.12% / +67.00%\n--------------------\n...",
        "chart": { "quarters": ["Q2 '23", ...], "eps_reported": [...], "eps_estimate": [...],
                   "rev_reported_M": [...], "rev_estimate_M": [...], "latest_idx": 7 }
      },
      "shortFloat": 31.6,                        // from Finviz (% of float)
      "shortRatio": 3.5,                         // days to cover
      "marketCap_M": 10620, "floatShares_M": 470,
      "perf1M": -0.5, "perf3M": -8.1, "perf6M": -22, "perfYTD": -48, "perf12M": -48,
      "neglected": true                          // optional, from claude_picks.json.picks[].neglected → fires N magna bit
    },
    "BOOT": { ... },
    ...
  },
  "claudePicks": [                               // from claude_picks.json
    { "symbol": "FIG", "rank": 1, "rationale": "...", "neglected": false },
    ...
  ],
  "dayResets": {                                 // from day_resets.json.resets
    "FIG": "Q1 +46% YoY 財報 — fresh earnings; prior +4.5% was unrelated noise",
    ...
  },
  "rawGappers": [...],                           // every Barchart row before filter (for /gappers page)
  "rawGappersFilter": { "chgMin": 4, "volMin": 100000 },
  "scanx": {                                     // SCANX page lists
    "gapUpEarnings": [...], "gapUpOther": [...],
    "gapDownEarnings": [...], "gapDownOther": [...]
  }
}
```

## Other top-level dashboard files

| File | Purpose |
|---|---|
| `dashboard/dates.json` | Array of `{date, label}` — controls the calendar picker. Regenerated each build by scanning `data/*.json`. |
| `dashboard/data.json` | Copy of latest `data/<DATE>.json` (backward-compat with v1 SPA that fetched a single file). |
| `dashboard/index.html` | The SPA shell. Regenerated each build from `INDEX_HTML` template in `build_dashboard.py`. **Don't edit this directly** — edit the template + run `_sync_template.py` to update. |

## Editing the SPA

The SPA's HTML+CSS+JS lives inside `build_dashboard.py` as a multi-line `r'''...'''` string named `INDEX_HTML`. To edit:

1. Edit `dashboard/index.html` directly (in the browser DevTools or any editor)
2. Run `py _sync_template.py` — this reads `dashboard/index.html` and re-embeds it into `build_dashboard.py`'s `INDEX_HTML` block
3. Run `py build_dashboard.py` to rebuild — produces an identical `index.html` (round-trip verified)

The two-file dance exists so the template is version-controlled inside the Python script (single source of truth for fresh builds) but you can still iterate visually by editing the rendered HTML.

## CSS / design tokens

The SPA uses the **Revolut design system** (cobalt-violet `#494fdf` primary, teal `#00a87e` positive, red `#e23b4a` negative, Aeonik Pro display, Inter body, JetBrains Mono numbers). Fonts loaded from Google Fonts CDN. See `<style>` block in `dashboard/index.html` for the full token list under `:root { --primary: ...; }`.
