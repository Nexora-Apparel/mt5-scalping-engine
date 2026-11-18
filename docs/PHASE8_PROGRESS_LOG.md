# Phase 8 — engineering progress and decision log

**Repository:** `Nexora-Apparel/mt5-scalping-engine`  
**Pull request:** [#61](https://github.com/Nexora-Apparel/mt5-scalping-engine/pull/61)  
**Working branch:** `phase8-distinct-validation-date-guard`  
**Last recorded repository state:** 2026-11-17  
**Scope:** XAUUSD only; authenticated Exness MT5 DEMO; read-only research and data collection.

> This is the living project log. Append dated entries when implementation, evidence, decisions, or blockers change. Distinguish code written from code tested, and distinguish a completed research run from strategy approval.

## 1. Current project state

- PR #61 is open, draft, and unmerged.
- The historical-probe implementation is currently recorded through commit `996d95088c628879349ef7c1d2335f188f868c1d`; the progress-log update itself will create a later PR head.
- `main` contains a narrowly scoped manual dispatcher at `.github/workflows/xauusd-historical-tick-probe-dispatch.yml` (latest dispatcher commit `bb7c97fe66c7f6f44e4a9d38d07f3080662db9c1`). It checks out the fixed Phase 8 PR branch; it does not merge PR #61 or copy the strategy implementation into `main`.
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
| Historical tick probe | Reworked as V2: inclusive UTC millisecond bounds, one-minute non-overlapping requests, strict tick-field validation, duplicate removal, chronological-order checks, atomic CSV publication, shared dataset audit, SHA-256 and source provenance | Prevent silent truncation/partial output and make historical evidence auditable |
| Historical probe tests | Expanded `tests/test_mt5_xauusd_historical_tick_probe.py` for offset normalization, chunk boundaries, endpoint inclusion, duplicate removal, malformed/out-of-range ticks, non-monotonic responses, DEMO rejection, empty results and API errors | Exercise the probe's fail-closed paths before any broker request |
| Manual probe workflow | Added PR-branch workflow `.github/workflows/xauusd-historical-tick-probe.yml` and a default-branch dispatcher `.github/workflows/xauusd-historical-tick-probe-dispatch.yml` | GitHub requires the manual-dispatch workflow to exist on the default branch; dispatcher checks out the fixed PR branch without merging it |
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

A source inspection identified and the implementation has now addressed these defects:

1. **CSV/manifest newline escaping:** corrected to real newline characters; tests assert the CSV does not contain escaped backslash-n records and the manifest ends with a newline.
2. **Default terminal path:** corrected to `C:\\MT5\\terminal64.exe`, matching the collector's Windows path convention.
3. **Probe/collector helper contract:** the probe uses the collector's `connect_expected_account`, `discover_symbol`, `utc_iso`, `validate_account`, `audit_ticks`, and `DEMO_TRADE_MODE`; the focused tests stub the account and broker helpers. Runtime integration against Exness remains untested.
4. **Retrieval completeness and ordering:** replaced the fragile 10,000-record cursor loop with one-minute, inclusive, non-overlapping UTC millisecond windows. Each chunk is independently requested; out-of-range, malformed, and backwards-ordered responses fail closed. The final CSV is audited using the collector's shared audit routine before its manifest is published.
5. **Workflow dispatch availability:** resolved with a dedicated dispatcher committed to `main`. It has only `contents: read`, checks out the fixed `phase8-distinct-validation-date-guard` branch with persisted credentials disabled, records the exact checked-out commit, and runs focused preflight tests before installing MT5 or using secrets. PR #61 remains unmerged.
6. **Signer trust:** Authenticode validity, MetaQuotes Ltd. publisher identity, and Code Signing EKU are checked by the workflow. Independent pinning of the signer thumbprint against Exness-controlled evidence is still outstanding.

The focused preflight tests are wired into the dispatcher, but have not yet been observed passing on GitHub Actions. Do not start a broker probe until the preflight succeeds. Independent installer signer-thumbprint pinning against Exness-controlled evidence remains outstanding.

## 6. Next implementation sequence

| Order | Next action | Completion evidence |
|---:|---|---|
| 1 | Complete code review of the V2 probe and focused tests | Source review plus passing preflight run |
| 2 | Execute focused tests through the main-branch dispatcher preflight | Passing pytest output tied to the checked-out PR commit |
| 3 | Verify manual dispatcher, branch pinning, permissions, and secret boundaries | Workflow run reaches preflight and does not proceed if tests fail |
| 4 | Run the full repository Python tests, compilation, and shell syntax checks | Successful CI run tied to the exact PR HEAD |
| 5 | Provide the owner the direct Actions link and exact input instructions when the workflow is genuinely dispatchable | Manual run instructions with the exact UTC interval |
| 6 | Run the historical probe over the exact `validation_05` overlap interval | Completed run and downloadable raw CSV/manifest artifact |
| 7 | Compare historical results against the preserved live `validation_05` capture | Counts, coverage, timestamp/quote matching, gaps, spread and hash report |
| 8 | If source quality passes, design a separately versioned historical replay plan before evaluating results | Preregistered plan and immutable input manifest |
| 9 | Run unchanged candidates with chronological partitions and dependence/multiple-testing controls | Research report; no automatic candidate approval || 10 | Keep live read-only verification and all independent release gates separate | Explicit evidence for each gate |

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


## 10. Append-only engineering update — 2026-11-17

- **Starting PR code commit:** `b700210ed758a19c74ebbbd63867f986ef74a129`
- **Files changed on PR branch:**
  - `tools/mt5_xauusd_historical_tick_probe.py`
  - `tests/test_mt5_xauusd_historical_tick_probe.py`
- **What changed:** Replaced the original historical request loop with fixed one-minute UTC millisecond windows; normalized tick access for MT5 structured records and test doubles; added finite-value, bid/ask, volume, timestamp-range and chronological-order validation; removed partial output on failure; writes CSV with actual newline delimiters; reuses the collector's `audit_ticks` before publishing the manifest; records the checked-out source commit, dispatcher commit and installer signer thumbprint.
- **Why:** The original code used an unsafe short-batch termination condition, had literal backslash-n output, and did not prove chunk-by-chunk integrity. A failed or incomplete response must not produce a PASS artifact.
- **Tests added:** UTC offset handling, non-overlapping chunks, inclusive final endpoint, duplicate removal, SHA-256, CSV/manifest newline integrity, invalid values, out-of-range records, non-monotonic provider response, non-DEMO rejection, empty data and broker API errors.
- **Manual trigger change on `main`:** Added `.github/workflows/xauusd-historical-tick-probe-dispatch.yml` (dispatcher commits `89fef6def381f564180644871403d0d65dbd86a3`, `35103dd0d651417f265aaa1c326f0fe6d8964626`, `2744af30fbe105789639b1087748ef90f84cb5a7`, and `bb7c97fe66c7f6f44e4a9d38d07f3080662db9c1`). It checks out only the fixed Phase 8 branch and runs focused pytest preflight before MT5 installation and credential use.
- **Result:** Code and workflow changes committed. Automated test result is **NOT YET RUN / NOT VERIFIED**; GitHub currently reports no check runs for the latest PR code commit.
- **Remaining risks:** Actual Exness historical API behavior, historical/live source parity, signer-thumbprint independent pinning, and all research/statistical release gates remain outstanding. No historical probe has been executed.
- **Next action:** Verify the focused preflight through GitHub Actions, correct any failures, then provide the manual dispatcher link and exact validation_05 overlap interval.


### 2026-11-17 — Historical probe preflight passed; manual dispatch enabled

- **PR code commit tested:** `91e765fa8b57460154e04230fd73e4225b0a2e8f`.
- **GitHub Actions run:** [44130806654](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44130806654).
- **Result:** PASS — 268 tests passed in 2.28 seconds; Python compilation and Linux shell syntax checks passed.
- **Workflow:** the default-branch manual dispatcher is present at [xauusd-historical-tick-probe-dispatch.yml](https://github.com/Nexora-Apparel/mt5-scalping-engine/blob/main/.github/workflows/xauusd-historical-tick-probe-dispatch.yml). It checks out the fixed Phase 8 branch, records the checked-out commit, runs focused historical-probe tests first, and only proceeds to MT5 installation and the historical API call if those tests pass.
- **Manual comparison interval:** `2026-11-17T13:50:00.282Z` through `2026-11-17T14:20:02.314Z`, matching the millisecond precision of the preserved `validation_05` live capture.
- **Not yet done:** no historical probe run has been dispatched; no historical artifact or source-parity result exists.
- **Remaining trust note:** installer Authenticode validity, MetaQuotes Ltd. publisher and Code Signing EKU are checked. Independent signer-thumbprint pinning against Exness-controlled evidence remains an outstanding assurance item; the observed thumbprint is recorded in the eventual probe manifest.
- **Next action:** owner manually dispatches the workflow using the exact interval above; inspect the resulting job and artifact before any historical dataset is admitted to research.


### 2026-11-17 — First Exness historical tick probe failed at interval validation

- **Workflow run:** [44133084809](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44133084809)
- **Job:** [134215186521](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44133084809/job/134215186521)
- **Checked-out source commit:** `78611a2853237f6893266a8693a602eba816ef31`.
- **Requested interval:** `2026-11-17T13:50:00.282Z` through `2026-11-17T14:20:02.314Z`.
- **Completed successfully:** credentials/input validation, focused preflight (10 passed), MT5 installer Authenticode/publisher/EKU checks, pinned MetaTrader5 package installation, and terminal shutdown.
- **Failed step:** historical retrieval exited with `historical API returned a tick outside the requested UTC interval`.
- **Artifact:** none; the probe correctly removed partial output and did not publish a success manifest.
- **Interpretation:** MT5 returned at least one tick whose millisecond timestamp did not satisfy the exact requested interval. The original error omitted the offending timestamp and offset, so the failure does not yet distinguish sub-second/range-boundary behavior from a larger timestamp/timezone discrepancy. Historical availability and source parity remain unproven.
- **Corrective change:** improved the probe error to report the offending tick's UTC timestamp, epoch milliseconds, offsets from both requested bounds, and the exact requested interval. Added a regression assertion for those diagnostic fields.
- **Code changes:** probe commit `db24dc3c9435114bccaecb4770c91e1cbc1840bd`; test commit `0ce513664d2a663f33818802b6efa6f725cbdc42`. The combined PR branch should be rechecked for the resulting latest HEAD and CI.
- **Result:** FAIL — runtime historical request; preflight and terminal setup passed. No dataset accepted.
- **Next action:** run CI on the corrected PR HEAD, then repeat the same 30-minute overlap request. Use the new timestamp diagnostic to identify the MT5 boundary/time conversion behavior before changing interval handling. Do not widen the accepted data window or silently discard out-of-range ticks.


### 2026-11-17 — Boundary diagnostics committed and full CI revalidated

- **Corrective probe commit:** `db24dc3c9435114bccaecb4770c91e1cbc1840bd`.
- **Regression-test commit:** `0ce513664d2a663f33818802b6efa6f725cbdc42`.
- **What changed:** Out-of-range tick failures now report the offending UTC timestamp and epoch milliseconds, signed millisecond offsets from both requested bounds, and the exact requested interval. The regression test asserts all diagnostic fields are present.
- **Why:** The first runtime attempt checked out `78611a2853237f6893266a8693a602eba816ef31`, which predates the diagnostic correction. Its log therefore contains only the generic error. A second request must run the corrected branch revision to identify the actual MT5 response behavior.
- **CI:** [Run 44134469699](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44134469699), job `134220125926`, associated with test commit `0ce513664d2a663f33818802b6efa6f725cbdc42`.
- **Result:** PASS — full repository suite `268 passed in 2.36s`; Python compilation and Linux bootstrap shell syntax checks passed. This is code/CI validation only, not MT5 historical runtime validation.
- **Historical probe status:** Still FAIL on the first runtime attempt; no CSV, manifest, or accepted historical data exists. No conclusion about Exness historical coverage can yet be drawn.
- **Next action:** Manually dispatch the default-branch workflow again using the same exact overlap interval. Confirm the run checks out a commit containing `db24dc3` and `0ce5136`; then inspect the detailed offending-tick diagnostic before making any further code change.
- **Safety and release status:** XAUUSD-only, verified Exness DEMO, read-only; no orders or position management. PR #61 remains open/draft/unmerged. No widening of the accepted range, no historical backfill expansion, no holdout access, and no strategy approval.


### 2026-11-17 — Second historical probe isolated MT5 range-boundary spill

- **Workflow run:** [44137204291](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44137204291)
- **Job:** [134229887785](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44137204291/job/134229887785)
- **Checked-out source:** `178a5e7dc3e6775408ef754d8bceab6b4ab35854`.
- **Exact diagnostic:** MT5 returned tick `2026-11-17T13:50:00.137Z`, 145 ms before the requested start `13:50:00.282Z`; it was 60,144 ms before the first chunk end. This is a small range-boundary spill, not evidence of a timezone shift or a tick from a different minute/day.
- **Root cause:** The probe passed the exact requested millisecond boundaries directly to MT5 `copy_ticks_range` and treated any adjacent boundary record as fatal. MT5's range response can include a nearby tick outside the exact boundary. Strict validation was applied at the wrong layer: the API query boundary and the final dataset acceptance boundary must be distinct.
- **Corrective implementation:** Query each logical one-minute chunk with a bounded 2,000 ms guard band on both sides; validate all returned tick fields and provider ordering within that padded query; then retain only records whose `time_msc` falls inside that chunk's exact inclusive millisecond interval. Guard-band records are counted in chunk diagnostics and excluded from the CSV. The final dataset remains strictly within the user-requested overall interval. The manifest records padding and exact filtering semantics. The 2-second guard is bounded; records outside it still fail closed.
- **Regression tests added:** A realistic -145 ms leading spill and +120 ms trailing spill are excluded while the exact in-range tick is retained; a tick beyond the 2-second guard fails closed. Existing chunk, ordering, duplicate, integrity and DEMO/read-only tests remain.
- **Code commit:** `32ac493fdc726950576b9e17c1e5646c152c6dc9`.
- **Test commit:** `dd51a7a537cd3693c36a2346e98f34556ee8b9d0`.
- **CI/runtime status:** The patch is committed but the new test revision has not yet been observed passing in GitHub Actions. No historical CSV or manifest was produced by run 44137204291. The boundary-padding fix is an evidence-based correction, not yet proven against a subsequent Exness runtime request.
- **Next action:** Run full CI on the updated branch, then repeat the same 30-minute overlap request. Verify the run checked out this patch, inspect manifest filtering counters, and compare accepted historical ticks with the live capture. Do not expand to multi-day backfill until this exact overlap test and source-parity audit pass.
- **Safety/release:** XAUUSD-only; authenticated DEMO; read-only; no order or position-management calls. PR #61 remains open/draft/unmerged; holdout remains sealed; no strategy approval.


### 2026-11-17 — Third historical probe exposed spill beyond padded query

- **Workflow run:** [44144128359](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44144128359)
- **Job:** [134254505247](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44144128359/job/134254505247)
- **Checked-out source:** `5bdaa8377c8babc006409619de0207bb7431e39e`.
- **Preflight:** 12 focused historical-probe tests passed. Terminal installation, Authenticode validation, MetaQuotes publisher check, and pinned MetaTrader5 package setup passed.
- **Exact diagnostic:** MT5 returned tick `2026-11-17T13:56:58.040Z`, 242 ms before the *padded query start* `13:56:58.282Z`. The earlier 2,000 ms padding around the logical chunk was not enough because the API itself returned a record outside that padded query.
- **Corrective implementation:** Added a separate bounded `RANGE_RESPONSE_SPILL_TOLERANCE_MILLISECONDS=2000` around the padded API query for validating provider-returned rows. These outer-spill rows are still excluded by the unchanged exact logical-chunk filter. The manifest records both query padding and response-spill tolerance. Rows beyond the combined bounded envelope still fail closed.
- **Regression coverage:** Added a test for the observed 242 ms spill beyond the padded query and adjusted the fail-closed test to reject records beyond the combined bound.
- **New code/test commits:** source and initial regression test followed by test-bound update; verify latest branch CI before another runtime request.
- **Runtime status:** No CSV or manifest was produced; no historical data accepted. This failure does not establish that Exness lacks history; it establishes MT5 range responses can spill outside the supplied query range.
- **Next action:** Wait for CI on the latest PR head, inspect the full focused and project test results, then repeat the same 30-minute interval only if CI passes. Do not widen the requested interval or expand to backfill until the overlap/parity audit passes.
- **Safety:** XAUUSD-only, authenticated Exness DEMO, read-only; no orders or position management. PR #61 remains draft/open/unmerged.


### 2026-11-17 — Historical XAUUSD probe succeeded; exact live-feed parity established

- **Workflow run:** [44148023850](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44148023850), job 134268379978; conclusion **SUCCESS**.
- **Checked-out source ref/commit:** phase8-distinct-validation-date-guard / 4818cf8b3aa154ea5ce22104754551602a082956.
- **Requested interval:** inclusive UTC milliseconds 2026-11-17T13:50:00.282Z through 2026-11-17T14:20:02.314Z.
- **Artifact:** [14357512410 — veltrix-xauusd-historical-probe-1](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44148023850/artifacts/14357512410); ZIP SHA-256 018cb97c8e8f05ab8db9956b3ade58b6626e95d8f5640740199a2184a0bc974b.
- **Historical CSV:** 8,988 rows; SHA-256 c3cc9c61f3bd4f395f183bf43be76e9c7b5886c64f253ac6f3540451f529a7ee; 31 one-minute chunks; dataset audit PASS. Published timestamps are all inside the exact requested interval. First/last ticks: 13:50:00.341Z / 14:20:02.161Z. Maximum inter-tick gap 1,877 ms; no gaps above 5 seconds. No nulls, negative bid/ask, crossed quotes, or exact duplicate quote rows. There are 104 repeated millisecond timestamps containing distinct quote rows; this is not exact-row duplication and is consistent with multiple quote updates sharing millisecond resolution.
- **Critical parity audit:** compared against preserved live validation_05 artifact 14335284843 (CSV SHA-256 5917a92e4feaa05f3f9756426baa59deb068fa21ab0c3950f7385a44c3dc7124). All 8,983 live rows match historical rows exactly on timestamp, bid, ask, last, volume, volume_real and flags. No live row is missing from historical output; historical output contains exactly five additional rows, all after the final live-captured tick (14:20:00.979Z) and before the requested end. The 8,879 shared unique timestamps have 100% exact bid/ask agreement (zero price differences). Both streams have the same 1,877 ms maximum inter-tick gap. This establishes exact parity for the overlapping captured live evidence, not universal historical-feed equivalence.
- **Spread context:** both captures show a constant 0.240 quote spread (240 points at 0.001 point size) throughout this interval. This is a property of this observed demo session and must not be assumed to represent all Exness account conditions or live execution.


### 2026-11-18 — Historical probe provenance and security review continuation

- **Reviewed PR state:** PR #61 remains open, draft, mergeable and unmerged at head `3215564b660df31820f28976c8e010f4f5907041`; PR #67 remains open, mergeable and unmerged at head `0edd4f9f9f3b479b2f6ef56d9bd287b8e0c74482`. No merge was performed.
- **CI evidence:** Project tests run [#44216203076](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44216203076) remains the latest verified run on PR #61 and passed the full configured checks.
- **Files reviewed:** `.github/workflows/xauusd-historical-tick-probe-dispatch.yml`, `.github/workflows/xauusd-historical-tick-probe.yml`, `tools/mt5_xauusd_historical_tick_probe.py`, `tests/test_mt5_xauusd_historical_tick_probe.py`, and `tests/test_phase8_collection_orchestration.py`.
- **Code review result:** The reviewed probe enforces explicit timezone-aware millisecond UTC bounds, bounded one-minute requests, bounded MT5 response spill, exact logical-window filtering before publication, monotonic provider ordering, finite/valid quote fields, exact-row deduplication, DEMO account validation, XAUUSD symbol discovery, audited CSV publication and SHA-256 manifest generation. It contains no order-submission or position-management call. The dispatcher uses `contents: read`, disables persisted checkout credentials, runs focused tests before MT5 installation, validates the installer Authenticode signature, publisher and Code Signing EKU, and disables terminal automated trading and DLL imports.
- **Cross-branch status:** PR #61 contains the provenance-hardened historical workflow and current default-branch dispatcher; its regression tests protect those workflow settings. The standalone PR #67 remains unmerged and must not be merged without explicit owner authorization.
- **Installer trust review:** Exness's official MT5 download page is the source for the Exness-linked installer URL: https://www.exness.com/metatrader-5/ . MetaQuotes publishes official MT5 download information: https://www.metaquotes.com/en/download . Neither reviewed official page publishes an independently verifiable SHA-1 signer-certificate thumbprint for this installer. Third-party certificate observations are not an acceptable substitute for Exness-controlled evidence. Therefore, the workflow's captured thumbprint remains provenance metadata, **not an independently pinned trust anchor**.
- **Manual-action capability:** The connected GitHub actions available in this session expose workflow-run inspection and rerun operations, but no workflow-dispatch action. No broker-connected run was initiated and no new artifact is claimed.
- **Result:** CODE REVIEW PASS for the inspected controls; INDEPENDENT SIGNER PINNING BLOCKED pending Exness-controlled certificate fingerprint evidence. No strategy approval, holdout access, execution enablement, or live trading.
- **Next action:** Obtain the installer signer certificate thumbprint through an independently authenticated Exness support response or another Exness-controlled channel, verify its scope/validity and compare it to the thumbprint observed at runtime. Then, after the required PR authorization/merge gate, run one bounded read-only DEMO probe and inspect the complete provenance manifest before planning any backfill.


### 2026-11-18 — PR #67 merged; Phase 8 branch synchronization required

- **Owner authorization:** The owner explicitly confirmed approval to complete the outstanding PR authorization gate and continue the listed sequence.
- **PR #67:** Successfully merged into `main` using a merge commit. PR: https://github.com/Nexora-Apparel/mt5-scalping-engine/pull/67 . Merge commit: `efcb9edcb4a3973e2a04fb8713aebf1a5ca05bff`. This publishes checkout credential hardening and explicit source commit/ref plus installer signer thumbprint provenance wiring on the default branch.
- **PR #61 impact:** After PR #67 merged, GitHub reports PR #61 still open/draft/unmerged but temporarily not mergeable; its feature branch is now 120 commits ahead and 4 commits behind `main`. No force push or merge was attempted. Reconcile the four new main commits into the Phase 8 branch and rerun CI before considering any merge of PR #61.
- **Main-branch workflow status:** The merge succeeded. The connected workflow-run query returned no run records for the merge commit at the time of inspection; this is not evidence of a passing post-merge workflow.
- **Signer fingerprint:** No authenticated Exness support channel is connected in this environment, and the reviewed official public Exness/MetaQuotes pages do not provide an independently verifiable signer certificate thumbprint. No support ticket or response was fabricated. Obtain the fingerprint through the owner's authenticated Exness support account, then compare the exact SHA-1 thumbprint to the runtime Authenticode signer certificate before treating it as pinned.
- **Historical probe:** Not dispatched. The available GitHub integration has no workflow-dispatch action, and the authenticated signer pinning gate remains open. No new broker artifact or CSV is claimed.
- **Result:** PR #67 MERGED; PR #61 SYNC REQUIRED; SIGNER PINNING BLOCKED; HISTORICAL PROBE NOT RUN.
- **Next action:** Obtain Exness-controlled signer evidence; synchronize PR #61 with current `main`; verify branch CI; then use the default-branch manual dispatcher for a single bounded, read-only Exness DEMO XAUUSD request and audit all provenance fields and CSV contents.


### 2026-11-18 — Official Exness installer source confirmed

- **Owner instruction:** Use only the official installer source for the historical XAUUSD probe.
- **Primary-source verification:** Inspected the live official Exness MT5 page at https://www.exness.com/metatrader-5/ . Its Windows MT5 download control links directly to the exact URL already configured in the Phase 8 dispatcher: https://download.terminal.free/cdn/web/exness.technologies.ltd/mt5/exness5setup.exe . The link was followed from the official Exness page; the endpoint returned an executable download response. This establishes the URL's provenance from Exness's own download page, rather than reliance on a third-party mirror or a guessed installer URL.
- **Independent developer source:** MetaQuotes's official download page is https://www.metaquotes.com/en/download and also links to its Windows MT5 download.
- **Workflow disposition:** The dispatch workflow's current installer URL already matches the official Exness page's link exactly; no source substitution is needed. Keep the Authenticode checks (valid signature, MetaQuotes Ltd. publisher, Code Signing EKU) and capture the signer thumbprint in the manifest. Do not describe the captured thumbprint as independently pinned merely because the download URL is official.
- **Safety:** The installer is used only in the bounded, read-only historical probe. DEMO identity checks, XAUUSD-only scope, disabled automated trading and DLL imports, and absence of order submission/position management remain mandatory.
- **Next action:** Synchronize PR #61 with current main, verify CI, then dispatch only after the provenance and safety gates are satisfied. Audit the manifest and CSV before any historical backfill.
### 2026-11-18 — Reconciled PR ancestry and made provenance mandatory

- **Fresh-state audit:** Before synchronization, PR #61 was open/draft/unmerged at 7c5afb5e70690dbd994c5309b69c5999f3c60990; current main was efcb9edcb4a3973e2a04fb8713aebf1a5ca05bff. GitHub compare reported 122 commits ahead and 4 behind. The earlier d561ad3 commit did not include the newly merged PR #67 commit as a second parent, despite its message; therefore it did not resolve ancestry.
- **Safe reconciliation:** Verified that the PR branch already retained the Phase 8 dispatcher watch paths and the current main versions of the two files changed by PR #67. Created true two-parent merge commit 7a646437160600a8679275534e7ab81c29511528 with the existing PR tree unchanged, parents PR head 7c5afb5e... and current main efcb9edc...; advanced the branch using an expected-head check (no force push). GitHub now reports PR #61 mergeable and zero commits behind main. The PR remains open, draft, and unmerged.
- **Merge CI:** Project tests run [44220444853](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44220444853) completed successfully on merge commit 7a646437... This run predates the subsequent provenance-hardening code commit below.
- **Provenance audit:** Confirmed the dispatcher exports the checked-out Phase 8 source ref/commit and signer thumbprint; the manifest dispatcher_commit is sourced from GitHub GITHUB_SHA, which identifies the workflow-dispatching commit on the default branch. The four manifest fields are source_ref, source_commit, dispatcher_commit, and installer_signer_thumbprint.
- **Fail-closed correction:** The collector previously permitted absent provenance values to be written as JSON nulls. Updated it to validate a non-empty source ref and 40-hex source commit, dispatcher commit, and SHA-1 signer thumbprint before initializing MT5. Missing or malformed provenance now aborts before broker connection or CSV publication. Added parameterized regression tests for all four missing fields and malformed commit metadata.
- **Code commit:** 29b1fd5810f4f42f82bd0af7c39102486035da06. The merge-only CI pass does not validate this later commit; a fresh CI run is required before any probe.
- **Historical probe:** Still not dispatched after provenance hardening. No new broker artifact or CSV is claimed.
- **Remaining manual gates:** (1) authenticated Exness support evidence for independent signer-thumbprint pinning, if that additional trust-anchor requirement is retained; (2) manual GitHub Actions dispatch of the default-branch workflow, because the connected GitHub integration exposes no workflow-dispatch operation. The official Exness-linked installer URL is already verified; do not use third-party mirrors.
- **Safety/release:** Historical collection remains authenticated Exness DEMO, XAUUSD-only, bounded and read-only. No order submission, position management, holdout access, strategy tuning, candidate approval, or live execution.
- **Next action:** Run and inspect full CI on the latest provenance-hardening commit, then continue code review and prepare the single bounded overlap probe. Stop at the manual dispatch/support boundary; inspect all four provenance fields and CSV hash/audit before considering any expansion.
### 2026-11-18 — Enforced a hard bound on each historical request

- **Risk found:** The workflow timeout limited runner duration, but the collector did not independently cap the requested historical interval. A manually supplied long date range could therefore initiate an unintended large backfill before timing out.
- **Safety correction:** Added MAX_PROBE_DURATION_MILLISECONDS = 31 minutes to the collector. Requests exceeding 31 minutes now fail before MT5 initialization, broker connection, or CSV creation. This keeps the known overlap verification window (30 minutes, 2.032 seconds) within the permitted single-request envelope while requiring a separately reviewed plan for larger backfills.
- **Regression coverage:** Added a test that requests 31 minutes plus 1 millisecond and asserts rejection before terminal initialization and without data output.
- **Code commit:** bca0a50c42b75b9e1fdf5444c123f8b8f8a3f969. CI for this newest safety-limit commit is pending; the prior provenance-hardening commit 29b1fd5810f4f42f82bd0af7c39102486035da06 passed Project tests in run [44220583612](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44220583612).
- **Next action:** Verify full CI on the 31-minute cap commit, then inspect the latest PR state and the dispatcher workflow. Do not dispatch until the CI result is green and the remaining manual trust/dispatch gates are addressed.
### 2026-11-18 — 31-minute collection bound passed CI

- **CI:** Project tests run [44220735496](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44220735496) completed successfully on code commit bca0a50c42b75b9e1fdf5444c123f8b8f8a3f969. All configured steps passed: dependency installation, Linux bootstrap shell syntax, Python compilation, and the full unit/fail-closed test suite.
- **Safety state:** The collector now rejects requests longer than 31 minutes before terminal initialization; complete provenance is mandatory before any MT5 connection. The known 30m2.032s overlap interval remains within the hard bound.
- **PR state:** PR #61 remains open/draft/unmerged and mergeable. Current main is an ancestor of the feature branch; no behind commits remain. No strategy approval or PR merge was performed.
- **Manual intervention boundary:** The available GitHub integration has no workflow-dispatch operation, and no authenticated Exness support session is connected for the independent signer-thumbprint request. No probe was dispatched and no new artifact is claimed.
- **Prepared bounded probe inputs:** start 2026-11-17T13:50:00.282Z; end 2026-11-17T14:20:02.314Z (inclusive UTC milliseconds; 30 minutes, 2.032 seconds). This repeats the previously audited overlap interval, not an expanded backfill.
- **Next action:** Use the default-branch manual dispatcher for this single interval after the owner completes the authenticated support check. Then inspect source_ref, source_commit, dispatcher_commit, installer_signer_thumbprint, verified DEMO identity, read-only flags, exact UTC bounds, CSV SHA-256, row count and audit output.

### 2026-11-18 — Provenance-complete historical probe succeeded; flag-bit discrepancy isolated

- **Workflow run:** [44221513372](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44221513372); job [134524256386](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44221513372/job/134524256386). Dispatcher workflow completed successfully on `main` at `efcb9edcb4a3973e2a04fb8713aebf1a5ca05bff`; it checked out the fixed Phase 8 branch at `9ed2cdc5bd5fdffe510abd0f004b63d0bc299349`.
- **Installer verification:** Windows Authenticode status `Valid`; publisher `MetaQuotes Ltd.`; Code Signing EKU present. Runtime signer SHA-1 thumbprint: `5A64A7AED24C33DED342D01D01FA5286F06DA6DC`. This is a verified runtime observation under Windows trust validation, **not** an independently Exness-pinned fingerprint. The Exness support confirmation remains outstanding.
- **All four provenance fields are present and valid in the manifest:** `source_ref=phase8-distinct-validation-date-guard`; `source_commit=9ed2cdc5bd5fdffe510abd0f004b63d0bc299349`; `dispatcher_commit=efcb9edcb4a3973e2a04fb8713aebf1a5ca05bff`; `installer_signer_thumbprint=5A64A7AED24C33DED342D01D01FA5286F06DA6DC`.
- **Probe safety and interval:** authenticated Exness MT5 DEMO; canonical symbol XAUUSD / broker symbol XAUUSDm; `trading_enabled=false`, `order_submission=false`, `position_management=false`; exact inclusive interval `2026-11-17T13:50:00.282Z` through `2026-11-17T14:20:02.314Z`; 31 one-minute chunks.
- **Artifact:** [14391096861 — veltrix-xauusd-historical-probe-4](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44221513372/artifacts/14391096861). ZIP SHA-256: `bfb62c1a9e06c8daadbffdaa67801981a183f16e31cef128dba66fe25f225f01`. CSV SHA-256: `68c60fd798cd9e8c44423917d0c6bb1de27ef7bcca7eef330bc994e9a1c32576`; 8,988 rows; manifest and independent CSV hash agree; dataset audit PASS; no nulls, invalid bid/ask or crossed quotes; all timestamps monotonic and inside requested bounds; no exact duplicate quote rows. There are 104 repeated millisecond timestamps with distinct quote rows. Maximum intertick gap 1,877 ms; no gaps above five seconds.
- **Live overlap comparison:** Re-downloaded the preserved `validation_05` artifact 14335284843 and compared all 8,983 live rows against this new historical CSV. All 8,983 match on timestamp, bid, ask, last, volume and volume_real; there are five additional historical rows after the final live tick. No live quote row is missing. Bid/ask values and timestamp coverage therefore reproduce the prior overlap result.
- **New discrepancy requiring explicit handling:** The new historical CSV records `flags=134` (`0x86`) for every row, while both the earlier historical artifact 14357512410 and the live `validation_05` capture record `flags=6` (`0x06`) for the same matched rows. The quote fields are identical, but the full-row parity claim including `flags` does **not** hold for this run. Official MQL5 documentation defines the standard BID and ASK bits as 2 and 4 and lists the standard tick flags through SELL=64; it does not document the additional `0x80` bit. Preserve the raw value; do not silently mask it or infer its meaning. Treat this as an unresolved terminal/provider metadata difference and do not use this flag bit for strategy features until its origin and semantics are established.
- **Spread observation:** All 8,988 historical rows have a 0.240 bid/ask spread in this particular interval. This is not evidence of universal account spread or execution/fill quality.
- **Result:** PROBE PASS; provenance completeness PASS; dataset structural audit PASS; exact quote-field overlap PASS; full flag-field parity **NOT PASS / INVESTIGATION REQUIRED**; independent Exness signer pinning remains BLOCKED. Historical quotes remain quote evidence, not broker fills. No candidate approval, holdout access, strategy certification, PR merge, or trading authorization.
- **PR state:** PR #61 remains open, draft, and unmerged. No merge was performed.
- **Next action:** Investigate why the terminal returned the undocumented `0x80` flag bit in the new historical response while the prior historical/live captures did not. Preserve raw flags and add a documented flag-distribution diagnostic/test if appropriate. Keep the dataset quarantined from any feature pipeline that interprets flags until resolved; continue the independent Exness signer confirmation separately.

### 2026-11-18 — Tick flag discrepancy explained as an undocumented MT5 internal bit; diagnostics added

- **Primary documentation review:** MetaQuotes' MQL5 reference and Python integration documentation enumerate six public tick flags: BID \`0x02\`, ASK \`0x04\`, LAST \`0x08\`, VOLUME \`0x10\`, BUY \`0x20\`, and SELL \`0x40\`. They do not define \`0x80\`.
- **Additional technical evidence:** An MQL5 community moderator explicitly confirms that downloaded/uncompressed tick records can contain undocumented internal flag bits (including \`0x80\`) beyond the six public flags and advises ignoring those bits for semantic interpretation. This matches the observed difference between the prior live/reconstructed rows (\`0x06\`) and the newly downloaded historical rows (\`0x86\`). The extra bit is therefore consistent with an MT5 internal metadata flag, not evidence by itself of altered bid/ask data or a corrupt CSV. It is not a documented public contract, so it must remain uninterpreted.
- **Evidence boundary:** The old and new workflows used the same pinned Python MetaTrader5 integration package \`5.0.6231\` and Python 3.12. The historical workflow did not record the terminal executable build/version, so a terminal-build difference cannot be confirmed or ruled out from the existing run logs. The next capture will record both terminal and Python integration version diagnostics.
- **Code hardening:** Collector commit \`e6907cf150e8afeacf5a2da0868227a890e12344\` adds documented flag-bit constants, raw flag-value distribution, nonstandard-mask distribution, and terminal/integration version metadata to the manifest. It preserves every raw \`flags\` value in the CSV and explicitly marks nonstandard bits uninterpreted. It also rejects values outside the unsigned 32-bit MqlTick field range; no flag is masked, rewritten, or dropped.
- **Regression tests:** Commit \`eef638d64e2ef086af9510b8e5fdc3c81fee70c8\` adds coverage proving \`0x86\` is preserved exactly, \`0x80\` is separately diagnosed, normal documented values remain unchanged, and negative/overflowing values fail closed.
- **Strategy/data treatment:** Continue to use the verified bid/ask/time/volume fields for their independently validated purposes. Do not use nonstandard flag bits as strategy features. The previous statement that the full flag mismatch necessarily meant parity failed is narrowed: the raw flags differ, but the public semantics of the documented bits agree (\`0x06\` in both records); the additional \`0x80\` is consistent with an internal MT5 flag.
- **Next action:** Run PR CI on the latest branch head. After CI passes, the next bounded read-only capture will include runtime version and flag diagnostics. No larger backfill, strategy tuning, candidate approval, holdout access, PR merge, or trading authorization is implied.

