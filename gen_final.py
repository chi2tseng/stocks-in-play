# -*- coding: utf-8 -*-
"""Generate final-candidates.csv from candidates.csv + catalysts_today.json + tv-summary.json."""
import csv, json, io, os
DIR = os.path.dirname(os.path.abspath(__file__))

with io.open(os.path.join(DIR,'catalysts_today.json'), encoding='utf-8') as f:
    cats = json.load(f)
with io.open(os.path.join(DIR,'tv-summary.json'), encoding='utf-8') as f:
    tv = {t['Ticker']: t for t in json.load(f)}

# Read candidates, dedupe per symbol keeping largest |chg|, track sessions
rows = {}
with io.open(os.path.join(DIR,'candidates.csv'), encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        sym = r['Symbol']
        chg = float(r['ChgPct'])
        cur = rows.get(sym)
        if cur is None or abs(chg) > abs(float(cur['ChgPct'])):
            rows[sym] = dict(r)
        # track multi-session
        rows[sym].setdefault('_sessions', set())
    # second pass for sessions
with io.open(os.path.join(DIR,'candidates.csv'), encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        rows[r['Symbol']]['_sessions'].add(r['Session'])

out = []
for sym, r in rows.items():
    sess = '+'.join(sorted(r['_sessions'])) if len(r['_sessions'])>1 else r['Session']
    c = cats.get(sym, {})
    t = tv.get(sym, {})
    out.append({
        'Symbol': sym,
        'Last': r['Last'],
        'ChgPct': r['ChgPct'],
        'Volume': r['Volume'],
        'Session': sess,
        'Direction': r['Direction'],
        'Type': c.get('Type','momentum'),
        'Name': r['Name'],
        'Catalyst': c.get('Catalyst',''),
        'TV_LatestEPS': t.get('LatestEPS',''),
        'TV_PriorYrEPS': t.get('PriorYrEPS',''),
        'TV_LatestRev_M': t.get('LatestRev_M',''),
        'TV_PriorYrRev_M': t.get('PriorYrRev_M',''),
        'TV_YoYBlock': t.get('YoYBlock',''),
    })

# sort by abs chg desc
out.sort(key=lambda x: -abs(float(x['ChgPct'])))
cols = ['Symbol','Last','ChgPct','Volume','Session','Direction','Type','Name','Catalyst',
        'TV_LatestEPS','TV_PriorYrEPS','TV_LatestRev_M','TV_PriorYrRev_M','TV_YoYBlock']
with io.open(os.path.join(DIR,'final-candidates.csv'),'w',encoding='utf-8-sig',newline='') as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    for r in out:
        w.writerow(r)
print(f'wrote {len(out)} rows to final-candidates.csv')
