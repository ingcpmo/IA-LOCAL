"""W5 V2, Fase D -- abstracción ModelProvider (sección 7 del plan
MODEL_PROVIDER_AND_LOCAL_AI_RUNTIME_SPEC.md).

Antes de esta fase, `chunked_engine.py` importaba `ollama_client`
directamente (acoplamiento confirmado en CURRENT_AGENT_RUNTIME_AUDIT.md:
"no existe ninguna clase ModelProvider... todo el código está acoplado
directamente a Ollama vía httpx"). Este módulo introduce la interfaz y UNA
implementación real (`OllamaProvider`, delegando 1:1 en `ollama_client.py`
-- cero cambio de comportamiento). `OpenAICompatibleProvider` y
`AnthropicProvider` NO se implementan aquí (la segunda requiere
autorización explícita de Capa 9 que no existe todavía, sección 7 del
plan) -- se documentan como extensión futura, no como stubs vacíos que
pudieran confundirse con soporte real.

La lógica regulatoria (`evaluate_chunked`) consume solo esta interfaz,
nunca `ollama_client` directamente -- ver el parámetro `provider` de
`evaluate_chunked()`."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from . import ollama_client


@runtime_checkable
class ModelProvider(Protocol):
    """Contrato mínimo que necesita el motor de integridad. Cualquier
    implementación (Ollama, un backend OpenAI-compatible local, etc.) debe
    cumplir esta interfaz para ser usada por evaluate_chunked()."""

    @property
    def model_name(self) -> str:
        """Identificador del modelo activo (para manifest/Finding.model)."""
        ...

    def generate(self, prompt: str) -> dict:
        """Llamada simple de generación (formato JSON forzado en el
        provider). Retorna el dict crudo de la API subyacente."""
        ...

    def show_digest(self) -> str:
        """Digest del modelo activo. Lanza si el runtime no está
        disponible -- nunca retorna None silenciosamente (mismo contrato
        que ollama_client.show_digest())."""
        ...

    def runtime_version(self) -> str:
        """Versión del runtime de inferencia (p.ej. versión del servidor
        Ollama)."""
        ...


class OllamaProvider:
    """Implementación real por defecto -- delega 1:1 en
    factory.engines.gmpai_integrity.ollama_client, sin cambiar ningún
    comportamiento ya probado (reintentos, timeouts, format:json,
    temperatura 0, etc. viven en ollama_client.py, no se duplican aquí)."""

    @property
    def model_name(self) -> str:
        return ollama_client.OLLAMA_MODEL

    def generate(self, prompt: str) -> dict:
        return ollama_client.generate(prompt)

    def show_digest(self) -> str:
        return ollama_client.show_digest()

    def runtime_version(self) -> str:
        return ollama_client.ollama_version()


DEFAULT_PROVIDER = OllamaProvider()
