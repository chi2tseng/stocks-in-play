import os, subprocess, csv

DIR = r'D:\SIPs'

syms = []
with open(os.path.join(DIR, 'candidates.csv'), 'r', encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        syms.append(r['Symbol'])

print(f'Running tv-scrape.js for {len(syms)} symbols...')
cmd = ['node', os.path.join(DIR, 'tv-scrape.js')] + syms
result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
print(result.stdout)
if result.stderr:
    print('ERRORS:', result.stderr)
