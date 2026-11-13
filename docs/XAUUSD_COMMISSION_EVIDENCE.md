# XAUUSD DEMO commission evidence contract

This directory contains the schema contract for broker-cost evidence. The template is deliberately unverified and cannot unlock net scoring.

## Required provenance
- Account mode must be DEMO and the broker symbol must match the collected instrument.
- Contract size must be confirmed from the applicable Exness instrument specification.
- Commission must be stated in USD per lot per side, with effective dates and an explicit charging basis.
- The original source artifact must be retained securely; only a sanitized reference and SHA-256 belong in the repository.
- Independent verification must be a separate JSON attestation with its own sanitized reference, SHA-256, reviewer identity/organization/role, reviewed source hash, exact XAUUSD DEMO contract and commission terms, effective dates, timestamp, and explicit independence statement.
- The attestation must be signed with Ed25519. The evaluator verifies it against a public key whose SHA-256 fingerprint is pinned through a trusted out-of-band channel. A public key or fingerprint embedded in the attestation is never trusted.
- The trusted fingerprint is an operational trust anchor: it must be obtained from the reviewer through a separately authenticated channel and protected from modification. The signature proves possession of the corresponding private key, not by itself a legal identity or organizational independence.

## Fail-closed rule
A template, missing field, stale schedule, mismatched account/symbol/currency, malformed hash, or unverified source is invalid. Never infer a commission rate from spread, swap, generic broker marketing pages, or another account type.

## Evaluation integration
Once independently verified, the evaluator must convert the verified per-side USD commission into basis points using the verified contract size and entry price, charge both sides exactly once, and apply identical costs to candidate and benchmark outcomes. No net-performance gate may pass based on this schema file alone.


## Read-only DEMO observations

The manual Windows DEMO collection workflow also runs
`tools/mt5_xauusd_demo_execution_cost_collector.py` after tick collection. It
captures the current account mode/currency, XAUUSD broker contract and volume
specification, and up to 365 days of sanitized XAUUSD deal history.

The output package is written under
`session-artifacts/execution-cost-evidence/`:

- `broker_account_snapshot.json`: DEMO/server/currency and terminal read-only state; no login is persisted.
- `symbol_spec_snapshot.json`: broker symbol, contract size, currencies, tick and volume specifications.
- `demo_deals_sanitized.csv`: XAUUSD deal observations with ticket/order/comment identifiers omitted.
- `round_trip_cost_summary.json`: position-grouped commission/fee/swap/profit observations. Incomplete or ambiguous positions are excluded from per-side estimates.
- `manifest.json`: SHA-256 and byte length for each other package file.
- `package-verification.json`: independent verifier result confirming the package hashes, DEMO/read-only account state, XAUUSD contract, sanitized deal schema, and summary counts. It never marks the commission schedule verified.

A completed DEMO position can corroborate the commission charged on that account
and instrument. It does not establish the broker's applicable schedule by
itself. The workflow runs `tools/verify_xauusd_demo_execution_cost_package.py` before
uploading the package. The package always leaves `commission_schedule_status`
unverified and `net_performance_allowed` false. The collector is read-only and contains no
order submission, order checking, position querying, or order-management path.
If no matching deal history exists, it records
`NEEDS_DEMO_DEAL_HISTORY` without failing the separate tick-integrity result.


## Walk-forward runtime integration

The preregistered walk-forward plan remains locked as
`UNVERIFIED_REQUIRED_INPUT`; do not edit the plan to self-assert that
commission has been verified. The evaluator accepts commission evidence only
as explicit runtime inputs:

```bash
python -m tools.mt5_xauusd_walk_forward \
  --catalog path/to/session-catalog.json \
  --stage validation \
  --commission-evidence path/to/verified-commission-evidence.json \
  --commission-source-artifact path/to/original-broker-schedule.pdf \
  --commission-verification-artifact path/to/independent-review-record.pdf
```

The validator checks both the original source artifact SHA-256 and a separately hashed, scope-bound Ed25519-signed review attestation against the separately pinned trusted key, DEMO account mode,
exact broker symbol, USD profit/commission currency, per-side charging basis,
contract size, and that the schedule's effective period covers the entire
evaluation partition. The contract size and broker symbol must also match every
evaluated session manifest. Independent verification may occur after historical
market data was collected; its timestamp must not be in the future relative to
the verification run.

When evidence is absent, validation reports remain gross-only and net values
stay null. When evidence is valid, the evaluator subtracts round-turn commission
once from every candidate and directional benchmark outcome, using each
outcome's executable entry price. It reports gross and net separately.

A validation configuration becomes eligible for holdout selection only when it
passes the sample-size gate and, at **every** registered slippage level (0, 1,
2, and 5 points per side), has positive mean net return, a positive
session-clustered 95% lower confidence bound, and positive lower-bound
outperformance against NO_TRADE, ALWAYS_LONG, and ALWAYS_SHORT. This is a
research selection gate, not authorization to trade.

Holdout remains sealed unless runtime commission evidence is supplied and the
committed validation report plus selection-freeze record satisfy the existing
chronology and hash-binding requirements. The preregistered plan is not
rewritten to manufacture a verified status.


## Signed reviewer attestation

The review JSON is canonicalized using UTF-8 JSON with sorted keys and compact separators, excluding `signature_ed25519_base64`, then signed with Ed25519. It must bind the exact source SHA-256, reviewer identity and organization, approval status, XAUUSD/XAUUSDm DEMO/USD scope, contract size, per-side commission, effective period, review timestamp, and independence statement. The public key is supplied separately; its raw Ed25519 key fingerprint is SHA-256. The fingerprint must come from a separately authenticated reviewer channel and must not be copied from the same untrusted evidence package. Synthetic test keys and attestations are test fixtures only and are never broker evidence.
