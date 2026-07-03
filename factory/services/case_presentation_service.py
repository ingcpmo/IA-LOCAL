"""
W6.4 — Capa de presentación de la Regulatory Case Memory: interpretación
primero, evidencia técnica después.

Enriquece cada case record (cases.jsonl, W6.3) con un bloque `presentation`
calculado de forma DETERMINISTA a partir de datos ya guardados localmente:
resumen ejecutivo, relevancia GMP derivada de la clasificación FDA, agente
recomendado con motivo, cita trazable, query de origen y estado del detalle.

Reglas duras de este módulo:
  - SOLO lectura local (cases.jsonl + factory_audit.jsonl vía paths). NUNCA
    escribe, NUNCA audita, NUNCA hace HTTP externo (no importa httpx ni
    audit_writer a propósito — test estructural lo fija).
  - Nada de lo calculado es juicio GMP: relevancia = mapeo fijo de la
    clasificación FDA; routing de agente = mapa determinista de señales
    (mismo patrón que GMP_TAG_MAP de W6.3). Todo bloque lleva
    deterministic=True y la nota de revisión humana.
  - cases.jsonl es append-only sagrado: la correlación query↔caso de los
    casos previos a W6.4 se resuelve en LECTURA contra los eventos
    regulatory_query_executed de la auditoría — el archivo no se reescribe.
    Correlación ambigua → found_by_query None, nunca se inventa.
  - La comparación con misión es INFORMATIVA (informational_only=True,
    gmp_decision=False): cruza tags/agentes/pruebas/dossier ya locales y
    jamás aprueba ni escribe nada.
"""

import json
from datetime import datetime

import yaml as _yaml

from factory.services import paths

# Ventana de correlación query↔caso contra la auditoría (casos pre-W6.4):
# el evento se escribe milisegundos después de consulted_at; 300s da margen
# sin arriesgar cruces entre consultas distintas (60s mínimo entre llamadas).
QUERY_MATCH_WINDOW_S = 300

# Relevancia GMP derivada SOLO de la clasificación FDA (Class I = riesgo
# serio para la salud). No usa tags ni texto: un test fija esta regla.
RELEVANCE_BY_CLASSIFICATION = {
    "Class I": "alta",
    "Class II": "media",
    "Class III": "baja",
}

# Routing determinista caso→agente. Señales evaluadas en orden de
# especificidad sobre razón+resumen+tags; default = qa_oos_profile porque
# todo recall/desviación de especificación cae en el dominio OOS del perfil
# (factory/profiles/qa_profiles.yaml, cobertura 80%).
AGENT_ROUTING = [
    ("integrity_lims_profile",
     ("data integrity", "audit trail", "falsif", "alcoa", "lims",
      "electronic record", "incomplete record", "recordkeeping"),
     "Señales de integridad de datos/registros (ALCOA+, Part 11, 211.68) — "
     "dominio del perfil integrity_lims_profile."),
    ("hplc_data_review_agent",
     ("hplc", "chromatograph", "sst", "rsd", "peak integration",
      "system suitability", "assay fail", "analytical test"),
     "Señales analíticas/cromatográficas (USP <621>, revisión de datos "
     "crudos) — dominio del agente hplc_data_review_agent."),
]
DEFAULT_AGENT = (
    "qa_oos_profile",
    "Recall/desviación de especificación — dominio de investigación OOS "
    "21 CFR 211.192 del perfil qa_oos_profile (default para drug_recall).")

NOT_GMP_JUDGMENT = ("clasificación determinista de presentación — NO es "
                    "juicio GMP; requiere revisión humana QA/QC")


# ── Lectura local de auditoría (read-only, jamás escribe) ─────────────────────

def _read_audit_events(event_types: set) -> list:
    events = []
    if not paths.AUDIT_FILE.exists():
        return events
    for raw in paths.AUDIT_FILE.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(raw)
        except Exception:
            continue
        if e.get("event_type") in event_types:
            events.append(e)
    return events


def _parse_ts(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _build_context() -> dict:
    """Índices de auditoría construidos UNA vez por lectura de la memoria:
    queries (para correlar found_by_query) y fetches por case_id."""
    events = _read_audit_events({"regulatory_query_executed", "case_detail_fetched"})
    queries, fetches = [], {}
    for e in events:
        ts = _parse_ts(e.get("timestamp"))
        data = e.get("data") or {}
        if e["event_type"] == "regulatory_query_executed" and ts:
            queries.append((ts, data.get("search_term")))
        elif e["event_type"] == "case_detail_fetched":
            cid = data.get("case_id")
            if cid:
                f = fetches.setdefault(cid, {"count": 0, "last_at": None})
                f["count"] += 1
                f["last_at"] = e.get("timestamp")
    return {"queries": queries, "fetches": fetches}


# ── Piezas deterministas del bloque presentation ──────────────────────────────

def _relevance(case: dict) -> dict:
    level = RELEVANCE_BY_CLASSIFICATION.get(case.get("classification"))
    return {"level": level, "derived_from": "FDA classification",
            "deterministic": True, "note": NOT_GMP_JUDGMENT}


def _recommend_agent(case: dict) -> dict:
    haystack = " ".join([
        str(case.get("reason", "")), str(case.get("summary", "")),
        " ".join(map(str, case.get("tags", []) or [])),
    ]).lower()
    agent_id, reason = DEFAULT_AGENT
    for candidate, signals, why in AGENT_ROUTING:
        if any(s in haystack for s in signals):
            agent_id, reason = candidate, why
            break
    return {"agent_id": agent_id, "reason": reason,
            "deterministic": True, "note": NOT_GMP_JUDGMENT}


def _executive_summary(case: dict) -> str:
    firm = case.get("recalling_firm") or "Firma no declarada"
    product = (case.get("product") or "producto no descrito")[:90]
    reason = (case.get("reason") or "razón no declarada")[:160]
    cls = case.get("classification") or "sin clasificación FDA"
    status = case.get("recall_status") or "estado no declarado"
    level = RELEVANCE_BY_CLASSIFICATION.get(case.get("classification"))
    rel = f" · relevancia GMP {level}" if level else ""
    return (f"{firm} retiró del mercado «{product}» por: {reason}. "
            f"{cls}{rel}. Estado del retiro: {status}.")


def _found_by_query(case: dict, ctx: dict) -> str | None:
    """Casos W6.4+ traen found_by_query persistido. Para casos previos se
    correla consulted_at con los eventos de consulta auditados; si en la
    ventana hay 0 o >1 términos distintos, se devuelve None (no se inventa)."""
    if case.get("found_by_query"):
        return case["found_by_query"]
    consulted = _parse_ts(case.get("consulted_at"))
    if not consulted:
        return None
    terms = {term for ts, term in ctx["queries"]
             if term and abs((ts - consulted).total_seconds()) <= QUERY_MATCH_WINDOW_S}
    return terms.pop() if len(terms) == 1 else None


def _detail_status(case: dict, ctx: dict) -> dict:
    f = ctx["fetches"].get(case.get("case_id"), {"count": 0, "last_at": None})
    state = "detail_fetched_not_persisted" if f["count"] else "light_memory_only"
    return {
        "state": state,
        "fetch_count": f["count"],
        "last_fetched_at": f["last_at"],
        "snapshot": {"supported": False,
                     "note": "snapshot persistido no existe — requiere aprobación futura"},
    }


def _citation(case: dict, query: str | None) -> str:
    return (f"{case.get('authority', '—')} Drug Enforcement Report — "
            f"{case.get('case_id', '—')} ({case.get('classification') or 'sin clasificación'}). "
            f"Consultado {case.get('consulted_at', '—')} vía {case.get('url', '—')}. "
            f"Query: {('«' + query + '»') if query else 'no registrada (caso pre-W6.4)'}. "
            f"Integridad: {case.get('content_hash', '—')}.")


# ── API del módulo ────────────────────────────────────────────────────────────

def enrich_case(case: dict, ctx: dict | None = None) -> dict:
    """Devuelve el case record + bloque `presentation`. Solo cómputo local."""
    ctx = ctx or _build_context()
    query = _found_by_query(case, ctx)
    case["presentation"] = {
        "executive_summary": _executive_summary(case),
        "gmp_relevance": _relevance(case),
        "recommended_agent": _recommend_agent(case),
        "found_by_query": query,
        "detail_status": _detail_status(case, ctx),
        "citation": _citation(case, query),
        "deterministic": True,
        "note": NOT_GMP_JUDGMENT,
    }
    return case


def enrich_cases(cases: list) -> list:
    ctx = _build_context()   # auditoría leída UNA vez para toda la lista
    return [enrich_case(c, ctx) for c in cases]


def read_case(case_id: str) -> dict | None:
    """Un caso enriquecido por case_id (última aparición gana). None si no está."""
    found = None
    if paths.CASE_MEMORY_FILE.exists():
        for raw in paths.CASE_MEMORY_FILE.read_text(encoding="utf-8").splitlines():
            try:
                c = json.loads(raw)
            except Exception:
                continue
            if c.get("case_id") == case_id:
                found = c
    return enrich_case(found) if found else None


# ── Comparación informativa con una misión (read-only, jamás decide) ──────────

def _load_yaml(path):
    if not path.exists():
        return None
    try:
        return _yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def compare_with_mission(case_id: str, project_id: str) -> dict | None:
    """Cruza un caso de la memoria con una misión: tags vs alcance/objetivo,
    agente recomendado vs agentes diseñados, pruebas y estado del dossier.
    SOLO hechos locales — el veredicto es siempre de QA/QC humano."""
    case = read_case(case_id)
    if case is None:
        return None
    mission = _load_yaml(paths.MISSIONS_DIR / f"{project_id}.yaml")
    if not isinstance(mission, dict):
        return {"error": "mission_not_found", "project_id": project_id}

    # Agentes diseñados de la misión (design proposal de Capa 8)
    proposal = _load_yaml(paths.DESIGNS_BASE / project_id / "agent_design_proposal.yaml")
    mission_agents = []
    if isinstance(proposal, list):
        mission_agents = [a.get("agent_id") for a in proposal
                          if isinstance(a, dict) and a.get("agent_id")]
    elif isinstance(proposal, dict):
        mission_agents = [a.get("agent_id") for a in proposal.get("agents", [])
                          if isinstance(a, dict) and a.get("agent_id")]

    # Pruebas funcionales del catálogo W4
    catalog = _load_yaml(paths.TEST_CATALOGS_DIR / f"{project_id}.yaml") or {}
    tests_by_agent = {a.get("agent_id"): len(a.get("tests", []) or [])
                      for a in (catalog.get("agents", []) or [])
                      if isinstance(a, dict)}

    # Dossier CSV (W6.2) — solo conteos, jamás toca aprobaciones.
    # documents es dict {doc_id: {status,...}} en el formato real de W6.2;
    # se acepta lista por robustez.
    dossier = _load_yaml(paths.VALIDATION_BASE / project_id / "dossier.yaml") or {}
    docs = dossier.get("documents") or {}
    entries = list(docs.values()) if isinstance(docs, dict) else list(docs)
    dossier_summary = {
        "exists": bool(dossier),
        "total_docs": len(entries),
        "approved": sum(1 for d in entries if isinstance(d, dict)
                        and d.get("status") == "approved"),
    }

    # Coincidencias de tags GMP del caso contra el texto de la misión y sus pruebas
    mission_text = " ".join([
        str(mission.get("objective", "")),
        " ".join(map(str, mission.get("regulatory_scope", []) or [])),
        json.dumps(catalog, ensure_ascii=False, default=str),
    ]).lower()
    tags = [str(t) for t in (case.get("tags") or [])]
    matched_tags = [t for t in tags if t.lower() in mission_text]

    recommended = case["presentation"]["recommended_agent"]["agent_id"]
    return {
        "informational_only": True,
        "gmp_decision": False,
        "note": ("comparación informativa de datos locales — no es análisis "
                 "GMP ni recomendación de disposición; revisión humana QA/QC"),
        "case_id": case_id,
        "project_id": project_id,
        "case": {
            "tags": tags,
            "classification": case.get("classification"),
            "case_type": case.get("case_type"),
            "recommended_agent": recommended,
        },
        "mission": {
            "objective": str(mission.get("objective", ""))[:400],
            "client_type": mission.get("client_type"),
            "regulatory_scope": mission.get("regulatory_scope", []) or [],
            "agents": mission_agents,
            "tests_by_agent": tests_by_agent,
            "dossier": dossier_summary,
        },
        "overlap": {
            "matched_tags": matched_tags,
            "unmatched_tags": [t for t in tags if t not in matched_tags],
            "recommended_agent_in_mission": recommended in mission_agents,
            "recommended_agent_tests": tests_by_agent.get(recommended, 0),
        },
    }
