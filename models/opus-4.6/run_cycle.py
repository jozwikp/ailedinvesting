#!/usr/bin/env python3
"""Run one Opus 4.6 investment decision cycle.

Usage:
    python3 run_cycle.py                         # Full cycle, reads current_portfolio.md
    python3 run_cycle.py --dry-run               # Print decisions without writing files
    python3 run_cycle.py --cash 850              # Override cash balance
    python3 run_cycle.py --cycle-number 3        # Set cycle number explicitly
    python3 run_cycle.py --positions '[...]'     # Override positions as JSON
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent

# Ensure local imports work
sys.path.insert(0, str(BASE))

from config import STRATEGY, UNIVERSE
from market_data import fetch_fx_rates, fetch_all_data, build_snapshots
from scoring import rank_candidates
from decision_engine import build_decisions, Position, PortfolioState
from state_io import (
    load_portfolio,
    write_portfolio,
    append_reasoning,
    append_transactions,
    write_decisions_json,
    update_symbol_map,
)


def _detect_cycle_number(reasoning_path: Path) -> int:
    """Detect next cycle number from reasoning.md."""
    if not reasoning_path.exists():
        return 1
    text = reasoning_path.read_text(encoding="utf-8")
    cycles = [int(m) for m in __import__("re").findall(r"## Cycle (\d+)", text)]
    return max(cycles, default=0) + 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Opus 4.6 decision cycle")
    parser.add_argument("--cash", type=float, help="Override cash PLN")
    parser.add_argument("--positions", type=str, help="Override positions as JSON array")
    parser.add_argument("--cycle-number", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true", help="Print decisions without writing files")
    args = parser.parse_args()

    print("=" * 60)
    print("  OPUS 4.6 — Investment Decision Cycle")
    print("=" * 60)

    # 1. Load current portfolio state
    print("\n[1/6] Loading portfolio state...")
    portfolio = load_portfolio(BASE / "current_portfolio.md")
    if args.cash is not None:
        portfolio.cash_pln = args.cash
        portfolio.total_value_pln = args.cash + sum(
            p.avg_entry_price * p.quantity for p in portfolio.positions
        )
    if args.positions:
        pos_data = json.loads(args.positions)
        portfolio.positions = [
            Position(
                ticker=p["ticker"],
                quantity=p["quantity"],
                avg_entry_price=p["avg_entry_price"],
                quote_currency=p.get("quote_currency", "USD"),
                asset_class=p.get("asset_class", "stock"),
            )
            for p in pos_data
        ]
    print(f"    Cash: {portfolio.cash_pln:.2f} PLN")
    print(f"    Positions: {len(portfolio.positions)}")
    print(f"    Total value: {portfolio.total_value_pln:.2f} PLN")

    # 2. Update symbol map
    print("\n[2/6] Updating symbol map...")
    update_symbol_map(BASE / "symbol_map.csv", UNIVERSE)
    print(f"    {len(UNIVERSE)} instruments mapped.")

    # 3. Fetch market data
    print("\n[3/6] Fetching market data (this may take a moment)...")
    fx_rates = fetch_fx_rates()
    print(f"    FX rates: USD/PLN={fx_rates.get('USD', '?'):.4f}, EUR/PLN={fx_rates.get('EUR', '?'):.4f}")

    raw_data = fetch_all_data(UNIVERSE, period=STRATEGY["history_period"])
    print(f"    Fetched data for {len(raw_data)} instruments.")

    snapshots = build_snapshots(UNIVERSE, fx_rates, raw_data)
    print(f"    Built {len(snapshots)} instrument snapshots.")

    # 4. Score and rank
    print("\n[4/6] Scoring and ranking instruments...")
    ranked = rank_candidates(snapshots, STRATEGY)
    print(f"    Ranked {len(ranked)} instruments.")
    if ranked:
        print("    Top 5:")
        for i, rc in enumerate(ranked[:5], 1):
            s = rc.snapshot
            print(
                f"      {i}. {s.xtb_ticker:15s} score={rc.score:+.4f}  "
                f"mom20d={s.momentum_20d:+.1%}  RSI={s.rsi_14:.0f}  "
                f"price={s.price:.2f} {s.quote_currency}"
            )

    # 5. Generate decisions
    print("\n[5/6] Generating decisions...")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cycle_num = args.cycle_number or _detect_cycle_number(BASE / "reasoning.md")

    decisions, rejected, notes = build_decisions(
        timestamp, portfolio, ranked, fx_rates, STRATEGY
    )

    print(f"\n{'=' * 60}")
    print(f"  CYCLE {cycle_num} DECISIONS — {timestamp}")
    print(f"{'=' * 60}")

    output = [d.to_dict() for d in decisions]
    print(json.dumps(output, indent=2))

    if notes:
        print("\nNotes:")
        for n in notes:
            print(f"  - {n}")
    if rejected:
        print("\nRejected alternatives:")
        for r in rejected[:5]:
            print(f"  - {r}")

    # 6. Write files (unless dry-run)
    if args.dry_run:
        print("\n[6/6] DRY RUN — no files written.")
    else:
        print("\n[6/6] Writing state files...")
        latest_prices = {
            s.xtb_ticker: (s.price, s.quote_currency, s.fx_to_pln)
            for s in snapshots
        }
        write_portfolio(
            BASE / "current_portfolio.md",
            portfolio, latest_prices, fx_rates, cycle_num, timestamp,
        )
        append_reasoning(
            BASE / "reasoning.md",
            cycle_num, timestamp, portfolio, ranked,
            decisions, rejected, notes,
        )
        append_transactions(
            BASE / "transactions.md",
            cycle_num, timestamp, decisions,
        )
        write_decisions_json(BASE / "latest_decisions.json", decisions)
        print("    Done. Files updated:")
        print("      - current_portfolio.md")
        print("      - reasoning.md")
        print("      - transactions.md")
        print("      - latest_decisions.json")

    print(f"\n{'=' * 60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
