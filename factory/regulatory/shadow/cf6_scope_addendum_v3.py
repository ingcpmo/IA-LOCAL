"""SHADOW · CF-6 v1.2 · CF6-2.G (revalidación) — propuesta gobernada de AMPLIACIÓN
de scope de la PILOT para el nuevo composer_prompt_version `shadow-cf6-composer-struct-v3`.

Responde a `PILOT_SCOPE_MATCH_CF6 (vs v3) = NO`: el ADDENDUM
`PILOT_EXECUTION-2026-037/-038` nombra explícitamente `shadow-cf6-composer-struct-v2`,
no v3. Se prepara —sin LLM y sin tocar el ledger— el `propose` de un nuevo ADDENDUM
que añade `shadow-cf6-composer-struct-v3` al scope de la familia PILOT_EXECUTION,
conservando la trazabilidad (ADDENDUM = amplía, no supersede; I-7).

Sólo cambia el `composer_prompt_version`: el TIPO de ejecución
(`structured_json_composer`), CF6-2.5, CF6-3 y el SAMPLE_MANIFEST congelado
(`7422faaf…`) son los mismos.

NO se firma. NO se escribe el ledger. `awaiting: human_confirmed / Capa 9`.
CERO LLM · no muta L2 / human_state / FINDINGS_FINGERPRINT.
"""
from __future__ import annotations

import json
from pathlib import Path

from factory.regulatory.shadow.cf6_scope_addendum import mechanism_check  # reuso: sigue = YES

NEW_COMPOSER_PROMPT_VERSION = "shadow-cf6-composer-struct-v3"
OLD_COMPOSER_PROMPT_VERSION = "shadow-cf6-composer-struct-v2"
EXECUTION_TYPE = "structured_json_composer"
EXTENDS_INSTANCES = ("PILOT_EXECUTION-2026-035", "PILOT_EXECUTION-2026-036",
                     "PILOT_EXECUTION-2026-037", "PILOT_EXECUTION-2026-038")
_CF6_2_5_DOCS = ("RW-0005", "RW-0006", "RW-0012", "RW-0014")
_CF6_3_DOCS = ("RW-0005", "RW-0006", "RW-0009", "RW-0011", "RW-0012", "RW-0014")
CF6_V3_MAX_CALLS = 250
SAMPLE_MANIFEST_HASH = "7422faaf569430dbc8a19647a2d2b64ff6b53b5231fc4e7962b4486e3165f5a0"


def _scope_units() -> list[dict]:
    units = []
    for d in _CF6_2_5_DOCS:
        units.append({"document_id": d, "agent_id": "shadow_composer_expert",
                      "requirement_id": "SHADOW_CF6_COMPOSER", "purpose": EXECUTION_TYPE,
                      "execution_phase": "CF6-2.5",
                      "composer_prompt_version": NEW_COMPOSER_PROMPT_VERSION,
                      "selection_reason": "re-generación de B con v3 sobre el SAMPLE_MANIFEST congelado (por sección)"})
    for d in _CF6_3_DOCS:
        units.append({"document_id": d, "agent_id": "shadow_composer_expert",
                      "requirement_id": "SHADOW_CF6_COMPOSER", "purpose": EXECUTION_TYPE,
                      "execution_phase": "CF6-3",
                      "composer_prompt_version": NEW_COMPOSER_PROMPT_VERSION,
                      "selection_reason": "corrida completa post-gate — 66 secciones documento × regulación"})
    return units


def build_addendum_propose(*, proposed_by_id: str = "Capa 8 (Claude Code)") -> dict:
    units = _scope_units()
    target_ids = sorted({u["document_id"] for u in units})
    payload = {
        "scope": units,
        "max_calls": CF6_V3_MAX_CALLS,
        "authorizes_corpus": False,
        "authorizes_baseline": False,
        "composer_prompt_version": NEW_COMPOSER_PROMPT_VERSION,
        "supersedes_prompt_version": OLD_COMPOSER_PROMPT_VERSION,
        "execution_type": EXECUTION_TYPE,
        "authorizes": ["CF6-2.5 SMALL QUALITY PILOT (re-generación con v3)",
                       "CF6-3 corrida completa post-gate"],
        "extends_instances": list(EXTENDS_INSTANCES),
        "parent_hard_cap": {"instance": "PILOT_EXECUTION-2026-035", "max_calls": 1000,
                            "used_by_g4": 481, "used_by_cf6_2_5_v2": 7, "still_binds": True},
        "sample_manifest_hash": SAMPLE_MANIFEST_HASH,
        "sample_manifest_tag": "cf6-G2.5-manifest",
        "prompt_signature_ref": "shadow-cf6-composer-struct-v3 SIGNED por Capa 9, tag cf6-G2-r1",
        "not_authorized": ["CORPUS_AUTHORIZATION", "D4", "FORMAL_BASELINE_READY",
                           "flip/adjudication/production"],
    }
    reason = (
        "ADDENDUM a la familia PILOT_EXECUTION (extiende -035/-036/-037/-038; NO los "
        "supersede — I-7). Amplía el scope firmado para autorizar EXPLÍCITAMENTE el nuevo "
        f"composer_prompt_version={NEW_COMPOSER_PROMPT_VERSION} (firmado por Capa 9 tras "
        f"HUMAN_QUALITY_GATE=FAIL del CF6-2.5 con {OLD_COMPOSER_PROMPT_VERSION}; tag cf6-G2-r1). "
        "Sólo cambia el prompt: el tipo de ejecución (structured_json_composer), CF6-2.5, CF6-3 "
        f"y el SAMPLE_MANIFEST congelado ({SAMPLE_MANIFEST_HASH[:16]}…, tag cf6-G2.5-manifest) son "
        f"los mismos. Tope duro CF-6 aditivo: {CF6_V3_MAX_CALLS} llamadas; el tope de 1000 de -035 "
        "sigue acotando el total de la familia (481 G4 + 7 del piloto v2). NO autoriza corpus, D4, "
        "baseline formal, flip, adjudicación ni producción."
    )
    return {
        "schema": "SHADOW_CF6_2_G_SCOPE_ADDENDUM_V3_PROPOSE/v1",
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
                     "note": "NO confirmar aquí. Tras confirmación: re-ejecutar cf6_pilot_scope.evaluate("
                             "required_composer_prompt_version='shadow-cf6-composer-struct-v3') -> debe pasar a YES."},
        "invariants": {
            "LLM_CALLS": 0, "G4D_CALLS": 0, "L2_MUTATIONS": 0, "HUMAN_STATE_CHANGES": 0,
            "FINDINGS_FINGERPRINT": "235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23",
        },
    }


if __name__ == "__main__":  # pragma: no cover
    out = Path("docs_plan/shadow_llm/CF6/CF6_2_G_SCOPE_ADDENDUM_V3_PROPOSE.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    rec = build_addendum_propose()
    out.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
    print("WROTE", out)
    print(json.dumps({"decision_type": rec["decision_type"], "amendment_sequence": rec["amendment_sequence"],
                      "supersedes_instance_id": rec["supersedes_instance_id"],
                      "composer_prompt_version": rec["payload"]["composer_prompt_version"],
                      "SCOPE_EXTENSION_SUPPORTED": rec["mechanism_check"]["SCOPE_EXTENSION_SUPPORTED"],
                      "written_to_ledger": rec["written_to_ledger"]}, indent=1, ensure_ascii=False))
