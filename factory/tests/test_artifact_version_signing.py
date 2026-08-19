"""Panel ARQ 2026-08-04 -- `artifact_version_signing.py`: selector filtrado
por artifact_path, ciclo de vida derivado, y firma con echo-back.

GUARDIA DE AISLAMIENTO: ningun test de este archivo debe escribir en el
almacen real. La fixture `tmp_decisions` construye un almacen TEMPORAL
propio en cada test; se verifica ademas, al final de la suite del modulo,
que el almacen real no cambio (mismo patron que
`test_no_test_in_this_file_wrote_to_the_real_store` de
test_resignature_g2prime.py)."""
from __future__ import annotations

import hashlib
import json

import pytest

from factory.services import artifact_version_signing as avs
from factory.services import decision_store_v2 as store

CATALOG = "factory/regulatory/requirement_catalog/requirements.yaml"
GOLDEN = "factory/regulatory/golden_dataset/semantic_verification_golden_dataset.py"
HASH_A = "a" * 64
HASH_B = "b" * 64


@pytest.fixture(autouse=True)
def _isolate_audit(monkeypatch, tmp_path):
    """`compute_state_hash()`/`family_state_hash()` incluyen la cola del
    audit log REAL -- sin aislarlo, dos lecturas del mismo test ven un
    audit log que sigue creciendo por trafico ajeno y el state_hash nunca
    es reproducible (mismo patron que test_artifact_version_apply.py)."""
    from factory.core import audit_writer as aw
    monkeypatch.setattr(aw, "AUDIT_FILE", tmp_path / "audit" / "factory_audit.jsonl")
    monkeypatch.setattr(aw, "_last_entry_hash", None)


@pytest.fixture()
def tmp_decisions(tmp_path):
    return tmp_path / "decisions_v2.jsonl"


@pytest.fixture()
def tmp_versions(tmp_path):
    return tmp_path / "artifact_versions.jsonl"


def _propose(store_file, *, iid, artifact_path=CATALOG, payload=None,
            proposed_by="tester"):
    record = store.build_record(
        decision_family="ARTIFACT_VERSION", decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", resolved_target_ids=[artifact_path],
        decision="APPROVE", decision_origin="agent_proposed",
        proposed_by_id=proposed_by, decision_instance_id=iid,
        payload=payload, reason="test", store_file=store_file)
    return store.append_record(record, store_file=store_file, emit_audit=False)


def _confirm(store_file, *, iid_confirmed, iid_confirm, payload=None):
    record = store.build_record(
        decision_family="ARTIFACT_VERSION", decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", resolved_target_ids=[CATALOG],
        decision="APPROVE", decision_origin="human_confirmed",
        approved_by_id="cesar", approved_by_display_name="Cesar",
        confirms_instance_id=iid_confirmed, decision_instance_id=iid_confirm,
        payload=payload, reason="confirma", store_file=store_file)
    return store.append_record(record, store_file=store_file, emit_audit=False)


def _full_payload(**overrides):
    p = {
        "artifact_path": CATALOG, "artifact_hash_before": HASH_A,
        "from_version": "2.0", "to_version": "2.1",
        "expected_hash_after": HASH_A, "change_reason": "test",
    }
    p.update(overrides)
    return p


# ---------------------------------------------------------------------------
# Selector: filtro por artifact_path, ciclo de vida
# ---------------------------------------------------------------------------

def test_selector_filters_by_exact_artifact_path(tmp_decisions):
    _propose(tmp_decisions, iid="ARTIFACT_VERSION-2026-001", artifact_path=CATALOG,
            payload=_full_payload())
    _propose(tmp_decisions, iid="ARTIFACT_VERSION-2026-002", artifact_path=GOLDEN,
            payload={"artifact_path": GOLDEN})

    props = avs.list_artifact_version_proposals(CATALOG, store_file=tmp_decisions)
    ids = {p["proposal_id"] for p in props}
    assert ids == {"ARTIFACT_VERSION-2026-001"}


def test_lifecycle_proposed_when_unconfirmed(tmp_decisions):
    _propose(tmp_decisions, iid="ARTIFACT_VERSION-2026-001", payload=_full_payload())
    props = avs.list_artifact_version_proposals(CATALOG, store_file=tmp_decisions)
    assert props[0]["status"] == avs.STATUS_PROPOSED
    assert props[0]["payload_complete"] is True


def test_exposed_state_hash_is_family_scoped_not_global(tmp_decisions):
    """Regresion real (2026-08-04, encontrada probando el CLI fallback con
    almacen temporal): esta funcion devolvia compute_state_hash() GLOBAL,
    pero sign_artifact_version_proposal() lo reenvia como family_state_hash
    a confirm() -- desajuste garantizado, 409 siempre. El endpoint HTTP y
    el JS real (via GOV.family_state_hashes.ARTIFACT_VERSION) exigen el
    mismo ambito: de familia."""
    from factory.services import governance_service as gov
    _propose(tmp_decisions, iid="ARTIFACT_VERSION-2026-001", payload=_full_payload())
    props = avs.list_artifact_version_proposals(CATALOG, store_file=tmp_decisions)
    esperado = gov.family_state_hash("ARTIFACT_VERSION", store_file=tmp_decisions)
    assert props[0]["state_hash"] == esperado
    assert props[0]["state_hash"] != gov.compute_state_hash(store_file=tmp_decisions)


def test_lifecycle_signed_when_confirmed_but_not_applied(tmp_decisions, tmp_versions):
    _propose(tmp_decisions, iid="ARTIFACT_VERSION-2026-001", payload=_full_payload())
    _confirm(tmp_decisions, iid_confirmed="ARTIFACT_VERSION-2026-001",
            iid_confirm="ARTIFACT_VERSION-2026-002")
    # ningun version_record referencia -002 todavia -- apply() no corrio.
    props = avs.list_artifact_version_proposals(
        CATALOG, store_file=tmp_decisions, versions_store_file=tmp_versions)
    assert props[0]["status"] == avs.STATUS_SIGNED


def test_lifecycle_applied_when_version_record_references_the_confirmation(
        tmp_decisions, tmp_versions):
    _propose(tmp_decisions, iid="ARTIFACT_VERSION-2026-001", payload=_full_payload())
    _confirm(tmp_decisions, iid_confirmed="ARTIFACT_VERSION-2026-001",
            iid_confirm="ARTIFACT_VERSION-2026-002")
    tmp_versions.write_text(json.dumps({
        "artifact": "catalog", "artifact_id": CATALOG, "version": "2.1",
        "sha256": HASH_A, "approved_by_decision": "ARTIFACT_VERSION-2026-002",
    }) + "\n", encoding="utf-8")

    props = avs.list_artifact_version_proposals(
        CATALOG, store_file=tmp_decisions, versions_store_file=tmp_versions)
    assert props[0]["status"] == avs.STATUS_APPLIED


def test_lifecycle_withdrawn_when_expired(tmp_decisions, monkeypatch):
    from datetime import datetime, timedelta, timezone
    old = (datetime.now(timezone.utc) - timedelta(hours=999)).isoformat()
    record = store.build_record(
        decision_family="ARTIFACT_VERSION", decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", resolved_target_ids=[CATALOG],
        decision="APPROVE", decision_origin="agent_proposed",
        proposed_by_id="tester", decision_instance_id="ARTIFACT_VERSION-2026-001",
        payload=_full_payload(), reason="test", store_file=tmp_decisions,
        decision_date=old)
    record["recorded_at"] = old
    store.append_record(record, store_file=tmp_decisions, emit_audit=False)

    props = avs.list_artifact_version_proposals(CATALOG, store_file=tmp_decisions)
    assert props[0]["status"] == avs.STATUS_WITHDRAWN


def test_the_real_case_001_is_applied_003_is_proposed_incomplete_005_is_proposed_complete(
        tmp_decisions, tmp_versions):
    """Fixture del caso real (2026-08-04): -001 aplicada via -002, -003
    huerfana con payload vacio, -005 completa y vigente."""
    _propose(tmp_decisions, iid="ARTIFACT_VERSION-2026-001", payload={})
    _confirm(tmp_decisions, iid_confirmed="ARTIFACT_VERSION-2026-001",
            iid_confirm="ARTIFACT_VERSION-2026-002")
    tmp_versions.write_text(json.dumps({
        "artifact": "catalog", "artifact_id": CATALOG, "version": "2.0",
        "sha256": "dc0" + "0" * 61, "approved_by_decision": "ARTIFACT_VERSION-2026-002",
    }) + "\n", encoding="utf-8")
    _propose(tmp_decisions, iid="ARTIFACT_VERSION-2026-003", payload={})
    _propose(tmp_decisions, iid="ARTIFACT_VERSION-2026-005", payload=_full_payload())

    props = {p["proposal_id"]: p for p in avs.list_artifact_version_proposals(
        CATALOG, store_file=tmp_decisions, versions_store_file=tmp_versions)}
    assert props["ARTIFACT_VERSION-2026-001"]["status"] == avs.STATUS_APPLIED
    assert props["ARTIFACT_VERSION-2026-003"]["status"] == avs.STATUS_PROPOSED
    assert props["ARTIFACT_VERSION-2026-003"]["payload_complete"] is False
    assert props["ARTIFACT_VERSION-2026-005"]["status"] == avs.STATUS_PROPOSED
    assert props["ARTIFACT_VERSION-2026-005"]["payload_complete"] is True


# ---------------------------------------------------------------------------
# Firma con echo-back: cada rama de rechazo + el camino de exito
# ---------------------------------------------------------------------------

def _state_hash(store_file):
    """El `state_hash` que este flujo firma es de FAMILIA (ARTIFACT_VERSION),
    no el global -- `sign_artifact_version_proposal` lo reenvia como
    `family_state_hash` a `confirm()` (mismo ambito que usa el JS real via
    `GOV.family_state_hashes.ARTIFACT_VERSION`)."""
    from factory.services import governance_service as gov
    return gov.family_state_hash("ARTIFACT_VERSION", store_file=store_file)


def test_sign_rejects_unknown_proposal_id(tmp_decisions):
    with pytest.raises(avs.ProposalMismatchError, match="no existe"):
        avs.sign_artifact_version_proposal(
            proposal_id="ARTIFACT_VERSION-2026-999", artifact_path=CATALOG,
            from_version="2.0", to_version="2.1", artifact_hash_before=HASH_A,
            expected_hash_after=HASH_A, state_hash=_state_hash(tmp_decisions),
            reason="test", approved_by_id="cesar", store_file=tmp_decisions)


@pytest.mark.parametrize("field,wrong_value", [
    ("from_version", "1.0"),
    ("to_version", "3.0"),
    ("artifact_hash_before", HASH_B),
    ("expected_hash_after", HASH_B),
])
def test_sign_rejects_any_echo_back_mismatch(tmp_decisions, field, wrong_value):
    _propose(tmp_decisions, iid="ARTIFACT_VERSION-2026-001", payload=_full_payload())
    kwargs = dict(
        proposal_id="ARTIFACT_VERSION-2026-001", artifact_path=CATALOG,
        from_version="2.0", to_version="2.1", artifact_hash_before=HASH_A,
        expected_hash_after=HASH_A, state_hash=_state_hash(tmp_decisions),
        reason="test", approved_by_id="cesar", store_file=tmp_decisions)
    kwargs[field] = wrong_value
    with pytest.raises(avs.ProposalMismatchError, match="echo-back"):
        avs.sign_artifact_version_proposal(**kwargs)


def test_sign_rejects_artifact_path_mismatch_as_not_found(tmp_decisions):
    """`artifact_path` es la CLAVE de busqueda, no solo un campo de
    echo-back: mandar el path equivocado busca la propuesta bajo un
    artefacto donde no existe -- se rechaza como "no existe", mensaje
    distinto pero igual de fail-closed que un mismatch de contenido."""
    _propose(tmp_decisions, iid="ARTIFACT_VERSION-2026-001", payload=_full_payload())
    with pytest.raises(avs.ProposalMismatchError, match="no existe"):
        avs.sign_artifact_version_proposal(
            proposal_id="ARTIFACT_VERSION-2026-001", artifact_path=GOLDEN,
            from_version="2.0", to_version="2.1", artifact_hash_before=HASH_A,
            expected_hash_after=HASH_A, state_hash=_state_hash(tmp_decisions),
            reason="test", approved_by_id="cesar", store_file=tmp_decisions)


def test_sign_rejects_duplicate_when_already_applied(tmp_decisions, tmp_versions):
    _propose(tmp_decisions, iid="ARTIFACT_VERSION-2026-001", payload=_full_payload())
    _confirm(tmp_decisions, iid_confirmed="ARTIFACT_VERSION-2026-001",
            iid_confirm="ARTIFACT_VERSION-2026-002")
    tmp_versions.write_text(json.dumps({
        "artifact": "catalog", "artifact_id": CATALOG, "version": "2.1",
        "sha256": HASH_A, "approved_by_decision": "ARTIFACT_VERSION-2026-002",
    }) + "\n", encoding="utf-8")

    with pytest.raises(avs.DuplicateSignatureError):
        avs.sign_artifact_version_proposal(
            proposal_id="ARTIFACT_VERSION-2026-001", **{k: v for k, v in
            _full_payload().items() if k != "change_reason"},
            state_hash=_state_hash(tmp_decisions), reason="test",
            approved_by_id="cesar", store_file=tmp_decisions,
            versions_store_file=tmp_versions)


def test_sign_success_writes_exactly_one_confirming_record(tmp_decisions):
    _propose(tmp_decisions, iid="ARTIFACT_VERSION-2026-001", payload=_full_payload())
    before_lines = tmp_decisions.read_text(encoding="utf-8").splitlines()

    result = avs.sign_artifact_version_proposal(
        proposal_id="ARTIFACT_VERSION-2026-001", **{k: v for k, v in
        _full_payload().items() if k != "change_reason"},
        state_hash=_state_hash(tmp_decisions), reason="firmado en test",
        approved_by_id="cesar", approved_by_display_name="Cesar May",
        store_file=tmp_decisions)

    after_lines = tmp_decisions.read_text(encoding="utf-8").splitlines()
    assert len(after_lines) == len(before_lines) + 1
    assert result["decision_origin"] == "human_confirmed"
    assert result["confirms_instance_id"] == "ARTIFACT_VERSION-2026-001"
    assert result["approved_by_id"] == "cesar"
    assert result["payload"]["to_version"] == "2.1"


def test_sign_rejects_stale_state_hash(tmp_decisions):
    _propose(tmp_decisions, iid="ARTIFACT_VERSION-2026-001", payload=_full_payload())
    from factory.services import governance_service as gov
    with pytest.raises(gov.StaleStateError):
        avs.sign_artifact_version_proposal(
            proposal_id="ARTIFACT_VERSION-2026-001", **{k: v for k, v in
            _full_payload().items() if k != "change_reason"},
            state_hash="0" * 64, reason="test", approved_by_id="cesar",
            store_file=tmp_decisions)


# ---------------------------------------------------------------------------
# HTTP -- mismo patron de test_governance_endpoints.py (monkeypatch de
# store.STORE_FILE + TestClient real sobre el router real)
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(tmp_decisions, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from factory.api.routes import layer9

    monkeypatch.setattr(store, "STORE_FILE", tmp_decisions)
    app = FastAPI()
    app.include_router(layer9.router)
    return TestClient(app)


def test_http_proposals_endpoint_filters_by_artifact_path(client, tmp_decisions):
    _propose(tmp_decisions, iid="ARTIFACT_VERSION-2026-001", payload=_full_payload())
    _propose(tmp_decisions, iid="ARTIFACT_VERSION-2026-002", artifact_path=GOLDEN,
            payload={"artifact_path": GOLDEN})

    r = client.get("/api/v1/layer9/governance/artifact-version/proposals",
                   params={"artifact_path": CATALOG})
    assert r.status_code == 200
    ids = {p["proposal_id"] for p in r.json()["proposals"]}
    assert ids == {"ARTIFACT_VERSION-2026-001"}


def test_http_sign_returns_409_with_reason_on_mismatch(client, tmp_decisions, identity_headers):
    _propose(tmp_decisions, iid="ARTIFACT_VERSION-2026-001", payload=_full_payload())
    r = client.post("/api/v1/layer9/governance/artifact-version/sign", json={
        "proposal_id": "ARTIFACT_VERSION-2026-001", "artifact_path": CATALOG,
        "from_version": "1.0",  # mismatch deliberado
        "to_version": "2.1", "artifact_hash_before": HASH_A,
        "expected_hash_after": HASH_A, "state_hash": _state_hash(tmp_decisions),
        "reason": "test",
    }, headers=identity_headers)
    assert r.status_code == 409
    assert r.json()["detail"]["reason"] == "proposal_mismatch"


def test_http_sign_success_end_to_end(client, tmp_decisions, identity_headers):
    _propose(tmp_decisions, iid="ARTIFACT_VERSION-2026-001", payload=_full_payload())
    r = client.post("/api/v1/layer9/governance/artifact-version/sign", json={
        "proposal_id": "ARTIFACT_VERSION-2026-001", "artifact_path": CATALOG,
        "from_version": "2.0", "to_version": "2.1",
        "artifact_hash_before": HASH_A, "expected_hash_after": HASH_A,
        "state_hash": _state_hash(tmp_decisions),
        "reason": "test http",
        "approved_by_display_name": "Cesar May",
    }, headers=identity_headers)
    assert r.status_code == 201, r.text
    assert r.json()["decision_origin"] == "human_confirmed"
    assert r.json()["approved_by_id"] == "Cesar"


# ---------------------------------------------------------------------------
# Guardia de aislamiento -- ningun test de este archivo toco el almacen real
# ---------------------------------------------------------------------------

def test_no_test_in_this_file_wrote_to_the_real_store():
    import subprocess
    from factory.services import decision_store_v2 as _store
    real = _store.STORE_FILE
    if not real.is_file():
        pytest.skip("almacen real no presente en este entorno")
    from pathlib import Path
    repo = Path(__file__).resolve().parents[2]
    rel = real.relative_to(repo).as_posix()
    r = subprocess.run(["git", "-C", str(repo), "diff", "--quiet", "HEAD", "--", rel])
    assert r.returncode == 0, "algun test de este archivo escribio en el almacen real"
