#!/usr/bin/env python3
# ABOUTME: Pre-flight checks before fetching option chains for income plan.
# ABOUTME: Returns earnings risks, per-stock trends, position sizing budget, and existing options.

import argparse
import json
import sys
from datetime import datetime, timedelta

from trading_skills.earnings import get_earnings_info
from trading_skills.scanner_bullish import compute_bullish_score


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
    """Compute per-stock trend classification."""
    results = {}
    for sym in symbols:
        try:
            data = compute_bullish_score(sym)
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

    # 1. Earnings check
    print("  Checking earnings dates...", file=sys.stderr)
    earnings = check_earnings(all_symbols)

    # 2. Per-stock trend analysis
    print("  Computing per-stock trends...", file=sys.stderr)
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
