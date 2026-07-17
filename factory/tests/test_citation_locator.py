"""W5 Ciclo 1 (v2), Fase 5.1 (W5.3), control #3 -- tests del localizador de
citas (mecanismo, no el catalogo definitivo)."""
from __future__ import annotations

from pathlib import Path

from factory.regulatory.requirement_catalog.citation_locator import locate_citation, sha256_file


def test_locate_citation_exact_match_in_plain_text(tmp_path):
    src = tmp_path / "source.txt"
    src.write_text("Linea uno.\nLimiting system access to authorized individuals.\nLinea tres.", encoding="utf-8")
    result = locate_citation("c1", "Limiting system access to authorized individuals.", src)
    assert result.match_type == "exact"
    assert result.verified is True
    assert result.page_found == 1  # texto plano = 1 sola "pagina"


def test_locate_citation_not_found_reports_unverified(tmp_path):
    src = tmp_path / "source.txt"
    src.write_text("Contenido totalmente distinto sin relacion alguna.", encoding="utf-8")
    result = locate_citation("c2", "Una cita que no existe en absoluto en este archivo.", src)
    assert result.match_type == "not_found"
    assert result.verified is False


def test_locate_citation_reports_correct_page_for_multi_page_source(tmp_path, monkeypatch):
    import factory.regulatory.requirement_catalog.citation_locator as mod

    def _fake_pages(path):
        return ["pagina uno sin la cita", "pagina dos con la cita real aqui", "pagina tres"]

    monkeypatch.setattr(mod, "_extract_text_pages", _fake_pages)
    result = locate_citation("c3", "con la cita real aqui", tmp_path / "irrelevant.pdf")
    assert result.verified is True
    assert result.page_found == 2


def test_sha256_file_is_deterministic(tmp_path):
    src = tmp_path / "f.txt"
    src.write_text("contenido estable", encoding="utf-8")
    assert sha256_file(src) == sha256_file(src)
