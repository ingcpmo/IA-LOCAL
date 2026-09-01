"""Cliente Ollama con PINNING COMPLETO (R3) + `format` = JSON Schema (R4).
Aislado: httpx directo, sin tocar factory/engines/gmpai_integrity/ollama_client.py.
FASE 2. No escribe en el audit trail real."""
from __future__ import annotations

import hashlib
import json
import time

import httpx

BASE_URL = "http://localhost:11434"

# R3 -- opciones pinneadas. temperature 0 + seed + num_ctx EXPLICITO + top_p/top_k/repeat_penalty.
PINNED_OPTIONS = {
    "temperature": 0,
    "seed": 7,
    "num_ctx": 16384,   # holgura: prompt (schema embebido + contexto ~24k chars) + num_predict
    "num_predict": 1500,
    "top_p": 0.9,
    "top_k": 40,
    "repeat_penalty": 1.1,
}

PROMPT_VERSION = "scta-poc-1.0"


def _get_with_retry(url: str, timeout: float, tries: int = 6, backoff: float = 5.0):
    """Reintento SOLO ante fallo de transporte (Ollama caido/reiniciando). La
    peticion es identica byte a byte -> no altera el pinning ni el determinismo.
    Un fallo de HTTP >=400 NO se reintenta (fail-closed)."""
    last = None
    for i in range(tries):
        try:
            return httpx.get(url, timeout=timeout)
        except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError) as e:
            last = e
            time.sleep(backoff * (i + 1))
    raise RuntimeError(f"transporte agotado tras {tries} intentos: {last!r}")


def model_digest(model: str) -> str:
    """Digest REAL del modelo (no el tag). Fail-closed si no aparece."""
    r = _get_with_retry(f"{BASE_URL}/api/tags", timeout=10.0)
    r.raise_for_status()
    for m in r.json().get("models", []):
        if m.get("name") == model or m.get("model") == model:
            d = m.get("digest")
            if not d:
                raise RuntimeError(f"/api/tags sin digest para {model}")
            return d
    raise RuntimeError(f"modelo {model} no esta en /api/tags")


def ollama_version() -> str:
    return httpx.get(f"{BASE_URL}/api/version", timeout=10.0).json().get("version", "?")


def input_fingerprint(digest: str, prompt: str, options: dict) -> str:
    payload = digest + "|" + PROMPT_VERSION + "|" + prompt + "|" + json.dumps(options, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generate(model: str, prompt: str, fmt_schema: dict, *, options: dict | None = None) -> dict:
    """Una inferencia pinneada. Devuelve dict con crudo + metadatos de pinning + timing.
    NO valida el contenido (eso es validator.py). NO reintenta."""
    opts = dict(PINNED_OPTIONS)
    if options:
        opts.update(options)
    digest = model_digest(model)
    fp = input_fingerprint(digest, prompt, opts)
    t0 = time.time()
    try:
        body = None
        for i in range(6):
            try:
                r = httpx.post(
                    f"{BASE_URL}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False,
                          "format": fmt_schema, "options": opts},
                    timeout=httpx.Timeout(connect=5.0, read=900.0, write=30.0, pool=5.0),
                )
                r.raise_for_status()
                body = r.json()
                break
            except httpx.ConnectError as e:  # Ollama caido/reiniciando: no llego a generar
                if i == 5:
                    raise
                time.sleep(5.0 * (i + 1))
        transport_error = None
    except Exception as e:  # noqa: BLE001
        return {
            "model": model, "model_digest": digest, "prompt_version": PROMPT_VERSION,
            "options": opts, "input_fingerprint": fp,
            "wall_time_s": round(time.time() - t0, 2),
            "raw_response": None, "output_hash": None, "done_reason": None,
            "eval_count": None, "prompt_eval_count": None,
            "transport_error": repr(e),
        }
    dt = time.time() - t0
    raw = body.get("response", "")
    return {
        "model": model, "model_digest": digest, "prompt_version": PROMPT_VERSION,
        "options": opts, "input_fingerprint": fp,
        "wall_time_s": round(dt, 2),
        "raw_response": raw,
        "output_hash": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "done_reason": body.get("done_reason"),
        "eval_count": body.get("eval_count"),
        "prompt_eval_count": body.get("prompt_eval_count"),
        "transport_error": None,
    }
