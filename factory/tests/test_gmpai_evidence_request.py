"""
Tests — Piloto de calidad B (seccion 7 del encargo): documento escaneado sin
texto util extraible. Confirma que el sistema NUNCA fabrica contenido y
genera una solicitud de evidencia real, no un DOCX "corregido".
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.services import gmpai_artifact_service as svc
from factory.services import gmpai_document_readiness_service as rs
from factory.services import gmpai_finding_correction_service as fcs

SCANNED_DOC = "215115305 MCCPDC PLC Panel Rev 0 09-07-22.pdf"
SCANNED_SHA256 = "dc733c64c747d84d21111fa7f68df41c79f5de5a5add338d4f3a984cafb65cea"


def test_scanned_document_real_extraction_has_zero_usable_text():
    """Verificado (fuera de este test, con extraction.py del workspace —
    pdfplumber solo esta disponible en el venv del workspace, no en el
    entorno de la suite pytest general): 0/24 paginas con texto real, el
    'texto' de 69 caracteres es solo separadores de pagina (\\n\\x0c\\n). Este
    test valida contra el dato ya agregado en el RC canonico (text_chars,
    scanned) para no depender de pdfplumber en este entorno."""
    pdata = svc.load_canonical_pipeline_data()[1]
    record = next(r for r in pdata["records"] if r["filename"] == SCANNED_DOC)
    assert record["sha256_computed"] == SCANNED_SHA256
    assert record["text_chars"] < 100  # pagina_o_seccion breaks unicamente
    rows = rs.build_readiness_matrix(pdata)
    row = next(r for r in rows if r["nombre"] == SCANNED_DOC)
    assert row["es_escaneado"] is True
    assert row["decision_preparacion"] == "OCR_OR_EXTRACTION_REQUIRED"


def test_evidence_request_never_fabricates_content():
    rec = fcs.build_evidence_request_record(
        documento=SCANNED_DOC, sha256=SCANNED_SHA256,
        pages_with_text=0, total_pages=24, extraction_confidence=0.0,
        raw_text_sample="\n\x0c\n",
    )
    assert rec["tipo"] == "evidence_request"
    assert rec["mecanismo_ocr_disponible"] is False
    assert rec["estado_correccion"] == "evidence_required"
    assert rec["revision_humana_requerida"] is True
    assert "no se genera correccion" in rec["hallazgo"].lower() or "no se infiere contenido" in rec["hallazgo"].lower()
    # Nunca debe declarar que hay contenido legible.
    assert rec["paginas_con_texto_real"] == 0
