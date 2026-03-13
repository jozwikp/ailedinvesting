# AI-Led Investing

Experiments in investing guided by AI models.

## First experiment

The first experiment is a competition between AI models to determine which one can build a better decision-making environment and deliver better investment results. We will test different models, including Grok, Gemini, OpenAI, and at least one open-source model.

Each model receives the same starting capital, the same time horizon, and the same operating constraints. The goal is to compare both investment outcomes and the quality of the decision process under controlled conditions.

## Experiment objective

The model must grow a starting portfolio of `1000 PLN` over a fixed investment period.

The primary objective is to maximize final portfolio value. Secondary evaluation criteria are used to compare risk, consistency, and decision quality.

## Core task

On each decision cycle, the model must:

1. Analyze the current portfolio, market conditions, and available historical data.
2. Decide whether to `BUY`, `SELL`, or `KEEP` each relevant position.
3. Produce structured investment decisions in the required format.
4. Record reasoning, decisions, and the current portfolio state in the required log files.
5. Stay within all portfolio, execution, and risk constraints.

The model may ask the user to provide approved APIs, market data, portfolio snapshots, or other inputs needed to make decisions. The model must not rely on future information, hindsight, or retroactive changes to previously logged decisions.

## Required decision output

Each investment decision must be provided in the following format:

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

Rules for the output:

- `datetime` must use ISO 8601 format.
- `ticker` must match the instrument identifier used by the broker or data source.
- `action` must be one of `BUY`, `SELL`, or `KEEP`.
- `price` must be the intended execution price at the time of the decision.
- `quantity` must be a positive numeric value. For `KEEP`, quantity may be omitted or set to the current position size.
- `reason` must briefly explain why the action is recommended.
- `risk_level` must describe the expected risk of the position.
- `invalidation` must define the condition that weakens or invalidates the idea.

## Required logs

The model must maintain the following files:

- `reasoning.md`: a timestamped record of each decision cycle, including market context, portfolio context, reasoning, rejected alternatives, and final decisions.
- `transactions.md`: a timestamped record of each proposed trade, whether it was executed or skipped, including ticker, action, proposed price, actual execution result, quantity, and short notes.
- `current_portfolio.md`: the latest snapshot of the portfolio, including available cash, open positions, average entry prices, current market prices if available, unrealized PnL if available, and total portfolio value.

Past entries in these files must not be edited after the cycle is complete, except to append the real execution result or a correction note.

## Allowed instruments

The model may trade only instruments from the following categories:

- Stocks
- ETFs
- Forex CFDs
- Index CFDs
- Commodity CFDs
- Cryptocurrency CFDs

The reference list of available instruments is:
[XTB instrument specification](https://www.xtb.com/pl/specyfikacja-instrumentow)

## Investment rules

- Starting capital: `1000 PLN`
- Base currency: `PLN`
- Investment horizon: `1 month` from the official experiment start date
- Decision frequency: defined by the model before the experiment starts
- Market data refresh frequency: defined by the model before the experiment starts
- The model may hold cash and is not required to stay fully invested
- The model is free to choose instruments from the allowed list
- Minimum diversification: at least `2 instruments` unless the model explicitly justifies a concentrated position
- Leverage above `20%` should be avoided
- The model's only primary goal is to grow capital while respecting these rules

## Execution rules

- The user executes the orders provided by the model after each decision cycle.
- An order is considered executable only if the market price is within `+/- 2%` of the proposed price.
- If the market price moves outside that range, the order is skipped.
- After trade execution or skipped execution, the user provides an updated account statement for the next cycle.
- After each cycle, `current_portfolio.md` must be updated to reflect the latest known portfolio state.
- If the market is closed, the order is skipped unless the model explicitly states that delayed execution is acceptable.
- The model may not revise a cycle's decisions after they are logged. Any new decision must be made in the next cycle.
