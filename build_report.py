"""Combine Barchart candidates + catalyst data + TradingView data and produce final report."""
import os, re, json, csv

DIR = os.environ.get('SIPS_DIR') or os.path.dirname(os.path.abspath(__file__))

# --- Load Barchart candidates from CSV ---
candidates = []
with open(os.path.join(DIR, 'candidates.csv'), 'r', encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        candidates.append({
            'Symbol': r['Symbol'],
            'Last': float(r['Last']),
            'ChgPct': float(r['ChgPct']),
            'Volume': int(r['Volume']),
            'Session': r['Session'],
            'Direction': r['Direction'],
            'Name': r['Name'],
        })

# --- Load TV summary ---
with open(os.path.join(DIR, 'tv-summary.json'), 'r', encoding='utf-8') as f:
    tv_data = json.load(f)
tv_by_ticker = {t['Ticker']: t for t in tv_data}

# --- Catalyst data: hand-entered for 2026-05-14 scan ---
catalysts = {
    # Tier 1 — Strong earnings beats / SIPs
    'CSCO': {'Type':'earnings','Catalyst':'Q3 FY26 營收 $15.84B 超預期 ($15.56B)、EPS $1.06 vs $1.03 (+2.4%)、Q4 指引 $16.7-16.9B 大幅高於 $15.8B 共識、FY26 EPS 上修至 $4.27-4.29、AI 基建訂單預期由 $5B 倍增至 $9B。'},
    'STAA': {'Type':'earnings','Catalyst':'Q1 2026 營收 $93.5M 大超預期 $78.7M (+19%)、年增 +119.6%、EPS $0.10 vs $0.05 預期 (+100%)、毛利率 73.6%、中國銷售 $47.4M 主驅動、調整 EBITDA $24.4M。'},
    'CRMD': {'Type':'earnings','Catalyst':'Q1 2026 營收 $127.4M 大超預期 $105M (+21%)、年增 +226%、淨利 $38.6M、調整 EBITDA $70M；DefenCath $97.5M (含 $9M 非經常性) + Melinta 組合 $29.9M。'},
    'STUB': {'Type':'earnings','Catalyst':'StubHub Q1 2026 營收 $446M 超預期 $402M (+11%)、年增 +12%、IPO 後首季由淨虧 -$22.2M 轉淨利 $48M、EBITDA $72M (16% 利潤率)、重申 FY GMS $9.9-10.1B、EBITDA $400-420M。'},
    'POET': {'Type':'contract','Catalyst':'與 Lumilens 簽光子整合 AI 基建大單，初期 $50M 訂單 + 五年累計達 $500M 潛在規模、樣品 2026Q4、量產 2027；定位 AI 數據中心高速光引擎。'},
    'GO':   {'Type':'earnings','Catalyst':'Grocery Outlet Q1 2026 EPS $0.05 超預期 $0.03 (+67%)、營收 $1.17B 超預期 $1.15B、年增 3.6%；雖然 GAAP 淨虧 $180M（商譽減損），重申 FY 指引、宣布優化計畫關閉 36 家門店。'},
    'EOSE': {'Type':'earnings','Catalyst':'Eos Energy Q1 2026 營收 $57M 年增 +445%、產量達去年 5 倍、EPS $0.12 大超 -$0.22 預期；積壓訂單 $645M、商業管線逾 100 GWh、重申 FY $300-400M、盤後 +20% 但盤前 -6%（獲利了結）。'},
    'AQST': {'Type':'earnings','Catalyst':'Aquestive Q1 2026 營收 $14.4M 超預期 $10.9M (+33%)、年增 +66%、EPS -$0.07 優於 -$0.14；Oaktree $150M 信貸、Anaphylm NDA Q3 重新提交、淨虧縮窄 $8.1M。'},
    'PGEN': {'Type':'earnings','Catalyst':'Precigen Q1 2026 Papzimias 首個完整商業季度營收 $21.6M (上季 $3.4M)、FDA 廣標籤無手術前提條件、預計 2026 達現金流盈虧平衡。'},
    'FOSL': {'Type':'earnings','Catalyst':'Fossil Q1 2026 EPS -$0.01 大超 -$0.28 預期 (+89%)、營收 $225M 超預期 $205M、毛利率 59.7%、SG&A 削減 13%、批發 +5% 但 DTC -29%。'},
    'MRAM': {'Type':'contract','Catalyst':'Everspin 拿下 $40M、30 個月國防 Toggle MRAM 分包合約 (DoD/航太)；Q1 2026 營收 $14.9M (+13% YoY)、毛利率擴張至 52.7%、MRAM 產品銷售年增 28%。'},
    'VRDN': {'Type':'earnings','Catalyst':'Viridian Q1 2026 EPS -$0.90 vs -$1.08 預期 (+17%)、現金 $762M；veligrotug PDUFA 日期前處於發射準備、REVEAL Phase 3 elegrobart 雙陽性數據。'},
    'MGNX': {'Type':'earnings','Catalyst':'MacroGenics Q1 2026 營收 $20.8M 超預期 (+36%)、年增 +57%、EPS -$0.58 接近預期；市場期待 mid-2026 MGC026 ADC Phase 1 數據。'},

    # Tier 2 — Analyst / Activist / Contract
    'HPE':  {'Type':'analyst','Catalyst':'Irenic Capital 加入 Elliott Management 行動投資人陣列、新 52 週高、Q1 FY26 營收 +18% YoY 強勢、上修 FY 指引、Juniper 整合進展順利、AI 網路訂單暢旺。'},
    'NOK':  {'Type':'analyst','Catalyst':'Q1 2026 AI/雲訂單年增 49% 達 €10 億、上修 AI/雲 CAGR 至 27%（前 16%）、與 Anduril 國防 AI-RAN 合作、與 Lockheed Martin 5G 國防方案，多家投行升評。'},
    'UMC':  {'Type':'news','Catalyst':'聯華電子 5 月加大買回計畫至 NT$3 億+、Q1 2026 EPS $0.20 vs $0.12 預期、CSCO/HPE 強勢拉動全球晶圓代工讀通。'},
    'WOLF': {'Type':'analyst','Catalyst':'Citrini Research 點名 Wolfspeed 為 AI 基建首選、稱「破產重整後完美設置」、過去 6 個交易日 +50%、Q3 2026 公告 +21% 至 $65.13、SiC 切入 AI 資料中心高功率轉換需求。'},
    'ONDS': {'Type':'contract','Catalyst':'5/14 盤前 Q1 2026 業績前，宣布 $175M 收購 Mistral 國防、Israel 邊境掃雷 $80M、INDO Earth Moving 初始 $68M（$140M 多年計畫），積壓訂單達 $457M（含 World View）。'},
    'KULR': {'Type':'contract','Catalyst':'5/14 盤後 Q1 2026 業績前，4/29 公布 $1M 國防無人機電池訂單、預計 2026 同客戶可達 $5M、Board 新任命；股價有 12 月 $14.24 高位的拉回機會。'},
    'WYFI': {'Type':'contract','Catalyst':'WhiteFiber 5/14 盤後 Q1 2026 業績前，NC-1 數據中心開始 $865M、10 年 Nscale 託管合約計費（4/30 首 20MW、5/30 再 20MW），轉型 colocation 模式。'},
    'DGXX': {'Type':'contract','Catalyst':'Digi Power X 公布次世代電池技術突破，與 Cerebras 託管合作 + SubQ 24 個月 $19.6M GPU 租賃合約（5/15 起）、過去一個月翻三倍，5/14 盤後 Q1 業績。'},
    'RR':   {'Type':'contract','Catalyst':'Richtech Robotics 公布與 SoundHound AI 語音整合機器人合作 + 歐洲展示新訂單；股價 +9.7% 至 $2.82，連動 AI 應用機器人主題。'},
    'TDIC': {'Type':'news','Catalyst':'子公司與 LinkFung 簽 12 個月 AI 圖庫平台 MoU，香港活動公司轉型 AI 圖像生成概念，盤前一度 +59%、波動極大。'},

    # Tier 3 — IPO / Macro / Biotech catalysts
    'FRVO': {'Type':'news','Catalyst':'Fervo Energy 地熱新股 5/13 Nasdaq 上市，IPO 募資 $1.89B、首日漲 33% 至市值 $10B，5/14 盤前 -4.21% 為 IPO 後波動。'},
    'KLAR': {'Type':'earnings','Catalyst':'Klarna 5/14 盤前發布 Q1 2026 業績，pre-earnings 反彈 +5% 至 $14.39；5 月以來連續上漲修復估值。'},
    'FIG':  {'Type':'earnings','Catalyst':'Figma 5/14 盤前 Q1 2026 業績前 +4.5%，預計營收 $315-317M (+38% YoY)、NDR 136%；先前因 AI 設計競爭擔憂股價回落 -48% YTD，本週反彈 8.3%。'},

    # Tier 4 — Bullish biotech / specialty
    'ABSI': {'Type':'earnings','Catalyst':'5/13 Director Menelas Pangalos 內部買入 37,453 股 (~$200,748)，前期 Q1 2026 營收 $215K 大幅低於預期 ($1.43M)、但 ABS-201 androgen alopecia 進度推進。'},

    # Tier 5 — Short candidates (gap-down)
    'DOCS': {'Type':'guidance','Catalyst':'Doximity Q4 FY26 EPS $0.26 低於 $0.28 預期 (-7%)、但 FY27 營收指引 $664-676M 大幅低於 $697M 共識、Q1 FY27 指引 $151-152M 也低；HCP digital pharma ad 軟弱、AI 計算成本壓縮毛利至 89%。'},
    'ALMU': {'Type':'earnings','Catalyst':'Aeluma Q3 FY26 營收 $1.22M 低於 $1.38M 預期 (-12%)、FY 指引收緊至 $4.2-4.6M（低端低於 $5.48M 共識）；管理層歸咎政府停擺與合約執行延遲。'},
    'ENVX': {'Type':'guidance','Catalyst':'Enovix Q1 2026 營收 $7.6M 超預期 ($7.09M)、年增 +49%、EPS -$0.14 優於 -$0.16；但 Q2 指引 $8-9M 偏保守，sell-the-news 暴跌 -13%。'},
    'AIRO': {'Type':'earnings','Catalyst':'AIRO Group 5/14 盤前 Q1 2026 業績前，預期營收 $16.59M 較 Q4 2025 $48.28M 大跌 -66%、EPS -$0.27、放棄 eVTOL 業務、BTIG 因積壓訂單下滑下修評級。'},
    'BATL': {'Type':'earnings','Catalyst':'Battalion Oil Q1 2026 淨虧 $64.8M、調整 EBITDA $10M 較 $15.1M 衰退、營收 $39.2M、產量 12,578 Boe/d 增加但實現價格下滑。'},
    'CSIQ': {'Type':'earnings','Catalyst':'Canadian Solar 5/14 盤前 Q1 2026 業績前，營收 $1.1B 達指引高端 (-10% YoY)、毛利率 25.1%（含 $93M 關稅退稅）、淨虧 $32M ($0.71/股)。'},
    'FRMI': {'Type':'news','Catalyst':'Fermi 5/14 盤前 Q1 2026 業績前，CEO Toby Neugebauer 離職觸發領導擔憂、UBS 5/5 自 Buy 降至 Neutral、新任 Larry Kellerman 入董事會。'},
    'LUNR': {'Type':'earnings','Catalyst':'Intuitive Machines 5/14 盤前 Q1 2026 業績前，預期營收 $203M、EPS -$0.07；昨日 +11% 後盤前獲利了結；Space Force Andromeda IDIQ 合約多廠商競爭、實際營收不確定。'},
    'LWLG': {'Type':'earnings','Catalyst':'Lightwave Logic 5/13 Q1 2026 業績與業務電話會前獲利了結；先前因聘任 Michael Best 律師事務所為 IP 策略而連續暴漲。'},
    'AMPG': {'Type':'earnings','Catalyst':'AmpliTech Q1 2026 營收 $5.35M (+48.6% YoY)、毛利率擴至 48%、淨虧縮窄 17.3% 至 $1.52M；盤後 +1.86%、盤前反向 -7.26%。'},
    'MSGM': {'Type':'earnings','Catalyst':'Motorsport Games Q1 2026 營收 $4.0M 年增 +129%、EPS $0.07 轉正、Le Mans Ultimate Steam 8,800 並發、RaceControl MRR > $0.2M。但市場反應未跟上。'},

    # Tier 6 — Speculative micro-cap pumps
    'WOK':  {'Type':'momentum','Catalyst':'WORK Medical 與上海諾華生技 AI BioToken 合作協議催出單週 +206% 後速崩，盤前 -46%、純動能炒作後反轉，基本面年營收 <$10M。'},
    'AEHL': {'Type':'momentum','Catalyst':'Antelope Enterprise 公告「Genius Plan」比特幣實現獲利 $190K + $95K 股票回購（6/6 開始）、中國微型股轉型加密貨幣與能源基建，盤前 +49% 純炒作。'},
    'AIIO': {'Type':'momentum','Catalyst':'Robo.AI 宣布 NeuroStream 平台 + $100M 全股票收購 Neurovia AI、新任 Mansoor Ali Khan 為 CTO；trailing 營收僅約 $950，P/S > 1,800 極端投機。'},
    'OCG':  {'Type':'momentum','Catalyst':'Oriental Culture 4 月底起從 <$1 一路飆至 $2+，純低浮動微型股動能交易、5/13 盤中觸 $2.93；盤前 -9% 後盤後 +4.66% 反彈。'},
    'BNKK': {'Type':'momentum','Catalyst':'Bonk Inc. 加密貨幣相關微型股，盤前 +16% 無明確新聞催化、典型低浮動跟風炒作。'},
    'BNRG': {'Type':'momentum','Catalyst':'Brenmiller Energy 5/14 Series C 認購權證到期、低浮動熱能儲存以色列公司、Tempo 32 MWh 計畫首認列 $387K 營收。'},
    'FNUC': {'Type':'momentum','Catalyst':'Frontier Nuclear (前 Snow Lake Resources) 美國核燃料循環故事 + 鋰資產分拆、無近期明確催化。'},
    'FPS':  {'Type':'earnings','Catalyst':'Forgent Power Solutions Q2 2026 營收年增 +69%、訂單年增 +268%、book-to-bill 升至 2.6x（前 1.6x），數據中心與電網需求驅動。'},
    'HTCO': {'Type':'news','Catalyst':'High-Trend International 5/14 完成 $15M 註冊直接增發 (2.31M 股 @ $6.50)、稀釋擔憂導致盤中 -30%，盤前先 +19% 後反轉。'},
    'HOVR': {'Type':'momentum','Catalyst':'New Horizon Aircraft eVTOL 微型股，無近期重大新聞、低浮動動能 +9%。'},
    'VIVO': {'Type':'momentum','Catalyst':'Vivopower 微型股無明確催化、盤前 +4% 盤後 +10%、典型動能炒作。'},
    'SLNH': {'Type':'news','Catalyst':'Soluna Holdings 恢復 Nasdaq 報價合規、$2 以下微型股 +4.6% 跟動能買盤。'},
    'RDW':  {'Type':'analyst','Catalyst':'Redwire Q1 2026 EPS -$0.40 低於 -$0.15 預期、營收 $97M 低於 $105M 預期；但 Truist Buy、Canaccord $14、Jefferies $13 升目標、Q1 訂單 $350M+。'},
    'RGNX': {'Type':'FDA','Catalyst':'Regenxbio 5/14 早盤 RGX-202 Phase 3 AFFINITY DUCHENNE 主要終點達顯著統計、Q1 2026 業績；盤前 -20% 為財報前避險，結果出爐後反轉。'},
    'SN':   {'Type':'earnings','Catalyst':'SharkNinja Q1 2026 EPS $1.09 大超預期 $0.84 (+30%)、營收 $1.41B (+15.6% YoY)、第 12 季連續雙位數成長、國際 +32%、上修 FY 營收成長 11.5-12.5%。'},
    'ABSI_placeholder': {'Type':'placeholder','Catalyst':'placeholder'},  # remove dup

    # Existing entries kept for compatibility
    'WOK_old':  {'Type':'momentum','Catalyst':'與上海諾華生技簽 AI BioToken 合作協議，純動能拉抬：盤後 +69.67%、盤前反轉 -36.73%，無真實基本面。'},
    'CNCK': {'Type':'earnings','Catalyst':'Q4 + FY 2026 財報於 5/12 發布，並宣布與 KDDI 加密貨幣業務戰略合作（資產負債 530 億現金、營收 3,833 億日圓），股價暴漲 +37%。'},
    'QUBT': {'Type':'earnings','Catalyst':'Q1 2026 營收 369 萬美元（去年同期 3.9 萬，+9400% YoY），EPS -$0.02 大幅優於 -$0.05 預期 (+60% 驚奇)，現金部位 14 億美元支撐量子製造擴張。'},
    'VSTS': {'Type':'earnings','Catalyst':'Q2 FY26 調整後 EBITDA $74.5M 超預期、上修全年 EBITDA 指引中點至 $310M（高於 $299.6M 共識），雖 GAAP 仍虧 $0.10/股。'},
    'OCG':  {'Type':'news','Catalyst':'4/21 宣布 1:3 反向分割以維持 Nasdaq 合規、加碼投資 Jade Cove $15M 取得 75% 股權，低浮動股票炒作 +45%。'},
    'VELO': {'Type':'earnings','Catalyst':'Q1 2026 營收 $13.8M 年增 48% 大超預期 (+40%)，毛利率從 7.5% 跳升至 17.2%，獲美國國防部 $9.8M 五年 IDIQ 合約 + 完成 $50M 增資減債 70%。'},
    'TDIC': {'Type':'news','Catalyst':'子公司 Trendic 與 LinkFung 簽 AI 圖庫平台 12 個月 MoU，香港活動公司轉型 AI 概念股動能拉抬，盤前一度漲 59%。'},
    'MGNX': {'Type':'earnings','Catalyst':'Q1 2026 連續第三季雙重擊敗，年初至今股價漲 38%，市場期待 mid-2026 MGC026 ADC 第一期數據觸發。'},
    'SLS':  {'Type':'FDA','Catalyst':'Q1 2026 EPS -$0.05 優於 -$0.07 預期，Phase 3 REGAL AML 試驗已達 78/80 事件、現金 1.071 億美元、SLS009 啟動 80 例第二期試驗。'},
    'DDD':  {'Type':'earnings','Catalyst':'Q1 2026 營收 $95.5M 年增 11% 超預期 ($90.6M)、醫療部門 +21% 首超工業、調整後 EBITDA $2.1M (前年同期 -$26.1M)、EPS -$0.01 大幅改善 95%。'},
    'PSIX': {'Type':'earnings','Catalyst':'Q1 2026 營收 $128.6M 大miss 預期 $160.8M (-20%)、調整 EPS $0.36 vs $0.74 預期 (-51%)、毛利率收縮 22.9%、撤回 FY 指引。'},
    'SST':  {'Type':'earnings','Catalyst':'Q1 2026 GAAP 淨虧 $57.6M、營收 $37.2M，連續 5 季營收下滑趨勢（FY25 -23%、Q4 25 -31%），廣告平台業務萎縮。'},
    'GTM':  {'Type':'guidance','Catalyst':'ZoomInfo 改名後首份財報：Q1 EPS $0.28 beat 但下修 FY26 營收指引至 $1.185-1.205B（前 $1.247-1.267B）、Q2 指引 $300-303M 低於 $313M 共識、宣布 20% 裁員。'},
    'UAA':  {'Type':'earnings','Catalyst':'Q4 FY26 營收 $1.17B 大幅低於預期 $1.68B (-30% miss)、毛利率 -470bps、FY27 EPS 指引 $0.08-0.12 遠低於 $0.23 共識（指引腰斬）。'},
    'UA':   {'Type':'earnings','Catalyst':'Under Armour C 類股，同 UAA 因 Q4 FY26 大幅 rev/EPS miss + FY27 指引腰斬重挫 -13%。'},
    'HIMS': {'Type':'earnings','Catalyst':'Q1 營收 $608M 年增 4% 訂閱數 +9%，但因 GLP-1 品牌轉型陣痛一次性費用導致每股虧 $0.40（市場預期獲利 $0.04），毛利率 -800bps 至 65%。'},
    'HTCO': {'Type':'news','Catalyst':'5/7 股東批准資本結構大幅改造：B 類股投票權升至 100 倍、新增至 50 億股授權、董事會獲 1000:1 反向分割授權。'},
    'RAL':  {'Type':'earnings','Catalyst':'Q1 2026 營收 $534.6M 年增 11% 超預期 (+2.8%)、調整後 EPS $0.57 大超 $0.49 預期 (+16%)、上修 FY 營收指引至 $21.85-22.45 億（高於 $21.9B 共識）。'},
    'KOPN': {'Type':'contract','Catalyst':'獲美國國防 $21.5M 紅外熱影像跟單合約 + Fabric.AI $15M 訂單與 19.9% 股權，分析師三家升 Buy 目標 $5-5.50。'},
    'WEN':  {'Type':'M&A','Catalyst':'Q1 2026 EPS $0.12 微超預期、新中國 1000 店十年擴張協議 + Trian/Peltz 私有化收購傳聞；同店銷售 -6.8%、淨利 -42% 是負面，混合催化。'},
    'SE':   {'Type':'earnings','Catalyst':'Q1 2026 營收 $7.1B 年增 46.6%、淨利 +6.7%，Shopee GMV +30% / 營收 +45%，Garena 自 2021 年來最強季，Monee +58%，調整 EBITDA 首破 $1B。'},
    'INTC': {'Type':'analyst','Catalyst':'HSBC 降評至 Reduce、CPI 高於預期帶動科技股獲利了結，前期股價已大漲後反轉。'},
    'PLUG': {'Type':'earnings','Catalyst':'Q1 2026 營收 $163.5M 年增 22% 超預期 $148M (+10.5%)、EPS -$0.08 優於 -$0.10、毛利率改善 42 個百分點、目標 Q4 2026 達正 EBITDAS。'},
    'GTLB': {'Type':'news','Catalyst':'宣布 AI 轉型重組裁員、Raymond James 自 Outperform 降至 Market Perform、CEO 強調轉向「agentic era」企業平台。'},
    'BWEN': {'Type':'earnings','Catalyst':'Q1 EPS -$0.02 優於 -$0.06、營收 $34.1M 超預期 ($32.79M)，但 Abilene 工廠出售中撤回 FY 指引，由風塔轉型發電與工業基建。'},
    'SATL': {'Type':'earnings','Catalyst':'Q1 2026 營收 $6.1M 年增 80% 超預期 ($5.4M)，但淨損擴大至 -$118.3M (-263% YoY)，EPS -$0.84，Freedom Capital 與 WallStreetZen 雙雙降評。'},
    # Agent-supplied
    'ABCL': {'Type':'earnings','Catalyst':'Q1 2026 公布 ABCL-635 第一期試驗有利安全性數據並啟動第二期血管舒縮症狀試驗，現金 5.3 億美元支撐研發，但盤前 -8.95%。'},
    'AMBO': {'Type':'earnings','Catalyst':'Q1 2026 營收增至 280 萬美元、毛利率 60.2%、HybriU 業務年增超倍且轉虧為盈，帶動股價暴漲 +14%（盤前曾 +69%）。'},
    'ANDG': {'Type':'earnings','Catalyst':'Andersen Group Q1 2026 營收年增 15.7% 至 $240.7M、調整淨利 $62.9M，上修全年營收指引至 $980M-1B。'},
    'ASPI': {'Type':'news','Catalyst':'ASP Isotopes 5/12 公司簡報、受南非氦氣供應緊張下擴產提前、量子躍進能源獲 5 億美元美國資金挹注。'},
    'ASTS': {'Type':'earnings','Catalyst':'Q1 2026 EPS -$0.66 與營收 $14.7M 雙雙不如預期，但 35 億美元現金部位與重申 2026 年 $150-200M 營收指引推動股價。'},
    'AU':   {'Type':'earnings','Catalyst':'Q1 EPS $2.52 大超預期（+186% YoY）、新增 Nevada Arthur 金礦 490 萬盎司儲量、創高金價推升盈利展望。'},
    'AVEX': {'Type':'analyst','Catalyst':'Jefferies/Raymond James 等多家投行 5/12 啟動買進評級（目標 $32-35），看好自主無人機與 AI 平台成長。'},
    'BAK':  {'Type':'analyst','Catalyst':'JPMorgan 5/7 將 Braskem 自中性上調至加碼、目標價 $5.50，配合 Q1 石化開工率改善推動股價飆 +28%（盤前 +9%）。'},
    'BKKT': {'Type':'earnings','Catalyst':'Q1 2026 營收 $243.6M、淨虧 $11.7M，推進全股票收購 DTR、攜手 Zoth 拓展跨境穩定幣支付。'},
    'CLIK': {'Type':'earnings','Catalyst':'中期業績營收年增 57.3% 至 HK$59M、長者護理 +117.8%、由虧轉盈並提出三年 5 億港元計畫，但盤前 -10.62% 動能反轉。'},
    'CLSK': {'Type':'earnings','Catalyst':'Q2 2026 營收 $136.4M (-25% YoY)、淨虧 $378M（受比特幣公允價值非現金虧損 $224M 拖累），EPS -$1.52 遠遜預期。'},
    'DGXX': {'Type':'contract','Catalyst':'Cerebras IPO 即將上市、合作 40MW AI 資料中心 10 年合約價值 $1.1B，並加碼 ATM 募資 $100M。'},
    'ELPW': {'Type':'momentum','Catalyst':'中國 EV 電池小型股 ADR，3 月 1:80 反向拆股、Nasdaq Capital Market 轉板後純技術性低浮動炒作後反轉 -18.66%。'},
    'ERNA': {'Type':'FDA','Catalyst':'ERNA-101 卵巢癌前臨床數據與 PD-1 合用達 100% 長期存活，5/13 線上投資人活動展示。'},
    'EXK':  {'Type':'earnings','Catalyst':'Q1 2026 銀當量產量年增 78% 至 300 萬盎司、營收 $2.1 億增 23%，受惠銀價 + 黃金價飆升。盤前 -4.15%（獲利回吐）。'},
    'FLNC': {'Type':'news','Catalyst':'5/12 啟動承銷公開增發股票，疊加先前公布的 $5.6B 創高訂單與 hyperscaler 大廠主供應協議，但增發稀釋擔憂導致 -10%。'},
    'GENI': {'Type':'earnings','Catalyst':'Q1 2026 業績與完成 Legend 收購後 2026 年 EBITDA 利潤率指引上調至 28%，自有業務營收指引 $810-820M（+22%）。'},
    'GTN':  {'Type':'earnings','Catalyst':'Q1 EPS $0.34 vs 去年 $0.23（+48%）、營收 $768M 符合預期，但 Q2 營收指引 $790M 低於市場共識 1.5%。'},
    'HIMX': {'Type':'earnings','Catalyst':'Q1 營收 $199M 優於預期、Q2 指引季增 10-13%、毛利率 32%、EPS 季增近倍，AR 顯示器新品助攻，但盤前 -5.52% 獲利了結。'},
    'HLIT': {'Type':'earnings','Catalyst':'Harmonic Q1 寬頻營收年增 43% 至 $121.7M、EPS $0.17 大超預期 (+42%)，上修 FY 寬頻營收指引至 $475-495M。'},
    'HROW': {'Type':'earnings','Catalyst':'Q1 2026 營收 $44.2M、調整 EBITDA -$12.7M，重申 FY $350-365M 指引，依靠 VEVYE 銷售與 IOPIDINE J-code 下半年催化，但盤前 -11.93%。'},
    'HYLN': {'Type':'earnings','Catalyst':'Q1 EPS $0.07 低於去年 $0.10，但重申 FY R&D 服務營收 $10M、KARNO 175kW 技術里程碑、約 500 封意向書。'},
    'INSM': {'Type':'earnings','Catalyst':'Q1 2026 BRINSUPRI 營收季增 44% 至 $207.9M、重申 BRINSUPRI 逾 $10 億銷售指引、ENCORE Phase 3b 正面數據。'},
    'KC':   {'Type':'analyst','Catalyst':'Goldman Sachs 將 Kingsoft Cloud 自中性調升至買進、目標 $15.60，受惠 AI 業務帳單年增 95% 與 2026 capex 突破百億人民幣展望，但盤前 -5.57%。'},
    'KRMN': {'Type':'earnings','Catalyst':'Karman Holdings Q1 2026 創歷史新高、FY25 營收與 EBITDA 雙雙年增 37%、訂單背書年增 38% 至 $801M、上修 2026 指引。'},
    'LWLG': {'Type':'news','Catalyst':'5/13 Q1 2026 業績公布前獲利了結，先前因 IP 法律顧問布局商業化 EO 高分子平台而暴漲後 -4%。'},
    'LYG':  {'Type':'news','Catalyst':'Lloyds Banking 依買回計畫向 Goldman Sachs 回購 3,233 萬股、加權平均價 94.5432p、擬全數註銷。'},
    'MNTS': {'Type':'news','Catalyst':'Momentus Vigoride 7 發射成功、Vigoride 8 完成初步設計審核、4 月以私募增資 $5M、5/15 將公布 Q1 業績。'},
    'MRAM': {'Type':'contract','Catalyst':'拿下美國海軍 $40M、30 個月 Toggle MRAM 國防分包合約，Q1 營收年增 13%、毛利率擴張，盤後 +7.7% (盤前 -9.59% 反轉)。'},
    'NRGV': {'Type':'earnings','Catalyst':'Q1 營收年增 156% 至 $21.9M、訂單背書創 $13.5 億高、新增 100MW AI 資料中心、進軍日本 850MW 儲能 IPP 組合。'},
    'NWG':  {'Type':'news','Catalyst':'NatWest Group 商業/機構業務 CEO 5/11 以 £5.8358 出售 15 萬股，引發股價在強勁 AGM 反彈後獲利了結回調。'},
    'NXT':  {'Type':'earnings','Catalyst':'Nextpower FY26 營收年增 20% 至 $35.6 億、訂單背書創 $52.5 億高，但 FY27 指引中位數 $39.5 億成長放緩。'},
    'ONON': {'Type':'earnings','Catalyst':'On Holding Q1 銷售年增 26.4%（恆匯）至 CHF 8.3 億、EPS $0.47 大幅優於 $0.35 預期、上修 FY 毛利率至 64.5%。'},
    'PENG': {'Type':'earnings','Catalyst':'Penguin Solutions Q2 2026 EPS $0.52 大超 $0.37 預期、上修 FY26 營收成長至 12%、宣布與 AMD/Shell 合作 AI 資料中心。'},
    'PL':   {'Type':'contract','Catalyst':'Planet Labs 受 $9 億美元國防訂單背書與 AI/衛星情報主題延續推動，盤前獲利了結 -4.16%。'},
    'Q':    {'Type':'macro','Catalyst':'Quantum 板塊聯動：QUBT 5/11 公布 Q1 營收 $3.69M（年增 9400 倍）擊敗預期後同業跟漲。'},
    'QBTS': {'Type':'earnings','Catalyst':'D-Wave Q1 2026 預訂 $33.4M（+1994% YoY）、含 FAU $20M 系統銷售與 Fortune 100 企業 2 年 $10M QCaaS 合約，但 -7.32% 獲利了結。'},
    'QS':   {'Type':'earnings','Catalyst':'QuantumScape Q1 2026 淨損縮窄至 EPS -$0.16 優於 -$0.18 預期、Eagle Line 試產線啟用、首次認列 $11M 客戶帳單。'},
    'QUIK': {'Type':'earnings','Catalyst':'QuickLogic Q1 EPS -$0.08 不如 -$0.06 預期、營收 $5.05M 低於預期但年增 16.5%、獲 7 位數 eFPGA 國防新合約，但盤後 -15.43% 大跌。'},
    'RCAT': {'Type':'earnings','Catalyst':'Q1 營收年增 849% 至 $15.5M、毛利率由 -52.1% 翻轉至 12.7%、接獲日本陸軍及 NATO Black Widow 無人機新訂單，但盤後 -10.29%。'},
    'SBSW': {'Type':'earnings','Catalyst':'Sibanye-Stillwater Q1 EBITDA 年增 371% 至 R194 億，受惠金屬價格、產量、美國 PGM 稅收抵免，並完成 Keliber 鋰計畫建設啟動爬坡，盤前 -4.05% 獲利了結。'},
    'SIDU': {'Type':'news','Catalyst':'宣布 5/14 下午 5 點召開 Q1 2026 業績電話會議，激發投機性買盤後 -7.22% 反轉。'},
    'SNBR': {'Type':'earnings','Catalyst':'Q1 淨銷售 $319M、調整 EBITDA $5.8M 雙雙年減，但獲新增 $55M 流動性、3 月起新床 ARU 較舊存高 12%。'},
    'STAK': {'Type':'momentum','Catalyst':'低浮動量石油設備中概小型股 4 月剛恢復 Nasdaq 合規後純技術性、低流通量交易波動，無明確基本面催化。'},
    'TACT': {'Type':'earnings','Catalyst':'TransAct Q1 營收年增 10% 至 $14.4M、調整 EBITDA $1.4M、FST 軟體營收 +23%、博弈業務 +24%。'},
    'TE':   {'Type':'earnings','Catalyst':'Telos Q1 營收年增 56% 至 $47.7M、GAAP 淨利轉正 $2M、安全方案部門 +78%、重申 FY $187-200M 營收指引。'},
    'TME':  {'Type':'earnings','Catalyst':'Tencent Music Q1 2026 總營收年增 7.3% 至 RMB 79 億、音樂服務 +12.2%、毛利率擴至 44.9%，每 ADS RMB 1.34 略低預期但股價 +3.2%。'},
    'VG':   {'Type':'earnings','Catalyst':'Venture Global Q1 營收年增 59% 至 $46 億、出口 130 船 LNG 創新高、大幅上修 FY 調整 EBITDA 指引至 $82-85 億。'},
    'VOD':  {'Type':'earnings','Catalyst':'Vodafone FY26 全年營收年增 8%、調整 EBITDAaL +4.5%、轉虧為盈，且收購 CK Hutchison VodafoneThree 49% 股權 £43 億，但市場聚焦利潤壓力導致 -8.46%。'},
    'VSH':  {'Type':'momentum','Catalyst':'Vishay 5/13 公布 Q1 業績前一個月已狂飆 53%，受惠類比半導體板塊熱、市場預期 Q1 營收年增 15.7%。'},
    'WOLF': {'Type':'earnings','Catalyst':'Wolfspeed Q3 2026 EPS -$3.26 遠遜 -$0.56 預期、營收 $150.2M 低於 $209.8M 預期 28%，但因重整與 SiC 進展股價反彈 +8%。'},
    'WSE':  {'Type':'news','Catalyst':'Wise 5/11 完成 Nasdaq 雙重上市、5/12 公布 FY26 預備 US GAAP 數字（跨境量 $2,430 億 +31%、淨營收 $25 億 +19%），但市場聚焦利潤壓力 -6.43%。'},
    'WTI':  {'Type':'earnings','Catalyst':'W&T Offshore Q1 EPS $0 優於 -$0.07 預期、營收 $150M 擊敗 $126.7M 預期，但 Q2 產量指引下調、租賃費用 $71-79M 引發賣壓後 +4.37%。'},
    'XOS':  {'Type':'news','Catalyst':'Xos 將於 5/14 盤後公布 Q1 業績、預計營收 $6.225M、5/13-14 美空軍全球打擊司令部商業能力展示 17 強參展。'},
}

# Today's catalysts override — read catalysts_today.json if present (created fresh each /SIPs run).
# Schema: { "<TICKER>": { "Type": "earnings|...", "Catalyst": "繁中一句" }, ... }
# Falls through to the hardcoded `catalysts` dict above for tickers not in today's file.
today_path = os.path.join(DIR, 'catalysts_today.json')
catalysts_today = {}
if os.path.exists(today_path):
    with open(today_path, 'r', encoding='utf-8') as f:
        catalysts_today = json.load(f)

# Merge data
for c in candidates:
    sym = c['Symbol']
    cat = catalysts_today.get(sym) or catalysts.get(sym, {'Type':'?','Catalyst':'(無催化劑資料)'})
    c['Type'] = cat['Type']
    c['Catalyst'] = cat['Catalyst']
    tv = tv_by_ticker.get(sym)
    c['HasTV'] = tv is not None
    c['TV'] = tv

# Save consolidated CSV
csv_path = os.path.join(DIR, 'final-candidates.csv')
with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Symbol','Last','ChgPct','Volume','Session','Direction','Type','Name','Catalyst',
                'TV_LatestEPS','TV_PriorYrEPS','TV_LatestRev_M','TV_PriorYrRev_M','TV_YoYBlock'])
    for c in candidates:
        tv = c.get('TV') or {}
        w.writerow([c['Symbol'],c['Last'],c['ChgPct'],c['Volume'],c['Session'],c['Direction'],
                    c['Type'],c['Name'],c['Catalyst'],
                    tv.get('LatestEPS',''),tv.get('PriorYrEPS',''),tv.get('LatestRev_M',''),
                    tv.get('PriorYrRev_M',''),tv.get('YoYBlock','').replace('\n',' | ')])
print(f"Saved {csv_path}")
print(f"Total candidates: {len(candidates)}")
print(f"With TV data: {sum(1 for c in candidates if c['HasTV'])}")
print(f"Catalyst types:")
from collections import Counter
for t, n in Counter(c['Type'] for c in candidates).most_common():
    print(f"  {t}: {n}")
