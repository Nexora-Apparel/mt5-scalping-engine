# Phase 7 desktop MT5 runtime verification runbook

## Purpose

Reproduce the synthetic Phase 7 file-I/O and persistence checks in a local desktop MT5 terminal if desired. The mandatory automated execution has already been completed by the Windows MT5 terminal CI, including a full process shutdown/relaunch between seed and verification scripts.

This is a file-I/O test only. It does not connect to a broker, read account credentials, submit orders, or modify a trading account.

## Required environment

- Desktop MetaTrader 5 terminal with MQL5 script execution support.
- The Android MT5 application cannot run MQL5 Expert Advisors or Scripts.
- No broker login is required for this synthetic journal test.

## Artifact

- Successful compile workflow: https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/43386014603
- Runtime script artifact: https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/43386014603/artifacts/14017899137
- Source: `MQL5/Scripts/RiskJournalRuntimeTest.mq5`

The artifact is an `.ex5` file. The Windows workflow compiled and executed it. Final runtime evidence is recorded in [workflow #43393115383](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/43393115383) and [result artifact](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/43393115383/artifacts/14022056627).

## Run procedure

1. Download and extract the `Veltrix-risk-journal-runtime-test` artifact.
2. In desktop MT5, select **File → Open Data Folder**.
3. Open `MQL5/Scripts` and copy `RiskJournalRuntimeTest.ex5` into that folder.
4. In the Navigator, refresh **Scripts** (or restart the terminal).
5. Open any chart, then run **RiskJournalRuntimeTest** from Navigator → Scripts.
6. Open the **Experts** or **Journal** tab and verify a line beginning:
   `RISK JOURNAL RUNTIME TEST PASS`.
7. In the same Data Folder, inspect `MQL5/Files/veltrix_risk_journal_runtime_test.result`. Its contents must begin with:
   `PASS |`.
8. Record the terminal build number, test date/time, and the exact result text in the Phase 7 verification record.

## What PASS covers

- New synthetic account/server journal creation in MT5 Common Files.
- Append and replay of request and closing-deal records.
- Duplicate request and closing-deal rejection.
- Server-day loss-lock event persistence.
- Permanent emergency-stop event persistence.
- Journal checksum-chain replay after closing and reopening the file.

## Cleanup and safety

- The test uses a generated synthetic login identifier and a fixed test-server label. It never uses the connected broker account identity.
- It creates a small synthetic journal in MT5 **Common Files**. It does not touch the production account's journal.
- Do not delete or edit any production `VELTRIX_XAUUSD_RISK_*` journal.
- Do not enable `NexoraScalper` order inputs or introduce an order path into `VeltrixScalper`.
- A PASS from this script does not verify the full `CVxRiskControls` integration, account switching, broker fills, risk sizing against live contract metadata, or trading performance.

## Completed automated Phase 7 runtime evidence

- `RiskJournalRuntimeTest.mq5`: append/replay, duplicate request/close rejection, daily-lock replay, emergency-stop replay, and checksum-chain replay — PASS.
- `RiskControlsRuntimeTest.mq5`: emergency-stop and daily-lock restoration, abandoned transaction-lock rejection, checksum mismatch rejection, cleanup — PASS.
- `RiskControlsRestartSeed.mq5` followed by `RiskControlsRestartVerify.mq5` in a fresh MT5 process: emergency-stop and daily-lock survived terminal shutdown/relaunch — PASS.
- `RiskJournalFailureRuntimeTest.mq5`: locked existing journal refused without recreation; corrupted journal sequence refused during replay — PASS.
- All tests use synthetic identities and do not connect to a broker or submit orders.

The local run procedure above is optional reproduction, not a remaining blocker. Phase 7 is complete for the read-only risk-control implementation. Broker-connected DEMO verification is deferred to Phase 9, after Phase 8 research gates pass.
