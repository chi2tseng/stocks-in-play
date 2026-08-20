import json, io, os

DST = 'news_detail.json'
d = json.load(io.open(DST, encoding='utf-8'))
before = len(d)

added = []
for f in ['news_shard_1000_A.json', 'news_shard_1000_B.json', 'news_shard_1000_C.json']:
    if not os.path.exists(f):
        print('[skip missing]', f)
        continue
    s = json.load(io.open(f, encoding='utf-8'))
    for k, v in s.items():
        if not (v.get('detail') or '').strip():
            continue
        cur = (d.get(k) or {}).get('detail') or ''
        # 封存保護:既有較長的內容不覆寫
        if len(cur) > len(v['detail']):
            print('[keep existing longer]', k, len(cur), '>', len(v['detail']))
            continue
        d[k] = v
        added.append((k, len(v['detail'])))

# TradingView 尚未更新今日財報季度的名字 — 依 SIPs §6.1 在詳解末尾標註
TV_PENDING = ['CRON', 'DEO', 'HIMX', 'IOVA', 'ROIV', 'SABR', 'TIGO', 'UMAC', 'WPP']
NOTE = '\n\n*(註:TradingView 季度資料尚未更新今日公布的最新一季,頁面上的 EPS/營收圖仍為前一季口徑,盤後會再補抓。)*'
for k in TV_PENDING:
    if k in d and isinstance(d[k], dict):
        det = d[k].get('detail') or ''
        if det and 'TradingView 季度資料尚未更新' not in det:
            d[k]['detail'] = det + NOTE

json.dump(d, io.open(DST, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('news_detail:', before, '->', len(d))
for k, n in added:
    print(f'  + {k} {n} chars')
