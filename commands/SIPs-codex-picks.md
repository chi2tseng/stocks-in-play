---
title: SIPs-codex-picks
runs_on: Codex CLI (ChatGPT)
sister_command: SIPs-codex-full (full pipeline)
related: SIPs-gemini-picks (Gemini version)
---

# /SIPs-codex-picks — picks-only, no scrape

You are running as **Codex CLI (ChatGPT)**. Today's scan data was already produced by
another agent (Claude's `/SIPs` or `/SIPs-gemini-full`). Your job: **just curate your
own top picks** based on the existing data, and write them to `codex_picks.json`.

Do NOT re-run any scrape (Barchart / Finviz / TradingView), do NOT re-fetch news, do
NOT touch news_detail.json / day_resets.json / catalysts_today.json. **All you do is
read the existing scan output and write `codex_picks.json`.**

## Step-by-step

### 1. Verify the scan exists for today

```bash
ls D:\SIPs\dashboard\data\<YYYY-MM-DD>.json
ls D:\SIPs\candidates.csv   # raw Barchart output
ls D:\SIPs\tv-summary.json  # TV FQ data
```

If `dashboard/data/<today>.json` doesn't exist, ABORT and tell the user to run
`/SIPs` (Claude) or `/SIPs-gemini-full` (Gemini) first — somebody needs to do the
actual scrape before picks-only mode is valid.

### 2. Read the candidate set

```python
import json, os, datetime
today = datetime.date.today().strftime('%Y-%m-%d')
with open(f'D:/SIPs/dashboard/data/{today}.json', encoding='utf-8') as f:
    data = json.load(f)
stocks = data['stocks']   # dict: { 'SYM': { sessions, chgPct, last, volume, type, catalyst, newsDetail, tv, ... } }
```

You now have everything Claude / Gemini saw: per-symbol catalyst, sessions, chgPct,
TV financials, news. Use this as your only input — no web search needed unless you
want to enrich a specific catalyst your decision hinges on.

### 3. Pick your top 10 SIPs + top 4 short candidates

Apply the same Stocks-In-Play methodology /SIPs uses:
- **Magnitude** (gap %, vol vs avg)
- **Quality** (earnings beat, contract win, M&A premium — clean catalyst)
- **Setup** (cup-with-handle, episodic pivot, breakout from base)

But pick what YOU think is best. Don't copy Claude's existing `claude_picks.json` — that
defeats the purpose. The user is comparing three independent reads.

### 4. Write `D:\SIPs\codex_picks.json`

```json
{
  "picks": [
    { "symbol": "FIG",  "rank": 1, "intent": "long",  "rationale": "..." },
    { "symbol": "ARM",  "rank": 2, "intent": "long",  "rationale": "..." }
  ]
}
```

Rationale rules:
- 1-3 sentences, 繁體中文
- Cite specific numbers from the scan (EPS surprise %, Rev YoY, gap %, vol)
- Explain WHY this beat your other candidates, not just why it's "good"

### 5. Rebuild dashboard + auto-push

```powershell
cd D:\SIPs
py build_dashboard.py
git add codex_picks.json dashboard/data/<DATE>.json dashboard/data.json dashboard/dates.json dashboard/index.html
git commit -m "codex picks: <DATE> — top: <SYM1>, <SYM2>, ..."
git push
```

User has standing auto-push approval — no confirmation prompt needed.

## What you must NOT touch

Same as `/SIPs-codex-full`: never write to `claude_picks.json` / `gemini_picks.json` /
`dashboard/studies/studies.json` / `news_detail.json` / `day_resets.json` /
`catalysts_today.json`. Picks-only mode means **picks file + rebuild + push, nothing
else**.

## Output for the user

Tight summary:
- "Read N candidates from <DATE>'s scan"
- "Wrote M picks to codex_picks.json"
- "Top pick: <SYM> — <one-line rationale>"
- "Live at https://chi2tseng.github.io/stocks-in-play/ (ChatGPT 精選 tab) in ~30s"
