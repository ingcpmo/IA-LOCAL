"""Cierre de la reproducibilidad de Fase D (W5 V2): el runtime desplegable
debe corresponder a un commit o artefacto versionado identificable.

Verifica lo que la auditoría dejó abierto: que el motor que ejecutan las
corridas reales esté git-trackeado (y no sea el motor legacy del workspace
gitignorado), y que la parte que git no puede versionar quede declarada por
hash de árbol en vez de quedar simplemente sin identidad.
"""
from pathlib import Path

import pytest

from factory.services import runtime_identity as ri


class TestEngineFilesAreVersioned:

    def test_every_engine_file_is_git_tracked(self):
        """Si esto falla, el runtime de producción vive fuera de git y
        ninguna corrida puede anclarse a un commit."""
        tracked = ri.engine_files_tracked()
        untracked = [name for name, ok in tracked.items() if not ok]
        assert untracked == [], f"ficheros del motor fuera de control de versiones: {untracked}"

    def test_engine_files_on_disk_match_head(self):
        """Trackeado no basta: el contenido en disco debe ser el del commit.
        Un fichero modificado sin commitear hace falsa la identidad."""
        drifted = [name for name, ok in ri.engine_files_match_head().items() if not ok]
        assert drifted == [], (
            f"ficheros del motor que no coinciden con HEAD: {drifted} -- "
            "commitear antes de declarar la identidad de una corrida"
        )

    def test_real_runs_import_the_tracked_engine_not_the_legacy_workspace_copy(self):
        """Hecho que sostiene todo lo anterior: los runners de las corridas
        reales importan el motor trackeado. Guardia contra una regresión que
        volviera a apuntar al motor legacy gitignorado."""
        runner = Path("logs/fsv12_reeval_20260728/run_fsv12_reeval.py")
        if not runner.is_file():
            pytest.skip("artefactos de la corrida real no presentes en este entorno")
        source = runner.read_text(encoding="utf-8")
        assert "from factory.engines.gmpai_integrity.chunked_engine import" in source
        assert "chunked_llm_integrity_engine" not in source


class TestWorkspaceIsDeclaredNotOrphaned:

    def test_workspace_tree_hash_is_declared_when_present(self):
        identity = ri.runtime_identity()
        if not identity["workspace_app_present"]:
            pytest.skip("workspace no presente en este entorno")
        assert identity["workspace_app_tree_sha256"]
        assert len(identity["workspace_app_tree_sha256"]) == 64
        assert identity["workspace_versioning"] == "GITIGNORED_DECLARED_BY_TREE_HASH"

    def test_tree_hash_changes_when_content_changes(self, tmp_path):
        """El hash de árbol sirve como identidad solo si detecta cambios:
        verificado por mutación real sobre un árbol temporal."""
        (tmp_path / "a.py").write_text("uno", encoding="utf-8")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.py").write_text("dos", encoding="utf-8")
        before = ri.sha256_tree(tmp_path)

        assert ri.sha256_tree(tmp_path) == before, "el hash debe ser estable sin cambios"

        (tmp_path / "sub" / "b.py").write_text("dos modificado", encoding="utf-8")
        assert ri.sha256_tree(tmp_path) != before, "un cambio de contenido debe cambiar el hash"

    def test_tree_hash_ignores_pycache(self, tmp_path):
        (tmp_path / "a.py").write_text("uno", encoding="utf-8")
        before = ri.sha256_tree(tmp_path)
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "a.cpython-311.pyc").write_bytes(b"\x00binario")
        assert ri.sha256_tree(tmp_path) == before


class TestFailClosedGuard:

    def test_assert_passes_on_a_reproducible_runtime(self):
        identity = ri.assert_runtime_reproducible()
        assert identity["reproducible"] is True
        assert len(identity["commit_sha"]) == 40

    def test_assert_raises_when_an_engine_file_is_not_tracked(self, monkeypatch):
        """Verificación por mutación: la guardia debe abortar, no advertir."""
        monkeypatch.setattr(
            ri, "engine_files_tracked",
            lambda: {"chunked_engine.py": False, "ollama_client.py": True,
                     "model_provider.py": True},
        )
        with pytest.raises(ri.RuntimeIdentityError) as exc:
            ri.assert_runtime_reproducible()
        assert "chunked_engine.py" in str(exc.value)

    def test_assert_raises_when_disk_drifted_from_head(self, monkeypatch):
        monkeypatch.setattr(
            ri, "engine_files_match_head",
            lambda: {"chunked_engine.py": True, "ollama_client.py": False,
                     "model_provider.py": True},
        )
        with pytest.raises(ri.RuntimeIdentityError) as exc:
            ri.assert_runtime_reproducible()
        assert "ollama_client.py" in str(exc.value)
