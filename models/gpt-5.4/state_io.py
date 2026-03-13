from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from schemas import ExecutionUpdate, PortfolioState, PositionState, RankedCandidate, TradeDecision


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_scalar(raw_value: str) -> str | float | None:
    value = raw_value.strip()
    if value == "":
        return None
    if value.lower() in {"null", "none"}:
        return None
    try:
        return float(value)
    except ValueError:
        return value


def parse_cycle_input(path: str | Path) -> tuple[str, float, list[PositionState], list[ExecutionUpdate], str]:
    top_level: dict[str, str | float | None] = {}
    sections: dict[str, list[dict[str, str | float | None]]] = {
        "positions": [],
        "execution_updates": [],
        "statement_source": [],
    }
    current_section: str | None = None
    current_item: dict[str, str | float | None] | None = None

    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("```"):
            continue
        if current_section and not raw_line.startswith(" "):
            current_section = None
            current_item = None

        if stripped.endswith(":") and stripped[:-1] in sections and not raw_line.startswith("-"):
            current_section = stripped[:-1]
            current_item = None
            continue

        if current_section:
            if stripped.startswith("- "):
                current_item = {}
                sections[current_section].append(current_item)
                payload = stripped[2:]
                if payload and ":" in payload:
                    key, raw_value = payload.split(":", 1)
                    current_item[key.strip()] = _parse_scalar(raw_value)
                continue
            if raw_line.startswith("  ") and current_item is not None and ":" in stripped:
                key, raw_value = stripped.split(":", 1)
                current_item[key.strip()] = _parse_scalar(raw_value)
                continue

        if ":" in stripped:
            key, raw_value = stripped.split(":", 1)
            top_level[key.strip()] = _parse_scalar(raw_value)

    cycle_timestamp = str(top_level.get("datetime") or utc_now_iso())
    cash_pln = float(top_level.get("cash_pln") or 0.0)

    positions = [
        PositionState(
            ticker=str(item.get("ticker") or ""),
            quantity=float(item.get("quantity") or 0.0),
            average_entry_price=float(item.get("average_entry_price") or 0.0),
            current_price=float(item.get("current_price")) if item.get("current_price") is not None else None,
            market_value_pln=float(item.get("market_value_pln")) if item.get("market_value_pln") is not None else None,
            unrealized_pnl_pln=float(item.get("unrealized_pnl_pln")) if item.get("unrealized_pnl_pln") is not None else None,
        )
        for item in sections["positions"]
        if item.get("ticker")
    ]

    execution_updates = [
        ExecutionUpdate(
            ticker=str(item.get("ticker") or ""),
            action=str(item.get("action") or ""),
            proposed_price=float(item.get("proposed_price")) if item.get("proposed_price") is not None else None,
            actual_status=str(item.get("actual_status") or ""),
            actual_price=float(item.get("actual_price")) if item.get("actual_price") is not None else None,
            quantity=float(item.get("quantity")) if item.get("quantity") is not None else None,
            fees_pln=float(item.get("fees_pln")) if item.get("fees_pln") is not None else None,
            notes=str(item.get("notes") or ""),
        )
        for item in sections["execution_updates"]
        if item.get("ticker")
    ]

    statement_chunks = []
    for item in sections["statement_source"]:
        chunk = ", ".join(
            f"{key}={value}" for key, value in item.items() if value not in {None, ""}
        )
        if chunk:
            statement_chunks.append(chunk)
    statement_source = " | ".join(statement_chunks) or "manual_input"

    return cycle_timestamp, cash_pln, positions, execution_updates, statement_source


def load_portfolio_from_cycle_input(path: str | Path) -> PortfolioState:
    cycle_timestamp, cash_pln, positions, _execution_updates, statement_source = parse_cycle_input(path)
    total_value = cash_pln
    for position in positions:
        if position.market_value_pln is not None:
            total_value += position.market_value_pln
    return PortfolioState(
        as_of=cycle_timestamp,
        cash_pln=cash_pln,
        positions=positions,
        total_value_pln=total_value,
        source=statement_source,
    )


def write_decisions_json(path: str | Path, decisions: list[TradeDecision]) -> None:
    payload = [decision.to_dict() for decision in decisions]
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _existing_experiment_start(path: str | Path) -> str | None:
    portfolio_path = Path(path)
    if not portfolio_path.exists():
        return None
    for line in portfolio_path.read_text(encoding="utf-8").splitlines():
        prefix = "- Official experiment start:"
        if line.startswith(prefix):
            value = line.removeprefix(prefix).strip()
            if value and value != "pending first live decision cycle":
                return value
    return None


def write_current_portfolio(
    path: str | Path,
    portfolio: PortfolioState,
    latest_prices: dict[str, tuple[float, str, float]],
) -> None:
    official_start = _existing_experiment_start(path) or portfolio.as_of
    total_value_pln = portfolio.cash_pln
    lines = [
        "# Current Portfolio",
        "",
        f"## Snapshot - {portfolio.as_of}",
        "",
        "- Model: `gpt-5.4`",
        "- Base currency: `PLN`",
        f"- Official experiment start: {official_start}",
        f"- Last portfolio truth source: {portfolio.source or 'manual_input'}",
        "",
        "## Cash",
        "",
        f"- Available cash: `{portfolio.cash_pln:.2f} PLN`",
        "",
        "## Open Positions",
        "",
    ]

    if not portfolio.positions:
        lines.append("No open positions.")
    else:
        for position in portfolio.positions:
            current_price, quote_currency, fx_to_pln = latest_prices.get(
                position.ticker,
                (position.current_price or position.average_entry_price, position.quote_currency, 1.0),
            )
            market_value_pln = position.quantity * current_price * fx_to_pln
            total_value_pln += market_value_pln
            entry_value_pln = position.quantity * position.average_entry_price * fx_to_pln
            unrealized_pnl_pln = market_value_pln - entry_value_pln
            lines.extend(
                [
                    f"- Ticker: `{position.ticker}`",
                    f"  - Quantity: `{position.quantity}`",
                    f"  - Average entry price: `{position.average_entry_price:.4f}`",
                    f"  - Current price: `{current_price:.4f} {quote_currency}`",
                    f"  - FX to PLN: `{fx_to_pln:.4f}`",
                    f"  - Market value: `{market_value_pln:.2f} PLN`",
                    f"  - Unrealized PnL: `{unrealized_pnl_pln:.2f} PLN`",
                ]
            )

    lines.extend(
        [
            "",
            "## Unrealized PnL",
            "",
        ]
    )

    unrealized_total = 0.0
    for position in portfolio.positions:
        current_price, _quote_currency, fx_to_pln = latest_prices.get(
            position.ticker,
            (position.current_price or position.average_entry_price, position.quote_currency, 1.0),
        )
        unrealized_total += (position.quantity * current_price * fx_to_pln) - (
            position.quantity * position.average_entry_price * fx_to_pln
        )
    lines.extend(
        [
            f"- Unrealized PnL: `{unrealized_total:.2f} PLN`",
            "",
            "## Total Portfolio Value",
            "",
            f"- Total value: `{total_value_pln:.2f} PLN`",
        ]
    )

    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_reasoning(
    path: str | Path,
    cycle_timestamp: str,
    portfolio: PortfolioState,
    ranked_candidates: list[RankedCandidate],
    decisions: list[TradeDecision],
    rejected_alternatives: list[str],
    notes: list[str],
) -> None:
    lines = [
        "",
        f"## Decision Cycle - {cycle_timestamp}",
        "",
        "### Cycle Header",
        "",
        f"- Timestamp: {cycle_timestamp}",
        "- Market regime: momentum-ranked daily review",
        f"- Portfolio value: {portfolio.total_value_pln or portfolio.cash_pln:.2f} PLN",
        f"- Cash: {portfolio.cash_pln:.2f} PLN",
        f"- Open positions: {len(portfolio.positions)}",
        "",
        "### Market Context",
        "",
    ]
    if ranked_candidates:
        for candidate in ranked_candidates[:5]:
            lines.append(
                (
                    f"- {candidate.snapshot.xtb_ticker}: score={candidate.score:.4f}, "
                    f"mom5={candidate.momentum_5d:.4%}, mom20={candidate.momentum_20d:.4%}, "
                    f"vol20={candidate.volatility_20d:.4%}"
                )
            )
    else:
        lines.append("- No ranked candidates were available from the active symbol map.")

    lines.extend(
        [
            "",
            "### Portfolio Context",
            "",
        ]
    )
    if portfolio.positions:
        for position in portfolio.positions:
            lines.append(
                f"- {position.ticker}: qty={position.quantity}, avg_entry={position.average_entry_price:.4f}"
            )
    else:
        lines.append("- Portfolio started the cycle with no open positions.")

    lines.extend(
        [
            "",
            "### Rejected Alternatives",
            "",
        ]
    )
    if rejected_alternatives:
        lines.extend(f"- {item}" for item in rejected_alternatives)
    else:
        lines.append("- No additional alternatives were rejected beyond the selected set.")

    lines.extend(
        [
            "",
            "### Final Decisions",
            "",
            "```json",
            json.dumps([decision.to_dict() for decision in decisions], indent=2),
            "```",
            "",
            "### Notes For Execution",
            "",
        ]
    )
    if notes:
        lines.extend(f"- {note}" for note in notes)
    else:
        lines.append("- Orders remain valid only within the stated +/- 2% execution band.")

    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def append_transactions(path: str | Path, decisions: list[TradeDecision]) -> None:
    trade_decisions = [decision for decision in decisions if decision.action in {"BUY", "SELL"}]
    if not trade_decisions:
        return

    lines: list[str] = [""]
    for decision in trade_decisions:
        lines.extend(
            [
                f"### Trade Record - {decision.datetime} - {decision.ticker}",
                "",
                f"- Timestamp: {decision.datetime}",
                f"- Ticker: {decision.ticker}",
                f"- Action: {decision.action}",
                f"- Proposed price: {decision.price}",
                f"- Quantity: {decision.quantity}",
                "- Execution status: `pending`",
                "- Actual execution price:",
                "- Actual execution quantity:",
                f"- Notes: {decision.reason}",
                "",
            ]
        )

    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def serialize_positions(positions: list[PositionState]) -> list[dict]:
    return [asdict(position) for position in positions]
