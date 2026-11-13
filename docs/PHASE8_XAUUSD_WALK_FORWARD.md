# Phase 8 — XAUUSD chronological walk-forward and robustness validation

**Status: IN PROGRESS — evaluation framework implemented; real validation data and commission evidence are outstanding.**

## Binding research controls

- Canonical instrument: XAUUSD only; Exness DEMO source; terminal trading and DLL permissions disabled.
- The frozen candidate registry remains the only source of signal definitions and parameter grids.
- Sessions 8 and 9 are already inspected development data. Their hashes are pinned in the registry and cannot be relabelled as validation or final holdout.
- No random row splits, future-window features, forward-filled quotes, cross-session feature history, or parameter tuning on final holdout.
- Purge at least 120 seconds at every partition boundary (60-second maximum lookback plus 60-second maximum outcome horizon).
- Each candidate configuration is evaluated as a single-position stream. An unresolved exit-quote timeout blocks subsequent signals for that configuration in that session.
- Executable quote marks cross Ask-to-Bid for longs and Bid-to-Ask for shorts, so spread is included once. Additional slippage is reported at 0/1/2/5 points per side.
- Commission remains unverified. Net P/L is null; no candidate can be ranked or approved on gross returns alone.
- Final holdout is sealed until commission is verified and a validation selection-freeze record is committed before any holdout session begins.

## Preregistered sample plan

| Partition | Sessions | Distinct dates | Minimum outcomes per configuration/horizon |
|---|---:|---:|---:|
| Development | 2 fixed sessions | Existing inspected date(s) | Smoke tests only |
| Validation | 4 new sessions | 4 | 100 |
| Final holdout | 10 new sessions | 10 | 300 |

Each new session must be at least 30 minutes, independently hashed, non-overlapping, and have an audited manifest proving Exness DEMO, XAUUSD-only contract metadata, and disabled trading/DLL permissions. The new-data requirement is at least 14 sessions (7 hours of bounded collection) across 14 distinct dates. This is a minimum; low candidate frequency can require additional sessions.

## Implementation

- Plan: research/xauusd_walk_forward_plan_v1.json
- Session catalog template: research/xauusd_walk_forward_catalog_template.json
- Evaluator: tools/mt5_xauusd_walk_forward.py
- Tests: tests/test_mt5_xauusd_walk_forward.py

The evaluator verifies the frozen registry hash, exact development hashes, DEMO/XAUUSD manifest contract, session duration, independent source hashes, non-overlap, chronological partition order, and distinct dates. It generates candidate events and quote-crossed replay outcomes, applies a one-position filter, reports slippage sensitivity, and calculates session-clustered bootstrap confidence intervals. It also reports always-long, always-short, and no-trade benchmarks. It never submits orders.

Validation command:

~~~powershell
python tools/mt5_xauusd_walk_forward.py --catalog research/xauusd_walk_forward_catalog.json --stage validation --output research/xauusd_validation_report.json
~~~

Holdout command is intentionally unavailable for scoring while commission is unverified. Once commission evidence is verified and the registry/plan are updated under a new reviewed change, holdout additionally requires a selection-freeze JSON and the exact validation report whose SHA-256 is embedded in that freeze. The freeze timestamp must precede every holdout collection start, and only frozen candidate configurations are scored on holdout.

## Current evidence and blockers

The two known development sessions are not sufficient to run chronological validation. The repository does not contain the actual CSV/manifest artifacts for the four future validation sessions or ten future holdout sessions. The current catalog template is empty, so the correct evaluator result is BLOCKED_INSUFFICIENT_DATA; it does not emit performance rankings.

The registry also marks Exness commission as UNVERIFIED_REQUIRED_INPUT. The final holdout remains sealed and net-performance claims remain disabled until the applicable DEMO commission schedule or statement is independently sourced.

The observed development-session median spread was 240 broker points (0.240 XAUUSD price units at a 0.001 point size). That is a material hurdle for 5–60 second scalping; all robustness reports must preserve the observed bid/ask crossing and additional cost sensitivity.

**Phase 8 is not complete.** No candidate is approved. Phase 9 DEMO forward validation and Phase 10 release hardening remain gated.
