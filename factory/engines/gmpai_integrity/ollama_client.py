"""Cliente Ollama — único egreso HTTP del motor de chunking, vía httpx REST
directo (regla dura CLAUDE.md: NO instalar el paquete Python 'ollama').
Idéntico patrón al que usaba factory/workspaces/gmpai_document_validation/
app/ollama_client.py; movido aquí para que el motor sea git-trackeado y no
dependa del workspace gitignorado."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

import httpx

from factory.regulatory.schema_loader import load_schema, schema_sha256, validate_against

OLLAMA_BASE_URL = os.getenv("FACTORY_OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("FACTORY_OLLAMA_MODEL", "qwen2.5:7b-instruct-q4_K_M")
NUM_PREDICT = 1024
NUM_CTX = int(os.getenv("FACTORY_OLLAMA_NUM_CTX", "8192"))
# Fix TE-01 (post-mortem cierre FS_v1.2 v3): temperatura 0 (determinista, no 0.1)
# reduce la tasa de respuestas no-JSON del modelo.
TEMPERATURE = 0.0
TIMEOUT_READ_S = float(os.getenv("FACTORY_OLLAMA_TIMEOUT_READ_S", "1200"))


def generate(prompt: str, temperature: float = TEMPERATURE, num_ctx: int | None = None) -> dict:
    # Fix TE-01: 'format': 'json' fuerza a Ollama a devolver JSON válido a
    # nivel de API (no elimina la necesidad de validar el esquema del
    # contenido, pero elimina la clase de fallo 'no es JSON en absoluto').
    r = httpx.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"num_predict": NUM_PREDICT, "temperature": temperature,
                        "num_ctx": num_ctx if num_ctx is not None else NUM_CTX},
        },
        timeout=httpx.Timeout(connect=5.0, read=TIMEOUT_READ_S, write=10.0, pool=5.0),
    )
    r.raise_for_status()
    return r.json()


class OllamaUnavailableError(Exception):
    """Ollama no alcanzable o /api/show sin campo digest -- distinto de un
    None silencioso (fix TE-02: nunca capturar la excepcion real en silencio)."""


def show_digest() -> str:
    """Lanza OllamaUnavailableError con el motivo real en vez de devolver
    None silenciosamente (fix TE-02).

    Fix 2026-07-16 (post-mortem piloto Autoclave URS): /api/show YA NO
    incluye el campo 'digest' en Ollama >=0.21 (verificado en vivo contra
    la version 0.21.2 -- las claves reales son license/modelfile/template/
    system/details/model_info/tensors/capabilities/modified_at, ninguna
    con el digest). El digest real vive en la entrada por-modelo de
    /api/tags. Se consulta ahi; se sigue fallando explicito (nunca None
    silencioso) si el modelo no aparece o no trae digest."""
    try:
        r = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10.0)
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise OllamaUnavailableError(f"Ollama no alcanzable en {OLLAMA_BASE_URL}: {e!r}") from e
    models = r.json().get("models", [])
    match = next((m for m in models if m.get("name") == OLLAMA_MODEL or m.get("model") == OLLAMA_MODEL), None)
    if match is None:
        raise OllamaUnavailableError(
            f"/api/tags no incluye el modelo '{OLLAMA_MODEL}' -- modelos disponibles: "
            f"{[m.get('name') for m in models]}"
        )
    digest = match.get("digest")
    if not digest:
        raise OllamaUnavailableError(f"/api/tags respondio sin campo digest para '{OLLAMA_MODEL}': claves={list(match.keys())}")
    return digest


FINDING_LLM_SCHEMA_NAME = "finding_llm_v1"


def _get_digest_cached(_cache: dict = {}) -> str | None:  # noqa: B006 - cache intencional por proceso
    """model_digest cacheado una vez por ejecucion (Bloque 1.5). Si Ollama no
    esta disponible, NO lanza -- devuelve None y el manifiesto queda marcado
    manifest_incomplete=True (P1: un manifiesto incompleto no invalida el
    hallazgo, pero nunca se oculta)."""
    if "digest" not in _cache:
        try:
            _cache["digest"] = show_digest()
        except OllamaUnavailableError:
            _cache["digest"] = None
    return _cache["digest"]


class ProductionNotEnabledError(Exception):
    """generate_controlled() invocado con run_context='production'. W5
    Ciclo 1 v2: PRODUCTION_ENABLEMENT=BLOCKED -- los prompts YAML de
    produccion no fueron reescritos para pedir chunk_observation (ver
    W5v2_CICLO1_CIERRE.md, recomendacion #1) y no existe aprobacion QA
    para habilitar este pipeline en produccion. Fail-closed explicito:
    ausencia de run_context (default) NUNCA habilita produccion -- el
    default es 'validation', el unico contexto autorizado hoy."""


def generate_controlled(prompt: str, chunk: dict, temperature: float = TEMPERATURE,
                         num_ctx: int | None = None, run_context: str = "validation") -> dict:
    """Ejecucion controlada (P4: temperatura 0 + seed es 'ejecucion
    controlada', NO determinismo garantizado -- de ahi el manifiesto por
    llamada) que valida la respuesta contra finding_llm_v1 (P2: el modelo
    SOLO puede emitir lo que ese schema permite -- observed/
    partially_observed/not_observed_in_chunk, nunca una conclusion de
    ausencia documental ni no_aplica, ver W5v2_FASE0_INVENTARIO.md #9.1).

    run_context: SOLO 'validation' esta habilitado (default). Cualquier
    otro valor -- incluido 'production' -- lanza ProductionNotEnabledError
    de inmediato, antes de gastar ninguna llamada a Ollama. La ausencia de
    este parametro NUNCA habilita produccion (default seguro).

    NO esta todavia cableada en evaluate_chunked() (chunked_engine.py): el
    consolidador actual espera el campo 'estado' (cumple/no_cumple/...) que
    el contrato de prompt YAML vigente le pide al modelo directamente --
    cambiar chunked_engine.py para consumir chunk_observation en vez de
    estado es una reescritura del consolidador (Fase 2), no un cambio
    aditivo. Cablear este contrato sin ese trabajo dejaria al pipeline
    pidiendole al modelo una cosa y a la consolidacion esperando otra.

    Devuelve dict con: llm_output (si valido) o None, execution_manifest,
    ok (bool), errors (list[str])."""
    if run_context != "validation":
        raise ProductionNotEnabledError(
            f"generate_controlled() bloqueado para run_context={run_context!r} -- "
            f"solo 'validation' esta habilitado (PRODUCTION_ENABLEMENT=BLOCKED)."
        )
    options = {"temperature": temperature, "seed": 42,
               "num_predict": NUM_PREDICT,
               "num_ctx": num_ctx if num_ctx is not None else NUM_CTX}
    schema = load_schema(FINDING_LLM_SCHEMA_NAME)
    chunk_text = chunk.get("text", "")

    def _call() -> tuple[dict | None, str]:
        r = httpx.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                  "format": schema, "options": options},
            timeout=httpx.Timeout(connect=5.0, read=TIMEOUT_READ_S, write=10.0, pool=5.0),
        )
        r.raise_for_status()
        raw_response = r.json().get("response", "")
        try:
            return json.loads(raw_response), raw_response
        except json.JSONDecodeError:
            return None, raw_response

    digest = _get_digest_cached()
    manifest = {
        "model": OLLAMA_MODEL,
        "model_digest": digest or "unavailable",
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "schema_name": FINDING_LLM_SCHEMA_NAME,
        "schema_sha256": schema_sha256(FINDING_LLM_SCHEMA_NAME),
        "chunk_sha256": hashlib.sha256(chunk_text.encode()).hexdigest(),
        "options": options,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_incomplete": digest is None,
    }

    llm_output, raw = _call()
    ok, errors = (False, ["respuesta del modelo no es JSON valido"]) if llm_output is None \
        else validate_against(llm_output, FINDING_LLM_SCHEMA_NAME)

    if not ok:
        # Un solo reintento (Bloque 1.5) -- sin bucle de reparacion.
        llm_output, raw = _call()
        ok, errors = (False, ["respuesta del modelo no es JSON valido"]) if llm_output is None \
            else validate_against(llm_output, FINDING_LLM_SCHEMA_NAME)

    return {
        "llm_output": llm_output if ok else None,
        "execution_manifest": manifest,
        "ok": ok,
        "errors": errors,
        "status": "verified" if ok else "rejected_by_verifier",
        "rejection_reason": None if ok else "schema_validation_failed",
        "raw_response": raw,
    }


def ollama_version() -> str:
    """Version del servidor Ollama (GET /api/version) -- captura obligatoria
    de metadata de reproducibilidad antes de la primera inferencia."""
    try:
        r = httpx.get(f"{OLLAMA_BASE_URL}/api/version", timeout=10.0)
        r.raise_for_status()
        return r.json().get("version", "unknown")
    except httpx.HTTPError as e:
        raise OllamaUnavailableError(f"Ollama no alcanzable en {OLLAMA_BASE_URL}: {e!r}") from e
