from __future__ import annotations

import math
from statistics import mean, pstdev

from schemas import PortfolioState, RankedCandidate, TradeDecision


def _asset_class_key(asset_class: str) -> str:
    return asset_class.strip().lower().replace(" ", "")


def _is_buyable_asset(asset_class: str) -> bool:
    return _asset_class_key(asset_class) in {
        "stock",
        "stocks",
        "etf",
        "etfs",
        "cryptocurrencycfd",
        "cryptocfd",
        "crypto",
        "cryptocurrency",
    }


def _supports_fractional_quantity(asset_class: str) -> bool:
    return _asset_class_key(asset_class) in {
        "cryptocurrencycfd",
        "cryptocfd",
        "crypto",
        "cryptocurrency",
        "forexcfd",
        "indexcfd",
        "commoditycfd",
    }


def _risk_level(asset_class: str, volatility_20d: float) -> str:
    key = _asset_class_key(asset_class)
    if key in {"cryptocurrencycfd", "cryptocfd", "crypto", "cryptocurrency"}:
        return "high"
    if volatility_20d >= 0.03:
        return "high"
    if volatility_20d >= 0.015:
        return "medium"
    return "low"


def _daily_returns(closes: list[float]) -> list[float]:
    returns: list[float] = []
    for previous, current in zip(closes, closes[1:]):
        if math.isclose(previous, 0.0):
            continue
        returns.append((current / previous) - 1.0)
    return returns


def rank_candidates(snapshots: list) -> list[RankedCandidate]:
    ranked: list[RankedCandidate] = []
    for snapshot in snapshots:
        if len(snapshot.closes) < 21:
            continue
        ma20 = mean(snapshot.closes[-20:])
        momentum_5d = (snapshot.price / snapshot.closes[-6]) - 1.0 if len(snapshot.closes) >= 6 else 0.0
        momentum_20d = (snapshot.price / snapshot.closes[-21]) - 1.0
        returns_20d = _daily_returns(snapshot.closes[-21:])
        volatility_20d = pstdev(returns_20d) if len(returns_20d) >= 2 else 0.0
        trend_bonus = 0.02 if snapshot.price > ma20 else -0.02
        quality_penalty = volatility_20d * 0.50
        score = (momentum_20d * 0.55) + (momentum_5d * 0.25) + trend_bonus - quality_penalty
        ranked.append(
            RankedCandidate(
                snapshot=snapshot,
                score=score,
                momentum_5d=momentum_5d,
                momentum_20d=momentum_20d,
                volatility_20d=volatility_20d,
                ma20=ma20,
            )
        )
    return sorted(ranked, key=lambda item: item.score, reverse=True)


def build_decisions(
    cycle_timestamp: str,
    portfolio: PortfolioState,
    ranked_candidates: list[RankedCandidate],
) -> tuple[list[TradeDecision], list[str], list[str]]:
    decisions: list[TradeDecision] = []
    rejected: list[str] = []
    notes: list[str] = []

    ranked_by_ticker = {candidate.snapshot.xtb_ticker: candidate for candidate in ranked_candidates}
    estimated_sell_value_pln = 0.0
    kept_tickers: set[str] = set()
    current_positions = {position.ticker: position for position in portfolio.positions}

    for position in portfolio.positions:
        candidate = ranked_by_ticker.get(position.ticker)
        current_price = position.current_price
        if candidate:
            current_price = candidate.snapshot.price
        if current_price is None:
            notes.append(f"{position.ticker}: no current price, defaulted to KEEP.")
            decisions.append(
                TradeDecision(
                    datetime=cycle_timestamp,
                    ticker=position.ticker,
                    action="KEEP",
                    price=round(position.average_entry_price, 4),
                    quantity=position.quantity,
                    reason="No fresh market data available for a conviction change.",
                    risk_level="medium",
                    invalidation="Review after a new broker quote or execution update is available.",
                )
            )
            kept_tickers.add(position.ticker)
            continue

        if candidate:
            should_sell = (
                current_price <= position.average_entry_price * 0.92
                or (candidate.snapshot.price < candidate.ma20 and candidate.momentum_20d < 0.0)
                or candidate.score < -0.015
            )
            risk_level = _risk_level(candidate.snapshot.asset_class, candidate.volatility_20d)
            if should_sell:
                estimated_sell_value_pln += candidate.snapshot.price_pln * position.quantity
                decisions.append(
                    TradeDecision(
                        datetime=cycle_timestamp,
                        ticker=position.ticker,
                        action="SELL",
                        price=round(candidate.snapshot.price, 4),
                        quantity=position.quantity,
                        reason="Trend and momentum weakened beyond the hold threshold.",
                        risk_level=risk_level,
                        invalidation="Sell thesis is invalidated only if a new cycle restores positive momentum and price above the 20-day average.",
                    )
                )
            else:
                kept_tickers.add(position.ticker)
                decisions.append(
                    TradeDecision(
                        datetime=cycle_timestamp,
                        ticker=position.ticker,
                        action="KEEP",
                        price=round(candidate.snapshot.price, 4),
                        quantity=position.quantity,
                        reason="Position remains above the hold threshold with acceptable momentum.",
                        risk_level=risk_level,
                        invalidation="Exit if price closes below the 20-day average and 20-day momentum turns negative.",
                    )
                )
        else:
            kept_tickers.add(position.ticker)
            notes.append(f"{position.ticker}: not present in the active symbol map, defaulted to KEEP.")
            decisions.append(
                TradeDecision(
                    datetime=cycle_timestamp,
                    ticker=position.ticker,
                    action="KEEP",
                    price=round(current_price, 4),
                    quantity=position.quantity,
                    reason="Instrument is not mapped for scoring, so no automated exit was triggered.",
                    risk_level="medium",
                    invalidation="Review once the instrument is added to the active symbol map.",
                )
            )

    eligible_buys = [
        candidate
        for candidate in ranked_candidates
        if candidate.snapshot.xtb_ticker not in current_positions
        and _is_buyable_asset(candidate.snapshot.asset_class)
        and candidate.snapshot.price > candidate.ma20
        and candidate.momentum_20d > 0.0
        and candidate.score > 0.015
    ]

    if not eligible_buys:
        rejected.append("No active stock, ETF, or crypto candidate met the minimum trend, momentum, and mapping thresholds.")

    keep_count = len(kept_tickers)
    target_position_count = 2 if keep_count < 2 else min(keep_count, 4)
    buy_slots = max(0, target_position_count - keep_count)
    if keep_count == 0:
        buy_slots = min(2, len(eligible_buys))

    available_cash_pln = portfolio.cash_pln + estimated_sell_value_pln
    cash_reserve_pln = max((portfolio.total_value_pln or portfolio.cash_pln) * 0.10, 100.0)
    deployable_cash_pln = max(0.0, available_cash_pln - cash_reserve_pln)

    selected_buys = eligible_buys[:buy_slots]
    if buy_slots and not selected_buys:
        rejected.append("Buy slots were available, but no candidate had enough data quality to allocate capital.")

    for skipped in eligible_buys[buy_slots:]:
        rejected.append(
            f"{skipped.snapshot.xtb_ticker}: ranked below selected candidates with a score of {skipped.score:.4f}."
        )

    for candidate in selected_buys:
        if buy_slots == 0:
            break
        per_trade_budget_pln = deployable_cash_pln / buy_slots if buy_slots else 0.0
        if candidate.snapshot.price_pln <= 0:
            rejected.append(f"{candidate.snapshot.xtb_ticker}: invalid PLN price conversion.")
            continue

        raw_quantity = per_trade_budget_pln / candidate.snapshot.price_pln
        if _supports_fractional_quantity(candidate.snapshot.asset_class):
            quantity = round(raw_quantity, 6)
            minimum_quantity = 0.0001
        else:
            quantity = math.floor(raw_quantity)
            minimum_quantity = 1

        if quantity < minimum_quantity:
            rejected.append(
                f"{candidate.snapshot.xtb_ticker}: insufficient capital to open the minimum position size while preserving cash reserve."
            )
            continue

        risk_level = _risk_level(candidate.snapshot.asset_class, candidate.volatility_20d)
        decisions.append(
            TradeDecision(
                datetime=cycle_timestamp,
                ticker=candidate.snapshot.xtb_ticker,
                action="BUY",
                price=round(candidate.snapshot.price, 4),
                quantity=quantity,
                reason="Ranked in the top momentum cohort with price above its 20-day average.",
                risk_level=risk_level,
                invalidation="Exit if price closes below the 20-day average and the 20-day momentum becomes negative.",
            )
        )

    if not decisions:
        notes.append("No mapped positions or candidates produced a tradeable decision.")

    return decisions, rejected, notes
