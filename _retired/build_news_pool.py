"""build_news_pool.py — 把 Claude 的當日獵獲轉成新聞池格式。

新聞共享池架構(2026-07-10 起):
  - 三個獵人各寫自己的池檔,避免併發寫入衝突:
      news_pool_claude.json  ← 本腳本從 catalysts_today.json + news_detail.json 衍生
      news_pool_grok.json    ← Grok 的 /SIPs-grok-hunt 直接寫
      news_pool_gemini.json  ← Gemini 的 /SIPs-gemini-hunt 直接寫
  - 四個評審(claude/codex/gemini/grok 的 picks 模式)讀「全部存在的池檔」聯集後各自判斷。

池檔 schema(三份同構):
{
  "_date": "YYYY-MM-DD",
  "_hunter": "claude",
  "items": {
    "SYM": [ { "headline_zh": "...", "detail_zh": "...", "type": "earnings",
               "source_url": "...", "published": "..." } ]
  }
}

用法:py build_news_pool.py   (在 Claude 的 /SIPs 新聞獵取完成後跑)
"""
import json, os, sys, datetime, re

sys.stdout.reconfigure(encoding='utf-8')
DIR = os.path.dirname(os.path.abspath(__file__))

def load(name):
    p = os.path.join(DIR, name)
    if not os.path.exists(p):
        return {}
    with open(p, encoding='utf-8') as f:
        return json.load(f)

cat = load('catalysts_today.json')
nd = load('news_detail.json')

date = cat.get('_date') or datetime.date.today().strftime('%Y-%m-%d')
items = {}

TICKER_RE = re.compile(r'^[A-Z]{1,6}$')
for sym, v in cat.items():
    # 只收「像 ticker 的鍵 + 有 Catalyst 欄」的列;跳過 _date/_note/clusters 這類結構鍵
    if not TICKER_RE.match(sym) or not isinstance(v, dict) or not v.get('Catalyst'):
        continue
    entry = {
        'headline_zh': (v.get('Catalyst') or '')[:120],
        'detail_zh': '',
        'type': v.get('Type') or 'news',
        'source_url': '',
        'published': '',
    }
    d = nd.get(sym)
    if isinstance(d, dict):
        detail = d.get('detail') or ''
        # 摘 blockquote 首段(今日漲因/跌因)當 detail_zh;沒有就取前 200 字
        m = re.match(r'>\s*(.{0,300}?)(?:\n\n|$)', detail, re.S)
        entry['detail_zh'] = (m.group(1) if m else detail[:200]).strip()
        entry['published'] = d.get('publishedAt') or ''
        srcs = d.get('sources') or []
        if srcs and isinstance(srcs[0], dict):
            entry['source_url'] = srcs[0].get('url') or ''
    items[sym] = [entry]

out = {'_date': date, '_hunter': 'claude', 'items': items}
out_path = os.path.join(DIR, 'news_pool_claude.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(f'[OK] news_pool_claude.json: {len(items)} tickers, date={date}')
