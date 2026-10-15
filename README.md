# MT5 Scalping Engine

A safety-first experimental trading project for an Exness MT5 demo account.

## Current status

- A read-only MetaApi diagnostic exists, but its first run failed because the MetaApi account was undeployed and the dashboard requested a balance top-up.
- A direct MT5 Expert Advisor has been added as a potential route that does not require MetaApi.
- The EA uses a provisional 9/21 EMA crossover for controlled research only. This is not a validated profitable strategy.
- Order submission is disabled by default and the emergency stop defaults to ON.
- The EA has **not** yet been compiled in MetaEditor or tested in MT5 Strategy Tester.
- Live trading is not approved.

## Choose a connection route

1. **MetaApi Cloud:** requires an account deployment and may incur balance/usage charges.
2. **Direct MT5 desktop EA:** avoids MetaApi, but requires a Windows computer with MT5 desktop installed and online. Android alone cannot run the desktop EA continuously.

See [docs/NO_COST_MT5_ROUTE.md](docs/NO_COST_MT5_ROUTE.md) for limitations and the validation sequence.

## Python project

- `src/mt5_scalping/config.py` — environment configuration with fail-closed defaults.
- `src/mt5_scalping/health.py` — read-only health-check result model.
- `scripts/check_metaapi.py` — read-only MetaApi diagnostic; never submits orders.
- `tests/` — Python unit tests.

## Safety gates

Before demo order testing, validate account identity, broker symbol mapping, quote freshness, spread/slippage limits, risk-based sizing, broker volume constraints, SL/TP placement, max positions, cooldown, duplicate-order protection, daily equity-loss lockout, emergency stop, and audit logs.

Never commit credentials, tokens, account IDs, or private logs.
