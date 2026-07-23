"""
Tests -- W5 V2 Fase L: factory.services.governed_candidate_document_pipeline.

Cubre: el punto de entrada único conecta Fase K (resolver de aplicación
gobernada) con Fase J (generador DOCX real) -- un cambio HIGH_RISK
rechazado NUNCA aparece en el documento generado, aunque se le pase junto
con cambios LOW_RISK válidos. Incluye un caso end-to-end real contra
FS_v1.2.pdf (Rockwell, generation_ready=True per Fase J).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from factory.regulatory import document_structure_extractor as extractor
from factory.services import remediation_package_service as svc
from factory.services.governed_candidate_document_pipeline import generate_governed_candidate

STRUCTURE = {
    "total_paginas": 20,
    "secciones": [
        {"numero": "1", "titulo": "Introduction", "pagina_inicio": 1, "parrafos": ["Texto original 1."]},
        {"numero": "2", "titulo": "Security", "pagina_inicio": 10, "parrafos": ["Texto original 2."]},
    ],
    "texto_previo_a_primera_seccion": ["Portada."],
    "toc_anchored": True,
}


def _change(change_id, risk, page_start=10, proposed_content="Contenido nuevo propuesto.",
            schema="PASSED", anchor="VERIFIED"):
    return {
        "change_id": change_id, "change_risk": risk, "change_type": "CONTENT_ADDITION",
        "proposed_content": proposed_content, "citations": [{"page_start": page_start}],
        "schema_validation_status": schema, "citation_anchor_status": anchor,
    }


def _package_state(changes, exceptions=None, batch_decisions=None):
    return {
        "changes": {c["change_id"]: c for c in changes},
        "exceptions": exceptions or {},
        "medium_risk_batch_decisions": batch_decisions or {},
    }


class TestGenerateGovernedCandidate:

    def test_low_risk_change_included(self):
        low = _change("LOW-1", "LOW_RISK")
        result = generate_governed_candidate(STRUCTURE, _package_state([low]))
        assert result.included_change_ids == ["LOW-1"]
        assert result.excluded_change_ids == []
        texts = [p.text for p in result.candidate_document.paragraphs]
        assert "Contenido nuevo propuesto." in texts

    def test_high_risk_without_exception_excluded_from_candidate(self):
        high = _change("HIGH-1", "HIGH_RISK", proposed_content="Texto de alto riesgo sin revisar.")
        result = generate_governed_candidate(STRUCTURE, _package_state([high]))
        assert result.included_change_ids == []
        assert result.excluded_change_ids == ["HIGH-1"]
        assert "EXCEPTION_REQUIRED" in result.exclusion_reasons["HIGH-1"]
        texts = [p.text for p in result.candidate_document.paragraphs]
        assert "Texto de alto riesgo sin revisar." not in texts

    def test_high_risk_rejected_exception_excluded_from_both_documents(self):
        high = _change("HIGH-1", "HIGH_RISK", proposed_content="Texto rechazado por humano.")
        state = _package_state([high], exceptions={
            "EXC-HIGH-1": {"exception_id": "EXC-HIGH-1", "change_id": "HIGH-1", "status": "REVIEWED",
                           "human_review_decision": "reject_unacceptable_risk"},
        })
        result = generate_governed_candidate(STRUCTURE, state)
        assert result.excluded_change_ids == ["HIGH-1"]
        candidate_texts = [p.text for p in result.candidate_document.paragraphs]
        redline_texts = [p.text for p in result.redline_document.paragraphs]
        assert not any("Texto rechazado por humano." in t for t in candidate_texts)
        assert not any("Texto rechazado por humano." in t for t in redline_texts)

    def test_mixed_changes_only_safe_ones_reach_the_document(self):
        low = _change("LOW-1", "LOW_RISK", proposed_content="Cambio seguro.")
        high = _change("HIGH-1", "HIGH_RISK", proposed_content="Cambio de alto riesgo pendiente.")
        result = generate_governed_candidate(STRUCTURE, _package_state([low, high]))
        assert result.included_change_ids == ["LOW-1"]
        assert result.excluded_change_ids == ["HIGH-1"]
        texts = [p.text for p in result.candidate_document.paragraphs]
        assert "Cambio seguro." in texts
        assert "Cambio de alto riesgo pendiente." not in texts

    def test_redline_manifest_only_covers_included_changes(self):
        low = _change("LOW-1", "LOW_RISK")
        high = _change("HIGH-1", "HIGH_RISK")
        result = generate_governed_candidate(STRUCTURE, _package_state([low, high]))
        manifest_ids = {m["change_id"] for m in result.insertion_manifest}
        assert manifest_ids == {"LOW-1"}

    def test_gate_failure_excludes_regardless_of_risk(self):
        broken_low = _change("LOW-1", "LOW_RISK", schema="FAILED")
        result = generate_governed_candidate(STRUCTURE, _package_state([broken_low]))
        assert result.excluded_change_ids == ["LOW-1"]
        assert "REJECTED_BY_VALIDATOR" in result.exclusion_reasons["LOW-1"]


class TestRealEndToEndAgainstFSv12Pdf:
    """FS_v1.2.pdf es generation_ready=True (Fase J) -- gate real contra el
    documento verdadero de Rockwell, mismo patron ya usado en Fase 4/5 del
    otro roadmap (correr contra el documento real expone bugs que un
    fixture sintetico no)."""

    PDF_PATH = Path(
        "/home/ing_cpmo/GMPAI/source/Rockwell/215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf"
    )

    @pytest.mark.skipif(not PDF_PATH.exists(), reason="requiere el PDF real de Rockwell, no presente en este entorno")
    def test_real_fs_v12_low_risk_change_reaches_candidate_high_risk_does_not(self):
        structure = extractor.extract_structure_from_pdf(self.PDF_PATH)
        assert structure["secciones"], "estructura real debe tener secciones (Fase 4 ya probado 8/8)"
        real_page = structure["secciones"][0]["pagina_inicio"]

        low = _change("LOW-REAL", "LOW_RISK", page_start=real_page, proposed_content="Adicion segura real.")
        high = _change("HIGH-REAL", "HIGH_RISK", page_start=real_page, proposed_content="Adicion de alto riesgo real.")
        result = generate_governed_candidate(structure, _package_state([low, high]))

        assert result.included_change_ids == ["LOW-REAL"]
        assert result.excluded_change_ids == ["HIGH-REAL"]
        texts = [p.text for p in result.candidate_document.paragraphs]
        assert "Adicion segura real." in texts
        assert "Adicion de alto riesgo real." not in texts
