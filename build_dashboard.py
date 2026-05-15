"""Build the unified dashboard at .firecrawl/dashboard/.
  - data/<YYYY-MM-DD>.json : per-day archive
  - data.json              : symlink-equivalent copy of latest (backward compat)
  - dates.json             : array of available dates, newest first
  - index.html             : SPA with #/<date>/<route> hash routing
"""
import json, csv, os, argparse, datetime, shutil

ap = argparse.ArgumentParser()
ap.add_argument('--date', default=datetime.date.today().isoformat(),
                help='YYYY-MM-DD; default = today (local)')
args = ap.parse_args()
DATE = args.date

# Location-agnostic: DIR = the directory containing this script. Override with SIPS_DIR env var.
DIR = os.environ.get('SIPS_DIR') or os.path.dirname(os.path.abspath(__file__))
DASH_DIR = os.path.join(DIR, 'dashboard')
DATA_DIR = os.path.join(DASH_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# --- Load TV data ---
with open(os.path.join(DIR, 'tv-summary.json'), 'r', encoding='utf-8') as f:
    tv_list = json.load(f)
tv = {t['Ticker']: t for t in tv_list}

# --- Load candidates ---
cands_by_sym = {}
with open(os.path.join(DIR, 'candidates.csv'), 'r', encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        sym = r['Symbol']
        cands_by_sym.setdefault(sym, []).append({
            'last': float(r['Last']), 'chgPct': float(r['ChgPct']),
            'volume': int(r['Volume']), 'session': r['Session'],
            'direction': r['Direction'], 'name': r['Name'],
        })

# --- Load RAW barchart pages (every stock Barchart returned, before the ±4% / 100k filter) ---
# These are the per-page JSON dumps the Playwright scraper saves: barchart-{session}-{direction}-pN.json
# We consolidate them into a flat list of rows so the Gappers page can show the full Barchart universe.
CHG_MIN, VOL_MIN = 4.0, 100_000  # must match barchart-scrape.js
def _load_raw_barchart():
    import glob
    rows = []
    seen_syms = set()  # dedupe across pages (same symbol can appear in multiple pages of the same source)
    for fp in glob.glob(os.path.join(DIR, 'barchart-*-p*.json')):
        fn = os.path.basename(fp)
        # Filename shape: barchart-{session}-{direction}-pN.json
        parts = fn.replace('.json', '').split('-')
        if len(parts) < 4: continue
        session = parts[1]                              # 'pre' or 'post'
        direction_label = parts[2]                      # 'advances' or 'declines'
        direction = 'up' if direction_label == 'advances' else 'down'
        prefix = 'preMarket' if session == 'pre' else 'postMarket'
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                blob = json.load(f)
        except Exception:
            continue
        for r in blob.get('data', []):
            sym = r.get('symbol')
            if not sym: continue
            key = (sym, session, direction)
            if key in seen_syms: continue
            seen_syms.add(key)
            raw = r.get('raw') or {}
            try:
                last = float(raw.get(f'{prefix}LastPrice') or r.get(f'{prefix}LastPrice', '0').replace(',', ''))
                chg  = float(raw.get(f'{prefix}PercentChange') or 0) * (100 if raw.get(f'{prefix}PercentChange') else 1)
                if not raw.get(f'{prefix}PercentChange'):
                    chg = float((r.get(f'{prefix}PercentChange', '+0%') or '+0').replace('%','').replace(',',''))
                vol  = int(raw.get(f'{prefix}Volume') or str(r.get(f'{prefix}Volume', '0')).replace(',', ''))
            except (ValueError, TypeError):
                continue
            # The advances list has positive %chg; declines list has negative — sign comes from direction tag.
            signed_chg = -abs(chg) if direction == 'down' else abs(chg)
            rows.append({
                'symbol': sym,
                'name': r.get('symbolName') or '',
                'last': last,
                'chgPct': round(signed_chg, 2),
                'volume': vol,
                'session': session,
                'direction': direction,
                'prevClose':  raw.get(f'{prefix}PreviousLast'),
                'prevHigh':   raw.get(f'{prefix}PreviousHighPrice'),
                'prevLow':    raw.get(f'{prefix}PreviousLowPrice'),
                'tradeTime':  r.get(f'{prefix}TradeTime'),
                'nextEarnings': r.get('nextEarningsDate'),
                'hasOptions': raw.get('hasOptions') if raw.get('hasOptions') is not None else (r.get('hasOptions') == 'Yes'),
                'passedFilter': abs(signed_chg) >= CHG_MIN and vol >= VOL_MIN,
            })
    # Sort by |chgPct| desc so the table comes out roughly ranked
    rows.sort(key=lambda r: -abs(r['chgPct']))
    return rows

raw_gappers = _load_raw_barchart()

# --- Load catalyst classification ---
catalyst = {}
fc_path = os.path.join(DIR, 'final-candidates.csv')
if os.path.exists(fc_path):
    with open(fc_path, 'r', encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if r['Symbol'] not in catalyst:
                catalyst[r['Symbol']] = {'type': r['Type'], 'catalyst': r['Catalyst'], 'name': r['Name']}

# --- Load optional news detail file ---
news_detail_path = os.path.join(DIR, 'news_detail.json')
news_detail_raw = {}
if os.path.exists(news_detail_path):
    with open(news_detail_path, 'r', encoding='utf-8') as f:
        news_detail_raw = json.load(f)

# --- Load optional Finviz shorts file (built by finviz-shorts.js) ---
# Schema: { "<TICKER>": { status, shortFloat, shortRatio, marketCap_M, floatShares_M,
#                         perf1M, perf3M, perf6M, perfYTD, perf12M, ... }, ... }
shorts_path = os.path.join(DIR, 'shorts.json')
shorts_raw = {}
if os.path.exists(shorts_path):
    with open(shorts_path, 'r', encoding='utf-8') as f:
        shorts_raw = json.load(f)

# --- Load optional prev-day OHLCV file (built by /SIPs after trading day) ---
# Schema: { "<TICKER>": { date, open, high, low, close, prev_close, volume } }
# Surfaces as DATA.stocks[sym].prevOhlcv so the Studies "Save to Studies" flow can auto-fill
# ohlcv when present (user doesn't have to re-key the numbers manually).
# `prev_close` (the close of the bar BEFORE `date`) drives the dashboard's day-%Chg derivation
# in renderStudyDetail: (close − prev_close) / prev_close · 100.
prev_ohlcv_path = os.path.join(DIR, 'prev_ohlcv.json')
prev_ohlcv_raw = {}
if os.path.exists(prev_ohlcv_path):
    with open(prev_ohlcv_path, 'r', encoding='utf-8') as f:
        prev_ohlcv_raw = json.load(f)

# --- Auto-backfill existing studies (dashboard/studies/studies.json) ---
# For every ticker the user has saved as a Study, if its ohlcv has never been filled
# (ohlcv.open is None), backfill from prev_ohlcv_raw. Manual data is sacred — anything
# the user typed in person stays exactly as they left it. This lets the day's %Chg auto-
# derive across the user's whole Studies library on every /SIPs run, without re-typing
# yesterday's bar for each ticker.
studies_json_path = os.path.join(DIR, 'dashboard', 'studies', 'studies.json')
if prev_ohlcv_raw and os.path.exists(studies_json_path):
    try:
        with open(studies_json_path, 'r', encoding='utf-8') as f:
            studies_arr = json.load(f)
        if isinstance(studies_arr, list):
            changed = False
            for st in studies_arr:
                sym = (st or {}).get('symbol')
                if not sym:
                    continue
                cur_ohlcv = st.get('ohlcv') or {}
                if cur_ohlcv.get('open') is not None:
                    continue  # user-filled — never overwrite
                row = prev_ohlcv_raw.get(sym)
                if not row:
                    continue
                # Merge — keep any existing fields the user may have partially typed
                st['ohlcv'] = {**cur_ohlcv, **{
                    'date':       row.get('date', cur_ohlcv.get('date', '')),
                    'open':       row.get('open'),
                    'high':       row.get('high'),
                    'low':        row.get('low'),
                    'close':      row.get('close'),
                    'prev_close': row.get('prev_close'),
                    'volume':     row.get('volume'),
                }}
                changed = True
            if changed:
                tmp = studies_json_path + '.tmp'
                with open(tmp, 'w', encoding='utf-8') as f:
                    json.dump(studies_arr, f, ensure_ascii=False, indent=2)
                os.replace(tmp, studies_json_path)
                print(f'[prev_ohlcv] backfilled {sum(1 for s in studies_arr if (s.get("ohlcv") or {}).get("open") is not None)} studies in dashboard/studies/studies.json')
    except Exception as e:
        print(f'[prev_ohlcv] backfill skipped (non-fatal): {e}')

# --- Load optional Claude picks file ---
# Schema: { "picks": [ { "symbol": "X", "rank": 1, "rationale": "..." }, ... ] }
claude_picks_path = os.path.join(DIR, 'claude_picks.json')
claude_picks_list = []
if os.path.exists(claude_picks_path):
    with open(claude_picks_path, 'r', encoding='utf-8') as f:
        _cp = json.load(f)
        if isinstance(_cp, dict):
            claude_picks_list = _cp.get('picks', []) or []
        elif isinstance(_cp, list):
            claude_picks_list = _cp

# --- Load optional day_resets.json — symbols whose day-count should reset to day1 today
# because a NEW MAJOR catalyst is the primary cause of the move (curated by Claude per scan). ---
day_resets_path = os.path.join(DIR, 'day_resets.json')
day_resets_map = {}
if os.path.exists(day_resets_path):
    with open(day_resets_path, 'r', encoding='utf-8') as f:
        _dr = json.load(f)
        day_resets_map = _dr.get('resets', {}) if isinstance(_dr, dict) else {}

def auto_news_links(sym):
    return [
        {'label': 'Finviz',           'url': f'https://finviz.com/quote.ashx?t={sym}'},
        {'label': 'Yahoo Finance',    'url': f'https://finance.yahoo.com/quote/{sym}'},
        {'label': 'TradingView News', 'url': f'https://www.tradingview.com/symbols/NASDAQ-{sym}/news/'},
    ]

def resolve_news(sym):
    """Returns (detail, links, publishedAt, publishedTimezone).
    See NEWS_TIME_SPEC.md for the publishedAt format and how to source real news timestamps.
    """
    entry = news_detail_raw.get(sym)
    if entry is None:
        return None, auto_news_links(sym), None, None
    if isinstance(entry, str):
        return entry, auto_news_links(sym), None, None
    detail = entry.get('detail')
    links = entry.get('links') or auto_news_links(sym)
    publishedAt = entry.get('publishedAt')                     # ISO 8601, e.g. "2026-05-13T06:30:00-04:00"
    publishedTz = entry.get('publishedTimezone') or 'ET'       # human-readable label
    return detail, links, publishedAt, publishedTz

# --- Build per-stock combined data ---
stocks = {}
all_syms = set(list(cands_by_sym.keys()) + list(tv.keys()) + list(catalyst.keys()))
for sym in all_syms:
    cands = cands_by_sym.get(sym, [])
    if not cands:
        continue  # skip if not in today's Barchart filter
    cat = catalyst.get(sym, {})
    t = tv.get(sym)
    tv_out = None
    if t:
        eps_lat = t.get('LatestEPS')
        eps_cons = t.get('LatestEPSConsensus')
        rev_lat = t.get('LatestRev_M')
        rev_cons = t.get('LatestRevConsensus_M')
        prior_rev = t.get('PriorYrRev_M')
        prior_eps = t.get('PriorYrEPS')
        # Universal YoY formula: (curr - prior) / abs(prior) * 100 — handles all sign combinations.
        # Both pos: growth %. Both neg: loss widening → negative %, narrowing → positive %.
        # Neg → pos: massive improvement (positive %, often >100%). Pos → neg: massive deterioration.
        # (Same formula parse_tv.py uses for the YoY block on the stock-detail page; the old
        #  `prior > 0 and curr > 0` guard hid the YoY % for every loss-related case.)
        yr_yr_rev = ((rev_lat - prior_rev) / abs(prior_rev) * 100) if (rev_lat is not None and prior_rev is not None and prior_rev != 0) else None
        eps_yoy   = ((eps_lat - prior_eps) / abs(prior_eps) * 100) if (eps_lat is not None and prior_eps is not None and prior_eps != 0) else None
        # Surprise % — use TV's parsed value when present, otherwise compute via universal formula.
        # parse_tv.py sometimes leaves Surprise_pct null when consensus is negative (e.g. ONDS:
        # actual EPS -$0.34, consensus -$0.71 → TV's % blanks out). We fill it in using
        # (actual - consensus) / |consensus| * 100 which handles negative-consensus correctly.
        eps_surp_pct = t.get('LatestEPSSurprise_pct')
        if eps_surp_pct is None and eps_lat is not None and eps_cons is not None and eps_cons != 0:
            eps_surp_pct = (eps_lat - eps_cons) / abs(eps_cons) * 100
        rev_surp_pct = t.get('LatestRevSurprise_pct')
        if rev_surp_pct is None and rev_lat is not None and rev_cons is not None and rev_cons != 0:
            rev_surp_pct = (rev_lat - rev_cons) / abs(rev_cons) * 100
        tv_out = {
            'latestEPS': eps_lat,
            'consensusEPS': eps_cons,
            'priorYrEPS': prior_eps,
            'surpriseEPS_pct': eps_surp_pct,
            'surpriseEPS_dollar': (eps_lat - eps_cons) if (eps_lat is not None and eps_cons is not None) else None,
            'latestRev_M': rev_lat,
            'consensusRev_M': rev_cons,
            'priorYrRev_M': prior_rev,
            'surpriseRev_pct': rev_surp_pct,
            'yrYrRev_pct': yr_yr_rev,
            'epsYoY_pct': eps_yoy,
            'epsEst_next4': t.get('EpsEst_Next4'),
            'revEst_next4': t.get('RevEst_Next4'),
            'yoyBlock': t.get('YoYBlock'),
            'chart': t.get('Chart'),
        }
    # If a ticker appears in both pre and post, store both, but pick primary by larger |%chg|
    primary = max(cands, key=lambda c: abs(c['chgPct']))
    news_detail_val, news_links_val, news_publishedAt, news_publishedTz = resolve_news(sym)
    # Pull Finviz shorts row for this ticker (or None if scraper didn't run / failed).
    sh = shorts_raw.get(sym) or {}
    if sh.get('status') != 'ok':
        sh = {}
    stocks[sym] = {
        'symbol': sym,
        'name': primary['name'] or cat.get('name', sym),
        'type': cat.get('type', '?'),
        'catalyst': cat.get('catalyst', ''),
        'newsDetail': news_detail_val,
        'newsLinks': news_links_val,
        'publishedAt': news_publishedAt,
        'publishedTimezone': news_publishedTz,
        'sessions': cands,
        'primarySession': primary['session'],
        'primaryDirection': primary['direction'],
        'last': primary['last'],
        'chgPct': primary['chgPct'],
        'volume': primary['volume'],
        'tv': tv_out,
        # Finviz-sourced fields (None when not available — dashboard handles gracefully)
        'shortFloat':    sh.get('shortFloat'),
        'shortRatio':    sh.get('shortRatio'),
        'marketCap_M':   sh.get('marketCap_M'),
        'floatShares_M': sh.get('floatShares_M'),
        'perf1M':        sh.get('perf1M'),
        'perf3M':        sh.get('perf3M'),
        'perf6M':        sh.get('perf6M'),
        'perfYTD':       sh.get('perfYTD'),
        'perf12M':       sh.get('perf12M'),
        # Prev-day OHLCV (optional, populated by /SIPs after the trading day).
        # Auto-fills Studies' ohlcv when user clicks "Save to Studies".
        'prevOhlcv':     prev_ohlcv_raw.get(sym) or None,
    }

# --- Build SCANX lists ---
gap_up_e, gap_up_o, gap_dn_e, gap_dn_o = [], [], [], []
seen = set()
for sym, s in stocks.items():
    for sess in s['sessions']:
        key = (sym, sess['direction'])
        if key in seen: continue
        seen.add(key)
        entry = {'symbol': sym, 'chg': sess['chgPct'], 'catalyst': s['catalyst'], 'type': s['type']}
        is_earnings = s['type'] in ('earnings', 'guidance')
        if sess['direction'] == 'up':
            (gap_up_e if is_earnings else gap_up_o).append(entry)
        else:
            (gap_dn_e if is_earnings else gap_dn_o).append(entry)

for lst in [gap_up_e, gap_up_o, gap_dn_e, gap_dn_o]:
    lst.sort(key=lambda e: -abs(e['chg']))

# Filter Claude picks to symbols that are actually in today's candidate set
# (so a stale claude_picks.json never points at delisted tickers).
# Also: if a pick carries a `neglected` flag, propagate it to the stock row so the MAGNA N
# bit lights up. Default is None → bits.N stays 'maybe' in the dashboard.
claude_picks_clean = []
for p in claude_picks_list:
    sym = p.get('symbol')
    if sym not in stocks:
        continue
    claude_picks_clean.append({
        'symbol': sym,
        'rank': p.get('rank'),
        'intent': p.get('intent', 'long'),         # 'long' (default) | 'short' — dashboard filters by direction match
        'rationale': p.get('rationale', ''),
        'neglected': p.get('neglected'),
    })
    if 'neglected' in p:
        stocks[sym]['neglected'] = p.get('neglected')

# Filter day_resets to symbols actually in today's candidate set (drop stale entries silently).
day_resets_clean = {sym: reason for sym, reason in day_resets_map.items() if sym in stocks}

_now = datetime.datetime.now()
data = {
    'date': DATE,
    'scanTime': _now.strftime('%H:%M'),
    'scanTimestamp': _now.isoformat(timespec='minutes'),
    'stocks': stocks,
    'rawGappers': raw_gappers,    # ALL Barchart rows from today's scrape, before the ±4%/100k filter
    'rawGappersFilter': {'chgMin': CHG_MIN, 'volMin': VOL_MIN},
    'claudePicks': claude_picks_clean,
    'dayResets': day_resets_clean,    # symbols whose day-count resets to day1 today (new major catalyst)
    'scanx': {
        'gapUpEarnings': gap_up_e, 'gapUpOther': gap_up_o,
        'gapDownEarnings': gap_dn_e, 'gapDownOther': gap_dn_o,
    },
}

day_path = os.path.join(DATA_DIR, f'{DATE}.json')
with open(day_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# Backward-compat: also copy to dashboard/data.json (latest)
shutil.copyfile(day_path, os.path.join(DASH_DIR, 'data.json'))

# Regenerate dates.json by scanning data/*.json
def _label(d):
    dt = datetime.date.fromisoformat(d)
    return f"{dt.month}/{dt.day} {dt.strftime('%a')}"   # "5/13 Wed"

dates_list = []
for fn in os.listdir(DATA_DIR):
    if fn.endswith('.json') and len(fn) == 15:
        d = fn[:-5]
        try:
            datetime.date.fromisoformat(d)
            dates_list.append({'date': d, 'label': _label(d)})
        except ValueError:
            pass
dates_list.sort(key=lambda x: x['date'], reverse=True)
with open(os.path.join(DASH_DIR, 'dates.json'), 'w', encoding='utf-8') as f:
    json.dump(dates_list, f, ensure_ascii=False, indent=2)

print(f'[OK] {DATE}: {len(stocks)} stocks; {len(raw_gappers)} raw Barchart rows; archive has {len(dates_list)} day(s)')

# --- Build index.html ---
INDEX_HTML = r'''<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Stocks In Play</title>
<!-- Custom "S" favicon — cobalt-violet rounded square + white S. Inline SVG data URI so it
     ships with the HTML, no extra request. Works in Chrome / Safari / Firefox tabs and PWA. -->
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='7' fill='%23494fdf'/><text x='16' y='23' font-family='Inter, system-ui, sans-serif' font-size='22' font-weight='800' fill='white' text-anchor='middle' letter-spacing='-1'>S</text></svg>">
<link rel="apple-touch-icon" href="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 180 180'><rect width='180' height='180' rx='40' fill='%23494fdf'/><text x='90' y='128' font-family='Inter, system-ui, sans-serif' font-size='120' font-weight='800' fill='white' text-anchor='middle' letter-spacing='-5'>S</text></svg>">
<!-- Webfonts — Inter (variable, with `opsz` axis for display sizes) acts as the Aeonik Pro stand-in
     per DESIGN.md §388 ("Inter Display ... credible substitutes"). JetBrains Mono for tabular numbers. -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,400;14..32,500;14..32,600;14..32,700&family=JetBrains+Mono:wght@500;600;700&display=swap">
<style>
:root {
  --primary: #494fdf;
  --primary-bright: #4f55f1;
  --primary-deep: #3a40c4;
  --on-primary: #ffffff;
  --ink: #191c1f;
  --body: #1f2226;
  --charcoal: #3a3d40;
  --mute: #505a63;
  --ash: #5c5e60;
  --stone: #8d969e;
  --faint: #c9c9cd;
  --canvas: #ffffff;
  --canvas-dark: #000000;
  --surface-soft: #f4f4f4;
  --surface-card: #ffffff;
  --surface-deep: #0a0a0a;
  --surface-elevated: #16181a;
  --hairline: #e2e2e7;
  --hairline-soft: #eef0f3;
  --hairline-dark: rgba(255, 255, 255, 0.12);
  --accent-teal: #00a87e;
  --accent-green-text: #006400;
  --accent-pink: #e61e49;
  --accent-danger: #e23b4a;
  --accent-deep-red: #8b0000;
  --accent-warning: #ec7e00;
  --accent-yellow: #b09000;
  --accent-light-blue: #007bc2;
  --accent-light-green: #428619;
  --accent-brown: #936d62;
  --link: #376cd5;
  --pos: var(--accent-teal);
  --neg: var(--accent-danger);
  --shadow-card: 0 12px 28px -16px rgba(5, 0, 56, 0.18);
  --r-sm: 8px;
  --r-md: 12px;
  --r-lg: 20px;
  --r-xl: 28px;
  --r-pill: 9999px;
  --s-xxs: 4px;
  --s-xs: 6px;
  --s-sm: 8px;
  --s-md: 14px;
  --s-lg: 16px;
  --s-xl: 24px;
  --s-xxl: 32px;
  --font-display: "Aeonik Pro", "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang TC", "Microsoft JhengHei", system-ui, sans-serif;
  --font-body:    "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang TC", "Microsoft JhengHei", system-ui, sans-serif;
  --font-mono:    "JetBrains Mono", "SF Mono", Menlo, "Courier New", monospace;
}
/* ── Dark mode overrides — toggle via body.dark class. Brand cobalt-violet primary stays
   the same; canvas/ink/surface tokens inverted with slightly elevated mid-tones so cards
   stand out. Pos/neg colors brightened for contrast on dark bg. ── */
body.dark {
  --ink: #f4f5f7;
  --body: #d6d9dd;
  --charcoal: #c9cdd2;
  --mute: #a3a8b0;
  --ash: #8d929a;
  --stone: #6f7480;
  --faint: #4a4f57;
  --canvas: #16181a;
  --surface-soft: #1f2226;
  --surface-card: #16181a;
  --surface-elevated: #2a2d31;
  --hairline: #2e3236;
  --hairline-soft: #25282c;
  --primary-deep: #6e74e8;
  --pos: #1ec887;
  --neg: #ff5466;
  --shadow-card: 0 12px 28px -16px rgba(0, 0, 0, 0.6);
}
/* Dark mode special-case rules — for elements that have hardcoded white/black colors. */
body.dark .stock-card,
body.dark .news-history-card,
body.dark .sip-card,
body.dark .scanx-section,
body.dark .panel,
body.dark .stock-header,
body.dark nav.topbar,
body.dark .cal-popup { background: var(--surface-card); }
body.dark th { background: var(--surface-card); color: var(--mute); }
body.dark td { color: var(--body); }
body.dark .sip-rank, body.dark .cal-btn { background: var(--surface-elevated); color: var(--ink); }
body.dark .copy-btn, body.dark .sip-copy-btn { background: var(--surface-elevated); color: var(--ink); }
body.dark .copy-btn:hover, body.dark .sip-copy-btn:hover { background: var(--primary); }
body.dark .subtab { background: var(--canvas); color: var(--mute); border-color: var(--hairline); }
body.dark .subtab.active { background: var(--primary); border-color: var(--primary); color: #fff; }
body.dark .chart .bar-reported { fill: #e8eaed; }
body.dark .chart .col-highlight { fill: #ffffff; opacity: 0; }
body.dark .chart .col-highlight.active { opacity: 0.08; }
body.dark #chart-tooltip .ct-inner { background: rgba(245, 246, 248, 0.96); color: var(--ink); }
body.dark #chart-tooltip .ct-dot.rep { background: var(--ink); }
body.dark #chart-tooltip .ct-lbl { color: rgba(25, 28, 31, 0.65); }
body.dark #chart-tooltip .ct-val { color: var(--ink); }
body.dark #chart-tooltip .ct-q { color: rgba(25, 28, 31, 0.45); }
body.dark #chart-tooltip .ct-unit { color: rgba(25, 28, 31, 0.5); }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body { font-family: var(--font-body); background: var(--canvas); color: var(--ink); font-size: 15px; line-height: 1.5; -webkit-font-smoothing: antialiased; font-optical-sizing: auto; }
/* Old <header> hero is hidden — using thin topbar instead */
header { display: none; }
/* ============================================================
   Topbar — single thin row: brand + nav links + date controls
   Figma-style — centered container, max 1440px
   ============================================================ */
nav.topbar {
  background: var(--canvas);
  border-bottom: 1px solid var(--hairline);
  height: 60px;
  display: flex;
  align-items: center;
  padding: 0 32px;
  position: sticky;
  top: 0;
  z-index: 20;
}
nav.topbar .topbar-inner {
  display: flex;
  align-items: center;
  width: 100%;
  max-width: 1440px;
  margin: 0 auto;
  gap: 0;
}
nav.topbar .brand {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.6px;
  color: var(--ink);
  margin-right: 40px;
  cursor: pointer;
  text-decoration: none;
  user-select: none;
}
nav.topbar .nav-links {
  display: flex;
  align-items: center;
  gap: 2px;
  flex: 1 1 auto;
}
nav.topbar .nav-links a {
  font-family: var(--font-body);
  font-size: 15px;
  font-weight: 500;
  color: var(--charcoal);
  text-decoration: none;
  padding: 8px 14px;
  cursor: pointer;
  border-radius: var(--r-sm);
  border-bottom: none;
  margin-right: 0;
  letter-spacing: 0;
  line-height: 1.4;
  transition: background 0.12s, color 0.12s;
}
nav.topbar .nav-links a:hover { color: var(--ink); background: var(--surface-soft); }
nav.topbar .nav-links a.active { color: var(--ink); background: var(--surface-soft); font-weight: 600; }
nav.topbar .topbar-right { display: flex; align-items: center; gap: 8px; flex: 0 0 auto; }
@media (max-width: 900px) {
  nav.topbar { padding: 0 16px; height: 56px; }
  nav.topbar .brand { font-size: 18px; margin-right: 16px; }
  nav.topbar .nav-links a { padding: 6px 10px; font-size: 13px; }
}
/* legacy .date-strip / .date-pill kept as no-op (old templates may still reference them) */
.date-strip, .date-pills { display: none; }
.cal-btn {
  padding: 6px 14px 6px 12px;
  background: var(--ink);
  color: #ffffff;
  border: none;
  border-radius: var(--r-pill);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-body);
  transition: background 0.12s;
}
.cal-btn:hover { background: var(--charcoal); }
/* Topbar icon buttons — used for language + dark-mode toggles. Same pill geometry as cal-btn
   but transparent surface so they read as secondary controls. */
.topbar-iconbtn {
  width: 32px; height: 32px; padding: 0;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: var(--r-pill); border: 1px solid var(--hairline);
  background: transparent; color: var(--ink); cursor: pointer;
  font-family: var(--font-mono); font-size: 11px; font-weight: 700;
  transition: background 0.12s, border-color 0.12s, color 0.12s, transform 100ms ease;
}
.topbar-iconbtn:hover { background: var(--surface-soft); border-color: var(--ink); }
.topbar-iconbtn:active { transform: scale(0.94); }
.topbar-iconbtn svg { width: 16px; height: 16px; }

/* ── Studies page (personal SIP library backed by localStorage) ── */
.studies-toolbar { display: flex; gap: 8px; align-items: center; margin: 0 0 16px; }
.studies-btn {
  padding: 7px 14px; border-radius: var(--r-pill); background: var(--canvas); border: 1px solid var(--hairline);
  font-size: 13px; font-weight: 600; color: var(--ink); cursor: pointer; font-family: var(--font-body);
  transition: background 0.12s, border-color 0.12s;
}
.studies-btn:hover { background: var(--surface-soft); border-color: var(--ink); }
.studies-btn-danger { color: var(--neg); }
.studies-btn-danger:hover { background: rgba(226,59,74,0.06); border-color: var(--neg); }

/* ── Read-only mode (hosted GitHub Pages — no sidecar) ──
   Studies are a "personal backup viewable on phone/other devices" — view but don't edit.
   The .readonly-mode body class is toggled in detectSidecar() once on boot. */
body.readonly-mode .ro-hide { display: none !important; }
body.readonly-mode [contenteditable="true"] { background: var(--surface-soft); cursor: not-allowed; }
body.readonly-mode .studies-btn,
body.readonly-mode .study-remove,
body.readonly-mode .notes-img-del,
body.readonly-mode .section-x,
body.readonly-mode .copy-btn,
body.readonly-mode .trade-pill,
body.readonly-mode .ms-edit input { pointer-events: none; opacity: 0.55; }
body.readonly-mode .studies-btn-danger { display: none !important; }
.readonly-badge {
  display: none; align-items: center; gap: 6px; padding: 4px 10px; font-size: 11px; font-weight: 600;
  border-radius: var(--r-pill); background: rgba(255, 178, 30, 0.12); color: #b97c00;
  border: 1px solid rgba(255, 178, 30, 0.4); font-family: var(--font-body); letter-spacing: 0.2px;
}
body.dark .readonly-badge { color: #ffce6a; background: rgba(255, 206, 106, 0.10); border-color: rgba(255, 206, 106, 0.35); }
body.readonly-mode .readonly-badge { display: inline-flex; }
.studies-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(440px, 1fr)); gap: 12px; }
.study-card {
  background: var(--canvas); border: 1px solid var(--hairline); border-radius: var(--r-lg);
  padding: 18px 20px; display: flex; flex-direction: column; gap: 10px;
}
.study-card-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.study-sym { font-family: var(--font-mono); font-size: 22px; font-weight: 700; color: var(--ink); text-decoration: none; letter-spacing: -0.5px; }
.study-sym:hover { color: var(--primary); }
.study-saved-on { font-size: 11px; color: var(--stone); margin-left: auto; font-family: var(--font-mono); }
.study-remove { background: transparent; border: none; color: var(--mute); cursor: pointer; font-size: 16px; padding: 4px 8px; border-radius: var(--r-sm); }
.study-remove:hover { color: var(--neg); background: rgba(226,59,74,0.08); }
.study-name { font-size: 13px; color: var(--mute); }
.study-catalyst { font-size: 13px; color: var(--body); line-height: 1.6; padding: 8px 10px; background: var(--surface-soft); border-radius: var(--r-sm); }
.study-rationale { font-size: 13px; color: var(--ink); line-height: 1.65; padding: 10px 12px; background: rgba(73,79,223,0.04); border-left: 3px solid var(--primary); border-radius: var(--r-sm); }
.study-fields { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
.study-field { display: flex; flex-direction: column; gap: 4px; font-size: 11px; color: var(--stone); font-weight: 600; text-transform: uppercase; letter-spacing: 0.4px; }
.study-field input { padding: 6px 10px; border: 1px solid var(--hairline); border-radius: var(--r-sm); background: var(--canvas); color: var(--ink); font-family: var(--font-mono); font-size: 13px; width: 100px; }
.study-field input[type="range"] { padding: 0; width: 110px; accent-color: var(--primary); }
.study-tags, .study-notes {
  padding: 8px 12px; border: 1px solid var(--hairline); border-radius: var(--r-sm);
  background: var(--canvas); color: var(--ink); font-family: var(--font-body); font-size: 13px;
  width: 100%; box-sizing: border-box; resize: vertical;
}
.study-tags:focus, .study-notes:focus { outline: none; border-color: var(--primary); }

/* "Save to Studies" button on SIP cards + stock detail header */
.save-study-btn {
  position: absolute; top: 14px; right: 16px; padding: 5px 12px;
  background: var(--canvas); border: 1px solid var(--hairline); border-radius: var(--r-pill);
  font-size: 11px; font-weight: 600; color: var(--mute); cursor: pointer;
  font-family: var(--font-body); transition: background 0.12s, color 0.12s, border-color 0.12s;
  z-index: 2;
}
.save-study-btn:hover { background: var(--ink); color: #fff; border-color: var(--ink); }
.save-study-btn.saved { background: rgba(0,168,126,0.10); color: var(--pos); border-color: var(--pos); }
body.readonly-mode .save-study-btn { display: none !important; }

/* ── OHLCV row + intraday chip ── */
.study-section-label {
  font-size: 11px; color: var(--stone); font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.6px; margin-top: 4px;
  display: flex; align-items: center; gap: 10px;
}
.study-intraday {
  font-family: var(--font-mono); font-size: 11px; font-weight: 700;
  padding: 2px 8px; border-radius: var(--r-pill); background: var(--surface-soft);
}
.study-intraday.pos { color: var(--pos); }
.study-intraday.neg { color: var(--neg); }
.study-ohlcv-row { display: grid; grid-template-columns: repeat(6, 1fr); gap: 6px; }
.study-ohlcv-field { display: flex; flex-direction: column; gap: 3px; font-size: 10px; color: var(--stone); font-weight: 600; text-transform: uppercase; letter-spacing: 0.4px; }
.study-ohlcv-field input {
  padding: 5px 8px; border: 1px solid var(--hairline); border-radius: var(--r-sm);
  background: var(--canvas); color: var(--ink); font-family: var(--font-mono); font-size: 12px;
}
.study-ohlcv-field input:focus { outline: none; border-color: var(--primary); }
@media (max-width: 700px) { .study-ohlcv-row { grid-template-columns: repeat(3, 1fr); } }

/* Lightbox overlay for click-to-enlarge any image in the notes block */
.shot-lightbox {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.88);
  display: flex; align-items: center; justify-content: center; flex-direction: column;
  z-index: 99999; cursor: zoom-out; padding: 40px;
}
.shot-lightbox img { max-width: 95vw; max-height: 88vh; box-shadow: 0 24px 64px rgba(0,0,0,0.5); border-radius: var(--r-sm); }
.shot-lightbox .shot-caption { color: rgba(255,255,255,0.85); margin-top: 12px; font-family: var(--font-mono); font-size: 13px; }

/* ── Undo snackbar (bottom-center, 10s auto-dismiss) ── */
.undo-snackbar {
  position: fixed; left: 50%; bottom: 24px;
  transform: translate(-50%, 24px); opacity: 0;
  display: flex; align-items: center; gap: 16px;
  padding: 12px 18px 12px 20px;
  background: rgba(25, 28, 31, 0.96); color: #fff;
  border-radius: var(--r-pill); box-shadow: 0 20px 48px -8px rgba(0,0,0,0.4);
  font-family: var(--font-body); font-size: 14px; font-weight: 500;
  z-index: 99998; pointer-events: none;
  transition: opacity 200ms ease-out, transform 220ms cubic-bezier(0.16, 1, 0.3, 1);
}
.undo-snackbar.show { opacity: 1; transform: translate(-50%, 0); pointer-events: auto; }
.undo-snackbar .undo-btn {
  background: transparent; border: 1px solid rgba(255,255,255,0.30);
  color: #fff; padding: 5px 14px; border-radius: var(--r-pill);
  font-weight: 600; cursor: pointer; font-family: var(--font-body); font-size: 13px;
}
.undo-snackbar .undo-btn:hover { background: rgba(255,255,255,0.10); border-color: #fff; }
body.dark .undo-snackbar { background: rgba(245, 246, 248, 0.96); color: var(--ink); }
body.dark .undo-snackbar .undo-btn { border-color: rgba(25,28,31,0.30); color: var(--ink); }

/* ── Study list preview cards ── */
.studies-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(440px, 1fr)); gap: 16px; }
.study-saved-on {
  font-family: var(--font-mono); font-size: 10px; color: var(--stone);
  text-transform: uppercase; letter-spacing: 0.4px; margin-left: 8px;
}
.study-preview-del {
  position: absolute; top: 12px; right: 14px;
  width: 24px; height: 24px; padding: 0;
  display: inline-flex; align-items: center; justify-content: center;
  background: transparent; border: 1px solid transparent; border-radius: 50%;
  color: var(--mute); font-size: 12px; cursor: pointer; opacity: 0;
  transition: opacity 0.12s, color 0.12s, background 0.12s, border-color 0.12s;
  z-index: 3;
}
.sip-card:hover .study-preview-del { opacity: 1; }
.study-preview-del:hover { color: var(--neg); background: rgba(226,59,74,0.10); border-color: rgba(226,59,74,0.30); }
.study-potential, .study-intraday {
  display: inline-flex; align-items: center; gap: 4px;
  font-family: var(--font-mono); font-size: 11px; font-weight: 700;
  padding: 3px 8px; border-radius: var(--r-pill); background: var(--surface-soft);
}
.study-potential.pos, .study-intraday.pos { color: var(--pos); background: rgba(0, 168, 126, 0.10); }
.study-potential.neg, .study-intraday.neg { color: var(--neg); background: rgba(226, 59, 74, 0.10); }

/* Study detail re-uses .stock-header from the original stock detail page. The only addition
   is the .stock-header-trade pill row (defined above) and per-section X (below). */

/* Trade pills — small inline pills in the stock-header row (Gain / Stop). Clickable to open OHLCV popup. */
.stock-header-trade { margin-top: 4px; }
.trade-pill { cursor: pointer; }
.trade-pill:hover { box-shadow: 0 0 0 2px rgba(73, 79, 223, 0.12); }
.trade-pill span { font-family: var(--font-mono); margin-left: 6px; font-weight: 700; }

/* Section X — appears top-right of each .study-section card on hover */
.study-section { position: relative; }
.section-x {
  position: absolute; top: 14px; right: 16px;
  width: 24px; height: 24px; padding: 0;
  display: inline-flex; align-items: center; justify-content: center;
  background: transparent; border: 1px solid transparent; border-radius: 50%;
  color: var(--mute); font-size: 14px; cursor: pointer; opacity: 0;
  transition: opacity 0.12s, color 0.12s, background 0.12s, border-color 0.12s;
  z-index: 3;
}
.study-section:hover .section-x { opacity: 1; }
.section-x:hover { color: var(--neg); background: rgba(226,59,74,0.10); border-color: rgba(226,59,74,0.30); }

/* Right-click context menu for restoring hidden sections */
.study-ctx-menu {
  position: fixed; min-width: 200px;
  background: var(--canvas); border: 1px solid var(--hairline); border-radius: var(--r-md);
  box-shadow: 0 24px 48px -8px rgba(0, 0, 0, 0.18);
  padding: 6px; z-index: 9999;
  font-family: var(--font-body); font-size: 13px;
}
.study-ctx-menu-title { padding: 8px 12px 6px; font-size: 11px; color: var(--stone); text-transform: uppercase; letter-spacing: 0.4px; font-weight: 700; }
.study-ctx-menu-item {
  display: block; width: 100%; padding: 8px 12px;
  background: transparent; border: none; text-align: left;
  color: var(--ink); cursor: pointer; border-radius: var(--r-sm);
}
.study-ctx-menu-item:hover { background: var(--surface-soft); color: var(--primary); }

/* OHLCV popup modal — opens on metric chip click. Centered, click-outside dismisses. */
.ohlcv-modal-overlay {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.40);
  display: flex; align-items: center; justify-content: center;
  z-index: 9999; opacity: 0; transition: opacity 160ms ease-out;
  cursor: pointer;
}
.ohlcv-modal-overlay.show { opacity: 1; }
.ohlcv-modal {
  background: var(--canvas); border-radius: var(--r-lg);
  padding: 0; min-width: 360px; max-width: 92vw;
  box-shadow: 0 32px 80px -16px rgba(0,0,0,0.30);
  cursor: default;
  transform: scale(0.96); transition: transform 180ms cubic-bezier(0.16, 1, 0.3, 1);
}
.ohlcv-modal-overlay.show .ohlcv-modal { transform: scale(1); }
.ohlcv-modal-head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 18px 22px; border-bottom: 1px solid var(--hairline);
}
.ohlcv-modal-head h3 { margin: 0; font-family: var(--font-display); font-size: 16px; }
.ohlcv-modal-close {
  width: 30px; height: 30px; padding: 0;
  display: inline-flex; align-items: center; justify-content: center;
  background: transparent; border: none; color: var(--mute);
  font-size: 22px; cursor: pointer; border-radius: 50%;
}
.ohlcv-modal-close:hover { background: var(--surface-soft); color: var(--ink); }
.ohlcv-modal-body {
  display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px;
  padding: 22px;
}
.ohlcv-modal-body .study-ohlcv-field input {
  padding: 8px 12px; font-size: 14px;
}
.ohlcv-modal-foot {
  padding: 14px 22px; border-top: 1px solid var(--hairline);
  display: flex; justify-content: flex-end;
}

/* Editable MS table — cells become flat-styled inputs that look like cells until focused */
.ms-table-editable .ms-cell-input {
  width: 100%; min-width: 0;
  padding: 4px 6px; font-family: var(--font-mono); font-variant-numeric: tabular-nums;
  font-size: 14px; text-align: right;
  background: transparent; color: inherit;
  border: 1px solid transparent; border-radius: var(--r-sm);
  outline: none;
}
.ms-table-editable .ms-cell-input:hover { background: var(--canvas); border-color: var(--hairline); }
.ms-table-editable .ms-cell-input:focus { background: var(--canvas); border-color: var(--primary); }
.ms-table-editable .ms-estimate .ms-cell-input { color: var(--mute); }

/* Notion-style rich notes — contenteditable with inline image embeds */
.study-notes-rich {
  min-height: 200px; padding: 16px 18px;
  border: 1px solid var(--hairline); border-radius: var(--r-sm);
  background: var(--canvas); color: var(--ink); font-family: var(--font-body);
  font-size: 14px; line-height: 1.7;
  transition: border-color 0.12s;
}
.study-notes-rich:focus { outline: none; border-color: var(--primary); }
.study-notes-rich.drag-over { border-color: var(--primary); border-style: dashed; background: rgba(73, 79, 223, 0.04); }
.study-notes-rich:empty:before { content: attr(data-placeholder); color: var(--stone); pointer-events: none; }
.study-notes-rich img {
  max-width: 100%; height: auto;
  border-radius: var(--r-sm); display: block;
  background: var(--surface-soft);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: transform 0.15s;
}
.study-notes-rich img:hover { transform: scale(1.005); }
.study-notes-rich p { margin: 0 0 12px; }
.study-notes-rich p:last-child { margin-bottom: 0; }
/* Inline image wrap — positions the delete X in the top-right corner on hover */
.notes-img-wrap {
  display: inline-block; position: relative; margin: 12px 0;
  max-width: 100%;
}
.notes-img-wrap img { margin: 0; }
.notes-img-del {
  position: absolute; top: 6px; right: 6px;
  width: 24px; height: 24px; padding: 0;
  display: inline-flex; align-items: center; justify-content: center;
  background: rgba(25, 28, 31, 0.85); color: #fff;
  border: none; border-radius: 50%; font-size: 16px; line-height: 1;
  cursor: pointer; opacity: 0;
  transition: opacity 0.12s, background 0.12s;
}
.notes-img-wrap:hover .notes-img-del { opacity: 1; }
.notes-img-del:hover { background: var(--neg); }
.cal-btn svg { width: 13px; height: 13px; }
.cal-popup { position: fixed; top: 0; left: 0; background: var(--canvas); border-radius: var(--r-md); padding: 16px; width: 280px; z-index: 9999; box-shadow: 0 24px 64px -12px rgba(0,0,0,0.25); border: 1px solid var(--hairline); display: none; }
.cal-popup.open { display: block; }
.cal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.cal-header .month-label { font-family: var(--font-display); font-weight: 600; font-size: 16px; }
.cal-nav-btn { width: 28px; height: 28px; border: none; background: var(--surface-soft); border-radius: var(--r-pill); cursor: pointer; font-size: 14px; }
.cal-nav-btn:hover { background: var(--hairline); }
.cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; }
.cal-grid .cal-dow { font-size: 10px; color: var(--stone); text-transform: uppercase; font-weight: 600; text-align: center; padding: 6px 0; }
.cal-day { text-align: center; padding: 8px 0; font-size: 13px; border-radius: var(--r-sm); cursor: pointer; color: var(--ink); font-family: var(--font-body); border: none; background: transparent; }
.cal-day.outside { color: var(--faint); }
.cal-day.has-data { background: rgba(73,79,223,0.08); color: var(--primary); font-weight: 600; }
.cal-day.has-data:hover { background: rgba(73,79,223,0.18); }
.cal-day.active { background: var(--primary); color: #ffffff; font-weight: 600; }
.cal-day.no-data { color: var(--stone); cursor: not-allowed; }
main { padding: 32px; max-width: 1280px; margin: 0 auto; background: var(--surface-soft); min-height: calc(100vh - 60px); }
@media (max-width: 900px) { main { padding: 20px 16px; } }
body { background: var(--surface-soft); }
nav.topbar, header { background: var(--canvas); }
.warning-banner { max-width: 1280px; margin: 16px auto 0; }
.page-title { font-family: var(--font-display); font-size: 28px; font-weight: 600; margin: 0 0 6px; letter-spacing: -0.5px; color: var(--ink); }
.page-sub { font-size: 14px; color: var(--mute); margin-bottom: 20px; }
.subtabs { display: flex; gap: var(--s-sm); margin: 16px 0 20px; align-items: center; }
.subtab { padding: 10px 20px; cursor: pointer; background: var(--canvas); border: 1px solid var(--hairline); font-weight: 600; color: var(--mute); font-size: 14px; border-radius: var(--r-pill); user-select: none; font-family: var(--font-body); transition: all 0.12s; }
.subtab:hover { color: var(--ink); border-color: var(--ink); }
.subtab.active { background: var(--ink); color: #ffffff; border-color: var(--ink); }
.subtab-hint { font-size: 13px; color: var(--mute); margin-left: 4px; }
/* Mismatch-filter toggle (Claude tab toolbar) — pill button. ON state = filled. */
.mismatch-toggle {
  margin-left: auto; padding: 6px 14px; border-radius: var(--r-pill);
  background: var(--canvas); border: 1px solid var(--hairline); color: var(--mute);
  font-size: 12px; font-weight: 600; cursor: pointer; font-family: var(--font-body);
  transition: background 0.12s, color 0.12s, border-color 0.12s;
}
.mismatch-toggle:hover { color: var(--ink); border-color: var(--ink); }
.mismatch-toggle.on { background: var(--ink); color: #ffffff; border-color: var(--ink); }
/* Direction-mismatch banner on a Claude pick card */
.dir-mismatch-banner {
  margin: 8px 0 10px; padding: 8px 12px;
  background: rgba(226, 59, 74, 0.08); color: var(--neg);
  border-left: 3px solid var(--neg); border-radius: var(--r-sm);
  font-size: 12px; font-weight: 500;
}
.sip-card.dir-mismatch { border-color: rgba(226, 59, 74, 0.30); }
.panel { background: var(--canvas); border: 1px solid var(--hairline); border-radius: var(--r-lg); padding: 0; overflow: hidden; }
.panel + .panel { margin-top: 16px; }
.panel-header { padding: 14px 20px; font-family: var(--font-display); font-size: 14px; font-weight: 600; color: var(--ink); background: var(--surface-soft); border-bottom: 1px solid var(--hairline); }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th { background: var(--canvas); padding: 14px 14px; text-align: left; border-bottom: 1px solid var(--hairline); cursor: pointer; user-select: none; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.6px; color: var(--stone); font-family: var(--font-body); }
th:hover { color: var(--ink); }
th.sorted-asc::after { content: " \25B2"; color: var(--primary); }
th.sorted-desc::after { content: " \25BC"; color: var(--primary); }
td { padding: 12px 14px; border-bottom: 1px solid var(--hairline-soft); vertical-align: middle; color: var(--body); }
tr:hover { background: var(--surface-soft); }
td.sym { font-weight: 600; }
td.sym a { color: var(--ink); text-decoration: none; font-family: var(--font-mono); padding: 3px 8px; border-radius: var(--r-sm); font-weight: 700; font-size: 13px; }
td.sym a:hover { background: var(--primary); color: #ffffff; }
td.num { text-align: right; font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 13px; }
.pos { color: var(--pos); font-weight: 600; }
.neg { color: var(--neg); font-weight: 600; }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: var(--r-pill); vertical-align: middle; }
.dot-up { background: var(--pos); }
.dot-down { background: var(--neg); }
.tag { display: inline-block; padding: 4px 12px; border-radius: var(--r-pill); font-size: 11px; font-weight: 700; background: var(--surface-soft); color: var(--mute); letter-spacing: 0.2px; text-transform: lowercase; font-family: var(--font-body); }
.tag-earnings  { background: rgba(73, 79, 223, 0.10); color: var(--primary-deep); }
.tag-analyst   { background: var(--primary); color: #ffffff; }
.tag-news      { background: rgba(0, 168, 126, 0.12); color: var(--accent-teal); }
.tag-ma        { background: rgba(236, 126, 0, 0.12); color: var(--accent-warning); }
.tag-fda       { background: rgba(66, 134, 25, 0.12); color: var(--accent-light-green); }
.tag-contract  { background: rgba(0, 123, 194, 0.12); color: var(--accent-light-blue); }
.tag-momentum  { background: var(--surface-soft); color: var(--stone); }
.scanx-section { background: var(--canvas); border: 1px solid var(--hairline); border-radius: var(--r-lg); padding: 24px 28px; margin-bottom: 16px; }
.scanx-section h2 { font-family: var(--font-display); font-size: 20px; font-weight: 600; margin: 0 0 16px; padding-bottom: 12px; border-bottom: 1px solid var(--hairline); display: flex; align-items: center; gap: 12px; letter-spacing: -0.2px; }
.scanx-section h3 { font-family: var(--font-body); font-size: 11px; margin: 20px 0 10px; font-weight: 700; color: var(--stone); text-transform: uppercase; letter-spacing: 0.8px; }
.scanx-inline { line-height: 2.2; font-size: 15px; color: var(--body); }
.scanx-list { list-style: none; padding: 0; margin: 0; line-height: 1.9; }
.scanx-list li { padding: 4px 0; border-bottom: 1px dotted var(--hairline); font-size: 14px; color: var(--body); }
.scanx-list li:last-child { border-bottom: none; }
.scanx-entry {
  display: inline-flex; align-items: baseline; gap: 6px;
  padding: 3px 8px; border-radius: var(--r-sm);
  text-decoration: none; cursor: pointer;
  transition: background 0.12s;
}
.scanx-list .scanx-entry { display: inline; padding: 4px 6px; }
.scanx-entry:hover { background: var(--surface-soft); }
.scanx-entry .scanx-sym { font-family: var(--font-mono); font-weight: 700; color: var(--ink); }
.scanx-entry .scanx-pct { font-family: var(--font-mono); font-weight: 600; }
.scanx-entry .scanx-pct.pos { color: var(--pos); }
.scanx-entry .scanx-pct.neg { color: var(--neg); }
.scanx-entry .scanx-cat { color: var(--mute); font-weight: 400; }
.scanx-entry .scanx-yoy { font-family: var(--font-mono); font-size: 12px; font-weight: 600; margin-left: 2px; }
.scanx-entry .scanx-yoy.pos { color: var(--pos); }
.scanx-entry .scanx-yoy.neg { color: var(--neg); }
/* Earnings-reaction enriched rows — one card per ticker showing YoY + Surprise metrics inline. */
.scanx-earnings-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 8px; margin: 4px 0 8px;
}
.scanx-earnings-row {
  display: flex; flex-direction: column; gap: 6px;
  padding: 10px 14px; border-radius: var(--r-md);
  background: var(--surface-soft); border: 1px solid var(--hairline-soft);
  text-decoration: none; color: inherit; transition: background 140ms ease, border-color 140ms ease;
}
.scanx-earnings-row:hover { background: var(--canvas); border-color: var(--primary); }
.scanx-earnings-head { display: flex; align-items: baseline; gap: 8px; }
.scanx-earnings-head .scanx-sym { font-size: 15px; }
.scanx-earnings-head .scanx-pct { font-size: 13px; }
.scanx-earnings-metrics { display: flex; flex-wrap: wrap; gap: 4px; }
.scanx-metric {
  display: inline-flex; flex-direction: column; align-items: flex-start;
  padding: 3px 8px; border-radius: var(--r-sm); background: var(--canvas);
  border: 1px solid var(--hairline-soft); min-width: 64px;
}
.scanx-metric-lbl { font-size: 9px; color: var(--stone); font-weight: 600; text-transform: uppercase; letter-spacing: 0.4px; }
.scanx-metric-val { font-family: var(--font-mono); font-size: 12px; font-weight: 700; }
.scanx-metric.pos .scanx-metric-val { color: var(--pos); }
.scanx-metric.neg .scanx-metric-val { color: var(--neg); }
.scanx-earnings-empty { color: var(--stone); font-size: 12px; font-style: italic; }
.breadcrumb { font-size: 13px; margin-bottom: 14px; color: var(--mute); }
.breadcrumb a { color: var(--ink); text-decoration: none; font-weight: 500; }
.breadcrumb a:hover { color: var(--primary); }
.stock-header { background: var(--canvas); padding: 24px 28px; border: 1px solid var(--hairline); border-radius: var(--r-lg); margin-bottom: 16px; display: flex; align-items: center; gap: 20px; flex-wrap: wrap; }
.stock-header .sym-big { font-size: 40px; font-weight: 700; color: var(--ink); font-family: var(--font-mono); letter-spacing: -1px; }
.stock-header .name { font-size: 15px; color: var(--mute); font-weight: 500; }
.stock-header .price { font-size: 26px; font-weight: 700; font-family: var(--font-mono); }
.stock-header .chg { font-size: 14px; font-weight: 600; margin-top: 4px; }
.stock-header .chg.pos { color: var(--pos); }
.stock-header .chg.neg { color: var(--neg); }
.stock-card { background: var(--canvas); border: 1px solid var(--hairline); border-radius: var(--r-lg); padding: 24px 28px; margin-bottom: 16px; position: relative; }
.stock-card h3 { font-family: var(--font-display); font-size: 14px; margin: 0 0 14px; font-weight: 600; color: var(--ink); letter-spacing: -0.1px; }
.stock-card h3 .label-en { font-size: 12px; color: var(--stone); font-weight: 500; margin-left: 6px; }
.news-detail p { margin: 0 0 14px; line-height: 1.75; font-size: 15px; color: var(--body); }
.news-detail p:last-child { margin-bottom: 0; }
.news-detail-placeholder { color: var(--stone); font-style: italic; padding: 12px 0 0; font-size: 13px; }
.news-detail-meta {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 10px; border-radius: var(--r-pill);
  background: var(--surface-soft); color: var(--mute);
  font-size: 12px; font-weight: 500; margin-bottom: 14px;
  font-family: var(--font-mono);
}
.news-detail-meta svg { width: 12px; height: 12px; }

/* Company News history (thefly-style) */
.news-history-card { background: var(--canvas); border: 1px solid var(--hairline); border-radius: var(--r-lg); margin-bottom: 16px; }
.news-history-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 18px 24px;
  border-bottom: 1px solid var(--hairline);
}
.news-history-header .title {
  display: flex; align-items: center; gap: 10px;
  font-family: var(--font-display);
  font-size: 16px; font-weight: 600; color: var(--ink);
}
.news-history-header .title .icon-box {
  width: 32px; height: 32px; border-radius: var(--r-sm);
  background: var(--yellow-light, #fff4c4); color: var(--accent-yellow);
  display: inline-flex; align-items: center; justify-content: center;
}
.news-history-header .expand-btn {
  padding: 6px 14px; background: var(--canvas);
  border: 1px dashed var(--hairline-strong); border-radius: var(--r-sm);
  font-size: 12px; font-weight: 500; cursor: pointer; color: var(--ink);
  display: inline-flex; align-items: center; gap: 6px;
}
.news-history-header .expand-btn:hover { background: var(--surface-soft); }
.news-history-list { max-height: 480px; overflow-y: auto; }
.news-history-group-label {
  padding: 14px 24px 8px; font-size: 13px;
  color: var(--mute); font-weight: 500;
  border-bottom: 1px solid var(--hairline-soft);
  background: var(--surface-soft);
}
.news-item {
  display: flex; gap: 12px; padding: 16px 24px;
  border-bottom: 1px solid var(--hairline-soft);
  cursor: pointer;
}
.news-item:last-child { border-bottom: none; }
.news-item:hover { background: var(--surface-soft); }
.news-item .news-icon {
  flex: 0 0 24px; width: 24px; height: 24px; border-radius: var(--r-sm);
  background: var(--primary); color: #fff;
  display: inline-flex; align-items: center; justify-content: center;
  margin-top: 1px;
}
.news-item .news-icon svg { width: 12px; height: 12px; }
.news-item .news-body { flex: 1 1 auto; }
.news-item .news-title {
  font-size: 15px; font-weight: 600; color: var(--ink);
  line-height: 1.4; margin-bottom: 6px;
}
.news-item .news-meta {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; color: var(--mute);
}
.news-item .news-meta .sym { color: var(--primary); font-weight: 600; }
.news-item .news-meta .sep { color: var(--faint); }
.news-item .news-meta .time { display: inline-flex; align-items: center; gap: 4px; }
.news-item .news-meta .time svg { width: 11px; height: 11px; opacity: 0.7; }
.news-item .news-expand { display: none; }   /* expand chevron retired — news-full always visible */
.news-item .news-full {
  margin-top: 10px; font-size: 14px; color: var(--body);
  line-height: 1.65; display: block;
}
.news-history-empty {
  padding: 40px 24px; text-align: center; color: var(--stone);
  font-size: 14px;
}
.yoy-block { background: var(--canvas); color: var(--ink); padding: 18px 22px; font-family: var(--font-mono); font-size: 14px; white-space: pre; line-height: 1.85; border-radius: var(--r-md); border: 1px solid var(--hairline); font-weight: 500; }
.yoy-hint { font-size: 12px; color: var(--mute); margin-top: 10px; }
.copy-btn { position: absolute; top: 24px; right: 28px; padding: 8px 18px; background: var(--ink); color: #ffffff; border: none; border-radius: var(--r-pill); font-size: 13px; font-weight: 600; font-family: var(--font-body); cursor: pointer; transition: background 0.12s; }
.copy-btn:hover { background: var(--primary); }
.copy-btn.copied { background: var(--accent-teal); }
.ms-table-wrap { overflow-x: auto; margin: -4px; padding: 4px; }
.ms-table { border-collapse: separate; border-spacing: 0; font-size: 14px; width: 100%; min-width: 720px; }
.ms-table th, .ms-table td { padding: 14px 12px; text-align: right; border-bottom: 1px solid var(--hairline); font-family: var(--font-mono); font-variant-numeric: tabular-nums; white-space: nowrap; font-size: 14px; }
.ms-table th { font-size: 13px; font-weight: 700; color: var(--ink); background: var(--canvas); border-bottom: 2px solid var(--ink); padding: 14px 12px 10px; font-family: var(--font-display); letter-spacing: 0; text-transform: none; }
.ms-table th.est-col { color: var(--primary); }
.ms-table .ms-rowlabel { text-align: left; font-family: var(--font-display); font-weight: 700; color: var(--ink); background: var(--surface-soft); font-size: 14px; padding: 14px 16px; border-left: 1px solid var(--hairline); letter-spacing: -0.1px; min-width: 110px; }
.ms-table .ms-reported { background: var(--canvas); color: var(--ink); }
.ms-table .ms-estimate { background: rgba(73, 79, 223, 0.04); color: var(--mute); }
/* Surprise % rows — grey band overlay so they read as a distinct "beat/miss" stripe between
   the value + YoY rows of EPS and the value + YoY rows of Sales. Number content is dimmed to
   60% opacity so it doesn't compete with the bolder YoY % Chg row above.
   No pos/neg background tint here — text color alone signals beat vs miss (looks cleaner). */
.ms-table .ms-surprise       { background: var(--surface-soft); color: var(--ink); }
.ms-table .ms-surprise > *   { opacity: 0.75; }
.ms-table .ms-surprise .pos,
.ms-table .ms-surprise .neg  { background: transparent; }
.ms-table .ms-surprise-label { background: var(--surface-soft); color: var(--charcoal); font-weight: 600; }
.ms-table .ms-divider { border-left: 3px solid var(--primary); }
.ms-table th.ms-divider { border-left: 3px solid var(--primary); }
.ms-table .pos { color: var(--pos); font-weight: 600; background: rgba(0, 168, 126, 0.06); }
.ms-table .neg { color: var(--neg); font-weight: 600; background: rgba(226, 59, 74, 0.06); }
.ms-table .nm { color: var(--stone); }
.ms-est-tag { color: var(--primary); font-weight: 700; font-size: 11px; margin-left: 4px; letter-spacing: 0.3px; }
.chart-wrap { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 900px) { .chart-wrap { grid-template-columns: 1fr; } }
.chart { width: 100%; height: 240px; }
.chart .bar-reported { fill: var(--ink); }
.chart .bar-estimate { fill: var(--primary); }
.chart .bar-hit { cursor: default; }
/* Column hover highlight — sits behind the bars. Sublty toned so it reads as a "selected" hint
   without competing with the bars themselves. Lit via .active class set by the tooltip handler. */
.chart .col-highlight {
  fill: var(--ink);
  opacity: 0;
  pointer-events: none;
  transition: opacity 140ms ease-out;
}
.chart .col-highlight.active { opacity: 0.06; }

/* Global custom tooltip for the EPS / Revenue bar charts.
   Architecture (for natural-feeling motion):
   • Outer #chart-tooltip handles POSITION via transform: translate3d(--tx, --ty, 0).
     A 120ms `cubic-bezier(0.4, 0, 0.2, 1)` transition makes adjacent-quarter pans GLIDE.
   • Inner .ct-inner handles SCALE (0.96 → 1) anchored at bottom-center so the tooltip
     appears to grow from the bar, not slide down from above.
   • A one-frame `.snap` class disables the transform transition during the entrance so the
     tooltip doesn't streak from (0,0) to the cursor on first show. */
#chart-tooltip {
  position: fixed; top: 0; left: 0;
  --tx: 0px;
  --ty: 0px;
  transform: translate3d(var(--tx), var(--ty), 0);
  transition: opacity 140ms ease-out, transform 120ms cubic-bezier(0.4, 0, 0.2, 1);
  opacity: 0;
  pointer-events: none;
  z-index: 9999;
  will-change: transform, opacity;
}
#chart-tooltip.visible { opacity: 1; }
#chart-tooltip.snap    { transition: opacity 140ms ease-out, transform 0ms; }

#chart-tooltip .ct-inner {
  padding: 10px 14px;
  background: rgba(25, 28, 31, 0.96);
  color: #ffffff;
  border-radius: var(--r-md);
  font-family: var(--font-body); font-size: 13px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.28);
  white-space: nowrap;
  transform: scale(0.96);
  transform-origin: 50% 100%;  /* scale anchored at bottom-center — feels rooted at the bar */
  transition: transform 160ms cubic-bezier(0.16, 1, 0.3, 1);
}
#chart-tooltip.visible .ct-inner { transform: scale(1); }

#chart-tooltip .ct-q { font-size: 11px; color: rgba(255,255,255,0.55); text-transform: uppercase; letter-spacing: 0.6px; font-weight: 700; margin-bottom: 6px; }
#chart-tooltip .ct-row { display: flex; align-items: center; gap: 10px; margin-top: 4px; }
#chart-tooltip .ct-row:first-child { margin-top: 0; }
#chart-tooltip .ct-dot { width: 8px; height: 8px; border-radius: 50%; flex: 0 0 8px; }
#chart-tooltip .ct-dot.rep { background: #ffffff; }
#chart-tooltip .ct-dot.est { background: var(--primary); }
#chart-tooltip .ct-lbl { font-weight: 600; min-width: 56px; color: rgba(255,255,255,0.78); }
#chart-tooltip .ct-val { font-family: var(--font-mono); font-weight: 700; color: #ffffff; }
#chart-tooltip .ct-unit { color: rgba(255,255,255,0.5); font-weight: 500; margin-left: 4px; }

@media (prefers-reduced-motion: reduce) {
  #chart-tooltip,
  #chart-tooltip .ct-inner { transition: opacity 0.001ms !important; }
  #chart-tooltip .ct-inner { transform: none !important; }
}
.empty { padding: 80px 20px; text-align: center; color: var(--stone); font-size: 15px; }
.warning-banner { background: rgba(236, 126, 0, 0.10); color: var(--accent-warning); padding: 12px 18px; border-radius: var(--r-md); font-size: 14px; margin: 16px 32px 0; border: 1px solid rgba(236, 126, 0, 0.3); font-weight: 500; }
/* SIPs page cards */
.sip-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
@media (max-width: 960px) { .sip-grid { grid-template-columns: 1fr; } }
.sip-card { background: var(--canvas); border: 1px solid var(--hairline); border-radius: var(--r-lg); padding: 22px 24px; cursor: pointer; }
/* Note: .sip-card transition + hover lift are defined in the Motion section below to keep all easing tokens consistent. */
.sip-card .sip-rank { display: inline-block; padding: 2px 10px; background: var(--ink); color: #ffffff; border-radius: var(--r-pill); font-size: 11px; font-weight: 700; font-family: var(--font-mono); }
.sip-card.featured .sip-rank { background: var(--primary); }
.sip-card .sip-rank-row { display: inline-flex; gap: 6px; align-items: center; margin-bottom: 12px; }
.sip-card .sip-rank-row .day-badge { margin-left: 0; }   /* override the default left-margin from generic .day-badge */
.sip-card .sip-header { display: flex; align-items: baseline; gap: 12px; margin-bottom: 4px; }
.sip-card .sip-sym { font-size: 32px; font-weight: 700; color: var(--ink); font-family: var(--font-mono); letter-spacing: -1px; }
.sip-card .sip-chg { font-size: 16px; font-weight: 600; font-family: var(--font-mono); }
.sip-card .sip-name { font-size: 14px; color: var(--mute); margin-bottom: 16px; }
.sip-card .sip-meta { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }
.sip-card .magna-bits { display: flex; gap: 4px; margin-bottom: 14px; font-family: var(--font-mono); font-size: 12px; }
.sip-card .magna-bit { padding: 3px 8px; border-radius: var(--r-sm); background: var(--surface-soft); color: var(--stone); font-weight: 600; letter-spacing: 0.5px; }
.sip-card .magna-bit.hit { background: var(--ink); color: #ffffff; }
.sip-card .magna-bit.maybe { background: rgba(73,79,223,0.10); color: var(--primary); }
.sip-card .sip-thesis { font-size: 13px; color: var(--body); line-height: 1.6; }
.sip-card .sip-catalyst { font-size: 13px; color: var(--body); line-height: 1.65; margin: 4px 0 14px; min-height: 60px; }
.sip-card .sip-yoy-label { font-size: 10px; color: var(--stone); text-transform: uppercase; letter-spacing: 0.8px; font-weight: 700; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--hairline-soft); display: flex; align-items: center; justify-content: space-between; }
.sip-card .sip-yoy-label .lbl-sub { color: var(--mute); font-weight: 500; letter-spacing: 0.3px; }
.sip-card .sip-yoy-block { background: var(--surface-soft); border-radius: var(--r-sm); padding: 10px 12px; margin-top: 6px; font-family: var(--font-mono); font-size: 12px; white-space: pre; line-height: 1.7; color: var(--ink); border: 1px solid var(--hairline-soft); }
.sip-card .sip-copy-btn {
  padding: 4px 10px;
  background: var(--ink);
  color: #ffffff;
  border: none;
  border-radius: var(--r-pill);
  font-size: 10px;
  font-weight: 600;
  font-family: var(--font-body);
  letter-spacing: 0.3px;
  cursor: pointer;
  text-transform: none;
}
.sip-card .sip-copy-btn:hover { background: var(--charcoal); }
.sip-card .sip-copy-btn.copied { background: var(--accent-teal); }
.sip-empty { padding: 60px 20px; text-align: center; color: var(--stone); font-size: 15px; background: var(--canvas); border: 1px solid var(--hairline); border-radius: var(--r-lg); }
/* day1 / day2 / day3 — based on first-seen date in dashboard archives */
.day-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--r-pill);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.5px;
  vertical-align: middle;
  margin-left: 6px;
  text-transform: lowercase;
  font-family: var(--font-mono);
}
.day-badge.day1 { background: var(--primary); color: #ffffff; }
.day-badge.day2 { background: rgba(73,79,223,0.10); color: var(--primary-deep); }
.day-badge.day3 { background: var(--surface-soft); color: var(--stone); }

/* ── Stat pills (short interest + perf history on SIP cards) ── */
.sip-shortperf { display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0 6px; }
.sip-shortperf-surp { margin-top: 4px; margin-bottom: 6px; }   /* second row: EPS Surp / Rev Surp — tighter gap above */
.stat-pill {
  font-family: var(--font-mono); font-size: 11px; font-weight: 600; letter-spacing: 0.2px;
  padding: 3px 9px; border-radius: var(--r-pill);
  background: var(--surface-soft); color: var(--mute);
  border: 1px solid var(--hairline-soft);
}
.stat-pill.pos { color: var(--pos); }
.stat-pill.neg { color: var(--neg); }
.stat-divider { display: inline-block; width: 1px; height: 14px; background: var(--hairline); margin: 0 2px; vertical-align: middle; }
/* Stock-header inline tag rows.
   • Row 1 (.stock-header-tags): session pills + type tag.
   • Row 2 (.stock-header-short): Short Float + DTC, slightly tighter top-margin so it reads as
     a sub-line under row 1. */
.stock-header-tags { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.stock-header-short { margin-top: 4px; }
.stock-header-surp  { margin-top: 4px; }   /* third row: EPS Surp / Rev Surp */
.stock-header-tags .stat-tag {
  background: var(--surface-soft); color: var(--charcoal);
  font-family: var(--font-mono); letter-spacing: 0.1px;
  text-transform: none; font-weight: 600; padding: 4px 10px;
}
.stock-header-tags .stat-tag.pos { color: var(--pos); }
.stock-header-tags .stat-tag.neg { color: var(--neg); }

/* ── Claude's Pick card variant ── */
.sip-card.claude-pick { border-color: rgba(73,79,223,0.20); }
.sip-rank.claude-rank { background: var(--primary); }
.claude-rationale-label {
  font-size: 10px; color: var(--primary); text-transform: uppercase; letter-spacing: 0.8px;
  font-weight: 700; margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--hairline-soft);
}
.claude-rationale {
  font-size: 14px; color: var(--ink); line-height: 1.7; margin-top: 8px;
  background: rgba(73,79,223,0.04); border-left: 3px solid var(--primary);
  border-radius: var(--r-sm); padding: 12px 14px;
}
.claude-rationale-empty {
  background: var(--surface-soft); border-left-color: var(--hairline);
  color: var(--mute); font-style: italic; font-size: 13px;
}
.claude-rationale code {
  font-family: var(--font-mono); font-size: 12px;
  background: var(--canvas); padding: 1px 5px; border-radius: var(--r-sm);
  color: var(--charcoal);
}

/* ── Short Squeeze toolbar (period-pill switcher above the table) ── */
.squeeze-toolbar { display: flex; align-items: center; gap: 12px; margin: 0 0 12px; flex-wrap: wrap; }
.squeeze-toolbar .toolbar-label { font-size: 12px; color: var(--mute); font-weight: 600; text-transform: uppercase; letter-spacing: 0.4px; }
.squeeze-toolbar .toolbar-hint { font-size: 12px; color: var(--stone); font-style: italic; margin-left: auto; }
.period-pills { display: inline-flex; background: var(--surface-soft); border: 1px solid var(--hairline); border-radius: var(--r-pill); padding: 3px; gap: 2px; }
.period-pill {
  font-family: var(--font-mono); font-size: 12px; font-weight: 600;
  padding: 5px 14px; border-radius: var(--r-pill);
  background: transparent; border: none; cursor: pointer; color: var(--mute);
  transition: background 140ms ease, color 140ms ease;
}
.period-pill:hover { color: var(--ink); }
.period-pill.active { background: var(--ink); color: #ffffff; }

/* ── Short Squeeze page ── */
.squeeze-grid { display: grid; grid-template-columns: 1fr; gap: 12px; }
.squeeze-row {
  display: grid; grid-template-columns: 60px minmax(120px, 1.4fr) repeat(5, minmax(70px, 1fr)) 1.6fr;
  gap: 12px; align-items: center;
  background: var(--canvas); border: 1px solid var(--hairline); border-radius: var(--r-lg);
  padding: 14px 18px; cursor: pointer; text-decoration: none; color: inherit;
}
.squeeze-row:hover { border-color: var(--primary); }
.squeeze-row .sq-rank {
  width: 36px; height: 36px; border-radius: var(--r-pill); background: var(--ink); color: #fff;
  display: inline-flex; align-items: center; justify-content: center;
  font-family: var(--font-mono); font-size: 13px; font-weight: 700;
}
.squeeze-row .sq-sym { font-family: var(--font-mono); font-size: 18px; font-weight: 700; color: var(--ink); }
.squeeze-row .sq-name { font-size: 11px; color: var(--mute); font-weight: 500; margin-top: 2px; }
.squeeze-row .sq-metric { font-family: var(--font-mono); font-size: 14px; font-weight: 600; text-align: right; color: var(--ink); }
.squeeze-row .sq-metric .sq-lbl { display: block; font-size: 9px; color: var(--stone); font-family: var(--font-body); font-weight: 600; text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 2px; }
.squeeze-row .sq-metric .sq-val { font-variant-numeric: tabular-nums; }
.squeeze-row .sq-metric.pos .sq-val { color: var(--pos); }
.squeeze-row .sq-metric.neg .sq-val { color: var(--neg); }
.squeeze-row .sq-cat { font-size: 12px; color: var(--mute); line-height: 1.5; }
.squeeze-header {
  display: grid; grid-template-columns: 60px minmax(120px, 1.4fr) repeat(5, minmax(70px, 1fr)) 1.6fr;
  gap: 12px; padding: 8px 18px; font-size: 10px; text-transform: uppercase; letter-spacing: 0.6px;
  color: var(--stone); font-weight: 700;
}
.squeeze-header > div { text-align: right; }
.squeeze-header > div:nth-child(1), .squeeze-header > div:nth-child(2), .squeeze-header > div:last-child { text-align: left; }
@media (max-width: 900px) {
  .squeeze-row, .squeeze-header { grid-template-columns: 50px 1.5fr repeat(2, 1fr); }
  .squeeze-row .sq-metric:nth-of-type(n+3), .squeeze-row .sq-cat,
  .squeeze-header > div:nth-of-type(n+5):not(:last-child) { display: none; }
}

/* ───────── Motion (Linear/Stripe-style, tasteful) ───────── */
/* All entrance motion: ease-out, 180-240ms, transform+opacity only (GPU-friendly).
   Stagger via --i custom property on each child (capped in JS to first ~12).
   prefers-reduced-motion at the bottom disables every keyframe + heavy transition. */

@keyframes fadeRise {
  from { opacity: 0; transform: translate3d(0, 8px, 0); }
  to   { opacity: 1; transform: translate3d(0, 0, 0); }
}
@keyframes popIn {
  from { opacity: 0; transform: scale(0.96) translateY(-4px); }
  to   { opacity: 1; transform: scale(1) translateY(0); }
}

/* Route transition — replays each time #app gets the .page-anim class. */
main#app.page-anim > * {
  animation: fadeRise 220ms cubic-bezier(0.16, 1, 0.3, 1) both;
}

/* SIP card stagger. --i is set inline; cap ~12 in JS so total stays under ~600ms. */
.sip-card, .squeeze-row {
  animation: fadeRise 240ms cubic-bezier(0.16, 1, 0.3, 1) both;
  animation-delay: calc(var(--i, 0) * 35ms);
  transition: border-color 180ms ease, transform 180ms cubic-bezier(0.16, 1, 0.3, 1), box-shadow 180ms ease;
  will-change: transform;
}
.sip-card:hover, .squeeze-row:hover {
  border-color: var(--primary);
  transform: translateY(-3px);
  box-shadow: 0 12px 28px -16px rgba(5, 0, 56, 0.18);
}

/* Stock-detail cards get the same soft entrance (no stagger needed). */
.stock-card, .news-history-card, .ms-table-wrap, .stock-header {
  animation: fadeRise 220ms cubic-bezier(0.16, 1, 0.3, 1) both;
}

/* Table row stagger — capped in JS to first 12 rows so long lists don't crawl. */
tbody tr.row-anim {
  animation: fadeRise 200ms cubic-bezier(0.16, 1, 0.3, 1) both;
  animation-delay: calc(var(--i, 0) * 22ms);
}
tr { transition: background 140ms ease; }

/* SCANX entries — consistent hover feel. */
.scanx-section, .scanx-entry { transition: background 140ms ease; }

/* Calendar popup — scale + fade from the button (top-right anchor).
   We use display:none/block (from the base rule near top) + a one-shot keyframe on .open
   so the open animation fires reliably when the popup is shown. Close is instant
   (acceptable for a calendar — close-animation isn't worth the visibility-transition jank). */
@keyframes calPopIn {
  from { opacity: 0; transform: scale(0.96) translateY(-4px); }
  to   { opacity: 1; transform: scale(1) translateY(0); }
}
.cal-popup { transform-origin: top right; }
.cal-popup.open {
  animation: calPopIn 160ms cubic-bezier(0.16, 1, 0.3, 1) both;
}

/* Cal day cells — tiny press feel + smoother hover. */
.cal-day { transition: background 120ms ease, color 120ms ease, transform 120ms ease; }
.cal-day:not(.no-data):hover { transform: scale(1.04); }
.cal-day:not(.no-data):active { transform: scale(0.94); }

/* Buttons — universal tap feedback (Linear-style 0.97 squish). */
.cal-btn:active, .copy-btn:active, .sip-copy-btn:active,
.subtab:active, .cal-nav-btn:active, .expand-btn:active {
  transform: scale(0.97);
}
.cal-btn, .copy-btn, .sip-copy-btn, .subtab, .cal-nav-btn {
  transition: background 150ms ease, color 150ms ease, transform 100ms ease, border-color 150ms ease;
  will-change: transform;
}
.copy-btn.copied, .sip-copy-btn.copied {
  animation: popIn 240ms cubic-bezier(0.16, 1, 0.3, 1);
}

/* Nav-link active indicator — fade smoothly. */
nav.topbar .nav-links a { transition: background 160ms ease, color 160ms ease; }

/* td.sym pill hover — slightly more polish on the inline ticker chips. */
td.sym a { transition: background 140ms ease, color 140ms ease; }

/* Warning banner slide-down. */
.warning-banner { animation: fadeRise 240ms cubic-bezier(0.16, 1, 0.3, 1) both; }

/* ── Respect prefers-reduced-motion ── */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.001ms !important;
    animation-delay: 0ms !important;
    transition-duration: 0.001ms !important;
  }
  .sip-card:hover { transform: none; box-shadow: none; }
  .cal-day:hover, .cal-day:active { transform: none; }
}
</style>
</head>
<body>
<nav class="topbar" id="nav">
  <div class="topbar-inner">
    <a class="brand" href="#/sips">SIPs</a>
    <div class="nav-links">
      <a data-route="sips">Today's SIPs</a>
      <a data-route="squeeze">Short Squeeze</a>
      <a data-route="earnings">Earnings Results</a>
      <a data-route="catalyst">Catalyst Deep Dive</a>
      <a data-route="scanx">SCANX</a>
      <a data-route="gappers">Gappers</a>
      <a data-route="studies">Studies</a>
    </div>
    <div class="topbar-right" id="topbar-right">
      <span class="readonly-badge" title="Sidecar (local Python server) not detected — viewing the committed snapshot. Run `py D:/SIPs/sidecar.py` to edit.">&#128274; View only</span>
      <button class="topbar-iconbtn" id="theme-toggle" aria-label="Toggle dark mode" title="Toggle dark mode">
        <svg id="theme-icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"></path></svg>
        <svg id="theme-icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:none"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
      </button>
      <button class="cal-btn" id="cal-btn" aria-label="Select date">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
        <span id="cal-btn-label">Select date</span>
      </button>
      <div class="cal-popup" id="cal-popup"></div>
    </div>
  </div>
</nav>
<div id="banner-holder"></div>
<main id="app"></main>
<div id="chart-tooltip" role="tooltip" aria-hidden="true"></div>
<script>
const STATE = { date: null, dates: [], data: null,
  // Sidecar mode = the local Python sidecar at 127.0.0.1:5510 is running.
  //   true  → Studies edits write through to disk (dashboard/studies/*).
  //   false → hosted GitHub Pages: read-only, all edit affordances disabled.
  // Detected once on boot via GET /api/health.
  sidecar: { available: false, checked: false, info: null },
  // Image-path index built by sidecar: { imgKey: 'imgKey.png' }. Used in read-only
  // mode to render <img src="studies/images/<filename>"> without probing extensions.
  imgIndex: null,
};
let DATA = null;

const fmtPct = v => v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
const fmtPctShort = v => v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
const fmtEps = v => v == null ? '—' : v.toFixed(2);
const fmtRev = v => {
  if (v == null) return '—';
  if (Math.abs(v) >= 1000) return (v/1000).toFixed(2) + 'B';
  return v.toFixed(1) + 'M';
};
const fmtVol = v => {
  if (v == null) return '—';
  if (v >= 1e6) return (v/1e6).toFixed(2) + 'M';
  return (v/1000).toFixed(0) + 'K';
};
const fmtPrice = v => v == null ? '—' : '$' + v.toFixed(2);
const cls = v => v == null ? '' : (v > 0 ? 'pos' : v < 0 ? 'neg' : '');
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
// Colorize a Forward YoY block (multiline text) — wraps each numeric value in a span.
// Positive numbers → green (.pos), negative → red (.neg), N/M and N/A → muted (.nm).
function colorizeYoyBlock(text) {
  if (!text) return '';
  return escapeHtml(text).replace(/([+\-]\d+\.\d+%|N\/[MA])/g, m => {
    if (m === 'N/M' || m === 'N/A') return `<span class="nm">${m}</span>`;
    const v = parseFloat(m);
    const cls = v > 0 ? 'pos' : v < 0 ? 'neg' : '';
    return `<span class="${cls}">${m}</span>`;
  });
}
function formatLabelHint(isoDate) {
  const d = new Date(isoDate + 'T00:00:00');
  const next = new Date(d); next.setDate(next.getDate() + 1);
  const monShort = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${monShort[d.getMonth()]} ${d.getDate()} 盤後 + ${monShort[next.getMonth()]} ${next.getDate()} 盤前`;
}

/* ═════ Sidecar detection + disk hydration for Studies ═════
   The local sidecar (D:/SIPs/sidecar.py) serves the same static files as
   `python -m http.server` PLUS write endpoints under /api/. We probe /api/health
   once on boot to decide:
     - sidecar.available = true  → Studies edits write through to disk; offer normal editing UX.
     - sidecar.available = false → we're on GitHub Pages (or sidecar isn't running); read-only mode.
   Either way, on boot we try to load `studies/studies.json` + `studies/images/index.json` so
   the user's most-recently-committed library shows up — that's what makes hosted Pages a
   "personal backup viewable on phone" rather than an empty shell. */
async function detectSidecar() {
  try {
    const r = await fetch('/api/health', {cache: 'no-store'});
    if (!r.ok) throw new Error('non-200');
    const info = await r.json();
    STATE.sidecar.available = !!info.ok && !!info.writable;
    STATE.sidecar.info = info;
  } catch (_) {
    STATE.sidecar.available = false;
  }
  STATE.sidecar.checked = true;
  document.body.classList.toggle('readonly-mode', !STATE.sidecar.available);
}

async function hydrateStudiesFromDisk() {
  // Pull the canonical studies file written by sidecar (or committed by /SIPs Phase 11).
  // Disk wins over localStorage: this is the "phone shows what my desktop saved last" path.
  try {
    const r = await fetch('studies/studies.json', {cache: 'no-store'});
    if (!r.ok) return;
    const arr = await r.json();
    if (Array.isArray(arr) && arr.length > 0) {
      // Replace localStorage so the rest of the app reads from a single source of truth.
      localStorage.setItem(STUDIES_KEY, JSON.stringify(arr));
    } else if (Array.isArray(arr) && arr.length === 0 && STATE.sidecar.available) {
      // Disk is empty but localStorage might have a pre-sidecar library — migrate it up.
      const local = JSON.parse(localStorage.getItem(STUDIES_KEY) || '[]');
      if (Array.isArray(local) && local.length > 0) {
        await postStudiesToDisk(local);
      }
    }
  } catch (_) { /* file may not exist yet — fine */ }
  // Image index (key → filename) so we can render <img> in read-only mode without probing.
  try {
    const r = await fetch('studies/images/index.json', {cache: 'no-store'});
    if (r.ok) STATE.imgIndex = await r.json();
  } catch (_) { /* no index yet */ }
}

async function boot() {
  try {
    const r = await fetch('dates.json', {cache: 'no-store'});
    STATE.dates = await r.json();
  } catch (e) { STATE.dates = []; }
  if (STATE.dates.length === 0) {
    const r = await fetch('data.json', {cache: 'no-store'});
    STATE.data = await r.json();
    STATE.date = STATE.data.date;
    STATE.dates = [{date: STATE.date, label: STATE.date}];
  }
  // Sidecar probe + studies hydration happen in parallel with route render.
  await detectSidecar();
  await hydrateStudiesFromDisk();
  installOutsideClickHandler();
  installChartTooltip();
  installThemeToggle();
  renderDateStrip();
  route();
}

/* Cross-date helpers */
async function loadDateData(d) {
  try {
    const r = await fetch(`data/${d}.json`, {cache: 'no-store'});
    if (!r.ok) return null;
    return await r.json();
  } catch (e) { return null; }
}
// Cache previous-day data to flag "new today" vs "repeated" stocks
const __prevCache = {};
async function getPrevDateData() {
  // Find the most recent date BEFORE STATE.date
  const idx = STATE.dates.findIndex(d => d.date === STATE.date);
  if (idx < 0 || idx + 1 >= STATE.dates.length) return null;
  const prevDate = STATE.dates[idx + 1].date;
  if (__prevCache[prevDate]) return __prevCache[prevDate];
  const d = await loadDateData(prevDate);
  __prevCache[prevDate] = d;
  return d;
}
// Return Set of symbols that appeared in any earlier date (cross-date dedup helper)
let __prevSymbolsSet = null;
async function getEarlierSymbolsSet() {
  if (__prevSymbolsSet) return __prevSymbolsSet;
  const idx = STATE.dates.findIndex(d => d.date === STATE.date);
  const earlier = STATE.dates.slice(idx + 1);
  const s = new Set();
  for (const d of earlier) {
    const data = await loadDateData(d.date);
    if (data && data.stocks) Object.keys(data.stocks).forEach(k => s.add(k));
  }
  __prevSymbolsSet = s;
  return s;
}

// Per-symbol first-seen date map; powers day1/day2/day3 labels.
// day1 = first seen TODAY (current STATE.date)
// day2 = first seen on the date immediately before STATE.date
// day3 = first seen 2+ days before STATE.date
let __firstSeenMap = null;
async function getSymbolFirstSeenMap() {
  if (__firstSeenMap) return __firstSeenMap;
  const m = new Map();
  // Walk ALL dates (oldest → newest) so the first hit wins
  const sortedDates = [...STATE.dates].sort((a, b) => a.date.localeCompare(b.date));
  for (const d of sortedDates) {
    const data = await loadDateData(d.date);
    if (!data || !data.stocks) continue;
    Object.keys(data.stocks).forEach(sym => {
      if (!m.has(sym)) m.set(sym, d.date);
    });
  }
  __firstSeenMap = m;
  return m;
}
function dayLabel(firstSeenIso, currentIso) {
  if (!firstSeenIso || !currentIso) return null;
  const a = new Date(firstSeenIso + 'T00:00:00');
  const b = new Date(currentIso + 'T00:00:00');
  const diff = Math.round((b.getTime() - a.getTime()) / 86400000);
  if (diff <= 0) return 'day1';
  if (diff === 1) return 'day2';
  return 'day3';
}

// Day-label with reset override.
// If the current date's data file has `dayResets[symbol]` set, treat that symbol as day1
// for THIS date only (used when the ticker has a NEW major catalyst — vs being pure
// momentum continuation of an old catalyst). Otherwise fall back to the historical walk.
function dayLabelWithReset(sym, firstSeenMap, currentIso) {
  if (DATA?.dayResets && Object.prototype.hasOwnProperty.call(DATA.dayResets, sym)) return 'day1';
  return dayLabel(firstSeenMap.get(sym), currentIso);
}

function parseHash() {
  // Default landing route is Today's SIPs (Claude 精選 subtab kicks in via renderSips's own default).
  const h = location.hash.slice(1) || '/sips';
  const parts = h.split('/').filter(Boolean);
  let date = null, routeVal = 'sips', arg = null;
  if (parts.length && /^\d{4}-\d{2}-\d{2}$/.test(parts[0])) date = parts.shift();
  if (parts.length) routeVal = parts.shift();
  if (parts.length) arg = parts.shift();
  return { date, route: routeVal, arg };
}

async function route() {
  const { date, route: r, arg } = parseHash();
  const targetDate = date || STATE.dates[0]?.date;
  if (targetDate && targetDate !== STATE.date) {
    const url = `data/${targetDate}.json`;
    try {
      const resp = await fetch(url, {cache: 'no-store'});
      if (!resp.ok) throw new Error('404');
      STATE.data = await resp.json();
      STATE.date = targetDate;
      clearBanner();
    } catch (e) {
      const latest = STATE.dates[0]?.date;
      if (latest) {
        const resp = await fetch(`data/${latest}.json`, {cache: 'no-store'});
        STATE.data = await resp.json();
        STATE.date = latest;
        showBanner(`所選日期 ${targetDate} 無資料；顯示最新日期 (${latest})。`);
      }
    }
  }
  if (!STATE.data) return;
  DATA = STATE.data;
  document.querySelectorAll('nav .nav-links a').forEach(a => a.classList.toggle('active', a.dataset.route === r));
  renderDateStrip();
  // Invalidate previous-symbols cache when date changes
  __prevSymbolsSet = null;
  // Route transition: strip + re-add .page-anim so the entrance keyframe replays.
  // Force a reflow between removal and re-add or the browser coalesces the class flip and skips the animation.
  const _appEl = document.getElementById('app');
  if (_appEl) {
    _appEl.classList.remove('page-anim');
    void _appEl.offsetWidth;  // reflow flush
    _appEl.classList.add('page-anim');
  }
  if (r === 'sips')     return renderSips(arg);
  if (r === 'squeeze')  return renderSqueeze();
  if (r === 'earnings') return renderEarnings();
  if (r === 'catalyst') return renderCatalyst();
  if (r === 'scanx')    return renderScanx();
  if (r === 'gappers')  return renderGappers();
  if (r === 'studies')  return renderStudies();
  if (r === 'study' && arg) return renderStudyDetail(arg);
  if (r === 'stock' && arg) return renderStock(arg);
  renderSips();
}

// Stagger helper: set --i on the first `cap` matching elements. Anything beyond gets --i: cap so
// it still fades in but doesn't extend total runtime past ~cap * step.
function staggerChildren(selector, cap = 12) {
  const els = document.querySelectorAll(selector);
  els.forEach((el, i) => el.style.setProperty('--i', String(Math.min(i, cap))));
}

window.addEventListener('hashchange', route);
document.querySelectorAll('nav .nav-links a').forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    const isLatest = STATE.date === STATE.dates[0]?.date;
    location.hash = '#/' + (isLatest ? '' : STATE.date + '/') + a.dataset.route;
  });
});

function showBanner(msg) {
  document.getElementById('banner-holder').innerHTML = `<div class="warning-banner">${escapeHtml(msg)}</div>`;
}
function clearBanner() { document.getElementById('banner-holder').innerHTML = ''; }

function renderDateStrip() {
  // cal-btn shows the active date directly (e.g. "5/15 Fri") — no separate pill strip.
  const label = document.getElementById('cal-btn-label');
  if (label) {
    const active = STATE.dates.find(d => d.date === STATE.date);
    label.textContent = active ? active.label : 'Select date';
  }
  // cal-btn is rendered once in HTML body — wire its click here (idempotent)
  const calBtn = document.getElementById('cal-btn');
  if (calBtn) calBtn.onclick = e => { e.stopPropagation(); toggleCalendar(); };
}

// Attach the outside-click listener ONCE at boot (not per render)
let __outsideClickInstalled = false;
function installOutsideClickHandler() {
  if (__outsideClickInstalled) return;
  __outsideClickInstalled = true;
  document.addEventListener('click', e => {
    const popup = document.getElementById('cal-popup');
    const btn = document.getElementById('cal-btn');
    if (popup && popup.classList.contains('open') && !popup.contains(e.target) && btn && e.target !== btn && !btn.contains(e.target)) {
      popup.classList.remove('open');
    }
  });
}

function navigateDate(d) {
  const { route: r, arg } = parseHash();
  const isLatest = d === STATE.dates[0].date;
  let h = '#/';
  if (!isLatest) h += d + '/';
  h += r;
  if (arg) h += '/' + arg;
  if (location.hash === h) route();
  else location.hash = h;
}

let calMonth = null;
function toggleCalendar() {
  const popup = document.getElementById('cal-popup');
  if (popup.classList.contains('open')) { popup.classList.remove('open'); return; }
  const cur = new Date(STATE.date + 'T00:00:00');
  calMonth = { year: cur.getFullYear(), month: cur.getMonth() };
  renderCalendar();
  popup.classList.add('open');
  // Position popup near the cal-btn using fixed coords
  const btn = document.getElementById('cal-btn');
  if (btn) {
    const r = btn.getBoundingClientRect();
    popup.style.left = (r.right - 280) + 'px';
    popup.style.top  = (r.bottom + 8) + 'px';
  }
}

function renderCalendar() {
  const popup = document.getElementById('cal-popup');
  const { year, month } = calMonth;
  const monthNames = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  const dowNames = ['Su','Mo','Tu','We','Th','Fr','Sa'];
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);
  const startWeekday = firstDay.getDay();
  const daysInMonth = lastDay.getDate();
  const dateSet = new Set(STATE.dates.map(d => d.date));
  let html = `<div class="cal-header"><button class="cal-nav-btn" id="cal-prev">‹</button><div class="month-label">${monthNames[month]} ${year}</div><button class="cal-nav-btn" id="cal-next">›</button></div><div class="cal-grid">`;
  dowNames.forEach(d => html += `<div class="cal-dow">${d}</div>`);
  for (let i = 0; i < startWeekday; i++) {
    const prevDate = new Date(year, month, -startWeekday + i + 1);
    html += `<button class="cal-day outside" disabled>${prevDate.getDate()}</button>`;
  }
  for (let day = 1; day <= daysInMonth; day++) {
    const iso = `${year}-${String(month + 1).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
    const hasData = dateSet.has(iso);
    const isActive = iso === STATE.date;
    const classes = ['cal-day'];
    if (isActive) classes.push('active');
    else if (hasData) classes.push('has-data');
    else classes.push('no-data');
    html += `<button class="${classes.join(' ')}" data-iso="${iso}" ${!hasData ? 'disabled' : ''}>${day}</button>`;
  }
  html += '</div>';
  popup.innerHTML = html;
  document.getElementById('cal-prev').onclick = e => { e.stopPropagation(); calMonth.month--; if (calMonth.month < 0) { calMonth.month = 11; calMonth.year--; } renderCalendar(); };
  document.getElementById('cal-next').onclick = e => { e.stopPropagation(); calMonth.month++; if (calMonth.month > 11) { calMonth.month = 0; calMonth.year++; } renderCalendar(); };
  popup.querySelectorAll('.cal-day:not(.outside):not(.no-data):not([disabled])').forEach(btn => {
    btn.onclick = e => { e.stopPropagation(); popup.classList.remove('open'); navigateDate(btn.dataset.iso); };
  });
}

function makeTable(container, rows, columns, defaultSortIdx, defaultDesc) {
  let sortIdx = defaultSortIdx, sortDir = (defaultDesc === true) ? -1 : 1;
  let isFirstRender = true;
  function render() {
    const sorted = [...rows].sort((a, b) => {
      const av = columns[sortIdx].sortVal(a);
      const bv = columns[sortIdx].sortVal(b);
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * sortDir;
      return String(av).localeCompare(String(bv)) * sortDir;
    });
    let html = '<table><thead><tr>';
    columns.forEach((c, i) => {
      const sc = i === sortIdx ? (sortDir === -1 ? 'sorted-desc' : 'sorted-asc') : '';
      html += `<th class="${sc}" data-i="${i}">${c.label}</th>`;
    });
    html += '</tr></thead><tbody>';
    sorted.forEach((r, idx) => {
      // FIRST render: every row fades in. Stagger ramps up over first 12 rows then plateaus —
      // rows 12+ all share --i=12 so the total entrance never exceeds ~12 × 22ms = 264ms,
      // but no row appears instantly (fixes the "後面好像沒動畫" issue on long lists).
      // Sort clicks (isFirstRender = false) drop the class entirely so re-renders feel instant.
      const animAttr = isFirstRender ? ` class="row-anim" style="--i:${Math.min(idx, 12)}"` : '';
      html += `<tr${animAttr}>` + columns.map(c => c.render(r)).join('') + '</tr>';
    });
    html += '</tbody></table>';
    container.innerHTML = html;
    isFirstRender = false;
    container.querySelectorAll('th').forEach(th => {
      th.onclick = () => {
        const i = +th.dataset.i;
        if (i === sortIdx) sortDir = -sortDir;
        else { sortIdx = i; sortDir = -1; }
        render();
      };
    });
  }
  render();
}

function typeTagClass(t) {
  return ({
    'earnings':'tag-earnings','guidance':'tag-earnings',
    'analyst':'tag-analyst','news':'tag-news',
    'M&A':'tag-ma','ma':'tag-ma',
    'FDA':'tag-fda','clinical':'tag-fda','fda':'tag-fda',
    'contract':'tag-contract','momentum':'tag-momentum',
  }[t] || 'tag-momentum');
}

/* ============================================================
   MAGNA53 scoring + SIPs page
   M assive — EPS growth ≥100%, Sales ≥100%, EPS surprise ≥100%, OR Rev YoY ≥100%
   G ap up — ≥4% gap on earnings day
   N eglect — stock was quiet/under-bid before today: 3M perf ≤ 0% AND 12M perf ≤ +15% (hit)
              or 3M perf between 0–+10% (maybe). Higher than that = not neglected.
   A cceleration — Sales accel ≥25%
   5 — Short interest >5 days to cover (from Finviz shortRatio field)
   3 — ≥3 analyst price target raises (not available from our data → 'maybe')
   ============================================================ */
function magna53(s) {
  const tv = s.tv;
  const bits = { M: false, G: false, N: 'maybe', A: false, _5: 'maybe', _3: 'maybe' };
  // Gap (G)
  bits.G = Math.abs(s.chgPct) >= 4.0;
  if (tv) {
    const epsSurp = tv.surpriseEPS_pct;
    const revSurp = tv.surpriseRev_pct;
    const revYoY  = tv.yrYrRev_pct;
    const epsYoY  = tv.epsYoY_pct;
    if ((epsSurp != null && epsSurp >= 100) ||
        (revSurp != null && revSurp >= 100) ||
        (revYoY  != null && revYoY  >= 100) ||
        (epsYoY  != null && epsYoY  >= 100))  {
      bits.M = true;
    }
    if (revYoY != null && revYoY >= 25) bits.A = true;
  }
  // Neglect (N) — decided manually by Claude (via claude_picks.json `neglected: true|false`).
  // Algorithm doesn't auto-flag any more; the perf 1M/3M/6M/12M pills on the card show
  // the raw history so Claude/you can judge whether the stock was truly under-bid.
  if (s.neglected === true)       bits.N = true;
  else if (s.neglected === false) bits.N = false;
  // else: bits.N stays 'maybe' (default)
  // 5 — days-to-cover (Finviz shortRatio)
  if (s.shortRatio != null) bits._5 = s.shortRatio >= 5 ? true : false;
  // Score
  let score = 0;
  if (bits.M) score += 5;
  if (bits.G) score += 2;
  if (bits.A) score += 3;
  if (bits.N === true) score += 2;
  if (bits._5 === true) score += 1;
  const heavyCatalyst = { 'earnings': 4, 'guidance': 3, 'contract': 3, 'M&A': 3, 'ma': 3, 'FDA': 3, 'fda': 3, 'clinical': 3, 'analyst': 2 };
  score += (heavyCatalyst[s.type] || 0);
  if (s.type === 'momentum') score -= 6;
  if (s.type === 'news' && !bits.M) score -= 2;
  if (Math.abs(s.chgPct) >= 15) score += 1;
  if (s.sessions && s.sessions.length >= 2) score += 1;
  return { bits, score };
}

// Render a single MAGNA-bit chip with three states: hit / maybe / off.
function magnaChip(label, state) {
  const cls = state === true ? 'hit' : (state === 'maybe' ? 'maybe' : '');
  return `<span class="magna-bit ${cls}">${label}</span>`;
}

// Card stats line — Short Float + DTC only. Perf history is hidden per user spec; Claude makes
// the neglect call manually (set `neglected: true` on a pick in claude_picks.json to light N up).
function shortPerfLine(s) {
  // Row 1: Short Float + DTC (Finviz-sourced shorts metrics).
  const shortBits = [];
  if (s.shortFloat != null) shortBits.push(`<span class="stat-pill" title="Short Float — % of float currently shorted">Short Float ${s.shortFloat.toFixed(1)}%</span>`);
  if (s.shortRatio != null) shortBits.push(`<span class="stat-pill" title="Days to cover (short ratio)">DTC ${s.shortRatio.toFixed(1)}d</span>`);
  // Row 2: EPS / Rev Surprise % (TradingView FQ-sourced earnings surprise metrics). Pos/neg tinted.
  const surpBits = [];
  const tv = s.tv;
  if (tv && tv.surpriseEPS_pct != null) {
    const v = tv.surpriseEPS_pct, cn = v >= 0 ? 'pos' : 'neg';
    surpBits.push(`<span class="stat-pill ${cn}" title="EPS surprise vs consensus (TradingView FQ)">EPS Surp ${(v >= 0 ? '+' : '') + v.toFixed(1)}%</span>`);
  }
  if (tv && tv.surpriseRev_pct != null) {
    const v = tv.surpriseRev_pct, cn = v >= 0 ? 'pos' : 'neg';
    surpBits.push(`<span class="stat-pill ${cn}" title="Revenue surprise vs consensus (TradingView FQ)">Rev Surp ${(v >= 0 ? '+' : '') + v.toFixed(1)}%</span>`);
  }
  if (!shortBits.length && !surpBits.length) return '';
  return [
    shortBits.length ? `<div class="sip-shortperf">${shortBits.join('')}</div>` : '',
    surpBits.length  ? `<div class="sip-shortperf sip-shortperf-surp">${surpBits.join('')}</div>` : '',
  ].join('');
}

// Build the Forward-YoY copy block (used by both MAGNA + Claude's Pick tabs).
function forwardYoyBlock(s) {
  if (!(s.tv && s.tv.yoyBlock)) return '';
  return `<div class="sip-yoy-label"><span>Forward YoY <span class="lbl-sub">EPS / Rev</span></span><button class="sip-copy-btn" data-copy-target="sip-yoy-${s.symbol}">Copy</button></div><div class="sip-yoy-block" id="sip-yoy-${s.symbol}" data-raw="${escapeHtml(s.tv.yoyBlock)}">${colorizeYoyBlock(s.tv.yoyBlock)}</div>`;
}

// Helper: render a day-1/2/3 badge (or empty string if firstSeen unknown).
function dayBadgeHtml(s) {
  const d = s._dayLabel;
  return d ? `<span class="day-badge ${d}">${d}</span>` : '';
}

function sipCardHtml(s, idx) {
  const isFeatured = idx < 3;
  const m = s._m53;
  const chgCls = s.chgPct >= 0 ? 'pos' : 'neg';
  const sessTags = s.sessions.map(x => `<span class="tag">${x.session.toUpperCase()} <span class="dot dot-${x.direction}"></span> ${fmtPctShort(x.chgPct)}</span>`).join(' ');
  const magnaHtml = magnaChip('M', m.bits.M) + magnaChip('G', m.bits.G) + magnaChip('N', m.bits.N) + magnaChip('A', m.bits.A) + magnaChip('5', m.bits._5) + magnaChip('3', m.bits._3);
  const catalystText = s.catalyst || '(無催化劑資料)';
  return `<a class="sip-card ${isFeatured ? 'featured' : ''}" href="#/stock/${s.symbol}" style="text-decoration:none;color:inherit;display:block;position:relative">
    ${saveStudyBtnHtml(s.symbol)}
    <span class="sip-rank-row"><span class="sip-rank">#${idx + 1}</span>${dayBadgeHtml(s)}</span>
    <div class="sip-header"><div class="sip-sym">${s.symbol}</div><div class="sip-chg ${chgCls}">${fmtPct(s.chgPct)}</div></div>
    <div class="sip-name">${escapeHtml(s.name)}</div>
    <div class="sip-meta">${sessTags} <span class="tag ${typeTagClass(s.type)}">${s.type}</span></div>
    <div class="magna-bits">${magnaHtml}</div>
    ${shortPerfLine(s)}
    <div class="sip-catalyst">${escapeHtml(catalystText)}</div>
    ${forwardYoyBlock(s)}
  </a>`;
}

// Claude's Pick card — emphasizes Claude's per-ticker rationale.
// Forward YoY block is shown when available (catalyst-only tickers without TV data simply skip it).
function claudePickCardHtml(s, idx) {
  const isFeatured = idx < 3;
  const chgCls = s.chgPct >= 0 ? 'pos' : 'neg';
  const sessTags = s.sessions.map(x => `<span class="tag">${x.session.toUpperCase()} <span class="dot dot-${x.direction}"></span> ${fmtPctShort(x.chgPct)}</span>`).join(' ');
  const rationale = s._claudeRationale || '';
  const rationaleHtml = rationale
    ? `<div class="claude-rationale">${escapeHtml(rationale).replace(/\n/g, '<br>')}</div>`
    : `<div class="claude-rationale claude-rationale-empty">（Claude 尚未提供分析——在 <code>D:\\SIPs\\claude_picks.json</code> 寫入 <code>{"symbol":"${s.symbol}","rationale":"..."}</code> 後 rebuild 即可。）</div>`;
  // Direction-mismatch banner — only shown when the toolbar toggle is ON and this pick's
  // declared intent disagrees with the actual chgPct sign.
  const mismatchBanner = s._claudeDirMismatch
    ? `<div class="dir-mismatch-banner">⚠️ 方向不符：intent=<b>${s._claudeIntent}</b> 但 chgPct=${fmtPctShort(s.chgPct)}</div>`
    : '';
  return `<a class="sip-card claude-pick ${isFeatured ? 'featured' : ''} ${s._claudeDirMismatch ? 'dir-mismatch' : ''}" href="#/stock/${s.symbol}" style="text-decoration:none;color:inherit;display:block;position:relative">
    ${saveStudyBtnHtml(s.symbol, s._claudeRationale, s._claudeIntent)}
    <span class="sip-rank-row"><span class="sip-rank claude-rank">#${idx + 1}</span>${dayBadgeHtml(s)}</span>
    ${mismatchBanner}
    <div class="sip-header"><div class="sip-sym">${s.symbol}</div><div class="sip-chg ${chgCls}">${fmtPct(s.chgPct)}</div></div>
    <div class="sip-name">${escapeHtml(s.name)}</div>
    <div class="sip-meta">${sessTags} <span class="tag ${typeTagClass(s.type)}">${s.type}</span></div>
    ${shortPerfLine(s)}
    <div class="claude-rationale-label">${t('claude-rationale-label')}</div>
    ${rationaleHtml}
    ${forwardYoyBlock(s)}
  </a>`;
}

// Module-level toggle: when ON, the Claude tab also shows picks whose `intent` doesn't match
// today's chgPct direction (e.g. a "long" pick on a stock that gapped down). Default OFF.
let SHOW_MISMATCHED_PICKS = false;

async function renderSips(subtab) {
  // Subtabs: 'claude' (default) — Claude-curated picks with rationale | 'magna' — MAGNA53 algorithmic score.
  // Default is Claude per user spec: algorithmic ranking includes shorts mixed in with longs, which is
  // confusing on a "Today's SIPs" landing. Claude's curated list is direction-aware (see filter below).
  const tab = (subtab === 'magna') ? 'magna' : 'claude';
  const app = document.getElementById('app');
  app.innerHTML = `
    <h2 class="page-title">Today's SIPs</h2>
    <div class="subtabs" id="sips-subtabs">
      <div class="subtab ${tab === 'claude' ? 'active' : ''}" data-sub="claude">Claude 精選</div>
      <div class="subtab ${tab === 'magna'  ? 'active' : ''}" data-sub="magna">MAGNA53 排序</div>
      <span class="subtab-hint" id="sips-hint"></span>
      ${tab === 'claude' ? `<button class="mismatch-toggle ${SHOW_MISMATCHED_PICKS ? 'on' : ''}" id="mismatch-toggle" title="顯示方向不符的 picks（intent vs chgPct 不一致）">
        ${SHOW_MISMATCHED_PICKS ? '✓ 包含方向不符' : '⊘ 隱藏方向不符'}
      </button>` : ''}
    </div>
    <div id="sips-stack"></div>`;
  // Wire subtab clicks → re-route via hash so URL is shareable. Claude is now the default
  // (no suffix); /magna is the explicit override.
  document.querySelectorAll('#sips-subtabs .subtab').forEach(t => {
    t.onclick = () => {
      const sub = t.dataset.sub;
      const isLatest = STATE.date === STATE.dates[0]?.date;
      location.hash = '#/' + (isLatest ? '' : STATE.date + '/') + 'sips' + (sub === 'claude' ? '' : '/' + sub);
    };
  });
  // Wire mismatch-filter toggle (only present on Claude tab) → flip the module flag + re-render in place.
  const mt = document.getElementById('mismatch-toggle');
  if (mt) mt.onclick = () => { SHOW_MISMATCHED_PICKS = !SHOW_MISMATCHED_PICKS; renderSips(subtab); };
  // Day1/2/3 label: walk previous date snapshots so a ticker that already showed up earlier in the
  // week gets tagged day2 / day3 instead of day1. The map is cached across calls within a session.
  const firstSeen = await getSymbolFirstSeenMap();
  const rows = Object.values(DATA.stocks).map(s => ({
    ...s,
    _m53: magna53(s),
    _dayLabel: dayLabelWithReset(s.symbol, firstSeen, DATA.date),
  }));
  const stack = document.getElementById('sips-stack');
  const hint = document.getElementById('sips-hint');
  hint.textContent = '';   // hint slot reserved but no count text per user spec
  if (tab === 'magna') {
    rows.sort((a, b) => b._m53.score - a._m53.score);
    const top = rows.filter(r => r._m53.score >= 4).slice(0, 12);
    if (top.length === 0) {
      stack.innerHTML = `<div class="sip-empty">No SIPs for ${STATE.date}. Use the date selector to view another day's scan.</div>`;
      return;
    }
    stack.innerHTML = '<div class="sip-grid">' + top.map((s, idx) => sipCardHtml(s, idx)).join('') + '</div>';
  } else {
    // Claude picks come from DATA.claudePicks (an array of {symbol, rank, rationale, intent?}).
    // Direction-match rule (per user spec): a `long` pick must be gap-up (chgPct > 0), a `short`
    // pick must be gap-down (chgPct < 0). When SHOW_MISMATCHED_PICKS is false (default), mismatches
    // are silently dropped. When true (via the toolbar toggle), mismatches are SHOWN but marked
    // with `_claudeDirMismatch: true` so the card can render a visual warning.
    // `intent` defaults to "long" when missing (legacy schema).
    const picks = Array.isArray(DATA.claudePicks) ? DATA.claudePicks.slice() : [];
    picks.sort((a, b) => (a.rank ?? 999) - (b.rank ?? 999));
    const bySym = Object.fromEntries(rows.map(r => [r.symbol, r]));
    const isMismatch = s => {
      if (s._claudeIntent === 'long')  return !(s.chgPct > 0);
      if (s._claudeIntent === 'short') return !(s.chgPct < 0);
      return false;
    };
    const all = picks
      .map(p => bySym[p.symbol]
        ? { ...bySym[p.symbol], _claudeRationale: p.rationale, _claudeIntent: p.intent || 'long' }
        : null)
      .filter(Boolean)
      .map(s => ({ ...s, _claudeDirMismatch: isMismatch(s) }));
    const enriched = SHOW_MISMATCHED_PICKS ? all : all.filter(s => !s._claudeDirMismatch);
    const droppedCount = all.length - enriched.length;
    if (enriched.length === 0) {
      stack.innerHTML = `<div class="sip-empty">尚無 Claude 精選清單${droppedCount > 0 ? `（${droppedCount} 筆方向跟市場不符已隱藏，按上方 toggle 顯示）` : ''}。<br><br>在 <code>D:\\SIPs\\claude_picks.json</code> 加入 <code>{"picks":[{"symbol":"X","rank":1,"rationale":"...","intent":"long"}]}</code> 後 rebuild dashboard 即可看到。</div>`;
      return;
    }
    if (!SHOW_MISMATCHED_PICKS && droppedCount > 0) {
      hint.textContent = `${enriched.length} picks shown · ${droppedCount} hidden (direction mismatch)`;
    } else if (SHOW_MISMATCHED_PICKS) {
      hint.textContent = `${enriched.length} picks shown (including mismatched)`;
    }
    stack.innerHTML = '<div class="sip-grid">' + enriched.map((s, idx) => claudePickCardHtml(s, idx)).join('') + '</div>';
  }
  staggerChildren('.sip-grid > .sip-card', 12);
  // Wire up Copy buttons (don't navigate when clicking copy)
  stack.querySelectorAll('.sip-copy-btn').forEach(btn => {
    btn.addEventListener('click', async (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      const tgt = document.getElementById(btn.dataset.copyTarget);
      if (!tgt) return;
      const text = tgt.dataset.raw || tgt.textContent;
      try { await navigator.clipboard.writeText(text); }
      catch (e) { const ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove(); }
      btn.textContent = 'Copied!'; btn.classList.add('copied');
      setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 1200);
    });
  });
}

function renderEarnings() {
  const app = document.getElementById('app');
  const pre = [], post = [];
  Object.values(DATA.stocks).filter(s => s.type === 'earnings' && s.tv).forEach(s => {
    s.sessions.forEach(sess => {
      const row = {...s, _sess: sess};
      (sess.session === 'pre' ? pre : post).push(row);
    });
  });
  // Default = combined view (both pre + post visible from the start)
  const active = new Set(['pre', 'post']);
  app.innerHTML = `
    <h2 class="page-title">Earnings Results</h2>
    <div class="subtabs">
      <div class="subtab active" data-sess="pre">Pre-Market (${pre.length})</div>
      <div class="subtab active" data-sess="post">Post-Market (${post.length})</div>
      <span class="subtab-hint" id="ear-hint"></span>
    </div>
    <div id="ear-stack"></div>
  `;
  // Standard columns (single-session view)
  const baseCols = [
    { label: 'Symbol',    sortVal: r => r.symbol,                  render: r => `<td class="sym">${r.symbol}</td>` },
    { label: 'EPS Surp $', sortVal: r => r.tv.surpriseEPS_dollar,  render: r => `<td class="num ${cls(r.tv.surpriseEPS_dollar)}">${fmtEps(r.tv.surpriseEPS_dollar)}</td>` },
    { label: 'EPS Surp %', sortVal: r => r.tv.surpriseEPS_pct,     render: r => `<td class="num ${cls(r.tv.surpriseEPS_pct)}">${fmtPct(r.tv.surpriseEPS_pct)}</td>` },
    { label: 'EPS YoY',   sortVal: r => r.tv.epsYoY_pct,           render: r => `<td class="num ${cls(r.tv.epsYoY_pct)}">${fmtPct(r.tv.epsYoY_pct)}</td>` },
    { label: 'Actual',    sortVal: r => r.tv.latestEPS,            render: r => `<td class="num">${fmtEps(r.tv.latestEPS)}</td>` },
    { label: 'Consensus', sortVal: r => r.tv.consensusEPS,         render: r => `<td class="num">${fmtEps(r.tv.consensusEPS)}</td>` },
    { label: '1 Yr Ago',  sortVal: r => r.tv.priorYrEPS,           render: r => `<td class="num">${fmtEps(r.tv.priorYrEPS)}</td>` },
    { label: 'Actual Rev',sortVal: r => r.tv.latestRev_M,          render: r => `<td class="num">${fmtRev(r.tv.latestRev_M)}</td>` },
    { label: 'Cons Rev',  sortVal: r => r.tv.consensusRev_M,       render: r => `<td class="num">${fmtRev(r.tv.consensusRev_M)}</td>` },
    { label: 'Rev Surp %',sortVal: r => r.tv.surpriseRev_pct,      render: r => `<td class="num ${cls(r.tv.surpriseRev_pct)}">${fmtPct(r.tv.surpriseRev_pct)}</td>` },
    { label: 'YoY Rev',   sortVal: r => r.tv.yrYrRev_pct,          render: r => `<td class="num ${cls(r.tv.yrYrRev_pct)}">${fmtPct(r.tv.yrYrRev_pct)}</td>` },
    { label: 'Today %Chg',sortVal: r => r._sess.chgPct,            render: r => `<td class="num ${cls(r._sess.chgPct)}">${fmtPct(r._sess.chgPct)}</td>` },
  ];
  // Combined columns: insert Session as second column when both sessions are active.
  // Session label reads _sessLabel ("PRE", "POST", or "BOTH") set during dedupe below.
  const combinedCols = [
    baseCols[0],
    { label: 'Session', sortVal: r => r._sessLabel || r._sess.session, render: r => `<td><span class="tag" style="padding:2px 8px;font-size:10px">${r._sessLabel || r._sess.session.toUpperCase()}</span></td>` },
    ...baseCols.slice(1),
  ];
  // Dedupe pre + post rows by symbol. If a ticker appears in BOTH sessions, keep the row
  // with the larger |chgPct| and tag _sessLabel = "BOTH" so the table shows one row per ticker.
  function dedupeCombined(pre, post) {
    const bySym = new Map();
    for (const r of [...pre, ...post]) {
      const existing = bySym.get(r.symbol);
      if (!existing) {
        bySym.set(r.symbol, { ...r, _sessLabel: r._sess.session.toUpperCase() });
      } else {
        const better = Math.abs(r._sess.chgPct) > Math.abs(existing._sess.chgPct) ? r : existing;
        bySym.set(r.symbol, { ...existing, _sess: better._sess, _sessLabel: 'BOTH' });
      }
    }
    return Array.from(bySym.values());
  }
  // After Session insertion, default-sort index shifts: YoY Rev is now at idx 8 (was 7)
  function bindEarningsRowClicks(container) {
    container.querySelectorAll('tbody tr').forEach(tr => {
      tr.style.cursor = 'pointer';
      tr.onclick = () => {
        const sym = tr.querySelector('td.sym')?.textContent?.trim();
        if (sym) location.hash = `#/stock/${sym}`;
      };
    });
  }
  function rerender() {
    const stack = document.getElementById('ear-stack');
    const hint = document.getElementById('ear-hint');
    document.querySelectorAll('.subtab[data-sess]').forEach(t => t.classList.toggle('active', active.has(t.dataset.sess)));
    hint.textContent = '';
    stack.innerHTML = '';
    let body;
    if (active.size === 2) {
      const combined = dedupeCombined(pre, post);
      const wrap = document.createElement('div');
      wrap.className = 'panel';
      wrap.innerHTML = `<div class="panel-header">Pre-Market / Post-Market</div><div class="panel-body"></div>`;
      stack.appendChild(wrap);
      body = wrap.querySelector('.panel-body');
      makeTable(body, combined, combinedCols, 11, true);   // default sort: YoY Rev desc
    } else {
      const sess = active.has('pre') ? 'pre' : 'post';
      const data = sess === 'pre' ? pre : post;
      const wrap = document.createElement('div');
      wrap.className = 'panel';
      wrap.innerHTML = `<div class="panel-body"></div>`;
      stack.appendChild(wrap);
      body = wrap.querySelector('.panel-body');
      makeTable(body, data, baseCols, 10, true);   // default sort: YoY Rev desc
    }
    bindEarningsRowClicks(body);
    new MutationObserver(() => bindEarningsRowClicks(body)).observe(body, { childList: true, subtree: true });
  }
  document.querySelectorAll('.subtab[data-sess]').forEach(t => {
    t.onclick = (ev) => {
      const s = t.dataset.sess;
      if (ev.shiftKey) {
        if (active.has(s)) { if (active.size > 1) active.delete(s); }
        else active.add(s);
      } else { active.clear(); active.add(s); }
      rerender();
    };
  });
  rerender();
}

async function renderCatalyst() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <h2 class="page-title">Catalyst Deep Dive</h2>
    <div class="panel" id="cat-panel"></div>
  `;
  const firstSeen = await getSymbolFirstSeenMap();
  // Inverted ranks so default-desc sort (down-arrow) puts day1 at the top, day3 at the bottom —
  // that's what "newest gappers first" should feel like, since day1 is the freshest sighting.
  const dayRank = { day1: 3, day2: 2, day3: 1, null: 0 };
  const rows = Object.values(DATA.stocks).map(s => {
    const d = dayLabelWithReset(s.symbol, firstSeen, DATA.date);
    return { ...s, _day: d, _scanDate: DATA.date };
  });
  const cols = [
    { label: 'Symbol', sortVal: r => r.symbol, render: r => `<td class="sym">${r.symbol}${r._day ? `<span class="day-badge ${r._day}">${r._day}</span>` : ''}</td>` },
    { label: 'Price', sortVal: r => r.last, render: r => `<td class="num">${fmtPrice(r.last)}</td>` },
    { label: '%Chg', sortVal: r => r.chgPct, render: r => `<td class="num ${cls(r.chgPct)}">${fmtPct(r.chgPct)}</td>` },
    { label: 'Volume', sortVal: r => r.volume, render: r => `<td class="num">${fmtVol(r.volume)}</td>` },
    { label: 'Session', sortVal: r => r.primarySession, render: r => `<td>${r.primarySession}</td>` },
    { label: 'Scan Date', sortVal: r => r._scanDate, render: r => `<td style="font-family:var(--font-mono);font-size:11px;color:var(--mute)">${r._scanDate}</td>` },
    { label: 'Day', sortVal: r => dayRank[r._day] ?? 0, render: r => `<td>${r._day ? `<span class="day-badge ${r._day}">${r._day}</span>` : ''}</td>` },
    { label: 'Dir', sortVal: r => r.primaryDirection, render: r => `<td><span class="dot dot-${r.primaryDirection}"></span></td>` },
    { label: 'Type', sortVal: r => r.type, render: r => `<td><span class="tag ${typeTagClass(r.type)}">${r.type}</span></td>` },
    { label: 'Catalyst', sortVal: r => r.catalyst, render: r => `<td style="font-size:13px;line-height:1.5;max-width:600px;color:var(--body)">${escapeHtml(r.catalyst)}</td>` },
  ];
  makeTable(document.getElementById('cat-panel'), rows, cols, 2, true);
  // Make the whole row clickable as a button → stock detail page
  const panel = document.getElementById('cat-panel');
  function bindRowClicks() {
    panel.querySelectorAll('tbody tr').forEach((tr, i) => {
      tr.style.cursor = 'pointer';
      tr.onclick = (e) => {
        // The td.sym contains <text>SYMBOL</text><span class="day-badge">day2</span>
        // so .textContent returns "AIIOday2" — strip everything after the first run of ticker chars.
        const raw = tr.querySelector('td.sym')?.textContent || '';
        const sym = raw.match(/^[A-Z][A-Z0-9.\-]*/)?.[0];
        if (sym) location.hash = `#/stock/${sym}`;
      };
    });
  }
  bindRowClicks();
  // Re-bind after any sort (makeTable re-renders the tbody)
  const observer = new MutationObserver(bindRowClicks);
  observer.observe(panel, { childList: true, subtree: true });
}

/* ============================================================
   Page: Gappers — raw Barchart candidates (all stocks, both directions)
   Sortable by every column. Click a row to open the stock detail.
   Default sort: |%Chg| desc.
   ============================================================ */
/* ============================================================
   Short Squeeze page — sortable table.
   Columns: Symbol, DTC, 1M, 3M, 6M, 12M, Cap, Catalyst.
   Default sort: DTC descending (highest days-to-cover first). Click any header to re-sort.
   Tickers without shortRatio are skipped (no DTC = can't rank).
   ============================================================ */
function fmtMcap(m) {
  if (m == null) return '—';
  if (m >= 1000) return (m/1000).toFixed(1) + 'B';
  return m.toFixed(0) + 'M';
}

function renderSqueeze() {
  const app = document.getElementById('app');
  const rows = Object.values(DATA.stocks).filter(s => s.shortRatio != null);
  app.innerHTML = `
    <h2 class="page-title">Short Squeeze</h2>
    ${rows.length === 0
      ? `<div class="sip-empty">尚無 Finviz 嘎空資料。<br><br>跑 <code>node D:\\SIPs\\finviz-shorts.js</code> 抓今日候選的 short float / short ratio / market cap，再 rebuild dashboard。</div>`
      : `<div class="panel"><div class="panel-body" id="squeeze-table"></div></div>`}
  `;
  if (rows.length === 0) return;

  const body = document.getElementById('squeeze-table');

  // Pre/Post-market % come from the row's session-specific entries. A ticker may have just one
  // (only pre or only post moved) or both — auto-fills as each scan adds data. null → "—".
  const prePct  = r => r.sessions?.find(x => x.session === 'pre')?.chgPct;
  const postPct = r => r.sessions?.find(x => x.session === 'post')?.chgPct;
  const numPct = v => v == null
    ? '<td class="num">—</td>'
    : `<td class="num ${cls(v)}">${fmtPct(v)}</td>`;
  const cols = [
    { label: 'Symbol',       sortVal: r => r.symbol,
      render: r => `<td class="sym">${r.symbol}</td>` },
    { label: 'Short Float',  sortVal: r => r.shortFloat ?? -Infinity,
      render: r => r.shortFloat == null ? '<td class="num">—</td>' : `<td class="num">${r.shortFloat.toFixed(1)}%</td>` },
    { label: 'DTC',          sortVal: r => r.shortRatio,
      render: r => `<td class="num">${r.shortRatio.toFixed(1)}d</td>` },
    { label: 'Pre %',        sortVal: r => prePct(r)  ?? -Infinity,
      render: r => numPct(prePct(r)) },
    { label: 'Post %',       sortVal: r => postPct(r) ?? -Infinity,
      render: r => numPct(postPct(r)) },
    { label: 'YoY Rev',      sortVal: r => r.tv?.yrYrRev_pct ?? -Infinity,
      render: r => numPct(r.tv?.yrYrRev_pct) },
    { label: 'YoY EPS',      sortVal: r => r.tv?.epsYoY_pct ?? -Infinity,
      render: r => numPct(r.tv?.epsYoY_pct) },
    { label: 'Cap',          sortVal: r => r.marketCap_M ?? Infinity,
      render: r => `<td class="num">${fmtMcap(r.marketCap_M)}</td>` },
    { label: 'Catalyst',     sortVal: r => r.catalyst || '',
      render: r => `<td>${escapeHtml(r.catalyst || '—')}</td>` },
  ];

  // Default sort: DTC desc (col index 2).
  makeTable(body, rows, cols, 2, true);

  function bindClicks() {
    body.querySelectorAll('tbody tr').forEach(tr => {
      tr.style.cursor = 'pointer';
      tr.onclick = () => {
        const raw = tr.querySelector('td.sym')?.textContent || '';
        const sym = raw.match(/^[A-Z][A-Z0-9.\-]*/)?.[0];
        if (sym) location.hash = `#/stock/${sym}`;
      };
    });
  }
  bindClicks();
  new MutationObserver(bindClicks).observe(body, { childList: true, subtree: true });
}

function renderGappers() {
  const app = document.getElementById('app');
  // Data source priority:
  //   1. DATA.rawGappers — every row from today's Barchart scrape, unfiltered (pre/post advances/declines).
  //   2. fallback for older snapshots without rawGappers: synthesize from DATA.stocks.
  let rows;
  const isRaw = Array.isArray(DATA.rawGappers) && DATA.rawGappers.length > 0;
  if (isRaw) {
    rows = DATA.rawGappers.map(r => ({
      symbol: r.symbol, name: r.name,
      last: r.last, chgPct: r.chgPct, absChg: Math.abs(r.chgPct),
      volume: r.volume, session: r.session, direction: r.direction,
      prevClose: r.prevClose, nextEarnings: r.nextEarnings,
      passedFilter: r.passedFilter,
      type: (DATA.stocks[r.symbol] || {}).type || '',
    }));
  } else {
    rows = [];
    Object.values(DATA.stocks).forEach(s => {
      (s.sessions || []).forEach(sess => {
        rows.push({
          symbol: s.symbol, name: s.name,
          last: sess.last ?? s.last, chgPct: sess.chgPct, absChg: Math.abs(sess.chgPct),
          volume: sess.volume ?? s.volume,
          session: sess.session, direction: sess.direction,
          type: s.type, passedFilter: true,
        });
      });
    });
  }
  const upCount   = rows.filter(r => r.direction === 'up').length;
  const downCount = rows.filter(r => r.direction === 'down').length;
  const passedCt  = rows.filter(r => r.passedFilter).length;
  const filt = DATA.rawGappersFilter || { chgMin: 4, volMin: 100000 };
  let dirFilter = 'all';
  let passFilter = 'all';   // 'all' / 'passed' / 'failed'
  app.innerHTML = `
    <h2 class="page-title">Gappers</h2>
    <p class="page-sub">${isRaw
      ? `Raw Barchart universe — ${rows.length} rows from pre + post-market advances/declines. <span style="color:var(--stone)">Filter cutoff: |%Chg| ≥ ${filt.chgMin}%, Volume ≥ ${(filt.volMin/1000).toFixed(0)}k</span>`
      : `Filtered candidates only (no rawGappers in this snapshot).`}</p>
    <div class="subtabs">
      <div class="subtab active" data-dir="all">All (${rows.length})</div>
      <div class="subtab" data-dir="up"><span class="dot dot-up"></span>&nbsp; Up (${upCount})</div>
      <div class="subtab" data-dir="down"><span class="dot dot-down"></span>&nbsp; Down (${downCount})</div>
      ${isRaw ? `
        <span style="width:1px;height:24px;background:var(--hairline);margin:0 8px"></span>
        <div class="subtab active" data-pass="all">All filter</div>
        <div class="subtab" data-pass="passed">Passed (${passedCt})</div>
        <div class="subtab" data-pass="failed">Below cutoff (${rows.length - passedCt})</div>
      ` : ''}
    </div>
    <div class="panel" id="gap-panel"></div>
  `;
  const baseCols = [
    { label: 'Symbol', sortVal: r => r.symbol, render: r => `<td class="sym">${r.symbol}</td>` },
    { label: 'Name',   sortVal: r => r.name,   render: r => `<td style="max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--mute);font-size:12px">${escapeHtml(r.name || '')}</td>` },
    { label: 'Price',  sortVal: r => r.last,   render: r => `<td class="num">${fmtPrice(r.last)}</td>` },
    { label: '%Chg',   sortVal: r => r.chgPct, render: r => `<td class="num ${cls(r.chgPct)}">${fmtPct(r.chgPct)}</td>` },
    // |%Chg| column retired — it was an absolute-value sort key but rendered positive numbers in red,
    // which looked like a bug (down -25% showing as red "25.60%"). %Chg above has the proper -X% sign.
    { label: 'Volume', sortVal: r => r.volume, render: r => `<td class="num">${fmtVol(r.volume)}</td>` },
    { label: 'Session',sortVal: r => r.session,render: r => `<td><span class="tag" style="padding:2px 8px;font-size:10px">${r.session.toUpperCase()}</span></td>` },
    { label: 'Dir',    sortVal: r => r.direction, render: r => `<td><span class="dot dot-${r.direction}"></span></td>` },
  ];
  const rawExtraCols = [
    { label: 'Prev Close', sortVal: r => r.prevClose, render: r => `<td class="num" style="color:var(--mute);font-size:12px">${r.prevClose != null ? '$' + Number(r.prevClose).toFixed(2) : '—'}</td>` },
    { label: 'Next ER',    sortVal: r => r.nextEarnings || '', render: r => `<td style="font-size:12px;color:var(--mute);font-family:var(--font-mono)">${r.nextEarnings || '—'}</td>` },
    { label: 'Filter',     sortVal: r => r.passedFilter ? 1 : 0, render: r => r.passedFilter
        ? `<td><span class="tag" style="background:rgba(0,168,126,0.12);color:var(--accent-teal);padding:2px 8px;font-size:10px">PASSED</span></td>`
        : `<td><span class="tag" style="padding:2px 8px;font-size:10px">below</span></td>` },
  ];
  const legacyTypeCol = { label: 'Type', sortVal: r => r.type, render: r => `<td><span class="tag ${typeTagClass(r.type)}">${r.type}</span></td>` };
  const cols = isRaw ? [...baseCols, ...rawExtraCols] : [...baseCols, legacyTypeCol];
  const panel = document.getElementById('gap-panel');
  function bindRows() {
    panel.querySelectorAll('tbody tr').forEach(tr => {
      tr.style.cursor = 'pointer';
      tr.onclick = () => {
        const sym = tr.querySelector('td.sym')?.textContent?.trim();
        if (sym) location.hash = `#/stock/${sym}`;
      };
    });
  }
  function rerender() {
    let data = rows;
    if (dirFilter !== 'all')      data = data.filter(r => r.direction === dirFilter);
    if (passFilter === 'passed')  data = data.filter(r => r.passedFilter);
    else if (passFilter === 'failed') data = data.filter(r => !r.passedFilter);
    document.querySelectorAll('.subtab[data-dir]').forEach(t => t.classList.toggle('active', t.dataset.dir === dirFilter));
    document.querySelectorAll('.subtab[data-pass]').forEach(t => t.classList.toggle('active', t.dataset.pass === passFilter));
    makeTable(panel, data, cols, 4, true);   // default sort: |%Chg| desc (col idx 4)
    bindRows();
  }
  document.querySelectorAll('.subtab[data-dir]').forEach(t => { t.onclick = () => { dirFilter = t.dataset.dir; rerender(); }; });
  document.querySelectorAll('.subtab[data-pass]').forEach(t => { t.onclick = () => { passFilter = t.dataset.pass; rerender(); }; });
  rerender();
  new MutationObserver(bindRows).observe(panel, { childList: true, subtree: true });
}

function renderScanx() {
  const app = document.getElementById('app');
  const sx = DATA.scanx;
  // Generic inline: ticker + colored %chg.
  const inlineFmt = lst => lst.map(e => {
    const pctCls = e.chg >= 0 ? 'pos' : 'neg';
    return `<a class="scanx-entry" href="#/stock/${e.symbol}"><span class="scanx-sym">${e.symbol}</span> <span class="scanx-pct ${pctCls}">${fmtPctShort(e.chg)}</span></a>`;
  }).join(', ');
  // Earnings-reaction inline: same as above + (Rev YoY ±N%) appended after the % when TV data exists.
  const earningsInlineFmt = lst => lst.map(e => {
    const pctCls = e.chg >= 0 ? 'pos' : 'neg';
    const tv = (DATA.stocks[e.symbol] || {}).tv;
    let revYoY = '';
    if (tv && tv.yrYrRev_pct != null) {
      const v = Math.round(tv.yrYrRev_pct);
      const cn = v >= 0 ? 'pos' : 'neg';
      revYoY = ` <span class="scanx-yoy ${cn}">(Rev ${v >= 0 ? '+' : ''}${v}%)</span>`;
    }
    return `<a class="scanx-entry" href="#/stock/${e.symbol}"><span class="scanx-sym">${e.symbol}</span> <span class="scanx-pct ${pctCls}">${fmtPctShort(e.chg)}</span>${revYoY}</a>`;
  }).join(', ');
  const listFmt = lst => lst.map(e => {
    const pctCls = e.chg >= 0 ? 'pos' : 'neg';
    return `<li><a class="scanx-entry" href="#/stock/${e.symbol}"><span class="scanx-sym">${e.symbol}</span> <span class="scanx-pct ${pctCls}">${fmtPctShort(e.chg)}</span> <span class="scanx-cat">（${escapeHtml(e.catalyst)}）</span></a></li>`;
  }).join('');
  app.innerHTML = `
    <h2 class="page-title">SCANX</h2>
    <div class="scanx-section">
      <h2><span class="dot dot-up"></span> Gapping up</h2>
      <h3>In reaction to earnings/guidance</h3>
      <div class="scanx-inline">${earningsInlineFmt(sx.gapUpEarnings)}</div>
      <h3>Other news</h3>
      <ul class="scanx-list">${listFmt(sx.gapUpOther)}</ul>
    </div>
    <div class="scanx-section">
      <h2><span class="dot dot-down"></span> Gapping down</h2>
      <h3>In reaction to earnings/guidance</h3>
      <div class="scanx-inline">${earningsInlineFmt(sx.gapDownEarnings)}</div>
      <h3>Other news</h3>
      <ul class="scanx-list">${listFmt(sx.gapDownOther)}</ul>
    </div>
  `;
}

function yoyPct(curr, prior, isEps) {
  if (curr == null || prior == null) return { txt: 'N/A', val: null };
  if (prior === 0) return { txt: 'N/M', val: null };
  // Universal "improvement = positive, deterioration = negative" formula.
  // Works for all sign combinations:
  //   both positive (5 → 8):       (8-5)/|5|  = +60%
  //   both negative (-0.41→-0.77): (-0.77+0.41)/0.41 = -88%   (loss widened)
  //   loss → profit (-0.40→0.50):  (0.50+0.40)/0.40  = +225%  (big improvement)
  //   profit → loss (0.50→-0.40):  (-0.40-0.50)/0.50 = -180%  (big deterioration)
  const pct = (curr - prior) / Math.abs(prior) * 100;
  const r = Math.round(pct);
  return { txt: (r >= 0 ? '+' : '') + r + '%', val: r };
}

function renderMarketSurgeTable(chart) {
  if (!chart || !chart.quarters || !chart.quarters.length) return '<div style="color:var(--stone);padding:20px">No quarterly data</div>';
  const q = chart.quarters, er = chart.eps_reported, ee = chart.eps_estimate, rr = chart.rev_reported_M, re = chart.rev_estimate_M, li = chart.latest_idx;
  const N = Math.min(11, q.length);
  let start = Math.max(0, li - 4);
  let end = Math.min(q.length, start + N);
  start = Math.max(0, end - N);
  const cells = [];
  // Surprise %: reported beat/missed estimate for the SAME quarter, computed via universal formula
  // (curr - prior) / |prior| * 100 so negative-consensus (e.g. ONDS) doesn't blank out.
  // Future quarters with only an estimate have no reported, so surprise = N/A.
  const surpPct = (rep, est) => {
    if (rep == null || est == null || est === 0) return { txt: 'N/A', val: null };
    const pct = (rep - est) / Math.abs(est) * 100;
    const r = Math.round(pct);
    return { txt: (r >= 0 ? '+' : '') + r + '%', val: r };
  };
  for (let i = start; i < end; i++) {
    const isReported = er[i] != null;
    const eps = isReported ? er[i] : ee[i];
    const rev = (rr[i] != null) ? rr[i] : re[i];
    const epsPrior = er[i-4] != null ? er[i-4] : null;
    const revPrior = rr[i-4] != null ? rr[i-4] : null;
    cells.push({
      q: q[i], eps, rev, isReported,
      epsYoY:  yoyPct(eps, epsPrior, true),
      revYoY:  yoyPct(rev, revPrior, false),
      epsSurp: surpPct(er[i], ee[i]),
      revSurp: surpPct(rr[i], re[i]),
    });
  }
  const firstEstIdx = cells.findIndex(c => !c.isReported);
  const fmtSales = v => {
    if (v == null) return '';
    if (Math.abs(v) >= 1000) return v.toLocaleString('en-US', {minimumFractionDigits:1, maximumFractionDigits:1});
    return v.toFixed(1);
  };
  const fmtEpsCell = v => v == null ? '' : v.toFixed(2);
  const fmtYoY = (txt, val) => {
    if (txt === 'N/M' || txt === 'N/A') return `<span class="nm">${txt}</span>`;
    const c = val > 0 ? 'pos' : val < 0 ? 'neg' : '';
    return `<span class="${c}">${txt}</span>`;
  };
  let head = '<tr>';
  cells.forEach((c, i) => {
    const div = (i === firstEstIdx && firstEstIdx > 0) ? 'ms-divider' : '';
    const estCls = c.isReported ? '' : 'est-col';
    const tag = c.isReported ? '' : ' <span class="ms-est-tag">est</span>';
    head += `<th class="${div} ${estCls}">${c.q}${tag}</th>`;
  });
  head += '<th class="ms-rowlabel"></th></tr>';
  function row(label, key, fmt) {
    let html = '<tr>';
    cells.forEach((c, i) => {
      const div = (i === firstEstIdx && firstEstIdx > 0) ? 'ms-divider' : '';
      const klass = c.isReported ? 'ms-reported' : 'ms-estimate';
      html += `<td class="${klass} ${div}">${fmt(c[key])}</td>`;
    });
    html += `<td class="ms-rowlabel">${label}</td></tr>`;
    return html;
  }
  function yoyRow(label, key) {
    let html = '<tr>';
    cells.forEach((c, i) => {
      const div = (i === firstEstIdx && firstEstIdx > 0) ? 'ms-divider' : '';
      const klass = c.isReported ? 'ms-reported' : 'ms-estimate';
      html += `<td class="${klass} ${div}">${fmtYoY(c[key].txt, c[key].val)}</td>`;
    });
    html += `<td class="ms-rowlabel">${label}</td></tr>`;
    return html;
  }
  // Surprise % row — only reported quarters have a value (estimate-only future quarters render
  // blank, since "surprise vs estimate" is meaningless when there's no reported number yet).
  // Rendered with `ms-surprise` class for the grey separator-band background.
  function surpRow(label, key) {
    let html = '<tr class="ms-surprise-row">';
    cells.forEach((c, i) => {
      const div = (i === firstEstIdx && firstEstIdx > 0) ? 'ms-divider' : '';
      // Blank cell for non-reported quarters or when surprise is N/A.
      const content = c.isReported && c[key].val != null
        ? fmtYoY(c[key].txt, c[key].val)
        : '';
      html += `<td class="ms-surprise ${div}">${content}</td>`;
    });
    html += `<td class="ms-rowlabel ms-surprise-label">${label}</td></tr>`;
    return html;
  }
  return `<div class="ms-table-wrap"><table class="ms-table"><thead>${head}</thead><tbody>${row('EPS ($)','eps',fmtEpsCell)}${yoyRow('YoY % Chg','epsYoY')}${surpRow('Surprise %','epsSurp')}${row('Sales ($M)','rev',fmtSales)}${yoyRow('YoY % Chg','revYoY')}${surpRow('Surprise %','revSurp')}</tbody></table></div>`;
}

/* Editable MS table for Studies — cells in EPS ($) / Sales ($M) rows are <input>; YoY % Chg
   and Surprise % rows are computed-only labels that update live as user types.
   Returns HTML; the renderStudyDetail bindMsTableEditors() wires input listeners that:
     1. parse the input value
     2. write it back into study.customChart[arrayName][quarterIdx]
     3. re-render the bar charts + recompute the YoY/Surprise cells in place. */
function renderEditableMsTable(chart, sym) {
  if (!chart || !chart.quarters || !chart.quarters.length) return '<div style="color:var(--stone);padding:20px">No quarterly data</div>';
  const q = chart.quarters, er = chart.eps_reported || [], ee = chart.eps_estimate || [], rr = chart.rev_reported_M || [], re = chart.rev_estimate_M || [], li = chart.latest_idx;
  const N = Math.min(11, q.length);
  let start = Math.max(0, li - 4);
  let end = Math.min(q.length, start + N);
  start = Math.max(0, end - N);
  const cells = [];
  for (let i = start; i < end; i++) {
    const isReported = er[i] != null;
    cells.push({ q: q[i], i, isReported });
  }
  const firstEstIdx = cells.findIndex(c => !c.isReported);
  // Header row
  let head = '<tr>';
  cells.forEach((c, idx) => {
    const div = (idx === firstEstIdx && firstEstIdx > 0) ? 'ms-divider' : '';
    const estCls = c.isReported ? '' : 'est-col';
    const tag = c.isReported ? '' : ' <span class="ms-est-tag">est</span>';
    head += `<th class="${div} ${estCls}">${c.q}${tag}</th>`;
  });
  head += '<th class="ms-rowlabel"></th></tr>';
  // Editable value row generator
  function inputRow(label, repArr, estArr, fmtVal, stepVal, dataKey) {
    let html = '<tr>';
    cells.forEach((c, idx) => {
      const div = (idx === firstEstIdx && firstEstIdx > 0) ? 'ms-divider' : '';
      const klass = c.isReported ? 'ms-reported' : 'ms-estimate';
      const v = c.isReported ? repArr[c.i] : estArr[c.i];
      const valStr = (v != null) ? fmtVal(v) : '';
      html += `<td class="${klass} ${div}"><input class="ms-cell-input" type="number" step="${stepVal}" data-sym="${sym}" data-row="${dataKey}" data-qi="${c.i}" data-isrep="${c.isReported ? 1 : 0}" value="${valStr}" placeholder="—"></td>`;
    });
    html += `<td class="ms-rowlabel">${label}</td></tr>`;
    return html;
  }
  // Computed-only row generator (YoY % Chg + Surprise %)
  function computedRow(label, kind, isEps, isSurp) {
    let html = `<tr ${isSurp ? 'class="ms-surprise-row"' : ''}>`;
    cells.forEach((c, idx) => {
      const div = (idx === firstEstIdx && firstEstIdx > 0) ? 'ms-divider' : '';
      const klass = isSurp ? 'ms-surprise' : (c.isReported ? 'ms-reported' : 'ms-estimate');
      html += `<td class="${klass} ${div}" data-computed="${kind}-${c.i}"></td>`;
    });
    html += `<td class="ms-rowlabel ${isSurp ? 'ms-surprise-label' : ''}">${label}</td></tr>`;
    return html;
  }
  const fmtEps  = v => v.toFixed(2);
  const fmtRev  = v => (Math.abs(v) >= 1000 ? v.toFixed(1) : v.toFixed(1));
  return `<div class="ms-table-wrap"><table class="ms-table ms-table-editable"><thead>${head}</thead><tbody>` +
    inputRow('EPS ($)',     er, ee, fmtEps, '0.01', 'eps') +
    computedRow('YoY % Chg', 'epsYoY', true, false) +
    computedRow('Surprise %','epsSurp', true, true) +
    inputRow('Sales ($M)',  rr, re, fmtRev, '0.1',  'rev') +
    computedRow('YoY % Chg', 'revYoY', false, false) +
    computedRow('Surprise %','revSurp', false, true) +
  `</tbody></table></div>`;
}

// JS twin of parse_tv.py's yoy() — universal formula `(curr - prior) / abs(prior) * 100`.
// Returns the same string the Python builder produces, e.g. '+34.12%' / '-87.80%' / 'N/M'.
function yoyText(curr, prior) {
  if (curr == null || prior == null) return 'N/M';
  if (prior === 0) return 'N/M';
  const pct = (curr - prior) / Math.abs(prior) * 100.0;
  const sign = pct >= 0 ? '+' : '';
  return `${sign}${pct.toFixed(2)}%`;
}

// Build the multiline Forward YoY text from a chart object (eps_reported / eps_estimate /
// rev_reported_M / rev_estimate_M arrays). Mirrors the Python `parse_tv.py` builder so the
// Studies page can recompute YoY whenever the user edits an MS-table cell.
//   line 0:  "<eps_yoy> / <rev_yoy>"      ← latest reported quarter vs same Q a year ago
//   line 1:  "--------------------"        ← separator
//   line 2+: "<eps_fwd_yoy> / <rev_fwd_yoy>"  ← one line per estimated forward quarter (up to 4)
function buildYoyBlockText(chart) {
  if (!chart) return '';
  const er = chart.eps_reported || [], ee = chart.eps_estimate || [];
  const rr = chart.rev_reported_M || [], re = chart.rev_estimate_M || [];
  // Find the latest index with a reported EPS value (matches Python's `latest` walk-back).
  let latest = -1;
  for (let k = er.length - 1; k >= 0; k--) {
    if (er[k] != null) { latest = k; break; }
  }
  if (latest < 0) return '';
  const priorEps = (latest >= 4) ? er[latest - 4] : null;
  const priorRev = (latest >= 4) ? rr[latest - 4] : null;
  const lines = [
    `${yoyText(er[latest], priorEps)} / ${yoyText(rr[latest], priorRev)}`,
    '-'.repeat(20),
  ];
  for (let fwd = 1; fwd <= 4; fwd++) {
    const fi = latest + fwd;
    if (fi < ee.length && ee[fi] != null) {
      const pe = (fi >= 4 && (fi - 4) < er.length) ? er[fi - 4] : null;
      const pr = (fi >= 4 && (fi - 4) < rr.length) ? rr[fi - 4] : null;
      const reVal = (fi < re.length) ? re[fi] : null;
      lines.push(`${yoyText(ee[fi], pe)} / ${yoyText(reVal, pr)}`);
    }
  }
  return lines.join('\n');
}

// Recompute the YoY / Surprise cells based on current customChart arrays.
function recomputeMsComputedCells(chart) {
  if (!chart) return;
  const er = chart.eps_reported || [], ee = chart.eps_estimate || [], rr = chart.rev_reported_M || [], re = chart.rev_estimate_M || [];
  const surp = (rep, est) => (rep == null || est == null || est === 0) ? { txt: '', val: null } : (() => { const r = Math.round((rep - est) / Math.abs(est) * 100); return { txt: (r >= 0 ? '+' : '') + r + '%', val: r }; })();
  const yoy  = (cur, prior) => (cur == null || prior == null) ? { txt: 'N/A', val: null } : (prior === 0 ? { txt: 'N/M', val: null } : (() => { const r = Math.round((cur - prior) / Math.abs(prior) * 100); return { txt: (r >= 0 ? '+' : '') + r + '%', val: r }; })());
  document.querySelectorAll('td[data-computed]').forEach(td => {
    const [kind, i] = td.dataset.computed.split('-');
    const idx = parseInt(i, 10);
    let v = { txt: '', val: null };
    if (kind === 'epsYoY') { const cur = (er[idx] != null) ? er[idx] : ee[idx]; v = yoy(cur, er[idx-4]); }
    else if (kind === 'revYoY') { const cur = (rr[idx] != null) ? rr[idx] : re[idx]; v = yoy(cur, rr[idx-4]); }
    else if (kind === 'epsSurp') { v = (er[idx] != null) ? surp(er[idx], ee[idx]) : { txt: '', val: null }; }
    else if (kind === 'revSurp') { v = (rr[idx] != null) ? surp(rr[idx], re[idx]) : { txt: '', val: null }; }
    if (!v.txt) { td.innerHTML = ''; return; }
    if (v.txt === 'N/M' || v.txt === 'N/A') { td.innerHTML = `<span class="nm">${v.txt}</span>`; return; }
    const c = v.val > 0 ? 'pos' : v.val < 0 ? 'neg' : '';
    td.innerHTML = `<span class="${c}">${v.txt}</span>`;
  });
}

/* ============================================================
   Company News history (thefly.com-style)
   Walks STATE.dates, loads each day's data, and collects every
   appearance of this symbol as a news item.
   ============================================================ */
function relativeDateGroup(isoDate, todayIso) {
  const d = new Date(isoDate + 'T00:00:00');
  const t = new Date(todayIso + 'T00:00:00');
  const diff = Math.round((t.getTime() - d.getTime()) / 86400000);
  if (diff === 0) return 'Today';
  if (diff === 1) return 'Yesterday';
  if (diff <= 7) return d.toLocaleDateString('en-US', { weekday: 'long' });
  return 'Over a week ago';
}
function fmtNewsTime(isoDate, scanTime) {
  // "May 13, 8:30 AM ET" style — fallback used when no publishedAt is available
  const d = new Date(isoDate + 'T00:00:00');
  const mo = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][d.getMonth()];
  const day = d.getDate();
  let timePart = '';
  if (scanTime) {
    const [hh, mm] = scanTime.split(':').map(Number);
    if (!isNaN(hh) && !isNaN(mm)) {
      const ampm = hh >= 12 ? 'PM' : 'AM';
      const h12 = hh % 12 || 12;
      timePart = `, ${h12}:${String(mm).padStart(2,'0')} ${ampm}`;
    }
  }
  return `${mo} ${day}${timePart}`;
}
// Format an ISO 8601 timestamp (e.g. "2026-05-13T06:30:00-04:00") as "May 13, 6:30 AM ET".
// Uses the timezone offset embedded in the ISO string for the displayed clock time.
function fmtPublishedAt(isoTs, tzLabel) {
  try {
    const d = new Date(isoTs);
    if (isNaN(d.getTime())) return null;
    // Display using the offset present in the ISO string (Date.toLocaleString in 'en-US' with the offset's notation)
    // Extract from ISO directly to avoid local-tz coercion
    const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(isoTs);
    if (!m) return null;
    const [, yy, mo, dd, hh, mm] = m;
    const monthName = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][parseInt(mo)-1];
    const H = parseInt(hh), M = parseInt(mm);
    const ampm = H >= 12 ? 'PM' : 'AM';
    const h12 = H % 12 || 12;
    const tz = tzLabel ? ' ' + tzLabel : '';
    return `${monthName} ${parseInt(dd)}, ${h12}:${String(M).padStart(2,'0')} ${ampm}${tz}`;
  } catch (e) { return null; }
}

async function buildNewsHistory(sym) {
  const out = [];
  for (const dEntry of STATE.dates) {
    const data = await loadDateData(dEntry.date);
    if (!data) continue;
    const s = data.stocks && data.stocks[sym];
    if (!s) continue;
    if (!s.catalyst && !s.newsDetail) continue;
    out.push({
      date: dEntry.date,
      scanTime: data.scanTime,
      scanTimestamp: data.scanTimestamp,
      publishedAt: s.publishedAt,                  // real news time (ISO 8601), if available
      publishedTimezone: s.publishedTimezone,
      title: s.catalyst || (s.newsDetail || '').slice(0, 200),
      detail: s.newsDetail || '',
      type: s.type,
      chgPct: s.chgPct,
    });
  }
  return out.sort((a, b) => b.date.localeCompare(a.date));
}

function clockSvg() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`;
}
function fileSvg() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`;
}
function chevronDownSvg() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>`;
}
function expandIconSvg() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/></svg>`;
}

function renderNewsHistory(sym, history, container) {
  if (!history.length) {
    container.innerHTML = `<div class="news-history-header">
      <div class="title"><span class="icon-box">${fileSvg()}</span>Company News</div>
    </div><div class="news-history-empty">尚無新聞記錄。 下次掃描 (/SIPs) 後會出現。</div>`;
    return;
  }
  // Group by relative date label
  const groups = {};
  const groupOrder = [];
  history.forEach(item => {
    const label = relativeDateGroup(item.date, STATE.date);
    if (!groups[label]) { groups[label] = []; groupOrder.push(label); }
    groups[label].push(item);
  });
  // Standard ordering: Today, Yesterday, day names (recent first), Over a week ago
  const stdOrder = ['Today', 'Yesterday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday', 'Over a week ago'];
  groupOrder.sort((a, b) => stdOrder.indexOf(a) - stdOrder.indexOf(b));

  // Expand button retired — every item's full text is now shown by default.
  let html = `<div class="news-history-header">
    <div class="title"><span class="icon-box">${fileSvg()}</span>Company News</div>
  </div><div class="news-history-list">`;
  groupOrder.forEach(label => {
    html += `<div class="news-history-group-label">${label}</div>`;
    groups[label].forEach((item, i) => {
      // Prefer real publication time (publishedAt) over scan time
      const realPub = item.publishedAt ? fmtPublishedAt(item.publishedAt, item.publishedTimezone) : null;
      const timeStr = realPub || fmtNewsTime(item.date, item.scanTime);
      const fullText = (item.detail && item.detail.length > item.title.length)
        ? item.detail : '';
      html += `<div class="news-item" data-idx="${i}-${label}">
        <div class="news-icon">${fileSvg()}</div>
        <div class="news-body">
          <div class="news-title">${escapeHtml(item.title)}</div>
          <div class="news-meta">
            <span class="sym">${sym}</span><span class="sep">|</span>
            <span class="time">${clockSvg()}${timeStr}</span>
          </div>
          ${fullText ? `<div class="news-full">${escapeHtml(fullText).split(/\n\n+/).map(p => `<p style="margin:0 0 8px">${p.replace(/\n/g,'<br>')}</p>`).join('')}</div>` : ''}
        </div>
        <div class="news-expand">${chevronDownSvg()}</div>
      </div>`;
    });
  });
  html += `</div>`;
  container.innerHTML = html;
  // News items are non-interactive now (always expanded); no click handler needed.
}

async function renderStock(sym) {
  const s = DATA.stocks[sym];
  const app = document.getElementById('app');
  if (!s) { app.innerHTML = `<div class="empty">Symbol ${sym} 不在今日掃描中</div>`; return; }
  // Compute day-label for header (only show "day1" — skip day2 / day3 per spec)
  const firstSeen = await getSymbolFirstSeenMap();
  const dLabel = dayLabelWithReset(s.symbol, firstSeen, DATA.date);
  const dayChip = dLabel === 'day1' ? `<span class="day-badge day1">day1</span>` : '';
  const sessTags = s.sessions.map(x => `<span class="tag">${x.session.toUpperCase()} <span class="dot dot-${x.direction}"></span> ${fmtPctShort(x.chgPct)}</span>`).join(' ');
  let chartHtml = { eps: '', rev: '' };
  let msHtml = '<div style="color:var(--stone);padding:20px">無 TradingView 季度估計資料</div>';
  let yoyHtml = '';
  if (s.tv) {
    chartHtml = renderChart(s.tv.chart);
    const t = s.tv;
    msHtml = renderMarketSurgeTable(t.chart);
    yoyHtml = `<button class="copy-btn" data-copy-target="yoy-${s.symbol}">Copy</button><div class="yoy-block" id="yoy-${s.symbol}" data-raw="${escapeHtml(t.yoyBlock || '')}">${colorizeYoyBlock(t.yoyBlock || '')}</div>`;
  }
  const detail = s.newsDetail || '';
  const fallbackCatalyst = s.catalyst || '';
  // Date/time meta — prefer s.publishedAt (real news publication time), fall back to DATA.scanTime
  const realPub = s.publishedAt ? fmtPublishedAt(s.publishedAt, s.publishedTimezone) : null;
  const pubTime = realPub || (fmtNewsTime(DATA.date, DATA.scanTime) + (DATA.scanTime ? ' ET' : '') + ' (scan time)');
  const metaPill = `<div class="news-detail-meta">${clockSvg()}<span>Published ${pubTime}</span></div>`;
  let newsDetailHtml = '';
  if (detail) {
    const paragraphs = String(detail).split(/\n\n+/).filter(Boolean).map(p => `<p>${escapeHtml(p).replace(/\n/g,'<br>')}</p>`).join('');
    newsDetailHtml = `<div class="stock-card news-detail"><h3>新聞詳情 <span class="label-en">News Detail</span></h3>${metaPill}${paragraphs}</div>`;
  } else if (fallbackCatalyst) {
    newsDetailHtml = `<div class="stock-card news-detail"><h3>新聞詳情 <span class="label-en">News Detail</span></h3>${metaPill}<p>${escapeHtml(fallbackCatalyst)}</p></div>`;
  }
  // Stock-detail header pills — split into TWO rows:
  //   • headerShortPills:  Short Float + DTC (Finviz-sourced shorts metrics)
  //   • headerSurpPills:   EPS Surp + Rev Surp (TradingView FQ earnings surprise, pos/neg tinted)
  const _tv = s.tv;
  const _surpPill = (lbl, v, title) => v == null
    ? ''
    : `<span class="tag stat-tag ${v >= 0 ? 'pos' : 'neg'}" title="${title}">${lbl} ${(v >= 0 ? '+' : '') + v.toFixed(1)}%</span>`;
  const headerShortPills = [
    s.shortFloat != null ? `<span class="tag stat-tag" title="Short Float — % of float currently shorted">Short Float ${s.shortFloat.toFixed(1)}%</span>` : '',
    s.shortRatio != null ? `<span class="tag stat-tag" title="Days to cover (short ratio)">DTC ${s.shortRatio.toFixed(1)}d</span>` : '',
  ].filter(Boolean).join(' ');
  const headerSurpPills = [
    _tv ? _surpPill('EPS Surp', _tv.surpriseEPS_pct, 'EPS surprise vs consensus (TradingView FQ)') : '',
    _tv ? _surpPill('Rev Surp', _tv.surpriseRev_pct, 'Revenue surprise vs consensus (TradingView FQ)') : '',
  ].filter(Boolean).join(' ');
  app.innerHTML = `
    <div class="breadcrumb"><a href="#/earnings">Earnings</a> · <a href="#/catalyst">Catalyst</a> · <a href="#/scanx">SCANX</a> &nbsp;»&nbsp; <b>${s.symbol}</b></div>
    <div class="stock-header" style="position:relative">
      ${saveStudyBtnHtml(s.symbol)}
      <div class="sym-big">${s.symbol}${dayChip}</div>
      <div>
        <div class="name">${escapeHtml(s.name)}</div>
        <div class="stock-header-tags">${sessTags} <span class="tag ${typeTagClass(s.type)}">${s.type}</span></div>
        ${headerShortPills ? `<div class="stock-header-tags stock-header-short">${headerShortPills}</div>` : ''}
        ${headerSurpPills  ? `<div class="stock-header-tags stock-header-surp">${headerSurpPills}</div>`   : ''}
      </div>
      <div style="margin-left:auto;text-align:right">
        <div class="price">${fmtPrice(s.last)}</div>
        <div class="chg ${cls(s.chgPct)}">${fmtPct(s.chgPct)} · Vol ${fmtVol(s.volume)}</div>
      </div>
    </div>
    ${newsDetailHtml}
    <div class="chart-wrap">
      <div class="stock-card"><h3>EPS Quarterly <span class="label-en">Reported vs Estimate</span></h3>${chartHtml.eps || ''}</div>
      <div class="stock-card"><h3>Revenue Quarterly <span class="label-en">Reported vs Estimate</span></h3>${chartHtml.rev || ''}</div>
    </div>
    <div class="stock-card">
      <h3>季度 EPS / Sales <span class="label-en">Reported + Estimate</span></h3>
      ${msHtml}
    </div>
    <div class="stock-card">
      <h3>Forward YoY <span class="label-en">TradingView FQ — EPS YoY / Rev YoY</span></h3>
      ${yoyHtml}
    </div>
    <div class="news-history-card" id="news-history-${s.symbol}"></div>
  `;
  // Async-load news history from all available date files
  buildNewsHistory(s.symbol).then(hist => {
    const container = document.getElementById(`news-history-${s.symbol}`);
    if (container) renderNewsHistory(s.symbol, hist, container);
  });
  app.querySelectorAll('.copy-btn').forEach(btn => {
    btn.onclick = async () => {
      const tgt = document.getElementById(btn.dataset.copyTarget);
      if (!tgt) return;
      const text = tgt.dataset.raw || tgt.textContent;
      try { await navigator.clipboard.writeText(text); }
      catch (e) { const ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove(); }
      btn.textContent = 'Copied!'; btn.classList.add('copied');
      setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 1200);
    };
  });
}

function renderChart(c) {
  if (!c) return { eps: '', rev: '' };
  return { eps: svgBarChart(c.quarters, c.eps_reported, c.eps_estimate, c.latest_idx, false), rev: svgBarChart(c.quarters, c.rev_reported_M, c.rev_estimate_M, c.latest_idx, true) };
}

// ── Chart hover tooltip (delegated, installed once on first call) ──────────────────────────
// One global #chart-tooltip element lives at the bottom of <body>. Every .bar-hit rect carries
// data-q (quarter), data-rep, data-est, data-rev so we can build the tooltip content on hover.
// Listeners are delegated on document so they survive route changes / re-renders.
let __chartTooltipInstalled = false;
function installChartTooltip() {
  if (__chartTooltipInstalled) return;
  __chartTooltipInstalled = true;
  const tip = document.getElementById('chart-tooltip');
  if (!tip) return;
  // Build the inner element ONCE at install time, then reuse it across shows.
  // Why: Chromium skips CSS transitions on freshly-inserted nodes (it considers them "first paint")
  // — so replacing the .ct-inner via innerHTML each show meant scale(0.96)→scale(1) never animated.
  // Keeping a stable .ct-inner element means the transition starts from a settled state every time.
  tip.innerHTML = `
    <div class="ct-inner">
      <div class="ct-q"></div>
      <div class="ct-row"><span class="ct-dot rep"></span><span class="ct-lbl">Reported</span><span class="ct-val rep-val"></span></div>
      <div class="ct-row"><span class="ct-dot est"></span><span class="ct-lbl">Estimate</span><span class="ct-val est-val"></span></div>
    </div>`;
  const qEl    = tip.querySelector('.ct-q');
  const repEl  = tip.querySelector('.rep-val');
  const estEl  = tip.querySelector('.est-val');

  const fmt = (raw, isRev) => {
    if (raw === '' || raw == null) return { val: '—', unit: '' };
    const v = parseFloat(raw);
    if (!isFinite(v)) return { val: '—', unit: '' };
    if (isRev) {
      const abs = Math.abs(v);
      if (abs >= 1000) return { val: '$' + (v / 1000).toFixed(2), unit: 'B USD' };
      return { val: '$' + v.toFixed(1), unit: 'M USD' };
    }
    return { val: v.toFixed(2), unit: 'USD' };
  };
  function setCellHtml(cell, parts) {
    cell.textContent = parts.val;
    if (parts.unit) {
      const u = document.createElement('span');
      u.className = 'ct-unit';
      u.textContent = parts.unit;
      cell.appendChild(u);
    }
  }
  // Track the column-highlight rect currently lit so we can dim it when the user pans away.
  let __activeHighlight = null;
  function activateHighlight(barHit) {
    const svg = barHit.ownerSVGElement;
    if (!svg) return;
    const idx = barHit.getAttribute('data-col-idx');
    const highlight = svg.querySelector(`.col-highlight[data-col-idx="${idx}"]`);
    if (highlight === __activeHighlight) return;
    if (__activeHighlight) __activeHighlight.classList.remove('active');
    if (highlight) highlight.classList.add('active');
    __activeHighlight = highlight;
  }
  function clearHighlight() {
    if (__activeHighlight) { __activeHighlight.classList.remove('active'); __activeHighlight = null; }
  }
  function show(rect, ev) {
    const isRev = rect.getAttribute('data-rev') === '1';
    const q   = rect.getAttribute('data-q') || '';
    const rep = fmt(rect.getAttribute('data-rep'), isRev);
    const est = fmt(rect.getAttribute('data-est'), isRev);
    qEl.textContent = q;
    setCellHtml(repEl, rep);
    setCellHtml(estEl, est);
    activateHighlight(rect);
    const wasVisible = tip.classList.contains('visible');
    void tip.offsetWidth;
    if (!wasVisible) {
      tip.classList.add('snap');
      position(ev);
      void tip.offsetWidth;
      tip.classList.remove('snap');
      tip.classList.add('visible');
    } else {
      position(ev);
    }
    tip.setAttribute('aria-hidden', 'false');
  }
  function position(ev) {
    const margin = 14;
    const rect = tip.getBoundingClientRect();
    let x = ev.clientX + margin;
    let y = ev.clientY - rect.height - margin;
    if (x + rect.width > window.innerWidth - 8)  x = ev.clientX - rect.width - margin;
    if (y < 8)                                   y = ev.clientY + margin;
    // CSS custom props feed `transform: translate3d(--tx, --ty, 0)` — compositor-only, animates
    // smoothly under the outer's transform transition rule.
    tip.style.setProperty('--tx', x + 'px');
    tip.style.setProperty('--ty', y + 'px');
  }
  function hide() {
    tip.classList.remove('visible');
    tip.setAttribute('aria-hidden', 'true');
    clearHighlight();
  }
  document.addEventListener('mouseover', e => {
    const hit = e.target.closest && e.target.closest('rect.bar-hit');
    if (hit) show(hit, e);
  });
  document.addEventListener('mousemove', e => {
    if (tip.classList.contains('visible')) position(e);
  });
  document.addEventListener('mouseout', e => {
    const hit = e.target.closest && e.target.closest('rect.bar-hit');
    if (hit && (!e.relatedTarget || !e.relatedTarget.closest || !e.relatedTarget.closest('rect.bar-hit'))) hide();
  });
}

function svgBarChart(quarters, reported, estimate, latestIdx, isRev) {
  const W = 540, H = 240, PAD_L = 44, PAD_R = 12, PAD_T = 24, PAD_B = 40;
  const n = Math.max(quarters.length, reported.length, estimate.length);
  if (n === 0) return '<div style="color:var(--stone);padding:20px">no data</div>';
  const all = [];
  reported.forEach(v => v != null && all.push(v));
  estimate.forEach(v => v != null && all.push(v));
  if (all.length === 0) return '<div style="color:var(--stone);padding:20px">no data</div>';
  const minV = Math.min(0, ...all);
  const maxV = Math.max(0, ...all);
  const range = maxV - minV || 1;
  const innerW = W - PAD_L - PAD_R;
  const innerH = H - PAD_T - PAD_B;
  // Wider gap between quarters: 2 bars take ~57% of column width (was 83%) → ~43% gap.
  const colW = innerW / n;
  const barW = colW / 3.5;
  const yZero = PAD_T + innerH * (maxV / range);
  const scaleY = innerH / range;
  // Format a value for the tooltip. EPS = 2-decimal $; revenue auto-switches M/B.
  const fmtBar = v => {
    if (v == null) return '—';
    if (isRev) return Math.abs(v) >= 1000 ? `$${(v/1000).toFixed(2)}B` : `$${v.toFixed(1)}M`;
    return `$${v.toFixed(2)}`;
  };
  // Column highlight rects — rendered BEFORE bars so they sit behind them. Each carries the same
  // data-col-idx as its matching bar-hit, so on hover we can toggle .active on the right one.
  let highlights = '';
  let bars = '';
  for (let i = 0; i < n; i++) {
    const xCenter = PAD_L + colW * (i + 0.5);
    const qLabel = quarters[i] || `Q${i+1}`;
    const rep = reported[i];
    const est = estimate[i];
    // Highlight rect (initially transparent, lights up via .active class on hover)
    highlights += `<rect class="col-highlight" data-col-idx="${i}" x="${xCenter - colW/2 + 2}" y="${PAD_T}" width="${colW - 4}" height="${innerH}" rx="4"></rect>`;
    if (rep != null) {
      const h = Math.abs(rep) * scaleY;
      const y = rep >= 0 ? yZero - h : yZero;
      bars += `<rect class="bar-reported" x="${xCenter - barW - 1}" y="${y}" width="${barW}" height="${h}" rx="2"></rect>`;
    }
    if (est != null) {
      const h = Math.abs(est) * scaleY;
      const y = est >= 0 ? yZero - h : yZero;
      bars += `<rect class="bar-estimate" x="${xCenter + 1}" y="${y}" width="${barW}" height="${h}" rx="2" opacity="0.85"></rect>`;
    }
    // Column-wide hit rect carries the values + label so the HTML tooltip (installChartTooltip)
    // can read them on hover. data-col-idx pairs it with its highlight rect.
    bars += `<rect class="bar-hit" data-col-idx="${i}" x="${xCenter - colW/2 + 2}" y="${PAD_T}" width="${colW - 4}" height="${innerH}" fill="transparent" pointer-events="all" data-q="${escapeHtml(qLabel)}" data-rep="${rep == null ? '' : rep}" data-est="${est == null ? '' : est}" data-rev="${isRev ? '1' : '0'}"></rect>`;
  }
  bars = highlights + bars;
  let labels = '';
  for (let i = 0; i < quarters.length; i++) {
    if (i % 2 !== 0 && quarters.length > 8) continue;
    const x = PAD_L + colW * (i + 0.5);
    const isLatest = i === latestIdx;
    labels += `<text x="${x}" y="${H - PAD_B + 16}" text-anchor="middle" fill="${isLatest ? '#191c1f' : '#8d969e'}" font-weight="${isLatest ? '700' : '500'}" font-size="11" font-family="Inter, sans-serif">${quarters[i] || ''}</text>`;
  }
  const tickCount = 4;
  let yLabels = '';
  for (let i = 0; i <= tickCount; i++) {
    const val = minV + (range * i / tickCount);
    const y = PAD_T + innerH - (innerH * i / tickCount);
    yLabels += `<line x1="${PAD_L}" y1="${y}" x2="${W - PAD_R}" y2="${y}" stroke="#eef0f3"></line>`;
    yLabels += `<text x="${PAD_L - 6}" y="${y + 3}" text-anchor="end" fill="#8d969e" font-size="10" font-family="Inter">${isRev ? (Math.abs(val) >= 1000 ? (val/1000).toFixed(1)+'B' : val.toFixed(0)+'M') : val.toFixed(2)}</text>`;
  }
  const legend = `<g transform="translate(${PAD_L}, ${PAD_T - 8})"><rect class="bar-reported" x="0" y="-10" width="11" height="11" rx="2"></rect><text x="16" y="0" dy="-1" font-size="11" font-family="Inter" fill="#505a63" font-weight="500">Reported</text><rect class="bar-estimate" x="80" y="-10" width="11" height="11" rx="2" opacity="0.85"></rect><text x="96" y="0" dy="-1" font-size="11" font-family="Inter" fill="#505a63" font-weight="500">Estimate</text></g>`;
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">${yLabels}${bars}<line x1="${PAD_L}" y1="${yZero}" x2="${W - PAD_R}" y2="${yZero}" stroke="#191c1f" stroke-width="1"></line><g class="axis">${labels}</g>${legend}</svg>`;
}

/* ═══════════════════════════════════════════════════════════════════
   Dark mode + i18n + Studies — added 2026-05-15
   ═══════════════════════════════════════════════════════════════════ */

// ── Dark mode toggle (persisted in localStorage). ──
function installThemeToggle() {
  const KEY = 'sips-theme';
  const apply = (dark) => {
    document.body.classList.toggle('dark', dark);
    const sun = document.getElementById('theme-icon-sun');
    const moon = document.getElementById('theme-icon-moon');
    if (sun)  sun.style.display  = dark ? 'none' : '';
    if (moon) moon.style.display = dark ? '' : 'none';
  };
  // Boot: read pref → apply. Defaults to light per Revolut design (white canvas).
  apply(localStorage.getItem(KEY) === 'dark');
  const btn = document.getElementById('theme-toggle');
  if (btn) btn.onclick = () => {
    const newDark = !document.body.classList.contains('dark');
    localStorage.setItem(KEY, newDark ? 'dark' : 'light');
    apply(newDark);
  };
}

// i18n removed (2026-05-15): user dropped the toggle. UI stays English, dynamic content
// (catalysts / news_detail / claude rationale) stays in 繁體中文 as captured by /SIPs.
// `t(key)` shim preserved for backward compat with existing call sites — returns the EN
// label or the key itself as fallback. Safe to remove later if every t() call gets inlined.
const _UI_LABELS = {
  'save-study': '➕ Save to Studies',
  'saved': '✓ Saved',
  'remove-study': 'Remove',
  'studies-empty': 'No SIPs saved yet. Click "Save to Studies" on any SIP card to add one.',
  'studies-note-placeholder': 'Notes — paste images (Ctrl+V) or drag-drop to embed inline…',
  'studies-export': 'Export JSON',
  'studies-import': 'Import JSON',
  'studies-clear': 'Clear all',
  'studies-clear-confirm': 'Clear all studies? This cannot be undone.',
  'studies-saved-on': 'Saved',
  'ohlcv-date': 'Date', 'ohlcv-open': 'Open', 'ohlcv-high': 'High',
  'ohlcv-low': 'Low', 'ohlcv-close': 'Close', 'ohlcv-prev-close': 'Prev close', 'ohlcv-volume': 'Volume',
  'claude-rationale-label': "Claude's Analysis",
};
function t(key) { return _UI_LABELS[key] || key; }

/* ═══════════ Studies (localStorage-backed personal library) ═══════════
   Schema in localStorage key 'sips-studies':
     [{ symbol, savedAt: ISO, snapshot: {chgPct, catalyst, tv, sessions, ...},
        notes: "...", tags: ["..."], targetPrice: number|null, stopLoss: number|null,
        conviction: 1-5 (default 3) }, ...]
   Studies are user-owned data, not synced to GitHub — Export/Import JSON button gives
   manual cross-device portability. */
const STUDIES_KEY = 'sips-studies';
/* ── IndexedDB image store ────────────────────────────────────────────
   localStorage caps at ~5 MB per origin (small for screenshots). IndexedDB
   has no practical cap on modern browsers — typically 50% of free disk.
   Screenshots get stored here keyed by uuid; the study metadata in
   localStorage holds the key (not the data) so the JSON stays small.
   API:  await putImg(key, dataUrl) / await getImg(key) / await delImg(key)
   ─────────────────────────────────────────────────────────────────── */
const IMG_DB_NAME = 'sips-images';
const IMG_STORE = 'images';
let __imgDB = null;
function openImgDB() {
  if (__imgDB) return Promise.resolve(__imgDB);
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(IMG_DB_NAME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(IMG_STORE);
    req.onsuccess = () => { __imgDB = req.result; resolve(__imgDB); };
    req.onerror = () => reject(req.error);
  });
}
async function putImg(key, dataUrl) {
  const db = await openImgDB();
  await new Promise((resolve, reject) => {
    const tx = db.transaction(IMG_STORE, 'readwrite');
    tx.objectStore(IMG_STORE).put(dataUrl, key);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  // Write through to sidecar disk so /SIPs Phase 11 commit picks it up.
  if (STATE.sidecar.available) {
    try {
      const r = await fetch('/api/studies/image', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ key, dataUrl }),
      });
      if (r.ok) {
        const info = await r.json();
        // Keep client-side index in sync so getImg can serve from disk if IDB ever clears.
        if (info && info.path) {
          STATE.imgIndex = STATE.imgIndex || {};
          STATE.imgIndex[key] = info.path.replace(/^studies\/images\//, '');
        }
      }
    } catch (e) { console.warn('[sidecar] putImg failed', e); }
  }
}
async function getImg(key) {
  // 1. IDB (fast path — everything we wrote locally lands here).
  const db = await openImgDB();
  const idbHit = await new Promise((resolve, reject) => {
    const tx = db.transaction(IMG_STORE, 'readonly');
    const req = tx.objectStore(IMG_STORE).get(key);
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error);
  });
  if (idbHit) return idbHit;
  // 2. Fall back to disk-served image (covers read-only hosted + post-IDB-clear cases).
  //    Returns the URL string — the caller uses it as <img src>.
  if (STATE.imgIndex && STATE.imgIndex[key]) {
    return `studies/images/${STATE.imgIndex[key]}`;
  }
  // 3. Last-ditch extension probe (only the formats we save).
  for (const ext of ['png', 'jpg', 'webp', 'gif']) {
    try {
      const r = await fetch(`studies/images/${key}.${ext}`, {method: 'HEAD'});
      if (r.ok) return `studies/images/${key}.${ext}`;
    } catch (_) {}
  }
  return null;
}
async function delImg(key) {
  const db = await openImgDB();
  await new Promise((resolve, reject) => {
    const tx = db.transaction(IMG_STORE, 'readwrite');
    tx.objectStore(IMG_STORE).delete(key);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  if (STATE.sidecar.available) {
    try {
      await fetch(`/api/studies/image/${encodeURIComponent(key)}`, {method: 'DELETE'});
      if (STATE.imgIndex) delete STATE.imgIndex[key];
    } catch (e) { console.warn('[sidecar] delImg failed', e); }
  }
}
async function getAllImgs() {
  const db = await openImgDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(IMG_STORE, 'readonly');
    const store = tx.objectStore(IMG_STORE);
    const out = {};
    const req = store.openCursor();
    req.onsuccess = e => {
      const cur = e.target.result;
      if (cur) { out[cur.key] = cur.value; cur.continue(); }
      else resolve(out);
    };
    req.onerror = () => reject(req.error);
  });
}
function uuid() {
  // Compact 12-char uuid suffix — collision-free enough for per-user image keys.
  return 'img-' + Math.random().toString(36).slice(2, 8) + Date.now().toString(36).slice(-4);
}

// Auto-downscale large screenshots before storage. Max 1600px on long edge, JPEG 0.88 quality.
// Keeps 4K screenshots under ~400 KB without losing legibility for chart annotations.
function downscaleImage(file, maxDim = 1600, quality = 0.88) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.onload = () => {
        let { width: w, height: h } = img;
        if (w > maxDim || h > maxDim) {
          const scale = maxDim / Math.max(w, h);
          w = Math.round(w * scale); h = Math.round(h * scale);
        }
        const canvas = document.createElement('canvas');
        canvas.width = w; canvas.height = h;
        canvas.getContext('2d').drawImage(img, 0, 0, w, h);
        // PNG → JPEG (massive size reduction). Keep PNG only if image is small + has transparency hints.
        const useJpeg = file.size > 200 * 1024 || file.type === 'image/jpeg';
        resolve(canvas.toDataURL(useJpeg ? 'image/jpeg' : 'image/png', quality));
      };
      img.onerror = reject;
      img.src = reader.result;
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function loadStudies() {
  try { return JSON.parse(localStorage.getItem(STUDIES_KEY) || '[]'); }
  catch { return []; }
}
// Debounced POST to /api/studies/save so rapid keystrokes (notes typing, OHLCV editing,
// etc.) coalesce into one disk write per ~600 ms. Latest payload wins.
let __studiesFlushTimer = null;
let __studiesFlushPending = null;
async function postStudiesToDisk(arr) {
  if (!STATE.sidecar.available) return;
  try {
    await fetch('/api/studies/save', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(arr),
    });
  } catch (e) { console.warn('[sidecar] saveStudies failed', e); }
}
function flushStudiesSoon(arr) {
  __studiesFlushPending = arr;
  if (__studiesFlushTimer) return;
  __studiesFlushTimer = setTimeout(() => {
    const payload = __studiesFlushPending;
    __studiesFlushTimer = null;
    __studiesFlushPending = null;
    postStudiesToDisk(payload);
  }, 600);
}
function saveStudies(arr) {
  // localStorage is always written immediately for snappy UI + offline fallback.
  localStorage.setItem(STUDIES_KEY, JSON.stringify(arr));
  // Then flush to disk via sidecar (no-op in read-only hosted mode).
  flushStudiesSoon(arr);
}
function isStudySaved(sym) {
  return loadStudies().some(st => st.symbol === sym);
}
function addStudy(stock) {
  const arr = loadStudies();
  if (arr.some(st => st.symbol === stock.symbol)) return false; // dedupe
  arr.push({
    symbol: stock.symbol,
    savedAt: new Date().toISOString(),
    snapshot: {
      name: stock.name,
      type: stock.type,
      chgPct: stock.chgPct,
      last: stock.last,
      catalyst: stock.catalyst,
      catalyst_en: stock.catalyst_en,
      tv: stock.tv,
      sessions: stock.sessions,
      shortFloat: stock.shortFloat,
      shortRatio: stock.shortRatio,
      marketCap_M: stock.marketCap_M,
      claudeRationale: stock._claudeRationale,
      claudeRationale_en: stock._claudeRationale_en,
      claudeIntent: stock._claudeIntent,
      scanDate: STATE.date,
    },
    notes: '',
    tags: [],
    targetPrice: null,
    stopLoss: null,
    conviction: 3,
    // Daily OHLCV — auto-filled from stock.prevOhlcv (if /SIPs ran the prev-day fetch),
    // otherwise blank for user to enter via the popup modal. `prev_close` drives the day's
    // %Chg derivation: (close − prev_close) / prev_close · 100.
    ohlcv: stock.prevOhlcv && typeof stock.prevOhlcv === 'object'
      ? { date: stock.prevOhlcv.date || '', open: stock.prevOhlcv.open ?? null, high: stock.prevOhlcv.high ?? null, low: stock.prevOhlcv.low ?? null, close: stock.prevOhlcv.close ?? null, prev_close: stock.prevOhlcv.prev_close ?? null, volume: stock.prevOhlcv.volume ?? null }
      : { date: '', open: null, high: null, low: null, close: null, prev_close: null, volume: null },
    // Screenshots — array of { id, label, caption, imgKey }. Image data lives in IndexedDB.
    screenshots: [],
  });
  saveStudies(arr);
  return true;
}
async function removeStudy(sym) {
  // Full wipe — the entire study object (notes, ohlcv, customChart, screenshots, tags,
  // conviction, …) goes when the user removes a ticker. Re-adding via "Save to Studies"
  // builds a fresh record from the current SIP snapshot — no residue from the prior session.
  // (The snackbar undo restores everything from the cached snapshot, including customChart.)
  const st = loadStudies().find(s => s.symbol === sym);
  if (st?.screenshots?.length) {
    for (const ss of st.screenshots) { try { await delImg(ss.imgKey); } catch {} }
  }
  saveStudies(loadStudies().filter(st => st.symbol !== sym));
}
function updateStudy(sym, patch) {
  const arr = loadStudies();
  const idx = arr.findIndex(st => st.symbol === sym);
  if (idx === -1) return;
  arr[idx] = { ...arr[idx], ...patch };
  saveStudies(arr);
}

/* ═══════ Studies list view — small preview cards like Today's SIPs ═══════
   Click a card → #/study/<SYM> for the full editable detail page.
   Each card shows: SYMBOL + chgPct + intent badge + 1-line catalyst preview
   + open→high catalyst-potential % (if OHLCV filled) + saved-on date.
   The card is purely read-only here; all editing happens on the detail page. */
function renderStudies() {
  const app = document.getElementById('app');
  const studies = loadStudies().slice().sort((a, b) => (b.savedAt || '').localeCompare(a.savedAt || ''));
  app.innerHTML = `
    <h2 class="page-title">My Studies</h2>
    <div class="studies-toolbar">
      <span class="readonly-badge" title="Sidecar (local Python server) not detected — viewing the committed snapshot. Run &quot;py D:/SIPs/sidecar.py&quot; to edit.">&#128274; View only</span>
      <button class="studies-btn" id="studies-export" style="margin-left:auto">${t('studies-export')}</button>
      <button class="studies-btn" id="studies-import">${t('studies-import')}</button>
      <input type="file" id="studies-import-file" accept="application/json" style="display:none">
      <button class="studies-btn studies-btn-danger" id="studies-clear">${t('studies-clear')}</button>
    </div>
    ${studies.length === 0
      ? `<div class="sip-empty">${t('studies-empty')}</div>`
      : `<div class="sip-grid" id="studies-grid">${studies.map(studyPreviewCardHtml).join('')}</div>`}
  `;
  // Cards are pure links — no wiring needed beyond toolbar handlers below.
  // Toolbar
  document.getElementById('studies-export')?.addEventListener('click', async () => {
    // Bundle screenshots inline as base64 so the JSON is self-contained for cross-device transfer.
    // Schema:  { version: 2, studies: [...], images: { imgKey: dataUrl } }
    // Strip `customChart` from each study so a re-import starts with a blank chart — the user
    // explicitly opted into "next import = blank" so MS-table edits don't carry over.
    const studies = loadStudies().map(st => {
      const { customChart, ...rest } = st;
      return rest;
    });
    const images = await getAllImgs();
    const bundle = { version: 2, exportedAt: new Date().toISOString(), studies, images };
    const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `sips-studies-${new Date().toISOString().slice(0,10)}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  });
  document.getElementById('studies-import')?.addEventListener('click', () => document.getElementById('studies-import-file').click());
  document.getElementById('studies-import-file')?.addEventListener('change', e => {
    const f = e.target.files[0]; if (!f) return;
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const parsed = JSON.parse(reader.result);
        if (Array.isArray(parsed)) {
          // v1 format: bare array of studies (no images bundle — accept anyway)
          saveStudies(parsed);
        } else if (parsed && parsed.version === 2 && Array.isArray(parsed.studies)) {
          // v2 format: { studies, images }. Restore both, replacing any existing data.
          saveStudies(parsed.studies);
          for (const [key, dataUrl] of Object.entries(parsed.images || {})) {
            try { await putImg(key, dataUrl); } catch (err) { console.warn('import img fail', key, err); }
          }
        } else {
          throw new Error('Unrecognized format');
        }
        renderStudies();
      } catch (err) { alert('Invalid JSON: ' + err.message); }
    };
    reader.readAsText(f);
  });
  document.getElementById('studies-clear')?.addEventListener('click', async () => {
    const before = loadStudies();
    if (!before.length) return;
    if (!confirm(t('studies-clear-confirm'))) return;
    // Snapshot images so undo is fully reversible
    const beforeImgs = await getAllImgs();
    saveStudies([]);
    for (const k of Object.keys(beforeImgs)) { try { await delImg(k); } catch {} }
    renderStudies();
    showUndoSnackbar(`Cleared ${before.length} studies`, async () => {
      saveStudies(before);
      for (const [k, v] of Object.entries(beforeImgs)) { try { await putImg(k, v); } catch {} }
      renderStudies();
    });
  });
}

// Save-to-Studies button helper — emits a button with inline click handler that stops
// the parent <a class="sip-card"> from navigating. Pulls the stock fresh from DATA.stocks.
function saveStudyBtnHtml(sym, claudeRationale, claudeIntent) {
  const saved = isStudySaved(sym);
  // Stash the rationale + intent on a global so the click handler can pick it up without
  // bloating the inline attribute. Falls back to whatever's in DATA.stocks[sym] anyway.
  window.__claudePendingMeta = window.__claudePendingMeta || {};
  if (claudeRationale) window.__claudePendingMeta[sym] = { rationale: claudeRationale, intent: claudeIntent };
  return `<button class="save-study-btn ${saved ? 'saved' : ''}" data-sym="${sym}"
          onclick="event.stopPropagation();event.preventDefault();handleSaveStudy('${sym}',this);"
          title="${saved ? t('saved') : t('save-study')}">${saved ? t('saved') : t('save-study')}</button>`;
}
window.handleSaveStudy = function(sym, btn) {
  const s = DATA?.stocks?.[sym];
  if (!s) return;
  const meta = (window.__claudePendingMeta || {})[sym] || {};
  if (isStudySaved(sym)) {
    removeStudy(sym);
    btn.classList.remove('saved');
    btn.textContent = t('save-study');
    btn.title = t('save-study');
  } else {
    addStudy({
      ...s,
      _claudeRationale: meta.rationale || s._claudeRationale,
      _claudeIntent:    meta.intent    || s._claudeIntent,
    });
    btn.classList.add('saved');
    btn.textContent = t('saved');
    btn.title = t('saved');
  }
};

// Small preview card for the Studies list — mirrors the layout of sipCardHtml so the user
// can scan ranks/intent/catalyst at a glance. Clicking the whole card opens the detail page.
function studyPreviewCardHtml(st, idx) {
  const s = st.snapshot;
  const chg = (st.chgPct != null) ? st.chgPct : s.chgPct;
  const chgCls = chg >= 0 ? 'pos' : 'neg';
  const intent = st.intent || s.claudeIntent || 'long';
  const intentBadge = `<span class="tag" style="background:${intent === 'short' ? 'rgba(226,59,74,0.10)' : 'rgba(0,168,126,0.10)'};color:${intent === 'short' ? 'var(--neg)' : 'var(--pos)'}">${intent.toUpperCase()}</span>`;
  const cat = (st.catalyst != null && st.catalyst !== '') ? st.catalyst : (s.catalyst || '');
  // Open → High potential: shows how much the stock could have run from open. If filled this is
  // the most valuable single number on the card — it's the "catalyst-realised return."
  const o = st.ohlcv || {};
  const potentialPct = (o.open && o.high) ? ((o.high - o.open) / o.open * 100) : null;
  const potentialChip = potentialPct != null
    ? `<span class="study-potential ${potentialPct >= 0 ? 'pos' : 'neg'}" title="Open → High (catalyst potential)">→High ${(potentialPct >= 0 ? '+' : '') + potentialPct.toFixed(2)}%</span>`
    : '';
  return `<a class="sip-card" href="#/study/${st.symbol}" style="text-decoration:none;color:inherit;display:block;position:relative">
    <button class="study-preview-del" data-sym="${st.symbol}" title="Delete study"
            onclick="event.preventDefault();event.stopPropagation();handleDeleteStudyFromList('${st.symbol}');">✕</button>
    <span class="sip-rank-row"><span class="sip-rank">#${idx + 1}</span><span class="study-saved-on">${(st.savedAt || '').slice(0, 10)}</span></span>
    <div class="sip-header"><div class="sip-sym">${st.symbol}</div><div class="sip-chg ${chgCls}">${fmtPct(chg)}</div></div>
    <div class="sip-name">${escapeHtml(s.name || '')}</div>
    <div class="sip-meta">${intentBadge} ${potentialChip}</div>
    ${cat ? `<div class="sip-catalyst" style="margin-top:8px">${escapeHtml(cat)}</div>` : ''}
  </a>`;
}

// Global delete handler used by the preview card's X — collects the full study + its images
// so the undo snackbar can fully restore. Called from inline onclick.
window.handleDeleteStudyFromList = async function(sym) {
  const studies = loadStudies();
  const st = studies.find(s => s.symbol === sym);
  if (!st) return;
  // Snapshot all images attached to this study (from notes <img data-img-key>, legacy screenshots)
  const imgKeys = new Set();
  (st.screenshots || []).forEach(ss => imgKeys.add(ss.imgKey));
  const noteImgs = (st.notes || '').match(/data-img-key="([^"]+)"/g) || [];
  noteImgs.forEach(m => imgKeys.add(m.replace(/data-img-key="|"$/g, '')));
  const beforeImgs = {};
  for (const k of imgKeys) { try { const v = await getImg(k); if (v) beforeImgs[k] = v; } catch {} }
  // Delete
  saveStudies(studies.filter(s => s.symbol !== sym));
  for (const k of imgKeys) { try { await delImg(k); } catch {} }
  renderStudies();
  showUndoSnackbar(`Removed ${sym}`, async () => {
    saveStudies([...loadStudies(), st]);
    for (const [k, v] of Object.entries(beforeImgs)) { try { await putImg(k, v); } catch {} }
    renderStudies();
  });
};

/* ═══════ Study detail page — #/study/<SYM> ═══════
   Same layout as the standard stock detail page, but every value is editable. Changes
   live on the study object only — never mutates DATA.stocks. Sections:
     • Header (symbol + chgPct + long/short + Save/Delete + Sections gear)
     • Catalyst (free-form textarea)
     • EPS Surp % / Rev Surp % chips → 漲幅 / 止損 chips (click opens OHLCV popup)
     • EPS Quarterly bar chart  ─┐
     • Revenue Quarterly bar chart ─┴─ all driven by study.customChart (overrides snapshot.tv.chart)
     • MS-style quarterly table (editable cells)
     • Forward YoY block
     • Notion-style notes (contenteditable + paste/drop images)
   Section visibility configurable via the gear button. */
async function renderStudyDetail(sym) {
  const app = document.getElementById('app');
  const study = loadStudies().find(st => st.symbol === sym);
  if (!study) {
    app.innerHTML = `<div class="empty">Study ${sym} not found. <a href="#/studies">← Back to Studies</a></div>`;
    return;
  }
  const s = study.snapshot || {};
  // %Chg priority (highest → lowest):
  //   1. study.chgPct        — user's manual override (future-proofing; no UI yet, set via OHLCV modal if you ever add one)
  //   2. derived from ohlcv  — (close − prev_close) / prev_close · 100, once /SIPs Phase 10b has filled both
  //   3. snapshot.chgPct     — the gap % (pre-market / post-market) baked in at scan time
  function deriveDayChgPct(ohlcv) {
    if (!ohlcv) return null;
    const close = ohlcv.close, prev = ohlcv.prev_close;
    if (close == null || prev == null || prev === 0) return null;
    return (close - prev) / prev * 100;
  }
  const _derivedChg = deriveDayChgPct(study.ohlcv);
  const chg = (study.chgPct != null) ? study.chgPct
            : (_derivedChg != null)  ? _derivedChg
            : s.chgPct;
  // Tag the chg readout so the hover title explains where the value came from.
  const chgSource = (study.chgPct != null) ? 'manual override'
                  : (_derivedChg != null)  ? "derived from today's OHLCV (close − prev_close)"
                  : 'snapshot gap % (pre/post-market)';
  // intent auto-derived from chgPct sign (gap up = long, gap down = short) — no UI override.
  const intent = chg < 0 ? 'short' : 'long';
  // Custom chart overrides snapshot's TV chart when user edits MS-table values.
  const baseChart = (s.tv && s.tv.chart) ? s.tv.chart : null;
  // Section visibility (hidden set). Defaults: everything visible. Hide via the X on each card.
  const sectionsAll = ['eps_chart', 'rev_chart', 'ms_table', 'yoy_block', 'notes'];
  const sectionLabels = { eps_chart: 'EPS Quarterly', rev_chart: 'Revenue Quarterly', ms_table: '季度 EPS / Sales', yoy_block: 'Forward YoY', notes: 'Notes' };
  const hidden = new Set(study.hiddenSections || []);
  const sectionShown = id => !hidden.has(id);
  // Migrate legacy thumbnail screenshots into the notes HTML on first detail-view render
  let notesHtml = study.notes || '';
  if (Array.isArray(study.screenshots) && study.screenshots.length && !study._migratedShots) {
    const tail = study.screenshots.map(ss =>
      `<p><span class="notes-img-wrap" contenteditable="false"><img data-img-key="${ss.imgKey}" alt="${escapeHtml(ss.label || '')}"><button class="notes-img-del" type="button" data-img-key="${ss.imgKey}" title="Delete image">&times;</button></span></p>${ss.label ? `<p><em>${escapeHtml(ss.label)}</em></p>` : ''}`
    ).join('');
    notesHtml = (notesHtml || '') + tail;
    updateStudy(sym, { notes: notesHtml, _migratedShots: true, screenshots: [] });
  }

  // Direction-aware metrics. 漲幅 (gain) = (H-O)/O · 止損 (stop) = (L-O)/O · sign-flipped for short.
  function computeMetrics() {
    const cur = loadStudies().find(st => st.symbol === sym)?.ohlcv || {};
    const dir = intent === 'short' ? -1 : 1;
    const gain = (cur.open && cur.high) ? ((cur.high - cur.open) / cur.open * 100 * dir) : null;
    const stop = (cur.open && cur.low)  ? ((cur.low  - cur.open) / cur.open * 100 * dir) : null;
    return { gain, stop };
  }
  const { gain: initGain, stop: initStop } = computeMetrics();
  const fmtMetric = v => v == null ? '—' : (v >= 0 ? '+' : '') + v.toFixed(2) + '%';

  // Build the four pill rows that mirror renderStock — short / surp / NEW trade pills.
  const _tv = s.tv;
  const sessTags = (s.sessions || []).map(x => `<span class="tag">${x.session.toUpperCase()} <span class="dot dot-${x.direction}"></span> ${fmtPctShort(x.chgPct)}</span>`).join(' ');
  const typeTag = `<span class="tag ${typeTagClass(s.type || 'momentum')}">${s.type || 'momentum'}</span>`;
  const _surpPill = (lbl, v, title) => v == null
    ? ''
    : `<span class="tag stat-tag ${v >= 0 ? 'pos' : 'neg'}" title="${title}">${lbl} ${(v >= 0 ? '+' : '') + v.toFixed(1)}%</span>`;
  const headerShortPills = [
    s.shortFloat != null ? `<span class="tag stat-tag" title="Short Float — % of float currently shorted">Short Float ${s.shortFloat.toFixed(1)}%</span>` : '',
    s.shortRatio != null ? `<span class="tag stat-tag" title="Days to cover (short ratio)">DTC ${s.shortRatio.toFixed(1)}d</span>` : '',
  ].filter(Boolean).join(' ');
  const headerSurpPills = [
    _tv ? _surpPill('EPS Surp', _tv.surpriseEPS_pct, 'EPS surprise vs consensus (TradingView FQ)') : '',
    _tv ? _surpPill('Rev Surp', _tv.surpriseRev_pct, 'Revenue surprise vs consensus (TradingView FQ)') : '',
  ].filter(Boolean).join(' ');
  // Trade pills row — Gain / Stop, click to open OHLCV popup. Pos/neg tinted.
  const gainCls = initGain == null ? '' : (initGain >= 0 ? 'pos' : 'neg');
  const stopCls = initStop == null ? '' : (initStop >= 0 ? 'pos' : 'neg');
  const tradePills = `
    <button class="tag stat-tag trade-pill ${gainCls}" type="button" id="study-gain-pill" title="Gain = (High − Open) / Open · sign-flipped for short · click to edit OHLCV">Gain <span id="study-gain-val">${fmtMetric(initGain)}</span></button>
    <button class="tag stat-tag trade-pill ${stopCls}" type="button" id="study-stop-pill" title="Stop = (Low − Open) / Open · sign-flipped for short · click to edit OHLCV">Stop <span id="study-stop-val">${fmtMetric(initStop)}</span></button>`;
  // Day-1 badge if applicable (from snapshot's _dayLabel — saved at the time the study was added)
  const dayChip = (study.snapshot?._dayLabel === 'day1') ? `<span class="day-badge day1">day1</span>` : '';
  // Catalyst row from the snapshot — if user has saved a custom catalyst override, prefer it
  const cat = (study.catalyst != null && study.catalyst !== '') ? study.catalyst : (s.catalyst || '');
  // News detail (snapshot) — shown like the original stock detail page
  const detail = s.newsDetail || '';
  const fallbackCatalyst = cat;
  const newsBlockHtml = detail
    ? `<div class="stock-card news-detail"><h3>新聞詳情 <span class="label-en">News Detail</span></h3>${String(detail).split(/\n\n+/).filter(Boolean).map(p => `<p>${escapeHtml(p).replace(/\n/g,'<br>')}</p>`).join('')}</div>`
    : (fallbackCatalyst ? `<div class="stock-card news-detail"><h3>新聞詳情 <span class="label-en">News Detail</span></h3><p>${escapeHtml(fallbackCatalyst)}</p></div>` : '');
  // Forward YoY block — copies the renderStock pattern exactly so the Copy button works.
  // If the user has edited the MS table (customChart present), regenerate the YoY text from
  // those custom arrays. Otherwise fall back to the snapshot's pre-baked yoyBlock from Python.
  const _customChart = study.customChart || null;
  const _initialYoyTxt = _customChart
    ? buildYoyBlockText(_customChart)
    : (s.tv && s.tv.yoyBlock) || '';
  const yoyHtml = _initialYoyTxt
    ? `<button class="copy-btn" data-copy-target="yoy-${sym}">Copy</button><div class="yoy-block" id="yoy-${sym}" data-raw="${escapeHtml(_initialYoyTxt)}">${colorizeYoyBlock(_initialYoyTxt)}</div>`
    : '';

  // Helper: render a section card with an X button. Sections can be hidden via the X then
  // re-added via right-click context menu.
  const sectionCard = (id, titleHtml, bodyHtml) => sectionShown(id)
    ? `<div class="stock-card study-section" data-section="${id}"><button class="section-x" type="button" data-section="${id}" title="Hide section (right-click anywhere to restore)">&times;</button>${titleHtml}${bodyHtml}</div>`
    : '';

  app.innerHTML = `
    <div class="breadcrumb"><a href="#/studies">← Studies</a> &nbsp;»&nbsp; <b>${sym}</b></div>
    <div class="stock-header" style="position:relative">
      <button class="studies-btn studies-btn-danger" id="study-delete" style="position:absolute;top:18px;right:18px;font-size:11px;padding:5px 12px">Delete</button>
      <div class="sym-big">${sym}${dayChip}</div>
      <div>
        <div class="name">${escapeHtml(s.name || '')}</div>
        <div class="stock-header-tags">${sessTags} ${typeTag}</div>
        ${headerShortPills ? `<div class="stock-header-tags stock-header-short">${headerShortPills}</div>` : ''}
        ${headerSurpPills  ? `<div class="stock-header-tags stock-header-surp">${headerSurpPills}</div>`   : ''}
        <div class="stock-header-tags stock-header-trade">${tradePills}</div>
      </div>
      <div style="margin-left:auto;text-align:right">
        <div class="price">${fmtPrice(s.last)}</div>
        <div class="chg ${cls(chg)}" id="study-chg-readout" title="${chgSource}">${fmtPct(chg)} · Vol ${fmtVol(s.volume)}</div>
      </div>
    </div>
    ${newsBlockHtml}
    <div class="chart-wrap study-charts-wrap" id="study-chart-wrap">
      ${sectionCard('eps_chart', `<h3>EPS Quarterly <span class="label-en">Reported vs Estimate</span></h3>`, `<div id="study-eps-chart-host"></div>`)}
      ${sectionCard('rev_chart', `<h3>Revenue Quarterly <span class="label-en">Reported vs Estimate</span></h3>`, `<div id="study-rev-chart-host"></div>`)}
    </div>
    ${sectionCard('ms_table', `<h3>季度 EPS / Sales <span class="label-en">Reported + Estimate · click any value to edit</span></h3>`, `<div id="study-ms-host"></div>`)}
    ${sectionCard('yoy_block', `<h3>Forward YoY <span class="label-en">TradingView FQ — EPS YoY / Rev YoY</span></h3>`, yoyHtml || '<div style="color:var(--stone)">No TradingView quarterly estimate data</div>')}
    ${sectionCard('notes', `<h3>Notes <span class="label-en">paste images (Ctrl+V) or drag-drop · Ctrl+Z to undo</span></h3>`, `<div class="study-notes-rich" id="study-notes" contenteditable="${STATE.sidecar.available ? 'true' : 'false'}" data-placeholder="${t('studies-note-placeholder')}">${notesHtml}</div>`)}
  `;

  // ── Chart + MS-table render helpers (recompute when customChart changes) ──
  function activeChart() {
    return loadStudies().find(st => st.symbol === sym)?.customChart || baseChart;
  }
  function renderAllCharts() {
    const c = activeChart();
    if (!c) return;
    const eps = document.getElementById('study-eps-chart-host');
    const rev = document.getElementById('study-rev-chart-host');
    if (eps) eps.innerHTML = svgBarChart(c.quarters, c.eps_reported, c.eps_estimate, c.latest_idx, false);
    if (rev) rev.innerHTML = svgBarChart(c.quarters, c.rev_reported_M, c.rev_estimate_M, c.latest_idx, true);
    const ms = document.getElementById('study-ms-host');
    if (ms) ms.innerHTML = renderEditableMsTable(c, sym);
    recomputeMsComputedCells(c);
    bindMsTableEditors();
  }
  // Editable MS table input listeners — write back into the right array slot of customChart,
  // then re-recompute the dependent YoY/Surp cells + re-render the bar charts.
  function bindMsTableEditors() {
    document.querySelectorAll('.ms-cell-input').forEach(inp => {
      inp.addEventListener('input', () => {
        const cur = loadStudies().find(st => st.symbol === sym);
        if (!cur) return;
        // Lazy-clone the chart so the original snapshot stays untouched
        const c = cur.customChart ? { ...cur.customChart,
          eps_reported: [...(cur.customChart.eps_reported || baseChart.eps_reported)],
          eps_estimate: [...(cur.customChart.eps_estimate || baseChart.eps_estimate)],
          rev_reported_M: [...(cur.customChart.rev_reported_M || baseChart.rev_reported_M)],
          rev_estimate_M: [...(cur.customChart.rev_estimate_M || baseChart.rev_estimate_M)]
        } : {
          quarters: [...baseChart.quarters],
          eps_reported: [...baseChart.eps_reported],
          eps_estimate: [...baseChart.eps_estimate],
          rev_reported_M: [...baseChart.rev_reported_M],
          rev_estimate_M: [...baseChart.rev_estimate_M],
          latest_idx: baseChart.latest_idx,
        };
        const qi = parseInt(inp.dataset.qi, 10);
        const isRep = inp.dataset.isrep === '1';
        const v = inp.value === '' ? null : parseFloat(inp.value);
        if (inp.dataset.row === 'eps') { (isRep ? c.eps_reported : c.eps_estimate)[qi] = (v != null && !isNaN(v)) ? v : null; }
        else                            { (isRep ? c.rev_reported_M : c.rev_estimate_M)[qi] = (v != null && !isNaN(v)) ? v : null; }
        updateStudy(sym, { customChart: c });
        // Re-render bar charts immediately + update computed cells
        const epsHost = document.getElementById('study-eps-chart-host');
        const revHost = document.getElementById('study-rev-chart-host');
        if (epsHost) epsHost.innerHTML = svgBarChart(c.quarters, c.eps_reported, c.eps_estimate, c.latest_idx, false);
        if (revHost) revHost.innerHTML = svgBarChart(c.quarters, c.rev_reported_M, c.rev_estimate_M, c.latest_idx, true);
        recomputeMsComputedCells(c);
        refreshYoyBlock(c);
      });
    });
  }
  // Re-paint the Forward YoY card from a (possibly customized) chart object so it stays
  // in sync with MS-table edits. Uses buildYoyBlockText (JS twin of parse_tv.yoy).
  function refreshYoyBlock(chart) {
    const host = document.getElementById(`yoy-${sym}`);
    if (!host) return;
    const txt = buildYoyBlockText(chart);
    if (!txt) {
      host.innerHTML = '<span class="nm">No quarterly data</span>';
      host.removeAttribute('data-raw');
      return;
    }
    host.setAttribute('data-raw', txt);
    host.innerHTML = colorizeYoyBlock(txt);
  }
  renderAllCharts();

  // Refresh Gain / Stop trade pills (called from OHLCV popup on every keystroke)
  function refreshTradeMetrics() {
    const m = computeMetrics();
    const gainEl = document.getElementById('study-gain-val');
    const stopEl = document.getElementById('study-stop-val');
    const gainBtn = document.getElementById('study-gain-pill');
    const stopBtn = document.getElementById('study-stop-pill');
    if (gainEl) gainEl.textContent = fmtMetric(m.gain);
    if (stopEl) stopEl.textContent = fmtMetric(m.stop);
    if (gainBtn) gainBtn.className = `tag stat-tag trade-pill ${m.gain == null ? '' : (m.gain >= 0 ? 'pos' : 'neg')}`;
    if (stopBtn) stopBtn.className = `tag stat-tag trade-pill ${m.stop == null ? '' : (m.stop >= 0 ? 'pos' : 'neg')}`;
  }

  // Re-render the %Chg readout in the header — runs whenever OHLCV changes so the auto-derived
  // day-chgPct flips in real time as user fills close/prev_close.
  function refreshChgReadout() {
    const cur = loadStudies().find(st => st.symbol === sym);
    if (!cur) return;
    const derived = deriveDayChgPct(cur.ohlcv);
    const newChg = (cur.chgPct != null) ? cur.chgPct
                 : (derived != null)    ? derived
                 : s.chgPct;
    const src = (cur.chgPct != null) ? 'manual override'
              : (derived != null)    ? "derived from today's OHLCV (close − prev_close)"
              : 'snapshot gap % (pre/post-market)';
    const el = document.getElementById('study-chg-readout');
    if (!el) return;
    el.className = `chg ${cls(newChg)}`;
    el.title = src;
    el.textContent = `${fmtPct(newChg)} · Vol ${fmtVol(s.volume)}`;
  }

  // ── OHLCV popup modal — opens when user clicks either trade metric chip ──
  function openOhlcvModal() {
    const cur = loadStudies().find(st => st.symbol === sym)?.ohlcv || {};
    const modal = document.createElement('div');
    modal.className = 'ohlcv-modal-overlay';
    modal.innerHTML = `
      <div class="ohlcv-modal" onclick="event.stopPropagation()">
        <div class="ohlcv-modal-head">
          <h3>OHLCV — ${sym}</h3>
          <button class="ohlcv-modal-close" type="button">&times;</button>
        </div>
        <div class="ohlcv-modal-body">
          <label class="study-ohlcv-field"><span>${t('ohlcv-date')}</span><input data-field="date" type="date" value="${cur.date || ''}"></label>
          <label class="study-ohlcv-field"><span>${t('ohlcv-open')}</span><input data-field="open" type="number" step="0.01" value="${cur.open ?? ''}" placeholder="—"></label>
          <label class="study-ohlcv-field"><span>${t('ohlcv-high')}</span><input data-field="high" type="number" step="0.01" value="${cur.high ?? ''}" placeholder="—"></label>
          <label class="study-ohlcv-field"><span>${t('ohlcv-low')}</span><input data-field="low" type="number" step="0.01" value="${cur.low ?? ''}" placeholder="—"></label>
          <label class="study-ohlcv-field"><span>${t('ohlcv-close')}</span><input data-field="close" type="number" step="0.01" value="${cur.close ?? ''}" placeholder="—"></label>
          <label class="study-ohlcv-field" title="Prior-day close — drives the day's %Chg derivation. Auto-filled by /SIPs Phase 10b when available."><span>${t('ohlcv-prev-close')}</span><input data-field="prev_close" type="number" step="0.01" value="${cur.prev_close ?? ''}" placeholder="—"></label>
          <label class="study-ohlcv-field"><span>${t('ohlcv-volume')}</span><input data-field="volume" type="number" step="1000" value="${cur.volume ?? ''}" placeholder="—"></label>
        </div>
        <div class="ohlcv-modal-foot">
          <button class="studies-btn" type="button" id="ohlcv-modal-done">Done</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    requestAnimationFrame(() => modal.classList.add('show'));
    const close = () => { modal.classList.remove('show'); setTimeout(() => modal.remove(), 180); };
    modal.onclick = close;
    modal.querySelector('.ohlcv-modal-close').onclick = close;
    modal.querySelector('#ohlcv-modal-done').onclick = close;
    modal.querySelectorAll('input').forEach(inp => {
      inp.addEventListener('input', e => {
        const field = e.target.dataset.field;
        const ohlcv = loadStudies().find(st => st.symbol === sym)?.ohlcv || {};
        const val = field === 'date' ? e.target.value : (parseFloat(e.target.value) || null);
        updateStudy(sym, { ohlcv: { ...ohlcv, [field]: val } });
        refreshTradeMetrics();
        refreshChgReadout();
      });
    });
    // Focus first empty input for fast entry
    const focusInp = Array.from(modal.querySelectorAll('input')).find(i => !i.value) || modal.querySelector('input');
    focusInp?.focus();
  }
  document.getElementById('study-gain-pill')?.addEventListener('click', openOhlcvModal);
  document.getElementById('study-stop-pill')?.addEventListener('click', openOhlcvModal);

  // ── Per-section X to hide + right-click menu to bring back ──
  app.querySelectorAll('.section-x').forEach(btn => {
    btn.addEventListener('click', e => {
      e.preventDefault();
      const sid = e.target.dataset.section;
      const cur = loadStudies().find(st => st.symbol === sym);
      if (!cur) return;
      const next = new Set(cur.hiddenSections || []);
      next.add(sid);
      updateStudy(sym, { hiddenSections: Array.from(next) });
      const card = e.target.closest('.study-section');
      if (card) card.remove();
    });
  });
  // Right-click anywhere on the detail page → context menu listing hidden sections to restore
  app.addEventListener('contextmenu', e => {
    const cur = loadStudies().find(st => st.symbol === sym);
    const hiddenList = (cur?.hiddenSections || []).filter(id => sectionsAll.includes(id));
    if (hiddenList.length === 0) return;   // default browser menu wins when nothing to restore
    e.preventDefault();
    // Remove any open menu
    document.querySelectorAll('.study-ctx-menu').forEach(m => m.remove());
    const menu = document.createElement('div');
    menu.className = 'study-ctx-menu';
    menu.style.left = e.clientX + 'px';
    menu.style.top  = e.clientY + 'px';
    menu.innerHTML = `<div class="study-ctx-menu-title">Restore hidden section</div>` +
      hiddenList.map(id => `<button class="study-ctx-menu-item" data-section="${id}">+ ${sectionLabels[id] || id}</button>`).join('');
    document.body.appendChild(menu);
    const close = () => menu.remove();
    menu.querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
      const sid = b.dataset.section;
      const cur2 = loadStudies().find(st => st.symbol === sym);
      const remaining = (cur2?.hiddenSections || []).filter(x => x !== sid);
      updateStudy(sym, { hiddenSections: remaining });
      close();
      renderStudyDetail(sym);   // re-render so the restored card appears in its original slot
    }));
    setTimeout(() => document.addEventListener('click', close, { once: true }), 0);
  });
  // Hydrate all <img data-img-key> inside notes from IndexedDB. For legacy imgs that aren't
  // already wrapped in .notes-img-wrap (older format), retro-fit the wrap + delete X so the
  // user can manage them the same way as freshly-pasted ones.
  for (const img of app.querySelectorAll('#study-notes img[data-img-key]')) {
    const key = img.getAttribute('data-img-key');
    if (key && !img.src) {
      try { const data = await getImg(key); if (data) img.src = data; } catch {}
    }
    img.style.cursor = 'zoom-in';
    // Retro-wrap legacy imgs (no parent .notes-img-wrap)
    if (img.parentElement && !img.parentElement.classList?.contains('notes-img-wrap')) {
      const wrap = document.createElement('span');
      wrap.className = 'notes-img-wrap';
      wrap.contentEditable = 'false';
      img.replaceWith(wrap);
      wrap.appendChild(img);
      const del = document.createElement('button');
      del.type = 'button';
      del.className = 'notes-img-del';
      del.dataset.imgKey = key;
      del.title = 'Delete image';
      del.innerHTML = '&times;';
      wrap.appendChild(del);
    }
  }
  // Delegated click handler for notes block — handles X (delete) + img click (lightbox).
  // Image delete is wrapped in an undo snackbar so accidental clicks are recoverable:
  //   • capture full notes innerHTML (with img src still attached) + the IDB image data
  //   • remove the wrap + delImg
  //   • on undo: putImg the data back + restore notes innerHTML to the pre-delete state
  app.querySelector('#study-notes')?.addEventListener('click', async e => {
    const delBtn = e.target.closest?.('.notes-img-del');
    if (delBtn) {
      e.preventDefault();
      const key = delBtn.dataset.imgKey;
      const notesEl = document.getElementById('study-notes');
      const wrap = delBtn.closest('.notes-img-wrap');
      // Snapshot for undo BEFORE mutation
      const beforeHtml = notesEl?.innerHTML;
      let beforeImg = null;
      try { beforeImg = await getImg(key); } catch {}
      // Apply delete
      wrap?.remove();
      try { await delImg(key); } catch {}
      // Persist the post-delete notes
      notesEl?.dispatchEvent(new Event('input', { bubbles: true }));
      // Undo: put the image back into IDB/disk + restore the notes HTML at original position
      showUndoSnackbar('Image deleted', async () => {
        if (beforeImg) { try { await putImg(key, beforeImg); } catch {} }
        if (notesEl && beforeHtml != null) {
          notesEl.innerHTML = beforeHtml;
          // Re-hydrate any img missing a src (defensive — beforeHtml already has src baked in)
          for (const img of notesEl.querySelectorAll('img[data-img-key]')) {
            if (!img.src) {
              const k = img.getAttribute('data-img-key');
              try { const v = await getImg(k); if (v) img.src = v; } catch {}
            }
          }
          notesEl.dispatchEvent(new Event('input', { bubbles: true }));
        }
      });
      return;
    }
    if (e.target.tagName === 'IMG' && e.target.src) {
      openShotLightbox(e.target.src);
    }
  });
  // Wire Copy buttons (Forward YoY) — mirrors the renderStock pattern
  app.querySelectorAll('.copy-btn').forEach(btn => {
    btn.onclick = async () => {
      const tgt = document.getElementById(btn.dataset.copyTarget);
      if (!tgt) return;
      const text = tgt.dataset.raw || tgt.textContent;
      try { await navigator.clipboard.writeText(text); }
      catch (e) { const ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove(); }
      btn.textContent = 'Copied!'; btn.classList.add('copied');
      setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 1200);
    };
  });
  // Delete with snackbar undo (instead of confirm dialog, since clear-all already pattern)
  document.getElementById('study-delete')?.addEventListener('click', async () => {
    const snapshot = loadStudies().find(st => st.symbol === sym);
    if (!snapshot) return;
    // Collect image keys for restore
    const imgKeys = new Set();
    const noteImgs = (snapshot.notes || '').match(/data-img-key="([^"]+)"/g) || [];
    noteImgs.forEach(m => imgKeys.add(m.replace(/data-img-key="|"$/g, '')));
    const beforeImgs = {};
    for (const k of imgKeys) { try { const v = await getImg(k); if (v) beforeImgs[k] = v; } catch {} }
    saveStudies(loadStudies().filter(s => s.symbol !== sym));
    for (const k of imgKeys) { try { await delImg(k); } catch {} }
    location.hash = '#/studies';
    showUndoSnackbar(`Deleted ${sym}`, async () => {
      saveStudies([...loadStudies(), snapshot]);
      for (const [k, v] of Object.entries(beforeImgs)) { try { await putImg(k, v); } catch {} }
      location.hash = '#/study/' + sym;
    });
  });
  // Notion-style notes — contenteditable with inline image paste/drop. Save innerHTML on input
  // (debounced via animation frame to batch fast typing).
  const notes = document.getElementById('study-notes');
  let saveTimer = null;
  const flushSave = () => {
    // Strip inline data: URIs from src before storage — images live in IndexedDB by data-img-key
    const clone = notes.cloneNode(true);
    clone.querySelectorAll('img[data-img-key]').forEach(img => img.removeAttribute('src'));
    updateStudy(sym, { notes: clone.innerHTML });
  };
  const scheduleSave = () => {
    if (saveTimer) cancelAnimationFrame(saveTimer);
    saveTimer = requestAnimationFrame(flushSave);
  };
  notes?.addEventListener('input', scheduleSave);
  // Image paste handler — insert <span.notes-img-wrap><img><button.notes-img-del>✕</button></span>
  // at cursor via execCommand so browser-native Ctrl+Z still works.
  const insertImgAtCursor = (dataUrl, key) => {
    const safeUrl = dataUrl.replace(/"/g, '&quot;');
    const html = `<span class="notes-img-wrap" contenteditable="false">` +
      `<img src="${safeUrl}" data-img-key="${key}" class="notes-inline-img" style="cursor:zoom-in">` +
      `<button class="notes-img-del" type="button" data-img-key="${key}" title="Delete image">&times;</button>` +
    `</span><br>`;
    notes.focus();
    if (!document.execCommand('insertHTML', false, html)) {
      // Fallback if execCommand is unavailable in the future
      const wrap = document.createElement('span');
      wrap.className = 'notes-img-wrap';
      wrap.contentEditable = 'false';
      wrap.innerHTML = `<img src="${safeUrl}" data-img-key="${key}" class="notes-inline-img" style="cursor:zoom-in"><button class="notes-img-del" type="button" data-img-key="${key}" title="Delete image">&times;</button>`;
      notes.appendChild(wrap);
      notes.appendChild(document.createElement('br'));
    }
    scheduleSave();
  };
  notes?.addEventListener('paste', async e => {
    const items = Array.from(e.clipboardData?.items || []);
    const imgItem = items.find(it => it.type.startsWith('image/'));
    if (imgItem) {
      e.preventDefault();
      const file = imgItem.getAsFile();
      const dataUrl = await downscaleImage(file);
      const key = uuid();
      await putImg(key, dataUrl);
      insertImgAtCursor(dataUrl, key);
    }
    // For non-image paste, also strip rich formatting (paste as plain text)
    else {
      const text = e.clipboardData?.getData('text/plain');
      if (text) {
        e.preventDefault();
        document.execCommand('insertText', false, text);
      }
    }
  });
  notes?.addEventListener('dragover', e => { e.preventDefault(); notes.classList.add('drag-over'); });
  notes?.addEventListener('dragleave', () => notes.classList.remove('drag-over'));
  notes?.addEventListener('drop', async e => {
    e.preventDefault();
    notes.classList.remove('drag-over');
    const files = Array.from(e.dataTransfer?.files || []).filter(f => f.type.startsWith('image/'));
    for (const file of files) {
      const dataUrl = await downscaleImage(file);
      const key = uuid();
      await putImg(key, dataUrl);
      insertImgAtCursor(dataUrl, key);
    }
  });
}

// Lightbox modal for clicking any image (used both in notes inline + legacy screenshots)
function openShotLightbox(dataUrl, caption) {
  const overlay = document.createElement('div');
  overlay.className = 'shot-lightbox';
  overlay.innerHTML = `<img src="${dataUrl}">${caption ? `<div class="shot-caption">${escapeHtml(caption)}</div>` : ''}`;
  overlay.onclick = () => overlay.remove();
  document.body.appendChild(overlay);
}

// ── Undo snackbar ───────────────────────────────────────────────
// Reusable bottom-of-screen toast for destructive actions. Caller passes
// (message, undoFn). 10s auto-dismiss; click Undo to invoke undoFn.
function showUndoSnackbar(message, undoFn, ms = 10000) {
  const old = document.getElementById('undo-snackbar');
  if (old) old.remove();
  const snack = document.createElement('div');
  snack.id = 'undo-snackbar';
  snack.className = 'undo-snackbar';
  snack.innerHTML = `<span></span><button class="undo-btn">Undo</button>`;
  snack.querySelector('span').textContent = message;
  document.body.appendChild(snack);
  requestAnimationFrame(() => snack.classList.add('show'));
  let dismissed = false;
  const dismiss = () => {
    if (dismissed) return; dismissed = true;
    snack.classList.remove('show');
    setTimeout(() => snack.remove(), 300);
  };
  const timer = setTimeout(dismiss, ms);
  snack.querySelector('.undo-btn').onclick = async () => {
    clearTimeout(timer);
    try { await undoFn(); } catch (e) { console.warn('undo failed', e); }
    dismiss();
  };
}

boot();
</script>
</body>
</html>
'''

with open(os.path.join(DASH_DIR, 'index.html'), 'w', encoding='utf-8') as f:
    f.write(INDEX_HTML)
print(f'[OK] index.html ({len(INDEX_HTML)} bytes) written to {DASH_DIR}')
