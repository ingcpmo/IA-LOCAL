"""Loader del artefacto GOBERNADO `technical_completeness_rules.yaml` (B6b v2).

Fail-closed: si el artefacto no esta `status: SIGNED`, `load_signed_rules()`
lanza. El detector determinista de completitud tecnica
(`technical_findings.completeness_findings`) NO corre sin firma.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml as _yaml

_PATH = Path(__file__).parent / "technical_completeness_rules.yaml"

_REQUIRED_RULE_KEYS = (
    "CASE_ID", "CONTROL_OBJECTIVE", "SOURCE_REQUIREMENT_ID", "REQUIRED_BEHAVIOR",
    "ACCEPTABLE_EVIDENCE_PATTERNS", "EXCLUDED_IMPLEMENTATION_ASSUMPTIONS",
    "DETERMINISTIC_DETECTION_RULE", "HUMAN_REVIEW_STATE",
)


class TechnicalRulesError(RuntimeError):
    """El artefacto no existe, no parsea, o no tiene la forma esperada."""


class TechnicalRulesNotSignedError(TechnicalRulesError):
    """El artefacto sigue sin `status: SIGNED` -- B6b v2 no corre (fail-closed)."""


def _validate_raw(data: dict, where: str) -> dict:
    if not isinstance(data, dict):
        raise TechnicalRulesError(f"{where}: el artefacto no es un mapping YAML")
    for k in ("artifact", "version", "status", "rules", "family_signals",
              "cross_reference_suppressors", "inconclusive_downgraders"):
        if k not in data:
            raise TechnicalRulesError(f"{where}: falta la clave de nivel superior '{k}'")
    for i, r in enumerate(data["rules"]):
        for key in _REQUIRED_RULE_KEYS:
            if key not in r:
                raise TechnicalRulesError(f"regla #{i} ({r.get('CASE_ID','?')}): falta '{key}'")
        ddr = r["DETERMINISTIC_DETECTION_RULE"]
        for key in ("topic_anchor", "scope", "emit_when", "finding"):
            if key not in ddr:
                raise TechnicalRulesError(f"{r['CASE_ID']}: DETERMINISTIC_DETECTION_RULE sin '{key}'")
        for key in ("finding_class", "subtype", "severity"):
            if key not in ddr["finding"]:
                raise TechnicalRulesError(f"{r['CASE_ID']}: finding sin '{key}'")
        hrs = r["HUMAN_REVIEW_STATE"]
        if hrs.get("human_state") != "UNREVIEWED":
            raise TechnicalRulesError(f"{r['CASE_ID']}: human_state debe nacer UNREVIEWED")
        if hrs.get("machine_state") not in ("MACHINE_DEVIATION_CANDIDATE", "MACHINE_INCONCLUSIVE"):
            raise TechnicalRulesError(f"{r['CASE_ID']}: machine_state no permitido: {hrs.get('machine_state')}")
    return data


@lru_cache(maxsize=1)
def _load_raw() -> dict:
    if not _PATH.exists():
        raise TechnicalRulesError(f"no encontrado: {_PATH}")
    return _validate_raw(_yaml.safe_load(_PATH.read_text(encoding="utf-8")), _PATH.name)


def _shape(d: dict) -> dict:
    """Normaliza un artefacto validado a la estructura que consume el detector.
    `scope_policy` ausente -> None -> comportamiento v1.0 (document_wide)."""
    return {
        "version": d["version"],
        "rules": d["rules"],
        "family_signals": d["family_signals"],
        "cross_reference_suppressors": [s.lower() for s in d["cross_reference_suppressors"]],
        "inconclusive_downgraders": [s.lower() for s in d["inconclusive_downgraders"]],
        "scope_policy": d.get("scope_policy"),
    }


def is_signed() -> bool:
    return str(_load_raw().get("status", "")).upper() == "SIGNED"


def assert_signed() -> None:
    if not is_signed():
        raise TechnicalRulesNotSignedError(
            "technical_completeness_rules.yaml sin 'status: SIGNED' -- B6b v2 no corre. "
            "Requiere firma de Capa 9.")


def load_signed_rules() -> dict:
    """Devuelve el artefacto VIVO (technical_completeness_rules.yaml) SOLO si
    esta firmado (fail-closed). Incluye `scope_policy` (None en v1.0)."""
    assert_signed()
    return _shape(_load_raw())


def load_rules_from(path, *, require_signed: bool = True) -> dict:
    """Carga un artefacto de reglas desde un path arbitrario (p.ej. el
    borrador v1.1). `require_signed=True` mantiene fail-closed; los tests que
    verifican el nuevo alcance lo pasan a False EXPLICITAMENTE sobre el
    borrador -- nunca en produccion."""
    path = Path(path)
    if not path.exists():
        raise TechnicalRulesError(f"no encontrado: {path}")
    d = _validate_raw(_yaml.safe_load(path.read_text(encoding="utf-8")), path.name)
    if require_signed and str(d.get("status", "")).upper() != "SIGNED":
        raise TechnicalRulesNotSignedError(f"{path.name} sin 'status: SIGNED'")
    return _shape(d)


def rule_case_ids() -> list[str]:
    return [r["CASE_ID"] for r in _load_raw()["rules"]]
