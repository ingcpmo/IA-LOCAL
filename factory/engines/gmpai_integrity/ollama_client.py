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
TEMPERATURE = 0.1
TIMEOUT_READ_S = float(os.getenv("FACTORY_OLLAMA_TIMEOUT_READ_S", "1200"))


def generate(prompt: str, temperature: float = TEMPERATURE, num_ctx: int | None = None) -> dict:
    r = httpx.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": NUM_PREDICT, "temperature": temperature,
                        "num_ctx": num_ctx if num_ctx is not None else NUM_CTX},
        },
        timeout=httpx.Timeout(connect=5.0, read=TIMEOUT_READ_S, write=10.0, pool=5.0),
    )
    r.raise_for_status()
    return r.json()


def show_digest() -> str | None:
    try:
        r = httpx.post(f"{OLLAMA_BASE_URL}/api/show", json={"name": OLLAMA_MODEL}, timeout=10.0)
        r.raise_for_status()
        d = r.json()
        return d.get("digest") or d.get("details", {}).get("digest")
    except Exception:
        return None
