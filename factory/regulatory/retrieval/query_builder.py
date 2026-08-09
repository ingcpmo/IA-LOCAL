"""R2 (docs_plan/R2_DESIGN_DETALLADO.md) -- construcción de la query de
recuperación desde el Evidence Pack gobernado. Regla dura explícita del
alcance (R1_CIERRE_Y_PREP_R2.md sección 4): `weak_keywords` NUNCA es la
única fuente de una query -- puede complementar, nunca sustituir a
`citation_text`/`evidence_min_criteria`/`requirement_terms.yaml`. Motivo:
`weak_keywords` existe en el catálogo precisamente para marcar términos
DÉBILES/ambiguos -- usarlos solos invitaría al mismo patrón que produjo
el falso positivo ANNEX11_4 original (keyword aislado sin contexto
normativo)."""
from __future__ import annotations

from factory.regulatory.evidence_verifier import load_requirement_terms
from factory.regulatory.requirement_catalog.requirement_catalog_loader import get_requirement


def build_retrieval_query(req_id: str) -> str:
    """Determinista -- mismo input siempre produce la misma query, sin
    llamada a LLM en ningún punto. Fuentes primarias y obligatorias:
    citation_text (texto normativo literal, gobernado) +
    evidence_min_criteria (criterios reales, interpretados por Cesar en
    Fase C de W5 V2) + los sinónimos ya gobernados de
    requirement_terms.yaml (reutilizado tal cual, sin reimplementar)."""
    entry = get_requirement(req_id)
    terms = load_requirement_terms(req_id)
    parts = [
        entry["citation"]["citation_text"],
        *entry.get("evidence_min_criteria", []),
        *terms,
    ]
    query = " ".join(p for p in parts if p)
    if not query.strip():
        raise ValueError(
            f"build_retrieval_query: query vacia para {req_id!r} -- citation_text/"
            "evidence_min_criteria/requirement_terms.yaml no aportaron ningun termino. "
            "weak_keywords NUNCA es un fallback aceptable aqui (ver docstring del modulo)."
        )
    return query
