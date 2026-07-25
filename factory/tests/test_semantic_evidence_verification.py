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


_ACCESS_CRITERIA = [
    "Mecanismo de control de acceso (propio o federado) sobre el sistema, descrito.",
    "Alta, cambio, revision periodica y revocacion de cuentas.",
    "Cuentas humanas individuales (no compartidas).",
    "Cuentas tecnicas no interactivas, si existen, gobernadas con propietario, proposito, privilegio "
    "minimo y prohibicion de firma electronica.",
    "Evidencia de prueba de acceso permitido y denegado.",
]


def _assessment(index: int, text: str, status: str, quote: str = "", location: str = "") -> dict:
    return {
        "criterion_index": index, "criterion_text": text, "status": status,
        "evidence_quote": quote, "evidence_location": location,
        "justification": "test", "limitations": "",
    }


def _all_met(criteria=_ACCESS_CRITERIA) -> list:
    return [_assessment(i + 1, c, "MET", quote=c, location="pag 1") for i, c in enumerate(criteria)]


def _all_not_met(criteria=_ACCESS_CRITERIA) -> list:
    return [_assessment(i + 1, c, "NOT_MET") for i, c in enumerate(criteria)]


class TestVerifySufficiency:

    def test_none_criteria_stays_not_assessable(self):
        status, reason, detail = sev.verify_sufficiency("21_CFR_11.10(d)", None, "cualquier texto")
        assert status == "NOT_ASSESSABLE"
        assert "pendiente" in reason.lower()
        assert detail == {}

    def test_unknown_requirement_id_stays_not_assessable(self):
        status, reason, detail = sev.verify_sufficiency("REQ_INVENTADO_XYZ", [], "texto")
        assert status == "NOT_ASSESSABLE"
        assert "desconocido" in reason.lower()

    def test_all_criteria_met_and_anchored_is_met(self):
        doc = " ".join(_ACCESS_CRITERIA)  # cada criterio ancla literalmente en el doc
        status, reason, detail = sev.verify_sufficiency("21_CFR_11.10(d)", _all_met(), doc)
        assert status == "MET"
        assert set(detail["met"]) == set(_ACCESS_CRITERIA)
        assert detail["missing"] == []

    def test_all_criteria_unmet_is_not_met(self):
        status, reason, detail = sev.verify_sufficiency(
            "21_CFR_11.10(d)", _all_not_met(), "documento sin evidencia real"
        )
        assert status == "NOT_MET"
        assert set(detail["not_met"]) == set(_ACCESS_CRITERIA)

    def test_partial_coverage_with_full_classification_is_partially_met(self):
        doc = _ACCESS_CRITERIA[0]  # solo el primero ancla
        assessments = [_assessment(1, _ACCESS_CRITERIA[0], "MET", quote=_ACCESS_CRITERIA[0], location="pag 1")]
        assessments += [_assessment(i + 2, c, "NOT_MET") for i, c in enumerate(_ACCESS_CRITERIA[1:])]
        status, reason, detail = sev.verify_sufficiency("21_CFR_11.10(d)", assessments, doc)
        assert status == "PARTIALLY_MET"
        assert detail["met"] == [_ACCESS_CRITERIA[0]]
        assert len(detail["not_met"]) == 4

    def test_incomplete_coverage_stays_not_assessable_never_guesses(self):
        """Solo 2 de 5 criterios clasificados -- nunca se adivina sobre los
        3 restantes, ni siquiera con los 2 confirmados en MET real."""
        doc = _ACCESS_CRITERIA[0]
        assessments = [
            _assessment(1, _ACCESS_CRITERIA[0], "MET", quote=_ACCESS_CRITERIA[0], location="pag 1"),
            _assessment(2, _ACCESS_CRITERIA[1], "NOT_MET"),
        ]
        status, reason, detail = sev.verify_sufficiency("21_CFR_11.10(d)", assessments, doc)
        assert status == "NOT_ASSESSABLE"
        assert len(detail["missing"]) == 3
        assert "incompleta" in reason.lower()

    def test_individual_not_assessable_forces_aggregate_not_assessable(self):
        """Cobertura completa pero un criterio queda NOT_ASSESSABLE
        individual (declarado por el modelo) -- nunca se confirma el
        agregado sin certeza real en todos los criterios."""
        doc = " ".join(_ACCESS_CRITERIA)
        assessments = _all_met()
        assessments[-1] = _assessment(5, _ACCESS_CRITERIA[4], "NOT_ASSESSABLE")
        status, reason, detail = sev.verify_sufficiency("21_CFR_11.10(d)", assessments, doc)
        assert status == "NOT_ASSESSABLE"
        assert _ACCESS_CRITERIA[4] in detail["not_assessable_individual"]

    def test_invented_criterion_text_rejects_whole_array_atomically(self):
        """El modelo 'inventa' un criterio fuera de la whitelist real del
        catalogo -- rechazo ATOMICO de todo el array (nivel de contrato),
        nunca se rescatan los 5 reales aunque esten bien formados."""
        doc = " ".join(_ACCESS_CRITERIA)
        assessments = _all_met()
        assessments.append(_assessment(6, "Criterio inventado que no existe en el catalogo", "MET",
                                        quote=doc, location="pag 1"))
        status, reason, detail = sev.verify_sufficiency("21_CFR_11.10(d)", assessments, doc)
        assert status == "NOT_ASSESSABLE"
        assert "contrato" in reason.lower()
        assert any("6" in v for v in detail["contract_violations"])  # indice fuera de rango

    def test_duplicate_criterion_index_rejects_whole_array_atomically(self):
        doc = " ".join(_ACCESS_CRITERIA)
        assessments = _all_met()
        assessments.append(_assessment(1, _ACCESS_CRITERIA[0], "MET", quote=_ACCESS_CRITERIA[0], location="pag 1"))
        status, reason, detail = sev.verify_sufficiency("21_CFR_11.10(d)", assessments, doc)
        assert status == "NOT_ASSESSABLE"
        assert any("duplicado" in v.lower() for v in detail["contract_violations"])

    def test_index_text_mismatch_rejects_whole_array_atomically(self):
        """criterion_index=1 pero criterion_text no es el criterio real #1
        -- desincronizacion indice/texto, rechazo atomico."""
        doc = " ".join(_ACCESS_CRITERIA)
        assessments = _all_met()
        assessments[0] = _assessment(1, _ACCESS_CRITERIA[1], "MET", quote=_ACCESS_CRITERIA[1], location="pag 1")
        status, reason, detail = sev.verify_sufficiency("21_CFR_11.10(d)", assessments, doc)
        assert status == "NOT_ASSESSABLE"
        assert any("no coincide" in v for v in detail["contract_violations"])

    def test_invalid_status_rejects_whole_array_atomically(self):
        doc = " ".join(_ACCESS_CRITERIA)
        assessments = _all_met()
        assessments[0]["status"] = "SOMETHING_MADE_UP"
        status, reason, detail = sev.verify_sufficiency("21_CFR_11.10(d)", assessments, doc)
        assert status == "NOT_ASSESSABLE"
        assert any("status invalido" in v for v in detail["contract_violations"])

    def test_met_without_evidence_quote_rejects_whole_array_atomically(self):
        doc = " ".join(_ACCESS_CRITERIA)
        assessments = _all_met()
        assessments[0]["evidence_quote"] = ""
        status, reason, detail = sev.verify_sufficiency("21_CFR_11.10(d)", assessments, doc)
        assert status == "NOT_ASSESSABLE"
        assert any("evidence_quote" in v for v in detail["contract_violations"])

    def test_met_without_evidence_location_rejects_whole_array_atomically(self):
        doc = " ".join(_ACCESS_CRITERIA)
        assessments = _all_met()
        assessments[0]["evidence_location"] = ""
        status, reason, detail = sev.verify_sufficiency("21_CFR_11.10(d)", assessments, doc)
        assert status == "NOT_ASSESSABLE"
        assert any("evidence_location" in v for v in detail["contract_violations"])

    def test_unanchored_quote_discards_criterion_never_trusts_bare_claim(self):
        """Un criterio MET (contrato válido) con cita no anclada se
        descarta individualmente (nivel factual, no de contrato) -- nunca
        cuenta como MET. Como queda sin clasificar, la cobertura es
        incompleta -> NOT_ASSESSABLE, nunca se adivina NOT_MET."""
        assessments = [_assessment(1, _ACCESS_CRITERIA[0], "MET",
                                    quote="cita que no existe en el documento real", location="pag 1")]
        assessments += [_assessment(i + 2, c, "NOT_MET") for i, c in enumerate(_ACCESS_CRITERIA[1:])]
        status, reason, detail = sev.verify_sufficiency(
            "21_CFR_11.10(d)", assessments, "documento real sin esa cita"
        )
        assert _ACCESS_CRITERIA[0] in detail["discarded_unanchored"]
        assert _ACCESS_CRITERIA[0] not in detail["met"]
        assert status == "NOT_ASSESSABLE"


class TestVerifyEvidenceABCD:

    def test_annex11_4_like_false_positive_never_accepted(self):
        """Reproduccion sintetica del caso real ANNEX11_4: una cita anclada
        (A=PASS) dentro de una lista de referencias numeradas debe quedar
        SIEMPRE rechazada por C, nunca 'substantive_evidence_accepted'."""
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
        assert result.substantive_evidence_accepted is False

    def test_d_is_always_not_assessable_never_fabricated_without_criterion_assessments(self):
        result = sev.verify_evidence_abcd("x", "x en contexto", "21_CFR_11.10(a)", [])
        assert result.d_sufficiency == "NOT_ASSESSABLE"
        assert "pendiente" in result.d_reason.lower()

    def test_unknown_requirement_id_never_accepted_even_with_good_anchor(self):
        result = sev.verify_evidence_abcd("texto real", "prefijo texto real sufijo", "REQ_FALSO", [])
        assert result.a_anchor == "PASS"
        assert result.b_source == "FAIL"
        assert result.substantive_evidence_accepted is False

    def test_substantive_evidence_accepted_requires_d_met_incondicional(self):
        """A^B^C pasan, pero D=NOT_MET -- substantive_evidence_accepted
        debe ser False (conjuncion incondicional, sin excepcion)."""
        doc = "Access to the system is limited to authorized individuals via role-based authentication."
        quote = "limited to authorized individuals via role-based authentication"
        result = sev.verify_evidence_abcd(
            quote, doc, "21_CFR_11.10(d)", requirement_terms=["access", "authorized", "authentication"],
            criterion_assessments=_all_not_met(),
        )
        assert result.a_anchor == "PASS" and result.b_source == "PASS" and result.c_semantic == "PASS"
        assert result.d_sufficiency == "NOT_MET"
        assert result.substantive_evidence_accepted is False
        assert result.operational_result == "EVALUATION_COMPLETE"

    def test_substantive_evidence_accepted_true_when_d_met_and_abc_pass(self):
        doc = ("Access to the system is limited to authorized individuals via role-based authentication. "
               + " ".join(_ACCESS_CRITERIA))
        quote = "limited to authorized individuals via role-based authentication"
        result = sev.verify_evidence_abcd(
            quote, doc, "21_CFR_11.10(d)", requirement_terms=["access", "authorized", "authentication"],
            criterion_assessments=_all_met(),
        )
        assert result.d_sufficiency == "MET"
        assert result.substantive_evidence_accepted is True
        assert result.operational_result == "EVALUATION_COMPLETE"

    def test_substantive_evidence_accepted_false_when_d_not_assessable_no_exception(self):
        """Default (sin criterion_assessments) -- resultado HISTORICO
        (p.ej. equivalente a la corrida URS v2.1): D=NOT_ASSESSABLE nunca
        se traduce en aceptacion, sin excepcion de compatibilidad
        retroactiva. operational_result marca la incompletitud."""
        doc = "Access to the system is limited to authorized individuals via role-based authentication."
        quote = "limited to authorized individuals via role-based authentication"
        result = sev.verify_evidence_abcd(
            quote, doc, "21_CFR_11.10(d)", requirement_terms=["access", "authorized", "authentication"],
        )
        assert result.d_sufficiency == "NOT_ASSESSABLE"
        assert result.substantive_evidence_accepted is False
        assert result.operational_result == "EVALUATION_INCOMPLETE"

    def test_partially_met_never_accepted(self):
        doc = " ".join(_ACCESS_CRITERIA) + " Access to the system is limited to authorized individuals via role-based authentication."
        quote = "limited to authorized individuals via role-based authentication"
        assessments = [_assessment(1, _ACCESS_CRITERIA[0], "MET", quote=_ACCESS_CRITERIA[0], location="pag 1")]
        assessments += [_assessment(i + 2, c, "NOT_MET") for i, c in enumerate(_ACCESS_CRITERIA[1:])]
        result = sev.verify_evidence_abcd(
            quote, doc, "21_CFR_11.10(d)", requirement_terms=["access", "authorized", "authentication"],
            criterion_assessments=assessments,
        )
        assert result.d_sufficiency == "PARTIALLY_MET"
        assert result.substantive_evidence_accepted is False
