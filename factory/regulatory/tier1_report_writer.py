"""R2.3/D2 -- escritor de persistencia del informe Tier-1 asistido.

Separa la GENERACIÓN (tier1_report.generate_tier1_report(), pura, sin
tocar disco -- así siguen los tests existentes) de la PERSISTENCIA
(este módulo). Mismo patrón que validation_evidence_writer.py: escritura
atómica, permisos 0o640, tamaño verificado ANTES de escribir (nunca
truncamiento silencioso), sin función de borrado expuesta (retención sin
expiración automática -- cualquier borrado es una decisión humana
explícita fuera de este módulo)."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path

from factory.core.path_policy import TIER1_REPORT_MAX_BYTES, resolve_tier1_report
from factory.regulatory.tier1_report import Tier1Report, render_tier1_markdown

TIER1_REPORTS_BASE = Path(__file__).parent / "tier1_reports"
DIR_PERMISSIONS = 0o750
FILE_PERMISSIONS = 0o640


class Tier1ReportTooLargeError(Exception):
    """El informe (markdown o JSON) excede TIER1_REPORT_MAX_BYTES -- fail-closed:
    nunca se trunca el contenido para que quepa."""


def persist_tier1_report(report: Tier1Report, *, reports_base: Path | None = None) -> dict:
    """Escribe el informe Tier-1 en dos formas (mismo contenido, dos
    representaciones): {run_id}.md (para lectura humana/descarga) y
    {run_id}.json (estructurado, para el endpoint de solo-lectura y
    cualquier consumidor programático). Ambos confinados vía
    resolve_tier1_report() -- mismo run_id que ya trae el Tier1Report
    (el que generó evaluate_chunked(), nunca uno inventado aquí).

    Devuelve un manifest con las rutas, tamaños y sha256 de cada
    artefacto -- nunca recalculado sobre el archivo ya escrito con el
    campo adentro (mismo principio no-circular que package_receipt.json)."""
    base = reports_base or TIER1_REPORTS_BASE
    base.mkdir(parents=True, exist_ok=True)
    os.chmod(base, DIR_PERMISSIONS)

    md_bytes = render_tier1_markdown(report).encode("utf-8")
    json_payload = {
        "document_id": report.document_id,
        "agent_id": report.agent_id,
        "run_id": report.run_id,
        "generated_at": report.generated_at,
        "counts_by_bucket": report.counts_by_bucket(),
        "requirements": [asdict(r) for r in report.requirements],
    }
    json_bytes = json.dumps(json_payload, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8")

    for label, data in (("markdown", md_bytes), ("json", json_bytes)):
        if len(data) > TIER1_REPORT_MAX_BYTES:
            raise Tier1ReportTooLargeError(
                f"Informe Tier-1 {report.run_id} ({label}) pesa {len(data)} bytes, excede "
                f"el límite de {TIER1_REPORT_MAX_BYTES} bytes -- no se trunca, no se escribe."
            )

    md_path = resolve_tier1_report(report.run_id, ".md", base)
    json_path = resolve_tier1_report(report.run_id, ".json", base)
    _atomic_write(md_path, md_bytes, base)
    _atomic_write(json_path, json_bytes, base)

    return {
        "document_id": report.document_id,
        "agent_id": report.agent_id,
        "run_id": report.run_id,
        "generated_at": report.generated_at,
        "counts_by_bucket": report.counts_by_bucket(),
        "markdown_path": str(md_path),
        "markdown_sha256": hashlib.sha256(md_bytes).hexdigest(),
        "markdown_bytes": len(md_bytes),
        "json_path": str(json_path),
        "json_sha256": hashlib.sha256(json_bytes).hexdigest(),
        "json_bytes": len(json_bytes),
    }


def _atomic_write(target: Path, data: bytes, base: Path) -> None:
    """Mismo patrón que validation_evidence_writer._atomic_write(): escritura
    a un '.tmp<pid>' en el mismo directorio + os.replace() atómico -- nunca
    un archivo parcial visible con el nombre final."""
    tmp = target.with_name(f"{target.name}.{os.getpid()}.tmp")
    tmp.write_bytes(data)
    os.chmod(tmp, FILE_PERMISSIONS)
    try:
        dir_stat = base.stat()
        os.chown(tmp, dir_stat.st_uid, dir_stat.st_gid)
    except PermissionError:
        pass
    os.replace(tmp, target)
