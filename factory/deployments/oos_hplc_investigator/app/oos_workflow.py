from __future__ import annotations

import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class OOSRecord:
    record_id: str
    sample_id: str
    test_method: str
    analyst_id: str
    result_value: float
    specification_min: float
    specification_max: float
    phase: str
    status: str
    findings: list
    disposition: Optional[str]
    created_utc: str
    closed_utc: Optional[str]


_VALID_DISPOSITIONS = {"approved", "rejected", "retest"}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_oos_record(
    sample_id: str,
    test_method: str,
    analyst_id: str,
    result_value: float,
    spec_min: float,
    spec_max: float,
) -> OOSRecord:
    return OOSRecord(
        record_id=str(uuid.uuid4()),
        sample_id=sample_id,
        test_method=test_method,
        analyst_id=analyst_id,
        result_value=result_value,
        specification_min=spec_min,
        specification_max=spec_max,
        phase="phase1",
        status="open",
        findings=[],
        disposition=None,
        created_utc=_utcnow_iso(),
        closed_utc=None,
    )


def is_oos(record: OOSRecord) -> bool:
    return (
        record.result_value < record.specification_min
        or record.result_value > record.specification_max
    )


def add_finding(record: OOSRecord, finding: str) -> OOSRecord:
    new_record = deepcopy(record)
    new_record.findings = list(record.findings) + [finding]
    return new_record


def advance_to_phase2(record: OOSRecord) -> OOSRecord:
    if record.phase != "phase1":
        raise ValueError(
            f"Record is in phase '{record.phase}', expected 'phase1'"
        )
    if not record.findings:
        raise ValueError("Cannot advance to Phase II: no findings recorded in Phase I")
    new_record = deepcopy(record)
    new_record.phase = "phase2"
    new_record.status = "phase2_open"
    return new_record


def close_oos(record: OOSRecord, disposition: str, supervisor_id: str) -> OOSRecord:
    if disposition not in _VALID_DISPOSITIONS:
        raise ValueError(
            f"Invalid disposition '{disposition}'. Must be one of {_VALID_DISPOSITIONS}"
        )
    if record.phase != "phase2":
        raise ValueError(
            f"Record is in phase '{record.phase}'. Phase II required to close OOS record"
        )
    new_record = deepcopy(record)
    new_record.disposition = disposition
    new_record.status = "closed"
    new_record.closed_utc = _utcnow_iso()
    return new_record


def record_to_dict(record: OOSRecord) -> dict:
    return {
        "record_id": record.record_id,
        "sample_id": record.sample_id,
        "test_method": record.test_method,
        "analyst_id": record.analyst_id,
        "result_value": record.result_value,
        "specification_min": record.specification_min,
        "specification_max": record.specification_max,
        "phase": record.phase,
        "status": record.status,
        "findings": list(record.findings),
        "disposition": record.disposition,
        "created_utc": record.created_utc,
        "closed_utc": record.closed_utc,
    }


def dict_to_record(d: dict) -> OOSRecord:
    return OOSRecord(
        record_id=d["record_id"],
        sample_id=d["sample_id"],
        test_method=d["test_method"],
        analyst_id=d["analyst_id"],
        result_value=d["result_value"],
        specification_min=d["specification_min"],
        specification_max=d["specification_max"],
        phase=d["phase"],
        status=d["status"],
        findings=list(d["findings"]),
        disposition=d.get("disposition"),
        created_utc=d["created_utc"],
        closed_utc=d.get("closed_utc"),
    )
