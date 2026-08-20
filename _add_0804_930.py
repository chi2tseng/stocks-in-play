"""Append headline rows to candidates.csv for 2026-08-04 9:30 ET refresh.
Fetches live quote (last / %chg vs prev close / volume) from Yahoo per symbol.
Usage: py _add_0804_930.py SYM1 SYM2 ...
"""
import csv, io, json, sys, urllib.request, concurrent.futures

DATE = '2026-08-04'
FIELDS = ['Symbol', 'Last', 'ChgPct', 'Volume', 'Session', 'SessionDate', 'Direction', 'Name']


def quote(sym):
    url = ('https://query1.finance.yahoo.com/v8/finance/chart/%s'
           '?range=2d&interval=1d&includePrePost=true' % sym)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.load(r)
    res = d['chart']['result'][0]
    m = res['meta']
    last = m.get('regularMarketPrice') or m.get('previousClose')
    prev = m.get('chartPreviousClose') or m.get('previousClose')
    vol = m.get('regularMarketVolume') or 0
    name = m.get('shortName') or m.get('longName') or sym
    chg = (last / prev - 1) * 100 if (last and prev) else 0.0
    return dict(Symbol=sym, Last='%.2f' % last, ChgPct='%.2f' % chg,
                Volume=str(int(vol)), Session='headline', SessionDate=DATE,
                Direction='up' if chg >= 0 else 'down', Name=name)


def main(syms):
    rows = list(csv.DictReader(io.open('candidates.csv', encoding='utf-8-sig')))
    have = {r['Symbol'] for r in rows}
    todo = [s for s in syms if s not in have]
    added = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for sym, fut in [(s, ex.submit(quote, s)) for s in todo]:
            try:
                rows.append(fut.result())
                added.append(sym)
            except Exception as e:
                print('[warn] %s: %s' % (sym, e))
    with io.open('candidates.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in FIELDS})
    print('added %d: %s' % (len(added), ','.join(added)))
    print('skipped (already present): %s' % ','.join(s for s in syms if s in have))
    print('total rows: %d' % len(rows))


if __name__ == '__main__':
    main([s.upper() for s in sys.argv[1:]])
