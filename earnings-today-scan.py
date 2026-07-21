#!/usr/bin/env python
"""earnings-today-scan.py — deterministic earnings-calendar gate for /SIPs §2.0d.

WHY THIS EXISTS (2026-07-16 ABT miss): every other net (barchart >=4% gap,
bignames-scan >=2% snapshot, pre-scan agent judgment) depends on a PRICE
SNAPSHOT, which is a moving target on earnings morning. ABT reported Q2 at
~7am ET, was +3.15% pre-market at scan time (cut by the 4% filter), invisible
to bignames-scan's daily-close math, and rallied to +12% during the run.
"Who reports today" is knowable from the CALENDAR before the market opens —
this script makes that a hard, deterministic input.

What it does:
  1. Pulls NASDAQ's earnings calendar for TODAY (BMO + AMC) and YESTERDAY
     (AMC only — after-hours reporters belong to this morning's scan).
  2. Keeps large/famous names: market cap >= $10B, or in the bignames UNIVERSE.
  3. Prints every such reporter NOT already in candidates.csv, with a live
     pre/post-aware quote — REGARDLESS of %move (big-cap earnings are news
     per SKILL.md §2.0b; % is irrelevant).

Usage:
    py earnings-today-scan.py               # today
    py earnings-today-scan.py 2026-07-16    # explicit date
Exit: prints '[earnings-today] MISSING=N'; N>0 means the run MUST add them.
"""
import sys, os, json, urllib.request, datetime

try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # cp950 console vs headlines
except Exception: pass

DIR = os.environ.get('SIPS_DIR') or os.path.dirname(os.path.abspath(__file__))

def _et_today():
    # 2026-07-20 23:xx Taipei is still 2026-07-20 in New York. date.today() is the
    # MACHINE's date (UTC+8 here), so after ~12:00 ET it rolls over and the run
    # would pull TOMORROW's earnings calendar mid-session. Trading day = ET day.
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo('America/New_York')).date().isoformat()
    except Exception:
        return datetime.date.today().isoformat()

TODAY = sys.argv[1] if len(sys.argv) > 1 else _et_today()
MIN_CAP = 10e9  # $10B

# same famous-name universe as bignames-scan.py (kept in sync manually; a name
# in EITHER net is enough)
sys.path.insert(0, DIR)
from prepost_quote import prepost_quote
from headline import top_headline
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location('bn', os.path.join(DIR, 'bignames-scan.py'))
    # don't exec — bignames-scan runs its scan on import. Parse UNIVERSE textually.
    UNIVERSE = set()
    src = open(os.path.join(DIR, 'bignames-scan.py'), encoding='utf-8').read()
    import re
    m = re.search(r'UNIVERSE = """(.*?)"""', src, re.S)
    if m: UNIVERSE = set(m.group(1).split())
except Exception:
    UNIVERSE = set()

def get(url):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json, text/plain, */*'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

def calendar(date_iso):
    try:
        d = get(f'https://api.nasdaq.com/api/calendar/earnings?date={date_iso}')
        return (d.get('data') or {}).get('rows') or []
    except Exception as e:
        print(f'[warn] calendar {date_iso}: {e}')
        return []

def parse_cap(s):
    try:
        return float(str(s).replace('$', '').replace(',', ''))
    except Exception:
        return 0.0

def quote_prepost(sym):
    """Last trade INCLUDING pre/post-market vs previous close.

    2026-07-20: the % here used to be the PREVIOUS day's move (range=1d returns
    the last trading day's bars pre-market, and chartPreviousClose is the day
    before that). Shared helper now does the session-date math."""
    q = prepost_quote(sym)
    return (q[1], q[0], q[2]) if q else (None, None, None)

# --- gather reporters: today BMO+AMC, yesterday AMC ---
yday = (datetime.date.fromisoformat(TODAY) - datetime.timedelta(days=1)).isoformat()
reporters = {}   # sym -> (when, name, cap)
for row in calendar(TODAY):
    sym = (row.get('symbol') or '').strip().upper()
    if not sym: continue
    reporters[sym] = (f"today-{(row.get('time') or '').replace('time-','')}",
                      row.get('name') or '', parse_cap(row.get('marketCap')))
for row in calendar(yday):
    if (row.get('time') or '') != 'time-after-hours': continue
    sym = (row.get('symbol') or '').strip().upper()
    if sym and sym not in reporters:
        reporters[sym] = ('yday-after-hours', row.get('name') or '', parse_cap(row.get('marketCap')))

big = {s: v for s, v in reporters.items() if v[2] >= MIN_CAP or s in UNIVERSE}

have = set()
cpath = os.path.join(DIR, 'candidates.csv')
if os.path.exists(cpath):
    for line in open(cpath, encoding='utf-8-sig').read().splitlines()[1:]:
        if line.strip(): have.add(line.split(',')[0])

missing = sorted([s for s in big if s not in have], key=lambda s: -big[s][2])
print(f'[earnings-today] date={TODAY} calendar={len(reporters)} bigcap/famous={len(big)} already-in={len(big)-len(missing)} MISSING={len(missing)}')
print('--- reporters NOT in candidates.csv (add as Session=headline, Type=earnings) ---')
for s in missing:
    when, name, cap = big[s]
    last, chg, vol = quote_prepost(s)
    capb = f'${cap/1e9:.0f}B' if cap else '?'
    chgs = f'{chg:+.2f}%' if chg is not None else 'no-pre'
    print(f'  {s:6} {chgs:>8}  ${last or "?":<9} {capb:>7}  {when:22} {name[:34]}')
    # headline column, default ON (2026-07-20) — the earnings story travels with the row
    h = top_headline(s)
    if h:
        print(f'         ↳ [{h["published"]} {h["publisher"]}] {h["title"]}')
        print(f'           {h["url"]}')
    else:
        print('         ↳ NO HEADLINE FOUND (<36h) — pull the press release from IR/SEC')
if not missing:
    print('  (none — every big-cap reporter is already in the scan)')
