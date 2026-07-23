"""
Tests -- factory/services/xlsx_candidate_generator.py.

Cubre generación del candidato limpio, el redline marcado (verde +
comentario `[change_id]`), y el gate DOCUMENT_CONFORMANCE reabriendo el
.xlsx real desde disco -- sobre un workbook real creado en el propio test
(no un mock), con hojas y fórmulas reales preservadas.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import openpyxl
import pytest

from factory.services.xlsx_candidate_generator import (
    generate_candidate_workbook, generate_redline_workbook, verify_workbook_conformance,
)


def _make_real_xlsx(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Alarms"
    ws1["A1"] = "Tag"
    ws1["B1"] = "Description"
    ws1["A2"] = "AL-001"
    ws1["B2"] = "High temperature"
    ws2 = wb.create_sheet("Totals")
    ws2["A1"] = "Count"
    ws2["A2"] = 5
    ws2["A3"] = "=SUM(A2:A2)"  # formula real, debe preservarse intacta
    wb.save(path)


def _change(change_id, document_location, proposed_content, change_type="CONTENT_ADDITION"):
    return {
        "change_id": change_id, "document_location": document_location,
        "proposed_content": proposed_content, "change_type": change_type,
    }


@pytest.fixture()
def real_xlsx(tmp_path) -> Path:
    path = tmp_path / "original.xlsx"
    _make_real_xlsx(path)
    return path


class TestGenerateCandidateWorkbook:

    def test_target_cell_updated_other_cells_preserved(self, real_xlsx):
        change = _change("C1", "Alarms!B2", "Very high temperature (revised)")
        wb = generate_candidate_workbook(str(real_xlsx), [change])
        assert wb["Alarms"]["B2"].value == "Very high temperature (revised)"
        assert wb["Alarms"]["A2"].value == "AL-001"  # celda vecina intacta

    def test_formulas_in_untouched_sheets_are_preserved(self, real_xlsx):
        change = _change("C1", "Alarms!B2", "nuevo valor")
        wb = generate_candidate_workbook(str(real_xlsx), [change])
        assert wb["Totals"]["A3"].value == "=SUM(A2:A2)"

    def test_original_file_on_disk_never_modified(self, real_xlsx):
        original_bytes_before = real_xlsx.read_bytes()
        generate_candidate_workbook(str(real_xlsx), [_change("C1", "Alarms!B2", "x")])
        assert real_xlsx.read_bytes() == original_bytes_before

    def test_unknown_sheet_raises_explicit_error(self, real_xlsx):
        change = _change("C1", "HojaFantasma!A1", "x")
        with pytest.raises(ValueError, match="no existe en el workbook real"):
            generate_candidate_workbook(str(real_xlsx), [change])

    def test_malformed_document_location_raises_explicit_error(self, real_xlsx):
        change = _change("C1", "esto no tiene el formato correcto", "x")
        with pytest.raises(ValueError, match="formato esperado"):
            generate_candidate_workbook(str(real_xlsx), [change])


class TestGenerateRedlineWorkbook:

    def test_manifest_records_change_and_original_value(self, real_xlsx):
        change = _change("C1", "Alarms!B2", "nuevo valor")
        wb, manifest = generate_redline_workbook(str(real_xlsx), [change])
        assert len(manifest) == 1
        entry = manifest[0]
        assert entry["change_id"] == "C1"
        assert entry["sheet_name"] == "Alarms"
        assert entry["cell_coordinate"] == "B2"
        assert entry["original_value"] == "High temperature"

    def test_modified_cell_has_comment_with_change_id(self, real_xlsx):
        change = _change("C1", "Alarms!B2", "nuevo valor")
        wb, _manifest = generate_redline_workbook(str(real_xlsx), [change])
        comment = wb["Alarms"]["B2"].comment
        assert comment is not None
        assert "[C1]" in comment.text

    def test_modified_cell_font_is_marked(self, real_xlsx):
        change = _change("C1", "Alarms!B2", "nuevo valor")
        wb, _manifest = generate_redline_workbook(str(real_xlsx), [change])
        assert wb["Alarms"]["B2"].font.color is not None


class TestVerifyWorkbookConformance:

    def test_real_gate_against_disk_saved_file(self, real_xlsx, tmp_path):
        change = _change("C1", "Alarms!B2", "Very high temperature (revised)")
        wb, manifest = generate_redline_workbook(str(real_xlsx), [change])
        saved_path = tmp_path / "redline.xlsx"
        wb.save(saved_path)

        results = verify_workbook_conformance(str(saved_path), [change], manifest)
        assert results == [{
            "change_id": "C1", "status": "DOCUMENT_CONFORMANCE",
            "sheet_name": "Alarms", "cell_coordinate": "B2",
        }]

    def test_conformance_fails_if_saved_value_does_not_match(self, real_xlsx, tmp_path):
        change = _change("C1", "Alarms!B2", "valor esperado")
        wb, manifest = generate_redline_workbook(str(real_xlsx), [change])
        # Simula una corrupcion real: se guarda con un valor DISTINTO al declarado.
        wb["Alarms"]["B2"] = "valor corrompido"
        saved_path = tmp_path / "redline.xlsx"
        wb.save(saved_path)

        results = verify_workbook_conformance(str(saved_path), [change], manifest)
        assert results[0]["status"] == "CHANGE_NOT_APPLIED"

    def test_missing_manifest_entry_is_change_not_applied(self, real_xlsx, tmp_path):
        change = _change("C1", "Alarms!B2", "x")
        saved_path = tmp_path / "unrelated.xlsx"
        _make_real_xlsx(saved_path)
        results = verify_workbook_conformance(str(saved_path), [change], insertion_manifest=[])
        assert results[0]["status"] == "CHANGE_NOT_APPLIED"
        assert "insertion_manifest" in results[0]["reason"]
