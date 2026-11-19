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

- **Fixture precision correction:** Test tick fixtures now default to the documented BID|ASK mask \`0x06\` rather than the earlier placeholder value \`0x03\`; this avoids accidentally treating reserved bit \`0x01\` as a documented flag in baseline diagnostics. Commit \`ff9ee5b560649a6b32196f17702fb428abfe5a2b\`. The production capture's raw values are unchanged.

- **CI defect found and corrected:** The first CI attempt after adding flag tests failed during pytest collection because a parameterization decorator was inadvertently attached to the new diagnostic test rather than the existing invalid-tick test. The fixture's default documented mask was also corrected to \`0x06\`. The decorator is now restored to the intended test and the baseline assertion expects \`0x00000006\`. Corrective commit: \`ad9c3324eb4fd3fd3f222b3219e74403b8c2fcdd\`. The failed runs were test-collection failures, not a production collector failure. Fresh CI is required on the corrected head.

- **Corrected-head CI:** Project tests run [44268936492](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44268936492) completed successfully for the PR merge ref containing branch head \`40ecc324e31c278c54925f78a1e0ddeb6caaf205\` and current \`main\`. All configured steps passed, including compile checks and \`pytest -q\`: **284 passed in 2.44 seconds**. This validates the raw flag diagnostics, uint32 bounds, and corrected test decorators on the tested merge ref.

### 2026-11-18 — Runtime provenance diagnostics passed CI; prospective session calendar corrected

- **Runtime metadata test:** The collector now records the MetaTrader5 Python integration version, MT5 terminal version tuple, and terminal build when the API exposes them. Regression fixtures verify these values reach the manifest without exposing account credentials.
- **CI:** Run [44269080930](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44269080930) passed on the PR merge ref containing branch commit \`ac485b137408a4d7f417c0272194d5b8c7def955\` and current \`main\`. Full configured checks passed; \`pytest -q\`: **284 passed in 2.45 seconds**.
- **Tick flag disposition:** The \`0x80\` addition is now classified as an MT5 internal/service flag consistent with the MQL5 moderator's explanation; it is not a public tick flag. Preserve it in raw data, count it in manifest diagnostics, and ignore it for semantic features. The public BID/ASK bits remain \`0x06\` in both the compared live and historical records. Source: https://www.mql5.com/en/forum/450530 (moderator explanation at post #3).
- **Validation calendar audit:** Queried the recent DEMO collection workflow runs; no run or artifact exists for \`validation_06\`. Its planned 2026-11-18 06:00–06:30 UTC window has elapsed without collection. Do not backdate or fabricate it.
- **Calendar correction:** Reassign the unused \`validation_06\` slot to 2026-11-18 13:30–14:00 UTC (London/New York overlap), subject to live MT5 market availability. The remaining preregistered sessions retain their dates: \`validation_07\` Nov 19 10:00–10:30 UTC; \`validation_08\` Nov 20 13:30–14:00 UTC; \`validation_09\` Nov 23 06:00–06:30 UTC; \`validation_10\` Nov 24 10:00–10:30 UTC; \`validation_11\` Nov 25 13:30–14:00 UTC; \`validation_12\` Nov 26 17:30–18:00 UTC; \`validation_13\` Nov 27 10:00–10:30 UTC. All eight remain on distinct UTC dates.
- **Operational boundary:** The DEMO collection workflow is manual-dispatch only. The connected GitHub integration in this session can inspect runs and artifacts but does not expose workflow dispatch. The owner must start the \`validation_06\` collection from Actions at the planned time; allow installer startup before the target collection window and confirm the manifest's actual start/end timestamps. No automatic schedule was added.
- **PR state:** PR #61 remains open/draft/unmerged. No merge or holdout access was performed.



## 2026-11-18 — Manual collection workflow dropdown repaired

- Root cause confirmed: GitHub's `workflow_dispatch` form reads the workflow definition from the default branch. The default-branch `.github/workflows/veltrix-demo-tick-collection.yml` exposed only `validation_01`–`validation_04`, while the reviewed Phase 8 branch already registered `validation_01` and `validation_03`–`validation_13`.
- Updated the default-branch workflow in commit `9375082d7a99e3bf42f812a0ce61e48a8f54e3d1` to expose the registered IDs `validation_01`, `validation_03`–`validation_13`; `validation_02` remains excluded from the eligible distinct-date sequence.
- The dispatch workflow now checks out the reviewed collector source at immutable commit `603069d081ddd701d2a3024d2349cd9fb41f8674`, rather than implicitly using the older default-branch collector. Checkout credential persistence remains disabled.
- Preserved DEMO credential validation, XAUUSD-only collector scope, read-only behavior, terminal trading/DLL disablement, Authenticode validation, bounded collection and artifact audit steps from the reviewed workflow.
- Verified the committed default-branch workflow contains all 12 registered session IDs, the pinned source SHA, and the checkout credential safeguard. This is a workflow-definition verification, not a live collection run; no session was dispatched by this change.
- Next: refresh the GitHub Actions manual-dispatch page and confirm `validation_06` is selectable. Dispatch `validation_06` once for its preregistered date; do not rerun `validation_05`.


### 2026-11-18 — Prospective validation_06 DEMO collection completed

- **Workflow run:** [44270396480](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44270396480); job [134685271928](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44270396480/job/134685271928).
- **Dispatch/source:** Run dispatched from default branch `main` at `9375082d7a99e3bf42f812a0ce61e48a8f54e3d1`; workflow checked out reviewed collector commit `603069d081ddd701d2a3024d2349cd9fb41f8674` with `persist-credentials: false`.
- **Session identity and interval:** `validation_06`; actual collection began `2026-11-18T08:50:56.378709Z` and ended `2026-11-18T09:20:58.416868Z` (1,802 seconds). The actual interval is earlier than the previously planned 13:30–14:00 UTC slot; retain the actual timestamps and do not represent it as having run in that planned window.
- **Account/scope:** Manifest reports `account_mode=DEMO`, server `Exness-MT5Trial10`, canonical XAUUSD / broker symbol XAUUSDm. No other symbol was collected.
- **Collection and audit:** 7,060 tick records; 1,799 quote-validation samples. Manifest status `PASS`; data audit `PASS`. First/last tick timestamps: `2026-11-18T08:50:58.717Z` / `2026-11-18T09:20:57.653Z`; maximum intertick gap 2,783 ms; zero gaps over five seconds. CSV SHA-256 `25eab39b5fee18f6d651bb61001f7f6ec93b2469a29d8701508dcb0b9d2f741d`; independently recomputed from downloaded artifact and matched manifest. CSV row count independently confirmed at 7,060; quote-validation CSV contains 1,799 rows.
- **Spread observation:** 240 points at each of 1,799 quote-validation samples (instrument point 0.001; observed bid/ask difference 0.240). This is specific to this capture and is not a general spread or execution-cost guarantee.
- **Installer diagnostics:** Windows Authenticode `Valid`; signer subject `CN=MetaQuotes Ltd., O=MetaQuotes Ltd., S=Lemesos, C=CY`; Code Signing EKU present; observed signer thumbprint `5A64A7AED24C33DED342D01D01FA5286F06DA6DC`. The fingerprint was recorded in the diagnostics artifact but was not independently pinned against authenticated Exness support evidence. Do not describe this as Exness independently authorizing that exact fingerprint.
- **Read-only controls:** Workflow completed the read-only confirmation step; collector states it contains no order-submission or position-management calls; terminal defaults were `Enabled=0`, `AllowLiveTrading=0`, `AllowDllImport=0`; manifest records `trading_enabled=false`.
- **Artifacts:** Tick dataset artifact [14413428365](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44270396480/artifacts/14413428365), ZIP SHA-256 `1202ef6a28e74ff853753a431d74bb816e592972edf00e0fd53d2b159c722f55`. Diagnostics artifact [14413243766](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44270396480/artifacts/14413243766), ZIP SHA-256 `a089a5c36737b735ccbfe5f556500977747b1723b3960e59f280cae4011d242e`.
- **Provenance boundary:** The run log proves the exact dispatcher head and checked-out collector commit, and the diagnostics artifact records installer provenance. Unlike the separate historical-probe manifest, this live-collection manifest does not itself contain the four-field `source_ref` / `source_commit` / `dispatcher_commit` / `installer_signer_thumbprint` tuple. Do not claim that all four fields were present in this manifest.
- **Result:** COLLECTION PASS; artifact hash/row-count verification PASS; distinct UTC date 2026-11-18 added to prospective validation evidence. This brings the eligible session count to **5 of 12** across **5 distinct UTC dates** (01, 03, 04, 05, 06); `validation_02` remains excluded as a duplicate date. This does not approve a strategy or satisfy the full Phase 8 statistical gates.
- **Remaining risks:** Independent Exness signer-thumbprint confirmation remains outstanding; actual broker fills, commissions, slippage and execution quality are not established by quote capture. PR #61 remains open/draft/unmerged; holdout remains sealed; no strategy tuning or live trading.
- **Next action:** Preserve this artifact as the `validation_06` evidence. Proceed with `validation_07` on its separately assigned UTC date; do not dispatch multiple formal validation IDs on the same UTC date and count them as distinct-date sessions.


### 2026-11-18 — Corrected Phase 8 next-step priority: historical replay before further prospective dates

- **Decision clarification:** The accelerated-validation research explicitly selected MT5 historical tick backfill plus a short prospective DEMO operational check as the preferred route. The eight future-date sequence is the fallback if historical backfill proves unavailable or inadequate; it is not the immediate next step after validation_06.
- **Existing historical feasibility evidence:** Historical probe run [44221513372](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44221513372), artifact [14391096861](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44221513372/artifacts/14391096861), retrieved 8,988 XAUUSD historical ticks for the bounded 2026-11-17 overlap interval. Its structural audit passed and its bid/ask/time/volume quote fields matched all 8,983 rows of the preserved live validation_05 capture. This proves bounded historical retrieval works for that interval; it does not yet prove broad multi-date backfill coverage.
- **Prospective validation_06 disposition:** Preserve run [44270396480](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44270396480) as a successful current-feed/operational observation on 2026-11-18. Do not discard it, but do not treat it as a substitute for a historical replay dataset.
- **Plan correction:** Do not automatically dispatch validation_07–validation_13 while the preferred historical route is being implemented and evaluated. Keep their existing schedule and eligibility definitions intact as a fallback; do not relabel retrospective records as prospective sessions or count same-day captures as distinct dates.
- **Next engineering work:** Review the existing bounded historical probe and its tests; design a separate batch-backfill workflow with strict per-request bounds, preregistered UTC intervals across multiple past dates and market sessions, exact source/account/symbol provenance, independent hashes, coverage/gap audits, failure isolation, and a distinct historical-replay manifest. First test a small multi-date batch before any larger acquisition. Preserve XAUUSD-only, authenticated Exness DEMO, read-only controls, and the sealed holdout.
- **Statistical boundary:** Historical dates can support a separately versioned chronological replay and date-clustered analysis, but data already used for debugging, candidate design or manual inspection must be disclosed and cannot be presented as untouched holdout evidence. Historical quotes do not establish fills, slippage or commissions. Candidate registry remains unchanged; no tuning, candidate approval, holdout access, strategy certification or live trading.
- **Result:** Research priority corrected and documented. Batch historical-backfill workflow is **NOT YET IMPLEMENTED**; no claim is made that the 12-date v2 prospective requirement has already been satisfied or formally superseded.


## 2026-11-18 — PR #69 CI dependency correction

- PR #69 CI run [44276342198](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44276342198) completed with failure during pytest collection; dependency installation, shell syntax validation, and Python compilation passed.
- Failure root cause: PR #69 included the reviewed mt5_demo_tick_collector.py but omitted its updated dependency tools/mt5_python_readonly_diagnostic.py. The collector imported connect_expected_account, which was not present in the older default-branch copy.
- Corrective commit ebf1ff509b1c86a9f06214a80ded69ff29678ea5 copies the diagnostic module from the reviewed PR #61 branch into PR #69. This preserves explicit DEMO account login, terminal trading/DLL-disabled checks, XAUUSD-only symbol discovery, and quote validation.
- The correction has been committed but its CI result is not yet available. No historical batch workflow was dispatched and no MT5 credentials were used by the failed Linux CI job.
- The batch workflow remains a candidate for a small, preregistered feasibility run only after CI passes and its default-branch dispatcher is available. Installer Authenticode checks still do not constitute independent Exness signer-thumbprint confirmation.


## 2026-11-18 — CI follow-up: stale distinct-date test corrected

- Follow-up PR #69 CI run [44286145807](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44286145807) passed dependency installation, shell validation, Python compilation, and 263 tests; one legacy orchestration assertion failed because it still required validation_02 in the workflow.
- The workflow intentionally excludes validation_02 because it duplicates validation_01's UTC date. The test has been updated to assert the current eligible IDs (01, 03, 04, 05, 06) and explicitly assert that 02 is absent.
- Test correction commit: 3c4ca0efbfa00e93c14e2b2047f80fe29ed6f87d. Awaiting its CI result. This is a test expectation correction only; no collection schedule or strategy rule was changed.


## 2026-11-18 — Independent installer signer pin added

- PR #69 project test run [44286249938](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44286249938) passed the complete repository test suite after the distinct-date assertion correction.
- The batch workflow now requires the GitHub Actions secret EXNESS_MT5_SIGNER_THUMBPRINT to contain a 40-hex-character fingerprint and compares it with the actual installer certificate thumbprint before executing the installer. Missing or mismatched fingerprints fail closed.
- Added a regression test requiring this independent signer pin, while retaining Authenticode Valid, MetaQuotes Ltd. publisher, Code Signing EKU, and disabled terminal trading/DLL imports.
- Implementation commits: a2c47038bdacebcd0f2fcf4c8c0b4eeb91732442 (workflow) and 5e44b13fea5ef0cfd8a621bb2fa104b84509e419 (test). CI for these changes is pending.
- Manual prerequisite remains: Exness must confirm the approved signer thumbprint through an authenticated support channel; the observed certificate fingerprint must not be treated as self-authorizing. No installer execution or historical batch request is authorized by this code change alone.


## 2026-11-18 — Signer-pin regression test import fix

- CI run [44286486336](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44286486336) passed compilation and 264 tests but failed the newly added workflow-guard test because its test module had no ROOT path constant. This was a test harness defect, not a workflow or signer-validation failure.
- Added pathlib.Path and a repository-root constant in commit 8065e971d9cabab233dea33445746f3b8593e6ba. Re-run pending.


## 2026-11-18 — Preregistered four-date feasibility sample

- Added research/xauusd_historical_replay_feasibility_v1.json before retrieving any of its intervals. It defines four 30-minute weekday windows across two weeks and four UTC session windows: 2 Nov (06:00 UTC), 4 Nov (10:00 UTC), 6 Nov (14:30 UTC), and 10 Nov (17:30 UTC).
- This is explicitly exploratory historical replay only. It is ineligible for the existing V1 validation partition, sealed holdout, and candidate approval. It does not replace prospective validation dates or the existing V1 plan.
- The plan contains only the exact three interval keys accepted by the batch runner; session labels are stored separately as metadata. Added a regression test for schema validity, four distinct dates, 2-hour aggregate duration, and non-holdout status.
- The batch workflow remains gated by the independent Exness-confirmed signer fingerprint secret. No batch has been dispatched and no new historical data has been retrieved.


## 2026-11-18 — Default-branch historical batch dispatcher merged

- PR #69 was merged to main after the updated Project Tests run [44286771020](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44286771020) passed. Merge commit: e2bd4191fd0beff1d83b30a504fede8c8eeef4a0.
- Verified on main that .github/workflows/xauusd-historical-tick-batch.yml exists, checks out the pinned reviewed batch source commit 054bcb2a22c3887a7416d08c8d2138bef0c7cc2d, and requires the EXNESS_MT5_SIGNER_THUMBPRINT secret to match the installer certificate before execution.
- Verified the preregistered four-date feasibility plan is present on main. Its data role is exploratory historical replay only; it is explicitly ineligible for V1 validation, sealed holdout, or candidate approval.
- PR #61 remains open/draft/unmerged. PR #68 remains open/unmerged against PR #61. No historical batch has been dispatched; no credentials have been used by this workflow.
- Manual blocker before any broker access: obtain the approved signer thumbprint from authenticated Exness support and add it to repository Actions secrets as EXNESS_MT5_SIGNER_THUMBPRINT. The workflow fails closed if this secret is absent or mismatched.



## 2026-11-18 — Historical batch failure isolation implemented

- **Triggering evidence:** Historical batch run [44288731924](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44288731924) completed security/setup gates but the first requested interval (2026-11-02 06:00–06:30 UTC) returned no historical ticks. The previous runner aborted immediately; later preregistered dates were not attempted.
- **Change:** The batch runner now isolates each interval. It records PASS/FAIL, record count, and bounded error detail per interval, persists the aggregate manifest after every attempt, and continues to the next preregistered interval after an individual retrieval exception.
- **Aggregate status:** PASS when all intervals succeed; PARTIAL when at least one succeeds and at least one fails; FAIL when none succeed. PARTIAL exits successfully only so GitHub Actions can upload the full diagnostic artifact; it is not classified as a data-coverage pass.
- **Safety preserved:** Exact preregistered UTC bounds, 12-interval maximum, 31-minute per-interval cap, six-hour total cap, unique dates, Exness DEMO identity, XAUUSD-only scope, independent installer signer pin, read-only terminal configuration, provenance, per-dataset audit and SHA-256 remain required. No interval is widened, silently skipped, or re-labelled.
- **Regression coverage:** Added a test proving that a failed first interval does not prevent the second interval from being attempted and that the PARTIAL manifest preserves both outcomes.
- **Workflow:** Updated the default-dispatch workflow's immutable checkout pin to the new reviewed source commit `2b797d670998fadce237164c26ec25d2b2ba961a`. The workflow still requires the independent Exness-confirmed signer thumbprint secret.
- **Result:** Implementation committed on branch `phase8-historical-batch-failure-isolation`; CI and live MT5 runtime are pending. This change resolves the batch-abort defect in code, but does not resolve broker-side historical coverage. The prior run remains a failed evidence record.
- **Next:** Run full CI on the PR, merge only after tests pass, then re-run the exact four preregistered intervals. The new runner will attempt all four and produce a per-date diagnostic manifest even when some dates return no ticks.



## 2026-11-18 — Failure-isolated historical batch merged and main CI passed

- **Triggering runtime evidence:** Historical batch run [44288731924](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44288731924) returned zero ticks for the first interval (2026-11-02 06:00–06:30 UTC) and aborted before attempting the other three dates.
- **Corrective PR:** [#70](https://github.com/Nexora-Apparel/mt5-scalping-engine/pull/70), merged as `5cb5e336cf0ee79eb66f99bf2ca5838aa699d79b`.
- **Behavior:** Every preregistered interval is now attempted independently. Each result or exception is written to the aggregate manifest immediately. Aggregate `PARTIAL` means at least one interval succeeded and at least one failed; it is an artifact-preservation status, not a data-coverage pass. `FAIL` means no interval returned an audited dataset. No dates or time bounds are silently changed.
- **Regression:** The test simulates an empty first interval followed by a successful second interval, verifies both attempts, validates the per-interval error/success records, and asserts the aggregate manifest is valid newline-terminated JSON.
- **PR CI:** [Run 44289795783](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44289795783) passed: 267 tests, Python compilation, dependency installation and shell syntax validation.
- **Main CI:** [Run 44289918551](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44289918551) passed on the merge commit: 267 tests, Python compilation, dependency installation and shell syntax validation.
- **Dispatcher verification:** Main workflow `.github/workflows/xauusd-historical-tick-batch.yml` now pins immutable source commit `2b797d670998fadce237164c26ec25d2b2ba961a`, which contains the corrected failure-isolated runner and newline-safe manifest output. Signer comparison remains fail-closed and the run #44288731924 reached/passed that gate.
- **Current evidence boundary:** The previous batch remains failed and only its first interval was attempted. The other three dates have no runtime result yet. The new behavior is code/CI verified; it has not yet been exercised against the broker.
- **Next action:** Re-dispatch the unchanged preregistered four-interval plan. Inspect all four per-date outcomes and artifacts. If all return empty, classify the broker's accessible historical range as inadequate for those dates and design a new separately versioned, preregistered sampling plan centered on known retrievable periods; do not rewrite v1's selected dates or count retrospective quotes as prospective sessions.
- **Safety:** Exness DEMO identity, XAUUSD-only scope, bounded requests, independent signer pin, terminal trading/DLL disabled, read-only collection, provenance, hashes and audit gates remain unchanged. No orders, candidate tuning, holdout access, approval, certification or live deployment.


### 2026-11-18 — Failure-isolated four-date historical batch returned two audited datasets

- **Workflow run:** [44290221351](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44290221351); job [134753224899](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44290221351/job/134753224899).
- **Dispatcher/source provenance:** Default branch `main` at dispatcher commit `6198cd7bcbc5f51c3d7966295dda16116bb5fbdb`; batch source commit `2b797d670998fadce237164c26ec25d2b2ba961a`. The four-date JSON preflight passed; focused probe/batch tests passed (34); installer Authenticode validation reported Valid, publisher MetaQuotes Ltd., and signer comparison passed; pinned MetaTrader5 integration installed successfully.
- **Batch behavior:** All four unchanged preregistered intervals were attempted. Aggregate manifest reports `attempted_count=4`, `successful_count=2`, `failed_count=2`, `status=PARTIAL`. This confirms PR #70's interval-failure isolation works against the broker endpoint. The PARTIAL workflow conclusion is artifact-preservation success, not a complete-coverage PASS.
- **Failed intervals:** `hist_20261102_asia` (2026-11-02 06:00–06:30 UTC) and `hist_20261104_london` (2026-11-04 10:00–10:30 UTC) each returned zero ticks with `DiagnosticFailure: no historical ticks returned for requested interval`. Their original preregistered bounds were not changed.
- **Successful interval 1:** `hist_20261106_overlap` (2026-11-06 14:30–15:00 UTC), Exness DEMO broker symbol XAUUSDm; 26,083 rows; 31 one-minute chunks; data audit PASS; first/last ticks 14:30:00.093Z / 14:59:59.634Z; maximum intertick gap 1,724 ms; zero gaps over 5 seconds; CSV SHA-256 `fe7fbfe6bba814eff8668efc9b882f80d74c7226227ef0a87c59c62ae563c232`.
- **Successful interval 2:** `hist_20261110_new_york` (2026-11-10 17:30–18:00 UTC), Exness DEMO broker symbol XAUUSDm; 4,836 rows; 31 one-minute chunks; data audit PASS; first/last ticks 17:30:00.155Z / 17:59:59.958Z; maximum intertick gap 2,232 ms; zero gaps over 5 seconds; CSV SHA-256 `0d584b28070102ff745193f08a83515dccd99d179ed27eadd3e81daf3fd88df9`.
- **Independent artifact inspection:** Downloaded artifact [14420498746](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44290221351/artifacts/14420498746), ZIP SHA-256 `245b7997d6f9f33754916e6f028df712dd8bc0c2db8dc53c5ad361a1f18c8921`. Independently read both CSVs and manifests: row counts matched, timestamps were monotonic, no null fields, no duplicate full quote rows, no non-positive bid/ask, no crossed quotes, and no gaps above five seconds. Both captures reported raw tick flag 134 for every row; preserve it as a raw provider flag and do not infer undocumented strategy semantics from it. Observed bid/ask spread ranged from 0.24 to 0.26 in these two historical windows only; this is not a universal spread or execution-cost guarantee.
- **Safety/provenance:** Aggregate manifest records DEMO required, canonical XAUUSD, trading disabled, order submission false and position management false. Both interval manifests retain source/dispatcher commits, installer signer fingerprint and dataset hashes. No orders or positions were submitted or managed.
- **Result:** HISTORICAL FEASIBILITY PARTIAL — 30,919 audited historical ticks across two of four preregistered dates and 60 minutes of the requested 120 minutes. This establishes successful bounded retrieval on 6 and 10 November, not broad historical coverage. The two zero-result dates remain failed evidence and must not be silently replaced in the original plan.
- **Statistical boundary:** These records remain exploratory retrospective quotes. They are not prospective sessions, broker fills, or untouched holdout evidence. The feasibility plan remains ineligible for V1 validation, holdout and candidate approval. No candidate tuning, certification or trading authorization follows from this retrieval.
- **Next action:** Design a new, separately versioned and preregistered historical sampling plan around the two demonstrated retrievable periods, while retaining the original four-date feasibility outcomes. Define the date/session selection and coverage criteria before additional broker requests. Then acquire only a bounded exploratory expansion and run a separate chronological, dependence-aware replay evaluation with costs/slippage limitations explicit. Keep the prospective operational check and all formal release gates separate.


### 2026-11-18 — Second historical sample preregistered before retrieval

- **Plan:** Added `research/xauusd_historical_replay_sampling_v2.json` in commit `85eb6b61b74f860787487062423d76ad5b97320b`. The file was committed before any v2 interval was requested.
- **Selection:** Four new 30-minute intervals on four distinct weekdays and UTC sessions: 5 Nov 10:00–10:30 (London), 9 Nov 06:00–06:30 (Asia), 11 Nov 14:30–15:00 (London-New York overlap), and 12 Nov 17:30–18:00 (New York). These dates do not repeat the four v1 feasibility dates or the known 17 Nov historical/live parity date.
- **Why:** The first batch demonstrated that bounded Exness DEMO historical retrieval can succeed on 6 and 10 Nov but returned no ticks on 2 and 4 Nov. V2 tests additional dates and session windows without editing or replacing those v1 outcomes.
- **Preflight review:** The committed JSON parses; it defines four unique UTC dates, each exactly 30 minutes, for a total of two hours. The batch runner's existing preflight will independently validate the exact interval schema, UTC precision, uniqueness, duration caps and safe IDs before any MT5 connection.
- **Acceptance:** Require DEMO identity, XAUUSD-only scope, exact coverage, audited nonempty CSVs, per-dataset SHA-256, monotonic timestamps, valid bid/ask, and reviewed gap/spread diagnostics. Expand only if all four intervals are individually complete and audited; failures remain recorded and cannot be replaced inside this plan.
- **Safety/statistical boundary:** Explicitly exploratory retrospective data; not V1 validation, not holdout, not prospective sessions, not actual fills. Candidate registry changes, tuning, approval, certification and trading remain disabled.
- **Result:** PLAN PREREGISTERED; broker retrieval NOT YET RUN.
- **Next action:** Dispatch the unchanged v2 interval JSON through the existing default-branch workflow. Keep the original v1 four-date plan and its two successes/two failures unchanged.


### 2026-11-18 — V2 historical sampling batch returned three audited datasets

- **Workflow:** [Run 44291179907](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44291179907), job [134756493318](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44291179907/job/134756493318). Workflow conclusion SUCCESS because the batch runner preserves artifacts on PARTIAL results; aggregate data status is PARTIAL, not PASS.
- **Preregistration/provenance:** The unchanged v2 plan was committed before dispatch in `85eb6b61b74f860787487062423d76ad5b97320b`; dispatcher HEAD `ef5203b35f5d72a840936158014a7ab5bdd6cb16`; historical source `2b797d670998fadce237164c26ec25d2b2ba961a`. Four distinct-date intervals passed preflight. Focused tests: 34 passed. Authenticode Valid, publisher MetaQuotes Ltd., signer comparison passed; pinned MetaTrader5 5.0.6231 installed.
- **Aggregate:** `attempted_count=4`, `successful_count=3`, `failed_count=1`, `status=PARTIAL`; total successful records 21,282 across 90 minutes of the 120 requested minutes. Exness DEMO; canonical XAUUSD, broker symbol XAUUSDm; read-only, no orders or position management, trading disabled.
- **Failed interval:** `hist2_20261105_london`, 2026-11-05 10:00–10:30 UTC, zero records; `DiagnosticFailure: no historical ticks returned for requested interval`. This date remains a failure and is not replaced inside v2.
- **Successful interval 1:** `hist2_20261109_asia`, 2026-11-09 06:00–06:30 UTC; 5,819 rows; data audit PASS; first/last 06:00:00.115Z / 06:29:59.890Z; max intertick gap 2,290 ms; zero gaps >5 seconds; SHA-256 `80aeb34d6351636498f4f4542ea667e43ff4de37383cbcf4a61dd024b6e3b906`.
- **Successful interval 2:** `hist2_20261111_overlap`, 2026-11-11 14:30–15:00 UTC; 11,037 rows; data audit PASS; first/last 14:30:00.114Z / 14:59:59.596Z; max intertick gap 2,135 ms; zero gaps >5 seconds; SHA-256 `58c130f0fef7c9757e9805b26d371f8a046273e805b8967c38c141230a61fec7`.
- **Successful interval 3:** `hist2_20261112_new_york`, 2026-11-12 17:30–18:00 UTC; 4,426 rows; data audit PASS; first/last 17:30:00.138Z / 17:59:59.506Z; max intertick gap 2,220 ms; zero gaps >5 seconds; SHA-256 `6562021f1d69047be6ce6e5c35ffdbecd90b9fc833d8ea51061ae2d05d53d85b`.
- **Independent artifact inspection:** Artifact [14422070722](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44291179907/artifacts/14422070722), ZIP SHA-256 `587d9e7533fa536469609bd20e0891391c0d8ca87ce35174a3c829aacfb328ee`. Independently recomputed all three CSV SHA-256 hashes; each matched its aggregate and interval audit manifest. CSV row counts matched manifests. All three timestamp streams were monotonic non-decreasing; repeated millisecond timestamps were retained where quote rows differed (29, 41 and 14 repeats respectively); no duplicate full quote rows, null cells, invalid bid/ask pairs, or gaps >5 seconds. Observed spread range across these windows was 0.24–0.26; this is a limited historical observation, not a universal spread/fill guarantee. All rows carry raw flag 134; preserve it as a raw provider flag without inferring undocumented semantics.
- **Combined feasibility tally:** V1 plus V2 now yielded five successful historical windows across five distinct UTC dates (6, 9, 10, 11 and 12 Nov), 52,201 total audited ticks and 150 minutes of retrieved intervals; three of eight preregistered intervals returned zero ticks (2, 4 and 5 Nov). Keep all failures visible. This is still a sparse feasibility sample, not a continuous historical archive or proof of general endpoint availability.
- **Statistical/safety boundary:** All observations remain retrospective DEMO quotes, not actual fills, prospective sessions or holdout. No candidate tuning, candidate registry changes, V1 validation promotion, certification or trading authorization follows.
- **Next action:** Do not expand v2 because one of its four intervals failed its explicit all-four acceptance rule. Preserve the v2 result and design a separately versioned follow-up sample if further coverage is justified. In parallel, implement the historical replay ingestion/normalization and audit pipeline for the five successful windows, with source hashes and interval provenance preserved; replay evaluation must remain separate from prospective V1 validation and include explicit spread, commission and slippage limitations.


### 2026-11-18 — Historical replay integration contract audit

- **Finding:** The newly retrieved batch CSVs pass the collector's tick schema and integrity audit, but the current Phase 5 replay loader cannot consume their raw interval manifests directly. `profile_dataset()` and `replay_events()` require manifest fields `dll_imports_enabled=false` and an `instrument_specs.XAUUSD` object containing verified contract currencies and point size. The historical probe manifest currently records `trading_enabled=false` and `instrument_point`, but omits the DLL-import attestation and structured instrument contract.
- **Decision:** Do not weaken the replay loader's fail-closed requirements, and do not fabricate missing manifest fields or treat a collector audit PASS as replay-readiness. The current v1/v2 historical CSVs remain retained, hash-verified exploratory source data.
- **Next engineering task:** Update the historical probe's manifest contract to record DLL-import-disabled status from the actual terminal configuration and verified `symbol_info` currency/point metadata; add tests for those fields and update the immutable source pin through the reviewed PR sequence. Separately implement a provenance-preserving adapter for existing historical artifacts only if the original run evidence can independently substantiate every required field. Then profile/replay the five successful windows with synthetic mechanics events only; do not generate or score candidate signals from this exploratory sample.
- **Safety:** Historical replay remains research-only. No strategy performance, candidate ranking, tuning, approval, holdout eligibility, or trading claim is permitted.


### 2026-11-18 — Runtime-verified historical replay manifest contract implemented

- **Branch:** `phase8-replay-manifest-contract`, based on main commit `1704af7185edf85751d5814bc493cd5d817c1ccf`.
- **Change:** Historical probe now reads effective MT5 `terminal_info().dlls_allowed` and fails closed unless it is explicitly `False`. The workflow's INI setting is not treated as runtime proof.
- **Contract metadata:** Probe now requires `symbol_info` to report exact `currency_base=XAU`, `currency_profit=USD`, and a finite positive point size. It records `dll_imports_enabled=false` and structured `instrument_specs.XAUUSD` with broker symbol, currencies and point size, matching the existing Phase 5 replay loader contract. Existing `instrument_point` is retained for compatibility.
- **Tests added:** Runtime DLL state true/missing cases and wrong/missing currency or invalid point cases fail closed; successful manifest assertions cover all replay-required fields.
- **Safety boundary:** No historical artifacts are rewritten and no missing metadata is backfilled into old manifests. Existing V1/V2 records remain unchanged until their original runtime evidence can substantiate the fields. No order, candidate signal, candidate tuning, holdout, approval, certification or trading operation is introduced.
- **Next:** Run focused and full CI on this branch. After review, update the default batch workflow's immutable source pin to the reviewed source commit in a separate workflow change, then collect no new records until the new manifest has been verified on a controlled run.


### 2026-11-18 — Historical replay manifest contract merged; dispatcher pin update prepared

- **Implementation PR:** [#71](https://github.com/Nexora-Apparel/mt5-scalping-engine/pull/71), merged after Project Tests passed. Squash merge commit: `1b8b6bf518a0bc997611183f0120295b82588a5e`.
- **CI:** PR run [44301980063](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44301980063) completed SUCCESS. The workflow completed Python compilation and the unit/fail-closed configuration test step.
- **Dispatcher change:** Prepared a separate PR to update the immutable historical batch source checkout from `2b797d670998fadce237164c26ec25d2b2ba961a` to the reviewed manifest-contract commit `1b8b6bf518a0bc997611183f0120295b82588a5e`.
- **Safety:** No new collection has been dispatched. Existing V1/V2 artifacts remain unchanged and are not replay-ready absent original runtime metadata evidence. No order submission, position management, strategy evaluation, candidate tuning, holdout, approval, certification or trading authorization.
- **Next:** Validate and merge the dispatcher pin update, then perform one bounded, explicitly labelled manifest-contract smoke capture before attempting to profile the historical datasets. This smoke capture validates the collector/replay contract; it is not additional strategy evidence or a replacement in either preregistered sample.


### 2026-11-19 — Legacy historical quote-only replay route implemented

- **PR #72:** Merged source-pin update after CI success. Merge commit: `b938cdc2f73e4af2eeaae2a63673c68f6bb2ff17`. The default historical batch workflow now checks out the reviewed probe commit `1b8b6bf518a0bc997611183f0120295b82588a5e`.
- **Existing artifact audit:** Downloaded and inspected V1 artifact `14420498746` and V2 artifact `14422070722`. All five successful interval manifests have `schema=VELTRIX_XAUUSD_HISTORICAL_TICK_PROBE_V2`, `account_mode=DEMO`, `trading_enabled=false`, `canonical_symbol=XAUUSD`, `broker_symbol=XAUUSDm`, and `instrument_point=0.001`. They contain no `dll_imports_enabled` value and no structured `instrument_specs`.
- **Original workflow evidence:** Both V1/V2 job logs show `AllowDllImport=0` written to `C:\MT5\config\common.ini` before collection. This proves the intended setting was written, but does not prove the effective MT5 runtime state. No retrospective false attestation will be added.
- **Blocker resolution design:** Added an explicit opt-in legacy historical profile path. It verifies the original CSV hash, schema, DEMO/trading-disabled state, canonical/broker symbol, point size, CSV schema, timestamps, quotes and duplicates. It records DLL runtime state as unverified and contract currencies as unverified. Strict default profile behavior remains unchanged.
- **Quote-only replay:** Added deterministic offline quote-state mechanics replay for this partial-provenance path. It reports tick replay counts, quote state changes, intertick gaps, spread points and midpoint movement in raw price units. It cannot generate signals, score candidates, calculate currency PnL, claim fills, or become holdout data. Existing candidate replay still requires the strict current manifest contract.
- **Journal:** `docs/PHASE8_PROGRESS_LOG.md` remains the canonical dated project journal; no duplicate journal was created.
- **Next:** Run CI; then execute the quote-only mechanics replay against the five original V1/V2 CSV/manifest pairs without modifying the source artifacts. Preserve all hashes and per-interval provenance. No new historical sampling is needed for this step.


### 2026-11-19 — Legacy replay implementation merged; artifact execution workflow prepared

- **Implementation PR:** [#73](https://github.com/Nexora-Apparel/mt5-scalping-engine/pull/73), merged after all checks passed. Merge commit: `90ea627b02af2e73899e224a477fa2fd1e3fffb7`.
- **Validation:** Project Tests [run 44607453844](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44607453844) passed: 276 tests. Existing historical-replay smoke [run 44607453875](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44607453875) passed; candidate-generation smoke [run 44607453771](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44607453771) passed. These two existing smoke workflows used certified prospective sessions, not the five legacy historical windows.
- **New workflow prepared:** `.github/workflows/xauusd-legacy-quote-mechanics-replay.yml` downloads the original V1/V2 artifacts by immutable artifact IDs, replays exactly the five successful interval CSVs, verifies source hashes and safety flags, and uploads reports. It does not connect to MT5 or collect new data.
- **Journal continuity:** This file remains the canonical dated Phase 8 journal; each implementation, evidence item, blocker and next step is being recorded here.
- **Next:** Merge the workflow PR and dispatch it against V1 artifact `14420498746` and V2 artifact `14422070722`. If all five report hashes match their original manifests, the historical quote-only replay integration blocker is resolved for descriptive mechanics. Candidate evaluation remains separately blocked by missing runtime DLL attestation and contract currency metadata.


### 2026-11-19 — Unrelated default profile workflow bootstrap mismatch diagnosed and corrected

- **Failure:** Main push profile run [44607597202](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44607597202) failed because the workflow's bootstrap source run `43194341816` / artifact `veltrix-exness-demo-ticks-3` contains XAGUSD-only rows. The profiler is intentionally XAUUSD-only and correctly rejected line 2. This was not a failure of the legacy historical replay implementation.
- **Replacement evidence:** Inspected the first preregistered validation artifact [14029149674](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/43408593546/artifacts/14029149674): manifest identifies `validation_01`, canonical symbol XAUUSD, broker symbol XAUUSDm, status PASS, 3,857 rows; independently inspected CSV rows and confirmed all 3,857 rows are XAUUSD.
- **Fix prepared:** Updated the profile workflow bootstrap source to run `43408593546`, artifact `veltrix-exness-demo-ticks-10`. The profiler's XAUUSD-only guard remains unchanged; no XAGUSD is silently accepted or relabelled.
- **Next:** PR #74 CI will validate the workflow/profile changes. After merge, the main push bootstrap should re-run against the verified XAUUSD dataset.


- **Execution trigger refinement:** The legacy replay workflow is configured to run automatically when its reviewed workflow file lands on `main`, while retaining manual dispatch with overridable artifact IDs. This avoids requiring a separate manual dispatch for the five known artifacts.


- **Legacy adapter hardening:** Before running against the original artifacts, tightened the adapter to require the original source name, source/dispatcher commit hashes, installer signer fingerprint, timezone-aware requested interval bounds, exact row broker-symbol match, and every tick within the original inclusive interval. Added fail-closed regression tests for broker-symbol and interval mismatches.


### 2026-11-19 — Final integration branch reconciliation

- **Branch:** `phase8-replay-mainline-integration`, based on current main after reconciling the legacy replay implementation and tests.
- **Regression correction:** The first hardened negative-test attempt exposed fixture problems (CSV line terminator and reversed test interval), not a production parser defect. The fixtures were simplified to mutate the source CSV without rewriting its header and to use a valid interval that excludes the test tick.
- **Validation history:** The initial PR #73 baseline passed 276 tests. The first added negative-test run failed on those fixture issues; corrected tests are included in this final integration branch and require a fresh full Project Tests result before merge.
- **Separate profile workflow fix:** The XAUUSD-only profiler's bootstrap now points to verified XAUUSD validation_01 artifact 14029149674 (run 43408593546), not the old XAGUSD-only artifact 13934849710.
- **Execution plan:** On merge, the manual/automatic artifact replay workflow downloads only original V1/V2 artifacts and runs quote-state mechanics across the five successful intervals. It must preserve all source hashes and report partial provenance explicitly.
