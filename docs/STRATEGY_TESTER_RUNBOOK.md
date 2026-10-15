# NexoraScalper Strategy Tester runbook

This is a research checklist, not a profitability claim. The current 9/21 EMA crossover is provisional and has not yet been backtested.

## Prerequisites

- MT5 desktop terminal running on a Windows or x86_64 Linux/Wine host.
- A connected **demo** account and downloaded history for the exact broker symbol.
- Current `NexoraScalper.ex5` compiled from the current `main` source.
- Use the broker's exact symbol name (for example, `EURUSD`, `EURUSDm`, or another broker-specific suffix). Do not assume the name.

## Baseline test

1. Open **View → Strategy Tester** and select `NexoraScalper`.
2. Select the exact broker symbol and the timeframe you intend to evaluate. Start with M1 only if that is the intended operating timeframe.
3. Select **Every tick based on real ticks** when the broker provides adequate tick history. Otherwise record the model used and treat results as lower confidence.
4. Set a historical range with both in-sample and out-of-sample periods. Do not choose dates only because they make results look good.
5. Set the test deposit, account currency, and leverage to realistic values. Include the broker's spread, commission, and swap assumptions.
6. In **Strategy Tester inputs only**, set `EnableDemoOrders=true` and `EmergencyStop=false` to allow simulated orders. These are test inputs; do not apply them to a live terminal. The EA's source defaults remain fail-closed.
7. Run the test once without optimization and save the full report and journal.

## Review the report

Record at least:

- Total trades and trades per month
- Net profit after costs
- Profit factor and expected payoff per trade
- Maximum balance drawdown and maximum equity drawdown
- Long/short split, average win/loss, largest loss, and consecutive losses
- Sensitivity to spread, commission, and slippage assumptions
- Whether performance remains positive in an untouched out-of-sample period

Reject the strategy if results depend on a small number of trades, disappear after realistic costs, or show unstable out-of-sample performance. A profitable historical report still does not guarantee future results.

## Risk and demo gates

- Keep risk per trade at or below the EA's 0.25% default while researching.
- The daily-loss gate uses a reconstructed server-day opening balance from account history and compares it with current equity. If history cannot be selected or a valid baseline cannot be established, the EA blocks entries.
- Verify stop-loss/target distances, volume steps, filling mode, spread limits, and duplicate-position behavior for the actual broker symbol.
- After an acceptable backtest, run a demo forward test and inspect terminal/journal logs. Keep the emergency stop ON except during an explicitly supervised demo test.
- Never use a real account as a test environment. Do not enable live trading based on compilation or a single backtest.
