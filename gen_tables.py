"""Generate 3 sorted markdown tables for the report."""
import csv, os

DIR = os.environ.get('SIPS_DIR') or os.path.dirname(os.path.abspath(__file__))
rows = []
with open(os.path.join(DIR, 'final-candidates.csv'), 'r', encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        try:
            rows.append({
                'Symbol': r['Symbol'],
                'Last': float(r['Last']),
                'ChgPct': float(r['ChgPct']),
                'Volume': int(r['Volume']),
                'Session': r['Session'],
                'Direction': r['Direction'],
                'Type': r['Type'],
                'Catalyst': r['Catalyst'],
                'TV_EPS': r['TV_LatestEPS'],
                'TV_Rev': r['TV_LatestRev_M'],
            })
        except (ValueError, TypeError) as e:
            print('[WARN] skipping bad final-candidates.csv row', r.get('Symbol'), e)
            continue

def fmt_vol(v):
    if v >= 1_000_000: return f'{v/1_000_000:.1f}M'
    return f'{v/1000:.0f}K'

def fmt_price(p):
    if p < 10: return f'${p:.2f}'
    return f'${p:.2f}'

def fmt_chg(c):
    return f'{c:+.2f}%'

def make_table(rows, title, sort_key, reverse=False):
    sorted_rows = sorted(rows, key=sort_key, reverse=reverse)
    out = [f'\n### {title}\n']
    out.append('| # | Ticker | Price | %Chg | Vol | Session | Dir | Type | 簡述 |')
    out.append('|---|---|---|---|---|---|---|---|---|')
    for i, r in enumerate(sorted_rows, 1):
        dir_emoji = '🟢' if r['Direction'] == 'up' else '🔴'
        out.append(f"| {i} | **{r['Symbol']}** | {fmt_price(r['Last'])} | {fmt_chg(r['ChgPct'])} | {fmt_vol(r['Volume'])} | {r['Session']} | {dir_emoji}{r['Direction']} | {r['Type']} | {r['Catalyst']} |")
    return '\n'.join(out)

# View 1: by |%Chg| descending
view1 = make_table(rows, '檢視 1 — 按 |%Chg| 排序 (波動度最大者在前)', lambda r: abs(r['ChgPct']), reverse=True)
# View 2: by Session (pre first, then post), then |%Chg| desc within session
view2 = make_table(rows, '檢視 2 — 按 Session 分組 (pre → post)，組內按 |%Chg| 排序', lambda r: (r['Session'], -abs(r['ChgPct'])))
# View 3: by Price ascending (lowest first)
view3 = make_table(rows, '檢視 3 — 按 Price 排序 (低價在前，便宜 = 風險profile 不同)', lambda r: r['Last'])

with open(os.path.join(DIR, 'sorted-views.md'), 'w', encoding='utf-8') as f:
    f.write(view1)
    f.write('\n\n---\n')
    f.write(view2)
    f.write('\n\n---\n')
    f.write(view3)

print(f"Wrote sorted-views.md ({os.path.getsize(os.path.join(DIR, 'sorted-views.md'))} bytes)")
print(f"Total rows in each view: {len(rows)}")
