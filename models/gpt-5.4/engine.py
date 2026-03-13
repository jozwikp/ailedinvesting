from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from decision_logic import build_decisions, rank_candidates
from market_data import MarketDataError, YahooFinanceClient, active_mappings, load_symbol_map
from state_io import (
    append_reasoning,
    append_transactions,
    load_portfolio_from_cycle_input,
    parse_cycle_input,
    write_current_portfolio,
    write_decisions_json,
)


def parse_args() -> argparse.Namespace:
    base_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Run one GPT-5.4 investment decision cycle.")
    parser.add_argument("--input-file", required=True, help="Path to the cycle input markdown file.")
    parser.add_argument("--symbol-map", default=str(base_dir / "symbol_map.csv"), help="Path to symbol_map.csv.")
    parser.add_argument("--reasoning-log", default=str(base_dir / "reasoning.md"), help="Path to reasoning.md.")
    parser.add_argument(
        "--transactions-log",
        default=str(base_dir / "transactions.md"),
        help="Path to transactions.md.",
    )
    parser.add_argument(
        "--portfolio-file",
        default=str(base_dir / "current_portfolio.md"),
        help="Path to current_portfolio.md.",
    )
    parser.add_argument(
        "--decisions-out",
        default=str(base_dir / "latest_decisions.json"),
        help="Where to write the structured decision JSON.",
    )
    parser.add_argument(
        "--history-size",
        type=int,
        default=60,
        help="Number of daily bars to request from Yahoo Finance for ranking.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cycle_timestamp, _cash_pln, _positions, _execution_updates, _statement_source = parse_cycle_input(args.input_file)
    portfolio = load_portfolio_from_cycle_input(args.input_file)
    mappings = active_mappings(load_symbol_map(args.symbol_map))

    if not mappings:
        print("No active symbol mappings found in symbol_map.csv.", file=sys.stderr)
        return 1

    try:
        client = YahooFinanceClient()
        snapshots = client.build_snapshots(mappings, history_size=args.history_size)
    except MarketDataError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    ranked_candidates = rank_candidates(snapshots)
    decisions, rejected_alternatives, notes = build_decisions(cycle_timestamp, portfolio, ranked_candidates)

    latest_prices = {
        snapshot.xtb_ticker: (snapshot.price, snapshot.quote_currency, snapshot.fx_to_pln)
        for snapshot in snapshots
    }
    portfolio.total_value_pln = portfolio.cash_pln
    for position in portfolio.positions:
        price, _currency, fx_to_pln = latest_prices.get(
            position.ticker,
            (position.current_price or position.average_entry_price, position.quote_currency, 1.0),
        )
        portfolio.total_value_pln += position.quantity * price * fx_to_pln

    write_decisions_json(args.decisions_out, decisions)
    append_reasoning(
        args.reasoning_log,
        cycle_timestamp,
        portfolio,
        ranked_candidates,
        decisions,
        rejected_alternatives,
        notes,
    )
    append_transactions(args.transactions_log, decisions)
    write_current_portfolio(args.portfolio_file, portfolio, latest_prices)

    print(json.dumps([decision.to_dict() for decision in decisions], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
