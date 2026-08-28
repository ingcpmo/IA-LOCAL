"""WP-D -- extracción de objetos `Test` (SAT/OQ/IQ/PQ) + gate sobre fixture sintético.

Verifica: parser de líneas (formatos válidos + anti-falso-positivo) · dedup ·
solo roles de protocolo · flag OFF por default => salida idéntica y EXTRACTION_VERSION
sin cambio · flag ON => test rows + versión sufijada · gate WP-D sintético
(tested_by>0, 0 regresión implemented_by/designed_by, REQUIREMENT_NOT_TESTED solo
para los no probados).
"""
from __future__ import annotations

import pytest

from factory.regulatory.canonical import model as m
from factory.regulatory.canonical.extract_tests import (
    TEST_DOC_TYPES, extract_tests_for_document, looks_like_test_line,
)


# ── parser de líneas ───────────────────────────────────────────────────
@pytest.mark.parametrize("line", [
    "SAT-001  Verify UR-WD-001 operator alarm acknowledgement.  Result: PASS",
    "SAT 42 : the audit trail records old and new value  PASSED",
    "OQ-7 the system logs all configuration changes  Pass",
    "Step 5.2.3  Confirm the nightly backup completes and is recorded",
    "Test Case 12  Value remains within tolerance across the run  Accepted",
    "TC-9  Role based access is enforced at login  P/F",
])
def test_line_parser_accepts_real_test_formats(line):
    assert looks_like_test_line(line) is not None


@pytest.mark.parametrize("line", [
    "Step 1 of 2",                                       # paginación
    "Test Step 3 of 10",                                 # paginación
    "Table of Contents .................. 3",            # TOC dot leaders
    "5.2  Execution Approach .................... 12",    # TOC
    "Note: the following section describes the approach.",
    "Revision B  2023-04-06  Issued for execution",      # cabecera
    "Page 4 of 20",
    "The operator shall be trained before execution.",   # prosa sin id
    "Step 3",                                            # id pelado sin sustancia
])
def test_line_parser_rejects_non_test_lines(line):
    assert looks_like_test_line(line) is None


def test_extract_returns_empty_for_non_protocol_roles():
    pages = ["SAT-001  Verify something meaningful here  PASS"]
    for role in ("URS", "FS", "DS", "SOP", "OTHER"):
        assert extract_tests_for_document("X", pages, role) == []
    assert "SAT" in TEST_DOC_TYPES and "OQ" in TEST_DOC_TYPES


def test_extract_dedups_by_identifier_and_captures_result_and_reqrefs():
    pages = [
        "SAT-001  Verify UR-WD-001 alarm acknowledgement by the operator.  Result: PASS\n"
        "SAT-001  duplicate identifier, must be ignored  PASS\n"
        "SAT-002  Verify UR-WD-002 and 21 CFR 11.10(e) audit trail content.  FAIL\n"
    ]
    tests = extract_tests_for_document("WD-SAT", pages, "SAT")
    assert [t.identificador for t in tests] == ["SAT-001", "SAT-002"]
    assert tests[0].resultado == "PASS"
    assert tests[1].resultado in ("FAIL", "FAILED")
    assert any("UR-WD-001" in r for r in tests[0].verifies_requirement_ids)
    assert all(t.provenance is not None for t in tests)


# ── flag de gobernanza (OFF por default) ───────────────────────────────
def test_flag_off_by_default(monkeypatch):
    monkeypatch.delenv(m.TEST_EXTRACTION_ENV, raising=False)
    assert m.test_extraction_enabled() is False
    assert m.effective_extraction_version() == m.EXTRACTION_VERSION


def test_flag_on_changes_effective_version(monkeypatch):
    monkeypatch.setenv(m.TEST_EXTRACTION_ENV, "1")
    assert m.test_extraction_enabled() is True
    assert m.effective_extraction_version() == m.EXTRACTION_VERSION + m.TEST_EXTRACTION_SUFFIX
    # el override explícito gana sobre el env
    assert m.effective_extraction_version(False) == m.EXTRACTION_VERSION


# ── gate WP-D sobre fixture sintético ─────────────────────────────────
def test_wp_d_synthetic_gate_passes():
    from factory.regulatory.validation_v2.wp_d_test_extraction import run_wp_d_synthetic
    g = run_wp_d_synthetic()
    assert g["ALL_PASSED"] is True
    assert g["TESTED_BY_EDGES"] > 0                       # de 0 en el corpus real -> >0
    assert g["TEST_NODES"] == 6 and g["N_TESTS_EXTRACTED"] == 6
    assert g["TEST_IDS"] == [f"SAT-{i:03d}" for i in range(1, 7)]
    assert g["ANTI_FP_OK"] is True                        # exactamente 6, ni uno de las 5 líneas-ruido
    assert g["IMPLEMENTED_BY_EDGES"] == 8                 # 0 regresión
    assert g["DESIGNED_BY_EDGES"] == 0
    assert g["TESTED_REQS_NO_LONGER_FLAGGED"] is True
    assert set(g["REQUIREMENT_NOT_TESTED_EMITTED_FOR"]) == {"UR-WD-007", "UR-WD-008"}
    assert g["document_egress_bytes"] == 0


def test_wp_d_synthetic_is_deterministic():
    from factory.regulatory.validation_v2.wp_d_test_extraction import run_wp_d_synthetic
    a, b = run_wp_d_synthetic(), run_wp_d_synthetic()
    assert a["edges_by_rel"] == b["edges_by_rel"]
    assert a["TEST_IDS"] == b["TEST_IDS"]


# ── E2E: extract_document con flag OFF (default) vs ON ─────────────────
def _make_sat_pdf(path):
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for ln in [
        "215115305-T-041 Site Acceptance Test 3 - Completed",
        "Section 5  Test Execution",
        "SAT-001  Verify UR-WD-001 operator can acknowledge an active alarm.  Result: PASS",
        "SAT-002  Verify UR-WD-002 audit trail records id, timestamp, old and new value.  Result: PASS",
        "SAT-003  Verify UR-WD-003 nightly backup completes and is logged.  Result: PASS",
        "Note: this line is guidance, not a test step.",
        "Step 1 of 2",
    ]:
        pdf.cell(0, 8, ln, new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(path))


def test_extract_document_flag_off_is_additive_noop(tmp_path):
    from factory.regulatory.canonical.extract_document import extract_document
    pdf = tmp_path / "sat.pdf"
    _make_sat_pdf(pdf)

    off = extract_document(pdf, "WD-E2E-OFF", tipo="SAT", store_dir=tmp_path,
                           extract_tests=False)
    on = extract_document(pdf, "WD-E2E-ON", tipo="SAT", store_dir=tmp_path,
                          extract_tests=True)

    # flag OFF: 0 tests, versión base, sin meta test_extraction
    assert off.counts.get("test", 0) == 0
    from factory.regulatory.canonical.persistence import CanonicalStore
    with CanonicalStore("WD-E2E-OFF", store_dir=tmp_path) as s:
        assert s.get_meta("extraction_version") == m.EXTRACTION_VERSION
        assert s.get_meta("test_extraction") is None
        assert s.all("document")[0]["extraction_version"] == m.EXTRACTION_VERSION

    # flag ON: tests > 0, versión sufijada, meta presente
    assert on.counts.get("test", 0) >= 3
    with CanonicalStore("WD-E2E-ON", store_dir=tmp_path) as s:
        assert s.get_meta("extraction_version") == m.EXTRACTION_VERSION + m.TEST_EXTRACTION_SUFFIX
        assert s.get_meta("test_extraction") == "tests-v1"
        ids = sorted(t["identificador"] for t in s.all("test"))
        assert ids[:3] == ["SAT-001", "SAT-002", "SAT-003"]
        # anti-FP en el E2E real: ni "Note:" ni "Step 1 of 2" generan test
        assert all(i.startswith("SAT-") for i in ids)

    # ADITIVO: claims/tablas/secciones idénticos con y sin el flag
    for k in ("claim", "table_obj", "section"):
        assert off.counts.get(k, 0) == on.counts.get(k, 0), k
