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

from factory.core.path_policy import (
    resolve_workspace, resolve_design, resolve_rc_artifact, resolve_deployment,
)


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
        "http://localhost:9000/api/v1/layer8/workspaces/c8_alcoa_validator/tree",
        headers={"x-api-key": key},
        timeout=10,
    )
    assert r.status_code == 200
    data = r.json()
    assert "files" in data
    assert "file_count" in data


# ── U9: headless/logs, artifacts y jobs UUID ──────────────────────────────────

@pytest.mark.parametrize("bad_id", TRAVERSAL_IDS)
def test_headless_logs_rejects_traversal(bad_id):
    import httpx
    key = _get_api_key()
    url = f"http://localhost:9000/api/v1/layer8/missions/{bad_id}/headless/logs"
    r = httpx.get(url, headers={"x-api-key": key}, timeout=10)
    assert r.status_code in (400, 404, 422), (
        f"headless/logs con project_id={bad_id!r} devolvió {r.status_code}"
    )


@pytest.mark.parametrize("bad_id", TRAVERSAL_IDS)
def test_artifacts_rejects_traversal(bad_id):
    import httpx
    key = _get_api_key()
    url = f"http://localhost:9000/api/v1/layer8/missions/{bad_id}/artifacts"
    r = httpx.get(url, headers={"x-api-key": key}, timeout=10)
    assert r.status_code in (400, 404, 422), (
        f"artifacts con project_id={bad_id!r} devolvió {r.status_code}"
    )


def test_headless_logs_response_has_no_absolute_path():
    """La respuesta de headless/logs no debe exponer rutas absolutas del filesystem."""
    import httpx
    key = _get_api_key()
    r = httpx.get(
        "http://localhost:9000/api/v1/layer8/missions/c8_alcoa_validator/headless/logs",
        headers={"x-api-key": key},
        timeout=10,
    )
    assert r.status_code == 200
    data = r.json()
    for log in data.get("logs", []):
        assert "path" not in log, (
            f"Campo 'path' expone ruta absoluta del FS: {log.get('path')}"
        )


def test_jobs_rejects_non_uuid_id():
    """GET /jobs/{job_id} debe rechazar IDs que no sean UUID válidos.

    Rutas con '/' son interceptadas por el router antes del handler (404).
    IDs sin '/' pero con formato inválido llegan al handler y reciben 400.
    En todos los casos no se sirve contenido sensible.
    """
    import httpx
    key = _get_api_key()
    # IDs con '/' → FastAPI los rutea como multi-segmento → 404 del router
    # IDs sin '/' pero no UUID → llegan al handler → 400
    for bad_id in ["../../../etc/passwd", "foo", "123", "notauuid"]:
        r = httpx.get(
            f"http://localhost:9000/api/v1/layer8/jobs/{bad_id}",
            headers={"x-api-key": key},
            timeout=10,
        )
        assert r.status_code in (400, 404, 422), (
            f"jobs/{bad_id!r} devolvió {r.status_code}, esperado 400/404/422"
        )


def test_valid_artifacts_returns_200():
    import httpx
    key = _get_api_key()
    r = httpx.get(
        "http://localhost:9000/api/v1/layer8/missions/c8_alcoa_validator/artifacts",
        headers={"x-api-key": key},
        timeout=10,
    )
    assert r.status_code == 200
    data = r.json()
    assert "artifacts" in data
    assert "project_id" in data


# ── W3: resolve_design unit tests ─────────────────────────────────────────────

class TestResolveDesign:

    def test_rejects_traversal_in_project_id(self, tmp_path):
        with pytest.raises(ValueError):
            resolve_design("../../../etc", tmp_path)

    def test_rejects_dotdot_in_project_id(self, tmp_path):
        with pytest.raises(ValueError):
            resolve_design("..", tmp_path)

    def test_returns_design_dir_without_path(self, tmp_path):
        d = tmp_path / "my_project"
        d.mkdir()
        result = resolve_design("my_project", tmp_path)
        assert result == d.resolve()

    def test_rejects_non_design_extension(self, tmp_path):
        d = tmp_path / "my_project"
        d.mkdir()
        (d / "script.py").write_text("x")
        with pytest.raises(PermissionError):
            resolve_design("my_project", tmp_path, "script.py")

    def test_allows_yaml_extension(self, tmp_path):
        d = tmp_path / "my_project"
        d.mkdir()
        (d / "spec.yaml").write_text("key: val")
        result = resolve_design("my_project", tmp_path, "spec.yaml")
        assert result.name == "spec.yaml"

    def test_rejects_traversal_in_relative_path(self, tmp_path):
        d = tmp_path / "my_project"
        d.mkdir()
        with pytest.raises((ValueError, PermissionError)):
            resolve_design("my_project", tmp_path, "../../../etc/passwd")

    def test_rejects_secret_part_in_path(self, tmp_path):
        d = tmp_path / "my_project"
        d.mkdir()
        with pytest.raises(PermissionError):
            resolve_design("my_project", tmp_path, ".env.yaml")

    def test_nonexistent_design_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            resolve_design("missing_project", tmp_path)


# ── W3: resolve_rc_artifact unit tests ────────────────────────────────────────

class TestResolveRcArtifact:

    def test_rejects_traversal_in_project_id(self, tmp_path):
        with pytest.raises(ValueError):
            resolve_rc_artifact("../x", "rc_id", tmp_path)

    def test_rejects_traversal_in_rc_id(self, tmp_path):
        p = tmp_path / "my_project"
        p.mkdir()
        with pytest.raises(ValueError):
            resolve_rc_artifact("my_project", "../other_rc", tmp_path)

    def test_returns_rc_dir_without_path(self, tmp_path):
        rc_dir = tmp_path / "my_project" / "my_rc"
        rc_dir.mkdir(parents=True)
        result = resolve_rc_artifact("my_project", "my_rc", tmp_path)
        assert result == rc_dir.resolve()

    def test_rejects_path_outside_rc_id(self, tmp_path):
        rc_a = tmp_path / "proj" / "rc_a"
        rc_b = tmp_path / "proj" / "rc_b"
        rc_a.mkdir(parents=True)
        rc_b.mkdir(parents=True)
        (rc_b / "secret.json").write_text("{}")
        with pytest.raises((ValueError, PermissionError)):
            resolve_rc_artifact("proj", "rc_a", tmp_path, "../rc_b/secret.json")

    def test_allows_json_in_rc_dir(self, tmp_path):
        rc_dir = tmp_path / "proj" / "my_rc"
        rc_dir.mkdir(parents=True)
        (rc_dir / "manifest.json").write_text("{}")
        result = resolve_rc_artifact("proj", "my_rc", tmp_path, "manifest.json")
        assert result.name == "manifest.json"

    def test_rejects_disallowed_extension(self, tmp_path):
        rc_dir = tmp_path / "proj" / "my_rc"
        rc_dir.mkdir(parents=True)
        with pytest.raises(PermissionError):
            resolve_rc_artifact("proj", "my_rc", tmp_path, "script.py")


# ── W3: resolve_deployment unit tests ────────────────────────────────────────

class TestResolveDeployment:

    def test_rejects_traversal_in_project_id(self, tmp_path):
        with pytest.raises(ValueError):
            resolve_deployment("../x", tmp_path)

    def test_returns_dep_dir_without_path(self, tmp_path):
        d = tmp_path / "my_project"
        d.mkdir()
        result = resolve_deployment("my_project", tmp_path)
        assert result == d.resolve()

    def test_blocks_dotenv(self, tmp_path):
        d = tmp_path / "my_project"
        d.mkdir()
        with pytest.raises(PermissionError):
            resolve_deployment("my_project", tmp_path, ".env")

    def test_blocks_data_directory(self, tmp_path):
        d = tmp_path / "my_project"
        d.mkdir()
        with pytest.raises(PermissionError):
            resolve_deployment("my_project", tmp_path, "data/chroma/index.json")

    def test_blocks_releases_directory(self, tmp_path):
        d = tmp_path / "my_project"
        d.mkdir()
        with pytest.raises(PermissionError):
            resolve_deployment("my_project", tmp_path, "releases/v0.3.0.json")

    def test_blocks_knowledge_corpus(self, tmp_path):
        d = tmp_path / "my_project"
        d.mkdir()
        with pytest.raises(PermissionError):
            resolve_deployment("my_project", tmp_path, "knowledge/corpus/doc.md")

    def test_blocks_traversal_in_relative_path(self, tmp_path):
        d = tmp_path / "my_project"
        d.mkdir()
        with pytest.raises((ValueError, PermissionError)):
            resolve_deployment("my_project", tmp_path, "../../../etc/passwd")

    def test_allows_compose_yaml(self, tmp_path):
        d = tmp_path / "my_project"
        d.mkdir()
        (d / "docker-compose.yml").write_text("services:")
        result = resolve_deployment("my_project", tmp_path, "docker-compose.yml")
        assert result.name == "docker-compose.yml"

    def test_allows_python_file(self, tmp_path):
        d = tmp_path / "my_project"
        (d / "app").mkdir(parents=True)
        (d / "app" / "main.py").write_text("pass")
        result = resolve_deployment("my_project", tmp_path, "app/main.py")
        assert result.name == "main.py"

    def test_nonexistent_dep_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            resolve_deployment("missing_project", tmp_path)
