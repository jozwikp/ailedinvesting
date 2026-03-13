from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Iterable

import yfinance as yf
from schemas import InstrumentMapping, MarketSnapshot


class MarketDataError(RuntimeError):
    pass


def load_symbol_map(path: str | Path) -> list[InstrumentMapping]:
    mappings: list[InstrumentMapping] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            xtb_ticker = (row.get("xtb_ticker") or "").strip()
            market_symbol = (
                (row.get("market_symbol") or "").strip()
                or (row.get("yfinance_symbol") or "").strip()
                or (row.get("twelve_data_symbol") or "").strip()
            )
            if not xtb_ticker or not market_symbol:
                continue
            mappings.append(
                InstrumentMapping(
                    xtb_ticker=xtb_ticker,
                    market_symbol=market_symbol,
                    asset_class=(row.get("asset_class") or "").strip() or "unknown",
                    quote_currency=((row.get("quote_currency") or "").strip() or "PLN").upper(),
                    status=(row.get("status") or "").strip().lower(),
                    notes=(row.get("notes") or "").strip(),
                )
            )
    return mappings


def active_mappings(mappings: list[InstrumentMapping]) -> list[InstrumentMapping]:
    return [mapping for mapping in mappings if mapping.status == "active"]


class YahooFinanceClient:
    def __init__(self, history_period: str = "6mo") -> None:
        self.history_period = history_period

    def _download_frame(self, symbols: list[str]):
        if not symbols:
            return None
        try:
            frame = yf.download(
                tickers=" ".join(symbols),
                period=self.history_period,
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False,
                group_by="ticker",
            )
        except Exception as exc:
            raise MarketDataError(f"Failed to download Yahoo Finance data: {exc}") from exc
        if frame is None or frame.empty:
            raise MarketDataError("Yahoo Finance returned no data.")
        return frame

    @staticmethod
    def _extract_closes(frame, symbol: str) -> list[tuple[str, float]]:
        if hasattr(frame.columns, "nlevels") and frame.columns.nlevels > 1:
            if symbol not in frame.columns.get_level_values(0):
                return []
            close_series = frame[symbol]["Close"].dropna()
        else:
            close_series = frame["Close"].dropna()
        return [(index.strftime("%Y-%m-%d"), float(value)) for index, value in close_series.items()]

    def fetch_fx_to_pln(self, quote_currency: str) -> float:
        quote_currency = quote_currency.upper()
        if quote_currency == "PLN":
            return 1.0

        direct_symbol = f"{quote_currency}PLN=X"
        try:
            direct_frame = self._download_frame([direct_symbol])
            direct_series = self._extract_closes(direct_frame, direct_symbol)
            if not direct_series:
                raise MarketDataError(f"No FX data returned for {direct_symbol}.")
            return direct_series[-1][1]
        except Exception:
            inverse_symbol = f"PLN{quote_currency}=X"
            inverse_frame = self._download_frame([inverse_symbol])
            inverse_series = self._extract_closes(inverse_frame, inverse_symbol)
            if not inverse_series:
                raise MarketDataError(f"No FX data returned for {inverse_symbol}.")
            inverse_value = inverse_series[-1][1]
            if math.isclose(inverse_value, 0.0):
                raise MarketDataError(f"Invalid FX rate for {quote_currency}.")
            return 1.0 / inverse_value

    def fetch_time_series_map(self, symbols: Iterable[str]) -> dict[str, list[tuple[str, float]]]:
        unique_symbols = [symbol for symbol in dict.fromkeys(symbols) if symbol]
        frame = self._download_frame(unique_symbols)
        return {symbol: self._extract_closes(frame, symbol) for symbol in unique_symbols}

    def build_snapshots(self, mappings: list[InstrumentMapping], history_size: int = 60) -> list[MarketSnapshot]:
        fx_cache: dict[str, float] = {}
        snapshots: list[MarketSnapshot] = []
        series_map = self.fetch_time_series_map([mapping.market_symbol for mapping in mappings])

        for mapping in mappings:
            series = series_map.get(mapping.market_symbol) or []
            quote_currency = mapping.quote_currency.upper()
            if quote_currency not in fx_cache:
                fx_cache[quote_currency] = self.fetch_fx_to_pln(quote_currency)

            closes = [close for _date, close in series[-history_size:]]
            if not closes:
                raise MarketDataError(f"No closing prices returned for {mapping.market_symbol}.")
            latest_date = series[-1][0]
            previous_close = closes[-2] if len(closes) >= 2 else None
            snapshots.append(
                MarketSnapshot(
                    xtb_ticker=mapping.xtb_ticker,
                    market_symbol=mapping.market_symbol,
                    asset_class=mapping.asset_class,
                    quote_currency=quote_currency,
                    fx_to_pln=fx_cache[quote_currency],
                    as_of=latest_date,
                    price=closes[-1],
                    previous_close=previous_close,
                    closes=closes,
                )
            )
        return snapshots
