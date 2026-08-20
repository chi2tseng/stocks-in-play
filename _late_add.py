# -*- coding: utf-8 -*-
import csv,io,json
DATE='2026-08-04'
NEW={
 'W':(17.57,104.60,'Wayfair Inc.','Q2 調整後 EPS $0.95 優於預期 $0.90、營收 $35.2 億優於預期 $34.7 億(年增 7.6%);盤前一度翻黑後急拉','earnings',True),
 'ET':(3.99,21.40,'Energy Transfer L.P.','8/4 盤前公布 Q2 財報後走高,盤前漲近 4%','earnings',True),
 'BR':(2.59,161.45,'Broadridge Financial Solutions, Inc.','8/4 盤前公布 Q2 財報後走高','earnings',True),
 'TPG':(2.56,47.50,'TPG Inc.','8/4 盤前公布 Q2 財報後走高','earnings',True),
}
rows=list(csv.DictReader(io.open('candidates.csv',encoding='utf-8-sig')))
have={r['Symbol'] for r in rows}; fn=list(rows[0].keys())
for s,(chg,px,name,cat,ty,er) in NEW.items():
    if s in have: continue
    rows.append({'Symbol':s,'Last':px,'ChgPct':chg,'Volume':0,'Session':'headline','SessionDate':DATE,'Direction':'up','Name':name})
w=csv.DictWriter(io.open('candidates.csv','w',encoding='utf-8-sig',newline=''),fieldnames=fn)
w.writeheader(); w.writerows(rows)
c=json.load(io.open('catalysts_today.json',encoding='utf-8'))
for s,(chg,px,name,cat,ty,er) in NEW.items(): c[s]={'Catalyst':cat,'Type':ty,'EarningsReaction':er}
json.dump(c,io.open('catalysts_today.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
d=json.load(io.open('news_detail.json',encoding='utf-8'))
d['W']={'detail':"""> **今日漲因:** 盤前 +17.6% 至約 $105 —— 8/4 盤前公布 Q2 財報,調整後 EPS 與營收雙雙優於預期。

**財報數字**

Wayfair 於 2026 年 8 月 4 日盤前公布第二季財報:

- **調整後每股盈餘 $0.95**,優於華爾街預估的 **$0.90**,去年同期為 **$0.87**,年增約 **9.2%**
- **營收 $35.2 億**,優於預期的 **$34.7 億**,去年同期 $32.7 億,年增約 **7.6%**

**盤中的方向反轉**

值得注意的是,美東時間 8/4 上午 7:44 的即時報導指出 Wayfair 盤前一度**下跌 3%**;到了接近開盤前,股價已翻為**上漲逾 17%**。單就上述營收與 EPS 的超預期幅度(分別約 1.4% 與 5.6%)並不足以解釋這樣的漲幅,推測與法說會內容或財測有關 —— 但這部分尚未取得可查證的一級來源,無法確認。

**風險備註**

本則所引用的公開資料未包含調整後 EBITDA、活躍顧客數與前瞻財測;股價漲幅與已公布數字之間的落差,在取得完整資料前應視為未經解釋。""",
 'publishedAt':'2026-08-04T07:00:00-04:00','publishedTimezone':'ET',
 'sources':[{'label':'Wayfair Q2 adjusted earnings, revenue rise — MT Newswires','url':'https://finance.yahoo.com/markets/stocks/articles/wayfair-q2-adjusted-earnings-revenue-114407666.html','publishedAt':'2026-08-04T07:44:00-04:00'}]}
json.dump(d,io.open('news_detail.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
r=json.load(io.open('day_resets.json',encoding='utf-8'))
r['resets']['W']='8/4 盤前 Q2 調整後 EPS $0.95 優於預期 $0.90、營收 $35.2 億優於預期 — 全新財報事件'
r['resets']['ET']='8/4 盤前 Q2 財報 — 全新財報事件'
r['resets']['BR']='8/4 盤前 Q2 財報 — 全新財報事件'
r['resets']['TPG']='8/4 盤前 Q2 財報 — 全新財報事件'
json.dump(r,io.open('day_resets.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
print('done')
