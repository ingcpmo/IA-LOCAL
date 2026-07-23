"""
Tests -- W5 V2 Fase F: factory.regulatory.semantic_evidence_verification
(validación A/B/C/D).

Cubre: A reusa match_citation sin reimplementar; B verifica requirement_id
+ integridad de la fuente; C combina la heurística léxica existente con
la regla estructural nueva de lista de referencias (validada contra un
fragmento SINTÉTICO que reproduce la ESTRUCTURA real confirmada en el
corpus Rockwell -- lista numerada entre corchetes -- sin citar el texto
extenso real); D siempre NOT_ASSESSABLE explícito, nunca inventado.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory import semantic_evidence_verification as sev


class TestVerifyAnchor:

    def test_exact_match_passes(self):
        status, match_type = sev.verify_anchor("texto exacto", "prefijo texto exacto sufijo")
        assert status == "PASS"
        assert match_type == "exact"

    def test_absent_quote_fails(self):
        status, match_type = sev.verify_anchor("no esta aqui", "otro contenido totalmente distinto")
        assert status == "FAIL"
        assert match_type == "not_found"


class TestVerifyRegulatorySource:

    def test_known_requirement_with_verified_source_passes(self):
        assert sev.verify_regulatory_source("21_CFR_11.10(a)") == "PASS"

    def test_unknown_requirement_fails(self):
        assert sev.verify_regulatory_source("REQ_INVENTADO_NO_EXISTE") == "FAIL"

    def test_all_19_real_requirements_pass_b(self):
        import yaml
        catalog = yaml.safe_load(
            Path("factory/regulatory/requirement_catalog/requirements.yaml").read_text()
        )
        for req_id in catalog["requirements"]:
            assert sev.verify_regulatory_source(req_id) == "PASS", f"{req_id} deberia pasar B"


class TestDetectReferenceListContext:

    def test_detects_bracketed_numbered_reference_list(self):
        """Estructura sintetica que reproduce el patron real confirmado en
        el corpus Rockwell (numeracion entre corchetes de una lista de
        referencias/estandares), sin citar el texto extenso real."""
        doc = (
            "[6]  Some Standard One, Body X\n"
            "[7]  Some Standard Two, Body Y\n"
            "[8]  Example Standard Title, Referenced Body Z\n"
            "[9]  Another internal spec reference\n"
        )
        quote = "Example Standard Title, Referenced Body Z"
        assert sev.detect_reference_list_context(quote, doc) is True

    def test_prose_citation_not_flagged_as_reference_list(self):
        doc = (
            "3. Validation\n"
            "3.1 Systems should be validated to ensure accuracy, reliability, "
            "and consistent intended performance throughout their lifecycle.\n"
        )
        quote = "accuracy, reliability, and consistent intended performance"
        assert sev.detect_reference_list_context(quote, doc) is False

    def test_single_bracket_marker_alone_is_not_enough(self):
        """Un solo marcador [N] no es evidencia suficiente de lista de
        referencias -- exige al menos 2 en la ventana."""
        doc = "Ver referencia [1] para mas detalle sobre el procedimiento de validacion del sistema."
        quote = "detalle sobre el procedimiento de validacion"
        assert sev.detect_reference_list_context(quote, doc) is False

    def test_empty_quote_returns_false(self):
        assert sev.detect_reference_list_context("", "[1] x [2] y") is False

    def test_quote_not_found_returns_false(self):
        assert sev.detect_reference_list_context("no existe en el doc", "[1] x [2] y") is False


class TestVerifySemanticRelevance:

    def test_reference_list_context_forces_not_verifiable(self):
        doc = "[3]  Foo Bar Baz Standard\n[4]  Some Title About Risk-Based Approach\n[5]  Another Ref"
        quote = "Some Title About Risk-Based Approach"
        status, flags = sev.verify_semantic_relevance(quote, doc, requirement_terms=["risk", "approach"])
        assert status == "NOT_VERIFIABLE"
        assert "REFERENCE_LIST_CONTEXT_SUSPECTED" in flags

    def test_no_requirement_terms_flags_not_evaluable(self):
        status, flags = sev.verify_semantic_relevance("cita normal de prosa", "prosa cita normal de prosa", [])
        assert status == "NOT_VERIFIABLE"
        assert "RELEVANCE_NOT_EVALUABLE" in flags

    def test_relevant_prose_with_matching_terms_passes(self):
        doc = "El sistema implementa control de acceso mediante autenticacion de usuarios autorizados."
        quote = "control de acceso mediante autenticacion de usuarios autorizados"
        status, flags = sev.verify_semantic_relevance(quote, doc, requirement_terms=["control de acceso", "autenticacion"])
        assert status == "PASS"
        assert flags == []


class TestVerifyEvidenceABCD:

    def test_annex11_4_like_false_positive_never_accepted(self):
        """Reproduccion sintetica del caso real ANNEX11_4: una cita anclada
        (A=PASS) dentro de una lista de referencias numeradas debe quedar
        SIEMPRE rechazada por C, nunca 'accepted'."""
        doc = (
            "[6]  21 CFR Part 11 Electronic Records, Electronic Signatures\n"
            "[7]  21 CFR Part 211 Current GMP for finished Pharmaceuticals\n"
            "[8]  Good Automated Manufacturing Practice, Guide for Validation\n"
            "[9]  Control programming specification\n"
        )
        quote = "Good Automated Manufacturing Practice, Guide for Validation"
        result = sev.verify_evidence_abcd(quote, doc, "ANNEX11_4", requirement_terms=["risk", "validation"])
        assert result.a_anchor == "PASS"  # la cita SI existe literalmente
        assert result.b_source == "PASS"  # ANNEX11_4 es un requisito real gobernado
        assert result.c_semantic == "NOT_VERIFIABLE"
        assert "REFERENCE_LIST_CONTEXT_SUSPECTED" in result.c_flags
        assert result.accepted is False  # A^B^C nunca se cumple pese a A y B en PASS

    def test_d_is_always_not_assessable_never_fabricated(self):
        result = sev.verify_evidence_abcd("x", "x en contexto", "21_CFR_11.10(a)", [])
        assert result.d_sufficiency == "NOT_ASSESSABLE"
        assert "pendiente" in result.d_reason.lower()

    def test_fully_valid_evidence_is_accepted(self):
        doc = "Access to the system is limited to authorized individuals via role-based authentication."
        quote = "limited to authorized individuals via role-based authentication"
        result = sev.verify_evidence_abcd(
            quote, doc, "21_CFR_11.10(d)", requirement_terms=["access", "authorized", "authentication"]
        )
        assert result.accepted is True

    def test_unknown_requirement_id_never_accepted_even_with_good_anchor(self):
        result = sev.verify_evidence_abcd("texto real", "prefijo texto real sufijo", "REQ_FALSO", [])
        assert result.a_anchor == "PASS"
        assert result.b_source == "FAIL"
        assert result.accepted is False
