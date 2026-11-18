#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ollama_full.py — FULL SIPs pipeline, Qwen's independent curation (no Claude, no VM).

Mirrors the SIPs-gemini-full contract: run the whole pipeline, but the ONLY shared
file Qwen writes is ollama_picks.json. Mechanical phases are deterministic code
(same scripts Claude calls); every judgment call is a small-context chat to the
local qwen-cc model on host Ollama — no giant harness, no compaction, no nested
tool schemas.

Usage:  py D:\\SIPs\\ollama_full.py            (add --dry to skip git push)
"""
import csv, io, json, os, re, subprocess, sys, time, urllib.request
from datetime import datetime, timezone, timedelta

DIR = os.path.dirname(os.path.abspath(__file__))
OLLAMA = "http://127.0.0.1:11434/api/chat"
LMSTUDIO = "http://127.0.0.1:1234/v1/chat/completions"
BACKEND = "lmstudio" if "--lmstudio" in sys.argv else "ollama"
MODEL = "qwen3.8-27b@iq3_xxs" if BACKEND == "lmstudio" else "qwen-cc"
for _i, _a in enumerate(sys.argv):
    if _a == "--model" and _i + 1 < len(sys.argv):
        MODEL = sys.argv[_i + 1]
MAX_SHORTLIST = 10
SNIP = 2400
ET = timezone(timedelta(hours=-4))
DATE = datetime.now(ET).strftime("%Y-%m-%d")
DRY = "--dry" in sys.argv
NO_DETAIL = "--no-detail" in sys.argv     # skip the Phase 6/6.5/7 composition stages
OVERWRITE = "--overwrite" in sys.argv     # replace existing entries instead of only filling gaps
TOPN = 5                                  # how many picks get the full deep-dive treatment


def log(*a):
    print(time.strftime("[%H:%M:%S]"), *a, flush=True)


def run(cmd, timeout=300, cwd=DIR):
    env = dict(os.environ, PYTHONUTF8="1")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout, cwd=cwd, env=env)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def chat(prompt, force_json=False, max_tokens=1500):
    # max_tokens is NOT optional: an uncapped generation ran away to 9.7k tokens on
    # 2026-08-27 and took the CUDA backend down with it (ggml-cuda.cu:106).
    if BACKEND == "lmstudio":
        body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                "stream": False, "temperature": 0.4, "max_tokens": max_tokens}
        if force_json:
            # LM Studio only accepts json_schema/text; permissive object schema
            body["response_format"] = {"type": "json_schema", "json_schema": {
                "name": "out", "schema": {"type": "object"}}}
        url = LMSTUDIO
    else:
        body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                "stream": False, "options": {"temperature": 0.4, "num_predict": max_tokens}}
        if force_json:
            body["format"] = "json"
        url = OLLAMA
    req = urllib.request.Request(url, json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        out = json.load(r)
    out = out["choices"][0]["message"]["content"] if BACKEND == "lmstudio" \
        else out["message"]["content"]
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


def exa_items(query, n=5):
    """Same Exa call, but parsed into records so news_detail can cite real URLs + times."""
    q = json.dumps({"query": query, "numResults": n}).replace('"', '\\"')
    rc, out = run('mcporter call exa.web_search_exa --args "%s"' % q, timeout=120, cwd=None)
    if rc != 0 or not out.strip():
        return []
    items = []
    for blk in out.split("\n---\n"):
        g = lambda k: (re.search(r"^%s:\s*(.+)$" % k, blk, re.M) or [None, ""])[1].strip()
        url = g("URL")
        if not url:
            continue
        body = blk.split("Highlights:", 1)[-1]
        items.append({"title": g("Title")[:160], "url": url,
                      "published": g("Published"), "text": re.sub(r"\s+", " ", body)[:900]})
    return items


def to_et_iso(published):
    """Exa gives UTC ISO (…Z). news_detail wants an ET-stamped ISO string."""
    try:
        dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
        return dt.astimezone(ET).replace(microsecond=0).isoformat()
    except Exception:
        return ""


def load_json(path, default):
    try:
        return json.load(open(os.path.join(DIR, path), encoding="utf-8"))
    except Exception:
        return default


def save_json(path, obj):
    p = os.path.join(DIR, path)
    tmp = p + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(json.dumps(obj, ensure_ascii=False, indent=1))
    json.load(open(tmp, encoding="utf-8"))          # parse-back guard before swap
    os.replace(tmp, p)


# ---------- phase 1-2: mechanical scan (same scripts Claude runs) ----------
def ensure_packet():
    # Unified /SIPs contract (2026-08-26): ALWAYS rescan from scratch — no freshness
    # shortcut. build_dashboard unions, so existing names/analysis never drop.
    pk_path = os.path.join(DIR, "dashboard", "data", DATE + ".json")
    if True:
        log("full rescan (unified contract: default from scratch)")
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


def num_block(sym, s):
    tv = s.get("tv") or {}
    return ("%s(%s) %+.2f%% | type=%s | mcap %sM | shortFloat %s | DTC %s | "
            "epsSurp %s | revSurp %s | catalyst: %s"
            % (sym, s.get("name") or "", s.get("chgPct") or 0, s.get("type"),
               s.get("marketCap_M"), s.get("shortFloat"), s.get("shortRatio"),
               tv.get("LatestEPSSurprise_pct"), tv.get("LatestRevSurprise_pct"),
               (s.get("catalyst") or "")[:160]))


# ---------- phase 7: news_detail.json (繁中 detail + REAL published time + sources) ----------
def compose_news_detail(picks, stocks, research):
    nd = load_json("news_detail.json", {})
    wrote = []
    for p in picks[:TOPN]:
        sym = p["symbol"]
        if sym in nd and not OVERWRITE:
            continue
        items = research.get(sym) or exa_items("%s stock news catalyst %s" % (sym, DATE))
        if not items:
            log(sym, "news_detail skipped (no sources)")
            continue
        src_txt = "\n\n".join("[%d] %s\n%s\n發布時間:%s\n%s"
                              % (i + 1, it["title"], it["url"], it["published"], it["text"])
                              for i, it in enumerate(items[:4]))
        s = stocks.get(sym) or {}
        prompt = (
            "今天是 %s(美股)。請為 %s 寫一段「今日漲跌新聞整理」,繁體中文台灣財經白話。\n"
            "數據:%s\n\n來源材料:\n%s\n\n"
            "格式(嚴格照抄結構,markdown):\n"
            "> **今日漲跌:** <盤前/盤中> %+.2f%% — <一句話講清楚漲跌主因>\n\n"
            "**財報/事件詳情**\n<具體數字:營收、EPS、年增率、指引,全部要有數字>\n\n"
            "**市場與供需細節**\n<訂單、客戶、產能、分析師動作等具體細節>\n\n"
            "**風險備註**\n<這則消息的反面或未確認之處>\n\n"
            "規則:只用來源材料裡的事實,不確定就寫「查無資料」;禁止空話與反向判定框架;"
            "禁止「這是X不是Y」句型;數字一律阿拉伯數字。只輸出上面那段 markdown,不要解釋。"
            % (DATE, sym, num_block(sym, s), src_txt, s.get("chgPct") or 0))
        try:
            detail = chat(prompt).strip()
        except Exception as e:
            log(sym, "news_detail failed:", e); continue
        if len(detail) < 80:
            log(sym, "news_detail too short, skipped"); continue
        dated = [it for it in items if to_et_iso(it["published"])]
        nd[sym] = {"detail": detail,
                   "publishedAt": to_et_iso(dated[0]["published"]) if dated else "",
                   "publishedTimezone": "ET",
                   "sources": [{"label": it["title"], "url": it["url"]} for it in items[:3]]}
        wrote.append(sym)
        log(sym, "news_detail OK")
    if wrote:
        save_json("news_detail.json", nd)
    return wrote


# ---------- phase 7: sean_analysis.json + milan_analysis.json ----------
def compose_views(picks, stocks, research):
    sean = load_json("sean_analysis.json", {})
    milan = load_json("milan_analysis.json", {})
    wrote = []
    for p in picks[:TOPN]:
        sym = p["symbol"]
        s = stocks.get(sym) or {}
        ctx = num_block(sym, s) + "\n研究摘要:" + ((research.get(sym) or [{}])[0].get("text", "")[:600]
                                                if research.get(sym) else "(無)")
        if sym not in sean or OVERWRITE:
            try:
                sean[sym] = {"analysis": chat(
                    "今天是 %s。用 Sean 的視角分析 %s,繁體中文台灣財經白話。\n%s\n\n"
                    "要求:開頭先講市值、空頭占比、DTC(要用括號解釋 DTC 代表什麼)、前一日漲幅;"
                    "然後判斷這是不是 episodic pivot(重大且突然的基本面轉折);"
                    "接著指出漲勢是否已被提前反映;沒有盤前量或圖表資料就明說查無。"
                    "最後一行必須是 **結論:主要觀察名單(MAIN WATCH)** 或 **結論:次要觀察名單(SECONDARY WATCH)**。"
                    "3-5 段,禁空話。" % (DATE, sym, ctx)).strip(),
                    "sourceDate": DATE}
                wrote.append(sym + ":sean")
            except Exception as e:
                log(sym, "sean failed:", e)
        if sym not in milan or OVERWRITE:
            try:
                milan[sym] = {"analysis": chat(
                    "今天是 %s。用 Milan 的視角評 %s 的催化劑品質,繁體中文台灣財經白話。\n%s\n\n"
                    "要求:先講催化劑本身是什麼、由誰觸發;質疑它是否已被股價反映;"
                    "指出哪些關鍵資料查無(例如前 60-90 天新聞背景、盤前量);"
                    "最後一行必須是 **催化劑評分:N/10** 加一句理由。3-4 段,禁空話。"
                    % (DATE, sym, ctx)).strip()}
                wrote.append(sym + ":milan")
            except Exception as e:
                log(sym, "milan failed:", e)
    if wrote:
        save_json("sean_analysis.json", sean)
        save_json("milan_analysis.json", milan)
    return wrote


# ---------- phase 6.5: day_resets.json ----------
def curate_day_resets(stocks):
    dr = load_json("day_resets.json", {})
    resets = dr.get("resets") or {}
    reasons = dr.get("_no_reset_reasons") or {}
    cands = [(k, v) for k, v in stocks.items()
             if v.get("type") in ("earnings", "guidance") and abs(v.get("chgPct") or 0) >= 4][:12]
    if not cands:
        return 0
    rows = [{"symbol": k, "chgPct": v.get("chgPct"), "type": v.get("type"),
             "catalyst": (v.get("catalyst") or "")[:110]} for k, v in cands]
    prompt = ("今天是 %s。以下是今日財報/指引異動股:\n%s\n\n"
              "判斷哪些是「全新的催化劑」(day count 應重置為 day1),哪些是舊消息延續。\n"
              "只回 JSON:{\"resets\":{\"SYM\":\"繁體中文一句理由(含日期與數字)\"},"
              "\"skip\":{\"SYM\":\"繁體中文一句不重置的理由\"}}"
              % (DATE, json.dumps(rows, ensure_ascii=False)))
    try:
        v = extract_json(chat(prompt, force_json=True, max_tokens=900))
    except Exception as e:
        log("day_resets failed:", e); return 0
    n = 0
    for sym, why in (v.get("resets") or {}).items():
        if sym in stocks and (sym not in resets or OVERWRITE):
            resets[sym] = str(why)[:200]; n += 1
    for sym, why in (v.get("skip") or {}).items():
        if sym in stocks:
            reasons[sym] = str(why)[:200]
    save_json("day_resets.json", {"resets": resets, "_no_reset_reasons": reasons})
    log("day_resets:", n, "new resets")
    return n


# ---------- phase 6: 繁中 deliverable ----------
def write_report(picks, stocks):
    lines = ["# SIPs %s — %s 獨立選股" % (DATE, MODEL), ""]
    for p in picks:
        sym = p["symbol"]
        s = stocks.get(sym) or {}
        tv = s.get("tv") or {}
        dot = "🟢 SIP" if p["intent"] == "long" else "🔴 SHORT"
        lines += ["## %s #%d — %s (%s / %+.2f%% / %s)"
                  % (dot, p.get("rank") or 0, sym, s.get("name") or "",
                     s.get("chgPct") or 0, s.get("type") or "-"),
                  "",
                  "- 市值 %sM｜空頭占比 %s｜DTC %s" % (s.get("marketCap_M"),
                                                  s.get("shortFloat"), s.get("shortRatio")),
                  "- EPS 驚喜 %s%%｜營收驚喜 %s%%" % (tv.get("LatestEPSSurprise_pct"),
                                                 tv.get("LatestRevSurprise_pct")),
                  "- 判定:" + p["rationale"], ""]
    lines += ["## 📊 今日結論", "",
              "共 %d 檔:%s" % (len(picks), "、".join(p["symbol"] for p in picks) or "無"), ""]
    path = os.path.join(DIR, "ollama_report_%s.md" % DATE)
    io.open(path, "w", encoding="utf-8").write("\n".join(lines))
    log("wrote", os.path.basename(path))
    return path


def main():
    t0 = time.time()
    log("model:", MODEL)
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
    research = {}
    for x in sl:
        sym = x["symbol"]
        s = stocks.get(sym) or {}
        chg = s.get("chgPct") or 0
        intent = "long" if chg > 0 else "short"
        items = exa_items("%s stock %s news catalyst" % (sym, DATE))
        research[sym] = items
        research_txt = "\n\n".join("%s (%s)\n%s" % (it["title"], it["published"], it["text"])
                                   for it in items)[:SNIP] or "(搜尋無結果)"
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
                   s.get("shortRatio"), s.get("marketCap_M"), research_txt, intent)
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

    out = os.path.join(DIR, "ollama_picks.json")
    tmp = out + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(
        json.dumps({"date": DATE, "model": MODEL, "picks": picks}, ensure_ascii=False, indent=1))
    json.load(open(tmp, encoding="utf-8"))
    os.replace(tmp, out)
    log("wrote ollama_picks.json:", [p["symbol"] for p in picks])

    # ---------- phase 6 / 6.5 / 7: composition stages (all Qwen) ----------
    if NO_DETAIL or not picks:
        log("--no-detail: skip news_detail / sean / milan / day_resets / report")
    else:
        log("composing news_detail for top", min(TOPN, len(picks)), "(each ~1 min)")
        compose_news_detail(picks, stocks, research)
        log("composing sean / milan views")
        compose_views(picks, stocks, research)
        curate_day_resets(stocks)
        write_report(picks, stocks)

    # ---------- mechanical close-out ----------
    run("py fetch_candles.py", timeout=180)
    rc, o = run("py build_dashboard.py", timeout=300)
    if rc != 0:
        log("final build FAILED:\n" + o[-400:]); sys.exit(1)
    if DRY:
        log("--dry: skip git push")
    else:
        run("git add ollama_picks.json news_detail.json sean_analysis.json milan_analysis.json "
            "day_resets.json dashboard/data/*.json dashboard/data.json dashboard/dates.json "
            "dashboard/index.html dashboard/candles.json", timeout=60)
        top = ", ".join(p["symbol"] for p in picks[:2]) or "none"
        run('git commit -m "ollama picks: %s — top: %s"' % (DATE, top), timeout=60)
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
