# -*- coding: utf-8 -*-
import csv, json, os
DIR = r'D:\SIPs'

CAT = {
 'HPE': ('earnings', 'FQ2 EPS $0.79 超預期 $0.53(+47.8%)、營收 $106.8 億超 $97.8 億(+9.2%)，FY26 調整後 EPS 指引上調至 $3.35–3.45，AI 基礎設施需求強勁。'),
 'MRVL': ('earnings', '發表業界首款 102.4 Tbps Teralynx T100 AI 資料中心交換晶片；最新季營收 $24.2 億 +27% YoY，AI 資料中心動能強勁。'),
 'DXST': ('news', '13D 揭露董事長孫鼎新增持 40 萬股 Class B、投票權升至 90.5%，盤後飆 148%。'),
 'VSA': ('momentum', '極低流通量(float 0.61M)、高空頭比之軋空標的，無實質個股新聞。'),
 'CTNT': ('M&A', '完成收購香港工業設備貿易商 Super International Trading，盤後 +71%。'),
 'ABTS': ('momentum', '加密題材投機性拉抬，基本面嚴重虧損，疑為低流通量拉抬。'),
 'SBFM': ('news', '完成 1:10 反向股票分割(6/1 生效)以維持 Nasdaq 最低股價合規。'),
 'ZJYL': ('momentum', '輪椅製造微型股，無明確個股消息，疑為低流通量中概小型股拉抬。'),
 'ANY': ('M&A', '完成收購 Cathedra Bitcoin，整合 53MW 跨 5 座資料中心算力平台(AI/HPC+BTC)，股價單日翻倍。'),
 'ZNB': ('momentum', '市值約 $360 萬之 BTC 機構金融平台微型股，無明確消息。'),
 'BJDX': ('momentum', 'Symphony IL-6 監測平台(未獲 FDA 清關)，盤後暴漲 233% 無新聞觸發，疑為低流通量軋空。'),
 'LAC': ('momentum', '鋰類股+美國政府股權合作題材帶動，選擇權買盤異常(call 量 3 倍)。'),
 'LFVN': ('news', '季度股息調升 11% 至每股 $0.05(6/15 派發)。'),
 'STM': ('guidance', '上調 2026 資料中心營收目標至約 $10 億(原 >$5 億)，暗示 2027 可望倍增，成 CAC 40 當日最強。'),
 'POET': ('news', '隨光通訊 AI 族群走強；先前與 Lumilens 簽含 $5,000 萬初始訂單、5 年逾 $5 億框架供貨協議。'),
 'MCHP': ('analyst', '受 STM 上調資料中心指引帶動之類比晶片復甦樂觀情緒，半導體族群動能拉抬。'),
 'HSAI': ('news', '宣布 6/26 股東會表決 8:1 股票分割與 ADS 比例調整、發行/回購授權。'),
 'LI': ('news', '5 月交付 33,350 輛，全新 Li L9 上市兩週訂單破萬，預告 6 月底發表 Li L8。'),
 'LWLG': ('momentum', '隨光通訊/光子 AI 族群走強(過去一年 +1,304%)，無單一個股催化。'),
 'MX': ('news', 'AI 伺服器電源晶片題材樂觀，股價衝 29 個月新高。'),
 'FLNC': ('contract', '獲選 NVIDIA+Siemens 共同開發 Vera Rubin AI 工廠參考架構儲能關鍵夥伴，盤中一度 +40%。'),
 'LITE': ('momentum', '隨 AI 資料中心光連結需求與 800G/1.6T 升級週期走強(年內 +180%)。'),
 'AVGO': ('momentum', '自研 AI 晶片+網通強勁需求題材帶動(年內 +29%)，族群性上漲，財報將近。'),
 'AAOI': ('analyst', 'Rosenblatt 上調目標價至 $220 重申買進，800G 雲端需求(疑 Amazon)+Oracle 認證題材。'),
 'XPEV': ('macro', '隨中概股+電動車族群同步走強，5 月交付數據與中國股市反彈帶動。'),
 'AXTI': ('momentum', 'InP(磷化銦)AI/資料中心需求帶動，Q1 營收與毛利率大增、$1 億在手訂單，隨光學 AI 族群走強。'),
 'BABA': ('macro', '隨中概股族群反彈，中國 AI/半導體類股走強帶動。'),
 'MXL': ('momentum', '隨半導體/光通訊族群走強，無單一個股催化。'),
 'DG': ('earnings', 'Q1 淨銷售 +3.4% 至 $109 億、同店 +2.0%、EPS $1.93 超預期 $1.66(+16.4%)，上調 FY26 EPS 指引至 $7.10–7.35。'),
 'GLW': ('news', '與 NVIDIA 簽多年合作擴大美國光連結產能(新建 3 廠)，光通訊佔營收 44%、Q1 該部門 +36% YoY。'),
 'SMCI': ('momentum', '隨 AI 伺服器需求+半導體族群走強(年內 +57%)。'),
 'NUAI': ('momentum', '能源+數位/AI 資料中心微型股投機性拉抬。'),
 'NVTS': ('momentum', 'GaN/SiC AI 資料中心電源題材族群性反彈。'),
 'COHR': ('momentum', '隨 AI 資料中心光連結需求走強(年內 +112%)。'),
 'ADEA': ('earnings', '公布 8 項新簽/續約授權(含與 AMD、Microsoft 多年協議)，營收 $1.048 億、調整後 EBITDA 利潤率 60%。'),
 'CING': ('momentum', 'ADHD 臨床階段藥廠，無明確個股消息，疑為低流通量拉抬。'),
 'SKM': ('analyst', 'HSBC 由減持上調至持有 + 完成 SK Broadband 100% 收購，盤中 +19–21%。'),
 'JD': ('macro', '隨中概股族群同步反彈，無單一個股重大新聞。'),
 'ELMT': ('momentum', '無明確個股消息，疑為低流通量拉抬。'),
 'PURR': ('momentum', '標的 HYPE 創新高(進前十大加密)+6/26 納入 Russell 2000/3000 與 gamma 軋空題材，盤前 +20%。'),
 'OSTX': ('FDA', 'OST-HER2 治療復發性骨肉瘤 Phase 2b 正面(2 年總存活 75% vs 歷史對照 40%)，推進 BLA 申請。'),
 'RDGT': ('momentum', '市值約 $146 萬微型股(4 月 1:150 反分割)，無明確消息。'),
 'FULC': ('FDA', 'FDA 認定 PRC2 抑制劑具次發血液惡性腫瘤風險、無監管路徑，終止鐮刀型貧血藥 pociredir 並啟動策略評估，盤後崩 50%。'),
 'ABVX': ('FDA', '潰瘍性結腸炎藥 obefazimod 三期 ABTECT 達主終點(緩解率約 51% vs 安慰劑 10%)，但高劑量組 3 例癌症安全訊號，Jefferies 降評目標價砍至 $90。'),
 'JZ': ('news', 'Jiuzi 公布 AI 智慧影像平台進展，但市場消化先前增發稀釋疑慮。'),
 'AIB': ('momentum', 'AI 資料中心/區塊鏈微型股，無明確個股消息，盤前回吐。'),
 'HKIT': ('momentum', '極度波動低流通量投機標的，衝破 $9 後快速回落。'),
 'FOFO': ('momentum', '香港顧問/資管微型股，無明確個股消息，波動回吐。'),
 'ASTC': ('momentum', '前三日因 1st Detect TRACER 1000 獲 ECAC/EU G1 認證暴漲逾 2,500% 後回檔修正。'),
 'CRDO': ('earnings', 'FQ4 營收 $4.37 億 +157% YoY、EPS $1.16 雙超預期，但毛利率環比下滑且高預期未獲滿足，盤後 -12%；Q1 指引 $4.65–4.75 億。'),
 'ORIC': ('news', '與 Jefferies 設立 ATM 股票發行計畫引發稀釋疑慮，股價承壓。'),
 'MASK': ('momentum', '前波由 $1.38 急拉至 $2.45 後回吐，投機性動能標的。'),
 'EQ': ('momentum', '臨床期生技(將出席 6/3 Jefferies 醫療會議)，低流通量投機波動。'),
 'EEIQ': ('momentum', '中概教育微型股，無明確個股消息，波動回吐。'),
 'SPCE': ('momentum', 'VSS Unity 恢復滑翔試飛、前一日 +18% 後回吐獲利了結。'),
 'NU': ('analyst', 'BofA 由中性降至表現不佳、目標價由 $16 砍至 $10，因 CFO Guilherme Lago 7/13 卸任轉特別顧問。'),
 'ZS': ('earnings', 'Q3 營收 +25% 至 $8.505 億、上調 FY26 指引，但 FY27 成長指引 16–17% 低於市場預期 18.9%；Guggenheim 升評至買進、目標價 $214。'),
 'ORCL': ('macro', '隨軟體股賣壓走弱(市場憂 AI 工具取代既有模式+AI 基建支出過高)，族群性下跌。'),
 'NOW': ('macro', '隨軟體股賣壓走弱(AI 取代疑慮)，年內已跌逾 40%。'),
 'ZETA': ('macro', '隨數據/行銷軟體族群在 AI 取代疑慮下走弱。'),
 'FRGT': ('news', '基本面惡化(過去一年 -92%、4/30 宣布無法如期遞交 20-F 年報)，持續性賣壓。'),
 'FIG': ('macro', '隨軟體股賣壓回吐；維權投資人 Findell Capital 推動策略變革，Q1 營收 $3.334 億超預期但 AI 取代疑慮壓抑估值。'),
}

# load TV summary
tv = {}
with open(os.path.join(DIR,'tv-summary.json'), encoding='utf-8') as f:
    d = json.load(f)
    rows = d if isinstance(d, list) else d.get('rows', [])
    for r in rows:
        tv[r.get('Ticker')] = r

# load candidates, dedupe by symbol keeping largest |chg|
best = {}
with open(os.path.join(DIR,'candidates.csv'), encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        sym = r['Symbol']
        chg = abs(float(r['ChgPct']))
        if sym not in best or chg > abs(float(best[sym]['ChgPct'])):
            best[sym] = r

out_rows = []
for sym, r in best.items():
    typ, cat = CAT.get(sym, ('news', '盤前無明確個股消息。'))
    t = tv.get(sym, {})
    out_rows.append({
        'Symbol': sym, 'Last': r['Last'], 'ChgPct': r['ChgPct'], 'Volume': r['Volume'],
        'Session': r['Session'], 'Direction': r['Direction'], 'Type': typ,
        'Name': r['Name'], 'Catalyst': cat,
        'TV_LatestEPS': t.get('LatestEPS',''), 'TV_PriorYrEPS': t.get('PriorYrEPS',''),
        'TV_LatestRev_M': t.get('LatestRev_M',''), 'TV_PriorYrRev_M': t.get('PriorYrRev_M',''),
        'TV_YoYBlock': t.get('YoYBlock',''),
    })

out_rows.sort(key=lambda x: -abs(float(x['ChgPct'])))
cols = ['Symbol','Last','ChgPct','Volume','Session','Direction','Type','Name','Catalyst',
        'TV_LatestEPS','TV_PriorYrEPS','TV_LatestRev_M','TV_PriorYrRev_M','TV_YoYBlock']
with open(os.path.join(DIR,'final-candidates.csv'),'w',encoding='utf-8-sig',newline='') as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader(); w.writerows(out_rows)
print('wrote', len(out_rows), 'rows to final-candidates.csv')
