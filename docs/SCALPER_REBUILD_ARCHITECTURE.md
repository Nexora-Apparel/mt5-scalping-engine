# VELTRIX MT5 Scalper — Rebuild Architecture

## Status

Architecture baseline only. The existing `NexoraScalper.mq5` is a legacy prototype and is **not approved for demo or live order execution**. Keep order submission disabled while the replacement is built and validated.

The Exness connectivity workflow is a separate infrastructure check. A successful login does not validate a trading strategy or authorize trading.

All merged foundation modules have passed their respective MetaEditor compile and Project Tests gates: read-only market health, fail-closed risk allocation, position lifecycle tracking, demo-only execution preflight, read-only broker reconciliation, state-only execution coordination, the research-only XAUUSD/XAGUSD strategy evaluator, and the point-in-time feature collector. These gates establish compilation and source/reference test coverage, not live broker runtime correctness or strategy profitability. The current increment adds `FeatureDatasetExporter.mqh`, a versioned CSV writer for caller-supplied feature snapshots. It validates source provenance, exact instrument, timestamp order, numeric feature bounds, and safe file names; it also verifies an existing CSV header before appending to prevent mixed-schema datasets. The exporter is included for compilation but is not instantiated or activated by the EA. MT5 terminal file I/O still requires its separate runtime test. Demo/live trading remains disabled.

## Product constraints

- Android is the operator/control device; MT5 runs on a temporary Windows GitHub-hosted runner during a manually started session.
- No always-on service is required. A session is explicitly started and stopped by the operator, with a hard maximum session duration of two hours for the first implementation.
- Broker/platform: Exness MT5.
- Initial instruments: XAUUSD and XAGUSD, using the exact broker symbol names and contract specifications discovered at runtime.
- Intended position holding time: 10–60 seconds. This is a target execution horizon, not a promise that every trade can close within that time during disconnection, market closure, or broker rejection.
- Multiple independently managed positions require an MT5 hedging account. On a netting account, same-symbol positions merge into one net position; the engine must detect this and disable independent same-symbol concurrency.
- A small account (including a $10 account) may not satisfy the broker's minimum volume, margin, stop-distance, or risk constraints. If risk-sized volume is below minimum volume, skip the trade. Never round volume upward to force an entry.
- Demo-only until explicit certification gates are passed. Live execution remains disabled.

## Existing prototype audit

The current EA has several useful fail-closed controls, but it does not implement the requested product:

1. It evaluates entries only on a new chart bar, not on a sub-minute execution loop.
2. It uses a 9/21 EMA crossover as an unvalidated entry strategy.
3. `HasPositionForSymbol()` blocks every additional position on the chart symbol.
4. It has no per-position 10–60 second lifecycle manager or time-based exit.
5. It has no portfolio-level position allocator for multiple independent positions.
6. It uses the terminal's spread field rather than a consistently sampled live bid/ask spread calculation.
7. It does not establish a stale-quote gate, quote-age telemetry, or a session heartbeat.
8. It does not implement a full execution state machine for partial fills, rejected closes, retries, and reconciliation after reconnect.
9. Its fixed point-based SL/TP inputs are not calibrated to each instrument's tick size, tick value, stop level, freeze level, and contract specification.
10. No evidence currently establishes positive expectancy, realistic slippage, or profitability.

Retain the prototype only as an audit reference. Do not silently reuse its EMA signal or entry decisions in the replacement.

## Target architecture

### 1. Android session control

- Manual GitHub Actions dispatch starts one bounded session.
- Operator supplies no secrets in workflow inputs; broker credentials remain in GitHub Actions Secrets.
- Session state is explicit: `STARTING`, `CONNECTED`, `ARMED_DEMO`, `RUNNING`, `STOPPING`, `STOPPED`, `FAULTED`.
- Default state is disarmed. A deliberate demo-only arm action is required after connectivity and health checks.
- Hard two-hour session timeout, emergency stop, and fail-closed shutdown.
- Workflow logs must redact credentials and must never print account passwords or tokens.

### 2. MT5 connectivity and market-data health

- Verify account login and exact server authorization before arming.
- Verify account trade mode is DEMO, terminal connectivity, symbol availability, trade permissions, and account margin mode.
- Discover and record symbol point, digits, tick size/value, volume min/max/step, stops level, freeze level, execution mode, filling modes, and trading sessions.
- Reject stale or missing ticks; compute spread from current ask minus bid.
- No entry when market data, broker metadata, or terminal state is uncertain.

### 3. Strategy engine (new, isolated)

- Strategy modules produce timestamped candidate intents only; they do not call order APIs.
- Inputs must be point-in-time bid/ask/tick data and explicitly versioned features.
- No inherited EMA crossover or other legacy signal logic without independent evidence.
- Separate XAUUSD and XAGUSD parameterization and validation.
- Candidate intent includes direction, invalidation, expected holding horizon, stop distance, confidence/evidence fields, and expiry.
- Every candidate is rejected if its quote is stale, spread/slippage regime is outside validated bounds, or session/liquidity conditions are unsupported.

### 4. Risk and portfolio allocator

- Calculate risk from current equity and instrument-specific tick economics.
- Enforce per-position risk, aggregate open-risk cap, daily equity drawdown lock, maximum position count, maximum exposure, margin reserve, and consecutive-loss cooldown.
- Use broker volume steps with round-down only. If calculated size is below minimum, skip.
- Enforce a configurable cap on simultaneous positions and prevent accidental duplicate intents.
- Independent same-symbol position tracking is permitted only on hedging accounts.
- Risk checks run both when creating an intent and immediately before order submission.

### 5. Execution state machine

Each position has a unique ticket/identifier and independent state:

`CANDIDATE → APPROVED → SUBMITTING → OPEN/PARTIAL → CLOSING → CLOSED`

Failure states include `REJECTED`, `UNKNOWN`, and `PROTECTION_FAILURE`. Unknown outcomes must be reconciled against broker positions/deals before retrying; never blindly resubmit.

- Demo preflight validates account mode, terminal permissions, quote freshness, spread, price drift, protective stop and target direction, broker volume constraints, and estimated margin.
- Broker reconciliation checks live position identifiers, volume, protective stops, and closing deal history.
- A position is marked CLOSED only when confirmed closing deals cover the registered volume; missing or incomplete history remains UNKNOWN.
- A future execution adapter must independently handle broker retcodes, partial fills, requotes, timeouts, and disconnects.
- A local 10–60 second holding-time manager requests closure at the configured deadline; it must not assume the close succeeded until broker state confirms it.
- Emergency stop blocks new entries immediately and initiates controlled position handling according to a separately tested policy.

### 6. Observability and audit trail

Record session ID, strategy version, quote timestamp, bid/ask, spread, candidate/rejection reason, risk calculation, order request, broker retcode, fills, position ticket, exit reason, realized P/L, and latency. Never log credentials.

The Android operator view must show session state, connection/quote freshness, spread, open positions, position age, aggregate risk, daily drawdown, last action, and emergency-stop state.

### Execution request state coordinator

- Track prepared intent, submission hand-off, acknowledgement, partial/full fills, rejection, unknown outcome, reconciliation, and cancellation.
- Deduplicate broker deal tickets and reject cumulative fill volume beyond the approved request.
- On disconnect, cancel intents that were never handed off and mark in-flight outcomes UNKNOWN.
- Reconnection alone does not resolve unknown outcomes. Require broker reconciliation before any retry.
- Emergency stop is latched, blocks new intents and submission hand-offs, and does not claim to close existing positions.
- This coordinator is state-only. It does not call broker execution, order modification, or position closure APIs. There is deliberately no reset method.

## Validation and release gates

1. **Static/build gate:** compile the replacement EA with the official MetaEditor compiler; no warnings accepted without review.
2. **Unit gate:** deterministic tests for sizing, tick/point conversion, stop/freeze checks, volume rounding, quote staleness, position allocation, and state transitions.
3. **Historical gate:** tick-level or highest-quality available data, chronological train/validation/test partitions, realistic spread, commission, swap where relevant, and slippage.
4. **Robustness gate:** out-of-sample performance, parameter sensitivity, spread/slippage stress, latency stress, and market-regime segmentation.
5. **Demo execution gate:** prospective demo observations across multiple sessions, including partial fills, disconnect/reconnect, rejected orders, emergency stop, and forced session timeout.
6. **Live gate:** remains locked until independent review of all preceding evidence and explicit user authorization. A green CI workflow or successful demo login is never sufficient.

## Immediate implementation sequence

1. Freeze the existing prototype as reference and keep its order defaults disabled.
2. Implement instrument metadata and quote-health module.
3. Implement pure risk-sizing and portfolio-allocation module with tests.
4. Implement position registry and lifecycle manager.
5. Implement demo-only execution preflight and read-only broker reconciliation.
6. Add a new strategy only after the execution/risk foundation is testable.
7. Add bounded Android-triggered demo session workflow.
8. Run validation gates in order; do not skip directly to live trading.
