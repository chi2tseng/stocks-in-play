"""fetch_earnings_dates.py — fallback earnings-date fetcher.

For any ticker in `tv-summary.json` where `LatestReportDate` is None (because
TV's earnings page showed "Next report date" instead of "Latest report date"
— common for tickers with upcoming reports), cascade through:

  1. NASDAQ earnings-surprise endpoint     — works for most US-listed names
  2. SEC EDGAR submissions API             — catches foreign issuers (6-K)
                                              + ADRs (20-F) that NASDAQ
                                              doesn't cover (BHP, RIO, CRML)

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
SEC_UA = 'Research research@example.com'  # SEC requires a UA with contact info

# Lazy-loaded SEC ticker → CIK map (~10k rows, fetched once per run).
_SEC_TICKERS = None
def _sec_tickers():
    global _SEC_TICKERS
    if _SEC_TICKERS is not None: return _SEC_TICKERS
    try:
        req = urllib.request.Request(
            'https://www.sec.gov/files/company_tickers.json',
            headers={'User-Agent': SEC_UA, 'Accept': 'application/json'},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
        _SEC_TICKERS = {v['ticker']: str(v['cik_str']).zfill(10) for v in data.values()}
    except Exception:
        _SEC_TICKERS = {}
    return _SEC_TICKERS

def fetch_nasdaq(sym):
    """NASDAQ earnings-surprise. Returns ISO YYYY-MM-DD or None."""
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
        date_str = (rows[0] or {}).get('dateReported')
        if not date_str: return None
        try:
            return datetime.strptime(date_str, '%m/%d/%Y').strftime('%Y-%m-%d')
        except Exception:
            return None
    except Exception:
        return None

def _is_fiscal_qend(date_str):
    """True if YYYY-MM-DD's MM-DD matches a typical fiscal quarter-end (3/31, 6/30, 9/30, 12/31)."""
    return bool(date_str) and date_str[5:] in ('03-31', '06-30', '09-30', '12-31')

def fetch_sec(sym):
    """SEC EDGAR. Walks recent filings (most-recent-first), returns filingDate
    of the most-recent earnings-bearing filing:
      • 10-Q / 10-K / 20-F → always earnings, use filingDate
      • 6-K               → only if reportDate is a fiscal quarter-end (foreign
                            issuers also file 6-K for interim press releases,
                            governance notices, etc. — those don't count)
    ISO YYYY-MM-DD or None."""
    cik = _sec_tickers().get(sym)
    if not cik: return None
    url = f'https://data.sec.gov/submissions/CIK{cik}.json'
    req = urllib.request.Request(url, headers={'User-Agent': SEC_UA, 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.load(r)
        rec = (d.get('filings') or {}).get('recent') or {}
        forms = rec.get('form', [])
        fdates = rec.get('filingDate', [])
        rdates = rec.get('reportDate', [])
        for i, form in enumerate(forms):
            if i >= len(rdates) or i >= len(fdates): continue
            rd, fd = rdates[i], fdates[i]
            if not rd or not fd: continue
            if form in ('10-Q', '10-K', '20-F'):
                return fd
            if form == '6-K' and _is_fiscal_qend(rd):
                return fd
        return None
    except Exception:
        return None

def fetch_one(sym):
    """Try NASDAQ first, fall back to SEC EDGAR for foreign issuers."""
    d = fetch_nasdaq(sym)
    if d: return d
    return fetch_sec(sym)

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
