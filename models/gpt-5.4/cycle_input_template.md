# Cycle Input Template

Use this template for each live decision cycle.

## Required Inputs

- Cycle timestamp in ISO 8601
- Available cash in `PLN`
- Open positions with ticker, quantity, average entry price, and current price if available
- Previous cycle execution results with executed price, skipped status, fees, and notes
- Latest broker statement, CSV, or manual account summary

## Preferred Input Format

```md
datetime: 2026-03-13T15:45:00+01:00

cash_pln: 1000.00

positions:
- ticker: 
  quantity: 
  average_entry_price: 
  current_price: 
  market_value_pln: 
  unrealized_pnl_pln: 

execution_updates:
- ticker: 
  action: 
  proposed_price: 
  actual_status: executed | skipped
  actual_price: 
  quantity: 
  fees_pln: 
  notes: 

statement_source:
- type: csv | broker_statement | manual_summary
- timestamp: 
- notes: 
```

## Output Produced Each Cycle

1. JSON decision objects in the required schema
2. A new reasoning entry appended to `reasoning.md`
3. New trade records appended to `transactions.md`
4. A refreshed snapshot in `current_portfolio.md`

## Decision JSON Schema

```json
{
  "datetime": "2026-03-13T09:00:00Z",
  "ticker": "AAPL",
  "action": "BUY | SELL | KEEP",
  "price": 210.5,
  "quantity": 2,
  "reason": "Brief explanation of the decision.",
  "risk_level": "low | medium | high",
  "invalidation": "Condition under which the trade idea is no longer valid."
}
```

## Notes

- If a new instrument is introduced, confirm or add its broker-to-data symbol mapping in `symbol_map.csv` first
- If execution is outside the allowed `+/- 2%` range, the trade will be logged as skipped
- If the market is closed, the order will be skipped unless delayed execution is explicitly allowed in the decision
