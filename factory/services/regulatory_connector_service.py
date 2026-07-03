"""
W6.3 — Conector online controlado: openFDA Drug Enforcement / Recalls.

Primera (y única) fuente conectada de la Regulatory Case Memory. Modelo:
source pointer + metadata + summary + tags + hash + freshness + selective fetch.

Reglas duras de esta fase:
  - UN solo sector: https://api.fda.gov/drug/enforcement.json (REST JSON
    oficial de FDA). Cero HTML, cero scraping, cero crawling.
  - Sin descarga masiva: limit 1..10 por consulta, sin paginación (skip no
    existe), un solo endpoint.
  - Sin recurrencia: cada llamada online exige acto humano con nombre real
    (regla run_by de W4). No hay cron, scheduler ni reintentos automáticos.
  - Anti-saturación: mínimo MIN_INTERVAL_S entre llamadas online y máximo
    MAX_CALLS_PER_DAY por día UTC (consultas y fetches comparten cupo),
    persistido en connector_state.json. Exceso → HTTP 429.
  - Memoria ligera: cases.jsonl (append-only) guarda SOLO pointer + metadata
    + resumen + hash. Nunca el documento completo, nunca direcciones postales.
  - Selective fetch: recupera el detalle de UN caso por recall_number, lo
    devuelve al llamador y NO lo persiste.
  - Auditoría: exactamente 1 evento por consulta (regulatory_query_executed)
    y 1 por fetch (case_detail_fetched). Las lecturas locales nunca auditan.
  - Los datos consultados NO alimentan decisiones GMP ni aprobaciones CSV:
    son memoria de referencia para revisión humana.
"""

import hashlib
import json
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException

from factory.services import paths
from factory.services import test_console_service as _console

SOURCE_ID = "openfda_enforcement"
AUTHORITY = "FDA"
ENDPOINT = "https://api.fda.gov/drug/enforcement.json"
USER_AGENT = "gmp-ai-factory-w6.3/1.0 (read-only regulatory connector; rate-limited)"

MAX_LIMIT = 10          # tope duro por consulta — anti descarga masiva
MIN_INTERVAL_S = 60     # segundos mínimos entre llamadas online
MAX_CALLS_PER_DAY = 10  # cupo diario UTC (consultas + fetches)
TIMEOUT_S = 10.0
STALE_AFTER_DAYS = 30

# Mapeo determinista razón→tags GMP (ayuda de clasificación, NO juicio GMP)
GMP_TAG_MAP = {
    "steril": "sterility",
    "cgmp": "cgmp",
    "contamin": "contamination",
    "label": "labeling",
    "stabilit": "stability",
    "dissolution": "dissolution",
    "impurit": "impurities",
    "potency": "potency",
    "particulate": "particulates",
    "microbial": "microbial",
    "mold": "microbial",
    "out of specification": "oos",
    "subpotent": "potency",
    "superpotent": "potency",
    "temperature": "cold_chain",
    "packag": "packaging",
    "mix-up": "mislabeling_mixup",
    "nitrosamine": "impurities",
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Rate limit persistido (anti-saturación) ───────────────────────────────────

def _load_state() -> dict:
    if paths.CONNECTOR_STATE_FILE.exists():
        try:
            return json.loads(paths.CONNECTOR_STATE_FILE.read_text(encoding="utf-8")) or {}
        except Exception:
            pass
    return {}


def _save_state(state: dict) -> None:
    paths.CONNECTOR_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    paths.CONNECTOR_STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _rate_gate() -> dict:
    """Reserva un slot ANTES de la llamada HTTP. Lanza 429 si se viola el
    intervalo mínimo o el cupo diario. Devuelve el estado actualizado."""
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    state = _load_state()

    if state.get("date") != today:
        state = {"date": today, "calls_today": 0, "last_call_at": None}

    if state.get("last_call_at"):
        try:
            last = datetime.fromisoformat(state["last_call_at"])
            elapsed = (now - last).total_seconds()
            if elapsed < MIN_INTERVAL_S:
                raise HTTPException(429, f"Rate limit: espera {int(MIN_INTERVAL_S - elapsed)}s "
                                         f"(mínimo {MIN_INTERVAL_S}s entre llamadas online)")
        except HTTPException:
            raise
        except Exception:
            pass  # timestamp corrupto: no bloquea, el cupo diario sigue vigente

    if state.get("calls_today", 0) >= MAX_CALLS_PER_DAY:
        raise HTTPException(429, f"Cupo diario agotado: {MAX_CALLS_PER_DAY} llamadas online/día UTC")

    state["calls_today"] = state.get("calls_today", 0) + 1
    state["last_call_at"] = now.isoformat()
    _save_state(state)
    return state


def quota_status() -> dict:
    """Estado del cupo para mostrar en la UI. Solo lectura local, no audita."""
    state = _load_state()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    used = state.get("calls_today", 0) if state.get("date") == today else 0
    return {"calls_today": used, "max_calls_per_day": MAX_CALLS_PER_DAY,
            "min_interval_s": MIN_INTERVAL_S, "last_call_at": state.get("last_call_at")}


# ── HTTP (única función que sale a internet — mockeable en tests) ─────────────

def _http_get(params: dict) -> httpx.Response:
    return httpx.get(ENDPOINT, params=params, timeout=TIMEOUT_S,
                     headers={"User-Agent": USER_AGENT})


# ── Normalización a memoria ligera ────────────────────────────────────────────

def _sanitize_term(term: str) -> str:
    """Neutraliza la sintaxis de búsqueda de openFDA (comillas, dos puntos,
    corchetes) para que el término no inyecte otros campos ni rangos."""
    clean = "".join(ch for ch in (term or "") if ch not in '":[]()+').strip()
    if not (2 <= len(clean) <= 80):
        raise HTTPException(422, "search_term debe tener entre 2 y 80 caracteres útiles")
    return clean


def _normalize(rec: dict, consulted_at: str) -> dict:
    """Registro openFDA → case record ligero. NO conserva direcciones postales
    ni el documento completo; el detalle vive en la fuente (selective fetch)."""
    rn = rec.get("recall_number") or f"sin-recall-number-{rec.get('event_id', '?')}"
    raw_hash = hashlib.sha256(
        json.dumps(rec, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    reason = (rec.get("reason_for_recall") or "").strip()
    product = (rec.get("product_description") or "").strip()
    firm = (rec.get("recalling_firm") or "").strip()
    tags = sorted({v for k, v in GMP_TAG_MAP.items() if k in reason.lower()})
    keywords = [x for x in [rec.get("classification"), rec.get("status"),
                            rec.get("voluntary_mandated"), firm] if x]
    summary = (f"{rec.get('classification') or 'Sin clasificación'} · recall {rn} — "
               f"{firm or 'firma no declarada'}: {product[:200]}. "
               f"Razón: {reason[:300]}. Estado: {rec.get('status') or '—'}. "
               f"Iniciado: {rec.get('recall_initiation_date') or '—'} · "
               f"Reportado: {rec.get('report_date') or '—'}.")
    return {
        "case_id": f"{SOURCE_ID}:{rn}",
        "url": f'{ENDPOINT}?search=recall_number:"{rn}"&limit=1',
        "source_id": SOURCE_ID,
        "authority": AUTHORITY,
        "consulted_at": consulted_at,
        "last_checked": consulted_at,
        "case_type": "drug_recall",
        "classification": rec.get("classification"),
        "recall_status": rec.get("status"),
        "product": product[:200],
        "reason": reason[:300],
        "recalling_firm": firm[:120],
        "recall_initiation_date": rec.get("recall_initiation_date"),
        "report_date": rec.get("report_date"),
        "keywords": keywords,
        "tags": tags,
        "summary": summary[:1200],
        "content_hash": f"sha256:{raw_hash}",
        "embedding_ref": None,   # embeddings no aprobados (fase futura)
        "retrieval_path": {"method": "GET", "url": ENDPOINT,
                           "params": {"search": f'recall_number:"{rn}"', "limit": 1}},
        "freshness": {"stale_after_days": STALE_AFTER_DAYS},
        "relevance": None,
    }


def _existing_case_ids() -> set:
    ids = set()
    if paths.CASE_MEMORY_FILE.exists():
        for raw in paths.CASE_MEMORY_FILE.read_text(encoding="utf-8").splitlines():
            try:
                ids.add(json.loads(raw).get("case_id"))
            except Exception:
                continue
    return ids


def _append_cases(cases: list) -> None:
    paths.CASE_MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(paths.CASE_MEMORY_FILE, "a", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")


# ── Consulta controlada ───────────────────────────────────────────────────────

def query_recalls(search_term: str, limit: int, run_by: str) -> dict:
    """UNA llamada online a openFDA: busca en reason_for_recall, guarda memoria
    ligera de los resultados nuevos, audita exactamente 1 evento."""
    name = _console.validate_run_by(run_by)
    term = _sanitize_term(search_term)
    limit = max(1, min(int(limit or 5), MAX_LIMIT))
    quota = _rate_gate()

    params = {"search": f'reason_for_recall:"{term}"',
              "limit": limit, "sort": "report_date:desc"}
    try:
        resp = _http_get(params)
    except Exception as e:
        raise HTTPException(502, f"openFDA no respondió: {e}")

    if resp.status_code == 404:
        results = []            # openFDA responde 404 cuando no hay coincidencias
    elif resp.status_code != 200:
        raise HTTPException(502, f"openFDA devolvió HTTP {resp.status_code}")
    else:
        results = (resp.json() or {}).get("results", []) or []

    now = _now()
    existing = _existing_case_ids()
    saved_cases, skipped = [], 0
    for rec in results[:limit]:
        case = _normalize(rec, now)
        if case["case_id"] in existing:
            skipped += 1
            continue
        existing.add(case["case_id"])
        saved_cases.append(case)
    _append_cases(saved_cases)

    from factory.core.audit_writer import write_event
    write_event("regulatory_query_executed", "regulatory_intel", {
        "source_id": SOURCE_ID, "search_term": term, "limit": limit,
        "results_returned": len(results), "saved": len(saved_cases),
        "skipped_existing": skipped, "run_by": name,
    })
    return {
        "source_id": SOURCE_ID, "search_term": term, "limit": limit,
        "results_returned": len(results), "saved": len(saved_cases),
        "skipped_existing": skipped,
        "cases": saved_cases,
        "quota": {"calls_today": quota.get("calls_today"),
                  "max_calls_per_day": MAX_CALLS_PER_DAY},
    }


# ── Selective fetch ───────────────────────────────────────────────────────────

def fetch_case_detail(case_id: str, run_by: str) -> dict:
    """Recupera de la fuente el detalle completo de UN caso ya presente en la
    memoria. Lo devuelve SIN persistirlo; compara hash para detectar cambios.
    Audita exactamente 1 evento."""
    name = _console.validate_run_by(run_by)
    stored = None
    if paths.CASE_MEMORY_FILE.exists():
        for raw in paths.CASE_MEMORY_FILE.read_text(encoding="utf-8").splitlines():
            try:
                c = json.loads(raw)
                if c.get("case_id") == case_id:
                    stored = c
            except Exception:
                continue
    if not stored:
        raise HTTPException(404, f"Caso '{case_id}' no está en la memoria — "
                                 "el selective fetch parte de un caso conocido")

    rp = stored.get("retrieval_path") or {}
    quota = _rate_gate()
    try:
        resp = _http_get(rp.get("params") or {})
    except Exception as e:
        raise HTTPException(502, f"openFDA no respondió: {e}")
    if resp.status_code == 404:
        raise HTTPException(404, "El caso ya no existe en la fuente (verificado online)")
    if resp.status_code != 200:
        raise HTTPException(502, f"openFDA devolvió HTTP {resp.status_code}")

    results = (resp.json() or {}).get("results", []) or []
    if not results:
        raise HTTPException(404, "La fuente no devolvió el registro")
    detail = results[0]
    new_hash = "sha256:" + hashlib.sha256(
        json.dumps(detail, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    changed = new_hash != stored.get("content_hash")

    # el detalle NO se guarda — se elimina solo lo que nunca almacenamos
    detail_light = {k: v for k, v in detail.items()
                    if k not in ("address_1", "address_2", "postal_code", "openfda")}

    from factory.core.audit_writer import write_event
    write_event("case_detail_fetched", "regulatory_intel", {
        "case_id": case_id, "run_by": name,
        "content_hash": new_hash, "content_changed": changed,
    })
    return {
        "case_id": case_id, "stored_case": stored,
        "detail": detail_light, "content_changed": changed,
        "fetched_at": _now(), "persisted": False,
        "quota": {"calls_today": quota.get("calls_today"),
                  "max_calls_per_day": MAX_CALLS_PER_DAY},
    }


def annotate_sources(registry: dict) -> dict:
    """Superpone el estado vivo del conector sobre el registry (el YAML no se
    reescribe desde código — sus comentarios de diseño se preservan)."""
    q = quota_status()
    for s in registry.get("sources", []):
        if s.get("source_id") == SOURCE_ID:
            s["last_checked"] = q.get("last_call_at")
            s["connector_live"] = True
            s["quota"] = q
    registry["connectors_implemented"] = True
    registry["connected_sources"] = [SOURCE_ID]
    return registry
