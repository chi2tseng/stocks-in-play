#!/usr/bin/env python
"""fetch_candles.py — anchor-aware Yahoo Finance daily-bar scraper.

Pulls ~1 year of OHLCV per ticker, computed PER-SYMBOL from the union of
"anchor dates" relevant to that ticker:
  - today's dashboard/data/<DATE>.json scan candidates → anchor = today
  - claude/codex/gemini picks for today → anchor = today
  - dashboard/studies/studies.json → each study's effective date AND every
    one of its datedSnapshots dates (so a study with anchor 4/30 still has
    chart data when the user adds a new 10/30 anchor for the same symbol)

Per-symbol fetch range:
  earliest_fetch = min(anchors) − 10 months
  latest_fetch   = min(today, max(anchors) + 2 months)

This gives every anchor a ~6-month default display window (-4mo … +2mo)
with ~6 extra months of scroll-back data the user can wheel-zoom into.

Writes to dashboard/candles.json (static asset, fetched once at dashboard boot).
Run after /SIPs Phase 9 (claude_picks.json written) and BEFORE Phase 10
(build_dashboard.py). Schema unchanged: { "SYM": [bar, bar, ...], ... }.
"""

import json, time, urllib.request, urllib.error
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from collections import defaultdict

DIR = Path(__file__).resolve().parent
TODAY = datetime.now(timezone.utc).strftime('%Y-%m-%d')
NOW_TS = int(datetime.now(timezone.utc).timestamp())


def _add_months_iso(iso, months):
    """Naive month arithmetic on an ISO date string. Returns ISO YYYY-MM-DD."""
    d = datetime.strptime(iso, '%Y-%m-%d')
    new_month = d.month + months
    new_year = d.year + (new_month - 1) // 12
    new_month = ((new_month - 1) % 12) + 1
    # Clamp day to last-day-of-month to avoid invalid dates like Feb 31.
    import calendar
    last_day = calendar.monthrange(new_year, new_month)[1]
    new_day = min(d.day, last_day)
    return f'{new_year:04d}-{new_month:02d}-{new_day:02d}'


def _iso_to_ts(iso):
    return int(datetime.strptime(iso, '%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp())


def collect_anchors_per_symbol():
    """Returns dict {sym: set(anchor_iso_dates)}. Each anchor = a date the
    user wants the chart to be reference-able from. Today's date is implicit
    for all scan / picks tickers; studies contribute their own per-date anchors."""
    anchors = defaultdict(set)
    # 1. Today's scan candidates → anchor on today's scan date (filename).
    today_data_path = DIR / 'dashboard' / 'data' / f'{TODAY}.json'
    scan_date = TODAY
    if today_data_path.exists():
        try:
            d = json.loads(today_data_path.read_text(encoding='utf-8'))
            scan_date = d.get('date') or TODAY
            for sym in (d.get('stocks') or {}).keys():
                anchors[sym.upper()].add(scan_date)
        except Exception:
            pass
    # 2. Picks files (claude / codex / gemini) → anchored on scan_date.
    for f in ['claude_picks.json', 'codex_picks.json', 'gemini_picks.json']:
        p = DIR / f
        if p.exists():
            try:
                pj = json.loads(p.read_text(encoding='utf-8'))
                for pk in pj.get('picks', []):
                    s = pk.get('symbol')
                    if s:
                        anchors[s.upper()].add(scan_date)
            except Exception:
                pass
    # 3. Studies → every study's effective date + every datedSnapshots key.
    studies_path = DIR / 'dashboard' / 'studies' / 'studies.json'
    if studies_path.exists():
        try:
            arr = json.loads(studies_path.read_text(encoding='utf-8'))
            for st in arr:
                sym = (st.get('symbol') or '').upper()
                if not sym:
                    continue
                # Primary anchor: ohlcv.date → snapshot.scanDate → savedAt-date.
                primary = (
                    ((st.get('ohlcv') or {}).get('date'))
                    or ((st.get('snapshot') or {}).get('scanDate'))
                    or (st.get('savedAt') or '')[:10]
                )
                if primary and len(primary) == 10:
                    anchors[sym].add(primary)
                # Every datedSnapshot key contributes a separate anchor — these are
                # the per-date research sessions the user has saved.
                for ds_date in (st.get('datedSnapshots') or {}).keys():
                    if ds_date and len(ds_date) == 10:
                        anchors[sym].add(ds_date)
        except Exception:
            pass
    return anchors


def fetch_one(sym, fetch_from_iso, fetch_to_iso):
    """Yahoo Finance daily chart between fetch_from and fetch_to (ISO dates).
    Returns list of bar dicts, or None on failure."""
    p1 = _iso_to_ts(fetch_from_iso) - 2 * 86400      # 2-day padding on each side
    p2 = min(NOW_TS, _iso_to_ts(fetch_to_iso) + 2 * 86400)
    if p2 <= p1:
        return None
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}&interval=1d'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.load(r)
        res = (d.get('chart') or {}).get('result') or [None]
        res = res[0] if res else None
        if not res:
            return None
        ts = res.get('timestamp') or []
        q = ((res.get('indicators') or {}).get('quote') or [{}])[0]
        bars = []
        for i, t in enumerate(ts):
            o = q.get('open', [None] * len(ts))[i]
            h = q.get('high', [None] * len(ts))[i]
            l = q.get('low',  [None] * len(ts))[i]
            c = q.get('close',[None] * len(ts))[i]
            v = q.get('volume',[None]* len(ts))[i]
            if o is None or c is None:
                continue
            bars.append({
                'date':   datetime.fromtimestamp(t, tz=timezone.utc).strftime('%Y-%m-%d'),
                'open':   round(o, 2),
                'high':   round(h, 2) if h is not None else round(max(o, c), 2),
                'low':    round(l, 2) if l is not None else round(min(o, c), 2),
                'close':  round(c, 2),
                'volume': int(v) if v is not None else None,
            })
        return bars
    except Exception:
        return None


def main():
    anchors_by_sym = collect_anchors_per_symbol()
    if not anchors_by_sym:
        print('[skip] no symbols found in scan / picks / studies')
        return
    # Compute per-symbol fetch range.
    tasks = []   # list of (sym, fetch_from_iso, fetch_to_iso)
    for sym, anchors in anchors_by_sym.items():
        sorted_anchors = sorted(anchors)
        earliest = sorted_anchors[0]
        latest = sorted_anchors[-1]
        # Wide enough for any anchor's [-4mo .. +2mo] display window + 6mo scroll-back.
        fetch_from = _add_months_iso(earliest, -10)
        fetch_to = _add_months_iso(latest, 2)
        if fetch_to > TODAY:
            fetch_to = TODAY
        tasks.append((sym, fetch_from, fetch_to))
    print(f'[fetch_candles] {len(tasks)} symbols to fetch (per-anchor 1-year ranges)')

    out = {}
    fail = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch_one, s, ff, ft): s for s, ff, ft in tasks}
        done = 0
        for f in as_completed(futs):
            sym = futs[f]
            done += 1
            try:
                bars = f.result()
                if bars and len(bars) > 10:
                    out[sym] = bars
                else:
                    fail.append(sym)
            except Exception:
                fail.append(sym)
            if done % 20 == 0 or done == len(tasks):
                print(f'  [{done}/{len(tasks)}] ok={len(out)} fail={len(fail)}')

    out_path = DIR / 'dashboard' / 'candles.json'
    out_path.write_text(json.dumps(out, separators=(',', ':')), encoding='utf-8')
    sz = out_path.stat().st_size
    bar_total = sum(len(b) for b in out.values())
    print(f'[OK] dashboard/candles.json written: {len(out)} symbols, {bar_total} bars total, {sz:,} bytes')
    if fail:
        print(f'[skipped] {len(fail)} symbols (Yahoo lookup failed): {", ".join(fail[:15])}{"..." if len(fail) > 15 else ""}')


if __name__ == '__main__':
    main()
