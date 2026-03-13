"""Market data fetching, technical indicators, and FX conversion."""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
import yfinance as yf

from config import UNIVERSE


@dataclass
class InstrumentSnapshot:
    xtb_ticker: str
    yf_symbol: str
    asset_class: str
    quote_currency: str
    price: float
    sma_20: float
    rsi_14: float
    momentum_5d: float
    momentum_20d: float
    volatility_20d: float
    atr_14: float
    volume_ratio: float
    fx_to_pln: float
    price_pln: float
    bars_available: int


# ---------------------------------------------------------------------------
# Technical indicator helpers (pure numpy, no external TA library)
# ---------------------------------------------------------------------------

def compute_rsi(closes: np.ndarray, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes[-(period + 1):])
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def compute_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> float:
    if len(close) < period + 1:
        return 0.0
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1]),
        ),
    )
    return float(np.mean(tr[-period:]))


def compute_indicators(df: pd.DataFrame) -> dict:
    """Compute all technical indicators from an OHLCV DataFrame."""
    close = df["Close"].values.astype(float)
    high = df["High"].values.astype(float)
    low = df["Low"].values.astype(float)
    volume = df["Volume"].values.astype(float) if "Volume" in df.columns else np.ones(len(close))

    n = len(close)
    price = float(close[-1]) if n > 0 else 0.0

    sma_20 = float(np.mean(close[-20:])) if n >= 20 else price
    rsi_14 = compute_rsi(close, 14)

    momentum_5d = (close[-1] / close[-6] - 1.0) if n >= 6 else 0.0
    momentum_20d = (close[-1] / close[-21] - 1.0) if n >= 21 else 0.0

    daily_returns = np.diff(close[-21:]) / close[-21:-1] if n >= 21 else np.array([0.0])
    volatility_20d = float(np.std(daily_returns)) if len(daily_returns) > 1 else 0.0

    atr_14 = compute_atr(high, low, close, 14)

    avg_vol_20 = float(np.mean(volume[-20:])) if n >= 20 else 1.0
    volume_ratio = float(volume[-1] / avg_vol_20) if avg_vol_20 > 0 else 1.0

    return {
        "price": price,
        "sma_20": sma_20,
        "rsi_14": rsi_14,
        "momentum_5d": momentum_5d,
        "momentum_20d": momentum_20d,
        "volatility_20d": volatility_20d,
        "atr_14": atr_14,
        "volume_ratio": volume_ratio,
        "bars": n,
    }


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_fx_rates() -> dict[str, float]:
    """Fetch FX rates to PLN. Returns {currency_code: rate_to_pln}."""
    rates = {"PLN": 1.0}
    fx_pairs = [("USD", "PLN=X"), ("EUR", "EURPLN=X"), ("GBP", "GBPPLN=X")]

    for currency, yf_symbol in fx_pairs:
        try:
            ticker = yf.Ticker(yf_symbol)
            hist = ticker.history(period="5d")
            if len(hist) > 0:
                rates[currency] = float(hist["Close"].iloc[-1])
            else:
                # Fallback approximate rates
                fallbacks = {"USD": 4.0, "EUR": 4.30, "GBP": 5.10}
                rates[currency] = fallbacks.get(currency, 4.0)
        except Exception:
            fallbacks = {"USD": 4.0, "EUR": 4.30, "GBP": 5.10}
            rates[currency] = fallbacks.get(currency, 4.0)

    return rates


def fetch_all_data(universe: list[tuple] | None = None, period: str = "90d") -> dict[str, pd.DataFrame]:
    """Fetch OHLCV data for all instruments in the universe.

    Returns dict mapping yfinance symbol -> DataFrame.
    """
    if universe is None:
        universe = UNIVERSE

    yf_symbols = list({row[1] for row in universe})

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        data = yf.download(yf_symbols, period=period, progress=False, group_by="ticker", threads=True)

    result: dict[str, pd.DataFrame] = {}
    for sym in yf_symbols:
        try:
            if len(yf_symbols) == 1:
                df = data.copy()
            else:
                df = data[sym].copy()
            df = df.dropna(subset=["Close"])
            if len(df) > 0:
                result[sym] = df
        except (KeyError, TypeError):
            pass

    return result


def build_snapshots(
    universe: list[tuple] | None = None,
    fx_rates: dict[str, float] | None = None,
    raw_data: dict[str, pd.DataFrame] | None = None,
) -> list[InstrumentSnapshot]:
    """Build instrument snapshots with indicators and PLN pricing."""
    if universe is None:
        universe = UNIVERSE
    if fx_rates is None:
        fx_rates = fetch_fx_rates()
    if raw_data is None:
        raw_data = fetch_all_data(universe)

    snapshots = []
    for xtb_ticker, yf_symbol, asset_class, quote_currency in universe:
        df = raw_data.get(yf_symbol)
        if df is None or len(df) < 5:
            continue

        ind = compute_indicators(df)
        fx = fx_rates.get(quote_currency, 4.0)

        snapshots.append(InstrumentSnapshot(
            xtb_ticker=xtb_ticker,
            yf_symbol=yf_symbol,
            asset_class=asset_class,
            quote_currency=quote_currency,
            price=ind["price"],
            sma_20=ind["sma_20"],
            rsi_14=ind["rsi_14"],
            momentum_5d=ind["momentum_5d"],
            momentum_20d=ind["momentum_20d"],
            volatility_20d=ind["volatility_20d"],
            atr_14=ind["atr_14"],
            volume_ratio=ind["volume_ratio"],
            fx_to_pln=fx,
            price_pln=ind["price"] * fx,
            bars_available=ind["bars"],
        ))

    return snapshots
