from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "veltrix-demo-tick-collection.yml"


def test_installer_source_is_the_exact_url_linked_by_official_exness_mt5_page():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert 'https://download.terminal.free/cdn/web/exness.technologies.ltd/mt5/exness5setup.exe' in source
    assert '$sourceUrl = "https://download.terminal.free/cdn/web/exness.technologies.ltd/mt5/exness5setup.exe"' in source


def test_installer_gate_requires_valid_authenticode_and_exact_metaquotes_publisher():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert 'Get-AuthenticodeSignature -LiteralPath $installer' in source
    assert '$signature.Status -ne "Valid"' in source
    assert 'if ($signerSubject -notmatch "^CN=MetaQuotes Ltd\\.,\\s*O=MetaQuotes Ltd\\."' in source
    assert 'Installer publisher is not the approved MetaQuotes Ltd. publisher' in source


def test_installer_gate_requires_code_signing_eku_and_records_thumbprint():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert 'Where-Object { $_.Oid.Value -eq "2.5.29.37" }' in source
    assert '$_.Value -eq "1.3.6.1.5.5.7.3.3"' in source
    assert 'code_signing_eku = $hasCodeSigningEku' in source
    assert 'signer_thumbprint = $signerThumbprint' in source
    assert 'if (!$signerThumbprint -or !$hasCodeSigningEku)' in source


def test_installer_gate_does_not_require_exness_as_software_publisher():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert '$signerSubject -notmatch "(?i)Exness"' not in source
    assert 'if ($signerSubject -notmatch "^CN=MetaQuotes Ltd\\.,\\s*O=MetaQuotes Ltd\\."' in source
