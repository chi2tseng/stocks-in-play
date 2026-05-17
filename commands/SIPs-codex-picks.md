---
title: SIPs-codex-picks
runs_on: Codex CLI (ChatGPT)
sister_command: SIPs-codex-full (full pipeline + writes shared state)
related: SIPs-gemini-picks (Gemini version)
---

# /SIPs-codex-picks — your own picks, no shared-state writes

You are running as **Codex CLI (ChatGPT)**. The day's scan (Barchart gap scan,
TradingView FQ scrape, Finviz shorts data) was already produced by another agent —
Claude's `/SIPs` or `/SIPs-gemini-full`. You **don't re-run the scraping** — those
files are expensive to regenerate and already current for today.

But you DO need to research each top candidate yourself: read its news, study its
financials, judge whether the setup is clean. That research informs your `rationale`
field — you can't write a meaningful 1-3 sentence pick rationale without knowing what
the catalyst actually was and how the numbers look. **Picks-mode means "make your own
analytical choices using the shared scrape inputs", not "skip analysis".**

The single hard rule: **your file writes are scoped to `codex_picks.json` only**. The
shared state files (`news_detail.json`, `day_resets.json`, `catalysts_today.json`)
already contain Claude's analysis — don't overwrite them. Your own analytical
perspective goes into the `rationale` field of each pick, NOT into those shared files.

## Step-by-step

### 1. Verify the scan is fresh for today

```bash
ls D:\SIPs\dashboard\data\<YYYY-MM-DD>.json
ls D:\SIPs\candidates.csv     # raw Barchart gap scan output
ls D:\SIPs\tv-summary.json    # TV FQ data (per-ticker EPS/Rev + chart)
ls D:\SIPs\final-candidates.csv  # post-MAGNA53 filtered set (Claude's output)
```

If `dashboard/data/<today>.json` doesn't exist, ABORT and tell the user to run
`/SIPs` (Claude) or `/SIPs-gemini-full` (Gemini) first — somebody needs to do the
actual scrape before you can do picks-only.

### 2. Read the candidate set

```python
import json, datetime
today = datetime.date.today().strftime('%Y-%m-%d')
with open(f'D:/SIPs/dashboard/data/{today}.json', encoding='utf-8') as f:
    data = json.load(f)
stocks = data['stocks']
# Each stocks[SYM] has: sessions, chgPct, last, volume, type, catalyst, newsDetail,
# tv (full EPS/Rev/chart), shortFloat, shortRatio, marketCap_M, etc.
```

This is your starting universe. ~50-100 tickers depending on the day. From here you
decide which deserve your top 10.

### 3. For each candidate you're seriously considering — DO YOUR OWN RESEARCH

This is where you earn your spot vs. Claude / Gemini. Don't just copy their picks.

- **WebSearch** for `<TICKER> <today's date> news` to read the catalyst story in your
  own words. The `stocks[SYM].catalyst` and `stocks[SYM].newsDetail` fields contain
  CLAUDE's summary — don't blindly trust it. Form your own opinion.
- **WebFetch** on SEC EDGAR / company IR pages for any 8-K filing if it's an earnings
  catalyst — confirm consensus vs reported, look at guidance, analyst reaction.
- **Inspect the TV data** in `stocks[SYM].tv`:
  - EPS surprise % + Revenue surprise %
  - YoY EPS / Rev growth
  - Forward 4 quarter estimates
  - Whether the chart shows acceleration or deceleration
- **Cross-check with Yahoo / Reuters / Bloomberg / Briefing** for the same-day analyst
  commentary.

You're competing with Claude and Gemini for the user's attention on which agent
catches the best setups. Your picks need a real edge — find it via research, not by
matching the other agents.

### 4. Apply Stocks-In-Play methodology

Same framework `/SIPs` uses (see `D:\SIPs\skills\SIPs\SKILL.md § 4` for the canonical
spec):

- **Magnitude** (gap %, vol vs avg, % move on the day)
- **Quality of catalyst** (earnings beat / contract win / M&A premium / FDA approval —
  clean specific news, not generic "guidance update")
- **Setup** (cup-with-handle, episodic pivot, breakout from base, post-earnings drift)
- **Direction match** (intent='long' for gap-ups, intent='short' for gap-downs — the
  dashboard hides mismatched picks unless the user toggles the override)

But pick what YOU think is best. Don't try to match Claude's `claude_picks.json` or
Gemini's `gemini_picks.json`. That defeats the purpose of having three independent
curators — the user is comparing your pattern recognition to theirs.

### 5. Write `D:\SIPs\codex_picks.json`

```json
{
  "picks": [
    {
      "symbol": "FIG",
      "rank": 1,
      "intent": "long",
      "rationale": "Q1 FY26 EPS $0.57 vs $0.43 est (+33% surp), Rev $534M vs $510M (+5%), FY guidance raised. Cleanest beat in the gap set — analyst PT upgrades from 5 firms cited. 200 SMA breakout w/ 3.5x avg vol confirms institutional accumulation."
    },
    {
      "symbol": "BOOT",
      "rank": 11,
      "intent": "short",
      "rationale": "Guidance cut on weakening Western retail demand. Q1 missed Rev by -8%, mgmt cited softening footfall. Gap-down -12% on 4x vol. Bearish setup for continuation to 50 SMA."
    }
  ]
}
```

Field rules:
- `symbol` — uppercase ticker, must exist in `stocks` dict (else dashboard filters it out)
- `rank`   — 1-based; 1 = your top long, 11+ = your shorts (any rank, just ranked)
- `intent` — `'long'` (gap-up plays) or `'short'` (gap-down plays)
- `rationale` — 繁體中文 (preferred) or English, 1-3 sentences citing **specific numbers** from your research (EPS surprise %, Rev YoY, gap %, vol vs avg, analyst PT changes, catalyst headline). NO generic "good momentum" / "strong setup" platitudes.

Target ~10 long picks + ~4 short picks. Quality over quantity.

### 6. Rebuild dashboard + auto-push

```powershell
cd D:\SIPs
py build_dashboard.py
git add codex_picks.json dashboard/data/<DATE>.json dashboard/data.json dashboard/dates.json dashboard/index.html
git commit -m "codex picks: <DATE> — top: <SYM1>, <SYM2>, ..."
git push
```

User has standing auto-push approval — no confirmation prompt needed.

## What you must NOT touch

These belong to Claude / Gemini / the user. Picks mode is about doing your OWN analysis
and writing your OWN picks file — not about touching anyone else's state:

- `claude_picks.json` — Claude's territory
- `gemini_picks.json` — Gemini's territory
- `dashboard/studies/studies.json` — user's hand-curated research library (separate
  from the day's gap scan; never modified by /SIPs)
- `news_detail.json` — contains Claude's curated 繁體中文 news per top stock; surfaced
  in stock detail pages
- `day_resets.json` — Claude's day1/day2 reset judgments
- `catalysts_today.json` — Claude's catalyst-type classifications

If you want your own perspective on a particular ticker's news / catalyst, put it in
your pick's `rationale` field — that's YOUR space. Don't write to the shared files.

## Output for the user

Tight summary at the end:
- "Read N candidates from <DATE>'s scan"
- "Did research on top ~15 candidates (catalysts, financials, analyst notes)"
- "Wrote M picks to codex_picks.json: K longs + L shorts"
- "Top pick: <SYM> rank #1 — <one-line rationale citing the key driver>"
- "Live at https://chi2tseng.github.io/stocks-in-play/ (ChatGPT 精選 tab) in ~30s"
