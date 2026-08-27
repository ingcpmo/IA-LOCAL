"""Findings FUNCIONALES / de TRAZABILIDAD / de COBERTURA desde el grafo
(V2, B6a) -- FASE 5.2 + FASE 7.

DETERMINISTA, sin LLM: recorre el evidence graph (B2) y emite
`FunctionalFinding` / `TraceabilityFinding` / `TestCoverageFinding`
(taxonomía B5) para lo que el grafo puede afirmar con aristas literales:

  - `contradicts` (claim<->claim, mismo ref, modal opuesto)
      -> FunctionalFinding: CONTRADICTORY_FUNCTIONAL_BEHAVIOR
  - test sin `verifies` ni `tested_by` entrante
      -> TestCoverageFinding: TEST_WITHOUT_REQUIREMENT
  - claim de un documento FUENTE (URS) sin `implemented_by`/`tested_by` saliente
      -> TraceabilityFinding: REQUIREMENT_NOT_TRACED

Los findings que dependen de linkear un requisito DEL CATÁLOGO a un claim
(REQUIREMENT_NOT_IMPLEMENTED / REQUIREMENT_NOT_TESTED con el req_id
regulatorio) quedan para B6 con capa semántica (embeddings / agente) --
el linkeo determinista requisito->claim es débil en corpus real (ver
deuda declarada de B2).

El anclaje de cada finding es el `source_text` LITERAL del claim/test,
resuelto abriendo el `CanonicalStore` (B1). Sin source_text no se emite.
"""
from __future__ import annotations

from factory.regulatory.canonical.persistence import STORE_DIR as CANON_DIR, CanonicalStore
from factory.regulatory.findings.risk import compute_risk
from factory.regulatory.findings.taxonomy import FindingProvenance, build_finding
from factory.regulatory.graph import queries as gq
from factory.regulatory.graph.store import GraphStore

_SOURCE_DOC_TYPES = ("URS",)   # documentos "fuente" de trazabilidad


def _claim_lookup(canon_dir, document_ids) -> dict:
    """{claim_id: {source_text, pagina, section_id}} y {test_id: {...}}."""
    out: dict = {}
    for did in document_ids:
        try:
            with CanonicalStore(did, store_dir=canon_dir) as s:
                for c in s.all("claim"):
                    out[c["claim_id"]] = {"source_text": c.get("source_text", ""),
                                          "pagina": c.get("pagina"),
                                          "section_id": c.get("section_id"),
                                          "document_id": did}
                for t in s.all("test"):
                    out[t["test_id"]] = {"source_text": t.get("descripcion", ""),
                                         "pagina": (t.get("provenance") or {}).get("page"),
                                         "section_id": t.get("section_id"),
                                         "document_id": did}
        except Exception:  # noqa: BLE001 -- un store ausente no aborta el resto
            continue
    return out


def _anchorable(rec) -> bool:
    return bool((rec or {}).get("source_text", "").strip()) and isinstance((rec or {}).get("pagina"), int) and rec["pagina"] >= 1


def graph_functional_findings(project_id: str, document_ids: list[str], *,
                              extraction_version: str, run_id: str | None = None,
                              canon_dir=CANON_DIR, graph_dir=None) -> list:
    from factory.regulatory.graph.store import STORE_DIR as GRAPH_DIR
    g = GraphStore(project_id, store_dir=graph_dir or GRAPH_DIR)
    lut = _claim_lookup(canon_dir, document_ids)
    src_docs = _source_document_ids(g)
    findings: list = []

    # ── contradicciones ────────────────────────────────────────────────
    for a, b, attrs in gq.contradictions(g):
        rec_a, rec_b = lut.get(a.node_id), lut.get(b.node_id)
        if not _anchorable(rec_a):
            continue
        subtype = "CONTRADICTORY_FUNCTIONAL_BEHAVIOR"
        prov = FindingProvenance(document_id=rec_a["document_id"],
                                 extraction_version=extraction_version, run_id=run_id,
                                 agent_id="functional_consistency_agent",
                                 graph_path=[a.node_id, "contradicts", b.node_id])
        rationale = (f"El grafo detecta contradicción (heurística: {attrs.get('heuristic')}, "
                     f"ref {attrs.get('via_ref')}) entre este claim y "
                     f"'{(rec_b or {}).get('source_text','')[:120]}'. BORRADOR ASISTIDO -- "
                     f"revisión humana requerida.")
        findings.append(build_finding(
            "FunctionalFinding", subtype, severity="MAJOR",
            document=rec_a["document_id"], page=rec_a["pagina"],
            source_text=rec_a["source_text"], section=rec_a.get("section_id"),
            rationale=rationale, confidence="LOW",
            machine_state="MACHINE_DEVIATION_CANDIDATE", provenance=prov,
            risk=compute_risk(subtype, "MAJOR", "MEDIUM").as_dict(),
            related_finding_ids=[],
        ))

    # ── tests sin requisito ────────────────────────────────────────────
    for t in gq.tests_without_requirement(g):
        rec = lut.get(t.node_id)
        if not _anchorable(rec):
            continue
        subtype = "TEST_WITHOUT_REQUIREMENT"
        prov = FindingProvenance(document_id=rec["document_id"],
                                 extraction_version=extraction_version, run_id=run_id,
                                 agent_id="test_coverage_agent")
        findings.append(build_finding(
            "TestCoverageFinding", subtype, severity="MINOR",
            document=rec["document_id"], page=rec["pagina"],
            source_text=rec["source_text"], section=rec.get("section_id"),
            rationale=("Test sin arista `verifies` ni `tested_by` entrante en el grafo: "
                       "no traza a ningún requisito ni elemento de diseño. BORRADOR ASISTIDO."),
            confidence="MEDIUM", machine_state="MACHINE_DEVIATION_CANDIDATE",
            provenance=prov, risk=compute_risk(subtype, "MINOR", "LOW").as_dict(),
        ))

    # ── claims de documento fuente sin trazabilidad hacia abajo ────────
    for n in g.nodes(kind="claim"):
        if n.document_id not in src_docs:
            continue
        if n.attrs.get("tipo") not in ("control", "function"):
            continue
        if g.edges(src_id=n.node_id, rel="implemented_by") or g.edges(src_id=n.node_id, rel="tested_by"):
            continue
        rec = lut.get(n.node_id)
        if not _anchorable(rec):
            continue
        subtype = "REQUIREMENT_NOT_TRACED"
        prov = FindingProvenance(document_id=rec["document_id"],
                                 extraction_version=extraction_version, run_id=run_id,
                                 agent_id="requirements_traceability_agent")
        findings.append(build_finding(
            "TraceabilityFinding", subtype, severity="MAJOR",
            document=rec["document_id"], page=rec["pagina"],
            source_text=rec["source_text"], section=rec.get("section_id"),
            rationale=("Claim de documento fuente sin arista `implemented_by` ni `tested_by` "
                       "saliente en el grafo: no se pudo trazar a diseño ni a prueba. "
                       "BORRADOR ASISTIDO -- puede ser un hueco real o un límite de la "
                       "extracción; revisión humana requerida."),
            confidence="LOW", machine_state="MACHINE_INCONCLUSIVE",
            provenance=prov, risk=compute_risk(subtype, "MAJOR", "MEDIUM").as_dict(),
        ))

    g.close()
    return findings


def _source_document_ids(g: GraphStore) -> set:
    return {n.document_id for n in g.nodes(kind="document")
            if (n.attrs or {}).get("tipo") in _SOURCE_DOC_TYPES}
