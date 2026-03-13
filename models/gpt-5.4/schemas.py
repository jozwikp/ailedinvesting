from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class InstrumentMapping:
    xtb_ticker: str
    market_symbol: str
    asset_class: str
    quote_currency: str
    status: str = ""
    notes: str = ""


@dataclass
class PositionState:
    ticker: str
    quantity: float
    average_entry_price: float
    current_price: float | None = None
    quote_currency: str = "PLN"
    market_value_pln: float | None = None
    unrealized_pnl_pln: float | None = None


@dataclass
class PortfolioState:
    as_of: str
    cash_pln: float
    positions: list[PositionState] = field(default_factory=list)
    total_value_pln: float | None = None
    source: str = ""


@dataclass
class ExecutionUpdate:
    ticker: str
    action: str
    proposed_price: float | None = None
    actual_status: str = ""
    actual_price: float | None = None
    quantity: float | None = None
    fees_pln: float | None = None
    notes: str = ""


@dataclass
class MarketSnapshot:
    xtb_ticker: str
    market_symbol: str
    asset_class: str
    quote_currency: str
    fx_to_pln: float
    as_of: str
    price: float
    previous_close: float | None
    closes: list[float] = field(default_factory=list)

    @property
    def price_pln(self) -> float:
        return self.price * self.fx_to_pln


@dataclass
class RankedCandidate:
    snapshot: MarketSnapshot
    score: float
    momentum_5d: float
    momentum_20d: float
    volatility_20d: float
    ma20: float


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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
