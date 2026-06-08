"""
GMP Orchestrator — Capa 2: router de agentes e intent detection.
"""
from app.agents.base import AgentConfig, AGENT_REGISTRY

_AGENT_KEYWORDS: dict[str, list[str]] = {
    "csv": [
        "sistema", "software", "validacion", "validación", "csv", "csa",
        "gamp", "gamp5", "gamp 5", "iq", "oq", "pq", "iq/oq", "oq/pq",
        "part 11", "part11", "21 cfr 11", "uv", "lims", "erp", "mes validacion",
        "computerized", "computer system", "sistema informatico", "sistema informático",
        "firmware", "change control", "revalidacion", "revalidación",
    ],
    "qa": [
        "deviation", "desviación", "desviacion", "oos", "out of specification",
        "fuera de especificacion", "fuera de especificación", "sop", "procedimiento",
        "trending", "quality system", "sistema de calidad", "deviation report",
        "non-conformance", "no conformidad", "batch release", "liberar lote",
        "annual product review", "pqr", "apr", "evento", "lote",
    ],
    "audit": [
        "inspector", "483", "form 483", "fda visit", "readiness",
        "fda audit", "regulatory audit", "inspeccion regulatoria",
        "inspección regulatoria", "inspection readiness", "warning letter",
        "observacion regulatoria", "observación regulatoria",
        "for cause", "pre-approval", "pai", "surveillance", "vigilancia",
        "regulatory gap", "compliance gap", "fda inspection", "gmp inspection",
        "inspeccion", "inspección", "inspection", "simula inspeccion", "simulate inspection",
        "audit readiness", "audit finding",
    ],
    "automation": [
        "plc", "scada", "dcs", "mes", "isa-88", "isa88", "isa-95", "isa95",
        "batch record", "batch record electronico", "ebr", "alarm", "alarma",
        "hmi", "historian", "isa 88", "isa 95", "control system",
        "sistema de control", "scada validacion", "plc validacion",
        "eemua", "namur", "fieldbus", "profibus", "opc",
    ],
    "integrity": [
        "alcoa", "data integrity", "integridad de datos", "audit trail",
        "metadata", "raw data", "datos crudos", "datos originales",
        "hybrid system", "sistema hibrido", "sistema híbrido",
        "tipp-ex", "falsificacion", "falsificación", "backdating",
        "mhra di", "fda di", "di guidance", "balanza", "sin audit trail",
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

_DEFAULT_AGENT = "csv"


def detect_agent(question: str, explicit_agent: str | None = None) -> str:
    """
    Si explicit_agent es un ID válido → retornarlo directamente.
    Si no → keyword scoring sobre la pregunta para auto-detectar el agente.
    En empate o sin match → retornar _DEFAULT_AGENT.
    """
    if explicit_agent and explicit_agent in AGENT_REGISTRY:
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

    sections.append("[FORMAT]\nEspañol. Cita secciones exactas. Respuesta concisa.")

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
