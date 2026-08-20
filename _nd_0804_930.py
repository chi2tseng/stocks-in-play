# -*- coding: utf-8 -*-
"""Add picks-tier news_detail entries for the three post-open additions."""
import json, io

ND = {
    'MOVE': {
        'detail': (
            '> **今日漲因:** 盤前 +68% — 8/4 Corvex 宣布簽下多年期合約,為一家領先的 AI 公司提供 '
            'NVIDIA Blackwell GPU 叢集,且擴充資金全來自債務、客戶預付款與現金,沒有增發新股。\n\n'
            '**合約內容**\n'
            'Corvex, Inc.(NASDAQ: MOVE,前身為 Movano)於 8/4 盤前公告,已簽署一份**多年期協議**,'
            '向一家未具名的「領先 AI 公司」提供 **NVIDIA Blackwell GPU 叢集**,'
            '叢集之間以 **NVIDIA Quantum-2 InfiniBand** 網路互連。'
            '公司未揭露合約總金額與客戶名稱。\n\n'
            '**技術執行:兩週完成液冷改裝**\n'
            ' 公告中最具體、也最難複製的一段是部署速度:Corvex 在**既有的氣冷機房內**,'
            '於設備到貨後約 **兩週** 完成高密度 **液冷 NVIDIA HGX B200** 產能的安裝與驗收,'
            '過程中不需要打掉重建機房,也不必搬遷到新園區。'
            '對資料中心代管業者而言,把氣冷場館就地改成能吃下 Blackwell 功耗密度的液冷環境,'
            '通常是整個交付流程中最慢的一關。\n\n'
            '**資金結構:不稀釋股東**\n'
            '這次擴充由 **債務融資、客戶預付款與公司手上現金** 共同支應,'
            '公司明確表示 **未發行新股**。營收將隨叢集分批交付於 2026 年內陸續認列,'
            '滿載的營收貢獻自本季中段開始。客戶預付款同時也代表需求端已先付錢,'
            '而不是簽了一紙意向書。\n\n'
            '**市場反應與籌碼**\n'
            '消息公布後股價盤前一度大漲逾 **67%**,成交量約 **61.9 萬股**。'
            '公司市值約 **$6.2 億**,近一個月已漲 **24%**、近半年漲 **105%**;'
            '放空比重僅 **0.62%**、回補天數 1.66 天,沒有軋空籌碼可燒,'
            '今天的漲幅屬於對新合約的直接重估。'
        ),
        'publishedAt': '2026-08-04T07:00:00-04:00',
        'publishedTimezone': 'ET',
        'sources': [
            {'label': 'Corvex 公告 — Signs Multi-Year Agreement to Provide NVIDIA Blackwell GPU Clusters',
             'url': 'https://www.stocktitan.net/news/MOVE/corvex-signs-multi-year-agreement-to-provide-nvidia-blackwell-gp-4v681x01ivv1.html'},
            {'label': 'Investing.com — Corvex signs multi-year deal for Nvidia Blackwell GPU clusters',
             'url': 'https://ca.investing.com/news/stock-market-news/corvex-signs-multiyear-deal-for-nvidia-blackwell-gpu-clusters-93CH-4773871'},
        ],
    },
    'W': {
        'detail': (
            '> **今日漲因:** 盤前 +17.6% — 8/4 盤前公布 Q2 財報,調整後 EPS $0.95 與營收 $35.2 億雙雙優於'
            '華爾街預估,活躍客戶數同步超標。\n\n'
            '**財報數字**\n'
            'Wayfair 於 8/4 美股盤前公布 2026 年第 2 季業績:**調整後每股盈餘 $0.95**,'
            '高於華爾街預估的 **$0.90**;**營收 $35.2 億**,同樣優於預估的 **$34.7 億**,'
            '較去年同期的 $32.7 億成長約 **7.6%**。公司同時表示活躍客戶數表現超出預期。\n\n'
            '**為什麼這一季重要**\n'
            '市場過去兩年對 Wayfair 最大的疑慮,是房市交易量在高利率下凍結,'
            '而家具屬於典型的遞延性大件消費 —— 房子沒換,家具就不會換。'
            '這一季的關鍵在於**營收超標帶動獲利超標**,而不是靠壓縮行銷與物流費用擠出來的獲利,'
            '方向性的意義大過單季數字本身。\n\n'
            '**市場反應**\n'
            '盤前股價一度上漲逾 **17%**,報約 **$106**,公司市值約 **$120 億**。'
            '對這個量級的公司而言,單日 17% 的跳空屬於大幅度重估。'
            '要留意的是零售股財報跳空常在開盤後 30 分鐘內出現獲利了結,'
            '量能能不能守住是當日的觀察重點。'
        ),
        'publishedAt': '2026-08-04T07:44:00-04:00',
        'publishedTimezone': 'ET',
        'sources': [
            {'label': 'MT Newswires — Wayfair Q2 Adjusted Earnings, Revenue Rise',
             'url': 'https://finance.yahoo.com/markets/stocks/articles/wayfair-q2-adjusted-earnings-revenue-114407666.html'},
            {'label': 'Wayfair Investor Relations', 'url': 'https://investor.wayfair.com/'},
        ],
    },
    'AHCO': {
        'detail': (
            '> **今日跌因:** 盤前 -26.8% — 8/4 盤前 Q2 營收 $7.40 億大幅低於預估 $8.47 億、'
            '每股虧損 $0.99,更關鍵的是全年營收與獲利指引一次砍到遠低於市場預期。\n\n'
            '**財報數字**\n'
            'AdaptHealth 於 8/4 盤前公布 2026 年第 2 季業績:**營收 $7.40 億**,'
            '遠低於華爾街預估的 **$8.47 億**;**每股虧損 $0.99**,'
            '去年同期為每股獲利 $0.11。獲利品質同步惡化 —— '
            '**營業利益率從去年同期的 +9.9% 轉為 -18.6%**,'
            '**自由現金流由 +$7,333 萬轉為 -$2,094 萬**。\n\n'
            '**真正砸盤的是全年財測**\n'
            '公司把 **全年營收指引中位數下修到 $28.7 億**,較華爾街預估低 **17.7%**;'
            '**全年調整後 EBITDA 指引中位數 $5.05 億**,相對於市場原本預估的 **$6.97 億**,'
            '等於一次砍掉將近三成的獲利預期。'
            '單季不如預期還可以解釋成認列時間差,'
            '但全年一次下修到這個幅度,通常代表居家醫療設備的給付價格與成本結構'
            '出現的是持續性、而非一次性的問題。\n\n'
            '**籌碼與風險**\n'
            '公布後股價一度跌至約 **$8.05**,跌幅約 **25.7%**,市值僅剩約 **$10 億**。'
            '放空比重 **9.29%**、回補天數 **5.65 天**,籌碼偏緊。'
            '近一個月股價已跌 **28%**,今日再重挫近 27%,'
            '追空的位置並不理想 —— 高回補天數在急殺後容易出現軋空式反彈。'
        ),
        'publishedAt': '2026-08-04T06:30:00-04:00',
        'publishedTimezone': 'ET',
        'sources': [
            {'label': 'StockStory — AdaptHealth Reports Sales Below Analyst Estimates In Q2 CY2026',
             'url': 'https://markets.financialcontent.com/stocks/article/stockstory-2026-8-4-adapthealth-nasdaqahco-reports-sales-below-analyst-estimates-in-q2-cy2026-earnings-stock-drops-257'},
            {'label': 'AdaptHealth Investor Relations — Latest Earnings',
             'url': 'https://adapthealth.com/category/latest-earnings/'},
        ],
    },
}

with io.open('news_detail.json', encoding='utf-8') as f:
    nd = json.load(f)
nd.update(ND)
with io.open('news_detail.json', 'w', encoding='utf-8') as f:
    json.dump(nd, f, ensure_ascii=False, indent=2)
print('news_detail updated: %s | total %d' % (','.join(ND), len(nd)))
