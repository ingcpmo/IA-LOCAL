"""Tests -- factory/regulatory/requirement_catalog/requirement_decomposition_loader.py
(V2, B3).

docs_plan/PLAN_IMPLEMENTACION_ANALIZADOR_GMP_LOCAL_V2.md B3 + FASE 4.1:
decomposition.yaml es contenido gobernado, hermano de requirements.yaml.
Todo requisito con descomposición no vacía; cada sub-criterio es texto,
no una referencia; coherente con el catálogo; fail-closed.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.requirement_catalog import requirement_decomposition_loader as dl
from factory.regulatory.requirement_catalog.requirement_catalog_loader import load_requirements


def test_loads_and_validates():
    data = dl.load_decomposition()
    assert data["decomposition_version"] == "1.1"
    assert data["signed_by"].startswith("Capa 9")
    assert data.get("bilingual") is True


def test_every_subcriterion_is_bilingual():
    """v1.1: cada sub-criterio tiene text (ES, autoritativo) + text_en
    (glosa EN, aid de recuperación cross-idioma)."""
    for rid in dl.load_decomposition()["requirements"]:
        for sc in dl.get_subcriteria(rid):
            assert sc.get("text_en", "").strip(), f"{rid}::{sc['id']} sin text_en"
            # el aid combina ambos idiomas
            m = dl.subcriterion_match_text(sc)
            assert sc["text"] in m and sc["text_en"] in m


def test_full_coverage_of_catalog():
    """Todo requisito del catálogo tiene descomposición (fail-closed en V2)."""
    catalog_ids = set(load_requirements()["requirements"])
    decomp_ids = set(dl.load_decomposition()["requirements"])
    assert catalog_ids == decomp_ids, f"faltan: {catalog_ids - decomp_ids}"


def test_declared_total_matches_real():
    data = dl.load_decomposition()
    real = sum(len(b["subcriteria"]) for b in data["requirements"].values())
    assert data["total_subcriteria"] == real == 84


def test_every_subcriterion_has_id_and_text():
    for rid in dl.load_decomposition()["requirements"]:
        subs = dl.get_subcriteria(rid)
        ids = [s["id"] for s in subs]
        assert len(ids) == len(set(ids)), f"{rid}: ids duplicados"
        for s in subs:
            assert s["id"]
            assert len(s["text"].strip()) > 10
            # el texto es una afirmación, no un id ni una referencia cruda
            assert not s["text"].strip().startswith(("sc", "evidence_min_criteria"))


def test_subcriteria_derive_from_catalog_fields():
    """`derived_from` referencia citation_text / evidence_min_criteria del
    propio requisito -- trazabilidad de autoría verificable."""
    for rid, block in dl.load_decomposition()["requirements"].items():
        for sc in block["subcriteria"]:
            df = sc.get("derived_from", [])
            assert df, f"{rid}::{sc['id']} sin derived_from"
            assert all(("evidence_min_criteria" in d or "citation_text" in d) for d in df)


def test_annex11_4_has_guard_note_and_three_substantive_subcriteria():
    """El negativo obligatorio N1: sus 3 sub-criterios exigen sustancia
    (documentación/evaluación/conexión), no la mención de un nombre."""
    subs = dl.get_subcriteria("ANNEX11_4")
    assert len(subs) == 3
    joined = " ".join(s["text"].lower() for s in subs)
    assert "documentación de validación" in joined
    assert "evaluación de riesgo" in joined
    assert "conexión explícita y trazable" in joined


def test_get_subcriteria_fail_closed_on_unknown():
    with pytest.raises(dl.DecompositionError):
        dl.get_subcriteria("NO_EXISTE")


def test_require_full_coverage():
    all_ids = list(load_requirements()["requirements"])
    dl.require_full_coverage(all_ids)              # no lanza
    with pytest.raises(dl.DecompositionError):
        dl.require_full_coverage(all_ids + ["FANTASMA"])


def test_subcriterion_ref_format():
    assert dl.subcriterion_ref("21_CFR_11.10(e)", "sc2") == "21_CFR_11.10(e)::sc2"
    refs = dl.all_subcriteria_refs()
    assert len(refs) == 84
    assert "21_CFR_11.10(e)::sc2" in refs
