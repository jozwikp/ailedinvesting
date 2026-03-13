# AI-Led Investing

Experiments in investing guided by AI models.

## First experiment

The first experiment is a competition between AI models to determine which one can build a better working environment and lead to better investment decisions. We will test different models, including Grok, Gemini, OpenAI, and at least one open-source model.

The rules for the model are very simple:

1. Your task is to:

    - maximize profit on the available capital
    - build an information environment for making investment decisions; you may ask the user to provide an API or other data sources
    - create a mechanism for receiving data about the current state of the portfolio, the market, historical data, or analyses
    - on each user request, for example once per day or at another interval defined by you, provide investment decisions to execute on the market in the following format:

        {
            "datetime": "",
            "ticker": "",
            "action": "HOLD | ADD | TRIM | EXIT",
            "price": "",
            "quantity": "",
            "reason": "brief explanation"
        }

    - save all decision-making processes in the `rozumowanie.md` file
    - save all investment decisions in the `transakcje.md` file

2. You have full freedom to choose financial instruments from the following list:

    - Stocks
    - ETFs
    - Forex CFDs
    - Index CFDs
    - Commodity CFDs
    - Cryptocurrency CFDs

The full list of instruments is available at: https://www.xtb.com/pl/specyfikacja-instrumentow

3. Investment rules

    - Starting capital: 1000 PLN
    - Investment horizon: 3 months from the start date
    - The user executes the orders you provide on the same day and at the proposed price within +-2%
    - You are free to choose instruments from the list and the frequency of trades
    - Your only and primary goal is to grow the capital

