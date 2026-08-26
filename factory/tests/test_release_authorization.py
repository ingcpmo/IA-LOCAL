"""Tests — factory/core/release_authorization.py (Decisión 2, 2026-08-26).

Control mínimo de autorización de liberación: fail-closed por diseño --
archivo ausente/vacío = NADIE autorizado, nunca "todos"."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.core import release_authorization as ra


def _write(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "release_authorized_identities.yaml"
    p.write_text(content, encoding="utf-8")
    return p


def test_missing_file_authorizes_nobody(tmp_path):
    p = tmp_path / "no_existe.yaml"
    assert ra.load_release_authorized_identities(path=p) == frozenset()
    assert ra.is_authorized_to_release("Cesar", path=p) is False


def test_empty_file_authorizes_nobody(tmp_path):
    p = _write(tmp_path, "")
    assert ra.load_release_authorized_identities(path=p) == frozenset()
    assert ra.is_authorized_to_release("Cesar", path=p) is False


def test_file_without_authorized_identities_key_authorizes_nobody(tmp_path):
    p = _write(tmp_path, "algo_distinto: [1, 2, 3]\n")
    assert ra.load_release_authorized_identities(path=p) == frozenset()


def test_listed_identity_is_authorized(tmp_path):
    p = _write(tmp_path, "authorized_identities:\n  - Cesar\n  - QA_Lead\n")
    assert ra.is_authorized_to_release("Cesar", path=p) is True
    assert ra.is_authorized_to_release("QA_Lead", path=p) is True


def test_unlisted_identity_is_not_authorized(tmp_path):
    p = _write(tmp_path, "authorized_identities:\n  - Cesar\n")
    assert ra.is_authorized_to_release("OtroRevisor", path=p) is False


def test_comparison_is_exact_not_case_insensitive(tmp_path):
    """Mismo criterio que identity_policy.validate_identity(): el nombre
    real no se normaliza -- 'cesar' no es 'Cesar'."""
    p = _write(tmp_path, "authorized_identities:\n  - Cesar\n")
    assert ra.is_authorized_to_release("cesar", path=p) is False
    assert ra.is_authorized_to_release("CESAR", path=p) is False


def test_empty_or_none_name_is_never_authorized(tmp_path):
    p = _write(tmp_path, "authorized_identities:\n  - Cesar\n  - ''\n")
    assert ra.is_authorized_to_release("", path=p) is False
    assert ra.is_authorized_to_release(None, path=p) is False


def test_real_config_file_lists_only_cesar():
    """El archivo real desplegado (factory/config/release_authorized_
    identities.yaml, versionado -- sin datos sensibles) arranca con
    exactamente Cesar autorizado, decisión explícita de Capa 9."""
    assert ra.load_release_authorized_identities() == frozenset({"Cesar"})
