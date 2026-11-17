# Phase 8 — immutable validation baseline and prospective replication v2

**Baseline workflow:** [run 44112391721](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44112391721)  
**Baseline job:** 134141209101  
**Baseline artifact:** 14340019644  
**Baseline report SHA-256:** `677818dd2b2b266dfce3ce280277de89684fb270fa238e22e86b2ce62df00931`  
**Status:** Research evaluation complete; no candidate approved; holdout remains sealed.

## 1. Immutable v1 baseline result

The formal workflow successfully downloaded the two preregistered development artifacts and all four eligible validation artifacts, verified their manifests and hashes, built the catalog, and completed the chronological evaluator.

The report contains 112 candidate-configuration/horizon rows. All 112 have `candidate_approval=NOT_APPROVED`. Top-level gates remain:

- `status=RESEARCH_EVALUATION_COMPLETE`
- `candidate_approval=NOT_APPROVED`
- `holdout_eligible=false`
- `commission_status=UNVERIFIED_REQUIRED_INPUT`
- `net_performance_allowed=false`
- `research_only=true`

### Aggregated configuration results

There are 28 registered parameter configurations per horizon. The following statistics are aggregated across those configurations; outcome totals are not unique market observations because configurations can evaluate overlapping quotes.

| Horizon | Configurations meeting 100-outcome minimum | Configurations with positive gross mean | Configurations with negative gross mean | Gross mean range (bps) |
|---:|---:|---:|---:|---:|
| 5 seconds | 10 / 28 | 1 | 27 | -0.890 to +0.292 |
| 15 seconds | 10 / 28 | 1 | 27 | -1.794 to +0.621 |
| 30 seconds | 7 / 28 | 2 | 26 | -3.578 to +2.460 |
| 60 seconds | 0 / 28 | 8 | 20 | -5.787 to +4.363 |

No configuration at any horizon had a session-clustered 95% confidence interval whose lower bound was above zero. Even the positive gross-mean rows therefore do not establish a robust edge. All outcomes are theoretical bid/ask quote marks, not broker fills. Commission is still unverified, so net performance cannot be calculated.

The 5-second horizon is diagnostic only and is outside the required 10–60-second holding window. It cannot support a deployment or execution decision.

## 2. Interpretation and anti-overfitting controls

This is a valid research rejection of the current candidate set on the observed sample, not a collection or CI failure. Do not change candidate definitions, parameter grids, signal thresholds, feature windows, exits, or benchmark rules in response to this report.

The first four eligible validation dates remain immutable: 13, 15, 16, and 17 November 2026. The v1 report and artifact must remain the baseline even after further data is collected.

## 3. Prospective replication v2

A separately versioned plan is added at `research/xauusd_walk_forward_plan_v2.json`. It retains the same strategy registry and all candidate definitions, parameter grids, evaluation horizons, bid/ask execution convention, benchmark set, slippage sensitivity grid, and commission lock. It extends the validation partition from four to twelve distinct UTC dates by adding:

- `validation_06`
- `validation_07`
- `validation_08`
- `validation_09`
- `validation_10`
- `validation_11`
- `validation_12`
- `validation_13`

Each additional session must be a full 30-minute Exness DEMO XAUUSD-only read-only collection on a separate UTC date after 17 November 2026. The v2 intake requires all twelve eligible validation IDs together and rejects missing IDs, duplicate IDs, duplicate UTC dates, non-PASS artifacts, or any change to the two fixed development artifacts.

The separate workflow is `.github/workflows/xauusd-prospective-validation-v2.yml`. It calls the same catalog builder and chronological evaluator with the v2 plan. The v1 workflow and v1 plan are left unchanged. The collector remains manual-dispatch; no schedule or unattended terminal operation is introduced.

### Suggested manual collection windows

These are target windows, not asserted actual collection times. Runner startup and terminal authorization can delay the real capture. Always use the manifest's actual UTC start/end for classification.

| Session ID | Target UTC date | Target UTC window | Intended coverage |
|---|---|---|---|
| validation_06 | 2026-11-18 | 06:00–06:30 | Asian |
| validation_07 | 2026-11-19 | 10:00–10:30 | London |
| validation_08 | 2026-11-20 | 13:30–14:00 | London–New York overlap |
| validation_09 | 2026-11-23 | 06:00–06:30 | Asian |
| validation_10 | 2026-11-24 | 10:00–10:30 | London |
| validation_11 | 2026-11-25 | 13:30–14:00 | London–New York overlap |
| validation_12 | 2026-11-26 | 17:30–18:00 | New York after London close |
| validation_13 | 2026-11-27 | 10:00–10:30 | London |

Use one collection per UTC date. Do not run multiple sessions on one date and count them as distinct-date evidence. Do not relabel a session if actual timestamps fall outside the intended window. The workflow dropdown now exposes these eight IDs.

After the eight collection runs succeed, update the JSON session map supplied to the v2 validation workflow with their actual GitHub Actions run IDs. The current workflow input default contains only the already completed v1 sessions; it is intentionally not populated with invented future run IDs.

## 4. Release gates unchanged

- Minimum 100 validation outcomes per candidate configuration/horizon remains required.
- Commission must be verified from the applicable Exness DEMO schedule or account statement before net-performance assessment.
- Independent reviewer attestation and out-of-band Ed25519 public-key fingerprint verification remain outstanding.
- Installer signer thumbprint must be independently pinned against Exness-controlled evidence.
- Manual owner-controlled DEMO reactivation rehearsal remains outstanding.
- Holdout stays sealed; no selection freeze, holdout scoring, production deployment, live execution, or real-money trading is authorized.

A successful v2 workflow will mean that the expanded research evaluation ran. It will not, by itself, approve a candidate or unlock execution.
