"""
Fase 7 (`factory/docs/document_remediation_evolution/REGULATORY_VALIDATION_PLAN.md`
§4) — los 12 criterios mínimos de aceptación, mecanizados sobre lo que ya
existe real (Fases 0-6): schema, catálogo regulatorio, `applicability.py`,
`source_currency_log.jsonl` (Fase 1), `document_quality_gates.py` (Fase 6),
y las invariantes ya vigentes de `remediation_package_service.py`.

**Esto NO cierra el gate completo del roadmap** ("12/12 criterios en
verde, con evidencia real, contra el Golden Dataset completo") -- ese
gate exige primero recolectar las 8 categorías reales todavía faltantes
de `REGULATORY_VALIDATION_PLAN.md` §2 (cumplimiento documental, falsa
ausencia, cita irrelevante, contradicción, requisito no aplicable,
recomendación mal redactada, capacidad inventada, LOW_RISK real), trabajo
de recolección/construcción de corpus, no de código. Lo que este módulo
sí hace: mecaniza los 12 criterios en código real y los corre contra el
único par de casos real disponible hoy (`PKG-FS-V1-2-MEDIUM-RISK-REAL`,
`PKG-FS-V1-2-REAL-CONTROLLED`), reportando cada resultado con evidencia
real -- nunca inferida -- y declarando `NOT_EVALUATED` explícito donde el
mecanismo real todavía no existe (mismo principio de honestidad ya usado
en Fase 5/6).
"""
from __future__ import annotations

import json

from factory.regulatory import applicability as applicability_mod
from factory.regulatory import broken_link_report
from factory.regulatory.regulatory_catalog import known_entry_ids
from factory.services import document_quality_gates as quality_gates
from factory.services import paths as svc_paths
from factory.services.remediation_package_schemas import (
    SchemaValidationError,
    validate_remediation_change,
)


def check_schema_valid(changes: list[dict]) -> dict:
    """Criterio 1 -- 100% salidas válidas contra schema."""
    failures = []
    for change in changes:
        try:
            validate_remediation_change(change)
        except SchemaValidationError as e:
            failures.append({"change_id": change.get("change_id"), "reason": str(e)})
    if failures:
        return {"status": "FAIL", "reason": failures}
    return {"status": "PASS", "reason": f"{len(changes)} cambio(s), 0 errores de schema"}


def check_applicability_traceable(changes: list[dict], document_type: str) -> dict:
    """Criterio 2 -- 100% requisitos con aplicabilidad trazable
    (`applicability_matrix.yaml`, `run_context=validation`)."""
    failures = []
    for change in changes:
        requirement_id = change["requirement_id"]
        app = applicability_mod.applicability(requirement_id, document_type)
        if app["value"] in ("review_required",) or "reason" in app:
            failures.append({
                "change_id": change["change_id"], "requirement_id": requirement_id,
                "applicability": app,
            })
    if failures:
        return {"status": "FAIL", "reason": failures}
    return {"status": "PASS", "reason": f"{len(changes)} requisito(s) con aplicabilidad trazada, ninguno review_required"}


def check_official_source_citations(changes: list[dict]) -> dict:
    """Criterio 3 -- 100% referencias con fuente oficial (fail-closed
    contra el catálogo real)."""
    known = known_entry_ids()
    failures = []
    for change in changes:
        for citation in change["citations"]:
            entry_id = citation["regulatory_catalog_entry_id"]
            if entry_id not in known:
                failures.append({"change_id": change["change_id"], "regulatory_catalog_entry_id": entry_id})
    if failures:
        return {"status": "FAIL", "reason": failures}
    return {"status": "PASS", "reason": f"todas las citas referencian entradas reales del catálogo ({len(known)} conocidas)"}


def check_links_verified(changes: list[dict]) -> dict:
    """Criterio 4 -- 100% enlaces y citas verificadas. Reutiliza el log
    append-only real de `source_currency_checker.py` (Fase 1) vía
    `broken_link_report.evaluate_source` -- NUNCA dispara una verificación
    de red nueva aquí (ese es el trabajo de Fase 1, no de este gate)."""
    log_entries = _read_currency_log()
    source_ids = sorted({
        citation["regulatory_source"] for change in changes for citation in change["citations"]
    })
    results = {sid: broken_link_report.evaluate_source(sid, log_entries) for sid in source_ids}
    not_ok = {sid: r for sid, r in results.items() if r["status"] != broken_link_report.STATUS_OK}
    if not_ok:
        return {"status": "FAIL" if any(
            r["status"] == broken_link_report.STATUS_UNVERIFIED for r in not_ok.values()
        ) else "NOT_EVALUATED", "reason": not_ok}
    return {"status": "PASS", "reason": results}


def _read_currency_log() -> list[dict]:
    if not svc_paths.SOURCE_CURRENCY_LOG_FILE.exists():
        return []
    entries = []
    for line in svc_paths.SOURCE_CURRENCY_LOG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def check_no_invented_citations(changes: list[dict]) -> dict:
    """Criterio 5 -- 0 citas inventadas. `citation_text_sha256` se
    recalcula desde `literal_text` dentro de `validate_remediation_change`
    (ya cubierto por el criterio 1); esta función re-verifica de forma
    independiente para que el criterio tenga su propia evidencia."""
    import hashlib
    failures = []
    for change in changes:
        for citation in change["citations"]:
            recomputed = hashlib.sha256(citation["literal_text"].encode("utf-8")).hexdigest()
            if recomputed != citation["citation_text_sha256"]:
                failures.append({"change_id": change["change_id"], "citation_id": citation["citation_id"]})
    if failures:
        return {"status": "FAIL", "reason": failures}
    return {"status": "PASS", "reason": "citation_text_sha256 coincide con literal_text en todas las citas"}


def check_no_partial_coverage_gap() -> dict:
    """Criterio 6 -- 0 DOCUMENTATION_GAP con cobertura parcial. Gap real
    conocido (Fase 3): `verified_conclusions` solo existe cuando
    `use_verified_pipeline=True`, y los 2 paquetes reales de esta sesión
    se generaron con el motor de producción (`chunked_engine.py` en su
    modo default, heurística `EVALUATION_INCOMPLETE-prone`). No hay campo
    real que verificar en `RemediationChange` para este criterio hoy --
    se declara `NOT_EVALUATED` en vez de inventar un PASS sin evidencia."""
    return {
        "status": "NOT_EVALUATED",
        "reason": "requiere que los paquetes reales se generen con use_verified_pipeline=True "
                  "(Fase 3) para tener verified_conclusions -- ningún paquete real de esta sesión lo usa todavía",
    }


def check_no_artifact_divergence() -> dict:
    """Criterio 10 -- 0 divergencias entre artefactos. Gap real conocido:
    hoy se verifica manualmente (scripts ad hoc); no existe todavía un
    reverify automatizado de artefactos (`DOCUMENT_REMEDIATION_SPEC.md`
    §5, IMPLEMENTATION_VERIFICATION -- explícitamente fuera del sistema
    por diseño)."""
    return {
        "status": "NOT_EVALUATED",
        "reason": "reverify automatizado de artefactos no existe todavía -- verificado manualmente en sesiones previas",
    }


def check_no_pending_high_risk_without_exception(package_state: dict) -> dict:
    """Criterio 11 -- 0 HIGH_RISK pendientes al aprobar paquetes. Verifica
    la invariante ya forzada en escritura por
    `record_package_decision()`/`IncompleteExceptionCoverageError`, mismo
    principio, aplicado como lectura de auditoría sobre el estado ya
    persistido."""
    high_risk_ids = set(package_state["package"]["changes"]["high_risk"])
    exceptions = package_state.get("exceptions", {})
    reviewed_ids = {
        exc["change_id"] for exc in exceptions.values()
        if exc.get("status") == "REVIEWED" and exc.get("human_review_decision")
    }
    missing = high_risk_ids - reviewed_ids
    if missing:
        return {"status": "FAIL", "reason": f"HIGH_RISK sin excepción revisada: {sorted(missing)}"}
    return {
        "status": "PASS",
        "reason": f"{len(high_risk_ids)} cambio(s) HIGH_RISK, todos con excepción REVIEWED: {sorted(high_risk_ids)}",
    }


def check_no_automatic_release() -> dict:
    """Criterio 12 -- 0 liberaciones automáticas. Verificación estructural
    real (no una suposición): el router de `remediation_packages.py` no
    registra ninguna ruta que contenga "release" en su path, y el módulo
    no importa `create_release_record` -- por lo tanto ningún endpoint
    HTTP puede alcanzarlo, sin depender de un servidor en vivo."""
    from factory.api.routes import remediation_packages as pkg_routes

    release_paths = [r.path for r in pkg_routes.router.routes if "release" in r.path.lower()]
    imports_release_fn = "create_release_record" in vars(pkg_routes)
    if release_paths or imports_release_fn:
        return {
            "status": "FAIL",
            "reason": {"release_paths": release_paths, "imports_create_release_record": imports_release_fn},
        }
    return {"status": "PASS", "reason": "router sin rutas de release y sin importar create_release_record"}


def evaluate_golden_dataset_criteria(
    package_state: dict, changes: list[dict], structure: dict, document_type: str
) -> dict:
    """Corre los 12 criterios (§4) sobre UN paquete real. No implica que
    el Golden Dataset esté completo (ver docstring del módulo) -- solo
    reporta, con evidencia real, el estado mecanizable de cada criterio
    para este paquete."""
    writing_results = [quality_gates.evaluate_quality_gates(c, structure) for c in changes]
    writing_failed = [
        {"change_id": r["change_id"], "failed_controls": r["failed_controls"]}
        for r in writing_results
        if any(c in r["failed_controls"] for c in ("redaccion_longitud", "redaccion_verbo_controlado"))
    ]
    unverified_claims_failed = [
        {"change_id": r["change_id"]}
        for r in writing_results
        if "ausencia_afirmacion_no_demostrada" in r["failed_controls"]
    ]

    criteria = {
        "1_schema_valido": check_schema_valid(changes),
        "2_aplicabilidad_trazable": check_applicability_traceable(changes, document_type),
        "3_fuente_oficial": check_official_source_citations(changes),
        "4_enlaces_verificados": check_links_verified(changes),
        "5_sin_citas_inventadas": check_no_invented_citations(changes),
        "6_sin_cobertura_parcial_en_gap": check_no_partial_coverage_gap(),
        "7_campos_obligatorios_completos": check_schema_valid(changes),
        "8_sin_redaccion_invalida": (
            {"status": "FAIL", "reason": writing_failed} if writing_failed
            else {"status": "PASS", "reason": f"{len(changes)} cambio(s) sin fallos de redacción evaluables"}
        ),
        "9_sin_afirmaciones_no_demostradas": (
            {"status": "FAIL", "reason": unverified_claims_failed} if unverified_claims_failed
            else {"status": "PASS", "reason": f"{len(changes)} cambio(s) sin afirmaciones de implementación no demostrada"}
        ),
        "10_sin_divergencia_artefactos": check_no_artifact_divergence(),
        "11_sin_high_risk_pendiente": check_no_pending_high_risk_without_exception(package_state),
        "12_sin_liberacion_automatica": check_no_automatic_release(),
    }

    passed = [k for k, v in criteria.items() if v["status"] == "PASS"]
    failed = [k for k, v in criteria.items() if v["status"] == "FAIL"]
    not_evaluated = [k for k, v in criteria.items() if v["status"] == "NOT_EVALUATED"]

    return {
        "package_id": package_state["package"]["package_id"],
        "criteria": criteria,
        "passed": passed,
        "failed": failed,
        "not_evaluated": not_evaluated,
        "gate_12_of_12": len(passed) == 12,
    }
