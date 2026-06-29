from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone


ALCOA_ATTRIBUTES = [
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

_VALID_ROLES = {"analyst", "supervisor"}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_record_hash(record: dict) -> str:
    serialized = json.dumps(record, sort_keys=True).encode()
    return "sha256:" + hashlib.sha256(serialized).hexdigest()


def validate_alcoa(record: dict) -> dict:
    present = [attr for attr in ALCOA_ATTRIBUTES if record.get(attr) is True]
    missing = [attr for attr in ALCOA_ATTRIBUTES if attr not in present]
    return {
        "compliant": len(missing) == 0,
        "present": present,
        "missing": missing,
        "score": len(present),
    }


def create_audit_stamp(
    actor: str, action: str, record: dict, role: str = "analyst"
) -> dict:
    return {
        "actor": actor,
        "role": role,
        "action": action,
        "timestamp_utc": _utcnow_iso(),
        "record_hash": compute_record_hash(record),
        "alcoa_validation": validate_alcoa(record),
    }


def sign_record(record: dict, actor: str, role: str) -> dict:
    if role not in _VALID_ROLES:
        raise ValueError(f"Invalid role '{role}'. Must be 'analyst' or 'supervisor'")
    signed_at = _utcnow_iso()
    signature_hash = compute_record_hash({**record, "signer": actor})
    signed = dict(record)
    signed["electronic_signature"] = {
        "signed_by": actor,
        "role": role,
        "signed_at_utc": signed_at,
        "signature_hash": signature_hash,
    }
    return signed
