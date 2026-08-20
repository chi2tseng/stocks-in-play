# -*- coding: utf-8 -*-
"""Write news_detail.json for 2026-08-05 scan."""
import json, io, os

ND = {}

ND["ANET"] = {
 "detail": """> **今日漲因:** 盤前 +15.7% — 8/4 盤後公布 Q2 財報,單季營收 **首度突破 30 億美元**、年增 37.7%,Q3 財測 33 億美元比華爾街預估高出 12%。

**財報詳解**

Arista 8/4 收盤後公布 2026 年第二季:營收 **$30.36 億**,較去年同期 $22.05 億成長 **37.7%**,較上一季成長 12.1%,超出華爾街預估的 $28.3 億約 **7.4%**。非 GAAP 每股盈餘 **$1.02**,高於預估的 $0.88、去年同期的 $0.73;GAAP 每股盈餘 $0.95(去年同期 $0.70)。

**分部與營運細節**

產品銷售 **$26.05 億**、服務收入 **$4.305 億**。毛利率是這份財報唯一往下走的數字:GAAP 毛利率 **62.9%**(去年同期 65.2%)、非 GAAP 毛利率 **63.4%**(去年同期 65.6%),兩者都比去年低約 2.2 個百分點 —— 這是 AI 資料中心大單佔比升高、產品組合稀釋的結果。但營業利益率仍維持在極高水準:GAAP 45.4%、非 GAAP **49.9%**。採購承諾(purchase commitments)本季來到 **$97 億**,顯示公司正為後續出貨大量備料。

**管理層說法**

執行長 Jayshree Ullal 在新聞稿中說:「As we deliver our first $3 billion quarter in Q2 2026, our Arista 2.0 platform strategy is compelling. Customers see networking as the central nervous system for infrastructure.」(我們交出第一個 30 億美元的季度,Arista 2.0 平台策略深具說服力;客戶把網路視為整個基礎設施的中樞神經系統。)財務長 Chantelle Breithaupt 補充,調整後每股盈餘年增 39.7%。

**指引 —— 這才是股價跳空的主因**

Q3 財測營收約 **$33 億**,而華爾街原本只預估 $29.5 億,等於一口氣高出 **約 12%**;非 GAAP 每股盈餘財測 **$1.06-1.08**,同樣遠高於共識的 $0.92。非 GAAP 營業利益率財測 48-49%。財報本身超預期只是門票,把下一季預估整個往上推 12% 才是盤後直接跳 10-13% 的原因。

**分析師與市場反應**

美國銀行(Bank of America)在報告中形容 Arista「continues to fire on all cylinders with accelerated demand across AI, Campus, and core data center switching」(AI、園區網路與核心資料中心交換器三條線需求同步加速)。摩根士丹利 8/5 盤前把目標價由 $190 調升至 **$220**,維持 Overweight。

**風險備註**

遞延收入年增率已從先前的高檔放緩至約 70%,部分賣方把它視為觀察後續訂單動能的指標;毛利率連兩季走低也值得追蹤。""",
 "publishedAt": "2026-08-04T16:05:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "Arista Networks Q2 2026 業績報導", "url": "https://blockonomi.com/arista-networks-inc-anet-stock-q2-revenue-jumps-37-7-as-ai-networking-demand-accelerates/"},
  {"label": "Yahoo Finance — Arista soars on strong outlook", "url": "https://uk.finance.yahoo.com/news/arista-networks-soars-13-strong-204417664.html"},
  {"label": "MT Newswires — Morgan Stanley 上調目標價至 $220", "url": "https://finance.yahoo.com/markets/stocks/articles/morgan-stanley-adjusts-pt-arista-093247458.html"}
 ]}

ND["PGEN"] = {
 "detail": """> **今日漲因:** 盤後 +8.3% — Q2 營收 **$5,500 萬**,而去年同期只有 **$90 萬**,新藥 PAPZIMEOS 單季貢獻 $5,310 萬,公司同時由虧轉盈。

**財報詳解**

Precigen 8/4 下午 4:01 ET 公布第二季財報。總營收 **$5,500 萬**,去年同期為 **$90 萬** —— 這不是百分比成長的問題,而是一家臨床期公司正式變成有商業產品的公司。上半年累計營收 $7,820 萬,其中 PAPZIMEOS 佔 $7,470 萬。

單季淨利 **$2,010 萬**、基本每股盈餘 **$0.06**(稀釋後 $0.05);去年同期為淨損 $2,660 萬、每股虧損 $0.09。

**產品爬坡細節**

PAPZIMEOS 單季產品淨收入 **$5,310 萬**,服務收入 $170 萬。支撐這個爬坡的三件事:
- 病患服務中心(hub)累計註冊 **500 位以上**病患
- 支付方覆蓋約 **3.15 億**名美國保戶,實質上等於全美有保險人口
- 永久性給付代碼 **J-code(J3404)** 自 2026/4/1 生效 —— 這是決定醫院願不願意大量使用的關鍵行政門檻
- FDA 給予 **7 年市場專屬權**;歐盟 EMA 的上市申請仍在審查中

**成本結構**

產品與服務成本 $280 萬(年增 $170 萬);研發費用 $730 萬,年減 $420 萬(臨床支出隨商業化下降);銷售管理費用 $2,220 萬,年增 $610 萬(擴編業務團隊)。去年同期認列的 $390 萬商譽減損本季為零。

**管理層說法**

財務長在新聞稿表示:「Based upon our current revenue trajectory... we continue to believe that our current cash position... will fund operations through cash flow break-even by the end of 2026.」(依目前的營收軌跡,我們仍相信現有現金足以支撐營運到 2026 年底達成現金流損益兩平。)

**籌碼面**

Finviz 資料顯示 PGEN 空單佔流通股 **25.76%**、回補天數 **8.54 天** —— 以 MAGNA53 的「5」(days to cover > 5)標準來看,這是明確的軋空燃料。近一個月股價已漲 29.6%、近半年 +48.8%。

**風險備註**

6/30 帳上現金與約當現金加投資僅 **$3,870 萬**,長期債務 **$9,390 萬**。管理層的「年底現金流打平」說法若跳票,增資壓力會很直接。""",
 "publishedAt": "2026-08-04T16:01:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "Precigen Q2 2026 財報新聞稿", "url": "https://www.stocktitan.net/news/PGEN/precigen-reports-second-quarter-2026-financial-results-highlighted-dszw7t9e0qhq.html", "publishedAt": "2026-08-04T16:01:00-04:00"}
 ]}

ND["KTOS"] = {
 "detail": """> **今日漲因:** 盤前 +10.4% — Q2 營收 **$4.588 億**、年增 30.5%,超出華爾街預估 11%,全年營收指引上調至 **$17.5-18.1 億**,在手訂單衝上 **$20.84 億**。

**財報詳解**

Kratos 8/4 盤後公布第二季:營收 **$4.588 億**,去年同期 $3.515 億,年增 **30.5%**,其中**有機成長 19.1%**(其餘來自併購)。這個數字超出 7 位分析師的共識 $4.117 億約 **11%**。調整後每股盈餘 **$0.21**,遠高於預估的 $0.13 與去年同期的 $0.11。GAAP 淨利 $440 萬(去年同期 $290 萬)。

**分部細節**

- **政府解決方案(Government Solutions)** 營收 **$3.797 億**,年增 **36.4%**、有機成長 22%
- **無人系統(Unmanned Systems)** 營收 **$7,910 萬**,年增 8.1%;本季接單 $7,840 萬,該分部在手訂單 $3.746 億

調整後 EBITDA **$3,820 萬**;不過本季仍有 $160 萬的營業虧損(GAAP 認列)。

**訂單能見度 —— 這是防衛股的重點**

- 總在手訂單 **$20.84 億**
- 本季接單 **$4.922 億**
- 12 個月接單出貨比(book-to-bill)**1.3**(大於 1 代表訂單流入快於認列)
- 提案中的商機管線(proposal pipeline)**$150 億**

**指引**

Q3 營收財測 **$4.60-4.80 億**;全年營收指引上調至 **$17.5-18.1 億**,有機成長預估同步調升至 **18-23%**。

**籌碼面**

空單佔流通股 5.62%、回補天數 2.15 天,不構成軋空題材。近一個月 +13.8%,但近半年仍 -44.6% —— 股價是從高檔大幅回落後才反彈,不是追在歷史高點。

**風險備註**

本季 GAAP 層面仍是營業虧損,獲利品質靠調整後數字支撐;可查來源中未見具名分析師於 8/4-8/5 調整評等或目標價。""",
 "publishedAt": "2026-08-04T16:05:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "AP — Kratos Q2 earnings snapshot", "url": "https://www.aol.com/articles/kratos-q2-earnings-snapshot-213858000.html"},
  {"label": "Kratos Q2 2026 業績與 Valkyrie 訂單報導", "url": "https://blockonomi.com/kratos-defense-ktos-stock-jumps-as-31-revenue-growth-and-valkyrie-orders-fuel-q2-rally/"}
 ]}

ND["AMPX"] = {
 "detail": """> **今日漲因:** 盤後 +10.4% — Q2 營收 **$3,400 萬**、年增 **126%**,毛利率從 9% 拉到 **27%**,並上調全年財測、首度預告全年調整後 EBITDA 轉正。

**財報詳解**

Amprius 8/4 下午 4:05 ET 公布第二季。營收 **$3,400 萬**,去年同期 $1,510 萬,年增 **126%**(2.3 倍),比上一季成長 19%。GAAP 每股虧損 **$0.04**(去年同期虧 $0.05),調整後每股虧損 $0.02。

**毛利率是這份財報真正的重點**

毛利 **$930 萬**,去年同期只有 $130 萬;毛利率由 **9% 拉升到 27%**,一年拉高 18 個百分點。營業虧損收窄至 $430 萬,調整後 EBITDA **-$100 萬**(去年同期 -$210 萬),已經逼近打平。對一家電池材料公司來說,營收翻倍的同時毛利率還能翻三倍,代表規模效益是真的開始出現,不是靠拉低售價衝量。

**訂單與產能**

- 與 **Stark Future** 簽下多年期供應合約,總額 **超過 $1 億**,自 2027 年開始交貨
- 一家未具名的歐洲無人機製造商下單 **$2,400 萬**
- 加州 Fremont 試產線擴建進度約 **40%**;另透過南韓代工夥伴擴充產能

**管理層說法**

執行長 Tom Stepien:「Revenue growing 2.3x year over year and gross margin expanding to 27%」(營收年增 2.3 倍,毛利率擴張到 27%)。財務長 Ricardo C. Rodriguez:「This was a strong quarter...with robust sequential growth, and gross margins on the path that we've been expecting」(這是很強的一季,季增穩健,毛利率走在我們預期的軌道上)。

**指引全面上調**

- 全年營收:**至少 $1.40 億**(原財測 $1.30 億)
- 全年毛利率:**至少 28%**(原 25%)
- 全年淨損:**低於 $1,000 萬**
- 全年調整後 EBITDA:**至少 $400 萬**(由負轉正)
- 資本支出:低於 $1,000 萬

**風險備註**

6/30 帳上現金與約當現金 **$7,450 萬**,而上半年營運現金流出 **$4,010 萬** —— 以目前燒錢速度約可支撐一年多。全年 EBITDA 轉正的財測若沒兌現,增資風險會回來。""",
 "publishedAt": "2026-08-04T16:05:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "Amprius Technologies Q2 2026 財報新聞稿 (IR)", "url": "https://ir.amprius.com/news-events/press-releases/detail/172/amprius-technologies-reports-second-quarter-2026-financial-results-and-recent-business-highlights", "publishedAt": "2026-08-04T16:05:00-04:00"}
 ]}

ND["UPST"] = {
 "detail": """> **今日漲因:** 盤後 +11.2% — Q2 營收 **$3.65 億**、年增 42%,撥貸量 **$42 億**、年增 50%,貢獻利潤創歷史新高 $1.93 億,且 GAAP 已回到獲利。

**財報詳解**

Upstart 8/4 下午 4:05 ET 公布第二季。總營收 **$3.65 億**,年增 **42%**;其中手續費收入 **$3.48 億**,年增 **45%**。GAAP 稀釋每股盈餘 **$0.16**,去年同期只有 $0.05;淨利 **$1,650 萬**,年增 195%。

**營運指標**

- 撥貸量(originations)**$42 億**,年增 **50%**;件數 **558,014 筆**,同樣年增 50%
- 貢獻利潤(contribution profit)**$1.93 億**,歷史新高,年增 37%
- **91%** 的貸款為全自動化核貸(不需人工介入)
- 調整後 EBITDA **$7,690 萬**,年增 45%,利潤率 21%

**兩個往下走的數字要一起看**

轉換率(conversion rate)**19.7%**,低於去年同期的 21.0%;貢獻利潤率 **55%**,也低於去年的 58%。也就是說,這一季的成長是「量」推動的,單位經濟效益略微稀釋。撥貸量 +50% 但貢獻利潤只 +37%,兩者的落差就是這 3 個百分點。

**管理層說法**

執行長 Paul Gu 提到核心個人信貸業務「re-accelerating growth」(成長重新加速),並強調公司「returned to GAAP profitability」(回到 GAAP 獲利)。

**指引**

全年財測**維持不變**:總營收約 **$14 億**、手續費收入約 $13 億、調整後 EBITDA 約 **$2.94 億**(利潤率 21%)。單季超預期但不調高全年,是這份財報比較保守的一面。

**籌碼面 —— 這是 UPST 的第二層題材**

空單佔流通股 **31.95%**、回補天數 **5.76 天**。以 Stockbee MAGNA53 的「5」(days to cover > 5)判準,這是明確的軋空結構;近一個月股價幾乎沒動(+1.0%),半年仍 -13.4%,籌碼並未事先擁擠。

**風險備註**

帳上現金與約當現金 **$4.56 億**,總資產 $31.71 億 —— Upstart 的資產負債表上持有貸款部位,利率與信用循環的敏感度高於一般軟體公司。""",
 "publishedAt": "2026-08-04T16:05:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "Upstart Q2 2026 財報新聞稿", "url": "https://www.stocktitan.net/news/UPST/upstart-announces-second-quarter-2026-5mglh8cp71et.html", "publishedAt": "2026-08-04T16:05:00-04:00"}
 ]}

ND["COMP"] = {
 "detail": """> **今日漲因:** 盤後 +12.1% — Q2 營收 **$43.1 億**、調整後 EBITDA **$3.63 億**創任何第二季的歷史新高,經紀人留存率升到 95.5%,且併購綜效目標再上調。

**財報詳解**

Compass 8/4 下午 4:05 ET 公布第二季。總營收 **$43.1 億**。這裡有一個必須講清楚的口徑問題:申報數字年增 **109%**,但那是把一樁大型併購併進來的結果;**同基期(pro forma)比較只成長 14.3%**(去年同期 pro forma $37.7 億)。看這檔股票要用 14.3% 這個數字,不是 109%。

GAAP 淨利 **$9,200 萬**;調整後 EBITDA **$3.63 億**,利潤率 8.4%,是公司史上任何一個第二季的最高紀錄。

**營運指標**

- 自營經紀(Brokerage)成交總額 GTV **$1,552 億**,同基期年增 **15.9%**
- 加盟(Franchise)GTV **$1,200 億**,同基期年增 11.7%
- 自營成交件數 **153,009 件**(同基期 +7.4%);加盟 203,207 件(+3.8%)
- 經紀人總數 **83,184 人**;本季新增 2,816 人
- **經紀人留存率 95.5%**,較上一季的 94.1% 明顯回升

**管理層說法**

執行長 Robert Reffkin:「our outperformance versus the industry accelerated, with Brokerage GTV up 15.9% YoY...reflecting approximately 1,000 basis points of GTV outperformance.」(我們相對產業的超額表現正在加速,自營 GTV 年增 15.9%,約領先產業 10 個百分點。)財務長 Scott Wahlers:「We delivered $4.3 billion in Revenue...Adjusted EBITDA grew to $363 million, which is an all-time record for any second quarter in our history.」

**指引與併購綜效**

Q3 財測:營收 **$38.5-40.5 億**、調整後 EBITDA **$2.75-3.05 億**。全年非 GAAP 營業費用 $27.5-28.0 億,自由現金流預期為正。併購第一年的成本綜效目標 **$3 億提前 5 個月達成**,目標再上調至 **$3.3 億**;2026 年可實現綜效由 $2 億上調至 $2.2 億。

**風險備註**

長期負債 **$31.4 億**,帳上現金 $6.94 億(較上季增加 $2.1 億);本季營運現金流 $1.91 億、自由現金流 $1.80 億。在房市成交量仍受利率牽制的環境下,這個負債水位是這檔股票的主要壓力來源。""",
 "publishedAt": "2026-08-04T16:05:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "Compass Q2 2026 財報新聞稿 (IR)", "url": "https://investors.compass.com/news-events/press-releases/detail/177/compass-inc-reports-record-second-quarter-2026-results", "publishedAt": "2026-08-04T16:05:00-04:00"}
 ]}

ND["APPS"] = {
 "detail": """> **今日漲因:** 盤後 +30.6% — FY27 Q1 營收 **$1.66 億**、年增 27%,調整後 EBITDA **$4,250 萬**、年增 69%,並上調全年財測。

**財報詳解**

Digital Turbine 8/4 下午 4:05 ET 公布 2027 會計年度第一季(對應 2026 年 6 月止季度)。營收 **$1.66 億**,去年同期 $1.309 億,年增 **27%**。非 GAAP 調整後每股盈餘 **$0.19**;GAAP 仍為每股虧損 $0.03(淨損 $320 萬)。

**兩大分部**

- **On Device Solutions(ODS,裝置端預載/推薦)** 營收 **$1.10 億**,年增 15%
- **App Growth Platform(AGP,廣告投放平台)** 營收 **$5,660 萬**,年增 **56%**

成長主要由 AGP 帶動 —— 這一段的年增速度是 ODS 的近四倍,代表營收結構正在往廣告平台傾斜。

**獲利品質**

非 GAAP 調整後 EBITDA **$4,250 萬**,年增 **69%**,利潤率 **25.6%**。營收 +27% 但 EBITDA +69%,這個槓桿差距是股價跳空 30% 的核心 —— 市場看到的是營運槓桿開始發揮,不只是營收回溫。本季自由現金流 **$1,130 萬**。

**管理層說法**

執行長在新聞稿中表示:「Our strong first quarter results reflect an encouraging start to the new fiscal year」(強勁的第一季為新會計年度開了一個令人鼓舞的頭),並提到公司運用 AI 夥伴關係與工具來優化平台成效。

**指引上調**

FY2027 全年財測調升為:營收 **$6.50-6.70 億**、非 GAAP 調整後 EBITDA **$1.45-1.55 億**。

**風險備註**

資產負債表是這檔股票最大的隱憂:總債務 **$3.529 億**,而帳上現金只有 **$4,320 萬**,股東權益 $1.906 億。獲利改善若中斷,這個負債結構的容錯空間很小。可查來源中未見 8/4-8/5 具名分析師的目標價調整。""",
 "publishedAt": "2026-08-04T16:05:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "Digital Turbine FY2027 Q1 財報新聞稿 (IR)", "url": "https://ir.digitalturbine.com/news-events/press-releases/detail/705/digital-turbine-reports-strong-fiscal-2027-first-quarter", "publishedAt": "2026-08-04T16:05:00-04:00"}
 ]}

ND["KODK"] = {
 "detail": """> **今日漲因:** 盤後 +11.6% — Q2 營收 **$3.11 億**、年增 18%,毛利率由 19% 升到 **26%**,由去年同期虧損 $2,600 萬轉為淨利 **$1,700 萬**,長期負債同時砍半。

**財報詳解**

Eastman Kodak 8/4 下午 4:15 ET 公布第二季。營收 **$3.11 億**,去年同期 $2.63 億,年增 **18%**。GAAP 稀釋每股盈餘 **$0.13**,去年同期為每股虧損 $0.36;淨利 **$1,700 萬**,對比去年同期淨損 $2,600 萬。

**三個分部**

- **Print(印刷)** 營收 **$1.95 億**
- **Advanced Materials & Chemicals(先進材料與化學)** 營收 **$1.05 億**
- **Brand(品牌授權)** 營收 **$700 萬**

**獲利結構改善**

毛利 **$8,200 萬**,毛利率 **26%**,去年同期只有 **19%** —— 一年拉高 7 個百分點。營運 EBITDA **$3,600 萬**,去年同期僅 $900 萬,是四倍的跳升。

**負債處理是這季被低估的一段**

本季償還定期貸款 **$1.01 億**,長期債務由 **$2.08 億降到 $1.08 億**。退休金與退休後福利計畫資產 $3.04 億、負債 $1.86 億,本季認列 $500 萬的退休金收益(不含服務成本)。柯達過去多年最大的財務包袱就是退休金與債務,這一季的處理進度是實質的。

**管理層說法**

執行董事長暨執行長 Jim Continenza:「The words that sum up our performance in the second quarter are stability and growth. We continued to deliver strong results for the fourth consecutive quarter, achieving significant year-over-year improvement in revenue, gross profit and Operational EBITDA.」(總結第二季表現的兩個詞是穩定與成長;我們連續第四季交出強勁結果,營收、毛利與營運 EBITDA 都有顯著年增改善。)

**籌碼面**

空單佔流通股 **10.23%**、回補天數 **6.69 天**,符合 MAGNA53 的「5」判準;近一個月 +22.1%、近半年 +34.9%。

**風險備註**

新聞稿**未提供 2026 全年財測**。帳上現金 **$2.90 億**,較 2025/12/31 減少 $4,700 萬 —— 償債用掉了不少現金部位。""",
 "publishedAt": "2026-08-04T16:15:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "Kodak Q2 2026 財報新聞稿", "url": "https://www.stocktitan.net/news/KODK/kodak-reports-second-quarter-2026-financial-kuk0ueogobns.html", "publishedAt": "2026-08-04T16:15:00-04:00"}
 ]}

ND["TDC"] = {
 "detail": """> **今日跌因:** 盤後 -17.9% — Q2 每股盈餘 $0.69 大勝預估 $0.55、營收 $4.10 億持平,但**年度經常性收入(ARR)只成長 1%**,市場認定成長引擎已經熄火。

**財報詳解**

Teradata 8/4 公布第二季,電話會議於下午 4:30 ET 舉行。營收 **$4.10 億**,與去年同期**持平**;經常性收入 $3.63 億,年增 3%(固定匯率下 +2%)。非 GAAP 每股盈餘 **$0.69**,遠高於 Zacks 共識的 $0.55、去年同期的 $0.47;GAAP 稀釋每股盈餘 $0.48(去年同期 $0.09)。

**為什麼超預期還跌 17.9%**

關鍵在訂閱指標,不在損益表:

- 總 ARR **$15.09 億**,年增僅 **1%**
- 公有雲 ARR **$6.86 億**,年增 **8%**

對一家正在做雲端轉型的資料庫公司,總 ARR 年增 1% 等於整體業務只是原地踏步;雲端 ARR +8% 也遠低於市場對雲端轉型股的期待。每股盈餘超標主要靠成本控制與非經常性因素撐起來,而不是業務擴張 —— 這是典型的「獲利數字漂亮、成長數字難看」組合。

**獲利率**

GAAP 毛利率 59.3%、GAAP 營業利益率 11.7%、非 GAAP 營業利益率 21.5%。

**全年指引**

- GAAP 每股盈餘 **$4.43-4.51**
- 非 GAAP 每股盈餘 **$2.65-2.73**
- 營運現金流 **$6.65-6.85 億**(其中含 SAP 和解案稅後挹注 **$3.15 億**)
- 調整後自由現金流 **$3.30-3.50 億**

要特別注意營運現金流裡有 $3.15 億是 SAP 訴訟和解的一次性挹注,不是本業產生的現金。ARR 與營收成長率僅「重申先前的溫和區間」。

**分析師動態**

可查來源中,8/4-8/5 沒有具名分析師調整目標價;最近一次動作是花旗 7/29 財報前重申買進。管理層在電話會議上的具體說法,現有可及來源未能取得逐字內容。""",
 "publishedAt": "2026-08-04T16:30:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "Teradata Q2 2026 財報彙整", "url": "https://www.stocktitan.net/news/TDC/"},
  {"label": "Teradata Q2 2026 法說會逐字稿", "url": "https://seekingalpha.com/article/4930381-teradata-corporation-tdc-q2-2026-earnings-call-transcript"}
 ]}

ND["AMD"] = {
 "detail": """> **今日跌因:** 盤後 -8.8% — Q2 營收 $115 億、年增 50%,資料中心年增 **107%**,全都超預期;但 Q3 財測 $130 億只算符合,加上執行長蘇姿丰**預告下半年 PC 市場轉弱**,股價從 $518.58 直接跌破 $475。

**財報詳解**

AMD 8/4 下午 4:15 ET 公布第二季。營收 **$115 億**,年增 **50%**、季增 13%。GAAP 每股盈餘 $1.38、非 GAAP 每股盈餘 **$1.66**。GAAP 營業利益 $20 億、非 GAAP 營業利益 $31 億。

**分部 —— 資料中心是唯一的主角**

- **資料中心** 營收 **$67 億**,年增 **107%**,佔總營收 **58%**
- **Client(個人電腦)** 年增 23%
- **Gaming** 年減 **31%**
- **Embedded(嵌入式)** 營收 **$9.77 億**,年增 19%

毛利率:GAAP **54%**、非 GAAP **56%**。

**為什麼財報全面超預期,股價卻跌 8.8%**

兩個原因,而且第二個比第一個重要:

**1. Q3 財測不夠驚豔。** Q3 營收財測 **$130 億 ± $3 億**(中位數年增 41%、季增 13%),非 GAAP 毛利率財測約 56%。對一家資料中心業務年增 107% 的公司,市場期待的是財測大幅超標,而不是「符合」。

**2. 執行長親口下修 PC 市場預期。** 蘇姿丰(Lisa Su)在法說會上說:「Looking to the second half of the year, we're planning for a softer PC market as higher memory and component costs weigh on demand.」(展望下半年,我們預期 PC 市場轉弱,因為記憶體與零組件成本上升將壓抑需求。)她補充:「Against this backdrop, we expect our client business to perform better than the market, driven by the strength of our Ryzen portfolio and growing commercial adoption.」(在此背景下,我們預期自家 Client 業務仍會優於整體市場,靠的是 Ryzen 產品線與商用市場滲透。)

記憶體漲價推升 PC 整機成本 —— 這條敘事在 8/5 盤前被放大成整個 PC 供應鏈的問題。

**進場前的位階提醒**

AMD 在 7/30、7/31、8/4 三個交易日分別上漲 5.5%、5.2%、4.7%,財報前已連續墊高;昨日收在 **$518.58**,盤後回到 $473 附近,等於把三天的漲幅全數吐回。近半年仍 +95.7%,籌碼並不便宜。

**分析師動態**

8/5 盤前 President Capital 將目標價由 $574 調升至 **$588**,維持買進 —— 賣方對長線 AI 需求並未轉向,今天的賣壓比較像是短線位階與 PC 端擔憂,而非基本面翻空。""",
 "publishedAt": "2026-08-04T16:15:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "AMD Q2 2026 財報 (IR)", "url": "https://ir.amd.com/news-events/press-releases"},
  {"label": "AMD Q2 2026 財報彙整", "url": "https://www.stocktitan.net/news/AMD/"},
  {"label": "MT Newswires — President Capital 上調目標價至 $588", "url": "https://finance.yahoo.com/markets/stocks/articles/president-capital-adjusts-pt-advanced-101758785.html"}
 ]}

# ---------- 大名字級 / 其他重要 gapper (150-450 字) ----------

ND["SPCX"] = {
 "detail": """> **今日跌因:** 盤前 -11.2% — 掛牌後首份財報營收 **$78.1 億**大勝預估 $69.3 億、年增 92%,但單季資本支出衝到 **$184 億**,市場對燒錢速度反應激烈。

SpaceX 8/4 盤後公布上市後第一份季報。營收 **$78.1 億**,年增 **92%**,超出市場預估的 $69.3 億。其中最亮眼的是 AI 雲端業務 —— 與 Anthropic、Google 的合作帶動該部分營收年增 **247%**。

賣壓來自資本支出:單季 **$184 億**,遠高於市場預期的投入節奏。營收再怎麼成長,這個量級的資本支出直接壓縮自由現金流,也讓市場重新計算獲利轉正的時間點。

這份財報同時外溢到兩個族群:
- **電信股承壓** —— 營運長 Gwynne Shotwell 表示星鏈直連手機可以搶下三大電信商的客戶,Bernstein 隨後下修 Verizon 目標價至 $44;VZ、T、TMUS 8/5 盤前同步走弱。
- **NVIDIA 受惠** —— SpaceX 宣布 AI 基礎設施全面採用 NVIDIA 晶片,明年將取得相當比例的 GPU 供應,NVDA 盤前 +2.1%。

籌碼面:空單佔流通股 **25.55%**,但回補天數僅 1.44 天(成交量極大),不構成軋空結構。近一個月 -26.1%。""",
 "publishedAt": "2026-08-04T16:30:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "Stocktwits — SpaceX 財報後電信股走弱", "url": "https://finance.yahoo.com/m/6c6619fb-13b3-3922-a626-c59ffd94b581/t%2C-vz%2C-tmus-stocks-drop.html"},
  {"label": "Barron's — NVIDIA 是 SpaceX 財報最大贏家", "url": "https://finance.yahoo.com/m/4bd74170-7f90-3341-83a5-1cf73b210611/why-nvidia-stock-is-the-big.html"}
 ]}

ND["CPNG"] = {
 "detail": """> **今日跌因:** 盤後 -7.3% — 韓國個資保護委員會開罰 **6,247 億韓元(約 $4.1 億)**,單季營業虧損擴大到 **$5.841 億**,是掛牌以來最大。

Coupang 8/4 公布第二季,總營收約 **$89 億**,與市場預估的 $89.2 億大致相當 —— 這一季的問題不在營收,在罰款。

**罰款細節:** 韓國個人資料保護委員會(PIPC)因一起影響 **3,750 萬個帳號**的資料外洩事件,認定 Coupang 資安控管不足,開罰 **6,247 億韓元**(約 $4.09-4.12 億)。此外另有約 3,000 億韓元的補稅評定與此事件相關。是否上訴,目前查無公開說法。

**財務衝擊:** 單季營業虧損 **$5.841 億**;2026 上半年累計淨損 **$7.98 億**,兩者都是 Coupang 在紐交所掛牌以來的最大虧損紀錄。

**另一條線:** 美國眾議院一個委員會據報認定南韓「對 Coupang 有差別待遇」,這條監管角力仍在進行中。分析師方面,德意志銀行將 Coupang 由持有調升至買進、目標價 $21.50(該動作的確切日期未能獨立確認為 8/4-8/5)。

分部拆分、活躍客戶數、每客戶消費額與下一季指引,在目前可及來源中均未取得,不做推測。""",
 "publishedAt": "2026-08-04T18:00:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "TechRepublic — Coupang 遭韓國開罰 $4.09 億", "url": "https://www.techrepublic.com/article/news-coupang-record-fine-409m-apac-south-korea/"},
  {"label": "StockAnalysis — CPNG", "url": "https://stockanalysis.com/stocks/CPNG/"}
 ]}

ND["ALIT"] = {
 "detail": """> **今日跌因:** 盤後 -10.6% — Q2 營收與每股盈餘雙雙超預期,但**全年營收指引下修到 $20.78-20.98 億**、低於華爾街共識的 $21.5 億。

Alight 8/4 晚間 8:05 ET 發布第二季財報。營收 **$5.11 億**,超出共識的 $4.97 億;調整後每股盈餘 **$0.91**,大勝共識的 $0.76(超出約 $0.15)。

**跌的原因完全在指引:**
- Q3 營收財測 **$4.69-4.79 億**,而共識是 **$5.018 億**
- 全年營收財測 **$20.78-20.98 億**,共識為 **$21.5 億**

換算下來,全年目標比市場原本的預期少了約 2.5%,Q3 更短少約 5%。財經媒體 StockStory 的標題直接點出癥結:客戶留存趨勢拖累展望。

另一個背景資訊:Alight 已於 2026/6/30 完成 **1 併 20 的反向股票分割**,目前股價位階需以此為準來看歷史圖形。

經常性收入與 BPaaS 分部的個別金額、續約率的具體數字,現有可及來源未揭露;GAAP 損益、毛利率與調整後 EBITDA 亦未取得,不做推測。""",
 "publishedAt": "2026-08-04T20:05:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "StockAnalysis — ALIT", "url": "https://stockanalysis.com/stocks/ALIT/"}
 ]}

ND["ALAB"] = {
 "detail": """> **今日漲因:** 盤前 +1.1% — Q2 營收 **$3.924 億**、年增 **104%**,每股盈餘 $0.80 大勝預估 $0.64;但股價在財報前一日已先漲 12.6%,利多多半反映完畢。

Astera Labs 8/4 盤後公布第二季:營收 **$3.924 億**,年增 **104%**,超出市場預估近 **9%**;每股盈餘 **$0.80**,大勝預估的 $0.64(超出 25%)。Q3 財測營收 **$5.4-5.6 億**、每股盈餘 **$1.16-1.21**。

這是一份帳面極強的財報 —— 營收年增破百的同時獲利超標 25%,Q3 財測還再往上跳一階。但今天盤前只有 +1.1%,原因在位階:ALAB 在 7/31 已先漲 9.5%、8/4 財報當天又漲 **12.6%**,收在 $361.67。也就是說,市場在財報公布前就已經把好消息買進去了,真正的財報反應反而平淡。

以交易角度看,這是「基本面很好但驚奇度已被消化」的典型 —— 財報數字值得追蹤,但今天的價格行為沒有給出跳空進場的理由。""",
 "publishedAt": "2026-08-04T16:05:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "Astera Labs Q2 2026 財報彙整", "url": "https://www.stocktitan.net/news/ALAB/"}
 ]}

ND["LLY"] = {
 "detail": """> **今日漲因:** 盤前約 +4.9% — Q2 營收 **$230 億**、年增 48%,調整後每股盈餘 $8.38、年增 33%,全年營收展望上修到 **$850-870 億**。

Eli Lilly 8/5 盤前公布第二季:營收 **$230 億**,年增 **48%**;調整後每股盈餘 **$8.38**,年增 **33%**。

全年展望同步調升:營收由原財測上修至 **$850-870 億**,調整後每股盈餘上修至 **$35.50-36.50**。

同一天的對照組是 Novo Nordisk —— NVO 第二季營收 784.9 億丹麥克朗僅成長 3%、每股盈餘年減 23.2%,口服版 Wegovy 銷售 32.2 億克朗低於預期並宣布降價 50%。GLP-1 這條賽道上,兩家公司的營收成長率差距(+48% vs +3%)已經大到市場很難再用「雙雄」來描述。""",
 "publishedAt": "2026-08-05T06:30:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "IBD — Novo Nordisk 與 Eli Lilly 競爭態勢", "url": "https://finance.yahoo.com/m/c4ecc3bc-64a8-3f02-b861-1581f635e650/novo-nordisk-stock-stumbles.html"}
 ]}

ND["DIS"] = {
 "detail": """> **今日漲因:** 盤前 +4.7% — FY26 Q3 調整後每股盈餘 **$1.61**(去年同期 $1.39),串流事業由虧損 $1,900 萬翻正到獲利 **$3.46 億**。

迪士尼 8/5 盤前公布 2026 會計年度第三季。調整後每股盈餘 **$1.61**,去年同期 $1.39。

真正的轉折在直接面對消費者(DTC)的串流業務:本季營業利益 **$3.46 億**,去年同期還是虧損 $1,900 萬 —— 這是完整的由虧轉盈。Disney+ 訂戶數達 **1.28 億**,本季淨增 **180 萬**。

整體分部營業利益年增 **8%** 至 **$46 億**。串流從「燒錢換訂戶」轉為「訂戶成長同時賺錢」,是這份財報最實質的變化。""",
 "publishedAt": "2026-08-05T07:00:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "Disney FY26 Q3 財報彙整", "url": "https://www.stocktitan.net/news/DIS/"}
 ]}

ND["DT"] = {
 "detail": """> **今日漲因:** 盤前 +11.6% — FY27 Q1 營收 **$5.55 億**、年增 16% 超預期,非 GAAP 每股盈餘 $0.48 高於自家財測上緣,ARR 達 **$21.36 億**、年增 17%。

Dynatrace 8/5 盤前公布 2027 會計年度第一季。營收 **$5.55 億**,年增 **16%**,超出市場預估的 $5.49 億;非 GAAP 每股盈餘 **$0.48**,高於公司原本 $0.44-0.45 的財測區間。

年度經常性收入(ARR)**$21.36 億**,年增 **17%** —— 對訂閱制軟體公司來說,ARR 增速高於營收增速代表後續認列還有支撐。

唯一的雜訊是匯率:公司因外幣因素小幅下修全年 ARR 與營收展望。但盤前仍跳漲逾 11%,顯示市場把匯率影響視為技術性、而非需求面問題。""",
 "publishedAt": "2026-08-05T06:55:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "Dynatrace FY27 Q1 財報彙整", "url": "https://www.stocktitan.net/news/DT/"}
 ]}

ND["GTE"] = {
 "detail": """> **今日漲因:** 盤前 +35.6% — Q2 由去年同期虧損 $1.19 億轉為淨利 **$2,500 萬**,營收 **$1.87 億**、年增 25%,並達成 Tisquirama 區塊 49% 權益的條件。

Gran Tierra Energy 8/4 公布第二季:淨利 **$2,500 萬**,而去年同期是虧損 **$1.19 億** —— 一年之內從大額虧損翻到獲利。營收 **$1.87 億**,年增 **25%**。

另一項實質利多是資產面:公司達成取得 **Tisquirama 區塊 49% 權益**的先決條件。對一家中小型油氣公司來說,權益比例的提升直接對應未來的可採量與現金流。

從虧轉盈 + 營收兩位數成長 + 資產權益增加,三件事同時發生,是這檔股票單日跳空逾 35% 的原因。""",
 "publishedAt": "2026-08-04T17:00:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "Gran Tierra Energy Q2 2026 財報彙整", "url": "https://www.stocktitan.net/news/GTE/"}
 ]}

ND["SGHT"] = {
 "detail": """> **今日漲因:** 盤後 +8.1% — 8/4 取得 FDA 510(k) 核准,青光眼微創手術系統 **OMNI Ultra** 預計 2026 年第四季在美上市。

Sight Sciences 8/4 宣布取得美國 FDA 的 510(k) 核准,產品為 **OMNI Ultra 手術系統**,適應症為青光眼微創手術(MIGS)。公司預計 **2026 年第四季**在美國正式商業化。

對這種規模的醫材公司,510(k) 核准的意義在於把產品從研發資產變成可銷售品項,時間表(Q4 上市)也給了市場一個明確的營收起算點。

核准本身不含營收預估或定價資訊,公司亦未提供相關財測。""",
 "publishedAt": "2026-08-04T16:30:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "Sight Sciences FDA 510(k) 核准公告", "url": "https://www.stocktitan.net/news/SGHT/"}
 ]}

ND["WYNN"] = {
 "detail": """> **今日漲因:** 盤後 +5.0% — Q2 營收 **$18.6 億**、年增 6.9%,調整後每股盈餘 **$1.24** 遠超市場預估的 $0.99-1.01。

Wynn Resorts 8/4 盤後公布第二季:營收 **$18.6 億**,年增 **6.9%**;調整後每股盈餘 **$1.24**,而市場預估區間為 $0.99-1.01 —— 超出上緣約 23%。

營收只成長 6.9% 但每股盈餘大幅超標,代表這一季的驚喜來自成本控制與營運槓桿,而非博弈量能的爆發。

籌碼面:空單佔流通股 **12.17%**、回補天數 **5.99 天**,符合 MAGNA53 的「5」判準;近一個月 +5.1%,半年仍 -7.4%,籌碼並未事先擁擠。""",
 "publishedAt": "2026-08-04T16:05:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "Wynn Resorts Q2 2026 財報彙整", "url": "https://www.stocktitan.net/news/WYNN/"}
 ]}

ND["RARE"] = {
 "detail": """> **今日漲因:** 盤後 +6.4% — Q2 營收創新高 **$2.14 億**,遠高於市場預估的 $1.82 億,並重申全年營收指引 $7.3-7.6 億。

Ultragenyx 8/4 盤後公布第二季:營收 **$2.14 億**,創單季新高,超出市場預估的 **$1.82 億** 約 18%。公司重申全年營收指引 **$7.3-7.6 億**。

罕見疾病藥廠的營收超標通常代表既有產品的滲透率或給付進度優於預期。重申(而非上修)全年指引,則顯示管理層對下半年仍持保守態度。

籌碼面:空單佔流通股 **14.98%**、回補天數 **6.11 天**,符合 MAGNA53「5」判準;近一個月股價 -23.4%,是從相對低位反彈。""",
 "publishedAt": "2026-08-04T16:05:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "Ultragenyx Q2 2026 財報彙整", "url": "https://www.stocktitan.net/news/RARE/"}
 ]}

ND["LCID"] = {
 "detail": """> **今日跌因:** 盤後 -7.9% — Q2 每股虧損 **$3.30**(市場預估虧 $2.46)、營收 $4.05 億低於預估的 $4.16 億,且**未提供 2026 年財測**、中型車款延後。

Lucid 8/4 盤後公布第二季:每股虧損 **$3.30**,市場原本預估虧 $2.46,虧損幅度比預期大 34%;營收 **$4.05 億**,低於預估的 $4.16 億。

比數字更傷的是兩件事:
1. 公司**未提供 2026 全年財測** —— 在電動車產業景氣不明的階段,拒絕給指引通常被市場解讀為能見度不足
2. **中型車款發表延後** —— 這是 Lucid 從高價位小眾市場走向量產的關鍵產品,時程延後直接推遲規模經濟的到來

營收未達標 + 虧損擴大 + 沒有指引 + 產品延期,四件負面同時出現。""",
 "publishedAt": "2026-08-04T16:05:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "Lucid Group Q2 2026 財報彙整", "url": "https://www.stocktitan.net/news/LCID/"}
 ]}

ND["PINS"] = {
 "detail": """> **今日跌因:** 盤後 -8.6% — Q2 營收 $11.8 億、每股盈餘 $0.43 都優於預期,但 Q3 營收指引 **$11.9-12.1 億**代表成長放緩到 13-15%。

Pinterest 8/4 盤後公布第二季:營收 **$11.8 億**、每股盈餘 **$0.43**,雙雙優於市場預期。

賣壓來自下一季:Q3 營收指引 **$11.9-12.1 億**,換算年增率只有 **13-15%**。對一家廣告平台股,成長率從先前的水準往下掉到十幾個百分點,估值倍數就必須重新計算。

這是本季一個反覆出現的型態 —— 財報本身沒問題,但下一季的成長率指引才是市場定價的依據。""",
 "publishedAt": "2026-08-04T16:05:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "Pinterest Q2 2026 財報彙整", "url": "https://www.stocktitan.net/news/PINS/"}
 ]}

ND["ZETA"] = {
 "detail": """> **今日跌因:** 盤後 -5.1% — Q2 營收 **$4.43 億**、年增 44%,連 **20 季**超預期並上調全年指引,但市場擔憂獲客成本而賣壓出籠。

Zeta Global 8/4 盤後公布第二季:營收 **$4.43 億**,年增 **44%**;這是公司**連續第 20 季**超出財測並同步上調全年指引(beat-and-raise)。

在這樣的紀錄下股價仍跌 5.1%,市場關注的是獲客成本 —— 營收高速成長若必須靠等比放大的行銷與獲客投入來換,單位經濟效益就會被侵蝕。這也是本季軟體/廣告科技股共通的檢視角度。

具體的獲客成本數字、毛利率與 EBITDA 明細,目前可及來源未揭露,不做推測。""",
 "publishedAt": "2026-08-04T16:05:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "Zeta Global Q2 2026 財報彙整", "url": "https://www.stocktitan.net/news/ZETA/"}
 ]}

ND["ECHO"] = {
 "detail": """> **今日跌因:** 盤後 -4.5% — Q2 營收 **$35.8 億**超預期,但同一天子公司 **Hughes Network Systems 聲請 Chapter 11 破產保護**。

EchoStar 8/4 公布第二季,營收 **$35.8 億**超出市場預期 —— 但這份財報被同日的另一則公告蓋過:子公司 **Hughes Network Systems 聲請美國破產法第 11 章重整保護**。

對控股公司而言,子公司進入 Chapter 11 牽動的是資產重分類、債務歸屬與後續合併報表的認列方式,不確定性遠高於單季營收超標的正面效果。市場選擇對後者定價。

破產程序的具體債務規模與重整計畫,現有可及來源尚未揭露。""",
 "publishedAt": "2026-08-04T16:30:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "EchoStar Q2 2026 與 Hughes Chapter 11", "url": "https://www.stocktitan.net/news/SATS/"}
 ]}

ND["UMC"] = {
 "detail": """> **今日跌因:** 盤前 -5.7% — 川普政府擬對進口晶片課徵 **100% 關稅**,聯電因未在美國設廠而被視為首當其衝。

聯電 8/5 盤前重挫,原因不是公司自身消息,而是政策面:川普政府傳出擬對進口晶片課徵 **100% 關稅**。

關鍵在豁免條件 —— 已在美國進行大額投資的業者可獲豁免,台積電因 **$165 億**的美國投資案被點名為受惠者;聯電目前**未在美國設有晶圓廠**,因此被市場歸類為直接受衝擊的一方。

這是典型的政策族群事件:同一則新聞讓同產業的兩家公司走向相反方向,判斷依據是各自的美國產能佈局,而非當季營運數字。""",
 "publishedAt": "2026-08-05T06:00:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "晶片關稅政策報導彙整", "url": "https://www.reuters.com/markets/"}
 ]}

ND["CRCL"] = {
 "detail": """> **今日漲因:** 盤前 +4.2% — 宣布收購 IBM 近 **1,000 項區塊鏈專利**;第二季財報另於今日盤前公布。

Circle Internet Group 因收購 **IBM 近 1,000 項區塊鏈相關專利**而在 8/4-8/5 連兩日走高。對一家穩定幣與鏈上支付業者,大規模專利組合的意義在於防禦性 —— 降低未來被競爭者或專利主張實體(NPE)訴訟的風險,同時提高自身在標準制定上的話語權。

專利收購金額未揭露。公司第二季財報排定 8/5 盤前另行公布,截至撰稿時尚未取得實際數字。

價格位階需注意:CRCL 8/3 曾下跌 6.2%,8/4、8/5 各回升約 4.2%,目前仍在區間震盪而非單邊突破。""",
 "publishedAt": "2026-08-04T09:00:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "Circle Internet Group 新聞彙整", "url": "https://www.stocktitan.net/news/CRCL/"}
 ]}

ND["DFNS"] = {
 "detail": """> **今日漲因:** 盤前 +10.2% — 1 併 125 反向分割後流通股僅 **112 萬股**,軋空行情疊加 Project 35 反無人機合約消息延續動能。

T3 Defense 的漲勢主因是籌碼結構,不是新的基本面事件。公司完成 **1 併 125** 的反向股票分割後,流通在外股數只剩約 **112 萬股** —— 在這種流通量下,任何買盤都會產生放大的價格反應。

消息面延續的是 Project 35 反無人機合約題材,並非今日新發布的公告。

**這檔要特別注意的是價格行為本身:** 近幾個交易日分別為 7/29 +41.5%、7/30 +80.8%、7/31 -55.5%、8/3 +52.0%、8/4 -19.4%、8/5 +10.2%。單日振幅動輒 40-80% 且方向反覆,屬於典型的極低流通股拉抬與出貨循環,不是可以用一般部位規模參與的標的。

Finviz 資料顯示空單佔流通股 15.36%,但回補天數僅 0.03 天(換手極快),近半年股價 -80.8%。""",
 "publishedAt": "2026-08-05T06:00:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "T3 Defense 新聞彙整", "url": "https://www.stocktitan.net/news/DFNS/"}
 ]}

ND["AMIX"] = {
 "detail": """> **今日跌因:** 盤前 -38.2% — 8/4 因公布神經感測/膀胱過動症新專利一度暴漲近 90%,8/5 盤前獲利了結倒車。

Autonomix Medical 8/4 公布與神經感測、膀胱過動症治療相關的新專利,股價當日一度暴漲近 **90%**。8/5 盤前回吐 **38.2%**,是前一日漲幅的獲利了結,而非新的利空。

這是微型醫材股在單一專利消息上的典型反應曲線:消息面本身不改變當期營收或現金流,價格反應完全由籌碼推動,漲跌都在一到兩個交易日內完成。

專利公告未附帶授權金、產品時程或營收預估。""",
 "publishedAt": "2026-08-04T09:00:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "Autonomix Medical 新聞彙整", "url": "https://www.stocktitan.net/news/AMIX/"}
 ]}

ND["INOD"] = {
 "detail": """> **今日漲因:** 盤後 +5.2% — 8/4 發布 AI 網路安全訓練資料集新產品線(共 12 組資料集),搶在 8/6 財報前推升股價。

Innodata 8/4 發布新產品線:共 **12 組** AI 網路安全訓練資料集。對一家以資料標註與訓練資料為主業的公司,推出打包好的垂直領域資料集,意義在於從專案制服務往可重複銷售的產品靠攏。

時間點也是市場關注的一環 —— 公司第二季財報排定 **8/6** 公布,在財報前一天發布新產品線,通常被解讀為管理層對後續業績有一定把握。

新產品線未揭露定價、預期營收貢獻或已簽約客戶。""",
 "publishedAt": "2026-08-04T09:00:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "Innodata 新產品發布", "url": "https://www.stocktitan.net/news/INOD/"}
 ]}

ND["VSH"] = {
 "detail": """> **今日漲因:** 盤前 +7.6% — Needham 8/4 首次覆蓋給予買進評等、目標價 **$45**,並點出訂單出貨比 1.34、在手訂單年增 42%。

Vishay Intertechnology 8/5 盤前的推力來自賣方 —— Needham 於 8/4 **首次覆蓋**,給予 **買進(Buy)** 評等、目標價 **$45**。

報告中被引用的兩個營運數字才是重點:
- **訂單出貨比(book-to-bill)1.34** —— 大於 1 代表新接訂單流入快於出貨認列
- **在手訂單年增 42%**

對被動元件這種景氣循環性強的產業,訂單出貨比是最領先的指標之一;1.34 這個水準通常對應到循環的擴張段。

首次覆蓋的買進評等本身影響有限,真正讓股價反應的是報告所揭露的訂單能見度。""",
 "publishedAt": "2026-08-04T07:00:00-04:00",
 "publishedTimezone": "ET",
 "sources": [
  {"label": "Vishay Intertechnology 新聞彙整", "url": "https://www.stocktitan.net/news/VSH/"}
 ]}

p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'news_detail.json')
old = {}
if os.path.exists(p):
    with io.open(p, encoding='utf-8') as f:
        old = json.load(f)
old.update(ND)
with io.open(p, 'w', encoding='utf-8') as f:
    json.dump(old, f, ensure_ascii=False, indent=1)
print('news_detail written:', len(ND), 'today /', len(old), 'total')
for k, v in ND.items():
    print(f"  {k:6} {len(v['detail'])} chars")
