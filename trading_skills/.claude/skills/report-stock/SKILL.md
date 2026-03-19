---
name: report-stock
description: >
  Generate a comprehensive stock analysis report (PDF or markdown) with full technical analysis,
  fundamentals, REAL live option chain data (via Tradier MCP), LEAP call scenarios with actual
  bid/ask prices, cash secured put (CSP) analysis with real premiums and greeks, PMCC viability,
  option spread strategies, and an overall 1-10 bullish conviction score.
  Use this skill whenever the user asks for a full stock report, deep-dive analysis, or wants to
  know if a stock is a good candidate for options strategies like LEAPs, CSP, or PMCC.
  Trigger on phrases like: "run report-stock on X", "give me a full stock report for X",
  "analyze X completely", "stock analysis report for X", "is X a good LEAP candidate",
  "deep dive on X", "full analysis of X", "comprehensive report on X", "should I buy LEAPs on X",
  "is X good for cash secured puts", "CSP analysis for X", "PMCC analysis for X",
  "find CSP candidates", "find PMCC candidates", "options analysis for X",
  or any request for thorough/complete analysis of a stock.
user_invocable: true
arguments:
  - name: symbols
    description: Stock ticker symbol(s) — single or space-separated list (e.g., AAPL or "AAPL MSFT GOOGL")
    required: true
dependencies: ["trading-skills"]
---

# Stock Analysis Report Generator

Generates professional, comprehensive reports covering trend analysis, fundamentals, PMCC viability,
LEAP call scenarios with **real Tradier option prices**, Cash Secured Put (CSP) analysis with
**actual bid/ask premiums and live greeks**, option spread strategies, and an overall 1-10 bullish
conviction score. Supports PDF and markdown output formats.

## Data Sources

| Data | Source |
|------|--------|
| Technical analysis (RSI, MACD, ADX, SMAs, bullish score) | `scripts/report.py` |
| Fundamentals (P/E, Piotroski, earnings history) | `scripts/report.py` |
| PMCC viability & spread strategies | `scripts/report.py` |
| **Live stock quote (price, bid, ask)** | **Tradier MCP → `get_market_quotes`** |
| **Real option chain (IV, delta, theta, bid/ask)** | **Tradier MCP → `get_options_chain`** |
| **Available expiry dates** | **Tradier MCP → `get_option_expirations`** |

---

## Instructions

### Step 1: Gather Technical & Fundamental Data

Run the report script for each symbol:

```bash
uv run python scripts/report.py SYMBOL
```

Returns JSON with:
- `recommendation` — overall recommendation with strengths/risks
- `company` — name, sector, industry, market cap, beta
- `trend_analysis` — bullish score, RSI, MACD, ADX, SMA20/50, signals, next earnings
- `pmcc_analysis` — PMCC score, IV%, LEAPS/short details, trade metrics
- `fundamentals` — valuation, profitability, dividend, balance sheet, earnings history
- `piotroski` — F-Score with all 9 criteria
- `spread_strategies` — bull call, bear put, straddle, strangle, iron condor

---

### Step 1.5: Fetch Real Option Chain Data (Tradier MCP)

Use Tradier MCP tools to get **live option prices, greeks, and IV**. This is the key upgrade —
real market data replaces formula estimates for all options analysis sections.

#### A. Live Stock Quote
```
get_market_quotes(symbols="SYMBOL")
```
Use the returned `last` price as the definitive current price for all calculations.

#### B. Find Target Expiry Dates
```
get_option_expirations(symbol="SYMBOL")
```
From the returned list, select:
- **CSP/Spread expiry**: the date closest to **30–45 DTE** from today
- **LEAPS expiry**: the date closest to **250–400 DTE** (prefer Jan LEAPS if available)

#### C. Fetch Near-Term Option Chain (for CSP, Spreads, and Stock IV)
```
get_options_chain(symbol="SYMBOL", expiration="CSP-EXPIRY-DATE", greeks=true)
```

From the **PUTS** side of the chain, find and extract the following 3 strikes:
- **Conservative put**: strike nearest to `current_price × 0.90` (~10% OTM)
- **Balanced put**: strike nearest to `current_price × 0.95` (~5% OTM)
- **Aggressive put**: strike nearest to `current_price × 0.98` (~2% OTM)

For each put record, extract:
| Field | Description |
|-------|-------------|
| `strike` | Strike price |
| `bid` | Real bid price |
| `ask` | Real ask price |
| `mid` | `(bid + ask) / 2` — use this as premium |
| `greeks.delta` | Real delta (will be negative for puts, use absolute value) |
| `greeks.mid_iv` | Implied volatility (e.g., 0.32 = 32%) |
| `open_interest` | Liquidity indicator |
| `volume` | Daily volume |

**Extract stock IV**: From the **CALL** side, find the ATM call (strike closest to current price).
Use its `greeks.mid_iv` as the stock's current implied volatility for all probability calculations.

#### D. Fetch LEAPS Option Chain (for LEAP Scenarios and PMCC)
```
get_options_chain(symbol="SYMBOL", expiration="LEAPS-EXPIRY-DATE", greeks=true)
```

From the **CALLS** side, find the strike with `greeks.delta` closest to **0.80** (deep ITM):
- Typically strike = 70–80% of current price
- Extract: `strike`, `bid`, `ask`, `mid`, `greeks.delta`, `greeks.mid_iv`, `greeks.theta`

**Fallback**: If Tradier returns no data or throws an error, fall back to estimates from
`pmcc_analysis` in the report.py output, clearly labeling them as "Estimated".

---

### Step 2: Compute Analyses Using Real Data

With both the report.py JSON (Step 1) and Tradier real option data (Step 1.5), compute:

#### A. Overall Bullish Score (1–10)

| Component | Max | Criteria |
|-----------|-----|----------|
| Trend (bullish score from report.py) | 3 | ≥6→3pts, ≥4→2pts, ≥2→1pt, <2→0pts |
| ADX strength | 1 | ADX ≥25 AND positive trend → 1pt |
| RSI zone | 1 | 50–70 → 1pt, 30–50 → 0.5pt, >70 or <30 → 0pt |
| Piotroski F-Score | 1 | ≥7→1pt, 4–6→0.5pt, <4→0pt |
| Fundamentals (Fwd P/E) | 1 | <15→1pt, 15–25→0.5pt, >25→0pt |
| PMCC viability score | 1 | ≥9→1pt, 7–8→0.75pt, 5–6→0.5pt, <5→0pt |
| Analyst sentiment | 1 | Majority buy→1pt, hold→0.5pt, sell→0pt |
| News/momentum | 1 | Positive catalysts→1pt, negative→0pt |

**Scale**: 1–3 = 🔴 Bearish, 4–5 = 🟡 Neutral, 6–7 = 🟢 Moderately Bullish, 8–9 = 🚀 Strong Bull, 10 = ⚡ Exceptional

#### B. LEAP Call Scenarios (Real Tradier Data)

Using the actual LEAPS call from Step 1.5D:

| Variable | Source |
|----------|--------|
| `leaps_cost` | `mid` from Tradier call chain |
| `delta` | `greeks.delta` from Tradier |
| `iv` | `greeks.mid_iv` from Tradier |
| `monthly_theta` | `abs(greeks.theta) × 30` |

For 6 scenarios (stock −10%, flat 0%, +5%, +10%, +20%, +30%):
```
price_change = current_price × move_pct
leaps_new_value = leaps_cost
                + (delta × price_change)
                + (0.5 × gamma × price_change²)    ← use gamma if available, else skip
                − monthly_theta
return_pct = (leaps_new_value − leaps_cost) / leaps_cost × 100
```

Also compute:
- **Break-even move**: `monthly_theta / delta / current_price × 100` (% stock must rise to offset theta)
- **Prob. of +30% gain in 1 month**:
  - Required stock move: `((leaps_cost × 1.30 − leaps_cost) + monthly_theta) / delta`
  - `z = required_move / (current_price × iv × sqrt(30/365))`
  - `prob = (1 − N(z)) × 100` where N is standard normal CDF

Label the section with: `📊 Source: Tradier live option chain — real prices`

#### C. Cash Secured Put (CSP) Analysis (Real Tradier Data)

Using actual put data from Step 1.5C. For each of the 3 tiers:

```
mid_premium   = (bid + ask) / 2        ← from Tradier
delta_abs     = abs(greeks.delta)      ← from Tradier
iv_pct        = greeks.mid_iv × 100   ← from Tradier
ann_yield_pct = (mid_premium / strike) × (365 / DTE) × 100
prob_profit   = (1 − delta_abs) × 100
capital_req   = strike × 100          ← per contract
```

**CSP Suitability Rating**:
- ✅ **Good**: IV > 25% AND stock bullish score ≥ 5 AND no earnings within 30 days
- ⚠️ **Caution**: IV 15–25% OR ADX < 20 (no clear trend) OR earnings within 30 days
- ❌ **Avoid**: IV < 15% OR stock in strong downtrend (bullish score < 2) OR earnings within 14 days

**Assignment scenario**: `cost_basis = strike − mid_premium`
**Best follow-up if assigned**: Sell covered calls (wheel strategy)

Label the section with: `📊 Source: Tradier live option chain — real bid/ask`

---

### Step 3: Generate Report

Choose output format based on user preference:

**Markdown** (default): Read `templates/markdown-template.md` for full formatting instructions.
Save to `sandbox/` with filename: `{SYMBOL}_Analysis_Report_{YYYY-MM-DD}_{HHmm}.md`

**PDF**: Use the `pdf` skill and read `templates/pdf-template.md`.
Save to `sandbox/` with filename: `{SYMBOL}_Analysis_Report_{YYYY-MM-DD}_{HHmm}.pdf`

---

### Step 4: Report Results to User

After generating, tell the user:
1. **Overall Bullish Score** (X/10) with one-line verdict
2. **Top trade setup** — best options strategy given conditions (CSP / LEAP / PMCC / Spread)
3. **Key risk to watch**
4. **File path** of the saved report

---

## Full Report Sections

| # | Section | Key Data |
|---|---------|----------|
| 1 | Executive Summary | Score, recommendation, company overview |
| 2 | Technical Analysis | RSI, MACD, ADX, SMA20/50, trend signals, earnings date |
| 3 | Fundamental Analysis | Valuation, profitability, balance sheet, earnings history |
| 4 | Piotroski F-Score | All 9 criteria pass/fail |
| 5 | Overall Bullish Score | 8-component scoring table |
| 6 | LEAP Call Scenarios | **Real prices** from Tradier, scenario table, break-even, probability |
| 7 | Cash Secured Put (CSP) | **Real bid/ask** from Tradier, 3-tier strikes, yields, suitability |
| 8 | PMCC Viability | Score, LEAPS/short details, trade metrics |
| 9 | Option Spread Strategies | Bull call, bear put, straddle, strangle, iron condor |
| 10 | Investment Summary | Strengths, risks, disclaimer |

---

## Example Usage

```bash
# Single symbol — full report
uv run python scripts/report.py AAPL
# Then call Tradier MCP tools for real option data
# Then generate markdown report to sandbox/

# Multiple symbols — run separately
uv run python scripts/report.py NVDA
uv run python scripts/report.py MSTR
```

---

## Dependencies

This skill aggregates data from:
- `scanner-bullish` → RSI, MACD, ADX, SMA trend analysis
- `scanner-pmcc` → PMCC viability score, spread strategies
- `fundamentals` → financial ratios, Piotroski, earnings history
- **Tradier MCP** → real-time option chain, live greeks, IV, bid/ask prices
