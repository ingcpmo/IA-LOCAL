"""
W6.5.1 (Pieza B) — Verificador v2 determinista de propuestas de agente.

Complementa el verificador de anclaje de dossier_agent_review_service con tres
detectores nuevos, todos ADVISORY (señalan al revisor humano; jamás reescriben
el texto del agente ni bloquean el flujo) y todos deterministas (sin LLM):

1. unverified_reference — cita [REF:] que no puede atarse a las declaraciones
   de corpus del agente (corpus_available + corpus_pending de profiles o del
   agent_design_proposal) ni al regulatory_scope de la misión. La whitelist NO
   es un archivo nuevo: se DERIVA de esas declaraciones existentes (cero
   mantenimiento humano adicional; se extiende sola a nuevos agentes/misiones).
   Granularidad de la derivación:
     - una sección CFR (11.30, 211.192…) solo es citable si alguna declaración
       la enumera; declarar la Parte completa autoriza citas de Parte y de
       Subparte, NUNCA de secciones específicas — la enumeración humana define
       el alcance verificable (evidencia real: v05 citó §11.30(a)/(c), fuera
       del alcance declarado §11.10, con contenido erróneo).
     - un documento (guía FDA/MHRA, USP, concepto) es citable a nivel
       documento; una cita con numeral de sección (§3.4) sobre un documento
       declarado sin secciones → flag (evidencia real: v05 inventó "FDA Data
       Integrity Guidance 2018, §3.4" — esa guía no tiene esa numeración).
     - corpus_pending también otorga citabilidad de TÍTULO: el documento está
       declarado y su título es verificable; la disponibilidad del contenido
       ya la captura corpus_sufficiency y la confianza computada.
2. negation_contradicted — claim negativa ("no hay evidencia de X") cuyo
   sujeto X SÍ aparece en la evidencia OPERACIONAL del prompt (runs, audit,
   rc, deployment: registros de lo que pasó). Mission/agents/doc_actual se
   excluyen a propósito: son declaraciones de intención — que la misión PIDA
   firmas electrónicas no contradice "no hay evidencia de firmas" (falso
   positivo real detectado en diseño). Los registros operacionales están en
   inglés (validation_doc_approved) y las claims en español: se usa un léxico
   ES→EN mínimo y explícito. Regla ALL: TODOS los tokens no genéricos del
   sujeto negado deben hallarse para señalar — precisión sobre exhaustividad,
   un flag falso erosiona la confianza del revisor (lección del anclaje v05).
3. multi_claim_line — más de una etiqueta [E:]/[SE]/[REF:] en la misma línea:
   el parser de claims solo cuenta la primera y el resto escapa a la
   verificación (evidencia real: v04 agrupó ~8 claims en 3 viñetas).
4. intra_proposal_contradiction (v2.1, W7 Fase A/B — limitación 1 del
   preflight de Fase 0) — viñeta [SE] cuya negación contradice una viñeta
   [E:] verificada (supported/partially_supported) de la MISMA respuesta.
   Evidencia real: v08 afirmó "[E: agents] qa_oos_profile es el perfil
   específico para la gestión OOS" y a la vez "[SE] No hay evidencia de un
   perfil de agente dedicado a la gestión OOS" — el v2.0 no lo veía (solo
   contrastaba contra evidencia operacional) y lo detectó Cesar a mano.
   Precisión sobre exhaustividad: regla ALL-tokens sobre el sujeto negado
   (≥2 tokens no genéricos — un solo sustantivo es señal demasiado débil) y
   los segmentos negados DENTRO de las [E:] se excluyen del contraste (dos
   negaciones coincidentes son acuerdo, no contradicción).

5. guidance_unapplied (v2.2, W7.1 — limitación §7.1 del cierre de Fase D) —
   revisión cuya respuesta es idéntica a la de su based_on_version
   (comparación de líneas no vacías con .strip(): inmune a whitespace, cero
   heurística de casi-igualdad — un cambio real de 1 carácter NO flaggea).
   Evidencia real: v2 del caso D-0554-2026 reprodujo v1 byte a byte
   ignorando la guidance de borrado y pasó v2.1 sin señal alguna. Solo
   aplica si quien llama pasa prev_response (modo revisión); en draft y en
   re-verificación de archivados (sin prev_response) jamás flaggea.

Fixtures de regresión obligatorios del gate: v01–v06 reales de
data_integrity_assessment, archivados en tests/fixtures/ (tests/
test_claim_verifier_v2.py); v08 real fija la regla 4; v01–v03 reales del
análisis de caso D-0554-2026 (tests/fixtures/case_analyses/) fijan la
regla 5. Módulo puro: sin I/O, sin HTTP, sin auditoría.
"""

import re
import unicodedata

VERIFIER_VERSION = "2.2"

# Evidencia operacional: registros de hechos ocurridos. La evidencia de
# intención (mission, agents, catalog, doc_actual) y la externa (case:*) no
# pueden "contradecir" una negación.
FACTUAL_EVIDENCE_IDS = frozenset({"runs", "audit", "rc", "deployment"})


def _norm(text: str) -> str:
    """minúsculas + sin acentos + '_'→' ' (los ids de misión y los eventos de
    auditoría usan snake_case; las claims usan español acentuado)."""
    text = str(text).lower().replace("_", " ")
    return "".join(ch for ch in unicodedata.normalize("NFD", text)
                   if not unicodedata.combining(ch))


# ── 1. unverified_reference ───────────────────────────────────────────────────

_CFR_SECTION_RE = re.compile(r"(?<![\d.])(\d{1,3})\.(\d{1,3})(?![\d.])")
_CFR_PART_RE = re.compile(r"\b(?:parte?|part)\s+(\d{1,3})\b|\bcfr\s+(\d{1,3})\b(?!\s*[.\d])")
# ids de misión normalizados: "21 cfr 211 192" (de 21_CFR_211_192)
_CFR_ID_SECTION_RE = re.compile(r"\bcfr\s+(\d{1,3})\s+(\d{1,3})\b")
_DOC_SECTION_MARKER_RE = re.compile(r"§|\bseccion\b|\bsection\b|\bnumeral\b")

# Relleno descriptivo de las declaraciones de corpus (no identifica al documento)
_DECL_STOP_TOKENS = frozenset({
    "de", "del", "la", "el", "los", "las", "y", "o", "u", "a", "en", "con",
    "para", "por", "the", "of", "for", "and", "texto", "publico", "completo",
    "pdf", "opcional", "concepto", "documentado", "documentada", "todos",
    "controles", "cfr",
})


def _content_tokens(norm_text: str) -> frozenset:
    return frozenset(t for t in re.findall(r"[a-z0-9]+", norm_text)
                     if t not in _DECL_STOP_TOKENS)


def parse_reference_grants(declarations: list) -> dict:
    """Deriva la whitelist de citas desde declaraciones de corpus + scope de
    misión (strings tal cual existen en profiles/*.yaml, agent_design_proposal
    y regulatory_scope). → {cfr_parts, cfr_sections, documents}."""
    grants = {"cfr_parts": set(), "cfr_sections": set(), "documents": []}
    for decl in declarations or []:
        norm = _norm(decl)
        if "cfr" in norm:
            for m in _CFR_SECTION_RE.finditer(norm):
                grants["cfr_sections"].add(f"{int(m.group(1))}.{int(m.group(2))}")
                grants["cfr_parts"].add(int(m.group(1)))
            for m in _CFR_ID_SECTION_RE.finditer(norm):
                grants["cfr_sections"].add(f"{int(m.group(1))}.{int(m.group(2))}")
                grants["cfr_parts"].add(int(m.group(1)))
            for m in _CFR_PART_RE.finditer(norm):
                grants["cfr_parts"].add(int(m.group(1) or m.group(2)))
        else:
            tokens = _content_tokens(norm)
            if tokens:
                grants["documents"].append(tokens)
    return grants


def check_reference(ref: str, grants: dict) -> dict | None:
    """→ None si la cita es atable a una declaración; detalle del flag si no."""
    norm = _norm(ref or "")
    if not norm.strip():
        return {"reason": "empty_reference"}
    if "cfr" in norm:
        m = _CFR_SECTION_RE.search(norm)
        if m:
            sec = f"{int(m.group(1))}.{int(m.group(2))}"
            if sec in grants["cfr_sections"]:
                return None
            return {"reason": "cfr_section_not_declared", "section": sec,
                    "declared_sections": sorted(grants["cfr_sections"])}
        parts = {int(g1 or g2) for g1, g2 in _CFR_PART_RE.findall(norm)}
        if parts & grants["cfr_parts"]:
            return None            # Parte o Subparte de una Parte declarada
        return {"reason": "cfr_part_not_declared", "parts": sorted(parts),
                "declared_parts": sorted(grants["cfr_parts"])}
    # documento / guía / concepto: citable solo a nivel documento
    if _DOC_SECTION_MARKER_RE.search(norm):
        return {"reason": "document_section_not_verifiable"}
    tokens = _content_tokens(norm)
    if tokens and any(tokens <= g for g in grants["documents"]):
        return None
    return {"reason": "document_not_declared"}


# ── 2. negation_contradicted ──────────────────────────────────────────────────

_NEGATION_RE = re.compile(
    r"(?:no hay|no existen?|no se (?:encontr|observ|registr|evidenci)\w*|"
    r"faltan?|carecen? de|ausencia de|sin evidencia de|no contienen?|"
    r"no cuentan? con)\b\s*(?P<subject>[^;.:,]*)")

# Tokens que no identifican al sujeto negado: gramática + sustantivos
# estructurales presentes en cualquier evidencia GMP de la factory +
# calificadores + estructura normativa (las citas las cubre el detector 1).
_GENERIC_SUBJECT_TOKENS = frozenset({
    "de", "del", "la", "el", "los", "las", "un", "una", "unos", "unas", "y",
    "o", "u", "a", "en", "con", "para", "por", "al", "lo", "que", "se", "su",
    "sus", "este", "esta", "estos", "estas", "como", "sobre", "conforme",
    "evidencia", "evidencias", "sistema", "sistemas", "registro", "registros",
    "dato", "datos", "informacion", "documento", "documentos",
    "documentacion", "archivo", "archivos", "cadena", "mision", "proyecto",
    "audit", "trail", "auditoria",
    "humano", "humana", "humanos", "humanas", "especifico", "especifica",
    "actual", "explicito", "explicita", "formal", "formales", "adecuado",
    "adecuada", "correspondiente", "correspondientes",
    # calificadores (v2.1): misma categoría que "especifico"/"adecuado" —
    # no identifican al sujeto negado (test fija la extensión del léxico)
    "dedicado", "dedicada", "dedicados", "dedicadas",
    "cfr", "fda", "mhra", "usp", "part", "parte", "subpart", "subparte",
    "norma", "normas", "guia", "guias", "guidance",
})

# Léxico ES→EN mínimo: sustantivos de dominio cuya forma inglesa aparece en
# los identificadores operacionales de la factory (eventos de auditoría,
# test_ids, estados). Extenderlo exige test que fije el nuevo comportamiento.
_ES_EN_EQUIV = {
    "aprobacion": ("approv",), "aprobaciones": ("approv",),
    "aprobado": ("approv",), "aprobados": ("approv",),
    "aprobada": ("approv",), "aprobadas": ("approv",),
    "firma": ("signature", "signing"), "firmas": ("signature", "signing"),
    "revision": ("review",), "revisiones": ("review",),
    "atributo": ("attribut",), "atributos": ("attribut",),
    "ejecucion": ("execut",), "ejecuciones": ("execut",),
    "prueba": ("test",), "pruebas": ("test",),
    "despliegue": ("deploy",), "despliegues": ("deploy",),
    "liberacion": ("release",),
    "rechazo": ("reject",), "rechazos": ("reject",),
    "rechazado": ("reject",), "rechazada": ("reject",),
    "propuesta": ("proposal",), "propuestas": ("proposal",),
    "decision": ("decision",), "decisiones": ("decision",),
}


def check_negations(claims: list, items: list) -> list:
    """Un finding por claim como máximo. Regla ALL sobre los tokens no
    genéricos del sujeto negado, contra la evidencia operacional únicamente."""
    factual_ids = [it["id"] for it in items if it["id"] in FACTUAL_EVIDENCE_IDS]
    factual = " \n ".join(_norm(it["content"]) for it in items
                          if it["id"] in FACTUAL_EVIDENCE_IDS)
    findings = []
    if not factual.strip():
        return findings
    for c in claims:
        for m in _NEGATION_RE.finditer(_norm(c["text"])):
            subject = m.group("subject").split(" que ")[0].strip()
            tokens = [t for t in re.findall(r"[a-z0-9+]+", subject)
                      if t not in _GENERIC_SUBJECT_TOKENS
                      and not t.isdigit() and len(t) > 2]
            if not tokens:
                continue
            matched = {}
            for t in tokens:
                hit = next((cand for cand in (t,) + _ES_EN_EQUIV.get(t, ())
                            if cand in factual), None)
                if hit is None:
                    matched = None
                    break
                matched[t] = hit
            if matched:
                findings.append({"type": "negation_contradicted",
                                 "claim": c["text"],
                                 "negated_subject": subject,
                                 "matched_tokens": matched,
                                 "evidence_ids": factual_ids})
                break
    return findings


def _negation_subject_tokens(text_norm: str) -> list:
    """Sujetos negados de un texto normalizado → [lista de tokens no genéricos
    por negación]. Mismo recorte y filtrado que check_negations."""
    out = []
    for m in _NEGATION_RE.finditer(text_norm):
        subject = m.group("subject").split(" que ")[0].strip()
        tokens = [t for t in re.findall(r"[a-z0-9+]+", subject)
                  if t not in _GENERIC_SUBJECT_TOKENS
                  and not t.isdigit() and len(t) > 2]
        if tokens:
            out.append((subject, tokens))
    return out


# ── 4. intra_proposal_contradiction (v2.1) ────────────────────────────────────

def check_intra_contradictions(claims: list) -> list:
    """Negaciones en viñetas [SE] contra las afirmaciones de las viñetas [E:]
    verificadas de la MISMA respuesta. Un finding por claim [SE] como máximo.
    Los segmentos negados dentro de la [E:] se excluyen del contraste: si la
    [E:] también niega el sujeto, hay acuerdo, no contradicción."""
    targets = []
    for c in claims:
        if c.get("tag") == "E" and c.get("support") in ("supported",
                                                        "partially_supported"):
            affirmative = _NEGATION_RE.sub(" ", _norm(c["text"]))
            targets.append((c, affirmative))
    findings = []
    if not targets:
        return findings
    for c in claims:
        if c.get("tag") != "SE":
            continue
        for subject, tokens in _negation_subject_tokens(_norm(c["text"])):
            if len(tokens) < 2:      # un solo sustantivo: señal demasiado débil
                continue
            hit = next((e for e, aff in targets
                        if all(t in aff for t in tokens)), None)
            if hit is not None:
                findings.append({"type": "intra_proposal_contradiction",
                                 "claim": c["text"],
                                 "negated_subject": subject,
                                 "subject_tokens": tokens,
                                 "contradicted_by": hit["text"],
                                 "contradicted_by_pointer": hit.get("pointer")})
                break
    return findings


# ── 3. multi_claim_line ───────────────────────────────────────────────────────

_CLAIM_TAG_RE = re.compile(r"\[(?:E:[^\]]*|SE|REF:[^\]]*)\]")


def check_multi_claim_lines(response: str) -> list:
    findings = []
    for n, line in enumerate((response or "").splitlines(), 1):
        tags = _CLAIM_TAG_RE.findall(line)
        if len(tags) > 1:
            findings.append({"type": "multi_claim_line", "line_number": n,
                             "tags": tags, "line": line.strip()[:200]})
    return findings


def check_guidance_unapplied(response: str, prev_response: str | None) -> list:
    """Regla 5 (v2.2, W7.1): revisión idéntica a la versión que debía corregir.
    prev_response None = modo draft o re-verificación de archivados → nunca
    flaggea. Igualdad de la secuencia de líneas no vacías .strip(): absorbe
    diferencias de solo whitespace; cualquier cambio real de contenido, aun
    de 1 carácter, NO flaggea (precisión sobre exhaustividad)."""
    if prev_response is None:
        return []
    norm = lambda t: [l.strip() for l in (t or "").splitlines() if l.strip()]
    if norm(response) != norm(prev_response):
        return []
    return [{"type": "guidance_unapplied",
             "detail": "la revisión es idéntica a la versión revisada — la "
                       "instrucción QA no tuvo efecto observable"}]


# ── Orquestación ──────────────────────────────────────────────────────────────

def verify_v2(response: str, claims: list, items: list, grants: dict,
              prev_response: str | None = None) -> dict:
    """→ {version, flags, findings}. Advisory: quien llama decide qué hacer
    con los flags (registro + penalización de confianza); aquí no se bloquea,
    no se reescribe y no se audita."""
    findings = []
    for c in claims:
        if c.get("tag") == "REF":
            detail = check_reference(c.get("pointer"), grants)
            if detail:
                findings.append({"type": "unverified_reference",
                                 "reference": c.get("pointer"),
                                 "claim": c["text"], **detail})
    findings += check_negations(claims, items)
    findings += check_multi_claim_lines(response)
    findings += check_intra_contradictions(claims)
    findings += check_guidance_unapplied(response, prev_response)
    flags = []
    for f in findings:
        if f["type"] not in flags:
            flags.append(f["type"])
    return {"version": VERIFIER_VERSION, "flags": flags, "findings": findings}


# ── Re-verificación de propuestas archivadas ──────────────────────────────────

_EVIDENCE_BLOCK_RE = re.compile(
    r"\[EVIDENCIA (?P<id>\S+) trust=(?P<trust>\w+) INICIO\]\n"
    r"(?P<content>.*?)\n\[EVIDENCIA (?P=id) FIN\]", re.S)


def items_from_prompt(prompt_full: str) -> list:
    """Reconstruye los items de evidencia desde un prompt archivado — permite
    re-verificar propuestas históricas (fixtures de regresión v01–v06 del
    gate) sin regenerarlas."""
    return [{"id": m.group("id"), "trust": m.group("trust"),
             "content": m.group("content")}
            for m in _EVIDENCE_BLOCK_RE.finditer(prompt_full or "")]
