"""G8 — resolución real de R(d,a) (spec §5.2 de
`MODEL_REQUALIFICATION_AND_D4A_SPEC.md`), la pieza que faltaba para calcular
D4-A sobre el catálogo de HOY en vez de reproducir la tabla calibratoria de
§5.4 (que describe un catálogo histórico distinto -- Part 11 tenía 4
checkpoints ahí, hoy tiene 5, y `21_CFR_211.68(b)` no participaba porque no
existía o tenía 0 criterios).

`R(d,a)` (spec §5.2) para un (documento, agente) es el subconjunto de
requisitos de ese agente que:
  1. la matriz de aplicabilidad NO marca `out_of_document_scope` ni
     `review_required` para el tipo documental de d (`applicability.py`,
     ya gobernado, nunca reimplementado);
  2. `resolve("D2", req).authorized == True` (cobertura humana real);
  3. `FORMAL_USE_ELIGIBILITY(source(req)) == True` (fuente verificada de
     origen Y vigencia, `source_lifecycle.py`, ya gobernado).

El agente de cada requisito se lee de los 4 `*_prompts.yaml` gobernados
(`checkpoints[].req_id`) -- NUNCA se infiere del prefijo del `req_id`: ese
patrón coincide hoy pero es un accidente de nomenclatura, no un contrato."""
from __future__ import annotations

from pathlib import Path

import yaml

from factory.core import decision_scope_resolver as resolver
from factory.regulatory import applicability
from factory.regulatory import source_lifecycle as sl
from factory.regulatory.requirement_catalog.requirement_catalog_loader import (
    load_requirements,
)

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "engines" / "gmpai_integrity" / "prompts"

#: (nombre_de_archivo, agent_id) -- el resto (checkpoints) se lee del YAML.
AGENT_PROMPT_FILES = (
    ("part11_prompts.yaml", "fda_part11_agent"),
    ("cgmp211_prompts.yaml", "fda_cgmp_211_agent"),
    ("annex11_prompts.yaml", "eu_annex11_agent"),
    ("alcoa_prompts.yaml", "alcoa_plus_agent"),
)

_NOT_APPLICABLE_VALUES = frozenset({"out_of_document_scope", "review_required"})


def load_agent_of_requirement() -> dict[str, str]:
    """`{req_id: agent_id}` leído en vivo de los 4 prompts gobernados."""
    mapping: dict[str, str] = {}
    for filename, agent_id in AGENT_PROMPT_FILES:
        data = yaml.safe_load((PROMPTS_DIR / filename).read_text(encoding="utf-8"))
        for cp in data["checkpoints"]:
            mapping[cp["req_id"]] = agent_id
    return mapping


def is_requirement_eligible(requirement_id: str, *,
                            requirements: dict | None = None,
                            decision_store_file: Path | None = None,
                            source_dims: dict | None = None) -> bool:
    """Condiciones 2 y 3 de R(d,a): cobertura D2 real + fuente con
    FORMAL_USE_ELIGIBILITY real -- nunca declaradas a mano."""
    catalog = requirements or load_requirements()["requirements"]
    d2 = resolver.resolve("D2", requirement_id, store_file=decision_store_file)
    if not d2.authorized:
        return False
    source_id = catalog[requirement_id]["source_id"]
    dims = source_dims or {d.source_id: d for d in sl.evaluate_registry()}
    state = dims.get(source_id)
    return state is not None and state.formal_use_eligibility


def resolve_document_agent_plan(document_type: str, *,
                                agent_of: dict[str, str] | None = None,
                                requirements: dict | None = None,
                                decision_store_file: Path | None = None,
                                source_dims: dict | None = None
                                ) -> dict[str, dict]:
    """R(d,a) para TODOS los agentes sobre un tipo documental: condición 1
    de la matriz (§2, arriba) MÁS elegibilidad real (2 y 3).

    Devuelve `{agent_id: {"requirement_ids": [...], "n_checkpoints": int,
    "n_criteria": int}}` -- agentes sin ningún requisito aplicable NO
    aparecen (mismo criterio que `calls_for_document`: un agente sin
    checkpoints no genera ninguna llamada)."""
    catalog = requirements or load_requirements()["requirements"]
    agents = agent_of or load_agent_of_requirement()
    dims = source_dims or {d.source_id: d for d in sl.evaluate_registry()}

    plan: dict[str, dict] = {}
    for req_id, entry in catalog.items():
        app = applicability.applicability(req_id, document_type)
        if app["value"] in _NOT_APPLICABLE_VALUES:
            continue
        if not is_requirement_eligible(req_id, requirements=catalog,
                                       decision_store_file=decision_store_file,
                                       source_dims=dims):
            continue
        agent_id = agents[req_id]
        bucket = plan.setdefault(agent_id, {"requirement_ids": [], "n_criteria": 0})
        bucket["requirement_ids"].append(req_id)
        bucket["n_criteria"] += len(entry.get("evidence_min_criteria") or [])

    for bucket in plan.values():
        bucket["n_checkpoints"] = len(bucket["requirement_ids"])
    return plan
