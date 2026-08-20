# -*- coding: utf-8 -*-
import json, io

DETAIL = """> **今日漲因:** 無今日新消息 — 7/31 公布的第一季財報(營業利益年增 40%、上調全年財測)延續買盤,盤前 +2.2%。

**財報回顧(7/31 公布)**
索尼集團 2026 財年(截至 2027 年 3 月)第一季(4-6 月)合併營收 **2 兆 8,378 億日圓**,年增 **8.2%**;營業利益 **4,765 億日圓**,年增 **40.2%**;淨利 **3,422 億日圓**,年增 **32.1%**,獲利表現優於華爾街預估。

**分部表現**
遊戲與網路服務(PlayStation)營收 **9,158 億日圓**、營業利益 **2,020 億日圓**(年增 37%),PlayStation 月活躍用戶創新高達 **1.25 億人**;不過本季 PS5 主機出貨僅 **160 萬台**,較去年同期 250 萬台年減 36%,成長動能來自軟體與服務而非硬體。音樂分部營業利益 **1,059 億日圓**、影像感測器(I&SS)分部營業利益 **1,222 億日圓**,雙雙寫下單季新高。

**上調全年財測**
索尼將 2026 財年全年營業利益上調約 8% 至 **1 兆 7,200 億日圓**,並同步上調營收與淨利預估;公司同時說明熊本地震對感測器產線的影響仍在評估中。

**今日走勢**
今日盤前 +2.2%,查無新的公司公告或分析師動作,屬財報後的延續行情;歸類在 SCANX 的「其他」桶,非當日財報反應。"""

p = 'news_detail.json'
d = json.load(io.open(p, encoding='utf-8'))
d['SONY'] = {
    "detail": DETAIL,
    "publishedAt": "2026-07-31T06:02:00-04:00",
    "publishedTimezone": "ET",
    "sources": [
        {"label": "Sony Group 6-K — Q1 FY2026 results", "url": "https://www.stocktitan.net/sec-filings/SONY/6-k-sony-group-corp-current-report-foreign-issuer-691401445e99.html"},
        {"label": "Investing.com — Sony Q1 FY2026 slides", "url": "https://www.investing.com/news/company-news/sony-q1-fy2026-slides-operating-income-surges-40-on-gaming-sensors-93CH-4827007"},
    ],
}
json.dump(d, io.open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('SONY detail written:', len(DETAIL), 'chars | total', len(d))
