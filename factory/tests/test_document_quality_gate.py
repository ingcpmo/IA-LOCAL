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

    def test_subsection_reference_is_not_evaluable_when_structure_has_no_subsections(self):
        """2026-07-28: document_structure_extractor modela SOLO nivel 1, asi
        que 'Section 2.1.1' no puede refutarse desde esta estructura.
        Reportarla como inexistente (comportamiento anterior) era afirmar lo
        que la estructura no puede saber -- los 4 casos reales de FS_v1.2
        (2.1.1, 3.1.3, 3.1.12, 7.1.1) son subsecciones reales cuya
        numeracion se perdio en la extraccion."""
        text = "Per Section 2.1.1 Software, la estacion de ingenieria esta incluida."
        result = check_cross_references_resolve(STRUCTURE, text)
        assert result["status"] == "NOT_EVALUATED"
        assert "2.1.1" in result["reason"]
        assert "solo secciones de nivel 1" in result["reason"]

    def test_level_one_reference_is_still_refuted_alongside_subsections(self):
        """Guardia anti-silenciamiento: que haya subsecciones no evaluables
        no puede tapar una referencia de nivel 1 que si es refutable."""
        text = "Ver seccion 99 y tambien la Section 2.1.1 Software del documento."
        result = check_cross_references_resolve(STRUCTURE, text)
        assert result["status"] == "FAIL"
        assert "99" in result["reason"]

    def test_subsection_reference_is_adjudicated_when_structure_models_subsections(self):
        """Si la estructura si modela subsecciones, la referencia vuelve a
        ser refutable y una subseccion inexistente falla."""
        with_subsections = {**STRUCTURE, "secciones": [
            *STRUCTURE["secciones"],
            {"numero": "2.1", "titulo": "Software", "pagina_inicio": 4, "parrafos": []},
        ]}
        ok = check_cross_references_resolve(with_subsections, "Ver seccion 2.1 del documento.")
        assert ok["status"] == "PASS"
        bad = check_cross_references_resolve(with_subsections, "Ver seccion 9.9 del documento.")
        assert bad["status"] == "FAIL"
        assert "9.9" in bad["reason"]


class TestNoDuplicateParagraphs:
    """2026-07-28: la regla pasó de "aparece más de una vez" a "multiplicidad
    AUMENTADA respecto al original". Motivo medido sobre FS_v1.2: 76/76
    duplicados reportados ya estaban en el documento fuente (encabezados de
    página × 58 páginas y texto de plantilla), 0 eran inserciones."""

    def test_no_duplicates_passes(self):
        text = "Primer parrafo bastante largo y distinto.\nSegundo parrafo tambien distinto y largo."
        result = check_no_duplicate_paragraphs(text, text)
        assert result["status"] == "PASS"

    def test_duplicate_introduced_by_generation_fails(self):
        original = "Este parrafo aparece una sola vez en el original.\n"
        candidate = (
            "Este parrafo aparece una sola vez en el original.\n"
            "Otro parrafo distinto que aparece una sola vez aqui.\n"
            "Este parrafo aparece una sola vez en el original.\n"
        )
        result = check_no_duplicate_paragraphs(candidate, original)
        assert result["status"] == "FAIL"
        assert "1 -> 2 veces" in result["reason"]

    def test_repetition_already_present_in_the_original_does_not_fail(self):
        """Encabezado de página del documento fuente: se repite en el
        original y en el candidato con la MISMA multiplicidad. No es un
        defecto del candidato y no puede reportarse como tal."""
        header = "MCCPDC - SCADA and PCS MISC. PLC System encabezado de pagina.\n"
        original = header * 58
        candidate = header * 58 + "Parrafo nuevo agregado por la remediacion documental.\n"
        result = check_no_duplicate_paragraphs(candidate, original)
        assert result["status"] == "PASS"
        assert "ya presentes en el original" in result["reason"]

    def test_extra_copy_of_a_repeated_header_is_still_caught(self):
        """Guardia anti-silenciamiento: que una repetición sea legítima en el
        original NO da licencia para insertar una copia más."""
        header = "MCCPDC - SCADA and PCS MISC. PLC System encabezado de pagina.\n"
        result = check_no_duplicate_paragraphs(header * 59, header * 58)
        assert result["status"] == "FAIL"
        assert "58 -> 59 veces" in result["reason"]

    def test_short_lines_never_flagged_as_duplicates(self):
        result = check_no_duplicate_paragraphs("N/A\nN/A\nN/A\n", "")
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
