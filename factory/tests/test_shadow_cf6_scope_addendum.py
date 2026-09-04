"""Tests — CF-6 v1.2 · CF6-2.G — propuesta gobernada de ampliación de scope (SHADOW, sin LLM).

Verifica que el mecanismo oficial permite ampliar la PILOT vigente conservando
trazabilidad (ADDENDUM) y que el `propose` preparado tiene la forma correcta,
SIN registrar human_confirmed y SIN tocar el ledger.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.shadow import cf6_scope_addendum as AD


def test_scope_extension_is_supported_via_addendum():
    mc = AD.mechanism_check()
    assert mc["SCOPE_EXTENSION_SUPPORTED"] == "YES"
    ev = mc["evidence"]
    assert "ADDENDUM" in ev["COVERING_TYPES"]
    assert "ADDENDUM" not in ev["AMENDING_TYPES"]          # amplía, no supersede
    assert ev["ADDENDUM_is_covering_type"] is True
    assert "PILOT_EXECUTION-2026-035" in mc["traceability"]


def test_addendum_propose_shape_authorizes_the_four_items():
    p = AD.build_addendum_propose(sample_manifest_hash="deadbeef")
    assert p["family"] == "PILOT_EXECUTION"
    assert p["decision_type"] == "ADDENDUM"
    assert p["amendment_sequence"] == 1
    assert p["supersedes_instance_id"] is None            # I-7
    assert p["decision_origin"] == "agent_proposed"
    assert p["written_to_ledger"] is False
    pl = p["payload"]
    assert pl["composer_prompt_version"] == "shadow-cf6-composer-struct-v2"
    assert pl["execution_type"] == "structured_json_composer"
    assert pl["authorizes"] == ["CF6-2.5 SMALL QUALITY PILOT", "CF6-3 corrida completa post-gate"]
    assert pl["extends_instances"] == ["PILOT_EXECUTION-2026-035", "PILOT_EXECUTION-2026-036"]
    assert pl["authorizes_corpus"] is False and pl["authorizes_baseline"] is False
    assert pl["sample_manifest_hash"] == "deadbeef"
    phases = {u["execution_phase"] for u in pl["scope"]}
    assert phases == {"CF6-2.5", "CF6-3"}
    assert all(u["composer_prompt_version"] == "shadow-cf6-composer-struct-v2" for u in pl["scope"])


def test_addendum_dry_run_validates_against_decision_store_invariants():
    dr = AD.dry_run_validate(sample_manifest_hash="deadbeef")
    assert dr["PASS"] is True, dr["violations"]
    assert dr["record_shape"]["decision_type"] == "ADDENDUM"
    assert dr["record_shape"]["amendment_sequence"] == 1
    assert dr["record_shape"]["selection_mode"] == "EXPLICIT_LIST"


def test_package_stops_before_human_confirmed_and_keeps_invariants():
    pkg = AD.package(sample_manifest_hash="deadbeef")
    assert pkg["llm_calls"] == 0
    assert pkg["propose"]["awaiting"]["action"] == "human_confirmed"
    assert pkg["propose"]["awaiting"]["authority"] == "Capa 9 (Cesar)"
    assert "NO registrar human_confirmed" in pkg["STOP"]
    assert pkg["propose"]["invariants"] == {
        "LLM_CALLS": 0, "G4D_CALLS": 0, "L2_MUTATIONS": 0, "HUMAN_STATE_CHANGES": 0,
        "FINDINGS_FINGERPRINT": "235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23"}


def test_building_the_package_does_not_touch_the_real_ledger():
    import hashlib
    ledger = (Path(__file__).parent.parent.parent / "factory" / "layer9"
              / "decisions" / "decisions_v2.jsonl")
    before = hashlib.sha256(ledger.read_bytes()).hexdigest()
    AD.package(sample_manifest_hash="deadbeef")     # incluye dry_run_validate (usa store scratch)
    AD.build_addendum_propose()
    after = hashlib.sha256(ledger.read_bytes()).hexdigest()
    assert before == after                          # el ledger canónico no se escribió
