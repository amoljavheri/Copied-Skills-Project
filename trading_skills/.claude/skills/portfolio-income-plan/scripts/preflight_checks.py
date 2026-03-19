#!/usr/bin/env python3
# ABOUTME: Pre-flight checks before fetching option chains for income plan.
# ABOUTME: Returns earnings risks, per-stock trends, position sizing budget, and existing options.
# ABOUTME: Includes market regime check (QQQ vs SMA200) and VXN volatility regime for CSP delta scaling.

import argparse
import json
import sys
from datetime import datetime, timedelta

import yfinance as yf

from trading_skills.earnings import get_earnings_info
from trading_skills.scanner_bullish import compute_bullish_score
from trading_skills.technicals import compute_raw_indicators


def classify_trend(score: float) -> str:
    """Map bullish score (0-8) to trend class."""
    if score >= 6.0:
        return "strong_bull"
    elif score >= 4.0:
        return "bull"
    elif score >= 2.0:
        return "neutral"
    elif score >= 1.0:
        return "bear"
    else:
        return "strong_bear"


def check_market_regime() -> dict:
    """Check top-down market regime using QQQ vs SMA200 and VXN volatility level.

    Backtest evidence (3-year QQQ CSP study):
      - QQQ > SMA200 (bull): assignment rate 13.2%
      - QQQ < SMA200 (bear): assignment rate 30.0%  ← 2.3× worse
      - VXN > 25: strikes further OTM but assignment clusters triple in frequency

    Returns recommended CSP delta adjustment to apply on top of per-stock trend class.
    """
    result = {
        "qqq_price": None,
        "qqq_sma200": None,
        "qqq_above_sma200": None,
        "vxn": None,
        "market_regime": "unknown",
        "csp_delta_adjustment": "none",
        "csp_recommendation": "",
        "warning": None,
    }
    try:
        # QQQ vs 200MA
        qqq = yf.Ticker("QQQ")
        df = qqq.history(period="12mo")
        if not df.empty and len(df) >= 200:
            raw = compute_raw_indicators(df)
            qqq_price = float(df["Close"].iloc[-1])
            sma200 = raw.get("sma200")
            result["qqq_price"] = round(qqq_price, 2)
            if sma200 is not None:
                result["qqq_sma200"] = round(sma200, 2)
                above = qqq_price > sma200
                result["qqq_above_sma200"] = above
                pct = ((qqq_price - sma200) / sma200) * 100
                if above:
                    result["market_regime"] = "bull"
                    result["csp_recommendation"] = (
                        f"QQQ {pct:+.1f}% above SMA200 — bull market. "
                        "Use standard delta targets per stock trend."
                    )
                else:
                    result["market_regime"] = "bear"
                    result["csp_delta_adjustment"] = "reduce_one_tier"
                    result["warning"] = (
                        f"⚠️ QQQ {pct:+.1f}% BELOW SMA200 — BEAR MARKET. "
                        "CSP assignment risk is 2.3× higher than normal. "
                        "Reduce delta by one tier (e.g. 0.20→0.15, 0.15→0.10). "
                        "Consider skipping new CSPs on weak/bear-trend stocks entirely."
                    )
                    result["csp_recommendation"] = result["warning"]

        # VXN volatility regime
        vxn = yf.Ticker("^VXN")
        vxn_df = vxn.history(period="5d")
        if not vxn_df.empty:
            vxn_val = float(vxn_df["Close"].iloc[-1])
            result["vxn"] = round(vxn_val, 1)
            if vxn_val >= 35:
                vxn_warning = (
                    f"⚠️⚠️ VXN={vxn_val:.0f} — EXTREME VOLATILITY (≥35). "
                    "Skip ALL new CSPs. Wait for VXN to fall below 30."
                )
                result["vxn_regime"] = "extreme"
                result["vxn_warning"] = vxn_warning
                if result["warning"]:
                    result["warning"] += " | " + vxn_warning
                else:
                    result["warning"] = vxn_warning
            elif vxn_val >= 25:
                vxn_warning = (
                    f"⚠️ VXN={vxn_val:.0f} — HIGH VOLATILITY (25–35). "
                    "Reduce delta one tier further. Use half-size positions."
                )
                result["vxn_regime"] = "high"
                result["vxn_warning"] = vxn_warning
                if result["warning"]:
                    result["warning"] += " | " + vxn_warning
                else:
                    result["warning"] = vxn_warning
            else:
                result["vxn_regime"] = "normal"
                result["vxn_warning"] = None

    except Exception as e:
        result["error"] = str(e)

    return result


def check_earnings(symbols: list[str]) -> dict:
    """Check earnings dates for each symbol and classify risk."""
    today = datetime.now().date()
    results = {}

    for sym in symbols:
        try:
            info = get_earnings_info(sym)
            date_str = info.get("earnings_date")
            if not date_str:
                results[sym] = {"date": None, "risk": "UNKNOWN", "days_away": None}
                continue

            earn_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            days_away = (earn_date - today).days

            if days_away <= 0:
                risk = "PAST"
            elif days_away <= 7:
                risk = "BLOCK"  # Do NOT sell any options
            elif days_away <= 14:
                risk = "BLOCK"  # Do NOT sell options spanning this date
            elif days_away <= 21:
                risk = "SHORT_DTE_ONLY"  # Only sell options expiring BEFORE earnings
            else:
                risk = "SAFE"

            # Calculate the last safe expiry date
            safe_expiry = None
            if risk in ("BLOCK", "SHORT_DTE_ONLY"):
                # Last safe expiry is 3-5 business days before earnings
                buffer_days = 5 if days_away <= 14 else 3
                safe_expiry = (earn_date - timedelta(days=buffer_days)).isoformat()

            results[sym] = {
                "date": date_str,
                "timing": info.get("timing"),
                "days_away": days_away,
                "risk": risk,
                "safe_expiry_before": safe_expiry,
            }
        except Exception as e:
            results[sym] = {"date": None, "risk": "ERROR", "error": str(e)}

    return results


def check_trends(symbols: list[str]) -> dict:
    """Compute per-stock trend classification using 12-month data for SMA200."""
    results = {}
    for sym in symbols:
        try:
            data = compute_bullish_score(sym, period="12mo")
            if data:
                score = data.get("score", 0)
                results[sym] = {
                    "score": round(score, 1),
                    "class": classify_trend(score),
                    "signals": data.get("signals", []),
                }
            else:
                results[sym] = {"score": 0.0, "class": "neutral", "signals": []}
        except Exception as e:
            results[sym] = {"score": 0.0, "class": "neutral", "error": str(e)}
    return results


def compute_budget(cash_available: float, buffer: float = 5000.0) -> dict:
    """Compute CSP position sizing budget."""
    usable = max(0, cash_available - buffer)
    return {
        "cash_available": round(cash_available, 2),
        "buffer": round(buffer, 2),
        "usable_cash": round(usable, 2),
        "max_per_csp": round(usable * 0.20, 2),    # 20% max per position
        "max_total_csp": round(usable * 0.50, 2),   # 50% max total exposure
    }


def extract_existing_options(option_positions: list[dict]) -> dict:
    """Build a map of existing options by underlying symbol."""
    result: dict[str, list[dict]] = {}
    for opt in option_positions:
        underlying = opt.get("underlying", "")
        if not underlying:
            continue
        if underlying not in result:
            result[underlying] = []
        result[underlying].append({
            "type": opt.get("option_type"),
            "strike": opt.get("strike"),
            "expiry": opt.get("expiry"),
            "quantity": opt.get("quantity"),
        })
    return result


def run_preflight(portfolio_data: dict) -> dict:
    """Run all pre-flight checks on parsed portfolio data."""
    # Collect all unique symbols
    stock_symbols = [s["symbol"] for s in portfolio_data.get("stock_positions", [])]
    option_underlyings = list({
        o["underlying"] for o in portfolio_data.get("option_positions", [])
    })
    all_symbols = sorted(set(stock_symbols + option_underlyings))

    print(f"Running preflight for {len(all_symbols)} symbols...", file=sys.stderr)

    # 0. Market regime check (top-down filter — must run first)
    print("  Checking market regime (QQQ SMA200 + VXN)...", file=sys.stderr)
    market_regime = check_market_regime()

    # 1. Earnings check
    print("  Checking earnings dates...", file=sys.stderr)
    earnings = check_earnings(all_symbols)

    # 2. Per-stock trend analysis (uses 12mo data for SMA200)
    print("  Computing per-stock trends (12mo / SMA200)...", file=sys.stderr)
    trends = check_trends(stock_symbols)  # Only stocks, not option-only positions

    # 3. Position sizing budget
    cash = portfolio_data.get("cash_available", 0)
    budget = compute_budget(cash)

    # 4. Existing options map
    existing = extract_existing_options(portfolio_data.get("option_positions", []))

    # 5. CC-eligible stocks (100+ shares)
    cc_eligible = [
        s["symbol"] for s in portfolio_data.get("stock_positions", [])
        if s.get("quantity", 0) >= 100
    ]

    return {
        "market_regime": market_regime,
        "earnings": earnings,
        "trends": trends,
        "budget": budget,
        "existing_options": existing,
        "cc_eligible": sorted(cc_eligible),
        "total_stocks": len(stock_symbols),
        "total_symbols_checked": len(all_symbols),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Pre-flight checks for portfolio income plan"
    )
    parser.add_argument("--file", help="Path to parse_etrade.py JSON output file")
    parser.add_argument("--buffer", type=float, default=5000.0,
                        help="Cash buffer to keep (default: $5,000)")
    args = parser.parse_args()

    # Read portfolio JSON from file or stdin
    if args.file:
        with open(args.file) as f:
            portfolio_data = json.load(f)
    else:
        portfolio_data = json.load(sys.stdin)

    result = run_preflight(portfolio_data)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
