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
      -> TraceabilityFinding: REQUIREMENT_NOT_TRACED, CON filtro de confianza:
         solo se emite si el claim parece un requisito real (no encabezado
         ni texto de alcance) Y lleva un identificador de referencia (UR#,
         F#, ...) -- así el linkeo determinista tuvo un asa. Si el id
         aparece aguas abajo pero sin arista -> confianza LOW
         (MACHINE_INCONCLUSIVE); si no aparece en ningún doc de
         impl/diseño/prueba -> confianza MEDIUM (MACHINE_DEVIATION_CANDIDATE).
         Claims sin id se SUPRIMEN (límite de extracción, no hueco).

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
from factory.regulatory.graph.build import extract_refs
from factory.regulatory.graph.store import GraphStore

_SOURCE_DOC_TYPES = ("URS",)   # documentos "fuente" de trazabilidad
_DOWNSTREAM_DOC_TYPES = ("FS", "DS", "SAT", "OQ", "IQ", "PQ")

# Filtro de confianza para REQUIREMENT_NOT_TRACED: un claim de la URS
# demasiado corto o que arranca con lenguaje de encabezado/alcance no es
# un requisito trazable -- es ruido de extracción heurística (B1).
_MIN_TRACE_CLAIM_CHARS = 40
_BOILERPLATE_PREFIXES = (
    "scope", "purpose", "introduction", "overview", "note", "this document",
    "alcance", "propósito", "proposito", "introducción", "introduccion",
    "este documento", "general", "background", "abbreviation", "definition",
)


def _claim_lookup(canon_dir, document_ids) -> dict:
    """{claim_id: {source_text, pagina, section_id, refs}} y {test_id: {...}}."""
    out: dict = {}
    for did in document_ids:
        try:
            with CanonicalStore(did, store_dir=canon_dir) as s:
                for c in s.all("claim"):
                    st = c.get("source_text", "")
                    out[c["claim_id"]] = {"source_text": st,
                                          "pagina": c.get("pagina"),
                                          "section_id": c.get("section_id"),
                                          "document_id": did,
                                          "refs": extract_refs(st)}
                for t in s.all("test"):
                    d = t.get("descripcion", "")
                    out[t["test_id"]] = {"source_text": d,
                                         "pagina": (t.get("provenance") or {}).get("page"),
                                         "section_id": t.get("section_id"),
                                         "document_id": did,
                                         "refs": extract_refs(d)}
        except Exception:  # noqa: BLE001 -- un store ausente no aborta el resto
            continue
    return out


def _looks_like_requirement(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < _MIN_TRACE_CLAIM_CHARS:
        return False
    low = t.lower()
    if any(low.startswith(p) for p in _BOILERPLATE_PREFIXES):
        return False
    return True


def _anchorable(rec) -> bool:
    return bool((rec or {}).get("source_text", "").strip()) and isinstance((rec or {}).get("pagina"), int) and rec["pagina"] >= 1


def graph_functional_findings(project_id: str, document_ids: list[str], *,
                              extraction_version: str, run_id: str | None = None,
                              canon_dir=CANON_DIR, graph_dir=None,
                              confidence_filter: bool = True,
                              stats: dict | None = None) -> list:
    """`confidence_filter` (default True): aplica el filtro de confianza a
    REQUIREMENT_NOT_TRACED -- solo emite cuando el claim de la URS parece
    un requisito real Y lleva un identificador de referencia (así el
    linkeo determinista tuvo un asa para encontrarlo). Claims sin id de
    referencia se SUPRIMEN (son límite de extracción, no hueco); claims
    cuyo id SÍ aparece aguas abajo pero sin arista se degradan a
    confianza baja. `stats` (opcional) recibe los conteos."""
    from factory.regulatory.graph.store import STORE_DIR as GRAPH_DIR
    g = GraphStore(project_id, store_dir=graph_dir or GRAPH_DIR)
    lut = _claim_lookup(canon_dir, document_ids)
    src_docs = _source_document_ids(g)
    downstream_refs = _downstream_ref_union(g, lut)
    _stats = {"untraced_emitted_high": 0, "untraced_emitted_low": 0,
              "untraced_suppressed_no_ref": 0, "untraced_suppressed_boilerplate": 0}
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
    subtype = "REQUIREMENT_NOT_TRACED"
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

        # ── filtro de confianza ──────────────────────────────────────
        own_refs = rec.get("refs") or set()
        if confidence_filter:
            if not _looks_like_requirement(rec["source_text"]):
                _stats["untraced_suppressed_boilerplate"] += 1
                continue
            if not own_refs:
                # el linkeo determinista nunca tuvo un asa: límite de
                # extracción, no un hueco de trazabilidad. No se emite.
                _stats["untraced_suppressed_no_ref"] += 1
                continue
            ref_seen_downstream = bool(own_refs & downstream_refs)
        else:
            ref_seen_downstream = bool(own_refs & downstream_refs)

        if ref_seen_downstream:
            _stats["untraced_emitted_low"] += 1
            confidence, machine_state, severity = "LOW", "MACHINE_INCONCLUSIVE", "MINOR"
            extra = ("El identificador de este requisito SÍ aparece en un documento aguas "
                     "abajo, pero sin arista de trazabilidad -- probable límite de "
                     "extracción; verificar el enlace real.")
        else:
            _stats["untraced_emitted_high"] += 1
            confidence, machine_state, severity = "MEDIUM", "MACHINE_DEVIATION_CANDIDATE", "MAJOR"
            extra = ("El identificador de este requisito NO aparece en ningún documento de "
                     "implementación/diseño/prueba -- candidato a hueco de trazabilidad real.")

        prov = FindingProvenance(document_id=rec["document_id"],
                                 extraction_version=extraction_version, run_id=run_id,
                                 agent_id="requirements_traceability_agent")
        findings.append(build_finding(
            "TraceabilityFinding", subtype, severity=severity,
            document=rec["document_id"], page=rec["pagina"],
            source_text=rec["source_text"], section=rec.get("section_id"),
            rationale=(f"Claim de documento fuente sin arista `implemented_by` ni `tested_by`. "
                       f"{extra} refs del claim: {sorted(own_refs)}. BORRADOR ASISTIDO -- "
                       f"revisión humana requerida."),
            confidence=confidence, machine_state=machine_state,
            provenance=prov, risk=compute_risk(subtype, severity, "MEDIUM").as_dict(),
        ))

    # ── requisito de doc fuente implementado pero SIN prueba ───────────
    for n in g.nodes(kind="claim"):
        if n.document_id not in src_docs:
            continue
        if n.attrs.get("tipo") not in ("control", "function"):
            continue
        if not g.edges(src_id=n.node_id, rel="implemented_by"):
            continue  # sin implementación -> ya cubierto por REQUIREMENT_NOT_TRACED
        rec = lut.get(n.node_id)
        if not _anchorable(rec):
            continue
        if confidence_filter and (not _looks_like_requirement(rec["source_text"])
                                  or not (rec.get("refs") or set())):
            continue
        if _reaches_test(g, n.node_id):
            continue
        subtype = "REQUIREMENT_NOT_TESTED"
        prov = FindingProvenance(document_id=rec["document_id"],
                                 extraction_version=extraction_version, run_id=run_id,
                                 agent_id="test_coverage_agent")
        findings.append(build_finding(
            "TestCoverageFinding", subtype, severity="MAJOR",
            document=rec["document_id"], page=rec["pagina"],
            source_text=rec["source_text"], section=rec.get("section_id"),
            rationale=("Requisito de documento fuente con implementación aguas abajo pero "
                       "SIN ningún `test` transitivo en el grafo. BORRADOR ASISTIDO -- "
                       "revisión humana requerida."),
            confidence="MEDIUM", machine_state="MACHINE_DEVIATION_CANDIDATE",
            provenance=prov, risk=compute_risk(subtype, "MAJOR", "MEDIUM").as_dict(),
        ))

    # ── claim de doc de implementación/diseño SIN requisito aguas arriba ─
    all_source_refs: set = set()
    for sd in src_docs:
        for cn in g.nodes(kind="claim", document_id=sd):
            all_source_refs |= extract_refs(lut.get(cn.node_id, {}).get("source_text", ""))
            if lut.get(cn.node_id, {}).get("refs"):
                all_source_refs |= lut[cn.node_id]["refs"]
    for n in g.nodes(kind="claim"):
        doc_type = _doc_type_of(g, n.document_id)
        if doc_type not in _DOWNSTREAM_DOC_TYPES:
            continue
        if n.attrs.get("tipo") not in ("control", "function"):
            continue
        if g.edges(dst_id=n.node_id, rel="implemented_by") or g.edges(dst_id=n.node_id, rel="designed_by"):
            continue  # tiene requisito/diseño aguas arriba
        rec = lut.get(n.node_id)
        if not _anchorable(rec):
            continue
        # si el claim cita un identificador de requisito que existe en un
        # documento fuente, está atado a ese requisito aunque falte la
        # arista -- no es "sin requisito", es un límite de extracción.
        if (rec.get("refs") or set()) & all_source_refs:
            continue
        if confidence_filter and (not _looks_like_requirement(rec["source_text"])
                                  or not (rec.get("refs") or set())):
            continue
        subtype = "IMPLEMENTATION_WITHOUT_REQUIREMENT"
        prov = FindingProvenance(document_id=rec["document_id"],
                                 extraction_version=extraction_version, run_id=run_id,
                                 agent_id="cross_document_agent")
        findings.append(build_finding(
            "FunctionalFinding", subtype, severity="MINOR",
            document=rec["document_id"], page=rec["pagina"],
            source_text=rec["source_text"], section=rec.get("section_id"),
            rationale=("Claim de un documento de implementación/diseño sin arista "
                       "`implemented_by`/`designed_by` entrante: no traza a ningún requisito "
                       "aguas arriba. BORRADOR ASISTIDO -- revisión humana requerida."),
            confidence="LOW", machine_state="MACHINE_INCONCLUSIVE",
            provenance=prov, risk=compute_risk(subtype, "MINOR", "LOW").as_dict(),
        ))

    if stats is not None:
        stats.update(_stats)
    g.close()
    return findings


def _doc_type_of(g: GraphStore, document_id: str) -> str | None:
    for dn in g.nodes(kind="document"):
        if dn.document_id == document_id:
            return (dn.attrs or {}).get("tipo")
    return None


def _reaches_test(g: GraphStore, node_id: str, *, max_depth: int = 8) -> bool:
    """¿Se alcanza algún nodo `test` desde `node_id` siguiendo
    implemented_by/designed_by/tested_by hacia abajo?"""
    from collections import deque
    seen = {node_id}
    dq = deque([(node_id, 0)])
    rels = ("implemented_by", "designed_by", "tested_by")
    while dq:
        nid, depth = dq.popleft()
        if depth >= max_depth:
            continue
        for rel in rels:
            for e in g.edges(src_id=nid, rel=rel):
                dst = g.get_node(e.dst_id)
                if dst is None:
                    continue
                if dst.kind == "test":
                    return True
                if dst.node_id not in seen:
                    seen.add(dst.node_id)
                    dq.append((dst.node_id, depth + 1))
    return False


def _downstream_ref_union(g: GraphStore, lut: dict) -> set:
    """Unión de todos los identificadores de referencia (UR#, F#, SAT-#,
    …) que aparecen en claims/tests de documentos de
    implementación/diseño/prueba."""
    downstream_docs = {n.document_id for n in g.nodes(kind="document")
                       if (n.attrs or {}).get("tipo") in _DOWNSTREAM_DOC_TYPES}
    refs: set = set()
    for rec in lut.values():
        if rec.get("document_id") in downstream_docs:
            refs |= (rec.get("refs") or set())
    return refs


def _source_document_ids(g: GraphStore) -> set:
    return {n.document_id for n in g.nodes(kind="document")
            if (n.attrs or {}).get("tipo") in _SOURCE_DOC_TYPES}
