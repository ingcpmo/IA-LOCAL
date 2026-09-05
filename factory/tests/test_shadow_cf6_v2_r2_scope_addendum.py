"""Tests — CF-6 v2.0 · R2 — propuesta gobernada de ampliación de scope para el
Composer de 4 pasos con Relevance Model (R1, tag cf6-v2-R1). SHADOW, sin LLM.

Verifica que el `propose` preparado tiene la forma correcta, extiende (no
supersede) las PILOT_EXECUTION vigentes, reserva el nombre del prompt sin
inventar que ya existe, y NO toca el ledger real ni registra human_confirmed.
"""
import hashlib
from pathlib import Path

from factory.regulatory.shadow import cf6_scope_addendum_v2_r1 as AD
from factory.regulatory.shadow import cf6_pilot_scope as scope


def test_scope_extension_is_supported_via_addendum():
    mc = AD.mechanism_check()
    assert mc["SCOPE_EXTENSION_SUPPORTED"] == "YES"
    assert "ADDENDUM" in mc["evidence"]["COVERING_TYPES"]
    assert "ADDENDUM" not in mc["evidence"]["AMENDING_TYPES"]


def test_addendum_propose_shape():
    p = AD.build_addendum_propose()
    assert p["family"] == "PILOT_EXECUTION"
    assert p["decision_type"] == "ADDENDUM"
    assert p["amendment_sequence"] == 1
    assert p["supersedes_instance_id"] is None            # I-7: amplía, no supersede
    assert p["decision_origin"] == "agent_proposed"
    assert p["written_to_ledger"] is False
    pl = p["payload"]
    assert pl["composer_prompt_version"] == AD.RESERVED_COMPOSER_PROMPT_VERSION
    assert pl["composer_prompt_version_status"] == "RESERVED_NAME_NOT_YET_DRAFTED"
    assert pl["execution_type"] == "structured_json_composer_relevance_filtered"
    assert pl["authorizes_corpus"] is False and pl["authorizes_baseline"] is False
    assert set(AD.EXTENDS_INSTANCES) <= set(pl["extends_instances"])
    assert "PILOT_EXECUTION-2026-039" in pl["extends_instances"]
    assert "PILOT_EXECUTION-2026-040" in pl["extends_instances"]
    assert all(u["composer_prompt_version"] == AD.RESERVED_COMPOSER_PROMPT_VERSION for u in pl["scope"])


def test_does_not_authorize_out_of_scope_decisions():
    p = AD.build_addendum_propose()
    not_auth = p["payload"]["not_authorized"]
    for token in ("CORPUS_AUTHORIZATION", "D4", "D-ADJ", "D-M4+", "D-REPORT-EXT"):
        assert any(token in x for x in not_auth), token


def test_package_stops_before_human_confirmed():
    pkg = AD.package()
    assert pkg["llm_calls"] == 0
    assert pkg["propose"]["awaiting"]["action"] == "human_confirmed"
    assert pkg["propose"]["awaiting"]["authority"] == "Capa 9 (Cesar)"
    assert "NO redactar el prompt" in pkg["STOP"]
    assert pkg["propose"]["invariants"] == {
        "LLM_CALLS": 0, "G4D_CALLS": 0, "L2_MUTATIONS": 0, "HUMAN_STATE_CHANGES": 0}


def test_addendum_confirmed_in_real_ledger_matches_check_a_by_name_only():
    """Aprobado por Capa 9 (2026-09-04) y formalizado vía `governance_service`:
    `PILOT_EXECUTION-2026-041` (propose) / `-042` (human_confirmed, cesar), y
    posteriormente el ADDENDUM correctivo `-043`/`-044` (añade el token legado
    'CF6-3' exigido por el chequeo c_cf6_3, sin editar -041/-042 -- append-only).
    `cf6_pilot_scope.evaluate()` hace COINCIDENCIA DE TEXTO contra el ÚLTIMO
    registro `human_confirmed` del ledger -- por eso `pilot_instance` avanza a
    `-044` tras la corrección, aunque `-042` sigue ACTIVE y sin editar."""
    res = scope.evaluate(required_composer_prompt_version=AD.RESERVED_COMPOSER_PROMPT_VERSION)
    assert res["pilot_instance"] == "PILOT_EXECUTION-2026-044"
    assert res["pilot_decision_origin"] == "human_confirmed"
    assert res["scope_checks"]["a_composer_prompt_version"] == "YES"
    assert res["ACTIVE"] == "YES"
    assert res["NOT_SUPERSEDED"] == "YES"
    assert res["REMAINING_BUDGET_SUFFICIENT"] == "YES"


def test_building_the_package_does_not_touch_the_real_ledger():
    ledger = (Path(__file__).parent.parent.parent / "factory" / "layer9"
              / "decisions" / "decisions_v2.jsonl")
    before = hashlib.sha256(ledger.read_bytes()).hexdigest()
    AD.package()
    AD.build_addendum_propose()
    after = hashlib.sha256(ledger.read_bytes()).hexdigest()
    assert before == after


def test_does_not_touch_decomposition_yaml():
    from factory.regulatory.requirement_catalog.requirement_decomposition_loader import (
        DECOMPOSITION_PATH,
    )
    before = hashlib.sha256(DECOMPOSITION_PATH.read_bytes()).hexdigest()
    AD.package()
    after = hashlib.sha256(DECOMPOSITION_PATH.read_bytes()).hexdigest()
    assert before == after
