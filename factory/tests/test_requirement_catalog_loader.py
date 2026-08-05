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
    """Invariante, no conteo. El numero de fuentes cambia cuando Capa 9 aprueba
    un alta (2026-07-29: ecfr_21cfr_part211); lo que NO puede cambiar sin
    decision es que toda fuente cargue integra. El conjunto exacto se fija a
    proposito en
    test_human_source_registration.test_real_registry_has_no_unauthorized_source.

    `regulatory_currency_status` ya NO se fija a un unico valor aqui (ver
    test_every_verified_current_source_has_a_real_backing_decision): desde
    SOURCE_CURRENCY (2026-08-05) puede ser 'verified_current' -- pero SOLO
    via una decision real, nunca por defecto."""
    registry = load_source_registry()
    assert registry["sources"], "el registry nunca queda vacio"
    for entry in registry["sources"]:
        assert entry["regulatory_currency_status"] in ("pending_reverification", "verified_current")
        assert entry["hashes_match"] is True
        assert entry["local_integrity_status"] == "PASS"


def test_every_verified_current_source_has_a_real_backing_decision():
    """Control explicito del usuario, ACTUALIZADO (2026-08-05): antes decia
    "ninguna fuente puede presentarse como vigente-verificada en este
    ciclo" -- una restriccion absoluta porque no existia NINGUN mecanismo
    gobernado para declarar vigencia. Ese mecanismo ahora existe
    (factory.regulatory.source_currency_confirmation, familia
    SOURCE_CURRENCY): propose deriva la evidencia real del log, confirm
    exige firma humana, y apply re-verifica al momento de escribir. La
    restriccion que SI se conserva, y es la que de verdad importa: ninguna
    fuente puede ser 'verified_current' SIN una decision human_confirmed
    real que lo respalde -- nunca por defecto, nunca a mano."""
    from factory.services import decision_store_v2 as store

    registry = load_source_registry()
    verificadas = [e["source_id"] for e in registry["sources"]
                  if e["regulatory_currency_status"] == "verified_current"]
    if not verificadas:
        pytest.skip("ninguna fuente verified_current hoy -- nada que verificar")

    registros = store.read_all()
    confirmadas = {
        r["payload"]["source_id"]
        for r in registros
        if r.get("decision_family") == "SOURCE_CURRENCY"
        and r.get("decision_origin") == "human_confirmed"
        and r.get("decision") == "APPROVE"
    }
    for sid in verificadas:
        assert sid in confirmadas, (
            f"{sid} es verified_current pero no hay ninguna decision SOURCE_CURRENCY "
            "human_confirmed que lo respalde -- estado fabricado, no gobernado")


def test_requirements_catalog_keeps_all_original_ids():
    """Los 19 originales no pueden desaparecer. El catalogo SI puede crecer
    (2026-07-29: 21_CFR_211.68(b)), asi que se afirma inclusion, no igualdad."""
    catalog = load_requirements()
    assert ALL_19_REQ_IDS <= set(catalog["requirements"].keys())


def test_every_requirement_is_covered_with_verified_citations():
    """Invariante: ninguna entrada queda en review_required. Vale para 19 o
    para 200 -- lo que no puede pasar es que una cita no ancle."""
    summary = validate_all()
    assert summary.total == len(load_requirements()["requirements"])
    assert summary.covered == summary.total
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


# ===========================================================================
# G1.8 -- elegibilidad de uso de un Evidence Pack (consumidor C-2)
# ===========================================================================

REQ = "21_CFR_11.10(a)"
SRC = "ecfr_21cfr_part11"


def _store(tmp_path, *records):
    import json as _json
    path = tmp_path / "decisions_v2.jsonl"
    path.write_text(
        "".join(_json.dumps(r, ensure_ascii=False) + "\n" for r in records),
        encoding="utf-8")
    return path


def _decision(family, targets, instance_id):
    from factory.services import decision_store_v2 as store
    return store.build_record(
        decision_family=family, decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", resolved_target_ids=list(targets),
        decision="APPROVE", decision_origin="human_confirmed",
        approved_by_id="Cesar", approved_by_display_name="Cesar",
        decision_instance_id=instance_id)


def test_loading_the_catalog_never_depends_on_decisions(tmp_path):
    """Cargar y estar autorizado son cosas distintas. Si `load_requirements()`
    dependiera del almacén de decisiones, faltar una firma rompería toda
    lectura -- informes, diagnóstico y la propia UI de gobernanza."""
    catalog = mod.load_requirements()
    assert len(catalog["requirements"]) >= 20
    src = Path(mod.__file__).read_text(encoding="utf-8")
    load_fn = src.split("def load_requirements(", 1)[1].split("\ndef ", 1)[0]
    assert "_resolver" not in load_fn


def test_pack_use_requires_BOTH_pack_and_source_coverage(tmp_path):
    """Un pack impecable sobre una fuente no autorizada no es utilizable."""
    solo_pack = _store(tmp_path, _decision("D2", [REQ], "D2-2026-001"))
    e = mod.evaluate_pack_eligibility(REQ, decision_store_file=solo_pack)
    assert e.pack_decision_authorized is True
    assert e.source_decision_authorized is False
    assert e.pack_use_allowed is False
    assert any("D1/" in r for r in e.denial_reasons)


def test_pack_use_allowed_when_both_are_signed(tmp_path):
    both = _store(tmp_path,
                  _decision("D2", [REQ], "D2-2026-001"),
                  _decision("D1", [SRC], "D1-2026-001"))
    e = mod.evaluate_pack_eligibility(REQ, decision_store_file=both)
    assert e.pack_use_allowed is True
    assert e.formal_conclusion_allowed is True
    assert set(e.covering_decisions) == {"D2-2026-001", "D1-2026-001"}
    assert e.denial_reasons == ()


def test_pack_eligibility_is_denied_not_raised(tmp_path):
    """Un requisito no autorizado debe salir NO EVALUADO del pipeline, nunca
    incumplido -- para eso el llamador necesita el motivo, no una excepción."""
    empty = _store(tmp_path)
    e = mod.evaluate_pack_eligibility(REQ, decision_store_file=empty)
    assert e.pack_use_allowed is False
    assert len(e.denial_reasons) == 2


def test_unknown_requirement_still_raises(tmp_path):
    """Eso SÍ es un error de programación, no una denegación de gobernanza."""
    with pytest.raises(CatalogValidationError):
        mod.evaluate_pack_eligibility("NO_EXISTE", decision_store_file=_store(tmp_path))


def test_eligible_requirement_ids_is_empty_without_decisions(tmp_path):
    """Estado REAL de hoy: ningún requisito es utilizable todavía."""
    assert mod.eligible_requirement_ids(decision_store_file=_store(tmp_path)) == []


def test_eligible_requirement_ids_lists_only_the_signed_ones(tmp_path):
    both = _store(tmp_path,
                  _decision("D2", [REQ], "D2-2026-001"),
                  _decision("D1", [SRC], "D1-2026-001"))
    assert mod.eligible_requirement_ids(decision_store_file=both) == [REQ]


def test_part211_pack_is_not_eligible_even_if_its_pack_were_signed(tmp_path):
    """El caso real: firmar el pack de 21_CFR_211.68(b) no basta mientras
    ecfr_21cfr_part211 siga sin cobertura D1."""
    solo_pack = _store(tmp_path, _decision("D2", ["21_CFR_211.68(b)"], "D2-2026-001"))
    e = mod.evaluate_pack_eligibility("21_CFR_211.68(b)", decision_store_file=solo_pack)
    assert e.source_id == "ecfr_21cfr_part211"
    assert e.pack_use_allowed is False
