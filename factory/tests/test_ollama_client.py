"""
Tests de factory.engines.gmpai_integrity.ollama_client.show_digest() --
Ollama SIEMPRE mockeado via monkeypatch de httpx.get (nunca un servidor
real en la suite pytest).

Cubre el fix 2026-07-16 (post-mortem piloto Autoclave URS): show_digest()
consultaba /api/show, que dejo de incluir el campo 'digest' en Ollama
>=0.21 (verificado en vivo contra la version 0.21.2 -- confirmado que el
digest real vive en la entrada por-modelo de /api/tags). Se corrigio para
consultar /api/tags; estos tests fijan ese contrato para que una regresion
futura (ej. volver a /api/show) rompa la suite en vez de fallar en
produccion contra un servidor Ollama real.
"""
import httpx
import pytest

from factory.engines.gmpai_integrity import ollama_client


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return self._json


def test_show_digest_reads_from_api_tags_not_api_show(monkeypatch):
    """El digest se obtiene de /api/tags (entrada por-modelo), no de /api/show."""
    calls = []

    def fake_get(url, timeout=None):
        calls.append(url)
        assert url.endswith("/api/tags"), "show_digest debe consultar /api/tags, no /api/show"
        return _FakeResponse({"models": [
            {"name": ollama_client.OLLAMA_MODEL, "model": ollama_client.OLLAMA_MODEL,
             "digest": "sha256:realdigest123"},
            {"name": "otro-modelo:latest", "model": "otro-modelo:latest", "digest": "sha256:otro"},
        ]})

    monkeypatch.setattr(httpx, "get", fake_get)
    digest = ollama_client.show_digest()
    assert digest == "sha256:realdigest123"
    assert calls == [f"{ollama_client.OLLAMA_BASE_URL}/api/tags"]


def test_show_digest_raises_explicit_when_model_not_in_tags(monkeypatch):
    """Si el modelo configurado no aparece en /api/tags, falla explicito (nunca None silencioso -- TE-02)."""
    monkeypatch.setattr(httpx, "get", lambda url, timeout=None: _FakeResponse({"models": [
        {"name": "otro-modelo:latest", "model": "otro-modelo:latest", "digest": "sha256:otro"},
    ]}))
    with pytest.raises(ollama_client.OllamaUnavailableError, match="no incluye el modelo"):
        ollama_client.show_digest()


def test_show_digest_raises_explicit_when_digest_field_missing(monkeypatch):
    """Si el modelo aparece pero sin campo digest, falla explicito (regresion tipo /api/show sin digest)."""
    monkeypatch.setattr(httpx, "get", lambda url, timeout=None: _FakeResponse({"models": [
        {"name": ollama_client.OLLAMA_MODEL, "model": ollama_client.OLLAMA_MODEL},
    ]}))
    with pytest.raises(ollama_client.OllamaUnavailableError, match="sin campo digest"):
        ollama_client.show_digest()


def test_show_digest_raises_explicit_on_connection_error(monkeypatch):
    """Ollama no alcanzable -- OllamaUnavailableError explicito, nunca None silencioso (TE-02)."""
    def fake_get(url, timeout=None):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(httpx, "get", fake_get)
    with pytest.raises(ollama_client.OllamaUnavailableError, match="no alcanzable"):
        ollama_client.show_digest()
