"""Tests -- factory.core.identity_registry / factory.api.auth (Paquete 2,
cierra hallazgo M: `decided_by`/`approved_by`/`reviewer`/`authored_by_id`
atados a identidad autenticada real en vez de texto libre en el body).

Cubre el modulo en aislamiento (sin FastAPI) y la dependencia HTTP contra
el router real, incluyendo el caso central que motiva el paquete: una
identidad autenticada NUNCA puede registrar una decision con el nombre de
otra persona -- el nombre lo fija el backend desde la key, el cliente no
lo controla ni aunque lo intente."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from factory.api import auth as _auth
from factory.core.identity_registry import (
    IdentityKeyError, load_registry, registry_path, resolve_identity,
)

CESAR_KEY = "clave-real-de-cesar-solo-para-test"
OTRO_KEY = "clave-real-de-otro-revisor-solo-para-test"


def _registry() -> dict[str, str]:
    return {
        hashlib.sha256(CESAR_KEY.encode()).hexdigest(): "Cesar",
        hashlib.sha256(OTRO_KEY.encode()).hexdigest(): "OtroRevisor",
    }


# ── resolve_identity: modulo puro, sin FastAPI ──────────────────────────────

class TestResolveIdentity:

    def test_known_key_resolves_to_its_real_name(self):
        assert resolve_identity(CESAR_KEY, _registry()) == "Cesar"

    def test_a_different_known_key_resolves_to_its_own_name_not_the_others(self):
        """El caso central: dos identidades registradas, cada key resuelve
        SOLO a su propio nombre -- nunca al de la otra."""
        assert resolve_identity(OTRO_KEY, _registry()) == "OtroRevisor"
        assert resolve_identity(CESAR_KEY, _registry()) != "OtroRevisor"
        assert resolve_identity(OTRO_KEY, _registry()) != "Cesar"

    def test_missing_key_is_rejected(self):
        with pytest.raises(IdentityKeyError, match="ausente"):
            resolve_identity("", _registry())

    def test_whitespace_only_key_is_rejected(self):
        with pytest.raises(IdentityKeyError, match="ausente"):
            resolve_identity("   ", _registry())

    def test_unknown_key_is_rejected(self):
        with pytest.raises(IdentityKeyError, match="desconocida"):
            resolve_identity("una-key-que-nadie-registro", _registry())

    def test_a_near_miss_key_is_rejected_not_fuzzy_matched(self):
        """Ni un solo caracter de diferencia resuelve -- no hay matching
        parcial ni normalizacion mas alla de strip()."""
        with pytest.raises(IdentityKeyError, match="desconocida"):
            resolve_identity(CESAR_KEY + "x", _registry())

    def test_empty_registry_rejects_every_key(self):
        """Registro sin provisionar: fail-closed, nadie firma nada."""
        with pytest.raises(IdentityKeyError, match="desconocida"):
            resolve_identity(CESAR_KEY, {})


# ── load_registry: lectura de archivo ───────────────────────────────────────

class TestLoadRegistry:

    def test_missing_file_returns_empty_dict(self, tmp_path):
        assert load_registry(tmp_path / "no-existe.yaml") == {}

    def test_loads_real_yaml_shape(self, tmp_path):
        key_hash = hashlib.sha256(CESAR_KEY.encode()).hexdigest()
        p = tmp_path / "identity_keys.yaml"
        p.write_text(
            f'identities:\n  - name: "Cesar"\n    key_sha256: "{key_hash}"\n',
            encoding="utf-8",
        )
        registry = load_registry(p)
        assert registry == {key_hash: "Cesar"}

    def test_entries_without_name_or_hash_are_skipped(self, tmp_path):
        p = tmp_path / "identity_keys.yaml"
        p.write_text(
            'identities:\n  - name: ""\n    key_sha256: "abc"\n'
            '  - name: "Sin Hash"\n    key_sha256: ""\n',
            encoding="utf-8",
        )
        assert load_registry(p) == {}

    def test_empty_file_returns_empty_dict(self, tmp_path):
        p = tmp_path / "identity_keys.yaml"
        p.write_text("", encoding="utf-8")
        assert load_registry(p) == {}

    def test_env_override_is_respected(self, tmp_path, monkeypatch):
        key_hash = hashlib.sha256(CESAR_KEY.encode()).hexdigest()
        p = tmp_path / "custom_identity_keys.yaml"
        p.write_text(
            f'identities:\n  - name: "Cesar"\n    key_sha256: "{key_hash}"\n',
            encoding="utf-8",
        )
        monkeypatch.setenv("IDENTITY_KEYS_FILE", str(p))
        assert registry_path() == p
        assert load_registry() == {key_hash: "Cesar"}


# ── require_identity: dependencia HTTP contra un router real ───────────────

@pytest.fixture()
def app_with_identity_probe(monkeypatch):
    """Router minimo, propio de este archivo -- no toca ningun endpoint
    real de gobernanza, solo verifica el contrato de la dependencia en
    aislamiento."""
    monkeypatch.setattr(_auth, "_REGISTRY", _registry())
    app = FastAPI()

    @app.post("/probe")
    async def probe(identity: str = Depends(_auth.require_identity)):
        return {"identity": identity}

    return TestClient(app)


class TestRequireIdentityDependency:

    def test_missing_header_is_401(self, app_with_identity_probe):
        r = app_with_identity_probe.post("/probe")
        assert r.status_code == 401

    def test_unknown_key_is_401(self, app_with_identity_probe):
        r = app_with_identity_probe.post("/probe", headers={"X-Identity-Key": "no-registrada"})
        assert r.status_code == 401

    def test_known_key_resolves_the_real_name(self, app_with_identity_probe):
        r = app_with_identity_probe.post("/probe", headers={"X-Identity-Key": CESAR_KEY})
        assert r.status_code == 200
        assert r.json()["identity"] == "Cesar"

    def test_client_cannot_impersonate_another_identity(self, app_with_identity_probe):
        """El caso que este paquete existe para cerrar: un cliente
        autenticado como 'OtroRevisor' no puede hacerse pasar por 'Cesar'
        -- no hay ningun campo que lo permita, el nombre viene solo de la
        key. Probar con la key de OtroRevisor nunca produce 'Cesar', pase
        lo que pase en cualquier otro lado de la peticion."""
        r = app_with_identity_probe.post("/probe", headers={"X-Identity-Key": OTRO_KEY})
        assert r.status_code == 200
        assert r.json()["identity"] == "OtroRevisor"
        assert r.json()["identity"] != "Cesar"
