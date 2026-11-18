# Phase 8 — validation_03 independent raw-tick audit

**Audit status:** PASS WITH REVIEW ITEMS  
**Workflow:** [Run 43773683398](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/43773683398)  
**Job:** 132995005437  
**Branch / source commit:** `phase8-distinct-validation-date-guard` / `eacb99a5b3785ff3530931c42627dfe65326d625`  
**Session:** `validation_03`  
**Collection window:** 2026-11-15 23:14:45.087447–23:44:47.061410 UTC  
**Account:** Exness-MT5Trial10, manifest declares DEMO  
**Instrument:** XAUUSD, broker symbol XAUUSDm

## Artifact identity

- Artifact: `veltrix-exness-demo-ticks-13` (run artifact ID 14185914411)
- Dataset: `veltrix_exness_demo_ticks.csv`
- CSV bytes: 507,707
- CSV rows: 4,035
- Independently recomputed SHA-256: `15e5066e687157fd9a5bbc1e66c3fc6fb2833693638a9c7010186d5d4096eb25`
- Manifest SHA-256: identical
- Manifest status: PASS
- Duration: 1,802 seconds (30 minutes + 2 seconds)
- Trading enabled: false
- DLL imports enabled: false

## Independent raw CSV checks

The downloaded ZIP was opened and the CSV was parsed independently, outside the workflow's own audit function.

| Check | Result |
|---|---:|
| Rows | 4,035 |
| Bid unique values | 3,187 |
| Ask unique values | 3,187 |
| Bid range | 3,877.539–3,890.750 |
| Ask range | 3,877.779–3,890.990 |
| Distinct observed spreads | 1 |
| Spread | 0.240 price units on every row |
| Spread in broker points (point=0.001) | 240 |
| Non-zero tick volume / volume_real rows | 0 |
| Tick flags | 6 on all 4,035 rows |
| Manifest maximum inter-tick gap | 4,873 ms |
| Gaps above 5 seconds | 0 |

Every raw row has ask minus bid equal to 0.240, subject only to floating-point representation. Bid and ask prices themselves vary. Tick flag 6 corresponds to bid/ask update flags; zero last/volume fields are therefore not by themselves evidence of malformed data for this quote-only stream.

## Review items — do not silently waive

1. **Constant spread:** all 4,035 stored ticks show exactly 0.240 spread (240 points). This may reflect the broker's quote conditions during this sample, but the single-spread observation needs comparison with contemporaneous terminal quote logs and subsequent independently collected sessions. Do not treat this one sample as proof of representative spread behaviour.
2. **Installer provenance:** workflow step 4 downloaded the terminal installer from `https://download.terminal.free/cdn/web/exness.technologies.ltd/mt5/exness5setup.exe`. The job log proves the download and installation completed; it does not prove the binary's publisher signature or independently trusted hash. Obtain and retain Authenticode publisher/signature and a trusted hash before marking runner software provenance verified.
3. **Execution-cost evidence:** the tick spread is not commission evidence. Commission schedule, contract/lot-side fee, slippage, and execution latency remain separate requirements.
4. **Account evidence:** the manifest and runtime reported DEMO identity; retain the sanitized diagnostic artifact and independently verify the account identity evidence under the existing intake process.

## Intake disposition

- The raw CSV hash matches the manifest.
- Structural/timestamp/price sanity checks and the workflow's duplicate/order checks passed.
- The sample is eligible to be submitted as `validation_03` to the strict four-session intake, **subject to resolving or explicitly recording the review items above**.
- This audit does not certify strategy performance, net profitability, realistic execution costs, commission, or readiness for live trading.
- Do not begin net scoring, candidate freeze, holdout, order execution, or live deployment on the strength of this artifact alone.

## Next steps

1. Collect `validation_04` on a UTC date distinct from `validation_01` and `validation_03`.
2. Collect `validation_05` on another distinct UTC date.
3. Compare spread distributions and terminal diagnostics across sessions.
4. Verify installer signature/provenance and obtain independent commission evidence.
5. Run the strict four-session intake only when all eligible session artifacts are available.
