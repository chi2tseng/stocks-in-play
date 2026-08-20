import json
with open('dashboard/data/2026-07-29.json', encoding='utf-8') as f:
    data = json.load(f)
stocks = data.get('stocks', {})
longs = sorted([s for s in stocks.values() if s.get('chgPct', 0) > 4], key=lambda x: x.get('chgPct', 0), reverse=True)
shorts = sorted([s for s in stocks.values() if s.get('chgPct', 0) < -4], key=lambda x: x.get('chgPct', 0))
with open('scratch_out.txt', 'w', encoding='utf-8') as out:
    out.write('--- TOP LONGS ---\n')
    for s in longs[:30]:
        out.write(f"{s['symbol']:<5} {s.get('chgPct'):>6.2f}% | Vol: {s.get('volume', 0):>8} | Type: {s.get('type')} | Cat: {s.get('catalyst')}\n")
    out.write('\n--- TOP SHORTS ---\n')
    for s in shorts[:30]:
        out.write(f"{s['symbol']:<5} {s.get('chgPct'):>6.2f}% | Vol: {s.get('volume', 0):>8} | Type: {s.get('type')} | Cat: {s.get('catalyst')}\n")
