# -*- coding: utf-8 -*-
"""Re-rank claude_picks.json for the 8/4 9:30 ET refresh.

Keeps the pre-market rationales verbatim; folds in the three names that only
became visible after the open (MOVE, W, AHCO).
"""
import json, io

NEW = {
    'MOVE': dict(intent='long', rationale=(
        '今天全市場最大的單一事件驅動。8/4 盤前 Corvex(前身 Movano)宣布簽下多年期合約,'
        '為一家「領先的 AI 公司」提供 **NVIDIA Blackwell GPU 叢集**,搭配 NVIDIA Quantum-2 '
        'InfiniBand 網路。技術面的重點是速度:公司在既有的氣冷機房裡,'
        '從設備到貨後約 **兩週** 就完成高密度液冷 HGX B200 機櫃的安裝與驗收,'
        '不必打掉重建、也不用搬到新園區 —— 這正是資料代管業者最難做到的一件事。\n\n'
        '財務結構才是這則新聞真正值錢的地方:這次擴充的資金來自 **債務融資、客戶預付款與'
        '手上現金**,公司明講沒有再發新股。也就是說營收要進來,但股東沒有被稀釋。'
        '營收將隨叢集分批交付在 2026 年內認列,滿載的營收貢獻從本季中段開始。\n\n'
        '風險要講清楚:市值僅約 **$6.2 億**、半年已經漲了 **105%**、放空比重只有 0.62%,'
        '沒有軋空柴火,今天 +68% 已經把大部分好消息反映掉。'
        '這是一檔靠真實合約撐起來的當沖題材股,不是可以無腦抱的持股。')),
    'W': dict(intent='long', rationale=(
        '大型股裡今天最乾淨的財報跳空。8/4 盤前 Wayfair 公布 Q2:'
        '調整後 EPS **$0.95** 勝華爾街預估的 $0.90,營收 **$35.2 億** 高於預估的 $34.7 億,'
        '較去年同期的 $32.7 億成長約 **7.6%**;活躍客戶數同樣超標。\n\n'
        '這檔的意義在於「線上家具在高利率環境下還能加速」這件事本身。'
        '過去兩年市場對 Wayfair 的疑慮一直是:房市凍住、大件家具是遞延性消費,'
        '營收要怎麼回到成長軌道。這一季營收與獲利同時超標,而且是**營收超標帶動**,'
        '不是靠砍成本擠出來的獲利,方向性比單季數字重要。\n\n'
        '市值約 **$120 億**,+17.6% 的跳空對這個量級的公司來說是大幅度重估。'
        '要留意的是零售股財報跳空常在開盤 30 分鐘內出現獲利了結,追高前先看量能守不守得住。')),
    'AHCO': dict(intent='short', rationale=(
        '今天最重的財報利空,而且壞在最要命的地方 —— 財測。'
        '8/4 盤前 AdaptHealth 公布 Q2 營收 **$7.40 億**,遠低於市場預估的 $8.47 億;'
        '每股虧損 **$0.99**,去年同期還是每股獲利 $0.11。'
        '營業利益率從去年同期的 **+9.9% 翻成 -18.6%**,自由現金流由 +$7,333 萬轉為 **-$2,094 萬**。\n\n'
        '真正砸盤的是全年指引:全年營收中位數下修到 **$28.7 億**,比華爾街預估低 **17.7%**;'
        '全年調整後 EBITDA 指引中位數 **$5.05 億**,對比市場原本預估的 $6.97 億,'
        '等於一口氣砍掉將近三成的獲利預期。單季不如預期還能解釋成時間差,'
        '全年一次砍到這個幅度,代表的是居家醫療設備的給付與成本結構出了持續性的問題。\n\n'
        '空方要注意的兩件事:市值只剩約 **$10 億**,放空比重 **9.29%**、回補天數 **5.65 天**,'
        '籌碼偏緊,急殺後的反彈軋空風險不低;而且一個月已經跌了 28%,'
        '今天再 -26.8%,追空的位置並不好。比較合理的做法是等反彈到壓力區再找空點。')),
}

# rank -> symbol (post-open ordering)
ORDER = ['COHR', 'PLTR', 'MOVE', 'CAT', 'W', 'AEIS', 'AAOI', 'AMRC', 'AHCO', 'POWL']

with io.open('claude_picks.json', encoding='utf-8') as f:
    data = json.load(f)

old = {p['symbol']: p for p in data['picks']}
picks = []
for i, sym in enumerate(ORDER, 1):
    if sym in NEW:
        picks.append(dict(symbol=sym, rank=i, intent=NEW[sym]['intent'],
                          rationale=NEW[sym]['rationale']))
    else:
        p = dict(old[sym])
        p['rank'] = i
        picks.append(p)

data['picks'] = picks
with io.open('claude_picks.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print('picks: ' + ', '.join('%d.%s(%s)' % (p['rank'], p['symbol'], p['intent']) for p in picks))
print('dropped: ' + ', '.join(s for s in old if s not in ORDER))
