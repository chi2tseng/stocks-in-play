# -*- coding: utf-8 -*-
import csv, json, io, os
DIR = os.path.dirname(os.path.abspath(__file__))

CAT = {
 'MU': ('earnings','Q3 FY26 營收 $41.46B 創紀錄 (+345.81% YoY、超預期 +15.4%)、非 GAAP EPS $25.11 (vs $20.86 估、+20.4%)、毛利率破紀錄 84.9%，HBM 售罄至 2026 年底，BofA 上調目標價至 $1,500，盤後 +13.7% 引爆記憶體超級循環'),
 'SNDK': ('analyst','MU 財報引爆記憶體超級循環，NAND/SSD 族群同漲，BofA($2,100)、Mizuho($2,200) 調高目標價'),
 'WDC': ('analyst','MU 引爆記憶體超級循環，HDD/儲存族群同漲，MS/JPM 上調目標價至 $650'),
 'STX': ('analyst','MU 引爆記憶體超級循環，AI 資料中心 HDD 需求帶動，MS($1,035)/JPM($920) 調高目標價'),
 'RMBS': ('momentum','MU 引爆記憶體超級循環，DRAM 介面/IP 概念股隨族群同漲'),
 'MRAM': ('news','MU 引爆記憶體超級循環，疊加 6/29 生效 Russell 2000 納入與 $40M 國防合約'),
 'AMKR': ('momentum','MU 引爆記憶體超級循環，先進封裝/OSAT 受惠 AI 記憶體需求同漲'),
 'ASX': ('momentum','MU 引爆記憶體超級循環，AI 先進封裝帶動 OSAT 族群同漲'),
 'UMC': ('news','媒體報導 UMC 與 Intel 深化合作共同開發先進製程 +6.9%，並受惠半導體族群回神'),
 'MX': ('momentum','MU 引爆記憶體超級循環，AI 伺服器電源功率半導體隨族群反彈'),
 'VSH': ('momentum','MU 引爆記憶體超級循環，被動元件/分立半導體隨族群反彈，盤後 +7%'),
 'AXTI': ('momentum','MU 引爆記憶體超級循環，InP 基板/光通訊高 beta 名稱隨半導體複合族群波動'),
 'RAM': ('momentum','2 倍槓桿 DRAM ETF (6/24 首日掛牌)，隨 MU 引爆記憶體族群機械式跳漲 +24.7%'),
 'LRCX': ('analyst','MU 引爆記憶體超級循環，Wells Fargo $365→$450、BofA→$480 (看好 NAND/DRAM 設備需求)'),
 'AMAT': ('analyst','MU 點燃記憶體/DRAM 超級循環，BofA $540→$720、Citi $550→$710'),
 'KLAC': ('analyst','MU 引爆記憶體超級循環，BofA 上調至 $317、Barclays/UBS/Citi 同步調高'),
 'MKSI': ('analyst','MU 帶動記憶體超級循環，BofA $380→$500、Cantor $300→$400，三星 NAND 擴產加成'),
 'ASML': ('analyst','MU 引爆 DRAM 超級循環，Bernstein 重申 DRAM 上行被低估、目標 $1,528'),
 'COHR': ('news','受惠 AI 光網絡需求 datacom 供不應求，JPM 維持 OW、TD Cowen→$395、BofA→$400，搭 MU 族群跳漲'),
 'AAOI': ('contract','鎖定逾 $324M 800G/1.6T 光收發模組訂單 (含單筆逾 $200M)，搭 MU 引爆族群走強'),
 'ALGM': ('momentum','MU 引爆記憶體超級循環，類比晶片族群同漲 (xEV/ADAS/資料中心電源題材)'),
 'CRDO': ('analyst','FY26 Q4 營收 $437M(+157% YoY) 爆量超預期後分析師上調目標 (Roth $300、Needham $275)，搭 MU 族群走強'),
 'QCOM': ('momentum','MU 引爆記憶體超級循環，AI 運算族群同步反彈 (前日 -8% 後回神 +13%)'),
 'ARM': ('analyst','多家投行 6/25 上調目標 (TD Cowen $475、UBS $470)，看好 agentic AI 驅動 CPU 需求，疊加 MU 超級循環'),
 'MRVL': ('momentum','MU 引爆記憶體超級循環，AI 運算族群同漲 (本週納入 S&P 500 加成)'),
 'INTC': ('momentum','MU 引爆記憶體超級循環，AI 運算族群同漲，前日 -6% 後回神'),
 'NBIS': ('momentum','MU 引爆記憶體超級循環，AI neocloud/運算族群同漲'),
 'CRWV': ('momentum','MU 引爆記憶體超級循環，AI neocloud/運算族群同漲'),
 'IREN': ('momentum','MU 引爆記憶體超級循環，AI 資料中心/運算族群同漲'),
 'VRT': ('momentum','MU 引爆記憶體超級循環，AI 資料中心電力族群同漲'),
 'ALAB': ('momentum','MU 引爆記憶體超級循環，AI 連結/運算族群同漲'),
 'BE': ('momentum','MU 引爆記憶體超級循環，AI 資料中心電力族群同漲'),
 'PENG': ('momentum','MU 引爆記憶體超級循環，受惠記憶體強勁需求 +7%'),
 'WYFI': ('momentum','MU 引爆記憶體超級循環，AI 運算/電力族群同漲'),
 'POET': ('momentum','MU 引爆記憶體超級循環，光電整合 AI 族群同漲'),
 'NVTS': ('news','6/24 宣布 $5 億 ATM 股票增發 (稀釋) 並推出新款高壓 SiC 封裝，疊加 MU 引爆超級循環'),
 'FRMI': ('momentum','Fermi (AI 電力園區) 延續 AI 資料中心題材強勁動能 (自 5 月底 mid-$5 翻倍)，收 $8.93'),
 'FLNC': ('momentum','Fluence Energy 隨 MU 帶動 AI 資料中心電力題材反彈，延續 Smartstack 10MWh 高密度儲能利多'),
 'WEN': ('squeeze','Wendy\'s 6/23 任命前 Potbelly CFO Steve Cirulis 出任 CFO 兼策略長，引爆「Save Wendy\'s」迷因散戶軋空 (S3 估空頭 ~29.67% 流通股)，6/24 收 +25.6%'),
 'MEI': ('earnings','Methode FY26 Q4 營收 $298.1M 大超 (vs $238M 估、+15.9% YoY) 轉虧為盈並給 FY27 $10.25-10.75 億營收指引，惟 adj EPS 略遜，盤後 +14.8%'),
 'BB': ('earnings','BlackBerry FY27 Q1 雙超預期 (EPS +100% surprise、營收 +9.4% YoY) 並給樂觀財測，QNX 軟體在 physical AI/車用動能帶動 +10%'),
 'GLW': ('contract','Corning 與 Amazon 簽多年期數十億美元光纖供應協議 (供應 AI 資料中心、北卡增 ~1,000 職位)，UBS 升評 $228 Buy、Truist $205'),
 'BLDP': ('M&A','Ballard Power 6/25 宣布以 £3.01 億收購英國氫能供應商 GeoPura，整合氫能方案、加速獲利'),
 'ONDS': ('contract','Ondas 子公司 Sentrycs 6/23 與 Lockheed Martin 合作整合反無人機技術進 Sanctum C-UAS 平台，疊加 6 月新接逾 $40M 國防訂單'),
 'OUST': ('contract','Ouster 擴大與 Benchmark 製造合作將 Rev8 光達產能拉至年逾 10 萬顆、簽 AIM 重機合約、完成 MetLife 球場部署，衝 52 週新高 $50.10'),
 'AMPX': ('momentum','Amprius (矽負極電池/無人機) 隨清潔科技反彈，背景題材為美軍 ~$5 億新訂單與全年營收上調至 ≥$130M'),
 'GLXY': ('macro','Galaxy Digital 隨 MU 帶動 AI/半導體反彈與比特幣回升 ($62,651) 反彈，前日 -8.8%'),
 'TE': ('momentum','T1 Energy (太陽能模組/電池) 隨類股反彈，延續 $32M 收購 Kore Power 進軍 BESS/資料中心題材'),
 'PURR': ('macro','Hyperliquid Strategies (HYPE 加密財庫股) 隨比特幣回升至 ~$62,651 與加密情緒回暖反彈，Chardan 目標價 $9.75'),
 'AZI': ('momentum','Autozi 極低浮籌股延續投機軋空 +100%，無新公司新聞，背景為加密國庫策略及 Nasdaq 市值合規壓力'),
 'WAVE': ('news','Eco Wave Power 因 NVIDIA 6/23 部落格《Turns Waves Into Watts With NVIDIA AI Infrastructure》獲 AI 能源題材加持，量逾 20 日均量 3 倍 +40%'),
 'FCUV': ('momentum','Focus Universal 1 拆 4 反向分割後低浮籌動能買盤湧入，單日急拉 +33% 至 ~$4.42'),
 'EHGO': ('offering','Eshallgo 延續 AI 合作題材極端波動，完成 454,968 股 @$3.25 註冊直接發行募資 ~$148 萬，動能買盤再起 +28%'),
 'BB ': ('earnings',''),
 # gap-downs / shorts
 'SPRY': ('guidance','ARS Pharma 6/24 盤後商業更新：旗艦腎上腺素鼻噴霧 neffy 在 7/1 給付週期未取得任何新主要商業保險納保，下修 2026 現金 OpEx 至 ~$248M，盤後 -24% (short float 39.5% 放大跌勢)'),
 'PASG': ('M&A','Passage Bio 6/24 盤後宣布與 Remix Therapeutics 全股票反向併購，現有股東僅持合併後 ~7%，更名 Remix 改代號 RMTX，並同步 ~$1 億私募，大幅稀釋 -18.9%'),
 'BOXL': ('momentum','Boxlight 1-for-6 反向分割造成超低浮籌，6/24 被散戶軋高 +37% 後動能耗盡遭獲利了結 -16.4% (YTD ~-52%)'),
 'TCOM': ('earnings','攜程 FY26 Q1 non-GAAP EPS $0.83 不如預期 $0.90 (-7.8%)、淨利年減 41.6%，Q2 淨營收指引僅年增 ~3-8% (遠低於 Q1)，加上 SAMR 反壟斷調查疑慮，三重利空 -14.3%'),
 'SKYQ': ('momentum','Sky Quarry 因內華達 Foreland 煉油廠 7 月投產消息單日飆 ~60% 後，6/25 盤前早期投資人獲利了結回吐 -13~14%，疊加最高 $1,260 萬 ATM 增發稀釋'),
 'INVE': ('M&A','Identiv 6/24 盤後宣布將 IoT 業務、德國 R&D、泰國子公司出售給 Trackonomy，且需「倒貼」再投入 $25M 現金換取 $50M 特別股，等同放棄主要營收 -12.2%'),
 'FND': ('macro','Floor & Decor 無個股利空，純宏觀反轉 — 6/24 隨房市股 +10.65% 後，6/25 因 Fed 點陣圖轉鷹、殖利率回升，利率敏感裝修股回吐 -9.6%'),
 'TSHA': ('offering','Taysha Gene Therapies 6/24 盤後以每股 $6.00 (低於收盤 $6.94) 定價 $2 億普通股加預融資權證承銷公開發行，稀釋壓力 -7.5%'),
 'TREX': ('momentum','Trex 6/24 因油價/建材成本下滑與房建族群反彈 +7.8% 後，6/25 缺乏個股催化隨漲勢退潮回吐 -7.2%'),
 'JHX': ('momentum','James Hardie 隨建材/房市反彈 +6% 後，6/25 無公司消息隨油價驅動的房建族群漲勢消退回落 -6%'),
 'CGON': ('momentum','CG Oncology 無個股新聞，PIVOT-006 第三期解盲在即的二元事件懸頂，疊加 6/25 全市場 risk-off 令臨床期生技遭拋售 -5.5%'),
 'DLTR': ('momentum','Dollar Tree 無當日個股新聞，過去一年大漲 ~73% 後在 6/25 risk-off (美元創新高) 中遭獲利了結，關稅/低收入消費承壓疑慮再起 -5.3%'),
 'MQ': ('momentum','Marqeta 無當日新催化，高 beta 金融科技股在 6/25 risk-off 中遭拋售，疊加 Block 合約重訂價使 2026 毛利承壓長期懸念 -5%'),
 'AVAH': ('news','控股 PE 股東 J.H. Whitney VII 於 6/24 提交 Form 144，計畫透過 RBC 出售近 690 萬股 Aveanna 持股，出場拋售壓力 -4.4%'),
 'MLKN': ('guidance','MillerKnoll FY26 Q4 雖 adj EPS $0.55/營收 $10 億雙超預期，但 FY27 指引 EPS $1.85-2.15 與 Q1 低於共識，加上訂單 -6.3%、在手訂單 -10.8%，盤後由漲反轉 -4.4%'),
}

tv = {}
for r in json.load(io.open(os.path.join(DIR,'tv-summary.json'),encoding='utf-8')):
    tv[r['Ticker']] = r

rows = []
with io.open(os.path.join(DIR,'candidates.csv'),encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        sym = r['Symbol']
        ctype, ctext = CAT.get(sym, ('momentum',''))
        t = tv.get(sym, {})
        rows.append({
            'Symbol': sym, 'Last': r['Last'], 'ChgPct': r['ChgPct'], 'Volume': r['Volume'],
            'Session': r['Session'], 'Direction': r['Direction'], 'Type': ctype,
            'Name': r['Name'], 'Catalyst': ctext,
            'TV_LatestEPS': t.get('LatestEPS',''), 'TV_PriorYrEPS': t.get('PriorYrEPS',''),
            'TV_LatestRev_M': t.get('LatestRev_M',''), 'TV_PriorYrRev_M': t.get('PriorYrRev_M',''),
            'TV_YoYBlock': (t.get('YoYBlock','') or '').replace('\n','  '),
        })

cols = ['Symbol','Last','ChgPct','Volume','Session','Direction','Type','Name','Catalyst',
        'TV_LatestEPS','TV_PriorYrEPS','TV_LatestRev_M','TV_PriorYrRev_M','TV_YoYBlock']
with io.open(os.path.join(DIR,'final-candidates.csv'),'w',encoding='utf-8-sig',newline='') as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
    for row in rows: w.writerow(row)
print('wrote', len(rows), 'rows to final-candidates.csv')
