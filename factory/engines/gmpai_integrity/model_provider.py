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

    def generate(self, prompt: str, *, num_predict: int | None = None) -> dict:
        """Llamada simple de generación (formato JSON forzado en el
        provider). Retorna el dict crudo de la API subyacente.

        num_predict (2026-07-28): presupuesto de tokens de SALIDA para esta
        llamada, calculado por el motor con
        `ollama_client.output_token_budget()` a partir del contrato real del
        prompt. `None` = el provider usa su propio default.

        Una implementación que no acepte este keyword sigue siendo válida
        (el motor lo detecta con `inspect` y lo registra en
        `preflight_metadata['provider_honors_token_budget']`), pero entonces
        NO puede garantizar que la respuesta quepa: el respaldo real contra
        el truncamiento es la detección de `done_reason == "length"` en
        `chunked_engine._extract_json()`, que funciona con cualquier
        provider."""
        ...

    # NOTA -- `context_window` es una extensión OPCIONAL, deliberadamente
    # fuera de este Protocol.
    #
    # Un provider puede declarar `context_window: int` (tokens totales,
    # prompt + salida, que admite una llamada). El motor lo lee con getattr
    # para su guardia de preflight, que impide que el runtime trunque el
    # prompt en silencio -- ver chunked_engine._assert_token_budget_fits().
    #
    # No se declara aquí porque este Protocol es `runtime_checkable`:
    # añadirlo haría que toda implementación existente dejara de satisfacer
    # `isinstance()`, rompiendo providers válidos por un dato que la mayoría
    # (p. ej. los de test) no puede conocer. Un provider que no lo declara
    # simplemente no se somete a la guardia, y eso queda registrado en
    # `preflight_metadata['token_budget']['context_window_declared']` en vez
    # de suponer una ventana inventada.

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

    @property
    def context_window(self) -> int:
        # Se lee en cada acceso (no se cachea) para que un cambio de
        # FACTORY_OLLAMA_NUM_CTX se refleje sin reimportar el modulo.
        return ollama_client.NUM_CTX

    def generate(self, prompt: str, *, num_predict: int | None = None) -> dict:
        return ollama_client.generate(prompt, num_predict=num_predict)

    def show_digest(self) -> str:
        return ollama_client.show_digest()

    def runtime_version(self) -> str:
        return ollama_client.ollama_version()


DEFAULT_PROVIDER = OllamaProvider()
