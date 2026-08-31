"""H-1 — identidad autenticada en los 7 mutadores críticos (diseño
`DISENO_H1_H10_ACTUALIZADO_R0_R5_20260829`). D-1 = herramienta de apoyo a la
decisión ⇒ atribución autenticada, NO firma electrónica Part 11 formal.

Verifica, para cada uno de los 7 "rojos" de R-3:
  - sin `X-Identity-Key`  ⇒ 401 (no decide nada)
  - con identidad válida  ⇒ el actor NO se toma del body; se deriva de la identidad resuelta
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from factory.api.routes import approvals, layer8, layer9, releases, workspaces


# ── clients por router ────────────────────────────────────────────────────
def _client(router) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def approvals_client():
    return _client(approvals.router)


@pytest.fixture
def layer8_client():
    return _client(layer8.router)


@pytest.fixture
def layer9_client():
    return _client(layer9.router)


@pytest.fixture
def releases_client():
    return _client(releases.router)


@pytest.fixture
def workspaces_client():
    return _client(workspaces.router)


# ── 1) test paramétrico: los 7 rojos rechazan sin identidad ───────────────
CRITICAL_MUTATORS = [
    ("approvals",  "post", "/api/v1/approvals/p1/confirm", {"action": "release"}),
    ("approvals",  "post", "/api/v1/approvals/p1/reject",  {"action": "release"}),
    ("layer8",     "post", "/api/v1/layer8/missions/p1/deploy-if-authorized", None),
    ("layer9",     "post", "/api/v1/layer9/review/rc-x/mark-canonical", {}),
    ("layer9",     "post", "/api/v1/layer9/w5-decisions/D1/correct", {"reason": "x"}),
    ("releases",   "post", "/api/v1/releases/p1/v1.0", {"workspace_path": "/tmp/nope"}),
    ("workspaces", "delete", "/api/v1/workspaces/p1", None),
]


@pytest.mark.parametrize("router_name,method,path,body", CRITICAL_MUTATORS,
                         ids=[m[2] for m in CRITICAL_MUTATORS])
def test_critical_mutator_without_identity_is_401(
        router_name, method, path, body,
        approvals_client, layer8_client, layer9_client, releases_client, workspaces_client):
    client = {
        "approvals": approvals_client, "layer8": layer8_client, "layer9": layer9_client,
        "releases": releases_client, "workspaces": workspaces_client,
    }[router_name]
    fn = getattr(client, method)
    r = fn(path, json=body) if body is not None else fn(path)
    assert r.status_code == 401, (
        f"{method.upper()} {path} respondió {r.status_code} sin X-Identity-Key "
        f"(debe ser 401): {r.text[:200]}")


@pytest.mark.parametrize("router_name,method,path,body", CRITICAL_MUTATORS,
                         ids=[m[2] for m in CRITICAL_MUTATORS])
def test_critical_mutator_with_unknown_identity_key_is_401(
        router_name, method, path, body,
        approvals_client, layer8_client, layer9_client, releases_client, workspaces_client):
    client = {
        "approvals": approvals_client, "layer8": layer8_client, "layer9": layer9_client,
        "releases": releases_client, "workspaces": workspaces_client,
    }[router_name]
    fn = getattr(client, method)
    h = {"X-Identity-Key": "clave-no-registrada"}
    r = fn(path, json=body, headers=h) if body is not None else fn(path, headers=h)
    assert r.status_code == 401


# ── 2) approvals/confirm: approved_by SE DERIVA de la identidad, no del body ──
def test_confirm_derives_approved_by_from_identity_not_body(
        approvals_client, identity_headers, isolated_audit, tmp_path, monkeypatch):
    # aísla la escritura de ficheros del endpoint
    monkeypatch.setattr(approvals, "WORKSPACES_DIR", tmp_path / "ws")
    monkeypatch.setattr(approvals, "APPROVALS_DIR", tmp_path / "approvals")
    r = approvals_client.post(
        "/api/v1/approvals/proj_h1/confirm",
        json={"action": "release", "version": "v1.0",
              # aunque un cliente intente colar approved_by, el body ya no lo acepta
              "approved_by": "Atacante"},
        headers={**identity_headers, "X-Change-Reason": "cierre H-1"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["approved_by"] == "Cesar"          # la identidad resuelta, NO "Atacante"
    assert body["recorded_by"] == "Cesar"
    assert body["decision_origin"] == "human_confirmed"
    assert body["change_reason"] == "cierre H-1"


def test_reject_derives_rejected_by_from_identity(
        approvals_client, identity_headers, isolated_audit, tmp_path, monkeypatch):
    monkeypatch.setattr(approvals, "APPROVALS_DIR", tmp_path / "approvals")
    r = approvals_client.post(
        "/api/v1/approvals/proj_h1/reject",
        json={"action": "release", "approved_by": "Atacante"},
        headers=identity_headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["rejected_by"] == "Cesar"
    assert r.json()["recorded_by"] == "Cesar"


def test_confirm_body_no_longer_has_approved_by_field():
    """El esquema ConfirmBody ya no expone approved_by/recorded_by."""
    fields = set(approvals.ConfirmBody.model_fields)
    assert "approved_by" not in fields
    assert "recorded_by" not in fields


def test_w5_correction_uses_identity_as_corrected_by(layer9_client, identity_headers, isolated_audit):
    # D1 no existe en el store aislado -> 404, pero la identidad ya se exigió (no 401)
    r = layer9_client.post("/api/v1/layer9/w5-decisions/D_inexistente/correct",
                           json={"reason": "x"}, headers=identity_headers)
    assert r.status_code in (404, 422)   # llegó más allá del gate de identidad
    assert r.status_code != 401
