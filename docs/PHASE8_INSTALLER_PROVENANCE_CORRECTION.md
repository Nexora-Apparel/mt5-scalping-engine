# Phase 8 — MT5 installer provenance correction

**Status:** Implemented on `phase8-distinct-validation-date-guard`; awaiting CI and a fresh manual `validation_05` run.

## Root cause

The previous installer gate required the Authenticode signer subject to contain `Exness`. The captured installer had a valid Authenticode signature whose publisher was `MetaQuotes Ltd.`, so the workflow stopped before installation. This was an incorrect publisher assumption: MetaQuotes develops and signs the MT5 terminal, while Exness distributes the broker-configured download.

## Independent source verification

The official Exness MT5 download page links directly to:

`https://download.terminal.free/cdn/web/exness.technologies.ltd/mt5/exness5setup.exe`

The exact URL matches the workflow's installer source. The link is present in the official Exness page's desktop MT5 download controls:
- Exness MT5 page: https://www.exness.com/metatrader-5/
- MetaQuotes official MT5 download page: https://www.metatrader5.com/en/download
- MetaQuotes installation documentation: https://www.metatrader5.com/en/terminal/help/start_advanced/installation

The official Exness page therefore independently establishes the distribution link, and the MetaQuotes publisher identity is consistent with the MT5 software publisher. This does not make every MetaQuotes-signed executable acceptable; source and signer checks are both required.

## New fail-closed policy

Before execution, the workflow now requires all of the following:

1. Download only from the exact installer URL linked by the official Exness MT5 page.
2. Installer size must exceed 1 MB.
3. Windows Authenticode status must be `Valid` (chain/signature validation).
4. Signer subject must begin with the exact publisher DN `CN=MetaQuotes Ltd., O=MetaQuotes Ltd.`.
5. Signing certificate must contain the Code Signing EKU OID `1.3.6.1.5.5.7.3.3`.
6. Signer thumbprint, issuer, source URL, SHA-256, signature status, EKU result and timestamp signer are recorded in provenance diagnostics.

The workflow no longer incorrectly requires the software publisher to be Exness. It does not accept an arbitrary valid signature or an arbitrary publisher. No signer thumbprint has been pinned from this single observation; Windows certificate-chain validation plus exact publisher identity, Code Signing EKU and the independently verified official Exness source link are used. The thumbprint is retained for future independent certificate continuity review.

## Safety invariants retained

- Manual workflow dispatch only.
- Exness DEMO credentials are required and never printed.
- Collector remains XAUUSD-only, bounded to 30 minutes, read-only.
- MT5 automated trading, live trading and DLL imports remain disabled.
- No order submission or position management.
- Signature/publisher/EKU failure stops before installer execution.
- Diagnostics upload remains available after a blocked run.
- No historical validation artifacts are modified.
- This change does not certify market coverage, strategy performance, or the Phase 8 intake.

## Regression coverage

`tests/test_phase8_installer_trust_policy.py` statically guards the official source URL, valid Authenticode requirement, exact MetaQuotes publisher identity, Code Signing EKU, thumbprint provenance and rejection of the old Exness-publisher assumption. Windows execution of the PowerShell certificate-inspection code still requires a fresh workflow run.

## Outstanding verification

1. Pass Project tests and Python compilation on this commit.
2. Run the manual workflow with `validation_05`.
3. Inspect the new provenance artifact and confirm signer subject, thumbprint, issuer, Code Signing EKU and SHA-256.
4. Confirm the terminal installed and the collector completed the full 30-minute read-only session.
5. Independently audit raw tick and quote-validation CSVs against their manifest hashes and run the market-session coverage reporter.

A successful CI run alone is not evidence that installer trust or tick collection succeeded.
