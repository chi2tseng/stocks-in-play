# Stocks In Play (SIPs)

A daily **NTRT/MTRT gap scanner** + **Stocks In Play dashboard** that classifies overnight movers using Stockbee's SIP framework and Mark Minervini's **MAGNA53** template. Outputs a 繁體中文 morning brief + a local static-SPA dashboard.

> 🔒 **Private repo.** Invited collaborators only. Skillfish install requires a GitHub personal access token (see below).

---

## What it does

Every morning (or post-market evening), the `/SIPs` skill:

1. **Scrapes Barchart** pre+post-market gappers (±4% / 100k vol) via Playwright + XHR intercept (~7s)
2. **Hunts catalysts** for every candidate via parallel WebSearch / Finviz / X (~5 min, $0)
3. **Pulls TradingView FQ quarterly grids** for earnings movers (raw EPS/Rev figures + forward YoY)
4. **Pulls Finviz shorts** (`shortFloat`, `shortRatio`, `marketCap`, 1M/3M/6M/12M perf) for every candidate
5. **Classifies with MAGNA53** (Massive / Gap / Neglect / Acceleration / 5DTC / 3+ Analyst raises)
6. **Composes a 繁體中文 brief** ranking 🟢 SIPs and 🔴 short candidates
7. **Publishes a local static SPA** — Today's SIPs, Short Squeeze, Earnings Results, Catalyst Deep Dive, SCANX, Gappers, per-stock detail pages

**Total runtime ~5-10 min. Total cost: $0** (Playwright for scraping + Claude API for synthesis).

---

## How to install (invited friends)

You'll need: **Windows / macOS / Linux**, **Node.js 18+**, **Python 3.10+**, **Claude Code** (latest), and a **GitHub PAT** with `repo` scope (since this repo is private).

```bash
# 1. Clone the repo (you must be invited as collaborator)
git clone https://github.com/chi2tseng/stocks-in-play.git
cd stocks-in-play

# 2. Install Playwright + Chromium
npm install
npx playwright install chromium

# 3. Install the Claude Code skill
#    Requires a GitHub PAT exported as GH_TOKEN since the repo is private
export GH_TOKEN=ghp_yourPersonalAccessToken     # macOS / Linux
$env:GH_TOKEN = 'ghp_yourPersonalAccessToken'   # Windows PowerShell
npx skillfish add chi2tseng/stocks-in-play SIPs

# 4. Open Claude Code in this directory and run the skill
claude
# Then in Claude:
/SIPs
```

The skill orchestrates the whole pipeline (Barchart → catalysts → TradingView → Finviz → report → dashboard). Output lands in your local `dashboard/` directory; Claude Preview serves it at `http://127.0.0.1:5510`.

### Daily workflow (after first install)

```bash
# Pull latest scan from upstream (if author has pushed)
git pull

# OR run your own
/SIPs

# View the dashboard locally
open http://127.0.0.1:5510/   # or whatever your OS opens URLs with
```

---

## Methodology

The system applies Mark Minervini's **MAGNA53** template to Stockbee's **SIP** framework:

| Letter | Meaning | Source |
|---|---|---|
| **M**assive | EPS growth ≥100% OR Sales ≥100% OR EPS surprise ≥100% | TradingView FQ |
| **G**ap up | ≥4% gap on news/earnings day | Barchart pre+post |
| **N**eglect | Stock was quiet/under-bid before the move | Curated by Claude (see [DAY_RESETS_JUDGMENT.md](docs/DAY_RESETS_JUDGMENT.md)) |
| **A**cceleration | Sales accel ≥25% (latest qtr) | TradingView FQ |
| **5** | Short Interest >5 days to cover | Finviz `shortRatio` |
| **3** | ≥3 analyst price-target raises | Hand-curated |

- Full methodology: [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md)
- Day-1/2/3 reset judgment rules: [`docs/DAY_RESETS_JUDGMENT.md`](docs/DAY_RESETS_JUDGMENT.md)
- News publication time format: [`docs/NEWS_TIME_SPEC.md`](docs/NEWS_TIME_SPEC.md)
- Dashboard route reference: [`docs/DASHBOARD_PAGES.md`](docs/DASHBOARD_PAGES.md)

---

## Architecture

```
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ Playwright       │    │ Claude           │    │ Python           │
│  scrapers (×3)   │───►│  catalyst agent  │───►│  build_dashboard │
│ - Barchart       │    │ - WebSearch ×N   │    │ - merge JSON     │
│ - TradingView FQ │    │ - X cashtag      │    │ - write SPA      │
│ - Finviz         │    │ - synthesize 1   │    │                  │
└──────────────────┘    │   繁中 sentence  │    └──────────────────┘
        │               └──────────────────┘             │
        │                       │                        │
        ▼                       ▼                        ▼
   candidates.csv         catalysts_today.json    dashboard/data/<DATE>.json
   shorts.json            news_detail.json        dashboard/index.html
   <TICKER>-earnings-fq.md  claude_picks.json     dashboard/dates.json
   tv-summary.json         day_resets.json
```

Scripts:
- `barchart-scrape.js` — Playwright + XHR intercept on `/proxies/core-api/v1/quotes/get`
- `tv-scrape.js` — Playwright with `?earnings-period=FQ&revenues-period=FQ` URL trick, NASDAQ→NYSE→AMEX auto-detect
- `finviz-shorts.js` — Playwright with concurrency=2 + jitter to avoid Cloudflare
- `parse_tv.py` — extracts Reported + Estimate raw figures + YoY block from TradingView markdown
- `build_report.py` — merges candidates + tv-summary + catalysts → `final-candidates.csv`
- `build_dashboard.py` — assembles per-day JSON + writes the SPA

---

## Disclaimer

Educational + personal reference only. **Not investment advice.** Past patterns do not guarantee future results. Conduct your own due diligence and risk management.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Author

[@chi2tseng](https://github.com/chi2tseng) — built collaboratively with Claude Sonnet 4.5.
