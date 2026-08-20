import csv,io,json
DATE='2026-08-04'
NEW={
 'APTV':(-6.95,53.25,'Aptiv PLC','Q2 EPS $1.63 優於預期 $1.43,但下修全年 EPS 至 $5.60-5.80、營收指引降至 $126-128 億','guidance',True),
 'ENLT':(8.50,89.73,'Enlight Renewable Energy Ltd.','Q2 營收 $2.10 億年增 55%、EPS $0.20 優於預期 $0.19,並上修全年展望','earnings',True),
 'IT':(7.86,163.44,'Gartner, Inc.','Q2 營收 $16.8 億超預期 $16.5 億、EPS $4.37 遠優於預期 $3.73','earnings',True),
 'CCEP':(-2.47,105.52,'Coca-Cola Europacific Partners plc','上半年稅後淨利 9.91 億歐元優於預期 9.84 億、EPS 年增 10.6% 至 2.20 歐元,但全年展望僅維持未上修','earnings',True),
 'PNW':(-2.49,98.30,'Pinnacle West Capital Corporation','8/4 盤前公布 Q2 財報,市場預期 EPS 約 $1.46-1.49、營收 $14 億;股價漲多回檔','earnings',True),
 'BNTX':(-2.47,89.98,'BioNTech SE','Q2 營收僅 1.056 億歐元、較去年同期 2.608 億腰斬,下修全年展望至 16-19 億歐元','guidance',True),
 'LSCC':(6.94,136.00,'Lattice Semiconductor Corporation','完成收購 AMI,TD Cowen 等券商調升目標價至 $165;財報今晚盤後才公布','analyst',False),
}
rows=list(csv.DictReader(io.open('candidates.csv',encoding='utf-8-sig')))
have={r['Symbol'] for r in rows}
fn=list(rows[0].keys())
for s,(chg,px,name,cat,ty,er) in NEW.items():
    if s in have: print('[skip]',s); continue
    rows.append({'Symbol':s,'Last':px,'ChgPct':chg,'Volume':0,'Session':'headline','SessionDate':DATE,'Direction':'up' if chg>=0 else 'down','Name':name})
w=csv.DictWriter(io.open('candidates.csv','w',encoding='utf-8-sig',newline=''),fieldnames=fn)
w.writeheader(); w.writerows(rows)
cj=json.load(io.open('catalysts_today.json',encoding='utf-8'))
for s,(chg,px,name,cat,ty,er) in NEW.items():
    cj[s]={'Catalyst':cat,'Type':ty,'EarningsReaction':er}
# shard A-D catalysts
SH={
 'AAOI':('隨光通訊/AI 族群齊漲;川普政府擬禁中國光模組進美資料中心,公司全年營收展望上看 10 億美元,8/6 財報前買盤湧入','policy',False),
 'ALAB':('隨 AI 族群走揚,TD Cowen 上調目標價至 $425;Q2 財報今晚盤後才公布','analyst',False),
 'AMD':('隨 AI 晶片族群走升;Q2 財報今晚盤後才公布,市場預期營收年增 47%','momentum',False),
 'AMKR':('查無當日個股新聞,隨光通訊/AI 封裝族群走(上週財報後重挫 23%,今日反彈)','momentum',False),
 'ASTS':('Meta 高管暗示 WhatsApp 將支援衛星直連,BlueBird 衛星 8/5 發射前買盤湧入','news',False),
 'CAT':('Q2 營收 $205 億創新高、EPS $8.17 遠超預期 $6.20','earnings',True),
 'CIFR':('Q2 營收 $2,500 萬遜於預期 $2,928 萬,EBITDA 虧損 $3,000 萬','earnings',True),
 'COHR':('川普政府草擬禁令、禁中國製光收發模組進入美國資料中心,Coherent 被點名為美系替代供應商;疊加 NVIDIA $20 億入股','policy',False),
 'CRDO':('川普政府擬禁中國資料中心光收發模組進口,美系光通訊供應鏈全面走揚','policy',False),
 'CRML':('高盛發布 AI「從礦到磁鐵」報告點名關鍵礦產,CRML 延續前日 17% 漲勢','analyst',False),
 'FLNC':('查無當日個股新聞,隨 AI 電力/儲能族群走','momentum',False),
 'GFS':('美國商務部意向書擬撥 3 億美元協助 GF 研發矽光子,疊加禁中國光模組題材','contract',False),
 'GLW':('川普政府擬立法禁止進口中國資料中心光收發模組,Corning 為主要受惠者','policy',False),
 'HPE':('查無當日個股新聞,隨 AI 資料中心硬體族群走','momentum',False),
 'HUT':('Q2 營收 $7,490 萬遜於共識 $8,000 萬,每股虧損 $1.27 遠差於預期','earnings',True),
 'INTC':('半導體股自週一中國競爭疑慮反彈,疊加禁中國光模組政策題材帶動','momentum',False),
 'KC':('查無當日個股新聞,隨中國 AI 雲端(金山雲/小米 GPU 題材延續)族群走','momentum',False),
 'LITE':('川普政府草擬禁令、禁中國製光收發模組進入美國資料中心,Lumentum 被點名為美系替代供應商','policy',False),
 'LPL':('查無當日個股新聞,隨光通訊/AI 基建族群走','momentum',False),
 'LWLG':('同受禁中國光模組消息激勵,電光聚合物調變器廠 LWLG 盤前漲近 14%','policy',False),
 'MP':('川習會前市場憂中國稀土出口管制加碼(彭博 8/3 報導),MP 盤前漲逾 5%','policy',False),
 'MRVL':('Marvell 於 FMS 2026 展示 Agentic AI 記憶體方案,帶動盤前漲逾 8%','news',False),
 'MXL':('MaxLinear 與 Everspin 簽 MOU 共同研發 AI 伺服器 MRAM 架構,股價漲 7.7%','contract',False),
 'NOK':('查無當日個股新聞,隨 AI/資料中心基建族群走(AI-RAN 與輝達合作題材延續)','momentum',False),
 'NVTS':('8/3 盤後公布 Q2 營收 $1,050 萬、季增 22% 勝預期 $997 萬,Q3 營收指引季增 28%','earnings',True),
 'POET':('查無當日個股新聞,隨光通訊族群走(禁中國光模組政策題材帶動)','momentum',False),
 'SATL':('8/5 將公布 Q2 財報,市場預期營收年增 110% 至 $933 萬,提前布局走高','momentum',False),
 'SPOT':('Q2 付費訂閱戶破 3 億創紀錄,但 Q3 營業利益指引 6.7 億歐元低於市場預期 6.78 億','earnings',True),
 'WDC':('查無當日個股新聞,隨記憶體族群走(SK 海力士 Q2 營收年增 257% 激勵 AI 儲存需求)','momentum',False),
 'WOLF':('查無當日個股新聞,隨 AI 資料中心功率半導體/光通訊族群走,財報 8/19 才公布','momentum',False),
 'KRYS':('8/3 公布 Q2 EPS $1.79 不如預期 $1.91、營收 $1.192 億亦低於預期 $1.204 億','earnings',True),
 'DOCN':('Q2 數字符合稍早預告的強勁 RPO(季增逾 10 倍達 $8 億),但獲利了結、Barclays 目標價砍至 $160','earnings',True),
}
for s,(cat,ty,er) in SH.items():
    cj[s]={'Catalyst':cat,'Type':ty,'EarningsReaction':er}
json.dump(cj,io.open('catalysts_today.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
rows2=list(csv.DictReader(io.open('candidates.csv',encoding='utf-8-sig')))
print('rows',len(rows2),'uniq',len({r['Symbol'] for r in rows2}),'catalysts',len(cj))
miss=[r['Symbol'] for r in rows2 if r['Symbol'] not in cj]
print('missing catalyst:',miss)
