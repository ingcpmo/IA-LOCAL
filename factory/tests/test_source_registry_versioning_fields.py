"""
Tests -- W5 V2 Fase B: campos de versionado (version, effective_date,
supersedes, reverification_due) agregados a
factory/regulatory/schemas/source_registry_entry_v1.json y respaldados por
factory/regulatory/tools/backfill_source_registry_versioning_fields.py.

Cubre: el schema exige los 4 campos nuevos (rechaza una entrada sin
alguno); las 3 fuentes reales YA gobernadas en registry.json validan
contra el schema extendido; los valores citados literalmente del propio
texto gobernado no se degradan silenciosamente (regresión); el backfill
rechaza source_id sin mapeo evidenciado en vez de escribir un valor
inventado.
"""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import jsonschema
import pytest

from factory.regulatory.tools import backfill_source_registry_versioning_fields as backfill_mod

_SCHEMA = json.loads(
    Path("factory/regulatory/schemas/source_registry_entry_v1.json").read_text()
)
_REGISTRY = json.loads(Path("factory/regulatory/sources/registry.json").read_text())


def _valid_entry() -> dict:
    return {
        "source_id": "fake_source",
        "canonical_path": "factory/regulatory/sources/sha256/aa/fake.pdf",
        "official_source_url": "https://example.org/fake.pdf",
        "official_source_description": "fake",
        "sha256_original": "a" * 64,
        "sha256_copy": "a" * 64,
        "hashes_match": True,
        "size_bytes": 10,
        "normative_type": "regulation",
        "jurisdiction": "US",
        "local_integrity_status": "PASS",
        "official_origin_status": "VERIFIED",
        "regulatory_currency_status": "pending_reverification",
        "version": "1.0",
        "effective_date": "2020-01-01",
        "supersedes": None,
        "reverification_due": None,
    }


class TestSchemaRequiresVersioningFields:

    @pytest.mark.parametrize(
        "missing_field", ["version", "effective_date", "supersedes", "reverification_due"]
    )
    def test_rejects_entry_missing_new_required_field(self, missing_field):
        entry = _valid_entry()
        del entry[missing_field]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(entry, _SCHEMA)

    def test_accepts_fully_populated_entry(self):
        jsonschema.validate(_valid_entry(), _SCHEMA)

    def test_null_supersedes_and_reverification_due_are_valid(self):
        entry = _valid_entry()
        entry["supersedes"] = "some_other_source_id"
        entry["reverification_due"] = "2027-01-01"
        jsonschema.validate(entry, _SCHEMA)

    def test_rejects_additional_unknown_property(self):
        entry = _valid_entry()
        entry["unexpected_field"] = "x"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(entry, _SCHEMA)


class TestRealRegistryValidatesAgainstExtendedSchema:

    def test_all_three_real_sources_validate(self):
        for source in _REGISTRY["sources"]:
            jsonschema.validate(source, _SCHEMA)

    def test_annex11_version_and_effective_date_match_document_citation(self):
        """Cita literal verificada en el propio PDF gobernado: 'Status of
        the document: revision 1' + 'Deadline for coming into operation:
        30 June 2011' (ver derived_artifacts del mismo source_id)."""
        entry = next(s for s in _REGISTRY["sources"] if s["source_id"] == "eu_gmp_annex11")
        assert entry["version"] == "revision 1"
        assert entry["effective_date"] == "2011-06-30"

    def test_mhra_version_and_effective_date_match_document_citation(self):
        """Cita literal: 'MHRA GXP Data Integrity Guidance and
        Definitions; Revision 1: March 2018' -- solo mes/anio declarado,
        nunca se inventa un dia."""
        entry = next(
            s for s in _REGISTRY["sources"] if s["source_id"] == "mhra_gxp_di_guidance_2018"
        )
        assert entry["version"] == "Revision 1"
        assert entry["effective_date"] == "2018-03"

    def test_ecfr_declares_no_discrete_version_honestly(self):
        """eCFR es texto consolidado sin edicion discreta -- el valor debe
        decir explicitamente por que no hay dato, nunca fingir uno."""
        entry = next(s for s in _REGISTRY["sources"] if s["source_id"] == "ecfr_21cfr_part11")
        assert entry["version"].startswith("NO_DISPONIBLE")
        assert entry["effective_date"].startswith("NO_DISPONIBLE")

    def test_no_source_supersedes_another_yet(self):
        assert all(s["supersedes"] is None for s in _REGISTRY["sources"])

    def test_reverification_due_is_null_pending_cadence_policy(self):
        """No existe todavia una politica de cadencia aprobada por Capa 9
        -- null es el valor honesto, no una fecha inventada."""
        assert all(s["reverification_due"] is None for s in _REGISTRY["sources"])


class TestBackfillScript:

    def test_backfill_is_idempotent(self, tmp_path):
        registry_copy = tmp_path / "registry.json"
        registry_copy.write_text(json.dumps(copy.deepcopy(_REGISTRY)), encoding="utf-8")
        result1 = backfill_mod.backfill(registry_copy)
        registry_copy.write_text(json.dumps(result1), encoding="utf-8")
        result2 = backfill_mod.backfill(registry_copy)
        assert result1 == result2

    def test_raises_on_source_id_without_backfill_mapping(self, tmp_path):
        data = copy.deepcopy(_REGISTRY)
        data["sources"].append({"source_id": "unmapped_new_source"})
        registry_copy = tmp_path / "registry.json"
        registry_copy.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="sin entrada de backfill"):
            backfill_mod.backfill(registry_copy)

    def test_raises_if_registry_missing_a_mapped_source(self, tmp_path):
        data = copy.deepcopy(_REGISTRY)
        data["sources"] = [s for s in data["sources"] if s["source_id"] != "eu_gmp_annex11"]
        registry_copy = tmp_path / "registry.json"
        registry_copy.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="sin mapeo"):
            backfill_mod.backfill(registry_copy)
