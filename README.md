# MT5 Scalping Engine

A safety-first experimental trading project for an Exness MT5 demo account.

## Current status

- A read-only MetaApi diagnostic exists, but its first run failed because the MetaApi account was undeployed and the dashboard requested a balance top-up.
- A direct MT5 Expert Advisor has been added as a potential route that does not require MetaApi. It uses native MQL5 order requests and compiles without an external Trade.mqh dependency.
- The EA uses a provisional 9/21 EMA crossover for controlled research only. This is not a validated profitable strategy.
- Order submission is disabled by default and the emergency stop defaults to ON.
- The current EA source compiled successfully in MetaEditor on 2026-10-15: **0 errors, 0 warnings**. The compiled `.ex5` is available for 14 days from the [latest successful compile run](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/38770182819); open the run and download the `NexoraScalper-compiled` artifact.
- The daily equity-loss lockout now latches after a breach until the next broker-server day, including a separate in-memory lock in Strategy Tester.
- The EA has **not** yet been run in MT5 Strategy Tester or demo-forward-tested.
- No persistent cloud terminal has been provisioned yet. Live trading is not approved.

## Choose a connection route

1. **MetaApi Cloud:** requires an account deployment and may incur balance/usage charges.
2. **Direct MT5 desktop EA:** avoids MetaApi, but requires a desktop terminal to remain online. Android alone cannot run the desktop EA.
3. **Experimental Oracle Always Free route:** [docs/ORACLE_CLOUD_SETUP.md](docs/ORACLE_CLOUD_SETUP.md) and [scripts/bootstrap_mt5_linux.sh](scripts/bootstrap_mt5_linux.sh) describe an unverified x86_64 Linux/Wine setup. It requires manual Oracle account/VM provisioning and is not guaranteed to be stable or available.

See [docs/NO_COST_MT5_ROUTE.md](docs/NO_COST_MT5_ROUTE.md) for limitations, [docs/ORACLE_CLOUD_SETUP.md](docs/ORACLE_CLOUD_SETUP.md) for the experimental free-cloud route, and [docs/STRATEGY_TESTER_RUNBOOK.md](docs/STRATEGY_TESTER_RUNBOOK.md) for the backtest procedure.

## Python project

- `src/mt5_scalping/config.py` — environment configuration with fail-closed defaults.
- `src/mt5_scalping/health.py` — read-only health-check result model.
- `scripts/check_metaapi.py` — read-only MetaApi diagnostic; never submits orders.
- `tests/` — Python unit tests.

## Safety gates

Before demo order testing, validate account identity, broker symbol mapping, quote freshness, spread/slippage limits, risk-based sizing, broker volume constraints, SL/TP placement, order preflight checks, max positions, cooldown, duplicate-order protection, daily equity-loss lockout, emergency stop, and audit logs.

Never commit credentials, tokens, account IDs, or private logs.
