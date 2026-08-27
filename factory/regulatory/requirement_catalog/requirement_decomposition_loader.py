"""Loader del archivo gobernado `decomposition.yaml` (V2, B3) —
docs_plan/PLAN_IMPLEMENTACION_ANALIZADOR_GMP_LOCAL_V2.md B3.

`decomposition.yaml` es HERMANO de `requirements.yaml`, no está dentro del
catálogo v1 (requirement_catalog_entry_v1.json es additionalProperties:false;
meterlo ahí rompería CURRENT). Este loader vive en el camino V2 y no lo
consume ningún código de CURRENT.

Validación fail-closed:
  - todo `requirement_id` de decomposition.yaml existe en el catálogo;
  - todo sub-criterio tiene `id` y `text` no vacíos;
  - `id` único dentro de cada requisito;
  - `total_subcriteria` declarado == real;
  - `require_full_coverage()` exige que TODO requisito del catálogo tenga
    descomposición (un requisito sin sub-criterios no es evaluable en
    modo V2 -- nunca se degrada en silencio).

Sin dependencias nuevas (yaml ya es dependencia del proyecto).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml as _yaml

DECOMPOSITION_PATH = Path(__file__).parent / "decomposition.yaml"


class DecompositionError(Exception):
    """decomposition.yaml ausente, malformado, o inconsistente con el catálogo."""


@lru_cache(maxsize=1)
def load_decomposition() -> dict:
    if not DECOMPOSITION_PATH.exists():
        raise DecompositionError(f"decomposition.yaml no encontrado: {DECOMPOSITION_PATH}")
    data = _yaml.safe_load(DECOMPOSITION_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "requirements" not in data:
        raise DecompositionError("decomposition.yaml sin bloque 'requirements'")

    reqs = data["requirements"]
    bilingual = bool(data.get("bilingual"))
    seen_total = 0
    for rid, block in reqs.items():
        subs = (block or {}).get("subcriteria") or []
        if not subs:
            raise DecompositionError(f"{rid}: sin subcriteria")
        ids = set()
        for i, sc in enumerate(subs):
            if not sc.get("id"):
                raise DecompositionError(f"{rid}: subcriterio {i} sin id")
            if not (sc.get("text") or "").strip():
                raise DecompositionError(f"{rid}::{sc.get('id')}: text vacío")
            if bilingual and not (sc.get("text_en") or "").strip():
                raise DecompositionError(
                    f"{rid}::{sc['id']}: bilingual=true pero text_en vacío")
            if sc["id"] in ids:
                raise DecompositionError(f"{rid}: id de subcriterio duplicado: {sc['id']!r}")
            ids.add(sc["id"])
        seen_total += len(subs)

    declared = data.get("total_subcriteria")
    if declared is not None and declared != seen_total:
        raise DecompositionError(
            f"total_subcriteria declarado ({declared}) != real ({seen_total})")

    # Coherencia con el catálogo: todo requirement_id debe existir.
    try:
        from factory.regulatory.requirement_catalog.requirement_catalog_loader import (
            load_requirements,
        )
        catalog_ids = set((load_requirements().get("requirements") or {}))
    except Exception as e:  # noqa: BLE001 -- el catálogo tiene sus propios tests
        raise DecompositionError(f"no se pudo cargar el catálogo para validar: {e}") from e
    unknown = set(reqs) - catalog_ids
    if unknown:
        raise DecompositionError(
            f"decomposition.yaml referencia requisitos que no están en el catálogo: {sorted(unknown)}")

    return data


def decomposition_version() -> str:
    return str(load_decomposition().get("decomposition_version", "unknown"))


def get_subcriteria(requirement_id: str) -> list[dict]:
    """Lista de `{id, text, derived_from}` para un requisito. Lanza
    DecompositionError si el requisito no tiene descomposición (nunca
    devuelve [] silencioso)."""
    reqs = load_decomposition()["requirements"]
    if requirement_id not in reqs:
        raise DecompositionError(
            f"{requirement_id!r} sin descomposición en decomposition.yaml "
            f"(v{decomposition_version()})")
    return list(reqs[requirement_id]["subcriteria"])


def subcriterion_ref(requirement_id: str, sc_id: str) -> str:
    return f"{requirement_id}::{sc_id}"


def subcriterion_match_text(sc: dict) -> str:
    """Texto para recuperación/rerank de un sub-criterio: `text` (ES,
    autoritativo) + `text_en` (glosa EN, aid cross-idioma) si existe. El
    ANCLAJE final sigue siendo Claim.source_text, nunca esto."""
    parts = [sc.get("text", "")]
    if sc.get("text_en"):
        parts.append(sc["text_en"])
    return " ".join(p for p in parts if p).strip()


def has_decomposition(requirement_id: str) -> bool:
    return requirement_id in load_decomposition()["requirements"]


def require_full_coverage(requirement_ids: list[str]) -> None:
    """Fail-closed: lanza si algún requisito de la lista no tiene
    descomposición. Lo llama el orquestador V2 antes de una corrida."""
    missing = [r for r in requirement_ids if not has_decomposition(r)]
    if missing:
        raise DecompositionError(
            f"requisitos sin descomposición (no evaluables en modo V2): {missing}")


def all_subcriteria_refs() -> list[str]:
    out = []
    for rid, block in load_decomposition()["requirements"].items():
        for sc in block["subcriteria"]:
            out.append(subcriterion_ref(rid, sc["id"]))
    return out
