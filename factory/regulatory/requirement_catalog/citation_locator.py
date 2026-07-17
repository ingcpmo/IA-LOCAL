"""W5 Ciclo 1 (v2), Fase 5.1 (W5.3), control #3 -- localizador de citas.

Verifica MECANICAMENTE que un citation_text propuesto existe literalmente
dentro de un archivo fuente real, antes de aceptarlo en el inventario o
(en Fase 5.2) en el catalogo definitivo. Reutiliza la MISMA taxonomia de
coincidencia que factory/regulatory/evidence_verifier.py (exact/normalized/
fuzzy/not_found) -- una cita de catalogo debe cumplir el mismo estandar que
una cita de un finding: no hay un segundo rasero mas laxo para "nuestras
propias" citas.

Extraccion de texto: PDF via pypdf (misma libreria ya usada en el motor,
sin agregar dependencia nueva), texto plano via lectura directa."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from factory.regulatory.evidence_verifier import match_citation


@dataclass
class CitationLocationResult:
    citation_id: str
    source_path: str
    match_type: str          # exact | normalized | fuzzy | not_found
    match_score: float
    page_found: int | None   # None si el source no es paginado (texto plano)
    verified: bool           # True solo si match_type in (exact, normalized)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _extract_text_pages(path: Path) -> list[str]:
    if path.suffix.lower() == ".pdf":
        import pypdf
        reader = pypdf.PdfReader(str(path))
        return [(p.extract_text() or "") for p in reader.pages]
    return [path.read_text(encoding="utf-8", errors="replace")]


def locate_citation(citation_id: str, citation_text: str, source_path: Path) -> CitationLocationResult:
    """Busca citation_text en CADA pagina/unidad de source_path (no en el
    documento concatenado -- asi se puede reportar page_found real para
    PDFs). Si no se encuentra exacto/normalizado en ninguna pagina
    individual, reintenta sobre el texto completo concatenado (una cita
    puede cruzar un salto de pagina de extraccion) antes de declarar
    not_found."""
    pages = _extract_text_pages(source_path)
    best = CitationLocationResult(citation_id, str(source_path), "not_found", 0.0, None, False)

    for i, page_text in enumerate(pages):
        match_type, score = match_citation(citation_text, page_text)
        if match_type in ("exact", "normalized"):
            return CitationLocationResult(citation_id, str(source_path), match_type, score, i + 1, True)
        if score > best.match_score:
            best = CitationLocationResult(citation_id, str(source_path), match_type, score,
                                           i + 1 if match_type == "fuzzy" else None, False)

    full_text = "\n".join(pages)
    match_type, score = match_citation(citation_text, full_text)
    if match_type in ("exact", "normalized") and not best.verified:
        return CitationLocationResult(citation_id, str(source_path), match_type, score, None, True)

    return best
