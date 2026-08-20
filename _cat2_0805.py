import json, io
p='catalysts_today.json'
d=json.load(io.open(p,encoding='utf-8'))
NEW={
# shard C — SpaceX telecom cluster + misc
"VZ":("news",False,"SpaceX 財報後 COO Gwynne Shotwell 稱星鏈直連手機可搶三大電信商客戶,Bernstein 下修目標價至 $44"),
"T":("news",False,"同 VZ — SpaceX 衛星直連手機威脅既有電信客戶群,Bernstein 同步下修目標價"),
"TMUS":("news",False,"同 VZ — SpaceX 衛星直連手機威脅既有電信客戶群,Bernstein 同步下修目標價"),
"NVDA":("contract",False,"SpaceX 宣布 AI 基礎設施全面採用 NVIDIA 晶片,明年將取得相當比例的 GPU 供應"),
"CSCO":("analyst",False,"UBS 8/4 發布報告,預期 Cisco FY Q4 營收與 EPS 將優於預期"),
"TM":("guidance",True,"Q1 淨利年增 75.6% 至 1.47 兆日圓,全年獲利預測上調至 3.25 兆日圓,並宣布約 $6.37 億庫藏股"),
"NVO":("earnings",True,"Q2 營收 784.9 億丹麥克朗 +3%、EPS 年減 23.2%;Wegovy 口服劑型銷售 32.2 億克朗遜於預期,並降價 50%"),
# shard D
"J":("earnings",True,"FY Q3 調整後 EPS $1.84 超預期 $1.83、營收 $40.8 億,連三季上修 FY26 指引至 $7.20-7.30"),
"BAM":("earnings",True,"Q2 EPS $0.582 遜於預期 $0.602,營收 $16.2 億持平,淨利 $6.2 億 +25% YoY 但每股動能轉弱"),
"TRI":("earnings",True,"Q2 營收 $19.54 億 +9%(有機 +8%)、調整後 EPS $0.99 +14%,全年營收成長指引上修至約 8%"),
"SU":("earnings",True,"Q2 淨利 37 億加元($3.17/股)遠高於去年 11 億,調整後營運 EPS $3.23,月度回購擴大至 5 億加元"),
"CG":("earnings",True,"Q2 獲利跳升、fee-related earnings 成長(Reuters 報導);精確 EPS/營收數字尚未取得"),
"RRX":("earnings",True,"8/5 盤前公布 Q2,法說會提及在手訂單激增但風險猶存;精確 EPS/營收數字尚未取得"),
"SHOP":("earnings",True,"8/5 盤前公布 Q2(市場預估 EPS $0.39/營收 $34.3 億);實際數字尚未取得,股價盤前 -2%"),
"RPRX":("earnings",True,"8/5 盤前公布 Q2(市場預估 EPS $1.27、portfolio receipts $7.4-7.6 億);實際數字尚未取得"),
# shard E
"TOST":("earnings",True,"Q2 EPS $0.26 超預期 $0.20、營收 $19.1 億超預期 $18.7 億,ARR 成長 25% 至 $24 億並調高全年展望"),
"WTRG":("earnings",True,"Q2 EPS $0.37(去年 $0.38)、營收 $5.31 億 +3% YoY,維持長期 EPS 年複合成長 5-7% 展望"),
"CRBG":("earnings",True,"Q2 EPS $1.12 小勝預期 $1.09,但營收 $42.96 億大幅低於預期 $48.29 億,保費與存款 90 億"),
"RBA":("earnings",True,"Q2 營收 $13.2 億超預期 $12.3 億(+11.1% YoY)、EPS $1.13 符合預期,全年 EBITDA 指引上調至 $15.2 億"),
"DOC":("earnings",True,"Q2 調整後 FFO $0.46/股超預期 $0.43、營收 $7.716 億超預期 $7.256 億,全年 FFO 指引上調至 $1.73-1.77"),
"ALAB":("earnings",True,"Q2 營收 $3.924 億(+104% YoY)超預期近 9%、EPS $0.80 大勝預期 $0.64;Q3 指引營收 $5.4-5.6 億"),
"DVN":("earnings",True,"Q2 調整後 EPS $1.57 超預期 $1.49、營收 $74.2 億遠超預期 $59.9 億(+80% YoY,含 Coterra 併購貢獻)"),
"SN":("earnings",True,"8/5 盤前公布 Q2 財報;實際 EPS/營收數字尚未取得"),
# shard G
"NI":("earnings",True,"Q2 GAAP EPS $0.09、調整後 $0.16,較去年 $0.22 下滑;重申全年 EPS 指引 $2.02-2.07"),
"PRU":("earnings",True,"Q2 調整後營運 EPS $4.08 優於去年 $3.58,淨利 $9.85 億大增"),
"IRM":("earnings",True,"Q2 營收 $20.3 億 +18.5% YoY、AFFO 每股 $1.44 +17%,全年營收指引上調至 $79.4-80.1 億"),
"AIZ":("earnings",True,"Q2 GAAP EPS $5.95 +30% YoY、調整後 EPS $6.41 +26%,並上調全年 EBITDA 與 EPS 展望"),
"EOG":("earnings",True,"Q2 EPS $5.15(調整後 $5.07)、營收 $86.2 億,維持全年油產成長 +5% 指引"),
"LTM":("earnings",True,"Q2 EPS $0.58 遠優於預期 $0.14、營收 $41.2 億優於預期 $40.6 億,並上調全年獲利展望"),
"OC":("earnings",True,"Q2 調整後 EPS $3.93、營收 $27.6 億持平,Q3 營收指引 $26-27 億低於去年同期"),
"IFF":("earnings",True,"Q2 淨銷售 $19.5 億 +2% YoY、調整後 EPS $0.82,並核准 $25 億庫藏股"),
"EQH":("earnings",True,"Q2 GAAP 每股虧損 $1.68、非 GAAP 營運 EPS $1.70 優於去年 $1.10;Corebridge 併購預計年底前完成"),
"CRL":("earnings",True,"8/5 盤前公布 Q2 財報;實際 EPS/營收數字尚未取得"),
}
for k,(t,er,c) in NEW.items():
    d[k]={"Type":t,"EarningsReaction":er,"Catalyst":c}
json.dump(d,io.open(p,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
print('written',len(NEW),'total',len(d))
