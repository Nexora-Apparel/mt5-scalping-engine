# Android-operated MT5 cloud session

## Current milestone: Exness demo connectivity only

The workflow `.github/workflows/exness-demo-connectivity.yml` starts a temporary Windows GitHub-hosted runner, installs the generic MetaTrader 5 terminal, and attempts to authenticate to the supplied Exness MT5 demo server.

It is intentionally **not a trading workflow**:

- It does not install or attach an Expert Advisor.
- It disables Expert Advisors and automated trading in the terminal configuration.
- It does not submit, modify, or close orders.
- It stops the terminal and removes the temporary configuration file before the job ends.
- It reports success only when a terminal log contains an account authorization event and the terminal remains alive for a further 30 seconds.

A successful result proves only that this runner can authenticate to the configured account/server. It does not prove quote quality, order execution, strategy performance, or readiness for live trading.

## Android setup after this change is merged

In the GitHub repository, open **Settings → Secrets and variables → Actions → New repository secret**. Create these three secrets:

| Secret name | Value |
|---|---|
| `MT5_LOGIN` | Numeric MT5 demo account login |
| `MT5_PASSWORD` | The demo account's MT5 trading/master password |
| `MT5_SERVER` | Exact server name shown in the Exness MT5 account details |

Do not put these values in workflow inputs, source files, issue comments, or chat messages. Never use an investor/read-only password for a later trading session.

Then open **Actions → Exness MT5 demo connectivity check → Run workflow**. Select the default branch after the workflow has been merged. Review the run summary; the workflow intentionally does not print the credentials or account balance.

## Constraints and safety gates

- This workflow uses a temporary GitHub-hosted Windows machine. Android is the control device; MT5 itself runs on the hosted Windows machine, not on Android.
- GitHub documents a six-hour maximum execution time per GitHub-hosted job. A future two-hour session is below that platform limit, but the limit is not a promise of uninterrupted broker connectivity.
- Public-repository GitHub Actions jobs have no billable execution minutes under GitHub's published guidance. Availability, concurrency, fair-use rules, and GitHub policy still apply.
- The first connection test must pass before building a timed demo session.
- The current `NexoraScalper.mq5` is a provisional EMA-cross EA, not certified for execution. It currently blocks a second same-symbol position and does not implement the requested 10–60 second per-position lifecycle. It must be redesigned and tested before any demo-order session.
- Multi-position same-symbol operation requires an MT5 hedging account. A netting account cannot represent multiple independent positions on one symbol.
- A small account balance does not justify forcing minimum lot size. If broker minimum volume exceeds the configured risk budget or available margin, the EA must reject the trade.
- Live trading remains out of scope until separate strategy, execution, risk, and operational validation is complete.

## Failure handling

If the workflow cannot confirm authorization, first verify the exact server string and that the credentials belong to an MT5 demo account. Do not paste credentials into logs or support messages. A failed connectivity check must not be bypassed by enabling automated trading.
