# -*- coding: utf-8 -*-
import json, io
with io.open('news_detail.json', encoding='utf-8') as f:
    nd = json.load(f)
add = {
 "DG": {
   "detail": "Dollar General 6/2 +5.3%，Q1 FY26 財報 beat：**EPS $1.93 超估 $1.66（+16.4% surprise）**，營收 $109.1 億微超估、YoY +5.9%。\n\n必需消費通路防禦性題材：通膨環境下低價零售客流穩健，毛利率改善。最新季 YoY EPS +14.9%，回到成長軌道。\n\n未來 4Q EPS 估 YoY +6~15%，營收溫和成長。屬大型流動性佳、波動可控的穩健 earnings 長單。觀察同店銷售（SSS）與全年指引是否同步上修，以及消費降級趨勢對其客群的助益。",
   "publishedAt": "2026-06-02T06:55:00-04:00", "publishedTimezone": "ET",
   "sources": [
     {"label":"Dollar General IR","url":"https://investor.dollargeneral.com/","publishedAt":"2026-06-02T06:55:00-04:00"},
     {"label":"Reuters — Retail","url":"https://www.reuters.com/business/retail-consumer/"}
   ]
 },
 "SMCI": {
   "detail": "Super Micro 6/1 盤後 +5%，財報呈現**獲利強、營收弱**的混合訊號：**EPS $0.84 超估 $0.62（+36% surprise）**，但**營收 $102.4 億 miss 估 -17.3%**。\n\n分析師面：Mizuho 上調目標 $36→$44（維持 Neutral），引述 agentic AI 伺服器需求；公司推出 12 款 Intel Xeon 6+ 新伺服器平台。\n\n最新季 YoY EPS +171%、營收 +123%，成長仍高速但營收 miss 反映拉貨節奏與供應鏈波動。搭 HPE 同向 AI-infra 題材，但營收 miss 限制追高空間，宜留意毛利率與下季指引。",
   "publishedAt": "2026-06-01T16:10:00-04:00", "publishedTimezone": "ET",
   "sources": [
     {"label":"Super Micro IR","url":"https://ir.supermicro.com/"},
     {"label":"SEC EDGAR — SMCI 8-K","url":"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=SMCI&type=8-K"}
   ]
 },
 "MCHP": {
   "detail": "Microchip 6/1 盤後 +9.3%，**EPS $0.57 超估 $0.50（+12.9%）、營收 $13.1 億超估 +3.8%**。\n\n關鍵在循環復甦訊號：**YoY EPS +418%**——自類比/MCU 庫存週期谷底大幅回升，暗示下游需求與通路庫存去化接近尾聲。\n\n屬 earnings + 半導體循環觸底反彈的雙重題材，量大波動足。未來 4Q EPS 維持高速 YoY，若庫存週期確認轉折，具多日延續潛力。觀察管理層對通路庫存與訂單能見度的評論。",
   "publishedAt": "2026-06-01T16:05:00-04:00", "publishedTimezone": "ET",
   "sources": [
     {"label":"Microchip IR","url":"https://www.microchip.com/en-us/about/investor-relations"},
     {"label":"SEC EDGAR — MCHP 8-K","url":"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=MCHP&type=8-K"}
   ]
 },
 "LAC": {
   "detail": "Lithium Americas 6/1 盤後 +17.4%，**Q1 首度轉盈**：淨利約 $460 萬（去年同期虧損）。\n\n營運面：Thacker Pass 鋰礦專案進展 + 阿根廷營運貢獻。選擇權市場異常活躍——**看漲選擇權 39,464 口、約常態 3 倍**，IV +3pt 至 92.39，顯示市場押注延續性。\n\n屬鋰價築底 + 轉盈拐點題材，小型高 beta 動能標的。風險：鋰價反覆、礦業專案執行風險。日內波動大，嚴設停損、避免在 IV 高檔追高。",
   "publishedAt": "2026-06-01T16:30:00-04:00", "publishedTimezone": "ET",
   "sources": [
     {"label":"Lithium Americas IR","url":"https://www.lithiumamericas.com/investors/"},
     {"label":"SEC EDGAR — LAC","url":"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=LAC&type=10-Q"}
   ]
 },
 "ABVX": {
   "detail": "Abivax 6/1 盤後 **-25.2%**——一個「**好數據、壞反應**」的稀釋型殺盤。\n\nobefazimod 的 **44 週 Phase 3 維持期達主要終點**（25mg/50mg 劑量均達臨床緩解），數據本身是利多。但近期公司進行 **ADS 增發 + 轉售登記**，造成股本稀釋與賣壓，疊加數據公布後的獲利了結，引發回落。\n\n做空邏輯是技術面（稀釋 + 過度延伸後修正）而非基本面崩壞——核心藥物數據仍佳。因此反彈可能劇烈，做空僅適合日內、嚴控風險，避免與基本面利多對作過久。",
   "publishedAt": "2026-06-01T16:20:00-04:00", "publishedTimezone": "ET",
   "sources": [
     {"label":"Abivax press release","url":"https://www.abivax.com/en/media/press-releases/"},
     {"label":"SEC EDGAR — ABVX 6-K","url":"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=ABVX&type=6-K"}
   ]
 },
 "ORIC": {
   "detail": "ORIC Pharmaceuticals 6/1 盤後 **-9.8%**，推進前列腺癌候選藥（rinzimetostat 調整至 400mg 劑量）至 Phase 3，但市場對其**安全性 / 劑量反應**仍有疑慮（先前 3 月曾因劑量調整重挫，此為餘波重定價）。\n\n屬臨床期生技的劑量/安全重定價型負催化，無營收、持續燒錢。\n\n做空為小型高波動標的，反彈劇烈，僅適合日內、嚴設停損；留意現金部位與任何後續臨床更新可能引發的軋空。",
   "publishedAt": "2026-06-01T16:30:00-04:00", "publishedTimezone": "ET",
   "sources": [
     {"label":"ORIC Pharmaceuticals IR","url":"https://ir.oricpharma.com/"},
     {"label":"SEC EDGAR — ORIC","url":"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=ORIC&type=8-K"}
   ]
 }
}
nd.update(add)
with io.open('news_detail.json', 'w', encoding='utf-8') as f:
    json.dump(nd, f, ensure_ascii=False, indent=2)
print('news_detail now has', len(nd), 'entries')
