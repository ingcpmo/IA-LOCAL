"""W5 Ciclo 1 (v2), Fase 2, Bloque 2.4 — tests del consolidador de ausencias."""
from __future__ import annotations

from factory.regulatory.absence_consolidator import consolidate


def _record(record_id, status, observation=None):
    r = {"record_id": record_id, "status": status}
    if observation is not None:
        r["llm_output"] = {"chunk_observation": observation}
    return r


def test_all_not_observed_and_expected_is_documentation_gap():
    records = [
        _record("r1", "verified", "not_observed_in_chunk"),
        _record("r2", "verified", "not_observed_in_chunk"),
        _record("r3", "verified_with_deviation", "not_observed_in_chunk"),
    ]
    c = consolidate("ANNEX11_9", "FS", "expected", records)
    assert c.conclusion == "DOCUMENTATION_GAP"
    assert c.chunks_evaluated == 3
    assert c.chunks_observed == 0


def test_one_observed_chunk_is_documented_never_gap():
    records = [
        _record("r1", "verified", "not_observed_in_chunk"),
        _record("r2", "verified", "observed"),
        _record("r3", "verified", "not_observed_in_chunk"),
    ]
    c = consolidate("ANNEX11_9", "FS", "expected", records)
    assert c.conclusion == "DOCUMENTED_AND_SUPPORTED"
    assert "r2" in c.supporting_records


def test_partially_observed_only_is_partially_documented():
    records = [
        _record("r1", "verified", "partially_observed"),
        _record("r2", "verified", "not_observed_in_chunk"),
    ]
    c = consolidate("ANNEX11_9", "FS", "expected", records)
    assert c.conclusion == "PARTIALLY_DOCUMENTED"


def test_not_observed_with_pending_review_is_evaluation_incomplete():
    """Ausencia bloqueada: no se puede declarar DOCUMENTATION_GAP mientras
    haya chunks todavia bajo revision humana (P1: no PASS/gap prematuro)."""
    records = [
        _record("r1", "verified", "not_observed_in_chunk"),
        _record("r2", "review_required", "not_observed_in_chunk"),
    ]
    c = consolidate("ANNEX11_9", "FS", "expected", records)
    assert c.conclusion == "EVALUATION_INCOMPLETE"
    assert "ABSENCE_BLOCKED_BY_PENDING_REVIEW" in c.review_flags


def test_all_rejected_is_evaluation_incomplete_no_valid_records():
    records = [
        _record("r1", "rejected_by_verifier"),
        _record("r2", "rejected_by_verifier"),
    ]
    c = consolidate("ANNEX11_9", "FS", "expected", records)
    assert c.conclusion == "EVALUATION_INCOMPLETE"
    assert "NO_VALID_RECORDS" in c.review_flags
    assert c.chunks_evaluated == 0


def test_no_records_at_all_is_evaluation_incomplete():
    c = consolidate("ANNEX11_9", "FS", "expected", [])
    assert c.conclusion == "EVALUATION_INCOMPLETE"
    assert "NO_VALID_RECORDS" in c.review_flags


def test_cross_reference_expected_without_observation_is_cross_reference_missing():
    records = [_record("r1", "verified", "not_observed_in_chunk")]
    c = consolidate("21_CFR_11.10(a)", "FS", "cross_reference_expected", records)
    assert c.conclusion == "CROSS_REFERENCE_MISSING"


def test_optional_without_observation_is_not_observed_optional_not_a_gap():
    records = [_record("r1", "verified", "not_observed_in_chunk")]
    c = consolidate("21_CFR_11.10(a)", "FS", "optional", records)
    assert c.conclusion == "NOT_OBSERVED_OPTIONAL"
    assert c.conclusion != "DOCUMENTATION_GAP"


def test_unresolved_applicability_without_observation_flags_applicability_unresolved():
    records = [_record("r1", "verified", "not_observed_in_chunk")]
    c = consolidate("21_CFR_11.10(a)", "FS", "unknown_value", records)
    assert c.conclusion == "EVALUATION_INCOMPLETE"
    assert "APPLICABILITY_UNRESOLVED" in c.review_flags
