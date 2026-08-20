#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""qwen_full.py — FULL SIPs pipeline, Qwen's independent curation (no Claude, no VM).

Mirrors the SIPs-gemini-full contract: run the whole pipeline, but the ONLY shared
file Qwen writes is qwen_picks.json. Mechanical phases are deterministic code
(same scripts Claude calls); every judgment call is a small-context chat to the
local qwen-cc model on host Ollama — no giant harness, no compaction, no nested
tool schemas.

Usage:  py D:\\SIPs\\qwen_full.py            (add --dry to skip git push)
"""
import csv, io, json, os, re, subprocess, sys, time, urllib.request
from datetime import datetime, timezone, timedelta

DIR = os.path.dirname(os.path.abspath(__file__))
OLLAMA = "http://127.0.0.1:11434/api/chat"
MODEL = "qwen-cc"
MAX_SHORTLIST = 10
SNIP = 2400
ET = timezone(timedelta(hours=-4))
DATE = datetime.now(ET).strftime("%Y-%m-%d")
DRY = "--dry" in sys.argv


def log(*a):
    print(time.strftime("[%H:%M:%S]"), *a, flush=True)


def run(cmd, timeout=300, cwd=DIR):
    env = dict(os.environ, PYTHONUTF8="1")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout, cwd=cwd, env=env)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def chat(prompt, force_json=False):
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
            "stream": False, "options": {"temperature": 0.4}}
    if force_json:
        body["format"] = "json"
    req = urllib.request.Request(OLLAMA, json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        out = json.load(r)["message"]["content"]
    return re.sub(r"<think>.*?</think>", "", out, flags=re.S).strip()


def extract_json(txt):
    txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M).strip()
    try:
        return json.loads(txt)
    except Exception:
        m = re.search(r"[\[{].*[\]}]", txt, re.S)
        if m:
            return json.loads(m.group(0))
        raise


def exa_search(query):
    q = json.dumps({"query": query, "numResults": 4}).replace('"', '\\"')
    rc, out = run('mcporter call exa.web_search_exa --args "%s"' % q, timeout=90, cwd=None)
    return out[:SNIP] if rc == 0 and out.strip() else ""


# ---------- phase 1-2: mechanical scan (same scripts Claude runs) ----------
def ensure_packet():
    pk_path = os.path.join(DIR, "dashboard", "data", DATE + ".json")
    fresh = False
    if os.path.exists(pk_path):
        pk = json.load(open(pk_path, encoding="utf-8"))
        ts = pk.get("scanTimestamp", "")
        try:
            # scanTimestamp is naive local time (build_dashboard uses datetime.now())
            age = (datetime.now() - datetime.fromisoformat(ts)).total_seconds()
            fresh = age < 7200
        except ValueError:
            pass
    if not fresh:
        log("packet stale/missing — rescanning barchart")
        rc, out = run("node barchart-scrape.js", timeout=180)
        if rc != 0:
            log("barchart FAILED:\n" + out[-500:]); sys.exit(1)
        sh = os.path.join(DIR, "shorts.json")
        if not os.path.exists(sh) or datetime.fromtimestamp(os.path.getmtime(sh)).date() != datetime.now().date():
            log("finviz shorts refresh (~90s)")
            run("node finviz-shorts.js", timeout=240)
        rc, out = run("py build_dashboard.py", timeout=300)
        if rc != 0:
            log("build FAILED:\n" + out[-500:]); sys.exit(1)
    pk = json.load(open(pk_path, encoding="utf-8"))
    log("packet", DATE, "stocks", len(pk.get("stocks", {})))
    return pk


def tv_topup(syms, stocks):
    """Scrape TradingView FQ for shortlisted earnings names lacking tv data."""
    need = [s for s in syms if not (stocks[s].get("tv") or {}).get("LatestEPS")
            and stocks[s].get("type") in ("earnings", "guidance")][:4]
    if not need:
        return False
    log("tv-scrape top-up:", need)
    run("node tv-scrape.js " + " ".join(need), timeout=420)
    run("py parse_tv.py " + " ".join(need), timeout=120)
    return True


# ---------- judgment stages (all Qwen) ----------
def compact_row(sym, s):
    tv = s.get("tv") or {}
    return {"symbol": sym, "chgPct": s.get("chgPct"), "type": s.get("type"),
            "mcap_M": s.get("marketCap_M"), "shortFloat": s.get("shortFloat"),
            "dtc": s.get("shortRatio"), "epsSurp": tv.get("LatestEPSSurprise_pct"),
            "revSurp": tv.get("LatestRevSurprise_pct"),
            "catalyst": (s.get("catalyst") or "")[:90]}


def main():
    t0 = time.time()
    pk = ensure_packet()
    stocks = pk.get("stocks") or {}
    rows = sorted((compact_row(k, v) for k, v in stocks.items()),
                  key=lambda r: -abs(r.get("chgPct") or 0))[:100]

    p1 = ("今天是 %s(美股)。以下為今日異動候選:\n%s\n\n"
          "你是獨立交易評審(不是 Claude,選你自己認為的)。選最多 %d 檔今天最值得深入研究的:"
          "真實催化劑(財報/合約/FDA/併購)優先於無消息 pump;數字規模與 squeeze 燃料(shortFloat/dtc)加分;"
          "漲的 intent=long、跌的 intent=short。\n"
          "只回 JSON 陣列:[{\"symbol\":\"SYM\",\"intent\":\"long|short\"}]"
          ) % (DATE, json.dumps(rows, ensure_ascii=False), MAX_SHORTLIST)
    sl = []
    for attempt in (1, 2):
        try:
            sl = extract_json(chat(p1))
            if isinstance(sl, dict):
                sl = sl.get("picks") or []
            sl = [x for x in sl if isinstance(x, dict) and x.get("symbol") in stocks][:MAX_SHORTLIST]
            if sl:
                break
        except Exception as e:
            log("shortlist attempt", attempt, "failed:", e)
    if not sl:
        log("FATAL: no shortlist"); sys.exit(1)
    log("shortlist:", [x["symbol"] for x in sl])

    if tv_topup([x["symbol"] for x in sl], stocks):
        run("py build_dashboard.py", timeout=300)      # fold fresh TV into packet
        pk = json.load(open(os.path.join(DIR, "dashboard", "data", DATE + ".json"), encoding="utf-8"))
        stocks = pk.get("stocks") or stocks

    picks = []
    for x in sl:
        sym = x["symbol"]
        s = stocks.get(sym) or {}
        chg = s.get("chgPct") or 0
        intent = "long" if chg > 0 else "short"
        research = exa_search("%s stock %s news catalyst" % (sym, DATE)) or "(搜尋無結果)"
        tv = s.get("tv") or {}
        p2 = ("今天是 %s。候選 %s(%s)今日 %+.1f%%。packet:type=%s catalyst=%s\n"
              "數字:epsSurp=%s revSurp=%s shortFloat=%s dtc=%s mcap_M=%s\n\n"
              "你自己的網路搜尋結果:\n%s\n\n"
              "判斷是否收進今日 picks(方向固定 %s)。查無實質消息傾向 drop;"
              "rationale 要引用具體消息與數字,繁體中文 1-3 句,禁空話。\n"
              "只回 JSON:{\"keep\":true|false,\"rationale\":\"...\"}"
              ) % (DATE, sym, s.get("name") or "", chg, s.get("type"),
                   (s.get("catalyst") or "")[:120], tv.get("LatestEPSSurprise_pct"),
                   tv.get("LatestRevSurprise_pct"), s.get("shortFloat"),
                   s.get("shortRatio"), s.get("marketCap_M"), research, intent)
        try:
            v = extract_json(chat(p2, force_json=True))
        except Exception as e:
            log(sym, "verdict failed:", e); continue
        if v.get("keep") and v.get("rationale"):
            picks.append({"symbol": sym, "intent": intent,
                          "rationale": str(v["rationale"])[:600]})
            log(sym, "KEEP")
        else:
            log(sym, "drop")

    if len(picks) > 1:
        try:
            order = extract_json(chat("重新排序(最強在前),只回 symbol 字串的 JSON 陣列:\n"
                                      + json.dumps(picks, ensure_ascii=False)))
            key = {(o if isinstance(o, str) else o.get("symbol")): i for i, o in enumerate(order)}
            picks.sort(key=lambda p: key.get(p["symbol"], 99))
        except Exception as e:
            log("ranking failed:", e)
    for i, p in enumerate(picks):
        p["rank"] = i + 1

    out = os.path.join(DIR, "qwen_picks.json")
    tmp = out + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(
        json.dumps({"date": DATE, "picks": picks}, ensure_ascii=False, indent=1))
    json.load(open(tmp, encoding="utf-8"))
    os.replace(tmp, out)
    log("wrote qwen_picks.json:", [p["symbol"] for p in picks])

    # ---------- mechanical close-out ----------
    run("py fetch_candles.py", timeout=180)
    rc, o = run("py build_dashboard.py", timeout=300)
    if rc != 0:
        log("final build FAILED:\n" + o[-400:]); sys.exit(1)
    if DRY:
        log("--dry: skip git push")
    else:
        run("git add qwen_picks.json dashboard/data/*.json dashboard/data.json dashboard/dates.json dashboard/index.html dashboard/candles.json", timeout=60)
        top = ", ".join(p["symbol"] for p in picks[:2]) or "none"
        run('git commit -m "qwen picks: %s — top: %s"' % (DATE, top), timeout=60)
        for i in (1, 2):
            rc, o = run("git push", timeout=120)
            if rc == 0:
                break
            log("push retry", i); run("git pull --rebase", timeout=120)
        log("push", "OK" if rc == 0 else "FAILED")

    log("done in %.1f min | %d candidates -> %d shortlist -> %d picks | #1 %s"
        % ((time.time() - t0) / 60, len(rows), len(sl), len(picks),
           picks[0]["symbol"] if picks else "-"))


if __name__ == "__main__":
    main()
