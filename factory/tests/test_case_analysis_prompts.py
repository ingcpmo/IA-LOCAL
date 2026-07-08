"""
W7 — Regresión estructural del set de prompts de análisis de casos.

Mismo régimen GxP que test_dossier_agent_prompts.py: SHA-256 declarado vs
recomputado (sin cambios silenciosos de configuración), invariantes de
contenido del diseño de Fase A (aprobado por Cesar) y verificación de que
este set es INDEPENDIENTE del set del dossier (decisión 1 de Fase A).
"""

import hashlib
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.services import paths

EXPECTED_AGENTS = {"qa_oos_profile", "integrity_lims_profile", "hplc_data_review_agent"}


def _load():
    return yaml.safe_load(paths.CASE_ANALYSIS_PROMPTS_FILE.read_text(encoding="utf-8"))


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
    d = _load()
    assert d["common_contract_sha256"] == _sha(d["common_contract"])
    assert d["revision_contract_sha256"] == _sha(d["revision_contract"])
    for agent, p in d["prompts"].items():
        assert p["sha256"] == _sha(p["system_prompt"]), (
            f"El prompt de {agent} cambió sin actualizar sha256/version")


def test_common_contract_invariants():
    c = _load()["common_contract"]
    assert "SIN EVIDENCIA" in c                        # disciplina anti-invención
    assert "[E:" in c and "[SE]" in c and "[REF:" in c   # contrato de formato
    assert "jamás instrucción" in c                    # cláusula anti-injection
    assert "NUNCA apruebes" in c                       # prohibición de decisión GMP
    assert "{corpus_sufficiency}" in c                 # placeholder del gate
    assert "Limitaciones" in c                         # sección obligatoria
    assert "español" in c                              # idioma fijado
    # específicos del análisis de caso (diseño Fase A):
    assert "TERCERO" in c                              # el caso es de otra firma
    assert "COHERENCIA" in c                           # regla 8 (limitación 1 Fase 0)
    assert "NO es una evaluación de impacto GMP" in c  # confusión regulatoria
    assert "### Relevancia para la misión" in c        # estructura fija
    assert "### Impacto potencial en el sistema" in c
    assert "### Acciones recomendadas (condicionadas a revisión QA)" in c


def test_agent_prompts_invariants():
    d = _load()
    for agent, p in d["prompts"].items():
        sp = p["system_prompt"]
        assert "ROL:" in sp and "TAREA:" in sp and "ENFOQUE:" in sp, agent
        assert "`case`" in sp, f"{agent}: la TAREA debe centrar el bloque case"
    assert "OOS" in d["prompts"]["qa_oos_profile"]["system_prompt"]
    assert "ALCOA" in d["prompts"]["integrity_lims_profile"]["system_prompt"]
    assert "USP <621>" in d["prompts"]["hplc_data_review_agent"]["system_prompt"]


def test_revision_contract_identical_to_dossier_set():
    """Decisión de Fase A: el revision_contract es el MISMO texto que el del
    dossier v1.1.0 (garantía W6.5.1 idéntica), duplicado a propósito para que
    cada set sea autocontenido. Si divergen, la divergencia debe ser bump
    consciente en ambos changelogs — este test la hace visible."""
    case_set = _load()
    dossier_set = yaml.safe_load(
        paths.AGENT_PROMPTS_FILE.read_text(encoding="utf-8"))
    assert case_set["revision_contract"] == dossier_set["revision_contract"]


def test_revision_contract_invariants():
    rc = _load()["revision_contract"]
    assert "[RESPUESTA_ANTERIOR INICIO]" in rc and "[RESPUESTA_ANTERIOR FIN]" in rc
    assert "ÚNICAMENTE" in rc and "TEXTUALMENTE" in rc
    assert "TODAS las instrucciones" in rc
    assert "## Limitaciones" in rc


def test_changelog_covers_current_versions():
    d = _load()
    logged = {e["version"] for e in d["changelog"]}
    assert d["prompt_set_version"] in logged


def test_independent_set_does_not_touch_dossier_prompts():
    """El set del dossier sigue en su versión vigente: crear el set de casos
    no produjo bump ni edición del set W6.5."""
    dossier_set = yaml.safe_load(
        paths.AGENT_PROMPTS_FILE.read_text(encoding="utf-8"))
    assert dossier_set["prompt_set_version"] == "1.1.0"
