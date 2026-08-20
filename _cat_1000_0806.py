import json, io
p = 'catalysts_today.json'
d = json.load(io.open(p, encoding='utf-8'))

MEM = "記憶體/儲存族群殺盤 — WDC、SanDisk 財測不如市場對 AI 記憶體的高預期,加上三星、SK 海力士擴產的供給過剩疑慮,南韓 KOSPI 盤中一度重挫觸發熔斷"
SAAS = "企業軟體殺盤 — 市場擔憂 AI 代理人侵蝕 SaaS 訂閱模式,資金撤出高本益比軟體與 AI 基建股"

NEW = {
 # --- 記憶體/儲存族群(theme_watch 領頭羊)---
 "STX":   ("macro",    False, MEM + ";Seagate 盤前 -5.7%,無個股新聞"),
 # --- 軟體 / AI 基建殺盤 ---
 "NOW":   ("macro",    False, SAAS + ";ServiceNow 盤前 -3.8%,無個股新聞"),
 "ADBE":  ("macro",    False, SAAS + ";Adobe 盤前 -3.5%,無個股新聞"),
 "ORCL":  ("news",     False, "AI 擴張舉債引發信用評等疑慮(標普 7 月已降至 BBB-),隨軟體族群回落,盤前 -3.4%"),
 "CRWV":  ("analyst",  False, "花旗分析師 Tyler Radke 將目標價由 $158 下修至 $142,8/11 財報前轉趨保守;盤前 -4.5%"),
 "COHR":  ("macro",    False, "AI 資料中心光通訊族群回落,前波執行長訪中題材大漲後獲利了結;盤前 -2.9%,無個股新聞"),
 "PLTR":  ("momentum", False, "8/3 財報後大漲近 29%,今日隨 AI 高估值股獲利了結;盤前 -2.4%,無個股新聞"),
 "MRVL":  ("momentum", False, "AI 半導體族群回落 — 前波 AI 儲存新品與 KeyBanc 目標價上調至 $400 後獲利了結;盤前 -2.8%"),
 "CRWD":  ("momentum", False, SAAS + ";CrowdStrike 盤前 -2.5%,無個股新聞"),
 "VRT":   ("momentum", False, "AI 資料中心設備族群修正,延續 7/29 財報後的高波動;盤前 -1.9%,無個股新聞"),
 "ALAB":  ("analyst",  False, "延續 8/5 財報後獲利了結,TD Cowen 目標價下修至 $375;盤前 -2.1%"),
 "AMD":   ("momentum", False, "延續 8/5 SpaceX 傳改採輝達晶片的消息與財測疑慮,隨 AI 半導體族群回落;盤前 -1.7%"),
 # --- 今晨盤前公布財報的大型股 ---
 "FOX":   ("earnings", True,  "8/6 盤前公布 FY26 Q4:營收 $42.1 億(年增 28%,華爾街預估 $36.4 億),世界盃廣告收入年增 78%、Tubi 串流成長帶動;淨利 $6.96 億、調整後 EBITDA $12.0 億;盤前 +2.9%"),
 "MCK":   ("earnings", True,  "8/5 盤後公布 FY27 Q1:調整後 EPS $9.93(年增 20%)、營收 $1,054 億(年增 8%),並上調全年財測至 $44.20-45.00;盤前 +2.6%"),
 "SONY":  ("earnings", True,  "8/6 盤前公布 Q1 財報:營收年增 8%、營業利益年增 40%,遊戲與影像感測器強勁帶動,並上調全年財測;盤前 +2.2%"),
 "FWONK": ("earnings", True,  "Liberty Media 合併營收 $9.34 億略低於預估 $9.57 億;F1 分部營收 $7.64 億(年減 38%,本季只有 5 場賽事、去年同期 9 場),調整後 OIBDA $2.06 億;盤前 +1.0%"),
}
for k, (t, er, c) in NEW.items():
    d[k] = {"Type": t, "EarningsReaction": er, "Catalyst": c}
json.dump(d, io.open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('catalysts +', len(NEW), '| total', len(d))
