"""
Tests — readiness de correccion por documento sobre los 13 Rockwell
restantes (tras el piloto sobre SAT3 Completed.pdf), matriz de
aplicabilidad y destino finding->documento. No reprocesa nada: opera sobre
el RC canonico real ya aprobado.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.services import gmpai_artifact_service as svc
from factory.services import gmpai_document_readiness_service as rs


def _real_pdata():
    return svc.load_canonical_pipeline_data()[1]


def test_readiness_matrix_covers_every_record_except_the_piloted_one():
    """Invariante, no conteo: la matriz cubre TODOS los documentos del RC
    salvo el ya piloteado — ni uno menos (omision silenciosa) ni uno mas.

    Antes afirmaba `len(rows) == 13`. Un documento nuevo en el RC canonico
    rompia el test con "13 != 14", que no dice nada de lo que importa; y un
    documento OMITIDO en silencio, junto con otro anadido, habria pasado
    inadvertido con el conteo intacto."""
    pdata = _real_pdata()
    rows = rs.build_readiness_matrix(pdata)
    esperado = {r["filename"] for r in pdata["records"]} - {rs.PILOTED_DOCUMENT}
    assert {r["nombre"] for r in rows} == esperado
    assert rs.PILOTED_DOCUMENT not in {r["nombre"] for r in rows}


def test_no_document_is_draft_ready_yet():
    """Ninguno de los 13 documentos reales califica hoy para DRAFT_READY:
    todos estan truncados, en conflicto de version, escaneados o con
    aplicabilidad incierta. No se deben generar borradores todavia."""
    pdata = _real_pdata()
    rows = rs.build_readiness_matrix(pdata)
    assert all(r["decision_preparacion"] != "DRAFT_READY" for r in rows)


def test_scanned_documents_classified_as_ocr_required():
    pdata = _real_pdata()
    rows = rs.build_readiness_matrix(pdata)
    scanned_names = {
        "215115305 MCCPDC PLC Panel Rev 0 09-07-22.pdf",
        "215115305 SCADA-PCS Misc PLC SAT3 Scanned-1.pdf",
        "215115305-T-039 Design Docs for ASantiago.docm",
    }
    by_name = {r["nombre"]: r for r in rows}
    for name in scanned_names:
        assert by_name[name]["decision_preparacion"] == "OCR_OR_EXTRACTION_REQUIRED"
        assert by_name[name]["texto_original_disponible"] is False


def test_version_conflict_documents_require_reanalysis_not_draft():
    pdata = _real_pdata()
    rows = rs.build_readiness_matrix(pdata)
    # Excluye el .docm en conflicto que ademas es escaneado/degradado (ese
    # caso cae primero en OCR_OR_EXTRACTION_REQUIRED, correctamente).
    conflicted = [r for r in rows if r["conflicto_de_version"] and not r["es_escaneado"]]
    assert conflicted
    assert all(r["decision_preparacion"] == "REANALYSIS_REQUIRED" for r in conflicted)


def test_alarm_listing_flagged_not_applicable_not_truncation():
    pdata = _real_pdata()
    rows = rs.build_readiness_matrix(pdata)
    row = next(r for r in rows if r["tipo_documental"] == "ALARM_IO_LISTING")
    assert row["decision_preparacion"] == "NO_APPLICABLE_CORRECTION"


def test_no_document_has_page_section_citations():
    """Confirmado sobre el RC real: 0 findings citan pagina/seccion real en
    todo el corpus (siempre 'n/a' o el texto generico de fallback)."""
    pdata = _real_pdata()
    rows = rs.build_readiness_matrix(pdata)
    assert all(r["citas_pagina_seccion_disponibles"] is False for r in rows)


def test_truncation_percentages_are_real_and_low():
    pdata = _real_pdata()
    rows = rs.build_readiness_matrix(pdata)
    by_name = {r["nombre"]: r for r in rows}
    urs = by_name["215115305 SCADA-PCS Misc PLC System URS v2.1.pdf"]
    assert urs["supera_6000_chars"] is True
    assert urs["pct_aproximado_analizado"] < 20.0


def test_applicability_matrix_covers_all_present_doc_types():
    present_types = {"URS", "FS", "DS", "ARCHITECTURE", "CONTROL_NARRATIVE", "ALARM_IO_LISTING", "SAT", "OTHER"}
    matrix_types = {row["tipo_documental"] for row in rs.applicability_matrix()}
    assert present_types.issubset(matrix_types)


def test_destination_matrix_never_marks_modify_existing_without_draft_ready():
    pdata = _real_pdata()
    readiness = rs.build_readiness_matrix(pdata)
    dest = rs.build_finding_destination_matrix(pdata, readiness)
    assert dest
    assert all(row["correction_type"] != "modify_existing_document" for row in dest)


def test_destination_matrix_covers_every_finding_of_the_covered_documents():
    """La regla que sostenia al `== 247` (267 totales - 19 del piloto - 1 de
    trazabilidad): un finding entra si y solo si su documento esta en la
    matriz de readiness. Se comprueba la regla contra los findings reales,
    en vez de congelar su resultado aritmetico de un dia concreto."""
    pdata = _real_pdata()
    readiness = rs.build_readiness_matrix(pdata)
    dest = rs.build_finding_destination_matrix(pdata, readiness)
    cubiertos = {r["nombre"] for r in readiness}
    esperados = [f for f in pdata["findings"] if f["documento"] in cubiertos]
    assert len(dest) == len(esperados)
    assert {row["source_document"] for row in dest} <= cubiertos
    assert rs.PILOTED_DOCUMENT not in {row["source_document"] for row in dest}
    # ningun finding se cae por un motivo no declarado: lo excluido es del
    # piloto o de un documento que no esta en los records del RC (SCADA)
    en_records = {r["filename"] for r in pdata["records"]}
    fuera = {f["documento"] for f in pdata["findings"]} - cubiertos
    assert fuera & en_records <= {rs.PILOTED_DOCUMENT}, (
        f"documentos del RC con findings pero sin fila de readiness: "
        f"{fuera & en_records - {rs.PILOTED_DOCUMENT}}"
    )
