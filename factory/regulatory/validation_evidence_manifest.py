"""W5.3 Fase 5.4.4 (gobernanza) -- manifiesto sanitizado y versionable de
una corrida de evidencia de validación.

Diseño ALLOWLIST, no blocklist: en vez de enumerar campos prohibidos (que
se olvidan cuando se agrega un campo nuevo), se enumera explícitamente qué
sobrevive. Cualquier campo no listado aquí -- incluidos raw_response,
llm_output completo (contiene evidence_quote/rationale = texto literal del
documento), source_text, _by_req_candidates, o cualquier campo futuro que
alguien agregue a un record sin pensar en esto -- se descarta por
construcción, no por lista negra.

Solo sobreviven: hashes, métricas, versiones, estados, trazabilidad."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

VALIDATION_EVIDENCE_BASE = Path(__file__).parent / "validation_evidence"
MANIFESTS_SUBDIR = "manifests"
FILE_PERMISSIONS = 0o640
DIR_PERMISSIONS = 0o750

_MANIFEST_RECORD_KEYS = ("record_id", "status", "rejection_reason", "review_flags")
_MANIFEST_MANIFEST_KEYS = (
    "model", "model_digest", "prompt_sha256", "schema_name", "schema_sha256",
    "chunk_sha256", "options", "timestamp_utc", "manifest_incomplete",
)
_MANIFEST_TOP_KEYS = (
    "run_id", "run_context", "run_by", "timestamp_utc", "document_sha256",
    "document_type", "document_type_source", "total_chunks_real",
    "chunks_used", "coverage", "model", "model_digest", "ollama_version",
    "records_by_status", "validation_evidence_status", "golden_dataset_eligible",
)
_MANIFEST_CONCLUSION_KEYS = ("conclusion", "chunks_evaluated", "chunks_observed", "review_flags")


def sanitize_run_raw_for_manifest(raw: dict, all_records: list[dict] | None = None) -> dict:
    """Construye el manifiesto sanitizado a partir de result.raw (el dict
    de agregados de run_validation_evidence()) y, opcionalmente, los
    all_records completos (para incluir su metadata por-registro sin su
    contenido). Nunca copia un dict de origen entero -- siempre reconstruye
    campo por campo desde la allowlist."""
    manifest: dict = {k: raw[k] for k in _MANIFEST_TOP_KEYS if k in raw}

    per_req = raw.get("per_requirement_conclusions") or {}
    manifest["per_requirement_conclusions"] = {
        req_id: {k: v[k] for k in _MANIFEST_CONCLUSION_KEYS if k in v}
        for req_id, v in per_req.items()
    }

    if all_records is not None:
        sanitized_records = []
        for rec in all_records:
            entry = {k: rec[k] for k in _MANIFEST_RECORD_KEYS if k in rec}
            exec_manifest = rec.get("execution_manifest") or {}
            entry["execution_manifest"] = {
                k: exec_manifest[k] for k in _MANIFEST_MANIFEST_KEYS if k in exec_manifest
            }
            entry["errors_count"] = len(rec.get("errors") or [])
            sanitized_records.append(entry)
        manifest["records"] = sanitized_records
        manifest["records_total"] = len(sanitized_records)

    serialized = json.dumps(manifest, sort_keys=True, ensure_ascii=False)
    manifest["manifest_sha256"] = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return manifest


def write_sanitized_manifest(
    run_id: str, raw: dict, all_records: list[dict] | None = None,
    evidence_base: Path | None = None,
) -> Path:
    """Escribe el manifiesto sanitizado en validation_evidence/manifests/
    (subdirectorio NO ignorado por .gitignore -- estos archivos SI son
    versionables). Mismo patrón de escritura atomica + permisos que
    validation_evidence_writer.write_validation_evidence()."""
    from factory.core.path_policy import resolve_validation_evidence

    base = evidence_base or VALIDATION_EVIDENCE_BASE
    manifests_dir = base / MANIFESTS_SUBDIR
    manifests_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(manifests_dir, DIR_PERMISSIONS)

    raw_target = resolve_validation_evidence(run_id, manifests_dir)
    target = raw_target.with_name(raw_target.name.replace(".json", ".manifest.json"))

    manifest = sanitize_run_raw_for_manifest(raw, all_records)
    final_bytes = json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")

    tmp = target.with_name(f"{target.name}.{os.getpid()}.tmp")
    tmp.write_bytes(final_bytes)
    os.chmod(tmp, FILE_PERMISSIONS)
    try:
        dir_stat = manifests_dir.stat()
        os.chown(tmp, dir_stat.st_uid, dir_stat.st_gid)
    except PermissionError:
        pass
    os.replace(tmp, target)
    return target
