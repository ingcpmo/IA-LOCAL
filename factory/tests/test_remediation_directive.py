"""R4-T1.0v2 (docs_plan/R4_T1_0v2_DIRECTIVA_REMEDIACION.md) -- guardianes
de `RemediationDirective`: Acto 2 (autoría humana de la corrección) nunca
se confunde con Acto 1 (adjudicar el hallazgo), y `proposed_text` es
siempre del humano, nunca del sistema. Cero llamadas LLM."""
import ast
from pathlib import Path

import pytest

from factory.layer9 import human_review_queue as hrq
from factory.services import remediation_directive as rd

MODULE_PATH = Path(rd.__file__)
_REAL_ENTRY_ID = "21_CFR_11.10(e)"


@pytest.fixture()
def isolated_directives(tmp_path, monkeypatch):
    directives_file = tmp_path / "remediation_directives_test.jsonl"
    monkeypatch.setattr(rd, "DIRECTIVES_FILE", directives_file)
    return directives_file


@pytest.fixture()
def fake_document(monkeypatch):
    """Evita tocar un PDF real: `_resolve_document_path` devuelve una ruta
    fija, `_extract_target_text` (patcheado directo) devuelve el texto de
    la pagina pedida -- controlado por el test."""
    fixed_path = Path("/fake/RW-TEST.pdf")
    fixed_sha = "a" * 64

    monkeypatch.setattr(rd, "_resolve_document_path", lambda document_id: (fixed_path, fixed_sha))

    class _FakeReader:
        pages = [object()] * 10  # 10 paginas "reales" para el chequeo de rango

    import pypdf
    monkeypatch.setattr(pypdf, "PdfReader", lambda path: _FakeReader())
    return fixed_path, fixed_sha


def _enqueue_confirmed(*, conclusion, reviewer="Cesar", requirement_id=_REAL_ENTRY_ID,
                        document_id="RW-TEST"):
    entry = hrq.enqueue_finding_for_review(
        run_id="chunked-test", requirement_id=requirement_id, document_id=document_id,
        page=None, evidence_quote="", conclusion=conclusion,
        review_flags=[], agent_id="fda_part11_agent",
    )
    hrq.mark_reviewed(entry["rc_id"], "confirmed", reviewer)
    return entry["rc_id"]


def _base_kwargs(finding_rc_id, **overrides):
    kwargs = dict(
        finding_rc_id=finding_rc_id, change_type="ADD",
        proposed_text="Procedimiento X debe registrar timestamp de cada cambio.",
        target_location={"page_start": 3, "page_end": 3, "section": None},
        regulatory_citation=[_REAL_ENTRY_ID], rationale="Cierra la brecha confirmada en la cola.",
        authored_by_id="Cesar",
    )
    kwargs.update(overrides)
    return kwargs


# ── Disparador correcto (hallazgo 2 corregido) ──────────────────────────────

def test_confirmed_documentation_gap_is_a_valid_trigger(isolated_review_queue, isolated_directives, fake_document):
    rc_id = _enqueue_confirmed(conclusion="DOCUMENTATION_GAP")
    directive = rd.propose_remediation_directive(**_base_kwargs(rc_id))
    assert directive["status"] == "SUBMITTED"
    assert directive["finding_rc_id"] == rc_id
    assert rd.list_directives(finding_rc_id=rc_id) == [directive]


def test_confirmed_provisional_gap_is_a_valid_trigger(isolated_review_queue, isolated_directives, fake_document):
    rc_id = _enqueue_confirmed(conclusion="PROVISIONAL_GAP")
    directive = rd.propose_remediation_directive(**_base_kwargs(rc_id))
    assert directive["status"] == "SUBMITTED"


def test_confirmed_supporting_evidence_is_rejected(isolated_review_queue, isolated_directives, fake_document):
    """Confirmar SUPPORTING_EVIDENCE_UNDER_REVIEW significa 'no hay
    brecha' -- nunca dispara una directiva (hallazgo 2)."""
    rc_id = _enqueue_confirmed(conclusion="SUPPORTING_EVIDENCE_UNDER_REVIEW")
    with pytest.raises(rd.RemediationDirectiveError, match="no es un disparador"):
        rd.propose_remediation_directive(**_base_kwargs(rc_id))


def test_confirmed_evaluation_incomplete_is_rejected(isolated_review_queue, isolated_directives, fake_document):
    """Una contradicción bloqueada exige que un humano decida qué sección
    es la vigente -- 'acepto el bloqueo' no es lo mismo que redactar un
    reemplazo."""
    rc_id = _enqueue_confirmed(conclusion="EVALUATION_INCOMPLETE")
    with pytest.raises(rd.RemediationDirectiveError, match="no es un disparador"):
        rd.propose_remediation_directive(**_base_kwargs(rc_id))


def test_unconfirmed_finding_is_rejected(isolated_review_queue, isolated_directives, fake_document):
    """Acto 1 (adjudicar) debe completarse antes que Acto 2 (redactar)."""
    entry = hrq.enqueue_finding_for_review(
        run_id="chunked-test", requirement_id=_REAL_ENTRY_ID, document_id="RW-TEST",
        page=None, evidence_quote="", conclusion="DOCUMENTATION_GAP",
        review_flags=[], agent_id="fda_part11_agent",
    )
    with pytest.raises(rd.RemediationDirectiveError, match="status="):
        rd.propose_remediation_directive(**_base_kwargs(entry["rc_id"]))


def test_unknown_finding_rc_id_is_rejected(isolated_review_queue, isolated_directives, fake_document):
    with pytest.raises(rd.RemediationDirectiveError, match="no existe"):
        rd.propose_remediation_directive(**_base_kwargs("finding-does-not-exist"))


# ── Cita regulatoria obligatoria ────────────────────────────────────────────

def test_directive_without_regulatory_citation_is_rejected(isolated_review_queue, isolated_directives, fake_document):
    rc_id = _enqueue_confirmed(conclusion="DOCUMENTATION_GAP")
    with pytest.raises(TypeError):
        # regulatory_citation es keyword-only obligatorio -- omitirlo es un TypeError,
        # nunca un default silencioso a lista vacía.
        kwargs = _base_kwargs(rc_id)
        del kwargs["regulatory_citation"]
        rd.propose_remediation_directive(**kwargs)


def test_directive_with_unknown_regulatory_citation_is_rejected(isolated_review_queue, isolated_directives, fake_document):
    rc_id = _enqueue_confirmed(conclusion="DOCUMENTATION_GAP")
    with pytest.raises(rd.RemediationDirectiveError, match="no existen en el catálogo"):
        rd.propose_remediation_directive(**_base_kwargs(rc_id, regulatory_citation=["NO_EXISTE_EN_CATALOGO"]))


# ── original_text: anclaje real para REPLACE/DELETE ─────────────────────────

def test_replace_with_unanchored_original_text_is_rejected(isolated_review_queue, isolated_directives, fake_document, monkeypatch):
    rc_id = _enqueue_confirmed(conclusion="DOCUMENTATION_GAP")
    monkeypatch.setattr(rd, "_extract_target_text", lambda path, location: "texto real de la pagina, nada que ver")
    with pytest.raises(rd.RemediationDirectiveError, match="no ancla literalmente"):
        rd.propose_remediation_directive(**_base_kwargs(
            rc_id, change_type="REPLACE", original_text="esto no existe en el documento",
        ))


def test_replace_with_anchored_original_text_succeeds(isolated_review_queue, isolated_directives, fake_document, monkeypatch):
    real_quote = "El procedimiento actual no registra timestamp."
    monkeypatch.setattr(rd, "_extract_target_text", lambda path, location: f"Contexto. {real_quote} Fin.")
    rc_id = _enqueue_confirmed(conclusion="DOCUMENTATION_GAP")
    directive = rd.propose_remediation_directive(**_base_kwargs(
        rc_id, change_type="REPLACE", original_text=real_quote,
    ))
    assert directive["original_text"] == real_quote


def test_replace_without_original_text_is_rejected(isolated_review_queue, isolated_directives, fake_document):
    rc_id = _enqueue_confirmed(conclusion="DOCUMENTATION_GAP")
    with pytest.raises(rd.RemediationDirectiveError, match="exige original_text"):
        rd.propose_remediation_directive(**_base_kwargs(rc_id, change_type="REPLACE", original_text=None))


def test_add_with_original_text_is_rejected(isolated_review_queue, isolated_directives, fake_document):
    """ADD es contenido nuevo -- no hay nada que reemplazar."""
    rc_id = _enqueue_confirmed(conclusion="DOCUMENTATION_GAP")
    with pytest.raises(rd.RemediationDirectiveError, match="no admite original_text"):
        rd.propose_remediation_directive(**_base_kwargs(rc_id, change_type="ADD", original_text="algo"))


# ── target_location real ────────────────────────────────────────────────────

def test_target_location_beyond_real_page_count_is_rejected(isolated_review_queue, isolated_directives, fake_document):
    rc_id = _enqueue_confirmed(conclusion="DOCUMENTATION_GAP")
    with pytest.raises(rd.RemediationDirectiveError, match="excede las páginas reales"):
        rd.propose_remediation_directive(**_base_kwargs(
            rc_id, target_location={"page_start": 500, "page_end": 500, "section": None}))


# ── Identidad real ───────────────────────────────────────────────────────────

def test_reserved_identity_is_rejected(isolated_review_queue, isolated_directives, fake_document):
    rc_id = _enqueue_confirmed(conclusion="DOCUMENTATION_GAP")
    with pytest.raises(Exception):  # IdentityValidationError
        rd.propose_remediation_directive(**_base_kwargs(rc_id, authored_by_id="human"))


# ── proposed_text: SIEMPRE de autoría humana, nunca generado ────────────────

def test_empty_proposed_text_is_rejected(isolated_review_queue, isolated_directives, fake_document):
    rc_id = _enqueue_confirmed(conclusion="DOCUMENTATION_GAP")
    with pytest.raises(rd.RemediationDirectiveError, match="proposed_text"):
        rd.propose_remediation_directive(**_base_kwargs(rc_id, proposed_text="   "))


def test_no_default_value_exists_for_proposed_text():
    """Guardián estático: `propose_remediation_directive` no tiene un
    default para `proposed_text` -- omitirlo es un TypeError en tiempo de
    llamada, nunca un valor inventado en silencio."""
    import inspect
    sig = inspect.signature(rd.propose_remediation_directive)
    assert sig.parameters["proposed_text"].default is inspect.Parameter.empty


def test_module_never_calls_an_llm_or_generation_helper():
    """Guardián estático central del arco: ningún nombre relacionado con
    generación/LLM aparece en el módulo -- `proposed_text`/`original_text`
    solo se leen desde los parámetros de la función, nunca se calculan."""
    source = MODULE_PATH.read_text(encoding="utf-8")
    forbidden = ["ollama", "generate_controlled", "model_provider", "ModelProvider", "llm_output"]
    hits = [f for f in forbidden if f in source]
    assert not hits, f"remediation_directive.py referencia generación/LLM: {hits}"

    tree = ast.parse(source)
    assigns_proposed_text = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Dict)
        for k in node.keys
        if isinstance(k, ast.Constant) and k.value == "proposed_text"
    ]
    # El único dict que construye 'proposed_text' es el propio `directive`
    # dentro de propose_remediation_directive(), y su valor debe ser
    # exactamente la variable del parámetro (Name 'proposed_text'), nunca
    # una llamada a función ni una f-string compuesta.
    for node in assigns_proposed_text:
        idx = next(i for i, k in enumerate(node.keys) if isinstance(k, ast.Constant) and k.value == "proposed_text")
        value_node = node.values[idx]
        assert isinstance(value_node, ast.Name) and value_node.id == "proposed_text", (
            "proposed_text del dict de la directiva no es el parametro tal cual -- "
            "¿alguien lo transformo o genero?")


# ── Schema de forma (validate_remediation_directive) ────────────────────────

def _valid_directive_dict(**overrides):
    d = {
        "directive_id": "DIR-x", "finding_rc_id": "finding-x", "document_id": "RW-TEST",
        "document_sha256": "a" * 64, "requirement_id": _REAL_ENTRY_ID, "change_type": "ADD",
        "proposed_text": "texto real", "target_location": {"page_start": 1, "page_end": 1, "section": None},
        "original_text": None, "regulatory_citation": [_REAL_ENTRY_ID], "rationale": "porque si",
        "authored_by_id": "Cesar", "authored_by_display_name": "Cesar", "authored_at": "2026-08-13T00:00:00+00:00",
        "status": "SUBMITTED",
    }
    d.update(overrides)
    return d


def test_schema_rejects_unexpected_keys():
    with pytest.raises(rd.RemediationDirectiveError, match="inesperadas"):
        rd.validate_remediation_directive(_valid_directive_dict(campo_extra="x"))


def test_schema_rejects_missing_keys():
    d = _valid_directive_dict()
    del d["rationale"]
    with pytest.raises(rd.RemediationDirectiveError, match="faltan campos"):
        rd.validate_remediation_directive(d)


def test_schema_valid_directive_passes():
    rd.validate_remediation_directive(_valid_directive_dict())
