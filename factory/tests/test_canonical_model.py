"""Tests -- factory/regulatory/canonical/model.py + persistence.py (V2, B1).

docs_plan/ARQUITECTURA_OBJETIVO_ANALIZADOR_GMP_LOCAL_V2.md FASE 2.2:
provenance obligatorio en todo objeto derivado; un objeto sin provenance
completo NO se persiste (fail-closed). Ids deterministas -> re-extracción
idempotente.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.canonical import model as m
from factory.regulatory.canonical.persistence import CanonicalStore


# ── provenance obligatorio ───────────────────────────────────────────────

def test_provenance_build_ok():
    p = m.Provenance.build("RW-0005", 45, "Audit trail records shall be archived.")
    m.validate_provenance(p)
    assert p.source_hash == m.sha256_text("Audit trail records shall be archived.")
    assert p.page == 45


@pytest.mark.parametrize("kwargs, msg", [
    (dict(document_id="", page=1, source_text="x" * 30), "document_id"),
    (dict(document_id="RW-0005", page=0, source_text="x" * 30), "page"),
    (dict(document_id="RW-0005", page=1, source_text="   "), "source_text"),
])
def test_provenance_build_rejects_incomplete(kwargs, msg):
    with pytest.raises(m.ProvenanceError) as e:
        m.Provenance.build(**kwargs)
    assert msg in str(e.value)


def test_provenance_hash_mismatch_rejected():
    bad = m.Provenance(
        document_id="RW-0005", page=1, source_text="real text here, long enough",
        source_hash="deadbeef", extraction_version=m.EXTRACTION_VERSION,
    )
    with pytest.raises(m.ProvenanceError):
        m.validate_provenance(bad)


# ── objetos derivados sin provenance -> rechazo ──────────────────────────

def test_section_requires_provenance():
    with pytest.raises(m.ProvenanceError):
        m.Section(section_id="sec-x", document_id="RW-0005", numero="1",
                  titulo="Introduction", pagina_inicio=1, pagina_fin=3,
                  provenance=None)


def test_claim_source_hash_must_match():
    with pytest.raises(m.ProvenanceError):
        m.Claim(claim_id="clm-x", document_id="RW-0005", section_id=None,
                pagina=1, source_text="some real claim text here",
                source_hash="wrong", tipo="statement",
                normalized_statement="some real claim text here",
                provenance=m.Provenance.build("RW-0005", 1, "some real claim text here"))


def test_evidence_requires_anchor():
    with pytest.raises(m.ProvenanceError):
        m.build_evidence("RW-0005", 1, "text long enough to be evidence")  # sin claim_id ni table_id


# ── constructores válidos ────────────────────────────────────────────────

def test_build_claim_ok_and_deterministic_id():
    c1 = m.build_claim("RW-0005", 45, "The system shall generate an audit trail record.",
                       "control", "The system shall generate an audit trail record.")
    c2 = m.build_claim("RW-0005", 45, "The system shall generate an audit trail record.",
                       "control", "irrelevante para el id")
    assert c1.claim_id == c2.claim_id            # id determinista por (doc, pagina, source_text)
    assert c1.tipo == "control"
    assert c1.source_hash == m.sha256_text(c1.source_text)


def test_build_table_normalizes_row_width():
    t = m.build_table("RW-0011", 12, headers=["Param", "User", "Time"],
                      rows=[["Alarm HI", "OP01"], ["Alarm LO", "OP02", "10:35", "extra"]])
    assert t.rows[0] == ["Alarm HI", "OP01", ""]          # padded
    assert t.rows[1][:3] == ["Alarm LO", "OP02", "10:35"]  # sobrante preservado


def test_invalid_enums_rejected():
    with pytest.raises(ValueError):
        m.Document(document_id="RW-0005", sha256="abc", tipo="NOPE", titulo="x", n_paginas=1)
    with pytest.raises(ValueError):
        m.Control(control_id="ctl-x", document_id="RW-0005", categoria="nope",
                  descripcion_operativa="x")


# ── persistencia ─────────────────────────────────────────────────────────

def test_store_roundtrip_and_idempotent(tmp_path):
    store = CanonicalStore("RW-TEST", store_dir=tmp_path)
    doc = m.Document(document_id="RW-TEST", sha256="abc123", tipo="FS",
                     titulo="Functional Spec", n_paginas=10)
    store.put(doc)
    claim = m.build_claim("RW-TEST", 5, "The operator must authenticate before access.",
                          "control", "The operator must authenticate before access.")
    store.put(claim)
    store.put(claim)  # idempotente

    assert store.counts()["document"] == 1
    assert store.counts()["claim"] == 1
    got = store.all("claim")
    assert got[0]["source_text"] == "The operator must authenticate before access."
    assert got[0]["provenance"]["source_hash"] == m.sha256_text(got[0]["source_text"])
    store.close()


def test_store_put_validates_provenance_second_barrier(tmp_path):
    """`store.put` revalida provenance de objetos prov-bearing aunque el
    constructor ya lo haya hecho (segunda barrera). Se simula corrupción
    post-construcción."""
    store = CanonicalStore("RW-TEST2", store_dir=tmp_path)
    sec = m.build_section("RW-TEST2", "1", "Introduction", 1, 3, source_text="Intro real text")
    object.__setattr__(sec.provenance, "source_hash", "corrupted")
    with pytest.raises(m.ProvenanceError):
        store.put(sec)
    store.close()
