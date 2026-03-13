# Opus 4.6 Investment Strategy

## Experiment Scope

- Model: `opus-4.6`
- Base currency: `PLN`
- Starting capital: `1000 PLN`
- Investment horizon: `1 month` from the official experiment start date
- Primary objective: maximize final portfolio value within experiment rules

## Decision Cadence

- Primary decision cycle: **once per trading day**
- Default decision time: `16:00 Europe/Warsaw` (captures European session close context and US session opening momentum)
- Weekend cycles: none, unless managing open CFD/crypto positions with material overnight risk
- Emergency review: allowed outside normal cadence only after a user-provided execution update that materially changes portfolio state, or a significant market event (>3% move in a core holding)

## Market Data Refresh

- Pre-decision refresh: `15 minutes` before the decision cycle
- Final quote check: immediately before publishing decisions
- Portfolio state refresh: after the user provides post-cycle execution results

## Approved Data Sources

- Market data: user-provided quotes, publicly available financial data, web search for current prices
- Broker instrument reference: XTB instrument specification (https://www.xtb.com/pl/specyfikacja-instrumentow)
- Execution truth: user-provided account statement, CSV, or explicit execution summary
- Symbol mapping: `symbol_map.csv` in this directory

## Investment Philosophy

Given the 1-month horizon and 1000 PLN capital:

1. **Momentum-tilted tactical allocation**: favor instruments showing clear short-term momentum with identifiable catalysts
2. **Asymmetric risk/reward**: prefer setups where potential upside exceeds downside by at least 2:1
3. **Capital preservation priority in week 1**: build positions gradually, avoid deploying more than 60% of capital in the first cycle
4. **Flexible exit**: be willing to cut losses early and let winners run
5. **Macro-aware**: consider prevailing macro conditions (rates, sentiment, geopolitical) when selecting instruments

## Portfolio Construction Rules

- Target active positions: `2-4` instruments
- Minimum diversification: at least `2 instruments` unless concentration is explicitly justified in reasoning.md
- Single-position target size: `20-35%` of portfolio value
- Maximum single-position size: `50%` of portfolio value (requires high-conviction justification)
- Maintain at least `10%` cash reserve in first two weeks; may deploy fully in final stretch if warranted
- Default stance: long bias with tactical flexibility

## Asset Preference Order

1. Liquid stocks (US large-cap, EU blue chips)
2. Broad market ETFs
3. Index CFDs (for tactical macro bets)
4. Commodity CFDs (gold, oil for hedging or momentum)
5. Forex CFDs (only for clear directional macro trades)
6. Cryptocurrency CFDs (small tactical positions only, high volatility awareness)

## Risk Rules

- Avoid leverage above `20%` of portfolio value
- Default mode: unleveraged or near-unleveraged
- Gross exposure should remain at or below `100%` of equity under normal conditions
- Per-trade risk budget: no single trade should risk more than `5%` of total portfolio value
- Every `BUY` decision must include: a clear thesis, a time horizon, and a concrete invalidation condition
- No averaging down without a new thesis documented in the next cycle
- Stop-loss discipline: mental stop at invalidation level; if price hits invalidation, SELL in next cycle

## Execution Rules

- Orders are for the current cycle only unless delayed execution is explicitly allowed
- Market price must be within `+/- 2%` of the proposed price for execution
- If the market is closed, the order is skipped unless delayed execution is explicitly stated
- Skipped trades are recorded in `transactions.md` with skip reason
- The model may not revise a cycle's decisions after they are logged

## Symbol Discipline

- `symbol_map.csv` is the source of truth for broker-to-market ticker mapping
- No trade is issued for a new instrument until its symbol mapping has been confirmed
- Decision JSON uses the XTB broker ticker

## Cycle Output Standard

Each decision cycle produces:

1. Structured JSON decisions for each relevant instrument
2. A timestamped reasoning entry in `reasoning.md`
3. Proposed-trade records in `transactions.md`
4. A refreshed portfolio snapshot in `current_portfolio.md`

## User Input Contract

Each cycle relies on user-provided:

- Available cash balance
- Open positions with quantities
- Average entry prices
- Execution results for prior orders (filled, partially filled, skipped)
- Fees or financing charges if applicable
- Current quotes or broker account statement
