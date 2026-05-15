# Methodology — MAGNA53 + Stockbee SIP

Two complementary frameworks power this scanner:
1. **Stockbee's SIP (Stocks In Play)** — news-driven daily setup (Pradeep Bonde, Nov 2022)
   📖 Source: <https://stockbee.io/sips/> (or search Twitter / Bluesky `@easyguru`)
2. **Mark Minervini's MAGNA53 template** — a 6-letter checklist for high-quality momentum setups

---

## Stockbee SIP — the news-driven daily setup

> Quant studies show **50% of stock moves are due to news**. Within that, **unscheduled news** has the biggest short-term impact — it surprises the market. — Stockbee

Two types of news:
- **Scheduled** — earnings, short interest, insider buys/sells. Released at fixed dates.
- **Unscheduled** — CEO change, new product, contract, FDA approval, shortage, M&A, influencer mention. Random timing.

**Both move stocks**, but **unscheduled news has bigger short-term impact** because it surprises the market. SIP is a setup that capitalizes on this.

### What constitutes a "valuable catalyst"

| Category | Examples | Notes |
|---|---|---|
| **Earnings** | Q1/Q2/Q3/Q4 EPS / revenue beats or misses | Second-biggest SIP opportunity after biotech (4× per year per ticker) |
| **Biotech catalysts** | FDA approval, drug trial readout, industry conference presentation | Biotech is the **biggest SIP opportunity**: ~150 +40% one-day moves per year. PDUFA calendar awareness required. |
| **Analyst** | PT changes — especially multiple firms on same day | Some firms (top tier) carry more weight |
| **M&A** | Mergers, acquisitions, LOIs | Especially when target's revenue scale ~doubles post-deal |
| **Contracts** | Major customer wins, government contracts, multi-year deals | "AI photonics signs $500M 5-year contract" type events |
| **Corporate actions** | Reverse split, special dividend, large buyback, share offering, ticker change | Discrete events with binary outcomes |
| **CEO change** | Resignation, replacement, activist-driven change | Signals structural shift |
| **Macro / sector** | New product launch, shortage, tariff, regulation | Sector-wide implications |

### What does NOT constitute a catalyst (filter out)

- ATM share issuance (dilution, ongoing)
- Insider sales (already priced)
- Stock split (1:N, not reverse) — cosmetic only
- "AI partnership MoU" with no $ figure attached — pure momentum
- "Strategic review" / "exploring alternatives" — vague
- Foreign issuer ADR resumes trading after compliance — micro-cap noise

---

## MAGNA53 — Minervini's 6-letter template

| Letter | Meaning | Test |
|---|---|---|
| **M**assive | Big growth shock | EPS growth ≥100% **OR** Sales ≥100% **OR** EPS surprise ≥100% **OR** 2 qtrs sales ≥29%. Scale must be meaningful (`10M→200M` ✓ vs `1¢→4¢` ✗). |
| **G**ap Up | Earnings-day gap | ≥4% gap, ≥100k pre/post-market volume |
| **N**eglect | One of 5 forms — see below | **Judgment-based, not algorithmic.** Set manually via `claude_picks.json.neglected` field. |
| **A**cceleration | Sales accel | Sales accel ≥25% **OR** 2 qtrs ≥29%. *EPS growth without sales growth is weaker.* |
| **5** | Short Interest | >5 days to cover (`shortRatio` from Finviz). Optional but fuels squeezes. |
| **3** | Analyst Upgrades | ≥3 price-target raises in last 30 days. Optional but fuels multi-day runners. |

### 5 forms of "Neglect"

1. **Financial neglect** — slow earnings growth turning into sudden acceleration
2. **Price neglect** — long sideways base, no recent run-up
3. **Volume neglect** — historically low liquidity, suddenly trading volume
4. **News neglect** — no major coverage in months/years, then sudden news cycle
5. **Ownership neglect** — <20-30 institutional holders; under-owned by smart money

---

## Setup classification (A / B / C / NULL)

A candidate qualifies as an SIP if **ANY** setup matches:

### Setup A — Growth Ignition (highest quality)
- Stock up ≥4%
- Volume ≥100k
- Sales growth ≥29% (latest qtr)
- Two quarters of sales growth ≥29%
- Annual sales ≥$25M
- Neglect present

### Setup B — Massive Earnings Shock
- ONE of: EPS growth ≥100% **OR** Sales growth ≥100% **OR** EPS surprise ≥100%
- PLUS: Sales growth ≥25% preferred (≥10% min)
- Neglect present

### Setup C — Analyst-Driven Move
- EPS surprise ≥100%
- Sales growth ≥10%
- Annual sales ≥$25M
- Neglect
- ≥3 analyst PT raises (often multi-day runners)

### NULL — no clean setup → drop from final ranking

---

## Entry rules

| Style | Trigger | Stop | Risk |
|---|---|---|---|
| **Aggressive** | After-hours fill | tight | Best price, highest risk (overnight gap risk) |
| **Semi-aggressive** | Pre-market fill | 3% | Early entry, many fades |
| **Standard** | At market open | **2.5%** | Default for most SIPs |
| **Conservative** | Wait 15 min after open | 2% | Lower risk, may miss spike |

### Trailing stops

| Stage of move | Trailing stop |
|---|---|
| Initial move (first 30 min) | $1 trailing (or 5% for cheaper stocks) |
| Mid move (extending) | $0.40 trailing |
| Later move (consolidating) | $0.20 trailing |

**Default mindset:** day-trade first. Upgrade to multi-day only if strong story + huge sales acceleration + institutional accumulation.

---

## Universal YoY formula

For all YoY calculations (earnings, revenue, EPS), use:

```python
yoy_pct = (curr - prior) / abs(prior) * 100
```

This handles all sign combinations correctly:
- both positive: standard growth %
- both negative (loss widening/narrowing): negative % = loss widened, positive % = loss narrowed
- negative → positive (turnaround): massive positive %, often >100%
- positive → negative (collapse): massive negative %

The old `(curr/prior - 1) * 100` formula blanks out half the cases. **Always use the universal formula.**

---

## References

- [Stockbee SIP commentary](https://stockbee.io/sips/) — original 7-page Twitter thread by Pradeep Bonde (Nov 2022). Not shipped in repo to respect copyright.
- [`./DAY_RESETS_JUDGMENT.md`](./DAY_RESETS_JUDGMENT.md) — day-1/2/3 reset judgment rules
- [`./NEWS_TIME_SPEC.md`](./NEWS_TIME_SPEC.md) — how to source real news publication times
- [`./DASHBOARD_PAGES.md`](./DASHBOARD_PAGES.md) — SPA route + JSON data contracts
- [Mark Minervini's books](https://www.minervini.com/) — "Trade Like a Stock Market Wizard", "Think & Trade Like a Champion" cover the MAGNA template in depth.

---

## Disclaimer

This methodology and any associated `claude_picks.json` / `news_detail.json` data is for **educational and personal reference only**. Not investment advice. Past patterns do not guarantee future results. Conduct your own due diligence and risk management.
