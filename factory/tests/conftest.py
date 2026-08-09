"""
Fixtures de aislamiento para la suite de tests de GMP AI Factory.

Cada fixture redirige los paths de persistencia a directorios temporales,
garantizando que los tests no contaminen datos reales de la fábrica.
"""

import sys
from pathlib import Path

import pytest

# Asegurar que factory/ es importable desde /home/ing_cpmo
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))


#: Requisitos del catalogo cuyo Evidence Pack existe pero AUN NO tiene
#: interpretacion humana (`structure_only_pending_human_interpretation`).
#:
#: No es una lista de excepciones toleradas: es una declaracion consciente.
#: Un requisito aqui tiene cita anclada y estructura valida, pero le faltan
#: los campos interpretativos (evidence_min_criteria, exclusion_criteria,
#: governed_interpretation...), asi que NO puede evaluarse en una corrida.
#: Los tests exigen que todo lo que este aqui siga bloqueado para produccion,
#: y que todo lo que NO este aqui tenga su pack completo.
#:
#: Anadir un id a este conjunto es un acto deliberado que debe acompanar a un
#: alta real de requisito -- nunca la via para silenciar un pack incompleto.
#: `21_CFR_211.68(b)` entro el 2026-07-29 con la ingesta de Part 211 y salio
#: el 2026-07-30 (G4): pack_version 2.0-draft, evidence_pack_status
#: human_drafted_provisional -- el conjunto queda vacio, no se retira el
#: mecanismo (el proximo requisito sin interpretar entra aqui igual).
PENDING_HUMAN_INTERPRETATION_REQ_IDS = frozenset()


@pytest.fixture()
def isolated_audit(tmp_path, monkeypatch):
    """
    Redirige audit_writer a un archivo JSONL temporal y resetea el hash global.
    Garantiza que write_event / verify_chain no tocan factory/audit/factory_audit.jsonl real.
    """
    import factory.core.audit_writer as aw

    audit_file = tmp_path / "factory_audit_test.jsonl"
    monkeypatch.setattr(aw, "AUDIT_FILE", audit_file)
    monkeypatch.setattr(aw, "_last_entry_hash", None)
    yield audit_file
    # monkeypatch restaura automáticamente; reset explícito como seguro adicional
    monkeypatch.setattr(aw, "_last_entry_hash", None)


@pytest.fixture()
def isolated_missions(tmp_path, monkeypatch, isolated_audit):
    """
    Redirige mission_control a un directorio de misiones temporal.
    Depende de isolated_audit porque create_mission/approve_mission llaman write_event.
    """
    import factory.layer9.mission_control as mc

    missions_dir = tmp_path / "missions"
    missions_dir.mkdir()
    monkeypatch.setattr(mc, "MISSIONS_DIR", missions_dir)
    yield missions_dir


@pytest.fixture()
def isolated_decisions(tmp_path, monkeypatch, isolated_audit):
    """Redirige decision_log a un archivo temporal."""
    import factory.layer9.decision_log as dl

    decisions_dir = tmp_path / "decisions"
    decisions_dir.mkdir()
    decisions_file = decisions_dir / "decisions.jsonl"
    monkeypatch.setattr(dl, "DECISIONS_FILE", decisions_file)
    yield decisions_file


@pytest.fixture()
def isolated_risks(tmp_path, monkeypatch, isolated_audit):
    """Redirige risk_acceptance a un archivo temporal."""
    import factory.layer9.risk_acceptance as ra

    risks_dir = tmp_path / "risks"
    risks_dir.mkdir()
    risks_file = risks_dir / "risks.jsonl"
    monkeypatch.setattr(ra, "RISKS_FILE", risks_file)
    yield risks_file


@pytest.fixture()
def isolated_workspaces(tmp_path, monkeypatch, isolated_audit):
    """
    Redirige claude_runtime a workspaces y runtime_config temporales.
    Retorna (ws_base, runtime_cfg_path).
    """
    import factory.layer8.claude_runtime as cr

    ws_base = tmp_path / "workspaces"
    ws_base.mkdir()
    runtime_cfg = tmp_path / "runtime_config.yaml"
    monkeypatch.setattr(cr, "WORKSPACES_BASE", ws_base)
    monkeypatch.setattr(cr, "RUNTIME_CONFIG", runtime_cfg)
    yield ws_base, runtime_cfg


@pytest.fixture(autouse=True)
def isolated_review_queue(tmp_path, monkeypatch):
    """R1.8 (2026-08-09): chunked_engine.evaluate_chunked() puede encolar
    findings SUPPORTING_EVIDENCE_UNDER_REVIEW en factory/layer9/
    review_queue.jsonl (real, gobernanza) durante CUALQUIER test que
    ejercite el pipeline verificado -- no solo los tests de
    human_review_queue explicitos. Autouse (no opt-in) para que ningun
    test, presente o futuro, contamine la cola real con hallazgos
    sinteticos. test_rc_approval_idempotency.py ya redirige
    REVIEW_QUEUE_FILE por su cuenta (isolated_rc); este fixture no
    interfiere -- el ultimo monkeypatch aplicado gana, ambos apuntan a
    tmp_path."""
    import factory.layer9.human_review_queue as hrq

    queue_file = tmp_path / "review_queue_test.jsonl"
    monkeypatch.setattr(hrq, "REVIEW_QUEUE_FILE", queue_file)
    yield queue_file
