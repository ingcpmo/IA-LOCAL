"""Model Qualification Gate — W5 V2, Fase G (sección 6 de
MODEL_PROVIDER_AND_LOCAL_AI_RUNTIME_SPEC.md).

Diseñado en la corrida de diseño del 2026-07-23 y NUNCA implementado hasta
hoy (2026-07-28): la auditoría maestra de cierre encontró que el término
solo aparecía en `W5_V2_EXECUTION_SUMMARY.md`, sin una línea de código. El
Golden Dataset (su insumo) sí existía y daba 14/14, pero **nada obligaba a
ejecutarlo**. El agujero real que eso dejó abierto, con nombre y fecha: el
2026-07-28 se cambiaron `num_predict` (1024 -> derivado del contrato) y
`num_ctx` (8192 -> 16384) y se corrió una re-evaluación regulatoria completa
sin que ningún mecanismo exigiera recalificar el modelo.

Qué hace este módulo:

1. Ejecuta el Golden Dataset y deriva de él las métricas que se pueden medir
   de forma DETERMINISTA (sin inferencia real).
2. Declara explícitamente `NOT_MEASURED` las que exigen una corrida real
   contra el modelo (latencia, tokens, reintentos) -- nunca inventa un
   número ni las omite en silencio.
3. Congela el fingerprint de la configuración calificada. Si la
   configuración vigente difiere del último registro de calificación, el
   estado pasa a `QUALIFICATION_INVALIDATED`: la calificación anterior no se
   hereda.
4. Aplica las 7 prioridades de decisión del diseño EN ORDEN, nunca invertido.

Fail-closed: el estado por defecto es `NOT_QUALIFIED`. Ninguna ruta devuelve
`QUALIFIED` sin las 13 métricas medidas y en umbral.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from factory.regulatory.golden_dataset.semantic_verification_golden_dataset import (
    run_all,
    summarize,
)

QUALIFICATION_DIR = Path(__file__).parent / "model_qualification"
RECORD_PATH = QUALIFICATION_DIR / "qualification_record.json"

# Las 13 métricas obligatorias de la sección 6 del spec, en su orden.
REQUIRED_METRICS = (
    "schema_valid_rate",
    "citation_anchor_precision",
    "semantic_precision",
    "semantic_recall",
    "false_positive_rate",
    "false_negative_rate",
    "contradiction_detection_rate",
    "remediation_acceptance_rate",
    "unsupported_claim_rate",
    "latency_p50",
    "latency_p95",
    "tokens_per_task",
    "retry_rate",
)

# Métricas que el Golden Dataset NO puede medir: dependen de inferencia real
# contra el modelo. Se declaran aquí para que su ausencia sea una decisión
# explícita del diseño y no un olvido que alguien "complete" con un 0.
RUNTIME_ONLY_METRICS = ("latency_p50", "latency_p95", "tokens_per_task", "retry_rate")

# Umbrales. Los de precisión/anclaje son 1.0 porque la prioridad 1 del
# diseño es CERO citas inventadas: no admite tolerancia.
THRESHOLDS = {
    "schema_valid_rate": 1.0,
    "citation_anchor_precision": 1.0,
    "semantic_precision": 1.0,
    "semantic_recall": 1.0,
    "false_positive_rate": 0.0,
    "false_negative_rate": 0.0,
    "contradiction_detection_rate": 1.0,
    "remediation_acceptance_rate": 1.0,
    "unsupported_claim_rate": 0.0,
}
# Métricas donde PASA si valor <= umbral (tasas de error). El resto: >=.
LOWER_IS_BETTER = {"false_positive_rate", "false_negative_rate", "unsupported_claim_rate"}

# Prioridades de decisión (sección 6). El orden es normativo.
DECISION_PRIORITIES = (
    ("cero_citas_inventadas", ("citation_anchor_precision", "unsupported_claim_rate")),
    ("menor_tasa_falsos_positivos", ("false_positive_rate",)),
    ("menor_tasa_falsos_negativos_criticos", ("false_negative_rate",)),
    ("cumplimiento_de_schema", ("schema_valid_rate",)),
    ("estabilidad", ("contradiction_detection_rate",)),
    ("calidad_de_remediacion", ("remediation_acceptance_rate",)),
    ("rendimiento", ("latency_p50", "latency_p95", "tokens_per_task", "retry_rate")),
)

STATUS_QUALIFIED = "QUALIFIED"
STATUS_VALIDATION_ONLY = "QUALIFIED_FOR_VALIDATION_ONLY"
STATUS_NOT_QUALIFIED = "NOT_QUALIFIED"
STATUS_INVALIDATED = "QUALIFICATION_INVALIDATED"


@dataclass
class MetricResult:
    name: str
    value: float | None
    threshold: float | None
    measured: bool
    passed: bool | None
    basis: str


@dataclass
class QualificationResult:
    status: str = STATUS_NOT_QUALIFIED
    evaluated_at: str = ""
    fingerprint: dict = field(default_factory=dict)
    previous_fingerprint: dict | None = None
    metrics: list = field(default_factory=list)
    golden_dataset: dict = field(default_factory=dict)
    failed_metrics: list = field(default_factory=list)
    unmeasured_metrics: list = field(default_factory=list)
    priority_verdicts: list = field(default_factory=list)
    blocking_reason: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["metrics"] = [asdict(m) if not isinstance(m, dict) else m for m in self.metrics]
        return d


def build_qualification_fingerprint(provider=None) -> dict:
    """Identidad EXACTA de la configuración que se califica. Cualquier cambio
    aquí invalida la calificación previa -- incluidos `num_predict` y
    `num_ctx`, que es justo lo que faltaba el 2026-07-28.

    `provider` permite calificar un modelo distinto del global sin tocar el
    módulo (mismo patrón que Fase D). None = DEFAULT_PROVIDER."""
    from factory.engines.gmpai_integrity import chunked_engine as ce
    from factory.engines.gmpai_integrity import ollama_client
    from factory.engines.gmpai_integrity.model_provider import DEFAULT_PROVIDER
    from factory.regulatory.requirement_catalog.requirement_catalog_loader import (
        catalog_fingerprint,
    )
    from factory.regulatory.schema_loader import schema_sha256

    provider = provider if provider is not None else DEFAULT_PROVIDER
    prompts = Path(__file__).parent.parent / "engines/gmpai_integrity/prompts"
    prompt_versions = {}
    for name in sorted(p.name for p in prompts.glob("*_prompts.yaml")):
        meta = ce.load_prompt_meta(prompts / name)
        prompt_versions[name] = meta.get("prompt_version")

    return {
        "model_name": provider.model_name,
        "model_digest": provider.show_digest(),
        "prompt_versions": prompt_versions,
        "schema_version": "checkpoint_llm_response_v1",
        "schema_sha256": schema_sha256("checkpoint_llm_response_v1"),
        **catalog_fingerprint(),
        # Configuración de generación: el defecto de 2026-07-28 entró por aquí.
        "num_ctx": ollama_client.NUM_CTX,
        "temperature": ollama_client.TEMPERATURE,
        "chunk_max_chars": ce.CHUNK_MAX_CHARS,
        "chunk_overlap_chars": ce.CHUNK_OVERLAP_CHARS,
        "output_token_budget_formula": {
            "tokens_per_criterion": ce.TOKENS_PER_CRITERION,
            "tokens_per_checkpoint": ce.TOKENS_PER_CHECKPOINT,
            "json_overhead": ce.TOKENS_JSON_OVERHEAD,
        },
    }


def _metrics_from_golden(results: list) -> dict[str, tuple[float, str]]:
    """Deriva las 9 métricas deterministas de los casos reales del Golden
    Dataset. Cada una se ata a las categorías de caso que la sustentan -- no
    se reporta una métrica que ningún caso ejercite."""
    by_cat: dict[str, list] = {}
    for r in results:
        by_cat.setdefault(r.category, []).append(r)

    # Las categorías reales del Golden Dataset son A/B/C/D/pipeline -- las
    # cuatro validaciones del plan más los casos de consolidación. El mapeo
    # se hace contra ESAS categorías (verificado ejecutando run_all()), no
    # contra nombres inventados: una métrica que ningún caso ejercita se
    # queda sin medir, no se rellena.
    def rate(casos: list) -> tuple[float, str] | None:
        if not casos:
            return None
        return (sum(1 for r in casos if r.passed) / len(casos),
                f"{len(casos)} casos: {', '.join(sorted(r.case_id for r in casos))}")

    total = len(results)
    todos = (sum(1 for r in results if r.passed) / total,
             f"{total} casos del Golden Dataset (schema/contrato de salida)")

    anclaje = rate(by_cat.get("A", []) + by_cat.get("B", []))      # A: ancla; B: fuente
    contexto = rate(by_cat.get("C", []))                            # C: relevancia semántica
    suficiencia = rate(by_cat.get("D", []))                         # D: suficiencia
    pipeline = by_cat.get("pipeline", [])
    contradiccion = rate([r for r in pipeline if "contradiction" in r.case_id])
    cobertura = rate([r for r in pipeline if "coverage" in r.case_id])

    metricas: dict[str, tuple[float, str]] = {"schema_valid_rate": todos}
    if anclaje:
        metricas["citation_anchor_precision"] = anclaje
        # Una cita inventada o de otro documento aceptada ES una afirmación
        # sin sustento: la tasa es el complemento de la precisión de anclaje.
        metricas["unsupported_claim_rate"] = (1.0 - anclaje[0], anclaje[1])
    if contexto:
        metricas["semantic_precision"] = contexto
        metricas["false_positive_rate"] = (1.0 - contexto[0], contexto[1])
    if cobertura:
        metricas["semantic_recall"] = cobertura
        metricas["false_negative_rate"] = (1.0 - cobertura[0], cobertura[1])
    if contradiccion:
        metricas["contradiction_detection_rate"] = contradiccion
    if suficiencia:
        metricas["remediation_acceptance_rate"] = suficiencia
    return metricas


def _load_previous() -> dict | None:
    if not RECORD_PATH.exists():
        return None
    try:
        return json.loads(RECORD_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def evaluate_model_qualification(provider=None, *, persist: bool = False) -> QualificationResult:
    """Ejecuta el gate completo. `persist=True` graba el registro de
    calificación (solo se debería hacer desde una calificación real,
    no desde un test)."""
    results = run_all()
    resumen = summarize(results)
    derivadas = _metrics_from_golden(results)
    fingerprint = build_qualification_fingerprint(provider)

    metricas: list[MetricResult] = []
    for name in REQUIRED_METRICS:
        umbral = THRESHOLDS.get(name)
        if name in RUNTIME_ONLY_METRICS:
            metricas.append(MetricResult(
                name=name, value=None, threshold=None, measured=False, passed=None,
                basis="NOT_MEASURED: requiere una corrida real de inferencia; el Golden "
                      "Dataset es determinista y no la produce. Nunca se sustituye por 0.",
            ))
            continue
        if name not in derivadas:
            metricas.append(MetricResult(
                name=name, value=None, threshold=umbral, measured=False, passed=None,
                basis="NOT_MEASURED: ningun caso del Golden Dataset ejercita esta metrica",
            ))
            continue
        valor, basis = derivadas[name]
        ok = valor <= umbral if name in LOWER_IS_BETTER else valor >= umbral
        metricas.append(MetricResult(name=name, value=valor, threshold=umbral,
                                     measured=True, passed=ok, basis=basis))

    fallidas = [m.name for m in metricas if m.measured and not m.passed]
    sin_medir = [m.name for m in metricas if not m.measured]

    veredictos = []
    for prioridad, nombres in DECISION_PRIORITIES:
        involucradas = [m for m in metricas if m.name in nombres]
        medidas = [m for m in involucradas if m.measured]
        if not medidas:
            veredicto = "NOT_MEASURED"
        elif all(m.passed for m in medidas):
            veredicto = "PASS" if len(medidas) == len(involucradas) else "PASS_PARTIAL"
        else:
            veredicto = "FAIL"
        veredictos.append({"priority": prioridad, "metrics": list(nombres),
                           "verdict": veredicto})

    previo = _load_previous()
    fingerprint_previo = (previo or {}).get("fingerprint")

    if fallidas:
        estado = STATUS_NOT_QUALIFIED
        motivo = (f"metricas fuera de umbral: {', '.join(fallidas)}. "
                  f"Prioridad violada: "
                  f"{next(v['priority'] for v in veredictos if v['verdict'] == 'FAIL')}")
    elif sin_medir:
        estado = STATUS_VALIDATION_ONLY
        motivo = (f"{len(sin_medir)} de {len(REQUIRED_METRICS)} metricas sin medir "
                  f"({', '.join(sin_medir)}): habilita run_context='validation', "
                  f"NUNCA produccion. Para QUALIFIED hace falta una corrida real de "
                  f"inferencia que mida latencia, tokens y reintentos.")
    else:
        estado = STATUS_QUALIFIED
        motivo = None

    # La invalidación por cambio de configuración pesa sobre cualquier otro
    # estado positivo: una calificación es de UNA configuración, no del modelo
    # a secas.
    if fingerprint_previo is not None and fingerprint_previo != fingerprint and not fallidas:
        cambios = sorted(k for k in set(fingerprint) | set(fingerprint_previo)
                         if fingerprint.get(k) != fingerprint_previo.get(k))
        estado = STATUS_INVALIDATED
        motivo = (f"la configuracion cambio desde la ultima calificacion "
                  f"({', '.join(cambios)}): la calificacion previa NO se hereda. "
                  f"Recalificar y volver a persistir.")

    resultado = QualificationResult(
        status=estado,
        evaluated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        fingerprint=fingerprint,
        previous_fingerprint=fingerprint_previo,
        metrics=metricas,
        golden_dataset=resumen,
        failed_metrics=fallidas,
        unmeasured_metrics=sin_medir,
        priority_verdicts=veredictos,
        blocking_reason=motivo,
    )

    if persist:
        QUALIFICATION_DIR.mkdir(parents=True, exist_ok=True)
        RECORD_PATH.write_text(json.dumps(resultado.to_dict(), indent=2, ensure_ascii=False),
                               encoding="utf-8")
    return resultado


def require_qualified_for_production(provider=None) -> None:
    """Guardia fail-closed para quien quiera habilitar produccion. Hoy SIEMPRE
    lanza, porque las metricas de runtime no estan medidas -- y eso es
    correcto: PRODUCTION_ENABLEMENT sigue BLOCKED."""
    r = evaluate_model_qualification(provider)
    if r.status != STATUS_QUALIFIED:
        raise ModelNotQualifiedError(f"{r.status}: {r.blocking_reason}")


class ModelNotQualifiedError(RuntimeError):
    """El modelo/configuracion no esta calificado para el uso solicitado."""
