#!/usr/bin/env python
"""bignames-scan.py — daily large-cap (>~$10B) mover sweep for /SIPs §2.0c.

Barchart's gap scan only lists pre/post-market movers >=4%. Well-known big
companies that move >=2% in regular hours (or sit just under 4%) get missed.
This scans a curated large-cap universe for today's |%chg| >= THRESHOLD and prints
the ones NOT already in candidates.csv, so the /SIPs pipeline can hunt catalysts
and append them as Session=headline rows.

Every mover row carries TODAY'S TOP HEADLINE + URL (2026-07-20: GOOG printed at
+2.86% with no news attached and the run shipped without a catalyst for it).
Headlines are ON BY DEFAULT — `--no-news` only exists for offline debugging.

Usage:
    py bignames-scan.py            # threshold 2.0, today, headlines on
    py bignames-scan.py 3          # threshold 3.0
    py bignames-scan.py --no-news  # skip the news fetch (debug only)
Override data dir with SIPS_DIR. No args needed in the daily run.
Also writes scan_headlines.json (sym -> {chg,last,title,url,publisher}).
"""
import sys, os, json

try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # cp950 console vs headlines
except Exception: pass

try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # cp950 console vs headlines
except Exception: pass

args = [a for a in sys.argv[1:] if not a.startswith('-')]
NEWS = '--no-news' not in sys.argv
THRESHOLD = float(args[0]) if args else 2.0
DIR = os.environ.get('SIPS_DIR') or os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DIR)
from prepost_quote import prepost_quote
from headline import top_headline

# Curated large-cap / well-known universe (market cap roughly >=$10B). Extend as
# needed — the point is "famous big companies", not an exhaustive index.
UNIVERSE = """
AAPL MSFT NVDA GOOGL GOOG AMZN META AVGO TSLA ORCL CRM ADBE AMD INTC QCOM TXN CSCO NOW AMAT LRCX KLAC MU ARM PLTR SNOW PANW CRWD ANET DELL SMCI MRVL IBM UBER ABNB
JPM BAC WFC C GS MS BLK BK STT SCHW AXP V MA COF USB PNC TFC MTB BX KKR APO SPGI CB PGR TRV AIG MET PRU ICE CME
UNH JNJ LLY ABBV MRK PFE TMO ABT DHR BMY AMGN GILD CVS ELV CI HUM ISRG MDT SYK VRTX REGN BSX BDX ZTS
WMT COST PG KO PEP MCD NKE SBUX HD LOW TGT DIS NFLX CMCSA PM MO GIS KHC MDLZ CL EL
XOM CVX COP BA CAT GE HON UNP UPS RTX LMT DE EMR GEV SLB EOG PSX MPC NOC GD
T VZ TMUS
BABA PDD JD BIDU NIO LI XPEV TSM SE SHOP SAP TM SONY NVO ASML AZN NVS HSBC TTE BP SHEL RIO BHP
HCA CI MCK COR
""".split()

def chg_today(sym):
    # Pre/post-aware (2026-07-16 ABT lesson): daily closes are blind to pre-market.
    # 2026-07-20 fix: the old range=1d call silently returned the PREVIOUS trading
    # day's bars pre-market, so Monday 8am reported Friday-vs-Thursday. See
    # prepost_quote.py. No bars today -> None (skipped, never guessed).
    q = prepost_quote(sym)
    return (q[0], q[1]) if q else None

# existing symbols already in today's candidate set
have = set()
cpath = os.path.join(DIR, 'candidates.csv')
if os.path.exists(cpath):
    for line in open(cpath, encoding='utf-8-sig').read().splitlines()[1:]:
        if line.strip():
            have.add(line.split(',')[0])

seen = set(); hits = []; nodata = []
for sym in UNIVERSE:
    if sym in seen: continue
    seen.add(sym)
    r = chg_today(sym)
    if r is None:
        nodata.append(sym)          # no-premarket-data: hasn't traded today yet
    elif abs(r[0]) >= THRESHOLD:
        hits.append((sym, r[0], r[1], sym in have))

hits.sort(key=lambda x: -abs(x[1]))
missing = [h for h in hits if not h[3]]

# headline column — default ON. A mover with no "why" attached is a lead nobody
# chases (2026-07-20 GOOG). Threaded: 8 workers keeps this under ~5s.
news = {}
if NEWS and hits:
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as ex:
        news = {s: h for s, h in zip([h[0] for h in hits],
                                     ex.map(top_headline, [h[0] for h in hits]))}

def show(sym, chg, last):
    print(f'  {sym:6} {chg:+6.2f}%  ${last}')
    h = news.get(sym)
    if h:
        print(f'         ↳ [{h["published"]} {h["publisher"]}] {h["title"]}')
        print(f'           {h["url"]}')
    elif NEWS:
        print(f'         ↳ NO HEADLINE FOUND (<36h) — hunt a catalyst manually before adding')

print(f'[bignames-scan] universe={len(seen)}  threshold=|chg|>={THRESHOLD}%  movers={len(hits)}  already-in={len(hits)-len(missing)}  MISSING={len(missing)}  no-premarket-data={len(nodata)}  news={"on" if NEWS else "OFF"}')
print('--- MISSING large-caps to add (Session=headline) ---')
for sym, chg, last, _ in missing:
    show(sym, chg, last)
if not missing:
    print('  (none — all large-cap movers already in the scan)')
already = [h for h in hits if h[3]]
if already:
    print('--- already in candidates.csv (headline for cross-check) ---')
    for sym, chg, last, _ in already:
        show(sym, chg, last)
if nodata:
    print(f'--- no-premarket-data (untraded today, %chg unknown) ---\n  {" ".join(nodata)}')

if NEWS:
    out = {s: dict(chg=c, last=l, in_csv=inc, **(news.get(s) or {}))
           for s, c, l, inc in hits}
    with open(os.path.join(DIR, 'scan_headlines.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'[bignames-scan] wrote scan_headlines.json ({len(out)} movers)')
