"""
Tests — factory/regulatory/regulatory_catalog.py es un adaptador de
nombres sobre el catalogo canonico (requirement_catalog_loader.py), NUNCA
una segunda fuente de verdad. Verifica que las 19 entradas coinciden
EXACTAMENTE (mismo dict, mismo hash) entre ambos modulos.
"""

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from factory.regulatory import regulatory_catalog as catalog
from factory.regulatory.requirement_catalog import requirement_catalog_loader as canonical

EXPECTED_ENTRY_COUNT = 19


def test_catalog_has_exactly_19_entries():
    assert len(catalog.known_entry_ids()) == EXPECTED_ENTRY_COUNT


def test_alcoa_contemporaneous_present():
    assert "ALCOA_CONTEMPORANEOUS" in catalog.known_entry_ids()


@pytest.mark.parametrize("requirement_id", sorted(catalog.known_entry_ids()))
def test_wrapper_returns_exactly_the_canonical_entry_no_divergence(requirement_id):
    """El adaptador NUNCA copia/deriva -- devuelve el mismo objeto que el
    catalogo canonico, campo por campo."""
    wrapped = catalog.get_catalog_entry(requirement_id)
    real = canonical.get_requirement(requirement_id)
    assert wrapped == real


@pytest.mark.parametrize("requirement_id", sorted(catalog.known_entry_ids()))
def test_citation_sha256_consistency_for_every_entry(requirement_id):
    """Para las 19 entradas: citation_sha256 declarado == sha256(citation_text)
    recalculado -- mismo criterio fail-closed que requirement_catalog_loader
    ya aplica al cargar, verificado aqui de forma independiente."""
    entry = catalog.get_catalog_entry(requirement_id)
    citation = entry["citation"]
    recomputed = hashlib.sha256(citation["citation_text"].encode("utf-8")).hexdigest()
    assert recomputed == citation["citation_sha256"], (
        f"{requirement_id}: citation_sha256 declarado no coincide con el texto real")


def test_unknown_entry_id_raises():
    with pytest.raises(catalog.RegulatoryCatalogError):
        catalog.get_catalog_entry("NO_EXISTE_EN_EL_CATALOGO")
