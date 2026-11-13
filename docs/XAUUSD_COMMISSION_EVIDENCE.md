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
