"""
Tests -- W5 V2 Fase M: factory.services.remediation_traceability_and_manifest.

Cubre: matriz de trazabilidad real (requirement_id -> change_id -> seccion
-> revalidacion), reseña de cambios ensamblada solo desde campos reales
(nunca texto inventado), y manifest con SHA-256 real por artefacto +
fingerprint parcial declarado honestamente.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.services.remediation_traceability_and_manifest import (
    build_change_narrative, build_full_change_review, build_package_manifest,
    build_traceability_matrix,
)


class _FakeGapResult:
    def __init__(self, change_id, gap_status, detail):
        self.change_id, self.gap_status, self.detail = change_id, gap_status, detail


class _FakeRevalidation:
    """Doble minimo del DocumentRevalidationResult de Fase O -- solo
    gap_results, que es lo unico que la matriz consume. El contrato real
    se verifica aparte con el objeto verdadero."""
    def __init__(self, gap_results):
        self.gap_results = gap_results


def _fake_revalidation(by_change_id: dict):
    return _FakeRevalidation([_FakeGapResult(cid, status, detail)
                               for cid, (status, detail) in by_change_id.items()])


def _citation(citation_id="CIT-1", regulatory_source="ecfr_21cfr_part11"):
    return {
        "citation_id": citation_id, "regulatory_catalog_entry_id": "21_CFR_11.10(a)",
        "regulatory_source": regulatory_source, "regulatory_source_sha256": "a" * 64,
        "requirement_catalog_sha256": "b" * 64, "run_id": "RUN-1", "record_id": "REC-1",
        "document_role": "CANDIDATE_DOCUMENT", "document_sha256": "c" * 64,
        "chunk_sha256": "d" * 64, "citation_locator": "chunk_1#p10-11",
        "page_start": 10, "page_end": 11, "literal_text": "texto literal real",
        "citation_text_sha256": "e" * 64, "evidence_type": "LITERAL_QUOTE",
        "evidence_location": "seccion 2, pagina 10",
    }


def _change(change_id, risk="LOW_RISK", requirement_id="21_CFR_11.10(a)", citations=None):
    return {
        "change_id": change_id, "requirement_id": requirement_id, "change_risk": risk,
        "document_location": "seccion 2", "original_content": None,
        "proposed_content": "texto propuesto real", "change_reason": "gap detectado en auditoria",
        "change_type": "CONTENT_ADDITION", "citations": citations or [_citation()],
        "schema_validation_status": "PASSED", "citation_anchor_status": "VERIFIED",
    }


def _package_state(changes, exceptions=None, batch_decisions=None):
    return {
        "changes": {c["change_id"]: c for c in changes},
        "exceptions": exceptions or {},
        "medium_risk_batch_decisions": batch_decisions or {},
    }


class TestBuildTraceabilityMatrix:

    def test_row_per_change_with_real_fields(self):
        change = _change("C1")
        state = _package_state([change])
        rows = build_traceability_matrix(state)
        assert len(rows) == 1
        row = rows[0]
        assert row.requirement_id == "21_CFR_11.10(a)"
        assert row.change_id == "C1"
        assert row.final_status == "AUTO_APPLIED_TO_DRAFT"
        assert row.citation_ids == ["CIT-1"]

    def test_section_numero_comes_from_insertion_manifest(self):
        change = _change("C1")
        state = _package_state([change])
        insertion_manifest = [{"change_id": "C1", "section_numero": "2", "paragraph_index": 5}]
        rows = build_traceability_matrix(state, insertion_manifest)
        assert rows[0].section_numero == "2"

    def test_excluded_change_still_appears_in_matrix_with_its_reason(self):
        """Un cambio excluido del candidato debe seguir siendo trazable --
        la matriz no oculta lo que no se aplico."""
        high = _change("C1", risk="HIGH_RISK")
        state = _package_state([high])
        rows = build_traceability_matrix(state)
        assert rows[0].final_status == "EXCEPTION_REQUIRED"
        assert rows[0].included_in_clean_candidate is False

    def test_revalidation_status_without_agt_rvl_result_is_not_executed(self):
        """Corregido en la auditoria de Fases J-P (2026-07-27): antes era la
        constante PENDING_PHASE_O con el motivo 'AGT-RVL no existe todavia',
        falso desde que Fase O (87d351f) lo construyo. Sin resultado real
        lo unico cierto es que no se ejecuto para ESTE paquete."""
        rows = build_traceability_matrix(_package_state([_change("C1")]))
        assert rows[0].revalidation_status == "REVALIDATION_NOT_EXECUTED"
        assert "no se ejecuto para este paquete" in rows[0].revalidation_detail

    def test_matrix_transports_the_real_agt_rvl_verdict_per_change(self):
        """Cableado real a Fase O: el gap_status de AGT-RVL viaja por
        change_id, no se re-deriva ni se resume."""
        state = _package_state([_change("C1"), _change("C2")])
        revalidation = _fake_revalidation({"C1": ("CLOSED", "anclado literalmente"),
                                            "C2": ("OPEN", "ausente del candidato real")})
        rows = {r.change_id: r for r in build_traceability_matrix(state, revalidation=revalidation)}
        assert rows["C1"].revalidation_status == "CLOSED"
        assert rows["C2"].revalidation_status == "OPEN"
        assert rows["C2"].revalidation_detail == "ausente del candidato real"

    def test_change_absent_from_the_revalidation_result_is_not_covered(self):
        """Fail-closed: AGT-RVL corrio pero no cubrio este cambio -- no
        hereda el veredicto de los demas ni se asume CLOSED."""
        state = _package_state([_change("C1"), _change("C2")])
        revalidation = _fake_revalidation({"C1": ("CLOSED", "ok")})
        rows = {r.change_id: r for r in build_traceability_matrix(state, revalidation=revalidation)}
        assert rows["C2"].revalidation_status == "REVALIDATION_NOT_COVERED"

    def test_real_agt_rvl_result_object_is_accepted(self):
        """Contra el objeto REAL de Fase O, no solo contra el doble: si el
        contrato de DocumentRevalidationResult cambia, esto se entera."""
        from factory.services.independent_candidate_revalidation import (
            DocumentRevalidationResult, GapRevalidationResult,
        )
        real = DocumentRevalidationResult(
            gap_results=[GapRevalidationResult("C1", "REQ-C1", "CLOSED", "anclado")],
            new_gaps_introduced=[], all_hashes_valid=True,
            document_opens_correctly=True, artifacts_consistent=True,
        )
        rows = build_traceability_matrix(_package_state([_change("C1")]), revalidation=real)
        assert rows[0].revalidation_status == "CLOSED"


class TestBuildChangeNarrative:

    def test_narrative_uses_only_real_fields(self):
        change = _change("C1")
        narrative = build_change_narrative(change, "AUTO_APPLIED_TO_DRAFT: gates ok")
        assert narrative["change_id"] == "C1"
        assert narrative["contenido_nuevo"] == "texto propuesto real"
        assert narrative["motivo"] == "gap detectado en auditoria"
        assert narrative["cita"] == "texto literal real"
        assert "gates ok" in narrative["estado_aplicacion"]

    def test_official_url_resolved_from_real_catalog(self):
        change = _change("C1")
        narrative = build_change_narrative(change, "x")
        assert narrative["url_oficial"].startswith("http")

    def test_unknown_source_id_never_fabricates_url(self):
        change = _change("C1", citations=[_citation(regulatory_source="fuente_inexistente")])
        narrative = build_change_narrative(change, "x")
        assert narrative["url_oficial"] == "NO_RESOLVIBLE (source_id no encontrado en el catalogo gobernado)"

    def test_implementation_pending_disclaimer_always_present(self):
        change = _change("C1")
        narrative = build_change_narrative(change, "x")
        assert "IMPLEMENTATION_VERIFICATION" in narrative["implementacion_pendiente"]

    def test_content_replacement_narrative_says_replaced(self):
        change = _change("C1")
        change["change_type"] = "CONTENT_REPLACEMENT"
        narrative = build_change_narrative(change, "x")
        assert "reemplazo" in narrative["narrativa"]


class TestBuildFullChangeReview:

    def test_covers_every_change_in_package(self):
        low = _change("C1")
        high = _change("C2", risk="HIGH_RISK")
        review = build_full_change_review(_package_state([low, high]))
        assert {r["change_id"] for r in review} == {"C1", "C2"}

    def test_high_risk_narrative_reflects_its_real_resolution(self):
        high = _change("C1", risk="HIGH_RISK")
        review = build_full_change_review(_package_state([high]))
        assert "EXCEPTION_REQUIRED" in review[0]["estado_aplicacion"]

    def test_review_without_agt_rvl_declares_not_executed(self):
        """La reseña es un artefacto que ve QA: no puede afirmar un
        resultado de revalidacion que nadie produjo."""
        review = build_full_change_review(_package_state([_change("C1")]))
        assert review[0]["resultado_revalidacion"] == "REVALIDATION_NOT_EXECUTED"
        assert "no se ejecuto para este paquete" in review[0]["resultado_revalidacion_detalle"]
        assert "REVALIDATION_NOT_EXECUTED" in review[0]["narrativa"]

    def test_review_transports_the_real_agt_rvl_verdict(self):
        state = _package_state([_change("C1"), _change("C2")])
        revalidation = _fake_revalidation({"C1": ("CLOSED", "anclado"),
                                            "C2": ("PARTIALLY_CLOSED", "desviacion fuzzy")})
        review = {r["change_id"]: r for r in build_full_change_review(state, revalidation=revalidation)}
        assert review["C1"]["resultado_revalidacion"] == "CLOSED"
        assert review["C2"]["resultado_revalidacion"] == "PARTIALLY_CLOSED"
        assert "PARTIALLY_CLOSED" in review["C2"]["narrativa"]

    def test_review_never_reports_the_obsolete_pending_phase_o_constant(self):
        """Guardia contra la regresion exacta que motivo este fix: el
        estado de revalidacion no puede volver a ser una constante que
        afirme que AGT-RVL no existe."""
        review = build_full_change_review(_package_state([_change("C1")]))
        serialized = str(review[0])
        assert "PENDING_PHASE_O" not in serialized
        assert "no existe todavia" not in serialized


class TestBuildPackageManifest:

    def test_computes_real_sha256_per_artifact(self):
        manifest = build_package_manifest(
            run_id="RUN-1", package_id="PKG-1", package_version=1,
            artifacts={"candidate.docx": b"contenido real del docx"},
        )
        import hashlib
        expected = hashlib.sha256(b"contenido real del docx").hexdigest()
        assert manifest["artifact_hashes"]["candidate.docx"] == expected

    def test_fingerprint_is_deterministic_for_same_inputs(self):
        m1 = build_package_manifest(run_id="RUN-1", package_id="PKG-1", package_version=1,
                                     artifacts={"a": b"x"})
        m2 = build_package_manifest(run_id="RUN-1", package_id="PKG-1", package_version=1,
                                     artifacts={"a": b"x"})
        assert m1["fingerprint"] == m2["fingerprint"]

    def test_fingerprint_changes_if_artifact_content_changes(self):
        m1 = build_package_manifest(run_id="RUN-1", package_id="PKG-1", package_version=1,
                                     artifacts={"a": b"x"})
        m2 = build_package_manifest(run_id="RUN-1", package_id="PKG-1", package_version=1,
                                     artifacts={"a": b"y"})
        assert m1["fingerprint"] != m2["fingerprint"]

    def test_declares_incomplete_fingerprint_honestly(self):
        manifest = build_package_manifest(run_id="RUN-1", package_id="PKG-1", package_version=1, artifacts={})
        assert manifest["fingerprint_complete"] is False
        assert "model_digest" in manifest["fingerprint_missing_components"]
