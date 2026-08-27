"""Carga de fixtures de validación V2 (B8) -- FASE 10 §1.

Suite A (Regulatory): el fixture 7P+2N EXISTENTE
(docs_plan/W5V2_RECALL_FIXTURE_SET_DRAFT.md) -- se referencia, no se
redefine aquí.

Suites B (Functional) y C (Technical): fixtures NUEVOS, borrador
(`fixtures_draft/`, `status: DRAFT_UNSIGNED`). `assert_signed()` falla
cerrado -- B8b (corrida real como gate) no puede usarlos sin firma de
Capa 9 como Golden Dataset.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml as _yaml

_DRAFT_DIR = Path(__file__).resolve().parent / "fixtures_draft"

SUITE_B = "functional_suite_b"
SUITE_C = "technical_suite_c"


class FixtureNotSignedError(RuntimeError):
    """El fixture B/C sigue en DRAFT_UNSIGNED -- no es un gate hasta la
    firma de Capa 9 como Golden Dataset."""


@lru_cache(maxsize=4)
def load_fixture(name: str) -> dict:
    path = _DRAFT_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(path)
    data = _yaml.safe_load(path.read_text(encoding="utf-8"))
    _validate_shape(name, data)
    return data


def _validate_shape(name: str, data: dict) -> None:
    if not isinstance(data, dict) or "cases" not in data:
        raise ValueError(f"{name}: sin bloque 'cases'")
    ids = set()
    for i, c in enumerate(data["cases"]):
        for key in ("case_id", "documents", "expected"):
            if key not in c:
                raise ValueError(f"{name} caso {i}: falta '{key}'")
        if c["case_id"] in ids:
            raise ValueError(f"{name}: case_id duplicado {c['case_id']!r}")
        ids.add(c["case_id"])
        exp = c["expected"]
        if "finding" not in exp:  # bool
            raise ValueError(f"{name}/{c['case_id']}: expected sin 'finding'")
        if exp["finding"] and not exp.get("subtype"):
            raise ValueError(f"{name}/{c['case_id']}: expected.finding=true sin 'subtype'")


def is_signed(name: str) -> bool:
    return str(load_fixture(name).get("status", "")).upper() not in ("DRAFT_UNSIGNED", "")


def assert_signed(name: str) -> None:
    if not is_signed(name):
        raise FixtureNotSignedError(
            f"{name} en DRAFT_UNSIGNED -- requiere firma de Capa 9 como Golden Dataset "
            f"(docs_plan/PROPUESTA_FIXTURES_FUNCIONAL_TECNICO_B8.md).")


def case_count(name: str) -> int:
    return len(load_fixture(name)["cases"])


def distribution(name: str) -> dict:
    out: dict = {}
    for c in load_fixture(name)["cases"]:
        exp = c["expected"]
        key = exp.get("subtype") if exp["finding"] else "NO_FINDING"
        out[key] = out.get(key, 0) + 1
    return out
