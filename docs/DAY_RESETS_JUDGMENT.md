# Day-Reset Judgment Rules

This doc captures the **judgment-based** rules for deciding whether a candidate gets `day1` (new major catalyst, fresh opportunity) vs `day2` / `day3` (continuation of an older move) on the Stocks In Play dashboard.

**Why this exists:** the original `dayLabel()` logic just counted scan-day appearances (in-scan today only → `day1`; in scan yesterday + today → `day2`; etc.). That's wrong when a stock had unrelated pre-earnings momentum on day -1 and -2 then released real earnings on day -1 evening — the earnings reaction should still count as `day1`.

The fix: `dayResets` map in each per-day JSON, populated from a hand-curated `day_resets.json` at repo root. The dashboard's `dayLabelWithReset()` honors this override.

---

## Process (per ticker, each /SIPs run)

1. **Identify today's catalyst** from `catalysts_today.json` + `news_detail.json`
2. **Look at prior-scan presence + |chgPct|** in last 1-3 scan-days
3. **Look at 1M / 3M perf** for cumulative price trend
4. **Ask**: are the prior moves **same driver** as today's catalyst (= continuation / leak / anticipation), or **unrelated** (= today's catalyst is genuinely new to the market)?
   - Same driver → leave at `day3` (don't add to resets)
   - Unrelated → add to `resets` so badge resets to `day1`

---

## Soft signals (worth examining, NOT auto-disqualifying)

| Signal | What to consider |
|---|---|
| Prior-scan day `\|chgPct\| ≥ 4%` | Was that move a **leak** of today's catalyst (e.g. earnings whispers running price up)? Or **unrelated** (e.g. crypto/IPO momentum on a name that happens to report earnings the next day)? |
| `1M cumulative > +100%` | Likely already running. But check: was the run-up on the SAME theme (= continuation, no reset) or different drivers (e.g. analyst upgrade earlier, earnings now = potentially fresh reset)? |
| Catalyst published `≥ 2 trading days ago` | Usually means today's price action is delayed / technical continuation, not fresh reset |

**Earlier draft used a hard 8% prior-scan threshold. That's wrong** — the user's actual rule is judgment: prior 4%+ is a *signal* to investigate, not an auto-disqualifier.

---

## Special cases that DO reset to `day1`

- **Reverse splits / corporate actions** (special dividend, large buyback, share offering announcement, ticker change) → `day1` even if prior 1M had small drift up. The corporate action itself is a discrete catalyst.
- **Biotech FDA / PDUFA approvals** → `day1` on announcement day even if biotech has been speculative running into the date. The binary event resolves; market reaction is fresh.
- **First earnings print as a public company** → `day1` even if IPO momentum already ran the stock — earnings is the first time fundamental data hits the tape.
- **CEO change / activist investor stake disclosed** → `day1` even with prior momentum, as the structural change is novel info.

---

## Special cases that do NOT reset (stay `day3` / `day2`)

- **Old catalyst with technical follow-through** — e.g. earnings published 3-7 days ago, stock still drifting on the theme. No reset.
- **Pump-and-dump unwind** — e.g. AI-related meme up +800% in 1M; today's "new contract" headline is just the trigger for the unwind, not fresh news. No reset.
- **Same-driver continuation** — e.g. a contract was announced in pre-market 2 days ago, stock spiked +22%, today is the day-2 momentum continuation. No reset.

---

## Worked examples (from 2026-05-15 scan)

### ✅ Reset to `day1`

| Ticker | Today | Prior | Why reset |
|---|---|---|---|
| **FIG** | +11.66% on Q1 +46% YoY earnings beat | 5/13 +4.5% / 5/14 +4.5% / 1M -0.5% | Prior +4.5% was unrelated pre-earnings noise (small bumps, not leak); today is the actual earnings reaction. **Fresh.** |
| **BOOT** | +7.95% on Q4 +19% YoY + FY27 guide raise | first time in scan / 1M -7.3% | First time in scan + flat-to-down 1M = no prior run. **Fresh.** |
| **BNKK** | +5.05% on Q1 +10,200% YoY first earnings as public co. | 5/13 +16.4% / 5/14 +16.4% / 1M -18.7% | Prior +16% was IPO/crypto-meme momentum, **different driver** from today's earnings print. First-ever earnings report → fresh data to market. **Fresh.** |
| **ELPW** | +7.73% on reverse-split announcement | 1M +7.8% / no prior scan | Corporate action = discrete catalyst per special-cases rule. **Fresh.** |

### ❌ No reset (stay `day3`)

| Ticker | Today | Prior | Why no reset |
|---|---|---|---|
| **AIIO** | -20.74% on M&A pump unwind | 5/13 +64.8% / 5/14 +64.8% / 1M +810% | Same AI/M&A theme already pump-and-dumping; today's M&A "news" is fulfillment + sell-the-news unwind, not new. **Continuation.** |
| **POET** | +11.28% on Lumilens contract | 5/13 +22.1% / 5/14 +22.1% (= catalyst day) / 1M +195% | Contract was announced 5/14 pre-market — 5/14 +22% IS the catalyst day. Today +11% is day-2 momentum on the same news. **Continuation.** |
| **AEHL** | -15.67% on Bitcoin Plan distribution | 5/13 +49% / 5/14 +49% / 1M +552% | $200M shelf was announced 5/11; subsequent days were continuation of the same Bitcoin Plan theme. Today's drop is distribution unwind. **Continuation.** |

---

## Schema

`./day_resets.json` lives at repo root:

```json
{
  "resets": {
    "TICKER": "one-line reason explaining why this is day1 (catalyst type + prior context)"
  },
  "_no_reset_reasons": {
    "TICKER": "one-line reason explaining why this stays day3 despite appearing fresh"
  }
}
```

`build_dashboard.py` reads `resets` and emits `data.dayResets` in the per-day JSON. The dashboard JS:

```js
function dayLabelWithReset(sym, firstSeenMap, currentIso) {
  if (DATA?.dayResets && Object.prototype.hasOwnProperty.call(DATA.dayResets, sym)) return 'day1';
  return dayLabel(firstSeenMap.get(sym), currentIso);
}
```

---

## When in doubt

**Default to NO reset.** A false-negative (showing `day3` for a true fresh catalyst) costs a moment of attention. A false-positive (showing `day1` for a continuation move) over-credits the candidate and may trigger an over-sized entry. Conservative bias is correct.
