import re, json
lines = open('_et.txt', encoding='utf-8', errors='replace').read().split('\n')
pat = re.compile(r'^\s{2}(\S+)\s+(\S+)\s+\$(\S+)\s+\$(\d+)B\s+(\S+)\s+(.*)$')
rows, labs = [], {}
for l in lines:
    m = pat.match(l)
    if not m:
        continue
    sym, chg, last, cap, lab, name = m.groups()
    labs[lab] = labs.get(lab, 0) + 1
    rows.append(dict(sym=sym, chg=chg, last=last, cap=int(cap), lab=lab, name=name.strip()))
print('LABELS:', labs)
pub = [r for r in rows if 'pre-market' in r['lab'] or 'yesterday' in r['lab'] or 'not-supplied' in r['lab']]
print('PUBLISHED:', len(pub))
for r in sorted(pub, key=lambda x: -abs(float(x['chg'].rstrip('%')) if x['chg'].endswith('%') else 0)):
    print('%-7s %8s %10s %5dB %-22s %s' % (r['sym'], r['chg'], r['last'], r['cap'], r['lab'], r['name'][:32]))
json.dump(pub, open('_et_pub.json', 'w'), indent=1)
