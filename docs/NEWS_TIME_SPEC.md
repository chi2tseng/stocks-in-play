# News Time Recording Spec

> **Read this BEFORE writing `news_detail.json` for any stock.** This file is the contract between `/SIPs` (the catalyst-hunt agent) and the Stocks-In-Play dashboard.

The dashboard's "新聞詳情 / News Detail" pill and the "Company News" history list (on every stock detail page) display a timestamp for each news item. That timestamp should reflect **when the news was actually published** — NOT when the scan ran. This spec tells you exactly how to source the real time, how to format it, and how to write it into `news_detail.json`.

---

## 1. File location

`D:\SIPs\news_detail.json`

Read on every `/SIPs` build by `build_dashboard.py` and merged into the per-stock data emitted to `dashboard/data/<DATE>.json`.

If the file is missing the dashboard falls back to displaying `scanTime` (when the build script ran) — that's fine for low-priority tickers but **degrades the UX for the top SIPs**, so the catalyst-hunt phase should always fill in `publishedAt` for at least the top 10 candidates.

---

## 2. Data shape

```json
{
  "MU": {
    "detail": "Q3 FY26 EPS $12.20 +682%，營收 $23.86B +196%。\n\nHBM3e 訂單已被 hyperscaler 完全包下，售完到 2026 fiscal year-end...\n\n管理層在電話會議上提到 ...",
    "publishedAt": "2026-05-13T16:05:00-04:00",
    "publishedTimezone": "ET",
    "links": [
      { "label": "Press Release", "url": "https://investors.micron.com/news-releases/news-release-details/q3-2026" }
    ]
  },
  "ASTS": {
    "detail": "...",
    "publishedAt": "2026-05-13T06:30:00-04:00",
    "publishedTimezone": "ET"
  },
  "PSIX": "Q1 2026 營收 $128.6M..."   // string-only entry, no time
}
```

### Field reference

| Field | Required? | Format | Notes |
|---|---|---|---|
| `detail` | ✅ yes | string, 繁體中文 markdown | Multi-paragraph. Paragraphs separated by `\n\n`. Single `\n` becomes `<br>` in the UI. |
| `publishedAt` | ⭐ strongly recommended | ISO 8601 with TZ offset | e.g. `2026-05-13T06:30:00-04:00`. See §3-§4. |
| `publishedTimezone` | optional | string, ≤6 chars | Display label, e.g. `"ET"`, `"PT"`, `"GMT"`. Defaults to `"ET"` if omitted. |
| `links` | optional | array of `{label, url}` | Currently NOT rendered in the dashboard (user removed external links). Keep field for future use. |

**Two equivalent compact forms also accepted:**
- `"SYM": "just the detail string"` — no `publishedAt`, treated as 1-line catalyst.
- `"SYM": { "detail": "..." }` — no time. Dashboard falls back to `scanTime`.

---

## 3. Where to find the real publication time

Listed in order of authoritativeness:

### 3.1 Earnings reports

1. **Company IR / press-release page** — most reliable. The PR header always contains the release time, e.g.:
   > *"FREMONT, Calif., May 13, 2026 (GLOBE NEWSWIRE) -- 6:05 AM ET..."*
   - Search: `<COMPANY> Q1 2026 earnings press release time`
   - Source: GlobeNewswire, Business Wire, PRNewswire — all include the timestamp in the dateline.

2. **Briefing.com "In Play" timestamps** — every entry is timestamped `HH:MM ET`.

3. **8-K SEC filing** — most authoritative legally. Search EDGAR for the company's 8-K filed on the catalyst date; the "Period of Report" + filing time is the canonical timestamp.

4. **Yahoo Finance "Latest Press Releases"** — shows release time relative to viewer's local TZ; click into the article for the absolute time.

5. **Earnings Whispers / Zacks earnings calendar** — explicit BMO / AMC tags + scheduled release time.

### 3.2 Analyst upgrades / price-target changes

1. **TheFly.com** — most timely; every upgrade is timestamped to the minute (e.g. `7:02 AM ET`).
2. **Benzinga PRO analyst ratings ticker** — same.
3. **Briefing.com "Analyst Calls"** section — also timestamped.

### 3.3 FDA approvals / clinical readouts

1. **FDA press release** — timestamped on FDA.gov in ET.
2. **Company 8-K** for material clinical results.
3. **Trial sponsor press release** (e.g. Phase 3 topline) — usually issued at 6:00 AM, 7:00 AM, or 8:00 AM ET on a Monday.

### 3.4 Contracts / M&A / corporate actions

1. **8-K filing time** (canonical).
2. **Joint press release** from both parties — both will issue same time.
3. **Reuters / Bloomberg first-print time** (when accessible).

### 3.5 Macro / sector news (no specific issuer)

- Use the first reputable wire's published timestamp (Reuters, Bloomberg, AP).
- If no specific time is locatable, OMIT `publishedAt` — the dashboard falls back to scan time, which is acceptable for non-issuer news.

---

## 4. Format rules

### 4.1 ISO 8601 with timezone offset (REQUIRED)

```
2026-05-13T06:30:00-04:00
^^^^^^^^^^^^^^^^^^^^^ ^^^^^
   date+time           offset
```

- The trailing offset MUST be present. Without it, the dashboard cannot tell whether the time is UTC, local, or US-Eastern.
- US Eastern offset:
  - **EDT** (Mar 2nd-Sunday through Nov 1st-Sunday): `-04:00`
  - **EST** (Nov 1st-Sunday through Mar 2nd-Sunday): `-05:00`
- For non-US news, use the issuer's local offset:
  - UK: `+00:00` (GMT) / `+01:00` (BST)
  - HK / TW: `+08:00`
  - JP: `+09:00`

### 4.2 Typical pre-market release times (US ET)

| Time slot | Notes |
|---|---|
| 04:00 - 05:30 | Asia/EU pre-open issuers, very early |
| 06:00 | Most common GlobeNewswire slot |
| 06:30 | TheFly batch of analyst calls fires |
| 07:00 | Major issuer earnings — most common |
| 07:30 | Late pre-market earnings (MU, NVDA-class tend to be 4:00 PM post-market) |
| 08:00 - 09:00 | Wave of European-listed ADR earnings |
| 09:25 | Last-minute news before bell |

### 4.3 Typical post-market release times (US ET)

| Time slot | Notes |
|---|---|
| 16:05 | Most common — 5 min after close, "after-the-bell" earnings |
| 16:15 - 16:30 | Bulk of AMC earnings (NVDA, MU, CRM, etc.) |
| 17:00 | Conference-call start time, sometimes news drops here too |
| 18:00 - 20:00 | Late releases, M&A announcements |

If you locate "released after the close on May 13" without an exact time, use `T16:30:00-04:00` (16:30 ET) as a reasonable default.

### 4.4 Edge cases

- **News spanning midnight ET** (e.g. analyst call at 5:00 AM HK = ~17:00 ET prior day): record in the wire's home TZ. The dashboard converts to its display TZ via the offset.
- **"Pre-market" without specific time**: use `T07:00:00-04:00` (07:00 ET) as a reasonable default.
- **Unknown time entirely**: OMIT the `publishedAt` field — the UI shows scan time with the note "(scan time)" so the user knows it's approximate.

---

## 5. Worked example

A catalyst-hunt agent has identified MU's Q3 earnings. Steps:

1. **Find the press release.** Google `MU Q3 FY26 earnings press release`. First result is `investors.micron.com/.../q3-2026-results`.
2. **Read the dateline.** It says `"BOISE, Idaho, May 13, 2026 (BUSINESS WIRE) -- Micron Technology, Inc. (Nasdaq: MU) today announced results for its third quarter ... 4:05 PM ET."`
3. **Construct ISO timestamp.** May 13 is during EDT, so offset is `-04:00`. 4:05 PM ET = 16:05 ET = `2026-05-13T16:05:00-04:00`.
4. **Write entry:**
   ```json
   "MU": {
     "detail": "Q3 FY26 EPS $12.20 vs consensus $9.19 (+33% surprise)、營收 $23.86B 大勝 $19.97B (+20% surprise)、HBM3e 訂單已售罄至 2026 fiscal 年底。\n\n管理層在電話會議上提到 HBM 產能在 2026 calendar year 已被 hyperscaler 完全包下，下一輪擴產要到 2027 H2 ...",
     "publishedAt": "2026-05-13T16:05:00-04:00",
     "publishedTimezone": "ET"
   }
   ```
5. **Save** `news_detail.json` and re-run `build_dashboard.py --date 2026-05-13`. The MU detail page now shows `Published May 13, 4:05 PM ET` (real news time) in the News Detail meta pill, and the Company News history item shows the same.

---

## 6. Display behavior

The dashboard prefers data sources in this order:

1. **`publishedAt`** (from `news_detail.json`) → displayed as `May 13, 4:05 PM ET`
2. **Stock-level scan time** (`scanTime` from data.json) → displayed as `May 13, 8:30 AM (scan time)` with the disclaimer suffix
3. **Date only** → displayed as `May 13` (last-resort fallback when nothing is known)

The Copy button on the Forward YoY block always copies the raw multiline YoY text, not the timestamp — timestamps are display-only.

---

## 7. Conventions / 慣例

- **All times in `publishedAt` must include a TZ offset.** Naive timestamps will be rejected as "could be anything."
- **Prefer the issuer's local TZ** when known (most US issuers will be ET). If a foreign issuer published at e.g. 09:30 Taipei time, write `2026-05-13T09:30:00+08:00`, not `2026-05-12T21:30:00-04:00`.
- **Round to the published minute**, not seconds. Use `:00` for seconds — exact seconds are noisy and rarely available.
- **Multiple news items per day for the same stock**: the current schema is one entry per `(symbol, date)`. If two distinct news items happened on the same day (e.g. analyst call at 7 AM + earnings at 4 PM), combine them into ONE `detail` string with `\n\n` separators and use the **most market-moving** time as `publishedAt`.

---

## 8. Quick test

After updating `news_detail.json`:

```powershell
cd D:\SIPs
py build_dashboard.py --date 2026-05-13
# Verify dashboard/data/2026-05-13.json contains publishedAt on the updated symbol(s):
py -c "import json; d=json.load(open(r'dashboard/data/2026-05-13.json','r',encoding='utf-8')); print(d['stocks']['MU'].get('publishedAt'))"
```

Then open the stock detail page in the browser at `http://127.0.0.1:5510/#/stock/MU` and confirm the News Detail meta pill shows the real publication time (no "(scan time)" suffix).
