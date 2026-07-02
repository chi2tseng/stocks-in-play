# -*- coding: utf-8 -*-
import csv, json, os
DIR=r'D:\SIPs'
# catalyst dict: sym -> (type, catalyst_zh)
CAT = {
 'AIIO':('news','Robo.ai 子公司 Neurovia AI 獲選第3屆政府網安峰會官方 AI 夥伴，早盤衝高後回落；過去一年仍跌89%，屬低浮籌投機。'),
 'ALM':('momentum','Almonty 鎢礦在前一交易日急拉後獲利回吐，盤前/盤後同步跌約10.5–10.8%，無新增重大消息；perf6M +204%、12M +513%。'),
 'AMPG':('earnings','AmpliTech 5G 室內 DAS 取得 FCC/ISED 全認證，Q1 營收年增48.6%至 $5.35M（超預期7%），自5月初翻倍續漲；perf1M +159%。'),
 'ARM':('macro','受 Broadcom AI 晶片展望不及預期（Q3 AI 營收指引 $16B vs 預估 $17.2B）拖累全晶片股，ARM 隨類股跌約5%。'),
 'BBCP':('earnings','Concrete Pumping Q2 營收年增14%至 $106.8M、調整後 EBITDA 增17%至 $26.4M 且上修展望，EPS $0.04 勝預估 $0.01（去年同期 -$0.01 轉盈）。'),
 'BCAB':('news','BioAtla 雙特異 T 細胞接合劑 BA3182 在大腸癌等實體瘤 Phase 1 顯腫瘤縮小訊號，低浮籌生技（流通僅150萬股）獲投機買盤推升約13%。'),
 'BESS':('momentum','Bimergen Energy（前 Bitech）儲能微型股在無明確新聞下放量急拉約15%，屬題材動能；perf6M -65%。'),
 'BGMS':('M&A','Bio Green Med Solution 宣布全股換股併購馬來西亞 Future NRG（Sendayan 臭氧醫療廢料廠，10噸/日），股價暴漲約185%。'),
 'BMNR':('news','全球最大 ETH 國庫公司 BitMine 因季度逾 $38 億虧損與加密情緒轉弱，自 $22–23 滑至 $17 附近、續跌約5%。'),
 'CDTG':('momentum','CDT Environmental 於6/1完成1:25反向分割後，盤後在無明確催化下漂移走低約4%。'),
 'CMND':('news','Clearmind 的 CMND-100 酒精使用障礙 Phase I/IIa 達主要安全終點、DSMB 准進入160mg 第四隊列並訂6/10 說明會，股價急拉約44%。'),
 'COO':('earnings','CooperCompanies Q2 調整後 EPS $1.21 勝預估 $1.10（+26% YoY）、營收 $1.08B 年增8% 並更新 FY 展望，盤後漲約5%（另含 $271.6M 訴訟一次性 GAAP 虧損）。'),
 'DOCU':('earnings','DocuSign FY1Q 調整後 EPS $1.09 勝 $1.00、營收 $830.2M 年增9% 超預期，但 Q2 與 FY27 指引僅符合預期令股價回落約4.6%。'),
 'DRCT':('news','Direct Digital 反向分割後 Q1 營收年減18%至 $6.7M、$23.9M 營運資金缺口觸發 going-concern 疑慮，股價跌約15%。'),
 'DXST':('news','Decent Holding 公布前5月初步營收 RMB55.1M、新增387個社區據點，加上董事長增持至90.5%投票權，股價漲約18%。'),
 'EDHL':('momentum','香港行銷/元宇宙公司 Everbright Digital 在無明確新聞下放量暴拉，盤中一度漲逾60%、收約+60%。'),
 'GWRE':('earnings','Guidewire Q3 EPS $0.82 勝 $0.74、營收 $372.5M 年增27% 且 ARR 增19%，但 Q4/FY 營收指引略低於市場（FY $1.46–1.47B vs $1.475B）令股價跌約14%。'),
 'HYLN':('news','Hyliion 的 KARNO 模組獲2026年度最有價值產品、進入美海軍 USX-1 無人艦海試，並累計近750組 LOI 逾 $4 億潛在營收，股價漲約5%；perf12M +392%。'),
 'INDP':('momentum','Indaptus 現金吃緊+策略檢討引發前一日逼空式急拉53.8%後回吐，盤前/盤後重挫約30–35%。'),
 'IOT':('earnings','Samsara Q1FY27 EPS $0.17 勝 $0.13（+31%）、營收 $478.8M 年增30.5% 超預期，但前瞻指引保守令股價盤後走弱約5.6%。'),
 'KEEL':('guidance','Keel Infrastructure 將可轉債發行上修至 $4 億（1.250%、2032到期，轉換價約 $7.41/溢價25%）募資建資料中心，稀釋疑慮使盤前跌約8.4%。'),
 'KNX':('news','Knight-Swift 創辦人兼執行董事長 Kevin Knight 退休、改任顧問兩年，盤後跌約5.8%；最新季 EPS $0.09 年減68%。'),
 'LASE':('contract','Laser Photonics 的 LSAD 反無人機系統獲 War Dept 在 MEIA Vulcan 徵案的 Counter C5ISR-T 類別選中、另傳 $13.2M 美海軍追加單，股價漲約17%（本週累漲逾150%）。'),
 'LULU':('guidance','Lululemon Q1 EPS $1.69/營收 $2.5B 大致符合，但下調全年指引（營收砍至 $11.0–11.15B、EPS 砍逾 $1），北美高個位數衰退，股價挫約11%。'),
 'MASK':('momentum','3 E Network 因芬蘭 Mikkeli AI 資料中心與 Orka 合作及可轉債融資題材放量，動能驅動盤前急拉約18%。'),
 'MNTS':('news','Momentus 憑 DARPA/AFRL/太空軍/NASA 訂單管線與2026營收上看 $10M（年增9倍）指引延續題材，股價漲約8%；perf3M +266%。'),
 'MRLN':('analyst','Merlin（AI 自主飛行軟體）獲 TD Cowen 於6/3首評 Buy 帶動延續性買盤，股價放量漲約28–39%；25% 短期空單為逼空燃料，惟最新季 EPS -$0.72 大幅虧損。'),
 'MTVA':('news','MetaVia 將於 ADA 2026（6/5–8）發表 DA-1726 與 vanoglipel 三張 late-breaking 海報（48mg 組 Day54 減重9.1%），題材推升股價約15%。'),
 'MU':('macro','受 Broadcom 疲弱 AI 展望引爆半導體類股拋售拖累，Micron 隨類股跌約4%（前一交易日盤中曾跌逾7%）；惟營收動能仍強。'),
 'NCT':('momentum','香港航運 Intercont (Cayman) 低價股動能波動，盤前小漲約6%，無明確公司消息。'),
 'ORGO':('earnings','Organogenesis Q1 營收年減58%至 $36.3M、淨虧 $53.2M，受 CMS 報銷新規衝擊（FY 展望砍至 $270–310M），盤後續跌約5%。'),
 'POET':('news','POET Technologies 遭多起證券集體訴訟（指控4月誤導 PFIC 稅務與商業協議）+稀釋疑慮，股價跌約4%（5月以來自 $20.81 重挫）。'),
 'PURR':('momentum','Hyperliquid Strategies（囤 HYPE 代幣）在 Chardan 上調目標價至 $9.75 觸發急拉近 $10.88 後回吐，獲利了結跌約6%。'),
 'RDW':('contract','Redwire 獲 Astrobiome Space 合約，用其太空溫室於 ISS 種植全球首批太空草莓並測生物刺激劑，盤前漲約4%（盤中一度+18%）。'),
 'SDOT':('M&A','Sadot Group 完成以 $12M（股權+可轉債）收購 Anira Consulting（TradeOS CTRM 平台）後前一日暴漲91%，盤後回吐約7.7%。'),
 'SIDU':('news','Sidus Space 以 LizzieSat/Fortis VPX 卡位飛彈防禦署與 SHIELD/Golden Dome 題材，惟近期完成 $58.5M/$100M 增發稀釋，股價放量漲約7.5%。'),
 'SKM':('news','SK Telecom 簽軍用 AI（A.X K1 模型）MOU，但因執行週期長且2025–26無法獲國家 GPU 配額，加上韓股 AI 熱退潮，股價跌約6–8.6%。'),
 'STI':('momentum','Solidion 推出專利 Gen-ECB 極端氣候電池平台（衛星/太空船/月面 -80°C 至 +60°C），前一日暴漲逾350%，盤前再漲約50%；純題材爆拉。'),
 'STM':('macro','STMicro 隨 Broadcom 引爆的歐美晶片股拋售下跌約4%（前數日因上修資料中心營收目標至約 $10 億而急漲後獲利回吐）。'),
 'TTAN':('earnings','ServiceTitan Q1FY27 EPS $0.37 勝 $0.28（+34%、+106% YoY）、營收 $268.8M 年增25%、GTV $21.7B 增23% 且給出 FY27 指引，股價漲約15%。'),
 'U':('analyst','Unity 獲分析師上調獲利預估、Hayden Capital 揭露新建倉（看好3D內容引擎與低估值），股價漲約5%。'),
 'VEEE':('momentum','Twin Vee PowerCats 因連年虧損、Nasdaq 下市風險與客戶集中度疑慮（going-concern），股價跌約4.6%。'),
 'VERU':('momentum','Veru 因6/2與 Novo Nordisk 的 enobosarm+Wegovy 臨床供應協議前一日暴漲88%後獲利回吐，盤前/盤後跌約10.4–10.9%（Oppenheimer 維持 Outperform/$24）。'),
 'XOS':('guidance','Xos 宣布以每股 $5.50 增發約109萬股募資約 $600 萬（投入 AI 資料中心供電與 Power Hub 業務），稀釋衝擊使股價跌約11%。'),
}

tv=json.load(open(os.path.join(DIR,'tv-summary.json'),encoding='utf-8'))
tvidx={r['Ticker']:r for r in tv}

rows=[]
seen=set()
with open(os.path.join(DIR,'candidates.csv'),encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        sym=r['Symbol']
        key=(sym,r['Session'],r['Direction'])
        if key in seen: continue
        seen.add(key)
        typ,cat=CAT.get(sym,('momentum','盤前/盤後波動，暫無明確催化劑。'))
        t=tvidx.get(sym,{})
        rows.append({
            'Symbol':sym,'Last':r['Last'],'ChgPct':r['ChgPct'],'Volume':r['Volume'],
            'Session':r['Session'],'Direction':r['Direction'],'Type':typ,'Name':r['Name'],
            'Catalyst':cat,
            'TV_LatestEPS':t.get('LatestEPS',''),'TV_PriorYrEPS':t.get('PriorYrEPS',''),
            'TV_LatestRev_M':t.get('LatestRev_M',''),'TV_PriorYrRev_M':t.get('PriorYrRev_M',''),
            'TV_YoYBlock':(t.get('YoYBlock','') or '').replace('\n','\n'),
        })

cols=['Symbol','Last','ChgPct','Volume','Session','Direction','Type','Name','Catalyst',
      'TV_LatestEPS','TV_PriorYrEPS','TV_LatestRev_M','TV_PriorYrRev_M','TV_YoYBlock']
with open(os.path.join(DIR,'final-candidates.csv'),'w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); w.writerows(rows)
print('wrote final-candidates.csv rows=',len(rows))
