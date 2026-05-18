#!/usr/bin/env python
"""fetch_candles.py — pull last ~6 months daily OHLCV from Yahoo Finance for
every ticker that appears in:
  - today's dashboard/data/<DATE>.json (the scan candidates)
  - claude_picks.json / codex_picks.json / gemini_picks.json (curated picks)
  - dashboard/studies/studies.json (saved studies)

Writes to dashboard/candles.json (served as a static asset, fetched once by
the dashboard at app init). Run after /SIPs Phase 8 but before
build_dashboard.py so the dashboard knows where to look.

Schema: { "SYM": [ {date, open, high, low, close, volume}, ... ], ... }
Last ~130 trading days per symbol (~6 calendar months).
"""

import json, os, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

DIR = Path(__file__).resolve().parent
TODAY = datetime.now(timezone.utc).strftime('%Y-%m-%d')


def collect_symbols():
    """Union of tickers across all current data sources."""
    syms = set()
    # 1. Today's scan candidates.
    today_data = DIR / 'dashboard' / 'data' / f'{TODAY}.json'
    if today_data.exists():
        try:
            d = json.loads(today_data.read_text(encoding='utf-8'))
            syms.update((d.get('stocks') or {}).keys())
        except Exception:
            pass
    # 2. Picks files (all three agents).
    for f in ['claude_picks.json', 'codex_picks.json', 'gemini_picks.json']:
        p = DIR / f
        if p.exists():
            try:
                pj = json.loads(p.read_text(encoding='utf-8'))
                for pk in pj.get('picks', []):
                    s = pk.get('symbol')
                    if s:
                        syms.add(s.upper())
            except Exception:
                pass
    # 3. Studies — so stock-detail pages opened from My Studies also have chart.
    studies = DIR / 'dashboard' / 'studies' / 'studies.json'
    if studies.exists():
        try:
            arr = json.loads(studies.read_text(encoding='utf-8'))
            for st in arr:
                s = st.get('symbol')
                if s:
                    syms.add(s.upper())
        except Exception:
            pass
    return sorted(syms)


def fetch_one(sym):
    """Yahoo Finance daily chart for last ~200 days. Returns list of bars or None."""
    end = int(time.time())
    start = end - 200 * 86400
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={start}&period2={end}&interval=1d'
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
        # Cap at last 130 trading days (~6 calendar months).
        return bars[-130:] if len(bars) > 130 else bars
    except Exception:
        return None


def main():
    syms = collect_symbols()
    print(f'[fetch_candles] {len(syms)} symbols to fetch')
    if not syms:
        print('[skip] no symbols found in scan / picks / studies')
        return

    out = {}
    fail = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch_one, s): s for s in syms}
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
            if done % 20 == 0 or done == len(syms):
                print(f'  [{done}/{len(syms)}] ok={len(out)} fail={len(fail)}')

    # Write to dashboard/candles.json so the dashboard can fetch it directly.
    out_path = DIR / 'dashboard' / 'candles.json'
    out_path.write_text(json.dumps(out, separators=(',', ':')), encoding='utf-8')
    sz = out_path.stat().st_size
    print(f'[OK] dashboard/candles.json written: {len(out)} symbols, {sz:,} bytes')
    if fail:
        print(f'[skipped] {len(fail)} symbols (Yahoo lookup failed): {", ".join(fail[:15])}{"..." if len(fail) > 15 else ""}')


if __name__ == '__main__':
    main()
