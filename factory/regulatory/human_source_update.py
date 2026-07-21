"""
Fase 1 pendiente (`factory/docs/document_remediation_evolution/
TARGET_REGULATORY_ARCHITECTURE.md` §2/§3) — `human_source_update`: único
punto de escritura para cambiar `official_source_url`/`sha256_original`
de una fuente gobernada en `sources/registry.json`.

**Nunca automatiza la sustitución de una URL rota** (§3: "el objetivo del
usuario prohíbe inventar enlaces, y una URL de reemplazo encontrada por
búsqueda automática no es verificablemente la fuente oficial correcta
sin juicio humano"). Mismo patrón que `applicability_matrix.yaml.approval`
(`MC-000X` en `factory/layer9/decisions/decisions.jsonl`, reutiliza
`decision_log.write_decision` -- no un mecanismo nuevo paralelo):

  propose_source_url_update()  -- agent_proposed, NUNCA escribe registry.json
  confirm_source_url_update()  -- human_confirmed, NUNCA escribe registry.json
  apply_source_url_update()    -- ÚNICA función que escribe registry.json,
                                   exige la decisión human_confirmed+approve
                                   Y que la fuente esté ya declarada
                                   REGULATORY_SOURCE_UNVERIFIED por
                                   `broken_link_report` (fail-closed: nunca
                                   reescribe una fuente sana sin ese caso
                                   real que lo justifique)

`regulatory_currency_status` NUNCA se toca aquí -- el schema lo fija a
`pending_reverification` por diseño (decisión ya tomada en Fase 1,
`source_currency_checker.py`); una URL nueva sigue sin verificar vigencia
hasta la siguiente corrida real del checker.
"""
from __future__ import annotations

import json
from pathlib import Path

from factory.core.audit_writer import write_event
from factory.layer9 import decision_log
from factory.regulatory import broken_link_report
from factory.services import paths as svc_paths

ACTION = "regulatory_source_url_update"
_ALLOWED_FIELDS = {"official_source_url", "sha256_original", "official_source_description"}
SOURCES_REGISTRY_FILE = Path(__file__).parent / "sources" / "registry.json"


class HumanSourceUpdateError(Exception):
    pass


def propose_source_url_update(
    source_id: str, new_values: dict, rationale: str, proposed_by: str = "layer8_agent",
) -> dict:
    """Registra una PROPUESTA (`agent_proposed`) en `decisions.jsonl` --
    nunca escribe `registry.json`. `new_values`: subconjunto de
    `_ALLOWED_FIELDS`, fail-closed ante cualquier campo desconocido (ej.
    nunca permite tocar `regulatory_currency_status` desde aquí)."""
    unknown = set(new_values) - _ALLOWED_FIELDS
    if unknown:
        raise HumanSourceUpdateError(f"campos no permitidos en new_values: {sorted(unknown)}")
    if not new_values:
        raise HumanSourceUpdateError("new_values vacío -- no hay nada que proponer")
    return decision_log.write_decision(
        project_id="gmpai_document_validation", action=ACTION, decision="approve",
        rationale=rationale, decided_by=proposed_by, decision_origin="agent_proposed",
        recorded_by=proposed_by,
        metadata={"source_id": source_id, "new_values": new_values},
    )


def confirm_source_url_update(decision_id: str, confirmed_by: str) -> dict:
    """Confirma una propuesta ya registrada -- nunca escribe
    `registry.json` (eso es `apply_source_url_update`, un paso más, para
    mantener propuesta/confirmación/aplicación como 3 pasos separados y
    auditables)."""
    proposal = _find_decision(decision_id)
    if proposal is None:
        raise HumanSourceUpdateError(f"decision_id {decision_id!r} no encontrada en decisions.jsonl")
    if proposal["action"] != ACTION or proposal["decision_origin"] != "agent_proposed":
        raise HumanSourceUpdateError(
            f"decision_id {decision_id!r} no es una propuesta agent_proposed de {ACTION!r}"
        )
    return decision_log.write_decision(
        project_id=proposal["project_id"], action=ACTION, decision="approve",
        rationale=f"Confirma propuesta {decision_id}", decided_by=confirmed_by,
        decision_origin="human_confirmed", recorded_by=confirmed_by,
        metadata={**proposal["metadata"], "confirms_decision_id": decision_id},
    )


def apply_source_url_update(decision_id: str) -> dict:
    """Único punto de escritura real sobre `sources/registry.json`.
    Fail-closed en 2 frentes independientes: (1) exige una decisión
    `human_confirmed`+`approve` ya registrada para `decision_id`, (2)
    exige que la fuente esté ya declarada `REGULATORY_SOURCE_UNVERIFIED`
    según el historial real de `source_currency_log.jsonl` -- nunca
    reescribe una fuente sana, ni siquiera con una decisión humana
    válida, porque §3 del diseño solo justifica este mecanismo para
    resolver un enlace roto real, no para cambios ad hoc."""
    decision = _find_decision(decision_id)
    if decision is None:
        raise HumanSourceUpdateError(f"decision_id {decision_id!r} no encontrada en decisions.jsonl")
    if (decision["action"] != ACTION or decision["decision_origin"] != "human_confirmed"
            or decision["decision"] != "approve"):
        raise HumanSourceUpdateError(
            f"decision_id {decision_id!r} no es human_confirmed+approve de {ACTION!r}"
        )

    source_id = decision["metadata"]["source_id"]
    new_values = decision["metadata"]["new_values"]

    log_entries = _read_currency_log()
    status = broken_link_report.evaluate_source(source_id, log_entries)["status"]
    if status != broken_link_report.STATUS_UNVERIFIED:
        raise HumanSourceUpdateError(
            f"source_id={source_id!r} no está REGULATORY_SOURCE_UNVERIFIED (status real={status!r}) "
            "-- human_source_update nunca reescribe una fuente sana"
        )

    registry = json.loads(SOURCES_REGISTRY_FILE.read_text(encoding="utf-8"))
    entry = next((s for s in registry["sources"] if s["source_id"] == source_id), None)
    if entry is None:
        raise HumanSourceUpdateError(f"source_id={source_id!r} no existe en sources/registry.json")

    before = {k: entry.get(k) for k in new_values}
    entry.update(new_values)
    if entry["regulatory_currency_status"] != "pending_reverification":
        raise HumanSourceUpdateError(
            "regulatory_currency_status cambió de 'pending_reverification' -- invariante del schema violada, abortando escritura"
        )

    SOURCES_REGISTRY_FILE.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    write_event("regulatory_source_url_updated", "gmpai_document_validation", {
        "source_id": source_id, "decision_id": decision_id, "before": before, "after": new_values,
    })

    return {"source_id": source_id, "before": before, "after": new_values, "decision_id": decision_id}


def _find_decision(decision_id: str) -> dict | None:
    for entry in decision_log.list_decisions():
        if entry["decision_id"] == decision_id:
            return entry
    return None


def _read_currency_log() -> list[dict]:
    if not svc_paths.SOURCE_CURRENCY_LOG_FILE.exists():
        return []
    entries = []
    for line in svc_paths.SOURCE_CURRENCY_LOG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries
