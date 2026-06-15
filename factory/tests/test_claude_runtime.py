"""
Tests de Capa 8 — Claude Runtime.

Cubre:
- validate_task_safety rechaza rutas y comandos prohibidos
- run_controlled_headless con headless_enabled=false → status=disabled
- Orden de guardas E1: headless_check → workspace_valid → task_safety
"""

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.layer8.claude_runtime import (
    FORBIDDEN_TASK_PATTERNS,
    validate_task_safety,
    validate_workspace,
    run_controlled_headless,
    REQUIRED_WORKSPACE_FILES,
)


# ── validate_task_safety ──────────────────────────────────────────────────────

class TestValidateTaskSafety:
    def test_safe_task_passes(self, isolated_workspaces):
        ws_base, _ = isolated_workspaces
        ws = ws_base / "proj_safe"
        ws.mkdir()
        (ws / "task.md").write_text(
            "Generar corpus HPLC con fuentes regulatorias citables y corpus ChromaDB.\n"
        )
        result = validate_task_safety("proj_safe")
        assert result["safe"] is True
        assert result["violations"] == []

    def test_rejects_app_path(self, isolated_workspaces):
        ws_base, _ = isolated_workspaces
        ws = ws_base / "proj_app"
        ws.mkdir()
        (ws / "task.md").write_text("Editar /home/ing_cpmo/app/main.py para agregar endpoint.\n")
        result = validate_task_safety("proj_app")
        assert result["safe"] is False
        assert "/home/ing_cpmo/app" in result["violations"]

    def test_rejects_env_path(self, isolated_workspaces):
        ws_base, _ = isolated_workspaces
        ws = ws_base / "proj_env"
        ws.mkdir()
        (ws / "task.md").write_text("Leer /home/ing_cpmo/.env para obtener credenciales.\n")
        result = validate_task_safety("proj_env")
        assert result["safe"] is False
        assert "/home/ing_cpmo/.env" in result["violations"]

    def test_rejects_rm_rf_command(self, isolated_workspaces):
        ws_base, _ = isolated_workspaces
        ws = ws_base / "proj_rm"
        ws.mkdir()
        (ws / "task.md").write_text("Ejecutar rm -rf /tmp/old_data para limpiar.\n")
        result = validate_task_safety("proj_rm")
        assert result["safe"] is False
        assert "rm -rf" in result["violations"]

    def test_rejects_dangerously_skip_permissions(self, isolated_workspaces):
        ws_base, _ = isolated_workspaces
        ws = ws_base / "proj_skip"
        ws.mkdir()
        (ws / "task.md").write_text(
            "claude --dangerously-skip-permissions -p 'haz todo'\n"
        )
        result = validate_task_safety("proj_skip")
        assert result["safe"] is False
        assert "--dangerously-skip-permissions" in result["violations"]

    def test_rejects_git_push(self, isolated_workspaces):
        ws_base, _ = isolated_workspaces
        ws = ws_base / "proj_push"
        ws.mkdir()
        (ws / "task.md").write_text("Hacer git push origin main para publicar.\n")
        result = validate_task_safety("proj_push")
        assert result["safe"] is False
        assert "git push" in result["violations"]

    def test_rejects_backups_path(self, isolated_workspaces):
        ws_base, _ = isolated_workspaces
        ws = ws_base / "proj_backup"
        ws.mkdir()
        (ws / "task.md").write_text(
            "Acceder a /home/ing_cpmo/backups/pre_factory para restaurar.\n"
        )
        result = validate_task_safety("proj_backup")
        assert result["safe"] is False

    def test_all_forbidden_patterns_are_detected(self, isolated_workspaces):
        """Todos los patrones de FORBIDDEN_TASK_PATTERNS deben ser rechazados."""
        ws_base, _ = isolated_workspaces
        for i, pattern in enumerate(FORBIDDEN_TASK_PATTERNS):
            ws = ws_base / f"proj_pattern_{i}"
            ws.mkdir(exist_ok=True)
            (ws / "task.md").write_text(f"Acción: {pattern}\n")
            result = validate_task_safety(f"proj_pattern_{i}")
            assert result["safe"] is False, (
                f"Patrón prohibido no detectado: '{pattern}'"
            )
            assert pattern in result["violations"]

    def test_missing_task_md_is_safe(self, isolated_workspaces):
        """Si no hay task.md, el runtime no tiene restricciones que validar."""
        ws_base, _ = isolated_workspaces
        ws = ws_base / "proj_notask"
        ws.mkdir()
        result = validate_task_safety("proj_notask")
        assert result["safe"] is True

    def test_multiple_violations_all_reported(self, isolated_workspaces):
        ws_base, _ = isolated_workspaces
        ws = ws_base / "proj_multi"
        ws.mkdir()
        (ws / "task.md").write_text(
            "rm -rf /data && git push && claude --dangerously-skip-permissions\n"
        )
        result = validate_task_safety("proj_multi")
        assert result["safe"] is False
        assert len(result["violations"]) >= 3


# ── validate_workspace ────────────────────────────────────────────────────────

class TestValidateWorkspace:
    def test_complete_workspace_is_valid(self, isolated_workspaces):
        ws_base, _ = isolated_workspaces
        ws = ws_base / "proj_complete"
        ws.mkdir()
        (ws / "CLAUDE.md").write_text("# Rules\n")
        (ws / "task.md").write_text("# Task\n")
        (ws / ".claude").mkdir()
        (ws / ".claude" / "settings.json").write_text("{}")
        result = validate_workspace("proj_complete")
        assert result["valid"] is True
        assert result["missing"] == []

    def test_missing_claude_md_is_invalid(self, isolated_workspaces):
        ws_base, _ = isolated_workspaces
        ws = ws_base / "proj_no_claude"
        ws.mkdir()
        (ws / "task.md").write_text("# Task\n")
        (ws / ".claude").mkdir()
        (ws / ".claude" / "settings.json").write_text("{}")
        result = validate_workspace("proj_no_claude")
        assert result["valid"] is False
        assert "CLAUDE.md" in result["missing"]

    def test_nonexistent_workspace_is_invalid(self, isolated_workspaces):
        result = validate_workspace("proj_doesnt_exist_xyz")
        assert result["valid"] is False
        assert len(result["missing"]) > 0

    def test_all_required_files_must_exist(self, isolated_workspaces):
        ws_base, _ = isolated_workspaces
        ws = ws_base / "proj_partial"
        ws.mkdir()
        # Solo CLAUDE.md — faltan task.md y .claude/settings.json
        (ws / "CLAUDE.md").write_text("# Rules\n")
        result = validate_workspace("proj_partial")
        assert result["valid"] is False
        missing = result["missing"]
        assert "task.md" in missing or any("task" in m for m in missing)


# ── run_controlled_headless ───────────────────────────────────────────────────

class TestRunControlledHeadless:
    def test_disabled_without_config_file(self, isolated_workspaces):
        """Sin runtime_config.yaml, headless_enabled por defecto es False → disabled."""
        _, runtime_cfg = isolated_workspaces
        assert not runtime_cfg.exists()
        result = run_controlled_headless("any_project")
        assert result["status"] == "disabled"

    def test_disabled_explicit_false_in_config(self, isolated_workspaces):
        """headless_enabled: false explícito en YAML → disabled."""
        _, runtime_cfg = isolated_workspaces
        runtime_cfg.write_text(
            yaml.dump({"headless_enabled": False, "default_mode": "manual_assisted"})
        )
        result = run_controlled_headless("any_project")
        assert result["status"] == "disabled"

    def test_disabled_reason_mentions_headless(self, isolated_workspaces):
        """El motivo de disabled debe mencionar headless_enabled."""
        result = run_controlled_headless("any_project")
        assert "headless" in result.get("reason", "").lower()

    # ── E1: orden de guardas ──────────────────────────────────────────────────

    def test_E1_headless_check_is_first_guard(self, isolated_workspaces):
        """
        E1 — Guard 1: si headless_enabled=false, retorna 'disabled' sin llegar a
        workspace_valid ni task_safety.
        Prueba: workspace inexistente + headless=false → debe ser 'disabled', no error de workspace.
        """
        _, runtime_cfg = isolated_workspaces
        runtime_cfg.write_text(yaml.dump({"headless_enabled": False}))
        # workspace inexistente: si la guarda de workspace corriese primero, daría workspace_invalid
        result = run_controlled_headless("workspace_no_existe_xyzabc")
        assert result["status"] == "disabled", (
            "E1: guarda headless_check debe disparar ANTES que workspace_valid"
        )

    def test_E1_workspace_check_before_safety(self, isolated_workspaces):
        """
        E1 — Guard 2 antes de Guard 3: con headless=true y workspace inválido,
        debe fallar con 'workspace_invalid', NO con 'task_safety_violated'.
        Si la guarda de task_safety corriese primero, daría task_safety_violated.
        """
        ws_base, runtime_cfg = isolated_workspaces
        runtime_cfg.write_text(yaml.dump({"headless_enabled": True}))

        ws = ws_base / "proj_e1_ws"
        ws.mkdir()
        # task.md con contenido prohibido — si safety check corre primero: task_safety_violated
        (ws / "task.md").write_text("Ejecutar rm -rf /home/ing_cpmo/app\n")
        # CLAUDE.md y .claude/settings.json ausentes → workspace inválido
        # → workspace_invalid debe ganar

        result = run_controlled_headless("proj_e1_ws")
        assert result["status"] == "error"
        assert result["reason"] == "workspace_invalid", (
            f"E1: esperado 'workspace_invalid', obtenido '{result.get('reason')}'. "
            "La guarda workspace_valid debe preceder a task_safety."
        )

    def test_E1_safety_check_after_valid_workspace(self, isolated_workspaces):
        """
        E1 — Guard 3: con headless=true y workspace válido pero task inseguro,
        debe fallar con 'task_safety_violated'.
        """
        ws_base, runtime_cfg = isolated_workspaces
        runtime_cfg.write_text(yaml.dump({"headless_enabled": True}))

        ws = ws_base / "proj_e1_safety"
        ws.mkdir()
        (ws / "CLAUDE.md").write_text("# Rules\n")
        (ws / "task.md").write_text("Editar /home/ing_cpmo/app/main.py\n")
        (ws / ".claude").mkdir()
        (ws / ".claude" / "settings.json").write_text("{}")

        result = run_controlled_headless("proj_e1_safety")
        assert result["status"] == "error"
        assert result["reason"] == "task_safety_violated", (
            f"E1: esperado 'task_safety_violated', obtenido '{result.get('reason')}'"
        )
