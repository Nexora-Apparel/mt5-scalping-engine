import csv
import importlib.util
from pathlib import Path
import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "dataset_integrity.py"
spec = importlib.util.spec_from_file_location("dataset_integrity", MODULE_PATH)
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)
HEADER = audit_module.EXPECTED_HEADER


def record(symbol="XAUUSD", source="gold-session", quote=1000, window=500, evaluation=1100):
    return ["1", "1.0.0", source, symbol, str(quote), str(window), str(evaluation),
            "3000.0", "3000.2", "1.5", "2.5", "0.6", "10"]


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerows(rows)


def test_valid_gold_dataset_passes_and_reports_one_stream(tmp_path):
    path = tmp_path / "gold.csv"
    write_csv(path, [record(), record(quote=1200, window=700, evaluation=1300)])
    result = audit_module.audit_dataset(path)
    assert result["status"] == "PASS" and result["records"] == 2
    assert len(result["sha256"]) == 64
    assert {item["symbol"] for item in result["streams"]} == {"XAUUSD"}


@pytest.mark.parametrize(("rows", "message"), [
    ([record(symbol="XAGUSD")], "XAUUSD only"),
    ([record(symbol="BTCUSD")], "XAUUSD only"),
    ([record(evaluation=1100), record(evaluation=1100)], "duplicate source/symbol"),
    ([record(evaluation=1200), record(quote=1100, evaluation=1100)], "not strictly increasing"),
    ([record(window=1200, quote=1100, evaluation=1300)], "window_start <= quote_time"),
    ([record()], "unused"),
])
def test_rejects_out_of_scope_or_corrupt_rows(tmp_path, rows, message):
    path = tmp_path / "bad.csv"
    write_csv(path, rows)
    if message == "unused":
        # The valid row is intentionally accepted; this branch protects fixture wiring.
        assert audit_module.audit_dataset(path)["status"] == "PASS"
    else:
        with pytest.raises(audit_module.DatasetIntegrityError, match=message):
            audit_module.audit_dataset(path)


def test_rejects_bad_numeric_and_schema_values(tmp_path):
    path = tmp_path / "bad.csv"
    row = record()
    row[7] = "nan"
    write_csv(path, [row])
    with pytest.raises(audit_module.DatasetIntegrityError, match="finite"):
        audit_module.audit_dataset(path)
    row = record()
    row[0] = "99"
    write_csv(path, [row])
    with pytest.raises(audit_module.DatasetIntegrityError, match="unsupported schema"):
        audit_module.audit_dataset(path)


def test_integrity_audit_does_not_mutate_source(tmp_path):
    path = tmp_path / "immutable.csv"
    write_csv(path, [record(), record(quote=1200, window=700, evaluation=1300)])
    before = path.read_bytes()
    assert audit_module.audit_dataset(path)["status"] == "PASS"
    assert path.read_bytes() == before
