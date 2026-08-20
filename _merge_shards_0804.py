# -*- coding: utf-8 -*-
"""Merge the 8/4 late-sweep news shards into news_detail.json."""
import json, io, os

SHARDS = ['news_shard_energy.json', 'news_shard_consumer.json', 'news_shard_fintech.json']
EXTRA = [('sean_new3.json', 'sean_analysis.json'), ('milan_new3.json', 'milan_analysis.json')]

with io.open('news_detail.json', encoding='utf-8') as f:
    nd = json.load(f)

merged = []
for p in SHARDS:
    if not os.path.exists(p):
        print('[warn] missing shard: %s' % p)
        continue
    with io.open(p, encoding='utf-8') as f:
        d = json.load(f)
    for sym, rec in d.items():
        old = (nd.get(sym) or {}).get('detail') or ''
        new = rec.get('detail') or ''
        if len(new) > len(old):          # never shrink an existing longer write-up
            nd[sym] = rec
            merged.append(sym)
with io.open('news_detail.json', 'w', encoding='utf-8') as f:
    json.dump(nd, f, ensure_ascii=False, indent=2)
print('news_detail merged %d: %s' % (len(merged), ','.join(merged)))

for src, dst in EXTRA:
    if not os.path.exists(src):
        print('[warn] missing: %s' % src)
        continue
    with io.open(dst, encoding='utf-8') as f:
        base = json.load(f)
    with io.open(src, encoding='utf-8') as f:
        base.update(json.load(f))
    with io.open(dst, 'w', encoding='utf-8') as f:
        json.dump(base, f, ensure_ascii=False, indent=2)
    print('%s -> %s (%d total)' % (src, dst, len(base)))
