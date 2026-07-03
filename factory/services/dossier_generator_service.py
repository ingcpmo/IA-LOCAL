"""
W6.2 — Generador asistido del dossier CSV/GAMP 5 por misión.

Genera BORRADORES de los 22 documentos del paquete de validación usando
ÚNICAMENTE evidencia real ya existente en la Factory (misión, diseño, agentes,
catálogo y resultados W4, RCs, deployment, auditoría). Reglas duras:

  - NUNCA inventa: cada afirmación lleva su fuente; donde no hay dato el texto
    dice literalmente "SIN EVIDENCIA — requiere aporte humano".
  - NUNCA aprueba: el estado `approved` solo lo produce el endpoint humano
    approve_document (nombre real, regla run_by de W4).
  - NUNCA sobrescribe trabajo aprobado: si el contenido regenerado de un doc
    `approved` difiere del aprobado (SHA-256), la aprobación se invalida a
    `needs_human_review` de forma explícita y auditada.
  - Todo borrador abre con el encabezado "sin valor regulatorio".

Estados: not_started | draft | missing_evidence | needs_human_review | approved
  - facts     → draft            (agregación pura de evidencia)
  - judgment  → needs_human_review (esqueleto de hechos + juicio humano pendiente)
  - cualquier doc sin una evidencia requerida → missing_evidence

Escrituras: SOLO bajo validation/<pid>/ (dossier.yaml + documents/*.md).
Auditoría: exactamente 1 evento por generate y 1 por approve (write_event
existente — mismo patrón que gmp_report_generated de W4.1.1).
"""

import hashlib
import json
from datetime import datetime, timezone

import yaml as _yaml
from fastapi import HTTPException

from factory.services import mission_evidence_service as _evidence
from factory.services import paths
from factory.services import test_console_service as _console
from factory.services import validation_readiness_service as _valready
from factory.services.validation_readiness_service import VALIDATION_DOCS

SIN_EVIDENCIA = "SIN EVIDENCIA — requiere aporte humano"

_TITLES = dict(VALIDATION_DOCS)


def _content_hash(content: str) -> str:
    """SHA-256 del contenido SIN la línea de metadata volátil (timestamp de
    generación): así regenerar sin cambio de evidencia no invalida aprobaciones."""
    stable = "\n".join(l for l in content.splitlines() if not l.startswith("> Misión:"))
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Evidence bundle (solo lecturas locales) ───────────────────────────────────

def build_evidence_bundle(project_id: str) -> dict:
    mission = _valready.require_mission(project_id)
    summary = _evidence.build_mission_summary(project_id)
    agents = (_evidence.read_agents(project_id) or {}).get("agents", [])
    catalog = _console.load_test_catalog(project_id)

    runs = []
    results_file = paths.TEST_RESULTS_DIR / f"{project_id}.jsonl"
    if results_file.exists():
        for raw in results_file.read_text(encoding="utf-8").splitlines():
            try:
                runs.append(json.loads(raw))
            except Exception:
                continue

    rc_canonical = None
    rc_dir = paths.RC_BASE / project_id
    if rc_dir.exists():
        for f in sorted(rc_dir.rglob("rc_manifest.json")):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                if d.get("is_canonical"):
                    rc_canonical = d
            except Exception:
                continue

    audit_events = []
    if paths.AUDIT_FILE.exists():
        for raw in paths.AUDIT_FILE.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(raw)
                if e.get("project_id") == project_id:
                    audit_events.append({
                        "event_type": e.get("event_type"),
                        "timestamp": e.get("timestamp"),
                        "by": (e.get("data") or {}).get("approved_by")
                        or (e.get("data") or {}).get("record_by") or "",
                    })
            except Exception:
                continue

    return {
        "project_id": project_id,
        "mission": mission,
        "summary": summary,
        "agents": agents,
        "catalog": catalog,
        "runs": runs,
        "rc_canonical": rc_canonical,
        "audit_events": audit_events,
    }


# ── Helpers de redacción (hechos + pointer, nunca prosa inventada) ────────────

def _li(items) -> str:
    return "\n".join(f"- {i}" for i in items)


def _src(pointer: str) -> str:
    return f"\n\n*Fuente: {pointer}*"


def _objective(b):
    o = b["mission"].get("objective")
    if not o:
        return None
    return (f"**URS-01 — requisito principal (verbatim de la misión):**\n\n{o}\n\n"
            f"Cliente: {b['mission'].get('client_type') or SIN_EVIDENCIA}"
            + _src(f"layer9/missions/{b['project_id']}.yaml"))


def _constraints(b):
    """Verbatim, SIN numerar como URS: en misiones reales `constraints` puede
    contener acciones de autonomía del pipeline, no requisitos de usuario —
    clasificarlas como URS formales es juicio QA, no del generador."""
    cs = b["mission"].get("constraints") or []
    if not cs:
        return None
    return ("Declaradas en la misión (verbatim). Pueden ser requisitos de usuario "
            "o acciones autorizadas del pipeline; su clasificación como URS "
            "formales requiere juicio QA:\n" + _li(cs)
            + _src("misión · constraints"))


def _reg_scope(b):
    rs = b["mission"].get("regulatory_scope") or []
    return (_li(rs) + _src("misión · regulatory_scope")) if rs else None


def _agents_block(b):
    if not b["agents"]:
        return None
    lines = []
    for a in b["agents"]:
        kind = f"perfil de {a.get('base_agent')}" if a.get("is_inherited") else "agente nuevo"
        lines.append(f"**{a.get('agent_id')}** ({kind}): {a.get('rationale') or 'sin rationale registrado'}")
    return "\n".join(lines) + _src("designs/·/agent_design_proposal.yaml")


def _catalog_endpoints(b):
    cat = b["catalog"]
    if not cat:
        return None
    eps = sorted({t.get("endpoint") for ag in cat.get("agents", []) for t in ag.get("tests", [])} - {None})
    return _li(eps) + _src(f"test_catalogs/{b['project_id']}.yaml")


def _design_files(b):
    d = (b["summary"].get("design") or {})
    files = d.get("files") or []
    if not files:
        return None
    return _li(str(f) for f in files[:30]) + _src("designs/ de la misión")


def _deployment_facts(b):
    dep = b["summary"].get("deployment") or {}
    if not dep.get("exists"):
        return None
    return (f"- Deployment en disco: sí\n- Puerto API asignado: {dep.get('api_port') or SIN_EVIDENCIA}\n"
            f"- Health check al generar: {'OK (HTTP 200)' if dep.get('health_ok') else 'sin respuesta'}"
            + _src("deployments/ + port_registry + /health"))


def _rc_facts(b):
    rc = b["rc_canonical"]
    if not rc:
        return None
    return (f"- RC canónico: {rc.get('rc_id')}\n- Estado: {rc.get('status')}\n"
            f"- Creado: {rc.get('created_at') or 'sin fecha en manifest'}"
            + _src("release_candidates/·/rc_manifest.json"))


def _ws_tests(b):
    t = b["summary"].get("tests")
    if not t or (t.get("passed", 0) + t.get("failed", 0)) == 0:
        return None
    return (f"- Suite del workspace: {t.get('passed')} passed · {t.get('failed')} failed "
            f"(returncode {t.get('returncode')})" + _src("workspace · test_report.json"))


def _runs_facts(b):
    if not b["runs"]:
        return None
    ok = sum(1 for r in b["runs"] if r.get("result") == "PASS"
             or any(t.get("result") == "PASS" for t in r.get("results", []) or []))
    by = sorted({r.get("run_by") for r in b["runs"] if r.get("run_by")})
    return (f"- Ejecuciones registradas: {len(b['runs'])}\n- Con al menos un PASS: {ok}\n"
            f"- Operadores (nombre real): {', '.join(by) or SIN_EVIDENCIA}"
            + _src(f"test_results/{b['project_id']}.jsonl"))


def _audit_facts(b):
    ev = b["audit_events"]
    if not ev:
        return None
    tail = ev[-10:]
    lines = [f"- {e['timestamp']} · {e['event_type']}" + (f" · por {e['by']}" if e["by"] else "")
             for e in tail]
    return (f"Eventos de la misión en la cadena (últimos {len(tail)} de {len(ev)}; "
            f"hash chain SHA-256):\n" + "\n".join(lines)
            + _src("audit/factory_audit.jsonl (cadena verificable)"))


def _last_run_by_test(b) -> dict:
    """Última ejecución registrada por test_id (el JSONL es cronológico; la
    última línea gana). Entradas de suite anidan results[] — run_by/run_at
    caen al nivel del run si el item no los trae."""
    last: dict[str, dict] = {}
    for r in b["runs"]:
        for t in ([r] if r.get("test_id") else r.get("results", []) or []):
            if t.get("test_id"):
                last[t["test_id"]] = {
                    "result": t.get("result", "—"),
                    "run_by": t.get("run_by") or r.get("run_by") or "—",
                    "run_at": (t.get("run_at") or r.get("run_at") or "")[:19] or "—",
                    "latency_ms": t.get("latency_ms", r.get("latency_ms")),
                    "assertion": t.get("assertion") or {},
                }
    return last


def _frs_table(b):
    """FRS numerados desde el catálogo curado W4: cada caso de prueba declara
    una función esperada verificable (título + endpoint). Evidencia real, no
    redacción del generador."""
    cat = b["catalog"]
    if not cat:
        return None
    rows = ["| FRS | Agente | Función esperada (título curado W4) | Endpoint |",
            "|---|---|---|---|"]
    n = 0
    for ag in cat.get("agents", []):
        for t in ag.get("tests", []):
            n += 1
            rows.append(f"| FRS-{n:02d} | {ag.get('agent_id')} "
                        f"| {t.get('title') or t.get('test_id')} | `{t.get('endpoint')}` |")
    if n == 0:
        return None
    return "\n".join(rows) + _src(f"test_catalogs/{b['project_id']}.yaml (catálogo curado W4)")


def _catalog_meta(b):
    cat = b["catalog"]
    if not cat:
        return None
    n = sum(len(ag.get("tests") or []) for ag in cat.get("agents", []))
    return (f"- Versión del catálogo: {cat.get('catalog_version') or SIN_EVIDENCIA}\n"
            f"- Deployment objetivo: {cat.get('deployment_base') or SIN_EVIDENCIA}\n"
            f"- Casos curados: {n} en {len(cat.get('agents', []))} agentes"
            + _src(f"test_catalogs/{b['project_id']}.yaml"))


def _oq_results_table(b):
    """Última ejecución por prueba con aserción, latencia, operador y timestamp
    — cada fila es localizable por su run_at en el JSONL de resultados."""
    last = _last_run_by_test(b)
    if not last:
        return None
    rows = ["| Prueba | Último resultado | Aserción (json_path: esperado → recibido) | ms | Operador | UTC |",
            "|---|---|---|---|---|---|"]
    for tid, r in sorted(last.items()):
        a = r["assertion"]
        asr = (f"`{a.get('json_path')}`: {json.dumps(a.get('expected_value'))} → "
               f"{json.dumps(a.get('received_value'))}") if a else "—"
        lat = "—" if r["latency_ms"] is None else r["latency_ms"]
        rows.append(f"| {tid} | {r['result']} | {asr} | {lat} | {r['run_by']} | {r['run_at']} |")
    return "\n".join(rows) + _src(f"test_results/{b['project_id']}.jsonl (última ejecución por prueba)")


def _trace_matrix(b):
    cat = b["catalog"]
    if not cat or not b["agents"]:
        return None
    last = _last_run_by_test(b)
    rows = ["| Requisito | Agente | Prueba (catálogo W4) | Endpoint | Último resultado | Ejecutado por · UTC | Documento |",
            "|---|---|---|---|---|---|---|"]
    for ag in cat.get("agents", []):
        for t in ag.get("tests", []):
            r = last.get(t.get("test_id"))
            res = r["result"] if r else "sin ejecución"
            who = f"{r['run_by']} · {r['run_at']}" if r else "—"
            rows.append(f"| URS-01 | {ag.get('agent_id')} | {t.get('test_id')} "
                        f"| `{t.get('endpoint')}` | {res} | {who} | OQ |")
    return ("URS-01 = objetivo de la misión (verbatim en el documento URS). Evidencia "
            "exacta de cada fila: la entrada con ese `run_at` en "
            f"`test_results/{b['project_id']}.jsonl` (cronológico, append-only).\n\n"
            + "\n".join(rows)
            + _src("misión + agent_design_proposal + catálogo W4 + test_results"))


def _pending_docs(b):
    docs = b["mission"].get("documents") or {}
    if not docs:
        return None
    return _li(f"{k}: {v}" for k, v in docs.items()) + _src("misión · documents")


def _judgment(_b):
    return None  # sección que exige juicio humano: siempre SIN EVIDENCIA


# ── Especificación de los 22 documentos ───────────────────────────────────────
# (kind, [evidencias requeridas], [(título de sección, extractor)])
# Requeridas posibles: objective, constraints, agents, catalog, runs,
#                      deployment, rc, audit, design_files

_REQ_CHECKS = {
    "objective": lambda b: bool(b["mission"].get("objective")),
    "constraints": lambda b: bool(b["mission"].get("constraints")),
    "agents": lambda b: bool(b["agents"]),
    "catalog": lambda b: bool(b["catalog"]),
    "runs": lambda b: bool(b["runs"]),
    "deployment": lambda b: bool((b["summary"].get("deployment") or {}).get("exists")),
    "rc": lambda b: bool(b["rc_canonical"]),
    "audit": lambda b: bool(b["audit_events"]),
    "design_files": lambda b: bool((b["summary"].get("design") or {}).get("files")),
}

DOC_SPECS: dict = {
    "intended_use": ("judgment", ["objective"], [
        ("Uso previsto declarado en la misión", _objective),
        ("Contexto regulatorio", _reg_scope),
        ("Límites de uso (constraints)", _constraints),
        ("Evaluación de idoneidad del uso previsto (juicio QA)", _judgment),
    ]),
    "gxp_impact_assessment": ("judgment", ["objective"], [
        ("Alcance regulatorio declarado", _reg_scope),
        ("Proceso GxP impactado (declarado en el objetivo)", _objective),
        ("Clasificación de impacto GxP (juicio QA)", _judgment),
    ]),
    "system_risk_assessment": ("judgment", ["agents"], [
        ("Componentes del sistema", _agents_block),
        ("Estado del deployment", _deployment_facts),
        ("Identificación y evaluación de riesgos (juicio QA)", _judgment),
    ]),
    "supplier_ai_model_assessment": ("judgment", ["rc"], [
        ("Release candidate evaluado", _rc_facts),
        ("Componente IA declarado", lambda b: "Ollama local (host, compartido vía host-gateway); "
         "el modelo concreto se configura por deployment." + _src("arquitectura factory · manifest")),
        ("Evaluación del proveedor/modelo (juicio QA)", _judgment),
    ]),
    "urs": ("facts", ["objective", "constraints"], [
        ("Requisito de usuario principal (URS-01, verbatim)", _objective),
        ("Alcance regulatorio declarado", _reg_scope),
        ("Restricciones/acciones declaradas en la misión (verbatim)", _constraints),
        ("Documentos regulatorios requeridos por la misión", _pending_docs),
        ("Descomposición en URS individuales verificables (juicio QA)", _judgment),
    ]),
    "frs": ("facts", ["agents", "catalog"], [
        ("Funciones por agente", _agents_block),
        ("Matriz FRS — funciones esperadas verificables (catálogo curado W4)", _frs_table),
        ("Endpoints funcionales cubiertos por el catálogo W4", _catalog_endpoints),
    ]),
    "design_spec": ("facts", ["design_files"], [
        ("Artefactos de diseño generados", _design_files),
        ("Agentes del diseño", _agents_block),
    ]),
    "configuration_spec": ("facts", ["deployment"], [
        ("Configuración del deployment", _deployment_facts),
        ("Release candidate desplegado", _rc_facts),
    ]),
    "data_integrity_assessment": ("judgment", ["audit"], [
        ("Mecanismos de integridad existentes (hechos)", _audit_facts),
        ("Evaluación de integridad de datos por flujo (juicio QA)", _judgment),
    ]),
    "part11_assessment": ("judgment", ["audit"], [
        ("Cadena de auditoría (hechos)", _audit_facts),
        ("Evaluación de cumplimiento §11 por requisito (juicio QA)", _judgment),
    ]),
    "alcoa_plus_assessment": ("judgment", ["audit"], [
        ("Trazabilidad existente (hechos)", _audit_facts),
        ("Evaluación ALCOA+ atributo por atributo (juicio QA)", _judgment),
    ]),
    "traceability_matrix": ("facts", ["agents", "catalog"], [
        ("Matriz objetivo → agente → prueba → evidencia → documento", _trace_matrix),
    ]),
    # judgment: una estrategia de pruebas exige justificación riesgo-basada
    # (qué se prueba, qué se excluye y por qué) — eso es juicio QA, no hechos.
    "test_strategy": ("judgment", ["catalog"], [
        ("Catálogo curado de pruebas funcionales (W4)", _catalog_meta),
        ("Cobertura de endpoints", _catalog_endpoints),
        ("Resultados de construcción (workspace)", _ws_tests),
        ("Gates de calidad del sistema", lambda b: "14 quality gates obligatorios previos a release "
         "+ selfcheck Gate 0 (py_compile, pytest, cadena de auditoría, estado)."
         + _src("factory/scripts/ops/factory_selfcheck.sh · quality_gate_runner")),
        ("Justificación riesgo-basada de la estrategia y exclusiones (juicio QA)", _judgment),
    ]),
    "iq": ("facts", ["deployment"], [
        ("Evidencia de instalación", _deployment_facts),
        ("Release instalado", _rc_facts),
    ]),
    "oq": ("facts", ["runs"], [
        ("Ejecuciones funcionales registradas (W4)", _runs_facts),
        ("Resultados por prueba — última ejecución con aserción y operador", _oq_results_table),
        ("Trazabilidad de pruebas", _trace_matrix),
    ]),
    "pq": ("no_evidence", ["__pq_production_data__"], [
        ("Datos de rendimiento en producción", _judgment),
        ("Criterios de aceptación PQ", _judgment),
    ]),
    "validation_summary_report": ("judgment", ["objective"], [
        ("Misión y alcance", _objective),
        ("Evidencia disponible al generar", lambda b: "\n".join(filter(None, [
            _ws_tests(b), _runs_facts(b), _rc_facts(b), _deployment_facts(b)])) or None),
        ("Conclusión de validación (juicio QA — nunca automática)", _judgment),
    ]),
    "sop_suggested": ("judgment", ["objective"], [
        ("Capacidades del sistema que requerirían SOP", lambda b:
         _li(["Operación y aprobación de misiones (Capa 9)",
              "Revisión humana de release candidates",
              "Ejecución de pruebas funcionales W4 (run_by nombre real)",
              "Generación y aprobación del dossier CSV",
              "Gestión del deployment y verificación de salud"])
         + _src("capacidades observables del sistema — propuesta, no SOP")),
        ("Redacción y aprobación de SOP (juicio QA)", _judgment),
    ]),
    "change_control": ("facts", ["audit"], [
        ("Historial de cambios auditado de la misión", _audit_facts),
    ]),
    "periodic_review": ("no_evidence", ["__periodic_review_done__"], [
        ("Revisiones periódicas realizadas", _judgment),
    ]),
    "incident_deviation_handling": ("no_evidence", ["__incident_records__"], [
        ("Incidentes / desviaciones registrados", _judgment),
        ("Procedimiento de manejo (juicio QA)", _judgment),
    ]),
    "retirement_plan": ("judgment", ["deployment"], [
        ("Inventario a retirar (hechos)", lambda b: "\n".join(filter(None, [
            _deployment_facts(b), _rc_facts(b)])) or None),
        ("Plan de retiro y retención de datos (juicio QA)", _judgment),
    ]),
}


# ── Generación ────────────────────────────────────────────────────────────────

def _render_doc(doc_id: str, bundle: dict, generated_by: str) -> tuple[str, list, list]:
    """→ (markdown, missing_evidence, evidence_sources)."""
    kind, required, sections = DOC_SPECS[doc_id]
    missing = [r for r in required if not _REQ_CHECKS.get(r, lambda b: False)(bundle)]

    body = [f"# {_TITLES[doc_id]}", "",
            "> **BORRADOR GENERADO POR LA FACTORY — sin valor regulatorio hasta "
            "revisión y aprobación humana.**",
            "> Revisión humana: verifique cada afirmación contra la fuente citada antes "
            "de aprobar; las secciones \"SIN EVIDENCIA\" requieren aporte humano previo.",
            f"> Misión: `{bundle['project_id']}` · Generado: {_now()} · Por: {generated_by}",
            ""]
    sources = []
    for title, extractor in sections:
        body.append(f"## {title}\n")
        content = extractor(bundle)
        if content:
            body.append(content)
            for line in content.splitlines():
                if line.startswith("*Fuente: "):
                    sources.append(line[9:].rstrip("*"))
        else:
            body.append(f"**{SIN_EVIDENCIA}**")
        body.append("")
    return "\n".join(body), missing, sorted(set(sources))


def _doc_status(doc_id: str, missing: list) -> str:
    kind = DOC_SPECS[doc_id][0]
    if missing:
        return "missing_evidence"
    return "needs_human_review" if kind == "judgment" else "draft"


def _load_dossier(project_id: str) -> dict:
    f = paths.VALIDATION_BASE / project_id / "dossier.yaml"
    if f.exists():
        try:
            return _yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:
            pass
    return {"meta": {}, "documents": {}}


def _save_dossier(project_id: str, dossier: dict) -> None:
    d = paths.VALIDATION_BASE / project_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "dossier.yaml").write_text(
        _yaml.safe_dump(dossier, allow_unicode=True, sort_keys=False), encoding="utf-8")


def generate_dossier(project_id: str, generated_by: str) -> dict:
    """Genera/regenera los borradores. Documentos approved: solo se invalidan
    (a needs_human_review) si su contenido regenerado difiere del aprobado."""
    name = _console.validate_run_by(generated_by)
    bundle = build_evidence_bundle(project_id)
    dossier = _load_dossier(project_id)
    docs_dir = paths.VALIDATION_BASE / project_id / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)

    generated, skipped_approved, invalidated = [], [], []
    for doc_id, _title in VALIDATION_DOCS:
        content, missing, sources = _render_doc(doc_id, bundle, name)
        sha = _content_hash(content)
        prev = dossier["documents"].get(doc_id) or {}

        if prev.get("status") == "approved":
            if prev.get("content_sha256") == sha:
                skipped_approved.append(doc_id)
                continue
            # la evidencia subyacente cambió: la aprobación deja de ser válida
            (docs_dir / f"{doc_id}.md").write_text(content, encoding="utf-8")
            dossier["documents"][doc_id] = {
                "status": "needs_human_review", "generated_at": _now(),
                "generated_by": name, "content_sha256": sha,
                "missing": missing, "evidence_sources": sources,
                "invalidated_approval": {
                    "approved_by": prev.get("approved_by"),
                    "approved_at": prev.get("approved_at"),
                    "reason": "contenido regenerado difiere del aprobado (SHA-256)",
                },
            }
            invalidated.append(doc_id)
            continue

        (docs_dir / f"{doc_id}.md").write_text(content, encoding="utf-8")
        dossier["documents"][doc_id] = {
            "status": _doc_status(doc_id, missing), "generated_at": _now(),
            "generated_by": name, "content_sha256": sha,
            "missing": missing, "evidence_sources": sources,
        }
        generated.append(doc_id)

    dossier["meta"] = {"version": 1, "generated_at": _now(), "generated_by": name}
    _save_dossier(project_id, dossier)

    from factory.core.audit_writer import write_event
    write_event("validation_dossier_generated", project_id, {
        "generated_by": name, "generated": len(generated),
        "skipped_approved": len(skipped_approved), "invalidated": invalidated,
    })
    return {
        "project_id": project_id, "generated": generated,
        "skipped_approved": skipped_approved, "invalidated": invalidated,
    }


def approve_document(project_id: str, doc_id: str, approved_by: str) -> dict:
    """Única vía al estado approved. Acto humano con nombre real, auditado.
    NO es firma electrónica."""
    name = _console.validate_run_by(approved_by)
    _valready.require_mission(project_id)
    if doc_id not in _TITLES:
        raise HTTPException(404, f"Documento '{doc_id}' no existe en el paquete")
    dossier = _load_dossier(project_id)
    entry = dossier["documents"].get(doc_id)
    if not entry:
        raise HTTPException(409, f"'{doc_id}' no ha sido generado — nada que aprobar")
    if entry.get("status") == "missing_evidence":
        raise HTTPException(422, f"'{doc_id}' tiene evidencia faltante ({entry.get('missing')}) "
                                 "— no puede aprobarse")
    if entry.get("status") == "approved":
        raise HTTPException(409, f"'{doc_id}' ya está aprobado por {entry.get('approved_by')}")

    entry["status"] = "approved"
    entry["approved_by"] = name
    entry["approved_at"] = _now()
    _save_dossier(project_id, dossier)

    from factory.core.audit_writer import write_event
    write_event("validation_doc_approved", project_id, {
        "doc_id": doc_id, "approved_by": name,
        "content_sha256": entry.get("content_sha256"),
    })
    return {"project_id": project_id, "doc_id": doc_id,
            "status": "approved", "approved_by": name}


def read_document(project_id: str, doc_id: str) -> dict:
    """Read-only: contenido del borrador + metadata. NUNCA audita."""
    _valready.require_mission(project_id)
    if doc_id not in _TITLES:
        raise HTTPException(404, f"Documento '{doc_id}' no existe en el paquete")
    f = paths.VALIDATION_BASE / project_id / "documents" / f"{doc_id}.md"
    if not f.exists():
        raise HTTPException(404, f"'{doc_id}' no ha sido generado todavía")
    dossier = _load_dossier(project_id)
    return {
        "project_id": project_id, "doc_id": doc_id, "title": _TITLES[doc_id],
        "content": f.read_text(encoding="utf-8"),
        "meta": dossier["documents"].get(doc_id, {}),
    }
