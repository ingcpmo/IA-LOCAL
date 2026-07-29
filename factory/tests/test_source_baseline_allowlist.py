"""
Tests -- factory/regulatory/tools/build_source_baseline_allowlist.py
(W5 V2, Fase A -- AGT-INV).

Cubre: deteccion de duplicados exactos (canonico = sin sufijo numerico),
extraccion segura de DOCM (nunca abre vbaProject.bin), gate de cobertura
100% (count(find)==count(allowlist)), validacion de schema, y confinamiento
de path_policy.resolve_regulatory_scope(). Incluye tambien un gate real
contra GMPAI/source/Rockwell/ (14 archivos reales conocidos, ver
ROCKWELL_SOURCE_INVENTORY_AND_SCOPE_SPEC.md) -- se salta si ese arbol no
existe en el entorno donde corre la suite.
"""
import json
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import jsonschema
import pypdf
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.core.path_policy import resolve_regulatory_scope
from factory.regulatory.tools.build_source_baseline_allowlist import (
    build_allowlist, entries_to_yaml_dict, extraction_capability_for,
    verify_coverage,
)

_SCHEMA = json.loads(
    Path("factory/regulatory/schemas/source_baseline_allowlist_entry_v1.json").read_text()
)
_REAL_SOURCE_DIR = Path("/home/ing_cpmo/GMPAI/source/Rockwell")


def _make_blank_pdf(path: Path) -> None:
    """PDF minimo pero VALIDO (pypdf lo abre sin error) -- las pruebas de
    duplicados/cobertura no dependen del contenido de texto real."""
    w = pypdf.PdfWriter()
    w.add_blank_page(width=72, height=72)
    with open(path, "wb") as f:
        w.write(f)


def _make_docm(path: Path, paragraphs: list[str], vba_marker: bytes = b"FAKE_VBA_NEVER_READ") -> None:
    """Construye un .docm minimo (paquete OOXML) con parrafos reales y un
    'word/vbaProject.bin' de relleno -- el test verifica que nunca se lee."""
    doc_xml_paras = "".join(f'<w:p><w:r><w:t>{p}</w:t></w:r></w:p>' for p in paragraphs)
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{doc_xml_paras}</w:body></w:document>'
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", document_xml)
        z.writestr("word/vbaProject.bin", vba_marker)


class TestExtractionCapability:

    def test_docm_extracts_text_without_reading_vba(self, tmp_path):
        docm = tmp_path / "sample.docm"
        _make_docm(docm, ["Hola mundo", "Segundo parrafo"])
        cap, note = extraction_capability_for(docm)
        assert cap == "TEXT_NATIVE"
        assert "10" in note or "chars" in note  # longitud real reportada

    def test_docm_vba_project_never_opened(self, tmp_path, monkeypatch):
        docm = tmp_path / "sample.docm"
        _make_docm(docm, ["contenido"])

        original_open = zipfile.ZipFile.open

        def _guarded_open(self, name, *a, **kw):
            if isinstance(name, str) and "vbaProject" in name:
                raise AssertionError("vbaProject.bin fue abierto -- violacion de la regla dura")
            return original_open(self, name, *a, **kw)

        monkeypatch.setattr(zipfile.ZipFile, "open", _guarded_open)
        cap, _ = extraction_capability_for(docm)
        assert cap == "TEXT_NATIVE"

    def test_xlsx_always_text_native(self, tmp_path):
        # No se abre el archivo para .xlsx (regla determinista por formato).
        xlsx = tmp_path / "listing.xlsx"
        xlsx.write_bytes(b"not a real xlsx, never opened")
        cap, note = extraction_capability_for(xlsx)
        assert cap == "TEXT_NATIVE"
        assert "estructurado" in note


class TestBuildAllowlistSynthetic:

    def _make_source_tree(self, tmp_path: Path) -> Path:
        src = tmp_path / "source" / "Rockwell"
        src.mkdir(parents=True)
        _make_blank_pdf(src / "URS v1.0.pdf")
        _make_blank_pdf(src / "FS_v1.0.pdf")
        # Copia byte-exacta (duplicado real, no solo "misma forma de PDF").
        (src / "FS_v1.0-2.pdf").write_bytes((src / "FS_v1.0.pdf").read_bytes())
        (src / "listing.xlsx").write_bytes(b"fake xlsx bytes -- nunca abierto para .xlsx")
        return src

    def test_exact_duplicate_canonical_is_the_one_without_numeric_suffix(self, tmp_path):
        # PDFs en blanco -> 0 chars/pagina -> OCR_REQUIRED es la clasificacion
        # correcta por si sola (ver TestExtractionCapability); lo que esta
        # prueba cubre es la eleccion de canonico entre duplicados exactos,
        # que se decide ANTES y de forma independiente de extraction_capability.
        src = self._make_source_tree(tmp_path)
        entries = build_allowlist(src)
        by_name = {e.name: e for e in entries}
        assert by_name["FS_v1.0.pdf"].processing_state != "DUPLICATE"
        assert by_name["FS_v1.0.pdf"].duplicate_of is None
        assert by_name["FS_v1.0-2.pdf"].processing_state == "DUPLICATE"
        assert by_name["FS_v1.0-2.pdf"].duplicate_of == by_name["FS_v1.0.pdf"].file_id

    def test_coverage_gate_passes_on_full_tree(self, tmp_path):
        src = self._make_source_tree(tmp_path)
        entries = build_allowlist(src)
        verify_coverage(src, entries)  # no debe lanzar

    def test_coverage_gate_fails_if_entry_missing(self, tmp_path):
        src = self._make_source_tree(tmp_path)
        entries = build_allowlist(src)
        with pytest.raises(AssertionError):
            verify_coverage(src, entries[:-1])  # simula una omision

    def test_applicability_always_pending_in_phase_a(self, tmp_path):
        src = self._make_source_tree(tmp_path)
        entries = build_allowlist(src)
        assert all(e.applicability == "PENDING_AGT_APP_ASSIGNMENT" for e in entries)
        assert all(e.related_requirements == [] for e in entries)

    def test_every_entry_validates_against_schema(self, tmp_path):
        src = self._make_source_tree(tmp_path)
        entries = build_allowlist(src)
        payload = entries_to_yaml_dict(entries)
        for entry in payload:
            jsonschema.validate(entry, _SCHEMA)


class TestResolveRegulatoryScope:

    def test_rejects_traversal(self, tmp_path):
        with pytest.raises(ValueError):
            resolve_regulatory_scope("../escape.yaml", tmp_path)

    def test_rejects_subdirectory(self, tmp_path):
        with pytest.raises(ValueError):
            resolve_regulatory_scope("sub/allowlist.yaml", tmp_path)

    def test_rejects_non_yaml_extension(self, tmp_path):
        with pytest.raises(PermissionError):
            resolve_regulatory_scope("allowlist.json", tmp_path)

    def test_rejects_uppercase_or_symbol_name(self, tmp_path):
        with pytest.raises(ValueError):
            resolve_regulatory_scope("Allow-List!.yaml", tmp_path)

    def test_accepts_valid_name_inside_base(self, tmp_path):
        target = resolve_regulatory_scope("source_baseline_allowlist.yaml", tmp_path)
        assert target == (tmp_path / "source_baseline_allowlist.yaml").resolve()


@pytest.mark.skipif(
    not _REAL_SOURCE_DIR.exists(),
    reason=f"Requiere el arbol real {_REAL_SOURCE_DIR} (no presente en este entorno).",
)
class TestRealRockwellCorpusGate:
    """Gate real contra los 14 archivos reales de Rockwell -- mismo patron
    ya usado en Fase 4 de document_remediation_evolution (correr contra el
    documento real, no solo fixtures sinteticos, es lo que expone bugs
    reales de clasificacion/extraccion)."""

    def test_covers_every_real_file_exactly_once(self):
        """`verify_coverage` ya es el gate real (0 omisiones permitidas). El
        `len(entries) == 14` que habia debajo congelaba el tamano del corpus
        de hoy sin anadir cobertura; se sustituye por el conteo real del
        directorio, que es contra lo que el gate se mide."""
        entries = build_allowlist(
            _REAL_SOURCE_DIR,
            manifest_path=Path("/home/ing_cpmo/GMPAI/manifests/SHA256SUMS.txt"),
            manifest_root=Path("/home/ing_cpmo/GMPAI"),
        )
        verify_coverage(_REAL_SOURCE_DIR, entries)
        archivos_reales = [p for p in _REAL_SOURCE_DIR.rglob("*") if p.is_file()]
        assert len(entries) == len(archivos_reales)
        assert {e.name for e in entries} == {p.name for p in archivos_reales}

    def test_exactly_one_duplicate_pair_fs_v1_2(self):
        entries = build_allowlist(
            _REAL_SOURCE_DIR,
            manifest_path=Path("/home/ing_cpmo/GMPAI/manifests/SHA256SUMS.txt"),
            manifest_root=Path("/home/ing_cpmo/GMPAI"),
        )
        duplicates = [e for e in entries if e.processing_state == "DUPLICATE"]
        assert len(duplicates) == 1
        assert duplicates[0].name == "215115305 SCADA-PCS Misc PLC System FS_v1.2-2.pdf"
        canonical = next(e for e in entries if e.file_id == duplicates[0].duplicate_of)
        assert canonical.name == "215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf"

    def test_scanned_pdf_flagged_ocr_required(self):
        entries = build_allowlist(_REAL_SOURCE_DIR)
        scanned = next(e for e in entries if "SAT3 Scanned" in e.name)
        assert scanned.extraction_capability == "OCR_REQUIRED"
        assert scanned.processing_state == "OCR_REQUIRED"

    def test_t039_content_override_applied_not_silently_classified_as_ds(self):
        entries = build_allowlist(_REAL_SOURCE_DIR)
        docm = next(e for e in entries if e.name.endswith("T-039 Design Docs for ASantiago.docm"))
        pdf = next(e for e in entries if e.name.endswith("T-039 Design Docs for ASantiago.pdf"))
        assert docm.doc_type == "OTHER"
        assert pdf.doc_type == "OTHER"
        assert pdf.processing_state == "HUMAN_REVIEW_REQUIRED"

    def test_all_entries_validate_against_schema(self):
        entries = build_allowlist(_REAL_SOURCE_DIR)
        payload = entries_to_yaml_dict(entries)
        for entry in payload:
            jsonschema.validate(entry, _SCHEMA)

    def test_generated_allowlist_file_matches_current_build(self):
        """El YAML ya commiteado en factory/regulatory/scope/ debe ser
        reproducible: reconstruirlo produce el mismo conjunto de sha256 y
        processing_state (no re-generamos el archivo, solo comparamos)."""
        allowlist_path = Path("factory/regulatory/scope/source_baseline_allowlist.yaml")
        if not allowlist_path.exists():
            pytest.skip("allowlist aun no generado en este checkout")
        on_disk = yaml.safe_load(allowlist_path.read_text())
        fresh = entries_to_yaml_dict(build_allowlist(
            _REAL_SOURCE_DIR,
            manifest_path=Path("/home/ing_cpmo/GMPAI/manifests/SHA256SUMS.txt"),
            manifest_root=Path("/home/ing_cpmo/GMPAI"),
        ))
        on_disk_by_sha = {e["sha256"]: e["processing_state"] for e in on_disk}
        fresh_by_sha = {e["sha256"]: e["processing_state"] for e in fresh}
        assert on_disk_by_sha == fresh_by_sha


# ===========================================================================
# G1.10 -- elegibilidad para la baseline FORMAL (consumidor C-4)
# ===========================================================================

import json as _json

import pytest as _pytest

from factory.regulatory.tools.build_source_baseline_allowlist import (
    FORMAL,
    PROVISIONAL,
    classify_baseline_eligibility,
)
from factory.services import decision_store_v2 as _store

DOC = "RW-0005"
SOURCES = ["ecfr_21cfr_part11", "eu_gmp_annex11"]


def _decisions(tmp_path, *, docs=(), sources=()):
    recs = []
    if docs:
        recs.append(_store.build_record(
            decision_family="D3", decision_type="ORIGINAL",
            selection_mode="EXPLICIT_LIST", resolved_target_ids=list(docs),
            decision="APPROVE", decision_origin="human_confirmed",
            approved_by_id="Cesar", approved_by_display_name="Cesar",
            decision_instance_id="D3-2026-001"))
    if sources:
        recs.append(_store.build_record(
            decision_family="D1", decision_type="ORIGINAL",
            selection_mode="EXPLICIT_LIST", resolved_target_ids=list(sources),
            decision="APPROVE", decision_origin="human_confirmed",
            approved_by_id="Cesar", approved_by_display_name="Cesar",
            decision_instance_id="D1-2026-001"))
    path = tmp_path / "decisions_v2.jsonl"
    path.write_text("".join(_json.dumps(r, ensure_ascii=False) + "\n" for r in recs),
                    encoding="utf-8")
    return path


def test_inventory_never_depends_on_decisions():
    """Negarse a inventariar por falta de firma dejaría a la fábrica sin saber
    siquiera QUÉ documentos existen -- lo contrario de la gobernanza."""
    import ast
    from pathlib import Path as _Path
    from factory.regulatory.tools import build_source_baseline_allowlist as _mod

    tree = ast.parse(_Path(_mod.__file__).read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "build_allowlist")
    assert "_resolver" not in ast.dump(fn)


def test_nothing_is_formal_without_any_decision(tmp_path):
    """Estado real de hoy."""
    result = classify_baseline_eligibility(
        [DOC], SOURCES, decision_store_file=_decisions(tmp_path))
    assert result[0].eligibility == PROVISIONAL
    assert result[0].formal is False


def test_document_signed_but_sources_not_is_still_provisional(tmp_path):
    """Una baseline formal se apoya en las fuentes regulatorias: si alguna no
    está cubierta, ningún documento sustenta una conclusión formal por
    impecable que sea su propia clasificación."""
    store_path = _decisions(tmp_path, docs=[DOC])
    result = classify_baseline_eligibility([DOC], SOURCES, decision_store_file=store_path)[0]
    assert result.document_decision_authorized is True
    assert result.regulatory_sources_authorized is False
    assert result.eligibility == PROVISIONAL
    assert set(result.uncovered_source_ids) == set(SOURCES)


def test_sources_signed_but_document_not_is_still_provisional(tmp_path):
    store_path = _decisions(tmp_path, sources=SOURCES)
    result = classify_baseline_eligibility([DOC], SOURCES, decision_store_file=store_path)[0]
    assert result.document_decision_authorized is False
    assert result.regulatory_sources_authorized is True
    assert result.eligibility == PROVISIONAL


def test_formal_requires_both(tmp_path):
    store_path = _decisions(tmp_path, docs=[DOC], sources=SOURCES)
    result = classify_baseline_eligibility([DOC], SOURCES, decision_store_file=store_path)[0]
    assert result.eligibility == FORMAL
    assert result.declared_limitations == ()


def test_uncovered_documents_are_declared_never_dropped(tmp_path):
    """Lo no cubierto sigue en la lista con el motivo escrito. Una baseline a
    la que le faltan documentos sin explicación es peor que una que declara
    sus límites."""
    store_path = _decisions(tmp_path, docs=[DOC], sources=SOURCES)
    result = classify_baseline_eligibility(
        [DOC, "RW-0006"], SOURCES, decision_store_file=store_path)
    assert [r.file_id for r in result] == [DOC, "RW-0006"]
    excluded = [r for r in result if not r.formal][0]
    assert excluded.file_id == "RW-0006"
    assert excluded.declared_limitations
    assert "D3/RW-0006" in excluded.declared_limitations[0]


def test_a_single_uncovered_source_blocks_every_document(tmp_path):
    store_path = _decisions(tmp_path, docs=[DOC, "RW-0006"],
                            sources=[SOURCES[0]])   # falta el segundo
    result = classify_baseline_eligibility(
        [DOC, "RW-0006"], SOURCES, decision_store_file=store_path)
    assert all(r.eligibility == PROVISIONAL for r in result)
    assert all(r.uncovered_source_ids == (SOURCES[1],) for r in result)


def test_d3_resolves_against_the_real_allowlist_structure():
    """El allowlist es una lista plana con `file_id`. La declaración anterior
    ('documents[].document_id') describía una estructura inexistente y
    coverage_report(D3) habría fallado al resolverla."""
    ids, registry_hash = _store.resolve_all_snapshot("D3")
    assert "RW-0001" in ids
    assert len(registry_hash) == 64
