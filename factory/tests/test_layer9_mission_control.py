"""
Tests de Capa 9 Mission Control.

Cubre: create/approve/list misión, decision_log, risk_acceptance
y la restricción H2 (el agente NO puede auto-aprobar).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.layer9.mission_control import (
    approve_mission,
    create_mission,
    get_mission,
    list_missions,
)
from factory.layer9.decision_log import list_decisions, write_decision
from factory.layer9.risk_acceptance import accept_risk

# ── Payload de misión válido (lab_qc domain) ──────────────────────────────────

_MISSION = {
    "project_id": "test_mc",
    "client_type": "pharma_manufacturer",
    "objective": (
        "Laboratorio QC con LIMS, HPLC análisis cromatográfico, "
        "investigación OOS Fase I/II, Data Integrity ALCOA+, 21 CFR Part 11"
    ),
    "regulatory_scope": ["21 CFR Part 211", "21 CFR Part 11"],
    "documents": {"FDA_OOS_Guidance_2022": "pending", "USP_621": "pending"},
    "constraints": ["Solo Ollama local", "Sin acceso internet"],
    "mission_approval": {
        "autonomy_level": "controlled_full",
        "allowed_actions": ["generate_code", "run_quality_gates"],
        "stop_conditions": ["quality_gate_fail", "forbidden_path_detected"],
        "final_human_decision_required": ["deploy_docker"],
        "deploy_docker_if_gates_pass": False,
    },
    "linked_release": {},
}


# ── Create ─────────────────────────────────────────────────────────────────────

class TestCreateMission:
    def test_creates_with_draft_status(self, isolated_missions):
        result = create_mission(dict(_MISSION))
        assert result["status"] == "draft"
        assert result["project_id"] == "test_mc"

    def test_mission_yaml_written_to_disk(self, isolated_missions):
        create_mission(dict(_MISSION))
        assert (isolated_missions / "test_mc.yaml").exists()

    def test_duplicate_project_id_raises_file_exists(self, isolated_missions):
        create_mission(dict(_MISSION))
        with pytest.raises(FileExistsError):
            create_mission(dict(_MISSION))

    def test_mission_has_required_fields(self, isolated_missions):
        result = create_mission(dict(_MISSION))
        for field in ("project_id", "status", "created_at", "mission_approval", "objective"):
            assert field in result, f"Campo requerido ausente: {field}"

    def test_invalid_autonomy_level_raises(self, isolated_missions):
        bad = dict(_MISSION)
        bad = {**_MISSION, "project_id": "test_bad"}
        bad["mission_approval"] = {**_MISSION["mission_approval"], "autonomy_level": "god_mode"}
        with pytest.raises(ValueError):
            create_mission(bad)


# ── Approve ────────────────────────────────────────────────────────────────────

class TestApproveMission:
    def test_approve_sets_status_approved(self, isolated_missions):
        create_mission(dict(_MISSION))
        result = approve_mission("test_mc", approved_by="Cesar", decision_origin="human_confirmed")
        assert result["status"] == "approved"

    def test_approve_records_approver(self, isolated_missions):
        """approved_by se almacena en history (excluido del return) y en el YAML."""
        create_mission(dict(_MISSION))
        approve_mission("test_mc", approved_by="Cesar")
        # Verificar via get_mission que incluye history
        detail = get_mission("test_mc")
        history = detail.get("history", [])
        assert any(h.get("by") == "Cesar" for h in history), (
            "El aprobador 'Cesar' debe aparecer en history de la misión"
        )
        assert detail.get("status") == "approved"

    def test_cannot_approve_already_approved(self, isolated_missions):
        create_mission(dict(_MISSION))
        approve_mission("test_mc", approved_by="Cesar")
        with pytest.raises(ValueError, match="draft"):
            approve_mission("test_mc", approved_by="Cesar")

    # ── H2: agente NO puede auto-aprobar ──────────────────────────────────────

    def test_H2_layer8_agent_is_blocked(self, isolated_missions):
        """H2: approved_by='layer8_agent' es valor reservado — debe levantar ValueError."""
        create_mission(dict(_MISSION))
        with pytest.raises(ValueError, match="reservado"):
            approve_mission("test_mc", approved_by="layer8_agent")

    def test_H2_all_reserved_approvers_are_blocked(self, isolated_missions):
        """H2: ningún valor genérico/reservado puede ser el aprobador."""
        create_mission(dict(_MISSION))
        reserved = ("agent", "layer8_agent", "auto", "system", "human", "")
        for bad_approver in reserved:
            with pytest.raises(ValueError, match="reservado"):
                approve_mission("test_mc", approved_by=bad_approver)

    def test_H2_real_human_name_is_accepted(self, isolated_missions):
        """H2: un nombre humano real supera la guarda de auto-aprobación."""
        create_mission(dict(_MISSION))
        result = approve_mission("test_mc", approved_by="Maria_Garcia")
        assert result["status"] == "approved"


# ── List / Get ────────────────────────────────────────────────────────────────

class TestListMissions:
    def test_list_empty_when_no_missions(self, isolated_missions):
        result = list_missions()
        assert result == []

    def test_list_includes_created_mission(self, isolated_missions):
        create_mission(dict(_MISSION))
        result = list_missions()
        assert any(m["project_id"] == "test_mc" for m in result)

    def test_list_filter_by_status_draft(self, isolated_missions):
        create_mission(dict(_MISSION))
        drafts = list_missions(status="draft")
        assert all(m["status"] == "draft" for m in drafts)
        assert any(m["project_id"] == "test_mc" for m in drafts)

    def test_list_filter_by_approved_excludes_draft(self, isolated_missions):
        create_mission(dict(_MISSION))
        approved = list_missions(status="approved")
        assert not any(m["project_id"] == "test_mc" for m in approved)

    def test_get_mission_returns_detail(self, isolated_missions):
        create_mission(dict(_MISSION))
        detail = get_mission("test_mc")
        assert detail["project_id"] == "test_mc"
        assert "mission_approval" in detail

    def test_get_nonexistent_mission_raises(self, isolated_missions):
        with pytest.raises(FileNotFoundError):
            get_mission("no_existe_xyz")


# ── Decision Log ──────────────────────────────────────────────────────────────

class TestDecisionLog:
    def test_write_human_confirmed_decision(self, isolated_decisions):
        entry = write_decision(
            project_id="test_mc",
            action="approve_release",
            decision="approve",
            rationale="Quality gates 12/12 PASS",
            decided_by="Cesar",
            decision_origin="human_confirmed",
        )
        assert entry["decision"] == "approve"
        assert entry["decided_by"] == "Cesar"
        assert entry["decision_origin"] == "human_confirmed"
        assert isolated_decisions.exists()

    def test_agent_proposed_decision_is_allowed(self, isolated_decisions):
        """El agente puede PROPONER (agent_proposed); no CONFIRMAR."""
        entry = write_decision(
            project_id="test_mc",
            action="propose_corpus",
            decision="conditional_approve",
            rationale="Corpus incompleto — pendiente USP PDF",
            decided_by="layer8_agent",
            decision_origin="agent_proposed",
        )
        assert entry["decision_origin"] == "agent_proposed"

    def test_invalid_decision_type_raises(self, isolated_decisions):
        with pytest.raises(ValueError, match="Decisión inválida"):
            write_decision(
                project_id="test",
                action="x",
                decision="auto_approve",
                decided_by="Cesar",
            )

    def test_invalid_decision_origin_raises(self, isolated_decisions):
        with pytest.raises(ValueError, match="decision_origin"):
            write_decision(
                project_id="test",
                action="x",
                decision="approve",
                decided_by="Cesar",
                decision_origin="robot_decided",
            )

    def test_decisions_accumulate_in_file(self, isolated_decisions):
        write_decision("test", "a1", "approve", decided_by="Cesar")
        write_decision("test", "a2", "reject", decided_by="Cesar")
        lines = [l for l in isolated_decisions.read_text().splitlines() if l.strip()]
        assert len(lines) == 2


# ── Risk Acceptance ───────────────────────────────────────────────────────────

class TestRiskAcceptance:
    def test_accept_medium_risk(self, isolated_risks):
        entry = accept_risk(
            project_id="test_mc",
            risk_description="Corpus parcial — FDA OOS Guidance PDF pendiente",
            severity="medium",
            mitigation="Corpus completo requerido antes de go-live",
            accepted_by="Cesar",
        )
        assert entry["status"] == "accepted"
        assert entry["severity"] == "medium"
        assert entry["project_id"] == "test_mc"
        assert isolated_risks.exists()

    def test_risk_entry_has_uuid_id(self, isolated_risks):
        entry = accept_risk("test", "Riesgo X", "low", accepted_by="Cesar")
        import uuid
        uuid.UUID(entry["risk_id"])  # raises if not valid UUID

    def test_invalid_severity_raises(self, isolated_risks):
        with pytest.raises(ValueError, match="Severidad inválida"):
            accept_risk(
                project_id="test",
                risk_description="algo",
                severity="extreme",
                accepted_by="Cesar",
            )

    def test_empty_description_raises(self, isolated_risks):
        with pytest.raises(ValueError):
            accept_risk(
                project_id="test",
                risk_description="",
                severity="low",
                accepted_by="Cesar",
            )

    def test_all_severity_levels_accepted(self, isolated_risks):
        for sev in ("low", "medium", "high", "critical"):
            entry = accept_risk("test", f"Riesgo {sev}", sev, accepted_by="Cesar")
            assert entry["severity"] == sev
