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

## Controlled validation collection

The 30-minute Exness DEMO collector is manual-dispatch only; no cron schedule or unattended validation-refresh workflow is active. Dispatch `.github/workflows/veltrix-demo-tick-collection.yml` once per distinct preregistered validation date, selecting one eligible ID from `validation_01`, `validation_03`, `validation_04`, or `validation_05`. `validation_02` is permanently excluded: it was collected on the same UTC date as `validation_01` and is retained only as an audit artifact. Intake requires all four eligible sessions together and rejects duplicate UTC collection dates. Each run writes the selected ID into its manifest. Artifact intake and the walk-forward evaluator both reject a validation manifest whose session ID does not match the preregistered catalog entry. Do not reuse a session ID or relabel a development artifact.

The collection workflow requires the repository's existing Exness DEMO secrets. It runs with MT5 terminal trading and DLL permissions disabled, and the collector contains no order-submission or position-management calls. Collection is not started automatically by this code change.

## Implementation

- Plan: research/xauusd_walk_forward_plan_v1.json
- Session catalog template: research/xauusd_walk_forward_catalog_template.json
- Evaluator: tools/mt5_xauusd_walk_forward.py
- Tests: tests/test_mt5_xauusd_walk_forward.py

The evaluator verifies the frozen registry hash, exact development hashes, DEMO/XAUUSD manifest contract, session duration, independent source hashes, non-overlap, chronological partition order, and distinct dates. It generates candidate events and quote-crossed replay outcomes, applies a one-position filter, reports slippage sensitivity, and calculates session-clustered bootstrap confidence intervals. It also reports always-long, always-short, and no-trade benchmarks. It never submits orders.

Copy the catalog template to a working catalog, then add one entry per collected session with its fixed session_id and local CSV/manifest paths. The two development entries must use the pinned Sessions 8 and 9 artifacts; validation entries use only the four eligible preregistered IDs (`validation_01`, `validation_03`, `validation_04`, `validation_05`) and must cover four distinct UTC dates.

~~~powershell
Copy-Item research/xauusd_walk_forward_catalog_template.json research/xauusd_walk_forward_catalog.json
python tools/mt5_xauusd_walk_forward.py --catalog research/xauusd_walk_forward_catalog.json --stage validation --output research/xauusd_validation_report.json
~~~

Holdout command is intentionally unavailable for scoring while commission is unverified. Once commission evidence is verified and the registry/plan are updated under a new reviewed change, holdout additionally requires a selection-freeze JSON and the exact validation report whose SHA-256 is embedded in that freeze. The validation report and selection-freeze JSON must both be committed. The evaluator checks the Git commit timestamps, binds the exact validation report SHA-256, requires the freeze commit to follow the report commit, and requires that freeze commit to precede every holdout collection start. A selection-freeze is additionally rejected unless the validation report explicitly records verified commission, net-performance authorization, the minimum outcome count, a positive net-return lower confidence bound, and outperformance of all registered benchmarks for the exact candidate configuration and horizon. Gross-only or under-sampled candidates cannot be selected.

## Current evidence and blockers

The two known development sessions were downloaded from their original GitHub Actions artifacts and their manifests/CSV hashes independently checked:

| Session | Collection window (UTC) | Ticks | Maximum inter-tick gap | Gaps over 5 seconds | Spread | Volume fields |
|---|---|---:|---:|---:|---:|---|
| Session 8 — run 43333365050, artifact 13997174371 | 00:00:09–00:30:11, 13 Nov 2026 | 5,192 | 3.040 s | 0 | 240 points on every tick | volume and volume_real always zero |
| Session 9 — run 43338046880, artifact 13999059160 | 00:34:53–01:04:55, 13 Nov 2026 | 7,646 | 3.812 s | 0 | median 240 points; 7 ticks at 260 points | volume and volume_real always zero |

Both manifests report DEMO, trading disabled, DLL imports disabled, and a broker contract XAUUSDm with base XAU, profit USD, contract size 100, point 0.001, and tick size 0.001. Their exact CSV hashes are pinned in the plan. The two sessions are non-overlapping, but they are on the same date and remain development-only. Validation evidence: `validation_01` (run 43408593546, artifact 14029149674) and `validation_02` (run 43509607846, artifact 14079846976) were both collected on 13 Nov 2026 UTC. `validation_01` is eligible; `validation_02` is preserved but ineligible because it repeats the same date. The second artifact contains 5,060 ticks, SHA-256 `39dc216f19d9c0263cc2130ace4a1b3b86498b3be2eccbb547577dd750d5d33e`, no exact duplicate records, no invalid/crossed quotes, a 5.551 s maximum gap (one gap over 5 s), constant 240-point spread, and zero non-zero volume observations. It cannot count toward the four distinct-date validation requirement. No eligible validation set or holdout set is complete. The empty catalog therefore correctly returns BLOCKED_INSUFFICIENT_DATA and emits no candidate rankings.

The spread is 0.240 XAUUSD price units for almost every tick. The feed also contains no nonzero tick-volume values. It is therefore unsuitable to claim volume-based order-flow evidence, and the spread is a severe cost hurdle for 5–60 second scalping. All robustness reports must preserve executable bid/ask crossing and additional cost sensitivity.

The registry marks Exness commission as UNVERIFIED_REQUIRED_INPUT. Final holdout remains sealed and net-performance claims remain disabled until the applicable DEMO commission schedule or statement is independently sourced.

**Phase 8 is not complete.** No candidate is approved. Phase 9 DEMO forward validation and Phase 10 release hardening remain gated.
