# -*- coding: utf-8 -*-
"""Merge 8/4 9:30 ET late-sweep catalysts into catalysts_today.json."""
import json, io

NEW = {
    'MCD':  'Q2 調整後 EPS $3.38 小勝華爾街預估 $3.32,但營收 $71.0 億略低於預估 $71.3 億',
    'DUK':  'Q2 調整後 EPS $1.43 勝預估 $1.30(+9.6%)、年增 14%,營收 $75.9 億略低於預估;重申全年指引',
    'MPC':  'Q2 EPS $17.73 遠勝預估 $14.27、營收 $523 億超預估 28%(去年同期 EPS $3.96),煉油利差大幅改善',
    'APO':  'Q2 調整後 EPS $2.11 略遜預估 $2.16;資產管理與退休服務獲利創高,惟營收認列口徑與市場預估基準不同',
    'MPLX': 'Q2 EPS $1.06 與預估一致、營收 $30.8 億略低於預估 $31.4 億;調整後 EBITDA $17.75 億',
    'SYY':  'FQ4 EPS $0.94、營收 $205.2 億,雙雙貼近華爾街預估,股價幾無反應',
    'PEG':  '8/4 盤前公布 Q2 財報,股價幾無反應;TradingView 季度資料顯示最新一季 EPS $1.55、營收 $38.5 億均高於預估',
    'WAT':  'Q2 調整後 EPS $3.05 微幅超預估 $3.01、營收 $16.5 億優於預估,並上調全年指引',
    'KMB':  'Q2 調整後 EPS $2.12 勝預估 $2.01(+5.6%),但營收 $41.9 億略低於預估 $42.2 億',
    'NRG':  'Q2 EPS $1.49 遜於預估 $1.77(-15.9%),但營收 $102.9 億超預估 22%',
    'TSEM': 'Q2 EPS $0.88 勝預估 $0.76(+16.1%)、營收 $4.60 億創單季新高(年增 24%)',
    'EXPD': 'Q2 EPS $1.71 大勝預估 $1.33(+28.7%)、營收 $27.8 億超預估 6.6%',
    'ULS':  'Q2 非 GAAP EPS $0.59 勝預估 $0.56、營收 $8.16 億年增 5.2%,符合預期',
    'BALL': 'Q2 非 GAAP EPS $1.03 勝預估 $0.99、營收 $40.0 億年增近 20% 且超預估 8.3%',
    'KIM':  'Q2 每股 FFO $0.46 優於去年同期 $0.44、營收 $5.46 億貼近預估',
    'SUN':  'Q2 EPS $2.85 大勝預估 $1.72(+65.6%)、營收 $106.9 億超預估 4.9%',
    'HSBC': '上半年稅前獲利 $101 億美元年增 60% 優於預期,宣布加碼 $10 億美元庫藏股;中國跨境財富業務承壓',
}

with io.open('catalysts_today.json', encoding='utf-8') as f:
    cat = json.load(f)

for sym, text in NEW.items():
    cat[sym] = {'Type': 'earnings', 'EarningsReaction': True, 'Catalyst': text}

with io.open('catalysts_today.json', 'w', encoding='utf-8') as f:
    json.dump(cat, f, ensure_ascii=False, indent=2)

print('catalysts merged: %d new, %d total' % (len(NEW), len(cat)))
