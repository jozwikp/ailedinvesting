# GPT-5.4 Investment Strategy

## Experiment Scope

- Model: `gpt-5.4`
- Base currency: `PLN`
- Starting capital: `1000 PLN`
- Investment horizon: `1 month`
- Official experiment start: first live decision cycle timestamp
- Primary objective: maximize final portfolio value within the experiment rules

## Decision Cadence

- Primary decision cycle: once per trading day
- Default decision time: `15:45 Europe/Warsaw`
- Weekend cadence: no routine cycle unless managing open CFD risk or a crypto CFD position
- Emergency review: allowed outside the normal cadence only after a user-provided execution update or material market event

## Market Data Cadence

- Primary refresh: `15 minutes` before the decision cycle
- Final quote check: immediately before publishing decisions
- Portfolio truth refresh: after the user provides the post-cycle CSV, statement, or execution update

## Approved Data Sources

- Primary market-data source: `Yahoo Finance` via `yfinance`
- Broker compatibility source: XTB instrument specification and broker-visible instrument names
- Execution truth source: user-provided CSV, account statement, or explicit execution summary
- If broker and public-market symbols differ, the final JSON decision must use the broker-compatible ticker

## Portfolio Construction Rules

- Target active positions: `2-4`
- Minimum diversification: at least `2 instruments` unless concentration is explicitly justified in `reasoning.md`
- Default stance: long bias with cash allowed
- Default asset preference:
  1. liquid stocks
  2. liquid ETFs
  3. index CFDs
  4. commodity CFDs
  5. forex CFDs
  6. cryptocurrency CFDs
- Single-position target size: `20-35%` of portfolio value
- Initial entries should preserve at least `10%` cash unless a higher-conviction deployment is documented

## Risk Rules

- Avoid leverage above `20%`
- Default operating mode is unlevered or near-unlevered exposure
- Gross exposure should normally remain at or below `100%` of equity
- Any use of CFDs must keep effective leverage conservative and explicitly state the invalidation condition
- No averaging down without a new thesis documented in the next cycle
- Every `BUY` decision must include:
  - a clear catalyst or setup
  - a time horizon
  - a concrete invalidation condition

## Execution Rules

- Orders are intended for the current cycle only unless delayed execution is explicitly allowed
- If the market price is outside the `+/- 2%` band of the proposed price, the order is skipped
- If the market is closed, the order is skipped unless the decision explicitly states that delayed execution is acceptable
- Skipped trades must still be recorded in `transactions.md`

## Symbol Discipline

- `symbol_map.csv` is the source of truth for broker ticker to market-data ticker mapping
- The default active universe should prioritize popular liquid instruments across stocks, ETFs, and crypto
- Do not issue a trade for a new instrument until its symbol mapping has been added or confirmed
- Instrument identifiers in final decisions must match the identifier the user can execute with their broker

## Cycle Output Standard

Each live cycle must produce:

1. Structured JSON decisions for each relevant instrument
2. A timestamped reasoning entry in `reasoning.md`
3. Proposed-trade records in `transactions.md`
4. A refreshed portfolio snapshot in `current_portfolio.md`

## User Input Contract

Each cycle should be based on the latest user-provided:

- available cash
- open positions
- average entry prices
- execution results for prior orders
- fees or financing charges if any
- current quotes or a broker/account statement when available
