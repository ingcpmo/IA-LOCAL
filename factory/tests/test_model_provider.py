"""
Tests -- W5 V2 Fase D: factory.engines.gmpai_integrity.model_provider.

Cubre: OllamaProvider delega 1:1 en ollama_client (cero cambio de
comportamiento); evaluate_chunked() con un ModelProvider custom NUNCA toca
ollama_client (prueba real de desacoplamiento, no solo cosmética); el
Protocol es runtime_checkable contra cualquier implementación que cumpla
la interfaz.
"""
import json
from pathlib import Path

import pytest

from factory.engines.gmpai_integrity import chunked_engine as ce
from factory.engines.gmpai_integrity import ollama_client
from factory.engines.gmpai_integrity.model_provider import (
    DEFAULT_PROVIDER, ModelProvider, OllamaProvider,
)

PROMPT_PATH = Path(__file__).parent.parent / "engines" / "gmpai_integrity" / "prompts" / "part11_prompts.yaml"


def _ollama_response(payload: dict) -> dict:
    return {"response": json.dumps(payload)}


def _all_insufficient():
    reqs = ("21_CFR_11.10(a)", "21_CFR_11.10(d)", "21_CFR_11.10(e)", "21_CFR_11.10(g)", "21_CFR_11.50_11.70")
    return {"checkpoints": [
        {"req_id": r, "estado": "evidencia_insuficiente", "evidencia_exacta": "", "brecha": "n/a", "recomendacion": "n/a"}
        for r in reqs
    ]}


class FakeProvider:
    """Implementación independiente de ollama_client, para probar
    desacoplamiento real -- si evaluate_chunked() llamara a ollama_client
    por accidente en vez de a `provider`, estos tests fallarían (el fake
    nunca produce esa respuesta y ollama_client real no está mockeado
    aquí, así que fallaría al intentar una conexión real)."""

    def __init__(self):
        self.generate_calls = 0

    @property
    def model_name(self) -> str:
        return "fake-model-v1"

    def generate(self, prompt: str) -> dict:
        self.generate_calls += 1
        return _ollama_response(_all_insufficient())

    def show_digest(self) -> str:
        return "sha256:fake-provider-digest"

    def runtime_version(self) -> str:
        return "9.9.9-fake"


class TestOllamaProviderDelegatesToOllamaClient:

    def test_model_name_reads_ollama_client_constant(self, monkeypatch):
        monkeypatch.setattr(ollama_client, "OLLAMA_MODEL", "some-model:tag")
        assert OllamaProvider().model_name == "some-model:tag"

    def test_generate_delegates(self, monkeypatch):
        calls = []
        monkeypatch.setattr(ollama_client, "generate", lambda p, *a, **k: (calls.append(p), {"response": "{}"})[1])
        OllamaProvider().generate("mi prompt")
        assert calls == ["mi prompt"]

    def test_show_digest_delegates(self, monkeypatch):
        monkeypatch.setattr(ollama_client, "show_digest", lambda: "sha256:abc")
        assert OllamaProvider().show_digest() == "sha256:abc"

    def test_runtime_version_delegates_to_ollama_version(self, monkeypatch):
        monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.21.2")
        assert OllamaProvider().runtime_version() == "0.21.2"

    def test_show_digest_propagates_unavailable_error(self, monkeypatch):
        def _raise():
            raise ollama_client.OllamaUnavailableError("no disponible")
        monkeypatch.setattr(ollama_client, "show_digest", _raise)
        with pytest.raises(ollama_client.OllamaUnavailableError):
            OllamaProvider().show_digest()


class TestModelProviderProtocolRuntimeCheckable:

    def test_ollama_provider_is_instance_of_protocol(self):
        assert isinstance(OllamaProvider(), ModelProvider)

    def test_fake_provider_is_instance_of_protocol(self):
        assert isinstance(FakeProvider(), ModelProvider)

    def test_object_missing_methods_is_not_instance(self):
        class Incomplete:
            @property
            def model_name(self) -> str:
                return "x"
        assert not isinstance(Incomplete(), ModelProvider)


class TestEvaluateChunkedNeverTouchesOllamaClientWithCustomProvider:

    def test_custom_provider_is_used_exclusively(self, monkeypatch, tmp_path):
        """Prueba dura de desacoplamiento: NO se mockea ollama_client en
        absoluto. Si evaluate_chunked() llamara a ollama_client.generate
        real, esto lanzaría un error de conexión (httpx) y el test
        fallaría -- pasar confirma que solo `provider` fue invocado."""
        pages = ["Pagina de prueba real " * 100]
        fake = FakeProvider()
        checkpoint_dir = tmp_path / "checkpoints"
        result = ce.evaluate_chunked(
            PROMPT_PATH, agent_id="fda_part11_agent", agent_version="v-test",
            per_unit_text=pages, sistema="sys", documento="doc", version="v1",
            archivo="doc.pdf", document_sha256="a" * 64,
            run_context="validation", provider=fake,
        )
        assert fake.generate_calls >= 1
        assert result["model"] == "fake-model-v1"
        assert result["model_digest"] == "sha256:fake-provider-digest"
        assert result["ollama_version"] == "9.9.9-fake"

    def test_default_provider_constant_is_an_ollama_provider(self):
        assert isinstance(DEFAULT_PROVIDER, OllamaProvider)

    def test_provider_none_falls_back_to_default_provider(self, monkeypatch, tmp_path):
        """Mismo patron que los tests existentes (mockean ollama_client
        directo) -- confirma que provider=None (default) sigue usando
        DEFAULT_PROVIDER -> ollama_client, sin romper compatibilidad."""
        pages = ["Pagina de prueba real " * 100]
        monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(_all_insufficient()))
        monkeypatch.setattr(ollama_client, "show_digest", lambda: "sha256:default-path")
        monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
        result = ce.evaluate_chunked(
            PROMPT_PATH, agent_id="fda_part11_agent", agent_version="v-test",
            per_unit_text=pages, sistema="sys", documento="doc", version="v1",
            archivo="doc.pdf", document_sha256="b" * 64,
            run_context="validation",
        )
        assert result["model_digest"] == "sha256:default-path"
