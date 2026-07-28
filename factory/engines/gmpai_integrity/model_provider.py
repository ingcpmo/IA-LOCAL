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

    # NOTA -- `generate_controlled` es la SEGUNDA extensión opcional, fuera
    # del Protocol por la misma razón que `context_window` (añadir un
    # miembro a un Protocol `runtime_checkable` invalida `isinstance()` para
    # toda implementación existente, incluidas las de test).
    #
    # Firma esperada de quien la ofrezca:
    #     generate_controlled(prompt: str, chunk: dict, *, run_context: str,
    #                         temperature: float = ..., num_ctx: int | None = None) -> dict
    #
    # Es la ruta de generación con schema forzado (`finding_llm_v1`) que usa
    # la evidencia regulatoria. Hasta 2026-07-28 no estaba detrás de ninguna
    # abstracción: `run_validation_evidence.py` llamaba a
    # `ollama_client.generate_controlled()` directamente, lo que hacía FALLAR
    # el gate 14 de la sección 22 del plan ("100% de agentes híbridos con
    # ModelProvider"). Un caller comprueba la capacidad con
    # `supports_controlled_generation(provider)` y falla explícitamente si el
    # provider inyectado no la ofrece -- nunca cae en silencio al cliente
    # Ollama global.

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

    def generate_controlled(self, prompt: str, chunk: dict, *, run_context: str,
                            temperature: float | None = None,
                            num_ctx: int | None = None) -> dict:
        """Extensión opcional (ver la nota en el Protocol). Delega 1:1; toda
        la política -- ProductionNotEnabledError, seed, schema finding_llm_v1,
        clasificación de rejection_reason -- sigue viviendo en ollama_client,
        no se duplica aquí.

        `temperature=None` deja que ollama_client aplique su propio default
        en vez de congelarlo en la firma del provider: si TEMPERATURE cambia
        en el cliente, esta ruta lo hereda."""
        kwargs = {} if temperature is None else {"temperature": temperature}
        return ollama_client.generate_controlled(
            prompt, chunk, run_context=run_context, num_ctx=num_ctx, **kwargs)

    def show_digest(self) -> str:
        return ollama_client.show_digest()

    def runtime_version(self) -> str:
        return ollama_client.ollama_version()


def supports_controlled_generation(provider: object) -> bool:
    """True si el provider ofrece la extensión `generate_controlled`. Un
    caller que la necesite debe comprobarla y fallar explícitamente si no
    está -- nunca recurrir a `ollama_client` por su cuenta, que es
    exactamente el acoplamiento que el gate 14 prohíbe."""
    return callable(getattr(provider, "generate_controlled", None))


class ControlledGenerationNotSupportedError(TypeError):
    """El provider inyectado no ofrece `generate_controlled`. Es un error
    duro y no un fallback: recurrir al cliente Ollama global produciría
    evidencia regulatoria atribuida a un modelo que no es el inyectado."""


DEFAULT_PROVIDER = OllamaProvider()
