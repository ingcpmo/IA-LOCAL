"""
W6.5 — Regresión estructural de los prompts expertos gobernados.

Los prompts son CONFIGURACIÓN GxP: cualquier edición sin bump de versión rompe
esta suite (SHA-256 declarado vs recomputado). Además se fijan los invariantes
de contenido que el diseño exige a todo prompt del set.
"""

import hashlib
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.services import paths

EXPECTED_AGENTS = {"qa_oos_profile", "integrity_lims_profile", "hplc_data_review_agent"}


def _load():
    return yaml.safe_load(paths.AGENT_PROMPTS_FILE.read_text(encoding="utf-8"))


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_prompt_file_structure():
    d = _load()
    assert d["prompt_set_version"]
    assert d["changelog"], "changelog obligatorio: todo cambio se registra"
    assert set(d["prompts"].keys()) == EXPECTED_AGENTS
    for agent, p in d["prompts"].items():
        assert p["prompt_version"], agent
        assert p["system_prompt"].strip(), agent


def test_sha256_forces_conscious_version_bump():
    """Editar un prompt sin actualizar su sha256 (y por gobierno, su versión)
    rompe la suite: no hay cambios silenciosos de configuración GxP."""
    d = _load()
    assert d["common_contract_sha256"] == _sha(d["common_contract"])
    for agent, p in d["prompts"].items():
        assert p["sha256"] == _sha(p["system_prompt"]), (
            f"El prompt de {agent} cambió sin actualizar sha256/version")


def test_common_contract_invariants():
    c = _load()["common_contract"]
    assert "SIN EVIDENCIA" in c                       # disciplina anti-invención
    assert "[E:" in c and "[SE]" in c and "[REF:" in c  # contrato de formato
    assert "jamás instrucción" in c                   # cláusula anti-injection
    assert "NUNCA apruebes" in c                      # prohibición de decisión GMP
    assert "{corpus_sufficiency}" in c                # placeholder del gate
    assert "Limitaciones" in c                        # sección obligatoria
    assert "español" in c                             # idioma fijado


def test_agent_prompts_invariants():
    d = _load()
    for agent, p in d["prompts"].items():
        sp = p["system_prompt"]
        assert "ROL:" in sp and "TAREA:" in sp and "ENFOQUE:" in sp, agent
    # anclaje de dominio mínimo por agente (el rol correcto, no intercambiado)
    assert "OOS" in d["prompts"]["qa_oos_profile"]["system_prompt"]
    assert "ALCOA" in d["prompts"]["integrity_lims_profile"]["system_prompt"]
    assert "USP <621>" in d["prompts"]["hplc_data_review_agent"]["system_prompt"]


def test_revision_contract_sha_and_invariants():
    """W6.5.1 Pieza A: el contrato de revisión es configuración GxP gobernada
    con las garantías que el gate exige (edición mínima + ledger vigente)."""
    d = _load()
    assert d["revision_contract_sha256"] == _sha(d["revision_contract"])
    rc = d["revision_contract"]
    assert "[RESPUESTA_ANTERIOR INICIO]" in rc and "[RESPUESTA_ANTERIOR FIN]" in rc
    assert "ÚNICAMENTE" in rc and "TEXTUALMENTE" in rc     # edición mínima
    assert "TODAS las instrucciones" in rc                 # ledger completo vigente
    assert "## Limitaciones" in rc                         # mismo contrato de formato


def test_changelog_covers_current_versions():
    d = _load()
    logged = {e["version"] for e in d["changelog"]}
    assert d["prompt_set_version"] in logged
