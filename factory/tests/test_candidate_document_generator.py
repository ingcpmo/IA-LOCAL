"""
Tests -- factory/services/candidate_document_generator.py (Fase 5,
document_remediation_evolution).

Cubre generacion del candidato limpio, el redline marcado, y el gate
exacto del roadmap: DOCUMENT_CONFORMANCE automatizado en 100% de los 3
cambios reales (COR-1, COR-2, COR-5) ya aprobados por Cesar en los 2
paquetes reales de la sesion anterior, aplicados sobre la representacion
real de Fase 4 (FS_v1.2.pdf de Rockwell).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from factory.regulatory import document_structure_extractor as extractor
from factory.services import candidate_document_generator as gen

STRUCTURE = {
    "total_paginas": 20,
    "secciones": [
        {"numero": "1", "titulo": "Introduction", "pagina_inicio": 1, "parrafos": ["Texto original 1."]},
        {"numero": "2", "titulo": "Security", "pagina_inicio": 10, "parrafos": ["Texto original 2."]},
    ],
    "texto_previo_a_primera_seccion": ["Portada."],
    "toc_anchored": True,
}


def _change(change_id, page_start, proposed_content, change_type="CONTENT_ADDITION"):
    return {
        "change_id": change_id,
        "change_type": change_type,
        "proposed_content": proposed_content,
        "citations": [{"page_start": page_start}],
    }


def test_generate_candidate_document_inserts_plain_text_no_markup():
    changes = [_change("COR-X", 10, "Contenido nuevo propuesto.")]
    doc = gen.generate_candidate_document(STRUCTURE, changes)
    all_text = [p.text for p in doc.paragraphs]
    assert "Contenido nuevo propuesto." in all_text
    inserted_para = next(p for p in doc.paragraphs if p.text == "Contenido nuevo propuesto.")
    for run in inserted_para.runs:
        assert run.font.color.rgb is None or run.font.color.rgb != gen._INSERTED_COLOR


def test_generate_redline_document_marks_insertion_and_tag():
    changes = [_change("COR-X", 10, "Contenido nuevo propuesto.")]
    doc, manifest = gen.generate_redline_document(STRUCTURE, changes)
    assert len(manifest) == 1
    entry = manifest[0]
    assert entry["change_id"] == "COR-X"
    assert entry["section_numero"] == "2"
    para = doc.paragraphs[entry["paragraph_index"]]
    assert para.text == "[COR-X] Contenido nuevo propuesto."
    tag_run, content_run = para.runs
    assert tag_run.font.color.rgb == gen._TAG_COLOR
    assert content_run.font.color.rgb == gen._INSERTED_COLOR
    assert content_run.text == "Contenido nuevo propuesto."


def test_change_anchored_to_correct_section_by_page():
    changes = [_change("COR-A", 1, "va en seccion 1"), _change("COR-B", 15, "va en seccion 2")]
    doc, manifest = gen.generate_redline_document(STRUCTURE, changes)
    by_id = {m["change_id"]: m for m in manifest}
    assert by_id["COR-A"]["section_numero"] == "1"
    assert by_id["COR-B"]["section_numero"] == "2"


def test_page_before_first_section_raises():
    changes = [_change("COR-X", 0, "texto")]
    with pytest.raises(ValueError):
        gen.generate_redline_document(STRUCTURE, changes)


def test_content_replacement_not_implemented():
    changes = [_change("COR-X", 10, "texto", change_type="CONTENT_REPLACEMENT")]
    with pytest.raises(NotImplementedError):
        gen.generate_redline_document(STRUCTURE, changes)
    with pytest.raises(NotImplementedError):
        gen.generate_candidate_document(STRUCTURE, changes)


def test_verify_document_conformance_reopens_from_disk_and_matches(tmp_path):
    changes = [_change("COR-X", 10, "Contenido exacto esperado.")]
    doc, manifest = gen.generate_redline_document(STRUCTURE, changes)
    path = tmp_path / "redline.docx"
    doc.save(str(path))

    results = gen.verify_document_conformance(str(path), changes, manifest)
    assert results == [{"change_id": "COR-X", "status": "DOCUMENT_CONFORMANCE", "paragraph_index": manifest[0]["paragraph_index"]}]


def test_verify_document_conformance_detects_missing_manifest_entry(tmp_path):
    changes = [_change("COR-X", 10, "Contenido.")]
    doc, manifest = gen.generate_redline_document(STRUCTURE, changes)
    path = tmp_path / "redline.docx"
    doc.save(str(path))

    results = gen.verify_document_conformance(str(path), changes, insertion_manifest=[])
    assert results[0]["status"] == "CHANGE_NOT_APPLIED"
    assert "sin entrada" in results[0]["reason"]


def test_verify_document_conformance_detects_text_mismatch(tmp_path):
    changes = [_change("COR-X", 10, "Contenido correcto.")]
    doc, manifest = gen.generate_redline_document(STRUCTURE, changes)
    path = tmp_path / "redline.docx"
    doc.save(str(path))

    tampered_manifest = [{**manifest[0], "proposed_content_sha256": "0" * 64}]
    results = gen.verify_document_conformance(
        str(path),
        [_change("COR-X", 10, "Texto distinto al realmente insertado.")],
        tampered_manifest,
    )
    assert results[0]["status"] == "CHANGE_NOT_APPLIED"


REAL_PDF = Path(
    "/home/ing_cpmo/GMPAI/source/Rockwell/215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf"
)
REAL_PACKAGES_DIR = Path("/home/ing_cpmo/factory/remediation_packages/gmpai_document_validation")


def _load_real_changes() -> list[dict]:
    changes = []
    for pkg, ids in [
        ("PKG-FS-V1-2-MEDIUM-RISK-REAL", ["COR-1"]),
        ("PKG-FS-V1-2-REAL-CONTROLLED", ["COR-2", "COR-5"]),
    ]:
        state = json.loads((REAL_PACKAGES_DIR / pkg / "v1" / "state.json").read_text(encoding="utf-8"))
        for change_id in ids:
            changes.append(state["changes"][change_id])
    return changes


def test_fase5_gate_document_conformance_100pct_on_3_real_changes(tmp_path):
    """Gate de Fase 5 (`IMPLEMENTATION_ROADMAP.md`): DOCUMENT_CONFORMANCE
    automatizado en 100% de los 3 cambios reales ya aprobados por Cesar
    (COR-1, COR-2, COR-5), aplicados sobre la representacion real de
    Fase 4 (FS_v1.2.pdf de Rockwell)."""
    if not REAL_PDF.exists() or not REAL_PACKAGES_DIR.exists():
        pytest.skip("PDF real o paquetes reales no disponibles en este entorno")

    structure = extractor.extract_structure_from_pdf(REAL_PDF)
    assert structure["toc_anchored"] is True

    changes = _load_real_changes()
    assert {c["change_id"] for c in changes} == {"COR-1", "COR-2", "COR-5"}

    doc, manifest = gen.generate_redline_document(structure, changes)
    path = tmp_path / "fs_v1_2_redline.docx"
    doc.save(str(path))

    results = gen.verify_document_conformance(str(path), changes, manifest)
    assert len(results) == 3
    assert all(r["status"] == "DOCUMENT_CONFORMANCE" for r in results), results

    clean = gen.generate_candidate_document(structure, changes)
    clean_texts = [p.text for p in clean.paragraphs]
    for change in changes:
        assert change["proposed_content"] in clean_texts
