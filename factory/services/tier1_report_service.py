"""R2.3/D2 -- servicio de solo-lectura de informes Tier-1 asistidos ya
persistidos (factory/regulatory/tier1_report_writer.py).

Mismo principio que gmp_report_service.py/gmpai_artifact_service.py: capa
de presentación sobre datos YA generados, nunca dispara una corrida nueva
ni invoca al modelo -- una corrida real de Tier-1 exige su propia
PILOT_EXECUTION vigente (ver factory/regulatory/tier1_report.py), fuera
del alcance HTTP de este servicio a propósito (evita que cualquier
llamador con API key dispare inferencia real vía el endpoint)."""
from __future__ import annotations

import json
from pathlib import Path

from factory.regulatory import tier1_report_writer as _writer

_JSON_SUFFIX = ".json"
_MD_SUFFIX = ".md"


class Tier1ReportNotFound(Exception):
    """No existe informe persistido para el run_id pedido."""


def list_reports(*, reports_base: Path | None = None) -> list[dict]:
    """Resumen de todos los informes Tier-1 persistidos (uno por run_id),
    más recientes primero por mtime del .json. Nunca lee el markdown
    completo -- solo counts_by_bucket/metadata, igual de barato que un
    índice."""
    # Referencia al módulo (no al nombre importado suelto) para que un
    # monkeypatch de tier1_report_writer.TIER1_REPORTS_BASE en tests siga
    # siendo la única fuente de verdad -- mismo motivo que
    # test_gmpai_artifacts.py monkeypatchea el atributo del propio módulo
    # de servicio, no una copia importada aparte.
    base = reports_base or _writer.TIER1_REPORTS_BASE
    if not base.exists():
        return []
    summaries = []
    for path in base.glob(f"*{_JSON_SUFFIX}"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        summaries.append({
            "run_id": data.get("run_id", path.stem),
            "document_id": data.get("document_id"),
            "agent_id": data.get("agent_id"),
            "generated_at": data.get("generated_at"),
            "counts_by_bucket": data.get("counts_by_bucket", {}),
        })
    summaries.sort(key=lambda s: s.get("generated_at") or "", reverse=True)
    return summaries


def get_report_json(run_id: str, *, reports_base: Path | None = None) -> dict:
    """Informe Tier-1 estructurado completo (requirements por bucket
    incluidos) para el run_id pedido."""
    base = reports_base or _writer.TIER1_REPORTS_BASE
    path = base / f"{run_id}{_JSON_SUFFIX}"
    if not path.exists():
        raise Tier1ReportNotFound(f"No hay informe Tier-1 persistido para run_id={run_id!r}")
    return json.loads(path.read_text(encoding="utf-8"))


def get_report_markdown(run_id: str, *, reports_base: Path | None = None) -> str:
    """Informe Tier-1 en markdown (el mismo texto que
    render_tier1_markdown() produjo al persistirse) para el run_id pedido."""
    base = reports_base or _writer.TIER1_REPORTS_BASE
    path = base / f"{run_id}{_MD_SUFFIX}"
    if not path.exists():
        raise Tier1ReportNotFound(f"No hay informe Tier-1 persistido para run_id={run_id!r}")
    return path.read_text(encoding="utf-8")
