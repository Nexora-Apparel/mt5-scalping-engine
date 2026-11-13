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
   - Evidence: cross-session diagnostics merged in PR #35; 124 tests passed; two certified sessions processed into 721 five-second windows (12,838 source ticks). Provenance hashes, distributions, null coverage, descriptive correlations, and median drift are recorded in `docs/PHASE3_XAUUSD_CROSS_SESSION_REPORT.md`. Median spread was 240 points (0.240 price units), a material cost constraint for short-horizon scalping.

4. **Strategy hypotheses and candidate specification — COMPLETE**
   - Freeze falsifiable XAUUSD-only hypotheses, entry context, direction, invalidation, 5–60 second evaluation horizons, and cost-aware outcomes before any candidate testing.
   - Evidence: PRs #40 and #41 merged; the fail-closed registry and exact past-only formulas passed 143 tests. Three finite candidate families are frozen with 5/15/30/60-second horizons, quote-crossed outcome rules, cost requirements, and chronological holdout/purge controls. Commission remains unverified; no net-performance pass is permitted.

5. **Tick replay and deterministic research simulator — COMPLETE**
   - Replay chronological bid/ask ticks; model spread-aware entries/exits, quote freshness, latency assumptions, and conservative execution constraints.
   - Evidence: PR #42 merged; 153 tests passed. Historical replay workflow #43378951998 rebuilt features and diagnostics from both certified artifacts, then produced 8/8 synthetic quote-replay smoke outcomes with zero entry/exit timeouts. The evidence artifact is [14015811691](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/43378951998/artifacts/14015811691). Replay confirmed XAUUSD DEMO provenance, Ask/Bid quote crossing, spread included once, no orders or actual-fill claims, and null net-after-commission. Both sessions remain development-only, not holdout.

6. **Strategy implementation and MQL5 research integration — COMPLETE**
   - Implement candidate analysis logic behind strict XAUUSD contract guards; keep collector and diagnostic workflows read-only; separate analysis from any order interface.
   - Evidence: PR #47 passed 172 Python tests; MQL5 compile reported 0 errors and 0 warnings across four configured targets; certified Sessions 8 and 9 passed provenance-checked candidate smoke generation (10,652 generated research events across 719 completed windows). Final partial windows were excluded. The bounded MQL5 five-second adapter is opt-in and journal-only. See `docs/PHASE6_XAUUSD_CANDIDATE_ANALYSIS.md`.
   - Limitation: live terminal runtime behavior remains untested; generated events are not trade outcomes or evidence of predictive edge. No execution authorization is implied.

7. **Risk engine and DEMO safety controls — IN PROGRESS**
   - Implement risk-based sizing, maximum exposure, protective stops, loss limits, cooldowns, duplicate-order protection, emergency stop, and reconciliation.
   - Current implementation: `RiskControls.mqh` adds exact DEMO login/server and XAUUSD contract checks, hard risk ceilings (0.25% per trade, 0.50% aggregate, 1.00% daily equity loss), one-position policy, daily lock, verified-close loss streak/cooldown, duplicate request IDs and closing-deal deduplication through the append-only checksum-chained `RiskJournal.mqh`; account/server-scoped terminal state persists the daily baseline, daily lock, loss streak, cooldown, and emergency-stop latch, with a last-written checksum marker and persistent compare-and-set lock to serialize close accounting across EA instances. `ExecutionGuard.mqh` now independently requires exact DEMO identity and verified XAUUSD metadata before its non-submitting preflight. See `docs/PHASE7_DEMO_RISK_CONTROLS.md`.
   - Remaining gates: tests and compile on final PR head; desktop MT5 runtime execution of `RiskJournalRuntimeTest.mq5`, controlled MT5 restart and abandoned-lock recovery, storage-failure tests, and a durable append-only risk/execution journal; independent review of broker runtime behavior. No order path is wired or authorized.

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
- Phase 4: complete.
- Phase 5: complete.
- Phase 6: complete.
- Phase 7: in progress.
- Phases 8–10: locked until preceding phase gates pass.
