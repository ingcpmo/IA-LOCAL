"""
R1.6 (docs_plan/R1_6_VALIDADOR_RELEVANCIA_IDIOMA.md, 2026-08-09) -- defecto
de mismatch de idioma en chunked_engine._is_topically_relevant() y su
correccion acotada.

Regimen de no-regresion exigido por R1.6 seccion 4.1: fija, con datos ya
persistidos (cero llamadas nuevas al modelo), el comportamiento ANTES y
DESPUES del fix sobre el fixture set real (N1=ANNEX11_4, la cita real de
P5) mas los casos construidos label/doc por combinacion de idioma.

Alcance de la correccion (ver docstring de _is_topically_relevant en
chunked_engine.py): solo deja de descartar la mitad en ingles de un label
bilingue "Termino ingles — glosa espanol" (familia ALCOA). NO agrega
ninguna fuente de comparacion nueva (requirement_terms.yaml se evaluo
como fuente alternativa y se descarto -- rompe
test_topically_irrelevant_citation_is_rejected, ver seccion 3 de R1_6).
Por eso el caso P5 real (evidencia parafraseada sin ninguna palabra
gobernada literal) sigue sin pasar el gate incluso despues del fix --
verificado explicitamente aqui, no asumido.
"""
from factory.engines.gmpai_integrity import chunked_engine as ce

# Evidencia real, persistida, run_id=chunked-596f70cc4520 (R1.5 Bloque 3):
# factory/regulatory/pilot_run/r1_5_h2h4_chunked-596f70cc4520/raw_response/
# task-3d9d395fa99e.txt.gz -- score de anclaje 1.0 (evidence_verifier.
# match_citation), no reproducido aqui, solo el texto exacto.
_P5_REAL_EVIDENCIA = (
    "FactoryTalk View SE provides an electronic signature feature for "
    "capturing operator actions performed in the production system. This "
    "feature is available in an E-Signature control, as well as the "
    "native button, numeric, and string input objects."
)
_P5_LABEL = "Contemporaneous — registrado en el momento"  # alcoa_prompts.yaml


def test_bilingual_label_english_half_no_longer_discarded():
    """El bug real: el split anterior se quedaba solo con la glosa en
    espanol ('registrado en el momento') y tiraba 'Contemporaneous'. Ahora
    una cita que SI repite el termino ingles del propio label (contenido
    ya gobernado, no una fuente nueva) debe aceptarse."""
    evidencia = "The system records data in a contemporaneous manner during each operation."
    assert ce._is_topically_relevant(evidencia, _P5_LABEL) is True


def test_p5_real_evidence_still_not_relevant_after_fix():
    """Limitacion residual documentada, no maquillada: la evidencia REAL
    de P5 (persistida, anclaje score 1.0) no repite NINGUNA palabra
    gobernada -- ni 'Contemporaneous' (ingles, ahora disponible tras el
    fix) ni 'registrado'/'momento' (espanol). El gate sigue rechazandola
    porque el defecto de fondo (coincidencia lexica literal, demasiado
    estricta para un cumple_parcialmente parafraseado) no se toco en este
    alcance -- requiere decision separada de Cesar (R1_6 seccion 3)."""
    assert ce._is_topically_relevant(_P5_REAL_EVIDENCIA, _P5_LABEL) is False


def test_annex11_4_pure_spanish_label_still_rejects_english_reference_list():
    """N1 del fixture set (GAMP5 en lista de referencias numeradas). Label
    puramente en espanol (sin guion largo, sin mitad en ingles que
    rescatar) -- el fix no cambia nada aqui, sigue rechazado."""
    label = "Gestion de riesgo del sistema computarizado"  # annex11_prompts.yaml, ANNEX11_4
    evidencia = "[8] Good Automated Manufacturing Practice, Guide for Validation (GAMP5)"
    assert ce._is_topically_relevant(evidencia, label) is False


def test_wrong_topic_same_language_citation_still_rejected_no_regression():
    """Reproduce exactamente el escenario de
    test_topically_irrelevant_citation_is_rejected (test_gmpai_chunked_engine.py):
    cita real, anclada, sobre audit trail, propuesta como evidencia de
    'Limitar acceso a individuos autorizados'. Mismo idioma en label y
    documento -- el fix NO debe empezar a aceptar esto (era la razon para
    descartar requirement_terms.yaml como fuente alternativa, ver
    docstring del gate)."""
    label = "Limitar acceso a individuos autorizados"  # part11_prompts.yaml, 21_CFR_11.10(d)
    evidencia = "Logins, logouts, and login attempts must be recorded in the Audit Trail"
    assert ce._is_topically_relevant(evidencia, label) is False


def test_label_english_doc_english_unaffected():
    label = "Audit trail"  # annex11_prompts.yaml, ANNEX11_9 -- pure English, no dash
    evidencia = "The system maintains a secure audit trail of all changes."
    assert ce._is_topically_relevant(evidencia, label) is True


def test_label_spanish_doc_spanish_unaffected():
    label = "Archivo y retencion de registros"  # annex11_prompts.yaml, ANNEX11_17
    evidencia = "Los registros se archivan y se retienen segun la politica de retencion vigente."
    assert ce._is_topically_relevant(evidencia, label) is True


def test_bilingual_label_neither_half_present_still_rejected():
    """Caso construido de control: si la cita no repite ni el termino
    ingles ni la glosa espanola del label bilingue, sigue rechazada (no es
    que el fix vuelva permisivo el gate en general)."""
    label = "Attributable — quien genero el dato"  # alcoa_prompts.yaml, ALCOA_ATTRIBUTABLE
    evidencia = "The device performs a daily self-calibration routine at startup."
    assert ce._is_topically_relevant(evidencia, label) is False
