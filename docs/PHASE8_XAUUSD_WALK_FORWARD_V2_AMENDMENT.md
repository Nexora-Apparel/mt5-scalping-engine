# Phase 8 — V2 preregistration amendment (draft)

**Status: DRAFT — NOT FROZEN; NO COLLECTION AUTHORIZED.**

## Purpose

This amendment establishes a separately versioned evaluation protocol for the corrected replay implementation. It does not modify or replace the original v1 plan, strategy registry, validation report, source CSVs, or holdout. It does not retroactively repair or rescore the four v1 validation dates.

## Frozen-v1 preservation boundary

- Original v1 validation sessions `validation_01` through `validation_04` are prohibited from corrected-performance rescoring.
- Original validation artifact: `14888181358`; ZIP SHA-256 `e2bd914a1598eb03e1ec83cbe03de2d149609f11c63483a2f934353ab3b2154d`.
- Original registry SHA-256 recorded by its report: `6feaef79f5c1481920b5c2519c72d3ade7aa29849ae9b7cf4fee4e410b024c59`.
- Original v1 plan and all historical source data remain immutable.

## New prospective validation partition

The v2 protocol reserves four new, unique IDs: `v2_validation_01` through `v2_validation_04`. Each must be collected prospectively on a different UTC date, for at least 1,800 seconds, using authenticated Exness DEMO, canonical XAUUSD only. A session must not be relabelled from a prior artifact or reused from any earlier analysis. The collection workflow, catalog intake, and evaluator must explicitly support these IDs before dispatch. Until then, collection is not authorized.

At least 100 accepted, non-overlapping outcomes are required per candidate configuration and horizon across at least four distinct dates. If a configuration/horizon fails the sample gate, it remains under-sampled; the threshold must not be relaxed. Additional fresh prospective dates may be added only through a separately recorded, predeclared extension before those sessions are collected.

## Position-lane semantics

A simulation lane is keyed by the exact tuple:

`(candidate_id, complete_parameter_set, horizon_seconds)`

Each lane is an independent counterfactual research stream with at most one open position. The four horizon arms are not simultaneous positions and do not block one another during research evaluation. This independence exists only to compare fixed-horizon outcomes; it is not permission for a future execution system to hold four simultaneous positions. Any later execution architecture must impose one account-level position across all strategies/horizons.

For each lane and session:

1. A signal is eligible only if its signal-window end is not earlier than the previous accepted exit timestamp. If `signal_window_end_msc < next_free_msc`, skip it even if the first quote after the signal arrives after the previous exit.
2. The entry is the first quote strictly after signal-window end, with a maximum delay of 5,000 ms inclusive.
3. The exit is the first quote at or after entry plus the fixed horizon, with a maximum delay of 2,000 ms inclusive.
4. Longs enter Ask and exit Bid; shorts enter Bid and exit Ask. Spread is included exactly once. Slippage sensitivity remains 0/1/2/5 points per side.
5. An entry quote timeout does not open a position and does not block later signals.
6. An exit quote timeout leaves the lane unresolved and blocks every later signal in that lane for the rest of that session. The timeout itself is counted only when the sequential filter actually attempts it; later blocked precomputed outcomes count as skipped.
7. Every lane resets at the session boundary. No position or feature history carries between sessions.

## Feature-boundary rules

- First and last partial fixed-width buckets must be explicitly marked and excluded from all signal windows, lookback calculations, volatility scales, compression histories, and directional benchmarks.
- Every bucket in the complete required history for a signal must be contiguous and complete.
- No forward fill, partial-window substitution, or cross-session feature history is permitted.
- A signal must not be generated if any current or required historical bucket is partial.

## Cost and approval gates

Exness DEMO commission remains `UNVERIFIED_REQUIRED_INPUT`. Net performance is disabled until the applicable commission schedule or account statement is independently verified, archived, and hash-pinned. Gross quote marks cannot approve a candidate. Existing requirements for positive net mean, a session-clustered 95% lower confidence bound above zero, and outperformance of NO_TRADE, ALWAYS_LONG, and ALWAYS_SHORT after identical costs remain binding. Holdout remains sealed and must not reuse v1 holdout data as a new untouched holdout.

## Freeze-before-collection rule

Before any v2 collection, commit a selection-freeze/preregistration record binding the exact v2 plan hash, corrected implementation commit, frozen registry hash, the four new session IDs, and intended UTC collection schedule. The freeze commit timestamp must precede the earliest collection start. No retroactive freeze is valid.

## Operational safety

All collection is manual-dispatch, authenticated Exness DEMO, read-only. Trading, order submission, position management, DLL imports, and live trading remain disabled. No scheduled or unattended collector is authorized by this amendment.

## Current status and next implementation work

This document is a draft protocol only. It does not yet authorize collection. The next code work is to update the catalog/intake and evaluator schemas to accept the four v2 IDs while continuing to reject v1 validation IDs for corrected rescoring; add tests for ID separation, lane isolation, boundary exclusion, and freeze-before-collection; then freeze the plan and only then schedule the four prospective sessions.

Machine-readable companion: `research/xauusd_walk_forward_plan_v2_amendment.json`.
