import json, io
p = 'catalysts_today.json'
d = json.load(io.open(p, encoding='utf-8'))

NEW = {
 # --- 貴金屬族群(gold_silver_rally):金價 $4,078→$4,178/oz、銀價 $59.5→$61.6/oz,GDX +2.5% ---
 "B":    ("macro", False, "貴金屬族群 — 美元走弱+殖利率下滑推升金價至 $4,178/oz;盤前 +7.4%,開盤後回吐至 +2.3%"),
 "NG":   ("macro", False, "無營收探勘股對金價槓桿最高 — 金價創波段高,盤前 +14.3%,盤中仍守 +6.6%"),
 "HMY":  ("macro", False, "南非金礦 — 金價 +2.2% 帶動,盤前 +10.4%,開盤後回吐至 +2.5%"),
 "PAAS": ("macro", False, "銀價升至 $61.6/oz(週內最強),盤前 +9%,盤中 +2.7%;Q2 財報 8/12 才公布"),
 "AU":   ("macro", False, "金價族群連動,盤前一度 +7.6%,開盤後全數回吐至平盤;無個股新聞"),
 "KGC":  ("macro", False, "金價族群連動,盤前 +6.7% 回吐至 +0.7%;Q2 財報 7/30 已公布,今日非新財報"),
 "OGG":  ("macro", False, "金價族群連動,盤前 +9.1%,開盤後回吐至 +0.8%;無公司特定消息"),
 # --- 個股事件 ---
 "TBLA": ("earnings", True,  "Q2 營收 $4.768 億遜於預期 $4.995 億、EPS $0.01 低於預期 $0.05,但上調全年 ex-TAC 毛利與調整後 EBITDA 指引;盤前一度 -32% 開盤後翻紅"),
 "FUBO": ("earnings", True,  "Q2 營收 $14.8 億(+35.8% YoY)略遜預期 $15.0 億,調整後 EBITDA $1,914 萬遠優於預期 $1,284 萬;盤前 -11.8% 收復至平盤"),
 "DBGI": ("momentum", False, "1 比 40 反向分割(7/24 生效)後流通量極低;延續 Q3 指引營收 $850-1,100 萬敘事,盤前一度 +118%,盤中回落至 +19%,今日無新公告"),
 "WETO": ("momentum", False, "8/3 分割生效、8/4 暫停交易後今日恢復交易,價格重整;盤前 -25%、盤中 -20%,無新催化劑"),
 "BIYA": ("momentum", False, "查無今日催化劑 — 反向分割後低流通量投機盤,盤前 +3% 開盤後翻黑 -8.4%"),
 "PCLA": ("momentum", False, "查無今日催化劑 — 盤前一度 +23.6%,開盤後翻黑 -3.4%,屬低流通量投機交易"),
}
for k, (t, er, c) in NEW.items():
    d[k] = {"Type": t, "EarningsReaction": er, "Catalyst": c}
json.dump(d, io.open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('catalysts +', len(NEW), '| total', len(d))
