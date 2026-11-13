# MT5 Scalping Engine

VELTRIX is an Exness MT5 research and scalping system with a strict **XAUUSD-only** instrument policy. Current research and collection workflows are offline/read-only; bounded Windows GitHub Actions sessions provide the temporary MT5 terminal.

## Active instrument policy

- XAUUSD is the only instrument permitted for market-data collection, feature generation, AI/strategy analysis, signal research, risk evaluation, and future demo execution.
- Broker suffixes such as `XAUUSDm` are accepted only after contract metadata verifies base currency XAU and profit currency USD.
- XAGUSD, other metals, forex, crypto, indices, and synthetic instruments are out of scope.
- Existing silver datasets are retained as historical archives but are not eligible for active research or certification.
- See [docs/INSTRUMENT_SCOPE.md](docs/INSTRUMENT_SCOPE.md) for the binding rule.

## Current engineering status

- The current active EA foundation is read-only. It collects market health and optional point-in-time research features; it does not submit, modify, or close orders.
- Python diagnostics and the bounded DEMO collector use the official MetaQuotes Python integration.
- Tick data is hashed, audited, profiled, and can be aggregated across independent sessions. These checks establish data integrity only, not profitability or execution readiness.
- The prior dual-instrument collection run is not a valid XAUUSD-only session.
- Live trading is prohibited. Future execution must be separately implemented and validated on a verified Exness DEMO account, with exact XAUUSD contract checks, risk limits, protective stops, emergency stop, and broker reconciliation.

## Safety gates

Before any demo order testing, validate account identity, XAUUSD broker contract mapping, quote freshness, spread/slippage limits, risk-based sizing, broker volume constraints, protective stops, order preflight, position limits, cooldown, duplicate-order protection, daily equity-loss lockout, emergency stop, and audit logs.

Never commit credentials, tokens, account IDs, or private logs.
Phase 6 candidate analysis implementation and safety contract: [docs/PHASE6_XAUUSD_CANDIDATE_ANALYSIS.md](docs/PHASE6_XAUUSD_CANDIDATE_ANALYSIS.md).
Phase 7 DEMO risk controls and safety policy: [docs/PHASE7_DEMO_RISK_CONTROLS.md](docs/PHASE7_DEMO_RISK_CONTROLS.md).
