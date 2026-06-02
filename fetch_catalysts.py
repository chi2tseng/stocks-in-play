import os, json, csv, urllib.request, time

DIR = r'D:\SIPs'

# Load candidates
candidates = []
with open(os.path.join(DIR, 'candidates.csv'), 'r', encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        candidates.append(r['Symbol'])

# Load catalysts_today
today_path = os.path.join(DIR, 'catalysts_today.json')
if os.path.exists(today_path):
    with open(today_path, 'r', encoding='utf-8') as f:
        catalysts_today = json.load(f)
else:
    catalysts_today = {}

# We won't parse build_report.py hardcoded dict, we'll just fetch for ALL missing from catalysts_today
# to ensure we have something for each.
for sym in candidates:
    if sym not in catalysts_today:
        url = f'https://query1.finance.yahoo.com/v1/finance/search?q={sym}&newsCount=2'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.load(r)
                news = data.get('news', [])
                if news:
                    title = news[0]['title']
                    catalysts_today[sym] = {'Type': 'news', 'Catalyst': title}
                else:
                    catalysts_today[sym] = {'Type': 'momentum', 'Catalyst': 'No recent news found, momentum move.'}
        except Exception as e:
            catalysts_today[sym] = {'Type': 'momentum', 'Catalyst': f'Error fetching news: {e}'}
        time.sleep(0.1)

with open(today_path, 'w', encoding='utf-8') as f:
    json.dump(catalysts_today, f, ensure_ascii=False, indent=2)

print(f'Populated catalysts_today.json with {len(catalysts_today)} entries.')
