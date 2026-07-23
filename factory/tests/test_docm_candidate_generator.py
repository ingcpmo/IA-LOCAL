"""
Tests -- factory/services/docm_candidate_generator.py.

Cubre generación del candidato DOCM real: inserción de párrafo anclada por
texto real (reutilizando semantic_evidence_verification.verify_anchor),
preservación byte-exacta de word/vbaProject.bin (nunca se abre, nunca se
ejecuta, nunca se modifica), y verificación de conformidad reabriendo el
.docm generado desde bytes reales.
"""
import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from factory.services.docm_candidate_generator import (
    generate_candidate_docm, generate_redline_docm, verify_docm_conformance,
    verify_vba_project_untouched,
)

_WORD_NS_URI = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_FAKE_VBA_BYTES = b"FAKE_VBA_PROJECT_BINARY_NEVER_PARSED_OR_EXECUTED"


def _make_real_docm(path: Path, paragraphs: list[str]) -> None:
    paras_xml = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{_WORD_NS_URI}"><w:body>{paras_xml}</w:body></w:document>'
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", document_xml)
        z.writestr("word/vbaProject.bin", _FAKE_VBA_BYTES)
        z.writestr("[Content_Types].xml", "<Types/>")


def _change(change_id, document_location, proposed_content, change_type="CONTENT_ADDITION"):
    return {
        "change_id": change_id, "document_location": document_location,
        "proposed_content": proposed_content, "change_type": change_type,
    }


@pytest.fixture()
def real_docm(tmp_path) -> Path:
    path = tmp_path / "original.docm"
    _make_real_docm(path, ["Primer parrafo real del documento.", "Segundo parrafo real, distinto."])
    return path


class TestGenerateCandidateDocm:

    def test_inserted_paragraph_appears_after_anchor(self, real_docm):
        change = _change("C1", "Primer parrafo real del documento.", "Texto nuevo insertado.")
        candidate_bytes = generate_candidate_docm(str(real_docm), [change])
        with zipfile.ZipFile(io.BytesIO(candidate_bytes)) as z:
            doc_xml = z.read("word/document.xml").decode("utf-8")
        assert "Texto nuevo insertado." in doc_xml
        assert "[C1]" in doc_xml

    def test_vba_project_bin_is_byte_identical_never_touched(self, real_docm):
        change = _change("C1", "Primer parrafo real del documento.", "Texto nuevo.")
        candidate_bytes = generate_candidate_docm(str(real_docm), [change])
        assert verify_vba_project_untouched(str(real_docm), candidate_bytes) is True

    def test_original_file_never_modified_on_disk(self, real_docm):
        original_bytes_before = real_docm.read_bytes()
        generate_candidate_docm(str(real_docm), [_change("C1", "Primer parrafo real del documento.", "x")])
        assert real_docm.read_bytes() == original_bytes_before

    def test_unknown_anchor_text_raises_explicit_error(self, real_docm):
        change = _change("C1", "Este texto no existe en ningun parrafo real.", "x")
        with pytest.raises(ValueError, match="no se encontro"):
            generate_candidate_docm(str(real_docm), [change])

    def test_content_replacement_raises_not_implemented(self, real_docm):
        change = _change("C1", "Primer parrafo real del documento.", "x", change_type="CONTENT_REPLACEMENT")
        with pytest.raises(NotImplementedError):
            generate_candidate_docm(str(real_docm), [change])

    def test_other_zip_parts_preserved_byte_identical(self, real_docm):
        candidate_bytes = generate_candidate_docm(
            str(real_docm), [_change("C1", "Primer parrafo real del documento.", "x")],
        )
        with zipfile.ZipFile(io.BytesIO(candidate_bytes)) as z:
            content_types = z.read("[Content_Types].xml")
        assert content_types == b"<Types/>"


class TestGenerateRedlineDocm:

    def test_manifest_covers_all_changes(self, real_docm):
        changes = [
            _change("C1", "Primer parrafo real del documento.", "Nuevo 1."),
            _change("C2", "Segundo parrafo real, distinto.", "Nuevo 2."),
        ]
        _bytes, manifest = generate_redline_docm(str(real_docm), changes)
        assert {m["change_id"] for m in manifest} == {"C1", "C2"}

    def test_second_change_can_anchor_after_first_insertion(self, real_docm):
        """Multiples cambios en la misma corrida: el segundo anclaje
        sigue resolviendose sobre el XML ya modificado por el primero."""
        changes = [
            _change("C1", "Primer parrafo real del documento.", "Insercion uno."),
            _change("C2", "Segundo parrafo real, distinto.", "Insercion dos."),
        ]
        redline_bytes, manifest = generate_redline_docm(str(real_docm), changes)
        with zipfile.ZipFile(io.BytesIO(redline_bytes)) as z:
            doc_xml = z.read("word/document.xml").decode("utf-8")
        assert "Insercion uno." in doc_xml
        assert "Insercion dos." in doc_xml
        assert len(manifest) == 2


class TestVerifyDocmConformance:

    def test_real_gate_against_generated_bytes(self, real_docm):
        change = _change("C1", "Primer parrafo real del documento.", "Texto confirmado real.")
        redline_bytes, manifest = generate_redline_docm(str(real_docm), [change])
        results = verify_docm_conformance(redline_bytes, [change], manifest)
        assert results == [{"change_id": "C1", "status": "DOCUMENT_CONFORMANCE"}]

    def test_missing_manifest_entry_is_change_not_applied(self, real_docm):
        change = _change("C1", "Primer parrafo real del documento.", "x")
        candidate_bytes = generate_candidate_docm(str(real_docm), [change])
        results = verify_docm_conformance(candidate_bytes, [change], insertion_manifest=[])
        assert results[0]["status"] == "CHANGE_NOT_APPLIED"


class TestVerifyVbaProjectUntouched:

    def test_returns_true_when_docm_has_no_vba_project(self, tmp_path):
        no_vba_path = tmp_path / "no_vba.docm"
        with zipfile.ZipFile(no_vba_path, "w") as z:
            z.writestr("word/document.xml", '<?xml version="1.0"?><w:document xmlns:w="{}"><w:body><w:p><w:r><w:t>x</w:t></w:r></w:p></w:body></w:document>'.format(_WORD_NS_URI))
        change = _change("C1", "x", "y")
        candidate_bytes = generate_candidate_docm(str(no_vba_path), [change])
        assert verify_vba_project_untouched(str(no_vba_path), candidate_bytes) is True

    def test_detects_tampered_vba_project(self, real_docm):
        change = _change("C1", "Primer parrafo real del documento.", "x")
        candidate_bytes = generate_candidate_docm(str(real_docm), [change])
        # Simula una corrupcion real: alguien reescribe el vbaProject.bin del candidato.
        with zipfile.ZipFile(io.BytesIO(candidate_bytes)) as zin:
            entries = {n: zin.read(n) for n in zin.namelist()}
        entries["word/vbaProject.bin"] = b"TAMPERED_BYTES"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zout:
            for name, data in entries.items():
                zout.writestr(name, data)
        assert verify_vba_project_untouched(str(real_docm), buf.getvalue()) is False
