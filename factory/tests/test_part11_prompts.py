"""
Tests -- validación de integridad de los prompts GxP gobernados en
factory/engines/gmpai_integrity/prompts/*.yaml.

Este archivo es referenciado por el propio header de part11_prompts.yaml
("El sha256 declarado es recomputado por tests/test_part11_prompts.py —
editar sin bump rompe la suite"), pero no existía en el repo (hallazgo
real de W5 V2 Fase E, 2026-07-23: la documentación afirmaba una
salvaguarda que no se cumplía). Este archivo cierra esa brecha con un
test real, no cosmético: cualquier edición futura de `common_contract` sin
recalcular `common_contract_sha256` debe romper esta suite.
"""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
import yaml

PROMPTS_DIR = Path(__file__).parent.parent / "engines" / "gmpai_integrity" / "prompts"

_PROMPTS_WITH_DECLARED_SHA256 = ["part11_prompts.yaml", "annex11_prompts.yaml", "alcoa_prompts.yaml"]


def _load(filename: str) -> dict:
    return yaml.safe_load((PROMPTS_DIR / filename).read_text(encoding="utf-8"))


@pytest.mark.parametrize("filename", _PROMPTS_WITH_DECLARED_SHA256)
def test_common_contract_sha256_matches_declared_value(filename):
    """Regla dura del propio header del YAML: cualquier cambio de version
    exige bump de version + changelog + recalculo de este hash. Si alguien
    edita common_contract sin recalcular, este test debe fallar."""
    meta = _load(filename)
    declared = meta["common_contract_sha256"]
    computed = hashlib.sha256(meta["common_contract"].encode("utf-8")).hexdigest()
    assert computed == declared, (
        f"{filename}: common_contract_sha256 declarado ({declared}) no coincide con el "
        f"recalculado ({computed}) -- common_contract fue editado sin recalcular el hash "
        f"y sin bump de prompt_version (violacion de la regla de gobernanza GxP del propio header)."
    )


@pytest.mark.parametrize("filename", _PROMPTS_WITH_DECLARED_SHA256 + ["traceability_prompts.yaml"])
def test_prompt_version_is_declared_and_well_formed(filename):
    meta = _load(filename)
    assert "prompt_version" in meta
    parts = meta["prompt_version"].split(".")
    assert len(parts) == 3 and all(p.isdigit() for p in parts), (
        f"{filename}: prompt_version {meta['prompt_version']!r} no es semver simple X.Y.Z"
    )


@pytest.mark.parametrize("filename", _PROMPTS_WITH_DECLARED_SHA256)
def test_changelog_has_at_least_one_entry_matching_current_version(filename):
    meta = _load(filename)
    versions_in_changelog = {c["version"] for c in meta["changelog"]}
    assert meta["prompt_version"] in versions_in_changelog, (
        f"{filename}: prompt_version {meta['prompt_version']!r} no tiene entrada en changelog"
    )
