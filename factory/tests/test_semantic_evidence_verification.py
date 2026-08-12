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


class TestVerifySufficiencyAggregated:
    """R2.1 Opcion C (docs_plan/R2_1_C_DISENO_AGREGACION_D.md, 2026-08-10):
    agrega criterion_assessments de VARIOS chunks de una misma unidad antes
    de decidir D -- verify_sufficiency() (un solo chunk) no cambia su
    comportamiento (ver TestVerifySufficiency arriba, sigue en verde sin
    tocarla)."""

    def test_single_chunk_matches_verify_sufficiency_exactly(self):
        """Con un solo chunk, el resultado agregado debe ser identico al de
        verify_sufficiency() -- la agregacion de 1 elemento es un no-op."""
        doc = " ".join(_ACCESS_CRITERIA)
        assessments = _all_met()
        single_status, single_reason, single_detail = sev.verify_sufficiency(
            "21_CFR_11.10(d)", assessments, doc)
        agg_status, agg_reason, agg_detail = sev.verify_sufficiency_aggregated(
            "21_CFR_11.10(d)", [(assessments, doc)])
        assert agg_status == single_status == "MET"
        assert agg_detail["met"] == single_detail["met"]

    def test_criteria_scattered_across_two_chunks_combine_to_met(self):
        """El caso central que motiva la Opcion C: ningun chunk individual
        cubre los 5 criterios, pero entre los dos SI -- P1 en la corrida
        real solo tuvo un chunk relevante (por eso no se rescata, ver test
        de abajo); este test prueba que el mecanismo funciona cuando SI hay
        cobertura distribuida real."""
        chunk_a_criteria = _ACCESS_CRITERIA[:3]
        chunk_b_criteria = _ACCESS_CRITERIA[3:]
        chunk_a_text = " ".join(chunk_a_criteria)
        chunk_b_text = " ".join(chunk_b_criteria)

        assessments_a = (
            [_assessment(i + 1, c, "MET", quote=c, location="pag 1") for i, c in enumerate(chunk_a_criteria)]
            + [_assessment(i + 4, c, "NOT_ASSESSABLE") for i, c in enumerate(chunk_b_criteria)]
        )
        assessments_b = (
            [_assessment(i + 1, c, "NOT_ASSESSABLE") for i, c in enumerate(chunk_a_criteria)]
            + [_assessment(i + 4, c, "MET", quote=c, location="pag 5") for i, c in enumerate(chunk_b_criteria)]
        )
        status, reason, detail = sev.verify_sufficiency_aggregated(
            "21_CFR_11.10(d)",
            [(assessments_a, chunk_a_text), (assessments_b, chunk_b_text)],
        )
        assert status == "MET", detail
        assert set(detail["met"]) == set(_ACCESS_CRITERIA)

    def test_p1_real_case_not_rescued_other_chunks_have_nothing_to_add(self):
        """Caso real de P1 (docs_plan/R2_1_C_DISENO_AGREGACION_D.md sec.4):
        el chunk 1 confirmo 2 MET/2 NOT_MET/5 NOT_ASSESSABLE de 9 criterios
        de 21_CFR_11.10(e); los otros 4 chunks reales de esa unidad no
        mencionaban el audit trail en absoluto (criterion_assessments todo
        NOT_ASSESSABLE). Honesto: agregar NO rescata este caso especifico --
        no hay otro chunk con informacion nueva que aportar."""
        from factory.regulatory.requirement_catalog.requirement_catalog_loader import get_requirement

        criteria = get_requirement("21_CFR_11.10(e)")["evidence_min_criteria"]
        assert len(criteria) == 9

        chunk1_text = "UR3.3.1 ... Date and time stamps ... fields listed"
        chunk1_assessments = [
            _assessment(1, criteria[0], "NOT_MET"),
            _assessment(2, criteria[1], "MET", quote="Date and time stamps", location="pag 46"),
            _assessment(3, criteria[2], "MET", quote="fields listed", location="pag 46"),
            _assessment(4, criteria[3], "NOT_MET"),
        ] + [_assessment(i + 5, c, "NOT_ASSESSABLE") for i, c in enumerate(criteria[4:])]

        unrelated_text = "Alarm Limit Modification (page 1 of 2) Security Code Assignments"
        unrelated_assessments = [_assessment(i + 1, c, "NOT_ASSESSABLE") for i, c in enumerate(criteria)]

        status, reason, detail = sev.verify_sufficiency_aggregated(
            "21_CFR_11.10(e)",
            [(chunk1_assessments, chunk1_text)]
            + [(unrelated_assessments, unrelated_text) for _ in range(4)],
        )
        assert status == "NOT_ASSESSABLE", detail
        assert len(detail["not_assessable_individual"]) == 5

    def test_off_topic_chunk_boilerplate_not_met_does_not_poison_real_evidence(self):
        """Fix B3 (R3-T1.4, docs_plan/R3_T1_4_FIX_AGREGACION_B3.md): un
        chunk cuyo `estado` de mas alto nivel ya es evidencia_insuficiente
        para este req_id (no trato el tema en absoluto) NUNCA debe poder
        contradecir en falso a un chunk que SI ancla evidencia real -- ese
        NOT_MET boilerplate se reclasifica a NOT_ASSESSABLE antes de
        agregar, no se cuenta como voto real."""
        anchor_text = " ".join(_ACCESS_CRITERIA)
        anchor_assessments = _all_met()  # chunk relevante, ancla los 5 criterios

        off_topic_text = "Alarm Limit Modification (page 1 of 2) Security Code Assignments"
        off_topic_assessments = _all_not_met()  # boilerplate "no se menciona X" en un chunk que no trata el tema

        status, reason, detail = sev.verify_sufficiency_aggregated(
            "21_CFR_11.10(d)",
            [
                (anchor_assessments, anchor_text, "cumple_parcialmente"),
                (off_topic_assessments, off_topic_text, "evidencia_insuficiente"),
            ],
        )
        assert status == "MET", detail
        assert set(detail["met"]) == set(_ACCESS_CRITERIA)
        assert "contradicted" not in detail

    def test_off_topic_chunk_reproduces_real_11_10_e_partial_case(self):
        """Reproduccion del caso real (R3_T1_3_VIABILIDAD_F2.md secc.1,
        checkpoint chunked-943a62bcbb85): el chunk ancla (p.45-46) confirma
        2/9 criterios de 21_CFR_11.10(e); los otros 28 chunks del documento
        no tratan el audit trail en absoluto y su propio `estado` ya lo
        dice (evidencia_insuficiente) pese a emitir NOT_MET boilerplate.
        Antes del fix esto daba NOT_ASSESSABLE por 'contradiccion real'
        (falsa, ver detail['contradicted'] con crit1..4). Con el fix sigue
        en NOT_ASSESSABLE (los criterios 5-9 nunca se resuelven en ningun
        chunk del documento real -- eso es honesto, no un defecto), pero
        AHORA por cobertura incompleta real, nunca por una contradiccion
        fabricada: crit1 (NOT_MET generico) y crit4 (NOT_MET generico) del
        ancla ya no colisionan con los NOT_MET boilerplate de los otros 28
        chunks, y los 2 MET reales (crit2/crit3) se preservan intactos."""
        from factory.regulatory.requirement_catalog.requirement_catalog_loader import get_requirement

        criteria = get_requirement("21_CFR_11.10(e)")["evidence_min_criteria"]
        assert len(criteria) == 9

        anchor_text = "UR3.3.1 ... Date and time stamps ... fields listed"
        anchor_assessments = [
            _assessment(1, criteria[0], "NOT_MET"),
            _assessment(2, criteria[1], "MET", quote="Date and time stamps", location="pag 46"),
            _assessment(3, criteria[2], "MET", quote="fields listed", location="pag 46"),
            _assessment(4, criteria[3], "NOT_MET"),
        ] + [_assessment(i + 5, c, "NOT_ASSESSABLE") for i, c in enumerate(criteria[4:])]

        off_topic_text = "Alarm Limit Modification (page 1 of 2) Security Code Assignments"
        off_topic_assessments = [_assessment(i + 1, c, "NOT_MET") for i, c in enumerate(criteria)]

        per_chunk = [(anchor_assessments, anchor_text, "cumple_parcialmente")] + [
            (off_topic_assessments, off_topic_text, "evidencia_insuficiente") for _ in range(28)
        ]
        status, reason, detail = sev.verify_sufficiency_aggregated("21_CFR_11.10(e)", per_chunk)
        assert status == "NOT_ASSESSABLE", detail
        assert "cobertura completa" in reason  # NOT_ASSESSABLE por incertidumbre real, no por contradiccion
        assert "contradicted" not in detail
        assert set(detail["met"]) == {criteria[1], criteria[2]}
        assert set(detail["not_met"]) == {criteria[0], criteria[3]}

    def test_genuine_contradiction_between_two_relevant_chunks_still_blocks(self):
        """Guardian obligatorio (sec.2.3 del plan): el fix B3 NUNCA debe
        destrabar una contradiccion GENUINA -- dos chunks AMBOS relevantes
        (estado != evidencia_insuficiente/no_aplica) en desacuerdo real
        sobre un criterio siguen forzando NOT_ASSESSABLE, exactamente como
        antes del fix."""
        crit = _ACCESS_CRITERIA[0]
        rest = _ACCESS_CRITERIA[1:]
        chunk_text = " ".join(_ACCESS_CRITERIA)

        assessments_a = [_assessment(1, crit, "MET", quote=crit, location="pag 1")] + [
            _assessment(i + 2, c, "MET", quote=c, location="pag 1") for i, c in enumerate(rest)
        ]
        assessments_b = [_assessment(1, crit, "NOT_MET")] + [
            _assessment(i + 2, c, "MET", quote=c, location="pag 1") for i, c in enumerate(rest)
        ]
        status, reason, detail = sev.verify_sufficiency_aggregated(
            "21_CFR_11.10(d)",
            [
                (assessments_a, chunk_text, "cumple_parcialmente"),
                (assessments_b, chunk_text, "no_cumple"),  # AMBOS chunks relevantes, no fuera de tema
            ],
        )
        assert status == "NOT_ASSESSABLE"
        assert crit in detail["contradicted"]
        assert "contradiccion" in reason

    def test_absence_across_all_chunks_never_fabricates_met(self):
        """Guardian obligatorio: si NINGUN chunk del documento trata el
        tema (todos evidencia_insuficiente), el fix jamas fabrica un MET --
        el agregado queda en incertidumbre real (NOT_ASSESSABLE), nunca en
        una conclusion positiva. Mas conservador que antes (que daba
        NOT_MET, una negativa 'confiada' que el propio contrato del prompt
        ya advierte no declarar sobre documentos de ingenieria OT), jamas
        menos."""
        off_topic_text = "contenido totalmente no relacionado con el requisito"
        off_topic_assessments = _all_not_met()
        per_chunk = [(off_topic_assessments, off_topic_text, "evidencia_insuficiente") for _ in range(5)]
        status, reason, detail = sev.verify_sufficiency_aggregated("21_CFR_11.10(d)", per_chunk)
        assert status == "NOT_ASSESSABLE", detail
        assert not detail["met"]

    def test_missing_chunk_estado_matches_pre_fix_behavior_exactly(self):
        """Retrocompatibilidad estricta: omitir el 3er elemento de la tupla
        (llamadores viejos, checkpoints anteriores al fix) reproduce el
        comportamiento EXACTO de antes del fix -- un NOT_MET sin `estado`
        conocido sigue contando como voto real y sigue pudiendo contradecir."""
        crit = _ACCESS_CRITERIA[0]
        rest = _ACCESS_CRITERIA[1:]
        chunk_text = " ".join(_ACCESS_CRITERIA)
        assessments_a = [_assessment(1, crit, "MET", quote=crit, location="pag 1")] + [
            _assessment(i + 2, c, "MET", quote=c, location="pag 1") for i, c in enumerate(rest)
        ]
        assessments_b = [_assessment(1, crit, "NOT_MET")] + [
            _assessment(i + 2, c, "MET", quote=c, location="pag 1") for i, c in enumerate(rest)
        ]
        status, reason, detail = sev.verify_sufficiency_aggregated(
            "21_CFR_11.10(d)",
            [(assessments_a, chunk_text), (assessments_b, chunk_text)],  # 2-tuplas, sin estado
        )
        assert status == "NOT_ASSESSABLE"
        assert crit in detail["contradicted"]

    def test_contradiction_across_chunks_never_resolved_silently(self):
        """Riesgo explicito del diseno (sec.3.1): un criterio MET anclado en
        un chunk y NOT_MET en otro es una contradiccion real -- degrada a
        NOT_ASSESSABLE con motivo explicito, nunca se resuelve a favor de
        ningun lado en silencio."""
        crit = _ACCESS_CRITERIA[0]
        rest = _ACCESS_CRITERIA[1:]
        chunk_a_text = " ".join(_ACCESS_CRITERIA)  # ancla crit y rest por igual

        assessments_a = [_assessment(1, crit, "MET", quote=crit, location="pag 1")] + [
            _assessment(i + 2, c, "MET", quote=c, location="pag 1") for i, c in enumerate(rest)
        ]
        # Mismo texto fuente para ambos chunks (chunk_a_text) para aislar la
        # contradiccion al criterio en disputa -- solo el status difiere.
        assessments_b = [_assessment(1, crit, "NOT_MET")] + [
            _assessment(i + 2, c, "MET", quote=c, location="pag 1") for i, c in enumerate(rest)
        ]
        status, reason, detail = sev.verify_sufficiency_aggregated(
            "21_CFR_11.10(d)",
            [(assessments_a, chunk_a_text), (assessments_b, chunk_a_text)],
        )
        assert status == "NOT_ASSESSABLE"
        assert crit in detail["contradicted"]
        assert "contradiccion" in reason

    def test_chunk_with_contract_violation_excluded_not_poisoning_others(self):
        """Un chunk con criterion_index invalido se excluye de la
        agregacion -- no invalida a los demas chunks validos de la misma
        unidad (a diferencia de verify_sufficiency() de un solo chunk,
        donde SI invalida todo porque no hay otro chunk con que
        combinar)."""
        good_text = " ".join(_ACCESS_CRITERIA)
        good_assessments = _all_met()
        bad_assessments = [_assessment(99, "criterio inventado", "MET", quote="x", location="pag 1")]

        status, reason, detail = sev.verify_sufficiency_aggregated(
            "21_CFR_11.10(d)",
            [(bad_assessments, "texto irrelevante"), (good_assessments, good_text)],
        )
        assert status == "MET", detail
        assert set(detail["met"]) == set(_ACCESS_CRITERIA)

    def test_all_chunks_with_contract_violations_falls_not_assessable(self):
        bad_assessments = [_assessment(99, "criterio inventado", "MET", quote="x", location="pag 1")]
        status, reason, detail = sev.verify_sufficiency_aggregated(
            "21_CFR_11.10(d)", [(bad_assessments, "texto irrelevante")],
        )
        assert status == "NOT_ASSESSABLE"
        assert detail["excluded_chunks_contract_violations"]

    def test_none_criteria_chunks_are_skipped(self):
        """Chunks sin criterion_assessments (None -- p.ej. un chunk cuyo
        estado fue evidencia_insuficiente sin array) se saltan, no rompen
        la agregacion de los demas."""
        good_text = " ".join(_ACCESS_CRITERIA)
        status, reason, detail = sev.verify_sufficiency_aggregated(
            "21_CFR_11.10(d)", [(None, "irrelevante"), (_all_met(), good_text)],
        )
        assert status == "MET"

    def test_unknown_requirement_id_not_assessable(self):
        status, reason, detail = sev.verify_sufficiency_aggregated(
            "REQ_INEXISTENTE", [(_all_met(), "texto")])
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
