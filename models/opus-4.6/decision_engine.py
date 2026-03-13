"""Core BUY/SELL/KEEP decision logic with ATR-based position sizing."""

from __future__ import annotations

from dataclasses import dataclass, asdict

from config import STRATEGY
from scoring import RankedCandidate


@dataclass
class Position:
    ticker: str
    quantity: float
    avg_entry_price: float
    quote_currency: str
    asset_class: str


@dataclass
class PortfolioState:
    cash_pln: float
    positions: list[Position]
    total_value_pln: float


@dataclass
class TradeDecision:
    datetime: str
    ticker: str
    action: str
    price: float
    quantity: float
    reason: str
    risk_level: str
    invalidation: str

    def to_dict(self) -> dict:
        return asdict(self)


def _round_price(price: float) -> float:
    """Round price to reasonable precision."""
    if price >= 100:
        return round(price, 2)
    if price >= 1:
        return round(price, 4)
    return round(price, 6)


def _risk_level(asset_class: str, volatility: float) -> str:
    if asset_class == "crypto_cfd" or volatility > 0.03:
        return "high"
    if asset_class in ("commodity_cfd", "forex_cfd") or volatility > 0.015:
        return "medium"
    return "low"


def evaluate_positions(
    timestamp: str,
    portfolio: PortfolioState,
    ranked_by_ticker: dict[str, RankedCandidate],
    cfg: dict,
) -> list[TradeDecision]:
    """Evaluate existing positions for SELL or KEEP."""
    decisions = []

    for pos in portfolio.positions:
        rc = ranked_by_ticker.get(pos.ticker)
        if rc is None:
            # No market data — KEEP with note
            decisions.append(TradeDecision(
                datetime=timestamp,
                ticker=pos.ticker,
                action="KEEP",
                price=pos.avg_entry_price,
                quantity=pos.quantity,
                reason="No current market data available. Holding position.",
                risk_level="medium",
                invalidation="Market data becomes available and shows adverse conditions.",
            ))
            continue

        snap = rc.snapshot
        score = rc.score
        p = _round_price(snap.price)

        # Hard stop: price dropped more than hard_stop_pct below entry
        loss_pct = (snap.price - pos.avg_entry_price) / pos.avg_entry_price
        if loss_pct <= -cfg["hard_stop_pct"]:
            decisions.append(TradeDecision(
                datetime=timestamp,
                ticker=pos.ticker,
                action="SELL",
                price=p,
                quantity=pos.quantity,
                reason=f"Hard stop triggered. Price down {loss_pct:.1%} from entry {pos.avg_entry_price:.2f}.",
                risk_level=_risk_level(pos.asset_class, snap.volatility_20d),
                invalidation="N/A — stop-loss exit.",
            ))
            continue

        # Trend breakdown: price < SMA20 AND negative momentum AND weak RSI
        if (snap.price < snap.sma_20
                and snap.momentum_20d < 0
                and snap.rsi_14 < 45):
            decisions.append(TradeDecision(
                datetime=timestamp,
                ticker=pos.ticker,
                action="SELL",
                price=p,
                quantity=pos.quantity,
                reason=f"Trend breakdown: price below SMA20, momentum {snap.momentum_20d:.1%}, RSI {snap.rsi_14:.0f}.",
                risk_level=_risk_level(pos.asset_class, snap.volatility_20d),
                invalidation="N/A — trend exit.",
            ))
            continue

        # Score degradation
        if score < cfg["score_sell_threshold"]:
            decisions.append(TradeDecision(
                datetime=timestamp,
                ticker=pos.ticker,
                action="SELL",
                price=p,
                quantity=pos.quantity,
                reason=f"Score degraded to {score:.4f}, below threshold {cfg['score_sell_threshold']}.",
                risk_level=_risk_level(pos.asset_class, snap.volatility_20d),
                invalidation="N/A — score-based exit.",
            ))
            continue

        # Default: KEEP
        note_parts = [f"Score {score:.4f}"]
        if loss_pct > 0.15 and snap.rsi_14 > 70:
            note_parts.append(f"Consider partial profit-take (gain {loss_pct:.1%}, RSI {snap.rsi_14:.0f})")

        decisions.append(TradeDecision(
            datetime=timestamp,
            ticker=pos.ticker,
            action="KEEP",
            price=p,
            quantity=pos.quantity,
            reason=f"Holding position. {'; '.join(note_parts)}.",
            risk_level=_risk_level(pos.asset_class, snap.volatility_20d),
            invalidation=f"Price falls below {_round_price(pos.avg_entry_price * (1 - cfg['hard_stop_pct']))} or trend breakdown occurs.",
        ))

    return decisions


def _estimate_sell_proceeds(decisions: list[TradeDecision], fx_rates: dict[str, float], positions: list[Position]) -> float:
    """Estimate PLN proceeds from SELL decisions."""
    total = 0.0
    pos_map = {p.ticker: p for p in positions}
    for d in decisions:
        if d.action == "SELL":
            pos = pos_map.get(d.ticker)
            if pos:
                fx = fx_rates.get(pos.quote_currency, 4.0)
                total += d.price * d.quantity * fx
    return total


def select_buys(
    timestamp: str,
    portfolio: PortfolioState,
    ranked: list[RankedCandidate],
    sell_decisions: list[TradeDecision],
    fx_rates: dict[str, float],
    cfg: dict,
) -> list[TradeDecision]:
    """Select BUY candidates from ranked list."""
    # Held tickers (after sells)
    sold_tickers = {d.ticker for d in sell_decisions if d.action == "SELL"}
    held_tickers = {p.ticker for p in portfolio.positions} - sold_tickers
    current_position_count = len(held_tickers)

    available_slots = cfg["max_positions"] - current_position_count
    if available_slots <= 0:
        return []

    # Available cash
    sell_proceeds = _estimate_sell_proceeds(sell_decisions, fx_rates, portfolio.positions)
    cash_reserve = portfolio.total_value_pln * cfg["cash_reserve_pct"]
    available_cash = portfolio.cash_pln + sell_proceeds - cash_reserve

    if available_cash <= 0:
        return []

    # Filter candidates
    candidates = []
    for rc in ranked:
        snap = rc.snapshot
        if snap.xtb_ticker in held_tickers:
            continue
        if snap.asset_class not in cfg["buyable_classes"]:
            continue
        if snap.price <= 0 or snap.sma_20 <= 0:
            continue
        if snap.price < snap.sma_20:
            continue
        if snap.momentum_20d < 0:
            continue
        if rc.score < cfg["min_buy_score"]:
            continue
        candidates.append(rc)

    if not candidates:
        return []

    decisions = []
    cash_remaining = available_cash

    for rc in candidates[:available_slots]:
        snap = rc.snapshot
        fx = fx_rates.get(snap.quote_currency, 4.0)

        # ATR-based position sizing
        risk_amount_pln = portfolio.total_value_pln * cfg["risk_per_trade_pct"]
        stop_distance = snap.atr_14 * cfg["atr_risk_multiplier"]

        if stop_distance > 0:
            quantity_by_risk = risk_amount_pln / (stop_distance * fx)
        else:
            quantity_by_risk = 0

        # Cap by target position size
        max_by_size = (portfolio.total_value_pln * cfg["target_position_pct"]) / (snap.price * fx)

        # Cap by available cash
        max_by_cash = cash_remaining / (snap.price * fx)

        quantity = min(quantity_by_risk, max_by_size, max_by_cash)

        if quantity <= 0:
            continue

        # Round: fractional shares allow 2 decimals, CFDs/forex may differ
        if snap.asset_class in ("stock", "etf"):
            quantity = round(quantity, 2)
        else:
            quantity = round(quantity, 4)

        if quantity <= 0:
            continue

        cost_pln = snap.price * quantity * fx
        if cost_pln > cash_remaining:
            continue

        cash_remaining -= cost_pln

        invalidation_price = _round_price(snap.price - stop_distance)
        decisions.append(TradeDecision(
            datetime=timestamp,
            ticker=snap.xtb_ticker,
            action="BUY",
            price=_round_price(snap.price),
            quantity=quantity,
            reason=(
                f"Top-ranked candidate (score {rc.score:.4f}). "
                f"Momentum 20d: {snap.momentum_20d:.1%}, RSI: {snap.rsi_14:.0f}, "
                f"price above SMA20 ({snap.sma_20:.2f})."
            ),
            risk_level=_risk_level(snap.asset_class, snap.volatility_20d),
            invalidation=f"Price falls below {invalidation_price:.2f} ({snap.quote_currency}).",
        ))

    return decisions


def build_decisions(
    timestamp: str,
    portfolio: PortfolioState,
    ranked: list[RankedCandidate],
    fx_rates: dict[str, float],
    cfg: dict | None = None,
) -> tuple[list[TradeDecision], list[str], list[str]]:
    """Run full decision cycle.

    Returns (decisions, rejected_alternatives, notes).
    """
    if cfg is None:
        cfg = STRATEGY

    ranked_by_ticker = {rc.snapshot.xtb_ticker: rc for rc in ranked}

    # 1. Evaluate existing positions
    position_decisions = evaluate_positions(timestamp, portfolio, ranked_by_ticker, cfg)

    # 2. Select new buys
    buy_decisions = select_buys(timestamp, portfolio, ranked, position_decisions, fx_rates, cfg)

    all_decisions = position_decisions + buy_decisions

    # 3. Build rejected alternatives list
    sold_tickers = {d.ticker for d in position_decisions if d.action == "SELL"}
    held_tickers = {p.ticker for p in portfolio.positions} - sold_tickers
    bought_tickers = {d.ticker for d in buy_decisions}
    active_tickers = held_tickers | bought_tickers

    rejected = []
    for rc in ranked[:10]:
        t = rc.snapshot.xtb_ticker
        if t not in active_tickers:
            rejected.append(f"{t} (score {rc.score:.4f}, RSI {rc.snapshot.rsi_14:.0f})")

    # 4. Notes
    notes = []
    sell_count = sum(1 for d in all_decisions if d.action == "SELL")
    buy_count = sum(1 for d in all_decisions if d.action == "BUY")
    keep_count = sum(1 for d in all_decisions if d.action == "KEEP")
    notes.append(f"Decisions: {buy_count} BUY, {sell_count} SELL, {keep_count} KEEP.")

    total_positions_after = len(held_tickers) + buy_count
    if total_positions_after < cfg["min_positions"] and buy_count == 0:
        notes.append("Warning: below minimum diversification target.")

    return all_decisions, rejected, notes
