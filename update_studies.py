"""Daily Studies OHLCV refresh.

For every study in dashboard/studies/studies.json that has `ohlcv.date` filled, fetches
fresh OHLCV from Yahoo Finance for THAT specific trading day (plus the prior day's close
as prev_close) and writes back: open / high / low / close / prev_close / volume.

Designed to run unattended — idempotent, no console interaction. Safe to schedule daily
via Windows Task Scheduler / cron.

Usage:
    py update_studies.py              # update every study with a filled date (overwrite mode)
    py update_studies.py --safe       # only fill NULL fields, never overwrite user values
    py update_studies.py --sym FIG ARM   # restrict to specific symbols
    py update_studies.py --dry-run    # show what would change without writing
    py update_studies.py --build      # also run build_dashboard.py after the refresh
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

REPO_DIR     = os.path.dirname(os.path.abspath(__file__))
STUDIES_JSON = os.path.join(REPO_DIR, 'dashboard', 'studies', 'studies.json')

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'


def parse_date(date_str: str) -> datetime | None:
    """Accept YYYY-MM-DD or MM/DD/YYYY → returns UTC midnight datetime, or None."""
    if not date_str:
        return None
    s = date_str.strip()
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def fetch_yahoo_window(symbol: str, target_date: datetime, days_before: int = 10) -> list[dict]:
    """
    Fetches daily bars for `target_date` minus `days_before` to `target_date` + 2 days.
    The window includes a few trading days BEFORE the target so we can compute prev_close
    (= close of the trading day immediately before target_date) and resolve cases where
    `target_date` lands on a weekend / holiday (we fall back to the nearest prior bar).

    Returns a list of dicts sorted by date ascending:
        [{date: 'YYYY-MM-DD', open, high, low, close, volume}, ...]
    Returns [] on any fetch / parse failure (caller decides what to do).
    """
    period1 = int(target_date.timestamp() - days_before * 86400)
    period2 = int(target_date.timestamp() + 2 * 86400)
    url = (f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
           f'?period1={period1}&period2={period2}&interval=1d&events=history')
    try:
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as e:
        print(f'  [warn] Yahoo HTTP {e.code} for {symbol}')
        return []
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        print(f'  [warn] Yahoo network error for {symbol}: {e}')
        return []
    except Exception as e:
        print(f'  [warn] Yahoo parse error for {symbol}: {e}')
        return []
    try:
        result = payload['chart']['result']
        if not result or not result[0]:
            err = (payload.get('chart') or {}).get('error') or {}
            print(f'  [warn] Yahoo returned no data for {symbol}: {err.get("description") or "empty result"}')
            return []
        result = result[0]
        timestamps = result.get('timestamp') or []
        quote = (result.get('indicators', {}).get('quote') or [{}])[0]
        opens   = quote.get('open')   or []
        highs   = quote.get('high')   or []
        lows    = quote.get('low')    or []
        closes  = quote.get('close')  or []
        volumes = quote.get('volume') or []
    except Exception as e:
        print(f'  [warn] Yahoo schema error for {symbol}: {e}')
        return []
    bars = []
    for i, ts in enumerate(timestamps):
        # Skip rows missing core fields (Yahoo occasionally returns null mid-array)
        if opens[i] is None or closes[i] is None:
            continue
        bars.append({
            'date':   datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%Y-%m-%d'),
            'open':   round(opens[i],  4),
            'high':   round(highs[i],  4) if highs[i]  is not None else None,
            'low':    round(lows[i],   4) if lows[i]   is not None else None,
            'close':  round(closes[i], 4),
            'volume': int(volumes[i]) if volumes[i] is not None else None,
        })
    return bars


def compute_study_patch(study: dict, bars: list[dict], date_str: str) -> dict[str, tuple] | None:
    """
    Find target_date's bar (or nearest prior trading day if exact date missing — Yahoo
    omits weekends / holidays). prev_close = close of the bar BEFORE the matched bar.

    Returns dict of {field: (old_value, new_value)} for fields that should change, or
    None if no matching bar.
    """
    if not bars:
        return None
    # Exact match first
    target = next((b for b in bars if b['date'] == date_str), None)
    if not target:
        # Fall back: nearest bar with date <= target. Useful when user types a weekend date.
        prior = [b for b in bars if b['date'] <= date_str]
        if not prior:
            return None
        target = prior[-1]
        if target['date'] != date_str:
            print(f'  [info] no bar for {date_str}; using nearest prior {target["date"]}')
    # prev_close = close of bar immediately before target's bar
    prev_bar = next((b for b in reversed(bars) if b['date'] < target['date']), None)
    prev_close = prev_bar['close'] if prev_bar else None

    cur_ohlcv = study.get('ohlcv') or {}
    new_vals = {
        'open':       target['open'],
        'high':       target['high'],
        'low':        target['low'],
        'close':      target['close'],
        'prev_close': prev_close,
        'volume':     target['volume'],
    }
    changes = {}
    for k, v in new_vals.items():
        if cur_ohlcv.get(k) != v:
            changes[k] = (cur_ohlcv.get(k), v)
    return changes


def update_one(study: dict, *, safe: bool, dry_run: bool) -> dict | None:
    """Returns the applied-changes dict, or None if skipped (no date / no data)."""
    sym = study.get('symbol') or ''
    if not sym:
        return None
    ohlcv = study.get('ohlcv') or {}
    date_str = (ohlcv.get('date') or '').strip()
    if not date_str:
        return None
    parsed = parse_date(date_str)
    if not parsed:
        print(f'  [warn] {sym}: unparseable date "{date_str}", skipping')
        return None
    # Skip future dates (Yahoo won't have data yet — avoid wasting an HTTP request)
    if parsed > datetime.now(timezone.utc):
        print(f'  [warn] {sym}: date {date_str} is in the future, skipping')
        return None
    # Normalize stored date to YYYY-MM-DD for consistent matching
    iso_date = parsed.strftime('%Y-%m-%d')
    bars = fetch_yahoo_window(sym, parsed)
    if not bars:
        return None
    changes = compute_study_patch(study, bars, iso_date)
    if not changes:
        return {}  # no diff
    # Apply (or filter in safe mode)
    final_changes = {}
    for k, (old, new) in changes.items():
        if safe and old is not None:
            continue   # safe mode: never overwrite user-typed value
        final_changes[k] = (old, new)
    if not final_changes:
        return {}
    if not dry_run:
        new_ohlcv = dict(ohlcv)
        # Normalize date field too
        new_ohlcv['date'] = iso_date
        for k, (old, new) in final_changes.items():
            new_ohlcv[k] = new
        study['ohlcv'] = new_ohlcv
    return final_changes


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--safe', action='store_true',
                    help='Only fill null fields — never overwrite a value the user typed.')
    ap.add_argument('--sym', nargs='+',
                    help='Restrict to specific symbols (case-insensitive).')
    ap.add_argument('--dry-run', action='store_true',
                    help='Show what would change without writing to disk.')
    ap.add_argument('--build', action='store_true',
                    help='After the refresh, run build_dashboard.py to regenerate the hosted dashboard.')
    args = ap.parse_args()

    if not os.path.exists(STUDIES_JSON):
        print(f'[err] No studies file at {STUDIES_JSON}')
        sys.exit(1)

    with open(STUDIES_JSON, 'r', encoding='utf-8') as f:
        studies = json.load(f)
    if not isinstance(studies, list):
        print(f'[err] {STUDIES_JSON} is not a JSON array')
        sys.exit(1)

    filter_syms = set(s.upper() for s in args.sym) if args.sym else None
    print(f'[update_studies] {len(studies)} studies total · '
          f'{"safe" if args.safe else "overwrite"} mode · '
          f'{"DRY RUN" if args.dry_run else "writing changes"}\n')

    total_updated = 0
    total_skipped = 0
    for st in studies:
        sym = (st.get('symbol') or '').upper()
        if not sym:
            continue
        if filter_syms and sym not in filter_syms:
            continue
        date_str = (st.get('ohlcv') or {}).get('date')
        if not date_str:
            total_skipped += 1
            continue
        print(f'· {sym} @ {date_str}')
        changes = update_one(st, safe=args.safe, dry_run=args.dry_run)
        if changes is None:
            total_skipped += 1
            continue
        if not changes:
            print('   no changes')
            continue
        for k, (old, new) in changes.items():
            old_s = '—' if old is None else (f'{old:.2f}' if isinstance(old, float) else str(old))
            new_s = '—' if new is None else (f'{new:.2f}' if isinstance(new, float) else str(new))
            print(f'   {k:11s}  {old_s} → {new_s}')
        total_updated += 1
        # gentle throttle so Yahoo doesn't rate-limit on a big Studies library
        time.sleep(0.25)

    if not args.dry_run and total_updated > 0:
        tmp = STUDIES_JSON + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(studies, f, ensure_ascii=False, indent=2)
        os.replace(tmp, STUDIES_JSON)
        print(f'\n[OK] {total_updated} updated, {total_skipped} skipped → {STUDIES_JSON}')
    elif args.dry_run:
        print(f'\n[dry-run] would update {total_updated}, skip {total_skipped}')
    else:
        print(f'\n[OK] No changes ({total_skipped} skipped, {len(studies) - total_skipped} already current)')

    if args.build and not args.dry_run:
        print('\n[build] running build_dashboard.py …')
        import subprocess
        subprocess.run([sys.executable, os.path.join(REPO_DIR, 'build_dashboard.py')], check=False)


if __name__ == '__main__':
    main()
