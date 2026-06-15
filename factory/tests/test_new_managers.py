"""
Tests para los módulos creados en Fase D+E:
- test_execution_manager
- artifact_collector
- autonomous_build_orchestrator
- gate_execution_manager
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ── test_execution_manager ───────────────────────────────────────────────────

class TestTestExecutionManager:
    def test_workspace_not_found(self, isolated_audit, tmp_path, monkeypatch):
        import factory.layer8.test_execution_manager as tem
        monkeypatch.setattr(tem, "WORKSPACES_BASE", tmp_path / "ws")
        result = tem.run_tests("no_such_project")
        assert result["all_passed"] is False
        assert "no encontrado" in result.get("error", "")

    def test_passing_tests(self, isolated_audit, tmp_path, monkeypatch):
        import factory.layer8.test_execution_manager as tem
        ws = tmp_path / "ws" / "myproj"
        ws.mkdir(parents=True)
        (ws / "tests").mkdir()
        (ws / "tests" / "test_ok.py").write_text("def test_pass(): assert True\n")
        monkeypatch.setattr(tem, "WORKSPACES_BASE", tmp_path / "ws")
        result = tem.run_tests("myproj", cmd="python3 -m pytest tests/ -q --tb=short")
        assert result["all_passed"] is True
        assert result["passed"] >= 1
        assert result["failed"] == 0
        assert (ws / "test_report.json").exists()

    def test_failing_tests(self, isolated_audit, tmp_path, monkeypatch):
        import factory.layer8.test_execution_manager as tem
        ws = tmp_path / "ws" / "myproj"
        ws.mkdir(parents=True)
        (ws / "tests").mkdir()
        (ws / "tests" / "test_fail.py").write_text("def test_fail(): assert False\n")
        monkeypatch.setattr(tem, "WORKSPACES_BASE", tmp_path / "ws")
        result = tem.run_tests("myproj", cmd="python3 -m pytest tests/ -q --tb=short")
        assert result["all_passed"] is False
        assert result["failed"] >= 1


# ── artifact_collector ───────────────────────────────────────────────────────

class TestArtifactCollector:
    def test_missing_required_returns_not_ok(self, isolated_audit, tmp_path, monkeypatch):
        import factory.layer8.artifact_collector as ac
        ws = tmp_path / "ws" / "proj"
        ws.mkdir(parents=True)
        rc_base = tmp_path / "rc"
        monkeypatch.setattr(ac, "WORKSPACES_BASE", tmp_path / "ws")
        monkeypatch.setattr(ac, "RC_BASE", rc_base)
        result = ac.collect("proj", "rc-001")
        assert result["ok"] is False
        assert any("test_report.json" in m for m in result["missing"])

    def test_collects_when_required_present(self, isolated_audit, tmp_path, monkeypatch):
        import factory.layer8.artifact_collector as ac
        ws = tmp_path / "ws" / "proj"
        ws.mkdir(parents=True)
        (ws / "test_report.json").write_text('{"all_passed":true}')
        log_dir = ws / "logs"
        log_dir.mkdir()
        (log_dir / "headless_1234567890.log").write_text("claude output")
        rc_base = tmp_path / "rc"
        monkeypatch.setattr(ac, "WORKSPACES_BASE", tmp_path / "ws")
        monkeypatch.setattr(ac, "RC_BASE", rc_base)
        result = ac.collect("proj", "rc-001")
        assert result["ok"] is True
        assert "test_report.json" in result["artifact_list"]
        artifacts_path = Path(result["artifacts_path"])
        assert (artifacts_path / "test_report.json").exists()


# ── autonomous_build_orchestrator ────────────────────────────────────────────

_MISSION_BASE = {
    "client_type": "pharma_manufacturer",
    "objective": "Test objetivo GMP",
    "regulatory_scope": ["21 CFR Part 211"],
    "documents": {"FDA_OOS": "pending"},
    "constraints": ["Solo Ollama local"],
    "mission_approval": {
        "autonomy_level": "controlled_full",
        "allowed_actions": ["run_claude_code", "generate_code"],
        "stop_conditions": ["quality_gate_fail"],
        "final_human_decision_required": ["deploy_docker"],
        "deploy_docker_if_gates_pass": False,
    },
    "linked_release": {},
}


class TestAutonomousBuildOrchestrator:
    def test_headless_disabled_returns_error(self, isolated_audit, tmp_path, monkeypatch):
        import factory.layer8.autonomous_build_orchestrator as abo
        import factory.layer8.host_worker as hw
        import factory.layer9.mission_control as mc

        missions_dir = tmp_path / "missions"
        missions_dir.mkdir()
        monkeypatch.setattr(mc, "MISSIONS_DIR", missions_dir)

        mc.create_mission({"project_id": "testproj", **_MISSION_BASE})
        mc.approve_mission("testproj", approved_by="Cesar",
                           allowed_actions=["run_claude_code", "generate_code"])

        monkeypatch.setattr(hw, "RUNTIME_CONFIG", tmp_path / "runtime_config.yaml")
        (tmp_path / "runtime_config.yaml").write_text("headless_enabled: false\n")

        result = abo.run_build_mission("testproj")
        assert result["status"] == "error"
        assert "headless" in result["reason"]

    def test_mission_not_approved_returns_error(self, isolated_audit, tmp_path, monkeypatch):
        import factory.layer8.autonomous_build_orchestrator as abo
        import factory.layer9.mission_control as mc

        missions_dir = tmp_path / "missions"
        missions_dir.mkdir()
        monkeypatch.setattr(mc, "MISSIONS_DIR", missions_dir)

        mc.create_mission({"project_id": "testproj2", **_MISSION_BASE})
        # No se aprueba — queda en draft

        result = abo.run_build_mission("testproj2")
        assert result["status"] == "error"
        assert "approved" in result["reason"]


# ── gate_execution_manager ───────────────────────────────────────────────────

class TestGateExecutionManager:
    def test_run_static_gates_structure(self, isolated_audit, tmp_path, monkeypatch):
        import factory.layer8.gate_execution_manager as gem
        ws = tmp_path / "ws" / "proj"
        ws.mkdir(parents=True)
        monkeypatch.setattr(gem, "WORKSPACES_BASE", tmp_path / "ws")
        result = gem.run_static_gates("proj")
        assert "all_pass" in result
        assert "summary" in result
        assert "gates" in result
        assert isinstance(result["gates"], list)
        assert "PASS" in result["summary"]
        assert "FAIL" in result["summary"]
        assert "SKIPPED" in result["summary"]
