#!/usr/bin/env python
"""prepost_quote.py — one correct "today's move incl. pre/post-market" helper.

WHY (2026-07-20 bug): range=1d&interval=5m returns the LAST TRADING DAY's bars.
Pre-market Monday that's still Friday, and meta.chartPreviousClose points at
Thursday — so the scripts reported Friday-vs-Thursday moves (ISRG -13.75%) and
called them "today pre-market". Real pre-market was ISRG +0.41%.

Fix: pull range=2d, split the 5m bars by EXCHANGE-LOCAL date (meta.gmtoffset),
keep only bars belonging to the CURRENT session date
(meta.currentTradingPeriod.regular.start), and compare the last of those to the
previous regular-session close. No today bars -> return None (never fall back to
a daily-close diff and pass it off as today's move).
"""
import json, urllib.request, datetime

UA = {'User-Agent': 'Mozilla/5.0'}


def _lt(ts, off):
    return datetime.datetime.utcfromtimestamp(ts + off)


def prepost_quote(sym, timeout=12):
    """-> (chg_pct, last, volume) for TODAY incl. pre/post, or None if no bars today."""
    u = (f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}'
         f'?range=2d&interval=5m&includePrePost=true')
    try:
        r = json.load(urllib.request.urlopen(
            urllib.request.Request(u, headers=UA), timeout=timeout))['chart']['result'][0]
    except Exception:
        return None
    m = r.get('meta') or {}
    off = m.get('gmtoffset')
    reg = ((m.get('currentTradingPeriod') or {}).get('regular') or {})
    start = reg.get('start')
    ts = r.get('timestamp') or []
    quote = ((r.get('indicators') or {}).get('quote') or [{}])[0]
    cl = quote.get('close') or []
    if off is None or not start or not ts:
        return None

    today = _lt(start, off).date()
    bars = [(t, c) for t, c in zip(ts, cl) if c is not None]
    todays = [(t, c) for t, c in bars if _lt(t, off).date() == today]
    if not todays:
        return None  # no-premarket-data: nothing traded today yet

    last = todays[-1][1]

    # Previous close. Yahoo's meta fields shift by one session at the open:
    # pre-market regularMarketPrice IS the prior official close while
    # previousClose is the day before that; after the open they swap
    # (regularMarketPrice goes live, previousClose becomes the prior close).
    # chartPreviousClose is unreliable in both states. So don't guess from the
    # clock — anchor on the previous session's own last regular-hours bar and
    # pick whichever meta field it matches.
    prev = [c for t, c in bars
            if _lt(t, off).date() < today
            and 9 * 60 + 30 <= _lt(t, off).hour * 60 + _lt(t, off).minute < 16 * 60]
    anchor = prev[-1] if prev else None
    cands = [c for c in (m.get('previousClose'), m.get('regularMarketPrice')) if c]
    if anchor and cands:
        pc = min(cands, key=lambda c: abs(c - anchor))
        if abs(pc - anchor) / anchor > 0.02:   # neither field is the prior close
            pc = anchor
    else:
        pc = anchor or (cands[0] if cands else None)
    if not pc:
        return None

    return round((last - pc) / pc * 100, 2), round(last, 2), m.get('regularMarketVolume')
