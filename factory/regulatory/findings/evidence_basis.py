"""WP-B -- Epistemología del finding: `evidence_basis` + `coverage_dependencies`.

docs_plan/PLAN_HARDENING_ANALIZADOR_GMP_LOCAL_V2.md §4.2 ; docs_plan/ADR_HARDENING_V2.md.

`evidence_basis ∈ {PRESENCE, ABSENCE_DEPENDENT, INDETERMINATE}` -- campo aditivo en `Finding`
(no clase nueva, no modelo paralelo). NO se usa un valor `ABSENCE` puro: en HEAD ninguna
desviación GMP se sostiene solo sobre ausencia (todas necesitan un positivo presente ⇒
ABSENCE_DEPENDENT), y `REGULATORY_INCONCLUSIVE` es INDETERMINATE (limitación de MÉTODO
--juicio semántico fuera de alcance--, no del documento).

`coverage_dependencies` -- metadata POR FINDING (vive en `analysis_coverage.json`, NO en la
taxonomía GMP, NO es un Finding, NO recibe risk/remediation/state). Base segura para un
futuro ENFORCE: ENFORCE solo tendrá que leer `would_degrade`.

Este módulo NO toca la lógica interna de ningún detector: `stamp()` es un post-pass que
rellena el campo aditivo, y `coverage_dependencies()` deriva la metadata del mapa
dependencia-por-subtipo × verdicts de adecuación.
"""
from __future__ import annotations

from pathlib import Path

# ── evidence_basis por subtipo ──────────────────────────────────────────
_PRESENCE = frozenset({
    "INTERFACE_INCONSISTENCY", "CONTRADICTORY_FUNCTIONAL_BEHAVIOR",
    "REGULATORY_COMPLIANT_EVIDENCE",
})
_INDETERMINATE = frozenset({
    "REGULATORY_INCONCLUSIVE", "REGULATORY_GAP", "REGULATORY_PARTIAL",
})
# el resto (REQUIREMENT_NOT_*, IMPLEMENTATION_WITHOUT_REQUIREMENT, TEST_WITHOUT_REQUIREMENT,
# ORPHAN_DESIGN_ELEMENT, BROKEN_TRACE_LINK, PARTIAL_TEST_COVERAGE, *_GAP) => ABSENCE_DEPENDENT

EVIDENCE_BASES = ("PRESENCE", "ABSENCE_DEPENDENT", "INDETERMINATE")


def classify(finding) -> str:
    st = getattr(finding, "subtype", "") or ""
    ms = getattr(finding, "machine_state", "") or ""
    if st in _PRESENCE:
        return "PRESENCE"
    if st in _INDETERMINATE:
        return "INDETERMINATE"
    # una regla de completitud que el propio detector degradó (inconclusive_downgraders)
    # significa "no pude concluir sobre el contenido", no "el documento carece de X".
    if st.endswith("_GAP") and ms == "MACHINE_INCONCLUSIVE":
        return "INDETERMINATE"
    return "ABSENCE_DEPENDENT"


def stamp(findings) -> None:
    """Post-pass: setea `.evidence_basis` en cada finding. Campo aditivo; no cambia
    subtype, machine_state, human_state, risk ni ningún otro dato."""
    for f in findings:
        try:
            f.evidence_basis = classify(f)
        except Exception:  # noqa: BLE001
            f.evidence_basis = None


# ── dependencias de cobertura por subtipo ───────────────────────────────
_TEST_ROLES = ("SAT", "OQ", "IQ", "PQ")
_SELF = "__self__"   # la dependencia es el propio documento del finding

_DEP: dict[str, dict] = {
    "REQUIREMENT_NOT_TESTED":            {"roles": _TEST_ROLES,
                                         "caps": ("test_object_extraction", "graph.tested_by_edges")},
    "PARTIAL_TEST_COVERAGE":             {"roles": _TEST_ROLES,
                                         "caps": ("test_object_extraction", "graph.tested_by_edges")},
    "TEST_WITHOUT_REQUIREMENT":          {"roles": _TEST_ROLES,
                                         "caps": ("test_object_extraction", "graph.verifies_edges")},
    "ORPHAN_DESIGN_ELEMENT":             {"roles": ("URS", "FS") + _TEST_ROLES,
                                         "caps": ("test_object_extraction", "graph.tested_by_edges",
                                                  "graph.implemented_by_edges")},
    "REQUIREMENT_NOT_TRACED":            {"roles": ("FS", "DS"),
                                         "caps": ("graph.implemented_by_edges",)},
    "REQUIREMENT_NOT_IMPLEMENTED":       {"roles": ("FS", "DS"),
                                         "caps": ("graph.implemented_by_edges",)},
    "BROKEN_TRACE_LINK":                 {"roles": ("URS", "FS", "DS"),
                                         "caps": ("graph.implemented_by_edges",)},
    "IMPLEMENTATION_WITHOUT_REQUIREMENT": {"roles": ("URS",),
                                          "caps": ("source_ref_extraction",)},
}
# *_GAP y cualquier subtipo no listado => depende del PROPIO documento + section_scoping
_DEFAULT_DEP = {"roles": (_SELF,), "caps": ("section_scoping",)}


def _any_test_rows(doc_ids, canon_dir) -> bool:
    from factory.regulatory.canonical.persistence import STORE_DIR, CanonicalStore
    cdir = Path(canon_dir) if canon_dir is not None else STORE_DIR
    for d in doc_ids or []:
        try:
            with CanonicalStore(d, store_dir=cdir) as cs:
                if cs.counts().get("test", 0) > 0:
                    return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _capabilities(graph_edges: dict | None, doc_ids, canon_dir) -> dict:
    e = graph_edges or {}
    return {
        "graph.implemented_by_edges": e.get("implemented_by", 0) > 0,
        "graph.designed_by_edges": e.get("designed_by", 0) > 0,
        "graph.tested_by_edges": e.get("tested_by", 0) > 0,
        "graph.verifies_edges": e.get("verifies", 0) > 0,
        "source_ref_extraction": True,
        "section_scoping": True,   # simplificación OBSERVE (realmente es por-documento)
        "test_object_extraction": _any_test_rows(doc_ids, canon_dir),
    }


def coverage_dependencies(findings, assessment: dict, *, graph_edges: dict | None = None,
                          canon_dir=None) -> list[dict]:
    """Una entrada por finding. Determinista. `assessment` = salida de
    `extraction_adequacy.assess_corpus`."""
    by_doc = assessment.get("by_document", {})
    doc_ids = list(by_doc)

    def _verdict(d: str) -> str:
        return (by_doc.get(d) or {}).get("verdict", "NOT_ANALYZABLE")

    role_of = {d: ((by_doc[d].get("signals") or {}).get("tipo")) for d in doc_ids}
    docs_by_role: dict[str, list[str]] = {}
    for d, r in role_of.items():
        if r:
            docs_by_role.setdefault(r, []).append(d)
    caps = _capabilities(graph_edges, doc_ids, canon_dir)

    out: list[dict] = []
    for f in findings:
        basis = classify(f)
        dep = _DEP.get(getattr(f, "subtype", ""), _DEFAULT_DEP)

        if _SELF in dep["roles"]:
            req_roles = [role_of.get(f.document) or "self"]
            req_docs = [f.document]
        else:
            req_roles = list(dep["roles"])
            req_docs = [d for r in dep["roles"] for d in docs_by_role.get(r, [])]

        cap_missing = [c for c in dep["caps"] if not caps.get(c, True)]
        analyzable = [d for d in req_docs if _verdict(d) == "ANALYZABLE"]
        degraded = [d for d in req_docs if _verdict(d) == "DEGRADED"]
        missing_role = (not req_docs) or (not analyzable and not degraded)

        if basis == "PRESENCE":
            status_, would, reason = ("OK", False,
                "conclusión sobre texto presente; no depende de la completitud de otra región")
        elif basis == "INDETERMINATE":
            status_, would, reason = ("OK", False,
                "el método determinista ya no concluyó (INDETERMINATE); ENFORCE no lo degrada más. "
                "Cobertura anotada a nivel de modalidad.")
        else:  # ABSENCE_DEPENDENT
            if cap_missing or missing_role:
                status_, would = "MISSING", True
            elif degraded and not analyzable:
                status_, would = "DEGRADED", True
            elif degraded:
                status_, would = "DEGRADED", False   # hay ≥1 doc ANALYZABLE del rol
            else:
                status_, would = "OK", False
            bits = []
            if cap_missing:
                bits.append(f"capacidades ausentes: {cap_missing}")
            if missing_role:
                bits.append(f"ningún documento ANALYZABLE para roles {req_roles}")
            if degraded:
                bits.append(f"documentos DEGRADED: {degraded}")
            reason = "; ".join(bits) or "cobertura suficiente"

        out.append({
            "finding_id": getattr(f, "finding_id", None),
            "subtype": getattr(f, "subtype", None),
            "document": getattr(f, "document", None),
            "evidence_basis": basis,
            "required_roles": req_roles,
            "required_documents": req_docs,
            "required_capabilities": list(dep["caps"]),
            "coverage_status": status_,
            "would_degrade": would,
            "reason": reason,
        })
    return out


def histogram(cov_deps: list[dict]) -> dict:
    h: dict = {"would_degrade_true": 0, "would_degrade_false": 0,
               "by_basis": {}, "by_status": {}}
    for c in cov_deps:
        key = "would_degrade_true" if c.get("would_degrade") else "would_degrade_false"
        h[key] += 1
        b, s = c.get("evidence_basis"), c.get("coverage_status")
        h["by_basis"][b] = h["by_basis"].get(b, 0) + 1
        h["by_status"][s] = h["by_status"].get(s, 0) + 1
    return h
