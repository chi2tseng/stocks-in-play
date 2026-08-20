import csv,io,json,urllib.request,os
DATE='2026-08-04'
NEW={
 # sym: (catalyst_zh, Type, ER)
 'CMI':('調整後 EPS $6.94 不如預期 $7.33,但營收 $95 億優於預期、年增 9%,全年營收指引上調 10-13%','earnings',True),
 'GWW':('EPS $12.01 優於預期 $11.28、營收 $50.2 億優於預期,上調全年獲利指引至 $45.50-47.25','earnings',True),
 'AME':('調整後 EPS $2.09 年增 17% 優於預期 $1.99,營收年增 15%,連兩季上調全年 EPS 指引至 $8.20-8.30','earnings',True),
 'ROK':('調整後 EPS $3.49 優於預期、營收 $23.13 億年增 8% 優於預期,上調全年 EPS 指引至 $13.00-13.30','earnings',True),
 'IDXX':('EPS $4.27 優於預期 $3.95、營收 $12.17 億年增 10% 優於預期,上調全年 EPS 指引至 $14.69-14.94','earnings',True),
 'ADM':('調整後 EPS $1.84 遠優於預期 $1.44,營收 $226.8 億年增 7.2% 優於預期','earnings',True),
 'TDG':('調整後 EPS $10.87 優於預期 $10.30、營收 $27.41 億年增 23%,上調全年 EPS 指引至 $40.62-41.46','earnings',True),
 'Q':('Q2 調整後 EPS $1.19 年增 53%、營收 $14.29 億年增 22%,並上修全年財測','earnings',True),
 'FIS':('Q2 調整後 EPS $1.48 年增 8.8%、營收約 $34 億年增 29%,但下修法人事業成長展望','earnings',True),
 'DD':('Q2 調整後 EPS $1.88 優於去年 $1.27、營收 $18.19 億,雖上修財測股價仍重挫','earnings',True),
 'ENTG':('Q2 調整後 EPS $0.93 優於預期 $0.82、營收 $8.83 億優於預期 $8.35 億','earnings',True),
 'ZBRA':('Q2 調整後 EPS $6.35 遠優於去年 $3.61、營收 $15.6 億年增 20%,大幅上修全年財測','earnings',True),
 'LDOS':('Q2 營收 $45.6 億年增 7%、調整後 EPS $3.26 優於去年 $3.21,並上修全年展望','earnings',True),
 'RVTY':('Q2 調整後 EPS $1.41、營收 $7.3 億僅年增 1.4%,含 $0.11 退稅挹注,財測偏保守','earnings',True),
 'AMAT':('高盛 8/3 將 AMAT 納入美股 Conviction List(同步剔除 AVGO),激勵股價領漲半導體','analyst',False),
 'ASML':('高盛 8/3 將 ASML 納入歐股 Conviction List,激勵股價領漲','analyst',False),
 'DELL':('Bloomberg 報導 NVIDIA 與 Dell 共同投資 AI 雲端新創 Volta,估值 24 億美元','news',False),
 'AMZN':('Bezos 依 10b5-1 計畫擬出售 1,500 萬股(約 41 億美元),持股降至約 8.1%','news',False),
 'MRK':('Q2 營收 $166.1 億優於預期,上調全年營收指引至 $663-673 億;認列 Terns 收購 $57 億費用致 EPS 下修','earnings',True),
 'PFE':('Q2 營收與獲利雙雙優於預期,上調全年營收指引中值 5 億美元','earnings',True),
 'BMY':('傳與 AstraZeneca 洽談規模達 4,000 億美元的合併案(FT/彭博 8/2 報導)','M&A',False),
}
def quote(sym):
    u=f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=2d&interval=1d&includePrePost=true'
    try:
        r=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'})
        d=json.load(urllib.request.urlopen(r,timeout=15))
        m=d['chart']['result'][0]['meta']
        last=m.get('postMarketPrice') or m.get('preMarketPrice') or m.get('regularMarketPrice')
        prev=m.get('chartPreviousClose') or m.get('previousClose')
        vol=m.get('regularMarketVolume') or 0
        return round(last,2), round((last/prev-1)*100,2), int(vol), m.get('shortName') or sym
    except Exception as e:
        print('[warn]',sym,e); return None
rows=list(csv.DictReader(io.open('candidates.csv',encoding='utf-8-sig')))
have={r['Symbol'] for r in rows}
fn=list(rows[0].keys())
added=[]
for s,(cat,ty,er) in NEW.items():
    if s in have: print('[skip in-csv]',s); continue
    q=quote(s)
    if not q: continue
    last,chg,vol,name=q
    rows.append({'Symbol':s,'Last':last,'ChgPct':chg,'Volume':vol,'Session':'headline','SessionDate':DATE,'Direction':'up' if chg>=0 else 'down','Name':name})
    added.append((s,chg))
w=csv.DictWriter(io.open('candidates.csv','w',encoding='utf-8-sig',newline=''),fieldnames=fn)
w.writeheader(); w.writerows(rows)
print('added',len(added),added)
# catalysts
cj=json.load(io.open('catalysts_today.json',encoding='utf-8')) if os.path.exists('catalysts_today.json') else {}
for s,(cat,ty,er) in NEW.items():
    cj[s]={'Catalyst':cat,'Type':ty,'EarningsReaction':er}
json.dump(cj,io.open('catalysts_today.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
print('catalysts now',len(cj))
