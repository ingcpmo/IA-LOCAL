"""Tests -- factory/regulatory/retrieval/evidence_bundle.py (V2, B3).

docs_plan/ARQUITECTURA_OBJETIVO_ANALIZADOR_GMP_LOCAL_V2.md FASE 4.3:
un EvidenceBundle por sub-criterio, ≤5 Claim candidatos con provenance
completo, ranking guiado por el texto del sub-criterio. Determinista,
sin LLM, sin embeddings.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.canonical import model as m
from factory.regulatory.canonical.persistence import CanonicalStore
from factory.regulatory.retrieval import evidence_bundle as eb
from factory.regulatory.requirement_catalog.requirement_decomposition_loader import get_subcriteria


def _seed(canon_dir: Path, document_id="RW-T"):
    """Claims en ESPAÑOL a propósito: los sub-criterios firmados
    (decomposition.yaml) están en español, así que un fixture en español
    prueba el MECANISMO de ranking por sub-criterio de forma determinista.
    El comportamiento con documentos en inglés (limitación conocida del
    reranker léxico cross-idioma) lo cubre `test_real_corpus_if_available`,
    de forma tolerante."""
    with CanonicalStore(document_id, store_dir=canon_dir) as s:
        s.put(m.Document(document_id=document_id, sha256="x" * 64, tipo="FS",
                         titulo="FS", n_paginas=50))
        texts = [
            (45, "control", "El sistema genera un audit trail seguro con timestamp para cada "
                            "entrada del operador que crea, modifica o elimina un registro "
                            "electrónico, preservando el valor previo."),
            (39, "control", "El acceso para modificar la configuración del audit trail está "
                            "restringido a usuarios con el rol de administrador de seguridad."),
            (12, "function", "La HMI muestra las tendencias de temperatura y presión del reactor."),
            (50, "control", "El audit trail se puede exportar a CSV para inspección y revisión."),
            (7, "statement", "Este documento describe el sistema SCADA-PCS Misc PLC para MCCPDC."),
        ]
        for pg, tp, tx in texts:
            s.put(m.build_claim(document_id, pg, tx, tp, tx))
        # una tabla de audit trail con encabezados en español
        s.put(m.build_table(document_id, 46, headers=["Fecha y hora", "Usuario", "Valor previo", "Valor nuevo"],
                            rows=[["10:35", "OP01", "100", "120"], ["10:37", "OP02", "20", "25"]]))
    return document_id


def test_bundle_per_subcriterion(tmp_path):
    canon_dir = tmp_path / "canon"
    did = _seed(canon_dir)
    bundles = eb.build_bundles_for_requirement(did, "21_CFR_11.10(e)", canon_dir=canon_dir)
    assert len(bundles) == len(get_subcriteria("21_CFR_11.10(e)")) == 9
    for b in bundles:
        assert b.subcriterion_ref.startswith("21_CFR_11.10(e)::sc")
        assert len(b.candidate_claims) <= eb.MAX_CANDIDATES
        for c in b.candidate_claims:
            assert c["source_text"]
            assert c["provenance"]["source_hash"]
            assert c["provenance"]["document_id"] == did
            assert "rerank_score" in c


def test_subcriterion_drives_ranking(tmp_path):
    canon_dir = tmp_path / "canon"
    did = _seed(canon_dir)
    bundles = {b.subcriterion_id: b for b in
               eb.build_bundles_for_requirement(did, "21_CFR_11.10(e)", canon_dir=canon_dir)}
    # sc5: "el acceso para modificar el propio audit trail está restringido a usuarios privilegiados"
    top5 = bundles["sc5"].candidate_claims[0]["source_text"].lower()
    assert "restringido a usuarios" in top5
    # sc9: "el audit trail se puede exportar o copiar para inspección"
    top9 = bundles["sc9"].candidate_claims[0]["source_text"].lower()
    assert "exportar a csv" in top9


def test_tables_attached_when_relevant(tmp_path):
    canon_dir = tmp_path / "canon"
    did = _seed(canon_dir)
    bundles = {b.subcriterion_id: b for b in
               eb.build_bundles_for_requirement(did, "21_CFR_11.10(e)", canon_dir=canon_dir)}
    # sc4 habla de "preserva el valor o la información previa" -> la tabla
    # con Old Value / New Value debería adjuntarse a algún sub-criterio de audit trail.
    any_table = any(b.candidate_tables for b in bundles.values())
    assert any_table
    for b in bundles.values():
        for t in b.candidate_tables:
            assert t["provenance"]["source_hash"]
            assert t["matched_rows"]


def test_deterministic(tmp_path):
    canon_dir = tmp_path / "canon"
    did = _seed(canon_dir)
    b1 = eb.build_bundles_for_requirement(did, "21_CFR_11.10(g)", canon_dir=canon_dir)
    b2 = eb.build_bundles_for_requirement(did, "21_CFR_11.10(g)", canon_dir=canon_dir)
    assert [(x.subcriterion_id, [c["claim_id"] for c in x.candidate_claims]) for x in b1] == \
           [(x.subcriterion_id, [c["claim_id"] for c in x.candidate_claims]) for x in b2]


def test_real_corpus_if_available(tmp_path):
    from factory.regulatory.canonical.extract_document import extract_document
    bases = [Path("/home/cmay/ivr-ia/GMPAI/source/Rockwell"),
             Path("/home/ing_cpmo/GMPAI/source/Rockwell")]
    base = next((b for b in bases if b.exists()), None)
    if base is None:
        pytest.skip("corpus real Rockwell no disponible")
    pdf = base / "215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf"
    if not pdf.exists():
        pytest.skip("FS_v1.2.pdf no disponible")
    canon_dir = tmp_path / "canon"
    extract_document(pdf, "RW-0005", tipo="FS", store_dir=canon_dir)
    bundles = eb.build_bundles_for_requirement("RW-0005", "21_CFR_11.10(e)", canon_dir=canon_dir)
    assert len(bundles) == 9
    assert any(b.candidate_claims for b in bundles)
    for b in bundles:
        assert len(b.candidate_claims) <= 5
        for c in b.candidate_claims:
            assert c["provenance"]["document_id"] == "RW-0005"
    # v1.1 (glosas EN): sobre el FS en inglés, los 9 sub-criterios ya NO
    # devuelven todos el mismo top claim -- el reranker bilingüe diferencia.
    tops = [b.candidate_claims[0]["claim_id"] for b in bundles if b.candidate_claims]
    assert len(set(tops)) >= 3, f"diferenciación insuficiente: {len(set(tops))} tops distintos de {len(tops)}"
