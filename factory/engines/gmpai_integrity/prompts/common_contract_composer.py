"""FASE M2 (`GMP_AI_FACTORY_ARQUITECTURA_OBJETIVO.md`, "Contrato unico +
chunking por seccion") -- ensamblador de `common_contract` a partir de
`common_contract_base.yaml` (biblioteca de bloques compartidos) +
`deltas/<agente>.yaml` (orden de bloques por agente).

No reescribe texto: reconstruye byte a byte lo que hoy vive duplicado en
cada `*_prompts.yaml`. La prueba de que la reconstruccion es exacta es el
propio sha256 gobernado ya declarado en cada `*_prompts.yaml`
(`common_contract_sha256`) -- `compose_common_contract()` lo verifica en
cada llamada y falla cerrado (nunca sirve un contrato no verificado) si
algun byte difiere. Ver `factory/tests/test_common_contract_composer.py`
para el test de no-regresion contra los 4 agentes reales.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

_PROMPTS_DIR = Path(__file__).parent
_DELTAS_DIR = _PROMPTS_DIR / "deltas"
_BASE_PATH = _PROMPTS_DIR / "common_contract_base.yaml"


class CommonContractCompositionError(RuntimeError):
    """El contrato compuesto no coincide byte a byte con el sha256
    gobernado esperado -- nunca se sirve un contrato no verificado."""


def _load_base() -> dict:
    return yaml.safe_load(_BASE_PATH.read_text(encoding="utf-8"))


def compose_common_contract(agent_id: str, *, base: dict | None = None) -> str:
    """Reconstruye el `common_contract` completo de `agent_id` desde la
    biblioteca compartida + su delta. Verifica el sha256 contra
    `expected_sha256` del delta (el mismo valor gobernado que
    `common_contract_sha256` en el `*_prompts.yaml` original) antes de
    devolver el texto -- fail-closed, nunca aproximado."""
    base = base or _load_base()
    delta_path = _DELTAS_DIR / f"{agent_id}.yaml"
    if not delta_path.exists():
        raise CommonContractCompositionError(f"sin delta de composicion para {agent_id}: {delta_path}")
    delta = yaml.safe_load(delta_path.read_text(encoding="utf-8"))

    intro = base["intros"][delta["intro_key"]]
    rules_header = base["rules_header"]
    rule_blocks = base["rule_blocks"]

    numbered_rules = []
    for i, key in enumerate(delta["rule_layout"], start=1):
        if key not in rule_blocks:
            raise CommonContractCompositionError(f"bloque '{key}' referenciado por {agent_id} no existe en la base")
        body = rule_blocks[key]
        first_line, *rest = body.split("\n")
        lines = [f"{i}. {first_line}", *rest]
        numbered_rules.append("\n".join(lines))

    text = intro + "\n\n" + rules_header + "\n\n" + "\n".join(numbered_rules) + "\n"

    actual_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    expected_sha256 = delta["expected_sha256"]
    if actual_sha256 != expected_sha256:
        raise CommonContractCompositionError(
            f"common_contract compuesto para {agent_id} no coincide con el sha256 "
            f"gobernado: esperado {expected_sha256}, obtenido {actual_sha256}"
        )
    return text


def compose_all() -> dict[str, str]:
    base = _load_base()
    return {
        delta_path.stem: compose_common_contract(delta_path.stem, base=base)
        for delta_path in sorted(_DELTAS_DIR.glob("*.yaml"))
    }
