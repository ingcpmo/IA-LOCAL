"""Poblado DETERMINISTA del grafo desde el canonical_store + el catálogo
de requisitos (V2, B2).

docs_plan/PLAN_IMPLEMENTACION_ANALIZADOR_GMP_LOCAL_V2.md B2.

Qué puebla (sin LLM, sin embeddings, sin red):
  - nodos: todos los objetos del canonical_store de cada documento del
    proyecto + un nodo `requirement` por requisito del catálogo + un nodo
    `regulation` por `source_id`.
  - `requirement --regulated_by--> regulation`  (del catálogo).
  - `requirement|claim|section --implemented_by/designed_by--> claim|section`
    y `--tested_by--> test`, por COINCIDENCIA DE IDENTIFICADORES/REFERENCIAS
    literales entre documentos (UR3.3.1, F12.00, SAT-039, req ids...).
  - `claim --refers_to--> system_component|actor`, por mención literal del
    nombre/rol.
  - `test --verifies--> requirement`, cuando el texto del test cita el req id
    o un identificador de requisito trazable a él.

Qué NO puebla aquí (deuda declarada, etapas posteriores):
  - aristas por SIMILITUD SEMÁNTICA de embeddings (B3+, gobernado por
    EMBED_EXECUTION).
  - `contradicts`: solo una heurística MUY conservadora (mismo identificador
    de referencia + modal opuesto shall / shall not). El grafo SOPORTA la
    arista para que B6/agentes FUNCTIONAL la añadan con más señal.
  - `supports`: lo añade el Adjudicator (B4/B6) cuando una Evidence ancla.
"""
from __future__ import annotations

import re

from factory.regulatory.canonical.persistence import STORE_DIR as CANON_DIR, CanonicalStore
from factory.regulatory.graph.store import STORE_DIR as GRAPH_DIR, GraphStore

# Identificadores de requisito de usuario / función / test que aparecen
# literalmente citados entre documentos.
_REF_PATTERNS = [
    re.compile(r"\bUR[S]?[\s\-]?\d+(?:\.\d+){0,3}[a-z]?\b", re.IGNORECASE),   # UR3.3.1, URS-3.3
    re.compile(r"\bF\d{1,2}\.\d{2}\b"),                                       # F12.00
    re.compile(r"\b(?:SAT|OQ|IQ|PQ)[\s\-]?\d{1,4}[a-z]?\b", re.IGNORECASE),   # SAT-039
    re.compile(r"\b\d{1,2}\s*CFR\s*\d{2,3}\.\d{1,3}\([a-z]\)", re.IGNORECASE),# 21 CFR 11.10(e)
    re.compile(r"\bANNEX\s*11[_\s\-]?\d{1,2}\b", re.IGNORECASE),
    re.compile(r"\bALCOA[_\s\-]?[A-Z]+\b", re.IGNORECASE),
    # B1.2 -- id formal de requisito: (URS-)PCS-SR-037, PCS-HR-021, MCCPDC-...
    re.compile(r"\b(?:URS[\s\-])?[A-Z]{2,6}[\s\-][A-Z]{2,5}[\s\-]\d{2,5}[a-z]?\b"),
]
# Número de sección jerárquico "desnudo" (3.3.1, 4.1.2.4). El URS de
# Rockwell numera sus requisitos así (sin prefijo "UR"), mientras que el
# FS los cita como "UR3.3.1" -> se normaliza el prefijo para que casen.
_BARE_SECTION_RE = re.compile(r"(?<![\w.])\d\.\d{1,2}(?:\.\d{1,3}){1,3}(?![\w])")

_MODAL_NEG = re.compile(r"\bshall not\b|\bmust not\b|\bno (?:debe|deberá)\b", re.IGNORECASE)
_MODAL_POS = re.compile(r"\bshall\b|\bmust\b|\bdebe\b|\bdeberá\b", re.IGNORECASE)

# Tipo de documento -> rol en la cadena de trazabilidad.
_CHAIN_ROLE = {"URS": "source", "FS": "impl", "DS": "design", "SAT": "test",
               "OQ": "test", "IQ": "test", "PQ": "test"}


def _norm_ref(ref: str) -> str:
    n = re.sub(r"[\s\-_]", "", ref).upper()
    # B1.2: id formal -- "URSPCSSR037" y "PCSSR037" identifican el mismo
    # requisito; se quita el prefijo URS para que colisionen.
    if n.startswith("URS") and re.match(r"^URS[A-Z]{4,}\d{2,}$", n):
        n = n[3:]
    return n


def _strip_ur_prefix(ref: str) -> str:
    """UR3.3.1 / URS3.3.1 -> 3.3.1 (para casar con la numeración de
    sección del URS, que no lleva prefijo)."""
    return re.sub(r"^UR[S]?", "", ref)


def extract_refs(text: str) -> set[str]:
    out: set[str] = set()
    for pat in _REF_PATTERNS:
        for m in pat.findall(text or ""):
            r = _norm_ref(m if isinstance(m, str) else m[0])
            out.add(r)
            stripped = _strip_ur_prefix(r)
            if stripped != r and re.match(r"^\d\.\d", stripped):
                out.add(stripped)          # "UR3.3.1" también aporta "3.3.1"
    for m in _BARE_SECTION_RE.findall(text or ""):
        out.add(_norm_ref(m))
    return out


def _ingest_canonical(g: GraphStore, canon: CanonicalStore, doc_type: str) -> dict:
    """Vuelca los objetos de un documento como nodos. Devuelve índices
    útiles para el linkeo posterior."""
    doc = canon.all("document")[0] if canon.all("document") else None
    document_id = canon.document_id
    if doc:
        g.add_node(document_id, "document", doc.get("titulo", document_id),
                   document_id=document_id, attrs={"tipo": doc.get("tipo"),
                                                   "sha256": doc.get("sha256")})

    idx = {"claims_by_ref": {}, "sections": [], "tests": [], "own_refs": set(),
           "doc_type": doc_type, "document_id": document_id, "claim_texts": {}}

    for s in canon.all("section"):
        g.add_node(s["section_id"], "section",
                   f'{s.get("numero") or "?"} {s.get("titulo") or ""}'.strip(),
                   document_id=document_id,
                   attrs={"numero": s.get("numero"), "pagina_inicio": s.get("pagina_inicio")})
        idx["sections"].append(s)

    for c in canon.all("claim"):
        g.add_node(c["claim_id"], "claim", c.get("normalized_statement", "")[:200],
                   document_id=document_id,
                   attrs={"tipo": c.get("tipo"), "pagina": c.get("pagina"),
                          "section_id": c.get("section_id")})
        refs = extract_refs(c.get("source_text", ""))
        # B1.2: el local_id (propio o heredado) del claim también es un
        # ancla de trazabilidad -- una continuación de línea de un
        # requisito de la URS no repite su número en el texto.
        if c.get("local_id"):
            refs |= {_norm_ref(c["local_id"])}
            stripped = _strip_ur_prefix(_norm_ref(c["local_id"]))
            if re.match(r"^\d\.\d", stripped):
                refs |= {stripped}
        for r in refs:
            idx["claims_by_ref"].setdefault(r, []).append(c["claim_id"])
        idx["own_refs"] |= refs
        idx["claim_texts"][c["claim_id"]] = c.get("source_text", "")

    for t in canon.all("test"):
        g.add_node(t["test_id"], "test", t.get("descripcion", "")[:200],
                   document_id=document_id,
                   attrs={"identificador": t.get("identificador"),
                          "resultado": t.get("resultado")})
        idx["tests"].append(t)

    for sc in canon.all("system_component"):
        g.add_node(sc["component_id"], "system_component", sc.get("nombre", ""),
                   document_id=document_id, attrs={"tipo": sc.get("tipo")})
    for a in canon.all("actor"):
        g.add_node(a["actor_id"], "actor", a.get("nombre_rol", ""),
                   document_id=document_id, attrs={"tipo": a.get("tipo")})

    return idx


def _ingest_requirements(g: GraphStore) -> dict:
    """Nodos requirement + regulation + arista regulated_by. Devuelve
    {normalized_ref -> requirement_id} para el linkeo."""
    from factory.regulatory.requirement_catalog.requirement_catalog_loader import load_requirements
    reqs = load_requirements()["requirements"]
    ref_to_req: dict[str, str] = {}
    for rid, entry in reqs.items():
        g.add_node(rid, "requirement", entry.get("label", rid),
                   attrs={"source_id": entry.get("source_id"),
                          "jurisdiction": entry.get("jurisdiction")})
        src = entry.get("source_id")
        if src:
            g.add_node(src, "regulation", src)
            g.add_edge(rid, src, "regulated_by")
        ref_to_req[_norm_ref(rid)] = rid
        # también por el patrón CFR/ANNEX embebido en el id
        for m in _REF_PATTERNS[3].findall(rid) + _REF_PATTERNS[4].findall(rid):
            ref_to_req[_norm_ref(m)] = rid
    return ref_to_req


def build_project_graph(project_id: str, documents: list[tuple[str, str]], *,
                        canon_dir=CANON_DIR, graph_dir=GRAPH_DIR) -> dict:
    """`documents`: lista de (document_id, doc_type). Cada uno debe tener
    ya su canonical_store poblado (B1: `extract_document`).

    Idempotente: re-ejecutar produce el mismo grafo (ids deterministas).
    """
    g = GraphStore(project_id, store_dir=graph_dir)
    ref_to_req = _ingest_requirements(g)

    indices: list[dict] = []
    for document_id, doc_type in documents:
        with CanonicalStore(document_id, store_dir=canon_dir) as canon:
            indices.append(_ingest_canonical(g, canon, doc_type))

    # ── linkeo cross-documento por referencia literal ────────────────────
    by_role: dict[str, list[dict]] = {}
    for idx in indices:
        by_role.setdefault(_CHAIN_ROLE.get(idx["doc_type"], "other"), []).append(idx)

    # requirement --implemented_by--> claim (cualquier claim que cite el req id)
    for idx in indices:
        for ref, claim_ids in idx["claims_by_ref"].items():
            rid = ref_to_req.get(ref)
            if not rid:
                continue
            for cid in claim_ids:
                _safe_edge(g, rid, cid, "implemented_by")

    # source(URS) --implemented_by--> impl(FS) ; impl(FS) --designed_by--> design(DS)
    _link_chain(g, by_role.get("source", []), by_role.get("impl", []), "implemented_by")
    _link_chain(g, by_role.get("impl", []), by_role.get("design", []), "designed_by")
    # cualquier eslabón --tested_by--> test(SAT/OQ)
    for upstream_role in ("source", "impl", "design"):
        _link_to_tests(g, by_role.get(upstream_role, []), by_role.get("test", []))

    # test --verifies--> requirement (el test cita el req id o un ref trazable)
    for tidx in by_role.get("test", []):
        for t in tidx["tests"]:
            trefs = extract_refs(t.get("descripcion", "")) | ({_norm_ref(t["identificador"])}
                                                              if t.get("identificador") else set())
            for r in trefs:
                rid = ref_to_req.get(r)
                if rid:
                    _safe_edge(g, t["test_id"], rid, "verifies")

    # contradicts (heurística conservadora: mismo ref + modal opuesto)
    _link_contradictions(g, indices)

    counts = g.counts()
    g.close()
    return counts


def _safe_edge(g: GraphStore, src: str, dst: str, rel: str, attrs: dict | None = None) -> None:
    from factory.regulatory.graph.store import DanglingEdgeError, UnknownRelationError
    try:
        g.add_edge(src, dst, rel, attrs=attrs)
    except (DanglingEdgeError, UnknownRelationError):
        pass  # el linkeo es best-effort; un extremo ausente o kind inválido se salta


def _link_chain(g: GraphStore, ups: list[dict], downs: list[dict], rel: str) -> None:
    """Une claims de docs 'aguas arriba' con claims de docs 'aguas abajo'
    que comparten un identificador de referencia literal."""
    for u in ups:
        for d in downs:
            shared = set(u["claims_by_ref"]) & set(d["claims_by_ref"])
            for ref in shared:
                for su in u["claims_by_ref"][ref]:
                    for sd in d["claims_by_ref"][ref]:
                        _safe_edge(g, su, sd, rel, {"via_ref": ref})


def _link_to_tests(g: GraphStore, ups: list[dict], tests_idx: list[dict]) -> None:
    for u in ups:
        for tidx in tests_idx:
            for t in tidx["tests"]:
                trefs = extract_refs(t.get("descripcion", ""))
                if t.get("identificador"):
                    trefs.add(_norm_ref(t["identificador"]))
                for ref in trefs & set(u["claims_by_ref"]):
                    for su in u["claims_by_ref"][ref]:
                        _safe_edge(g, su, t["test_id"], "tested_by", {"via_ref": ref})


def _link_contradictions(g: GraphStore, indices: list[dict]) -> None:
    """MUY conservador: dos claims (de cualquier par de documentos) que
    comparten un identificador de referencia y donde uno usa modal
    POSITIVO y el otro modal NEGATIVO sobre ese ref. No pretende cubrir
    contradicciones semánticas -- eso es trabajo de B6/agentes.

    Usa `idx["claim_texts"]`/`idx["claims_by_ref"]` ya capturados en
    `_ingest_canonical` -- no vuelve a leer el store (así no depende de
    ningún `store_dir` implícito)."""
    ref_claims: dict[str, list[tuple[str, str]]] = {}  # ref -> [(claim_id, source_text)]
    for idx in indices:
        texts = idx["claim_texts"]
        for ref, claim_ids in idx["claims_by_ref"].items():
            for cid in claim_ids:
                ref_claims.setdefault(ref, []).append((cid, texts.get(cid, "")))
    for ref, items in ref_claims.items():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                (ci, ti), (cj, tj) = items[i], items[j]
                neg_i, neg_j = bool(_MODAL_NEG.search(ti)), bool(_MODAL_NEG.search(tj))
                pos_i = bool(_MODAL_POS.search(ti)) and not neg_i
                pos_j = bool(_MODAL_POS.search(tj)) and not neg_j
                if (neg_i and pos_j) or (neg_j and pos_i):
                    _safe_edge(g, ci, cj, "contradicts", {"via_ref": ref, "heuristic": "modal_opposite"})
