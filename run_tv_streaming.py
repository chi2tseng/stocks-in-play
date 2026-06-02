import os, subprocess, csv

DIR = r'D:\SIPs'

syms = []
with open(os.path.join(DIR, 'candidates.csv'), 'r', encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        syms.append(r['Symbol'])

# Filter out symbols that already have the output file
missing_syms = []
for sym in syms:
    if not os.path.exists(os.path.join(DIR, f'{sym}-earnings-fq.md')):
        missing_syms.append(sym)

print(f'Running tv-scrape.js for {len(missing_syms)} missing symbols...')
if not missing_syms:
    import sys; sys.exit(0)

process = subprocess.Popen(['node', os.path.join(DIR, 'tv-scrape.js')] + missing_syms, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
while True:
    line = process.stdout.readline()
    if not line and process.poll() is not None:
        break
    if line:
        print(line.strip())
