---
title: SIPs-codex-full
runs_on: Codex CLI (ChatGPT)
sister_command: SIPs-codex-picks (skip scrape, picks-only)
related: SIPs (Claude version), SIPs-gemini-full (Gemini version)
---

# /SIPs-codex-full — full SIPs pipeline, ChatGPT's curation

You are running as **Codex CLI (ChatGPT)**. Execute the FULL `/SIPs` workflow as
documented at `D:\SIPs\skills\SIPs\SKILL.md` (read it before starting — every phase
applies to you exactly the same as it does to Claude), with **ONE difference**:

> When you reach Phase 8 (curate the top 10 SIPs + top 4 short candidates with rationales),
> write your output to **`D:\SIPs\codex_picks.json`** instead of `claude_picks.json`.
>
> **Never touch `claude_picks.json` or `gemini_picks.json`.** Those belong to the other
> agents. Your tab on the dashboard reads from `codex_picks.json`; their tabs read from
> their own files.

## Schema for `codex_picks.json`

Same as `claude_picks.json` — identical shape so the dashboard can render all three
tabs uniformly:

```json
{
  "picks": [
    { "symbol": "FIG",  "rank": 1, "intent": "long",  "rationale": "Q1 EPS beat +6% / Rev +37% YoY ..." },
    { "symbol": "ARM",  "rank": 2, "intent": "long",  "rationale": "..." },
    { "symbol": "BOOT", "rank": 3, "intent": "short", "rationale": "..." }
  ]
}
```

Field rules:
- `symbol` — uppercase ticker
- `rank`   — 1-based ordering; 1 = your top pick
- `intent` — `'long'` for gap-up plays, `'short'` for gap-down plays (dashboard hides
  picks whose intent doesn't match today's actual chgPct direction unless the
  "mismatch" toggle is on)
- `rationale` — 1-3 sentences in 繁體中文 explaining WHY this is your pick. Cite
  specific numbers from the scan data (EPS surprise %, Rev YoY, gap %, vol vs avg,
  catalyst headline). NO generic platitudes like "good momentum" — be specific.

## How your picks should differ from Claude's

You're not Claude. Pick what YOU think looks best from the day's gap candidates based on
your own model of what makes a good Stocks-In-Play setup. Don't try to match Claude —
that defeats the purpose of having three independent curators. The user reads all three
tabs and decides which agent's pattern recognition they trust for which kind of setup.

## What to scrape / read

Same input data as Claude. The full pipeline is:

1. **Barchart scrape** → `node D:\SIPs\barchart-scrape.js` (or use pre-scraped
   `D:\SIPs\candidates.csv` if it exists and is fresh — same day's date).
2. **Finviz shorts** → `node D:\SIPs\finviz-shorts.js` (or use cached `shorts.json`).
3. **TradingView FQ** → `node D:\SIPs\tv-scrape.js <SYMS>` + `py D:\SIPs\parse_tv.py`.
4. **News sourcing** for top candidates → WebFetch / WebSearch.
5. **MAGNA53 classification** → in-memory only, no file output.
6. **Brief composition** in 繁體中文 → for chat output (not file).
7. **Phase 8 — write `codex_picks.json`** ← your only file write.
8. **Phase 10 — `py D:\SIPs\build_dashboard.py`** → rebuilds dashboard.
9. **Phase 11 — auto git push** (user has standing approval, no confirmation needed).

## What you must NOT touch

- `claude_picks.json` — Claude's territory
- `gemini_picks.json` — Gemini's territory
- `dashboard/studies/studies.json` — user's hand-curated research library
- `news_detail.json` — shared, used by all three but written by whichever agent first
  curates it. If it already exists for today, leave it alone (Claude / Gemini may have
  already written it). If not, you may write it.
- `day_resets.json` / `catalysts_today.json` — shared curated state; leave alone.

The three agents all share read access to the scrape outputs (Barchart / Finviz / TV /
news), but each writes ONLY to their own picks file. That's the contract.

## Output for the user

After completing all phases, give the user a tight 6-12 line summary:
- # candidates scanned
- # of your top picks written to `codex_picks.json`
- which ticker is your #1 + a one-line rationale
- whether build + push succeeded
- the live dashboard URL: `https://chi2tseng.github.io/stocks-in-play/`
  + which tab to click ("ChatGPT 精選")

Stop there. Don't add commentary.
