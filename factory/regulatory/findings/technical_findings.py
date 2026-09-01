"""Findings TÉCNICOS deterministas (V2, B6b v1 + v2) -- FASE 5.2.

DETERMINISTA, sin LLM. La capa HYBRID NO está activada; no se usa el 7B.

B6b v1 -- desde el evidence graph (B2):
  - `INTERFACE_INCONSISTENCY` (TechnicalFinding): un mismo identificador
    de referencia citado en claims de >= 2 documentos donde el predicado
    es modal-opuesto (`shall` vs `shall not`) o donde diverge un valor de
    parámetro numérico adyacente. Anclado al `source_text` literal.
  - `ORPHAN_DESIGN_ELEMENT` (TraceabilityFinding): claim de un documento
    de diseño (DS/FS) con identificador propio, sin `tested_by` saliente
    y sin `implemented_by`/`designed_by` entrante.

B6b v2 -- reglas de COMPLETITUD del artefacto GOBERNADO FIRMADO
`requirement_catalog/technical_completeness_rules.yaml` (`completeness_findings`):
  patrón "tema obligatorio presente + comportamiento requerido ausente en
  el documento", con el comportamiento tomado SOLO de una fuente normativa
  explícita. Reglas C01/C03/C04/C05/C08/C09/C10. Ninguna implementación
  concreta (NTP, RTO/RPO, hash/HMAC/SHA, firma digital, matriz formal,
  controles físicos, memoria retentiva) es requisito -- son ejemplos. Cada
  finding nace `human_state=UNREVIEWED` y va a revisión humana con
  cobertura declarada; nunca auto-confirma. Fail-closed: si el artefacto
  no está `status: SIGNED`, `completeness_findings` no emite nada.

Reutiliza el modelo canónico (B1), el evidence graph (B2) y los helpers
de `functional_findings` (B6a). Sin efectos de red, sin egress.
"""
from __future__ import annotations

import re

from factory.regulatory.canonical.persistence import STORE_DIR as CANON_DIR
from factory.regulatory.findings.functional_findings import (
    _anchorable, _claim_lookup, _doc_type_of, _looks_like_requirement,
)
from factory.regulatory.findings.risk import compute_risk
from factory.regulatory.findings.taxonomy import FindingProvenance, build_finding
from factory.regulatory.graph.build import _CONTRA_STOP, _MODAL_NEG, _MODAL_POS, _predicate_overlap
from factory.regulatory.graph.store import GraphStore

_DESIGN_DOC_TYPES = ("DS", "FS")

# valores de parámetro con unidad -- divergencia numérica entre dos claims
# que comparten identificador = inconsistencia de interfaz candidata.
_PARAM_VALUE_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s?(?:ms|msec|s|sec|secs|seconds?|min|mins|minutes?|hours?|hrs?|"
    r"hz|khz|vdc|vac|vrms|v|ma|a|%|bar|psi|kpa|mbar|db|mm|cm|m|baud|bps|kbps)\b",
    re.IGNORECASE,
)


def _param_values(text: str) -> set[str]:
    return {m.group(0).lower().replace(" ", "") for m in _PARAM_VALUE_RE.finditer(text or "")}


def _interface_divergence(a: str, b: str, ref: str) -> tuple[str, str] | None:
    """Devuelve (tipo, detalle) si `a` y `b` (dos claims que comparten
    `ref`) son inconsistentes de forma DETERMINISTA; None si no."""
    a = a or ""
    b = b or ""
    # 1. modal opuesto sobre el mismo predicado
    a_neg, b_neg = bool(_MODAL_NEG.search(a)), bool(_MODAL_NEG.search(b))
    a_pos, b_pos = bool(_MODAL_POS.search(a)), bool(_MODAL_POS.search(b))
    modal_opposite = (a_neg and b_pos and not b_neg) or (b_neg and a_pos and not a_neg)
    if modal_opposite and _predicate_overlap(a, b, ref) >= 0.55:
        return ("modal_opposite", "un documento lo prohíbe y el otro lo exige sobre el mismo predicado")
    # 2. divergencia de valor de parámetro con contexto compartido
    va, vb = _param_values(a), _param_values(b)
    if va and vb and va != vb and _predicate_overlap(a, b, ref) >= 0.30:
        return ("parameter_value", f"valores divergentes {sorted(va)} vs {sorted(vb)}")
    return None


def _shared_context_ok(a: str, b: str, ref: str) -> bool:
    """Evita emparejar dos menciones triviales del mismo id: exige algo de
    solapamiento de vocabulario de contenido más allá del propio id."""
    def toks(t: str) -> set[str]:
        return {w for w in re.findall(r"[a-záéíóúñ]{3,}", (t or "").lower())
                if w not in _CONTRA_STOP}
    return len(toks(a) & toks(b)) >= 2


_AGENT_BY_CLASS = {
    "TechnicalFinding": "technical_design_agent",
    "SecurityFinding": "security_architecture_agent",
    "DataIntegrityFinding": "data_integrity_agent",
    "TestCoverageFinding": "test_coverage_agent",
    "TraceabilityFinding": "requirements_traceability_agent",
}


def _text_has_all(text_lower: str, group) -> bool:
    return all(s in text_lower for s in group)


def _family_present(doc_text_lower: str, family_name: str, family_signals: dict) -> bool:
    for group in family_signals.get(family_name, []):
        if _text_has_all(doc_text_lower, group):
            return True
    return False


def _incidental_anchor(text: str, rule_tokens: list[str], guard: dict | None) -> bool:
    """v1.2 (D5-D remediation 3C): un `topic_anchor` de UN SOLO token debil
    (p.ej. "role") NO ancla la regla si TODAS sus ocurrencias caen tras un
    conector de subordinacion/exclusion Y la clausula principal contiene un
    ancla FUERTE de OTRA familia gobernada (p.ej. "audit trail ... by any role").
    Determinista. Nunca depende de un solo substring aislado."""
    if not guard:
        return False
    low = (text or "").lower()
    weak = [t for t in rule_tokens if t in set(guard.get("weak_single_tokens", []))]
    present_weak = [t for t in weak if t in low]
    if not present_weak:
        return False
    conns = guard.get("subordinating_connectives", [])
    cuts = [low.find(c) for c in conns if c in low]
    if not cuts:
        return False
    head = low[: min(cuts)]
    if any(t in head for t in present_weak):
        return False            # el token debil tambien esta en la clausula principal
    return any(s in head for s in guard.get("strong_foreign_anchors", []))


_XREF_SECTION_RE = re.compile(r"\b(?:see|refer to|per)\s+section\s+([0-9]+(?:\.[0-9]+)*)", re.I)
# fila de indice / tabla de trazabilidad del FS ("...-F12.00, 45" al final)
_TRACE_INDEX_RE = re.compile(r"-\s*F\d{1,2}\.\d{2}\s*,\s*\d{1,3}\s*$")


def _load_sections(canon_dir, document_ids) -> dict:
    """{document_id: {section_id: numero}}  y  {document_id: {numero: section_id}}."""
    from factory.regulatory.canonical.persistence import CanonicalStore
    by_id: dict = {}
    for did in document_ids:
        try:
            with CanonicalStore(did, store_dir=canon_dir) as s:
                m = {sec["section_id"]: str(sec.get("numero") or "")
                     for sec in s.all("section") if sec.get("section_id")}
                by_id[did] = m
        except Exception:  # noqa: BLE001
            by_id[did] = {}
    return by_id


def _scope_claims(anchor_rec, recs_by_page, sec_num_by_id, policy) -> list[dict]:
    """Selecciona los claims que forman el ALCANCE de evaluacion del
    comportamiento requerido, segun `scope_policy`. NUNCA document-wide."""
    if not policy or policy.get("behavior_search") != "context_scoped":
        return recs_by_page                       # v1.0: document-wide
    win = int((policy.get("fallback_when_section_unresolved") or {}).get("window_claims", 6))
    max_scope = int(policy.get("max_scope_claims", 60))

    anchor_sid = anchor_rec.get("section_id")
    anchor_num = sec_num_by_id.get(anchor_sid) if anchor_sid else None

    def window() -> list[dict]:
        i = recs_by_page.index(anchor_rec)
        return recs_by_page[max(0, i - win): i + win + 1]

    if not anchor_num:
        return window()                           # Section no resuelta -> ventana acotada

    # familia de numeros: misma seccion, hijas (prefijo), padre inmediato
    related = {anchor_num}
    parent = anchor_num.rsplit(".", 1)[0] if "." in anchor_num else None
    if parent:
        related.add(parent)
    for num in sec_num_by_id.values():
        if num == anchor_num or num.startswith(anchor_num + "."):
            related.add(num)
    # referencia cruzada explicita en el claim ancla ("see section N")
    for mnum in _XREF_SECTION_RE.findall(anchor_rec.get("source_text") or ""):
        related.add(mnum)

    scope = [r for r in recs_by_page
             if sec_num_by_id.get(r.get("section_id")) in related]
    if not scope:
        return window()
    if len(scope) > max_scope:                     # Section demasiado gruesa -> ventana DENTRO del alcance
        sc_set = {id(r) for r in scope}
        i = recs_by_page.index(anchor_rec)
        w = recs_by_page[max(0, i - win): i + win + 1]
        return [r for r in w if id(r) in sc_set] or scope[:max_scope]
    return scope


def completeness_findings(document_ids: list[str], *, extraction_version: str,
                          run_id: str | None = None, canon_dir=CANON_DIR,
                          stats: dict | None = None, rules_artifact: dict | None = None) -> list:
    """B6b v2 -- reglas de COMPLETITUD deterministas desde el artefacto
    GOBERNADO `technical_completeness_rules.yaml`. Patron: "tema obligatorio
    presente + comportamiento requerido ausente EN EL CONTEXTO del tema".
    CERO LLM. Fail-closed: si el artefacto no esta SIGNED, no emite nada.

    `rules_artifact` (opcional): dict ya cargado por el loader -- lo usan los
    tests que verifican el alcance context-scoped del borrador v1.1. En
    produccion se usa el artefacto VIVO firmado.

    Alcance de la evaluacion del comportamiento: `scope_policy` del artefacto.
    None (v1.0) -> document-wide. `context_scoped` (v1.1) -> Section del claim
    ancla + subsecciones relacionadas + referencia cruzada explicita, con
    ventana acotada de fallback. NUNCA una frase no relacionada en otra parte
    del documento suprime un gap.

    Cada finding nace `human_state=UNREVIEWED` y va a revision humana con
    cobertura declarada. NUNCA auto-confirma."""
    from factory.regulatory.requirement_catalog import technical_completeness_loader as tcl

    _stats = {"completeness_rules_evaluated": 0, "completeness_emitted": 0,
              "completeness_suppressed_family_present": 0,
              "completeness_suppressed_xref": 0, "completeness_downgraded": 0,
              "completeness_artifact_signed": True, "completeness_scope": "document_wide"}
    findings: list = []
    if rules_artifact is not None:
        art = rules_artifact
    else:
        try:
            art = tcl.load_signed_rules()
        except tcl.TechnicalRulesNotSignedError:
            _stats["completeness_artifact_signed"] = False
            if stats is not None:
                stats.update(_stats)
            return findings

    policy = art.get("scope_policy")
    if policy and policy.get("behavior_search") == "context_scoped":
        _stats["completeness_scope"] = "context_scoped"

    lut = _claim_lookup(canon_dir, document_ids)
    by_doc: dict[str, list[dict]] = {}
    for rec in lut.values():
        by_doc.setdefault(rec.get("document_id"), []).append(rec)
    sections = _load_sections(canon_dir, document_ids)

    xref = art["cross_reference_suppressors"]
    downg = art["inconclusive_downgraders"]
    fam_sig = art["family_signals"]
    guard = art.get("incidental_anchor_guard")            # v1.2 (D5-D remediation 3C); None -> desactivado
    c01_doc_finding: dict[str, str] = {}

    for rule in art["rules"]:
        case_id = rule["CASE_ID"]
        ddr = rule["DETERMINISTIC_DETECTION_RULE"]
        topics = [t.lower() for t in ddr["topic_anchor"]]
        # v1.2 (D5-D remediation 1A/1B): tier de patron compuesto ADEMAS del anchor literal.
        patterns = [re.compile(p, re.IGNORECASE) for p in (ddr.get("topic_anchor_patterns") or [])]
        weak_tokens = set((guard or {}).get("weak_single_tokens", []))
        # v1.2 (D5-D remediation 3B): supresores de familia adicionales, declarativos por regla.
        extra_supp = list(ddr.get("additional_suppressor_families") or [])
        if case_id == "C09" and "audit_trail_privileged_protection" not in extra_supp:
            extra_supp.append("audit_trail_privileged_protection")   # compat v1.0/v1.1 (era caso especial)
        fam_name = (rule["ACCEPTABLE_EVIDENCE_PATTERNS"] or {}).get("family")
        fclass = ddr["finding"]["finding_class"]
        subtype = ddr["finding"]["subtype"]
        severity = ddr["finding"]["severity"]
        default_ms = rule["HUMAN_REVIEW_STATE"]["machine_state"]

        def _anchors_here(r) -> bool:
            txt = r["source_text"] or ""
            low = txt.lower()
            lit_hits = [t for t in topics if t in low]
            pat_hit = any(p.search(txt) for p in patterns)
            if not lit_hits and not pat_hit:
                return False
            strong_lit = [t for t in lit_hits if t not in weak_tokens]
            if strong_lit or pat_hit:
                return True
            # solo anclo por token(s) debil(es) -> descartar si es incidental
            return not _incidental_anchor(txt, topics, guard)

        for d in document_ids:
            recs = by_doc.get(d) or []
            if not recs:
                continue
            _stats["completeness_rules_evaluated"] += 1
            # ancla determinista: la PRIMERA mencion del tema por numero de pagina
            recs_by_page = sorted(recs, key=lambda r: (r.get("pagina") or 0))
            anchor_rec = next((r for r in recs_by_page if _anchorable(r) and _anchors_here(r)), None)
            if anchor_rec is None:
                continue
            anchor_low = (anchor_rec["source_text"] or "").lower()
            if any(x in anchor_low for x in xref):
                _stats["completeness_suppressed_xref"] += 1
                continue
            # ALCANCE context-scoped (o document-wide en v1.0)
            scope_recs = _scope_claims(anchor_rec, recs_by_page, sections.get(d, {}), policy)
            scope_text = "\n".join((r.get("source_text") or "") for r in scope_recs).lower()
            if fam_name and _family_present(scope_text, fam_name, fam_sig):
                _stats["completeness_suppressed_family_present"] += 1
                continue
            if any(_family_present(scope_text, fn, fam_sig) for fn in extra_supp):
                _stats["completeness_suppressed_family_present"] += 1
                continue
            machine_state = default_ms
            if default_ms == "MACHINE_DEVIATION_CANDIDATE" and any(x in scope_text for x in downg):
                machine_state = "MACHINE_INCONCLUSIVE"
                _stats["completeness_downgraded"] += 1
            confidence = "MEDIUM" if machine_state == "MACHINE_DEVIATION_CANDIDATE" else "LOW"
            related = [c01_doc_finding[d]] if (case_id == "C09" and d in c01_doc_finding) else []
            prov = FindingProvenance(
                document_id=d, extraction_version=extraction_version, run_id=run_id,
                agent_id=_AGENT_BY_CLASS.get(fclass, "technical_design_agent"),
                subcriterion_ref=rule["SOURCE_REQUIREMENT_ID"])
            f = build_finding(
                fclass, subtype, severity=severity,
                document=d, page=anchor_rec["pagina"],
                source_text=anchor_rec["source_text"], section=anchor_rec.get("section_id"),
                rationale=(f"[{case_id}] {' '.join(str(rule['CONTROL_OBJECTIVE']).split())} "
                           f"Fuente: {rule['SOURCE_REQUIREMENT_ID']}. El documento describe el tema "
                           f"pero NO se encontro el comportamiento requerido: "
                           f"{' '.join(str(rule['REQUIRED_BEHAVIOR']).split())[:220]} "
                           f"Regla determinista de completitud (artefacto gobernado "
                           f"v{art['version']}). BORRADOR ASISTIDO -- revision humana requerida."),
                confidence=confidence, machine_state=machine_state,
                provenance=prov, technical_basis=str(rule["SOURCE_REQUIREMENT_ID"]),
                risk=compute_risk(subtype, severity, "MEDIUM").as_dict(),
                related_finding_ids=related,
            )
            findings.append(f)
            _stats["completeness_emitted"] += 1
            if case_id == "C01":
                c01_doc_finding[d] = f.finding_id

    if stats is not None:
        stats.update(_stats)
    return findings


def graph_technical_findings(project_id: str, document_ids: list[str], *,
                             extraction_version: str, run_id: str | None = None,
                             canon_dir=CANON_DIR, graph_dir=None,
                             include_completeness: bool = True,
                             stats: dict | None = None) -> list:
    """DETERMINISTA (0 LLM). Emite:
      - `INTERFACE_INCONSISTENCY` y `ORPHAN_DESIGN_ELEMENT` desde el grafo (B6b v1)
      - reglas de completitud tecnica del artefacto gobernado firmado (B6b v2,
        `include_completeness=True`, fail-closed si el artefacto no esta SIGNED)
    `stats` (opcional) recibe conteos."""
    from factory.regulatory.graph.store import STORE_DIR as GRAPH_DIR
    g = GraphStore(project_id, store_dir=graph_dir or GRAPH_DIR)
    lut = _claim_lookup(canon_dir, document_ids)
    _stats = {"interface_pairs_examined": 0, "interface_inconsistency": 0,
              "orphan_design_element": 0}
    findings: list = []

    # ── INTERFACE_INCONSISTENCY ───────────────────────────────────────
    by_ref: dict[str, list[tuple[str, dict]]] = {}
    for cid, rec in lut.items():
        for ref in (rec.get("refs") or set()):
            by_ref.setdefault(ref, []).append((cid, rec))

    seen_pairs: set[tuple[str, str]] = set()
    for ref, items in sorted(by_ref.items()):
        if len({r["document_id"] for _, r in items}) < 2:
            continue
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                ci, ri = items[i]
                cj, rj = items[j]
                if ri["document_id"] == rj["document_id"]:
                    continue
                if not (_anchorable(ri) and _anchorable(rj)):
                    continue
                ti, tj = ri["source_text"], rj["source_text"]
                if not _shared_context_ok(ti, tj, ref):
                    continue
                _stats["interface_pairs_examined"] += 1
                div = _interface_divergence(ti, tj, ref)
                if div is None:
                    continue
                key = tuple(sorted([ci, cj]))
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                _stats["interface_inconsistency"] += 1
                kind, detail = div
                subtype = "INTERFACE_INCONSISTENCY"
                prov = FindingProvenance(
                    document_id=ri["document_id"], extraction_version=extraction_version,
                    run_id=run_id, agent_id="technical_design_agent",
                    graph_path=[ci, "refers_to", cj])
                findings.append(build_finding(
                    "TechnicalFinding", subtype, severity="MAJOR",
                    document=ri["document_id"], page=ri["pagina"],
                    source_text=ti, section=ri.get("section_id"),
                    rationale=(f"El identificador '{ref}' aparece en {ri['document_id']} y en "
                               f"{rj['document_id']} con inconsistencia determinista "
                               f"({kind}: {detail}). Otro lado: "
                               f"'{tj[:140]}'. BORRADOR ASISTIDO -- revisión humana requerida."),
                    confidence="LOW", machine_state="MACHINE_DEVIATION_CANDIDATE",
                    provenance=prov, technical_basis=f"cross-document identifier {ref}",
                    risk=compute_risk(subtype, "MAJOR", "MEDIUM").as_dict(),
                    related_finding_ids=[],
                ))

    # ── ORPHAN_DESIGN_ELEMENT ─────────────────────────────────────────
    for n in g.nodes(kind="claim"):
        if _doc_type_of(g, n.document_id) not in _DESIGN_DOC_TYPES:
            continue
        if n.attrs.get("tipo") not in ("control", "function"):
            continue
        if g.edges(src_id=n.node_id, rel="tested_by"):
            continue
        if (g.edges(dst_id=n.node_id, rel="implemented_by")
                or g.edges(dst_id=n.node_id, rel="designed_by")):
            continue
        rec = lut.get(n.node_id)
        if not _anchorable(rec):
            continue
        if not _looks_like_requirement(rec["source_text"]):
            continue
        if not (rec.get("refs") or set()):
            continue
        # guarda de precision: fila de la tabla de trazabilidad / "List of
        # Functions" del FS (patron "...-F##.##, NN" al final) -- no es un
        # elemento de diseno huerfano, es un indice.
        if _TRACE_INDEX_RE.search(rec["source_text"] or ""):
            continue
        _stats["orphan_design_element"] += 1
        subtype = "ORPHAN_DESIGN_ELEMENT"
        prov = FindingProvenance(
            document_id=rec["document_id"], extraction_version=extraction_version,
            run_id=run_id, agent_id="requirements_traceability_agent")
        findings.append(build_finding(
            "TraceabilityFinding", subtype, severity="MINOR",
            document=rec["document_id"], page=rec["pagina"],
            source_text=rec["source_text"], section=rec.get("section_id"),
            rationale=("Elemento de diseño con identificador propio, sin arista `tested_by` "
                       "saliente y sin requisito/diseño aguas arriba: nadie lo pidió y nadie "
                       f"lo prueba. refs: {sorted(rec.get('refs') or set())}. "
                       "BORRADOR ASISTIDO -- revisión humana requerida."),
            confidence="LOW", machine_state="MACHINE_INCONCLUSIVE",
            provenance=prov, risk=compute_risk(subtype, "MINOR", "LOW").as_dict(),
        ))

    g.close()

    # ── B6b v2: reglas de completitud del artefacto gobernado firmado ──
    if include_completeness:
        findings.extend(completeness_findings(
            document_ids, extraction_version=extraction_version, run_id=run_id,
            canon_dir=canon_dir, stats=_stats))

    if stats is not None:
        stats.update(_stats)
    return findings
