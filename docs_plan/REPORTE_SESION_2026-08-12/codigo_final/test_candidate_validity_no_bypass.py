"""R3-T1.7 (docs_plan/R3_T1_7_SUPERFICIE_UNICA_CANDIDATO.md, bloque 2.3):
guardian de NO-BYPASS -- la decision de "¿este candidato ancla / aporta
evidencia valida?" vive en UNA sola superficie
(factory/regulatory/candidate_validity.py). Antes de R3-T1.7 esta decision
estaba fragmentada en al menos 2 rutas independientes dentro de
chunked_engine.py, cada una con su propia logica de anclaje y su propio
bug (B3/B4/B5 fueron el MISMO defecto reapareciendo en sitios distintos).
Este test falla si algun modulo reimplementa esa logica en vez de llamar
a `resolve_candidate_evidence()` -- mismo espiritu que
test_refresh_readonly.py (invariante estructural, no de negocio)."""
from __future__ import annotations

import ast
from pathlib import Path

FACTORY_ROOT = Path(__file__).parent.parent
CANDIDATE_VALIDITY_PATH = FACTORY_ROOT / "regulatory" / "candidate_validity.py"

# Marcador literal del headline derivado por rescate B4/B5 -- si aparece
# hardcodeado en OTRO archivo de produccion, alguien reimplemento el
# rescate en vez de llamar a resolve_candidate_evidence().
_DERIVED_HEADLINE_MARKER = "headline derivado de citas por criterio verificadas"

# Archivos de produccion (excluye tests, docs_plan, scripts de replay
# fuera de factory/) que podrian, en teoria, decidir anclaje de candidato.
_PRODUCTION_PY_FILES = [
    p for p in FACTORY_ROOT.rglob("*.py")
    if "/tests/" not in str(p) and "__pycache__" not in str(p)
]


def test_candidate_validity_module_exists_and_exports_the_single_surface():
    assert CANDIDATE_VALIDITY_PATH.exists(), (
        "factory/regulatory/candidate_validity.py no existe -- la superficie "
        "unica de R3-T1.7 fue movida o eliminada")
    source = CANDIDATE_VALIDITY_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    top_level_funcs = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert "resolve_candidate_evidence" in top_level_funcs
    assert "is_literally_anchored" in top_level_funcs


def test_derived_headline_marker_lives_only_in_the_single_surface():
    """Si el marcador del headline derivado aparece en CUALQUIER otro
    archivo de produccion, ese archivo reimplemento el rescate B4/B5 en
    vez de llamar a resolve_candidate_evidence() -- exactamente el patron
    que causo que el mismo defecto reapareciera 3 veces (B3, B4, B5)."""
    offenders = []
    for path in _PRODUCTION_PY_FILES:
        if path == CANDIDATE_VALIDITY_PATH:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if _DERIVED_HEADLINE_MARKER in text:
            offenders.append(str(path.relative_to(FACTORY_ROOT.parent)))
    assert offenders == [], (
        f"El marcador de headline derivado aparece fuera de candidate_validity.py "
        f"en: {offenders} -- reimplementacion del rescate B4/B5 detectada, "
        f"debe llamar a resolve_candidate_evidence() en su lugar")


def test_chunked_engine_calls_the_single_surface_not_its_own_logic():
    """evaluate_chunked() debe importar y llamar a
    resolve_candidate_evidence() -- no debe redefinir su propia funcion
    de anclaje/rescate a nivel de modulo (ver _is_anchored, que ahora es
    solo un alias/reexport, verificado por separado)."""
    chunked_engine_path = FACTORY_ROOT / "engines" / "gmpai_integrity" / "chunked_engine.py"
    source = chunked_engine_path.read_text(encoding="utf-8")
    assert "from factory.regulatory.candidate_validity import resolve_candidate_evidence" in source, (
        "chunked_engine.py ya no importa resolve_candidate_evidence() -- "
        "¿alguien reimplemento la decision de anclaje inline?")
    assert source.count("resolve_candidate_evidence(") >= 2, (
        "resolve_candidate_evidence() debe llamarse desde evaluate_chunked() -- "
        "si aparece menos de 2 veces (import + al menos 1 llamada), la "
        "superficie unica dejo de estar conectada")


def test_is_anchored_is_a_thin_reexport_not_a_reimplementation():
    """chunked_engine._is_anchored() debe ser un alias de
    candidate_validity.is_literally_anchored() -- nunca una segunda
    implementacion del mismo chequeo (eso fue exactamente el defecto que
    R3-T1.7 vino a cerrar)."""
    from factory.engines.gmpai_integrity import chunked_engine as ce
    source = ce.__file__ and Path(ce.__file__).read_text(encoding="utf-8")
    # La funcion debe delegar explicitamente -- nunca reimplementar
    # normalize+substring por su cuenta.
    start = source.index("def _is_anchored(")
    end = source.index("\n\n\n", start)
    body = source[start:end]
    assert "is_literally_anchored" in body, (
        "_is_anchored() ya no delega en candidate_validity.is_literally_anchored() -- "
        "reimplementacion detectada")
    assert "_normalize(" not in body, (
        "_is_anchored() volvio a implementar su propia normalizacion -- "
        "debe delegar en la superficie unica, no duplicarla")
