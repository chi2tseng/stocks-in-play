# model_predict.py — 把 v12 模型預測注入 dashboard 日包(s.modelPred)
# 用法: py model_predict.py [--date YYYY-MM-DD]   (預設 dates.json 最新)
# 每次 build_dashboard.py 之後執行(build 會自動呼叫);冪等,可重跑。
# 模型係數在 model_params.json(由模型迭代管線導出;勿手改)。
import json, math, os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))

def load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)

def tier_of(mcap_M):
    if not mcap_M: return 'na'
    lm = math.log10(mcap_M)
    return 'big' if lm >= 4 else ('mid' if lm >= 3.3 else 'small')

def hinge(w, g):
    return w[0] + w[1]*g + w[2]*max(g-15, 0) + w[3]*max(-15-g, 0)

def derive_traj(ch):
    # surp_trend / eps_accel(同模型管線 chart_factors.py 定義)
    li = ch.get('latest_idx')
    er = ch.get('eps_reported') or []; ee = ch.get('eps_estimate') or []
    if li is None or li < 1: return None, None
    def at(a, i): return a[i] if 0 <= i < len(a) else None
    surps = []
    for i in range(max(0, li-3), li+1):
        e_, est = at(er, i), at(ee, i)
        if e_ is not None and est and est > 0:
            surps.append((e_/est-1)*100)
    st = (surps[-1] - sum(surps[:-1])/len(surps[:-1])) if len(surps) >= 3 else None
    def yoy(c, p):
        return (c/p-1)*100 if (c is not None and p and p > 0) else None
    y_now = yoy(at(er, li), at(er, li-4)); y_prev = yoy(at(er, li-1), at(er, li-5))
    ac = (y_now - y_prev) if (y_now is not None and y_prev is not None) else None
    return st, ac

def spike_table():
    """盤中最高預測(2026-08-07 R11-R12 重建):spike = 高點 vs 開盤價。
    12 輪盲測結論:type×tier 分桶經驗分位數(P25/P50/P75)IC 0.341、
    P25-P75 帶內率 50%(校準完美),勝過所有回歸與 gap 線性 hi 模型(那是 gap 回聲)。
    從 model_events.json 即時計算 — 事件庫每天 ingest 長大,表自動更新。"""
    try:
        ev = load(os.path.join(ROOT, 'model_events.json'))
    except Exception:
        return {}
    buckets = {}
    for e in ev:
        g, hi = e.get('gap'), e.get('hi')
        if g is None or hi is None or abs(g) > 100: continue
        sp = ((1 + hi/100) / (1 + g/100) - 1) * 100
        if not (-5 <= sp <= 300): continue
        sp = min(max(sp, 0), 80)
        lm = e.get('log_mcap')
        t = tier_of(10**lm if lm else None)
        buckets.setdefault((e['type'], t), []).append(sp)
        buckets.setdefault((e['type'],), []).append(sp)
        buckets.setdefault('_g', []).append(sp)
    def q(vs):
        vs = sorted(vs)
        return [round(vs[int(len(vs)*p)], 1) for p in (0.25, 0.5, 0.75)]
    return {k: q(v) for k, v in buckets.items() if k == '_g' or len(v) >= 25}

def load_spike_gbm():
    """逐檔盤中最高模型(model_spike.pkl,由 model_lab spikefit 訓練;R15-R17)。
    載入失敗回 None → fallback 到 spike_table 分桶。"""
    try:
        import pickle
        with open(os.path.join(ROOT, 'model_spike.pkl'), 'rb') as f:
            return pickle.load(f)
    except Exception:
        return None

def spike_from_gbm(SM, s, gap, typ, tier):
    """packet stock → 事件同構特徵 → GBM p50 + conformal 帶。訓練/推論欄位對映:
    chgPct→gap、marketCap_M→log_mcap、shortRatio/shortFloat/floatShares_M/volume 同名、
    tv.surprise*→*_surp、tv.*YoY→*_yoy;fwd/perf 缺就 NaN(HistGBR 原生吃 NaN)。"""
    try:
        import math as _m
        tv = s.get('tv') or {}
        vol, fl = s.get('volume'), s.get('floatShares_M')
        e = dict(gap=gap, type=typ,
                 rot=_m.log10(max(vol/(fl*1e6), 1e-6)) if (vol and fl and fl > 0) else None,
                 log_mcap=_m.log10(s['marketCap_M']) if s.get('marketCap_M') else None,
                 short_ratio=s.get('shortRatio'), short_float=s.get('shortFloat'),
                 float_M=fl, volume=vol,
                 eps_surp=tv.get('surpriseEPS_pct'), rev_surp=tv.get('surpriseRev_pct'),
                 eps_yoy=tv.get('epsYoY_pct'), rev_yoy=tv.get('yrYrRev_pct'),
                 fwd_eps=None, fwd_rev=None,
                 perf1M=s.get('perf1M'), perf3M=s.get('perf3M'),
                 er=1 if typ == 'earnings' else 0)
        import model_lab as _ML
        x = _ML.spike_feats(e, SM['types'])
        p50 = max(float(SM['model'].predict([x])[0]), 0.0)
        lo, hi = SM['rq'].get(tier, SM['rg'])
        return [round(max(p50 + lo, 0), 1), round(p50, 1), round(p50 + hi, 1)]
    except Exception:
        return None

def predict(s, P, SP=None, SM=None):
    gap = s.get('chgPct')
    if gap is None: return None
    typ = (s.get('type') or 'unknown').lower()
    tier = tier_of(s.get('marketCap_M'))
    w = P['seg'].get(f'{typ}|{tier}') or P['type'].get(typ) or P['global_w']
    p = hinge(w, gap)
    # rot 修正:僅 small gap-up
    vol, fl = s.get('volume'), s.get('floatShares_M')
    if tier == 'small' and gap >= 2 and abs(gap) <= 100 and vol and fl and fl > 0:
        rot = math.log10(max(vol/(fl*1e6), 1e-6))
        p += P['rot'][0] + P['rot'][1]*rot
    # 財報基本面門控
    tv = s.get('tv') or {}
    if typ == 'earnings':
        rs = tv.get('surpriseRev_pct')
        if rs is not None:
            p += P['fund']['rev_big'] if rs > 5 else P['fund']['rev_small']
        ch = tv.get('chart')
        if ch:
            st, ac = derive_traj(ch)
            if st is not None: p += P['fund']['st_hi'] if st > 5 else P['fund']['st_lo']
            if ac is not None: p += P['fund']['ac_hi'] if ac > 10 else P['fund']['ac_lo']
    # 盤中最高:優先逐檔 GBM(R15-R17,桶內 IC +0.206);失敗才退分桶常數
    sq = None
    if SM:
        sq = spike_from_gbm(SM, s, gap, typ, tier)
    if sq is None and SP:
        sq = SP.get((typ, tier)) or SP.get((typ,)) or SP.get('_g')
    out = dict(version=P.get('version', 'v12'), gap=round(gap, 2), predDay=round(p, 1),
               band=P['bands'].get(tier, P['bands']['na']), tier=tier)
    if sq:
        # 換算為 vs 昨收:(1+gap)(1+spike)−1;同時保留 spike(開盤後再衝)供對帳
        def to_pc(sp): return round(((1 + gap/100) * (1 + sp/100) - 1) * 100, 1)
        out['spike'] = sq                       # [P25, P50, P75] vs 開盤
        out['predHi'] = to_pc(sq[1])            # 中位 vs 昨收
        out['predHiBand'] = [to_pc(sq[0]), to_pc(sq[2])]
    # Setup 旗標(可複數;各自獨立分類,回測見 SKILL §8.2 模型預測段)
    flags = []
    if typ == 'contract' and gap >= 15:
        flags.append('contract_fade')
    try:
        dtc = float(s.get('shortRatio') or 0)
    except (TypeError, ValueError):
        dtc = 0
    if dtc > 5 and gap >= 2:
        flags.append('dtc_squeeze')
    # growth_29(雙成長)2026-08-05 使用者指示自卡面移除;回測結論留在迭代日誌,不出旗標
    if flags:
        out['flags'] = flags
        out['flag'] = flags[0]   # 舊欄位相容
    return out

def apply_qual(out, sym, qual):
    """質化調整層(2026-08-06 使用者:「更多質化分析,不要非黑即白」)。
    model_qual.json 由主模型於每日 /SIPs 撰寫:{SYM:{adj, confidence, reasoning, date}}。
    adj = 對 predDay 的連續調整(clamp ±8);reasoning = 為什麼這檔會偏離量化基準。
    predDay 保留量化值(predQuant),最終值 = 量化 + 質化 — verify 會分開追蹤兩者。"""
    q = (qual or {}).get(sym)
    if not q or q.get('adj') is None:
        return out
    adj = max(-8.0, min(8.0, float(q['adj'])))
    out['predQuant'] = out['predDay']
    out['predDay'] = round(out['predDay'] + adj, 1)
    out['qual'] = dict(adj=round(adj, 1), confidence=q.get('confidence'),
                       reasoning=(q.get('reasoning') or '')[:220])
    return out

def main():
    P = load(os.path.join(ROOT, 'model_params.json'))
    SP = spike_table()
    SM = load_spike_gbm()
    if SM: print(f"[model_predict] spike GBM loaded ({SM.get('version')}, n={SM.get('n')})")
    else: print('[model_predict] spike GBM 缺,退分桶 fallback')
    date = None
    if '--date' in sys.argv:
        date = sys.argv[sys.argv.index('--date')+1]
    else:
        dates = load(os.path.join(ROOT, 'dashboard', 'dates.json'))
        date = dates[0]['date'] if isinstance(dates, list) else dates['dates'][0]['date']
    pk_path = os.path.join(ROOT, 'dashboard', 'data', f'{date}.json')
    d = load(pk_path)
    qual_all = load(os.path.join(ROOT, 'model_qual.json')) or {}
    qual = {k: v for k, v in qual_all.items() if isinstance(v, dict) and v.get('date') == date}
    n, nq = 0, 0
    for sym, s in (d.get('stocks') or {}).items():
        mp = predict(s, P, SP, SM)
        if mp:
            mp = apply_qual(mp, sym, qual)
            if mp.get('qual'): nq += 1
            s['modelPred'] = mp; n += 1
            # ex-ante 凍結(2026-08-23):掃描當下這份預測只寫一次,之後任何 rebuild 或
            # sidecar 盤前刷新都不得覆寫。先前 modelPred 被三方輪流改寫,同一天 verify
            # 會因執行順序給出不同結論(8/21 在 43% 與 34% 之間跳動)。
            s.setdefault('modelPredScan', json.loads(json.dumps(mp)))
    with open(pk_path, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False)
    # data.json mirror 同日才同步
    dj_path = os.path.join(ROOT, 'dashboard', 'data.json')
    try:
        dj = load(dj_path)
        if dj.get('date', '')[:10] == date:
            for sym, s in (dj.get('stocks') or {}).items():
                mp = predict(s, P, SP, SM)
                if mp:
                    mp = apply_qual(mp, sym, qual)
                    s['modelPred'] = mp
            with open(dj_path, 'w', encoding='utf-8') as f:
                json.dump(dj, f, ensure_ascii=False)
    except Exception as e:
        print(f'[model_predict] mirror skip: {e}')
    print(f'[model_predict] {date}: modelPred injected into {n} stocks ({nq} with qual overlay)')

if __name__ == '__main__':
    main()
