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


# ── Fase 5.4.4: clasificacion de rejection_reason en generate_controlled() ──
#
# Antes de este fix, generate_controlled() SIEMPRE devolvia
# rejection_reason="schema_validation_failed" para cualquier fallo (incluso
# JSON no parseable), y un fallo de transporte HTTP no se capturaba en
# absoluto -- se propagaba como excepcion no controlada y abortaba toda la
# corrida del runner (perdiendo el analisis ya completado de otros
# requisitos/chunks). Estos tests fijan las 3 causas reales, distintas entre
# si, para que una regresion futura que las vuelva a colapsar rompa la suite.

_VALID_CHUNK = {"text": "fragmento de prueba"}


def _fixed_digest(monkeypatch, value="digest-fixed"):
    """_get_digest_cached() usa un cache por-proceso (default mutable
    compartido entre tests) -- se sustituye la funcion entera para que cada
    test sea independiente del orden de ejecucion."""
    monkeypatch.setattr(ollama_client, "_get_digest_cached", lambda: value)


def test_generate_controlled_classifies_ollama_transport_failed(monkeypatch):
    _fixed_digest(monkeypatch)

    def fake_post(url, json=None, timeout=None):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(httpx, "post", fake_post)

    result = ollama_client.generate_controlled("prompt", _VALID_CHUNK, run_context="validation")

    assert result["ok"] is False
    assert result["status"] == "rejected_by_verifier"
    assert result["rejection_reason"] == "ollama_transport_failed"
    assert result["llm_output"] is None
    assert result["raw_response"] is None
    assert any("ollama_transport_failed" in e for e in result["errors"])


def test_generate_controlled_classifies_json_parse_failed(monkeypatch):
    _fixed_digest(monkeypatch)
    monkeypatch.setattr(httpx, "post", lambda url, json=None, timeout=None: _FakeResponse(
        {"response": "esto no es json valido {{{"}
    ))

    result = ollama_client.generate_controlled("prompt", _VALID_CHUNK, run_context="validation")

    assert result["ok"] is False
    assert result["status"] == "rejected_by_verifier"
    assert result["rejection_reason"] == "json_parse_failed"
    assert result["llm_output"] is None
    assert result["raw_response"] == "esto no es json valido {{{"
    assert result["errors"] == ["respuesta del modelo no es JSON valido"]


def test_generate_controlled_classifies_schema_validation_failed(monkeypatch):
    """Mismo caso real reproducido en el canario de Fase 5.4.4: JSON valido,
    pero confidence en escala 0-100 en vez de 0-1."""
    import json as json_mod

    _fixed_digest(monkeypatch)
    bad_payload = json_mod.dumps({
        "requirement_id": "ALCOA_ACCURATE", "chunk_observation": "observed",
        "evidence_quote": "cita", "evidence_page": 1, "confidence": 100,
        "rationale": "n/a",
    })
    monkeypatch.setattr(httpx, "post", lambda url, json=None, timeout=None: _FakeResponse(
        {"response": bad_payload}
    ))

    result = ollama_client.generate_controlled("prompt", _VALID_CHUNK, run_context="validation")

    assert result["ok"] is False
    assert result["status"] == "rejected_by_verifier"
    assert result["rejection_reason"] == "schema_validation_failed"
    assert result["llm_output"] is None
    assert result["raw_response"] == bad_payload
    assert any("confidence" in e for e in result["errors"])


def test_generate_controlled_ok_when_valid(monkeypatch):
    import json as json_mod

    _fixed_digest(monkeypatch)
    good_payload = json_mod.dumps({
        "requirement_id": "ALCOA_ACCURATE", "chunk_observation": "observed",
        "evidence_quote": "cita", "evidence_page": 1, "confidence": 0.9,
        "rationale": "n/a",
    })
    monkeypatch.setattr(httpx, "post", lambda url, json=None, timeout=None: _FakeResponse(
        {"response": good_payload}
    ))

    result = ollama_client.generate_controlled("prompt", _VALID_CHUNK, run_context="validation")

    assert result["ok"] is True
    assert result["status"] == "verified"
    assert result["rejection_reason"] is None
    assert result["llm_output"]["confidence"] == 0.9


def test_generate_controlled_rejection_reasons_are_never_confused(monkeypatch):
    """Las 3 causas de rechazo deben ser mutuamente distintas -- confirma
    que ninguna clasificacion colapsa sobre otra (el bug original: todo
    caia en 'schema_validation_failed', incluidas causas no relacionadas
    con el schema)."""
    import json as json_mod
    _fixed_digest(monkeypatch)

    def _run_with_response(make_response):
        monkeypatch.setattr(httpx, "post", make_response)
        return ollama_client.generate_controlled("prompt", _VALID_CHUNK, run_context="validation")

    def _transport(url, json=None, timeout=None):
        raise httpx.ConnectError("refused")
    r_transport = _run_with_response(_transport)

    r_json = _run_with_response(
        lambda url, json=None, timeout=None: _FakeResponse({"response": "{no valido"})
    )

    bad_schema = json_mod.dumps({
        "requirement_id": "ALCOA_ACCURATE", "chunk_observation": "observed",
        "evidence_quote": "cita", "evidence_page": 1, "confidence": 100,
        "rationale": "n/a",
    })
    r_schema = _run_with_response(
        lambda url, json=None, timeout=None: _FakeResponse({"response": bad_schema})
    )

    reasons = {r_transport["rejection_reason"], r_json["rejection_reason"], r_schema["rejection_reason"]}
    assert reasons == {"ollama_transport_failed", "json_parse_failed", "schema_validation_failed"}, (
        f"las 3 causas deben ser distintas entre si, obtuvo: {reasons}"
    )


def test_generate_controlled_manifest_incomplete_never_becomes_rejection_reason(monkeypatch):
    """P1 (doctrina ya decidida, ver comentario en _get_digest_cached): un
    manifiesto incompleto NO invalida el hallazgo. Confirma que aunque el
    digest no este disponible, un JSON valido que cumple el schema sigue
    siendo 'verified' con rejection_reason=None -- manifest_incomplete
    NUNCA debe convertirse en una causa de rechazo."""
    import json as json_mod

    monkeypatch.setattr(ollama_client, "_get_digest_cached", lambda: None)
    good_payload = json_mod.dumps({
        "requirement_id": "ALCOA_ACCURATE", "chunk_observation": "observed",
        "evidence_quote": "cita", "evidence_page": 1, "confidence": 0.9,
        "rationale": "n/a",
    })
    monkeypatch.setattr(httpx, "post", lambda url, json=None, timeout=None: _FakeResponse(
        {"response": good_payload}
    ))

    result = ollama_client.generate_controlled("prompt", _VALID_CHUNK, run_context="validation")

    assert result["execution_manifest"]["manifest_incomplete"] is True
    assert result["ok"] is True
    assert result["status"] == "verified"
    assert result["rejection_reason"] is None
