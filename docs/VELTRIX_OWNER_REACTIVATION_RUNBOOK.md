# VELTRIX Owner-Controlled Risk Reactivation Runbook

## Scope and safety

This runbook applies only to the read-only VELTRIX MQL5 risk-control research branch and an explicitly verified Exness DEMO account denominated in USD. It does not authorize order execution. The scripts contain no order submission, modification, or close calls.

Reactivation is a local, manually initiated terminal action. Never publish these scripts through a web endpoint, Telegram command, remote admin route, or unauthenticated automation. The operator ID is self-asserted audit attribution; it is not a cryptographic identity proof. Local operating-system and terminal access control are the ownership boundary.

## Preflight

1. Confirm the connected terminal is on the intended Exness DEMO server and the account currency is USD.
2. Record the exact account login and server name from the terminal. Enter those exact values into the script inputs; do not infer or guess them.
3. Review the original deposit evidence and verify the immutable original-deposit baseline. Use the broker statement/deposit ledger, not current balance or equity.
4. Confirm the evidence reference is traceable and does not contain secrets. Suitable references include a statement ID/date or a controlled evidence-record identifier.
5. Record the operator ID and a specific reason for the reactivation.
6. Confirm no other person or process is operating the terminal. Do not run both reactivation scripts concurrently.

## Daily-loss lock: 15% ceiling

Run MQL5/Scripts/DailyLossOwnerRearm.mq5 manually from the local MetaTrader 5 terminal.

Required inputs:
- Expected DEMO login and exact server name.
- Owner-verified original-deposit amount and InpOriginalDepositEvidenceReviewed=true.
- Operator ID, reason, and traceable evidence reference.
- Exact confirmation phrase: VELTRIX OWNER CONFIRM DAILY REACTIVATION.

Expected behavior:
- Rejects non-DEMO, non-USD, disconnected, or mismatched account identity.
- Rejects missing evidence review, missing audit metadata, or an incorrect confirmation phrase.
- Appends an operator/reason/evidence-attributed DAILY_REARM record with timestamp and verified current-equity baseline to the checksum-chained risk journal.
- Does not clear the 50% overall-loss lock or emergency stop.
- If terminal-state persistence fails after journal append, the emergency stop is latched; do not retry blindly. Inspect the journal and restart-recovery state first.

After success, reinitialize/restart the EA so its in-memory daily baseline and lock state are reloaded from durable state. Confirm the daily lock is clear and independently confirm the overall-loss lock and emergency stop remain in their previous states.

## Overall account-loss lock: 50% ceiling

Run MQL5/Scripts/OverallLossOwnerRearm.mq5 manually from the local MetaTrader 5 terminal.

Required inputs:
- Expected DEMO login and exact server name.
- Original-deposit amount matching the immutable verified baseline and InpOriginalDepositEvidenceReviewed=true.
- Operator ID, reason, and traceable evidence reference.
- Exact confirmation phrase required by the script.
- Account equity strictly above the 50% loss boundary. At or below the boundary, reactivation must fail.

Expected behavior:
- Rejects non-DEMO, non-USD, disconnected, or mismatched account identity.
- Preserves the original-deposit baseline; it is never reset by reactivation.
- Writes intent/commit/abort audit events into the account-scoped checksum-chained audit journal.
- Rejects invalid confirmation, invalid audit fields, tampered audit state, partial persisted state, and interrupted reactivation.
- Does not clear the separate daily-loss lock or emergency stop.

After success, reinitialize/restart the EA and verify the persisted overall-loss state. A daily-loss lock or emergency stop must still independently prevent operation.

## Audit and incident handling

- Preserve the terminal Experts/Journal logs and the account-scoped audit journal with the evidence reference.
- Do not edit, delete, or recreate terminal global variables or journal records to force a reactivation.
- If an audit checksum, sequence, baseline, account identity, or persistence check fails, treat the account as locked and stop. Preserve artifacts for investigation.
- A successful synthetic runtime test proves deterministic code paths only. It does not prove that a manual owner action was performed correctly on a live terminal or that broker-side account data is accurate.
- A real Exness DEMO rehearsal remains outstanding. No script has yet been executed against the user's account.

## Release boundary

Both reactivation scripts are compile/runtime-tested in CI. They remain manual-only and local. No remote reactivation endpoint, live trading, DEMO order execution, deployment, or scheduled workflow is authorized by this runbook.
