"""R4-T1.0v2 bloque 2 (docs_plan/R4_T1_0v2_DIRECTIVA_REMEDIACION.md) --
guardianes del wiring directiva -> Ruta D -> RemediationChange. Cero
llamadas LLM (Ruta D es determinista)."""
from pathlib import Path

import pytest

from factory.layer9 import human_review_queue as hrq
from factory.services import remediation_directive as rd
from factory.services import remediation_directive_dispatch as dispatch
from factory.services.gap_assessment_finding_mapper import NotMappableToCurrentSchema
from factory.services.remediation_package_schemas import validate_remediation_change

_REAL_ENTRY_ID = "21_CFR_11.10(e)"


@pytest.fixture()
def isolated_directives(tmp_path, monkeypatch):
    directives_file = tmp_path / "remediation_directives_test.jsonl"
    monkeypatch.setattr(rd, "DIRECTIVES_FILE", directives_file)
    return directives_file


@pytest.fixture()
def fake_document(monkeypatch):
    fixed_path = Path("/fake/RW-TEST.pdf")
    fixed_sha = "a" * 64
    monkeypatch.setattr(rd, "_resolve_document_path", lambda document_id: (fixed_path, fixed_sha))
    monkeypatch.setattr(dispatch, "_resolve_document_path", lambda document_id: (fixed_path, fixed_sha))

    class _FakeReader:
        pages = [object()] * 10

    import pypdf
    monkeypatch.setattr(pypdf, "PdfReader", lambda path: _FakeReader())
    return fixed_path, fixed_sha


def _enqueue_confirmed(*, conclusion, reviewer="Cesar", requirement_id=_REAL_ENTRY_ID, document_id="RW-TEST"):
    entry = hrq.enqueue_finding_for_review(
        run_id="chunked-test", requirement_id=requirement_id, document_id=document_id,
        page=None, evidence_quote="", conclusion=conclusion,
        review_flags=[], agent_id="fda_part11_agent",
    )
    hrq.mark_reviewed(entry["rc_id"], "confirmed", reviewer)
    return entry["rc_id"]


def _propose_add_directive(rc_id, **overrides):
    kwargs = dict(
        finding_rc_id=rc_id, change_type="ADD",
        proposed_text="El SOP debe registrar timestamp de fecha y hora de cada cambio critico.",
        target_location={"page_start": 3, "page_end": 3, "section": None},
        regulatory_citation=[_REAL_ENTRY_ID], rationale="Cierra la brecha confirmada en la cola.",
        authored_by_id="Cesar",
    )
    kwargs.update(overrides)
    return rd.propose_remediation_directive(**kwargs)


def test_add_directive_dispatches_to_a_valid_remediation_change(isolated_review_queue, isolated_directives, fake_document):
    rc_id = _enqueue_confirmed(conclusion="DOCUMENTATION_GAP")
    directive = _propose_add_directive(rc_id)
    mapped = dispatch.dispatch_directive_to_remediation(directive, run_id="run-test")
    validate_remediation_change(mapped.change)  # no lanza -> forma valida
    assert mapped.change["finding_id"] == directive["directive_id"]
    assert mapped.change["requirement_id"] == _REAL_ENTRY_ID
    assert mapped.change["change_type"] == "CONTENT_ADDITION"


def test_provisional_gap_trigger_also_dispatches(isolated_review_queue, isolated_directives, fake_document):
    rc_id = _enqueue_confirmed(conclusion="PROVISIONAL_GAP")
    directive = _propose_add_directive(rc_id)
    mapped = dispatch.dispatch_directive_to_remediation(directive, run_id="run-test")
    validate_remediation_change(mapped.change)


def test_replace_directive_dispatches_with_anchored_evidence(isolated_review_queue, isolated_directives, fake_document, monkeypatch):
    real_quote = "El procedimiento actual no registra timestamp de los cambios."
    monkeypatch.setattr(rd, "_extract_target_text", lambda path, location: f"Contexto. {real_quote} Fin.")
    monkeypatch.setattr(dispatch, "_extract_target_text", lambda path, location: f"Contexto. {real_quote} Fin.")
    rc_id = _enqueue_confirmed(conclusion="DOCUMENTATION_GAP")
    directive = _propose_add_directive(rc_id, change_type="REPLACE", original_text=real_quote)
    mapped = dispatch.dispatch_directive_to_remediation(directive, run_id="run-test")
    validate_remediation_change(mapped.change)
    assert mapped.change["change_type"] == "CONTENT_REPLACEMENT"
    assert mapped.change["citation_anchor_status"] == "VERIFIED"


def test_delete_directive_is_rejected_explicitly(isolated_review_queue, isolated_directives, fake_document, monkeypatch):
    """Decisión de Cesar (2026-08-13): DELETE no tiene regla de mapeo en
    Ruta D todavía -- rechazo explícito, nunca silencioso."""
    real_quote = "Texto real a eliminar del documento."
    monkeypatch.setattr(rd, "_extract_target_text", lambda path, location: f"Contexto. {real_quote} Fin.")
    rc_id = _enqueue_confirmed(conclusion="DOCUMENTATION_GAP")
    directive = _propose_add_directive(rc_id, change_type="DELETE", original_text=real_quote)
    with pytest.raises(dispatch.DirectiveNotDispatchable, match="DELETE"):
        dispatch.dispatch_directive_to_remediation(directive, run_id="run-test")


def test_document_drift_since_directive_is_rejected(isolated_review_queue, isolated_directives, fake_document, monkeypatch):
    rc_id = _enqueue_confirmed(conclusion="DOCUMENTATION_GAP")
    directive = _propose_add_directive(rc_id)
    # El documento "cambio" despues de que se redacto la directiva.
    monkeypatch.setattr(dispatch, "_resolve_document_path", lambda document_id: (Path("/fake/RW-TEST.pdf"), "b" * 64))
    with pytest.raises(dispatch.DirectiveNotDispatchable, match="no coincide"):
        dispatch.dispatch_directive_to_remediation(directive, run_id="run-test")


def test_unknown_requirement_id_is_rejected(isolated_review_queue, isolated_directives, fake_document, monkeypatch):
    rc_id = _enqueue_confirmed(conclusion="DOCUMENTATION_GAP")
    directive = _propose_add_directive(rc_id)
    directive = dict(directive, requirement_id="NO_EXISTE_EN_CATALOGO")
    with pytest.raises(dispatch.DirectiveNotDispatchable, match="catálogo"):
        dispatch.dispatch_directive_to_remediation(directive, run_id="run-test")
