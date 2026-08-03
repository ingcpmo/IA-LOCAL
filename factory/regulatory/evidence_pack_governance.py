"""G5 — validacion y elegibilidad de Evidence Packs para D2-A, segun
`factory/docs/design/regulatory_redesign_v2/governance/EVIDENCE_PACK_GOVERNANCE_AND_D2A_SPEC.md`.

Solo la parte VALIDA (deterministas, sin LLM, sin juicio) y el calculo de
`D2AReadiness` (spec §5). El paso PROPONE (borrador LLM por campo) y el paso
APRUEBA (UI + aplicador) NO estan en alcance de este modulo -- el spec los
declara explicitamente fuera de esta pieza mientras no exista una superficie
de UI real que los invoque (§7: "No aprueba ningun pack ni redacta ningun
criterio").

Reutiliza en vez de duplicar: `evaluate_pack_eligibility()` (D1/D2 del
resolver) ya calcula V9/V10 en `requirement_catalog_loader.py`;
`source_lifecycle.evaluate_registry()` ya calcula el lifecycle_state real de
cada fuente; `artifact_version_guard.guard_report()` ya calcula si el
catalogo esta versionado consistentemente; `semantic_evidence_verification.
verify_anchor()` ya implementa el anclaje de una cita contra un texto.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from factory.core import artifact_version_guard as guard
from factory.core import decision_scope_resolver as resolver
from factory.regulatory import applicability as applicability_mod
from factory.regulatory import source_lifecycle
from factory.regulatory.requirement_catalog.requirement_catalog_loader import (
    evaluate_pack_eligibility, load_requirements, load_source_registry,
)
from factory.regulatory.semantic_evidence_verification import verify_anchor
from factory.regulatory.tools.build_requirement_evidence_pack_context import (
    _load_source_full_text,
)

CATALOG_ARTIFACT_ID = "factory/regulatory/requirement_catalog/requirements.yaml"

#: Los 6 campos de juicio regulatorio humano (spec §2.1). El resto del pack
#: (citation, context_before/after, source_id, normative_type,
#: binding_status, los 8 campos de elegibilidad, pack_version, hashes) es
#: derivado o determinista y no entra en este flujo.
GOVERNED_FIELDS = (
    "evidence_min_criteria", "exclusion_criteria", "weak_keywords",
    "typical_insufficient_evidence", "governed_interpretation",
    "expected_doc_types",
)
#: Campos de tipo lista de los 6 anteriores (governed_interpretation es texto
#: libre, no lista -- V2/V3 tratan listas; V2 tambien exige no-vacio para el
#: texto libre).
LIST_FIELDS = (
    "evidence_min_criteria", "exclusion_criteria", "weak_keywords",
    "typical_insufficient_evidence", "expected_doc_types",
)
#: Campos anclables al texto canonico (V5). `weak_keywords` y
#: `expected_doc_types` son vocabulario/enumeracion, no evidencia citada -- no
#: se anclan (el spec §2.2 solo exige V5 para evidence_min_criteria y
#: exclusion_criteria).
ANCHORABLE_FIELDS = ("evidence_min_criteria", "exclusion_criteria")


def _normalize_for_dedup(text: str) -> str:
    """Minusculas, sin acentos, sin puntuacion final (V3/V4)."""
    t = unicodedata.normalize("NFKD", text.strip().lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[.,;:!?]+$", "", t).strip()


@dataclass(frozen=True)
class ValidationFailure:
    code: str
    field: str
    detail: str


@dataclass(frozen=True)
class PackValidationReport:
    requirement_id: str
    passed: bool
    failures: tuple[ValidationFailure, ...]

    def failure_codes(self) -> tuple[str, ...]:
        return tuple(f.code for f in self.failures)


def validate_pack(requirement_id: str, *,
                  requirements: dict | None = None,
                  registry: dict | None = None,
                  decision_store_file: Path | None = None) -> PackValidationReport:
    """V1-V10 del spec §2.2. Nunca lanza salvo `requirement_id` inexistente
    -- un pack invalido es un resultado (`passed=False`), no una excepcion."""
    catalog = requirements or load_requirements()
    entry = catalog["requirements"][requirement_id]  # KeyError real si no existe -- fail-loud a proposito
    failures: list[ValidationFailure] = []

    # V1 -- schema completo: los 6 campos presentes (pueden faltar del todo
    # en un pack `structure_only_pending_human_interpretation`).
    missing = [f for f in GOVERNED_FIELDS if f not in entry or entry.get(f) is None]
    if missing:
        failures.append(ValidationFailure(
            "V1_SCHEMA_INCOMPLETE", ",".join(missing),
            f"campos ausentes: {missing}"))

    # De aqui en mas, los validadores que dependen de un campo presente se
    # saltan ese campo si V1 ya lo declaro ausente -- comparar contra None
    # no aporta una segunda senal, solo ruido duplicado.
    present_list_fields = [f for f in LIST_FIELDS if entry.get(f) is not None]
    present_text_fields = [f for f in GOVERNED_FIELDS
                           if f not in LIST_FIELDS and entry.get(f) is not None]

    # V2 -- ningun campo vacio ni con lista de 0 elementos.
    for f in present_list_fields:
        if len(entry[f]) == 0:
            failures.append(ValidationFailure("V2_EMPTY_FIELD", f, "lista vacia"))
    for f in present_text_fields:
        if not str(entry[f]).strip():
            failures.append(ValidationFailure("V2_EMPTY_FIELD", f, "texto vacio"))

    # V3 -- sin duplicados dentro de un campo (normalizado).
    for f in present_list_fields:
        seen: dict[str, str] = {}
        for item in entry[f]:
            key = _normalize_for_dedup(str(item))
            if key in seen:
                failures.append(ValidationFailure(
                    "V3_DUPLICATE_WITHIN_FIELD", f,
                    f"{item!r} duplica (normalizado) a {seen[key]!r}"))
            else:
                seen[key] = item

    # V4 -- weak_keywords no puede ser tambien un criterio minimo.
    if "weak_keywords" in present_list_fields and "evidence_min_criteria" in present_list_fields:
        weak_norm = {_normalize_for_dedup(w) for w in entry["weak_keywords"]}
        for crit in entry["evidence_min_criteria"]:
            key = _normalize_for_dedup(str(crit))
            if key in weak_norm:
                failures.append(ValidationFailure(
                    "V4_WEAK_KEYWORD_AS_CRITERION", "evidence_min_criteria",
                    f"{crit!r} es tambien un weak_keyword"))

    # V5 -- cada evidence_min_criteria/exclusion_criteria ancla al texto
    # canonico REAL de la fuente verificada (nunca se inventa: si la fuente
    # no tiene texto completo disponible, se declara explicito, no se omite).
    source_id = entry.get("source_id")
    source_entry = None
    if source_id:
        reg = registry or load_source_registry()
        source_entry = next(
            (s for s in reg["sources"] if s["source_id"] == source_id), None)
    full_text = None
    full_text_error = None
    if source_entry is not None:
        try:
            full_text = _load_source_full_text(source_entry)
        except Exception as exc:  # noqa: BLE001 -- se declara el motivo, nunca se omite
            full_text_error = str(exc)
    for f in ANCHORABLE_FIELDS:
        if f not in present_list_fields:
            continue
        for item in entry[f]:
            if full_text is None:
                failures.append(ValidationFailure(
                    "V5_NOT_ANCHORED", f,
                    f"{item!r}: sin texto completo de la fuente disponible "
                    f"({full_text_error or 'fuente no encontrada'})"))
                continue
            status, match_type = verify_anchor(str(item), full_text)
            if status != "PASS":
                failures.append(ValidationFailure(
                    "V5_NOT_ANCHORED", f,
                    f"{item!r} no ancla al texto canonico de {source_id} "
                    f"(match_type={match_type})"))

    # V6 -- expected_doc_types subconjunto de document_types de la matriz.
    if "expected_doc_types" in present_list_fields:
        known_types = set(applicability_mod.load_matrix().get("document_types") or [])
        unknown = [t for t in entry["expected_doc_types"] if t not in known_types]
        if unknown:
            failures.append(ValidationFailure(
                "V6_UNKNOWN_DOC_TYPE", "expected_doc_types",
                f"tipos fuera de applicability_matrix.yaml: {unknown}"))

    # V7 -- ningun criterio identico a un criterio de OTRO requirement_id.
    # (cierra el defecto ya conocido de req_id duplicado que sobrescribia en
    # silencio -- ver Fase F de project_w5_v2_regulatory_redesign).
    for f in ("evidence_min_criteria", "exclusion_criteria"):
        if f not in present_list_fields:
            continue
        mine = {_normalize_for_dedup(str(i)) for i in entry[f]}
        for other_id, other_entry in catalog["requirements"].items():
            if other_id == requirement_id:
                continue
            other_items = other_entry.get(f) or []
            for other_item in other_items:
                if _normalize_for_dedup(str(other_item)) in mine:
                    failures.append(ValidationFailure(
                        "V7_CROSS_REQUIREMENT_DUPLICATE", f,
                        f"comparte un criterio (normalizado) con {other_id!r}"))
                    break

    # V8 -- hash del pack: delegado en artifact_version_guard, que ya calcula
    # `canonical_hash_pack()` por requirement_id y lo compara contra su
    # version_record -- no se reimplementa el hash aqui.
    report = guard.guard_report(decision_store_file=decision_store_file)
    pack_finding = next(
        (f for f in report["findings"]
         if f["artifact"] == "evidence_pack" and f["artifact_id"] == requirement_id
         and f["severity"] == "FAIL"),
        None)
    if pack_finding is not None:
        failures.append(ValidationFailure(
            "V8_HASH_VERSION_MISMATCH", "pack_version", pack_finding["detail"]))

    # V9 -- la fuente del pack esta en LOCAL_CANONICAL_COPY_VERIFIED.
    if source_id:
        dims = {d.source_id: d for d in source_lifecycle.evaluate_registry()}
        state = dims.get(source_id)
        if state is None or state.lifecycle_state != source_lifecycle.LOCAL_CANONICAL_COPY_VERIFIED:
            failures.append(ValidationFailure(
                "V9_SOURCE_NOT_VERIFIED", "source_id",
                f"{source_id}: lifecycle_state="
                f"{state.lifecycle_state if state else 'DESCONOCIDO'}"))

    # V10 -- resolve("D1", source_id).authorized == True.
    if source_id:
        d1 = resolver.resolve("D1", source_id, store_file=decision_store_file)
        if not d1.authorized:
            failures.append(ValidationFailure(
                "V10_SOURCE_NOT_COVERED_BY_D1", "source_id",
                f"{source_id}: coverage_basis={d1.coverage_basis}"))

    return PackValidationReport(
        requirement_id=requirement_id, passed=not failures,
        failures=tuple(failures))


@dataclass(frozen=True)
class D2AReadiness:
    requirement_id: str
    source_verified: bool
    source_covered: bool
    pack_complete: bool
    matrix_approved: bool
    catalog_versioned: bool
    ready: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)


def _catalog_versioned(*, decision_store_file: Path | None = None) -> bool:
    """`version_guard(catalog).consistent` (spec §5): ninguna inconsistencia
    FAIL registrada para el artefacto `catalog` completo."""
    report = guard.guard_report(decision_store_file=decision_store_file)
    return not any(
        f["artifact"] == "catalog" and f["artifact_id"] == CATALOG_ARTIFACT_ID
        and f["severity"] == "FAIL"
        for f in report["findings"])


def d2a_ready(requirement_id: str, *,
             decision_store_file: Path | None = None) -> D2AReadiness:
    """`D2_A_READY` calculado (spec §5) -- nunca declarado a mano."""
    catalog = load_requirements()
    entry = catalog["requirements"][requirement_id]
    source_id = entry["source_id"]

    dims = {d.source_id: d for d in source_lifecycle.evaluate_registry()}
    state = dims.get(source_id)
    source_verified = (state is not None
                      and state.lifecycle_state == source_lifecycle.LOCAL_CANONICAL_COPY_VERIFIED)

    eligibility = evaluate_pack_eligibility(requirement_id, decision_store_file=decision_store_file)
    source_covered = eligibility.source_decision_authorized

    pack_report = validate_pack(requirement_id, requirements=catalog,
                               decision_store_file=decision_store_file)
    pack_complete = pack_report.passed

    matrix_version = str(applicability_mod.load_matrix().get("matrix_version"))
    matrix_approved = resolver.resolve(
        "APPLICABILITY_MATRIX", matrix_version, store_file=decision_store_file).authorized

    catalog_versioned = _catalog_versioned(decision_store_file=decision_store_file)

    ready = all((source_verified, source_covered, pack_complete,
                matrix_approved, catalog_versioned))

    reasons = []
    if not source_verified:
        reasons.append(f"source_verified=False (lifecycle_state="
                       f"{state.lifecycle_state if state else 'DESCONOCIDO'})")
    if not source_covered:
        reasons.append(f"source_covered=False ({eligibility.source_coverage_basis})")
    if not pack_complete:
        reasons.append(f"pack_complete=False ({len(pack_report.failures)} fallos: "
                       f"{sorted(set(pack_report.failure_codes()))})")
    if not matrix_approved:
        reasons.append(f"matrix_approved=False (matrix_version={matrix_version!r} sin "
                       f"decision APPLICABILITY_MATRIX human_confirmed)")
    if not catalog_versioned:
        reasons.append("catalog_versioned=False (CONTENT_CHANGED_VERSION_SAME pendiente)")

    return D2AReadiness(
        requirement_id=requirement_id, source_verified=source_verified,
        source_covered=source_covered, pack_complete=pack_complete,
        matrix_approved=matrix_approved, catalog_versioned=catalog_versioned,
        ready=ready, reasons=tuple(reasons))
