# Phase 8 V2 collector, intake, and evaluator integration

Status: implementation branch pending CI; V2 preregistration remains draft and no collection is authorized yet.

## Dependency order

1. PR #80 records the immutable V1 signal/replay audit and its dated first-window provenance correction. It does not change source datasets or results.
2. PR #81 contains the separately versioned replay corrections. Its latest recorded CI passed 294 project tests plus historical replay and candidate-generation smoke workflows.
3. PR #83 adds the V2 protocol amendment on top of the PR #81 branch.
4. This integration branch is based on PR #83 and adds the V2-only collector, dispatch gate, prospective intake, evaluator adapter, manual workflows, and regression tests.

No PR is merged by this change. The integration PR must be reviewed after its CI completes. Because #80 is an independent audit/documentation dependency, it can be reviewed in parallel; it must not be used as a substitute for the code/test gates in #81–#84.

## Collection path

- `.github/workflows/xauusd-v2-demo-validation-collection.yml` is manual-only and exposes exactly `v2_validation_01` through `v2_validation_04`.
- The workflow checks out the exact dispatch commit with full Git history, validates the frozen amendment/registry/implementation hashes and the selected session's scheduled UTC slot, then performs the existing official Exness-linked installer Authenticode checks.
- The collector is a V2-only copy. It rejects V1 IDs and records explicit false values for trading, DLL imports, order submission, position management, execution, and live trading.
- Each collection is a bounded 30-minute authenticated Exness DEMO XAUUSD capture. There is no scheduled trigger, no cron, and no order/position API.
- The workflow run ID is the immutable collection reference. Do not re-run a session ID to replace a failed or questionable artifact; investigate and version any repair separately.

## Intake and evaluation path

- `tools/prepare_xauusd_v2_validation_catalog.py` accepts exactly four distinct collection run IDs mapped one-to-one to the four V2 IDs. It delegates artifact/hash/provenance validation to the existing catalog intake and then enforces the frozen UTC schedule, four distinct dates, monotonic prospective duration, DEMO identity, XAUUSD-only contract, and explicit read-only controls.
- V1 validation IDs and artifacts cannot be mapped into the V2 catalog.
- `tools/mt5_xauusd_v2_validation.py` adapts the immutable V1 plan to the four V2 IDs only after verifying the frozen amendment, registry, implementation ancestry, and freeze record. The V1 holdout IDs remain unchanged and inaccessible.
- The V2 evaluator reports quote-crossed gross research outcomes only. Commission remains `UNVERIFIED_REQUIRED_INPUT`; net performance remains disabled. No candidate approval or execution follows from a successful report.

## Freeze contract

The V2 amendment must be changed from draft to `FROZEN_PREREGISTRATION_RESEARCH_ONLY` only after this integration has passed its complete CI suite and has been reviewed. The freeze record must bind:

- exact amendment SHA-256;
- exact V1 strategy registry SHA-256;
- validated implementation commit SHA;
- UTC freeze timestamp;
- all four ordered V2 session IDs;
- four distinct-date UTC collection slots, each at least 30 minutes;
- the explicit `UNVERIFIED_REQUIRED_INPUT` commission lock unless independently verified account-specific evidence is supplied.

The implementation gate rejects a draft amendment, stale/mismatched hashes, non-ancestor implementation commit, duplicate dates, schedule entries before freeze, or a commission claim unsupported by this workflow. Collection dispatch additionally fails unless the selected ID is within its frozen +/-10-minute UTC slot.

## Remaining external operations

The connected GitHub interface can inspect and edit repository content and inspect workflow runs, but it does not expose the Actions `workflow_dispatch` operation. After the reviewed dependency stack is merged to the default branch, a human must start the four manual collection runs from the Actions UI on their four frozen dates and enter each session ID. The separate V2 intake/evaluation workflow then accepts the four run IDs as JSON.

Commission cannot be verified from tick artifacts or from a generic public fee table. It requires the applicable Exness DEMO account commission schedule or statement with exact per-side/per-lot charge and currency. Until that evidence is independently inspected and hashed, gross-only research is the maximum permitted analysis.

## Safety and data integrity

- Original V1 report artifact 14888181358, V1 validation sessions, frozen V1 registry, and holdout artifacts remain unchanged.
- No corrected-performance rescoring of V1 dates.
- No holdout access, parameter tuning on holdout, candidate approval, order submission, position management, or live trading.
- V2 collection is not automatically started by this PR. The amendment remains draft until CI/review and the later freeze commit.
