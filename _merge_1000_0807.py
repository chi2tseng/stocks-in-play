import json, io, os

DST = 'news_detail.json'
d = json.load(io.open(DST, encoding='utf-8'))
before = len(d)

added, short = [], []
for f in ['news_shard_1000_metals.json', 'news_shard_1000_other.json']:
    if not os.path.exists(f):
        print('[skip missing]', f)
        continue
    s = json.load(io.open(f, encoding='utf-8'))
    for k, v in s.items():
        det = (v.get('detail') or '').strip()
        if not det:
            continue
        cur = (d.get(k) or {}).get('detail') or ''
        # 封存保護:既有較長的內容不覆寫(SKILL §8.1)
        if len(cur) > len(det):
            print('[keep existing longer]', k, len(cur), '>', len(det))
            continue
        d[k] = v
        added.append((k, len(det)))
        if len(det) < 300:
            short.append((k, len(det)))

json.dump(d, io.open(DST, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('news_detail:', before, '->', len(d), '| added', len(added))
if short:
    print('[!! still <300 chars !!]', short)
else:
    print('[ok] all merged details >=300 chars')
