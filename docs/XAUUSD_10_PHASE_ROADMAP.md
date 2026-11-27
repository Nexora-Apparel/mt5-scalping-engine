# VELTRIX XAUUSD scalping-engine: 10-phase execution roadmap

## Binding scope

- Instrument: XAUUSD only. XAGUSD, BTC, forex, indices, and all other instruments are excluded.
- Broker/account: Exness DEMO for current collection and validation.
- Current collectors, diagnostics, profiling, feature generation, and research are read-only.
- Preserve the existing GitHub repository, workflows, historical datasets, manifests, and credentials. Never commit credentials.
- No live/real-money trading. Any future order execution must be a separate, verified DEMO-only system with exact contract checks, strict risk limits, protective stops, emergency stop, broker reconciliation, and audit logs.
- Production deployment and scheduling remain disabled until Phase 10 release gates pass. Telegram integration/controller has been removed from project scope; do not reintroduce it.

## Phases and gates

1. **Market-data foundation and integrity certification — COMPLETE**
   - XAUUSD-only contract scope; bounded DEMO collection; immutable CSV/manifest integrity; offline profiling; independent non-overlapping session certification; verified feature-window generation.
   - Evidence: two certified Exness DEMO sessions; feature builder merged in PR #33; both certified datasets processed into 5-second windows; CI and post-merge checks passed.

2. **Causal feature and market-regime research — COMPLETE**
   - Build descriptive features; classify volatility/trend/direction/activity using trailing prior windows only; preserve warm-up and missing-data states; test no-lookahead invariance and provenance reconciliation.
   - Evidence: regime research merged in PR #34; 117 tests passed; two certified sessions classified independently with 330 windows each and explicit warm-up windows.

3. **Cross-session feature stability and research diagnostics — COMPLETE**
   - Compare independent sessions without pooling away session identity; report distributions, null coverage, correlations, and median drift; reject duplicate or overlapping sessions and incompatible schemas.
   - Evidence: cross-session diagnostics merged in PR #35; 124 tests passed; two certified sessions processed into 721 five-second windows (12,838 source ticks). Provenance hashes, distributions, null coverage, descriptive correlations, and median drift are recorded in `docs/PHASE3_XAUUSD_CROSS_SESSION_REPORT.md`. Median spread was 240 points (0.240 price units), a material cost constraint for short-horizon scalping.

4. **Strategy hypotheses and candidate specification — COMPLETE**
   - Freeze falsifiable XAUUSD-only hypotheses, entry context, direction, invalidation, 5–60 second evaluation horizons, and cost-aware outcomes before any candidate testing.
   - Evidence: PRs #40 and #41 merged; the fail-closed registry and exact past-only formulas passed 143 tests. Three finite candidate families are frozen with 5/15/30/60-second horizons, quote-crossed outcome rules, cost requirements, and chronological holdout/purge controls. Commission remains unverified; no net-performance pass is permitted.

5. **Tick replay and deterministic research simulator — COMPLETE**
   - Replay chronological bid/ask ticks; model spread-aware entries/exits, quote freshness, latency assumptions, and conservative execution constraints.
   - Evidence: PR #42 merged; 153 tests passed. Historical replay workflow #43378951998 rebuilt features and diagnostics from both certified artifacts, then produced 8/8 synthetic quote-replay smoke outcomes with zero entry/exit timeouts. The evidence artifact is [14015811691](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/43378951998/artifacts/14015811691). Replay confirmed XAUUSD DEMO provenance, Ask/Bid quote crossing, spread included once, no orders or actual-fill claims, and null net-after-commission. Both sessions remain development-only, not holdout.

6. **Strategy implementation and MQL5 research integration — COMPLETE**
   - Implement candidate analysis logic behind strict XAUUSD contract guards; keep collector and diagnostic workflows read-only; separate analysis from any order interface.
   - Evidence: PR #47 passed 172 Python tests; MQL5 compile reported 0 errors and 0 warnings across four configured targets; certified Sessions 8 and 9 passed provenance-checked candidate smoke generation (10,652 generated research events across 719 completed windows). Final partial windows were excluded. The bounded MQL5 five-second adapter is opt-in and journal-only. See `docs/PHASE6_XAUUSD_CANDIDATE_ANALYSIS.md`.
   - Limitation: live terminal runtime behavior remains untested; generated events are not trade outcomes or evidence of predictive edge. No execution authorization is implied.

7. **Risk engine and DEMO safety controls — COMPLETE**
   - Implement risk-based sizing, maximum exposure, protective stops, loss limits, cooldowns, duplicate-order protection, emergency stop, and reconciliation.
   - Current implementation: `RiskControls.mqh` adds exact DEMO login/server and XAUUSD contract checks, hard risk ceilings (0.25% per trade, 0.50% aggregate, 1.00% daily equity loss), one-position policy, daily lock, verified-close loss streak/cooldown, duplicate request IDs and closing-deal deduplication through the append-only checksum-chained `RiskJournal.mqh`, which also permanently records emergency-stop and server-day loss-lock events; account/server-scoped terminal state persists the daily baseline, daily lock, loss streak, cooldown, and emergency-stop latch, with a last-written checksum marker and persistent compare-and-set lock to serialize close accounting across EA instances. `ExecutionGuard.mqh` now independently requires exact DEMO identity and verified XAUUSD metadata before its non-submitting preflight. See `docs/PHASE7_DEMO_RISK_CONTROLS.md`.
   - Evidence: PR #50 merged the new-journal initialization fix; PR #51 added a true two-process MT5 restart test; PR #52 added locked-file and corrupted-journal fail-closed tests. Final PR #52 head passed 199 Python tests and nine MQL5 compilation targets with 0 errors and 0 warnings. Windows MT5 terminal runtime passed five synthetic harnesses: journal append/replay and duplicate rejection; risk-state restore, abandoned-lock rejection, and checksum mismatch rejection; emergency-stop/daily-lock seed; fresh-process restart restoration; and existing-journal lock/corruption rejection. Runtime evidence: [workflow #43393115383](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/43393115383), [results artifact](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/43393115383/artifacts/14022056627). PR #53 additionally removed XAGUSD from every active DEMO workflow and the read-only MQL5 diagnostic EA; broker symbol resolution now requires XAUUSD prefix plus XAU/USD contract metadata. The owner reviewed and accepted the personal-use implementation on 13 Nov 2026; the owner also reports a colleague reviewed it outside GitHub. No order path is wired or authorized, so broker-fill behavior and trading performance remain untested and are not Phase 7 claims.

8. **Chronological walk-forward and robustness evaluation — IN PROGRESS**
   - Preregistered plan, evaluator, safe artifact-intake helper, and manual-only workflow added: `research/xauusd_walk_forward_plan_v1.json`, `tools/mt5_xauusd_walk_forward.py`, `tools/prepare_xauusd_walk_forward_catalog.py`, `.github/workflows/xauusd-walk-forward-validation.yml`, and `docs/PHASE8_XAUUSD_WALK_FORWARD.md`.
   - Plan pins the two known development hashes; requires four new validation sessions across four dates (100 non-overlapping outcomes per candidate configuration/horizon), then ten untouched holdout sessions across ten dates (300 outcomes per configuration/horizon), 120-second partition purge, one-position simulation, 0/1/2/5-point slippage sensitivity, and always-long/always-short/no-trade benchmarks.
   - The manual-only Phase 8 workflow downloads completed session artifacts by run ID, verifies artifact/manifest/CSV hashes and XAUUSD DEMO provenance, then runs the evaluator. Final holdout remains sealed until runtime commission evidence, a verified validation report, and a selection-freeze record committed before every holdout collection are all present. The preregistered plan remains locked; verification is not self-asserted by editing plan fields.
   - The two pinned development artifacts were downloaded and independently verified: 5,192 and 7,646 XAUUSD ticks across two 30:02 sessions; maximum gaps 3.040s/3.812s with no gaps over 5s; median spread 240 points (7 ticks in Session 9 at 260 points); volume and volume_real were zero throughout. Both were Exness DEMO, XAUUSDm (XAU/USD), with trading and DLL imports disabled. CSV and manifest hashes, workflow run IDs, and artifact IDs are pinned in the plan. These same-date sessions remain development-only.
   - Validation_01 was successfully collected in workflow [#43408593546](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/43408593546): 1,802 seconds, 3,857 XAUUSD ticks, 1,797 quote-validation cycles, maximum inter-tick gap 4.28 seconds, and zero gaps over 5 seconds. The integrity audit passed; this is one validation session only. The corresponding market profile [#43412642978](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/43412642978) recorded a 240-point median spread and no non-zero Last or real-volume observations. Validation_02–04 on three additional dates and ten untouched holdout sessions remain outstanding.
   - Draft PR #60 adds the commission evidence contract, a read-only Exness DEMO execution-cost collector, SHA-256 validation of the original broker schedule plus a scope-bound Ed25519-signed reviewer attestation, verified against a public-key fingerprint pinned through a separately authenticated out-of-band channel; runtime net scoring remains locked unless all evidence validates. The collector is included in the manual DEMO workflow; it exports sanitized deal history and broker contract metadata but never submits or manages orders. A separate package verifier now rechecks file hashes, Exness broker identity, DEMO/read-only controls, XAUUSD contract metadata, deal timestamps, and summary reconciliation before upload. Deal position references use a fresh per-package salted SHA-256 reference so raw broker IDs are not exported or correlatable across separate runs; this is not HMAC. Missing deal history remains an evidence gap, not a commission estimate. Signed-attestation, protected trust-anchor, Exness-identity, and collector-verifier tests passed in GitHub Actions [#43507164021](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/43507164021): **272 tests passed** on code commit `73b21b8aae3f4ffa74e244cff3f04991d727f335`. An additional walk-forward test now verifies that partial reviewer inputs fail closed; latest run [#43507381686](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/43507381686) passed compilation, shell checks, and **273 tests in 2.47s** on commit `d55d4f17b0ba870399aa8ae1ffcbfd3d06ba5d49`. PR #60 remains draft and unmerged.
   - No applicable Exness DEMO commission schedule, signed reviewer attestation, trusted reviewer public key, or independently pinned key fingerprint has been supplied. Synthetic Ed25519 keys are test fixtures only. A valid signature proves possession of the pinned private key, not legal identity or organizational independence by itself. Net performance remains locked, no candidate is ranked or approved, and holdout remains sealed.
   - Gate: complete chronological sessions, sample counts, separately verified commission source and review artifacts covering the full evaluation period, positive net mean with session-clustered 95% lower bound above zero at every registered slippage level, and positive lower-bound performance versus all registered benchmarks after identical costs.

9. **Prospective Exness DEMO forward validation**
   - Conduct a separately authorized, monitored DEMO-only forward test after all earlier gates; reconcile every decision and any permitted demo order.
   - Gate: complete prospective sample, risk-control evidence, operational logs, and independent review. No live funds.

10. **Final hardening and controlled release**
    - Security review, configuration audit, recovery tests, observability, rollback, runbooks, and final release certification.
    - Gate: all prior evidence approved; only then may production deployment or scheduling be considered. Telegram remains out of scope unless explicitly re-authorized.

## Current status

- Phase 1: complete.
- Phase 2: complete.
- Phase 3: complete.
- Phase 4: complete.
- Phase 5: complete.
- Phase 6: complete.
- Phase 7: complete for the read-only safety-control implementation and synthetic terminal-runtime certification.
- Phase 8: in progress; preregistered evaluator and holdout controls implemented, but future validation data and verified commission are outstanding.
- Phases 9–10: remain gated by Phase 8 and the prospective DEMO/release criteria.
