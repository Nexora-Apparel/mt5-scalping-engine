> **Scope supersession (2026-11-12):** This architecture document's earlier dual-instrument references are historical. The binding product scope is now **XAUUSD only**. XAGUSD and every other instrument are disabled across active collection, features, strategy research, profiling, certification, and future execution. See [INSTRUMENT_SCOPE.md](INSTRUMENT_SCOPE.md). The legacy EA is audit-only and is now contract-locked to verified XAUUSD.

# VELTRIX MT5 Scalper — Rebuild Architecture

## Status

Architecture baseline only. The existing `NexoraScalper.mq5` is a legacy prototype and is **not approved for demo or live order execution**. Keep order submission disabled while the replacement is built and validated.

The Exness connectivity workflow is a separate infrastructure check. A successful login does not validate a trading strategy or authorize trading.

All merged foundation modules have passed their respective MetaEditor compile and Project Tests gates: read-only market health, fail-closed risk allocation, position lifecycle tracking, demo-only execution preflight, read-only broker reconciliation, state-only execution coordination, the research-only XAUUSD/XAGUSD strategy evaluator, the point-in-time feature collector, and the versioned feature dataset exporter. These gates establish compilation and source/reference test coverage, not live broker runtime correctness or strategy profitability. The merged dataset integrity auditor, terminal runtime test, and optional quote-to-CSV feature pipeline have passed their respective CI gates. The pipeline remains disabled by default and no dataset is accepted for research until its integrity audit passes. Demo/live trading remains disabled.

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


## Dataset integrity and terminal runtime verification

- `tools/dataset_integrity.py` validates the exact versioned 13-column CSV schema without modifying input rows.
- It rejects unsupported schema/feature versions, malformed or extra fields, blank records, non-finite values, invalid bid/ask, invalid feature bounds, unsupported symbols, duplicate source/symbol/evaluation timestamps, and non-increasing evaluation timestamps within each source/symbol stream.
- Timestamp integrity requires `window_start_msc <= quote_time_msc <= evaluation_time_msc`. XAUUSD and XAGUSD remain separate streams.
- A successful audit emits a JSON manifest containing SHA-256, byte count, record count, version identities, and per-source/symbol UTC evaluation ranges. The auditor never sorts, repairs, deduplicates, imputes, or drops rows.
- `tests/test_dataset_integrity.py` covers valid datasets and corrupted chronology, schema, encoding, numeric, symbol, and row-width cases.
- `MQL5/Scripts/FeatureDatasetExporterRuntimeTest.mq5` exercises terminal-side CSV creation, append, invalid-symbol rejection, read-back, and cleanup. The manual/branch-triggered `mql5-dataset-runtime.yml` workflow runs it in an isolated MT5 terminal without broker credentials or trade permissions.
- MetaEditor compilation of the runtime test script is added to the compile workflow, but compilation and terminal runtime execution remain separate checks.
- No dataset is eligible for backtesting until both the Python integrity audit and MT5 runtime test pass for the exporter build that produced it.


## Optional live feature-data collection

- `FeaturePipeline.mqh` connects the read-only quote snapshot to the bounded point-in-time collector and versioned CSV exporter.
- Collection is controlled by the explicit EA input `EnableDatasetCollection`, which defaults to `false`. No collection starts unless the operator enables it on an exact `XAUUSD` or `XAGUSD` chart.
- Each session uses a unique provenance identifier unless the operator supplies one. Dataset filenames are generated from the exact instrument and restricted to safe CSV basenames.
- The pipeline accepts each strictly newer broker quote once, uses the quote's own millisecond timestamp as the evaluation timestamp, waits for the complete configured lookback, and exports only validated snapshots.
- An exporter or integrity failure latches the collector into a faulted state; it does not retry writes blindly. Duplicate/out-of-order quote timestamps are ignored.
- This is research-data collection only. The pipeline does not evaluate trade decisions, prepare execution intents, or call any broker order API. Live trading remains disabled.
- The MT5 runtime test feeds synthetic timestamped quotes through the pipeline and verifies that two post-warm-up rows are exported, in addition to the existing direct CSV writer tests.


## Bounded Exness demo data-collection session

- The manual `mt5-demo-session.yml` workflow starts a temporary Windows-hosted MT5 terminal only when dispatched by the operator. It offers 30-, 60-, or 120-minute sessions and has a 135-minute hard job timeout for setup and shutdown overhead.
- Broker credentials are read only from the existing `MT5_LOGIN`, `MT5_PASSWORD`, and `MT5_SERVER` repository secrets. They are not workflow inputs, printed to logs, or included in uploaded artifacts.
- The EA requires an exact connected DEMO account match against the expected login and server before enabling collection. The terminal configuration explicitly sets `AllowLiveTrading=0`.
- The workflow creates an ephemeral MT5 preset with collection enabled, starts `VeltrixScalper` on the selected exact XAUUSD/XAGUSD chart, and waits for the EA's demo-account guard and collection-ready log markers.
- At the requested end time, the terminal is stopped, the CSV is copied from the terminal Files sandbox, and the strict Python dataset auditor must pass before the dataset and manifest are uploaded as an artifact.
- This workflow does not run continuously and does not place, modify, or close trades. It is not dispatched automatically; the operator starts it from GitHub Actions when ready to collect data.
