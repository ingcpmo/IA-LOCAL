"""Tests -- factory/regulatory/findings/regulatory_tier1.py (Palanca C).

Modo Tier-1 para la clase Regulatory tras el 0/7 de B4b. CERO LLM.
Eco léxico anclado -> candidato a confirmación humana; todo lo demás ->
revisión humana con cobertura declarada. Nunca aprobación automática.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.canonical import model as m
from factory.regulatory.canonical.persistence import CanonicalStore
from factory.regulatory.findings import regulatory_tier1 as t1


def _seed(canon_dir, claims):
    with CanonicalStore("RW-0005", store_dir=canon_dir) as s:
        s.put(m.Document(document_id="RW-0005", sha256="x" * 64, tipo="FS",
                         titulo="FS", n_paginas=60))
        for pg, tx in claims:
            s.put(m.build_claim("RW-0005", pg, tx, "control", tx))
    return "RW-0005"


def test_lexical_echo_becomes_confirmed_candidate(tmp_path):
    canon_dir = tmp_path / "canon"
    # claim con eco léxico casi verbatim de un sub-criterio de 11.10(e)
    _seed(canon_dir, [
        (45, "cada entrada del audit trail registra fecha y hora del evento del operador"),
        (12, "la pantalla muestra la temperatura del reactor"),
    ])
    findings = t1.regulatory_tier1_findings(
        "RW-0005", ["21_CFR_11.10(e)"], extraction_version="v1", canon_dir=canon_dir)
    assert findings
    confirmed = [f for f in findings if f.machine_state == "MACHINE_CONFIRMED_FINDING"]
    assert confirmed, "algún sub-criterio con eco léxico debería quedar como candidato confirmado"
    c = confirmed[0]
    assert c.subtype == "REGULATORY_COMPLIANT_EVIDENCE"
    assert c.human_state == "UNREVIEWED"
    assert "NO es aprobación" in c.rationale
    assert "TIER-1" in c.rationale


def test_no_echo_goes_to_human_review_with_coverage_statement(tmp_path):
    canon_dir = tmp_path / "canon"
    _seed(canon_dir, [
        (30, "el operador puede acceder a la función de reset mediante su credencial"),
    ])
    findings = t1.regulatory_tier1_findings(
        "RW-0005", ["ALCOA_CONTEMPORANEOUS"], extraction_version="v1", canon_dir=canon_dir)
    assert findings
    for f in findings:
        assert f.machine_state == "MACHINE_INCONCLUSIVE"
        assert f.subtype == "REGULATORY_INCONCLUSIVE"
        assert f.human_state == "UNREVIEWED"
        assert "RECUPERACIÓN" in f.rationale
        assert "detección automática de evidencia PARAFRASEADA NO está incluida" in f.rationale


def test_never_emits_approval_states(tmp_path):
    canon_dir = tmp_path / "canon"
    _seed(canon_dir, [(45, "cada entrada del audit trail registra fecha y hora")])
    findings = t1.regulatory_tier1_findings(
        "RW-0005", ["21_CFR_11.10(e)", "21_CFR_11.10(g)"], extraction_version="v1",
        canon_dir=canon_dir)
    for f in findings:
        assert f.machine_state in ("MACHINE_CONFIRMED_FINDING", "MACHINE_INCONCLUSIVE")
        assert f.machine_state not in ("QA_APPROVED", "RELEASED", "CAPA_CLOSED", "FINAL_GMP_APPROVAL")
        assert f.human_state == "UNREVIEWED"


def test_zero_llm_calls(tmp_path, monkeypatch):
    """Si algo intentara llamar al provider, el test rompería -- aquí solo
    confirmamos que el módulo no importa ni usa judgment_v2/model_provider."""
    import factory.regulatory.findings.regulatory_tier1 as mod
    src = Path(mod.__file__).read_text()
    assert "model_provider" not in src
    assert "judgment_v2" not in src
    assert "provider" not in src
