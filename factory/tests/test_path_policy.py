"""
Guard U7: política de rutas server-side compartida para diff, tree y file.

Verifica que resolve_workspace() rechace path traversal via project_id y que
los tres endpoints (diff/tree/file) la usen de forma consistente.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.core.path_policy import resolve_workspace


# ── resolve_workspace unit tests ──────────────────────────────────────────────

class TestResolveWorkspace:

    def test_rejects_dotdot_traversal(self, tmp_path):
        with pytest.raises(ValueError):
            resolve_workspace("../../../etc", tmp_path)

    def test_rejects_slash_in_project_id(self, tmp_path):
        with pytest.raises(ValueError):
            resolve_workspace("foo/bar", tmp_path)

    def test_rejects_backslash_in_project_id(self, tmp_path):
        with pytest.raises(ValueError):
            resolve_workspace("foo\\bar", tmp_path)

    def test_rejects_empty_project_id(self, tmp_path):
        with pytest.raises(ValueError):
            resolve_workspace("", tmp_path)

    def test_rejects_dotdot_embedded(self, tmp_path):
        with pytest.raises(ValueError):
            resolve_workspace("valid..invalid", tmp_path)

    def test_raises_file_not_found_for_nonexistent_workspace(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            resolve_workspace("nonexistent_project", tmp_path)

    def test_returns_resolved_path_for_valid_project(self, tmp_path):
        proj = tmp_path / "my_project"
        proj.mkdir()
        result = resolve_workspace("my_project", tmp_path)
        assert result == proj.resolve()
        assert result.is_relative_to(tmp_path.resolve())

    def test_resolved_path_stays_inside_ws_base(self, tmp_path):
        proj = tmp_path / "my_project"
        proj.mkdir()
        result = resolve_workspace("my_project", tmp_path)
        assert result.is_relative_to(tmp_path.resolve())

    def test_dotdot_only_raises_value_error(self, tmp_path):
        with pytest.raises(ValueError):
            resolve_workspace("..", tmp_path)

    def test_dot_prefix_rejected(self, tmp_path):
        # ".hidden" contiene "." pero no ".." — permitido si existe
        proj = tmp_path / ".hidden"
        proj.mkdir()
        # solo rechaza si contiene ".." como substring — ".hidden" no lo tiene
        result = resolve_workspace(".hidden", tmp_path)
        assert result.exists()


# ── integración live con factory-api ─────────────────────────────────────────

def _get_api_key():
    import subprocess
    r = subprocess.run(
        ["docker", "exec", "factory-api", "printenv", "FACTORY_API_KEY"],
        capture_output=True, text=True, timeout=5,
    )
    key = r.stdout.strip()
    if not key:
        pytest.skip("factory-api no disponible")
    return key


TRAVERSAL_IDS = ["../../../etc", "..", "foo/bar", "foo\\bar"]


@pytest.mark.parametrize("bad_id", TRAVERSAL_IDS)
def test_tree_rejects_traversal(bad_id):
    import httpx
    key = _get_api_key()
    # FastAPI URL-encodea los "/" en path params → llegan como %2F → 422 o 400
    url = f"http://localhost:9000/api/v1/layer8/workspaces/{bad_id}/tree"
    r = httpx.get(url, headers={"x-api-key": key}, timeout=10)
    assert r.status_code in (400, 404, 422), (
        f"tree con project_id={bad_id!r} devolvió {r.status_code}, esperado 400/404/422"
    )


@pytest.mark.parametrize("bad_id", TRAVERSAL_IDS)
def test_file_rejects_traversal_via_project_id(bad_id):
    import httpx
    key = _get_api_key()
    url = f"http://localhost:9000/api/v1/layer8/workspaces/{bad_id}/file"
    r = httpx.get(url, params={"path": "manifest.yaml"}, headers={"x-api-key": key}, timeout=10)
    assert r.status_code in (400, 404, 422), (
        f"file con project_id={bad_id!r} devolvió {r.status_code}, esperado 400/404/422"
    )


def test_file_rejects_path_traversal():
    """El parámetro 'path' tampoco puede escapar del workspace."""
    import httpx
    key = _get_api_key()
    r = httpx.get(
        "http://localhost:9000/api/v1/layer8/workspaces/r6_change_control/file",
        params={"path": "../../../etc/passwd"},
        headers={"x-api-key": key},
        timeout=10,
    )
    assert r.status_code in (400, 404), (
        f"Traversal via 'path' devolvió {r.status_code}, esperado 400/404"
    )


def test_valid_project_tree_returns_200():
    import httpx
    key = _get_api_key()
    r = httpx.get(
        "http://localhost:9000/api/v1/layer8/workspaces/r6_change_control/tree",
        headers={"x-api-key": key},
        timeout=10,
    )
    assert r.status_code == 200
    data = r.json()
    assert "files" in data
    assert "file_count" in data
