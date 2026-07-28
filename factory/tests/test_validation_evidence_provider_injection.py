"""Gate 14 de la seccion 22 del plan W5 V2 ("100% de agentes hibridos con
ModelProvider") sobre `run_validation_evidence.py`.

Hasta 2026-07-28 este runner llamaba a `ollama_client.generate_controlled()`,
`show_digest()`, `ollama_version()` y `OLLAMA_MODEL` directamente. Era el
unico incumplimiento real del gate en codigo git-trackeado, y significaba
que la evidencia regulatoria no se podia producir contra otro modelo sin
editar el modulo.

La prueba dura de desacoplamiento es la misma que uso Fase D para el motor:
inyectar un provider falso SIN mockear nada de `ollama_client`. Si el runner
tocara el cliente global por accidente, el test fallaria con un error de
conexion real (no hay nada mockeado que lo atrape).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from factory.engines.gmpai_integrity.model_provider import (
    ControlledGenerationNotSupportedError,
    supports_controlled_generation,
)
from factory.regulatory import validation_evidence_manifest as manifest_mod
from factory.regulatory import validation_evidence_writer as writer
from factory.regulatory.tools.run_validation_evidence import (
    EvidenceRunConfig,
    run_validation_evidence,
)

FAKE_PAGES = ["El sistema no menciona autenticacion en esta pagina."] * 2


@pytest.fixture
def dummy_document(tmp_path):
    p = tmp_path / "dummy.pdf"
    p.write_bytes(b"%PDF-1.4 contenido sintetico para hash de prueba")
    return p


@pytest.fixture(autouse=True)
def _isolate_validation_evidence_base(monkeypatch, tmp_path):
    monkeypatch.setattr(writer, "VALIDATION_EVIDENCE_BASE", tmp_path / "ve_autouse")
    monkeypatch.setattr(manifest_mod, "VALIDATION_EVIDENCE_BASE", tmp_path / "ve_autouse")


def _manifest():
    return {
        "model": "modelo-inyectado", "model_digest": "digest-inyectado",
        "prompt_sha256": "p", "schema_name": "finding_llm_v1", "schema_sha256": "s",
        "chunk_sha256": "c", "options": {}, "timestamp_utc": "t",
        "manifest_incomplete": False,
    }


class FakeProvider:
    """No importa `ollama_client` en absoluto."""

    def __init__(self):
        self.controlled_calls = 0
        self.run_contexts: list[str] = []

    @property
    def model_name(self) -> str:
        return "modelo-inyectado"

    def generate(self, prompt: str, *, num_predict: int | None = None) -> dict:
        raise AssertionError("el runner debe usar generate_controlled, no generate")

    def generate_controlled(self, prompt, chunk, *, run_context,
                            temperature=None, num_ctx=None) -> dict:
        self.controlled_calls += 1
        self.run_contexts.append(run_context)
        return {
            "ok": True,
            "llm_output": {
                "requirement_id": "ANNEX11_12",
                "chunk_observation": "not_observed_in_chunk",
                "evidence_quote": "",
                "evidence_page": 1,
                "confidence": 0.4,
                "rationale": "sin evidencia en el fragmento",
                "flags": [],
            },
            "execution_manifest": _manifest(),
            "errors": [],
            "rejection_reason": None,
            "raw_response": "{}",
        }

    def show_digest(self) -> str:
        return "digest-inyectado"

    def runtime_version(self) -> str:
        return "runtime-inyectado-0.0.0"


class ProviderSinControlada:
    """Provider valido para el motor (cumple el Protocol) pero sin la
    extension opcional. Debe ser rechazado, no degradado."""

    @property
    def model_name(self) -> str:
        return "sin-controlada"

    def generate(self, prompt: str, *, num_predict: int | None = None) -> dict:
        return {}

    def show_digest(self) -> str:
        return "d"

    def runtime_version(self) -> str:
        return "v"


def _config(doc: Path) -> EvidenceRunConfig:
    return EvidenceRunConfig(
        document_path=doc, document_type="FS", document_type_source="test",
        requirement_ids=["ANNEX11_12"], extractor=lambda p: FAKE_PAGES,
        run_by="tester",
    )


def test_runner_usa_el_provider_inyectado_y_nunca_ollama_client(dummy_document):
    """Nada de ollama_client esta mockeado: si el runner lo tocara, fallaria
    con un error de conexion real contra el Ollama del host."""
    provider = FakeProvider()
    result = run_validation_evidence(_config(dummy_document), provider=provider)

    assert provider.controlled_calls > 0, "el provider inyectado no se uso"
    assert set(provider.run_contexts) == {"validation"}


def test_metadata_del_manifiesto_viene_del_provider_no_del_cliente_global(dummy_document):
    """Si `model`/`model_digest`/`ollama_version` siguieran leyendose de
    ollama_client, el artefacto mentiria al inyectar otro modelo."""
    result = run_validation_evidence(_config(dummy_document), provider=FakeProvider())

    assert result.raw["model"] == "modelo-inyectado"
    assert result.raw["model_digest"] == "digest-inyectado"
    assert result.raw["ollama_version"] == "runtime-inyectado-0.0.0"


def test_provider_sin_generate_controlled_falla_cerrado(dummy_document):
    """Fail-closed: se aborta ANTES de cualquier llamada. Recurrir al cliente
    global produciria evidencia atribuida a un modelo que no es el
    inyectado."""
    provider = ProviderSinControlada()
    assert supports_controlled_generation(provider) is False

    with pytest.raises(ControlledGenerationNotSupportedError) as exc:
        run_validation_evidence(_config(dummy_document), provider=provider)
    assert "generate_controlled" in str(exc.value)


def test_ollama_provider_declara_la_capacidad():
    from factory.engines.gmpai_integrity.model_provider import DEFAULT_PROVIDER

    assert supports_controlled_generation(DEFAULT_PROVIDER) is True


def test_sin_provider_el_comportamiento_es_el_de_siempre(monkeypatch, dummy_document):
    """Default None => DEFAULT_PROVIDER => ollama_client. Se comprueba con el
    mismo monkeypatch que usan los tests historicos, que siguen pasando
    porque OllamaProvider resuelve el modulo en cada llamada."""
    from factory.engines.gmpai_integrity import ollama_client

    llamadas = []

    def _fake(prompt, chunk, *, run_context, **kwargs):
        llamadas.append(run_context)
        return FakeProvider().generate_controlled(prompt, chunk, run_context=run_context)

    monkeypatch.setattr(ollama_client, "generate_controlled", _fake)
    monkeypatch.setattr(ollama_client, "show_digest", lambda: "digest-global")
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "global-0.0.0")

    result = run_validation_evidence(_config(dummy_document))

    assert llamadas == ["validation"]
    assert result.raw["model_digest"] == "digest-global"
