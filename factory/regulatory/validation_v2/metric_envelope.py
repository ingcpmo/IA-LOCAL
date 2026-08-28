"""WP-E -- Sobre de métrica (metric envelope).

docs_plan/PLAN_HARDENING_ANALIZADOR_GMP_LOCAL_V2.md WP-E:
"cada métrica publicada viaja con `suite_version + tamaño + definición + rango
reportable + declaración de contaminación`. Sin eso, no se publica."

Este módulo hace ese gate EXPLÍCITO y fail-closed: `require_envelope()` lanza si
falta cualquiera de los cinco campos. `publish()` devuelve el dict listo para
persistir.  Aditivo -- no re-puntúa ninguna suite existente.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

REQUIRED_FIELDS = ("metric", "value", "suite_version", "size", "definition",
                   "reportable_range", "contamination_statement")

# Valores admitidos para `reportable_range` cuando no es un intervalo numérico.
RANGE_SENTINELS = ("UNKNOWN", "INDICATIVE_ONLY", "NOT_A_GATE", "SYNTHETIC_ONLY")


class MetricEnvelopeError(ValueError):
    """Se intentó publicar una métrica sin sobre completo."""


@dataclass
class MetricEnvelope:
    metric: str                     # p.ej. "TECHNICAL_RECALL"
    value: object                   # el número/estado medido (no se toca)
    suite_version: str              # versión firmada/etiquetada del instrumento
    size: int | dict                # nº de casos (o {positives, negatives, ...})
    definition: str                 # qué cuenta como TP/FN/FP EXACTAMENTE
    reportable_range: object        # intervalo [lo, hi] o uno de RANGE_SENTINELS
    contamination_statement: str    # cómo se controló autor↔ground-truth, held-out, anchors, etc.
    notes: str = ""
    extra: dict = field(default_factory=dict)

    def validate(self) -> "MetricEnvelope":
        for f in ("metric", "suite_version", "definition", "contamination_statement"):
            if not str(getattr(self, f) or "").strip():
                raise MetricEnvelopeError(f"metric envelope: campo '{f}' vacío")
        rr = self.reportable_range
        is_sentinel = isinstance(rr, str) and rr in RANGE_SENTINELS
        ok_range = is_sentinel or (isinstance(rr, (list, tuple)) and len(rr) == 2)
        if not ok_range:
            raise MetricEnvelopeError(
                f"metric envelope: 'reportable_range' inválido {rr!r} "
                f"(intervalo [lo,hi] o uno de {RANGE_SENTINELS})")
        # `value` puede ser None SOLO si el rango es un sentinel (métrica aún no medible).
        if self.value is None and not is_sentinel:
            raise MetricEnvelopeError(
                "metric envelope: 'value' es None con un rango numérico "
                "(usa reportable_range='UNKNOWN' si aún no hay medición)")
        if isinstance(self.size, int) and self.size <= 0:
            raise MetricEnvelopeError("metric envelope: 'size' <= 0")
        return self

    def as_dict(self) -> dict:
        return asdict(self)


def wrap(metric: str, value, *, suite_version: str, size, definition: str,
         reportable_range, contamination_statement: str, notes: str = "",
         **extra) -> dict:
    return MetricEnvelope(
        metric=metric, value=value, suite_version=suite_version, size=size,
        definition=definition, reportable_range=reportable_range,
        contamination_statement=contamination_statement, notes=notes,
        extra=dict(extra),
    ).validate().as_dict()


def require_envelope(d: dict) -> dict:
    """Fail-closed: valida que `d` sea un sobre de métrica completo."""
    missing = [f for f in REQUIRED_FIELDS if f not in d]
    if missing:
        raise MetricEnvelopeError(f"metric envelope: faltan campos {missing}")
    return MetricEnvelope(
        metric=d["metric"], value=d["value"], suite_version=d["suite_version"],
        size=d["size"], definition=d["definition"],
        reportable_range=d["reportable_range"],
        contamination_statement=d["contamination_statement"],
        notes=d.get("notes", ""), extra=d.get("extra", {}),
    ).validate().as_dict()


def wilson_interval(successes: int, n: int, z: float = 1.96) -> list[float]:
    """Intervalo de Wilson (score) para una proporción. Determinista.
    Para `reportable_range` de recall/precisión sobre muestras pequeñas."""
    if n <= 0:
        return [0.0, 1.0]
    p = successes / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = (z * ((p * (1 - p) / n + z2 / (4 * n * n)) ** 0.5)) / denom
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]
