# -*- coding: utf-8 -*-
import json, io
nd = {
 "HPE": {
   "detail": "HPE 於 6/1 盤後公布 Q2 FY26（截至 4/30）財報，**EPS $0.79 遠超市場預期 $0.53（+47.8% surprise）**，營收 **$106.8 億超估 $97.8 億（+9.2%）、YoY +40%**。\n\n爆發點在 AI 伺服器：管理層表示 **AI 系統訂單與 backlog 近翻倍**，傳統伺服器訂單亦翻倍；同時 **$140 億併購 Juniper Networks** 的網路業務整合進度優於預期。前一年同期 EPS 僅 $0.38，本季 YoY EPS +107.9%。\n\n公司上調全年展望，盤後一度 +28%、收盤 +9.35%。\n\n注意：未來 4Q EPS 估計 $0.64→$0.72→$0.69→$0.69，YoY 動能在第四季轉負（-12.66%），暗示本季為基期偏低放大的爆量，追高需留意開盤後 15 分鐘量能是否延續。",
   "publishedAt": "2026-06-01T16:05:00-04:00", "publishedTimezone": "ET",
   "sources": [
     {"label":"HPE Q2 FY26 IR","url":"https://investors.hpe.com/","publishedAt":"2026-06-01T16:05:00-04:00"},
     {"label":"Reuters — Technology","url":"https://www.reuters.com/technology/"},
     {"label":"SEC EDGAR — HPE 8-K","url":"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=HPE&type=8-K"}
   ]
 },
 "CDNS": {
   "detail": "Cadence 6/2 盤前 +4.8%，催化來自兩條：**推出 ChipStack AI Super Agent**，宣稱可將晶片驗證從 5 週縮短至 <1 天；同時**上修全年營收指引至 $61.25–62.25 億**（原 $59–60 億）。\n\nBofA 將目標價上修至 $400。最新季 EPS $1.96 超估 $1.91、營收 $14.7 億 +18.6% YoY，獲利能力穩健。\n\nCDNS 屬 Computex 後 AI 晶片設計（EDA）重評族群，與 ARM 同向。未來 4Q EPS 估 $2.05→$1.93→$1.98→$2.13，營收持續雙位數成長，是今日最乾淨的軟體型催化之一。",
   "publishedAt": "2026-06-02T07:00:00-04:00", "publishedTimezone": "ET",
   "sources": [
     {"label":"Cadence Newsroom","url":"https://www.cadence.com/en_US/home/company/newsroom.html"},
     {"label":"Reuters — Technology","url":"https://www.reuters.com/technology/"}
   ]
 },
 "ASAN": {
   "detail": "Asana 最新季（Q1 FY27，截至 4/30）**EPS $0.10 超估 $0.08（+33% surprise）、YoY +100%**，營收 $2.051 億超估、YoY +9.5%。\n\n獲利能力是亮點：**GAAP 營益率 YoY 改善約 1,600bps，non-GAAP 營益率創 11.5% 紀錄**。在 Huang Computex「agentic AI 放大企業軟體用量」背書下，整個企業軟體族群走強，ASAN 隨之 +8.3%。\n\n未來 4Q EPS 估 $0.09→$0.09→$0.10→$0.12，YoY EPS 維持 +20~50% 高速。屬族群帶動 + 自身獲利轉佳的雙重題材。",
   "publishedAt": "2026-05-29T16:05:00-04:00", "publishedTimezone": "ET",
   "sources": [
     {"label":"Asana Investor Relations","url":"https://investors.asana.com/"},
     {"label":"SEC EDGAR — ASAN","url":"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=ASAN&type=10-Q"}
   ]
 },
 "NBIS": {
   "detail": "Nebius 6/2 +5.4%，催化為 **前 OpenAI 研究員 Leopold Aschenbrenner 申報 13G、揭露 5.6% 持股**，市場視為 AI-infra 新雲業者的背書。\n\n基本面爆發：最新季營收 $3.99 億 **YoY +684%**（去年同期僅 $5,530 萬），超估 +6.4%；仍處虧損（EPS -$0.32，但優於估 -$0.77）。\n\n未來 4Q 營收估 $5.95 億→$9.33 億→$14.9 億→$22.9 億，呈拋物線成長。屬高 beta、高成長 AI 雲題材，波動大，適合動能交易但需嚴設停損。",
   "publishedAt": "2026-06-01T18:00:00-04:00", "publishedTimezone": "ET",
   "sources": [
     {"label":"SEC EDGAR — NBIS 13G","url":"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=NBIS&type=SC+13G"},
     {"label":"Nebius IR","url":"https://group.nebius.com/investors"}
   ]
 },
 "CRWV": {
   "detail": "CoreWeave 6/2 +4.8%，三條題材疊加：**首家部署並驗證 NVIDIA Vera Rubin NVL72**（宣稱推理每瓦效能達前代 10x）、投資推理新創 Tensormesh、以及 **6/26 將納入 Russell 3000**。\n\n最新季營收 $20.8 億 **YoY +112%**，超估 +5.5%；但仍大幅虧損（EPS -$1.11，差於估 -$0.92），資本支出沉重。\n\n未來 4Q 營收估 $25.7 億→$34.7 億→$45.5 億→$50.6 億，成長曲線陡峭但 EPS 持續為負。屬 Computex AI-infra 主軸的核心受惠股，動能強但估值與燒錢風險高。",
   "publishedAt": "2026-06-01T20:00:00-04:00", "publishedTimezone": "ET",
   "sources": [
     {"label":"CoreWeave Newsroom","url":"https://www.coreweave.com/news"},
     {"label":"NVIDIA Newsroom","url":"https://nvidianews.nvidia.com/"}
   ]
 },
 "ARM": {
   "detail": "Arm Holdings 6/2 盤前 +10.5%，由 **Computex NVIDIA 利多外溢 + 分析師連環上修目標** 驅動：RBC 將目標 $175→$260（資料中心權利金翻倍）、Mizuho 給 $360。\n\nNVIDIA RTX Spark Windows-on-Arm 超級晶片直接擴大 Arm 架構在 AI PC 與資料中心的觸角，是 QCOM/INTC 的鏡像受惠者。\n\n最新季 EPS $0.60 超估 $0.58、營收 $14.9 億 +20% YoY。未來 4Q EPS 估 $0.40→$0.44→$0.55→$0.78，YoY 動能後段加速（+27.9%、+30%）。屬 analyst-driven + 族群題材的多日 runner 候選。",
   "publishedAt": "2026-06-02T06:30:00-04:00", "publishedTimezone": "ET",
   "sources": [
     {"label":"Briefing.com — Analyst Actions","url":"https://www.briefing.com/"},
     {"label":"Reuters — Technology","url":"https://www.reuters.com/technology/"}
   ]
 },
 "TMHC": {
   "detail": "Taylor Morrison 6/2 盤前 +22.3%，**Berkshire Hathaway 宣布全現金併購，每股 $72.50、總額約 $68 億**（企業價值約 $85 億），較前收溢價約 24%。\n\n這是硬性 M&A 催化：股價直接跳空至接近成交價並收斂。對日內交易而言上檔已被現金對價封頂（$72.50），不適合追高動能，屬併購套利型而非 SIP 動能標的。\n\n風險：監管或股東審查；競價可能性低（Berkshire 全現金）。觀察是否有套利價差可賺取最後幾個百分點。",
   "publishedAt": "2026-06-02T07:00:00-04:00", "publishedTimezone": "ET",
   "sources": [
     {"label":"SEC EDGAR — TMHC 8-K","url":"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=TMHC&type=8-K"},
     {"label":"Reuters — Deals","url":"https://www.reuters.com/markets/deals/"}
   ]
 },
 "MGM": {
   "detail": "MGM Resorts 6/2 +11.3%，**People Inc.（前 IAC，已持股 26.1%）提出非約束性現金收購提案，每股 $48.30 收購剩餘 73.9%**，整體估值 >$180 億，溢價約 10.6%。\n\n屬初步、非約束性提案（非已簽署協議），因此股價未完全跳空至對價，仍有談判與盡職調查不確定性，較 TMHC 的 Berkshire 全現金確定併購弱。\n\n觀察：董事會回應、特別委員會成立、是否引發其他競標者。日內可交易性高於 TMHC（價差未封頂），但 headline 風險大。",
   "publishedAt": "2026-06-01T17:30:00-04:00", "publishedTimezone": "ET",
   "sources": [
     {"label":"SEC EDGAR — MGM 8-K","url":"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=MGM&type=8-K"},
     {"label":"Bloomberg","url":"https://www.bloomberg.com/"}
   ]
 },
 "FULC": {
   "detail": "Fulcrum Therapeutics 6/1 盤後 **-49.7%**，公司宣布**終止其唯一臨床計畫 pociredir（鎌狀細胞病）**。\n\n原因：FDA 對 PRC2 抑制劑類藥物致**二次血液惡性腫瘤風險**有安全疑慮（同類 Tazverik 已於 3 月全球撤市）。公司同步啟動**策略檢討**（potential sale / 清算）。\n\n管線歸零、現金成為唯一價值支撐。EPS 估計持平於 -$0.27 附近、無營收。屬基本面已 de-risk 向下的破底股，反彈僅靠現金/併購投機；做空風險在於現金價值若高於股價時的軋空。",
   "publishedAt": "2026-06-01T16:15:00-04:00", "publishedTimezone": "ET",
   "sources": [
     {"label":"Fulcrum Therapeutics IR","url":"https://ir.fulcrumtx.com/"},
     {"label":"SEC EDGAR — FULC 8-K","url":"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=FULC&type=8-K"}
   ]
 },
 "OCS": {
   "detail": "Oculis Holding 6/2 **-30%**，**DIAMOND-1 與 DIAMOND-2 兩項 Phase 3（糖尿病黃斑水腫 DME）主要終點雙雙失敗**，公司放棄該適應症的 FDA 申請。\n\n這是 binary 試驗失敗：核心晚期資產報廢，剩餘管線價值需重估。Levi & Korsinsky 等已啟動股東調查。\n\n最新季營收極小（$0.25M）、持續虧損（EPS -$0.61）。未來營收 YoY 估計轉負（-34%~-66%）。屬乾淨的負催化做空標的，但小型生技反彈劇烈，需嚴設停損、留意現金部位。",
   "publishedAt": "2026-06-02T06:00:00-04:00", "publishedTimezone": "ET",
   "sources": [
     {"label":"Oculis News & Events","url":"https://www.oculis.com/news-events/"},
     {"label":"SEC EDGAR — OCS 6-K","url":"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=OCS&type=6-K"}
   ]
 },
 "CRDO": {
   "detail": "Credo Technology 6/1 盤後 **-11.7%**，這是一個「**beat 但不夠強**」的獲利了結案例。\n\nQ4（截至 5/2）**EPS $1.16 超估 $1.02、營收 $4.37 億 YoY +157%**，全面超預期。但股價在財報前已大漲、預期過高，數字未能再超出 buy-side whisper，引發拉回。\n\n未來 4Q EPS 估 $1.11→$1.17→$1.46→$1.87，YoY 仍 +74~113% 高速成長——基本面並未轉壞。屬「強財報 + 弱反應」的短線做空/觀望，但中期趨勢仍多，不宜重壓空方；適合日內回補。",
   "publishedAt": "2026-06-01T16:05:00-04:00", "publishedTimezone": "ET",
   "sources": [
     {"label":"Credo Q4 FY26 IR","url":"https://investors.credosemi.com/"},
     {"label":"SEC EDGAR — CRDO 8-K","url":"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=CRDO&type=8-K"}
   ]
 },
 "QCOM": {
   "detail": "Qualcomm 6/2 盤前 **-6.9%**，利空來自 **Computex NVIDIA 發表 RTX Spark Windows-on-Arm 超級晶片**，直接威脅 Snapdragon X Elite 在 AI PC 的地位，且 Dragonfly 資料中心品牌被搶風頭。\n\n基本面本就轉弱：最新季 EPS $2.65 雖超估，但 **YoY -7%**，營收 YoY -2.2%。未來 4Q YoY 估計持續惡化（EPS -20%~-23%、營收 -6.9%~-12%），反映手機與授權業務成熟、AI PC 競爭加劇。\n\n大型流動性佳、適合日內做空。風險在於估值已低 + 超跌反彈，宜分批進場。",
   "publishedAt": "2026-06-02T06:30:00-04:00", "publishedTimezone": "ET",
   "sources": [
     {"label":"Reuters — Technology","url":"https://www.reuters.com/technology/"},
     {"label":"Qualcomm IR","url":"https://investor.qualcomm.com/"}
   ]
 },
 "CRSR": {
   "detail": "Corsair Gaming 6/2 **-15.6%**，**Craig-Hallum 將評級由 Buy 降至 Hold、目標價 $10**。\n\n理由：擔憂 FY26 消費電子需求疲弱 + **記憶體漲價壓縮毛利**（記憶體佔上季營收約 42%，DRAM 漲價直接侵蝕利潤）。\n\n屬分析師降評型負催化，配合消費疲弱與記憶體成本的雙重逆風。做空可參考 $10 目標價為下檔參考，但單一降評殺傷力有限，留意超賣反彈。",
   "publishedAt": "2026-06-02T07:00:00-04:00", "publishedTimezone": "ET",
   "sources": [
     {"label":"TheFly — Analyst Actions","url":"https://thefly.com/"},
     {"label":"Corsair IR","url":"https://ir.corsair.com/"}
   ]
 }
}
with io.open('news_detail.json','w',encoding='utf-8') as f:
    json.dump(nd, f, ensure_ascii=False, indent=2)
print('wrote', len(nd), 'news_detail entries')
