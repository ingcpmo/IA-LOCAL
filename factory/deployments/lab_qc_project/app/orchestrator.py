"""
Lab QC Orchestrator — router de agentes e intent detection.
Agentes activos: qa, integrity, capa, qa_oos_profile, integrity_lims_profile, hplc_data_review.
"""
from app.agents.base import AgentConfig, AGENT_REGISTRY

_AGENT_KEYWORDS: dict[str, list[str]] = {
    "hplc_data_review": [
        "hplc", "chromatogram", "cromatograma", "sst", "system suitability",
        "aptitud del sistema", "idoneidad del sistema", "peak integration", "integracion de pico",
        "integración de pico", "baseline", "linea base", "tailing factor", "factor de cola",
        "plate count", "numero de platos", "resolution", "resolución", "resolution rs",
        "injection sequence", "secuencia de inyección", "secuencia de inyeccion",
        "bracketing standard", "estándar de encuadre", "manual integration",
        "integración manual", "calibration curve", "curva de calibración",
        "r squared", "r2", "coeficiente de correlación", "raw chromatogram",
        "cromatograma original", "hplc data", "datos hplc", "uplc", "uhplc",
        "gc data", "datos gc", "chromatographic", "cromatográfico",
        "usp 621", "usp <621>", "ich q2", "peak area", "área de pico",
        "retention time", "tiempo de retención", "injection order",
        "inyección de prueba", "test injection", "sequence log",
        "data file", "archivo de datos", "procesamiento de datos cromatográficos",
    ],
    "qa_oos_profile": [
        "oos", "out of specification", "fuera de especificacion", "fuera de especificación",
        "oot", "out of trend", "fuera de tendencia", "oos investigation",
        "investigación oos", "investigacion oos", "phase i investigation", "phase ii investigation",
        "fase i investigación", "fase ii investigación", "invalidate result",
        "invalidar resultado", "invalidación", "invalidacion", "retest",
        "reensayo", "resample", "re-muestreo", "oos guidance", "fda oos",
        "211.160", "211.165", "211.192", "211.194", "assignable cause",
        "causa asignable", "lab error", "error de laboratorio", "analyst error",
        "error del analista", "oos disposition", "disposición oos",
        "batch disposition", "disposición de lote", "reject batch", "rechazar lote",
        "additional testing", "pruebas adicionales", "statistical outlier",
        "outlier estadístico", "out-of-specification",
    ],
    "integrity_lims_profile": [
        "lims", "laboratory information", "sistema de información de laboratorio",
        "lims audit trail", "audit trail lims", "lims user access", "acceso lims",
        "shared login lims", "cuenta compartida lims", "lims configuration",
        "configuración lims", "raw data lims", "datos originales lims",
        "usp 1058", "usp <1058>", "aiq", "analytical instrument qualification",
        "calificación de instrumento analítico", "instrument qualification",
        "calificación de instrumento", "lims integrity", "integridad lims",
        "electronic result", "resultado electrónico", "lims record",
        "registro lims", "lims sequence", "secuencia lims", "instrument link",
        "vinculación instrumento", "method in lims", "método en lims",
    ],
    "integrity": [
        "alcoa", "data integrity", "integridad de datos", "audit trail",
        "metadata", "raw data", "datos crudos", "datos originales",
        "hybrid system", "sistema hibrido", "sistema híbrido",
        "tipp-ex", "falsificacion", "falsificación", "backdating",
        "mhra di", "fda di", "di guidance", "balanza", "sin audit trail",
        "shared account", "shared user", "shared admin", "shared login",
        "not reviewed", "audit trail not", "modify result", "modify analytical",
        "administrator user", "generic account", "cuenta compartida",
    ],
    "qa": [
        "deviation", "desviación", "desviacion", "sop", "procedimiento",
        "trending", "quality system", "sistema de calidad", "deviation report",
        "non-conformance", "no conformidad", "batch release", "liberar lote",
        "annual product review", "pqr", "apr", "evento", "lote",
    ],
    "capa": [
        "capa", "corrective", "preventive", "root cause", "causa raiz", "causa raíz",
        "effectiveness", "efectividad", "closure", "cierre de capa",
        "5-why", "5 why", "cinco porques", "ishikawa", "fishbone",
        "fault tree", "fta", "rpn", "recurring deviation", "desviacion recurrente",
        "desviación recurrente", "effectiveness check", "effectiveness verification",
        "dias sin", "days without", "overdue",
    ],
}

# Para QC de laboratorio, el agente por defecto más apropiado es qa
_DEFAULT_AGENT = "qa"


def detect_agent(question: str, explicit_agent: str | None = None) -> str:
    """
    Si explicit_agent es un ID válido (no 'auto', no None) → retornarlo directamente.
    Si explicit_agent es 'auto', None, o cualquier valor no registrado → keyword scoring.
    En empate o sin match → retornar _DEFAULT_AGENT.
    """
    if explicit_agent and explicit_agent != "auto" and explicit_agent in AGENT_REGISTRY:
        return explicit_agent

    q_lower = question.lower()
    scores: dict[str, int] = {aid: 0 for aid in _AGENT_KEYWORDS}

    for agent_id, keywords in _AGENT_KEYWORDS.items():
        for kw in keywords:
            if kw in q_lower:
                scores[agent_id] += 1

    best_agent = max(scores, key=lambda k: scores[k])
    if scores[best_agent] == 0:
        return _DEFAULT_AGENT
    return best_agent


def build_prompt(
    question: str,
    agent_config: AgentConfig,
    context: str,
    rule_context: str,
) -> str:
    """
    Construye el prompt multicapa:
      [SYSTEM]  → system_prompt del agente
      [RULES]   → reglas determinísticas disparadas (si las hay)
      [CONTEXT] → fragmentos de ChromaDB relevantes
      [TASK]    → pregunta del usuario
      [FORMAT]  → instrucción de formato
    """
    sections: list[str] = []

    sections.append(f"[SYSTEM]\n{agent_config.system_prompt}")

    if rule_context:
        sections.append(f"[RULES — MANDATORY COMPLIANCE TRIGGERS]\n{rule_context}")

    if context:
        sections.append(f"[REGULATORY CONTEXT]\n{context}")

    sections.append(f"[TASK]\n{question}")

    # --- detección de idioma ---
    EN_WORDS = {
        'the','is','are','was','were','have','has','what','how','when','where',
        'which','that','this','with','for','and','does','do','should','must',
        'required','need','can','will','would','if','an','a','in','of','to',
        'be','been','it','its','not','or','at','but','from','by','on'
    }
    words = question.lower().split()
    en_score = sum(1 for w in words if w in EN_WORDS) / max(len(words), 1)
    lang_instruction = (
        "Respond in English. Be specific. Cite regulations with exact section numbers."
        if en_score >= 0.12
        else
        "Responde en español. Sé específico. Cita regulaciones con número de sección exacto."
    )
    # --- fin detección ---

    sections.append(f"[FORMAT] {lang_instruction}\n")

    return "\n\n".join(sections)


def route_and_build(
    question: str,
    explicit_agent: str,
    contexts: list[str],
    rules: list,
) -> tuple[str, str]:
    """
    Retorna (prompt_final, agent_id_detectado).
    """
    from app.rules import get_rule_context
    from app.agents.base import get_agent

    agent_id = detect_agent(question, explicit_agent)
    agent_cfg = get_agent(agent_id)
    rule_ctx = get_rule_context(rules)
    context_block = "\n\n".join(c[:400] for c in contexts[:4]) if contexts else ""
    prompt = build_prompt(question, agent_cfg, context_block, rule_ctx)
    return prompt, agent_id
