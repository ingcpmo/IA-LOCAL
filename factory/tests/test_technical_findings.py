"""Tests -- factory/regulatory/findings/technical_findings.py (V2, B6b v1 + v2).

DETERMINISTA, sin LLM:
  - B6b v1: INTERFACE_INCONSISTENCY, ORPHAN_DESIGN_ELEMENT (grafo).
  - B6b v2: reglas de COMPLETITUD del artefacto GOBERNADO firmado
    `technical_completeness_rules.yaml` ("tema obligatorio presente +
    comportamiento requerido ausente"). Sin criptografía forzada, sin
    implementaciones concretas como requisito, revisión humana siempre.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.canonical import model as m
from factory.regulatory.canonical.persistence import CanonicalStore
from factory.regulatory.findings import technical_findings as tf
from factory.regulatory.graph import build as gb


def _seed(canon_dir, did, tipo, claims, tests=None):
    with CanonicalStore(did, store_dir=canon_dir) as s:
        s.put(m.Document(document_id=did, sha256="x" * 64, tipo=tipo, titulo=tipo, n_paginas=40))
        for pg, tp, tx in claims:
            s.put(m.build_claim(did, pg, tx, tp, tx[:180]))
        for pg, ident, desc in (tests or []):
            s.put(m.build_test(did, pg, ident, desc))


def test_interface_inconsistency_modal_opposite(tmp_path):
    canon_dir, graph_dir = tmp_path / "c", tmp_path / "g"
    _seed(canon_dir, "T-DS1", "DS", [
        (9, "control", "For interface IF-EMS-WFI-07 on communication failure the system shall "
                       "hold the last known value."),
    ])
    _seed(canon_dir, "T-DS2", "DS", [
        (7, "control", "For interface IF-EMS-WFI-07 on communication failure the system shall "
                       "not hold the last known value and shall force outputs to a safe state."),
    ])
    docs = [("T-DS1", "DS"), ("T-DS2", "DS")]
    gb.build_project_graph("PRJ-IFM", docs, canon_dir=canon_dir, graph_dir=graph_dir)
    findings = tf.graph_technical_findings("PRJ-IFM", [d for d, _ in docs],
                                          extraction_version="v1", canon_dir=canon_dir,
                                          graph_dir=graph_dir)
    ii = [f for f in findings if f.subtype == "INTERFACE_INCONSISTENCY"]
    assert len(ii) == 1
    f = ii[0]
    assert f.finding_class == "TechnicalFinding"
    assert "IF-EMS-WFI-07" in f.source_text
    assert f.human_state == "UNREVIEWED"
    assert f.machine_state == "MACHINE_DEVIATION_CANDIDATE"
    assert "modal_opposite" in f.rationale
    assert f.provenance.graph_path[1] == "refers_to"


def test_interface_inconsistency_parameter_value(tmp_path):
    canon_dir, graph_dir = tmp_path / "c", tmp_path / "g"
    _seed(canon_dir, "T-FS", "FS", [
        (30, "function", "For interface IF-PCS-SCADA-01 the SCADA polling interval shall be 500 ms."),
    ])
    _seed(canon_dir, "T-DS", "DS", [
        (8, "control", "For interface IF-PCS-SCADA-01 the SCADA polling interval shall be 1000 ms."),
    ])
    docs = [("T-FS", "FS"), ("T-DS", "DS")]
    gb.build_project_graph("PRJ-IFP", docs, canon_dir=canon_dir, graph_dir=graph_dir)
    findings = tf.graph_technical_findings("PRJ-IFP", [d for d, _ in docs],
                                          extraction_version="v1", canon_dir=canon_dir,
                                          graph_dir=graph_dir)
    ii = [f for f in findings if f.subtype == "INTERFACE_INCONSISTENCY"]
    assert len(ii) == 1
    assert "parameter_value" in ii[0].rationale
    assert "500 ms" in ii[0].source_text or "1000 ms" in ii[0].source_text


def test_no_interface_finding_when_consistent(tmp_path):
    """Mismo identificador en dos docs pero SIN divergencia -> nada."""
    canon_dir, graph_dir = tmp_path / "c", tmp_path / "g"
    _seed(canon_dir, "T-FS", "FS", [
        (30, "function", "For interface IF-PCS-SCADA-01 the SCADA polling interval shall be 500 ms."),
    ])
    _seed(canon_dir, "T-DS", "DS", [
        (8, "control", "Interface IF-PCS-SCADA-01 uses the SCADA polling interval of 500 ms as specified."),
    ])
    docs = [("T-FS", "FS"), ("T-DS", "DS")]
    gb.build_project_graph("PRJ-OK", docs, canon_dir=canon_dir, graph_dir=graph_dir)
    findings = tf.graph_technical_findings("PRJ-OK", [d for d, _ in docs],
                                          extraction_version="v1", canon_dir=canon_dir,
                                          graph_dir=graph_dir)
    assert [f for f in findings if f.subtype == "INTERFACE_INCONSISTENCY"] == []


def _completeness(canon_dir, did, tipo, claims):
    _seed(canon_dir, did, tipo, claims)
    return tf.completeness_findings([did], extraction_version="v1", canon_dir=canon_dir)


def _live_artifact():
    from factory.regulatory.requirement_catalog import technical_completeness_loader as tcl
    return tcl.load_signed_rules()          # v1.1 SIGNED, context_scoped


def _as_v10(art: dict) -> dict:
    """Emula el alcance v1.0 (document_wide) sobre el artefacto vivo:
    misma reglas/family_signals, sin scope_policy."""
    return {**art, "scope_policy": None}


def _seed_sectioned(canon_dir, did, tipo, sections):
    """sections = [(numero, titulo, pag, [(pag, tipo, texto), ...]), ...]"""
    with CanonicalStore(did, store_dir=canon_dir) as s:
        s.put(m.Document(document_id=did, sha256="x" * 64, tipo=tipo, titulo=tipo, n_paginas=80))
        for numero, titulo, pag, claims in sections:
            sec = m.build_section(did, numero, titulo, pag, pag + 5)
            s.put(sec)
            for cp, ct, cx in claims:
                s.put(m.build_claim(did, cp, cx, ct, cx[:180], section_id=sec.section_id))


def test_completeness_rule_emits_on_topic_present_behavior_absent(tmp_path):
    """B6b v2: 'audit trail' presente + sin protección contra modificación
    privilegiada -> AUDIT_TRAIL_DESIGN_GAP, revisión humana, nunca auto-confirmado."""
    findings = _completeness(tmp_path / "c", "T-FS", "FS", [
        (12, "function", "The audit trail records every change made to critical process parameters."),
        (14, "function", "A nightly backup of the application database is performed automatically."),
    ])
    st = {f.subtype: f for f in findings}
    assert "AUDIT_TRAIL_DESIGN_GAP" in st
    assert "BACKUP_RECOVERY_GAP" in st           # backup sin prueba de restore
    a = st["AUDIT_TRAIL_DESIGN_GAP"]
    assert a.finding_class == "TechnicalFinding"
    assert a.human_state == "UNREVIEWED"
    assert a.machine_state == "MACHINE_DEVIATION_CANDIDATE"
    assert a.technical_basis == "21_CFR_11.10(e)"
    assert a.provenance.agent_id == "technical_design_agent"


def test_completeness_c09_does_not_require_cryptography(tmp_path):
    """C09: un control NO criptográfico (append-only + alarma) satisface el
    comportamiento -> no se emite AUDIT_TRAIL_INTEGRITY_GAP. La regla nunca
    exige hash/HMAC/SHA/firma digital."""
    findings = _completeness(tmp_path / "c", "T-FS", "FS", [
        (12, "function", "The audit trail is append-only; any attempt to modify audit records "
                         "is logged and alarmed, so tampering with the audit trail is detected."),
    ])
    subs = {f.subtype for f in findings}
    assert "AUDIT_TRAIL_INTEGRITY_GAP" not in subs
    assert "AUDIT_TRAIL_DESIGN_GAP" not in subs   # append-only cubre la protección privilegiada


def test_completeness_suppressed_when_behavior_present(tmp_path):
    """Si el comportamiento requerido está descrito (aunque parafraseado),
    la regla NO emite -- sin falso positivo."""
    findings = _completeness(tmp_path / "c", "T-FSOK", "FS", [
        (40, "function", "Electronic records are retained for seven years; their accessibility, "
                         "legibility and integrity are verified annually."),
        (41, "function", "Privileges are defined per role for each operation and reviewed."),
        (42, "function", "The ability to restore the database from backup is tested during validation."),
    ])
    subs = {f.subtype for f in findings}
    assert "TECHNICAL_DESIGN_GAP" not in subs      # retención con verificación
    assert "ACCESS_CONTROL_GAP" not in subs        # autorización por operación descrita
    assert "BACKUP_RECOVERY_GAP" not in subs       # restore verificado


def test_completeness_cross_reference_suppressor(tmp_path):
    """Si el claim del tema remite el comportamiento a otro documento -> se
    suprime (es un puntero, no un hueco)."""
    findings = _completeness(tmp_path / "c", "T-FS", "FS", [
        (10, "function", "Backup and restore verification is covered by document INFRA-BR-001; "
                         "see document INFRA-BR-001 for the restore test evidence."),
    ])
    assert all(f.subtype != "BACKUP_RECOVERY_GAP" for f in findings)


def test_completeness_rtorpo_never_required_for_c03(tmp_path):
    """C03: solo se exige la verificación de restore. Un backup con restore
    verificado NO se marca aunque no mencione RTO/RPO."""
    findings = _completeness(tmp_path / "c", "T-FS", "FS", [
        (10, "function", "A nightly backup is performed and the restore procedure is tested "
                         "during validation and re-verified periodically."),
    ])
    assert all(f.subtype != "BACKUP_RECOVERY_GAP" for f in findings)


def test_completeness_fail_closed_when_artifact_not_signed(tmp_path, monkeypatch):
    """Si el artefacto de reglas no está SIGNED, B6b v2 no emite nada."""
    from factory.regulatory.requirement_catalog import technical_completeness_loader as tcl
    monkeypatch.setattr(tcl, "is_signed", lambda: False)
    findings = _completeness(tmp_path / "c", "T-FS", "FS", [
        (12, "function", "The audit trail records every change made to critical process parameters."),
    ])
    assert findings == []


# ---- OD-6: alcance context-scoped (artefacto v1.1 FIRMADO) ----

_TWO_SEC = [
    ("3", "Functions", 20, [
        (20, "function", "The system audit report shows that configuration files "
                         "cannot be modified without administrator rights."),
    ]),
    ("5", "Data", 45, [
        (45, "function", "The audit trail records every change made to critical process "
                         "parameters, including user id and timestamp."),
    ]),
]


def test_od6_v10_document_wide_false_suppresses_real_gap(tmp_path):
    """Emulación v1.0 (document-wide): una frase NO relacionada en otra
    Section ('audit ... cannot be modified' sobre config files) SUPRIME el
    gap real del audit trail. Es el defecto que OD-6 corrige."""
    canon = tmp_path / "c"
    _seed_sectioned(canon, "T-FS", "FS", _TWO_SEC)
    findings = tf.completeness_findings(["T-FS"], extraction_version="v1", canon_dir=canon,
                                        rules_artifact=_as_v10(_live_artifact()))
    assert all(f.subtype != "AUDIT_TRAIL_DESIGN_GAP" for f in findings)


def test_od6_v11_context_scoped_emits_real_gap(tmp_path):
    """v1.1 FIRMADO (context_scoped, artefacto vivo): la misma frase no
    relacionada en otra Section NO suprime; el gap real SE EMITE. Un
    negativo real DENTRO de la misma Section sigue suprimiendo."""
    art = _live_artifact()
    assert art["scope_policy"]["behavior_search"] == "context_scoped"

    canon = tmp_path / "c"
    _seed_sectioned(canon, "T-FS", "FS", _TWO_SEC)
    stats: dict = {}
    findings = tf.completeness_findings(["T-FS"], extraction_version="v1", canon_dir=canon,
                                       stats=stats)
    assert stats["completeness_scope"] == "context_scoped"
    assert "AUDIT_TRAIL_DESIGN_GAP" in {f.subtype for f in findings}

    _seed_sectioned(canon / "ok", "T-OK", "FS", [
        ("5", "Data", 45, [
            (45, "function", "The audit trail records every change, and the audit trail "
                             "cannot be modified or disabled by any user role."),
        ]),
    ])
    ok = tf.completeness_findings(["T-OK"], extraction_version="v1", canon_dir=canon / "ok")
    assert all(f.subtype != "AUDIT_TRAIL_DESIGN_GAP" for f in ok)


def test_od6_v11_still_fail_closed_and_keeps_xref_suppressors(tmp_path):
    """v1.1 mantiene fail-closed y los cross_reference_suppressors intactos."""
    from factory.regulatory.requirement_catalog import technical_completeness_loader as tcl
    canon = tmp_path / "c"
    # fail-closed: si el artefacto no está SIGNED -> no emite nada
    _seed_sectioned(canon, "T-FC", "FS", [
        ("5", "Data", 45, [(45, "function", "The audit trail records every change.")]),
    ])
    import unittest.mock as _mock
    with _mock.patch.object(tcl, "is_signed", lambda: False):
        assert tf.completeness_findings(["T-FC"], extraction_version="v1", canon_dir=canon) == []
    # cross-reference suppressor sigue operando bajo v1.1
    _seed_sectioned(canon / "x", "T-XR", "FS", [
        ("5", "Data", 45, [
            (45, "function", "Backup and restore verification is covered by document "
                             "INFRA-BR-001; see document INFRA-BR-001."),
        ]),
    ])
    findings = tf.completeness_findings(["T-XR"], extraction_version="v1", canon_dir=canon / "x")
    assert all(f.subtype != "BACKUP_RECOVERY_GAP" for f in findings)


def test_orphan_design_element(tmp_path):
    """Claim de diseño con identificador propio, sin test y sin upstream -> ORPHAN."""
    canon_dir, graph_dir = tmp_path / "c", tmp_path / "g"
    _seed(canon_dir, "T-DS", "DS", [
        (5, "control", "DE-CTRL-42 The auxiliary trend buffer shall retain 24 hours of samples in RAM."),
    ])
    docs = [("T-DS", "DS")]
    gb.build_project_graph("PRJ-ORPH", docs, canon_dir=canon_dir, graph_dir=graph_dir)
    findings = tf.graph_technical_findings("PRJ-ORPH", [d for d, _ in docs],
                                          extraction_version="v1", canon_dir=canon_dir,
                                          graph_dir=graph_dir)
    orph = [f for f in findings if f.subtype == "ORPHAN_DESIGN_ELEMENT"]
    assert orph
    assert orph[0].finding_class == "TraceabilityFinding"
    assert "DE-CTRL-42" in orph[0].source_text
    assert orph[0].machine_state == "MACHINE_INCONCLUSIVE"


def test_orphan_suppressed_when_tested(tmp_path):
    canon_dir, graph_dir = tmp_path / "c", tmp_path / "g"
    _seed(canon_dir, "T-DS", "DS", [
        (5, "control", "DE-CTRL-42 The auxiliary trend buffer shall retain 24 hours of samples in RAM."),
    ])
    _seed(canon_dir, "T-SAT", "SAT", [], tests=[
        (3, "SAT-42", "Test case SAT-42: verify DE-CTRL-42 retains 24 hours of samples."),
    ])
    docs = [("T-DS", "DS"), ("T-SAT", "SAT")]
    gb.build_project_graph("PRJ-ORPH2", docs, canon_dir=canon_dir, graph_dir=graph_dir)
    findings = tf.graph_technical_findings("PRJ-ORPH2", [d for d, _ in docs],
                                          extraction_version="v1", canon_dir=canon_dir,
                                          graph_dir=graph_dir)
    assert [f for f in findings if f.subtype == "ORPHAN_DESIGN_ELEMENT"] == []


def test_suite_c_dry_run_with_b6b_v2(tmp_path):
    """Dry-run de Suite C con B6b v1 + v2 (artefacto de reglas FIRMADO).
    9 objetivos deterministas detectados (7 completitud + 2 interfaz), 0
    falsos positivos, gate ORIGINAL en verde. C07 (SEMANTIC) sigue MISS --
    NO se relaja el gate ni se reclasifica."""
    from factory.regulatory.validation_v2.technical_suite_c import run_suite_c_dry

    r = run_suite_c_dry(tmp_path / "c", tmp_path / "g")
    assert r["VALID_POSITIVE_CASES"] == ["C01", "C03", "C04", "C05", "C06",
                                         "C07", "C08", "C09", "C10", "C12"]
    assert r["DETERMINISTIC_TARGET_CASES"] == ["C01", "C03", "C04", "C05", "C06",
                                               "C08", "C09", "C10", "C12"]
    assert r["SEMANTIC_CASES"] == ["C07"]
    assert r["NOT_APPLICABLE_CASES"] == ["C02", "C11", "C13"]
    assert r["PROJECTED_MAX_DETERMINISTIC_RECALL"] == 0.9

    assert r["DETECTED_NOW"] == ["C01", "C03", "C04", "C05", "C06",
                                 "C08", "C09", "C10", "C12"]
    assert r["recall_now"] == 0.9
    assert r["n_false_positives"] == 0
    assert r["MISSED_DETERMINISTIC_TARGET_PENDING_V2"] == []
    assert r["MISSED_SEMANTIC_OUT_OF_SCOPE"] == ["C07"]
    assert r["stats"]["completeness_artifact_signed"] is True
    assert r["stats"]["completeness_emitted"] == 7
    # v1.2 (D5-D remediation): C05 ahora ancla tambien sobre el negativo C15 via el tier
    # `topic_anchor_patterns` de modelo de roles ("Roles are defined ...") y se SUPRIME
    # correctamente porque `per_operation_authorization` esta presente en ese scope
    # -> +1 supresion. Sin cambios en findings emitidos (7), 0 falsos positivos, recall 0.9.
    assert r["stats"]["completeness_suppressed_family_present"] == 5

    gates = {g["name"]: g for g in r["gate_report"]["gates"]}
    assert gates["TECHNICAL_RECALL"]["passed"] is True     # 0.90 >= 0.90
    assert gates["TECHNICAL_FALSE_POSITIVE"]["passed"] is True
    assert r["gate_report"]["all_passed"] is True
