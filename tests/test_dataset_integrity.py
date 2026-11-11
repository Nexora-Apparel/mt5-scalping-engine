import csv
import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "dataset_integrity.py"
spec = importlib.util.spec_from_file_location("dataset_integrity", MODULE_PATH)
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)

HEADER = audit_module.EXPECTED_HEADER


def record(source="demo-session-01", symbol="XAUUSD", quote=1000,
           window=500, evaluation=1100, bid="2000.0", ask="2000.2",
           momentum="1.5", volatility="2.5", efficiency="0.6",
           observations="10", schema="1", feature="1.0.0"):
    return [schema, feature, source, symbol, str(quote), str(window),
            str(evaluation), bid, ask, momentum, volatility, efficiency,
            observations]


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerows(rows)


def test_valid_dataset_generates_hash_and_separate_symbol_streams(tmp_path):
    path = tmp_path / "valid.csv"
    write_csv(path, [
        record(evaluation=1100),
        record(symbol="XAUUSD", quote=1200, window=700, evaluation=1300),
        record(symbol="XAGUSD", quote=1250, window=750, evaluation=1350),
    ])
    manifest = audit_module.audit_dataset(path)
    assert manifest["status"] == "PASS"
    assert manifest["records"] == 3
    assert len(manifest["sha256"]) == 64
    assert {(s["source_id"], s["symbol"]) for s in manifest["streams"]} == {
        ("demo-session-01", "XAUUSD"), ("demo-session-01", "XAGUSD")
    }


@pytest.mark.parametrize("rows, message", [
    ([record(evaluation=1100), record(quote=1000, window=500, evaluation=1100)],
     "duplicate source/symbol/evaluation timestamp"),
    ([record(evaluation=1200), record(quote=1100, window=500, evaluation=1100)],
     "not strictly increasing"),
    ([record(window=1200, quote=1100, evaluation=1300)],
     "window_start <= quote_time <= evaluation_time"),
    ([record(symbol="BTCUSD")], "unsupported symbol"),
    ([record(ask="1999.0")], "invalid or crossed"),
    ([record(volatility="-0.1")], "cannot be negative"),
    ([record(efficiency="1.01")], r"must be in \[0, 1\]"),
    ([record(observations="1")], "at least 2"),
    ([record(momentum="nan")], "must be finite"),
    ([record(schema="99")], "unsupported schema_version"),
    ([record(feature="9.9.9")], "unsupported feature_version"),
    ([record(quote=999999999999999999, evaluation=999999999999999999)], "outside the supported UTC range"),
])
def test_invalid_dataset_is_rejected_without_repair(tmp_path, rows, message):
    path = tmp_path / "invalid.csv"
    write_csv(path, rows)
    with pytest.raises(audit_module.DatasetIntegrityError, match=message):
        audit_module.audit_dataset(path)


def test_duplicate_header_and_extra_fields_are_rejected(tmp_path):
    path = tmp_path / "bad-header.csv"
    path.write_text(",".join(HEADER[:-1] + ["symbol"]) + "\n", encoding="utf-8")
    with pytest.raises(audit_module.DatasetIntegrityError, match="header mismatch"):
        audit_module.audit_dataset(path)

    path = tmp_path / "extra.csv"
    write_csv(path, [record() + ["unexpected"]])
    with pytest.raises(audit_module.DatasetIntegrityError, match="missing or extra"):
        audit_module.audit_dataset(path)


def test_empty_file_and_header_only_file_are_rejected(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_bytes(b"")
    with pytest.raises(audit_module.DatasetIntegrityError, match="empty"):
        audit_module.audit_dataset(path)
    write_csv(path, [])
    with pytest.raises(audit_module.DatasetIntegrityError, match="no data records"):
        audit_module.audit_dataset(path)


def test_utf8_bom_is_accepted_but_invalid_encoding_is_rejected(tmp_path):
    path = tmp_path / "bom.csv"
    body = ",".join(HEADER) + "\n" + ",".join(record()) + "\n"
    path.write_bytes(("\ufeff" + body).encode("utf-8"))
    assert audit_module.audit_dataset(path)["records"] == 1
    path.write_bytes(b"\xff\xfe\xff")
    with pytest.raises(audit_module.DatasetIntegrityError, match="UTF-8"):
        audit_module.audit_dataset(path)


def test_integrity_audit_does_not_mutate_source_dataset(tmp_path):
    path = tmp_path / "immutable.csv"
    write_csv(path, [record(), record(quote=1200, window=700, evaluation=1300)])
    before = path.read_bytes()
    manifest = audit_module.audit_dataset(path)
    after = path.read_bytes()
    assert manifest["status"] == "PASS"
    assert before == after
