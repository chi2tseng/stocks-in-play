import csv, io, json

DATE = '2026-07-29'

# (sym, chgPct, last, name)  -- all already-published today; Session=headline
EXTRA = [
    ('CAT',  -4.26, 805.00, 'Caterpillar Inc'),
    ('AMAT', -2.10, 466.45, 'Applied Materials'),
    ('LI',    4.43,  13.79, 'Li Auto Inc ADR'),
    ('RIO',   2.07,  93.54, 'Rio Tinto plc ADR'),
    ('DB',    2.10,  35.00, 'Deutsche Bank AG'),
    ('TM',    4.26, 194.23, 'Toyota Motor Corp ADR'),
    ('V',    -2.06, 359.03, 'Visa Inc'),
    ('EMR',  -3.39, 146.66, 'Emerson Electric Co'),
    ('BP',    3.20,  43.00, 'BP plc ADR'),
]

pub = json.load(open('_et_pub.json'))
rows = list(csv.DictReader(io.open('candidates.csv', encoding='utf-8-sig')))
have = {r['Symbol'] for r in rows}
FIELDS = ['Symbol', 'Last', 'ChgPct', 'Volume', 'Session', 'SessionDate', 'Direction', 'Name']

added = []
for r in pub:
    s = r['sym']
    if s in have or s == 'WSO.B':
        continue
    if not r['chg'].endswith('%'):
        continue
    chg = float(r['chg'].rstrip('%'))
    rows.append(dict(Symbol=s, Last=r['last'], ChgPct='%.2f' % chg, Volume='0',
                     Session='headline', SessionDate=DATE,
                     Direction='up' if chg >= 0 else 'down', Name=r['name']))
    have.add(s); added.append(s)

for s, chg, last, name in EXTRA:
    if s in have:
        continue
    rows.append(dict(Symbol=s, Last='%.2f' % last, ChgPct='%.2f' % chg, Volume='0',
                     Session='headline', SessionDate=DATE,
                     Direction='up' if chg >= 0 else 'down', Name=name))
    have.add(s); added.append(s)

f = io.open('candidates.csv', 'w', encoding='utf-8-sig', newline='')
w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows); f.close()
print('added %d  total_rows=%d  unique=%d' % (len(added), len(rows), len(have)))
print(' '.join(added))
