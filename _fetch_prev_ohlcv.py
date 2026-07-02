# -*- coding: utf-8 -*-
import json, os, io, csv, urllib.request
from datetime import datetime, timedelta, timezone

DIR = os.path.dirname(os.path.abspath(__file__))
# Target trading day = July 1 (Wed) — the gap session is 7/1 pre + 7/1 post.
yesterday_iso = '2026-07-01'
today_iso = '2026-07-02'

todays = []
with io.open(os.path.join(DIR, 'candidates.csv'), encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        s = (row.get('Symbol') or '').strip()
        if s: todays.append(s)
todays = sorted(set(todays))

studies = []
sp = os.path.join(DIR, 'dashboard', 'studies', 'studies.json')
if os.path.exists(sp):
    with io.open(sp, encoding='utf-8') as f: studies = json.load(f)

work = [(t, yesterday_iso) for t in todays]
for s in studies:
    if (s.get('ohlcv') or {}).get('open') is not None: continue
    sdate = (s.get('ohlcv') or {}).get('date') or yesterday_iso
    if sdate > today_iso: continue
    work.append((s['symbol'], sdate))
work = list({(sym, dt) for sym, dt in work})

def fetch_bar_at(sym, target_iso):
    t = datetime.strptime(target_iso, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    p1 = int(t.timestamp()) - 12*86400
    p2 = int(t.timestamp()) + 3*86400
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}&interval=1d'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as r: d = json.load(r)
    res = d['chart']['result'][0]
    ts = res['timestamp']; q = res['indicators']['quote'][0]
    bars = []
    for i, t_ in enumerate(ts):
        if q['open'][i] is None or q['close'][i] is None: continue
        bars.append({
            'date': datetime.fromtimestamp(t_, tz=timezone.utc).strftime('%Y-%m-%d'),
            'open': round(q['open'][i], 2), 'high': round(q['high'][i], 2),
            'low': round(q['low'][i], 2), 'close': round(q['close'][i], 2),
            'volume': int(q['volume'][i]) if q['volume'][i] is not None else None,
        })
    if not bars: return None
    matched = next((b for b in bars if b['date'] == target_iso), None)
    if matched is None:
        priors = [b for b in bars if b['date'] <= target_iso]
        if not priors: return None
        matched = priors[-1]
    idx = bars.index(matched)
    prev_close = bars[idx-1]['close'] if idx > 0 else None
    return {**matched, 'prev_close': prev_close}

out = {}
ok = fail = 0
for sym, target_iso in work:
    try:
        bar = fetch_bar_at(sym, target_iso)
        if bar: out[sym] = bar; ok += 1
        else: fail += 1
    except Exception as e:
        fail += 1
        print(f'[warn] {sym} @ {target_iso}: {e}')

with io.open(os.path.join(DIR, 'prev_ohlcv.json'), 'w', encoding='utf-8') as f:
    json.dump(out, f, indent=2)
print(f'[OK] prev_ohlcv.json: {len(out)} symbols (ok={ok} fail={fail})')
