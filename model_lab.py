# model_lab.py — 模型日常維護三件套(2026-08-06 使用者:「每次都去驗證並且改進模型」)
#
#   py model_lab.py ingest [DATE]   # 把某日 packet(預設=最新已收盤日)收進 model_events.json
#   py model_lab.py verify [DATE]   # 對照 modelPred vs 實際,誤差歸因,寫 model_track_record.json
#   py model_lab.py refit           # v12 全資料重擬合 + 嚴格 walk-forward 盲測;變好才更新 model_params.json
#
# /SIPs 每日流程:開跑先 verify 昨日(結果進 brief);週五或 verify 連兩日出現分層偏差 ≥2pt 時 refit。
# 資料:model_events.json(事件庫)、model_bars_cache.json(日K,gitignored)、model_track_record.json。
import json, os, sys, math, time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36'}
KNOT = 15.0

def jload(p, default=None):
    if not os.path.exists(p): return default
    with open(p, encoding='utf-8') as f: return json.load(f)

def jsave(p, obj):
    with open(p, 'w', encoding='utf-8') as f: json.dump(obj, f, ensure_ascii=False)

# ---------- 日K ----------
def fetch_bars(sym, p1='2026-02-01'):
    t1 = int(datetime.strptime(p1, '%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp())
    t2 = int(time.time()) + 86400
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={t1}&period2={t2}&interval=1d'
    for _ in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15) as r:
                d = json.load(r)
            res = d['chart']['result'][0]
            ts = res['timestamp']; q = res['indicators']['quote'][0]
            out = {}
            for i, t in enumerate(ts):
                if q['open'][i] is None or q['close'][i] is None: continue
                day = datetime.fromtimestamp(t, tz=timezone.utc).strftime('%Y-%m-%d')
                out[day] = [round(q['open'][i],4), round(q['high'][i],4), round(q['low'][i],4), round(q['close'][i],4)]
            return sym, out
        except Exception:
            time.sleep(1)
    return sym, None

def refresh_bars(syms):
    cache = jload('model_bars_cache.json', {})
    with ThreadPoolExecutor(max_workers=8) as ex:
        for sym, bars in ex.map(fetch_bars, syms):
            if bars:
                if cache.get(sym): cache[sym].update(bars)
                else: cache[sym] = bars
    jsave('model_bars_cache.json', cache)
    return cache

def outcomes(cache, sym, date):
    b = cache.get(sym)
    if not b or date not in b: return None
    days = sorted(b); i = days.index(date)
    if i == 0: return None
    o, h, l, c = b[date]; pc = b[days[i-1]][3]
    if not pc or not o: return None
    return dict(gap=round((o/pc-1)*100,2), day=round((c/pc-1)*100,2), intra=round((c/o-1)*100,2),
                ext=round((h/o-1)*100,2), hi=round((h/pc-1)*100,2))

def tier_of(mcap_M):
    if not mcap_M: return 'na'
    lm = math.log10(mcap_M)
    return 'big' if lm >= 4 else ('mid' if lm >= 3.3 else 'small')

# ---------- ingest ----------
def latest_completed_date():
    dates = jload(os.path.join('dashboard', 'dates.json'))
    lst = dates if isinstance(dates, list) else dates.get('dates')
    today_et = datetime.now(timezone.utc)
    # 收盤 20:00 UTC;未過收盤的日期不算完成
    for d in lst:
        dt = d['date']
        if dt < today_et.strftime('%Y-%m-%d') or (dt == today_et.strftime('%Y-%m-%d') and today_et.hour >= 21):
            return dt
    return lst[-1]['date']

def cmd_ingest(date):
    pk = jload(os.path.join('dashboard', 'data', f'{date}.json'))
    if not pk: print(f'[ingest] no packet {date}'); return
    ev = jload('model_events.json', [])
    have = {(e['sym'], e['date']) for e in ev}
    stocks = pk.get('stocks') or {}
    cache = refresh_bars(sorted(stocks))
    n = 0
    for sym, s in stocks.items():
        if (sym, date) in have: continue
        o = outcomes(cache, sym, date)
        if not o: continue
        tv = s.get('tv') or {}
        mcap = s.get('marketCap_M')
        e = dict(sym=sym, date=date, type=(s.get('type') or 'unknown').lower(),
                 er=1 if s.get('earningsReaction') else 0,
                 session=s.get('primarySession') or 'pre',
                 eps_surp=tv.get('surpriseEPS_pct'), rev_surp=tv.get('surpriseRev_pct'),
                 eps_yoy=tv.get('epsYoY_pct'), rev_yoy=tv.get('yrYrRev_pct'),
                 log_mcap=math.log10(mcap) if mcap else None,
                 short_float=s.get('shortFloat'), short_ratio=s.get('shortRatio'),
                 float_M=s.get('floatShares_M'), volume=s.get('volume'),
                 picks={}, ct_pct=None, src='daily')
        e.update(o); e['next'] = None
        ev.append(e); n += 1
    jsave('model_events.json', ev)
    print(f'[ingest] {date}: +{n} events -> total {len(ev)}')

# ---------- v12 擬合(同 scratchpad v11/v12 定義)----------
def _design(g):
    return [1.0, g, max(g-KNOT, 0), max(-KNOT-g, 0)]

def _lstsq(X, y):
    import numpy as np
    X = np.asarray(X, float); y = np.asarray(y, float)
    w, *_ = np.linalg.lstsq(X, y, rcond=None)
    return w

def robust_hinge_fit(pairs):
    import numpy as np
    pairs = [(g, y) for g, y in pairs if abs(g) <= 100]
    if len(pairs) < 40: return None
    X = [ _design(g) for g, _ in pairs ]
    y = np.clip([y for _, y in pairs], -60, 60)
    w = _lstsq(X, y)
    r = y - np.asarray(X) @ w
    mad = float(np.median(np.abs(r - np.median(r)))) or 1.0
    keep = np.abs(r) <= 4*1.4826*mad
    if keep.sum() >= 40:
        w = _lstsq(np.asarray(X)[keep], y[keep])
    return [round(float(x), 4) for x in w]

def fit_params(ev):
    import numpy as np
    for e in ev:
        e['tier'] = tier_of(10**e['log_mcap'] if e.get('log_mcap') else None)
        v, fl = e.get('volume'), e.get('float_M')
        e['rot'] = math.log10(max(v/(fl*1e6), 1e-6)) if (v and fl and fl > 0) else None
    P = dict(version='v12', knot=KNOT, generated=datetime.now(timezone.utc).strftime('%Y-%m-%d'),
             seg={}, type={}, global_w=None, rot=None, fund={}, hi={}, hi_global=None, bands={})
    segs = {}
    for e in ev: segs.setdefault((e['type'], e['tier']), []).append(e)
    for k, sub in segs.items():
        w = robust_hinge_fit([(x['gap'], x['day']) for x in sub])
        if w: P['seg'][f'{k[0]}|{k[1]}'] = w
    tsegs = {}
    for e in ev: tsegs.setdefault(e['type'], []).append(e)
    for k, sub in tsegs.items():
        w = robust_hinge_fit([(x['gap'], x['day']) for x in sub])
        if w: P['type'][k] = w
    P['global_w'] = robust_hinge_fit([(e['gap'], e['day']) for e in ev])
    def base(e):
        w = P['seg'].get(f"{e['type']}|{e['tier']}") or P['type'].get(e['type']) or P['global_w']
        return sum(a*b for a, b in zip(w, _design(e['gap'])))
    s = [e for e in ev if e.get('rot') is not None and e['gap'] >= 2 and e['tier'] == 'small' and abs(e['gap']) <= 100]
    if len(s) > 60:
        x = np.array([e['rot'] for e in s]); r = np.array([np.clip(e['day'], -60, 60) - base(e) for e in s])
        c1, c0 = np.polyfit(x, r, 1); P['rot'] = [round(float(c0), 4), round(float(c1), 4)]
    else:
        P['rot'] = [0.0, 0.0]
    for key, cond in [('rev_big', lambda e: (e.get('rev_surp') or 0) > 5),
                      ('rev_small', lambda e: e.get('rev_surp') is not None and e['rev_surp'] <= 5),
                      ('fwd_hi', lambda e: (e.get('fwd_eps') or -999) > 20),
                      ('fwd_lo', lambda e: e.get('fwd_eps') is not None and e['fwd_eps'] <= 20),
                      ('st_hi', lambda e: (e.get('surp_trend') or -999) > 5),
                      ('st_lo', lambda e: e.get('surp_trend') is not None and e['surp_trend'] <= 5),
                      ('ac_hi', lambda e: (e.get('eps_accel') or -999) > 10),
                      ('ac_lo', lambda e: e.get('eps_accel') is not None and e['eps_accel'] <= 10)]:
        sub = [np.clip(e['day'], -40, 40) - base(e) for e in ev if e['type'] == 'earnings' and cond(e)]
        P['fund'][key] = round(float(np.median(sub)), 3) if len(sub) > 40 else 0.0
    for kind in ('earnings', 'contract'):
        sub = [e for e in ev if e['type'] == kind and e.get('hi') is not None and abs(e['gap']) <= 100]
        if len(sub) > 60:
            b, a = np.polyfit([e['gap'] for e in sub], np.clip([e['hi'] for e in sub], -40, 80), 1)
            P['hi'][kind] = [round(float(a), 3), round(float(b), 3)]
    sub = [e for e in ev if e.get('hi') is not None and abs(e['gap']) <= 100]
    b, a = np.polyfit([e['gap'] for e in sub], np.clip([e['hi'] for e in sub], -40, 80), 1)
    P['hi_global'] = [round(float(a), 3), round(float(b), 3)]
    for t in ('big', 'mid', 'small', 'na'):
        errs = [e['day'] - base(e) for e in ev if e['tier'] == t]
        if errs:
            P['bands'][t] = [round(float(np.percentile(errs, 25)), 1), round(float(np.percentile(errs, 75)), 1)]
    return P

def predict_with(P, e):
    w = P['seg'].get(f"{e['type']}|{e['tier']}") or P['type'].get(e['type']) or P['global_w']
    p = sum(a*b for a, b in zip(w, _design(e['gap'])))
    if P.get('rot') and e.get('rot') is not None and e['gap'] >= 2 and e['tier'] == 'small':
        p += P['rot'][0] + P['rot'][1]*e['rot']
    if e['type'] == 'earnings':
        f = P.get('fund') or {}
        if e.get('rev_surp') is not None:
            p += f.get('rev_big', 0) if e['rev_surp'] > 5 else f.get('rev_small', 0)
        if e.get('fwd_eps') is not None:
            p += f.get('fwd_hi', 0) if e['fwd_eps'] > 20 else f.get('fwd_lo', 0)
        if e.get('surp_trend') is not None:
            p += f.get('st_hi', 0) if e['surp_trend'] > 5 else f.get('st_lo', 0)
        if e.get('eps_accel') is not None:
            p += f.get('ac_hi', 0) if e['eps_accel'] > 10 else f.get('ac_lo', 0)
    return p

def blind_eval(ev):
    """嚴格 walk-forward 5 段盲測,回 (hit%, rho, tier_hits)。"""
    import numpy as np
    dates = sorted(set(e['date'] for e in ev))
    blocks = np.array_split(np.array(dates), 6)
    hs, th, rhos = [], {}, []
    def spear(a, b):
        a, b = np.asarray(a, float), np.asarray(b, float)
        def rk(v):
            s = np.argsort(v); r_ = np.empty(len(v)); r_[s] = np.arange(len(v)); return r_
        n = len(a)
        return float(1-6*np.sum((rk(a)-rk(b))**2)/(n*(n*n-1))) if n > 19 else 0.0
    for i in range(1, 6):
        tr = [e for e in ev if e['date'] in set(np.concatenate(blocks[:i]))]
        te = [e for e in ev if e['date'] in set(blocks[i])]
        if len(te) < 30: continue
        P = fit_params([dict(x) for x in tr])
        pred = np.array([predict_with(P, e) for e in te]); act = np.array([e['day'] for e in te])
        h = np.abs(pred-act) <= np.maximum(3.0, 0.25*np.abs(pred))
        hs.append(h.mean()*100); rhos.append(spear(pred, act))
        for t in ('big', 'mid', 'small', 'na'):
            idx = [j for j, e in enumerate(te) if e['tier'] == t]
            if idx: th.setdefault(t, []).append(h[idx].mean()*100)
    return (round(float(np.mean(hs)), 1), round(float(np.mean(rhos)), 3),
            {t: round(float(np.mean(v)), 1) for t, v in th.items()})

# ---------- verify ----------
def cmd_verify(date):
    import numpy as np
    pk = jload(os.path.join('dashboard', 'data', f'{date}.json'))
    if not pk: print(f'[verify] no packet {date}'); return
    stocks = {k: v for k, v in (pk.get('stocks') or {}).items() if v.get('modelPred')}
    cache = refresh_bars(sorted(stocks))
    rows = []
    for sym, s in stocks.items():
        o = outcomes(cache, sym, date)
        if not o: continue
        mp = s['modelPred']
        pq = mp.get('predQuant', mp['predDay'])   # 純量化值(質化層調整前)
        rows.append(dict(sym=sym, tier=mp.get('tier', 'na'), type=(s.get('type') or '?').lower(),
                         gap_pred_base=mp.get('gap'), gap_real=o['gap'],
                         pred=mp['predDay'], pred_quant=pq, qual=1 if mp.get('qual') else 0,
                         act=o['day'], err=round(o['day']-mp['predDay'], 1),
                         err_quant=round(o['day']-pq, 1),
                         hit=1 if abs(o['day']-mp['predDay']) <= max(3.0, 0.25*abs(mp['predDay'])) else 0))
    if not rows: print('[verify] no verifiable rows'); return
    errs = np.array([r['err'] for r in rows]); hits = np.mean([r['hit'] for r in rows])*100
    print(f'=== model verify {date}: n={len(rows)} 命中={hits:.0f}% bias={np.mean(errs):+.2f} MAE={np.mean(np.abs(errs)):.2f} ===')
    for t in ('big', 'mid', 'small', 'na'):
        sub = [r for r in rows if r['tier'] == t]
        if len(sub) >= 5:
            e2 = np.array([r['err'] for r in sub])
            print(f'  {t:5} n={len(sub):>3} 命中={np.mean([r["hit"] for r in sub])*100:>3.0f}% bias={np.mean(e2):+.2f}')
    # 盤前 gap 快照 vs 實際開盤 gap 的落差(預測誤差的最大已知來源)
    gd = [abs((r['gap_pred_base'] or 0) - r['gap_real']) for r in rows if r['gap_pred_base'] is not None]
    print(f'  盤前快照 vs 實際開盤 gap 落差:中位 {np.median(gd):.1f}pt(這部分誤差來自報價時點,非模型係數)')
    worst = sorted(rows, key=lambda r: -abs(r['err']))[:5]
    print('  最大誤差:', ', '.join(f"{r['sym']}({r['err']:+.0f})" for r in worst))
    # 質化層加值追蹤(2026-08-06:主模型的質化調整也要被驗證,加不加值數據說話)
    qr = [r for r in rows if r['qual']]
    if qr:
        mq = np.mean([abs(r['err_quant']) for r in qr]); mf = np.mean([abs(r['err']) for r in qr])
        verdict = '加值' if mf < mq else ('持平' if mf == mq else '減值')
        print(f'  質化層(n={len(qr)}):純量化 MAE {mq:.2f} → 加質化 {mf:.2f}({verdict} {mq-mf:+.2f})')
    rec = jload('model_track_record.json', [])
    rec = [x for x in rec if x.get('date') != date]
    rec.append(dict(date=date, n=len(rows), hit=round(float(hits)), bias=round(float(np.mean(errs)), 2),
                    mae=round(float(np.mean(np.abs(errs))), 2),
                    tiers={t: dict(n=len([r for r in rows if r['tier'] == t]),
                                   bias=round(float(np.mean([r['err'] for r in rows if r['tier'] == t] or [0])), 2))
                           for t in ('big', 'mid', 'small', 'na')},
                    rows=rows))
    rec.sort(key=lambda x: x['date'])
    jsave('model_track_record.json', rec)
    # 漂移警報:同一 tier 連兩日 |bias| >= 2 → 建議 refit
    if len(rec) >= 2:
        for t in ('big', 'mid', 'small'):
            b2 = [x['tiers'].get(t, {}).get('bias', 0) for x in rec[-2:]]
            if all(abs(b) >= 2 and (b > 0) == (b2[0] > 0) for b in b2):
                print(f'[!! MODEL-DRIFT !!] {t} 層連兩日同向偏差 {b2} — 執行 `py model_lab.py refit`')

# ---------- refit ----------
def cmd_refit():
    ev = jload('model_events.json', [])
    for e in ev:
        e['tier'] = tier_of(10**e['log_mcap'] if e.get('log_mcap') else None)
        v, fl = e.get('volume'), e.get('float_M')
        e['rot'] = math.log10(max(v/(fl*1e6), 1e-6)) if (v and fl and fl > 0) else None
    hit, rho, tiers = blind_eval(ev)
    old = jload('model_params.json', {})
    old_score = (old.get('_blind') or {}).get('hit', 0)
    print(f'[refit] blind: hit={hit}% rho={rho} tiers={tiers} (現行記錄 hit={old_score}%)')
    if hit + 0.5 < old_score:
        print('[refit] 新擬合盲測較差,保留現行 model_params.json(記錄本次於 iterations)')
    else:
        P = fit_params(ev)
        P['_blind'] = dict(hit=hit, rho=rho, tiers=tiers, n=len(ev))
        jsave('model_params.json', P)
        print(f'[refit] model_params.json 已更新(n={len(ev)})')
    logs = jload('model_iterations.json', [])
    logs.append(dict(iteration=len(logs)+1, cmd='refit', date=datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                     n=len(ev), blind=dict(hit=hit, rho=rho, tiers=tiers)))
    jsave('model_iterations.json', logs)

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'verify'
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    if cmd == 'ingest': cmd_ingest(arg or latest_completed_date())
    elif cmd == 'verify': cmd_verify(arg or latest_completed_date())
    elif cmd == 'refit': cmd_refit()
    else: print('usage: py model_lab.py ingest|verify|refit [DATE]')
