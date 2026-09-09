#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""daily_case.py — one liquid stock per day: ex-ante directional call → post-close truth → cause.

  py daily_case.py pick [DATE]                 rank liquid candidates from that day's packet (ex-ante fields)
  py daily_case.py choose DATE SYM up|down "thesis"   write the day's case (call must be made pre-open)
  py daily_case.py resolve DATE                fill actual OHLC from Yahoo + hit/miss
  py daily_case.py cause DATE "why it moved" ["lesson"]   attribution written after research
  py daily_case.py list                        table of all cases

Liquidity gate: mcap >= $1B, 20d avg $-volume >= $20M, not lottery-flagged, |gap| >= 3%.
Store: D:\\SIPs\\daily_case.json  {"cases":[{date,symbol,direction,thesis,...}]}
"""
import io, json, os, sys, urllib.request
from datetime import datetime, timezone, timedelta

DIR = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.join(DIR, 'daily_case.json')
ET = timezone(timedelta(hours=-4))
TYPE_W = {'earnings': 1.0, 'guidance': 1.0, 'news': 1.0, 'fda': 1.0, 'contract': 0.9, 'm&a': 0.5,
          'analyst': 0.8, 'macro': 0.7, 'policy': 0.7, 'momentum': 0.6}


def load():
    return json.load(open(STORE, encoding='utf-8')) if os.path.exists(STORE) else {'cases': []}


def save(d):
    tmp = STORE + '.tmp'
    io.open(tmp, 'w', encoding='utf-8').write(json.dumps(d, ensure_ascii=False, indent=1))
    json.load(open(tmp, encoding='utf-8')); os.replace(tmp, STORE)


def packet(date):
    return json.load(open(os.path.join(DIR, 'dashboard', 'data', date + '.json'), encoding='utf-8'))


def candidates(date):
    d = packet(date)
    candles = json.load(open(os.path.join(DIR, 'dashboard', 'candles.json'), encoding='utf-8'))
    out = []
    for sym, s in (d.get('stocks') or {}).items():
        mp = s.get('modelPredOpen') or s.get('modelPredPre') or s.get('modelPredScan') or s.get('modelPred') or {}
        gap = mp.get('gap'); pred = mp.get('predDay')
        bars = [b for b in (candles.get(sym) or []) if b.get('date', '') < date][-20:]
        avg_dv = sum(b['volume'] * b['close'] for b in bars) / len(bars) if bars else 0
        mcap = s.get('marketCap_M') or 0
        if gap is None or pred is None or mp.get('lottery') or mcap < 1000 or avg_dv < 20e6 or abs(gap) < 3:
            continue
        typ = (s.get('type') or '').lower()
        score = abs(pred) * TYPE_W.get(typ, 0.6)
        out.append(dict(symbol=sym, mcap_M=round(mcap), avg_dollar_vol_M=round(avg_dv / 1e6, 1), gap=gap,
                        predDay=pred, type=typ, catalyst=(s.get('catalyst') or '')[:80], score=round(score, 1)))
    out.sort(key=lambda r: -r['score'])
    return out


def yahoo_bar(sym, date):
    t0 = datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=ET)
    p1 = int(t0.timestamp()) - 6 * 86400; p2 = int(t0.timestamp()) + 2 * 86400
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}&interval=1d'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as r:
        res = json.load(r)['chart']['result'][0]
    q = res['indicators']['quote'][0]
    bars = [(datetime.fromtimestamp(t, ET).strftime('%Y-%m-%d'), q['open'][i], q['high'][i], q['low'][i], q['close'][i], q['volume'][i])
            for i, t in enumerate(res['timestamp']) if q['close'][i] is not None]
    idx = next((i for i, b in enumerate(bars) if b[0] == date), None)
    if idx is None or idx == 0:
        return None
    d, o, h, l, c, v = bars[idx]; pc = bars[idx - 1][4]
    return dict(prev_close=round(pc, 2), open=round(o, 2), high=round(h, 2), low=round(l, 2), close=round(c, 2), volume=int(v),
                gap_pct=round((o / pc - 1) * 100, 2), day_pct=round((c / pc - 1) * 100, 2),
                intra_pct=round((c / o - 1) * 100, 2), hi_pct=round((h / pc - 1) * 100, 2), lo_pct=round((l / pc - 1) * 100, 2))


def main():
    a = sys.argv[1:]
    if not a or a[0] == 'list':
        d = load()
        print('%-11s %-6s %-4s %8s %8s  %-6s %s' % ('date', 'sym', 'dir', 'day%', 'intra%', 'result', 'cause'))
        for c in d['cases']:
            act = c.get('actual') or {}
            print('%-11s %-6s %-4s %8s %8s  %-6s %s' % (c['date'], c['symbol'], c['direction'],
                  act.get('day_pct', '-'), act.get('intra_pct', '-'), c.get('result', '-'), (c.get('cause') or '')[:60]))
        return
    cmd = a[0]
    if cmd == 'pick':
        date = a[1] if len(a) > 1 else datetime.now(ET).strftime('%Y-%m-%d')
        rows = candidates(date)
        print(f'{date}: {len(rows)} liquid candidates (mcap>=1B, $vol>=20M, non-lottery, |gap|>=3)')
        for r in rows[:6]:
            print('  %-6s mcap %6dM $vol %6.1fM gap %+6.1f predDay %+6.1f %-9s score %5.1f | %s' % (
                r['symbol'], r['mcap_M'], r['avg_dollar_vol_M'], r['gap'], r['predDay'], r['type'], r['score'], r['catalyst']))
        return
    if cmd == 'choose':
        date, sym, direction, thesis = a[1], a[2].upper(), a[3].lower(), a[4]
        assert direction in ('up', 'down')
        d = load(); d['cases'] = [c for c in d['cases'] if c['date'] != date]
        cand = next((r for r in candidates(date) if r['symbol'] == sym), None)
        d['cases'].append(dict(date=date, symbol=sym, direction=direction, thesis=thesis,
                               premarket=cand, written_at=datetime.now(ET).isoformat(timespec='minutes')))
        d['cases'].sort(key=lambda c: c['date']); save(d)
        print(f'[case] {date} {sym} {direction} written (ex-ante at {d["cases"][-1]["written_at"]})')
        return
    if cmd == 'resolve':
        date = a[1]; d = load()
        c = next((c for c in d['cases'] if c['date'] == date), None)
        if not c: print('no case for', date); return
        act = yahoo_bar(c['symbol'], date)
        if not act: print('no bar yet for', date); return
        c['actual'] = act
        want = 1 if c['direction'] == 'up' else -1
        c['result'] = 'HIT' if act['day_pct'] * want > 0 else 'MISS'
        c['intraday_result'] = 'HIT' if act['intra_pct'] * want > 0 else 'MISS'   # open→close, the tradeable part
        save(d)
        print(f'[case] {date} {c["symbol"]} {c["direction"]}: day {act["day_pct"]:+.1f}% (gap {act["gap_pct"]:+.1f}, intra {act["intra_pct"]:+.1f}, hi {act["hi_pct"]:+.1f}, lo {act["lo_pct"]:+.1f}) -> {c["result"]} / intraday {c["intraday_result"]}')
        return
    if cmd == 'cause':
        date, cause = a[1], a[2]; lesson = a[3] if len(a) > 3 else ''
        d = load(); c = next((c for c in d['cases'] if c['date'] == date), None)
        if not c: print('no case for', date); return
        c['cause'] = cause; c['lesson'] = lesson; c['analyzed_at'] = datetime.now(ET).isoformat(timespec='minutes')
        save(d); print(f'[case] {date} {c["symbol"]} cause recorded')
        return
    print(__doc__)


if __name__ == '__main__':
    main()
