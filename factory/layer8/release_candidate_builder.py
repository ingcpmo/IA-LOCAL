"""
Capa 8 — Release Candidate Builder.

Ensambla un RC formal con artefactos verificados y lo coloca en
pending_human_confirmation. Nunca marca un RC como "approved".
El RC solo avanza a approved/rejected/returned mediante decisión humana explícita.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import write_event
from factory.layer8.artifact_collector import collect
from factory.layer9.human_review_queue import enqueue

RC_BASE = Path(__file__).parent.parent / "release_candidates"

_RESERVED_APPROVERS = {"human", "agent", "layer8", "system", "capa8", "capa9"}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_rc(project_id: str, version: str) -> dict:
    """
    Construye un RC formal. Status inicial: pending_human_confirmation.
    Nunca "approved".
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    rc_id = f"{project_id}-rc-{version}-{ts}"

    # 1. Recolectar artefactos
    collection = collect(project_id, rc_id)
    if not collection.get("ok"):
        return {
            "ok": False,
            "rc_id": rc_id,
            "reason": "artifacts_incomplete",
            "missing": collection.get("missing", []),
        }

    artifacts_path = Path(collection["artifacts_path"])

    # 4. SHA256SUMS de artefactos
    sha256sums: dict[str, str] = {}
    for f in artifacts_path.iterdir():
        if f.is_file():
            sha256sums[f.name] = _sha256_file(f)

    # 3. Escribir rc_manifest.json
    rc_manifest = {
        "rc_id": rc_id,
        "project_id": project_id,
        "version": version,
        "status": "pending_human_confirmation",
        "decision_origin": "agent_proposed",
        "approved_by": None,
        "artifacts_path": str(artifacts_path),
        "proposed_at": _ts(),
        "sha256sums": sha256sums,
    }
    manifest_path = artifacts_path.parent / "rc_manifest.json"
    manifest_path.write_text(json.dumps(rc_manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    # 5. Audit
    write_event("release_candidate_created", project_id, {
        "rc_id": rc_id,
        "version": version,
        "artifacts": collection.get("artifact_list", []),
        "sha256sums": sha256sums,
    })

    # 6. Encolar para revisión humana
    enqueue(rc_id, project_id, {
        "version": version,
        "artifacts": collection.get("artifact_list", []),
        "proposed_at": rc_manifest["proposed_at"],
    })

    return {
        "ok": True,
        "rc_id": rc_id,
        "status": "pending_human_confirmation",
        "artifacts_path": str(artifacts_path),
    }


def list_pending_rcs() -> list[dict]:
    """Lista todos los RC en pending_human_confirmation."""
    result = []
    if not RC_BASE.exists():
        return result
    for manifest_file in RC_BASE.rglob("rc_manifest.json"):
        try:
            d = json.loads(manifest_file.read_text(encoding="utf-8"))
            if d.get("status") == "pending_human_confirmation":
                result.append(d)
        except Exception:
            continue
    return result


def get_rc(rc_id: str) -> dict | None:
    """Busca rc_manifest.json por rc_id en todos los subdirectorios."""
    if not RC_BASE.exists():
        return None
    for manifest_file in RC_BASE.rglob("rc_manifest.json"):
        try:
            d = json.loads(manifest_file.read_text(encoding="utf-8"))
            if d.get("rc_id") == rc_id:
                return d
        except Exception:
            continue
    return None


def confirm_rc(
    rc_id: str,
    approved_by: str,
    decision: str,
    notes: str = "",
) -> dict:
    """
    Registra la decisión humana sobre un RC.
    decision: "approved" | "rejected" | "returned_to_adjustments"
    approved_by no puede ser un valor reservado.
    """
    if approved_by.lower().strip() in _RESERVED_APPROVERS:
        raise ValueError(
            f"approved_by='{approved_by}' es reservado. Usa el nombre real del revisor."
        )

    valid_decisions = {"approved", "rejected", "returned_to_adjustments"}
    if decision not in valid_decisions:
        raise ValueError(f"decision='{decision}' inválida. Válidas: {valid_decisions}")

    # Encontrar el manifest
    if not RC_BASE.exists():
        raise FileNotFoundError(f"RC '{rc_id}' no encontrado")

    manifest_file = None
    for f in RC_BASE.rglob("rc_manifest.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            if d.get("rc_id") == rc_id:
                manifest_file = f
                rc_manifest = d
                break
        except Exception:
            continue

    if manifest_file is None:
        raise FileNotFoundError(f"RC '{rc_id}' no encontrado")

    rc_manifest["status"] = decision
    rc_manifest["approved_by"] = approved_by
    rc_manifest["decided_at"] = _ts()
    rc_manifest["decision_origin"] = "human_confirmed"
    rc_manifest["notes"] = notes

    manifest_file.write_text(json.dumps(rc_manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    event = "release_candidate_approved" if decision == "approved" else "release_candidate_rejected"
    write_event(event, rc_manifest["project_id"], {
        "rc_id": rc_id,
        "decision": decision,
        "approved_by": approved_by,
        "notes": notes,
    })

    return {"ok": True, "rc_id": rc_id, "decision": decision, "approved_by": approved_by}
