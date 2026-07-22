#!/usr/bin/env python
"""fetch_logos.py — download company logo PNGs for the SIPs dashboard.

Writes one PNG per ticker to dashboard/logos/<SYM>.png so the dashboard can
show a logo next to each stock. Idempotent — re-running only fetches symbols
that don't already have a logo file (daily runs just top up new tickers).

Symbol universe = union of three sources:
  a) bignames-scan.py's UNIVERSE curated large-cap list (regex-extracted from
     the triple-quoted string, since importing that module pulls in network
     helpers we don't need here).
  b) dashboard/earnings_calendar.json — every symbol across all days/sessions
     (bmo/amc/unspecified).
  c) today's daily package — dashboard/data/<ET-date>.json's "stocks" keys
     (ET date via zoneinfo America/New_York), falling back to
     dashboard/data.json if the dated file isn't there yet.

Logo sources (both already verified 200 + real PNG for GEV/RNR/BABA/TSM/SDOT/
NVS/EQNR/PNFP — do not re-verify, just use):
  1. primary:  https://images.financialmodelingprep.com/symbol/<SYM>.png
  2. fallback: https://assets.parqet.com/logos/symbol/<SYM>?format=png

A download only counts as success if HTTP 200 AND the body starts with the
PNG magic bytes (\x89PNG) AND is >300 bytes — some APIs 404 into an HTML page
or a tiny placeholder image instead of a clean error, so magic-byte + size
sniffing is what actually guards against writing a bad file.

Usage:
    py fetch_logos.py
Override the SIPs root with the SIPS_DIR env var (defaults to this script's
own directory, matching the other /SIPs tooling).
"""
import os
import re
import json
import sys
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # cp950 console
except Exception:
    pass

DIR = os.environ.get("SIPS_DIR") or os.path.dirname(os.path.abspath(__file__))
DASHBOARD_DIR = os.path.join(DIR, "dashboard")
LOGOS_DIR = os.path.join(DASHBOARD_DIR, "logos")

PRIMARY_URL = "https://images.financialmodelingprep.com/symbol/{sym}.png"
FALLBACK_URL = "https://assets.parqet.com/logos/symbol/{sym}?format=png"

PNG_MAGIC = b"\x89PNG"
MIN_BYTES = 300
WORKERS = 8


def _extract_bignames_universe():
    """Regex-pull the UNIVERSE = \"\"\"...\"\"\" block out of bignames-scan.py.

    We don't import the module directly — it pulls in prepost_quote/headline
    network helpers we don't need just to read a symbol list.
    """
    path = os.path.join(DIR, "bignames-scan.py")
    if not os.path.exists(path):
        return set()
    text = open(path, encoding="utf-8").read()
    m = re.search(r'UNIVERSE\s*=\s*"""(.*?)"""', text, re.S)
    return set(m.group(1).split()) if m else set()


def _extract_earnings_calendar_symbols():
    path = os.path.join(DASHBOARD_DIR, "earnings_calendar.json")
    if not os.path.exists(path):
        return set()
    try:
        cal = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print(f"[warn] earnings_calendar.json unreadable: {e}")
        return set()
    symbols = set()
    for day in cal.get("days", []):
        for session in ("bmo", "amc", "unspecified"):
            for row in day.get(session, []) or []:
                sym = row.get("symbol")
                if sym:
                    symbols.add(sym)
    return symbols


def _extract_today_package_symbols():
    today_et = None
    if ZoneInfo is not None:
        try:
            today_et = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
        except Exception:
            today_et = None

    path = None
    if today_et:
        dated = os.path.join(DASHBOARD_DIR, "data", f"{today_et}.json")
        if os.path.exists(dated):
            path = dated
    if path is None:
        fallback = os.path.join(DASHBOARD_DIR, "data.json")
        if os.path.exists(fallback):
            path = fallback
    if path is None:
        return set()

    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print(f"[warn] {path} unreadable: {e}")
        return set()
    return set(data.get("stocks", {}).keys())


def get_universe():
    symbols = set()
    symbols |= _extract_bignames_universe()
    symbols |= _extract_earnings_calendar_symbols()
    symbols |= _extract_today_package_symbols()
    return sorted(s for s in symbols if s)


def _is_valid_png(body):
    return bool(body) and len(body) > MIN_BYTES and body[:4] == PNG_MAGIC


def _try_download(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                return None
            body = resp.read()
    except (URLError, HTTPError, TimeoutError, ConnectionError, OSError):
        return None
    return body if _is_valid_png(body) else None


def fetch_one(sym):
    """Returns (status, sym, used_fallback). status in {'downloaded','miss'}."""
    body = _try_download(PRIMARY_URL.format(sym=sym))
    used_fallback = False
    if body is None:
        used_fallback = True
        body = _try_download(FALLBACK_URL.format(sym=sym))
    if body is None:
        return ("miss", sym, False)
    out_path = os.path.join(LOGOS_DIR, f"{sym}.png")
    with open(out_path, "wb") as f:
        f.write(body)
    return ("downloaded", sym, used_fallback)


def main():
    os.makedirs(LOGOS_DIR, exist_ok=True)
    universe = get_universe()
    total = len(universe)

    existing = [s for s in universe if os.path.exists(os.path.join(LOGOS_DIR, f"{s}.png"))]
    todo = [s for s in universe if s not in set(existing)]

    downloaded = []
    missed = []
    fallback_hits = 0

    if todo:
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futures = {ex.submit(fetch_one, sym): sym for sym in todo}
            for fut in as_completed(futures):
                status, sym, used_fallback = fut.result()
                if status == "downloaded":
                    downloaded.append(sym)
                    if used_fallback:
                        fallback_hits += 1
                else:
                    missed.append(sym)
                    print(f"[miss] {sym}")

    print()
    print(
        f"total={total} existed={len(existing)} downloaded={len(downloaded)} "
        f"missed={len(missed)} fallback_used={fallback_hits}"
    )
    if missed:
        print("missed list:", ", ".join(sorted(missed)))


if __name__ == "__main__":
    main()
