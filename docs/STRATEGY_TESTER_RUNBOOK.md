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
- Once the daily loss threshold is reached, the EA latches the lockout until the next broker-server day, even if equity subsequently recovers. In Strategy Tester, the latch is isolated from terminal global variables and resets when the simulated server day changes.
- Verify stop-loss/target distances, volume steps, filling mode, spread limits, and duplicate-position behavior for the actual broker symbol.
- After an acceptable backtest, run a demo forward test and inspect terminal/journal logs. Keep the emergency stop ON except during an explicitly supervised demo test.
- Never use a real account as a test environment. Do not enable live trading based on compilation or a single backtest.

## Account-balance range

- `MinimumEquityUSD` defaults to USD 10. The EA blocks new entries whenever current equity is below this threshold.
- There is no EA-imposed maximum account balance. Position sizing remains percentage-based and adapts to current equity; broker maximum volume, available margin, symbol rules, and configured risk limits still constrain actual trades. “No maximum balance” does not mean unlimited lot size or unlimited risk.
- A balance above USD 10 does not guarantee that a trade is feasible. If the minimum broker volume would exceed the risk budget or margin is insufficient, the EA must skip the trade.

## Small-balance compatibility test (Deriv XAUUSD)

The EA has an experimental small-balance profile for **Strategy Tester/demo research only**:
- It activates at or below the configured equity threshold (default USD 100).
- It uses current equity for per-trade sizing so the risk budget adapts as equity changes.
- Defaults are 0.5% risk, 40-point stop, 60-point target, and a 20-point spread ceiling. The risk budget may be too small for Deriv's minimum volume, in which case the EA must skip the trade. This is a demo-research setting, not a live-trading recommendation.
- On the user's reported XAUUSD specification (2 digits, 0.01 minimum volume, 20-point spread shown, 20-point stop level), the stop is only eligible when the actual spread and stop-level checks pass. If spread rises above the profile ceiling, the EA must skip the entry.
- The EA checks estimated loss with `OrderCalcProfit` after rounding volume. If minimum volume exceeds the configured monetary risk budget, it skips the trade. Margin/preflight checks can also reject it.
- The profile does not promise trades or profitability. At a simulated USD 10 equity, a 0.5% risk budget is only USD 0.05; if the minimum 0.01 lot's calculated stop loss is larger than that, the EA must skip the trade. Do not increase risk merely to force trades. If broker spread, stop rules, or margin make the trade infeasible, skipping is the correct behaviour.

Test with a **USD 10 test deposit** and the exact Deriv demo XAUUSD symbol, ideally using real ticks. Confirm actual tick value, spread, stops level, order rejection reasons, drawdown, and performance after costs. Keep source defaults `EnableDemoOrders=false` and `EmergencyStop=true`; only change those inputs inside a supervised Strategy Tester run. Live-account execution is blocked by the EA's account-mode gate.
