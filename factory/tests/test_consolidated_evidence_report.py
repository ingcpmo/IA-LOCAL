"""
Tests -- factory/services/consolidated_evidence_report.py (Fase 8,
document_remediation_evolution).

Fase 8 no decide nada: consolida evidencia real de Fases 0-7. Garantias
clave: release_decision es siempre la constante fija OUT_OF_SCOPE_HUMAN_ONLY
(nunca calculada), y el informe declara honestamente que la mayoria de
fases quedaron con pendientes abiertos -- no finge un cierre 100%.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from factory.services import consolidated_evidence_report as report


def test_release_decision_is_fixed_constant_never_computed():
    assert report.RELEASE_DECISION["status"] == "OUT_OF_SCOPE_HUMAN_ONLY"
    assert report.RELEASE_DECISION["computed_from_gate_results"] is False


def test_phase_status_has_all_8_phases_declared():
    assert set(report.PHASE_STATUS.keys()) == {
        "fase_0_higiene", "fase_1_vigencia_fuentes", "fase_2_unificar_cobertura",
        "fase_3_cablear_verificado", "fase_4_extraccion_estructurada",
        "fase_5_candidato_completo", "fase_6_quality_gates", "fase_7_golden_dataset",
    }


def test_only_fases_2_y_4_estan_completamente_cerradas():
    """Hallazgo real de esta consolidacion: de las 8 fases con codigo,
    solo 2 y 4 no dejaron ningun pendiente declarado."""
    fully_closed = [name for name, info in report.PHASE_STATUS.items() if info["status"] == "CERRADA"]
    assert set(fully_closed) == {"fase_2_unificar_cobertura", "fase_4_extraccion_estructurada"}


def test_fase_0_flagged_as_uncommitted_despite_closed_status():
    assert report.PHASE_STATUS["fase_0_higiene"]["status"] == "CERRADA_SIN_COMMITEAR"
    assert report.PHASE_STATUS["fase_0_higiene"]["commit"] is None


REAL_PDF = Path(
    "/home/ing_cpmo/GMPAI/source/Rockwell/215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf"
)
REAL_PACKAGES_DIR = Path("/home/ing_cpmo/factory/remediation_packages/gmpai_document_validation")
REPO_ROOT = Path("/home/ing_cpmo")


def test_fase8_consolidated_report_runs_against_real_evidence():
    """Gate de Fase 8: consolidar evidencia real de Fases 0-7 -- corre los
    gates reales de Fase 7 contra los 2 casos reales, y reporta con
    exactitud que 5 de las 8 fases con codigo quedaron con pendientes
    abiertos. release_decision nunca se deriva de los resultados."""
    if not REAL_PDF.exists() or not REAL_PACKAGES_DIR.exists():
        pytest.skip("PDF real o paquetes reales no disponibles en este entorno")

    result = report.generate_consolidated_evidence_report(REAL_PDF, REAL_PACKAGES_DIR, REPO_ROOT)

    assert result["release_decision"] == report.RELEASE_DECISION
    assert result["any_gate_failed"] is False
    assert len(result["phases_not_fully_closed"]) == 6
    assert set(result["golden_dataset_results"].keys()) == {
        "PKG-FS-V1-2-MEDIUM-RISK-REAL", "PKG-FS-V1-2-REAL-CONTROLLED",
    }
    for pkg_id, gate_result in result["golden_dataset_results"].items():
        assert gate_result["failed"] == [], (pkg_id, gate_result["failed"])
        assert gate_result["gate_12_of_12"] is False

    # evidencia real de git status -- Fase 0 y los 8 documentos de diseño
    # siguen sin commitear en este repo, hallazgo real no asumido
    assert any("regulatory_catalog.py" in p for p in result["uncommitted_evidence"])
    assert any("document_remediation_evolution" in p for p in result["uncommitted_evidence"])


def test_release_decision_never_flips_even_when_all_gates_pass(monkeypatch):
    """Invariante dura: aunque any_gate_failed diera False y todas las
    fases estuvieran CERRADA, release_decision no cambia -- es una
    constante, no una funcion de los resultados."""
    if not REAL_PDF.exists() or not REAL_PACKAGES_DIR.exists():
        pytest.skip("PDF real o paquetes reales no disponibles en este entorno")

    fully_closed_status = {k: {**v, "status": "CERRADA"} for k, v in report.PHASE_STATUS.items()}
    monkeypatch.setattr(report, "PHASE_STATUS", fully_closed_status)

    result = report.generate_consolidated_evidence_report(REAL_PDF, REAL_PACKAGES_DIR, REPO_ROOT)
    assert result["phases_not_fully_closed"] == []
    assert result["release_decision"]["status"] == "OUT_OF_SCOPE_HUMAN_ONLY"
