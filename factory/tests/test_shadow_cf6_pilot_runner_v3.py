"""Tests — CF-6 v1.2 · CF6-2.5 (v3) pilot runner + human-gate package (SHADOW).

Dry-run: NO llama al LLM. Verifica el cableado v3 (prompt firmado, allowed_technical_findings
determinista, validate_structure_contract v3, dedupe, Q-STATE sin cambios, fallback),
que el SAMPLE_MANIFEST está FROZEN con hash 7422faaf…, y que NO se sobrescriben los
artefactos del piloto v2.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.shadow import cf6_pilot_runner_v3 as PR3
from factory.regulatory.shadow import cf6_human_gate_v3 as HG3
from factory.regulatory.shadow import composer_prompt_v3 as V3

_REPO = Path(__file__).parent.parent.parent
_SL = _REPO / "docs_plan" / "shadow_llm"
_MANIFEST = _SL / "CF6" / "CF6_2_5_SAMPLE_MANIFEST.json"
_SECTIONS = ["sec-0004", "sec-0005", "sec-0016", "sec-0018", "sec-0026", "sec-0042", "sec-0062"]


def test_preconditions_signed_prompt_and_frozen_manifest():
    assert V3.is_signed() is True
    assert V3.PROMPT_VERSION == "shadow-cf6-composer-struct-v3"
    m = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    assert m["status"].upper().startswith("FROZEN")
    assert m["sample_manifest_hash"].startswith("7422faaf")
    assert m["sections_selected"] == _SECTIONS


def test_dry_run_covers_7_sections_zero_llm_and_deterministic_types(tmp_path):
    s = PR3.run_cf6_2_5_v3(_SL, _MANIFEST, out_dir=tmp_path, dry_run=True)
    assert s["PROMPT_VERSION"] == "shadow-cf6-composer-struct-v3"
    assert s["sections"] == _SECTIONS
    assert s["LLM_CALLS_TOTAL"] == 0
    assert s["within_budget"] is True
    assert s["POST_QSTATE_LLM_CALLS"] == 0
    assert s["G4D_CALLS"] == 0 and s["g4d_reexecuted"] is False
    assert s["L2_MUTATIONS"] == 0 and s["HUMAN_STATE_CHANGES"] == 0
    assert s["FINDINGS_FINGERPRINT"].startswith("235f724a738ce783")
    # sin estructura del LLM -> todas a modo seguro, blacklist-limpio, Q-STATE 0 violaciones publicadas
    assert s["sections_safe_mode"] == 7
    assert s["blacklist_hits_in_published"] == 0
    assert s["qstate_violations_in_published"] == 0
    atf = s["ALLOWED_TECHNICAL_FINDINGS_BY_SECTION"]
    assert atf["sec-0026"] == ["BACKUP_RECOVERY_GAP"]
    assert atf["sec-0042"] == ["IMPLEMENTATION_WITHOUT_REQUIREMENT", "ORPHAN_DESIGN_ELEMENT"]
    assert atf["sec-0005"] == [] and atf["sec-0016"] == [] and atf["sec-0062"] == []
    assert atf["sec-0004"] == ["ACCESS_CONTROL_GAP", "AUTHORITY_CHECK_GAP"]


def test_dry_run_does_not_overwrite_v2_pilot_artifacts(tmp_path):
    import hashlib
    v2b = _SL / "CF6" / "CF6_2_5_B_OUTPUTS.jsonl"
    v2r = _SL / "CF6" / "CF6_2_5_PILOT_RUN.json"
    before = (hashlib.sha256(v2b.read_bytes()).hexdigest(), hashlib.sha256(v2r.read_bytes()).hexdigest())
    PR3.run_cf6_2_5_v3(_SL, _MANIFEST, out_dir=tmp_path, dry_run=True)
    after = (hashlib.sha256(v2b.read_bytes()).hexdigest(), hashlib.sha256(v2r.read_bytes()).hexdigest())
    assert before == after
    assert (tmp_path / "CF6_2_5_v3_B_OUTPUTS.jsonl").is_file()
    assert (tmp_path / "CF6_2_5_v3_PILOT_RUN.json").is_file()


def test_budget_cap_and_pilot_instance():
    assert PR3.CF6_MAX_CALLS == 250
    assert PR3.PILOT_INSTANCE == "PILOT_EXECUTION-2026-040"


def test_human_gate_v3_package_is_per_section_llm_free_and_unscored(tmp_path):
    PR3.run_cf6_2_5_v3(_SL, _MANIFEST, out_dir=tmp_path, dry_run=True)
    md = HG3.build(_SL, _MANIFEST, tmp_path / "CF6_2_5_v3_B_OUTPUTS.jsonl")
    assert "shadow-cf6-composer-struct-v3" in md
    assert "Claude Code **no** puntúa ni declara PASS/FAIL" in md
    for sid in _SECTIONS:
        assert f"## {sid}" in md
        assert f"Rúbrica §4.2 — {sid}" in md
    assert "A — reporte determinista L2" in md
    assert "B — resultado CF6 v3" in md
    assert "HUMAN_QUALITY_GATE (v3) = PENDIENTE" in md
