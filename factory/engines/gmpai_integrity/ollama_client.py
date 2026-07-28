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
# Fallback SOLO para llamadas que no declaran su contrato de salida. El
# camino real (evaluate_chunked) calcula su presupuesto con
# output_token_budget() y lo pasa explicitamente -- ver el post-mortem
# W5v2_POSTMORTEM_TRUNCAMIENTO_NUM_PREDICT.md: este 1024 quedo atras cuando
# la ampliacion D de la Fase F agrego criterion_assessments al contrato, y
# trunco (done_reason="length") toda respuesta que analizara contenido real.
# Ajustable por entorno igual que NUM_CTX (antes era el unico de los dos
# hardcodeado, asimetria sin razon).
NUM_PREDICT = int(os.getenv("FACTORY_OLLAMA_NUM_PREDICT", "1024"))
# Subido de 8192 a 16384 (2026-07-28): con el presupuesto de salida real,
# alcoa_plus_agent no cabe en 8192. Medido sobre FS_v1.2 ejecutando la propia
# guardia: peor prompt 4410 tokens estimados (chunk 3) + num_predict 4096 =
# 8506 > 8192, y _assert_token_budget_fits() aborta con TokenBudgetError.
#
# El margen es mas estrecho de lo que parece y conviene no perderlo de vista:
# la tokenizacion REAL de ese prompt son ~4019 tokens (prompt_eval_count
# medido), o sea 8115, que cabria en 8192 por 77 tokens. La guardia usa la
# estimacion conservadora de PROMPT_CHARS_PER_TOKEN a proposito -- 77 tokens
# de holgura sobre un documento concreto no son margen para ningun otro
# documento. Y pasarse no falla ruidosamente: Ollama trunca el PROMPT en
# silencio, y lo que se pierde es el principio, common_contract y la lista de
# req_id. Ver chunked_engine._assert_token_budget_fits().
NUM_CTX = int(os.getenv("FACTORY_OLLAMA_NUM_CTX", "16384"))
# Fix TE-01 (post-mortem cierre FS_v1.2 v3): temperatura 0 (determinista, no 0.1)
# reduce la tasa de respuestas no-JSON del modelo.
TEMPERATURE = 0.0
TIMEOUT_READ_S = float(os.getenv("FACTORY_OLLAMA_TIMEOUT_READ_S", "1200"))

# El timeout de lectura tambien tiene que escalar con el presupuesto de
# salida (2026-07-28). Con TIMEOUT_READ_S fijo en 1200 s, la primera
# validacion real del presupuesto nuevo (num_predict=3072) murio por
# ReadTimeout: generar 3072 tokens a la velocidad real del host son ~15 min,
# mas ~4 min de prompt eval, justo por encima de los 20 min. Es la MISMA
# clase de defecto que motivo todo este trabajo -- una constante que no se
# recalculo cuando crecio el contrato de salida -- asi que se deriva igual
# que num_predict en vez de subirla a otro numero fijo.
#
# Velocidad DELIBERADAMENTE conservadora: la medida fue 3,33 tok/s; se usa
# 2,0 para que una maquina cargada (este host es compartido) no produzca un
# timeout espureo. Un timeout holgado no cuesta nada cuando la respuesta
# llega antes; uno corto tira a la basura una generacion de 20 minutos.
MIN_TOKENS_PER_SECOND = float(os.getenv("FACTORY_OLLAMA_MIN_TOK_S", "2.0"))
PROMPT_EVAL_ALLOWANCE_S = float(os.getenv("FACTORY_OLLAMA_PROMPT_ALLOWANCE_S", "600"))


def read_timeout_for(num_predict: int | None) -> float:
    """Timeout de lectura suficiente para generar num_predict tokens a la
    velocidad minima asumida, mas margen para el prompt eval. Nunca por
    debajo de TIMEOUT_READ_S (que sigue siendo el piso configurable)."""
    if not num_predict:
        return TIMEOUT_READ_S
    return max(TIMEOUT_READ_S,
               num_predict / MIN_TOKENS_PER_SECOND + PROMPT_EVAL_ALLOWANCE_S)


def generate(prompt: str, temperature: float = TEMPERATURE, num_ctx: int | None = None,
             num_predict: int | None = None) -> dict:
    # Fix TE-01: 'format': 'json' fuerza a Ollama a devolver JSON válido a
    # nivel de API (no elimina la necesidad de validar el esquema del
    # contenido, pero elimina la clase de fallo 'no es JSON en absoluto').
    # NOTA: 'format':'json' NO protege del truncamiento -- si la generacion
    # agota num_predict, Ollama devuelve JSON incompleto con
    # done_reason="length". Esa clase de fallo se detecta rio arriba
    # (chunked_engine._extract_json), no aqui.
    r = httpx.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"num_predict": num_predict if num_predict is not None else NUM_PREDICT,
                        "temperature": temperature,
                        "num_ctx": num_ctx if num_ctx is not None else NUM_CTX},
        },
        timeout=httpx.Timeout(connect=5.0, read=read_timeout_for(num_predict),
                              write=10.0, pool=5.0),
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
    para habilitar este pipeline en produccion."""


def generate_controlled(prompt: str, chunk: dict, *, run_context: str,
                         temperature: float = TEMPERATURE,
                         num_ctx: int | None = None) -> dict:
    """Ejecucion controlada (P4: temperatura 0 + seed es 'ejecucion
    controlada', NO determinismo garantizado -- de ahi el manifiesto por
    llamada) que valida la respuesta contra finding_llm_v1 (P2: el modelo
    SOLO puede emitir lo que ese schema permite -- observed/
    partially_observed/not_observed_in_chunk, nunca una conclusion de
    ausencia documental ni no_aplica, ver W5v2_FASE0_INVENTARIO.md #9.1).

    run_context: OBLIGATORIO, sin default (Fase 5.0, W5.3 -- corrige el
    default anterior 'validation', que aunque era el valor seguro, seguia
    permitiendo que un caller no pensara conscientemente el contexto en
    cada llamada). SOLO 'validation' esta habilitado -- cualquier otro
    valor, incluido 'production', lanza ProductionNotEnabledError de
    inmediato, antes de gastar ninguna llamada a Ollama.

    NO esta todavia cableada en evaluate_chunked() (chunked_engine.py): el
    consolidador actual espera el campo 'estado' (cumple/no_cumple/...) que
    el contrato de prompt YAML vigente le pide al modelo directamente --
    cambiar chunked_engine.py para consumir chunk_observation en vez de
    estado es una reescritura del consolidador (Fase 2), no un cambio
    aditivo. Cablear este contrato sin ese trabajo dejaria al pipeline
    pidiendole al modelo una cosa y a la consolidacion esperando otra.

    Devuelve dict con: llm_output (si valido) o None, execution_manifest,
    ok (bool), errors (list[str]), rejection_reason (None si ok, si no una
    de exactamente 4 causas -- Fase 5.4.4, fix ETAPA 1 continuado: antes
    rejection_reason quedaba SIEMPRE hardcodeado a 'schema_validation_failed'
    incluso cuando la causa real era JSON no parseable o (sin este fix) un
    fallo de transporte no capturado que tumbaba la corrida entera:
      - 'ollama_transport_failed': la llamada HTTP a Ollama fallo (conexion,
        timeout, status de error) -- antes de este fix, esta excepcion NO
        se capturaba aqui y se propagaba sin control, abortando toda la
        corrida (perdiendo el analisis ya completado de otros requisitos/
        chunks, pese al contrato de persistencia de Fase 5.4).
      - 'json_parse_failed': la respuesta llego pero no es JSON valido.
      - 'schema_validation_failed': JSON valido que no cumple finding_llm_v1.
      - manifest_incomplete (model_digest no disponible) NO es una causa de
        rejection_reason -- P1 (linea ~88 de este archivo) es doctrina ya
        decidida: un manifiesto incompleto no invalida el hallazgo. Sigue
        expuesto solo como execution_manifest['manifest_incomplete']."""
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

    def _call() -> tuple[dict | None, str | None, str | None]:
        """Devuelve (llm_output_o_None, raw_response_o_None, transport_error_o_None)."""
        try:
            r = httpx.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                      "format": schema, "options": options},
                timeout=httpx.Timeout(connect=5.0, read=read_timeout_for(options["num_predict"]),
                                      write=10.0, pool=5.0),
            )
            r.raise_for_status()
        except httpx.HTTPError as e:
            return None, None, f"{type(e).__name__}: {e}"
        raw_response = r.json().get("response", "")
        try:
            return json.loads(raw_response), raw_response, None
        except json.JSONDecodeError:
            return None, raw_response, None

    def _classify(llm_output: dict | None, transport_error: str | None) -> tuple[bool, list[str], str | None]:
        if transport_error is not None:
            return False, [f"ollama_transport_failed: {transport_error}"], "ollama_transport_failed"
        if llm_output is None:
            return False, ["respuesta del modelo no es JSON valido"], "json_parse_failed"
        ok, errors = validate_against(llm_output, FINDING_LLM_SCHEMA_NAME)
        return (True, errors, None) if ok else (False, errors, "schema_validation_failed")

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

    llm_output, raw, transport_error = _call()
    ok, errors, rejection_reason = _classify(llm_output, transport_error)

    if not ok:
        # Un solo reintento (Bloque 1.5) -- sin bucle de reparacion.
        llm_output, raw, transport_error = _call()
        ok, errors, rejection_reason = _classify(llm_output, transport_error)

    return {
        "llm_output": llm_output if ok else None,
        "execution_manifest": manifest,
        "ok": ok,
        "errors": errors,
        "status": "verified" if ok else "rejected_by_verifier",
        "rejection_reason": rejection_reason,
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
