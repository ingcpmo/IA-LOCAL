"""
Tests -- W5 V2 Fase C: campos mecánicos del Requirement Evidence Pack
(context_before, context_after, pack_version, evidence_pack_status)
agregados a requirement_catalog_entry_v1.json y respaldados por
factory/regulatory/tools/build_requirement_evidence_pack_context.py.

Alcance de esta fase (decisión explícita de Capa 9, 2026-07-23): SOLO los
campos mecánicos se generan aquí. Los campos interpretativos
(evidence_min_criteria, exclusion_criteria, weak_keywords,
typical_insufficient_evidence, governed_interpretation,
expected_doc_types) requieren juicio regulatorio humano y deben quedar
ausentes -- estas pruebas verifican precisamente que NO se inventen.
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


class TestRealCatalogHasMechanicalFieldsOnly:

    def test_all_19_requirements_validate_against_extended_schema(self):
        for rid, entry in _REAL_CATALOG["requirements"].items():
            full = {"requirement_id": rid, **entry}
            jsonschema.validate(full, _SCHEMA)

    def test_all_have_evidence_pack_status_pending_human_interpretation(self):
        for entry in _REAL_CATALOG["requirements"].values():
            assert entry["evidence_pack_status"] == "structure_only_pending_human_interpretation"

    def test_all_have_non_trivial_context(self):
        """Ninguno de los 19 debe haber quedado con contexto vacio -- si
        alguno quedara asi, seria una cita no localizada silenciosamente."""
        for rid, entry in _REAL_CATALOG["requirements"].items():
            assert entry["context_before"] or entry["context_after"], (
                f"{rid}: contexto vacio -- la cita no se localizo en el documento"
            )

    def test_interpretive_fields_are_absent_not_fabricated(self):
        """Regla dura de esta fase: evidence_min_criteria, exclusion_criteria,
        weak_keywords, typical_insufficient_evidence, governed_interpretation
        y expected_doc_types NUNCA deben aparecer todavia -- si aparecen,
        alguien los genero sin la interpretacion humana requerida."""
        interpretive_fields = {
            "evidence_min_criteria", "exclusion_criteria", "weak_keywords",
            "typical_insufficient_evidence", "governed_interpretation",
            "expected_doc_types",
        }
        for rid, entry in _REAL_CATALOG["requirements"].items():
            present = interpretive_fields & set(entry.keys())
            assert not present, f"{rid}: campos interpretativos presentes sin aprobacion humana: {present}"

    def test_context_is_real_text_not_placeholder(self):
        """Verificacion puntual del caso ANNEX11_4 (el falso positivo
        semantico real de la corrida URS v2.1): el contexto real debe
        mostrar que la cita '4.1' vive dentro de un encabezado de seccion
        de Validacion, evidencia legible para juicio humano futuro."""
        entry = _REAL_CATALOG["requirements"]["ANNEX11_4"]
        assert "Validation" in entry["context_before"]
