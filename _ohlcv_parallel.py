# -*- coding: utf-8 -*-
import json, os, io, csv, urllib.request
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

DIR = os.path.dirname(os.path.abspath(__file__))
TARGET = '2026-06-30'   # last completed trading day (7/1 pre + 6/30 post gaps)
TODAY  = '2026-07-01'

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

work = [(t, TARGET) for t in todays]
for s in studies:
    if (s.get('ohlcv') or {}).get('open') is not None: continue
    sdate = (s.get('ohlcv') or {}).get('date') or TARGET
    if sdate > TODAY: continue
    work.append((s['symbol'], sdate))
work = list({(sym, dt) for sym, dt in work})

def fetch_bar_at(sym, target_iso):
    t = datetime.strptime(target_iso, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    p1 = int(t.timestamp()) - 12*86400
    p2 = int(t.timestamp()) + 3*86400
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}&interval=1d'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=12) as r: d = json.load(r)
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

def task(pair):
    sym, dt = pair
    try:
        return sym, fetch_bar_at(sym, dt)
    except Exception as e:
        return sym, None

out = {}
with ThreadPoolExecutor(max_workers=8) as ex:
    for sym, bar in ex.map(task, work):
        if bar: out[sym] = bar

with io.open(os.path.join(DIR, 'prev_ohlcv.json'), 'w', encoding='utf-8') as f:
    json.dump(out, f, indent=2)
print(f'[OK] prev_ohlcv.json: {len(out)}/{len(work)} symbols, target {TARGET}')

# Backfill blank studies + sync snapshot
changed = False
for s in studies:
    if (s.get('ohlcv') or {}).get('open') is not None: continue
    row = out.get(s['symbol'])
    if not row: continue
    s['ohlcv'] = {**(s.get('ohlcv') or {}), **row}
    s.setdefault('snapshot', {})['last'] = row['close']
    changed = True
if changed:
    with io.open(sp, 'w', encoding='utf-8') as f:
        json.dump(studies, f, ensure_ascii=False, indent=2)
    print('[OK] studies backfilled')
else:
    print('[OK] no blank studies to backfill')
