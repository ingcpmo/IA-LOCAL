"""
W9 Bloque 3 — Segunda(s) fuente(s) online controlada(s): openFDA Device
Enforcement y openFDA Food Enforcement. Mismo patrón gobernado de W6.3
(`regulatory_connector_service.py`: pointer + metadata + summary + tags +
hash + freshness + selective fetch), generalizado a más de una fuente SIN
tocar el conector original — cero riesgo de regresión sobre lo ya
aprobado y probado en W6.3/W6.4/W7/W8. Aprobado por Cesar
(W8_GROUNDING_PLAN.md §Bloque 3, 2026-07-10): "Bloque 3 con segunda fuente
openFDA Device/Food Enforcement".

Reglas duras (idénticas a W6.3, generalizadas por fuente):
  - Cero HTML, cero scraping: solo los 2 endpoints REST JSON oficiales de
    SOURCES (mismo dominio api.fda.gov que W6.3, mismo modelo de datos
    openFDA — recall_number, reason_for_recall, classification, etc.).
  - Cupo COMPARTIDO con W6.3: reutiliza el mismo rate gate
    (`regulatory_connector_service._rate_gate`, mismo
    `connector_state.json`) — el límite protege a openFDA de la fábrica en
    conjunto (drug+device+food), no por endpoint. MIN_INTERVAL_S/
    MAX_CALLS_PER_DAY del módulo base aplican igual aquí, sin duplicar
    estado ni crear una segunda cuenta de cupo.
  - Selective fetch determina el endpoint correcto leyendo el `source_id`
    YA guardado en el case record — nunca asume drug ni un endpoint fijo.
  - Memoria ligera idéntica: NUNCA address/postal_code/openfda ni el
    documento completo.
  - Auditoría: reutiliza los mismos 2 tipos de evento de W6.3
    (`regulatory_query_executed`/`case_detail_fetched`) — mismo pipeline
    de auditoría/routing/verificador aguas abajo (W6.4/W7), sin cambios.
"""

import hashlib
import json
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException

from factory.services import paths
from factory.services import regulatory_connector_service as _base
from factory.services import test_console_service as _console

SOURCES = {
    "openfda_device_enforcement": {
        "endpoint": "https://api.fda.gov/device/enforcement.json",
        "authority": "FDA", "case_type": "device_recall",
    },
    "openfda_food_enforcement": {
        "endpoint": "https://api.fda.gov/food/enforcement.json",
        "authority": "FDA", "case_type": "food_recall",
    },
}

# Extensión mínima del mapeo de tags de W6.3 — señales frecuentes en recalls
# de dispositivo/alimento que el mapeo original (centrado en drogas) no cubre.
EXTRA_TAG_MAP = {
    "allergen": "allergen_undeclared", "undeclared": "allergen_undeclared",
    "malfunction": "device_malfunction", "software": "software_defect",
    "battery": "device_malfunction", "listeria": "microbial",
    "salmonella": "microbial",
}
TAG_MAP = {**_base.GMP_TAG_MAP, **EXTRA_TAG_MAP}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_source(source_id: str) -> dict:
    cfg = SOURCES.get(source_id)
    if not cfg:
        raise HTTPException(404, f"Fuente '{source_id}' no es un conector de Bloque 3 "
                                 f"válido (válidas: {sorted(SOURCES)})")
    return cfg


def _http_get(endpoint: str, params: dict) -> httpx.Response:
    return httpx.get(endpoint, params=params, timeout=_base.TIMEOUT_S,
                     headers={"User-Agent": _base.USER_AGENT})


def _normalize(source_id: str, cfg: dict, rec: dict, consulted_at: str,
              found_by_query: str | None = None) -> dict:
    endpoint = cfg["endpoint"]
    rn = rec.get("recall_number") or f"sin-recall-number-{rec.get('event_id', '?')}"
    raw_hash = hashlib.sha256(
        json.dumps(rec, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    reason = (rec.get("reason_for_recall") or "").strip()
    product = (rec.get("product_description") or "").strip()
    firm = (rec.get("recalling_firm") or "").strip()
    tags = sorted({v for k, v in TAG_MAP.items() if k in reason.lower()})
    keywords = [x for x in [rec.get("classification"), rec.get("status"),
                            rec.get("voluntary_mandated"), firm] if x]
    summary = (f"{rec.get('classification') or 'Sin clasificación'} · recall {rn} — "
               f"{firm or 'firma no declarada'}: {product[:200]}. "
               f"Razón: {reason[:300]}. Estado: {rec.get('status') or '—'}. "
               f"Iniciado: {rec.get('recall_initiation_date') or '—'} · "
               f"Reportado: {rec.get('report_date') or '—'}.")
    return {
        "case_id": f"{source_id}:{rn}",
        "url": f'{endpoint}?search=recall_number:"{rn}"&limit=1',
        "source_id": source_id,
        "authority": cfg["authority"],
        "consulted_at": consulted_at,
        "last_checked": consulted_at,
        "found_by_query": found_by_query,
        "case_type": cfg["case_type"],
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
        "embedding_ref": None,
        "retrieval_path": {"method": "GET", "url": endpoint,
                           "params": {"search": f'recall_number:"{rn}"', "limit": 1}},
        "freshness": {"stale_after_days": _base.STALE_AFTER_DAYS},
        "relevance": None,
    }


# ── Consulta controlada ───────────────────────────────────────────────────────

def query_recalls(source_id: str, search_term: str, limit: int, run_by: str) -> dict:
    """UNA llamada online a openFDA (device o food): busca en reason_for_recall,
    guarda memoria ligera de los resultados nuevos, audita exactamente 1 evento.
    Mismo cupo compartido de W6.3 (_base._rate_gate)."""
    cfg = _require_source(source_id)
    name = _console.validate_run_by(run_by)
    term = _base._sanitize_term(search_term)
    limit = max(1, min(int(limit or 5), _base.MAX_LIMIT))
    quota = _base._rate_gate()

    params = {"search": f'reason_for_recall:"{term}"',
              "limit": limit, "sort": "report_date:desc"}
    try:
        resp = _http_get(cfg["endpoint"], params)
    except Exception as e:
        raise HTTPException(502, f"openFDA no respondió: {e}")

    if resp.status_code == 404:
        results = []            # openFDA responde 404 cuando no hay coincidencias
    elif resp.status_code != 200:
        raise HTTPException(502, f"openFDA devolvió HTTP {resp.status_code}")
    else:
        results = (resp.json() or {}).get("results", []) or []

    now = _now()
    existing = _base._existing_case_ids()
    saved_cases, skipped = [], 0
    for rec in results[:limit]:
        case = _normalize(source_id, cfg, rec, now, found_by_query=term)
        if case["case_id"] in existing:
            skipped += 1
            continue
        existing.add(case["case_id"])
        saved_cases.append(case)
    _base._append_cases(saved_cases)

    from factory.core.audit_writer import write_event
    write_event("regulatory_query_executed", "regulatory_intel", {
        "source_id": source_id, "search_term": term, "limit": limit,
        "results_returned": len(results), "saved": len(saved_cases),
        "skipped_existing": skipped, "run_by": name,
    })
    return {
        "source_id": source_id, "search_term": term, "limit": limit,
        "results_returned": len(results), "saved": len(saved_cases),
        "skipped_existing": skipped,
        "cases": saved_cases,
        "quota": {"calls_today": quota.get("calls_today"),
                  "max_calls_per_day": _base.MAX_CALLS_PER_DAY},
    }


# ── Selective fetch ───────────────────────────────────────────────────────────

def fetch_case_detail(case_id: str, run_by: str) -> dict:
    """Recupera de la fuente el detalle completo de UN caso de device/food ya
    presente en la memoria. El endpoint se decide por el source_id guardado
    en el propio case record — nunca asume drug. Lo devuelve SIN persistirlo."""
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
    cfg = _require_source(stored.get("source_id") or "")

    rp = stored.get("retrieval_path") or {}
    quota = _base._rate_gate()
    try:
        resp = _http_get(cfg["endpoint"], rp.get("params") or {})
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
                  "max_calls_per_day": _base.MAX_CALLS_PER_DAY},
    }


def annotate_sources(registry: dict) -> list:
    """Superpone el estado vivo (cupo COMPARTIDO con W6.3) sobre las 2 fuentes
    de Bloque 3 en el registry. Devuelve los source_id anotados — el caller
    (route) los añade a connected_sources sin pisar los de W6.3."""
    q = _base.quota_status()
    connected = []
    for s in registry.get("sources", []):
        if s.get("source_id") in SOURCES:
            s["last_checked"] = q.get("last_call_at")
            s["connector_live"] = True
            s["quota"] = q
            connected.append(s["source_id"])
    return connected
