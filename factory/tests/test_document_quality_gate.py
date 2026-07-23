"""
Tests -- AGT-QLT: factory.services.document_quality_gate.

Cubre los 3 controles de alcance-documento genuinamente nuevos
(numeración secuencial, referencias cruzadas, duplicación de párrafos) y
la agregación con los 8 controles por-cambio ya existentes (Fase 6,
document_quality_gates.py, reutilizados sin reimplementar).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.services.candidate_document_generator import generate_candidate_document
from factory.services.document_quality_gate import (
    check_cross_references_resolve, check_no_duplicate_paragraphs,
    check_section_numbering_sequential, evaluate_document_quality,
)

STRUCTURE = {
    "total_paginas": 20,
    "secciones": [
        {"numero": "1", "titulo": "Introduction", "pagina_inicio": 1, "parrafos": ["Texto original 1, bastante largo para no confundirse con basura."]},
        {"numero": "2", "titulo": "Security", "pagina_inicio": 10, "parrafos": ["Texto original 2, tambien suficientemente largo."]},
        {"numero": "3", "titulo": "Data", "pagina_inicio": 15, "parrafos": ["Texto original 3, igual de largo que los anteriores."]},
    ],
    "texto_previo_a_primera_seccion": ["Portada."],
    "toc_anchored": True,
}


def _citation():
    import hashlib
    literal = "texto literal real de prueba"
    return {
        "citation_id": "CIT-1", "regulatory_catalog_entry_id": "ALCOA_CONTEMPORANEOUS",
        "regulatory_source": "ALCOA+", "regulatory_source_sha256": hashlib.sha256(b"src").hexdigest(),
        "requirement_catalog_sha256": hashlib.sha256(b"cat").hexdigest(), "run_id": "RUN-1",
        "record_id": "REC-1", "document_role": "CANDIDATE_DOCUMENT",
        "document_sha256": hashlib.sha256(b"doc").hexdigest(), "chunk_sha256": hashlib.sha256(b"chunk").hexdigest(),
        "citation_locator": "chunk_1#p10-11", "page_start": 10, "page_end": 11,
        "literal_text": literal, "citation_text_sha256": hashlib.sha256(literal.encode()).hexdigest(),
        "evidence_type": "LITERAL_QUOTE", "evidence_location": "seccion 2, pagina 10",
    }


def _change(change_id, proposed_content="Agregar control de acceso adicional segun el nuevo requisito."):
    return {
        "change_id": change_id, "finding_id": f"F-{change_id}", "requirement_id": "21_CFR_11.10(a)",
        "document_location": "seccion 2", "original_content": None,
        "proposed_content": proposed_content, "change_reason": "gap detectado en auditoria",
        "change_type": "CONTENT_ADDITION", "citations": [_citation()],
        "change_risk": "LOW_RISK", "change_risk_basis": ["change_type"],
        "evaluation_confidence": "HIGH_CONFIDENCE", "evaluation_confidence_basis": ["coverage_status"],
        "schema_validation_status": "PASSED", "citation_anchor_status": "VERIFIED",
        "relevance_status": "CONFIRMED", "candidate_application_status": "APPLIED_TO_DRAFT",
        "limitations": "",
    }


class TestSectionNumberingSequential:

    def test_sequential_numbering_passes(self):
        result = check_section_numbering_sequential(STRUCTURE)
        assert result["status"] == "PASS"

    def test_gap_in_numbering_fails(self):
        broken = {**STRUCTURE, "secciones": [
            {"numero": "1", "titulo": "A", "pagina_inicio": 1, "parrafos": []},
            {"numero": "3", "titulo": "B", "pagina_inicio": 5, "parrafos": []},
        ]}
        result = check_section_numbering_sequential(broken)
        assert result["status"] == "FAIL"

    def test_duplicate_section_number_fails(self):
        broken = {**STRUCTURE, "secciones": [
            {"numero": "1", "titulo": "A", "pagina_inicio": 1, "parrafos": []},
            {"numero": "1", "titulo": "B", "pagina_inicio": 5, "parrafos": []},
        ]}
        result = check_section_numbering_sequential(broken)
        assert result["status"] == "FAIL"
        assert "duplicados" in result["reason"]


class TestCrossReferencesResolve:

    def test_reference_to_real_section_passes(self):
        text = "Ver seccion 2 para mas detalle sobre control de acceso."
        result = check_cross_references_resolve(STRUCTURE, text)
        assert result["status"] == "PASS"

    def test_reference_to_nonexistent_section_fails(self):
        text = "Ver seccion 99 para mas detalle, que no existe en este documento."
        result = check_cross_references_resolve(STRUCTURE, text)
        assert result["status"] == "FAIL"
        assert "99" in result["reason"]

    def test_no_references_at_all_passes_trivially(self):
        result = check_cross_references_resolve(STRUCTURE, "Texto sin ninguna referencia cruzada.")
        assert result["status"] == "PASS"


class TestNoDuplicateParagraphs:

    def test_no_duplicates_passes(self):
        text = "Primer parrafo bastante largo y distinto.\nSegundo parrafo tambien distinto y largo."
        result = check_no_duplicate_paragraphs(text)
        assert result["status"] == "PASS"

    def test_literal_duplicate_paragraph_fails(self):
        text = (
            "Este parrafo aparece dos veces en el documento completo.\n"
            "Otro parrafo distinto que aparece una sola vez aqui.\n"
            "Este parrafo aparece dos veces en el documento completo.\n"
        )
        result = check_no_duplicate_paragraphs(text)
        assert result["status"] == "FAIL"

    def test_short_lines_never_flagged_as_duplicates(self):
        text = "N/A\nN/A\nN/A\n"
        result = check_no_duplicate_paragraphs(text)
        assert result["status"] == "PASS"


class TestEvaluateDocumentQuality:

    def test_valid_document_and_changes_pass(self):
        change = _change("C1")
        candidate = generate_candidate_document(STRUCTURE, [change])
        full_text = "\n".join(p.text for p in candidate.paragraphs)
        result = evaluate_document_quality(structure=STRUCTURE, candidate_full_text=full_text, changes=[change])
        assert result["applied"] is True
        assert result["failed_document_wide_controls"] == []
        assert result["failed_change_ids"] == []

    def test_invalid_change_fails_aggregate(self):
        bad_change = _change("C1", proposed_content="palabra")  # verbo no controlado, muy corto
        candidate = generate_candidate_document(STRUCTURE, [bad_change])
        full_text = "\n".join(p.text for p in candidate.paragraphs)
        result = evaluate_document_quality(structure=STRUCTURE, candidate_full_text=full_text, changes=[bad_change])
        assert result["applied"] is False
        assert "C1" in result["failed_change_ids"]

    def test_document_wide_failure_marks_applied_false_even_if_all_changes_pass(self):
        change = _change("C1")
        broken_structure = {**STRUCTURE, "secciones": [
            {"numero": "1", "titulo": "A", "pagina_inicio": 1, "parrafos": []},
            {"numero": "1", "titulo": "B", "pagina_inicio": 5, "parrafos": []},
        ]}
        result = evaluate_document_quality(
            structure=broken_structure, candidate_full_text="algo", changes=[change],
        )
        assert result["applied"] is False
        assert "numeracion_secuencial" in result["failed_document_wide_controls"]

    def test_not_evaluated_controls_never_block_applied(self):
        """Terminologia/ortografia/tablas/abreviaturas son NOT_EVALUATED
        -- nunca deben, por si solas, forzar applied=False."""
        change = _change("C1")
        candidate = generate_candidate_document(STRUCTURE, [change])
        full_text = "\n".join(p.text for p in candidate.paragraphs)
        result = evaluate_document_quality(structure=STRUCTURE, candidate_full_text=full_text, changes=[change])
        not_evaluated = [
            name for name, r in result["document_wide_controls"].items() if r["status"] == "NOT_EVALUATED"
        ]
        assert len(not_evaluated) == 4  # terminologia, ortografia, tablas, abreviaturas
        assert result["applied"] is True
