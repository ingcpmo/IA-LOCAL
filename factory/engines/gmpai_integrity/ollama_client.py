"""Cliente Ollama — único egreso HTTP del motor de chunking, vía httpx REST
directo (regla dura CLAUDE.md: NO instalar el paquete Python 'ollama').
Idéntico patrón al que usaba factory/workspaces/gmpai_document_validation/
app/ollama_client.py; movido aquí para que el motor sea git-trackeado y no
dependa del workspace gitignorado."""

from __future__ import annotations

import os

import httpx

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
    None silenciosamente (fix TE-02)."""
    try:
        r = httpx.post(f"{OLLAMA_BASE_URL}/api/show", json={"name": OLLAMA_MODEL}, timeout=10.0)
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise OllamaUnavailableError(f"Ollama no alcanzable en {OLLAMA_BASE_URL}: {e!r}") from e
    d = r.json()
    digest = d.get("digest") or d.get("details", {}).get("digest")
    if not digest:
        raise OllamaUnavailableError(f"/api/show respondio sin campo digest: claves={list(d.keys())}")
    return digest


def ollama_version() -> str:
    """Version del servidor Ollama (GET /api/version) -- captura obligatoria
    de metadata de reproducibilidad antes de la primera inferencia."""
    try:
        r = httpx.get(f"{OLLAMA_BASE_URL}/api/version", timeout=10.0)
        r.raise_for_status()
        return r.json().get("version", "unknown")
    except httpx.HTTPError as e:
        raise OllamaUnavailableError(f"Ollama no alcanzable en {OLLAMA_BASE_URL}: {e!r}") from e
