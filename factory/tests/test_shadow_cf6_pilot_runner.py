"""Tests — CF-6 v1.2 · CF6-2.5 pilot runner + human-gate package (SHADOW).

El dry-run NO llama al LLM: valida el cableado (contexto determinista, prompt
firmado, gate composer_gate, fallback modo seguro) y que el manifest esté FROZEN.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.shadow import cf6_pilot_runner as PR
from factory.regulatory.shadow import cf6_human_gate as HG
from factory.regulatory.shadow import composer_prompt as CP

_REPO = Path(__file__).parent.parent.parent
_SL = _REPO / "docs_plan" / "shadow_llm"
_MANIFEST = _SL / "CF6" / "CF6_2_5_SAMPLE_MANIFEST.json"


def test_runner_requires_signed_prompt_and_frozen_manifest():
    assert CP.is_signed() is True                       # prerequisito CF6-2
    import json
    m = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    assert m["status"].upper().startswith("FROZEN")     # prerequisito CF6-2.5 §4.1


def test_dry_run_covers_the_7_manifest_sections_with_zero_llm(tmp_path):
    s = PR.run_cf6_2_5(_SL, _MANIFEST, out_dir=tmp_path, dry_run=True)
    assert s["n_sections"] == 7
    assert s["sections"] == ["sec-0004", "sec-0005", "sec-0016", "sec-0018",
                             "sec-0026", "sec-0042", "sec-0062"]
    assert s["llm_calls"] == 0
    assert s["within_budget"] is True
    assert s["post_qstate_llm_calls_total"] == 0
    assert s["g4d_reexecuted"] is False
    # sin estructura del LLM -> todas a modo determinista seguro, blacklist-limpio
    assert s["sections_safe_mode"] == 7
    assert s["blacklist_hits_in_published"] == 0
    assert s["qstate_violations_in_published"] == 0
    assert s["integrity"]["FINDINGS_FINGERPRINT"].startswith("235f724a738ce783")
    assert (tmp_path / "CF6_2_5_B_OUTPUTS.jsonl").is_file()


def test_dry_run_section_types_are_deterministic(tmp_path):
    s = PR.run_cf6_2_5(_SL, _MANIFEST, out_dir=tmp_path, dry_run=True)
    by = {p["section_id"]: p for p in s["per_section"]}
    assert by["sec-0016"]["section_type"] == "REGULATORY"
    assert by["sec-0018"]["section_type"] == "CROSS_DOMAIN"
    assert by["sec-0026"]["section_type"] == "TECHNICAL"
    assert by["sec-0042"]["section_type"] == "FUNCTIONAL_TRACEABILITY"
    for sid in ("sec-0016", "sec-0018", "sec-0062", "sec-0004", "sec-0005"):
        assert by[sid]["regulatory_state"] == "INCONCLUSIVE"
    for sid in ("sec-0026", "sec-0042"):
        assert by[sid]["regulatory_state"] == "NOT_APPLICABLE"


def test_budget_cap_is_the_cf6_addendum_allocation():
    assert PR.CF6_MAX_CALLS == 250
    assert PR.PILOT_INSTANCE == "PILOT_EXECUTION-2026-038"


def test_human_gate_package_is_per_section_and_llm_free(tmp_path):
    # requiere que exista un B_OUTPUTS; usa el del dry-run
    PR.run_cf6_2_5(_SL, _MANIFEST, out_dir=tmp_path, dry_run=True)
    md = HG.build(_SL, _MANIFEST, tmp_path / "CF6_2_5_B_OUTPUTS.jsonl")
    assert "HUMAN_QUALITY_GATE" in md
    assert "PASS del conjunto solo si CADA sección" in md
    assert "Sobreafirmación regulatoria" in md
    for sid in ("sec-0004", "sec-0005", "sec-0016", "sec-0018", "sec-0026", "sec-0042", "sec-0062"):
        assert f"## {sid}" in md
        assert f"Rúbrica §4.2 — {sid}" in md
    assert "A — reporte determinista L2" in md
    assert "B — narrativa CF6-2.5" in md
    assert "HUMAN_QUALITY_GATE = PENDIENTE" in md
