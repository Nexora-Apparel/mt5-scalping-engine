# VELTRIX XAUUSD scalping-engine: 10-phase execution roadmap

## Binding scope

- Instrument: XAUUSD only. XAGUSD, BTC, forex, indices, and all other instruments are excluded.
- Broker/account: Exness DEMO for current collection and validation.
- Current collectors, diagnostics, profiling, feature generation, and research are read-only.
- Preserve the existing GitHub repository, workflows, historical datasets, manifests, and credentials. Never commit credentials.
- No live/real-money trading. Any future order execution must be a separate, verified DEMO-only system with exact contract checks, strict risk limits, protective stops, emergency stop, broker reconciliation, and audit logs.
- Production deployment and scheduling remain disabled until Phase 10 release gates pass. Telegram integration/controller has been removed from project scope; do not reintroduce it.

## Phases and gates

1. **Market-data foundation and integrity certification — COMPLETE**
   - XAUUSD-only contract scope; bounded DEMO collection; immutable CSV/manifest integrity; offline profiling; independent non-overlapping session certification; verified feature-window generation.
   - Evidence: two certified Exness DEMO sessions; feature builder merged in PR #33; both certified datasets processed into 5-second windows; CI and post-merge checks passed.

2. **Causal feature and market-regime research — COMPLETE**
   - Build descriptive features; classify volatility/trend/direction/activity using trailing prior windows only; preserve warm-up and missing-data states; test no-lookahead invariance and provenance reconciliation.
   - Evidence: regime research merged in PR #34; 117 tests passed; two certified sessions classified independently with 330 windows each and explicit warm-up windows.

3. **Cross-session feature stability and research diagnostics — COMPLETE**
   - Compare independent sessions without pooling away session identity; report distributions, null coverage, correlations, and median drift; reject duplicate or overlapping sessions and incompatible schemas.
   - Evidence: cross-session diagnostics merged in PR #35; 124 tests passed; both certified sessions compared; session identity and source hashes retained.

4. **Strategy hypotheses and candidate specification — IN PROGRESS**
   - Freeze falsifiable XAUUSD-only hypotheses, entry context, direction, invalidation, 5–60 second evaluation horizons, and cost-aware outcomes before any candidate testing.
   - Gate: versioned pre-registration and validation of registry constraints; no threshold tuning on holdout data.

5. **Tick replay and deterministic research simulator**
   - Replay chronological bid/ask ticks; model spread-aware entries/exits, quote freshness, latency assumptions, and conservative execution constraints.
   - Gate: deterministic replay, timestamp integrity, no lookahead, and audited cost assumptions.

6. **Strategy implementation and MQL5 research integration**
   - Implement candidate analysis logic behind strict XAUUSD contract guards; keep collector and diagnostic workflows read-only; separate analysis from any order interface.
   - Gate: unit/integration tests, deterministic outputs, and no order path in research workflows.

7. **Risk engine and DEMO safety controls**
   - Implement risk-based sizing, maximum exposure, protective stops, loss limits, cooldowns, duplicate-order protection, emergency stop, and reconciliation.
   - Gate: fail-closed tests and verified DEMO account/contract identity; live trading remains disabled.

8. **Chronological walk-forward and robustness evaluation**
   - Use time-ordered train/validation/test partitions, untouched holdouts, multiple sessions/dates, cost sensitivity, and benchmark comparisons.
   - Gate: predeclared statistical and risk criteria pass; no retrospective threshold changes.

9. **Prospective Exness DEMO forward validation**
   - Conduct a separately authorized, monitored DEMO-only forward test after all earlier gates; reconcile every decision and any permitted demo order.
   - Gate: complete prospective sample, risk-control evidence, operational logs, and independent review. No live funds.

10. **Final hardening and controlled release**
    - Security review, configuration audit, recovery tests, observability, rollback, runbooks, and final release certification.
    - Gate: all prior evidence approved; only then may production deployment or scheduling be considered. Telegram remains out of scope unless explicitly re-authorized.

## Current status

- Phase 1: complete.
- Phase 2: complete.
- Phase 3: complete.
- Phase 4: in progress.
- Phases 5–10: locked until preceding phase gates pass.
