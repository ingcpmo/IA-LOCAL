import hashlib
import json
from datetime import datetime, timezone

ATTRIBUTES = [
    "attributable",
    "legible",
    "contemporaneous",
    "original",
    "accurate",
    "complete",
    "consistent",
    "enduring",
    "available",
]


def validate_alcoa_record(record: dict) -> dict:
    present = [a for a in ATTRIBUTES if record.get(a)]
    missing = [a for a in ATTRIBUTES if a not in present]
    return {
        "compliant": len(missing) == 0,
        "present": present,
        "missing": missing,
        "score": len(present),
    }


def compute_record_hash(record: dict) -> str:
    serialized = json.dumps(record, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def audit_stamp(actor: str, action: str, record: dict) -> dict:
    return {
        "actor": actor,
        "action": action,
        "timestamp_utc": datetime.now(tz=timezone.utc).isoformat(),
        "record_hash": compute_record_hash(record),
    }
