# -*- coding: utf-8 -*-
import json, csv, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

C = {
# shard A
"WXM":  ("momentum", False, "6 月 10 併 1 反向分割後流通股僅 113 萬股,超低流通量炒作,查無具體消息"),
"WAFU": ("news", False, "8/10 盤後公告簽下 3 項 AI 大模型客製化合作案,未揭露金額"),
"AIHS": ("contract", False, "與 Energence Utah 簽意向書,投資 500 萬美元建猶他州機房,首期 100MW"),
"BW":   ("earnings", True, "Q2 EPS $0.07 轉盈(去年同期虧 $0.63),營收 3.2 億美元年增 130%"),
"WYHG": ("momentum", False, "低流通量 ADS 炒作,8/10 私募案完成後查無新催化劑"),
"STKH": ("momentum", False, "Perfecta 美國上市消息帶動飆漲後獲利了結,加上私募稀釋疑慮"),
"PIII": ("earnings", True, "Q2 營收 3.86 億美元年增 9% 並轉盈,淨利 1,570 萬美元,上調 EBITDA 財測"),
"MGIH": ("momentum", False, "查無明確消息"),
"RIOT": ("contract", False, "簽下 Anthropic 20 年 AI 機房租約,年租金上看 10 億美元"),
"FF":   ("news", False, "7 月機器人銷量 152 台創新高,同步啟動美國在地製造計畫"),
"UPWK": ("guidance", True, "Q2 EPS 超乎預期,但 Q3 營收展望不如華爾街預估,AI 衝擊接案需求"),
"LIF":  ("guidance", True, "Q2 營收 1.59 億美元年增 38%,但 GAAP 淨利降至 510 萬,全年展望不如預期"),
"GENK": ("guidance", True, "CPG 事業營收季增 341% 創新高,擬以約 1 億美元出售美國餐廳資產"),
# shard B
"FRMI": ("contract", False, "與 TensorWave 簽 15 年資料中心租約,總值 65 億美元、222MW 電力(Project Matador)"),
"ELPW": ("news", False, "8/10 生效 45 併 1 反向分割,股數縮至 51 萬股,以守住 Nasdaq $0.10 門檻"),
"CLRO": ("M&A", False, "Cortigent 合併案遭律師事務所調查股東稀釋問題,原股東僅保留 12.7-14.4% 股權"),
"JWEL": ("momentum", False, "8/10 無消息單日暴漲 58% 至 $2.49,今日獲利了結回落,查無新催化劑"),
"NIQ":  ("earnings", True, "Q2 EPS $0.27 贏過預估 $0.20(+33%),營收 11.2 億美元年增 8%,上調全年財測"),
"ACVA": ("earnings", True, "Q2 EBITDA 2,078 萬美元超乎預期,重申 FY26 營收 8.5 億美元財測"),
"ELVA": ("guidance", True, "Q3 財報後下修 FY26 營收財測至 7,000-7,300 萬美元(原估逾 8,300 萬)"),
"OPFI": ("earnings", True, "Q2 調整後 EPS 年減 25% 至 $0.33,壞帳率升至 52.3%,獲利疑慮壓垮股價"),
"ONON": ("earnings", True, "Q2 營收 8.50 億瑞郎不如預估 8.81 億(−3.0%),EPS 雖小勝仍重挫逾 13%"),
"GCTS": ("earnings", True, "Q2 非 GAAP EPS 優於預期,但先前已下修 FY26 營收展望至 2,160 萬美元且有存續疑慮"),
"THH":  ("news", False, "8/10 生效 10 併 1 反向分割以維持 Nasdaq 最低股價合規,分割後遭持續拋售"),
"QMCO": ("earnings", True, "會計年度 Q1 營收 8,080 萬美元優於預估 7,505 萬,非 GAAP EPS 轉正 $0.18(原估虧 $0.15)"),
"ARTW": ("momentum", False, "查無明確消息(8/10 僅有模組建築積壓訂單增至 1,900 萬美元的正面新聞,方向相反)"),
# shard C
"PLUG": ("earnings", True, "Q2 營收 1.78 億美元超乎預期,並上調全年成長財測至 15-16%"),
"KOPN": ("earnings", True, "Q2 營收年增 51% 至 1,270 萬美元,由虧轉盈"),
"YJ":   ("momentum", False, "查無明確消息,先前 3 日暴漲 176% 後獲利了結回落"),
"SE":   ("earnings", True, "Q2 營收 71 億美元大勝預估 64.6 億(+10%),EPS $0.88 勝預估 $0.75,蝦皮電商動能強"),
"ZJYL": ("momentum", False, "前一日公布上半年營收後暴漲 88%,今日獲利了結回檔"),
"NUS":  ("guidance", True, "Q2 營收 3.2 億美元不如預估 3.45 億,FY26 EPS 財測下修至 $0.7-0.9"),
"USAR": ("earnings", True, "Q2 營收 580 萬美元遠低於預估 800 萬,盤後重挫"),
"MLCI": ("momentum", False, "查無明確消息,Q2 財報今日盤後才公布"),
"FA":   ("momentum", False, "財報 8/6 已公布且無新利空,技術面超買後獲利了結"),
"ONFO": ("news", False, "8/10 生效 50 併 1 反向分割,流通股僅剩約 85 萬股"),
"SOC":  ("momentum", False, "查無明確消息"),
"DPRO": ("earnings", True, "Q2 每股虧損 $0.24 遠不如預估虧 $0.11,雖營收創高仍重挫"),
"RPD":  ("earnings", True, "Q2 非 GAAP EPS $0.44 超乎預期 26%,同時宣布裁員 12%"),
# shard F / cluster agents
"SYK":  ("momentum", False, "查無個股專屬催化劑,當日僅有機構持股增減報導,判定為無消息日的類股連動"),
"SMCI": ("news", False, "財報前買盤湧入,加上 8/10 傳出取得 Gigawatt 級 AI 資料中心訂單"),
"AXSM": ("earnings", True, "8/10 公布 Q2 營收年增 46% 至 2.18 億美元優於預期,今日多家券商調升目標價(富國調至 $256)"),
"STX":  ("momentum", False, "Q4 財報強勁、股價創高後,今日出現漲勢是否見頂的疑慮而獲利了結"),
"FERG": ("momentum", False, "8/10 財報營收 87.5 億美元、EPS $3.43 優於預期並上修全年財測後大漲,今日因估值疑慮回吐"),
"PLTR": ("news", False, "Michael Burry 加碼買進賣權看空,CTO Sankar 出脫 350 萬股,估值壓力浮現"),
"MU":   ("momentum", False, "財報後漲多回檔,SK 海力士與三星財報釋出競爭警訊,記憶體漲價動能降溫"),
"SNDK": ("momentum", False, "記憶體漲價動能降溫,財報暴漲後賣壓延續"),
"WDC":  ("momentum", False, "記憶體/儲存類股整體回檔,8/9 曾單日重挫 16% 為領跌者"),
"ASML": ("momentum", False, "8/10 費半指數重挫 2.94% 後,設備類股今日全面逢低回補反彈"),
"AMAT": ("momentum", False, "設備類股齊反彈,8/13 將公布財報"),
"LRCX": ("momentum", False, "7 月財報爆量大漲(單日 +20%)後延續強勢,今日續彈"),
"KLAC": ("momentum", False, "設備類股全面回補,延續 7 月財報後的強勢"),
"COHR": ("momentum", False, "8/10 財報前獲利了結重挫 14.2% 後反彈,8/12 盤後將公布財報"),
"INTC": ("news", False, "上修增資規模至 200 億美元、每股 95 美元定價,稀釋疑慮壓抑股價"),
# earnings-calendar gate (今晨盤前已公布)
"ESLT": ("earnings", True, "Q2 EPS $3.61 勝預估 $3.38(+6.9%)、營收 22.9 億美元勝預估 22.5 億(+1.6%),但盤前仍跳空跌逾 8%"),
"CAH":  ("earnings", True, "盤前公布會計年度 Q4:季度數字好壞參半,但全年財測強勁"),
"ARMK": ("earnings", True, "會計年度 Q3 調整後獲利與營收雙成長,並上調 FY26 營收展望"),
# shard D
"RKLB": ("earnings", True, "Q2 每股虧損 $0.08 不如預估虧 $0.06,Q3 毛利率財測 29-31% 遠低於預估 37.6%"),
"IPHA": ("momentum", False, "8/10 因 IPH4502 試驗完成 76 例收案而急漲,今日獲利了結拉回"),
"AMTM": ("earnings", True, "會計年度 Q3 營收 34.9 億美元不如預估 35.7 億,盤後重挫逾 15%"),
"HIMS": ("earnings", True, "Q2 每股虧損 $0.37 遠不如預估虧 $0.05,營收 7.53 億美元雖超乎預期仍重挫"),
"CRNT": ("earnings", True, "Q2 營收 9,390 萬美元年增 14.2% 超乎預期,上調全年營收財測至 3.55-3.85 億美元"),
"VSA":  ("momentum", False, "查無明確消息"),
"HROW": ("earnings", True, "Q2 每股虧損 $0.46 遠不如預估虧 $0.11,營收 7,070 萬美元年增 11%,8/10 盤後重挫"),
"EVC":  ("earnings", True, "Q2 營收年增 126% 至 2.28 億美元,但獲利不如預期,財報後重挫"),
"BKKT": ("earnings", True, "Q2 營收年減 70% 至 1.70 億美元,靠一次性收益撐住帳面獲利仍重挫"),
"TME":  ("earnings", True, "Q2 營收年增 5.8% 至人民幣 89.3 億元,成長放緩,財報後重挫"),
"VG":   ("earnings", True, "Q2 營收年增 48% 至 46 億美元,雖調高全年 EBITDA 財測仍一度重挫"),
# 新增盤前 gapper
"KEEL": ("earnings", False, "Q2 營收 3,040 萬美元不如預估 3,342 萬,前一日挫 12% 後今日反彈;Alliance 下修目標價至 $7"),
"NB":   ("news", False, "Elk Creek 可行性研究:稅前淨現值 41 億美元,8/11 法說會公布數據,分析師目標價 $11.72"),
"TDIC": ("momentum", False, "查無明確消息(8/13 將公布財報,盤前無對應新聞可解釋跌幅)"),
"P":    ("contract", False, "與第二家前五大雲端業者簽 DirectFlash 設計供應協議(FY2028 起貢獻營收),8/10 已獲兩家券商調升"),
"BSP":  ("analyst", False, "瑞穗以併購題材調升目標價;漲幅大於單一目標價調升所能解釋,其餘原因查無"),
"ACM":  ("earnings", True, "會計年度 Q3 認列 3.37 億美元工程減損,GAAP 每股虧損 $0.65,營收季減 14.2%"),
"EVH":  ("momentum", False, "查無明確消息(Q2 財報 8/6 已公布並反應完畢)"),
"RILY": ("momentum", False, "查無明確消息(Q2 財報 8/6 已公布並反應完畢)"),
"SANA": ("earnings", True, "Q2 手上現金 1.605 億美元;透過 ATM 增發加上 Mayo 投資共募得 9,330 萬美元"),
"BKD":  ("earnings", True, "Q2 EPS $0.10 勝預估虧 $0.06,但營收 7.19 億美元季減 11.6% 不如預期"),
}

rows = list(csv.DictReader(open('candidates.csv', encoding='utf-8-sig')))
syms = sorted({r['Symbol'] for r in rows})
out = {}
for s in syms:
    if s in C:
        t, er, cat = C[s]
        out[s] = {"Type": t, "Catalyst": cat, "EarningsReaction": er}
missing = [s for s in syms if s not in out]
json.dump(out, open('catalysts_today.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('wrote', len(out), 'MISSING:', ' '.join(missing))
