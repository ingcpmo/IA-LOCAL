"""
Tests -- factory/regulatory/human_source_update.py (Fase 1 pendiente,
document_remediation_evolution).

Garantías fijadas:
  - propose_/confirm_ NUNCA escriben sources/registry.json -- solo
    decisions.jsonl (mismo patrón que applicability_matrix.approval)
  - apply_ es la ÚNICA función con permiso de escritura real
  - apply_ exige decision_origin='human_confirmed'+decision='approve' --
    una propuesta agent_proposed sin confirmar nunca se aplica
  - apply_ exige que la fuente esté REGULATORY_SOURCE_UNVERIFIED
    (broken_link_report) O ARTIFACT_TYPE_MISMATCH
    (artifact_type_mismatch_report) según el historial real de
    source_currency_log.jsonl -- nunca reescribe una fuente sana, ni con
    decisión humana válida
  - regulatory_currency_status nunca cambia (se mantiene
    'pending_reverification', invariante del schema de Fase 1)
  - campos no permitidos en new_values se rechazan fail-closed
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from factory.regulatory import artifact_type_mismatch_report
from factory.regulatory import broken_link_report
from factory.regulatory import human_source_update as hsu
from factory.services import paths as svc_paths

SOURCE_ID = "fake_source"


@pytest.fixture()
def registry_env(tmp_path, monkeypatch, isolated_decisions):
    registry = {
        "registry_version": "1.1",
        "sources": [{
            "source_id": SOURCE_ID,
            "official_source_url": "https://old.example.org/norma.pdf",
            "official_source_description": "vieja",
            "sha256_original": "a" * 64,
            "regulatory_currency_status": "pending_reverification",
        }],
    }
    registry_file = tmp_path / "registry.json"
    registry_file.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr(hsu, "SOURCES_REGISTRY_FILE", registry_file)

    currency_log_file = tmp_path / "source_currency_log.jsonl"
    monkeypatch.setattr(svc_paths, "SOURCE_CURRENCY_LOG_FILE", currency_log_file)
    yield registry_file, currency_log_file


def _write_unverified_history(currency_log_file, source_id=SOURCE_ID, n=3):
    entries = [
        {"source_id": source_id, "checked_at": f"2026-07-2{i}T00:00:00+00:00", "reachable": False}
        for i in range(n)
    ]
    currency_log_file.write_text(
        "\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8"
    )


def _write_artifact_type_mismatch_history(currency_log_file, source_id=SOURCE_ID, n=3):
    entries = [
        {"source_id": source_id, "checked_at": f"2026-08-0{i}T00:00:00+00:00",
         "reachable": True, "comparable": False}
        for i in range(1, n + 1)
    ]
    currency_log_file.write_text(
        "\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8"
    )


def test_propose_never_writes_registry(registry_env):
    registry_file, _ = registry_env
    before = registry_file.read_text(encoding="utf-8")
    hsu.propose_source_url_update(
        SOURCE_ID, {"official_source_url": "https://new.example.org/norma.pdf"},
        rationale="url rota", proposed_by="layer8_agent",
    )
    assert registry_file.read_text(encoding="utf-8") == before


def test_propose_rejects_unknown_field(registry_env):
    with pytest.raises(hsu.HumanSourceUpdateError):
        hsu.propose_source_url_update(SOURCE_ID, {"regulatory_currency_status": "verified_current"}, rationale="x")


def test_propose_rejects_empty_new_values(registry_env):
    with pytest.raises(hsu.HumanSourceUpdateError):
        hsu.propose_source_url_update(SOURCE_ID, {}, rationale="x")


def test_confirm_never_writes_registry(registry_env):
    registry_file, _ = registry_env
    proposal = hsu.propose_source_url_update(
        SOURCE_ID, {"official_source_url": "https://new.example.org/norma.pdf"}, rationale="x",
    )
    before = registry_file.read_text(encoding="utf-8")
    hsu.confirm_source_url_update(proposal["decision_id"], confirmed_by="Cesar")
    assert registry_file.read_text(encoding="utf-8") == before


def test_confirm_rejects_unknown_decision_id(registry_env):
    with pytest.raises(hsu.HumanSourceUpdateError):
        hsu.confirm_source_url_update("no-existe", confirmed_by="Cesar")


def test_confirm_rejects_already_confirmed_decision(registry_env):
    proposal = hsu.propose_source_url_update(
        SOURCE_ID, {"official_source_url": "https://new.example.org/norma.pdf"}, rationale="x",
    )
    confirmation = hsu.confirm_source_url_update(proposal["decision_id"], confirmed_by="Cesar")
    with pytest.raises(hsu.HumanSourceUpdateError):
        hsu.confirm_source_url_update(confirmation["decision_id"], confirmed_by="Cesar")


def test_apply_rejects_agent_proposed_without_confirmation(registry_env):
    _, currency_log_file = registry_env
    _write_unverified_history(currency_log_file)
    proposal = hsu.propose_source_url_update(
        SOURCE_ID, {"official_source_url": "https://new.example.org/norma.pdf"}, rationale="x",
    )
    with pytest.raises(hsu.HumanSourceUpdateError):
        hsu.apply_source_url_update(proposal["decision_id"])


def test_apply_rejects_healthy_source_even_with_valid_confirmation(registry_env):
    """Sin historial de fallos (fuente OK o sin historial) -- apply_ nunca
    escribe, aunque la decision este human_confirmed+approve."""
    proposal = hsu.propose_source_url_update(
        SOURCE_ID, {"official_source_url": "https://new.example.org/norma.pdf"}, rationale="x",
    )
    confirmation = hsu.confirm_source_url_update(proposal["decision_id"], confirmed_by="Cesar")
    with pytest.raises(hsu.HumanSourceUpdateError):
        hsu.apply_source_url_update(confirmation["decision_id"])


def test_apply_succeeds_for_unverified_source_with_valid_confirmation(registry_env):
    registry_file, currency_log_file = registry_env
    _write_unverified_history(currency_log_file)

    proposal = hsu.propose_source_url_update(
        SOURCE_ID,
        {"official_source_url": "https://new.example.org/norma.pdf", "sha256_original": "b" * 64},
        rationale="url oficial rota 3 veces seguidas, nueva URL verificada manualmente",
    )
    confirmation = hsu.confirm_source_url_update(proposal["decision_id"], confirmed_by="Cesar")
    result = hsu.apply_source_url_update(confirmation["decision_id"])

    assert result["source_id"] == SOURCE_ID
    updated = json.loads(registry_file.read_text(encoding="utf-8"))
    entry = updated["sources"][0]
    assert entry["official_source_url"] == "https://new.example.org/norma.pdf"
    assert entry["sha256_original"] == "b" * 64
    assert entry["regulatory_currency_status"] == "pending_reverification"


def test_apply_succeeds_for_artifact_type_mismatch_source_with_valid_confirmation(registry_env):
    """G3: URL viva (reachable=True) pero comparable=False 3 veces seguidas
    -- ARTIFACT_TYPE_MISMATCH, no un enlace roto -- también habilita apply_."""
    registry_file, currency_log_file = registry_env
    _write_artifact_type_mismatch_history(currency_log_file)

    proposal = hsu.propose_source_url_update(
        SOURCE_ID,
        {"official_source_url": "https://archive.example.org/norma_archivada.pdf"},
        rationale="URL viva pero sirve HTML, no el PDF archivado gobernado",
    )
    confirmation = hsu.confirm_source_url_update(proposal["decision_id"], confirmed_by="Cesar")
    result = hsu.apply_source_url_update(confirmation["decision_id"])

    assert result["source_id"] == SOURCE_ID
    updated = json.loads(registry_file.read_text(encoding="utf-8"))
    entry = updated["sources"][0]
    assert entry["official_source_url"] == "https://archive.example.org/norma_archivada.pdf"
    assert entry["regulatory_currency_status"] == "pending_reverification"


def test_apply_rejects_unknown_decision_id(registry_env):
    with pytest.raises(hsu.HumanSourceUpdateError):
        hsu.apply_source_url_update("no-existe")


def test_full_cycle_writes_exactly_one_audit_event(registry_env, isolated_audit):
    _, currency_log_file = registry_env
    _write_unverified_history(currency_log_file)

    proposal = hsu.propose_source_url_update(
        SOURCE_ID, {"official_source_url": "https://new.example.org/norma.pdf"}, rationale="x",
    )
    confirmation = hsu.confirm_source_url_update(proposal["decision_id"], confirmed_by="Cesar")
    hsu.apply_source_url_update(confirmation["decision_id"])

    from factory.core import audit_writer as aw
    lines = aw.AUDIT_FILE.read_text(encoding="utf-8").splitlines()
    events = [json.loads(l) for l in lines]
    apply_events = [e for e in events if e.get("event_type") == "regulatory_source_url_updated"]
    assert len(apply_events) == 1
    assert apply_events[0]["data"]["source_id"] == SOURCE_ID


REAL_LOG = Path("/home/ing_cpmo/factory/regulatory/source_currency_log.jsonl")


def test_real_log_today_has_no_unverified_source_no_real_trigger_case():
    """Confirma el hallazgo real de la auditoria: hoy ninguna de las 4
    fuentes gobernadas esta REGULATORY_SOURCE_UNVERIFIED -- por eso
    human_source_update sigue sin un caso real de enlace roto que lo
    dispare, aunque el mecanismo ya exista y este probado (arriba, con
    fixtures)."""
    if not REAL_LOG.exists():
        pytest.skip("log real no disponible en este entorno")
    log_entries = [json.loads(l) for l in REAL_LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    source_ids = sorted({e["source_id"] for e in log_entries})
    for source_id in source_ids:
        status = broken_link_report.evaluate_source(source_id, log_entries)["status"]
        assert status != broken_link_report.STATUS_UNVERIFIED, (source_id, status)


def test_real_log_today_reflects_mhra_remediated_and_part11_still_mismatched():
    """G3: Cesar corrio 2 reverificaciones reales mas (2026-08-03 16:37/16:39)
    tras la primera (2026-08-02), completando las 3 consecutivas que el
    guard exige. Con esos datos reales, `mhra_gxp_di_guidance_2018` quedo
    remediada (`b46fa03` + apply real de `21db47e2-...`, official_source_url
    apunta ahora al PDF directo, comparable=True en la reverificacion
    posterior) -- ya NO es ARTIFACT_TYPE_MISMATCH. `ecfr_21cfr_part11` sigue
    sin remediar: la version anterior de este test asumia "sin trigger real
    todavia" porque solo habia 1 dato; con las 3 corridas reales confirmadas
    el trigger SI existe -- afirmar lo contrario seria fotografiar el estado
    viejo en vez de medir la regla (mismo patron ya corregido varias veces
    en este roadmap). Bloqueador real restante de G3, no de este mecanismo:
    resolver `ecfr_21cfr_part11` con el mismo patron propose/confirm/apply."""
    if not REAL_LOG.exists():
        pytest.skip("log real no disponible en este entorno")
    log_entries = [json.loads(l) for l in REAL_LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    source_ids = sorted({e["source_id"] for e in log_entries})
    assert "mhra_gxp_di_guidance_2018" in source_ids and "ecfr_21cfr_part11" in source_ids

    for source_id in source_ids:
        status = artifact_type_mismatch_report.evaluate_source(source_id, log_entries)["status"]
        if source_id == "ecfr_21cfr_part11":
            assert status == artifact_type_mismatch_report.STATUS_ARTIFACT_TYPE_MISMATCH, (source_id, status)
        else:
            assert status != artifact_type_mismatch_report.STATUS_ARTIFACT_TYPE_MISMATCH, (source_id, status)
