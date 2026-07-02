"""
W6 — Servicio read-only de las vistas MODO DISEÑO de Mission Control:
Tareas operativas de agentes, Fuentes regulatorias y Memoria de casos.

Reglas duras de este módulo:
  - SOLO lectura de archivos locales (yaml/jsonl bajo factory/). NUNCA audita,
    NUNCA escribe, NUNCA hace HTTP externo (no importa httpx a propósito).
  - Archivo ausente o corrupto → estado vacío explícito, nunca error 500
    ni datos inventados.
  - La búsqueda de casos es substring naive sobre resumen/tags/keywords:
    los embeddings reales son fase futura aprobada.

Los tests redirigen rutas con monkeypatch sobre factory.services.paths.
"""

import json

import yaml as _yaml

from factory.services import paths


def _load_yaml(path) -> dict | None:
    """None si el archivo no existe o no parsea — el caller decide el vacío."""
    if not path.exists():
        return None
    try:
        data = _yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def read_agent_tasks() -> dict:
    """Catálogo de TaskSpecs. design_mode=True siempre en W6 (sin ejecutor)."""
    data = _load_yaml(paths.AGENT_TASKS_FILE)
    if data is None:
        return {"design_mode": True, "executor_implemented": False, "tasks": [],
                "note": "sin especificaciones de tareas (archivo no encontrado)"}
    return {
        "design_mode": True,
        "executor_implemented": bool(data.get("executor_implemented", False)),
        "tasks": data.get("tasks", []) or [],
    }


def read_agent_task(task_id: str) -> dict | None:
    for task in read_agent_tasks()["tasks"]:
        if task.get("task_id") == task_id:
            return task
    return None


def read_source_registry() -> dict:
    """Registro de fuentes oficiales. connected siempre False en W6."""
    data = _load_yaml(paths.SOURCE_REGISTRY_FILE)
    if data is None:
        return {"design_mode": True, "connectors_implemented": False, "sources": [],
                "note": "sin registro de fuentes (archivo no encontrado)"}
    return {
        "design_mode": True,
        "connectors_implemented": bool(data.get("connectors_implemented", False)),
        "default_policy": data.get("default_policy", {}),
        "sources": data.get("sources", []) or [],
    }


def read_case_memory(limit: int = 100) -> dict:
    """Case records de la memoria local. Vacía en W6 — y eso se dice tal cual."""
    cases = []
    if paths.CASE_MEMORY_FILE.exists():
        for raw in paths.CASE_MEMORY_FILE.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                cases.append(json.loads(raw))
            except Exception:
                continue  # línea corrupta: se omite, no rompe la lectura
    return {
        "design_mode": True,
        "count": len(cases),
        "cases": cases[-limit:],
        "note": None if cases else
        "memoria vacía: se poblará solo con casos reales de fuentes oficiales bajo aprobación",
    }


def search_case_memory(query: str, limit: int = 20) -> dict:
    """Búsqueda substring (case-insensitive) sobre summary/tags/keywords/case_type."""
    q = (query or "").strip().lower()
    if not q:
        return {"design_mode": True, "query": query, "count": 0, "results": []}
    results = []
    for case in read_case_memory(limit=10_000)["cases"]:
        haystack = " ".join([
            str(case.get("summary", "")),
            " ".join(map(str, case.get("tags", []) or [])),
            " ".join(map(str, case.get("keywords", []) or [])),
            str(case.get("case_type", "")),
        ]).lower()
        if q in haystack:
            results.append(case)
        if len(results) >= limit:
            break
    return {"design_mode": True, "query": query, "count": len(results), "results": results}
