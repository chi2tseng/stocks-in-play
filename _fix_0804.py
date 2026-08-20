import csv,io,json,urllib.request
FIX={'CMI':-7.22,'GWW':-5.20,'AME':5.43,'ROK':-4.39,'IDXX':4.08,'ADM':3.15,'TDG':3.07,'Q':7.28,
     'FIS':-6.81,'DD':-5.15,'ENTG':7.56,'ZBRA':9.95,'LDOS':5.29,'RVTY':-3.66,
     'AMAT':5.17,'ASML':2.92,'DELL':3.78,'AMZN':-2.33,'MRK':0.88,'PFE':-0.12}
PRICE={'CMI':602.0,'GWW':1300.0,'AME':257.0,'ROK':459.86,'IDXX':591.0,'ADM':80.52,'TDG':1325.0,'Q':143.0,
       'FIS':41.73,'DD':134.0,'ENTG':134.67,'ZBRA':320.66,'LDOS':125.0,'RVTY':111.0,
       'AMAT':545.0,'ASML':1690.45,'DELL':445.24,'AMZN':277.40,'MRK':128.9,'PFE':25.0}
def pre(sym):
    u=f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=1d&interval=5m&includePrePost=true'
    r=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'})
    d=json.load(urllib.request.urlopen(r,timeout=15))
    m=d['chart']['result'][0]['meta']
    prev=m.get('chartPreviousClose') or m.get('previousClose')
    q=d['chart']['result'][0]['indicators']['quote'][0]['close']
    last=[c for c in q if c is not None]
    if not last or not prev: return None
    return round(last[-1],2), round((last[-1]/prev-1)*100,2)
rows=list(csv.DictReader(io.open('candidates.csv',encoding='utf-8-sig')))
for r in rows:
    s=r['Symbol']
    if r['Session']!='headline' or r['SessionDate']!='2026-08-04': continue
    if s in FIX:
        r['ChgPct']=FIX[s]; r['Last']=PRICE[s]
    elif s=='BMY':
        p=pre(s)
        if p: r['Last'],r['ChgPct']=p
    r['Direction']='up' if float(r['ChgPct'])>=0 else 'down'
w=csv.DictWriter(io.open('candidates.csv','w',encoding='utf-8-sig',newline=''),fieldnames=list(rows[0].keys()))
w.writeheader(); w.writerows(rows)
for r in rows:
    if r['Session']=='headline' and r['SessionDate']=='2026-08-04':
        print(f"{r['Symbol']:<6}{float(r['ChgPct']):>8.2f}%  {r['Direction']}")
