#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ledger_update.py — rebuild live_ledger per setup from ex-ante trade_ideas history.

Walks git history of trade_ideas.json (one version per trade date, newest commit wins),
simulates each idea with its setup's standard rules on Yahoo 5m bars, and writes the
per-setup live_ledger back into trade_setups.json. Prints kill-criteria status.
Run daily from /SIPs Step 0 (after ingest). Yahoo 5m covers ~60 days; older days are
frozen from the cached ledger file.

Usage: py ledger_update.py            (reads/writes D:\\SIPs\\trade_setups.json)
"""
import json, os, subprocess, time, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')   # DST-aware: fixed -4 shifted every EST bar by 1h
DIR = os.path.dirname(os.path.abspath(__file__))
SETUPS = os.path.join(DIR, 'trade_setups.json')
CACHE = os.path.join(DIR, 'live_ledger_cache.json')     # per-trade results, survives Yahoo window
KNOWN = {('2026-08-07', 'DBX'): ('TARGET', 0.53), ('2026-08-07', 'TXG'): ('TARGET', 1.53)}   # verified day-of

FAMILY = {'beatdip': 'beatdip', 'cap10': 'cap1010', 'squeeze': 'beaten_squeeze_go',
          'contract': 'contract_fade', 'dtc': 'dtc_fade'}


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                          encoding='utf-8', errors='replace', cwd=DIR).stdout


def ideas_history():
    by_date = {}
    for ln in sh('git log --format="%H %cI" -- trade_ideas.json').strip().splitlines():
        h, iso = ln.split()
        try:
            d = json.loads(sh('git show %s:trade_ideas.json' % h))
        except Exception:
            continue
        dt = d.get('date')
        if dt and dt >= '2026-08-07' and dt not in by_date:
            by_date[dt] = {'commit': iso, 'ideas': d.get('ideas') or []}
    return by_date


def bars5m(sym, date):
    t0 = datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=ET)
    p1 = int(t0.replace(hour=4).timestamp()); p2 = int(t0.replace(hour=16, minute=5).timestamp())
    url = ('https://query1.finance.yahoo.com/v8/finance/chart/%s?period1=%d&period2=%d'
           '&interval=5m&includePrePost=false' % (sym, p1, p2))
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as r:
        res = json.load(r)['chart']['result'][0]
    prev = res['meta'].get('chartPreviousClose')
    q = res['indicators']['quote'][0]
    out = []
    for i, t in enumerate(res['timestamp']):
        if q['open'][i] is None:
            continue
        hm = datetime.fromtimestamp(t, ET).strftime('%H:%M')
        if '09:30' <= hm < '16:00':
            out.append((hm, q['open'][i], q['high'][i], q['low'][i], q['close'][i]))
    return prev, out


def family(setup_str):
    s = (setup_str or '').lower()
    for k, v in FAMILY.items():
        if k in s:
            return v
    return None


def sim(fam, prev, bars):
    if not bars or prev is None:
        return None
    o = bars[0][1]; gap = (o / prev - 1) * 100
    i1030 = next((i for i, b in enumerate(bars) if b[0] >= '10:30'), None)
    i1330 = next((i for i, b in enumerate(bars) if b[0] >= '13:30'), len(bars) - 1)
    if fam == 'beatdip':
        if not (-18 <= gap <= -4) or i1030 is None:
            return ('VOID', 0.0)
        low = min(b[3] for b in bars[:i1030]); entry = bars[i1030][1]
        if entry < low * 1.005:
            return ('VOID', 0.0)
        stop = low * 0.995; target = min(prev, entry * 1.06); risk = entry - stop
        if risk <= 0:
            return ('VOID', 0.0)
        for b in bars[i1030:i1330 + 1]:
            if b[3] <= stop: return ('STOP', -1.0)
            if b[2] >= target: return ('TARGET', (target - entry) / risk)
        return ('TIME', (bars[i1330][4] - entry) / risk)
    if fam in ('cap1010', 'beaten_squeeze_go'):
        entry = o; sp = 2.5 if fam == 'cap1010' else 5.0
        stop = entry * (1 - sp / 100); target = entry * 1.10 if fam == 'cap1010' else None
        risk = entry - stop
        for b in bars[:i1330 + 1]:
            if b[3] <= stop: return ('STOP', -1.0)
            if target and b[2] >= target: return ('TARGET', (target - entry) / risk)
        return ('TIME', (bars[i1330][4] - entry) / risk)
    if fam in ('contract_fade', 'dtc_fade'):
        if fam == 'dtc_fade':
            if i1030 is None: return ('VOID', 0.0)
            entry = bars[i1030][1]; start = i1030; stop = entry * 1.05
        else:
            entry = o; start = 0; stop = entry * 1.20
        risk = stop - entry
        for b in bars[start:]:
            if b[2] >= stop: return ('STOP', -1.0)
        return ('TIME', (entry - bars[-1][4]) / risk)
    return None


def main():
    cache = json.load(open(CACHE, encoding='utf-8')) if os.path.exists(CACHE) else {}
    hist = ideas_history()
    for dt, rec in sorted(hist.items()):
        for idea in rec['ideas']:
            sym = idea['symbol']; key = '%s|%s' % (dt, sym)
            if key in cache:
                continue
            fam = family(idea.get('setup'))
            if (dt, sym) in KNOWN:
                res, R = KNOWN[(dt, sym)]
            else:
                try:
                    prev, bars = bars5m(sym, dt); time.sleep(0.3)
                    r = sim(fam, prev, bars)
                except Exception:
                    r = None
                if r is None:
                    continue                     # no data yet (today) — retry next run
                res, R = r
            cache[key] = {'date': dt, 'sym': sym, 'setup': fam, 'res': res, 'R': round(R, 2),
                          'commit': rec['commit'], 'written_at': idea.get('written_at')}
    json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    setups = json.load(open(SETUPS, encoding='utf-8'))
    print('%-18s %3s %5s %7s  %s' % ('setup', 'n', 'win%', 'sumR', 'kill_criteria'))
    for s in setups['setups']:
        rows = [c for c in cache.values() if c['setup'] == s['id'] and c['res'] in ('STOP', 'TARGET', 'TIME')]
        n = len(rows); sumR = round(sum(c['R'] for c in rows), 2)
        win = round(sum(1 for c in rows if c['R'] > 0) / n * 100) if n else 0
        s['live_ledger'] = {'n': n, 'sumR': sumR, 'win_pct': win,
                            'avgR': round(sumR / n, 2) if n else 0.0,
                            'trades': ['%s %s %s %+.2f' % (c['date'], c['sym'], c['res'], c['R']) for c in rows],
                            'updated': datetime.now(ET).strftime('%Y-%m-%d')}
        print('%-18s %3d %4d%% %+7.2f  %s' % (s['id'], n, win, sumR, s.get('live_kill_criteria', '')[:60]))
    tmp = SETUPS + '.tmp'
    json.dump(setups, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.load(open(tmp, encoding='utf-8')); os.replace(tmp, SETUPS)
    print('[ledger] trade_setups.json live_ledger updated; %d trades cached' % len(cache))


if __name__ == '__main__':
    main()
