import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from alcoa_validator import (
    ATTRIBUTES,
    validate_alcoa_record,
    compute_record_hash,
    audit_stamp,
)


def _full_record():
    return {attr: True for attr in ATTRIBUTES}


def test_full_record_compliant():
    result = validate_alcoa_record(_full_record())
    assert result["compliant"] is True
    assert result["score"] == 9
    assert result["missing"] == []


def test_missing_accurate_not_compliant():
    record = _full_record()
    record["accurate"] = False
    result = validate_alcoa_record(record)
    assert result["compliant"] is False
    assert "accurate" in result["missing"]


def test_empty_record_not_compliant():
    result = validate_alcoa_record({})
    assert result["compliant"] is False
    assert result["score"] == 0


def test_hash_prefix_and_stability():
    record = {"key": "value", "number": 42}
    h1 = compute_record_hash(record)
    h2 = compute_record_hash(record)
    assert h1.startswith("sha256:")
    assert h1 == h2


def test_audit_stamp_fields():
    record = {"data": "example"}
    stamp = audit_stamp("cesar", "CREATE", record)
    assert "actor" in stamp
    assert "action" in stamp
    assert "timestamp_utc" in stamp
    assert "record_hash" in stamp


def test_audit_stamp_utc():
    stamp = audit_stamp("cesar", "UPDATE", {"x": 1})
    ts = stamp["timestamp_utc"]
    assert ts.endswith("+00:00") or ts.endswith("Z")
