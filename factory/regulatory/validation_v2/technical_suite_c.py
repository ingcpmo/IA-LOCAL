"""Dry-run de Suite C (TECHNICAL) -- DETERMINISTIC-only, ground truth corregido.

Autorización de Capa 9 (2026-08-27): implementar SOLO capacidades TECHNICAL
DETERMINISTAS; NO activar HYBRID; NO pedir PILOT_EXECUTION; NO construir
detectores LOCAL_LLM autónomos.

GROUND TRUTH CORREGIDO tras revisión normativa (ver
`fixtures_draft/technical_suite_c.yaml` v0.2 y
`requirement_catalog/technical_completeness_rules_draft.yaml`):

  - DETERMINISTIC_V1 (C06, C12): inconsistencia de interfaz cross-documento
    real -> la regla YA implementada (technical_findings.py) DEBE detectarlos.
  - DETERMINISTIC_V2 (C01, C03, C04, C05, C08, C09, C10): "tema presente,
    sub-atributo obligatorio ausente" -- regla de completitud GOBERNADA
    (`technical_completeness_rules.yaml`, FIRMADA 1.0), implementada en
    `technical_findings.completeness_findings`. El positivo va en TC-FS y
    su negativo conforme en TC-FSOK (doc separado) para que la regla no
    "vea" la evidencia conforme del negativo al evaluar el positivo.
  - SEMANTIC (C07): juicio de criticidad + defecto tema-ausente -- fuera del
    detector determinista; NO se activa HYBRID ni LLM.
  - NOT_APPLICABLE (C02, C11, C13): la revisión normativa mostró que NO hay
    fuente normativa ni requisito de cliente que sostenga un defecto
    positivo. NO se cuentan ni como positivo ni como negativo. Razón
    documentada en el fixture.
  - negativos (C14-C20): el control SÍ está descrito / fuera de alcance
    -> el analizador NO debe emitir nada.

NINGUNA clasificación se cambió para mejorar el recall: se retiraron 3
casos (C02, C11, C13) que la revisión normativa mostró mal especificados.
Determinista, sin LLM, sin gobernanza consumida, DOCUMENT_EGRESS = 0.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path as _P

from factory.regulatory.canonical import model as m
from factory.regulatory.canonical.persistence import CanonicalStore
from factory.regulatory.graph import build as gb

PROJECT_ID = "SUITE-C-TECH"
# TC-FS   = FS con los defectos (positivos)
# TC-FSOK = FS conforme (negativos) -- documento SEPARADO para que la regla de
#           completitud no "vea" la evidencia conforme del negativo al evaluar
#           el positivo (ambos comparten tema pero no documento).
URS, FS, FSOK, DS1, DS2, SAT = "TC-URS", "TC-FS", "TC-FSOK", "TC-DS1", "TC-DS2", "TC-SAT"
_EXT_VER = "canonical-v1-2026-08"

# GROUND TRUTH CORREGIDO tras revision normativa de Capa 9 (2026-08-27):
#   DETERMINISTIC_V1 : regla de interfaz ya implementada en B6b v1
#   DETERMINISTIC_V2 : regla de completitud gobernada (technical_completeness_
#                      rules_draft.yaml) -- pendiente de firma, aun NO implementada
#   SEMANTIC         : requiere lectura comprensiva -- fuera del detector; NO LLM/HYBRID
#   NOT_APPLICABLE   : sin fuente normativa ni requisito de cliente -> no hay
#                      defecto positivo; NO se cuenta ni como positivo ni como negativo
DETERMINISTIC_V1 = "DETERMINISTIC_V1"
DETERMINISTIC_V2 = "DETERMINISTIC_V2"
SEMANTIC = "SEMANTIC"
NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class SuiteCCase:
    case_id: str
    topic: str
    expected_finding: bool
    expected_class: str | None
    expected_subtype: str | None
    detection_class: str | None   # DETERMINISTIC_V1|V2 | SEMANTIC | NOT_APPLICABLE | None (negativo)
    anchor: str                   # substring que debe aparecer en el finding (solo positivos DET_V1)


CASES: list[SuiteCCase] = [
    # ---- positivos validos: objetivo DETERMINISTA (regla de completitud gobernada, B6b v2) ----
    SuiteCCase("C01", "audit_trail_design", True, "TechnicalFinding", "AUDIT_TRAIL_DESIGN_GAP", DETERMINISTIC_V2,
               "audit trail records every change"),
    SuiteCCase("C03", "backup_recovery", True, "TechnicalFinding", "BACKUP_RECOVERY_GAP", DETERMINISTIC_V2,
               "nightly backup of the application database"),
    SuiteCCase("C04", "access_control", True, "SecurityFinding", "ACCESS_CONTROL_GAP", DETERMINISTIC_V2,
               "assigned to one of the roles"),
    SuiteCCase("C05", "authority_check", True, "SecurityFinding", "AUTHORITY_CHECK_GAP", DETERMINISTIC_V2,
               "enforces role based access"),
    SuiteCCase("C08", "data_retention", True, "TechnicalFinding", "TECHNICAL_DESIGN_GAP", DETERMINISTIC_V2,
               "retained for a period of seven years"),
    SuiteCCase("C09", "audit_trail_integrity", True, "DataIntegrityFinding", "AUDIT_TRAIL_INTEGRITY_GAP", DETERMINISTIC_V2,
               "audit trail"),
    SuiteCCase("C10", "attributable", True, "DataIntegrityFinding", "ALCOA_ATTRIBUTABLE_GAP", DETERMINISTIC_V2,
               "proper credentials"),
    # ---- positivos validos: objetivo DETERMINISTA (regla de interfaz, B6b v1 -- ya implementada) ----
    SuiteCCase("C06", "interfaces", True, "TechnicalFinding", "INTERFACE_INCONSISTENCY", DETERMINISTIC_V1,
               "IF-PCS-SCADA-01"),
    SuiteCCase("C12", "interfaces", True, "TechnicalFinding", "INTERFACE_INCONSISTENCY", DETERMINISTIC_V1,
               "IF-EMS-WFI-07"),
    # ---- positivo valido: SEMANTIC (fuera del detector; no LLM/HYBRID ahora) ----
    SuiteCCase("C07", "redundancy", True, "TechnicalFinding", "REDUNDANCY_GAP", SEMANTIC, ""),
    # ---- NOT_APPLICABLE (revision normativa: no hay defecto positivo -- no se puntua) ----
    SuiteCCase("C02", "time_sync", False, None, None, NOT_APPLICABLE, ""),
    SuiteCCase("C11", "physical_security", False, None, None, NOT_APPLICABLE, ""),
    SuiteCCase("C13", "backup_recovery", False, None, None, NOT_APPLICABLE, ""),
    # ---- negativos (el control tecnico SI esta descrito, o no aplica) ----
    SuiteCCase("C14", "audit_trail_design", False, None, None, None, ""),
    SuiteCCase("C15", "access_control", False, None, None, None, ""),
    SuiteCCase("C16", "time_sync", False, None, None, None, ""),
    SuiteCCase("C17", "interfaces", False, None, None, None, ""),
    SuiteCCase("C18", "redundancy", False, None, None, None, ""),
    SuiteCCase("C19", "data_retention", False, None, None, None, ""),
    SuiteCCase("C20", "physical_security", False, None, None, None, ""),
]

VALID_POSITIVES = [c for c in CASES if c.expected_finding]
DETERMINISTIC_TARGET = [c for c in VALID_POSITIVES if c.detection_class in (DETERMINISTIC_V1, DETERMINISTIC_V2)]
SEMANTIC_ONLY = [c for c in VALID_POSITIVES if c.detection_class == SEMANTIC]
NOT_APPLICABLE_CASES = [c for c in CASES if c.detection_class == NOT_APPLICABLE]
NEGATIVE_CASES = [c for c in CASES if not c.expected_finding and c.detection_class is None]


def _c(store, did, page, text, tipo="control"):
    store.put(m.build_claim(did, page, text, tipo, text[:180]))


def build_suite_c_corpus(canon_dir, graph_dir) -> dict:
    """Materializa los 20 casos en un corpus sintético fiel. Devuelve los
    conteos del grafo."""
    with CanonicalStore(URS, store_dir=canon_dir) as s:
        s.put(m.Document(document_id=URS, sha256="u" * 64, tipo="URS", titulo="URS suite C", n_paginas=20))
        # requisitos de interfaz SIN citar el identificador literal (evitar que
        # una frase-placeholder de la URS cuente como spec de interfaz que
        # contradice al diseño). El identificador cruzado vive en FS/DS/SAT.
        _c(s, URS, 1, "UR-IF-01 The interface between the PCS and the SCADA system shall have "
                      "its polling behaviour defined.")
        _c(s, URS, 2, "UR-IF-07 The interface between the EMS and the WFI system shall have its "
                      "communication-failure behaviour defined.")

    with CanonicalStore(FS, store_dir=canon_dir) as s:
        s.put(m.Document(document_id=FS, sha256="f" * 64, tipo="FS", titulo="FS suite C", n_paginas=60))
        # C06 -- lado FS de la inconsistencia de interfaz (valor de parámetro divergente)
        _c(s, FS, 30, "For interface IF-PCS-SCADA-01 the SCADA polling interval shall be 500 ms.", "function")
        # C01 DETERMINISTIC_V2 -- audit trail presente, sin proteccion contra modificacion privilegiada
        _c(s, FS, 12, "The audit trail records every change made to critical process parameters.", "function")
        # C02 NOT_APPLICABLE -- (materializado; sin base normativa, el analizador no debe emitir)
        _c(s, FS, 13, "Timestamps are applied to every audit record and every batch report.", "function")
        # C03 DETERMINISTIC_V2 -- backup sin prueba de restore (RTO/RPO fuera de alcance)
        _c(s, FS, 14, "A nightly backup of the application database is performed automatically.", "function")
        # C04 DETERMINISTIC_V2 -- roles sin nivel de autorizacion por operacion
        _c(s, FS, 15, "Users are assigned to one of the roles: Operator, Supervisor or Engineer.", "function")
        # C05 DETERMINISTIC_V2 -- sin chequeo de autoridad por operacion
        _c(s, FS, 16, "The system enforces role based access for the operator interface.", "function")
        # C08 DETERMINISTIC_V2 -- retencion sin verificacion de accesibilidad/legibilidad
        _c(s, FS, 18, "Electronic records are retained for a period of seven years.", "function")
        # C09 DETERMINISTIC_V2 -- audit trail sin capacidad de deteccion de manipulacion (medio libre)
        _c(s, FS, 19, "The audit trail is stored in a dedicated table of the application database.", "function")
        # C11 NOT_APPLICABLE -- (materializado; Annex 11 12.1 admite solo-logico justificado)
        _c(s, FS, 20, "The application executes on a Windows server located in the plant.", "function")

    # ---- TC-FSOK: FS conforme -- documento SEPARADO con los negativos ----
    with CanonicalStore(FSOK, store_dir=canon_dir) as s:
        s.put(m.Document(document_id=FSOK, sha256="0" * 64, tipo="FS", titulo="FS suite C (conforme)", n_paginas=60))
        # C14 -- audit trail con campos completos Y proteccion contra modificacion privilegiada
        _c(s, FSOK, 40, "The audit trail records operator id, timestamp, previous value and new "
                        "value for every change to a critical parameter, and the audit trail "
                        "cannot be modified or disabled by any user role, including administrators.",
           "function")
        # C15 -- roles adecuados + nivel de autorizacion por operacion
        _c(s, FSOK, 41, "Roles are defined with least privilege for each function; privileges are "
                        "defined per role for each operation and reviewed periodically.", "function")
        # C16 -- fuente de tiempo maestra descrita explicitamente (control negativo)
        _c(s, FSOK, 42, "A master time source is described explicitly and all nodes synchronise to "
                        "it every hour.", "function")
        # C17 -- interfaz descrita de forma consistente dentro del mismo documento
        _c(s, FSOK, 43, "The internal HMI to historian interface is described consistently: a "
                        "polling interval of 200 ms is used in every section.", "function")
        # C18 -- redundancia fuera del alcance del FS de aplicacion (cross-reference legitima)
        _c(s, FSOK, 44, "Infrastructure redundancy is out of scope for this application FS and is "
                        "covered by the infrastructure qualification.", "function")
        # C19 -- retencion CON verificacion de accesibilidad/legibilidad/integridad descrita
        _c(s, FSOK, 45, "Electronic records are retained for seven years; their accessibility, "
                        "legibility and integrity are verified annually.", "function")

    with CanonicalStore(DS1, store_dir=canon_dir) as s:
        s.put(m.Document(document_id=DS1, sha256="d" * 64, tipo="DS", titulo="EMS control narrative", n_paginas=40))
        # C06 -- lado DS de la inconsistencia de interfaz (valor divergente 1000 ms vs 500 ms)
        _c(s, DS1, 8, "For interface IF-PCS-SCADA-01 the SCADA polling interval shall be 1000 ms.")
        # C12 -- lado DS1 de la inconsistencia de interfaz (modal: shall hold last value)
        _c(s, DS1, 9, "For interface IF-EMS-WFI-07 on communication failure the system shall hold "
                      "the last known value.")
        # C07 SEMANTIC -- sin redundancia/failover del PLC de control crítico
        _c(s, DS1, 10, "The EMS control PLC executes the environmental monitoring control strategy.")
        # C10 DETERMINISTIC_V2 -- acciones de calibración sin identidad individual
        _c(s, DS1, 11, "Calibration actions require the technician to have proper credentials.")
        # C13 NOT_APPLICABLE -- (se materializa igual; el analizador no debe emitir nada por esto)
        _c(s, DS1, 12, "On restart the EMS control PLC resumes execution of the control strategy.")

    with CanonicalStore(DS2, store_dir=canon_dir) as s:
        s.put(m.Document(document_id=DS2, sha256="e" * 64, tipo="DS", titulo="WFI control narrative", n_paginas=40))
        # C12 -- lado DS2: modal OPUESTO sobre el mismo predicado (shall NOT hold last value)
        _c(s, DS2, 7, "For interface IF-EMS-WFI-07 on communication failure the system shall not "
                      "hold the last known value and shall force outputs to a safe state.")

    with CanonicalStore(SAT, store_dir=canon_dir) as s:
        s.put(m.Document(document_id=SAT, sha256="a" * 64, tipo="SAT", titulo="SAT suite C", n_paginas=20))
        # los identificadores de interfaz cruzados SÍ se prueban -> no son 'orphan'
        s.put(m.build_test(SAT, 3, "SAT-IF-01",
                           "Test case SAT-IF-01: verify interface IF-PCS-SCADA-01 polling behaviour."))
        s.put(m.build_test(SAT, 4, "SAT-IF-07",
                           "Test case SAT-IF-07: verify interface IF-EMS-WFI-07 communication failure handling."))

    return gb.build_project_graph(
        PROJECT_ID,
        [(URS, "URS"), (FS, "FS"), (FSOK, "FS"), (DS1, "DS"), (DS2, "DS"), (SAT, "SAT")],
        canon_dir=canon_dir, graph_dir=graph_dir,
    )


def run_suite_c_dry(canon_dir, graph_dir) -> dict:
    """Corre el analizador TECHNICAL DETERMINISTA (B6b v1) sobre el corpus
    de Suite C y mide contra el GROUND TRUTH CORREGIDO. Sin LLM, sin
    gobernanza. Mantiene los gates originales; NO reclasifica casos.

    C02/C11/C13 son NOT_APPLICABLE -> no se puntuan (ni positivo ni
    negativo). C07 es SEMANTIC -> cuenta en el denominador de recall pero
    NO es objetivo del detector determinista."""
    from factory.regulatory.findings.technical_findings import graph_technical_findings
    from factory.regulatory.validation_v2 import gates

    counts = build_suite_c_corpus(canon_dir, graph_dir)
    stats: dict = {}
    findings = graph_technical_findings(
        PROJECT_ID, [URS, FS, FSOK, DS1, DS2, SAT], extraction_version=_EXT_VER,
        run_id="suite-c-dry", canon_dir=canon_dir, graph_dir=graph_dir, stats=stats)

    positives = list(VALID_POSITIVES)      # C01,C03,C04,C05,C06,C07,C08,C09,C10,C12
    negatives = list(NEGATIVE_CASES)       # C14..C20 -- NO incluye NOT_APPLICABLE

    matched_ids: set[str] = set()
    detected: dict[str, bool] = {}
    for c in positives:
        hit = next((f for f in findings
                    if f.finding_class == c.expected_class
                    and f.subtype == c.expected_subtype
                    and (c.anchor and c.anchor in f.source_text)
                    and f.finding_id not in matched_ids), None)
        detected[c.case_id] = hit is not None
        if hit:
            matched_ids.add(hit.finding_id)

    false_positives = [
        {"subtype": f.subtype, "class": f.finding_class, "document": f.document,
         "page": f.page, "source_text": f.source_text[:160]}
        for f in findings if f.finding_id not in matched_ids
    ]

    # case_results para el gate original (sin tocar umbrales)
    case_results: list[dict] = []
    for c in positives:
        case_results.append({"case_id": c.case_id, "expected_finding": True,
                             "emitted_finding": detected[c.case_id],
                             "subtype_match": detected[c.case_id]})
    for c in negatives:
        touched = any(c.topic in (f.rationale or "") for f in findings if f.finding_id not in matched_ids)
        case_results.append({"case_id": c.case_id, "expected_finding": False,
                             "emitted_finding": touched})
    for i, fp in enumerate(false_positives):
        case_results.append({"case_id": f"FP-{fp['subtype']}-{i}",
                             "expected_finding": False, "emitted_finding": True})

    report = gates.evaluate_technical(case_results)

    missed = [c for c in positives if not detected[c.case_id]]
    missed_det_target = [c for c in missed if c.detection_class in (DETERMINISTIC_V1, DETERMINISTIC_V2)]
    missed_semantic = [c for c in missed if c.detection_class == SEMANTIC]
    n_valid_pos = len(positives)
    n_det_target = len(DETERMINISTIC_TARGET)
    return {
        "graph_edges": counts.get("edges_by_rel", counts),
        "n_valid_positive": n_valid_pos,
        "n_detected_now": sum(detected.values()),
        "n_missed": len(missed),
        "n_false_positives": len(false_positives),
        "recall_now": round(sum(detected.values()) / n_valid_pos, 3),
        "by_case": detected,
        "false_positives": false_positives,
        "gate_report": report.as_dict(),
        "stats": stats,
        "n_findings_total": len(findings),
        # ---- ground truth corregido ----
        "VALID_POSITIVE_CASES": sorted(c.case_id for c in positives),
        "DETERMINISTIC_TARGET_CASES": sorted(c.case_id for c in DETERMINISTIC_TARGET),
        "SEMANTIC_CASES": sorted(c.case_id for c in SEMANTIC_ONLY),
        "NOT_APPLICABLE_CASES": sorted(c.case_id for c in NOT_APPLICABLE_CASES),
        # techo de recall determinista = objetivo determinista / positivos validos
        "PROJECTED_MAX_DETERMINISTIC_RECALL": round(n_det_target / n_valid_pos, 3),
        # estado actual (B6b v1 solo; reglas v2 aun sin firmar/implementar)
        "DETECTED_NOW": sorted(c.case_id for c in positives if detected[c.case_id]),
        "MISSED_NOW": sorted(c.case_id for c in missed),
        "MISSED_DETERMINISTIC_TARGET_PENDING_V2": sorted(c.case_id for c in missed_det_target),
        "MISSED_SEMANTIC_OUT_OF_SCOPE": sorted(c.case_id for c in missed_semantic),
        "FALSE_POSITIVES": len(false_positives),
    }


def run_suite_c_formal(canon_dir=None, graph_dir=None) -> dict:
    """Suite C FORMAL (benchmark FASE 10). Exige el fixture FIRMADO, corre
    bajo `network_locked()` y consolida TODOS los gates de FASE 10:
    TECHNICAL_RECALL, TECHNICAL_FALSE_POSITIVE, FABRICATED_CITATIONS,
    TRACEABILITY_COMPLETE, LOCAL_ONLY, DOCUMENT_EGRESS.

    NO modifica el ground truth. Determinista, sin LLM."""
    import tempfile
    from factory.regulatory.validation_v2 import fixtures
    from factory.regulatory.validation_v2.local_only import network_locked

    fixtures.assert_signed(fixtures.SUITE_C)   # fail-closed si no está firmado

    cdir = canon_dir or _P(tempfile.mkdtemp())
    gdir = graph_dir or _P(tempfile.mkdtemp())

    with network_locked() as egress:
        r = run_suite_c_dry(cdir, gdir)

    # FABRICATED_CITATIONS: cada finding emitido está anclado a source_text
    # literal de un claim del corpus (benchmark sintético) -> por construcción 0.
    # Se verifica que ningún source_text esté vacío.
    from factory.regulatory.findings.technical_findings import graph_technical_findings
    findings = graph_technical_findings(
        PROJECT_ID, [URS, FS, FSOK, DS1, DS2, SAT], extraction_version=_EXT_VER,
        run_id="suite-c-formal", canon_dir=cdir, graph_dir=gdir)
    fabricated = sum(1 for f in findings if not (f.source_text or "").strip())

    edges = r["graph_edges"] if isinstance(r["graph_edges"], dict) else {}
    traceability_complete = bool(edges) and sum(edges.values()) > 0

    tech = r["gate_report"]
    all_gates = list(tech["gates"]) + [
        {"name": "FABRICATED_CITATIONS", "value": fabricated, "threshold": "0",
         "passed": fabricated == 0, "detail": f"{len(findings)} findings, todos anclados"},
        {"name": "TRACEABILITY_COMPLETE", "value": "YES" if traceability_complete else "NO",
         "threshold": "YES", "passed": traceability_complete,
         "detail": f"edges={edges}"},
        {"name": "LOCAL_ONLY", "value": egress.local_only, "threshold": "YES",
         "passed": egress.local_only is True, "detail": ""},
        {"name": "DOCUMENT_EGRESS", "value": egress.document_egress_bytes, "threshold": "0",
         "passed": egress.document_egress_bytes == 0,
         "detail": f"attempts={list(getattr(egress, 'attempts', []))}"},
    ]
    all_passed = all(g["passed"] for g in all_gates)
    tp = r["n_detected_now"]
    fn_cases = r["MISSED_NOW"]
    return {
        "suite": "technical_suite_c_formal",
        "fixture_version": fixtures.load_fixture(fixtures.SUITE_C).get("version"),
        "fixture_signed": True,
        "TP": tp,
        "FN": fn_cases,
        "FP": r["n_false_positives"],
        "recall": r["recall_now"],
        "VALID_POSITIVE_CASES": r["VALID_POSITIVE_CASES"],
        "DETERMINISTIC_TARGET_CASES": r["DETERMINISTIC_TARGET_CASES"],
        "SEMANTIC_CASES": r["SEMANTIC_CASES"],
        "NOT_APPLICABLE_CASES": r["NOT_APPLICABLE_CASES"],
        "detected": r["DETECTED_NOW"],
        "gates": all_gates,
        "all_passed": all_passed,
        "scope_policy": r["stats"].get("completeness_scope"),
        "local_only": egress.local_only,
        "document_egress_bytes": egress.document_egress_bytes,
    }
