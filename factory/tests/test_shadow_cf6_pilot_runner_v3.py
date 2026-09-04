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


def test_fix_A_exactly_one_llm_call_per_section(monkeypatch, tmp_path):
    calls = {"n": 0}

    def fake_call(prompt, **kw):
        calls["n"] += 1
        return ("{ esto no es json valido", 0.01, {})   # falla -> antes reintentaba, ahora NO

    monkeypatch.setattr(PR3, "_call_llm", fake_call)
    s = PR3.run_cf6_2_5_v3(_SL, _MANIFEST, out_dir=tmp_path, dry_run=False)
    assert s["LLM_CALLS_TOTAL"] == 7                      # 1 por sección, sin reintento
    assert all(v == 1 for v in s["LLM_CALLS_BY_SECTION"].values())
    assert calls["n"] == 7
    assert s["sections_safe_mode"] == 7
    assert s["POST_QSTATE_LLM_CALLS"] == 0


def test_fix_B_dedup_before_validation_rescues_duplicate_only_section(monkeypatch, tmp_path):
    # sec-0026: TECHNICAL / NOT_APPLICABLE, allowed=[BACKUP_RECOVERY_GAP], 1 finding.
    import json as _json
    l2 = json.loads((_SL / "FINAL_GMP_CORPUS_FINDINGS.json").read_text(encoding="utf-8"))["findings"]
    from factory.regulatory.shadow import composer as _skel
    sec = next(s for s in _skel.build_composer_skeleton(l2)["sections"] if s["section_id"] == "sec-0026")
    rid = (sec.get("finding_record_ids") or [e["finding_record_id"] for e in sec["entries"]])[0]
    f = next(x for x in l2 if x["finding_record_id"] == rid)
    q = (f.get("evidence") or {}).get("anchored_quote") or f.get("source_text")

    good_with_dupes = {
        "section_type": "TECHNICAL", "regulatory_state": "NOT_APPLICABLE",
        "evidence_observed": [{"finding_record_id": rid, "quote": q},
                              {"finding_record_id": rid, "quote": q}],   # duplicado textual
        "evidence_limitation": ["no se ancló eco léxico en el alcance revisado"],
        "technical_findings": ["BACKUP_RECOVERY_GAP"],
        "reviewer_action": "Revisar en el documento fuente si el respaldo por batería está descrito",
        "prohibited_conclusion": "NONE",
    }

    def fake_call(prompt, **kw):
        return (_json.dumps(good_with_dupes), 0.01,
                {}) if "sec-0026" in prompt or "ANNEX11_7" in prompt or "UPS" in prompt else \
               ("{ no json", 0.01, {})

    monkeypatch.setattr(PR3, "_call_llm", fake_call)
    s = PR3.run_cf6_2_5_v3(_SL, _MANIFEST, out_dir=tmp_path, dry_run=False)
    rows = {json.loads(l)["section_id"]: json.loads(l)
            for l in (tmp_path / "CF6_2_5_v3_B_OUTPUTS.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
    r26 = rows["sec-0026"]
    # dedup ANTES de validar -> el duplicado no dispara violación -> Q-STATE -> RENDERED
    assert r26["mode"] == "RENDERED", (r26["mode"], r26["structure_contract_violations"], r26.get("qstate"))
    assert len(r26["structured_llm"]["evidence_observed"]) == 1       # deduplicado
    assert r26["duplicate_quotes_raw"] == [" ".join(q.split())]       # el crudo se conserva en el reporte
    assert r26["llm_calls_section"] == 1
    assert r26["post_qstate_llm_calls"] == 0


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
