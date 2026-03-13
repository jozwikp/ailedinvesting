"""Multi-factor scoring and ranking of instruments."""

from __future__ import annotations

from dataclasses import dataclass

from config import STRATEGY
from market_data import InstrumentSnapshot


@dataclass
class RankedCandidate:
    snapshot: InstrumentSnapshot
    score: float
    score_components: dict


def compute_score(snap: InstrumentSnapshot, cfg: dict | None = None) -> tuple[float, dict]:
    """Compute composite score for an instrument.

    Returns (score, components_dict).
    """
    if cfg is None:
        cfg = STRATEGY

    # 1. Momentum components (cap at ±30% to avoid futures rollover distortion)
    capped_mom_20d = max(-0.30, min(0.30, snap.momentum_20d))
    capped_mom_5d = max(-0.15, min(0.15, snap.momentum_5d))
    mom_20d = capped_mom_20d * cfg["w_momentum_20d"]
    mom_5d = capped_mom_5d * cfg["w_momentum_5d"]

    # 2. Trend bonus/penalty
    if snap.price > snap.sma_20 and snap.sma_20 > 0:
        trend_raw = 0.02
    elif snap.sma_20 > 0:
        trend_raw = -0.02
    else:
        trend_raw = 0.0
    trend = trend_raw * (cfg["w_trend_bonus"] / 0.15)

    # 3. RSI signal
    rsi = snap.rsi_14
    if rsi < cfg["rsi_oversold"]:
        rsi_raw = 0.02  # oversold bounce potential
    elif rsi > cfg["rsi_overbought"]:
        rsi_raw = -0.02  # overbought risk
    else:
        rsi_raw = (rsi - 50) / 1000  # mild directional tilt
    rsi_signal = rsi_raw * (cfg["w_rsi_signal"] / 0.20)

    # 4. Volatility penalty (ATR-normalized)
    rel_vol = snap.atr_14 / snap.price if snap.price > 0 else 0.0
    vol_penalty = rel_vol * (cfg["w_volatility_penalty"] / 0.15)

    # 5. Volume confirmation bonus
    vol_bonus = 0.005 if snap.volume_ratio > 1.2 else 0.0

    total = mom_20d + mom_5d + trend + rsi_signal - vol_penalty + vol_bonus

    components = {
        "momentum_20d": mom_20d,
        "momentum_5d": mom_5d,
        "trend": trend,
        "rsi_signal": rsi_signal,
        "vol_penalty": -vol_penalty,
        "vol_bonus": vol_bonus,
    }

    return total, components


def rank_candidates(
    snapshots: list[InstrumentSnapshot],
    cfg: dict | None = None,
) -> list[RankedCandidate]:
    """Score all snapshots and return sorted list (best first)."""
    if cfg is None:
        cfg = STRATEGY

    ranked = []
    for snap in snapshots:
        if snap.bars_available < cfg["min_data_bars"]:
            continue
        score, components = compute_score(snap, cfg)
        ranked.append(RankedCandidate(
            snapshot=snap,
            score=score,
            score_components=components,
        ))

    ranked.sort(key=lambda r: r.score, reverse=True)
    return ranked
