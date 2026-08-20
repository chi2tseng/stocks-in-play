# -*- coding: utf-8 -*-
import json, io

DETAIL = """> **今日跌因:** 盤前 -18% — Q2 財報數字本身優於預期,但全年營收成長財測由 4-6.5% 砍到 3.2-4.2%,第三季只給年增 1.7%。

**財報數字**
EPAM Systems 公布第二季調整後每股盈餘 **$3.38**、營收 **$14.1 億**,兩項都優於華爾街預估。市場的問題不在已發生的一季,而在公司對下半年的看法。

**財測下修才是重點**
公司把 2026 全年營收成長財測由原本的 **4-6.5%** 下修到 **3.2-4.2%**,第三季財測更只有年增 **1.7%**。對一家過去被當成數位工程外包成長股的公司來說,個位數低段的成長等同於成長敘事失效,這是盤前重挫近兩成的直接原因。

**市場擔心什麼**
IT 服務業近一年同時面對兩件事:企業客戶延後非必要的數位轉型專案,以及 AI 程式生成工具壓縮傳統人力外包的計價基礎。財測下修被解讀為前述壓力已經反映到訂單上,而不只是單季的專案遞延。

*(數字來源:公司財報與當日一級財經媒體報導;TradingView 季度資料尚未更新今日公布的最新一季,盤後會再補抓。)*"""

p = 'news_detail.json'
d = json.load(io.open(p, encoding='utf-8'))
d['EPAM'] = {
    "detail": DETAIL,
    "publishedAt": "2026-08-06T06:30:00-04:00",
    "publishedTimezone": "ET",
    "sources": [
        {"label": "EPAM Systems Investor Relations", "url": "https://investors.epam.com/"},
    ],
}
json.dump(d, io.open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('EPAM detail written:', len(DETAIL), 'chars | total', len(d))
