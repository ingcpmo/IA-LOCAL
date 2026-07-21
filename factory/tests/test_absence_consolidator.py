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
    c = consolidate("ANNEX11_9", "FS", "expected", records, coverage_complete=True)
    assert c.conclusion == "DOCUMENTATION_GAP"
    assert c.chunks_evaluated == 3
    assert c.chunks_observed == 0


def test_one_observed_chunk_is_documented_never_gap():
    records = [
        _record("r1", "verified", "not_observed_in_chunk"),
        _record("r2", "verified", "observed"),
        _record("r3", "verified", "not_observed_in_chunk"),
    ]
    c = consolidate("ANNEX11_9", "FS", "expected", records, coverage_complete=True)
    assert c.conclusion == "DOCUMENTED_AND_SUPPORTED"
    assert "r2" in c.supporting_records


def test_partially_observed_only_is_partially_documented():
    records = [
        _record("r1", "verified", "partially_observed"),
        _record("r2", "verified", "not_observed_in_chunk"),
    ]
    c = consolidate("ANNEX11_9", "FS", "expected", records, coverage_complete=True)
    assert c.conclusion == "PARTIALLY_DOCUMENTED"


def test_not_observed_with_pending_review_is_evaluation_incomplete():
    """Ausencia bloqueada: no se puede declarar DOCUMENTATION_GAP mientras
    haya chunks todavia bajo revision humana (P1: no PASS/gap prematuro)."""
    records = [
        _record("r1", "verified", "not_observed_in_chunk"),
        _record("r2", "review_required", "not_observed_in_chunk"),
    ]
    c = consolidate("ANNEX11_9", "FS", "expected", records, coverage_complete=True)
    assert c.conclusion == "EVALUATION_INCOMPLETE"
    assert "ABSENCE_BLOCKED_BY_PENDING_REVIEW" in c.review_flags


def test_all_rejected_is_evaluation_incomplete_no_valid_records():
    records = [
        _record("r1", "rejected_by_verifier"),
        _record("r2", "rejected_by_verifier"),
    ]
    c = consolidate("ANNEX11_9", "FS", "expected", records, coverage_complete=True)
    assert c.conclusion == "EVALUATION_INCOMPLETE"
    assert "NO_VALID_RECORDS" in c.review_flags
    assert c.chunks_evaluated == 0


def test_no_records_at_all_is_evaluation_incomplete():
    c = consolidate("ANNEX11_9", "FS", "expected", [], coverage_complete=True)
    assert c.conclusion == "EVALUATION_INCOMPLETE"
    assert "NO_VALID_RECORDS" in c.review_flags


def test_cross_reference_expected_without_observation_is_cross_reference_missing():
    records = [_record("r1", "verified", "not_observed_in_chunk")]
    c = consolidate("21_CFR_11.10(a)", "FS", "cross_reference_expected", records,
                     coverage_complete=True)
    assert c.conclusion == "CROSS_REFERENCE_MISSING"


def test_optional_without_observation_is_not_observed_optional_not_a_gap():
    records = [_record("r1", "verified", "not_observed_in_chunk")]
    c = consolidate("21_CFR_11.10(a)", "FS", "optional", records, coverage_complete=True)
    assert c.conclusion == "NOT_OBSERVED_OPTIONAL"
    assert c.conclusion != "DOCUMENTATION_GAP"


def test_unresolved_applicability_without_observation_flags_applicability_unresolved():
    records = [_record("r1", "verified", "not_observed_in_chunk")]
    c = consolidate("21_CFR_11.10(a)", "FS", "unknown_value", records, coverage_complete=True)
    assert c.conclusion == "EVALUATION_INCOMPLETE"
    assert "APPLICABILITY_UNRESOLVED" in c.review_flags


# --- W5.5: regla reforzada de P3 -- DOCUMENTATION_GAP exige cobertura
# completa Y cero chunks rechazados (hallazgo real: ALCOA_CONTEMPORANEOUS
# en ETAPA 3 se declaro GAP con solo 2/29 chunks reales, 1 de los 3 usados
# quedo rejected_by_verifier) ---

def test_documentation_gap_blocked_when_coverage_incomplete():
    records = [
        _record("r1", "verified", "not_observed_in_chunk"),
        _record("r2", "verified", "not_observed_in_chunk"),
    ]
    c = consolidate("ANNEX11_9", "FS", "expected", records, coverage_complete=False)
    assert c.conclusion == "EVALUATION_INCOMPLETE"
    assert "ABSENCE_BLOCKED_BY_PARTIAL_COVERAGE" in c.review_flags


def test_documentation_gap_blocked_when_rejected_chunks_present_even_with_full_coverage():
    """Caso real de ALCOA_CONTEMPORANEOUS/ETAPA 3: coverage_complete=True
    pero uno de los chunks del conjunto quedo rejected_by_verifier -- ese
    chunk nunca fue observado con exito, no puede sostener una ausencia."""
    records = [
        _record("r1", "verified", "not_observed_in_chunk"),
        _record("r2", "verified", "not_observed_in_chunk"),
        _record("r3", "rejected_by_verifier"),
    ]
    c = consolidate("ALCOA_CONTEMPORANEOUS", "FS", "expected", records,
                     coverage_complete=True)
    assert c.conclusion == "EVALUATION_INCOMPLETE"
    assert "ABSENCE_BLOCKED_BY_REJECTED_CHUNKS" in c.review_flags


def test_documentation_gap_still_emitted_with_full_coverage_and_no_rejections():
    """No-regresion: la regla reforzada no bloquea el caso legitimo (mismo
    escenario que test_all_not_observed_and_expected_is_documentation_gap,
    explicito con coverage_complete=True y cero rechazados)."""
    records = [
        _record("r1", "verified", "not_observed_in_chunk"),
        _record("r2", "verified", "not_observed_in_chunk"),
    ]
    c = consolidate("ANNEX11_9", "FS", "expected", records, coverage_complete=True)
    assert c.conclusion == "DOCUMENTATION_GAP"


def test_cross_reference_missing_not_blocked_by_partial_coverage():
    """Fuera de alcance del fix W5.5 (P3 solo cubre DOCUMENTATION_GAP,
    ver docstring del modulo) -- confirma el limite intencional."""
    records = [_record("r1", "verified", "not_observed_in_chunk")]
    c = consolidate("21_CFR_11.10(a)", "FS", "cross_reference_expected", records,
                     coverage_complete=False)
    assert c.conclusion == "CROSS_REFERENCE_MISSING"


# --- W5.6 (ETAPA 4): DOCUMENTED_AND_SUPPORTED exige al menos un observed
# verificado -- solo review_required nunca basta para afirmar soporte ---

def test_only_review_required_observed_is_supporting_evidence_under_review():
    """Caso real ETAPA 4 (ALCOA_CONTEMPORANEOUS, run w5v3-validation-
    46ccbbe29eb3): los 3 unicos registros 'observed' de 18 evaluados
    quedaron los 3 en review_required (ninguno verified) -- antes de este
    fix, consolidate() igual concluia DOCUMENTED_AND_SUPPORTED."""
    records = [
        _record("r1", "verified", "not_observed_in_chunk"),
        _record("r2", "review_required", "observed"),
        _record("r3", "review_required", "observed"),
    ]
    c = consolidate("ALCOA_CONTEMPORANEOUS", "FS", "expected", records, coverage_complete=False)
    assert c.conclusion == "SUPPORTING_EVIDENCE_UNDER_REVIEW"
    assert "OBSERVED_ONLY_UNVERIFIED" in c.review_flags
    assert c.conclusion not in ("DOCUMENTED_AND_SUPPORTED", "PARTIALLY_DOCUMENTED")


def test_one_verified_observed_among_pending_is_still_documented_and_supported():
    """No-regresion: si HAY al menos un observed verificado, el resultado
    sigue siendo DOCUMENTED_AND_SUPPORTED (con el flag existente de
    evidencia adicional bajo revision), igual que antes de W5.6."""
    records = [
        _record("r1", "verified", "observed"),
        _record("r2", "review_required", "observed"),
    ]
    c = consolidate("ANNEX11_9", "FS", "expected", records, coverage_complete=True)
    assert c.conclusion == "DOCUMENTED_AND_SUPPORTED"
    assert "SUPPORTING_EVIDENCE_UNDER_REVIEW" in c.review_flags


def test_verified_with_deviation_observed_counts_as_verified():
    records = [_record("r1", "verified_with_deviation", "observed")]
    c = consolidate("ANNEX11_9", "FS", "expected", records, coverage_complete=True)
    assert c.conclusion == "DOCUMENTED_AND_SUPPORTED"


def test_coverage_complete_is_required_keyword_argument():
    records = [_record("r1", "verified", "not_observed_in_chunk")]
    try:
        consolidate("ANNEX11_9", "FS", "expected", records)
    except TypeError:
        pass
    else:
        raise AssertionError("coverage_complete debe ser obligatorio, sin default")
