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

def predict(s, P):
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
    hw = P['hi'].get(typ) or P['hi_global']
    ph = hw[0] + hw[1]*gap
    out = dict(version=P.get('version', 'v12'), gap=round(gap, 2), predDay=round(p, 1),
               predHi=round(ph, 1), band=P['bands'].get(tier, P['bands']['na']), tier=tier)
    if typ == 'contract' and gap >= 15:
        out['flag'] = 'contract_fade'
    return out

def main():
    P = load(os.path.join(ROOT, 'model_params.json'))
    date = None
    if '--date' in sys.argv:
        date = sys.argv[sys.argv.index('--date')+1]
    else:
        dates = load(os.path.join(ROOT, 'dashboard', 'dates.json'))
        date = dates[0]['date'] if isinstance(dates, list) else dates['dates'][0]['date']
    pk_path = os.path.join(ROOT, 'dashboard', 'data', f'{date}.json')
    d = load(pk_path)
    n = 0
    for sym, s in (d.get('stocks') or {}).items():
        mp = predict(s, P)
        if mp:
            s['modelPred'] = mp; n += 1
    with open(pk_path, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False)
    # data.json mirror 同日才同步
    dj_path = os.path.join(ROOT, 'dashboard', 'data.json')
    try:
        dj = load(dj_path)
        if dj.get('date', '')[:10] == date:
            for sym, s in (dj.get('stocks') or {}).items():
                mp = predict(s, P)
                if mp: s['modelPred'] = mp
            with open(dj_path, 'w', encoding='utf-8') as f:
                json.dump(dj, f, ensure_ascii=False)
    except Exception as e:
        print(f'[model_predict] mirror skip: {e}')
    print(f'[model_predict] {date}: modelPred injected into {n} stocks')

if __name__ == '__main__':
    main()
