"""Strategy parameters for Opus 4.6 investment decision engine."""

STRATEGY = {
    # --- Scoring weights (sum to ~1.0) ---
    "w_momentum_20d": 0.35,
    "w_momentum_5d": 0.15,
    "w_rsi_signal": 0.20,
    "w_trend_bonus": 0.15,
    "w_volatility_penalty": 0.15,

    # --- RSI thresholds ---
    "rsi_oversold": 35,
    "rsi_overbought": 70,

    # --- Position sizing ---
    "target_position_pct": 0.25,
    "max_position_pct": 0.35,
    "risk_per_trade_pct": 0.05,
    "atr_risk_multiplier": 2.0,
    "cash_reserve_pct": 0.10,

    # --- Portfolio limits ---
    "max_positions": 4,
    "min_positions": 2,

    # --- Sell triggers ---
    "hard_stop_pct": 0.08,
    "trailing_stop_atr_mult": 2.5,
    "score_sell_threshold": -0.01,

    # --- Buy filters ---
    "min_buy_score": 0.01,
    "min_data_bars": 25,

    # --- Data ---
    "history_period": "90d",

    # --- Allowed asset classes for buying ---
    "buyable_classes": [
        "stock", "etf", "index_cfd",
        "commodity_cfd", "forex_cfd", "crypto_cfd",
    ],
}

# Instrument universe: (xtb_ticker, yfinance_symbol, asset_class, quote_currency)
UNIVERSE = [
    # US Stocks (fractional on XTB)
    ("AAPL.US_9", "AAPL", "stock", "USD"),
    ("MSFT.US_9", "MSFT", "stock", "USD"),
    ("NVDA.US_9", "NVDA", "stock", "USD"),
    ("AMZN.US_9", "AMZN", "stock", "USD"),
    ("META.US_9", "META", "stock", "USD"),
    ("GOOG.US_9", "GOOG", "stock", "USD"),
    ("TSLA.US_9", "TSLA", "stock", "USD"),
    # EU Stocks
    ("CDR.PL_9", "CDR.WA", "stock", "PLN"),
    ("PKO.PL_9", "PKO.WA", "stock", "PLN"),
    # ETFs
    ("VUSA.UK_9", "VUSA.L", "etf", "GBP"),
    ("CSPX.UK_9", "CSPX.L", "etf", "USD"),
    # Index CFDs
    ("US500", "^GSPC", "index_cfd", "USD"),
    ("US100", "^NDX", "index_cfd", "USD"),
    ("DE40", "^GDAXI", "index_cfd", "EUR"),
    ("W20", "WIG20.WA", "index_cfd", "PLN"),
    # Commodity CFDs
    ("GOLD", "GC=F", "commodity_cfd", "USD"),
    ("SILVER", "SI=F", "commodity_cfd", "USD"),
    ("OIL.WTI", "CL=F", "commodity_cfd", "USD"),
    ("NATGAS", "NG=F", "commodity_cfd", "USD"),
    # Forex CFDs
    ("EURUSD", "EURUSD=X", "forex_cfd", "USD"),
    ("USDPLN", "PLN=X", "forex_cfd", "PLN"),
    ("EURPLN", "EURPLN=X", "forex_cfd", "PLN"),
    # Crypto CFDs
    ("BITCOIN", "BTC-USD", "crypto_cfd", "USD"),
    ("ETHEREUM", "ETH-USD", "crypto_cfd", "USD"),
]
