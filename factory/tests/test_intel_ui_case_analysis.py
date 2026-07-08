"""
W7 Fase C — Garantías estructurales de la UI de análisis de casos.

La UI es JS (sin suite propia): estos tests fijan sobre el fuente los
invariantes del diseño de Fase A §9 y el correctivo de la limitación 2 del
preflight de Fase 0 (nada se descarta en silencio).
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

UI_DIR = Path(__file__).parent.parent / "ui" / "js" / "mission_control"
INTEL = (UI_DIR / "intel_views.js").read_text(encoding="utf-8")
VALIDATION = (UI_DIR / "validation_view.js").read_text(encoding="utf-8")
MAIN = (UI_DIR / "main.js").read_text(encoding="utf-8")


def test_design_panel_replaced_by_real_flow():
    """El panel DISEÑO de W6.4 ya no existe; el flujo real usa los 3 endpoints
    de W7 Fase B."""
    assert "toggleAnalyzeDesign" not in INTEL
    assert "este botón NO ejecuta" not in INTEL
    assert "/analyze" in INTEL
    assert "/analysis" in INTEL
    assert "/decision" in INTEL
    for fn in ("toggleCaseAnalysis", "runCaseAnalysis",
               "loadCaseAnalysis", "decideCaseAnalysis"):
        assert f"function {fn}" in INTEL, fn
        assert fn in MAIN, f"{fn} no expuesto como handler global"
    assert "toggleAnalyzeDesign" not in MAIN


def test_case_analysis_uses_inline_form_not_window_prompt():
    """Correctivo obligatorio de Fase C (hallazgo UX de Fase 0): el flujo de
    análisis usa form INLINE — los diálogos nativos son suprimibles por el
    navegador y descartaban solicitudes en silencio."""
    # el flujo nuevo de análisis no usa window.prompt en ninguna de sus funciones
    analysis_block = INTEL[INTEL.index("toggleCaseAnalysis"):]
    analysis_block = analysis_block[:analysis_block.index("promptCaseCompare")] \
        if "promptCaseCompare" in analysis_block else analysis_block
    assert "window.prompt" not in analysis_block
    assert 'id="case-an-by-' in INTEL          # nombre real inline
    assert 'id="case-an-guidance-' in INTEL    # instrucción inline
    assert 'id="case-an-reason-' in INTEL      # motivo de decisión inline


def test_no_silent_discard_anywhere():
    """Limitación 2 de Fase 0 CERRADA: todo camino que no envía la acción da
    feedback visible (toast) — en intel_views y en validation_view."""
    for src, fname in ((INTEL, "intel_views"), (VALIDATION, "validation_view")):
        for m in re.finditer(r"window\.prompt\([^;]*?\)\s*\|\|\s*''\)\.trim\(\);\s*\n(\s*if\(!\w+\)\{?[^\n]*)", src):
            guard = m.group(1)
            assert "toast(" in guard, (
                f"{fname}: cancelación sin feedback → descarte silencioso: {guard!r}")
    # los caminos de validación del flujo nuevo también avisan
    assert "Solicitud NO enviada" in INTEL
    assert "Decisión NO enviada" in INTEL


def test_governance_panel_complete():
    """Fase A §9 / criterio de éxito 4: gobierno completo en la tarjeta —
    modelo, versiones de prompt, SHAs, corpus, flags, confianza computada,
    routing determinista, y disclaimers default-deny."""
    for needle in ("template_sha256", "rendered_sha256", "set_version",
                   "agent_prompt_version", "corpus_sufficiency", "confianza",
                   "(computada)", "routing determinista", "_claimsBar",
                   "_renderResponse", "regulatory_note", "stale"):
        assert needle in INTEL, needle


def test_long_wait_handled():
    """Riesgo del plan W7: la vista maneja la espera ~7-9 min — cronómetro y
    vía de recuperación si la conexión se corta (la generación sigue en el
    servidor; el GET recupera)."""
    assert "case-an-wait-" in INTEL            # cronómetro visible
    assert "Recargar análisis" in INTEL        # vía de recuperación
    assert "7–9 min" in INTEL                  # expectativa explícita


def test_decision_semantics_labels():
    """accept = solo registro (no toca dossier); reject/ajuste exigen motivo;
    calibración 7B visible para el revisor."""
    assert "Aceptar (solo registro)" in INTEL
    assert "obligatorio para rechazar" in INTEL.lower() or "Motivo (obligatorio" in INTEL
    assert "1 acción por instrucción" in INTEL


def test_validation_view_helpers_shared_not_duplicated():
    """La UI de casos reutiliza los helpers de la vista Validación (claims
    coloreadas, barra de conteos, chips de confianza) — sin copias."""
    assert "from './validation_view.js'" in INTEL
    assert "export function _claimsBar" in VALIDATION
    assert "export function _renderResponse" in VALIDATION
    assert "export const _CONF_CHIP" in VALIDATION
    # intel_views no redefine los helpers importados
    assert "function _claimsBar" not in INTEL
    assert "function _renderResponse" not in INTEL
