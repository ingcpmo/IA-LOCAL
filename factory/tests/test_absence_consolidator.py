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


# ---------------------------------------------------------------------------
# W5 V2 §13.3 — precondiciones de conclusion (2026-07-27).
# consolidate() decide sobre los chunk records; apply_conclusion_preconditions()
# aplica las reglas duras que consolidate() estructuralmente no puede conocer.
# ---------------------------------------------------------------------------

import pytest

from factory.regulatory.absence_consolidator import (
    DocumentConclusion, apply_conclusion_preconditions,
)


def _conclusion(value, **kw):
    return DocumentConclusion("21_CFR_11.10(d)", "FS", value, **kw)


def _apply(value, **over):
    kw = dict(
        d_sufficiency="MET", substantive_evidence_accepted=True,
        operational_result="EVALUATION_COMPLETE", applicability_value="expected",
        positive_conclusion_eligibility="FORMAL", has_open_contradiction=False,
        applicability_rule_approved=True,
    )
    kw.update(over)
    return apply_conclusion_preconditions(_conclusion(value), **kw)


# ── Invariante: NOT_APPLICABLE no puede coexistir con soporte documental ──

def test_not_applicable_requirement_can_never_be_documented_and_supported():
    """Defecto reproducido: consolidate() decide `if observed:` ANTES de
    mirar la aplicabilidad, asi que un requisito fuera del alcance del tipo
    documental con evidencia observada salia DOCUMENTED_AND_SUPPORTED."""
    c = _apply("DOCUMENTED_AND_SUPPORTED", applicability_value="out_of_document_scope")
    assert c.conclusion == "NOT_APPLICABLE"
    assert "NOT_APPLICABLE_BY_APPLICABILITY_MATRIX" in c.review_flags


def test_not_applicable_beats_every_other_conclusion():
    for value in ("PARTIALLY_DOCUMENTED", "DOCUMENTATION_GAP",
                  "SUPPORTING_EVIDENCE_UNDER_REVIEW", "EVALUATION_INCOMPLETE"):
        c = _apply(value, applicability_value="out_of_document_scope")
        assert c.conclusion == "NOT_APPLICABLE", value


def test_unresolved_applicability_blocks_support_and_gap():
    """review_required = la aplicabilidad no esta resuelta: ni soporte ni
    ausencia consolidada pueden sostenerse (§13.3 'aplicabilidad aprobada')."""
    for value in ("DOCUMENTED_AND_SUPPORTED", "DOCUMENTATION_GAP"):
        c = _apply(value, applicability_value="review_required")
        assert c.conclusion == "EVALUATION_INCOMPLETE", value
        assert "APPLICABILITY_UNRESOLVED" in c.review_flags


# ── §13.3: DOCUMENTATION_GAP exige 0 contradicciones abiertas ─────────────

def test_open_contradiction_blocks_documentation_gap():
    c = _apply("DOCUMENTATION_GAP", has_open_contradiction=True)
    assert c.conclusion == "EVALUATION_INCOMPLETE"
    assert "ABSENCE_BLOCKED_BY_OPEN_CONTRADICTION" in c.review_flags


def test_open_contradiction_blocks_positive_conclusion():
    """§12.2: 'Contradiccion entre secciones ⇒ bloquea conclusion positiva',
    incluso con A∧B∧C∧D==MET sobre el candidato ganador."""
    c = _apply("DOCUMENTED_AND_SUPPORTED", has_open_contradiction=True)
    assert c.conclusion == "SUPPORTING_EVIDENCE_UNDER_REVIEW"
    assert "POSITIVE_BLOCKED_BY_OPEN_CONTRADICTION" in c.review_flags


# ── §12.1/§12.2: techo por evidencia sustantiva A∧B∧C∧D ───────────────────

def test_abcd_met_keeps_documented_and_supported():
    assert _apply("DOCUMENTED_AND_SUPPORTED").conclusion == "DOCUMENTED_AND_SUPPORTED"


def test_d_not_assessable_never_produces_positive_conclusion():
    c = _apply("DOCUMENTED_AND_SUPPORTED", d_sufficiency="NOT_ASSESSABLE",
               substantive_evidence_accepted=False, operational_result="EVALUATION_INCOMPLETE")
    assert c.conclusion == "EVALUATION_INCOMPLETE"
    assert "ABCD_D_NOT_ASSESSABLE" in c.review_flags


def test_d_partially_met_ceiling_is_partially_documented():
    """§12.2: evidencia parcial ⇒ FAIL en D ⇒ MAXIMO PARTIALLY_DOCUMENTED --
    ni mas (DOCUMENTED_AND_SUPPORTED) ni menos que el techo del plan."""
    c = _apply("DOCUMENTED_AND_SUPPORTED", d_sufficiency="PARTIALLY_MET",
               substantive_evidence_accepted=False)
    assert c.conclusion == "PARTIALLY_DOCUMENTED"
    assert "ABCD_D_PARTIALLY_MET" in c.review_flags


def test_d_not_met_blocks_any_support_conclusion():
    c = _apply("PARTIALLY_DOCUMENTED", d_sufficiency="NOT_MET",
               substantive_evidence_accepted=False)
    assert c.conclusion == "SUPPORTING_EVIDENCE_UNDER_REVIEW"
    assert "SUBSTANTIVE_EVIDENCE_NOT_ACCEPTED" in c.review_flags


def test_missing_abcd_data_on_support_conclusion_is_fail_closed():
    """Sin datos ABCD para una conclusion que afirma soporte: el verificador
    nunca corrio sobre esa evidencia -> EVALUATION_INCOMPLETE, jamas se
    asume que paso."""
    c = _apply("DOCUMENTED_AND_SUPPORTED", d_sufficiency=None,
               substantive_evidence_accepted=None, operational_result=None)
    assert c.conclusion == "EVALUATION_INCOMPLETE"
    assert "ABCD_NOT_EVALUATED" in c.review_flags


def test_abcd_rules_never_touch_absence_conclusions():
    """Una ausencia no afirma soporte: no hay evidencia positiva que validar
    con A∧B∧C∧D, asi que D ausente no la degrada."""
    c = _apply("DOCUMENTATION_GAP", d_sufficiency=None,
               substantive_evidence_accepted=None, operational_result=None)
    assert c.conclusion == "DOCUMENTATION_GAP"


# ── §10: gobernanza de fuente ─────────────────────────────────────────────

@pytest.mark.parametrize("final,provisional", [
    ("DOCUMENTED_AND_SUPPORTED", "PROVISIONALLY_DOCUMENTED"),
    ("PARTIALLY_DOCUMENTED", "PROVISIONALLY_PARTIALLY_DOCUMENTED"),
    ("DOCUMENTATION_GAP", "PROVISIONAL_GAP"),
])
def test_pending_reverification_downgrades_final_results(final, provisional):
    """Defecto reproducido: los 19 requisitos del catalogo estan en
    source_verification_status=PENDING_REVERIFICATION y el runtime emitia
    igualmente DOCUMENTED_AND_SUPPORTED / DOCUMENTATION_GAP, ambos en
    provisional_evidence_model.PROHIBITED_FINAL_RESULTS_WHILE_PENDING."""
    c = _apply(final, positive_conclusion_eligibility="PROVISIONAL_ONLY")
    assert c.conclusion == provisional
    assert "SOURCE_PENDING_REVERIFICATION" in c.review_flags


def test_pending_reverification_marks_even_non_final_conclusions():
    """Analisis provisional SI permitido (§10 + modelo provisional), pero la
    marca de provisionalidad nunca se pierde."""
    c = _apply("CROSS_REFERENCE_MISSING", positive_conclusion_eligibility="PROVISIONAL_ONLY")
    assert c.conclusion == "CROSS_REFERENCE_MISSING"
    assert "SOURCE_PENDING_REVERIFICATION" in c.review_flags


def test_blocked_source_eligibility_blocks_every_conclusion():
    """Requisito sin fuente gobernada (o eligibility BLOCKED): §10 'Fuente no
    verificada ⇒ EVALUATION_INCOMPLETE'."""
    c = _apply("DOCUMENTED_AND_SUPPORTED", positive_conclusion_eligibility="BLOCKED")
    assert c.conclusion == "EVALUATION_INCOMPLETE"
    assert "SOURCE_CONCLUSION_BLOCKED" in c.review_flags


def test_blocked_source_does_not_override_not_applicable():
    """NOT_APPLICABLE es una exclusion de alcance, no una afirmacion sobre
    la fuente: no se convierte en EVALUATION_INCOMPLETE."""
    c = _apply("DOCUMENTED_AND_SUPPORTED", applicability_value="out_of_document_scope",
               positive_conclusion_eligibility="BLOCKED")
    assert c.conclusion == "NOT_APPLICABLE"


def test_formal_eligibility_leaves_conclusion_untouched():
    c = _apply("DOCUMENTATION_GAP", positive_conclusion_eligibility="FORMAL")
    assert c.conclusion == "DOCUMENTATION_GAP"
    assert "SOURCE_PENDING_REVERIFICATION" not in c.review_flags


# ── No mutacion / no perdida de datos ─────────────────────────────────────

def test_preconditions_never_mutate_input_nor_lose_counters():
    original = _conclusion("DOCUMENTED_AND_SUPPORTED", chunks_evaluated=7, chunks_observed=3,
                            chunks_review_pending=1, supporting_records=["r1"],
                            review_flags=["PREV"])
    out = apply_conclusion_preconditions(
        original, d_sufficiency="NOT_MET", substantive_evidence_accepted=False,
        operational_result="EVALUATION_COMPLETE", applicability_value="expected",
        positive_conclusion_eligibility="FORMAL", has_open_contradiction=False,
        applicability_rule_approved=True)
    assert original.conclusion == "DOCUMENTED_AND_SUPPORTED"   # entrada intacta
    assert original.review_flags == ["PREV"]
    assert out.conclusion == "SUPPORTING_EVIDENCE_UNDER_REVIEW"
    assert out.review_flags == ["PREV", "SUBSTANTIVE_EVIDENCE_NOT_ACCEPTED"]
    assert (out.chunks_evaluated, out.chunks_observed, out.chunks_review_pending) == (7, 3, 1)
    assert out.supporting_records == ["r1"]


def test_degradation_order_is_deterministic_across_stacked_failures():
    """Aplicabilidad manda sobre contradiccion, contradiccion sobre ABCD y
    ABCD sobre gobernanza de fuente: el resultado no depende del orden en
    que el llamador descubra los problemas."""
    c = _apply("DOCUMENTED_AND_SUPPORTED", applicability_value="out_of_document_scope",
               has_open_contradiction=True, d_sufficiency="NOT_MET",
               substantive_evidence_accepted=False,
               positive_conclusion_eligibility="PROVISIONAL_ONLY")
    assert c.conclusion == "NOT_APPLICABLE"


# ── P3: la validacion del modelo provisional debe poder FALLAR ────────────

def test_unmapped_final_result_under_pending_source_is_rejected():
    """Defecto reproducido (P3, 2026-07-27): apply_conclusion_preconditions()
    solo llamaba a validate_result_status_allowed() cuando la conclusion YA
    estaba en ALLOWED_RESULTS_WHILE_PENDING_REVERIFICATION -- es decir, solo
    validaba lo que por definicion iba a pasar. Un resultado final prohibido
    que no estuviera en _PROVISIONAL_EQUIVALENT (aqui GAP_CLOSED, prohibido
    explicitamente por el modelo provisional) atravesaba la fase 4 intacto.

    Fail-closed esperado: excepcion, que evaluate_chunked() convierte en
    excepcion gobernada + EVALUATION_INCOMPLETE para ese requisito, sin
    detener la corrida."""
    from factory.regulatory.requirement_catalog.provisional_evidence_model import (
        ProvisionalEvidenceModelError,
    )
    with pytest.raises(ProvisionalEvidenceModelError):
        _apply("GAP_CLOSED", positive_conclusion_eligibility="PROVISIONAL_ONLY")


def test_not_applicable_under_pending_source_requires_approved_rule():
    """El unico consumidor real de applicability_rule_approved: NOT_APPLICABLE
    con fuente pendiente solo es legal si la aplicabilidad la determino una
    regla independiente APROBADA. Con la matriz sin aprobar -> fail-closed."""
    from factory.regulatory.requirement_catalog.provisional_evidence_model import (
        ProvisionalEvidenceModelError,
    )
    with pytest.raises(ProvisionalEvidenceModelError):
        apply_conclusion_preconditions(
            _conclusion("NOT_APPLICABLE"),
            d_sufficiency=None, substantive_evidence_accepted=None, operational_result=None,
            applicability_value="expected", positive_conclusion_eligibility="PROVISIONAL_ONLY",
            has_open_contradiction=False, applicability_rule_approved=False,
        )
    # Con la regla aprobada, el mismo caso pasa.
    c = apply_conclusion_preconditions(
        _conclusion("NOT_APPLICABLE"),
        d_sufficiency=None, substantive_evidence_accepted=None, operational_result=None,
        applicability_value="expected", positive_conclusion_eligibility="PROVISIONAL_ONLY",
        has_open_contradiction=False, applicability_rule_approved=True,
    )
    assert c.conclusion == "NOT_APPLICABLE"


@pytest.mark.parametrize("non_final", [
    "SUPPORTING_EVIDENCE_UNDER_REVIEW", "CROSS_REFERENCE_MISSING", "NOT_OBSERVED_OPTIONAL",
])
def test_non_final_states_survive_pending_source_without_raising(non_final):
    """La validacion incondicional no debe romper el analisis provisional que
    §10 habilita: los estados NO finales pasan, marcados como provisionales."""
    c = _apply(non_final, positive_conclusion_eligibility="PROVISIONAL_ONLY")
    assert c.conclusion == non_final
    assert "SOURCE_PENDING_REVERIFICATION" in c.review_flags
