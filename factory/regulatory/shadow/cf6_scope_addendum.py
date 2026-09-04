"""SHADOW · CF-6 v1.2 · CF6-2.G — propuesta gobernada de AMPLIACIÓN de scope de la PILOT.

Responde a `PILOT_SCOPE_MATCH_CF6 = NO` (CF6-2.G FAIL) preparando —sin LLM y sin
tocar el ledger canónico— el `propose` de un **ADDENDUM** a la familia
`PILOT_EXECUTION` que conserva la trazabilidad de `PILOT_EXECUTION-2026-035/-036`.

Por qué ADDENDUM (mecanismo oficial):
  - `decision_store_v2.COVERING_TYPES = {ORIGINAL, CORRECTION, ADDENDUM, SUPERSESSION}`
    → el `decision_scope_resolver` **une** los target_ids de todos los registros
    `human_confirmed` ACTIVE de esos tipos.
  - `ADDENDUM ∉ AMENDING_TYPES` y la invariante **I-7**: "ADDENDUM amplía, no
    supersede — no puede referenciar `supersedes_*`" + `amendment_sequence >= 1`.
    → `-035/-036` siguen ACTIVE y cubriendo; el ADDENDUM SUMA el scope de CF-6
    sin superseder nada (trazabilidad intacta).
  - Familia `PILOT_EXECUTION`: `requires_human_confirmation: true`,
    `selection_modes: [EXPLICIT_LIST]`, sin lista blanca de `decision_type`.

Este módulo NO llama a `governance_service.propose` sobre el ledger real: entrega el
PAQUETE del propose (campos exactos + llamada equivalente) para que Capa 9 lo someta
por el canal gobernado (Mission Control), igual que `-035`. NO registra
`human_confirmed`.

CERO LLM · CERO red · no muta L2 / human_state / FINDINGS_FINGERPRINT / el ledger.
"""
from __future__ import annotations

import json
from pathlib import Path

COMPOSER_PROMPT_VERSION = "shadow-cf6-composer-struct-v2"
EXECUTION_TYPE = "structured_json_composer"
EXTENDS_INSTANCES = ("PILOT_EXECUTION-2026-035", "PILOT_EXECUTION-2026-036")

# documentos del arco shadow (RW-*). CF6-2.5 = subconjunto del SAMPLE_MANIFEST;
# CF6-3 = corrida completa (66 secciones, 6 documentos).
_CF6_2_5_DOCS = ("RW-0005", "RW-0006", "RW-0012", "RW-0014")   # docs de las 7 secciones del manifest
_CF6_3_DOCS = ("RW-0005", "RW-0006", "RW-0009", "RW-0011", "RW-0012", "RW-0014")

# tope duro CF-6 (aditivo). CF6-2.5 ≤ 7 secc · CF6-3 ≤ 66 secc; con reintentos/margen.
CF6_MAX_CALLS = 250


def mechanism_check() -> dict:
    """SCOPE_EXTENSION_SUPPORTED — ¿el mecanismo oficial permite ampliar una PILOT
    vigente conservando su trazabilidad?"""
    try:
        from factory.services import decision_store_v2 as _ds
        covering = sorted(_ds.COVERING_TYPES)
        amending = sorted(_ds.AMENDING_TYPES)
    except Exception:  # noqa: BLE001
        covering, amending = [], []
    addendum_is_covering = "ADDENDUM" in covering
    addendum_not_amending = "ADDENDUM" not in amending
    supported = addendum_is_covering and addendum_not_amending
    return {
        "SCOPE_EXTENSION_SUPPORTED": "YES" if supported else "NO",
        "mechanism": "decision_type=ADDENDUM en la familia PILOT_EXECUTION",
        "evidence": {
            "COVERING_TYPES": covering,
            "AMENDING_TYPES": amending,
            "ADDENDUM_is_covering_type": addendum_is_covering,
            "ADDENDUM_not_amending (no supersede)": addendum_not_amending,
            "I-7": "ADDENDUM amplía, no supersede — sin supersedes_*, amendment_sequence>=1",
            "resolver": "decision_scope_resolver une target_ids de los COVERING_TYPES "
                        "human_confirmed ACTIVE (union de otorgantes menos revocaciones)",
            "family_PILOT_EXECUTION": {"requires_human_confirmation": True,
                                       "selection_modes": ["EXPLICIT_LIST"],
                                       "decision_type_allowlist": None},
        },
        "traceability": (f"-035/-036 permanecen ACTIVE y cubriendo; el ADDENDUM referencia "
                         f"{list(EXTENDS_INSTANCES)} en `reason` y NO los supersede"),
    }


def _scope_units() -> list[dict]:
    units: list[dict] = []
    for d in _CF6_2_5_DOCS:
        units.append({
            "document_id": d, "agent_id": "shadow_composer_expert",
            "requirement_id": "SHADOW_CF6_COMPOSER",
            "purpose": EXECUTION_TYPE, "execution_phase": "CF6-2.5",
            "composer_prompt_version": COMPOSER_PROMPT_VERSION,
            "selection_reason": "SMALL QUALITY PILOT — secciones del SAMPLE_MANIFEST (por sección)",
        })
    for d in _CF6_3_DOCS:
        units.append({
            "document_id": d, "agent_id": "shadow_composer_expert",
            "requirement_id": "SHADOW_CF6_COMPOSER",
            "purpose": EXECUTION_TYPE, "execution_phase": "CF6-3",
            "composer_prompt_version": COMPOSER_PROMPT_VERSION,
            "selection_reason": "corrida completa post-gate — 66 secciones documento × regulación",
        })
    return units


def build_addendum_propose(*, proposed_by_id: str = "Capa 8 (Claude Code)",
                           sample_manifest_hash: str | None = None) -> dict:
    units = _scope_units()
    target_ids = sorted({u["document_id"] for u in units})
    payload = {
        "scope": units,
        "max_calls": CF6_MAX_CALLS,
        "authorizes_corpus": False,
        "authorizes_baseline": False,
        # autorizaciones explícitas que exige CF6-2.G (§6)
        "composer_prompt_version": COMPOSER_PROMPT_VERSION,
        "execution_type": EXECUTION_TYPE,
        "authorizes": ["CF6-2.5 SMALL QUALITY PILOT", "CF6-3 corrida completa post-gate"],
        "extends_instances": list(EXTENDS_INSTANCES),
        "parent_hard_cap": {"instance": "PILOT_EXECUTION-2026-035", "max_calls": 1000,
                            "used_by_g4": 481, "still_binds": True},
        "sample_manifest_hash": sample_manifest_hash,
        "not_authorized": ["CORPUS_AUTHORIZATION", "D4", "FORMAL_BASELINE_READY",
                           "flip/adjudication/production"],
    }
    reason = (
        "ADDENDUM a PILOT_EXECUTION-2026-035/-036 (NO los supersede — I-7). Amplía el "
        "scope firmado para autorizar EXPLÍCITAMENTE el arco CF-6 v1.2: "
        f"composer_prompt_version={COMPOSER_PROMPT_VERSION} (firmado por Capa 9, tag cf6-G2), "
        "ejecución CF6-2.5 (SMALL QUALITY PILOT sobre el SAMPLE_MANIFEST, evaluación por "
        "sección), ejecución CF6-3 (corrida completa post-gate), y el tipo de ejecución "
        f"'{EXECUTION_TYPE}' (emisión de estructura JSON del Composer, no la interpretación "
        "experta de prosa libre que -035/-036 autorizó para SHADOW_G4A..G4E). Tope duro "
        f"CF-6 aditivo: {CF6_MAX_CALLS} llamadas; el tope de 1000 de -035 sigue acotando el "
        "total de la familia (481 usadas por G4). NO autoriza corpus, D4, baseline formal, "
        "flip, adjudicación ni producción."
    )
    return {
        "schema": "SHADOW_CF6_2_G_SCOPE_ADDENDUM_PROPOSE/v1",
        "action": "propose",
        "decision_origin": "agent_proposed",
        "written_to_ledger": False,
        "submit_via": "canal gobernado (Mission Control) — Capa 9, igual que -035",
        "family": "PILOT_EXECUTION",
        "decision": "APPROVE",
        "decision_type": "ADDENDUM",
        "amendment_sequence": 1,
        "selection_mode": "EXPLICIT_LIST",
        "supersedes_instance_id": None,              # I-7: ADDENDUM no supersede
        "proposed_by_id": proposed_by_id,
        "target_ids": target_ids,
        "payload": payload,
        "reason": reason,
        "equivalent_call": (
            "factory.services.governance_service.propose("
            "family='PILOT_EXECUTION', target_ids=%r, decision='APPROVE', "
            "decision_type='ADDENDUM', selection_mode='EXPLICIT_LIST', amendment_sequence=1, "
            "proposed_by_id=%r, reason=<reason>, payload=<payload>)" % (target_ids, proposed_by_id)),
        "awaiting": {"action": "human_confirmed", "authority": "Capa 9 (Cesar)",
                     "note": "NO registrar human_confirmed todavía — detenerse para aprobación."},
        "invariants": {
            "LLM_CALLS": 0, "G4D_CALLS": 0, "L2_MUTATIONS": 0, "HUMAN_STATE_CHANGES": 0,
            "FINDINGS_FINGERPRINT": "235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23",
        },
    }


def dry_run_validate(*, sample_manifest_hash: str | None = None) -> dict:
    """Valida la FORMA del ADDENDUM contra las invariantes de decision_store_v2
    usando un almacén SCRATCH (nunca el ledger real)."""
    import tempfile
    pkg = build_addendum_propose(sample_manifest_hash=sample_manifest_hash)
    out = {"checked": [], "violations": []}
    try:
        from factory.services import decision_store_v2 as _ds
        with tempfile.TemporaryDirectory() as td:
            scratch = Path(td) / "scratch_decisions.jsonl"
            scratch.write_text("", encoding="utf-8")
            rec = _ds.build_record(
                decision_family=pkg["family"], decision_type=pkg["decision_type"],
                selection_mode=pkg["selection_mode"], resolved_target_ids=pkg["target_ids"],
                decision=pkg["decision"], decision_origin="agent_proposed",
                proposed_by_id=pkg["proposed_by_id"],
                supersedes_instance_id=None, amendment_sequence=pkg["amendment_sequence"],
                reason=pkg["reason"], payload=pkg["payload"], store_file=scratch)
            out["checked"].append("build_record OK")
            # I-5/I-7 checks explícitos
            if rec["decision_type"] == "ADDENDUM":
                if rec.get("supersedes_instance_id") or rec.get("supersedes_event_id"):
                    out["violations"].append("I-7: ADDENDUM no puede supersedes_*")
                if rec["amendment_sequence"] < 1:
                    out["violations"].append("I-7: ADDENDUM exige amendment_sequence>=1")
            out["checked"].append("I-7 ADDENDUM (sin supersede, amendment_sequence>=1) OK")
            out["record_shape"] = {k: rec.get(k) for k in
                                   ("decision_family", "decision_type", "amendment_sequence",
                                    "selection_mode", "decision_origin", "status",
                                    "target_set_hash")}
    except Exception as e:  # noqa: BLE001
        out["violations"].append(f"error de validación: {type(e).__name__}: {e}")
    out["PASS"] = not out["violations"]
    return out


def package(*, sample_manifest_hash: str | None = None) -> dict:
    return {
        "schema": "SHADOW_CF6_2_G_SCOPE_RESOLUTION/v1",
        "trigger": "CF6-2.G · PILOT_SCOPE_MATCH_CF6 = NO",
        "llm_calls": 0,
        "mechanism_check": mechanism_check(),
        "propose": build_addendum_propose(sample_manifest_hash=sample_manifest_hash),
        "dry_run_validation": dry_run_validate(sample_manifest_hash=sample_manifest_hash),
        "STOP": "detenerse para aprobación de Capa 9 — NO registrar human_confirmed; "
                "NO ejecutar CF6-2.5 ni CF6-3.",
    }


if __name__ == "__main__":  # pragma: no cover
    import sys
    smh = None
    mp = Path("docs_plan/shadow_llm/CF6/CF6_2_5_SAMPLE_MANIFEST.json")
    if mp.is_file():
        smh = json.loads(mp.read_text(encoding="utf-8")).get("sample_manifest_hash")
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "docs_plan/shadow_llm/CF6/CF6_2_G_SCOPE_ADDENDUM_PROPOSE.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    pkg = package(sample_manifest_hash=smh)
    out.write_text(json.dumps(pkg, indent=1, ensure_ascii=False), encoding="utf-8")
    print("WROTE", out)
    print(json.dumps({"SCOPE_EXTENSION_SUPPORTED": pkg["mechanism_check"]["SCOPE_EXTENSION_SUPPORTED"],
                      "decision_type": pkg["propose"]["decision_type"],
                      "amendment_sequence": pkg["propose"]["amendment_sequence"],
                      "target_ids": pkg["propose"]["target_ids"],
                      "dry_run_PASS": pkg["dry_run_validation"]["PASS"],
                      "written_to_ledger": pkg["propose"]["written_to_ledger"]},
                     indent=1, ensure_ascii=False))
