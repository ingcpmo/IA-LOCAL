"""Extracción y normalización de `Claim` desde secciones (V2, B1) —
docs_plan/ARQUITECTURA_OBJETIVO_ANALIZADOR_GMP_LOCAL_V2.md FASE 2.4.

Objetivo del rediseño (FASE 1: la causa raíz del recall es
`SEMANTIC_JUDGMENT_FAILURE` — el 7B no cruza pasaje→criterio sin eco
léxico): que el LLM de juicio reciba un `Claim.normalized_statement`
corto y un sub-criterio concreto, en vez de una página plana de ~6000
caracteres. El salto pasa de "página → criterio abstracto" a
"afirmación normalizada → sub-criterio".

B1 usa HEURÍSTICA LÉXICA, sin llamadas LLM:
  - segmenta el texto de sección en oraciones candidatas;
  - filtra ruido (líneas de tabla de contenido, furniture, headers sueltos);
  - clasifica el `tipo` por patrones (control / function / test /
    parameter / actor_action / statement);
  - `normalized_statement` = limpieza determinista (colapso de espacios,
    quita muletillas, recorta) — NUNCA reescribe ni infiere contenido.

`Claim.source_text` es SIEMPRE el literal de la oración; es la única
cita citable. `normalized_statement` jamás se usa como evidencia (mismo
guardián que la Palanca V2b).

La variante opcional (1 llamada LLM local corta por sección: "describe
en términos operativos, sin norma") se documenta en la arquitectura pero
NO se implementa aquí — sería el único punto LLM y queda fuera de B1.
"""
from __future__ import annotations

import re

from factory.regulatory.canonical.model import Claim, build_claim
from factory.regulatory.evidence_verifier import strip_page_furniture

# Oración: termina en . ; : o salto; mínimo razonable de longitud.
_SENT_SPLIT_RE = re.compile(r"(?<=[.;:])\s+|\n+")
_MIN_CLAIM_CHARS = 25
_MAX_CLAIM_CHARS = 600

# Líneas de tabla de contenido: "algo ..... 45"
_TOC_LINE_RE = re.compile(r"\.{4,}\s*\d+\s*$")
# Header suelto de plantilla / numeración pura
_NOISE_RE = re.compile(
    r"^(page\s+\d+\s+of\s+\d+|©.*rockwell|id code:|project:|author:|\d+(\.\d+)*\s*$)",
    re.IGNORECASE,
)

# Muletillas de arranque que no aportan al statement (se recortan solo del
# INICIO, nunca del interior — no se altera contenido).
_LEADING_FILLER_RE = re.compile(
    r"^(note that|please note|it should be noted that|in addition,?|furthermore,?|"
    r"as such,?|therefore,?|thus,?|hence,?|nota:?|cabe destacar que|se debe notar que)\s+",
    re.IGNORECASE,
)

_CONTROL_HINTS = (
    "shall", "must", "will be", "is restricted", "is required", "access", "audit trail",
    "authorization", "authoriz", "permission", "role", "credential", "login", "password",
    "backup", "recovery", "encrypt", "restrict", "prevent", "enforce", "debe", "deberá",
    "restringe", "controla", "impide",
)
_FUNCTION_HINTS = (
    "the system", "this function", "the function", "provides", "performs", "calculates",
    "displays", "monitors", "records", "generates", "implements", "el sistema", "la función",
    "esta función", "registra", "genera", "muestra", "monitorea",
)
_TEST_HINTS = ("test case", "sat-", "oq-", "verify that", "expected result", "acceptance criteria",
               "step ", "prueba", "verificar que", "resultado esperado", "criterio de aceptación")
_PARAMETER_HINTS = ("setpoint", "set point", "range", "threshold", "limit", "value of",
                    "parameter", "tag ", "= ", "shall be set to", "rango", "límite", "umbral")
_ACTOR_HINTS = ("the operator", "the user", "the administrator", "the engineer", "personnel",
                "el operador", "el usuario", "el administrador", "personal autorizado")


def _classify(sentence: str) -> str:
    s = sentence.lower()
    if any(h in s for h in _TEST_HINTS):
        return "test"
    if any(h in s for h in _PARAMETER_HINTS):
        return "parameter"
    if any(h in s for h in _CONTROL_HINTS):
        return "control"
    if any(h in s for h in _ACTOR_HINTS):
        return "actor_action"
    if any(h in s for h in _FUNCTION_HINTS):
        return "function"
    return "statement"


def _is_noise(line: str) -> bool:
    l = line.strip()
    if len(l) < _MIN_CLAIM_CHARS:
        return True
    if _TOC_LINE_RE.search(l):
        return True
    if _NOISE_RE.match(l):
        return True
    # Casi todo dígitos / puntuación
    alpha = sum(c.isalpha() for c in l)
    if alpha < len(l) * 0.4:
        return True
    return False


def normalize_statement(sentence: str) -> str:
    """Limpieza DETERMINISTA. Colapsa espacios, quita furniture de
    plantilla, recorta muletillas de arranque, trunca a
    `_MAX_CLAIM_CHARS`. No reescribe, no infiere, no traduce, no añade ni
    quita vocabulario del cuerpo de la frase."""
    s = strip_page_furniture(sentence or "")
    s = re.sub(r"\s+", " ", s).strip()
    s = _LEADING_FILLER_RE.sub("", s)
    s = s.strip(" -•\t")
    if len(s) > _MAX_CLAIM_CHARS:
        s = s[:_MAX_CLAIM_CHARS].rsplit(" ", 1)[0] + "…"
    return s


def sentences_from_section_text(text: str) -> list[str]:
    raw = strip_page_furniture(text or "")
    parts = [p.strip() for p in _SENT_SPLIT_RE.split(raw) if p.strip()]
    out: list[str] = []
    for p in parts:
        if _is_noise(p):
            continue
        if len(p) > _MAX_CLAIM_CHARS * 2:
            # Bloque sin puntuación (frecuente en PDF): parte por longitud
            # en el último espacio para no cortar palabras.
            while len(p) > _MAX_CLAIM_CHARS:
                cut = p[:_MAX_CLAIM_CHARS].rsplit(" ", 1)[0] or p[:_MAX_CLAIM_CHARS]
                if not _is_noise(cut):
                    out.append(cut)
                p = p[len(cut):].strip()
            if p and not _is_noise(p):
                out.append(p)
        else:
            out.append(p)
    return out


# B1.2 -- identificador de requisito al INICIO de una oración/línea:
#   - id formal:   URS-PCS-SR-037 / PCS-SR-037 / MCCPDC-... (letras-letras-numero)
#   - número jerárquico de 3+ niveles: 4.4.1 / 5.2.22 / 1.4.2.4
# Se exige que vaya SEGUIDO de más texto (no un encabezado suelto).
_REQ_LOCAL_ID_RE = re.compile(
    r"^\s*(?P<id>(?:URS[\s\-])?[A-Z]{2,6}[\s\-][A-Z]{2,5}[\s\-]\d{2,5}[A-Za-z]?"
    r"|\d\.\d{1,2}(?:\.\d{1,3}){1,3})\b\s*[-:\.]?\s*(?=\S)"
)


def _extract_local_id(sentence: str) -> str | None:
    m = _REQ_LOCAL_ID_RE.match(sentence or "")
    if not m:
        return None
    return re.sub(r"\s+", "-", m.group("id").strip()).upper()


def extract_claims_for_section(document_id: str, pagina: int, section_text: str, *,
                               section_id: str | None = None,
                               section_numero: str | None = None,
                               section_titulo: str | None = None) -> list[Claim]:
    """Determinista, sin LLM. Un `Claim` por oración candidata que
    sobrevive el filtro de ruido.

    B1.2: si una oración arranca con un identificador de requisito
    (número jerárquico 3+ niveles o id formal tipo URS-PCS-SR-037), ese
    id se guarda en `Claim.local_id` y se HEREDA a las oraciones
    siguientes de la misma sección que no traigan uno propio (una
    continuación de línea pertenece al mismo bloque de requisito). El id
    se resetea al aparecer uno nuevo. `local_id` NO es una cita citable."""
    claims: list[Claim] = []
    seen: set[str] = set()
    current_local_id: str | None = None
    for sent in sentences_from_section_text(section_text):
        own = _extract_local_id(sent)
        if own:
            current_local_id = own
        norm = normalize_statement(sent)
        if len(norm) < _MIN_CLAIM_CHARS:
            continue
        key = norm.lower()
        if key in seen:
            continue
        seen.add(key)
        claims.append(build_claim(
            document_id=document_id, pagina=pagina, source_text=sent,
            tipo=_classify(sent), normalized_statement=norm,
            section_id=section_id, section_numero=section_numero,
            section_titulo=section_titulo,
            local_id=own or current_local_id,
        ))
    return claims
