# Phase 8 — engineering progress and decision log

**Repository:** `Nexora-Apparel/mt5-scalping-engine`  
**Pull request:** [#61](https://github.com/Nexora-Apparel/mt5-scalping-engine/pull/61)  
**Working branch:** `phase8-distinct-validation-date-guard`  
**Last recorded repository state:** 2026-11-17  
**Scope:** XAUUSD only; authenticated Exness MT5 DEMO; read-only research and data collection.

> This is the living project log. Append dated entries when implementation, evidence, decisions, or blockers change. Distinguish code written from code tested, and distinguish a completed research run from strategy approval.

## 1. Current project state

- PR #61 is open, draft, and unmerged.
- The PR head last verified for this log was `3f4be6b674d2d9c421bdb08cde3dc0e4da506025`.
- `main` remains unchanged.
- Four eligible live validation sessions are preserved across four distinct UTC dates:
  - `validation_01` — 2026-11-13
  - `validation_03` — 2026-11-15
  - `validation_04` — 2026-11-16
  - `validation_05` — 2026-11-17
- `validation_02` is retained as audit evidence but excluded from eligible date count because it duplicates the UTC date of `validation_01`.
- The v1 baseline research evaluation completed, but **no candidate was approved**.
- The final holdout remains sealed.
- Historical MT5 tick retrieval is being investigated as a way to reduce calendar waiting without misrepresenting retrospective data as prospective collection.

## 2. Why the Phase 8 approach changed

The original prospective v2 design adds eight future 30-minute sessions on eight distinct UTC dates. Review identified that the proposed schedule included market-closed weekend windows and overlap windows one hour early after the US daylight-saving transition.

A separate research review proposed a faster, evidence-preserving alternative:

1. Probe historical XAUUSD ticks from the authenticated Exness MT5 terminal.
2. Compare an overlapping historical interval with the already verified `validation_05` live tick capture.
3. If source quality and coverage are adequate, build a separately versioned historical-replay dataset and plan.
4. Keep a short live DEMO read-only capture for present-day terminal/feed operation.
5. Preserve chronological evaluation, date/session dependence controls, multiple-testing safeguards, commission verification, and the sealed holdout.

This is an acceleration of data acquisition, not a shortcut to approval. Historical quote records are not broker fills and cannot prove account-specific execution, slippage, or commission.

Detailed research and source references: [PHASE8_ACCELERATED_VALIDATION_RESEARCH.md](PHASE8_ACCELERATED_VALIDATION_RESEARCH.md).

## 3. Work completed or recorded

| Work item | What changed / evidence | Reason |
|---|---|---|
| Distinct-date eligibility | Kept `validation_02` excluded from eligible count; four distinct eligible UTC dates remain | Multiple sessions on one date must not be represented as independent dates |
| Collector session allowlist | Extended accepted IDs to `validation_01` and `validation_03`–`validation_13` | The v2 workflow exposed IDs that the collector previously rejected |
| Collector tests | Updated accepted-ID coverage and added rejection coverage for `validation_14` | Prevent unregistered collection IDs |
| Historical tick probe | Added `tools/mt5_xauusd_historical_tick_probe.py` using MetaTrader5 `copy_ticks_range` | Test whether the connected broker terminal can supply historical ticks |
| Historical probe tests | Added `tests/test_mt5_xauusd_historical_tick_probe.py` | Test UTC parsing, DEMO/read-only manifest behaviour, hashing, and empty results |
| Manual probe workflow | Added `.github/workflows/xauusd-historical-tick-probe.yml` | Run the bounded historical request on a Windows runner with the configured MT5 terminal |
| PR activity record | Added a PR comment describing the probe implementation and intended first comparison interval | Preserve implementation context and avoid implying that the probe has already run |
| Research redesign | Added `docs/PHASE8_ACCELERATED_VALIDATION_RESEARCH.md` | Evaluate a faster route without weakening statistical or safety gates |

**Important status distinction:** These entries record implementation and repository evidence. They do not, by themselves, mean the new historical probe has run, that source parity has been established, or that all tests for the newest commit have passed.

## 4. Baseline evidence — not approved

Formal v1 evaluation:

- Workflow run: [44112391721](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44112391721)
- Job: `134141209101`
- Artifact: `14340019644`
- Report SHA-256: `677818dd2b2b266dfce3ce280277de89684fb270fa238e22e86b2ce62df00931`
- Status: `RESEARCH_EVALUATION_COMPLETE`
- Candidate approval: `NOT_APPROVED`
- Candidate/horizon rows: 112; all 112 not approved
- No configuration had a date/session-clustered 95% confidence interval lower bound above zero.
- Commission remained unverified; net performance was blocked.
- Outcomes were theoretical bid/ask quote marks, not actual broker fills.
- Holdout eligibility remained false.

Interpretation: this was a research rejection of the current candidate set on the available sample, not a collection or CI failure. Do not tune the frozen candidate registry against this result.

## 5. Current implementation review findings

A source inspection after adding the probe identified issues that must be corrected and tested before manual execution:

1. **Python string escaping in the historical probe:** the CSV writer's line terminator and manifest trailing newline appear to be encoded as literal backslash-plus-`n`, rather than actual newline characters. Correct these to match the existing collector's newline handling.
2. **Default terminal path:** the probe's fallback `MT5_TERMINAL` path contains doubled backslashes in a raw string. Normalize it to the same Windows path convention used by the collector.
3. **Probe/collector helper contract:** confirm `connect_expected_account`, `discover_symbol`, `utc_iso`, and `DEMO_TRADE_MODE` are imported from the expected module and match their runtime signatures/return values.
4. **Pagination and ordering:** test full and partial 10,000-record batches, millisecond overlaps, duplicate removal, end-boundary handling, and termination when the broker returns repeated timestamps.
5. **Workflow dispatch availability:** GitHub generally requires a `workflow_dispatch` workflow to exist on the default branch before it can be manually dispatched from the Actions UI. This workflow currently exists on the PR branch only. Do not merge PR #61 merely to expose the manual button. Resolve dispatch mechanics without silently changing `main` or exposing secrets to untrusted PR code.
6. **Signer trust:** Authenticode validity, MetaQuotes Ltd. publisher identity, and Code Signing EKU are checked by the workflow. Independent pinning of the signer thumbprint against Exness-controlled evidence is still outstanding.

Until these items are addressed, the historical probe must be treated as **not yet ready for manual execution**.

## 6. Next implementation sequence

| Order | Next action | Completion evidence |
|---:|---|---|
| 1 | Fix the historical probe string/path defects and review helper contracts | Corrected source diff and focused unit tests |
| 2 | Strengthen pagination, timestamp-boundary, duplicate, and failure-path tests | Passing focused test run |
| 3 | Review the workflow's dispatch and secret-access design without merging or modifying `main` | Documented, safe manual trigger path |
| 4 | Run the full repository Python tests, compilation, and shell syntax checks | Successful CI run tied to the exact PR HEAD |
| 5 | Provide the owner the direct Actions link and exact input instructions when the workflow is genuinely dispatchable | Manual run instructions with the exact UTC interval |
| 6 | Run the historical probe over the exact `validation_05` overlap interval | Completed run and downloadable raw CSV/manifest artifact |
| 7 | Compare historical results against the preserved live `validation_05` capture | Counts, coverage, timestamp/quote matching, gaps, spread and hash report |
| 8 | If source quality passes, design a separately versioned historical replay plan before evaluating results | Preregistered plan and immutable input manifest |
| 9 | Run unchanged candidates with chronological partitions and dependence/multiple-testing controls | Research report; no automatic candidate approval |
| 10 | Keep live read-only verification and all independent release gates separate | Explicit evidence for each gate |

## 7. Manual execution handoff format

When a manual action is required, the project update must contain:

- Direct GitHub Actions workflow URL.
- Exact workflow name and button to press.
- Exact `from_utc` and `to_utc` values to enter.
- Expected run name and success/failure indicators.
- Exact artifact name to download.
- Instruction to upload the artifact back into this conversation for integrity and source-parity review.

Do not ask the owner to inspect code, edit workflow YAML, or supply credentials in chat. Credentials remain in GitHub Actions secrets.

## 8. Safety and release gates — unchanged

- Historical probe and collector are read-only.
- XAUUSD only; DEMO account identity must be verified.
- No order submission, position management, or live/real-money execution in this workflow.
- Terminal trading and DLL permissions remain disabled by the collector workflow.
- No weakening of account identity, installer signature, or read-only controls.
- No candidate freeze, holdout access/scoring, performance certification, production deployment, or real-money trading until the relevant gates are independently satisfied.
- Outstanding evidence includes applicable Exness commission/fee verification, independent reviewer attestation, out-of-band Ed25519 fingerprint verification, independent signer-thumbprint pinning, and manual owner-controlled DEMO reactivation rehearsal.

## 9. Append-only update template

Use this format for each material change:

### YYYY-MM-DD — Short change title

- **Starting commit / PR head:**
- **Files changed:**
- **What changed:**
- **Why it changed:**
- **Tests and exact run links:**
- **Evidence/artifact IDs and hashes:**
- **Result:** PASS / FAIL / BLOCKED / NOT RUN
- **Remaining risks or blockers:**
- **Next action:**

Never overwrite a failed result with a later success. Record the later success as a new entry and retain the earlier result for auditability.
