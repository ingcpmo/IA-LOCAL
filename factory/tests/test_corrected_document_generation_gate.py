"""
Tests -- W5 V2 Fase N: factory.services.corrected_document_generation_gate.

Cubre los 15 criterios del plan (seccion 16). Regla dura verificada
explicitamente: sin quality_report provisto, "reporte_de_calidad_existe"
falla honestamente (nunca se asume calidad sin el reporte real); con
AGT-QLT ya conectado (document_quality_gate.evaluate_document_quality),
el criterio refleja el resultado real de ese reporte.
"revalidacion_ejecutada" sigue fallando siempre -- Fase O/AGT-RVL no esta
conectada a este gate todavia.
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.services.candidate_document_generator import (
    generate_candidate_document, generate_redline_document,
)
from factory.services.corrected_document_generation_gate import (
    evaluate_corrected_document_generation_gate,
)
from factory.services.document_quality_gate import evaluate_document_quality
from factory.services.remediation_traceability_and_manifest import (
    build_full_change_review, build_package_manifest, build_traceability_matrix,
)

STRUCTURE = {
    "total_paginas": 20,
    "secciones": [
        {"numero": "1", "titulo": "Introduction", "pagina_inicio": 1, "parrafos": ["Texto original 1."]},
        {"numero": "2", "titulo": "Security", "pagina_inicio": 10, "parrafos": ["Texto original 2."]},
    ],
    "texto_previo_a_primera_seccion": ["Portada."],
    "toc_anchored": True,
}


def _citation():
    return {
        "citation_id": "CIT-1", "regulatory_catalog_entry_id": "21_CFR_11.10(a)",
        "regulatory_source": "ecfr_21cfr_part11", "regulatory_source_sha256": "a" * 64,
        "requirement_catalog_sha256": "b" * 64, "run_id": "RUN-1", "record_id": "REC-1",
        "document_role": "CANDIDATE_DOCUMENT", "document_sha256": "c" * 64,
        "chunk_sha256": "d" * 64, "citation_locator": "chunk_1#p10-11",
        "page_start": 10, "page_end": 11, "literal_text": "texto literal real",
        "citation_text_sha256": "e" * 64, "evidence_type": "LITERAL_QUOTE",
        "evidence_location": "seccion 2, pagina 10",
    }


def _change(change_id):
    return {
        "change_id": change_id, "requirement_id": "21_CFR_11.10(a)", "change_risk": "LOW_RISK",
        "document_location": "seccion 2", "original_content": None,
        "proposed_content": "Contenido nuevo propuesto.", "change_reason": "gap detectado",
        "change_type": "CONTENT_ADDITION", "citations": [_citation()],
        "schema_validation_status": "PASSED", "citation_anchor_status": "VERIFIED",
    }


def _doc_bytes(doc) -> bytes:
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _build_real_gate_inputs():
    change = _change("C1")
    package_state = {"changes": {"C1": change}, "exceptions": {}, "medium_risk_batch_decisions": {}}
    candidate_doc = generate_candidate_document(STRUCTURE, [change])
    redline_doc, insertion_manifest = generate_redline_document(STRUCTURE, [change])
    matrix = build_traceability_matrix(package_state, insertion_manifest)
    review = build_full_change_review(package_state)
    candidate_bytes = _doc_bytes(candidate_doc)
    redline_bytes = _doc_bytes(redline_doc)
    manifest = build_package_manifest(
        run_id="RUN-1", package_id="PKG-1", package_version=1,
        artifacts={"candidate": candidate_bytes, "redline": redline_bytes,
                   "matrix": b"matrix-placeholder", "narrativa": b"narrativa-placeholder"},
    )
    return dict(
        candidate_document=candidate_doc, redline_document=redline_doc, structure=STRUCTURE,
        original_document_sha256="f" * 64, candidate_document_bytes=candidate_bytes,
        included_change_ids=["C1"], traceability_matrix_change_ids=[r.change_id for r in matrix],
        insertion_manifest=insertion_manifest, manifest=manifest,
        required_manifest_artifacts=["candidate", "redline", "matrix", "narrativa"],
        change_review=review,
    )


class TestGateAlwaysFailsOnRevalidationAndQuality:

    def test_revalidation_check_always_fails_today(self):
        result = evaluate_corrected_document_generation_gate(**_build_real_gate_inputs())
        revalidation = next(c for c in result.checks if c.criterion == "revalidacion_ejecutada")
        assert revalidation.passed is False
        assert "Fase O" in revalidation.detail

    def test_quality_report_fails_when_not_provided(self):
        result = evaluate_corrected_document_generation_gate(**_build_real_gate_inputs())
        quality = next(c for c in result.checks if c.criterion == "reporte_de_calidad_existe")
        assert quality.passed is False
        assert "quality_report" in quality.detail

    def test_gate_never_reaches_corrected_document_generated_today(self):
        """Consecuencia esperada, no un bug: ningun documento real puede
        pasar el gate completo mientras Fase O/AGT-QLT no existan."""
        result = evaluate_corrected_document_generation_gate(**_build_real_gate_inputs())
        assert result.gate_passed is False
        assert result.final_state != "CORRECTED_DOCUMENT_GENERATED"

    def test_final_state_is_partial_when_only_revalidation_and_quality_are_missing(self):
        result = evaluate_corrected_document_generation_gate(**_build_real_gate_inputs())
        assert result.final_state == "DOCUMENT_GENERATION_PARTIAL"
        assert set(result.failed_criteria) == {"revalidacion_ejecutada", "reporte_de_calidad_existe"}


class TestCoreCriteriaWithRealArtifacts:

    def test_candidate_exists_and_not_empty(self):
        result = evaluate_corrected_document_generation_gate(**_build_real_gate_inputs())
        assert next(c for c in result.checks if c.criterion == "candidato_existe").passed
        assert next(c for c in result.checks if c.criterion == "candidato_no_vacio").passed

    def test_structure_preserved_with_real_generator_output(self):
        result = evaluate_corrected_document_generation_gate(**_build_real_gate_inputs())
        assert next(c for c in result.checks if c.criterion == "conserva_estructura_requerida").passed
        assert next(c for c in result.checks if c.criterion == "no_truncado").passed

    def test_sha256_new_differs_from_original(self):
        result = evaluate_corrected_document_generation_gate(**_build_real_gate_inputs())
        assert next(c for c in result.checks if c.criterion == "sha256_nuevo").passed

    def test_all_change_ids_are_in_matrix(self):
        result = evaluate_corrected_document_generation_gate(**_build_real_gate_inputs())
        assert next(c for c in result.checks if c.criterion == "todos_los_change_id_en_matriz").passed

    def test_redline_matches_candidate_change_ids(self):
        result = evaluate_corrected_document_generation_gate(**_build_real_gate_inputs())
        assert next(c for c in result.checks if c.criterion == "redline_coincide_con_candidato").passed

    def test_manifest_includes_all_required_artifacts(self):
        result = evaluate_corrected_document_generation_gate(**_build_real_gate_inputs())
        assert next(c for c in result.checks if c.criterion == "manifest_incluye_todos_los_artefactos").passed

    def test_review_covers_all_changes(self):
        result = evaluate_corrected_document_generation_gate(**_build_real_gate_inputs())
        assert next(c for c in result.checks if c.criterion == "resena_completa").passed


class TestBrokenScenariosAreDetected:

    def test_missing_manifest_artifact_fails_that_criterion(self):
        inputs = _build_real_gate_inputs()
        inputs["manifest"] = {"artifact_hashes": {"candidate": "x"}}
        result = evaluate_corrected_document_generation_gate(**inputs)
        check = next(c for c in result.checks if c.criterion == "manifest_incluye_todos_los_artefactos")
        assert check.passed is False
        assert "redline" in check.detail

    def test_change_id_missing_from_matrix_fails_that_criterion(self):
        inputs = _build_real_gate_inputs()
        inputs["traceability_matrix_change_ids"] = []
        result = evaluate_corrected_document_generation_gate(**inputs)
        check = next(c for c in result.checks if c.criterion == "todos_los_change_id_en_matriz")
        assert check.passed is False

    def test_same_sha256_as_original_fails_sha256_nuevo(self):
        inputs = _build_real_gate_inputs()
        inputs["original_document_sha256"] = inputs["candidate_document_bytes"]
        import hashlib
        inputs["original_document_sha256"] = hashlib.sha256(inputs["candidate_document_bytes"]).hexdigest()
        result = evaluate_corrected_document_generation_gate(**inputs)
        check = next(c for c in result.checks if c.criterion == "sha256_nuevo")
        assert check.passed is False

    def test_incomplete_package_when_core_criteria_also_fail(self):
        inputs = _build_real_gate_inputs()
        inputs["traceability_matrix_change_ids"] = []
        result = evaluate_corrected_document_generation_gate(**inputs)
        assert result.final_state == "DOCUMENT_PACKAGE_INCOMPLETE"


class TestAGTQLTConnected:
    """AGT-QLT ya conectado: el criterio 'reporte_de_calidad_existe' debe
    reflejar el resultado real de document_quality_gate.evaluate_document_quality,
    no un FAIL hardcodeado."""

    def _full_change(self, change_id="C1"):
        import hashlib
        literal_text = "texto literal real"
        citation = {
            "citation_id": "CIT-1", "regulatory_catalog_entry_id": "21_CFR_11.10(a)",
            "regulatory_source": "ecfr_21cfr_part11", "regulatory_source_sha256": "a" * 64,
            "requirement_catalog_sha256": "b" * 64, "run_id": "RUN-1", "record_id": "REC-1",
            "document_role": "CANDIDATE_DOCUMENT", "document_sha256": "c" * 64,
            "chunk_sha256": "d" * 64, "citation_locator": "chunk_1#p10-11",
            "page_start": 10, "page_end": 11, "literal_text": literal_text,
            "citation_text_sha256": hashlib.sha256(literal_text.encode()).hexdigest(),
            "evidence_type": "LITERAL_QUOTE", "evidence_location": "seccion 2, pagina 10",
        }
        return {
            "change_id": change_id, "finding_id": f"F-{change_id}", "requirement_id": "21_CFR_11.10(a)",
            "change_risk": "LOW_RISK", "document_location": "seccion 2", "original_content": None,
            "proposed_content": "Agregar control de acceso adicional segun el nuevo requisito.",
            "change_reason": "gap detectado", "change_type": "CONTENT_ADDITION", "citations": [citation],
            "change_risk_basis": ["change_type"], "evaluation_confidence": "HIGH_CONFIDENCE",
            "evaluation_confidence_basis": ["coverage_status"], "schema_validation_status": "PASSED",
            "citation_anchor_status": "VERIFIED", "relevance_status": "CONFIRMED",
            "candidate_application_status": "APPLIED_TO_DRAFT", "limitations": "",
        }

    def test_quality_report_passing_makes_the_criterion_pass(self):
        change = self._full_change()
        candidate = generate_candidate_document(STRUCTURE, [change])
        full_text = "\n".join(p.text for p in candidate.paragraphs)
        quality_report = evaluate_document_quality(
            structure=STRUCTURE, candidate_full_text=full_text, changes=[change],
        )
        assert quality_report["applied"] is True

        inputs = _build_real_gate_inputs()
        inputs["quality_report"] = quality_report
        result = evaluate_corrected_document_generation_gate(**inputs)
        quality_check = next(c for c in result.checks if c.criterion == "reporte_de_calidad_existe")
        assert quality_check.passed is True

    def test_quality_report_failing_makes_the_criterion_fail_with_real_reason(self):
        bad_change = self._full_change()
        bad_change["proposed_content"] = "x"  # verbo no controlado, demasiado corto
        quality_report = evaluate_document_quality(
            structure=STRUCTURE, candidate_full_text="documento sin relacion", changes=[bad_change],
        )
        assert quality_report["applied"] is False

        inputs = _build_real_gate_inputs()
        inputs["quality_report"] = quality_report
        result = evaluate_corrected_document_generation_gate(**inputs)
        quality_check = next(c for c in result.checks if c.criterion == "reporte_de_calidad_existe")
        assert quality_check.passed is False
        assert "C1" in quality_check.detail

    def test_revalidation_still_fails_gate_never_reaches_full_pass(self):
        """AGT-QLT conectado no basta para CORRECTED_DOCUMENT_GENERATED --
        revalidacion_ejecutada sigue sin conectar (fuera de este cambio)."""
        change = self._full_change()
        candidate = generate_candidate_document(STRUCTURE, [change])
        full_text = "\n".join(p.text for p in candidate.paragraphs)
        quality_report = evaluate_document_quality(
            structure=STRUCTURE, candidate_full_text=full_text, changes=[change],
        )
        inputs = _build_real_gate_inputs()
        inputs["quality_report"] = quality_report
        result = evaluate_corrected_document_generation_gate(**inputs)
        assert result.gate_passed is False
        assert result.failed_criteria == ["revalidacion_ejecutada"]
        assert result.final_state == "DOCUMENT_GENERATION_PARTIAL"
