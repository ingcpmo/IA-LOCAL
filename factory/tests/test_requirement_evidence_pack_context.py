"""
Tests -- W5 V2 Fase C: campos mecánicos del Requirement Evidence Pack
(context_before, context_after, pack_version, evidence_pack_status)
agregados a requirement_catalog_entry_v1.json y respaldados por
factory/regulatory/tools/build_requirement_evidence_pack_context.py.

Los campos interpretativos (evidence_min_criteria, exclusion_criteria,
weak_keywords, typical_insufficient_evidence, governed_interpretation,
expected_doc_types) requieren juicio regulatorio humano. A partir de
2026-07-23 (aprobación de Cesar) los 19 requisitos del catálogo -- CFR11
(5), ANNEX11 (5) y ALCOA (9) -- ya tienen ese contenido redactado; estas
pruebas verifican que está presente, no vacío, y que ningún requisito
quedó sin pasar por ese juicio humano.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import jsonschema
import pytest
import yaml

from factory.regulatory.tools import build_requirement_evidence_pack_context as ctx_mod

_SCHEMA = json.loads(
    Path("factory/regulatory/schemas/requirement_catalog_entry_v1.json").read_text()
)
_REAL_CATALOG = yaml.safe_load(
    Path("factory/regulatory/requirement_catalog/requirements.yaml").read_text()
)


class TestNormalizeWithMapping:

    def test_collapses_whitespace_runs_to_single_space(self):
        norm, mapping = ctx_mod._normalize_with_mapping("a  \n\n  b")
        assert norm == "a b"
        assert len(mapping) == len(norm)

    def test_mapping_points_back_to_original_indices(self):
        text = "hello   world"
        norm, mapping = ctx_mod._normalize_with_mapping(text)
        assert norm == "hello world"
        # el espacio normalizado debe apuntar al primer espacio original
        assert text[mapping[5]] == " "


class TestFindContext:

    def test_exact_substring_match(self):
        full_text = "prefijo texto ANCLA_REAL sufijo"
        before, after = ctx_mod.find_context(full_text, "ANCLA_REAL", context_chars=20)
        assert before.endswith("prefijo texto ")
        assert after.startswith(" sufijo")

    def test_matches_across_normalized_whitespace(self):
        """El texto fuente puede tener saltos de linea donde citation_text
        tiene un solo espacio -- debe encontrarse igual."""
        full_text = "antes de la cita\nUNA CITA\ncon\nsaltos DE linea aqui despues"
        before, after = ctx_mod.find_context(full_text, "UNA CITA\ncon\nsaltos DE linea", context_chars=50)
        assert "antes de la cita" in before
        assert "aqui despues" in after

    def test_returns_empty_strings_when_not_found(self):
        before, after = ctx_mod.find_context("texto que no contiene nada relevante", "CITA_INEXISTENTE")
        assert before == ""
        assert after == ""

    def test_context_never_invents_text_beyond_document_boundaries(self):
        full_text = "CITA_AL_INICIO resto del documento"
        before, after = ctx_mod.find_context(full_text, "CITA_AL_INICIO", context_chars=50)
        assert before == ""  # nada antes, nunca se rellena con placeholder


class TestBackfillRaisesOnUnlocatableCitation:

    def test_raises_when_citation_not_found_in_source_text(self, tmp_path, monkeypatch):
        requirements_path = tmp_path / "requirements.yaml"
        requirements_path.write_text(yaml.safe_dump({
            "requirements": {
                "FAKE_REQ": {
                    "source_id": "fake_source",
                    "citation": {"citation_text": "esto no existe en ningun lado"},
                }
            }
        }), encoding="utf-8")
        registry_path = tmp_path / "registry.json"
        source_txt = tmp_path / "source.txt"
        source_txt.write_text("contenido real que no menciona la cita buscada", encoding="utf-8")
        registry_path.write_text(json.dumps({
            "sources": [{
                "source_id": "fake_source",
                "canonical_path": str(source_txt),
                "derived_artifacts": [],
            }]
        }), encoding="utf-8")
        with pytest.raises(ValueError, match="no localizado"):
            ctx_mod.backfill(requirements_path, registry_path)

    def test_raises_when_source_id_unknown(self, tmp_path):
        requirements_path = tmp_path / "requirements.yaml"
        requirements_path.write_text(yaml.safe_dump({
            "requirements": {
                "FAKE_REQ": {
                    "source_id": "no_existe",
                    "citation": {"citation_text": "algo"},
                }
            }
        }), encoding="utf-8")
        registry_path = tmp_path / "registry.json"
        registry_path.write_text(json.dumps({"sources": []}), encoding="utf-8")
        with pytest.raises(ValueError, match="no existe en registry.json"):
            ctx_mod.backfill(requirements_path, registry_path)


CFR11_HUMAN_DRAFTED_REQ_IDS = {
    "21_CFR_11.10(a)", "21_CFR_11.10(d)", "21_CFR_11.10(e)", "21_CFR_11.10(g)",
    "21_CFR_11.50_11.70",
}
ANNEX11_HUMAN_DRAFTED_REQ_IDS = {
    "ANNEX11_4", "ANNEX11_7.1", "ANNEX11_9", "ANNEX11_12", "ANNEX11_17",
}
ALCOA_HUMAN_DRAFTED_REQ_IDS = {
    "ALCOA_ATTRIBUTABLE", "ALCOA_LEGIBLE", "ALCOA_CONTEMPORANEOUS",
    "ALCOA_ORIGINAL", "ALCOA_ACCURATE", "ALCOA_COMPLETE", "ALCOA_CONSISTENT",
    "ALCOA_ENDURING", "ALCOA_AVAILABLE",
}
#: G4 (2026-07-30): 21_CFR_211.68(b) sale de PENDING_HUMAN_INTERPRETATION_REQ_IDS
#: (conftest.py) con contenido interpretativo redactado -- mismo regimen que
#: el lote de Fase C, en su propio conjunto por venir de una ingesta posterior.
CGMP211_HUMAN_DRAFTED_REQ_IDS = {"21_CFR_211.68(b)"}
HUMAN_DRAFTED_REQ_IDS = (
    CFR11_HUMAN_DRAFTED_REQ_IDS | ANNEX11_HUMAN_DRAFTED_REQ_IDS | ALCOA_HUMAN_DRAFTED_REQ_IDS
    | CGMP211_HUMAN_DRAFTED_REQ_IDS
)
INTERPRETIVE_FIELDS = {
    "evidence_min_criteria", "exclusion_criteria", "weak_keywords",
    "typical_insufficient_evidence", "governed_interpretation",
    "expected_doc_types",
}


class TestRealCatalogHasMechanicalFieldsOnly:

    def test_all_19_requirements_validate_against_extended_schema(self):
        for rid, entry in _REAL_CATALOG["requirements"].items():
            full = {"requirement_id": rid, **entry}
            jsonschema.validate(full, _SCHEMA)

    def test_every_requirement_is_either_human_drafted_or_declared_pending(self):
        """Fase C completa (2026-07-23, aprobado por Cesar): los 19 requisitos
        originales (CFR11 5 + ANNEX11 5 + ALCOA 9) tienen interpretacion humana
        real. Un requisito solo puede escapar de eso estando declarado en
        PENDING_HUMAN_INTERPRETATION_REQ_IDS -- nunca en silencio.

        Esto es mas fuerte que el conteo que habia antes: cubre cualquier
        requisito futuro, no solo los 19 de entonces."""
        from tests.conftest import PENDING_HUMAN_INTERPRETATION_REQ_IDS
        ids = set(_REAL_CATALOG["requirements"].keys())
        assert HUMAN_DRAFTED_REQ_IDS <= ids, "desaparecio un requisito ya interpretado"
        no_declarados = ids - HUMAN_DRAFTED_REQ_IDS - PENDING_HUMAN_INTERPRETATION_REQ_IDS
        assert no_declarados == set(), (
            f"requisitos sin interpretacion humana y sin declarar: {no_declarados}"
        )
        for rid, entry in _REAL_CATALOG["requirements"].items():
            esperado = ("structure_only_pending_human_interpretation"
                        if rid in PENDING_HUMAN_INTERPRETATION_REQ_IDS
                        else "human_drafted_provisional")
            assert entry["evidence_pack_status"] == esperado, rid

    def test_human_drafted_batches_have_human_drafted_provisional_status(self):
        for rid in HUMAN_DRAFTED_REQ_IDS:
            entry = _REAL_CATALOG["requirements"][rid]
            assert entry["evidence_pack_status"] == "human_drafted_provisional", rid
            assert entry["content_review_status"] == "ACCEPTED_FOR_DRAFTING", rid
            assert entry["source_verification_status"] == "PENDING_REVERIFICATION", rid
            # Regla dura: fuente pendiente de reverificacion nunca habilita
            # liberacion/candidato limpio/produccion, sin importar el
            # contenido interpretativo redactado.
            assert entry["clean_candidate_eligibility"] == "BLOCKED", rid
            assert entry["release_eligibility"] == "BLOCKED", rid
            assert entry["production_eligibility"] == "BLOCKED", rid
            assert entry["ready_for_regulatory_use"] is False, rid

    def test_annex11_batch_does_not_use_part11_applicability_profile(self):
        """PART11_APPLICABILITY_V1 es exclusivo de CFR 11 -- ANNEX11 no debe
        referenciarlo, por instruccion explicita de Cesar."""
        for rid in ANNEX11_HUMAN_DRAFTED_REQ_IDS:
            entry = _REAL_CATALOG["requirements"][rid]
            assert "applicability_profile_ref" not in entry, rid

    def test_all_have_non_trivial_context(self):
        """Ninguno de los 19 debe haber quedado con contexto vacio -- si
        alguno quedara asi, seria una cita no localizada silenciosamente."""
        for rid, entry in _REAL_CATALOG["requirements"].items():
            assert entry["context_before"] or entry["context_after"], (
                f"{rid}: contexto vacio -- la cita no se localizo en el documento"
            )

    def test_human_drafted_batches_interpretive_fields_are_present_and_non_empty(self):
        """Reverso deliberado de la regla anterior para los lotes CFR 11 y
        ANNEX11: la interpretacion humana real de esta sesion (2026-07-23)
        SI debe estar presente y no vacia -- lo contrario seria perder
        silenciosamente el trabajo de redaccion aprobado."""
        for rid in HUMAN_DRAFTED_REQ_IDS:
            entry = _REAL_CATALOG["requirements"][rid]
            for field in INTERPRETIVE_FIELDS - {"expected_doc_types"}:
                assert entry.get(field), f"{rid}: {field} ausente o vacio"
            assert entry.get("expected_doc_types"), rid

    def test_human_drafted_batches_separate_documentary_and_implementation_evidence(self):
        for rid in HUMAN_DRAFTED_REQ_IDS:
            entry = _REAL_CATALOG["requirements"][rid]
            assert entry.get("documentary_evidence_expected"), rid
            assert entry.get("implementation_evidence_expected"), rid
            assert entry["documentary_evidence_expected"] != entry["implementation_evidence_expected"], rid

    def test_context_is_real_text_not_placeholder(self):
        """Verificacion puntual del caso ANNEX11_4 (el falso positivo
        semantico real de la corrida URS v2.1): el contexto real debe
        mostrar que la cita '4.1' vive dentro de un encabezado de seccion
        de Validacion, evidencia legible para juicio humano futuro."""
        entry = _REAL_CATALOG["requirements"]["ANNEX11_4"]
        assert "Validation" in entry["context_before"]


class TestAlcoaContentCorrections2026_07_23:
    """Las 5 correcciones regulatorias reales aplicadas tras la auditoria de
    2026-07-23 sobre el lote ALCOA. Cada test verifica el texto corregido
    Y falla explicitamente si el contenido regresara a la formulacion
    anterior (defectuosa) -- no solo verifica presencia superficial."""

    def test_attributable_distinguishes_human_from_automated_data(self):
        entry = _REAL_CATALOG["requirements"]["ALCOA_ATTRIBUTABLE"]
        text = entry["governed_interpretation"]
        assert "instrumento" in text or "sistema" in text, (
            "ALCOA_ATTRIBUTABLE debe permitir atribucion a instrumento/sistema "
            "para datos autogenerados, no solo identidad humana"
        )
        assert "automaticamente" in text or "autogenerado" in " ".join(
            entry["evidence_min_criteria"] + entry["exclusion_criteria"]
        ), "debe distinguir explicitamente el caso de dato autogenerado"
        criteria_text = " ".join(entry["exclusion_criteria"])
        assert "compartida" in criteria_text, (
            "la exclusion de cuentas humanas compartidas debe seguir vigente -- "
            "la correccion agrega el caso automatizado, no reemplaza el caso humano"
        )

    def test_contemporaneous_scribe_records_in_real_time(self):
        entry = _REAL_CATALOG["requirements"]["ALCOA_CONTEMPORANEOUS"]
        text = entry["governed_interpretation"]
        assert "escribiente" in text and "contrafirma" in text, (
            "debe distinguir explicitamente escribiente (contemporaneo) de "
            "contrafirma del ejecutor (unica pieza que puede ser retrospectiva)"
        )
        assert "no retrospectivo" in text or "no retrospectiva" in text, (
            "el registro del escribiente debe declararse explicitamente NO retrospectivo"
        )

    def test_contemporaneous_rejects_delay_documented_alone_as_sufficient(self):
        """Regresion directa contra la formulacion anterior: 'motivo y demora
        documentados, registro lo antes posible' aceptaba cualquier
        transcripcion tardia solo por estar documentada la demora."""
        entry = _REAL_CATALOG["requirements"]["ALCOA_CONTEMPORANEOUS"]
        exclusion_text = " ".join(entry["exclusion_criteria"])
        assert "unicamente porque la demora" in exclusion_text or (
            "solo porque la demora" in exclusion_text
        ), (
            "debe excluir explicitamente aceptar una transcripcion tardia "
            "solo porque la demora esta documentada"
        )
        # La formulacion anterior (defectuosa) aparecia en evidence_min_criteria
        # como una condicion suficiente aislada -- no debe volver a existir así.
        old_defective_min_criteria = [
            "Para excepciones reales, motivo y demora documentados, registro lo antes posible."
        ]
        assert entry["evidence_min_criteria"] != old_defective_min_criteria, (
            "evidence_min_criteria no debe reducirse otra vez a la formulacion "
            "que aceptaba demora documentada como condicion suficiente aislada"
        )

    def test_accurate_scopes_all_forms_to_evaluated_process(self):
        """Regresion directa: 'cubre todas las formas en que el dato existe'
        (sin acotar) generaba gaps falsos para soportes fuera de alcance."""
        entry = _REAL_CATALOG["requirements"]["ALCOA_ACCURATE"]
        criteria_text = " ".join(entry["evidence_min_criteria"])
        assert "todas las formas en que el dato existe" not in criteria_text, (
            "la formulacion sin acotar a proceso/alcance evaluado no debe reaparecer"
        )
        assert "proceso y alcance evaluados" in criteria_text, (
            "debe acotar explicitamente 'todas las formas' al proceso y alcance evaluados"
        )

    def test_complete_conditions_oos_on_applicability(self):
        """Regresion directa: exigir OOS sin condicion de aplicabilidad genera
        falso gap en procesos donde OOS no es un concepto aplicable."""
        entry = _REAL_CATALOG["requirements"]["ALCOA_COMPLETE"]
        full_text = entry["governed_interpretation"] + " ".join(
            entry["evidence_min_criteria"] + entry["exclusion_criteria"]
        )
        assert "OOS" in full_text, "debe mencionar explicitamente el tratamiento condicional de OOS"
        assert "aplicable" in full_text or "aplique" in full_text, (
            "el tratamiento de OOS debe estar condicionado a su aplicabilidad al proceso evaluado"
        )
        assert any("falso gap" in c for c in entry["exclusion_criteria"]), (
            "debe excluir explicitamente exigir OOS en un proceso donde no aplica"
        )

    def test_available_replaces_ambiguous_reasonable_timeframe(self):
        """Regresion directa: 'en plazo razonable' es la frase ambigua que
        la correccion reemplaza por el estandar 'sin demora indebida,
        directamente accesible ... y en forma legible'."""
        entry = _REAL_CATALOG["requirements"]["ALCOA_AVAILABLE"]
        full_text = " ".join(
            [entry["governed_interpretation"]]
            + entry["evidence_min_criteria"]
            + entry["exclusion_criteria"]
            + entry["implementation_evidence_expected"]
        )
        assert "plazo razonable" not in full_text, (
            "la frase ambigua 'plazo razonable' no debe reaparecer en ningun campo"
        )
        assert "sin demora indebida" in full_text, "debe usar el estandar acordado"
        assert "directamente accesible" in full_text, "debe usar el estandar acordado"
        assert "forma legible" in full_text, "debe usar el estandar acordado"

    def test_consistent_accepts_human_or_technical_equivalent_controls(self):
        """Aclaracion explicita: la deteccion de inconsistencias no debe
        exigir exclusivamente un control automatizado."""
        entry = _REAL_CATALOG["requirements"]["ALCOA_CONSISTENT"]
        full_text = entry["governed_interpretation"] + " ".join(entry["evidence_min_criteria"])
        assert "humano" in full_text or "humanos" in full_text, (
            "debe aclarar explicitamente que un control humano es aceptable"
        )
        assert "gobernado" in full_text or "gobernados" in full_text, (
            "el control humano/tecnico/equivalente debe estar sujeto a gobierno explicito"
        )

    def test_no_duplicated_structural_fields_added(self):
        """Regla dura de esta correccion (instruccion explicita de Cesar):
        no agregar canonical_text/supporting_citations/source_scope/
        source_applicability_caveats -- esos campos no existen en el schema
        y no deben aparecer en ningun requisito."""
        forbidden_fields = {
            "canonical_text", "supporting_citations",
            "source_scope", "source_applicability_caveats",
        }
        for rid, entry in _REAL_CATALOG["requirements"].items():
            present = forbidden_fields & set(entry.keys())
            assert not present, f"{rid}: campos estructurales no autorizados presentes: {present}"
        assert not (forbidden_fields & set(_SCHEMA["properties"].keys())), (
            "el schema no debe declarar estos campos sin una decision arquitectonica separada"
        )
