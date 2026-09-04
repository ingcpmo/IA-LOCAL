"""SHADOW · CF-6 v2.0 · R2 (corrección) — ADDENDUM adicional que añade el
token literal "CF6-3" al scope ya aprobado, sin tocar
`PILOT_EXECUTION-2026-041/-042` (append-only -- no se editan) y sin cambiar
NINGUNA unidad de scope ya confirmada.

Causa (`docs_plan/shadow_llm/CF6/CF6_v2_R2_GATE_RECHECK.md`): el chequeo
`c_cf6_3` de `cf6_pilot_scope.py` -- heredado tal cual de v1.2/v1.3, sin
modificar aquí -- exige uno de los tokens literales `"CF6-3"` / `"cf6_3"` /
`"corrida completa cf6"` / `"full cf6"` en el scope firmado. El ADDENDUM
`-041/-042` usó la terminología de fases del diseño v2.0 (`"CF6-v2-R5"`,
"corrida completa bajo la arquitectura R1-R3, diseño §13, R5") y no incluyó
ninguno de esos tokens -- coincidencia de texto rota por elección de
palabras, no una falla de scope real.

**Este módulo CONSERVA exactamente las mismas unidades de scope que
`cf6_scope_addendum_v2_r1._scope_units()`** (reutilizadas sin cambio) y
AÑADE, sin tocarlas, un campo explícito de alias legado (`legacy_token`) más
una mención literal de `"CF6-3"` en `reason`. NO se relaja ningún chequeo:
se completa el vocabulario que el chequeo ya exigía, con el mismo
significado ya autorizado (la corrida completa de R5 ES, sustantivamente,
lo que v1.2/v1.3 llamaba "CF6-3": la corrida completa post-gate, 66
secciones documento × regulación).

Mismo patrón histórico que -037/-038 (v2) seguido de -039/-040 (v3):
ADDENDUM independiente, `decision_type=ADDENDUM`, `amendment_sequence=1`,
`supersedes_instance_id=None` (I-7 -- amplía, nunca supersede).

NO llama a `governance_service.propose` sobre el ledger real desde este
módulo importado sin más -- el `propose`/`confirm` real se ejecuta desde el
script de cierre de la fase (ver reporte), igual que -041/-042. CERO LLM ·
CERO red · no muta L2 / human_state / FINDINGS_FINGERPRINT / decomposition.yaml.
"""
from __future__ import annotations

import json
from pathlib import Path

from factory.regulatory.shadow.cf6_scope_addendum import mechanism_check
from factory.regulatory.shadow.cf6_scope_addendum_v2_r1 import (
    CF6_V2_R2_MAX_CALLS,
    RESERVED_COMPOSER_PROMPT_VERSION,
    _scope_units,
)

LEGACY_TOKEN = "CF6-3"
EXTENDS_INSTANCES = ("PILOT_EXECUTION-2026-035", "PILOT_EXECUTION-2026-036",
                     "PILOT_EXECUTION-2026-037", "PILOT_EXECUTION-2026-038",
                     "PILOT_EXECUTION-2026-039", "PILOT_EXECUTION-2026-040",
                     "PILOT_EXECUTION-2026-041", "PILOT_EXECUTION-2026-042")


def build_addendum_propose(*, proposed_by_id: str = "cf6_scope_addendum_agent") -> dict:
    units = _scope_units()   # EXACTAMENTE las mismas unidades que -041/-042, sin cambio
    target_ids = sorted({u["document_id"] for u in units})
    payload = {
        "scope": units,
        "max_calls": CF6_V2_R2_MAX_CALLS,
        "authorizes_corpus": False,
        "authorizes_baseline": False,
        "composer_prompt_version": RESERVED_COMPOSER_PROMPT_VERSION,
        "corrects_gate_check": "c_cf6_3 (cf6_pilot_scope.py, heredado de v1.2/v1.3, sin modificar)",
        "legacy_token": LEGACY_TOKEN,
        "legacy_token_meaning": (
            "El token 'CF6-3' (v1.2/v1.3: corrida completa post-gate, 66 secciones "
            "documento x regulacion) es, sustantivamente, la misma corrida que "
            "'CF6-v2-R5' en el diseno v2.0 (corrida completa bajo la arquitectura "
            "R1-R3, ver diseno paragrafo 13). Este ADDENDUM completa el vocabulario "
            "que el gate ya exigia -- no amplia el alcance sustantivo autorizado en "
            "-041/-042."),
        "extends_instances": list(EXTENDS_INSTANCES),
        "corrects_instance": "PILOT_EXECUTION-2026-042 (NO se edita -- append-only; este "
                             "ADDENDUM la complementa)",
        "parent_hard_cap": {"instance": "PILOT_EXECUTION-2026-035", "max_calls": 1000,
                            "used_by_g4": 481, "used_by_cf6_2_5_v2": 7, "used_by_cf6_2_5_v3": 7,
                            "still_binds": True},
        "not_authorized": ["CORPUS_AUTHORIZATION", "D4", "FORMAL_BASELINE_READY",
                           "flip/adjudication/production", "D-ADJ", "D-M4+", "D-REPORT-EXT",
                           "R2.2 (regeneración con LLM)", "R3"],
    }
    reason = (
        f"ADDENDUM CORRECTIVO (extiende -035..-042; NO las supersede -- I-7; NO edita "
        f"-041/-042, append-only). Añade el token legado requerido por el chequeo "
        f"c_cf6_3 de cf6_pilot_scope.py: '{LEGACY_TOKEN}'. La corrida completa "
        f"'CF6-v2-R5' del scope YA APROBADO en -041/-042 (mismas unidades, sin cambio "
        f"-- ver payload.scope) ES, sustantivamente, la corrida que v1.2/v1.3 llamaba "
        f"'{LEGACY_TOKEN}': corrida completa post-gate, 66 secciones documento x "
        f"regulacion. Este ADDENDUM no amplia scope sustantivo, solo completa el "
        f"vocabulario que el chequeo heredado exige por texto. NO autoriza R2.2, R3, "
        f"corpus, D4, baseline formal, flip, adjudicacion, produccion, ni D-ADJ/D-M4+/"
        f"D-REPORT-EXT."
    )
    return {
        "schema": "SHADOW_CF6_V2_R2_SCOPE_ADDENDUM_CORRECTION_PROPOSE/v1",
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


if __name__ == "__main__":  # pragma: no cover
    out = Path("docs_plan/shadow_llm/CF6/CF6_v2_R2_SCOPE_ADDENDUM_CORRECTION_PROPOSE.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    rec = build_addendum_propose()
    out.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
    print("WROTE", out)
    print(json.dumps({"decision_type": rec["decision_type"], "legacy_token": rec["payload"]["legacy_token"],
                      "target_ids": rec["target_ids"], "written_to_ledger": rec["written_to_ledger"]},
                     indent=1, ensure_ascii=False))
