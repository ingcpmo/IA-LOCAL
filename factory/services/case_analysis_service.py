"""
W7 — Análisis de casos regulatorios por agente experto (Fase B).

Extiende el pipeline gobernado de W6.5/W6.5.1 de "documentos del dossier" a
"casos de la memoria regulatoria": el agente que el routing determinista W6.4
ya recomienda analiza UN caso (openFDA) contra una misión concreta; el humano
decide. Diseño y contrato aprobados en docs/W7_FASEA_DISENO_ANALISIS_CASOS.md.

Reglas duras de este módulo (fijadas por test):
  - CERO egreso HTTP propio: no importa httpx; la única llamada LLM va por
    referencia de módulo a dossier_agent_review_service._ollama_generate
    (monkeypatcheable en tests igual que en W6.5). Jamás llama al endpoint de
    aprobación del dossier ni lo nombra.
  - trigger.mode == "manual" único aceptado (403 al resto); principal con
    nombre real (validate_run_by).
  - El caso es el CENTRO del prompt pero sigue siendo EXTERNO: trust=external,
    tope propio MAX_CASE_TARGET_CHARS (1500 — decisión 2 de Fase A; el tope
    600 de W6.5 truncaba el caso real D-0554-2026), sanitizado anti
    marker-forgery. El detalle openFDA NO existe localmente (selective fetch
    W6.3 no persiste): al prompt entra solo el HECHO auditado del fetch.
  - cases.jsonl JAMÁS se escribe. No hay archivo de estado mutable: el estado
    vigente de un análisis es el status del último vNN.json (decisión 3).
  - accept NO toca dossier, documentos ni cases.jsonl: solo marca el registro
    y audita (decisión 5 — vincular análisis al dossier sería aprobación
    futura aparte).
  - Registros versionados inmutables en generación bajo
    regulatory/case_analyses/<project_id>/<case_dir>/vNN.json; la decisión
    humana se ANEXA sin alterar prompt/respuesta.
  - Verificador determinista + verify_v2 (incluye intra_proposal_contradiction
    v2.1) y confianza SIEMPRE computada, igual que W6.5.
"""

import json
import re
from datetime import datetime, timezone

import yaml as _yaml
from fastapi import HTTPException

from factory.services import case_presentation_service as _cases
from factory.services import claim_verifier as _verifier
from factory.services import dossier_agent_review_service as _review
from factory.services import paths
from factory.services import test_console_service as _console
from factory.services import validation_readiness_service as _valready

# Topes de sanitización propios (decisión 2 de Fase A): el caso objetivo y su
# presentación embeben texto openFDA → external; compare/detail_status son
# hechos locales → internal
MAX_CASE_TARGET_CHARS = 1500
MAX_PRESENTATION_CHARS = 1200
MAX_COMPARE_CHARS = 3000
MAX_DETAIL_STATUS_CHARS = 600

# supporting = dominios de revisión recomendados al humano (NO ejecutados);
# qa_oos_profile es el dueño del dominio OOS de la misión
SUPPORTING_BY_PRIMARY = {
    "qa_oos_profile": [],
    "integrity_lims_profile": ["qa_oos_profile"],
    "hplc_data_review_agent": ["qa_oos_profile"],
}

PENDING_STATUS = "agent_analysis_proposed"

_SAFE_DIR_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Persistencia (versionada, inmutable en generación) ───────────────────────

def _case_dir(case_id: str) -> str:
    """openfda_enforcement:D-0554-2026 → openfda_enforcement__D-0554-2026;
    el case_id exacto vive dentro del record."""
    return _SAFE_DIR_RE.sub("__", str(case_id))


def _analyses_dir(project_id: str, case_id: str):
    return paths.CASE_ANALYSES_BASE / project_id / _case_dir(case_id)


def _analysis_path(project_id: str, case_id: str, version: int):
    return _analyses_dir(project_id, case_id) / f"v{version:02d}.json"


def _latest_version(project_id: str, case_id: str) -> int:
    d = _analyses_dir(project_id, case_id)
    return len(list(d.glob("v*.json"))) if d.exists() else 0


def _load_analysis(project_id: str, case_id: str, version: int) -> dict:
    f = _analysis_path(project_id, case_id, version)
    if not f.exists():
        raise HTTPException(404, f"No existe el análisis v{version} del caso "
                                 f"'{case_id}' para '{project_id}'")
    return json.loads(f.read_text(encoding="utf-8"))


def _save_analysis(project_id: str, case_id: str, record: dict) -> None:
    d = _analyses_dir(project_id, case_id)
    d.mkdir(parents=True, exist_ok=True)
    _analysis_path(project_id, case_id, record["version"]).write_text(
        json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")


# ── Prompts gobernados propios (set independiente del dossier) ────────────────

def _load_prompts() -> dict:
    f = paths.CASE_ANALYSIS_PROMPTS_FILE
    if not f.exists():
        raise HTTPException(500, "Archivo de prompts gobernados no encontrado "
                                 "(factory/agent_prompts/case_analysis_prompts.yaml)")
    return _yaml.safe_load(f.read_text(encoding="utf-8")) or {}


# ── Evidencia del prompt (§3 del diseño de Fase A) ────────────────────────────

def _case_stale(case: dict) -> bool:
    consulted = _cases._parse_ts(case.get("consulted_at"))
    days = (case.get("freshness") or {}).get("stale_after_days")
    if not consulted or not days:
        return False
    age = datetime.now(timezone.utc) - consulted
    return age.total_seconds() > float(days) * 86400


def _load_mission_agents(project_id: str) -> list:
    proposal = _cases._load_yaml(
        paths.DESIGNS_BASE / project_id / "agent_design_proposal.yaml")
    if isinstance(proposal, list):
        return [a for a in proposal if isinstance(a, dict)]
    if isinstance(proposal, dict):
        return [a for a in proposal.get("agents", []) if isinstance(a, dict)]
    return []


def _evidence_items(project_id: str, case: dict) -> list:
    """→ [{id, trust, pointer, content}] — el caso objetivo pasa de contexto a
    centro; otros casos de la memoria NO entran (menos superficie injection)."""
    mission = _cases._load_yaml(paths.MISSIONS_DIR / f"{project_id}.yaml") or {}
    pres = case.get("presentation") or {}
    items = [{"id": "mission", "trust": "internal",
              "pointer": f"layer9/missions/{project_id}.yaml",
              "content": json.dumps({
                  "objective": mission.get("objective"),
                  "client_type": mission.get("client_type"),
                  "regulatory_scope": mission.get("regulatory_scope"),
                  "constraints": mission.get("constraints"),
                  "documents": mission.get("documents"),
              }, ensure_ascii=False, indent=1)}]

    agents = _load_mission_agents(project_id)
    if agents:
        items.append({"id": "agents", "trust": "internal",
                      "pointer": f"designs/{project_id}/agent_design_proposal.yaml",
                      "content": "\n".join(
                          f"- {a.get('agent_id')} "
                          f"({'perfil de ' + str(a.get('base_agent')) if a.get('is_inherited') or a.get('decision') == 'profile' else 'agente nuevo'}): "
                          f"{a.get('rationale') or 'sin rationale'}"
                          for a in agents)})

    items.append({"id": "case", "trust": "external",
                  "pointer": f"regulatory/case_memory/cases.jsonl#{case.get('case_id')}",
                  "content": json.dumps({
                      "case_id": case.get("case_id"),
                      "authority": case.get("authority"),
                      "case_type": case.get("case_type"),
                      "classification": case.get("classification"),
                      "recall_status": case.get("recall_status"),
                      "product": case.get("product"),
                      "reason": case.get("reason"),
                      "recalling_firm": case.get("recalling_firm"),
                      "recall_initiation_date": case.get("recall_initiation_date"),
                      "report_date": case.get("report_date"),
                      "tags": case.get("tags"),
                      "summary": case.get("summary"),
                      "content_hash": case.get("content_hash"),
                  }, ensure_ascii=False, indent=1)})

    items.append({"id": "case_presentation", "trust": "external",
                  "pointer": "presentación determinista W6.4 (case_presentation_service)",
                  "content": json.dumps({
                      "executive_summary": pres.get("executive_summary"),
                      "gmp_relevance": (pres.get("gmp_relevance") or {}).get("level"),
                      "citation": pres.get("citation"),
                      "found_by_query": pres.get("found_by_query"),
                  }, ensure_ascii=False, indent=1)})

    detail = pres.get("detail_status") or {}
    items.append({"id": "detail_status", "trust": "internal",
                  "pointer": "audit/factory_audit.jsonl (case_detail_fetched)",
                  "content": f"estado: {detail.get('state')} · "
                             f"fetches del detalle: {detail.get('fetch_count', 0)} · "
                             f"último: {detail.get('last_fetched_at')} · "
                             "NOTA: el detalle openFDA no está persistido "
                             "localmente — solo consta el hecho auditado del fetch"})

    compare = _cases.compare_with_mission(case["case_id"], project_id) or {}
    if not compare.get("error"):
        m, ov = compare.get("mission") or {}, compare.get("overlap") or {}
        items.append({"id": "compare", "trust": "internal",
                      "pointer": f"GET /case-memory/·/compare/{project_id} (informational_only)",
                      "content": json.dumps({
                          "matched_tags": ov.get("matched_tags"),
                          "unmatched_tags": ov.get("unmatched_tags"),
                          "recommended_agent_in_mission": ov.get("recommended_agent_in_mission"),
                          "recommended_agent_tests": ov.get("recommended_agent_tests"),
                          "mission_agents": m.get("agents"),
                          "dossier": m.get("dossier"),
                      }, ensure_ascii=False, indent=1)})

    caps = {"case": MAX_CASE_TARGET_CHARS,
            "case_presentation": MAX_PRESENTATION_CHARS,
            "compare": MAX_COMPARE_CHARS,
            "detail_status": MAX_DETAIL_STATUS_CHARS}
    for it in items:
        cap = caps.get(it["id"], _review.MAX_INTERNAL_CHARS)
        it["content"] = _review._sanitize(it["content"], cap)
    return items


# ── Prompt final (mismo esqueleto que W6.5; tarea de análisis de caso) ────────

def _build_prompt(prompts: dict, primary: str, case: dict, corpus_level: str,
                  items: list, guidance: str | None,
                  prev_response: str | None = None,
                  guidance_ledger: list | None = None) -> tuple[str, str]:
    contract = prompts.get("common_contract") or ""
    agent_prompt = ((prompts.get("prompts") or {}).get(primary) or {}).get("system_prompt")
    if not agent_prompt:
        raise HTTPException(500, f"No hay prompt de análisis gobernado para '{primary}'")

    parts = [contract.replace("{corpus_sufficiency}", corpus_level), agent_prompt,
             f"CASO OBJETIVO: {case.get('case_id')} "
             f"({case.get('classification') or 'sin clasificación'} · "
             f"{case.get('case_type') or 'tipo no declarado'}).",
             "Redacta el ANÁLISIS PROPUESTO del caso en relación con la misión, "
             "con la estructura exacta del contrato; cada afirmación como viñeta "
             "etiquetada."]
    if prev_response is not None:
        revision_contract = prompts.get("revision_contract") or ""
        if not revision_contract.strip():
            raise HTTPException(500, "El set de prompts no define revision_contract "
                                     "(requerido por el gate W6.5.1 para request_changes)")
        template_sha = _review._sha(contract + revision_contract + agent_prompt)
        parts.append(revision_contract)
        parts.append("[RESPUESTA_ANTERIOR INICIO]\n"
                     + _review._sanitize(prev_response, _review.MAX_INTERNAL_CHARS)
                     + "\n[RESPUESTA_ANTERIOR FIN]")
        parts.append("INSTRUCCIONES DE QA (acumuladas, TODAS vigentes a la vez):\n"
                     + "\n".join(f"{n}. {_review._sanitize(g, 1500)}"
                                 for n, g in enumerate(guidance_ledger or [], 1)))
    else:
        template_sha = _review._sha(contract + agent_prompt)
        if guidance:
            parts.append("AJUSTE SOLICITADO POR QA (instrucción humana con prioridad):\n"
                         + _review._sanitize(guidance, 1500))
    parts.append("EVIDENCIA DISPONIBLE — ids citables con [E: <id>]: "
                 + ", ".join(it["id"] for it in items))
    parts.extend(_review._wrap(it["id"], it["trust"], it["content"]) for it in items)
    return "\n\n".join(parts), template_sha


# ── Fallo gobernado (evento propio; el caso y la memoria quedan intactos) ─────

def _fail(project_id: str, case_id: str, agent: str, reason: str, trigger: dict,
          requested_by: str, http_status: int, detail: str):
    from factory.core.audit_writer import write_event
    write_event("case_analysis_failed", project_id, {
        "case_id": case_id, "agent": agent, "reason": reason,
        "trigger": trigger, "requested_by": requested_by,
    })
    raise HTTPException(http_status, {"error": reason, "detail": detail,
                                      "model": _review.OLLAMA_MODEL,
                                      "case_id": case_id})


# ── Generación de análisis ────────────────────────────────────────────────────

def _require_case(case_id: str) -> dict:
    case = _cases.read_case(case_id)
    if case is None:
        raise HTTPException(404, f"Caso '{case_id}' no está en la memoria regulatoria")
    return case


def analyze_case(project_id: str, case_id: str, trigger: dict,
                 guidance: str | None = None,
                 revision_of: int | None = None) -> dict:
    """Genera un análisis propuesto del caso contra la misión. NUNCA escribe en
    cases.jsonl ni en el dossier; ante cualquier fallo la memoria queda intacta.

    revision_of: versión del análisis a revisar — activa el modo revisión
    W6.5.1 (respuesta anterior íntegra + ledger completo + temperatura 0.0)."""
    trigger = trigger or {}
    if trigger.get("mode") != "manual":
        raise HTTPException(403, "W7 solo admite trigger manual: la generación "
                                 "automática gobernada es un gate futuro que requiere "
                                 "TaskSpec aprobado, presupuesto y kill-switch")
    name = _console.validate_run_by(trigger.get("principal") or "")
    _valready.require_mission(project_id)
    case = _require_case(case_id)

    latest = _latest_version(project_id, case_id)
    if latest and revision_of is None:
        prev_status = _load_analysis(project_id, case_id, latest).get("status")
        if prev_status == PENDING_STATUS:
            raise HTTPException(409, f"El análisis v{latest} del caso está pendiente "
                                     "de decisión humana — decide (accept/reject/"
                                     "request_changes) antes de generar otro")

    routing = (case.get("presentation") or {}).get("recommended_agent") or {}
    primary = routing.get("agent_id")
    if not primary:
        raise HTTPException(500, "El routing determinista W6.4 no devolvió agente")
    supporting = SUPPORTING_BY_PRIMARY.get(primary, [])

    mode = "revision" if revision_of else "draft"
    prev_response, ledger = None, ([guidance] if guidance else [])
    if revision_of:
        prev = _load_analysis(project_id, case_id, revision_of)
        prev_response = prev.get("response") or ""
        ledger = _review._guidance_ledger_of(prev) + ([guidance] if guidance else [])

    corpus = _review.corpus_sufficiency(project_id, primary)
    items = _evidence_items(project_id, case)
    prompts_meta = _load_prompts()
    prompt, template_sha = _build_prompt(prompts_meta, primary, case,
                                         corpus["level"], items, guidance,
                                         prev_response=prev_response,
                                         guidance_ledger=ledger if revision_of else None)
    agent_prompt_version = ((prompts_meta.get("prompts") or {}).get(primary) or {}).get("prompt_version")

    # Guard anti-truncado W6.5 (constantes por referencia de módulo)
    est_tokens = len(prompt) // 3 + 128
    budget = _review.NUM_CTX - _review.NUM_PREDICT
    if est_tokens > budget:
        _fail(project_id, case_id, primary, "prompt_too_long", trigger, name, 413,
              f"~{est_tokens} tokens estimados > presupuesto {budget} "
              f"(num_ctx {_review.NUM_CTX} - num_predict {_review.NUM_PREDICT})")

    temperature = (_review.TEMPERATURE_REVISION if mode == "revision"
                   else _review.TEMPERATURE)
    t0 = datetime.now(timezone.utc)
    response, retried = None, False
    for attempt in (1, 2):
        current_prompt = prompt if attempt == 1 else (
            prompt + "\n\nCORRECCIÓN DE FORMATO: tu respuesta anterior no cumplió el "
            "contrato. Cada afirmación DEBE ser una viñeta '- [E: id] ...', '- [SE] ...' "
            "o '- [REF: norma] ...' y DEBE existir la sección final '## Limitaciones'.")
        # errores clasificados con los tipos del módulo W6.5 (referencia de
        # módulo: este archivo no importa httpx — regla estructural)
        try:
            data = _review._ollama_generate(current_prompt, temperature)
        except _review.httpx.ConnectError as e:
            _fail(project_id, case_id, primary, "ollama_unreachable", trigger, name, 503, str(e))
        except _review.httpx.TimeoutException as e:
            _fail(project_id, case_id, primary, "ollama_timeout", trigger, name, 504, str(e))
        except Exception as e:
            _fail(project_id, case_id, primary, "ollama_error", trigger, name, 502, str(e))
        response = data.get("response", "")
        if _review._format_valid(_review._parse_claims(response), response):
            break
        if attempt == 1:
            retried = True
    latency_ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)

    claims = _review._parse_claims(response)
    format_ok = _review._format_valid(claims, response)
    verified = _review._verify_claims(claims, items)
    counts = _review._claims_summary(verified)
    flags = _review._output_flags(response)
    if counts["unsupported"] > 0:
        flags.append("unsupported_claims")
    mission = _cases._load_yaml(paths.MISSIONS_DIR / f"{project_id}.yaml") or {}
    grants = _verifier.parse_reference_grants(
        list(corpus["available"]) + list(corpus["pending"])
        + list(mission.get("regulatory_scope") or []))
    v2 = _verifier.verify_v2(response, verified, items, grants)
    flags.extend(f for f in v2["flags"] if f not in flags)
    stale = _case_stale(case)
    if stale and "stale_case" not in flags:
        flags.append("stale_case")   # se declara, no bloquea (anti-optimismo)
    confidence = _review._confidence(corpus["level"], counts, flags)

    version = _latest_version(project_id, case_id) + 1
    record = {
        "project_id": project_id, "case_id": case_id, "version": version,
        "status": PENDING_STATUS if format_ok else "format_invalid",
        "case_ref": {"case_id": case_id,
                     "content_hash": case.get("content_hash"),
                     "classification": case.get("classification"),
                     "consulted_at": case.get("consulted_at"),
                     "stale": stale},
        "routing": {"agent_id": primary,
                    "reason": routing.get("reason"),
                    "deterministic": True},
        "agent": {"primary": primary, "supporting": supporting,
                  "supporting_note": "dominios de revisión recomendados para el "
                                     "revisor humano (no ejecutados en W7)"},
        "model": {"name": _review.OLLAMA_MODEL,
                  "options": {"num_predict": _review.NUM_PREDICT,
                              "temperature": temperature,
                              "num_ctx": _review.NUM_CTX}},
        "prompt": {"set_version": prompts_meta.get("prompt_set_version"),
                   "agent_prompt_version": agent_prompt_version,
                   "template_sha256": template_sha,
                   "rendered_sha256": _review._sha(prompt)},
        "corpus_sufficiency": corpus,
        "evidence_sources": [{"id": it["id"], "trust": it["trust"], "pointer": it["pointer"]}
                             for it in items],
        "claims": {**counts, "detail": verified},
        "verifier": {"version": v2["version"], "findings": v2["findings"]},
        "revision": {"mode": mode, "based_on_version": revision_of,
                     "guidance_ledger": ledger},
        "confidence": confidence,
        "flags": flags,
        "response": response,
        "governance": {"trigger": trigger, "requested_by": name,
                       "guidance": guidance, "prompt_full": prompt,
                       "generated_at": _now(), "latency_ms": latency_ms,
                       "format_retry": retried},
        "decision": None,
        "regulatory_note": "ANÁLISIS PROPUESTO POR AGENTE — informativo, sin "
                           "valor regulatorio: NO es evaluación de impacto GMP "
                           "ni disposición; requiere revisión humana QA.",
    }
    _save_analysis(project_id, case_id, record)

    from factory.core.audit_writer import write_event
    if not format_ok:
        write_event("case_analysis_failed", project_id, {
            "case_id": case_id, "agent": primary, "reason": "format_invalid",
            "trigger": trigger, "requested_by": name, "version": version,
            "mode": mode, "based_on_version": revision_of,
        })
        return {"project_id": project_id, "case_id": case_id, "version": version,
                "status": "format_invalid", "mode": mode,
                "confidence": confidence, "flags": flags}

    write_event("case_analysis_generated", project_id, {
        "case_id": case_id, "version": version,
        "case_content_hash": case.get("content_hash"),
        "agent_primary": primary, "agent_supporting": supporting,
        "routing_agent": primary,
        "model": _review.OLLAMA_MODEL,
        "prompt_set_version": record["prompt"]["set_version"],
        "prompt_version": agent_prompt_version,
        "template_sha256": template_sha,
        "rendered_sha256": record["prompt"]["rendered_sha256"],
        "response_sha256": _review._sha(response),
        "corpus_sufficiency": corpus["level"],
        "claims": counts, "confidence": confidence, "flags": flags,
        "mode": mode, "based_on_version": revision_of,
        "guidance_ledger_sha256": [_review._sha(g) for g in ledger],
        "trigger": trigger, "requested_by": name,
    })
    return {"project_id": project_id, "case_id": case_id, "version": version,
            "status": PENDING_STATUS, "agent": record["agent"],
            "mode": mode, "corpus_sufficiency": corpus["level"],
            "claims": counts, "confidence": confidence, "flags": flags}


# ── Lectura (nunca audita) ────────────────────────────────────────────────────

def read_analysis(project_id: str, case_id: str, version: int | None = None) -> dict:
    """Read-only: análisis completo con gobierno. NUNCA audita. Sin version →
    el último (que define el estado vigente del par caso×misión)."""
    _valready.require_mission(project_id)
    _require_case(case_id)
    if version is None:
        version = _latest_version(project_id, case_id)
        if not version:
            raise HTTPException(404, f"El caso '{case_id}' no tiene análisis "
                                     f"para '{project_id}'")
    return _load_analysis(project_id, case_id, version)


# ── Decisión humana (jamás toca dossier ni cases.jsonl) ───────────────────────

def decide_analysis(project_id: str, case_id: str, decision: str,
                    decided_by: str, reason: str | None = None) -> dict:
    """accept | reject | request_changes — siempre acto humano con nombre real.
    accept SOLO marca el registro y audita (decisión 5 de Fase A): el análisis
    aceptado no entra a ningún documento GMP."""
    name = _console.validate_run_by(decided_by)
    if decision not in _review.VALID_DECISIONS:
        raise HTTPException(422, f"decision debe ser una de {_review.VALID_DECISIONS}")
    if decision in ("reject", "request_changes") and not (reason or "").strip():
        raise HTTPException(422, f"'{decision}' exige reason: motivo del rechazo o "
                                 "instrucción de ajuste para el agente")
    _valready.require_mission(project_id)
    version = _latest_version(project_id, case_id)
    if not version:
        raise HTTPException(409, f"El caso '{case_id}' no tiene análisis que decidir")
    record = _load_analysis(project_id, case_id, version)
    if record.get("status") != PENDING_STATUS:
        raise HTTPException(409, f"El análisis v{version} está en "
                                 f"'{record.get('status')}' — solo "
                                 f"{PENDING_STATUS} admite decisión")

    new_status = {"accept": "accepted", "reject": "rejected",
                  "request_changes": "changes_requested"}[decision]
    record["status"] = new_status
    record["decision"] = {"decision": decision, "decided_by": name,
                          "decided_at": _now(), "reason": reason}
    _save_analysis(project_id, case_id, record)

    from factory.core.audit_writer import write_event
    write_event("case_analysis_decision", project_id, {
        "case_id": case_id, "analysis_version": version, "decision": decision,
        "decided_by": name, "reason": reason, "new_status": new_status,
    })

    out = {"project_id": project_id, "case_id": case_id, "decision": decision,
           "analysis_version": version, "decided_by": name,
           "analysis_status": new_status}

    if decision == "request_changes":
        # nueva versión en MODO REVISIÓN (W6.5.1): respuesta anterior íntegra +
        # ledger completo + temperatura 0.0; genera su propio evento
        regen = analyze_case(project_id, case_id,
                             {"mode": "manual", "principal": name,
                              "authorization_ref": None}, guidance=reason,
                             revision_of=version)
        out["new_analysis"] = regen
    return out
