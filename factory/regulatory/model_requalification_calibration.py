"""W5 V2 ARQ — corrida real de calibración de rendimiento (sección 4 de
MODEL_REQUALIFICATION_AND_D4A_SPEC.md).

`model_qualification_gate.py` (G6) mide 9 métricas de forma determinista con
el Golden Dataset y declara `NOT_MEASURED` las 4 restantes
(`latency_p50`, `latency_p95`, `tokens_per_task`, `retry_rate`) porque exigen
inferencia real -- el Golden Dataset usa providers sintéticos a propósito
(nunca llama a Ollama). Este módulo es esa corrida real, hasta hoy
`NOT_IMPLEMENTED_YET`:

  "La recalificación misma es la primera inferencia autorizada, y va contra
  el Golden Dataset, no contra documentos Rockwell." (spec §4)

Reutiliza `chunked_engine.evaluate_chunked()` -- el MISMO camino de
producción usado en corridas reales (p.ej. eu_annex11 sobre FS_v1.2,
2026-07-28) -- contra 2 páginas sintéticas reales (texto regulatorio real:
los 5 criterios mínimos de acceso del Golden Dataset, `ACCESS_CRITERIA`),
cada una forzada a superar `CHUNK_MAX_CHARS` para producir 2 llamadas reales
separadas (mismo patrón que
`semantic_verification_golden_dataset._case_contradiction_between_sections`,
único caso del Golden Dataset que ya ejercita `evaluate_chunked`, con un
fake provider). Aquí se usa `DEFAULT_PROVIDER` (Ollama real), envuelto en
`_InstrumentedProvider` para capturar latencia y tokens reales por llamada
sin tocar `chunked_engine.py` ni `ollama_client.py` -- ninguna línea de esos
dos archivos cambia en este commit.

Autorización: antes de la primera llamada real se exige
`require_inference_authorized(status, call_type=INFERENCE,
run_context='model_requalification', target=GOLDEN_DATASET_TARGET)` -- la
única excepción que el gate permite sin `QUALIFIED` pleno. Nota de
vocabulario: ese `run_context='model_requalification'` es un concepto del
GATE (G6), una capa por encima del motor -- `evaluate_chunked()` solo conoce
`{'production', 'validation'}` como run_context propio (ValueError para
cualquier otro valor) y aquí se le pasa `'validation'`, la etiqueta correcta
para una corrida real que SÍ debe dejar evidencia de validación y auditoría
-- nunca `'production'`, que sigue `BLOCKED`.

`retry_rate` se define aquí como la tasa de `technical_execution_failure` en
el primer (y único) intento de cada chunk -- `evaluate_chunked()` no
reintenta dentro de una misma corrida (el reintento vive en la reanudación
vía `checkpoint_store`, fuera de alcance de esta corrida acotada de 2
chunks); es la señal real más cercana disponible sin reimplementar ese
mecanismo aquí.
"""
from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from factory.engines.gmpai_integrity import chunked_engine as ce
from factory.engines.gmpai_integrity.model_provider import DEFAULT_PROVIDER, ModelProvider
from factory.regulatory import model_qualification_gate as gate
from factory.regulatory.golden_dataset.semantic_verification_golden_dataset import (
    _ACCESS_CRITERIA as ACCESS_CRITERIA,
)

CALIBRATION_PROMPT_PATH = (
    Path(__file__).parent.parent / "engines" / "gmpai_integrity" / "prompts" / "part11_prompts.yaml"
)
CALIBRATION_DIR = Path(__file__).parent / "model_qualification"
CALIBRATION_RECORD_PATH = CALIBRATION_DIR / "runtime_calibration_record.json"

# 2 páginas reales, cada una forzada a superar CHUNK_MAX_CHARS (6000) para
# garantizar 2 chunks/llamadas reales separadas -- mismo criterio que el
# caso 6 del Golden Dataset. Texto regulatorio real, nunca lorem ipsum.
_CALIBRATION_TEXT = " ".join(ACCESS_CRITERIA)
CALIBRATION_PAGES = [f"Pagina {i}. {_CALIBRATION_TEXT} " * 60 for i in (1, 2)]

# Documento sintético declarado como tal en todos sus campos identificables
# (documento/archivo/agent_id) -- nunca se hace pasar por un documento real;
# el evento de auditoría real que esto genera queda etiquetado como lo que
# es: una corrida de calibración de rendimiento, no una revisión regulatoria.
CALIBRATION_DOCUMENT_ID = "golden-dataset-runtime-calibration"
CALIBRATION_DOCUMENT_SHA256 = "0" * 64


@dataclass
class CalibrationCall:
    wall_clock_ms: float
    prompt_eval_count: int | None
    eval_count: int | None
    done_reason: str | None


class _InstrumentedProvider:
    """Envoltura de solo-medición -- delega 1:1 en el provider real (mismo
    patrón que `OllamaProvider` delega en `ollama_client`), agrega
    ÚNICAMENTE captura de latencia/tokens por llamada. Nunca modifica el
    prompt que sale ni la respuesta que ve `chunked_engine`."""

    def __init__(self, inner: ModelProvider):
        self._inner = inner
        self.calls: list[CalibrationCall] = []

    @property
    def model_name(self) -> str:
        return self._inner.model_name

    @property
    def context_window(self):
        return getattr(self._inner, "context_window", None)

    def generate(self, prompt: str, *, num_predict: int | None = None) -> dict:
        t0 = time.monotonic()
        raw = (self._inner.generate(prompt, num_predict=num_predict)
               if num_predict is not None else self._inner.generate(prompt))
        wall_ms = (time.monotonic() - t0) * 1000
        self.calls.append(CalibrationCall(
            wall_clock_ms=wall_ms,
            prompt_eval_count=raw.get("prompt_eval_count") if isinstance(raw, dict) else None,
            eval_count=raw.get("eval_count") if isinstance(raw, dict) else None,
            done_reason=raw.get("done_reason") if isinstance(raw, dict) else None,
        ))
        return raw

    def show_digest(self) -> str:
        return self._inner.show_digest()

    def runtime_version(self) -> str:
        return self._inner.runtime_version()


class CalibrationProducedNoCallsError(RuntimeError):
    """`evaluate_chunked()` no generó ninguna llamada real -- nunca se
    reporta una métrica de rendimiento derivada de cero muestras."""


def _percentile(sorted_values: list[float], p: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    idx = p * (len(sorted_values) - 1)
    lo, hi = int(idx), min(int(idx) + 1, len(sorted_values) - 1)
    frac = idx - lo
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * frac


def run_runtime_calibration(provider: ModelProvider | None = None, *,
                             persist: bool = False) -> dict:
    """Corrida real acotada (2 chunks) contra el Golden Dataset. Exige la
    autorización explícita de §4.1 ANTES de la primera llamada real -- nunca
    se asume permitido solo porque el caller es este módulo."""
    inner = provider or DEFAULT_PROVIDER
    fingerprint = gate.build_qualification_fingerprint(inner)
    current_status = gate.evaluate_model_qualification(inner).status

    gate.require_inference_authorized(
        current_status, call_type=gate.CALL_TYPE_INFERENCE,
        run_context=gate.RUN_CONTEXT_MODEL_REQUALIFICATION,
        target=gate.GOLDEN_DATASET_TARGET,
    )

    instrumented = _InstrumentedProvider(inner)
    result = ce.evaluate_chunked(
        CALIBRATION_PROMPT_PATH, agent_id="model_requalification_calibration",
        agent_version="v-calibration", per_unit_text=CALIBRATION_PAGES,
        sistema="calibration", documento=CALIBRATION_DOCUMENT_ID,
        version="v1", archivo=CALIBRATION_DOCUMENT_ID,
        document_sha256=CALIBRATION_DOCUMENT_SHA256,
        run_context="validation", provider=instrumented,
    )

    calls = instrumented.calls
    if not calls:
        raise CalibrationProducedNoCallsError(
            "evaluate_chunked() no genero ninguna llamada real -- 0 chunks ejecutados")

    latencies_s = sorted(c.wall_clock_ms / 1000 for c in calls)
    tokens = [c.eval_count for c in calls if c.eval_count is not None]
    failures = [c for c in result["chunk_executions"] if c.get("technical_execution_failure")]

    metrics = {
        "latency_p50": statistics.median(latencies_s),
        "latency_p95": _percentile(latencies_s, 0.95),
        "tokens_per_task": statistics.mean(tokens) if tokens else None,
        "retry_rate": len(failures) / len(result["chunk_executions"]),
    }

    record = {
        "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_context": gate.RUN_CONTEXT_MODEL_REQUALIFICATION,
        "target": gate.GOLDEN_DATASET_TARGET,
        "fingerprint": fingerprint,
        "n_calls": len(calls),
        "metrics": metrics,
        "raw_calls": [vars(c) for c in calls],
        "run_fingerprint": result["preflight_metadata"]["run_fingerprint"],
        "run_id": result["run_id"],
    }

    if persist:
        CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
        CALIBRATION_RECORD_PATH.write_text(
            json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return record


def load_calibration_record() -> dict | None:
    """Registro persistido de la última calibración, o None si no existe o
    esta corrupto (nunca lanza -- mismo patron que `_load_previous()` de
    model_qualification_gate)."""
    if not CALIBRATION_RECORD_PATH.exists():
        return None
    try:
        return json.loads(CALIBRATION_RECORD_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
