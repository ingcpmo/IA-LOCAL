"""SHADOW · CF-6 v2.0 · R2 — propuesta gobernada de AMPLIACIÓN de scope de la PILOT
para el Composer de 4 pasos con Relevance Model (R1, tag `cf6-v2-R1`, auditado
externamente como PASS).

Responde a `PILOT_SCOPE_MATCH_CF6 (nuevo tipo de ejecución) = NO`
(`docs_plan/shadow_llm/CF6/CF6_v2_R2_SCOPE_CHECK.md`): el chequeo (a) falla porque
ningún `composer_prompt_version` firmado nombra todavía el pipeline de R1 (Relevance
Model + contrato requirement-centric + `ProfessionalAssessmentRecord`) — R1 no
necesitó ninguno, es 100% determinista, sin LLM.

Igual que `cf6_scope_addendum.py` (v2) y `cf6_scope_addendum_v3.py`: se prepara —sin
LLM y sin tocar el ledger canónico— el `propose` de un ADDENDUM que amplía
`PILOT_EXECUTION-2026-035/-036/-037/-038/-039/-040` (no las supersede — I-7).

Diferencia deliberada con los dos precedentes: en ambos, el `composer_prompt_version`
referenciado YA EXISTÍA como archivo (`composer_structured_v2.yaml` /
`composer_structured_v3.yaml`, `DRAFT_UNSIGNED` en el momento del propose). Aquí
NO se redacta ningún YAML de prompt nuevo -- instrucción explícita: "no rediseñar R1
ni CF-6 v2.0, no implementar". `RESERVED_COMPOSER_PROMPT_VERSION` es por tanto un
NOMBRE RESERVADO, no un artefacto todavía existente. Esta ADDENDUM, por sí sola, NO
deja `PILOT_SCOPE_MATCH_CF6 = YES` -- eso requiere ADEMÁS que exista y esté (al menos)
`DRAFT_UNSIGNED` un prompt con ese nombre exacto (decisión y trabajo separados, fuera
de este propose). Ver `STOP_RESIDUAL` en `package()`.

NO llama a `governance_service.propose` sobre el ledger real. NO registra
`human_confirmed`. CERO LLM · CERO red · no muta L2 / human_state / FINDINGS_FINGERPRINT.
"""
from __future__ import annotations

import json
from pathlib import Path

from factory.regulatory.shadow.cf6_scope_addendum import mechanism_check  # reuso: sigue = YES

RESERVED_COMPOSER_PROMPT_VERSION = "shadow-cf6-composer-v2.0-relevance-filtered"
EXECUTION_TYPE = "structured_json_composer_relevance_filtered"  # distingue del tipo previo
                                                                # ("structured_json_composer"):
                                                                # el Composer recibe SOLO
                                                                # relevant_evidence[] (R1 §4/§5)
EXTENDS_INSTANCES = ("PILOT_EXECUTION-2026-035", "PILOT_EXECUTION-2026-036",
                     "PILOT_EXECUTION-2026-037", "PILOT_EXECUTION-2026-038",
                     "PILOT_EXECUTION-2026-039", "PILOT_EXECUTION-2026-040")
_CF6_2_5_DOCS = ("RW-0005", "RW-0006", "RW-0012", "RW-0014")
_CF6_3_DOCS = ("RW-0005", "RW-0006", "RW-0009", "RW-0011", "RW-0012", "RW-0014")
CF6_V2_R2_MAX_CALLS = 250


def _scope_units() -> list[dict]:
    units = []
    for d in _CF6_2_5_DOCS:
        units.append({"document_id": d, "agent_id": "shadow_composer_expert",
                      "requirement_id": "SHADOW_CF6_COMPOSER", "purpose": EXECUTION_TYPE,
                      "execution_phase": "CF6-v2-R2",
                      "composer_prompt_version": RESERVED_COMPOSER_PROMPT_VERSION,
                      "selection_reason": "regeneración de la muestra CF6-2.5 bajo el "
                                          "Composer de 4 pasos + Relevance Model (R1)"})
    for d in _CF6_3_DOCS:
        units.append({"document_id": d, "agent_id": "shadow_composer_expert",
                      "requirement_id": "SHADOW_CF6_COMPOSER", "purpose": EXECUTION_TYPE,
                      "execution_phase": "CF6-v2-R5",
                      "composer_prompt_version": RESERVED_COMPOSER_PROMPT_VERSION,
                      "selection_reason": "corrida completa bajo la arquitectura R1-R3 "
                                          "(diseño §13, R5) — 66 secciones documento × regulación"})
    return units


def build_addendum_propose(*, proposed_by_id: str = "Capa 8 (Claude Code)") -> dict:
    units = _scope_units()
    target_ids = sorted({u["document_id"] for u in units})
    payload = {
        "scope": units,
        "max_calls": CF6_V2_R2_MAX_CALLS,
        "authorizes_corpus": False,
        "authorizes_baseline": False,
        "composer_prompt_version": RESERVED_COMPOSER_PROMPT_VERSION,
        "composer_prompt_version_status": "RESERVED_NAME_NOT_YET_DRAFTED",
        "execution_type": EXECUTION_TYPE,
        "authorizes": ["CF6-v2 R2 regeneración de CF6-2.5 bajo Relevance Model",
                       "CF6-v2 R5 corrida completa post-gate (diseño §13)"],
        "extends_instances": list(EXTENDS_INSTANCES),
        "parent_hard_cap": {"instance": "PILOT_EXECUTION-2026-035", "max_calls": 1000,
                            "used_by_g4": 481, "used_by_cf6_2_5_v2": 7, "used_by_cf6_2_5_v3": 7,
                            "still_binds": True},
        "relevance_model_ref": "factory/regulatory/shadow/relevance_model.py, tag cf6-v2-R1 "
                                "(auditado externamente PASS)",
        "not_authorized": ["CORPUS_AUTHORIZATION", "D4", "FORMAL_BASELINE_READY",
                           "flip/adjudication/production", "D-ADJ (GMP Adjudication Expert)",
                           "D-M4+ (benchmark modelo mayor/LoRA/qualification)",
                           "D-REPORT-EXT (distribución externa)",
                           "redacción/firma del prompt RESERVED_COMPOSER_PROMPT_VERSION "
                           "(decisión separada, no cubierta por este ADDENDUM)"],
    }
    reason = (
        "ADDENDUM a la familia PILOT_EXECUTION (extiende -035/-036/-037/-038/-039/-040; NO las "
        "supersede — I-7). Responde a PILOT_SCOPE_MATCH_CF6=NO verificado explícitamente para "
        "el nuevo tipo de ejecución de R1 (CF6_v2_R2_SCOPE_CHECK.md): el Composer de 4 pasos con "
        "Relevance Model activo (R1, tag cf6-v2-R1, auditado externamente PASS) recibe SOLO "
        f"relevant_evidence[] -- tipo de ejecución distinto del previo ('{EXECUTION_TYPE}' vs. "
        "'structured_json_composer'). Reserva el nombre "
        f"'{RESERVED_COMPOSER_PROMPT_VERSION}' en el scope para cuando exista un prompt firmado "
        "con ese nombre exacto -- esta ADDENDUM NO redacta ni firma ningún YAML de prompt nuevo "
        "(fuera del mandato de esta sesión: 'no rediseñar R1 ni CF-6 v2.0, no implementar'). "
        f"Tope duro aditivo: {CF6_V2_R2_MAX_CALLS} llamadas; el tope de 1000 de -035 sigue "
        "acotando el total de la familia. NO autoriza corpus, D4, baseline formal, flip, "
        "adjudicación, producción, ni ninguna de las decisiones D-ADJ/D-M4+/D-REPORT-EXT "
        "(diseño §13, explícitamente fuera de alcance de R1-R6)."
    )
    return {
        "schema": "SHADOW_CF6_V2_R2_SCOPE_ADDENDUM_PROPOSE/v1",
        "action": "propose",
        "decision_origin": "agent_proposed",
        "written_to_ledger": False,
        "submit_via": "canal gobernado (governance_service.propose ADDENDUM PILOT_EXECUTION) — firma de Capa 9",
        "family": "PILOT_EXECUTION",
        "decision": "APPROVE",
        "decision_type": "ADDENDUM",
        "amendment_sequence": 1,
        "selection_mode": "EXPLICIT_LIST",
        "supersedes_instance_id": None,
        "proposed_by_id": proposed_by_id,
        "target_ids": target_ids,
        "payload": payload,
        "reason": reason,
        "mechanism_check": mechanism_check(),
        "equivalent_call": (
            "governance_service.propose(family='PILOT_EXECUTION', target_ids=%r, decision='APPROVE', "
            "decision_type='ADDENDUM', selection_mode='EXPLICIT_LIST', amendment_sequence=1, "
            "proposed_by_id=%r, reason=<reason>, payload=<payload>)" % (target_ids, proposed_by_id)),
        "awaiting": {"action": "human_confirmed", "authority": "Capa 9 (Cesar)",
                     "note": "NO confirmar aquí."},
        "invariants": {
            "LLM_CALLS": 0, "G4D_CALLS": 0, "L2_MUTATIONS": 0, "HUMAN_STATE_CHANGES": 0,
        },
    }


def package(*, proposed_by_id: str = "Capa 8 (Claude Code)") -> dict:
    propose = build_addendum_propose(proposed_by_id=proposed_by_id)
    return {
        "schema": "SHADOW_CF6_V2_R2_SCOPE_RESOLUTION/v1",
        "trigger": "CF6-v2 R2 punto 1 · PILOT_SCOPE_MATCH_CF6 = NO (CF6_v2_R2_SCOPE_CHECK.md)",
        "llm_calls": 0,
        "mechanism_check": mechanism_check(),
        "propose": propose,
        "STOP_RESIDUAL": (
            "Firmar este ADDENDUM (human_confirmed) NO deja por sí solo "
            "PILOT_SCOPE_MATCH_CF6=YES: el chequeo (a) de cf6_pilot_scope.evaluate() exige que "
            f"'{RESERVED_COMPOSER_PROMPT_VERSION}' exista como composer_prompt_version real "
            "(al menos DRAFT_UNSIGNED). Esa redacción es una decisión y un trabajo separados, "
            "explícitamente NO incluidos en este propose ('no implementar'). Orden esperado, "
            "igual que el precedente v2→v3: (1) Capa 9 decide si autoriza redactar ese prompt; "
            "(2) si lo autoriza, se redacta y (eventualmente) se firma; (3) este ADDENDUM (o uno "
            "análogo) se firma human_confirmed; (4) recién entonces "
            "cf6_pilot_scope.evaluate(required_composer_prompt_version="
            f"'{RESERVED_COMPOSER_PROMPT_VERSION}') puede dar GATE_RESULT=PASS."
        ),
        "STOP": "detenerse para decisión de Capa 9 — NO registrar human_confirmed; "
                "NO redactar el prompt; NO ejecutar R2.2/R5.",
    }


if __name__ == "__main__":  # pragma: no cover
    out = Path("docs_plan/shadow_llm/CF6/CF6_v2_R2_SCOPE_ADDENDUM_PROPOSE.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    pkg = package()
    out.write_text(json.dumps(pkg, indent=1, ensure_ascii=False), encoding="utf-8")
    print("WROTE", out)
    print(json.dumps({
        "decision_type": pkg["propose"]["decision_type"],
        "amendment_sequence": pkg["propose"]["amendment_sequence"],
        "supersedes_instance_id": pkg["propose"]["supersedes_instance_id"],
        "composer_prompt_version": pkg["propose"]["payload"]["composer_prompt_version"],
        "composer_prompt_version_status": pkg["propose"]["payload"]["composer_prompt_version_status"],
        "SCOPE_EXTENSION_SUPPORTED": pkg["mechanism_check"]["SCOPE_EXTENSION_SUPPORTED"],
        "written_to_ledger": pkg["propose"]["written_to_ledger"],
    }, indent=1, ensure_ascii=False))
