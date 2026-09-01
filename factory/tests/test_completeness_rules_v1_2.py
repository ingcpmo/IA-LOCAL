"""D5-D analyzer remediation -- reglas de completitud tecnica v1.2.

Fixtures NUEVOS, independientes de los casos held-out HO-T-* (contaminados para tuning):
redaccion distinta, mismos 3 mecanismos.

  1A  C03  topic_anchor_patterns          -- parafrasis de backup sin la palabra literal
  1B  C05  topic_anchor_patterns + acote  -- modelo de roles/autorizacion parafraseado;
                                             mecanismo de auth ("login") NO basta;
                                             suprimido si per_operation_authorization presente
  3C  C04  incidental_anchor_guard        -- token debil "role" incidental en frase de otro control
          family:access_control_enforced  -- evidencia afirmativa suprime C04

Determinista, 0 LLM. Corre contra el artefacto VIVO firmado (v1.2).
"""
from __future__ import annotations

import pytest

from factory.regulatory.canonical import model as m
from factory.regulatory.canonical.persistence import CanonicalStore
from factory.regulatory.findings import technical_findings as tf


def _subs(canon_dir, did, tipo, claims):
    with CanonicalStore(did, store_dir=canon_dir) as s:
        s.put(m.Document(document_id=did, sha256="x" * 64, tipo=tipo, titulo=tipo, n_paginas=40))
        for pg, ct, cx in claims:
            s.put(m.build_claim(did, pg, cx, ct, cx[:180]))
    fs = tf.completeness_findings([did], extraction_version="v1", canon_dir=canon_dir)
    return {f.subtype for f in fs}, fs


# ---------------------------------------------------------------------------
# 1A -- C03 BACKUP_RECOVERY_GAP : parafrasis
# ---------------------------------------------------------------------------
def test_c03_paraphrase_cadence_emits(tmp_path):
    subs, _ = _subs(tmp_path / "a", "T1", "FS", [
        (11, "function", "Application data is exported to a secondary server every night."),
    ])
    assert "BACKUP_RECOVERY_GAP" in subs


def test_c03_paraphrase_destination_emits(tmp_path):
    subs, _ = _subs(tmp_path / "b", "T2", "FS", [
        (11, "function", "Database records are replicated to an offsite storage location "
                         "on a scheduled basis."),
    ])
    assert "BACKUP_RECOVERY_GAP" in subs


def test_c03_isolated_copy_is_not_backup(tmp_path):
    subs, _ = _subs(tmp_path / "c", "T3", "FS", [
        (11, "function", "The shift report is copied to the control room printer at end of shift."),
    ])
    assert "BACKUP_RECOVERY_GAP" not in subs


def test_c03_isolated_network_is_not_backup(tmp_path):
    subs, _ = _subs(tmp_path / "d", "T4", "FS", [
        (11, "function", "The engineering workstation is connected to the plant network switch."),
    ])
    assert "BACKUP_RECOVERY_GAP" not in subs


def test_c03_literal_backup_still_emits(tmp_path):
    """regresion: el anchor literal de v1.1 sigue funcionando."""
    subs, _ = _subs(tmp_path / "e", "T5", "FS", [
        (11, "function", "A nightly backup of the application database is performed."),
    ])
    assert "BACKUP_RECOVERY_GAP" in subs


def test_c03_backup_with_restore_verification_suppressed(tmp_path):
    """regresion: backup CON verificacion de restauracion -> sin hueco."""
    subs, _ = _subs(tmp_path / "f", "T6", "FS", [
        (11, "function", "Application data is copied nightly to an offsite server, and the "
                         "restore procedure is tested during validation and re-verified periodically."),
    ])
    assert "BACKUP_RECOVERY_GAP" not in subs


# ---------------------------------------------------------------------------
# 1B -- C05 AUTHORITY_CHECK_GAP : modelo de roles/autorizacion
# ---------------------------------------------------------------------------
def test_c05_role_model_without_operation_authority_check_emits(tmp_path):
    subs, _ = _subs(tmp_path / "g", "T7", "FS", [
        (14, "function", "Four distinct operator roles are configured in the HMI application."),
    ])
    assert "AUTHORITY_CHECK_GAP" in subs


def test_c05_security_levels_defined_emits(tmp_path):
    subs, _ = _subs(tmp_path / "h", "T8", "FS", [
        (14, "function", "Security levels are defined for the SCADA project and assigned per user."),
    ])
    assert "AUTHORITY_CHECK_GAP" in subs


def test_c05_login_password_only_no_false_positive(tmp_path):
    subs, _ = _subs(tmp_path / "i", "T9", "FS", [
        (14, "function", "Users sign in to the application with a username and a password."),
    ])
    assert "AUTHORITY_CHECK_GAP" not in subs


def test_c05_incidental_role_no_false_positive(tmp_path):
    subs, _ = _subs(tmp_path / "j", "T10", "FS", [
        (14, "function", "The retention period is fixed at ten years and stored records "
                         "cannot be shortened or removed by any role."),
    ])
    assert "AUTHORITY_CHECK_GAP" not in subs


def test_c05_role_model_with_explicit_operation_authority_check_suppressed(tmp_path):
    subs, _ = _subs(tmp_path / "k", "T11", "FS", [
        (14, "function", "Several user roles exist; the system verifies the operator's authority "
                         "before executing each critical operation."),
    ])
    assert "AUTHORITY_CHECK_GAP" not in subs


def test_c05_role_model_with_per_operation_authorization_suppressed(tmp_path):
    subs, _ = _subs(tmp_path / "l", "T12", "FS", [
        (14, "function", "Named roles are configured; the authorization level required for each "
                         "operation is defined per role."),
    ])
    assert "AUTHORITY_CHECK_GAP" not in subs


def test_c05_role_based_access_literal_still_emits(tmp_path):
    """regresion: el anchor literal 'role based access' de v1.1 sigue funcionando."""
    subs, _ = _subs(tmp_path / "m", "T13", "FS", [
        (16, "function", "The system enforces role based access for the operator interface."),
    ])
    assert "AUTHORITY_CHECK_GAP" in subs


# ---------------------------------------------------------------------------
# 3C -- C04 ACCESS_CONTROL_GAP : ancla incidental / evidencia afirmativa
# ---------------------------------------------------------------------------
def test_c04_genuine_access_control_gap_still_detected(tmp_path):
    subs, _ = _subs(tmp_path / "n", "T14", "FS", [
        (15, "function", "Three roles are available in the system: Viewer, Operator and Engineer."),
    ])
    assert "ACCESS_CONTROL_GAP" in subs


def test_c04_audit_trail_immutability_by_any_role_no_false_positive(tmp_path):
    subs, _ = _subs(tmp_path / "o", "T15", "FS", [
        (12, "function", "The audit trail cannot be modified or disabled by any role, "
                         "including administrators."),
    ])
    assert "ACCESS_CONTROL_GAP" not in subs


def test_c04_electronic_signature_incidental_role_no_false_positive(tmp_path):
    subs, _ = _subs(tmp_path / "p", "T16", "FS", [
        (12, "function", "The electronic signature manifest cannot be edited by any user role."),
    ])
    assert "ACCESS_CONTROL_GAP" not in subs


def test_c04_per_operation_authorization_still_suppresses(tmp_path):
    """regresion: si la autorizacion por operacion esta descrita -> sin hueco C04."""
    subs, _ = _subs(tmp_path / "q", "T17", "FS", [
        (15, "function", "Roles are defined and the privileges are defined per role for each "
                         "operation and reviewed periodically."),
    ])
    assert "ACCESS_CONTROL_GAP" not in subs


# ---------------------------------------------------------------------------
# contaminacion / diagnostico -- NO es gate
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("case_text,expect_subtype", [
    ("System data is copied to a network share periodically.", "BACKUP_RECOVERY_GAP"),   # HO-T-002 style
])
def test_diagnostic_remediation_check_ho_t_002_now_detected(tmp_path, case_text, expect_subtype):
    """DIAGNOSTIC_REMEDIATION_CHECK -- reproduce el FN HO-T-002 con la redaccion contaminada.
    Solo diagnostico: NUNCA cuenta como gate (held-out contaminado)."""
    subs, _ = _subs(tmp_path / "r", "T18", "FS", [(14, "function", case_text)])
    assert expect_subtype in subs
