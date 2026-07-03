"""
W6.5 — Agent Expert Review & Drafting para el dossier CSV/GAMP 5.

Los agentes expertos de la solución REDACTAN PROPUESTAS de análisis técnico
para documentos en needs_human_review, con evidencia real citada y verificada.
El humano acepta, rechaza o pide ajuste; solo el humano aprueba (endpoint
existente de W6.2 — este módulo jamás lo toca).

Reglas duras de este módulo (fijadas por test):
  - Único egreso HTTP permitido: Ollama (_ollama_generate, monkeypatcheable).
    NUNCA aprueba: la palabra clave del endpoint de aprobación no aparece aquí.
  - trigger.mode == "manual" es el único aceptado en W6.5 (403 al resto); el
    esquema trigger {mode, principal, authorization_ref} queda listo para
    generación automática gobernada futura SIN cambiar auditoría ni firmas.
  - Elegibles: solo docs en needs_human_review | agent_proposed con routing
    declarado en DOC_ROUTING. missing_evidence/draft/approved → 422.
  - Toda evidencia va envuelta en marcadores canónicos, sanitizada (anti
    marker-forgery, control chars, topes de longitud); lo de origen externo
    (memoria regulatoria openFDA) se marca trust=external: dato, no instrucción.
  - Verificador determinista de afirmaciones: supported | partially_supported
    | unsupported | unverifiable. Nunca reescribe el texto del agente.
  - Confianza SIEMPRE computada (corpus × claims), jamás autodeclarada.
  - Ante fallo (Ollama caído, formato inválido) el documento queda intacto y
    el fallo se audita (dossier_agent_proposal_failed).
  - accept ≠ approve: accept incorpora el bloque marcado al .md, recalcula
    content_sha256 y deja el doc en needs_human_review para aprobación humana.
  - Propuestas versionadas e inmutables en generación bajo
    validation/<pid>/agent_proposals/<doc_id>/vNN.json; la decisión humana se
    anexa al registro sin alterar prompt/respuesta generados.
"""

import hashlib
import json
import os
import re
from datetime import datetime, timezone

import httpx
import yaml as _yaml
from fastapi import HTTPException

from factory.services import case_presentation_service as _cases
from factory.services import dossier_generator_service as _dossier
from factory.services import paths
from factory.services import test_console_service as _console
from factory.services import validation_readiness_service as _valready

# ── Gobierno Ollama (env de factory-api; registrado en cada propuesta) ────────
OLLAMA_BASE_URL = os.getenv("FACTORY_OLLAMA_BASE_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("FACTORY_OLLAMA_MODEL", "mistral:7b-instruct-q4_K_M")
NUM_PREDICT = 1024
TEMPERATURE = 0.2
TIMEOUT_READ_S = 120.0

# Topes de longitud del sanitizador (defensa injection §7 del diseño)
MAX_INTERNAL_CHARS = 6000
MAX_EXTERNAL_CHARS = 600
MAX_CASES_IN_CONTEXT = 3

VALID_DECISIONS = ("accept", "reject", "request_changes")

# ── Routing doc → agente (primary, [supporting]) — tabla fijada por test ──────
# W6.5 ejecuta SOLO el primary (una llamada LLM); supporting se muestra al
# revisor humano como "dominios de revisión recomendados". Docs facts y
# missing_evidence no tienen routing a propósito.
DOC_ROUTING = {
    "intended_use": ("qa_oos_profile", []),
    "gxp_impact_assessment": ("qa_oos_profile", []),
    "system_risk_assessment": ("qa_oos_profile",
                               ["integrity_lims_profile", "hplc_data_review_agent"]),
    "supplier_ai_model_assessment": ("qa_oos_profile", []),
    "data_integrity_assessment": ("integrity_lims_profile", ["qa_oos_profile"]),
    "part11_assessment": ("integrity_lims_profile", []),
    "alcoa_plus_assessment": ("integrity_lims_profile", ["qa_oos_profile"]),
    "test_strategy": ("qa_oos_profile", ["hplc_data_review_agent"]),
    "validation_summary_report": ("qa_oos_profile", ["integrity_lims_profile"]),
    "sop_suggested": ("qa_oos_profile", []),
    "retirement_plan": ("qa_oos_profile", ["integrity_lims_profile"]),
}

ELIGIBLE_STATES = {"needs_human_review", "agent_proposed"}

# Afirmaciones etiquetadas del contrato de salida:  - [E: id] / - [SE] / - [REF: norma]
CLAIM_RE = re.compile(r"^\s*[-*]\s*\[(E:\s*(?P<pointer>[^\]]+)|SE|REF:\s*(?P<ref>[^\]]*))\]\s*(?P<text>.+)$")
# Anclas verificables dentro de una afirmación [E:]: ids en mayúsculas y cifras
ANCHOR_RE = re.compile(r"\b[A-Z][A-Z0-9_-]{1,}\b|\b\d[\d.,:%]*\b")
# Acrónimos de dominio sin valor de anclaje (aparecen en cualquier texto GMP)
STOP_ANCHORS = frozenset({
    "QA", "QC", "GMP", "GXP", "FDA", "CFR", "USP", "OOS", "HPLC", "ALCOA",
    "CSV", "CSA", "GAMP", "API", "IA", "AI", "SST", "RSD", "LIMS", "UTC",
    "SHA", "SHA-256", "REF", "SE", "OK", "SOP", "URS", "FRS", "LLM",
})
DECISION_LANGUAGE_RE = re.compile(
    r"(?i)\b(se aprueba|apruebo|queda aprobado|se libera|libero el lote|"
    r"lote liberado|se cierra la desviaci|cierro la desviaci)\w*\b")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── Prompts gobernados (configuración GxP versionada) ─────────────────────────

def _load_prompts() -> dict:
    f = paths.AGENT_PROMPTS_FILE
    if not f.exists():
        raise HTTPException(500, "Archivo de prompts gobernados no encontrado "
                                 "(factory/agent_prompts/dossier_review_prompts.yaml)")
    return _yaml.safe_load(f.read_text(encoding="utf-8")) or {}


# ── Gate corpus_sufficiency (determinista, desde declaraciones existentes) ────

def corpus_sufficiency(project_id: str, agent_id: str) -> dict:
    """sufficient | partial | insufficient — desde factory/profiles/*.yaml
    (perfiles) o designs/<pid>/agent_design_proposal.yaml (agentes nuevos).
    Nunca bloquea la generación: declara la limitación y limita la confianza."""
    available, pending, source = [], [], None

    profiles_dir = paths.PROFILES_DIR
    if profiles_dir.exists():
        for f in sorted(profiles_dir.glob("*_profiles.yaml")):
            try:
                data = _yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            profile = (data.get("profiles") or data).get(agent_id)
            if isinstance(profile, dict):
                available = profile.get("corpus_available") or []
                pending = profile.get("corpus_pending") or []
                source = f"profiles/{f.name}"
                break

    if source is None:
        design = paths.DESIGNS_BASE / project_id / "agent_design_proposal.yaml"
        if design.exists():
            try:
                data = _yaml.safe_load(design.read_text(encoding="utf-8")) or {}
                for a in data.get("agents") or []:
                    if a.get("agent_id") == agent_id:
                        available = a.get("corpus_available") or []
                        pending = a.get("corpus_pending") or []
                        source = f"designs/{project_id}/agent_design_proposal.yaml"
                        break
            except Exception:
                pass

    if not available:
        level = "insufficient"
    elif pending:
        level = "partial"
    else:
        level = "sufficient"
    return {"level": level, "available": available, "pending": pending,
            "source": source or "sin declaración de corpus"}


# ── Sanitización y envoltura canónica de evidencia (defensa injection) ────────

def _sanitize(text: str, max_chars: int) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(text))
    # anti marker-forgery: la evidencia no puede abrir/cerrar bloques EVIDENCIA
    text = text.replace("[EVIDENCIA", "(EVIDENCIA")
    return text[:max_chars]


def _wrap(eid: str, trust: str, content: str) -> str:
    return f"[EVIDENCIA {eid} trust={trust} INICIO]\n{content}\n[EVIDENCIA {eid} FIN]"


def _relevant_cases(primary_agent: str) -> list:
    """Casos de memoria regulatoria cuyo routing determinista W6.4 apunta al
    agente primario. Solo lectura local; contenido tratado como EXTERNO."""
    f = paths.CASE_MEMORY_FILE
    if not f.exists():
        return []
    out = []
    for raw in f.read_text(encoding="utf-8").splitlines():
        try:
            case = json.loads(raw)
        except Exception:
            continue
        routed = _cases._recommend_agent(case).get("agent_id")
        if routed == primary_agent:
            out.append(case)
    return out[:MAX_CASES_IN_CONTEXT]


def _evidence_items(project_id: str, doc_id: str, bundle: dict, primary: str) -> list:
    """→ [{id, trust, pointer, content}] — ids = whitelist citables con [E: id]."""
    items = []
    m = bundle["mission"]
    items.append({"id": "mission", "trust": "internal",
                  "pointer": f"layer9/missions/{project_id}.yaml",
                  "content": json.dumps({
                      "objective": m.get("objective"),
                      "client_type": m.get("client_type"),
                      "regulatory_scope": m.get("regulatory_scope"),
                      "constraints": m.get("constraints"),
                      "documents": m.get("documents"),
                  }, ensure_ascii=False, indent=1)})
    if bundle["agents"]:
        items.append({"id": "agents", "trust": "internal",
                      "pointer": f"designs/{project_id}/agent_design_proposal.yaml",
                      "content": "\n".join(
                          f"- {a.get('agent_id')} "
                          f"({'perfil de ' + str(a.get('base_agent')) if a.get('is_inherited') or a.get('decision') == 'profile' else 'agente nuevo'}): "
                          f"{a.get('rationale') or 'sin rationale'}"
                          for a in bundle["agents"])})
    if bundle["catalog"]:
        cat = bundle["catalog"]
        lines = [f"catalog_version: {cat.get('catalog_version')}"]
        for ag in cat.get("agents", []):
            for t in ag.get("tests", []):
                lines.append(f"- {t.get('test_id')} · {ag.get('agent_id')} · "
                             f"{t.get('title') or ''} · {t.get('endpoint')}")
        items.append({"id": "catalog", "trust": "internal",
                      "pointer": f"test_catalogs/{project_id}.yaml",
                      "content": "\n".join(lines)})
    if bundle["runs"]:
        last = _dossier._last_run_by_test(bundle)
        items.append({"id": "runs", "trust": "internal",
                      "pointer": f"test_results/{project_id}.jsonl",
                      "content": f"ejecuciones registradas: {len(bundle['runs'])}\n" + "\n".join(
                          f"- {tid}: {r['result']} · por {r['run_by']} · {r['run_at']}"
                          for tid, r in sorted(last.items()))})
    if bundle["rc_canonical"]:
        rc = bundle["rc_canonical"]
        items.append({"id": "rc", "trust": "internal",
                      "pointer": "release_candidates/·/rc_manifest.json",
                      "content": f"rc_id: {rc.get('rc_id')} · status: {rc.get('status')} · "
                                 f"created_at: {rc.get('created_at')}"})
    dep = (bundle["summary"].get("deployment") or {})
    if dep.get("exists"):
        items.append({"id": "deployment", "trust": "internal",
                      "pointer": "deployments/ + port_registry + /health",
                      "content": f"api_port: {dep.get('api_port')} · "
                                 f"health_ok: {dep.get('health_ok')}"})
    if bundle["audit_events"]:
        tail = bundle["audit_events"][-10:]
        items.append({"id": "audit", "trust": "internal",
                      "pointer": "audit/factory_audit.jsonl (cadena SHA-256)",
                      "content": f"eventos de la misión: {len(bundle['audit_events'])} · últimos:\n"
                      + "\n".join(f"- {e['timestamp']} · {e['event_type']}"
                                  + (f" · por {e['by']}" if e["by"] else "") for e in tail)})

    doc_file = paths.VALIDATION_BASE / project_id / "documents" / f"{doc_id}.md"
    if doc_file.exists():
        items.append({"id": "doc_actual", "trust": "internal",
                      "pointer": f"validation/{project_id}/documents/{doc_id}.md",
                      "content": doc_file.read_text(encoding="utf-8")})

    for case in _relevant_cases(primary):
        items.append({"id": f"case:{case.get('case_id')}", "trust": "external",
                      "pointer": f"regulatory/case_memory/cases.jsonl#{case.get('case_id')}",
                      "content": f"{case.get('classification')} · {case.get('product')} · "
                                 f"razón: {case.get('reason')} · resumen: {case.get('summary')}"})

    for it in items:
        cap = MAX_EXTERNAL_CHARS if it["trust"] == "external" else MAX_INTERNAL_CHARS
        it["content"] = _sanitize(it["content"], cap)
    return items


# ── Prompt final ──────────────────────────────────────────────────────────────

def _build_prompt(prompts: dict, primary: str, doc_id: str, corpus_level: str,
                  items: list, guidance: str | None) -> tuple[str, str]:
    """→ (prompt_final, template_sha256). El template es contrato+prompt del
    agente SIN evidencia (reproducibilidad: qué configuración GxP se usó)."""
    contract = prompts.get("common_contract") or ""
    agent_prompt = ((prompts.get("prompts") or {}).get(primary) or {}).get("system_prompt")
    if not agent_prompt:
        raise HTTPException(500, f"No hay prompt experto gobernado para '{primary}'")
    template_sha = _sha(contract + agent_prompt)

    parts = [contract.replace("{corpus_sufficiency}", corpus_level), agent_prompt,
             f"DOCUMENTO OBJETIVO: {_dossier._TITLES[doc_id]} ({doc_id}).",
             "Redacta el ANÁLISIS PROPUESTO para las secciones del documento actual "
             "(bloque de evidencia doc_actual) marcadas como juicio pendiente "
             "(\"SIN EVIDENCIA — requiere aporte humano\"). Una subsección `###` por "
             "sección analizada; cada afirmación como viñeta etiquetada."]
    if guidance:
        parts.append("AJUSTE SOLICITADO POR QA (instrucción humana con prioridad):\n"
                     + _sanitize(guidance, 1500))
    parts.append("EVIDENCIA DISPONIBLE — ids citables con [E: <id>]: "
                 + ", ".join(it["id"] for it in items))
    parts.extend(_wrap(it["id"], it["trust"], it["content"]) for it in items)
    return "\n\n".join(parts), template_sha


# ── Ollama (único egreso HTTP del módulo; monkeypatcheable en tests) ──────────

def _ollama_generate(prompt: str) -> dict:
    r = httpx.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
              "options": {"num_predict": NUM_PREDICT, "temperature": TEMPERATURE}},
        timeout=httpx.Timeout(connect=5.0, read=TIMEOUT_READ_S, write=10.0, pool=5.0))
    r.raise_for_status()
    return r.json()


# ── Verificador determinista de afirmaciones (nunca reescribe el texto) ───────

def _parse_claims(response: str) -> list:
    claims = []
    for line in response.splitlines():
        mt = CLAIM_RE.match(line)
        if not mt:
            continue
        raw_tag = mt.group(1)
        if raw_tag.startswith("E:"):
            tag, pointer = "E", (mt.group("pointer") or "").strip()
        elif raw_tag.startswith("REF"):
            tag, pointer = "REF", (mt.group("ref") or "").strip()
        else:
            tag, pointer = "SE", None
        claims.append({"tag": tag, "pointer": pointer, "text": mt.group("text").strip()})
    return claims


def _anchors(text: str) -> list:
    out = []
    for a in ANCHOR_RE.findall(text):
        norm = a.strip(".,:%")
        if norm and norm.upper() not in STOP_ANCHORS and len(norm) > 1:
            out.append(norm)
    return out


def _verify_claims(claims: list, items: list) -> list:
    """Clasifica cada afirmación: supported | partially_supported | unsupported
    | unverifiable. Regla de anclaje: ids/cifras de la afirmación deben existir
    en la evidencia citada (match por token normalizado, case-insensitive)."""
    by_id = {it["id"]: it["content"].lower() for it in items}
    verified = []
    for c in claims:
        if c["tag"] in ("SE", "REF"):
            status = "unverifiable"
        elif c["pointer"] not in by_id:
            status = "unsupported"
        else:
            content = by_id[c["pointer"]]
            anchors = _anchors(c["text"])
            if not anchors:
                status = "partially_supported"
            else:
                found = [a for a in anchors if a.lower() in content]
                if len(found) == len(anchors):
                    status = "supported"
                elif found:
                    status = "partially_supported"
                else:
                    status = "unsupported"
        verified.append({**c, "support": status})
    return verified


def _claims_summary(verified: list) -> dict:
    counts = {"supported": 0, "partially_supported": 0, "unsupported": 0, "unverifiable": 0}
    for c in verified:
        counts[c["support"]] += 1
    return counts


def _confidence(corpus_level: str, counts: dict) -> str:
    """SIEMPRE computada, jamás autodeclarada por el LLM (regla del diseño §8)."""
    if counts["unsupported"] > 0 or corpus_level == "insufficient":
        return "baja"
    verifiable = counts["supported"] + counts["partially_supported"]
    if (corpus_level == "sufficient" and verifiable
            and counts["supported"] / verifiable >= 0.7):
        return "alta"
    return "media"


def _output_flags(response: str) -> list:
    flags = []
    if "[EVIDENCIA" in response:
        flags.append("injection_suspect_forged_markers")
    if DECISION_LANGUAGE_RE.search(response):
        flags.append("decision_language")
    return flags


def _format_valid(claims: list, response: str) -> bool:
    return bool(claims) and "limitaciones" in response.lower()


# ── Persistencia de propuestas (versionadas) ──────────────────────────────────

def _proposals_dir(project_id: str, doc_id: str):
    return paths.VALIDATION_BASE / project_id / "agent_proposals" / doc_id


def _next_version(project_id: str, doc_id: str) -> int:
    d = _proposals_dir(project_id, doc_id)
    return len(list(d.glob("v*.json"))) + 1 if d.exists() else 1


def _proposal_path(project_id: str, doc_id: str, version: int):
    return _proposals_dir(project_id, doc_id) / f"v{version:02d}.json"


def _load_proposal(project_id: str, doc_id: str, version: int) -> dict:
    f = _proposal_path(project_id, doc_id, version)
    if not f.exists():
        raise HTTPException(404, f"No existe la propuesta v{version} de '{doc_id}'")
    return json.loads(f.read_text(encoding="utf-8"))


def _save_proposal(project_id: str, doc_id: str, record: dict) -> None:
    d = _proposals_dir(project_id, doc_id)
    d.mkdir(parents=True, exist_ok=True)
    _proposal_path(project_id, doc_id, record["version"]).write_text(
        json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")


# ── Generación de propuesta ───────────────────────────────────────────────────

def _require_eligible(project_id: str, doc_id: str) -> dict:
    _valready.require_mission(project_id)
    if doc_id not in _dossier._TITLES:
        raise HTTPException(404, f"Documento '{doc_id}' no existe en el paquete")
    if doc_id not in DOC_ROUTING:
        raise HTTPException(422, f"'{doc_id}' no tiene routing de agente experto: "
                                 "es un documento de hechos o sin evidencia posible "
                                 "(missing_evidence) — no aplica redacción por agente")
    dossier = _dossier._load_dossier(project_id)
    entry = dossier["documents"].get(doc_id)
    if not entry:
        raise HTTPException(409, f"'{doc_id}' no ha sido generado — genera el dossier primero")
    if entry.get("status") not in ELIGIBLE_STATES:
        raise HTTPException(422, f"'{doc_id}' está en estado '{entry.get('status')}' — "
                                 f"solo {sorted(ELIGIBLE_STATES)} admiten propuesta de agente")
    return dossier


def _fail(project_id: str, doc_id: str, agent: str, reason: str, trigger: dict,
          requested_by: str, http_status: int, detail: str):
    from factory.core.audit_writer import write_event
    write_event("dossier_agent_proposal_failed", project_id, {
        "doc_id": doc_id, "agent": agent, "reason": reason,
        "trigger": trigger, "requested_by": requested_by,
    })
    raise HTTPException(http_status, {"error": reason, "detail": detail,
                                      "model": OLLAMA_MODEL, "doc_id": doc_id})


def propose_document(project_id: str, doc_id: str, trigger: dict,
                     guidance: str | None = None) -> dict:
    """Genera una propuesta de análisis experto. NUNCA cambia nada a estado
    aprobado; ante cualquier fallo el documento queda intacto."""
    trigger = trigger or {}
    if trigger.get("mode") != "manual":
        raise HTTPException(403, "W6.5 solo admite trigger manual: la generación "
                                 "automática gobernada es un gate futuro que requiere "
                                 "TaskSpec aprobado, presupuesto y kill-switch")
    name = _console.validate_run_by(trigger.get("principal") or "")
    dossier = _require_eligible(project_id, doc_id)
    primary, supporting = DOC_ROUTING[doc_id]

    corpus = corpus_sufficiency(project_id, primary)
    bundle = _dossier.build_evidence_bundle(project_id)
    items = _evidence_items(project_id, doc_id, bundle, primary)
    prompts_meta = _load_prompts()
    prompt, template_sha = _build_prompt(prompts_meta, primary, doc_id,
                                         corpus["level"], items, guidance)
    agent_prompt_version = ((prompts_meta.get("prompts") or {}).get(primary) or {}).get("prompt_version")

    t0 = datetime.now(timezone.utc)
    response, retried = None, False
    for attempt in (1, 2):
        current_prompt = prompt if attempt == 1 else (
            prompt + "\n\nCORRECCIÓN DE FORMATO: tu respuesta anterior no cumplió el "
            "contrato. Cada afirmación DEBE ser una viñeta '- [E: id] ...', '- [SE] ...' "
            "o '- [REF: norma] ...' y DEBE existir la sección final '## Limitaciones'.")
        try:
            data = _ollama_generate(current_prompt)
        except httpx.ConnectError as e:
            _fail(project_id, doc_id, primary, "ollama_unreachable", trigger, name, 503, str(e))
        except httpx.TimeoutException as e:
            _fail(project_id, doc_id, primary, "ollama_timeout", trigger, name, 504, str(e))
        except Exception as e:
            _fail(project_id, doc_id, primary, "ollama_error", trigger, name, 502, str(e))
        response = data.get("response", "")
        if _format_valid(_parse_claims(response), response):
            break
        if attempt == 1:
            retried = True
    latency_ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)

    claims = _parse_claims(response)
    format_ok = _format_valid(claims, response)
    verified = _verify_claims(claims, items)
    counts = _claims_summary(verified)
    confidence = _confidence(corpus["level"], counts)
    flags = _output_flags(response)
    if counts["unsupported"] > 0:
        flags.append("unsupported_claims")

    version = _next_version(project_id, doc_id)
    record = {
        "project_id": project_id, "doc_id": doc_id, "version": version,
        "status": "agent_proposed" if format_ok else "format_invalid",
        "agent": {"primary": primary, "supporting": supporting,
                  "supporting_note": "dominios de revisión recomendados para el "
                                     "revisor humano (no ejecutados en W6.5)"},
        "model": {"name": OLLAMA_MODEL,
                  "options": {"num_predict": NUM_PREDICT, "temperature": TEMPERATURE}},
        "prompt": {"set_version": prompts_meta.get("prompt_set_version"),
                   "agent_prompt_version": agent_prompt_version,
                   "template_sha256": template_sha, "rendered_sha256": _sha(prompt)},
        "corpus_sufficiency": corpus,
        "evidence_sources": [{"id": it["id"], "trust": it["trust"], "pointer": it["pointer"]}
                             for it in items],
        "claims": {**counts, "detail": verified},
        "confidence": confidence,
        "flags": flags,
        "response": response,
        "governance": {"trigger": trigger, "requested_by": name,
                       "guidance": guidance, "prompt_full": prompt,
                       "generated_at": _now(), "latency_ms": latency_ms,
                       "format_retry": retried},
        "decision": None,
        "regulatory_note": "PROPUESTA DE AGENTE — sin valor regulatorio hasta "
                           "revisión y aprobación humana. NO es firma electrónica.",
    }
    _save_proposal(project_id, doc_id, record)

    from factory.core.audit_writer import write_event
    if not format_ok:
        # propuesta inutilizable pero archivada y visible; el doc no cambia
        write_event("dossier_agent_proposal_failed", project_id, {
            "doc_id": doc_id, "agent": primary, "reason": "format_invalid",
            "trigger": trigger, "requested_by": name, "version": version,
        })
        return {"project_id": project_id, "doc_id": doc_id, "version": version,
                "status": "format_invalid", "confidence": confidence, "flags": flags}

    entry = dossier["documents"][doc_id]
    entry["status"] = "agent_proposed"
    entry["agent_proposal"] = {
        "version": version, "status": "agent_proposed", "agent": primary,
        "supporting": supporting, "confidence": confidence,
        "corpus_sufficiency": corpus["level"], "claims": counts,
        "generated_at": record["governance"]["generated_at"],
        "path": f"agent_proposals/{doc_id}/v{version:02d}.json",
    }
    _dossier._save_dossier(project_id, dossier)

    write_event("dossier_agent_proposal_generated", project_id, {
        "doc_id": doc_id, "version": version,
        "agent_primary": primary, "agent_supporting": supporting,
        "model": OLLAMA_MODEL,
        "prompt_set_version": record["prompt"]["set_version"],
        "prompt_version": agent_prompt_version,
        "template_sha256": template_sha,
        "rendered_sha256": record["prompt"]["rendered_sha256"],
        "response_sha256": _sha(response),
        "corpus_sufficiency": corpus["level"],
        "claims": counts, "confidence": confidence, "flags": flags,
        "trigger": trigger, "requested_by": name,
    })
    return {"project_id": project_id, "doc_id": doc_id, "version": version,
            "status": "agent_proposed", "agent": record["agent"],
            "corpus_sufficiency": corpus["level"], "claims": counts,
            "confidence": confidence, "flags": flags}


# ── Lectura (nunca audita) ────────────────────────────────────────────────────

def read_proposal(project_id: str, doc_id: str, version: int | None = None) -> dict:
    """Read-only: propuesta completa con gobierno. NUNCA audita."""
    _valready.require_mission(project_id)
    if doc_id not in _dossier._TITLES:
        raise HTTPException(404, f"Documento '{doc_id}' no existe en el paquete")
    if version is None:
        d = _proposals_dir(project_id, doc_id)
        versions = sorted(d.glob("v*.json")) if d.exists() else []
        if not versions:
            raise HTTPException(404, f"'{doc_id}' no tiene propuestas de agente")
        version = len(versions)
    return _load_proposal(project_id, doc_id, version)


# ── Decisión humana (accept ≠ approve; jamás produce estado aprobado) ─────────

def _render_accepted_block(record: dict, accepted_by: str) -> str:
    c = record["claims"]
    return (
        f"\n## Análisis experto propuesto por agente (v{record['version']})\n\n"
        f"> **PROPUESTO POR AGENTE: {record['agent']['primary']} · "
        f"modelo {record['model']['name']} · "
        f"prompt v{record['prompt']['agent_prompt_version']} "
        f"(set {record['prompt']['set_version']}) · "
        f"generado {record['governance']['generated_at']} · "
        f"corpus: {record['corpus_sufficiency']['level']} · "
        f"afirmaciones: {c['supported']} supported / {c['partially_supported']} "
        f"partially / {c['unsupported']} unsupported / {c['unverifiable']} unverifiable · "
        f"confianza computada: {record['confidence']} · "
        f"aceptado por: {accepted_by} ({_now()}) — texto propuesto por agente, "
        f"sin valor regulatorio hasta aprobación humana.**\n\n"
        f"{record['response']}\n")


def decide_proposal(project_id: str, doc_id: str, decision: str,
                    decided_by: str, reason: str | None = None) -> dict:
    """accept | reject | request_changes — siempre acto humano con nombre real.
    accept incorpora el texto y deja el doc en needs_human_review (la aprobación
    formal sigue siendo el endpoint humano existente de W6.2)."""
    name = _console.validate_run_by(decided_by)
    if decision not in VALID_DECISIONS:
        raise HTTPException(422, f"decision debe ser una de {VALID_DECISIONS}")
    if decision in ("reject", "request_changes") and not (reason or "").strip():
        raise HTTPException(422, f"'{decision}' exige reason: motivo del rechazo o "
                                 "instrucción de ajuste para el agente")
    _valready.require_mission(project_id)
    dossier = _dossier._load_dossier(project_id)
    entry = dossier["documents"].get(doc_id)
    if not entry or not entry.get("agent_proposal"):
        raise HTTPException(409, f"'{doc_id}' no tiene propuesta de agente que decidir")
    if entry.get("status") != "agent_proposed":
        raise HTTPException(409, f"'{doc_id}' está en '{entry.get('status')}' — "
                                 "solo agent_proposed admite decisión")

    version = entry["agent_proposal"]["version"]
    record = _load_proposal(project_id, doc_id, version)
    decided_at = _now()
    new_sha = None

    if decision == "accept":
        doc_file = paths.VALIDATION_BASE / project_id / "documents" / f"{doc_id}.md"
        content = doc_file.read_text(encoding="utf-8") + _render_accepted_block(record, name)
        doc_file.write_text(content, encoding="utf-8")
        new_sha = _dossier._content_hash(content)
        entry["status"] = "needs_human_review"
        entry["content_sha256"] = new_sha
        entry["agent_proposal"]["status"] = "accepted"
        record["status"] = "accepted"
    elif decision == "reject":
        entry["status"] = "needs_human_review"
        entry["agent_proposal"]["status"] = "rejected"
        record["status"] = "rejected"
    else:  # request_changes
        entry["agent_proposal"]["status"] = "changes_requested"
        record["status"] = "changes_requested"

    record["decision"] = {"decision": decision, "decided_by": name,
                          "decided_at": decided_at, "reason": reason}
    _save_proposal(project_id, doc_id, record)
    _dossier._save_dossier(project_id, dossier)

    from factory.core.audit_writer import write_event
    write_event("dossier_agent_proposal_decision", project_id, {
        "doc_id": doc_id, "proposal_version": version, "decision": decision,
        "decided_by": name, "reason": reason,
        "new_status": dossier["documents"][doc_id]["status"],
        "content_sha256": new_sha,
    })

    out = {"project_id": project_id, "doc_id": doc_id, "decision": decision,
           "proposal_version": version, "decided_by": name,
           "doc_status": dossier["documents"][doc_id]["status"]}

    if decision == "request_changes":
        # nueva versión con la instrucción humana como guidance (mismo gobierno;
        # genera su propio evento). Si Ollama falla, la decisión queda registrada
        # y el doc permanece agent_proposed con la propuesta marcada.
        regen = propose_document(project_id, doc_id,
                                 {"mode": "manual", "principal": name,
                                  "authorization_ref": None}, guidance=reason)
        out["new_proposal"] = regen
    return out
