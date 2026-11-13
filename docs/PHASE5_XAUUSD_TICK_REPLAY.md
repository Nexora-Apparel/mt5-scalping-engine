# Phase 5 — deterministic XAUUSD tick replay

## Purpose

The replay engine evaluates supplied candidate events against a verified historical XAUUSD bid/ask tick stream. It does not generate signals; candidate signal generation is a separate Phase 6 responsibility. This separation makes the execution-price convention independently testable.

## Contract

- Input CSV and manifest must pass the existing offline dataset profiler: SHA-256, record count, Exness DEMO provenance, XAUUSD-only scope, valid chronological quotes, and trading/DLL disabled.
- Entry is the first valid tick strictly after the completed signal window, with a maximum five-second wait.
- Exit is the first valid tick at or after entry plus the registered horizon, no more than two seconds late. Missing quotes produce explicit timeout outcomes; no forward fill is permitted.
- Long: entry Ask, exit Bid. Short: entry Bid, exit Ask. Spread is included exactly once.
- Slippage sensitivity is 0, 1, 2, or 5 broker points per side. These are assumptions, not measured slippage.
- Commission remains `UNVERIFIED_REQUIRED_INPUT`; net-after-commission is null and no candidate pass can be declared.
- No orders are submitted, no actual fill is claimed, and no position sizing is performed.

## CLI

Supply an event JSON file with an `events` array. Each event contains a unique `signal_id`, registered `candidate_id`, `signal_window_end_msc`, `direction` (`long` or `short`), and preregistered `horizon_seconds`.

```bash
python -m tools.mt5_xauusd_tick_replay --csv ticks.csv --manifest manifest.json --events events.json --registry research/xauusd_strategy_registry_v1.json --output replay.json
```

The output is deterministic and contains source/registry hashes, entry/exit quote timestamps, gross quote-crossed outcomes, slippage sensitivity, and explicit missing-outcome counts.

## Scope limitation

The two already inspected sessions remain development-only. Replay smoke tests on them validate mechanics, not strategy performance. No final holdout is opened or scored in this phase.
