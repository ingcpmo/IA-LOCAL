"""
GMP Rule Engine — Capa 3 (lógica determinística).
Evalúa reglas regulatorias por keyword matching antes de llamar al LLM.
"""
from dataclasses import dataclass

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


@dataclass
class RuleResult:
    triggered: bool
    rule_id: str
    risk_level: str  # CRITICAL / HIGH / MEDIUM / LOW
    action: str
    regulatory_basis: str


GMP_RULES: list[dict] = [
    {
        "id": "R001",
        "agent": "csv",
        "condition_keywords": ["firmware", "software", "sistema gmp crítico", "gmp critical system"],
        "risk": "HIGH",
        "action": "OQ requerido + regression testing + QA approval antes de retorno a servicio GMP",
        "regulatory_basis": "21 CFR 211.68, EU GMP Annex 11 §4, GAMP5 Cat4/5",
    },
    {
        "id": "R002",
        "agent": "integrity",
        "condition_keywords": ["audit trail deshabilitado", "audit trail disabled", "sin audit trail", "no audit trail"],
        "risk": "CRITICAL",
        "action": "Data Integrity CAPA obligatorio + escalación inmediata a QA management + revisión retrospectiva de datos",
        "regulatory_basis": "21 CFR Part 11.10(e), EU GMP Annex 11 §9, FDA DI Guidance 2018",
    },
    {
        "id": "R003",
        "agent": "capa",
        "condition_keywords": ["capa abierto", "capa open", "90 días", "90 days", "sin cierre", "overdue capa"],
        "risk": "HIGH",
        "action": "Escalación obligatoria a management review + justificación documentada + plan de cierre con fecha compromiso",
        "regulatory_basis": "21 CFR 820.100, ICH Q10 Section 3.2, ISO 13485:2016 §8.5.2",
    },
    {
        "id": "R004",
        "agent": "csv",
        "condition_keywords": ["iq incompleto", "iq incomplete", "instalación sin calificar", "sin iq", "no iq"],
        "risk": "MEDIUM",
        "action": "Validation gap — completar IQ antes de OQ/PQ. Sistema no puede procesarse como validado sin IQ aprobado",
        "regulatory_basis": "EU GMP Annex 15, GAMP5, FDA Process Validation Guidance 2011",
    },
    {
        "id": "R005",
        "agent": "csv",
        "condition_keywords": ["21 cfr part 11", "part 11", "firma electrónica", "electronic signature", "sin validar", "not validated"],
        "risk": "CRITICAL",
        "action": "Compliance gap Part 11 — sistema debe estar validado antes de usar firmas electrónicas con valor GMP. Suspender uso hasta validación",
        "regulatory_basis": "21 CFR Part 11, EU GMP Annex 11 §4, FDA Part 11 Guidance 2003",
    },
    {
        "id": "R006",
        "agent": "qa",
        "condition_keywords": ["desviación recurrente", "recurring deviation", "mismo equipo", "same equipment", "reincidencia"],
        "risk": "HIGH",
        "action": "CAPA obligatorio por desviación recurrente. Root cause analysis sistémico requerido. Revisar efectividad de CAPA previo",
        "regulatory_basis": "21 CFR 211.192, ICH Q10 Section 3.2, EU GMP Chapter 1",
    },
    {
        "id": "R007",
        "agent": "integrity",
        "condition_keywords": ["audit trail sin revisar", "audit trail not reviewed", "revisión periódica", "periodic review"],
        "risk": "HIGH",
        "action": "DI finding — audit trail debe revisarse en cada revisión de batch record. Implementar SOP de revisión con evidencia documentada",
        "regulatory_basis": "MHRA DI Guidance 2018, 21 CFR Part 11.10(e), EU GMP Annex 11 §9",
    },
    {
        "id": "R008",
        "agent": "automation",
        "condition_keywords": ["plc", "scada", "cambio sin change control", "change without change control", "modificación no autorizada"],
        "risk": "CRITICAL",
        "action": "GMP violation — cambio en PLC/SCADA sin change control aprobado. Detener operación, documentar estado, iniciar retroactive change control + CAPA",
        "regulatory_basis": "21 CFR 211.100, EU GMP Annex 11 §10, GAMP5, ISA-88",
    },
    {
        "id": "R009",
        "agent": "automation",
        "condition_keywords": ["ebr", "electronic batch record", "batch record electrónico", "sin firma electrónica", "unsigned ebr"],
        "risk": "HIGH",
        "action": "Part 11 gap — eBR requiere firma electrónica válida por persona autorizada. No liberar batch sin firma compliant con Part 11",
        "regulatory_basis": "21 CFR Part 11.50, EU GMP Annex 11 §14, ISA-88",
    },
    {
        "id": "R010",
        "agent": "qa",
        "condition_keywords": ["oos", "out of specification", "fuera de especificación", "sin investigación", "without investigation"],
        "risk": "CRITICAL",
        "action": "Compliance failure — resultado OOS debe investigarse conforme FDA OOS Guidance. No retener, promediar ni ignorar. Batch en cuarentena hasta cierre de investigación",
        "regulatory_basis": "21 CFR 211.192, FDA OOS Guidance 2006, EU GMP Chapter 6",
    },
    {
        "id": "R011",
        "agent": "csv",
        "condition_keywords": ["gamp5 cat4", "gamp 5 category 4", "categoria 4", "configured standard", "sin oq", "no oq"],
        "risk": "HIGH",
        "action": "Validation gap — GAMP5 Cat4 requiere OQ documentado con testing de funciones configuradas. Sistema no puede considerarse validado sin OQ aprobado",
        "regulatory_basis": "GAMP5 4th/5th Ed., EU GMP Annex 11, 21 CFR 211.68",
    },
    {
        "id": "R012",
        "agent": "integrity",
        "condition_keywords": ["backup sin verificar", "backup not verified", "backup no verificado", "30 días", "30 days", "respaldo sin verificación"],
        "risk": "MEDIUM",
        "action": "Data integrity risk — backups deben verificarse periódicamente. Ejecutar verificación inmediata y establecer SOP con frecuencia definida (mínimo mensual)",
        "regulatory_basis": "EU GMP Annex 11 §17, MHRA DI Guidance, 21 CFR Part 11.10(c)",
    },
]


def evaluate_rules(question: str, agent: str) -> list[RuleResult]:
    """
    Keyword matching sobre la pregunta del usuario.
    agent="" o "all" evalúa todas las reglas sin filtro por agente.
    Retorna reglas disparadas ordenadas por severidad (CRITICAL primero).
    """
    q_lower = question.lower()
    triggered: list[RuleResult] = []

    for rule in GMP_RULES:
        if agent and agent not in ("all", "") and rule["agent"] != agent:
            continue
        if any(kw in q_lower for kw in rule["condition_keywords"]):
            triggered.append(
                RuleResult(
                    triggered=True,
                    rule_id=rule["id"],
                    risk_level=rule["risk"],
                    action=rule["action"],
                    regulatory_basis=rule["regulatory_basis"],
                )
            )

    triggered.sort(key=lambda r: SEVERITY_ORDER.get(r.risk_level, 99))
    return triggered


def get_rule_context(rules: list[RuleResult]) -> str:
    """Convierte reglas disparadas en bloque de contexto para el prompt del LLM."""
    if not rules:
        return ""
    lines = ["REGULATORY RULES TRIGGERED:"]
    for r in rules:
        lines.append(f"[{r.rule_id}] {r.risk_level}: {r.action}")
        lines.append(f"  Basis: {r.regulatory_basis}")
    return "\n".join(lines)
