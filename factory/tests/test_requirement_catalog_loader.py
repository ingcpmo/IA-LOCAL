"""W5.3 Fase 5.2 -- tests del catalogo atomico de requisitos + validacion
cruzada fail-closed contra el source_registry."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from factory.regulatory.requirement_catalog import requirement_catalog_loader as mod
from factory.regulatory.requirement_catalog.requirement_catalog_loader import (
    CatalogValidationError, get_requirement, get_source, load_requirements,
    load_source_registry, validate_all,
)

ALL_19_REQ_IDS = {
    "21_CFR_11.10(a)", "21_CFR_11.10(d)", "21_CFR_11.10(e)", "21_CFR_11.10(g)",
    "21_CFR_11.50_11.70", "ANNEX11_4", "ANNEX11_7.1", "ANNEX11_9", "ANNEX11_12",
    "ANNEX11_17", "ALCOA_ATTRIBUTABLE", "ALCOA_LEGIBLE", "ALCOA_CONTEMPORANEOUS",
    "ALCOA_ORIGINAL", "ALCOA_ACCURATE", "ALCOA_COMPLETE", "ALCOA_CONSISTENT",
    "ALCOA_ENDURING", "ALCOA_AVAILABLE",
}


def test_source_registry_loads_and_validates():
    registry = load_source_registry()
    assert len(registry["sources"]) == 3
    for entry in registry["sources"]:
        assert entry["regulatory_currency_status"] == "pending_reverification"
        assert entry["hashes_match"] is True
        assert entry["local_integrity_status"] == "PASS"


def test_no_source_declares_itself_verified_current():
    """Control explicito del usuario: ninguna fuente puede presentarse como
    vigente-verificada en este ciclo."""
    registry = load_source_registry()
    for entry in registry["sources"]:
        assert entry["regulatory_currency_status"] == "pending_reverification"
        assert "verified_current" not in str(entry.get("regulatory_currency_status", ""))
        assert "current" != entry["regulatory_currency_status"]


def test_requirements_catalog_has_all_19_ids():
    catalog = load_requirements()
    assert set(catalog["requirements"].keys()) == ALL_19_REQ_IDS


def test_all_19_requirements_are_covered_with_verified_citations():
    summary = validate_all()
    assert summary.total == 19
    assert summary.covered == 19
    assert summary.review_required == 0


def test_every_requirement_has_all_required_fields():
    catalog = load_requirements()
    for req_id, entry in catalog["requirements"].items():
        assert entry["source_id"], req_id
        c = entry["citation"]
        assert c["citation_text"], req_id
        assert c["match_type"] in ("exact", "normalized", "fuzzy", "not_found")
        assert c["section_page_paragraph"], req_id
        assert len(c["citation_sha256"]) == 64
        assert entry["normative_type"] in ("regulation", "official_guidance", "internal_interpretation")
        assert entry["jurisdiction"]
        assert entry["binding_status"]
        assert entry["review_status"] in ("covered", "review_required")


def test_every_covered_requirement_source_id_resolves_in_registry():
    catalog = load_requirements()
    known_ids = {e["source_id"] for e in load_source_registry()["sources"]}
    for req_id, entry in catalog["requirements"].items():
        if entry["review_status"] == "covered":
            assert entry["source_id"] in known_ids, req_id


def test_pdf_sources_have_derived_pdfplumber_artifacts():
    registry = load_source_registry()
    for entry in registry["sources"]:
        if entry["canonical_path"].endswith(".pdf"):
            assert len(entry["derived_artifacts"]) >= 1, entry["source_id"]
            for artifact in entry["derived_artifacts"]:
                assert artifact["extractor"] == "pdfplumber"
                assert artifact["source_sha256"] == entry["sha256_copy"]


def test_get_requirement_unknown_id_raises_not_none():
    with pytest.raises(CatalogValidationError):
        get_requirement("NOT_A_REAL_REQUIREMENT_ID")


def test_get_source_unknown_id_raises_not_none():
    with pytest.raises(CatalogValidationError):
        get_source("not_a_real_source")


def test_covered_without_valid_citation_and_source_is_rejected(tmp_path, monkeypatch):
    """Fail-closed central: review_status='covered' declarado sin que
    source_resolves Y citation_anchored sean ambos verdaderos debe
    detener la carga completa, nunca colarse."""
    bad_catalog = {
        "catalog_version": "1.0",
        "requirements": {
            "FAKE_REQ": {
                "label": "Requisito de prueba invalido",
                "source_id": "no_such_source",
                "citation": {
                    "citation_id": "c1", "citation_text": "algo real",
                    "match_type": "not_found", "match_score": 0.1,
                    "section_page_paragraph": "p1",
                    "citation_sha256": mod._sha256_text("algo real"),
                },
                "normative_type": "regulation", "jurisdiction": "US",
                "binding_status": "binding_regulation", "review_status": "covered",
                "pack_version": "1.0", "context_before": "", "context_after": "",
                "evidence_pack_status": "structure_only_pending_human_interpretation",
            }
        },
    }
    tmp = tmp_path / "bad_requirements.yaml"
    tmp.write_text(yaml.dump(bad_catalog), encoding="utf-8")
    monkeypatch.setattr(mod, "REQUIREMENTS_PATH", tmp)
    mod.load_requirements.cache_clear()
    try:
        with pytest.raises(CatalogValidationError, match="covered.*nunca se declara"):
            mod.load_requirements()
    finally:
        mod.load_requirements.cache_clear()


def test_tampered_citation_sha256_is_rejected(tmp_path, monkeypatch):
    """citation_sha256 debe coincidir con sha256(citation_text) recalculado
    -- si alguien edita citation_text sin recalcular el hash, la carga
    debe fallar, no confiar en el valor declarado."""
    tampered_catalog = {
        "catalog_version": "1.0",
        "requirements": {
            "21_CFR_11.10(d)": {
                "label": "Limitar acceso a individuos autorizados",
                "source_id": "ecfr_21cfr_part11",
                "citation": {
                    "citation_id": "c1", "citation_text": "Texto modificado sin recalcular el hash.",
                    "match_type": "exact", "match_score": 1.0,
                    "section_page_paragraph": "§ 11.10(d)",
                    "citation_sha256": mod._sha256_text("Texto ORIGINAL, distinto."),
                },
                "normative_type": "regulation", "jurisdiction": "US",
                "binding_status": "binding_regulation", "review_status": "covered",
                "pack_version": "1.0", "context_before": "", "context_after": "",
                "evidence_pack_status": "structure_only_pending_human_interpretation",
            }
        },
    }
    tmp = tmp_path / "tampered_requirements.yaml"
    tmp.write_text(yaml.dump(tampered_catalog), encoding="utf-8")
    monkeypatch.setattr(mod, "REQUIREMENTS_PATH", tmp)
    mod.load_requirements.cache_clear()
    try:
        with pytest.raises(CatalogValidationError, match="citation_sha256"):
            mod.load_requirements()
    finally:
        mod.load_requirements.cache_clear()


def test_derived_artifact_source_sha256_mismatch_is_rejected(tmp_path, monkeypatch):
    bad_registry = {
        "registry_version": "1.1",
        "sources": [{
            "source_id": "source_one",
            "canonical_path": "factory/regulatory/sources/sha256/aa/file.pdf",
            "official_source_url": "https://example.org",
            "official_source_description": "desc",
            "sha256_original": "a" * 64,
            "sha256_copy": "a" * 64,
            "hashes_match": True,
            "size_bytes": 10,
            "normative_type": "regulation",
            "jurisdiction": "US",
            "local_integrity_status": "PASS",
            "official_origin_status": "some real status text",
            "regulatory_currency_status": "pending_reverification",
            "version": "1.0",
            "effective_date": "2020-01-01",
            "supersedes": None,
            "reverification_due": None,
            "derived_artifacts": [{
                "extractor": "pdfplumber", "extractor_version": "0.11.10",
                "source_sha256": "b" * 64,  # NO coincide con sha256_copy
                "artifact_path": "x", "artifact_sha256": "c" * 64,
            }],
        }],
    }
    import json
    tmp = tmp_path / "bad_registry.json"
    tmp.write_text(json.dumps(bad_registry), encoding="utf-8")
    monkeypatch.setattr(mod, "REGISTRY_PATH", tmp)
    mod.load_source_registry.cache_clear()
    try:
        with pytest.raises(CatalogValidationError, match="source_sha256"):
            mod.load_source_registry()
    finally:
        mod.load_source_registry.cache_clear()
