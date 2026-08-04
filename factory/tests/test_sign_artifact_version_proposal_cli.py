"""Panel ARQ 2026-08-04 §6 -- CLI de firma con almacen TEMPORAL. Guardia:
si el script alguna vez leyera `decision_store_v2.STORE_FILE` sin que este
test lo haya monkeypatcheado a un tmp_path, escribiria en el almacen real
-- por eso el test AUTOUSE de aislamiento de auditoria + el monkeypatch de
STORE_FILE van juntos en cada test, nunca opcionales."""
from __future__ import annotations

import io
from pathlib import Path

import pytest

from factory.scripts.ops import sign_artifact_version_proposal as cli
from factory.services import decision_store_v2 as store

CATALOG = "factory/regulatory/requirement_catalog/requirements.yaml"
HASH_A = "a" * 64


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    from factory.core import audit_writer as aw
    monkeypatch.setattr(aw, "AUDIT_FILE", tmp_path / "audit" / "factory_audit.jsonl")
    monkeypatch.setattr(aw, "_last_entry_hash", None)
    tmp_store = tmp_path / "decisions_v2.jsonl"
    monkeypatch.setattr(store, "STORE_FILE", tmp_store)
    return tmp_store


def _propose(store_file, *, iid, payload):
    record = store.build_record(
        decision_family="ARTIFACT_VERSION", decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", resolved_target_ids=[CATALOG],
        decision="APPROVE", decision_origin="agent_proposed",
        proposed_by_id="tester", decision_instance_id=iid,
        payload=payload, reason="test", store_file=store_file)
    return store.append_record(record, store_file=store_file, emit_audit=False)


def _full_payload():
    return {"artifact_path": CATALOG, "artifact_hash_before": HASH_A,
           "from_version": "2.0", "to_version": "2.1",
           "expected_hash_after": HASH_A, "change_reason": "test"}


def _run_with_inputs(monkeypatch, capsys, inputs, argv):
    it = iter(inputs)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(it))
    monkeypatch.setattr("sys.argv", ["sign_artifact_version_proposal.py", *argv])
    rc = cli.main()
    return rc, capsys.readouterr()


def test_unknown_proposal_id_errors_without_prompting(monkeypatch, capsys, _isolate):
    rc, out = _run_with_inputs(monkeypatch, capsys, [],
                               ["--proposal-id", "ARTIFACT_VERSION-2026-999"])
    assert rc == 1
    assert "no existe" in out.err


def test_incomplete_payload_is_rejected(monkeypatch, capsys, _isolate):
    _propose(_isolate, iid="ARTIFACT_VERSION-2026-003", payload={})
    rc, out = _run_with_inputs(monkeypatch, capsys, [],
                               ["--proposal-id", "ARTIFACT_VERSION-2026-003"])
    assert rc == 1
    assert "no es firmable" in out.err


def test_mistyped_reconfirmation_of_proposal_id_aborts(monkeypatch, capsys, _isolate):
    _propose(_isolate, iid="ARTIFACT_VERSION-2026-005", payload=_full_payload())
    rc, out = _run_with_inputs(
        monkeypatch, capsys,
        inputs=["ARTIFACT_VERSION-2026-WRONG"],
        argv=["--proposal-id", "ARTIFACT_VERSION-2026-005"])
    assert rc == 1
    assert "no coincide" in out.err
    # nada se escribio
    assert len(store.read_all(_isolate)) == 1  # solo la propuesta original


def test_reserved_identity_is_rejected(monkeypatch, capsys, _isolate):
    _propose(_isolate, iid="ARTIFACT_VERSION-2026-005", payload=_full_payload())
    rc, out = _run_with_inputs(
        monkeypatch, capsys,
        inputs=["ARTIFACT_VERSION-2026-005", "2.1", "human"],
        argv=["--proposal-id", "ARTIFACT_VERSION-2026-005"])
    assert rc == 1
    assert len(store.read_all(_isolate)) == 1


def test_final_confirmation_word_required(monkeypatch, capsys, _isolate):
    _propose(_isolate, iid="ARTIFACT_VERSION-2026-005", payload=_full_payload())
    rc, out = _run_with_inputs(
        monkeypatch, capsys,
        inputs=["ARTIFACT_VERSION-2026-005", "2.1", "cesar", "Cesar May",
               "motivo real de prueba", "no"],
        argv=["--proposal-id", "ARTIFACT_VERSION-2026-005"])
    assert rc == 1
    assert "Cancelado" in out.out
    assert len(store.read_all(_isolate)) == 1


def test_full_successful_flow_writes_exactly_one_record(monkeypatch, capsys, _isolate):
    _propose(_isolate, iid="ARTIFACT_VERSION-2026-005", payload=_full_payload())
    rc, out = _run_with_inputs(
        monkeypatch, capsys,
        inputs=["ARTIFACT_VERSION-2026-005", "2.1", "cesar", "Cesar May",
               "motivo real de prueba", "FIRMAR"],
        argv=["--proposal-id", "ARTIFACT_VERSION-2026-005"])
    assert rc == 0
    assert "FIRMADO" in out.out
    assert "NO se aplico el bump" in out.out

    records = store.read_all(_isolate)
    assert len(records) == 2  # propuesta + confirmacion
    confirmacion = records[-1]
    assert confirmacion["decision_origin"] == "human_confirmed"
    assert confirmacion["approved_by_id"] == "cesar"
    assert confirmacion["approved_by_display_name"] == "Cesar May"
    assert confirmacion["payload"]["to_version"] == "2.1"


def test_no_force_flag_exists():
    """Regla dura §6.6: sin flags de fuerza. Se inspecciona el codigo fuente
    real de main() -- no una lista mantenida a mano que podria desincronizarse."""
    import inspect
    src = inspect.getsource(cli.main)
    add_argument_calls = [line for line in src.splitlines() if "add_argument" in line]
    assert len(add_argument_calls) == 1, f"se esperaba 1 sola opcion declarada: {add_argument_calls}"
    assert "--proposal-id" in add_argument_calls[0]
    assert "force" not in src.lower() and "--yes" not in src and "skip" not in src.lower()
