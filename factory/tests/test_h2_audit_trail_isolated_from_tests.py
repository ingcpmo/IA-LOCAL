"""H-2 — el audit trail productivo está aislado de la suite.

Diseño `DISENO_H1_H10_ACTUALIZADO_R0_R5_20260829`, EVIDENCIA_R = R-1 G-7
(la ruta se resolvía desde __file__ y el fixture isolated_audit NO era autouse).

Verifica:
  1. `isolated_audit` es autouse ⇒ en CUALQUIER test, `aw.AUDIT_FILE` NO resuelve
     bajo el repositorio (guard-test).
  2. Escribir eventos desde un test NO cambia el conteo de líneas del audit
     trail productivo.
  3. La ruta es INYECTABLE (env `FACTORY_AUDIT_FILE`), no una constante ciega.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import factory.core.audit_writer as aw

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PRODUCTIVE = _REPO_ROOT / "factory" / "audit" / "factory_audit.jsonl"


def _productive_line_count() -> int:
    if not _PRODUCTIVE.exists():
        return 0
    return sum(1 for ln in _PRODUCTIVE.read_text(encoding="utf-8").splitlines() if ln.strip())


def test_audit_file_does_not_resolve_under_the_repo_during_tests():
    """Guard-test: la autouse `isolated_audit` debe estar activa en todo test."""
    resolved = Path(aw.AUDIT_FILE).resolve()
    assert _REPO_ROOT not in resolved.parents, (
        f"aw.AUDIT_FILE resuelve BAJO el repositorio durante un test: {resolved}. "
        f"El fixture isolated_audit debe ser autouse y apuntar a tmp_path.")


def test_writing_events_from_a_test_does_not_touch_the_productive_trail():
    before = _productive_line_count()
    for i in range(25):
        aw.write_event("gates_executed", "h2_probe_project", {"i": i})
    after = _productive_line_count()
    assert after == before, (
        f"la suite escribió en el audit trail productivo: {before} -> {after}")
    # y los eventos SÍ se escribieron, pero en el fichero aislado
    assert Path(aw.AUDIT_FILE).exists()
    assert sum(1 for _ in Path(aw.AUDIT_FILE).read_text().splitlines()) >= 25


def test_default_audit_file_is_the_productive_path():
    """Sin env var, el default apunta al fichero productivo bajo el repo
    (la autouse lo redirige encima, pero el default original es ese)."""
    assert aw._DEFAULT_AUDIT_FILE.resolve() == _PRODUCTIVE.resolve()


def test_audit_file_is_injectable_via_env(monkeypatch, tmp_path):
    """FACTORY_AUDIT_FILE fija la ruta sin tocar código (recarga del módulo)."""
    import importlib
    target = tmp_path / "injected_audit.jsonl"
    monkeypatch.setenv("FACTORY_AUDIT_FILE", str(target))
    reloaded = importlib.reload(aw)
    try:
        assert Path(reloaded.AUDIT_FILE).resolve() == target.resolve()
    finally:
        monkeypatch.delenv("FACTORY_AUDIT_FILE", raising=False)
        importlib.reload(aw)  # restaura el estado del módulo para el resto de la suite
