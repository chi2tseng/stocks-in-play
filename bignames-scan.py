#!/usr/bin/env python
"""bignames-scan.py — daily large-cap (>~$10B) mover sweep for /SIPs §2.0c.

Barchart's gap scan only lists pre/post-market movers >=4%. Well-known big
companies that move >=2% in regular hours (or sit just under 4%) get missed.
This scans a curated large-cap universe for today's |%chg| >= THRESHOLD and prints
the ones NOT already in candidates.csv, so the /SIPs pipeline can hunt catalysts
and append them as Session=headline rows.

Usage:
    py bignames-scan.py            # threshold 2.0, today
    py bignames-scan.py 3          # threshold 3.0
Override data dir with SIPS_DIR. No args needed in the daily run.
"""
import sys, os, json, urllib.request

THRESHOLD = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
DIR = os.environ.get('SIPS_DIR') or os.path.dirname(os.path.abspath(__file__))

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
    try:
        u = f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d'
        r = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'}), timeout=12))['chart']['result'][0]
        q = r['indicators']['quote'][0]
        cl = [c for c in q['close'] if c is not None]
        if len(cl) >= 2:
            return round((cl[-1] - cl[-2]) / cl[-2] * 100, 2), round(cl[-1], 2)
        m = r.get('meta', {}); p = m.get('regularMarketPrice'); pc = m.get('chartPreviousClose')
        if p and pc: return round((p - pc) / pc * 100, 2), round(p, 2)
    except Exception:
        pass
    return None

# existing symbols already in today's candidate set
have = set()
cpath = os.path.join(DIR, 'candidates.csv')
if os.path.exists(cpath):
    for line in open(cpath, encoding='utf-8-sig').read().splitlines()[1:]:
        if line.strip():
            have.add(line.split(',')[0])

seen = set(); hits = []
for sym in UNIVERSE:
    if sym in seen: continue
    seen.add(sym)
    r = chg_today(sym)
    if r and abs(r[0]) >= THRESHOLD:
        hits.append((sym, r[0], r[1], sym in have))

hits.sort(key=lambda x: -abs(x[1]))
missing = [h for h in hits if not h[3]]
print(f'[bignames-scan] universe={len(seen)}  threshold=|chg|>={THRESHOLD}%  movers={len(hits)}  already-in={len(hits)-len(missing)}  MISSING={len(missing)}')
print('--- MISSING large-caps to add (Session=headline) ---')
for sym, chg, last, _ in missing:
    print(f'  {sym:6} {chg:+6.2f}%  ${last}')
if not missing:
    print('  (none — all large-cap movers already in the scan)')
