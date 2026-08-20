import json, io, csv
p='catalysts_today.json'
d=json.load(io.open(p,encoding='utf-8'))
NEW={
"DT":("earnings",True,"FY27 Q1 營收 $5.55 億(+16% YoY)超預期 $5.49 億、非 GAAP EPS $0.48 高於財測 $0.44-0.45,ARR $21.36 億 +17%;匯率拖累小幅下修全年展望"),
"VSAT":("earnings",True,"FY27 Q1 營收 $11.6 億(-1% YoY)遜於預期 $12.0 億、固網寬頻年減 27%;非 GAAP EPS $0.17 雖超預期 $0.10,股價仍收黑"),
"LLY":("earnings",True,"Q2 營收 $230 億(+48% YoY)、調整後 EPS $8.38(+33%),全年展望上修至營收 $850-870 億、調整後 EPS $35.50-36.50"),
"UTHR":("earnings",True,"Q2 營收 $7.833 億(-2% YoY)遜於預期 $8.046 億,Tyvaso 系列合計年減 4% 至 $4.526 億(霧化劑型年減 18%)"),
"DIS":("earnings",True,"FY26 Q3 調整後 EPS $1.61(去年 $1.39),串流事業獲利 $3.46 億大逆轉(去年虧 $1,900 萬),Disney+ 訂戶達 1.28 億"),
"BWA":("earnings",True,"Q2 營收 $36.5 億持平、調整後 EPS $1.42 遠超預期 $1.26(+17.4% YoY),全年調整後 EPS 上修至 $5.05-5.30,股利調升 55%"),
"ZBH":("earnings",True,"Q2 營收 $21.77 億(+4.8%)、調整後 EPS $2.07 持平,全年營收成長指引上修至 3.9-4.9%,庫藏股額度增至 $10 億"),
"AMGN":("earnings",True,"Q2 營收 $101 億(+10% YoY)、非 GAAP EPS $6.29(+4%),全年 EPS 指引上調至 $22.30-23.50"),
"AFG":("earnings",True,"Q2 淨利 $2.48 億、EPS $2.99(去年 $2.07),核心股東權益報酬率 19.2%,綜合成本率 91.5%"),
"GILD":("earnings",True,"Q2 營收 $78 億(+10% YoY);因 $112 億收購案認列在研發資產費用轉為 GAAP 每股虧損 $8.45,全年產品銷售指引上修至 $301-304 億"),
}
for k,(t,er,c) in NEW.items():
    d[k]={"Type":t,"EarningsReaction":er,"Catalyst":c}
json.dump(d,io.open(p,'w',encoding='utf-8'),ensure_ascii=False,indent=1)

# --- remove not-yet-published reporters + no-real-news names (SIPs 2.0d rule 4 / 2.0c rule 3)
DROP={'MDLN','FLUT','KHC','PSX','NYT','CRL','PODD','SHOP','RPRX','RRX','SN','CRWD'}
rows=[]
kept=0; dropped=0
with io.open('candidates.csv',encoding='utf-8-sig') as f:
    rd=csv.reader(f); hdr=next(rd)
    for r in rd:
        if len(r)!=8: continue
        if r[0] in DROP and r[4]=='headline' and r[5]=='2026-08-05': dropped+=1; continue
        rows.append(r); kept+=1
with io.open('candidates.csv','w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f); w.writerow(hdr); w.writerows(rows)
print('catalysts +',len(NEW),'| rows kept',kept,'dropped',dropped)
