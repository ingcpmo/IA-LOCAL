"""Tests -- factory/regulatory/findings/taxonomy.py (V2, B5).

FASE 7.2: provenance obligatorio; subtype válido por clase; machine_state
válido; y sobre todo: `human_state` NUNCA lo cambia código de IA -- solo
`set_human_state(..., reviewer=<nombre real>)`, que además rechaza
QA_APPROVED / RELEASED / CAPA_CLOSED / FINAL_GMP_APPROVAL.
"""
import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.findings import taxonomy as tx


def _prov(doc="RW-0005"):
    return tx.FindingProvenance(document_id=doc, extraction_version="canonical-v1-2026-08",
                                run_id="run-1", agent_id="fda_part11_agent")


def _mk(**kw):
    base = dict(finding_class="RegulatoryFinding", subtype="REGULATORY_GAP",
                severity="MAJOR", document="RW-0005", page=45,
                source_text="El sistema no genera un audit trail con timestamp.",
                rationale="r", confidence="MEDIUM",
                machine_state="MACHINE_DEVIATION_CANDIDATE", provenance=_prov())
    base.update(kw)
    return tx.build_finding(**base)


def test_build_ok_and_deterministic_id():
    f1 = _mk()
    f2 = _mk(rationale="otra cosa")
    assert f1.finding_id == f2.finding_id          # id por (doc, class, subtype, page, source_text)
    assert f1.human_state == "UNREVIEWED"
    assert f1.source_hash == hashlib.sha256(f1.source_text.encode()).hexdigest()


def test_subtype_must_match_class():
    with pytest.raises(ValueError):
        _mk(subtype="REQUIREMENT_NOT_TESTED")     # de TestCoverageFinding, no Regulatory


def test_provenance_fail_closed():
    with pytest.raises(tx.FindingProvenanceError):
        _mk(source_text="  ")
    with pytest.raises(tx.FindingProvenanceError):
        _mk(page=0)
    with pytest.raises(tx.FindingProvenanceError):
        _mk(provenance=tx.FindingProvenance(document_id="", extraction_version="v1"))


def test_machine_state_validation_and_forbidden():
    with pytest.raises(ValueError):
        _mk(machine_state="SOMETHING")
    for bad in ("QA_APPROVED", "RELEASED", "CAPA_CLOSED", "FINAL_GMP_APPROVAL"):
        with pytest.raises(ValueError):
            _mk(machine_state=bad)


def test_finding_is_born_unreviewed_only():
    """No se puede construir un Finding ya revisado -- __post_init__ lo prohíbe."""
    with pytest.raises(tx.HumanStateViolation):
        tx.Finding(
            finding_id="fnd-x", finding_class="RegulatoryFinding", subtype="REGULATORY_GAP",
            severity="MAJOR", document="RW-0005", page=45, section=None,
            source_text="x" * 20, source_hash=hashlib.sha256(("x" * 20).encode()).hexdigest(),
            rationale="r", confidence="LOW", machine_state="MACHINE_INCONCLUSIVE",
            provenance=_prov(), human_state="ACCEPTED",
        )


def test_set_human_state_requires_real_reviewer():
    f = _mk()
    with pytest.raises(tx.HumanStateViolation):
        tx.set_human_state(f, "ACCEPTED", reviewer="")
    with pytest.raises(tx.HumanStateViolation):
        tx.set_human_state(f, "ACCEPTED", reviewer="   ")


def test_set_human_state_rejects_forbidden_states():
    f = _mk()
    for bad in ("QA_APPROVED", "RELEASED", "CAPA_CLOSED", "FINAL_GMP_APPROVAL"):
        with pytest.raises(tx.ForbiddenStateError):
            tx.set_human_state(f, bad, reviewer="Cesar")


def test_set_human_state_happy_path_is_a_copy():
    f = _mk()
    g = tx.set_human_state(f, "REJECTED", reviewer="Cesar")
    assert f.human_state == "UNREVIEWED"           # original intacto
    assert g.human_state == "REJECTED"
    assert g.reviewer == "Cesar"
    assert g.reviewed_at


def test_all_classes_have_subtypes():
    for cls in tx.FINDING_CLASSES:
        assert tx.SUBTYPES.get(cls), f"{cls} sin subtipos"


def test_as_dict_flattens_provenance():
    d = tx.as_dict(_mk())
    assert d["provenance"]["document_id"] == "RW-0005"
    assert d["human_state"] == "UNREVIEWED"
