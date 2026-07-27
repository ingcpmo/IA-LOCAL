"""Tests -- factory/services/finding_substantive_adapter.py (deuda I-1,
W5 V2, 2026-07-27).

Fijan que el veredicto sustantivo A^B^C^D viaje del `Finding` real del
motor al narrative JSON SIN re-derivarse, y que los casos degenerados
(ausente, incompleto, invalido, contradictorio) fallen cerrados.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from factory.engines.gmpai_integrity.chunked_engine import compute_substantive_support
from factory.engines.gmpai_integrity.models import Finding
from factory.services.finding_substantive_adapter import (
    SUBSTANTIVE_FIELDS,
    attach_substantive_verdict,
    read_substantive_verdict,
    substantive_block,
)


def _finding(**kw) -> Finding:
    base = dict(
        sistema="S", documento="D", version="1", archivo="a.pdf",
        pagina_o_seccion="pag 1-1 (chunk 0)", requisito_regulatorio="ANNEX11_7.1 — x",
        evidencia_exacta="cita", estado="cumple_parcialmente", brecha="b",
        severidad="menor", riesgo="r", recomendacion="Agregar x", confianza="media",
        agente_responsable="ag", revision_humana_requerida=True,
    )
    base.update(kw)
    return Finding(**base)


# ── transporte: copia verbatim, nunca re-derivacion ───────────────────────

def test_substantive_block_copies_all_four_fields_verbatim():
    f = _finding(d_sufficiency="MET", substantive_evidence_accepted=True,
                  operational_result="COMPLETED", substantive_support="SUPPORTED")
    block = substantive_block(f)
    assert set(block) == set(SUBSTANTIVE_FIELDS)
    assert block["d_sufficiency"] == "MET"
    assert block["substantive_support"] == "SUPPORTED"


def test_substantive_block_accepts_to_dict_form():
    f = _finding(substantive_support="NOT_SUPPORTED")
    assert substantive_block(f.to_dict()) == substantive_block(f)


def test_attach_does_not_mutate_the_original_narrative():
    narrative = {"finding_id": "X-1", "requisito": "ANNEX11_7.1 — x"}
    out = attach_substantive_verdict(narrative, _finding(substantive_support="NOT_APPLICABLE"))
    assert "substantive_support" not in narrative  # P1: el artefacto original intacto
    assert out["substantive_support"] == "NOT_APPLICABLE"
    assert out["finding_id"] == "X-1"


def test_adapter_never_invents_a_verdict_for_a_finding_that_has_none():
    """Un Finding pre-Fase F trae los 4 campos en None -- el adaptador los
    transporta como None, no los rellena."""
    block = substantive_block(_finding())
    assert block == {k: None for k in SUBSTANTIVE_FIELDS}
    assert read_substantive_verdict(block).status == "INCOMPLETE"


# ── lectura del veredicto ya transportado ────────────────────────────────

@pytest.mark.parametrize("support,accepted", [
    ("SUPPORTED", True), ("NOT_SUPPORTED", False), ("NOT_APPLICABLE", None),
])
def test_read_returns_the_transported_verdict(support, accepted):
    v = read_substantive_verdict(
        {"substantive_support": support, "substantive_evidence_accepted": accepted})
    assert v.status == support


def test_invalid_support_value_is_rejected_not_coerced():
    v = read_substantive_verdict({"substantive_support": "PROBABLEMENTE_SI"})
    assert v.status == "INVALID"


def test_supported_without_accepted_evidence_is_inconsistent():
    """El unico juicio propio del adaptador: SUPPORTED solo puede
    sostenerse sobre substantive_evidence_accepted=True. La contradiccion
    se rechaza, no se resuelve eligiendo un lado."""
    v = read_substantive_verdict(
        {"substantive_support": "SUPPORTED", "substantive_evidence_accepted": None,
         "d_sufficiency": "NOT_ASSESSABLE"})
    assert v.status == "INCONSISTENT"
    assert "contradice" in v.reason


def test_partial_block_without_the_verdict_is_incomplete():
    v = read_substantive_verdict({"d_sufficiency": "MET"})
    assert v.status == "INCOMPLETE"


# ── narrative legacy: misma autoridad del motor, fail-closed ─────────────

def test_legacy_positive_estado_is_not_supported_because_d_was_never_evaluated():
    """El agujero real de la deuda I-1: un narrative anterior a Fase F con
    estado positivo no puede pasar como sustentado -- D nunca corrio."""
    v = read_substantive_verdict({"estado_agente_original": "cumple_parcialmente"})
    assert v.status == "NOT_SUPPORTED"
    assert "fail-closed" in v.reason


def test_legacy_non_positive_estado_is_not_applicable():
    v = read_substantive_verdict({"estado_agente_original": "no_cumple"})
    assert v.status == "NOT_APPLICABLE"


def test_legacy_verdict_uses_the_engine_authority_not_a_local_copy():
    """No debe existir una segunda autoridad del veredicto: para cada
    estado real, el adaptador tiene que coincidir con
    chunked_engine.compute_substantive_support (la misma funcion)."""
    for estado in ("cumple", "cumple_parcialmente", "no_cumple",
                    "evidencia_insuficiente", "no_aplica"):
        v = read_substantive_verdict({"estado_agente_original": estado})
        assert v.status == compute_substantive_support(estado, None), estado


def test_narrative_with_neither_block_nor_estado_is_absent():
    v = read_substantive_verdict({"finding_id": "X-1"})
    assert v.status == "ABSENT"


def test_transported_block_wins_over_legacy_estado():
    """Si el bloque ABCD real viaja, manda sobre la derivacion legacy --
    un Finding con D==MET no debe degradarse por su estado."""
    v = read_substantive_verdict({
        "estado_agente_original": "cumple_parcialmente",
        "substantive_support": "SUPPORTED", "substantive_evidence_accepted": True,
        "d_sufficiency": "MET",
    })
    assert v.status == "SUPPORTED"
