"""Read/write portfolio state, reasoning, transactions, and symbol map."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from decision_engine import Position, PortfolioState, TradeDecision
from scoring import RankedCandidate


# ---------------------------------------------------------------------------
# Portfolio I/O
# ---------------------------------------------------------------------------

def load_portfolio(path: Path) -> PortfolioState:
    """Parse current_portfolio.md into a PortfolioState."""
    text = path.read_text(encoding="utf-8")

    # Extract cash
    cash = 1000.0
    cash_match = re.search(r"\|\s*PLN\s*\|\s*([\d.]+)\s*\|", text)
    if cash_match:
        cash = float(cash_match.group(1))

    # Extract positions from Open Positions table
    positions: list[Position] = []
    pos_section = re.search(
        r"## Open Positions\s*\n(.*?)(?=\n## |\Z)", text, re.DOTALL
    )
    if pos_section:
        rows = re.findall(
            r"\|\s*(\S+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*(\w+)\s*\|\s*(\w+)\s*\|",
            pos_section.group(1),
        )
        for ticker, qty, entry, currency, asset_class in rows:
            if ticker.startswith("-") or ticker.lower() == "ticker":
                continue
            positions.append(Position(
                ticker=ticker,
                quantity=float(qty),
                avg_entry_price=float(entry),
                quote_currency=currency,
                asset_class=asset_class,
            ))

    # Extract total value
    total = cash
    total_match = re.search(r"Total portfolio value.*?\*\*([\d.]+)\s*PLN\*\*", text)
    if total_match:
        total = float(total_match.group(1))

    return PortfolioState(cash_pln=cash, positions=positions, total_value_pln=total)


def write_portfolio(
    path: Path,
    portfolio: PortfolioState,
    latest_prices: dict[str, tuple[float, str, float]],
    fx_rates: dict[str, float],
    cycle_num: int,
    timestamp: str,
) -> None:
    """Write current_portfolio.md with updated state."""
    lines = [
        "# Current Portfolio — Opus 4.6\n",
        f"**Last updated:** {timestamp}",
        f"**Cycle:** {cycle_num}\n",
        "## Cash\n",
        "| Currency | Amount |",
        "|----------|--------|",
        f"| PLN      | {portfolio.cash_pln:.2f} |\n",
        "## Open Positions\n",
    ]

    if not portfolio.positions:
        lines.append("_No open positions._\n")
        total_pos_value = 0.0
        unrealized_pnl = 0.0
    else:
        lines.extend([
            "| Ticker | Quantity | Avg Entry | Current Price | Currency | Class | Value (PLN) | PnL (PLN) |",
            "|--------|----------|-----------|---------------|----------|-------|-------------|-----------|",
        ])
        total_pos_value = 0.0
        unrealized_pnl = 0.0
        for pos in portfolio.positions:
            price_info = latest_prices.get(pos.ticker)
            if price_info:
                cur_price, cur, fx = price_info
            else:
                cur_price = pos.avg_entry_price
                fx = fx_rates.get(pos.quote_currency, 4.0)

            pos_value_pln = cur_price * pos.quantity * fx
            entry_value_pln = pos.avg_entry_price * pos.quantity * fx
            pnl = pos_value_pln - entry_value_pln
            total_pos_value += pos_value_pln
            unrealized_pnl += pnl

            lines.append(
                f"| {pos.ticker} | {pos.quantity} | {pos.avg_entry_price:.2f} "
                f"| {cur_price:.2f} | {pos.quote_currency} | {pos.asset_class} "
                f"| {pos_value_pln:.2f} | {pnl:+.2f} |"
            )
        lines.append("")

    total_value = portfolio.cash_pln + total_pos_value

    lines.extend([
        "## Portfolio Summary\n",
        "| Metric              | Value      |",
        "|---------------------|------------|",
        f"| Total cash          | {portfolio.cash_pln:.2f} PLN |",
        f"| Total position value | {total_pos_value:.2f} PLN   |",
        f"| Unrealized PnL      | {unrealized_pnl:+.2f} PLN   |",
        f"| **Total portfolio value** | **{total_value:.2f} PLN** |",
    ])

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Reasoning log
# ---------------------------------------------------------------------------

def append_reasoning(
    path: Path,
    cycle_num: int,
    timestamp: str,
    portfolio: PortfolioState,
    ranked: list[RankedCandidate],
    decisions: list[TradeDecision],
    rejected: list[str],
    notes: list[str],
) -> None:
    """Append a cycle entry to reasoning.md."""
    top5 = ranked[:5]
    top5_str = "\n".join(
        f"  - {rc.snapshot.xtb_ticker}: score={rc.score:.4f}, "
        f"mom20d={rc.snapshot.momentum_20d:.1%}, RSI={rc.snapshot.rsi_14:.0f}, "
        f"price={rc.snapshot.price:.2f} {rc.snapshot.quote_currency}"
        for rc in top5
    )

    decisions_json = json.dumps([d.to_dict() for d in decisions], indent=2)

    rejected_str = "\n".join(f"  - {r}" for r in rejected) if rejected else "  None."
    notes_str = "\n".join(f"  - {n}" for n in notes) if notes else "  None."

    entry = f"""
## Cycle {cycle_num} — {timestamp}

**Portfolio context:** Cash: {portfolio.cash_pln:.2f} PLN, Positions: {len(portfolio.positions)}, Total value: {portfolio.total_value_pln:.2f} PLN

**Top 5 ranked instruments:**
{top5_str}

**Rejected alternatives:**
{rejected_str}

**Notes:**
{notes_str}

**Final decisions:**
```json
{decisions_json}
```

---
"""

    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)


# ---------------------------------------------------------------------------
# Transaction log
# ---------------------------------------------------------------------------

def append_transactions(
    path: Path,
    cycle_num: int,
    timestamp: str,
    decisions: list[TradeDecision],
) -> None:
    """Append trade decisions to transactions.md."""
    text = path.read_text(encoding="utf-8")

    # Remove the placeholder row if present
    text = text.replace("| _No transactions yet._ | | | | | | | |\n", "")

    trade_decisions = [d for d in decisions if d.action in ("BUY", "SELL")]
    if not trade_decisions:
        return

    new_rows = []
    for d in trade_decisions:
        new_rows.append(
            f"| {cycle_num} | {timestamp} | {d.ticker} | {d.action} "
            f"| {d.price:.2f} | {d.quantity} | PENDING | {d.reason[:60]} |"
        )

    # Insert before the trailing ---
    if text.rstrip().endswith("---"):
        text = text.rstrip().rstrip("-").rstrip() + "\n"

    text += "\n".join(new_rows) + "\n\n---\n"
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Decisions JSON
# ---------------------------------------------------------------------------

def write_decisions_json(path: Path, decisions: list[TradeDecision]) -> None:
    """Write latest_decisions.json."""
    data = [d.to_dict() for d in decisions]
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Symbol map
# ---------------------------------------------------------------------------

def update_symbol_map(path: Path, universe: list[tuple]) -> None:
    """Ensure all universe instruments are in symbol_map.csv."""
    existing = set()
    if path.exists():
        with open(path, encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if row:
                    existing.add(row[0])

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["xtb_ticker", "yfinance_symbol", "asset_class", "quote_currency", "status", "notes"])
        for xtb, yf_sym, cls, cur in universe:
            writer.writerow([xtb, yf_sym, cls, cur, "active", ""])
