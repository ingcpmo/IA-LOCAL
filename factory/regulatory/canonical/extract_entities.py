"""H-10 -- Extracción determinista de `SystemComponent` y `Actor` desde el
cuerpo YA extraído de un documento (lista de `claim` con provenance).

Cierra el sub-fallo de R-5: `build.py` sabe crear `claim --refers_to-->
system_component|actor`, pero no había etapa que poblara esos nodos, así que
`refers_to` quedaba inanido.

ADITIVA y GOBERNADA POR EL MISMO FLAG que la extracción de `Test`
(`V2_TEST_EXTRACTION` / `extract_tests=True`): con el flag OFF la salida del
pipeline no cambia. Activarlo agrupa Test + entidades en el ÚNICO salto
gobernado de `EXTRACTION_VERSION` (`canonical-v1-2026-08+tests-v1`).

Anti-fabricación (regla dura):
  * NUNCA se crea un nodo sin una MENCIÓN LITERAL en el `source_text` de un
    claim real -> provenance completa (document_id + page + source_text + hash).
  * Diccionario CERRADO de nombres de componente/rol (no NER abierta). Un
    nombre que no está en el diccionario y no casa un patrón de tag de equipo
    NO genera nodo.
  * Nombres genéricos de una sola palabra (`system`, `user`, `HMI`, `PLC`...)
    NO generan nodo por sí solos -> evita `refers_to` de baja señal.

Sin LLM, sin red. Determinista.
"""
from __future__ import annotations

import re

from factory.regulatory.canonical.model import build_actor, build_system_component

# ── Componentes: diccionario cerrado nombre_literal -> tipo canónico ──────
# tipo ∈ COMPONENT_TYPES = PLC SCADA HMI Historian DB network server other
_COMPONENT_TERMS: dict[str, str] = {
    "ControlLogix": "PLC",
    "CompactLogix": "PLC",
    "GuardLogix": "PLC",
    "FactoryTalk View SE": "SCADA",
    "FactoryTalk View": "SCADA",
    "FactoryTalk Historian": "Historian",
    "FactoryTalk Linx": "network",
    "FactoryTalk Directory": "server",
    "FactoryTalk": "SCADA",
    "PanelView Plus": "HMI",
    "PanelView": "HMI",
    "OPC server": "server",
    "OPC UA server": "server",
    "SCADA server": "server",
    "Historian server": "Historian",
    "domain controller": "server",
    "Active Directory": "server",
    "thin client": "server",
    "engineering workstation": "server",
    "Stratix": "network",
}

# Tag de equipo real del proyecto (panel / controlador). Distinto del id de
# REQUISITO (patrón XX-[HS]R-NNN, p.ej. PCS-HR-001) -> se excluye ese caso.
_EQUIP_TAG_RE = re.compile(r"\bPCS[- ]?CP[- ]?0*\d{1,2}\b", re.IGNORECASE)   # PCS-CP-01, PCS CP01
_CP_TAG_RE = re.compile(r"\bCP-?0\d\b", re.IGNORECASE)                        # CP01, CP-02
_REQ_ID_RE = re.compile(r"\b[A-Z]{2,4}-[HS]R-\d{2,4}\b")                      # PCS-HR-001 (requisito, NO equipo)

# ── Actores: diccionario cerrado rol_literal -> tipo canónico ─────────────
# tipo ∈ ACTOR_TYPES = human system role
_ACTOR_TERMS: dict[str, str] = {
    "System Administrator": "role",
    "Domain Administrator": "role",
    "Administrator": "role",
    "Operator": "role",
    "Supervisor": "role",
    "Maintenance Technician": "role",
    "Maintenance Engineer": "role",
    "Quality Assurance": "role",
    "QA Reviewer": "role",
    "QA Approver": "role",
    "Validation Engineer": "role",
    "Controls Engineer": "role",
    "Shift Supervisor": "role",
}

_MAX_ENTITIES_PER_DOC = 2000


def _mentions(text: str, term: str) -> bool:
    """Mención literal por límite de palabra, case-insensitive."""
    return re.search(r"\b" + re.escape(term) + r"\b", text or "", re.IGNORECASE) is not None


#: H-10: una entrada de lista de referencias / cita de manual NO es un buen
#: ancla de provenance para un componente (aunque lo nombre). Se prefiere una
#: mención en prosa. Si SÓLO hay menciones de este tipo, se usa la primera igual
#: (mejor un ancla real de cita que ninguna).
_CITATION_ANCHOR_RE = re.compile(
    r"^\s*(?:\[\d{1,3}\]|\d{1,2}\.\s+[A-Z].{0,80}(?:Guide|Manual|Standard|Specification))"
    r"|User'?s?\s+Guide|Reference Manual|\bUM\d{3}[A-Z]?\b|VIEWSE-UM", re.IGNORECASE)


def _is_citation_anchor(text: str) -> bool:
    return bool(_CITATION_ANCHOR_RE.search(text or ""))


def extract_entities_for_document(document_id: str, claims: list[dict]) -> tuple[list, list]:
    """Devuelve (system_components, actors) del modelo canónico, anclados a la
    primera mención literal EN PROSA (no en lista de referencias) en un claim.
    Dedup por nombre normalizado. Determinista."""
    comps: list = []
    actors: list = []
    seen_c: set[str] = set()
    seen_a: set[str] = set()

    # orden estable: menciones en prosa ANTES que citas de manual/ref-list;
    # luego por página, luego por hash del texto.
    ordered = sorted(
        claims or [],
        key=lambda c: (_is_citation_anchor(c.get("source_text", "")),
                       c.get("pagina") or 0, c.get("source_hash") or ""))

    for c in ordered:
        txt = c.get("source_text", "") or ""
        if not txt.strip():
            continue
        pag = c.get("pagina") or 1
        s_num = (c.get("provenance") or {}).get("section_numero")
        s_tit = (c.get("provenance") or {}).get("section_titulo")

        # --- componentes por diccionario cerrado ---
        for term, tipo in _COMPONENT_TERMS.items():
            key = term.strip().lower()
            if key in seen_c:
                continue
            if _mentions(txt, term):
                comps.append(build_system_component(
                    document_id, pag, term, tipo, source_text=txt[:400],
                    section_numero=s_num, section_titulo=s_tit))
                seen_c.add(key)

        # --- componentes por tag de equipo (excluye ids de requisito) ---
        for m in list(_EQUIP_TAG_RE.finditer(txt)) + list(_CP_TAG_RE.finditer(txt)):
            raw = m.group(0)
            # si el match está dentro de un id de requisito, saltar
            span = txt[max(0, m.start() - 4): m.end() + 4]
            if _REQ_ID_RE.search(span):
                continue
            name = re.sub(r"[\s]", "-", raw.upper()).replace("--", "-")
            key = name.lower()
            if key in seen_c:
                continue
            comps.append(build_system_component(
                document_id, pag, name, "PLC", source_text=txt[:400],
                section_numero=s_num, section_titulo=s_tit))
            seen_c.add(key)

        # --- actores por diccionario cerrado ---
        for term, tipo in _ACTOR_TERMS.items():
            key = term.strip().lower()
            if key in seen_a:
                continue
            if _mentions(txt, term):
                actors.append(build_actor(
                    document_id, pag, term, tipo, source_text=txt[:400],
                    section_numero=s_num, section_titulo=s_tit))
                seen_a.add(key)

        if len(comps) + len(actors) >= _MAX_ENTITIES_PER_DOC:
            break

    return comps, actors
