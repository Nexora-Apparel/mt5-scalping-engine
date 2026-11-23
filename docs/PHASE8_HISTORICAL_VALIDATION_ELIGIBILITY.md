# Phase 8 — Historical validation eligibility audit

**Decision: eligible for preregistered validation intake, subject to artifact re-verification. Not eligible for holdout.**

## Frozen strategy and chronology

- Candidate registry was frozen in commit `71d3546e2beeff3d91d3a292f7c46ab937e8bb20` at 2026-11-13 06:17:49 UTC.
- Walk-forward plan was committed in `46218e59c19e3fc59e2d1a5439e4d4127c95e9a3` at 2026-11-13 08:55:57 UTC.
- The registry has no later commit in its file history. Candidate definitions and finite parameter grids therefore predate the proposed Nov 16–19 validation intervals.
- The ten-date historical backfill completed in workflow run [44654151366](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44654151366), artifact [14592042454](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44654151366/artifacts/14592042454), ZIP SHA-256 `a3387bde442bc657ec9489c54c71853acdae4844bf1a25ce8fea5159f8bd2f75`.
- The four proposed intervals are the first four available weekdays after the Nov 13 development date, each exactly 17:30:00–18:00:00 UTC: Nov 16, 17, 18 and 19, 2026. They are distinct, chronological and non-overlapping.

## Prior exposure and leakage assessment

These four dates were included in the previously recorded 12-date descriptive movement analysis. That analysis reported absolute midpoint displacement, quantiles, and time-block heterogeneity. It did **not** generate candidate signals, evaluate candidate directions, calculate candidate trade outcomes, compare candidate configurations with benchmarks, or rank parameters.

The strategy registry was already frozen on Nov 13, before these four market intervals. Its file history contains no later registry update. The proposed mapping uses all four consecutive eligible post-development weekdays, rather than selecting dates by observed candidate performance.

This is not an untouched holdout. It is an explicitly disclosed, descriptively inspected but candidate-unscored validation sample. The final holdout remains separately sealed and must remain untouched until a cost-qualified validation selection is frozen.

## Historical source versus prospective capture

Historical tick retrieval is not prospective live capture and historical quote marks are not actual broker fills. The new intake path:
- pins the previously successful historical batch run and reviewed retrieval source commit;
- verifies the batch artifact, per-interval manifests, CSV SHA-256 values, exact requested UTC bounds, DEMO identity, XAUUSD contract metadata, and disabled trading/DLL/order/position controls;
- maps the four exact intervals to the four already preregistered validation IDs without changing the frozen plan or candidate registry;
- creates derived session manifests that preserve the source manifest and CSV hashes while explicitly marking `duration_clock=historical_interval` and `not_prospective_capture=true`;
- keeps all candidate calculations on the frozen registry and the evaluator's existing causal, bid/ask-crossed replay.

No raw historical CSV or original source manifest is modified. The derived manifest is an intake envelope, not a claim that historical retrieval happened in real time.

## Remaining gates

- Commission remains `UNVERIFIED_REQUIRED_INPUT`; net performance, candidate approval and selection freeze remain disabled.
- Validation still requires at least 100 non-overlapping outcomes for each candidate configuration/horizon and the registered benchmark comparisons.
- A gross-only report is descriptive research evidence, not proof of an edge or permission to trade.
- Holdout IDs remain sealed; no holdout collection or scoring is part of this intake.
- No order submission, position management, DEMO execution, or live-money execution is enabled.

## Exact default mapping

| Validation ID | Historical interval ID | UTC date | Requested window |
|---|---|---|---|
| validation_01 | ny_20261116_1730 | 2026-11-16 | 17:30–18:00 |
| validation_02 | ny_20261117_1730 | 2026-11-17 | 17:30–18:00 |
| validation_03 | ny_20261118_1730 | 2026-11-18 | 17:30–18:00 |
| validation_04 | ny_20261119_1730 | 2026-11-19 | 17:30–18:00 |

All times are UTC. The intake workflow must independently re-check the artifact and manifests before any candidate evaluation occurs.
