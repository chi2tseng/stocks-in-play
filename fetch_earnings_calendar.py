#!/usr/bin/env python
"""fetch_earnings_calendar.py — forward-looking earnings calendar for the dashboard.

Pulls NASDAQ's earnings calendar day-by-day for the next 14 CALENDAR days
(America/New_York dates — Taipei midnight runs are still "yesterday" in ET,
same fix as earnings-today-scan.py's _et_today()), keeps only "big" names
(market cap >= $10B OR ticker in bignames-scan.py's UNIVERSE), and writes
a day-bucketed (bmo/amc/unspecified) JSON for a new dashboard page.

Weekends/holidays are NOT special-cased — the API is just queried for every
date in the window and empty/short responses are handled generically; date
logic stays NASDAQ's problem, not ours.

Usage:
    py fetch_earnings_calendar.py                # 14 days starting today (ET)
    py fetch_earnings_calendar.py 2026-07-23      # 14 days starting this date
Override data dir with SIPS_DIR. Writes dashboard/earnings_calendar.json.
Never raises past main(): a dead API day prints [WARN] and is skipped so the
overall /SIPs pipeline (which calls this as a supplement) doesn't break.
"""
import sys, os, re, json, datetime
from concurrent.futures import ThreadPoolExecutor

try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # cp950 console
except Exception: pass

DIR = os.environ.get('SIPS_DIR') or os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(DIR, 'dashboard', 'earnings_calendar.json')
MIN_CAP_B = 10.0  # $10B, in mcap_B units
DAYS_AHEAD = 14
MAX_WORKERS = 8

def _et_today():
    # Same rollover fix as earnings-today-scan.py: date.today() is machine-local
    # (UTC+8 here) and would drift a day ahead of ET mid-session.
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo('America/New_York')).date().isoformat()
    except Exception:
        return datetime.date.today().isoformat()

def _et_now_iso():
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo('America/New_York')).isoformat()
    except Exception:
        return datetime.datetime.utcnow().isoformat() + 'Z'

START = sys.argv[1] if len(sys.argv) > 1 else _et_today()

# Same curated large-cap/famous-name universe as bignames-scan.py — parsed
# textually (not imported) so we don't trigger that script's on-import scan.
def _load_universe():
    path = os.path.join(DIR, 'bignames-scan.py')
    try:
        src = open(path, encoding='utf-8').read()
        m = re.search(r'UNIVERSE = """(.*?)"""', src, re.S)
        return set(m.group(1).split()) if m else set()
    except Exception:
        return set()

UNIVERSE = _load_universe()

def fetch_calendar(date_iso):
    """One day's NASDAQ earnings calendar rows. [] on any failure (logged)."""
    import urllib.request
    url = f'https://api.nasdaq.com/api/calendar/earnings?date={date_iso}'
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json, text/plain, */*'})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.load(r)
        return (d.get('data') or {}).get('rows') or []
    except Exception as e:
        print(f'[WARN] calendar {date_iso}: {e}')
        return []

def parse_cap_b(s):
    """'$1,234,567,890' -> 1.23457 (billions). Empty/unparseable -> 0.0."""
    try:
        return float(str(s).replace('$', '').replace(',', '').strip()) / 1e9
    except Exception:
        return 0.0

TIME_BUCKET = {
    'time-pre-market': 'bmo',
    'time-after-hours': 'amc',
}

def build_day(date_iso):
    rows = fetch_calendar(date_iso)
    buckets = {'bmo': [], 'amc': [], 'unspecified': []}
    seen = set()
    for row in rows:
        sym = (row.get('symbol') or '').strip().upper()
        if not sym or sym in seen:
            continue
        cap_b = parse_cap_b(row.get('marketCap'))
        if cap_b < MIN_CAP_B and sym not in UNIVERSE:
            continue
        seen.add(sym)
        eps = (row.get('epsForecast') or '').strip() or None
        bucket = TIME_BUCKET.get(row.get('time') or '', 'unspecified')
        buckets[bucket].append({
            'symbol': sym,
            'name': row.get('name') or '',
            'mcap_B': round(cap_b, 1),
            'epsForecast': eps,
        })
    for k in buckets:
        buckets[k].sort(key=lambda x: -x['mcap_B'])
    return date_iso, buckets

def main():
    start_date = datetime.date.fromisoformat(START)
    dates = [(start_date + datetime.timedelta(days=i)).isoformat() for i in range(DAYS_AHEAD)]

    results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        for date_iso, buckets in ex.map(build_day, dates):
            results[date_iso] = buckets

    days_out = []
    for date_iso in dates:  # already ascending
        buckets = results.get(date_iso, {'bmo': [], 'amc': [], 'unspecified': []})
        if not (buckets['bmo'] or buckets['amc'] or buckets['unspecified']):
            continue  # no big-cap reporters that day — omit, no empty shell
        d = datetime.date.fromisoformat(date_iso)
        label = f'{d.month}/{d.day} {d.strftime("%a")}'
        days_out.append({'date': date_iso, 'label': label, **buckets})

    out = {'generated': _et_now_iso(), 'days': days_out}
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    total = sum(len(dd['bmo']) + len(dd['amc']) + len(dd['unspecified']) for dd in days_out)
    print(f'[fetch_earnings_calendar] window={dates[0]}..{dates[-1]}  universe={len(UNIVERSE)}  '
          f'days-with-reporters={len(days_out)}/{DAYS_AHEAD}  total-companies={total}')
    for dd in days_out:
        allrows = sorted(dd['bmo'] + dd['amc'] + dd['unspecified'], key=lambda x: -x['mcap_B'])
        top3 = ', '.join(f"{r['symbol']}(${r['mcap_B']:.0f}B)" for r in allrows[:3])
        print(f"  {dd['date']} {dd['label']:9}  bmo={len(dd['bmo']):<2} amc={len(dd['amc']):<2} "
              f"unspecified={len(dd['unspecified']):<2}  top3: {top3}")
    print(f'[OK] wrote {OUT_PATH}')

if __name__ == '__main__':
    main()
