"""Tests — CF-6 v2.0 · R2 (corrección) — ADDENDUM que añade el token legado
"CF6-3" sin tocar PILOT_EXECUTION-2026-041/-042 ni cambiar el scope ya
aprobado. SHADOW, sin LLM.
"""
import hashlib
from pathlib import Path

from factory.regulatory.shadow import cf6_scope_addendum_v2_r1 as AD_BASE
from factory.regulatory.shadow import cf6_scope_addendum_v2_r1_correction as AD


def test_scope_units_identical_to_base_addendum():
    assert AD.build_addendum_propose()["payload"]["scope"] == AD_BASE._scope_units()


def test_payload_contains_legacy_token_literal():
    p = AD.build_addendum_propose()
    assert p["payload"]["legacy_token"] == "CF6-3"
    assert "CF6-3" in p["reason"]


def test_does_not_reference_editing_041_042():
    p = AD.build_addendum_propose()
    assert p["supersedes_instance_id"] is None
    assert "PILOT_EXECUTION-2026-041" in p["payload"]["extends_instances"]
    assert "PILOT_EXECUTION-2026-042" in p["payload"]["extends_instances"]


def test_does_not_authorize_r2_2_or_r3():
    p = AD.build_addendum_propose()
    not_auth = p["payload"]["not_authorized"]
    assert any("R2.2" in x for x in not_auth)
    assert any("R3" in x for x in not_auth)


def test_package_does_not_touch_real_ledger():
    ledger = (Path(__file__).parent.parent.parent / "factory" / "layer9"
              / "decisions" / "decisions_v2.jsonl")
    before = hashlib.sha256(ledger.read_bytes()).hexdigest()
    AD.build_addendum_propose()
    after = hashlib.sha256(ledger.read_bytes()).hexdigest()
    assert before == after
