"""
Fase 8 (`factory/docs/document_remediation_evolution/IMPLEMENTATION_ROADMAP.md`)
— Revisión de arquitectura final: consolida evidencia REAL de las Fases
0-7 en un informe único.

Este módulo NO decide nada. La decisión de habilitar cualquier endpoint
de release queda SIEMPRE fuera de este roadmap y SIEMPRE humana (mismo
principio de `DOCUMENT_REMEDIATION_SPEC.md` §5 `REGULATORY_COMPLIANCE` y
`LANGUAGE_AND_TECHNICAL_QUALITY_GATES.md` §6) — completar fases mejora la
conformidad documental y la trazabilidad, pero **nunca** constituye por
sí solo autorización de liberación. `release_decision` en el resultado
de este módulo es una constante fija, nunca calculada a partir de los
demás resultados -- ninguna combinación de gates en verde puede hacerla
cambiar.

`phase_status` está fijado a mano con los hechos reales ya verificados en
esta misma auditoría (commits reales, pendientes reales declarados en
cada fase) -- no se deriva de heurísticas sobre el repo, para no
esconder un pendiente real detrás de una inferencia equivocada."""
from __future__ import annotations

from pathlib import Path

from factory.regulatory import document_structure_extractor as extractor
from factory.services import golden_dataset_criteria as gdc

RELEASE_DECISION = {
    "status": "OUT_OF_SCOPE_HUMAN_ONLY",
    "reason": (
        "La decisión de si/cuándo/cómo se habilita un endpoint de release "
        "queda explícitamente fuera de este roadmap (Fase 8 de "
        "IMPLEMENTATION_ROADMAP.md) -- requiere aprobación humana de QA "
        "autorizado. Completar todas las fases mejora la conformidad "
        "documental y la trazabilidad; no constituye, por sí solo, "
        "autorización de liberación."
    ),
    "computed_from_gate_results": False,
}

PHASE_STATUS = {
    "fase_0_higiene": {
        "status": "CERRADA_SIN_COMMITEAR",
        "commit": None,
        "nota": (
            "Cambios reales aplicados (regulatory_catalog.py, "
            "sources/registry.json: URLs oficiales corregidas y "
            "verificadas por hash) pero NUNCA commiteados -- siguen como "
            "'M' en git status desde que se hicieron. Hallazgo real de "
            "esta consolidación, no asumido."
        ),
        "pendientes": ["decidir si se commitea junto con los 8 documentos de diseño"],
    },
    "fase_1_vigencia_fuentes": {
        "status": "CERRADA_PARCIAL", "commit": "1dd96ba",
        "pendientes": ["`human_source_update`: ninguna fuente llegó a REGULATORY_SOURCE_UNVERIFIED todavía, sin caso real"],
    },
    "fase_2_unificar_cobertura": {"status": "CERRADA", "commit": "e3f69a4", "pendientes": []},
    "fase_3_cablear_verificado": {
        "status": "CERRADA_PARCIAL", "commit": "5f8138e",
        "pendientes": ["corrida real con Ollama sobre FS_v1.2.pdf comparando contra los 19 findings de v5, no hecha"],
    },
    "fase_4_extraccion_estructurada": {"status": "CERRADA", "commit": "00b8e43", "pendientes": []},
    "fase_5_candidato_completo": {
        "status": "CERRADA_PARCIAL", "commit": "4e9424b",
        "pendientes": ["matriz de trazabilidad completa (§4)", "reseña de cambios y fundamento regulatorio (§6)"],
    },
    "fase_6_quality_gates": {
        "status": "CERRADA_PARCIAL", "commit": "ec36e8f",
        "pendientes": ["terminología consistente (NOT_EVALUATED, sin tabla real)", "ortografía/gramática (NOT_EVALUATED, sin herramienta instalada)"],
    },
    "fase_7_golden_dataset": {
        "status": "CERRADA_PARCIAL", "commit": "757d4da",
        "pendientes": ["8/14 categorías reales del Golden Dataset sin recolectar", "gate 12/12 NUNCA alcanzado (máximo posible hoy: 9/12)"],
    },
}


def _uncommitted_paths(repo_root: Path) -> list[str]:
    """Evidencia real de git status -- no una suposición. Devuelve rutas
    bajo document_remediation_evolution/ o los 2 archivos de Fase 0 que
    siguen sin commitear."""
    import subprocess
    result = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain",
         "factory/regulatory/regulatory_catalog.py",
         "factory/regulatory/sources/registry.json",
         "factory/docs/document_remediation_evolution/"],
        capture_output=True, text=True, check=True,
    )
    return [line[3:] for line in result.stdout.splitlines() if line.strip()]


def generate_consolidated_evidence_report(
    pdf_path: Path, packages_dir: Path, repo_root: Path, document_type: str = "FS"
) -> dict:
    """Corre los gates reales de Fases 6/7 contra los 2 casos reales
    disponibles y los combina con el estado real de cada fase (fijado a
    mano, ver PHASE_STATUS) en un único informe. No certifica nada por sí
    mismo -- `release_decision` es siempre la constante fija RELEASE_DECISION."""
    structure = extractor.extract_structure_from_pdf(pdf_path)

    import json
    golden_dataset_results = {}
    for pkg_dir in sorted(packages_dir.iterdir()):
        state_path = pkg_dir / "v1" / "state.json"
        if not state_path.exists():
            continue
        state = json.loads(state_path.read_text(encoding="utf-8"))
        changes = list(state["changes"].values())
        golden_dataset_results[pkg_dir.name] = gdc.evaluate_golden_dataset_criteria(
            state, changes, structure, document_type
        )

    any_gate_failed = any(
        r["failed"] for r in golden_dataset_results.values()
    )
    phases_not_fully_closed = [
        name for name, info in PHASE_STATUS.items() if info["status"] != "CERRADA"
    ]

    return {
        "phase_status": PHASE_STATUS,
        "golden_dataset_results": golden_dataset_results,
        "any_gate_failed": any_gate_failed,
        "phases_not_fully_closed": phases_not_fully_closed,
        "uncommitted_evidence": _uncommitted_paths(repo_root),
        "release_decision": RELEASE_DECISION,
    }
