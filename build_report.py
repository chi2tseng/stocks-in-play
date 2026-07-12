"""Combine Barchart candidates + catalyst data + TradingView data and produce final report."""
import os, re, json, csv

DIR = os.environ.get('SIPS_DIR') or os.path.dirname(os.path.abspath(__file__))

# --- Load Barchart candidates from CSV ---
candidates = []
with open(os.path.join(DIR, 'candidates.csv'), 'r', encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        try:
            candidates.append({
                'Symbol': r['Symbol'],
                'Last': float(r['Last']),
                'ChgPct': float(r['ChgPct']),
                'Volume': int(r['Volume']),
                'Session': r['Session'],
                'Direction': r['Direction'],
                'Name': r['Name'],
            })
        except (ValueError, TypeError) as e:
            print('[WARN] skipping bad candidates.csv row', r.get('Symbol'), e)
            continue

# --- Load TV summary ---
with open(os.path.join(DIR, 'tv-summary.json'), 'r', encoding='utf-8') as f:
    tv_data = json.load(f)
tv_by_ticker = {t['Ticker']: t for t in tv_data}

# --- Catalyst data: today's file only. The old hand-entered dict (a frozen
# 2026-05-14 snapshot) was removed — it silently backfilled two-month-old text
# for any ticker missing from catalysts_today.json. Missing tickers now get an
# empty string + a [WARN] so stale data can't leak in.

# Today's catalysts — read catalysts_today.json if present (created fresh each /SIPs run).
# Schema: { "<TICKER>": { "Type": "earnings|...", "Catalyst": "繁中一句" }, ... }
# Tickers not in today's file get an empty catalyst (+ a [WARN]) — no stale backfill.
today_path = os.path.join(DIR, 'catalysts_today.json')
catalysts_today = {}
if os.path.exists(today_path):
    with open(today_path, 'r', encoding='utf-8') as f:
        catalysts_today = json.load(f)

# Merge data
for c in candidates:
    sym = c['Symbol']
    cat = catalysts_today.get(sym)
    if not cat:
        print('[WARN] no catalyst for', sym)
        cat = {'Type': '?', 'Catalyst': ''}
    c['Type'] = cat['Type']
    c['Catalyst'] = cat['Catalyst']
    tv = tv_by_ticker.get(sym)
    c['HasTV'] = tv is not None
    c['TV'] = tv

# Save consolidated CSV
csv_path = os.path.join(DIR, 'final-candidates.csv')
with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Symbol','Last','ChgPct','Volume','Session','Direction','Type','Name','Catalyst',
                'TV_LatestEPS','TV_PriorYrEPS','TV_LatestRev_M','TV_PriorYrRev_M','TV_YoYBlock'])
    for c in candidates:
        tv = c.get('TV') or {}
        w.writerow([c['Symbol'],c['Last'],c['ChgPct'],c['Volume'],c['Session'],c['Direction'],
                    c['Type'],c['Name'],c['Catalyst'],
                    tv.get('LatestEPS',''),tv.get('PriorYrEPS',''),tv.get('LatestRev_M',''),
                    tv.get('PriorYrRev_M',''),tv.get('YoYBlock','').replace('\n',' | ')])
print(f"Saved {csv_path}")
print(f"Total candidates: {len(candidates)}")
print(f"With TV data: {sum(1 for c in candidates if c['HasTV'])}")
print(f"Catalyst types:")
from collections import Counter
for t, n in Counter(c['Type'] for c in candidates).most_common():
    print(f"  {t}: {n}")
