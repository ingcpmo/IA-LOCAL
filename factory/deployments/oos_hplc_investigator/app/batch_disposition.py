from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class DispositionDecision:
    lot_id: str
    oos_record_ids: list
    decision: str
    rationale: str
    decided_by: str
    decided_at_utc: str
    signature_hash: str


_VALID_DECISIONS = {"approved", "rejected", "retest"}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_signature(
    lot_id: str, decision: str, rationale: str, supervisor_id: str, utc: str
) -> str:
    payload = json.dumps(
        {
            "lot_id": lot_id,
            "decision": decision,
            "rationale": rationale,
            "supervisor_id": supervisor_id,
            "utc": utc,
        },
        sort_keys=True,
    ).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def evaluate_disposition(
    lot_id: str,
    oos_records: list[dict],
    supervisor_id: str,
    decision: str,
    rationale: str,
) -> DispositionDecision:
    if decision not in _VALID_DECISIONS:
        raise ValueError(
            f"Invalid decision '{decision}'. Must be one of {_VALID_DECISIONS}"
        )

    unclosed = [r["record_id"] for r in oos_records if r.get("status") != "closed"]
    if unclosed:
        raise ValueError(
            f"Cannot evaluate disposition: {len(unclosed)} record(s) not closed: {unclosed}"
        )

    decided_at = _utcnow_iso()
    sig = _compute_signature(lot_id, decision, rationale, supervisor_id, decided_at)

    return DispositionDecision(
        lot_id=lot_id,
        oos_record_ids=[r["record_id"] for r in oos_records],
        decision=decision,
        rationale=rationale,
        decided_by=supervisor_id,
        decided_at_utc=decided_at,
        signature_hash=sig,
    )
