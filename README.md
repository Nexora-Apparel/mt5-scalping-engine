# MT5 Scalping Engine

A safety-first Python trading engine for an **Exness MT5 demo account** connected through MetaApi Cloud.

## Current status

This repository starts with the project scaffold and safety boundaries. It does not place trades yet.

- MetaApi account and demo connection are configured externally by the operator.
- Live trading is disabled by design.
- Order submission must not be enabled until market-data validation, strategy tests, risk controls, and demo execution tests pass.
- Never commit API tokens, broker credentials, account IDs, or private logs.

## Architecture

- `src/mt5_scalping/config.py` — environment configuration and fail-closed defaults.
- `src/mt5_scalping/health.py` — read-only health-check result model.
- `src/mt5_scalping/strategies/` — signal generation, separate from execution.
- `src/mt5_scalping/risk/` — position sizing and hard risk limits.
- `src/mt5_scalping/execution/` — execution adapter; no order submission is enabled in this scaffold.
- `tests/` — unit tests.

## Local setup

Python 3.11+ is recommended.

1. Create a virtual environment.
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and populate secrets locally.
4. Run tests: `pytest`

Do not put secrets in source code or commit the local `.env` file.

## Safety gates

Before any demo order can be enabled, the project must test:
- account identity and connection state;
- quote freshness and broker symbol mapping;
- spread and slippage limits;
- position sizing and broker volume constraints;
- stop-loss validation before entry;
- max open positions, cooldown, duplicate-order protection;
- daily loss and drawdown lockouts;
- emergency stop and persistent audit logging.

Live trading remains disabled until a separate review explicitly changes the deployment configuration.
