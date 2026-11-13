# XAUUSD DEMO commission evidence contract

This directory contains the schema contract for broker-cost evidence. The template is deliberately unverified and cannot unlock net scoring.

## Required provenance
- Account mode must be DEMO and the broker symbol must match the collected instrument.
- Contract size must be confirmed from the applicable Exness instrument specification.
- Commission must be stated in USD per lot per side, with effective dates and an explicit charging basis.
- The source artifact must be retained securely; only a sanitized reference and SHA-256 belong in the repository.
- Independent verification must be documented with a separate reference and timestamp.

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

A completed DEMO position can corroborate the commission charged on that account
and instrument. It does not establish the broker's applicable schedule by
itself. The package always leaves `commission_schedule_status` unverified and
`net_performance_allowed` false. The collector is read-only and contains no
order submission, order checking, position querying, or order-management path.
If no matching deal history exists, it records
`NEEDS_DEMO_DEAL_HISTORY` without failing the separate tick-integrity result.
