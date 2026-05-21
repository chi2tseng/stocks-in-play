"""fetch_earnings_dates.py — fallback earnings-date fetcher.

For any ticker in `tv-summary.json` where `LatestReportDate` is None (because
TV's earnings page showed "Next report date" instead of "Latest report date"
— common for tickers with upcoming reports), query NASDAQ's
earnings-surprise endpoint for the most recent `dateReported`.

Run AFTER parse_tv.py and BEFORE build_dashboard.py.

  py parse_tv.py
  py fetch_earnings_dates.py     ← this script
  py build_dashboard.py
"""
import json, urllib.request
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

DIR = Path(__file__).resolve().parent
TV_PATH = DIR / 'tv-summary.json'

def fetch_one(sym):
    """Hit NASDAQ's earnings-surprise endpoint. Returns ISO YYYY-MM-DD or None."""
    url = f'https://api.nasdaq.com/api/company/{sym}/earnings-surprise'
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json',
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.load(r)
        rows = (((d.get('data') or {}).get('earningsSurpriseTable') or {}).get('rows')) or []
        if not rows: return None
        # rows[0] = most recent quarter. dateReported format: "M/D/YYYY".
        date_str = (rows[0] or {}).get('dateReported')
        if not date_str: return None
        try:
            dt = datetime.strptime(date_str, '%m/%d/%Y')
            return dt.strftime('%Y-%m-%d')
        except Exception:
            return None
    except Exception:
        return None

def main():
    if not TV_PATH.exists():
        print('[skip] tv-summary.json not found — run parse_tv.py first')
        return
    arr = json.loads(TV_PATH.read_text(encoding='utf-8'))
    missing = [t for t in arr if not t.get('LatestReportDate')]
    if not missing:
        print('[skip] all tickers already have LatestReportDate from TV')
        return
    print(f'[fetch_earnings_dates] {len(missing)} tickers missing date, querying NASDAQ...')
    updated, failed = 0, 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(fetch_one, t['Ticker']): t for t in missing}
        for done, f in enumerate(as_completed(futs), 1):
            t = futs[f]
            try:
                date = f.result()
                if date:
                    t['LatestReportDate'] = date
                    updated += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
            if done % 20 == 0:
                print(f'  [{done}/{len(missing)}] ok={updated} fail={failed}')
    TV_PATH.write_text(json.dumps(arr, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'[OK] backfilled {updated} earnings dates from NASDAQ, {failed} not found')

if __name__ == '__main__':
    main()
