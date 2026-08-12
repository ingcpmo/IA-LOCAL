"""Ciclo de vida de una fuente regulatoria — W5 V2 G1.12.

Implementa SOURCE_LIFECYCLE_SPEC.md. Cierra A-2 (una fuente autorizada para
existir pero no para su ciclo de vida) y da nombre formal a lo que pasó con
21 CFR Part 211.

EL PUNTO ENTERO DE ESTE MODULO
------------------------------
Hoy el registry maneja tres campos independientes que se leen como si fueran
uno. Part 211 tiene `local_integrity_status=PASS` -- su hash se recalculó y
coincide -- y en un informe eso se lee como "fuente verificada", cuando lo
único demostrado es que el fichero no se corrompió desde que se copió.

Aquí se separan CINCO dimensiones ortogonales, cada una respondiendo a una
pregunta distinta, y cada una capaz de estar en verde con las demás en rojo:

    COPY_HASH_INTEGRITY           ¿la copia local sigue siendo la ingerida?
    OFFICIAL_ORIGIN_VERIFICATION  ¿viene de la URL oficial y se comparó?
    REGULATORY_CURRENCY           ¿el texto sigue vigente hoy?
    HUMAN_DECISION_COVERAGE       ¿un humano firmó que se use?
    FORMAL_USE_ELIGIBILITY        ¿puede sustentar una conclusión formal?

La quinta es la CONJUNCION de las cuatro y la única que habilita conclusiones
formales. Ninguna de las cuatro por separado lo hace, y ninguna combinación
de tres tampoco.

REGLA ANTI-COLAPSO (§2.2): ningún informe, endpoint, UI o artefacto puede
exponer un único booleano "fuente verificada". Quien necesite un resumen,
expone las cinco. `test_no_collapsed_source_verified_flag` lo vigila.

NINGUNA DIMENSION LEE A OTRA. Cada `_dim_*` recibe solo lo que necesita y no
llama a las demás; `test_l01_dimensions_are_computed_independently` lo
comprueba por AST. Una dimensión que se derive de otra es el colapso de
siempre por otro camino.

READ-ONLY. Este módulo NO escribe en `registry.json`, no promueve estados y
no sale a la red. `derive_registry_v2()` genera un artefacto NUEVO y
derivado; el rollback es borrarlo.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

from factory.core import decision_scope_resolver as _resolver

DECISION_FAMILY = "D1"

REPO = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO / "factory" / "regulatory" / "sources" / "registry.json"
REGISTRY_V2_PATH = REPO / "factory" / "regulatory" / "sources" / "registry_v2.json"

# --- Valores de cada dimensión ----------------------------------------------
# Enums y no booleanos a propósito. `OFFICIAL_ORIGIN_VERIFICATION` de Part 211
# es ÁMBAR, no rojo: `apply_source_registration()` RECHAZA por código declarar
# `VERIFIED_AGAINST_PRIOR_KNOWN_HASH` en una primera ingesta, porque no hay
# hash previo con el que comparar. El valor es honesto y forzado, no un
# descuido, y aplanarlo a `False` perdería justo esa diferencia.

# COPY_HASH_INTEGRITY
COPY_VERIFIED = "VERIFIED"
COPY_CORRUPTED = "CORRUPTED"
COPY_FILE_MISSING = "FILE_MISSING"

# OFFICIAL_ORIGIN_VERIFICATION
ORIGIN_VERIFIED = "VERIFIED"
ORIGIN_FIRST_INGESTION = "NOT_COMPARABLE_FIRST_INGESTION"   # ámbar
ORIGIN_UNVERIFIED = "UNVERIFIED"

# REGULATORY_CURRENCY
CURRENCY_CURRENT = "CURRENT"
CURRENCY_PENDING = "PENDING_REVERIFICATION"
CURRENCY_EXPIRED = "EXPIRED"

# HUMAN_DECISION_COVERAGE — proyección de `coverage_basis`, no un cálculo
# nuevo. El resolver es la única autoridad sobre quién firmó qué.
COVERAGE_COVERED = "COVERED"
COVERAGE_NOT_COVERED = "NOT_COVERED"
COVERAGE_REVOKED = "REVOKED"
COVERAGE_RECONSTRUCTED = "RECONSTRUCTED_PENDING_FORMAL_CORRECTION"

# --- Estados del ciclo de vida (§3) -----------------------------------------
REGISTERED_PENDING_AUTHORIZATION = "REGISTERED_PENDING_AUTHORIZATION"
AUTHORIZED_PENDING_REVERIFICATION = "AUTHORIZED_PENDING_REVERIFICATION"
LOCAL_CANONICAL_COPY_VERIFIED = "LOCAL_CANONICAL_COPY_VERIFIED"
SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
REVERIFICATION_EXPIRED = "REVERIFICATION_EXPIRED"
REVOKED = "REVOKED"

LIFECYCLE_STATES = (
    REGISTERED_PENDING_AUTHORIZATION,
    AUTHORIZED_PENDING_REVERIFICATION,
    LOCAL_CANONICAL_COPY_VERIFIED,
    SOURCE_UNAVAILABLE,
    REVERIFICATION_EXPIRED,
    REVOKED,
)

# Estados que conceden MAS permiso que el de partida. Ninguna transición hacia
# uno de ellos puede ser automática (§3.2): exige un acto humano o un chequeo
# determinista lanzado con identidad humana real. Restringir sí es automático,
# porque restringir es seguro.
PERMISSIVE_STATES = frozenset({
    AUTHORIZED_PENDING_REVERIFICATION,
    LOCAL_CANONICAL_COPY_VERIFIED,
})


@dataclass(frozen=True)
class SourceDimensions:
    source_id: str
    copy_hash_integrity: str
    official_origin_verification: str
    regulatory_currency: str
    human_decision_coverage: str
    formal_use_eligibility: bool
    lifecycle_state: str
    # Por qué no es elegible, en palabras. Un `false` sin motivo obliga a
    # reconstruir el razonamiento a mano en cada informe.
    ineligibility_reasons: tuple[str, ...]
    evaluated_at: str


# ---------------------------------------------------------------------------
# Las cuatro dimensiones de entrada. Independientes por construcción.
# ---------------------------------------------------------------------------

def _dim_copy_hash_integrity(canonical_path: str, sha256_copy: str, *,
                             repo: Path | None = None) -> str:
    """¿El fichero canónico sigue siendo el que se ingirió?

    Recalcula. No se fía de `local_integrity_status`, que es el resultado
    almacenado de un cálculo pasado: si el fichero se corrompió después, el
    campo sigue diciendo PASS.
    """
    base = repo or REPO
    path = Path(canonical_path)
    if not path.is_absolute():
        path = base / path
    if not path.is_file():
        return COPY_FILE_MISSING

    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return COPY_VERIFIED if h.hexdigest() == sha256_copy else COPY_CORRUPTED


def _dim_official_origin_verification(official_origin_status: str) -> str:
    """¿Procede de la URL oficial primaria y se comparó contra algo?"""
    status = official_origin_status or ""
    if status.startswith("VERIFIED_AGAINST_PRIOR_KNOWN_HASH"):
        return ORIGIN_VERIFIED
    if status.startswith("FIRST_INGESTION_NO_PRIOR_KNOWN_HASH"):
        # Ámbar: falta un segundo punto de comparación en el tiempo, que solo
        # puede existir tras la primera reverificación. Se resuelve con el
        # tiempo, no con una corrección.
        return ORIGIN_FIRST_INGESTION
    return ORIGIN_UNVERIFIED


def _dim_regulatory_currency(regulatory_currency_status: str,
                             reverification_due, *, now=None) -> str:
    """¿El texto sigue vigente hoy?

    `reverification_due` vencido gana sobre cualquier estado almacenado:
    caducar es una restricción, y restringir es la operación segura.
    """
    if reverification_due:
        try:
            due = datetime.fromisoformat(str(reverification_due).replace("Z", "+00:00"))
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            if due < (now or datetime.now(timezone.utc)):
                return CURRENCY_EXPIRED
        except ValueError:
            # Fecha ilegible: no se puede afirmar vigencia sobre algo que no
            # se sabe leer.
            return CURRENCY_PENDING

    if (regulatory_currency_status or "").lower() in ("verified_current", "current"):
        return CURRENCY_CURRENT
    return CURRENCY_PENDING


def _dim_human_decision_coverage(source_id: str, *,
                                 decision_store_file: Path | None = None) -> str:
    """¿Un humano firmó que esta fuente se use, con qué cadencia y autoridad?"""
    scope = _resolver.resolve(DECISION_FAMILY, source_id,
                              store_file=decision_store_file)
    if scope.authorized:
        return COVERAGE_COVERED
    if scope.coverage_basis == _resolver.REVOKED:
        return COVERAGE_REVOKED
    if scope.coverage_basis == _resolver.RECONSTRUCTED_PENDING_FORMAL_CORRECTION:
        # Se distingue de NOT_COVERED para poder DECIRLO en un informe. No
        # autoriza igualmente: reconstruir lo que probablemente se firmó no es
        # lo mismo que tener la firma.
        return COVERAGE_RECONSTRUCTED
    return COVERAGE_NOT_COVERED


# ---------------------------------------------------------------------------
# La quinta dimensión y el estado
# ---------------------------------------------------------------------------

def _formal_use_eligibility(copy: str, origin: str, currency: str,
                            coverage: str) -> tuple[bool, tuple[str, ...]]:
    """Conjunción estricta de las cuatro. Devuelve además POR QUE no."""
    reasons = []
    if copy != COPY_VERIFIED:
        reasons.append(f"COPY_HASH_INTEGRITY={copy}")
    if origin != ORIGIN_VERIFIED:
        reasons.append(f"OFFICIAL_ORIGIN_VERIFICATION={origin}")
    if currency != CURRENCY_CURRENT:
        reasons.append(f"REGULATORY_CURRENCY={currency}")
    if coverage != COVERAGE_COVERED:
        reasons.append(f"HUMAN_DECISION_COVERAGE={coverage}")
    return (not reasons), tuple(reasons)


def derive_lifecycle_state(copy: str, origin: str, currency: str,
                           coverage: str) -> str:
    """Derivación determinista del estado (§3.1). Sin juicio, sin excepciones.

    ORDEN DELIBERADO: la cobertura humana se evalúa ANTES que la vigencia.
    Una fuente no autorizada no debe siquiera preguntarse si está vigente --
    preguntarlo implica salir a la red por algo que nadie firmó que se
    pudiera usar. El orden de este `if` es, literalmente, lo que impide el
    tráfico saliente no autorizado.
    """
    if coverage == COVERAGE_REVOKED:
        return REVOKED
    if copy != COPY_VERIFIED:
        # Una copia local corrupta es un incidente, no un estado ordinario:
        # bloquea todo uso de la fuente, provisional incluido.
        return SOURCE_UNAVAILABLE
    if coverage != COVERAGE_COVERED:
        return REGISTERED_PENDING_AUTHORIZATION
    if currency == CURRENCY_EXPIRED:
        return REVERIFICATION_EXPIRED
    if currency != CURRENCY_CURRENT:
        return AUTHORIZED_PENDING_REVERIFICATION
    if origin != ORIGIN_VERIFIED:
        # Las cuatro no están en verde: `LOCAL_CANONICAL_COPY_VERIFIED` exige
        # las cuatro, y el origen ámbar no lo es.
        return AUTHORIZED_PENDING_REVERIFICATION
    return LOCAL_CANONICAL_COPY_VERIFIED


def evaluate_source(entry: dict, *,
                    decision_store_file: Path | None = None,
                    repo: Path | None = None,
                    now=None) -> SourceDimensions:
    """Las cinco dimensiones y el estado de UNA entrada del registry.

    No muta `entry` ni escribe nada. No accede a la red.
    """
    source_id = entry["source_id"]
    copy = _dim_copy_hash_integrity(
        entry.get("canonical_path", ""), entry.get("sha256_copy", ""), repo=repo)
    origin = _dim_official_origin_verification(entry.get("official_origin_status", ""))
    currency = _dim_regulatory_currency(
        entry.get("regulatory_currency_status", ""),
        entry.get("reverification_due"), now=now)
    coverage = _dim_human_decision_coverage(
        source_id, decision_store_file=decision_store_file)

    eligible, reasons = _formal_use_eligibility(copy, origin, currency, coverage)
    return SourceDimensions(
        source_id=source_id,
        copy_hash_integrity=copy,
        official_origin_verification=origin,
        regulatory_currency=currency,
        human_decision_coverage=coverage,
        formal_use_eligibility=eligible,
        lifecycle_state=derive_lifecycle_state(copy, origin, currency, coverage),
        ineligibility_reasons=reasons,
        evaluated_at=datetime.now(timezone.utc).isoformat(),
    )


def evaluate_registry(registry_path: Path | None = None, *,
                      decision_store_file: Path | None = None,
                      repo: Path | None = None,
                      now=None) -> list[SourceDimensions]:
    path = registry_path or REGISTRY_PATH
    data = json.loads(path.read_text(encoding="utf-8"))
    return [evaluate_source(e, decision_store_file=decision_store_file,
                            repo=repo, now=now)
            for e in data.get("sources", [])]


# ---------------------------------------------------------------------------
# R3-T1.2/F0.6 (2026-08-12) -- espejo mecánico hacia el catálogo de
# requisitos. `requirements.yaml` declara su PROPIO
# `source_verification_status` por requisito (redundante por diseño con
# este módulo -- el schema exige que coincida con la fuente real), pero
# nada lo mantenía sincronizado tras una reverificación real: el catálogo
# quedó congelado en 'PENDING_REVERIFICATION' incluso después de que la
# segunda reingesta gobernada (G3, 2026-08-07) llevara las 4 fuentes a
# LOCAL_CANONICAL_COPY_VERIFIED (verificado en vivo, no leído de un campo
# guardado). Esta función NUNCA toca disco ni decide nada por juicio
# humano -- es una función pura texto->texto, deliberadamente simétrica a
# `artifact_version_apply.CATALOG_VERSION_LINE` (sustitución por regex
# sobre el texto vivo, preservando comentarios/formato/orden -- nunca un
# round-trip por un dumper YAML genérico, que destruiría ambos). El
# resultado se PROPONE como ARTIFACT_VERSION (nunca se escribe aquí).
# ---------------------------------------------------------------------------

import re as _re

_SOURCE_VERIFICATION_LINE = _re.compile(
    r"(\bsource_verification_status:\s*)([A-Z_]+)")


def sync_catalog_source_verification_status(
    catalog_text: str, requirement_order: list[tuple[str, str]], *,
    registry_path: Path | None = None,
    decision_store_file: Path | None = None,
    repo: Path | None = None,
    now=None,
) -> tuple[str, dict]:
    """Recalcula `source_verification_status` de cada requisito contra el
    estado REAL y vivo de `evaluate_registry()` (nunca contra un campo
    guardado). `requirement_order` es `[(requirement_id, source_id), ...]`
    EN EL ORDEN en que aparecen en `catalog_text` -- el llamador lo deriva
    de `yaml.safe_load(catalog_text)['requirements']` (Python/PyYAML
    preservan el orden del archivo) ANTES de llamar aquí, para que esta
    función no dependa de un parser YAML propio y quede fácil de probar
    con texto sintético corto.

    Devuelve `(nuevo_texto, changes)` -- `changes` mapea
    `requirement_id -> {'from': ..., 'to': ...}` SOLO para las entradas que
    de verdad cambian (transparencia total del diff antes de proponerlo,
    nunca "se recalculó todo" sin decir qué cambió realmente). Si el
    número de ocurrencias de `source_verification_status:` en el texto no
    coincide con `len(requirement_order)`, falla explícito -- nunca
    adivina a qué requisito pertenece cada línea."""
    matches = list(_SOURCE_VERIFICATION_LINE.finditer(catalog_text))
    if len(matches) != len(requirement_order):
        raise ValueError(
            f"{len(matches)} líneas 'source_verification_status:' en el texto, "
            f"pero {len(requirement_order)} requisitos declarados -- no se puede "
            "emparejar 1:1 con seguridad, nada se cambia")

    dims_by_source = {d.source_id: d for d in evaluate_registry(
        registry_path, decision_store_file=decision_store_file, repo=repo, now=now)}

    changes: dict[str, dict[str, str]] = {}
    pieces: list[str] = []
    cursor = 0
    for (req_id, source_id), m in zip(requirement_order, matches):
        dim = dims_by_source.get(source_id)
        new_status = (
            LOCAL_CANONICAL_COPY_VERIFIED
            if dim is not None and dim.lifecycle_state == LOCAL_CANONICAL_COPY_VERIFIED
            else CURRENCY_PENDING
        )
        old_status = m.group(2)
        pieces.append(catalog_text[cursor:m.start()])
        pieces.append(m.group(1) + new_status)
        cursor = m.end()
        if old_status != new_status:
            changes[req_id] = {"from": old_status, "to": new_status}
    pieces.append(catalog_text[cursor:])
    return "".join(pieces), changes


# ---------------------------------------------------------------------------
# Derivación aditiva a registry_v2.json
# ---------------------------------------------------------------------------

def derive_registry_v2(registry_path: Path | None = None,
                       out_path: Path | None = None, *,
                       decision_store_file: Path | None = None,
                       repo: Path | None = None,
                       now=None) -> dict:
    """Genera `registry_v2.json` a partir de `registry.json`. ADITIVO.

    `registry.json` NO SE TOCA -- ni se reescribe, ni se reordena, ni se
    reformatea. Los campos actuales (`local_integrity_status`,
    `official_origin_status`, `regulatory_currency_status`) se conservan tal
    cual en el v2: son las ENTRADAS de las dimensiones, no sus sustitutos.
    Borrarlos convertiría el v2 en la única verdad y haría el rollback
    imposible; conservándolos, el rollback es borrar el fichero.
    """
    src = registry_path or REGISTRY_PATH
    dst = out_path or REGISTRY_V2_PATH
    data = json.loads(src.read_text(encoding="utf-8"))

    sources_v2 = []
    for entry in data.get("sources", []):
        dims = evaluate_source(entry, decision_store_file=decision_store_file,
                               repo=repo, now=now)
        merged = dict(entry)
        merged["lifecycle_state"] = dims.lifecycle_state
        merged["dimensions"] = {
            "COPY_HASH_INTEGRITY": dims.copy_hash_integrity,
            "OFFICIAL_ORIGIN_VERIFICATION": dims.official_origin_verification,
            "REGULATORY_CURRENCY": dims.regulatory_currency,
            "HUMAN_DECISION_COVERAGE": dims.human_decision_coverage,
            "FORMAL_USE_ELIGIBILITY": dims.formal_use_eligibility,
        }
        merged["ineligibility_reasons"] = list(dims.ineligibility_reasons)
        sources_v2.append(merged)

    out = {
        "registry_version": 2,
        "derived_from": src.name,
        "derived_from_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources_v2,
    }
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def as_dict(dims: SourceDimensions) -> dict:
    """Serialización de las CINCO dimensiones. Nunca un booleano único.

    Existe para que ningún consumidor tenga la tentación de inventarse su
    propio resumen: si necesita uno, este es, y trae las cinco.
    """
    d = asdict(dims)
    d["ineligibility_reasons"] = list(dims.ineligibility_reasons)
    return d
