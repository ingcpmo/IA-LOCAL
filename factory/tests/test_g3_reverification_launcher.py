"""G3 — el lanzador de la reverificacion de fuentes gobernadas.

El checkpoint humano de G3 es *"Cesar lanza la reverificacion con su nombre y
revisa el resultado"*. `check_all_governed_sources()` existia desde la Fase 1 y
no habia por donde lanzarla: ni endpoint, ni boton, ni script. Una accion que un
humano tiene que ejecutar y no tiene superficie es una accion que no ocurre — el
mismo agujero que dejo el panel G7 inalcanzable detras de un boton apagado.

Lo que se prueba aqui NO es la logica de comparacion de fuentes (eso es
`test_source_currency_checker`), sino las guardias del lanzador: que sin nombre
real no corre, que `--dry-run` no toca la red ni escribe, y que un hallazgo
—una fuente cambiada— no se confunde con un fallo de ejecucion.
"""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "factory/scripts/ops/reverify_governed_sources.py"

from factory.scripts.ops import reverify_governed_sources as launcher  # noqa: E402


def _run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, timeout=120)


@pytest.fixture()
def sin_red(monkeypatch):
    """Cualquier peticion real revienta el test en vez de salir a internet."""
    def _prohibido(*a, **k):
        raise AssertionError("el lanzador hizo una peticion de red que no debia")
    monkeypatch.setattr(launcher.checker, "check_all_governed_sources", _prohibido)
    return monkeypatch


# ===========================================================================
# Sin nombre real no se lanza
# ===========================================================================

def test_without_a_name_it_refuses_and_writes_nothing():
    """Una verificacion regulatoria consta con el nombre de quien la lanza.

    No hay valor por defecto que sea honesto: `system` en un log de evidencia no
    identifica a nadie.
    """
    antes = launcher.checker.paths.SOURCE_CURRENCY_LOG_FILE.read_bytes()
    r = _run()
    assert r.returncode == 2, r.stdout + r.stderr
    assert "--run-by" in (r.stdout + r.stderr)
    assert launcher.checker.paths.SOURCE_CURRENCY_LOG_FILE.read_bytes() == antes


@pytest.mark.parametrize("generico", ["system", "admin", "human", "  "])
def test_a_generic_name_is_refused_by_the_same_rule_as_the_rest(generico):
    """Se valida con `validate_run_by`, la misma funcion que el resto de la
    fabrica: una segunda lista de nombres reservados acabaria divergiendo."""
    antes = launcher.checker.paths.SOURCE_CURRENCY_LOG_FILE.read_bytes()
    r = _run("--run-by", generico)
    assert r.returncode == 2, r.stdout + r.stderr
    assert launcher.checker.paths.SOURCE_CURRENCY_LOG_FILE.read_bytes() == antes


def test_a_real_name_passes_the_identity_guard():
    """Y la otra mitad: un nombre real no se rechaza.

    Sin esto, lo aprobaria un lanzador que rechazara siempre — que es lo mismo
    que no tener lanzador.
    """
    from factory.services import test_console_service as console
    assert console.validate_run_by("Cesar Ponce") == "Cesar Ponce"


# ===========================================================================
# --dry-run no toca nada
# ===========================================================================

def test_dry_run_touches_neither_the_network_nor_the_log(sin_red, capsys):
    antes = launcher.checker.paths.SOURCE_CURRENCY_LOG_FILE.read_bytes()
    assert launcher.main(["--dry-run"]) == 0
    salida = capsys.readouterr().out
    assert "no se ha hecho ninguna peticion" in salida
    assert launcher.checker.paths.SOURCE_CURRENCY_LOG_FILE.read_bytes() == antes


def test_dry_run_reports_the_c1_gate_for_every_source(sin_red, capsys):
    """La puerta C-1 se imprime ANTES de tocar la red.

    Una fuente denegada no genera trafico, y su linea en el log dice algo muy
    distinto de un fallo de red. Verlo antes evita leer el resultado al reves.
    """
    launcher.main(["--dry-run"])
    salida = capsys.readouterr().out
    fuentes = launcher._fuentes()
    assert len(fuentes) >= 4
    for f in fuentes:
        assert f["source_id"] in salida
    assert "AUTORIZADA" in salida or "DENEGADA" in salida


def test_the_c1_gate_is_the_resolver_and_not_a_copy():
    """El preflight pregunta al resolver, no reimplementa la regla.

    Una segunda implementacion de "esta autorizada" es exactamente como se llega
    a que el gate diga una cosa y el resolver otra.
    """
    from factory.core import decision_scope_resolver as resolver
    for sid, autorizada in launcher._preflight(launcher._fuentes()):
        assert autorizada == resolver.resolve(launcher.FAMILIA, sid).authorized


# ===========================================================================
# Un hallazgo no es un fallo de ejecucion
# ===========================================================================

def test_a_changed_source_is_a_finding_not_a_crash(monkeypatch, capsys):
    """Salir con != 0 ante una fuente cambiada convertiria el hallazgo en un
    error, y alguien acabaria silenciando el comando en vez de leerlo."""
    monkeypatch.setattr(launcher.checker, "check_all_governed_sources",
                        lambda nombre, fuentes: [
                            {"source_id": "ecfr_21cfr_part11", "reachable": True,
                             "content_matches_governed_copy": False,
                             "authorized_by_decision": True},
                            {"source_id": "eu_gmp_annex11", "reachable": True,
                             "content_matches_governed_copy": True,
                             "authorized_by_decision": True},
                        ])
    assert launcher.main(["--run-by", "Cesar Ponce"]) == 0
    salida = capsys.readouterr().out
    assert "CAMBIADA" in salida and "COINCIDE" in salida
    assert "1 requieren juicio humano" in salida


def test_a_non_comparable_source_is_not_reported_as_changed(monkeypatch, capsys):
    """`comparable: False` (URL sirve un tipo de artefacto distinto al
    archivado) no es lo mismo que un cambio real de contenido -- confundirlos
    fue exactamente la falsa alarma real de la corrida del 2026-07-30 (dos
    fuentes con URL viva sirviendo HTML contra una copia gobernada .txt/.pdf).
    No cuenta como "requiere juicio humano" de contenido: ese juicio es sobre
    apuntar la URL al artefacto correcto, un acto de gobernanza aparte."""
    monkeypatch.setattr(launcher.checker, "check_all_governed_sources",
                        lambda nombre, fuentes: [
                            {"source_id": "ecfr_21cfr_part11", "reachable": True,
                             "content_matches_governed_copy": None,
                             "comparable": False, "note": "no comparable: TEXT vs HTML",
                             "authorized_by_decision": True},
                            {"source_id": "eu_gmp_annex11", "reachable": True,
                             "content_matches_governed_copy": True,
                             "comparable": True, "authorized_by_decision": True},
                        ])
    launcher.main(["--run-by", "Cesar Ponce"])
    salida = capsys.readouterr().out
    assert "NO COMPARABLE" in salida
    assert "CAMBIADA" not in salida
    assert "0 requieren juicio humano" in salida


def test_an_unreachable_source_is_distinguished_from_a_changed_one(monkeypatch,
                                                                   capsys):
    """No alcanzable y cambiada piden acciones distintas: una es un problema de
    red y la otra un cambio regulatorio."""
    monkeypatch.setattr(launcher.checker, "check_all_governed_sources",
                        lambda nombre, fuentes: [
                            {"source_id": "mhra_gxp_di_guidance_2018",
                             "reachable": False, "error": "timeout",
                             "content_matches_governed_copy": False,
                             "authorized_by_decision": True},
                        ])
    launcher.main(["--run-by", "Cesar Ponce"])
    salida = capsys.readouterr().out
    assert "NO ALCANZABLE" in salida
    assert "CAMBIADA" not in salida


def test_a_denied_source_is_not_reported_as_a_network_problem(monkeypatch, capsys):
    """Denegada por falta de cobertura != inalcanzable. Se registra igual —que
    se intento reverificar algo no autorizado es un hecho auditable— pero no se
    cuenta como problema tecnico."""
    monkeypatch.setattr(launcher.checker, "check_all_governed_sources",
                        lambda nombre, fuentes: [
                            {"source_id": "x", "reachable": False,
                             "content_matches_governed_copy": False,
                             "authorized_by_decision": False},
                        ])
    launcher.main(["--run-by", "Cesar Ponce"])
    salida = capsys.readouterr().out
    assert "DENEGADA" in salida
    assert "0 requieren juicio humano" in salida


def test_the_run_says_out_loud_that_it_promotes_nothing(monkeypatch, capsys):
    """U-5 tambien aqui: reverificar NO cambia el estado de ninguna fuente.

    El lifecycle sale de la cobertura de decision. Que el propio comando lo diga
    evita la lectura de que "ya verifique, luego ya vale".
    """
    monkeypatch.setattr(launcher.checker, "check_all_governed_sources",
                        lambda nombre, fuentes: [])
    launcher.main(["--run-by", "Cesar Ponce"])
    salida = capsys.readouterr().out
    assert "NO promueve" in salida
