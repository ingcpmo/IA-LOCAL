"""FASE M2 (`GMP_AI_FACTORY_ARQUITECTURA_OBJETIVO.md`) -- test de
no-regresion textual: los 4 `common_contract` reconstruidos desde
`common_contract_base.yaml` + `deltas/<agente>.yaml` deben producir el
mismo `common_contract_sha256` -- y el mismo texto byte a byte -- que los
`*_prompts.yaml` gobernados que siguen siendo la copia servida hoy en
produccion. No prueba juicio ni recall: prueba que el refactor de
mecanismo de composicion no toco ni un byte de contenido gobernado.
"""
from pathlib import Path

import pytest
import yaml

from factory.engines.gmpai_integrity.prompts.common_contract_composer import (
    CommonContractCompositionError,
    compose_common_contract,
)

_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "engines" / "gmpai_integrity" / "prompts"

_AGENT_YAML = {
    "fda_part11_agent": "part11_prompts.yaml",
    "eu_annex11_agent": "annex11_prompts.yaml",
    "alcoa_plus_agent": "alcoa_prompts.yaml",
    "fda_cgmp_211_agent": "cgmp211_prompts.yaml",
}


@pytest.mark.parametrize("agent_id,filename", sorted(_AGENT_YAML.items()))
def test_composed_contract_matches_governed_yaml_exactly(agent_id, filename):
    original = yaml.safe_load((_PROMPTS_DIR / filename).read_text(encoding="utf-8"))
    composed = compose_common_contract(agent_id)
    assert composed == original["common_contract"]
    assert composed.encode("utf-8")
    import hashlib
    assert hashlib.sha256(composed.encode("utf-8")).hexdigest() == original["common_contract_sha256"]


def test_unknown_agent_raises_instead_of_silently_composing_wrong_text():
    with pytest.raises(CommonContractCompositionError):
        compose_common_contract("no_existe_este_agente")


def test_tampered_delta_fails_closed(tmp_path, monkeypatch):
    """Si un delta referencia un bloque inexistente o el sha256 esperado no
    coincide, el ensamblador debe fallar cerrado -- nunca servir un
    contrato no verificado a evidence_pack_gate/build_prompt."""
    import factory.engines.gmpai_integrity.prompts.common_contract_composer as mod

    bad_delta_dir = tmp_path / "deltas"
    bad_delta_dir.mkdir()
    (bad_delta_dir / "fake_agent.yaml").write_text(
        "agent_id: fake_agent\nintro_key: fda_part11_agent\n"
        "rule_layout:\n  - bloque_que_no_existe\n"
        "expected_sha256: \"" + ("0" * 64) + "\"\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "_DELTAS_DIR", bad_delta_dir)
    with pytest.raises(CommonContractCompositionError):
        mod.compose_common_contract("fake_agent")
