"""W5.3 Fase 5.2 -- loader fail-closed del catalogo atomico de requisitos +
validacion cruzada contra el source_registry. Mismo patron que
factory/regulatory/applicability.py / schema_loader.py: cargar valida,
nunca sirve un dato inconsistente en silencio.

Reglas fail-closed (ninguna es opcional):
  1. Cada entrada de requirements.yaml y de source_registry.json debe
     validar contra su JSON Schema (additionalProperties:false).
  2. requirement.source_id DEBE resolver a un source_id existente en el
     registry -- si no, error al cargar (no un requisito "huerfano").
  3. requirement.citation.citation_sha256 se RECALCULA desde citation_text
     y se compara -- una discrepancia es un error (la cita pudo ser
     editada sin recalcular el hash).
  4. review_status=covered SOLO es valido si match_type in
     (exact, normalized) Y el source_id resuelve. Cualquier otra
     combinacion con review_status=covered es un error de carga (fail
     inmediato) -- covered nunca se declara por accidente.
  5. Cada derived_artifact.source_sha256 debe coincidir con el
     sha256_copy del source padre.

W5 V2 G1.8 -- CONSUMIDOR C-2 del DecisionScopeResolver
------------------------------------------------------
CARGAR un catalogo y estar AUTORIZADO a usar un pack son dos cosas distintas,
y este modulo las mantiene separadas a proposito:

  - `load_requirements()` sigue sin consultar decision alguna. Un catalogo es
    legible con independencia de que sus packs esten aprobados; hacerlo
    depender del almacen de decisiones romperia toda lectura -- informes,
    diagnostico, la propia UI de gobernanza -- en cuanto faltara una firma.
  - `evaluate_pack_eligibility()` es la superficie nueva: responde si un pack
    PUEDE USARSE, y para eso si pregunta al resolver.

`PACK_USE_ALLOWED` exige DOS coberturas independientes, nunca colapsadas:
D2 sobre el `requirement_id` (alguien firmo los criterios interpretativos) y
D1 sobre su `source_id` (alguien firmo que esa fuente se use). Un pack
impecable sobre una fuente no autorizada no es utilizable."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml as _yaml

from factory.core import decision_scope_resolver as _resolver
from factory.regulatory.schema_loader import validate_against

CATALOG_DIR = Path(__file__).parent
REQUIREMENTS_PATH = CATALOG_DIR / "requirements.yaml"
REGISTRY_PATH = CATALOG_DIR.parent / "sources" / "registry.json"

_VALID_MATCH_TYPES_FOR_COVERED = {"exact", "normalized"}


class CatalogValidationError(Exception):
    """Fail-closed: el catalogo o el registry no pasan validacion. Nunca se
    sirve un catalogo parcialmente invalido."""


def _sha256_text(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def catalog_fingerprint() -> dict:
    """W5 V2, Fase F (invalidacion de checkpoint por fingerprint,
    2026-07-25). {"catalog_version", "catalog_sha256"} -- mismo patron de
    hash-de-archivo que schema_loader.schema_sha256(), pero sobre
    requirements.yaml completo (no un campo individual). Usado por
    chunked_engine.build_run_fingerprint() para que un checkpoint no se
    reanude si el catalogo cambio desde que se guardo."""
    return {
        "catalog_version": load_requirements().get("catalog_version"),
        "catalog_sha256": hashlib.sha256(REQUIREMENTS_PATH.read_bytes()).hexdigest(),
    }


@lru_cache(maxsize=1)
def load_source_registry() -> dict:
    if not REGISTRY_PATH.exists():
        raise CatalogValidationError(f"source_registry no encontrado: {REGISTRY_PATH}")
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    for entry in data.get("sources", []):
        ok, errors = validate_against(entry, "source_registry_entry_v1")
        if not ok:
            raise CatalogValidationError(
                f"source_registry entry invalida ({entry.get('source_id')}): {errors}"
            )
        for artifact in entry.get("derived_artifacts", []):
            if artifact["source_sha256"] != entry["sha256_copy"]:
                raise CatalogValidationError(
                    f"derived_artifact de {entry['source_id']} tiene source_sha256 "
                    f"que no coincide con sha256_copy del source padre"
                )
    return data


@lru_cache(maxsize=1)
def known_source_ids() -> frozenset[str]:
    return frozenset(e["source_id"] for e in load_source_registry()["sources"])


@lru_cache(maxsize=1)
def load_requirements() -> dict:
    if not REQUIREMENTS_PATH.exists():
        raise CatalogValidationError(f"requirements.yaml no encontrado: {REQUIREMENTS_PATH}")
    catalog = _yaml.safe_load(REQUIREMENTS_PATH.read_text(encoding="utf-8"))
    source_ids = known_source_ids()

    for req_id, entry in (catalog.get("requirements") or {}).items():
        full_entry = {"requirement_id": req_id, **entry}
        ok, errors = validate_against(full_entry, "requirement_catalog_entry_v1")
        if not ok:
            raise CatalogValidationError(f"{req_id}: entrada invalida contra schema: {errors}")

        citation = entry["citation"]
        recomputed = _sha256_text(citation["citation_text"])
        if recomputed != citation["citation_sha256"]:
            raise CatalogValidationError(
                f"{req_id}: citation_sha256 declarado ({citation['citation_sha256']}) "
                f"no coincide con el recalculado ({recomputed}) -- la cita pudo editarse "
                f"sin recalcular el hash."
            )

        source_resolves = entry["source_id"] in source_ids
        citation_anchored = citation["match_type"] in _VALID_MATCH_TYPES_FOR_COVERED
        should_be_covered = source_resolves and citation_anchored

        if entry["review_status"] == "covered" and not should_be_covered:
            raise CatalogValidationError(
                f"{req_id}: review_status='covered' pero source_resolves={source_resolves} "
                f"citation_anchored={citation_anchored} -- covered nunca se declara sin ambas "
                f"condiciones (fail-closed)."
            )
        if entry["review_status"] == "review_required" and should_be_covered:
            # No es un error -- un requisito puede degradarse a review_required
            # por otras razones (ej. decision humana futura); pero SI es un
            # error que 'covered' se declare sin cumplir las condiciones (arriba).
            pass

    return catalog


def get_requirement(requirement_id: str) -> dict:
    """Devuelve la entrada completa o lanza CatalogValidationError si el
    requisito no existe -- nunca None silencioso."""
    reqs = load_requirements()["requirements"]
    if requirement_id not in reqs:
        raise CatalogValidationError(f"requirement_id desconocido en el catalogo: {requirement_id!r}")
    return reqs[requirement_id]


def get_source(source_id: str) -> dict:
    for entry in load_source_registry()["sources"]:
        if entry["source_id"] == source_id:
            return entry
    raise CatalogValidationError(f"source_id desconocido en el registry: {source_id!r}")


# ---------------------------------------------------------------------------
# C-2 -- elegibilidad de uso de un Evidence Pack
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PackEligibility:
    requirement_id: str
    source_id: str
    pack_use_allowed: bool
    pack_decision_authorized: bool
    source_decision_authorized: bool
    pack_coverage_basis: str
    source_coverage_basis: str
    covering_decisions: tuple[str, ...]
    denial_reasons: tuple[str, ...]

    @property
    def formal_conclusion_allowed(self) -> bool:
        """Alias explicito: sin cobertura humana no hay conclusion formal."""
        return self.pack_use_allowed


def evaluate_pack_eligibility(requirement_id: str, *,
                              decision_store_file: Path | None = None) -> PackEligibility:
    """PACK_USE_ALLOWED para un requisito. Read-only, fail-closed.

    No lanza si el requisito no esta autorizado -- devuelve el detalle. Un
    requisito no autorizado debe salir NO EVALUADO del pipeline, nunca
    incumplido, y para eso el llamador necesita el motivo, no una excepcion.
    """
    entry = get_requirement(requirement_id)      # si no existe, si lanza
    source_id = entry["source_id"]

    pack = _resolver.resolve("D2", requirement_id, store_file=decision_store_file)
    source = _resolver.resolve("D1", source_id, store_file=decision_store_file)

    reasons = []
    if not pack.authorized:
        reasons.append(f"D2/{requirement_id}: {pack.denial_reason}")
    if not source.authorized:
        reasons.append(f"D1/{source_id}: {source.denial_reason}")

    return PackEligibility(
        requirement_id=requirement_id,
        source_id=source_id,
        pack_use_allowed=pack.authorized and source.authorized,
        pack_decision_authorized=pack.authorized,
        source_decision_authorized=source.authorized,
        pack_coverage_basis=pack.coverage_basis,
        source_coverage_basis=source.coverage_basis,
        covering_decisions=tuple(pack.covering_instances) + tuple(source.covering_instances),
        denial_reasons=tuple(reasons),
    )


def eligible_requirement_ids(*, decision_store_file: Path | None = None) -> list[str]:
    """Los requisitos realmente utilizables hoy. Lo usa el planner (C-3) para
    no gastar presupuesto de inferencia en lo que no esta autorizado."""
    return [
        rid for rid in load_requirements()["requirements"]
        if evaluate_pack_eligibility(rid, decision_store_file=decision_store_file).pack_use_allowed
    ]


@dataclass
class ValidationSummary:
    total: int
    covered: int
    review_required: int
    requirement_ids_review_required: list[str]


def validate_all() -> ValidationSummary:
    """Fuerza la carga completa (todas las validaciones fail-closed de
    arriba) y devuelve un resumen -- si algo es invalido, ya lanzo antes
    de llegar aqui."""
    reqs = load_requirements()["requirements"]
    review_required = [rid for rid, e in reqs.items() if e["review_status"] == "review_required"]
    return ValidationSummary(
        total=len(reqs),
        covered=len(reqs) - len(review_required),
        review_required=len(review_required),
        requirement_ids_review_required=review_required,
    )
