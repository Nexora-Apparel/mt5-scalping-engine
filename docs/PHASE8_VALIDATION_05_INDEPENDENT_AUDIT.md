# Phase 8 — validation_05 independent raw-artifact audit

**Audit status:** PASS for collection, raw-artifact integrity, and distinct-date checks; formal catalog intake still pending  
**Workflow:** [Run 44096443341](https://github.com/Nexora-Apparel/mt5-scalping-engine/actions/runs/44096443341)  
**Job:** 134084731269  
**Branch / source commit:** `phase8-distinct-validation-date-guard` / `f8829d1e3e8ed6a5831f1854975a0156f72492c7`  
**Session:** `validation_05`  
**Collection window:** 2026-11-17 13:50:00.282198–14:20:02.314597 UTC  
**Account:** Exness-MT5Trial10, manifest declares DEMO  
**Instrument:** canonical XAUUSD, broker symbol XAUUSDm

## Artifact identity

- Tick artifact: `veltrix-exness-demo-ticks-18` (artifact ID 14335284843)
- Diagnostics artifact: `veltrix-exness-collector-diagnostics-18` (artifact ID 14335524258)
- Dataset: `veltrix_exness_demo_ticks.csv`
- CSV bytes: 1,129,947
- CSV rows: 8,983
- Independently recomputed SHA-256: `5917a92e4feaa05f3f9756426baa59deb068fa21ab0c3950f7385a44c3dc7124`
- Manifest SHA-256: identical
- Manifest status and data-audit status: PASS
- Duration: 1,802 seconds (30 minutes + 2 seconds)
- Quote-validation cycles: 1,798
- Trading enabled in collector manifest: false
- DLL imports enabled: false

## Independent raw CSV checks

The tick artifact ZIP was downloaded and parsed independently.

| Check | Result |
|---|---:|
| Raw tick rows | 8,983 |
| Bid unique values | varies |
| Ask unique values | varies |
| Raw tick spread | 240 points on all 8,983 rows |
| Point size | 0.001 |
| Price spread | 0.240 |
| Maximum raw inter-tick gap | 1,877 ms |
| Gaps above 5 seconds | 0 |
| Canonical symbols | XAUUSD only |
| Broker symbols | XAUUSDm only |
| Timestamp order | monotonic |
| CSV SHA-256 vs manifest | match |

## Quote-validation snapshot audit

The artifact additionally contains `quote_validation_samples.csv`, which is independently checked against the manifest.

- Rows: 1,798 (matches manifest record count).
- Bytes: 235,324 (matches manifest).
- SHA-256: `7c21e3d5cbf8e41bc1565cd1ef44b3b698d1fc74a4b34e5a02e750e65f540a0f` (matches manifest).
- Spread: 240 points in all 1,798 samples (0.240 price units).
- Quote age: minimum 137 ms, maximum 1,669 ms, mean approximately 443.6 ms, 95th percentile 1,027 ms.
- Observation timestamps and quote timestamps are retained separately.

The raw tick and periodic quote-validation datasets are separate populations. Both independently show a constant 240-point spread in this collection. This is an observed sample, not a guarantee of future spreads or executable fills.

## Account, terminal, and installer diagnostics

- Sanitized terminal log records successful authorization through Exness Access Point 1.
- Terminal synchronized with Exness Technologies Ltd. and reported 0 positions and 0 orders.
- Terminal identified the account as a DEMO hedging account.
- The terminal log also says trading was enabled for the demo account. This is the terminal/account permission state, not evidence of an order. The collector manifest records `trading_enabled=false`; the workflow's read-only confirmation passed; no order-submission or position-management calls are part of the collector.
- Installer provenance JSON records Authenticode status `Valid`, code-signing EKU present, installer SHA-256 `4f717f74d665c581f08d3f015d05ff0187d6854babd1cbad8a7679e15e8ff75f`, and signer `CN=MetaQuotes Ltd., O=MetaQuotes Ltd., S=Lemesos, C=CY`.
- The installer URL is the exact Exness-linked download URL used by the workflow. MetaQuotes is the software publisher signer; Exness is the distributor/brand. Do not mislabel the signer as Exness.
- The signer thumbprint is recorded as `5A64A7AED24C33DED342D01D01FA5286F06DA6DC`, but independent pinning against Exness-controlled evidence remains outstanding.

## Distinct-date and session coverage checks

The four intended eligible sessions now have four distinct UTC start dates:

| Session | Run ID | Tick artifact ID | UTC date | Raw ticks | Session classification |
|---|---:|---:|---|---:|---|
| validation_01 | 43408593546 | 14029149674 | 2026-11-13 | 3,857 | London |
| validation_03 | 43773683398 | 14185914411 | 2026-11-15 | 4,035 | Outside defined windows |
| validation_04 | 43814840356 | 14203352046 | 2026-11-16 | 11,537 | Asian |
| validation_05 | 44096443341 | 14335284843 | 2026-11-17 | 8,983 | London, New York, and overlap |

For 17 November 2026, the London and New York windows overlap from 13:00 to 17:00 UTC. The actual validation_05 collection from 13:50 to 14:20 UTC falls wholly inside that overlap. Independent IANA timezone classification gives 8,983 London ticks, 8,983 New York ticks, and 8,983 overlap ticks.

The four downloaded CSV hashes match their manifests. Each manifest reports PASS collection and data-audit status, DEMO account mode, trading disabled, DLL imports disabled, XAUUSD-only symbol identity, and 1,802 seconds of monotonic collection duration. This is an independent artifact review; the repository's formal all-session catalog workflow must still be run to validate the full preregistered package.

## Intake disposition and remaining gates

- validation_05 passed its collection workflow and independent raw-artifact checks.
- The four UTC dates are distinct: 13, 15, 16, and 17 November 2026. validation_02 remains excluded because it shares 13 November with validation_01.
- The four session artifacts are ready for submission to the strict catalog intake. Do not mark the formal catalog as passed until the manual validation workflow downloads and verifies all six preregistered development/validation artifacts and the chronological evaluator completes.
- Commission schedule/contract fee verification, independent reviewer attestation, and out-of-band Ed25519 public-key fingerprint verification remain outstanding.
- Manual owner-controlled DEMO reactivation rehearsal remains outstanding.
- No net performance certification, candidate freeze, holdout scoring, live deployment, or real-money execution is authorized by this audit.

## Next action

Run the manual workflow `.github/workflows/xauusd-walk-forward-validation.yml` with the six-session map now populated as its default input. Review the resulting catalog and validation report before advancing to any performance or holdout stage.
