"""R2.2 §4.3 -- cliente de embeddings, vía httpx REST directo al MISMO
Ollama del host (`localhost:11434`, `factory.engines.gmpai_integrity.
ollama_client.OLLAMA_BASE_URL` reutilizado, nunca reimplementado) que ya
usa el juicio LLM. NUNCA el paquete Python `ollama` (regla dura de
CLAUDE.md). NUNCA `aria-ollama` (contenedor ajeno, fuera de alcance).

Modelo: `nomic-embed-text:latest`, CPU-friendly, ya pulleado localmente
(EMBED_EXECUTION-2026-002, human_confirmed, digest 0a109f422b47e3a30ba2).
Deliberadamente separado de `OLLAMA_MODEL` (el de juicio, qwen2.5) -- un
embedding es un vector determinista, no un juicio, así que usa su propio
endpoint (`/api/embeddings`) y su propio nombre de modelo, nunca comparte
código de generación de texto con `ollama_client.generate()`."""
from __future__ import annotations

import math
import os

import httpx

from factory.engines.gmpai_integrity.ollama_client import OLLAMA_BASE_URL

EMBED_MODEL = os.getenv("FACTORY_OLLAMA_EMBED_MODEL", "nomic-embed-text:latest")
EMBED_TIMEOUT_S = float(os.getenv("FACTORY_OLLAMA_EMBED_TIMEOUT_S", "120"))
# Hallazgo real de la corrida R2.2 §4.3 (2026-08-10, nomic-embed-text:latest
# digest 0a109f422b47e3a30ba2): el modelo pulleado tiene context_length=2048
# TOKENS real (`ollama show`, `model_info["nomic-bert.context_length"]`), no
# negociable vía `options.num_ctx` (se probó -- el limite es del modelo, no
# del buffer de KV-cache). Algunos chunks de `build_page_chunks()` (pensados
# para el LLM de juicio, con ventana mucho mayor) superan ese límite y
# `/api/embeddings` responde 500 "the input length exceeds the context
# length". Truncar es la única opción sin GPU/proveedor externo -- se hace
# aquí, nunca en `embed_index.py`/`fusion.py`, para que el chunk_index/page
# mapping (requisito de R2.2 §4.4) permanezca intacto: el vector representa
# el mismo chunk, solo un prefijo de su texto.
_MAX_RETRIES = 4


class EmbeddingUnavailableError(Exception):
    """Ollama no alcanzable, o /api/embeddings respondió sin 'embedding' --
    nunca un None/vector-cero silencioso (mismo principio P1/TE-02 que
    `ollama_client.OllamaUnavailableError`: fallar explícito, no fingir)."""


def _is_context_length_error(response: httpx.Response) -> bool:
    try:
        return "context length" in (response.json().get("error") or "")
    except Exception:  # noqa: BLE001 -- si el body no es JSON, no es este caso
        return False


def embed_text(text: str, *, model: str = EMBED_MODEL) -> list[float]:
    """Un vector real por llamada -- NUNCA cachea ni deduplica internamente
    (eso es responsabilidad de `embed_index.py`, que decide qué ya está
    indexado antes de gastar presupuesto de EMBED_EXECUTION).

    Si el texto excede el contexto real del modelo, reintenta truncando a la
    mitad (determinista, hasta `_MAX_RETRIES` veces) -- nunca silencioso: el
    vector resultante representa un PREFIJO del chunk, no el chunk completo."""
    prompt = text
    last_response: httpx.Response | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            r = httpx.post(
                f"{OLLAMA_BASE_URL}/api/embeddings",
                json={"model": model, "prompt": prompt},
                timeout=httpx.Timeout(connect=5.0, read=EMBED_TIMEOUT_S, write=10.0, pool=5.0),
            )
            r.raise_for_status()
            break
        except httpx.HTTPStatusError as e:
            last_response = e.response
            if attempt < _MAX_RETRIES and e.response.status_code == 500 and _is_context_length_error(e.response):
                prompt = prompt[: len(prompt) // 2]
                continue
            raise EmbeddingUnavailableError(
                f"Ollama /api/embeddings no alcanzable en {OLLAMA_BASE_URL}: {e!r}") from e
        except httpx.HTTPError as e:
            raise EmbeddingUnavailableError(
                f"Ollama /api/embeddings no alcanzable en {OLLAMA_BASE_URL}: {e!r}") from e
    else:
        raise EmbeddingUnavailableError(
            f"/api/embeddings sigue excediendo el contexto tras {_MAX_RETRIES} truncados "
            f"(último intento: {len(prompt)} caracteres): {last_response.text if last_response else '?'}")
    body = r.json()
    vector = body.get("embedding")
    if not isinstance(vector, list) or not vector:
        raise EmbeddingUnavailableError(
            f"/api/embeddings respondió sin campo 'embedding' válido: claves={list(body.keys())}")
    return vector


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Determinista, sin dependencia nueva (stdlib `math`, ya usado en
    `bm25.py` para el mismo motivo). 0.0 si algún vector es todo-ceros
    (evita ZeroDivisionError sin fingir similitud)."""
    if len(a) != len(b):
        raise ValueError(f"vectores de dimensión distinta: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
