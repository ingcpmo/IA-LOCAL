"""Gate 0 ampliado — W5 V2 G1.17, último de G1.

Un Gate 0 cuya rama de FAIL nadie ha ejecutado nunca es un gate que nadie ha
verificado. Estos tests invocan los veredictos del propio `factory_selfcheck.sh`
con valores inyectados y comprueban que la corrupción de contenido, un fork
nuevo y una inconsistencia de versión lo ponen en rojo DE VERDAD.

Se cargan las funciones con `SELFCHECK_LIB_ONLY=1`, que hace que el script
retorne antes de correr la suite entera -- sin eso, probar el gate implicaría
correr el gate, y el test tardaría seis minutos por caso.
"""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

REPO = Path(__file__).resolve().parents[2]
SELFCHECK = REPO / "factory" / "scripts" / "ops" / "factory_selfcheck.sh"


def _run_verdict(llamada: str, *, env_extra: dict | None = None) -> dict:
    """Carga solo las funciones del selfcheck y ejecuta un veredicto."""
    script = (
        f'set -euo pipefail\n'
        f'export SELFCHECK_LIB_ONLY=1\n'
        f'source "{SELFCHECK}"\n'
        f'{llamada}\n'
        f'echo "RESULT PASS=$PASS WARN=$WARNS FAIL=$FAIL"\n'
    )
    env = {"PATH": "/usr/bin:/bin", "SELFCHECK_LIB_ONLY": "1"}
    env.update(env_extra or {})
    proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                          timeout=60, env=env)
    assert proc.returncode == 0, f"el veredicto no corrió:\n{proc.stderr}"
    linea = [l for l in proc.stdout.splitlines() if l.startswith("RESULT ")][-1]
    partes = dict(p.split("=") for p in linea.removeprefix("RESULT ").split())
    return {"pass": int(partes["PASS"]), "warn": int(partes["WARN"]),
            "fail": int(partes["FAIL"]), "salida": proc.stdout}


# ===========================================================================
# El script carga y las funciones existen
# ===========================================================================

def test_the_selfcheck_is_syntactically_valid():
    proc = subprocess.run(["bash", "-n", str(SELFCHECK)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_lib_only_mode_does_not_run_the_whole_suite():
    """Si esto dejara de funcionar, cada test de abajo tardaría seis minutos."""
    r = _run_verdict('true')
    assert "pytest" not in r["salida"]
    assert "py_compile" not in r["salida"]


def test_the_selfcheck_declares_six_steps():
    texto = SELFCHECK.read_text(encoding="utf-8")
    for n in range(1, 7):
        assert f'section "{n}/6' in texto, f"falta el paso {n}/6"
    assert '/5 ' not in texto, "quedó una numeración vieja de 5 pasos"


# ===========================================================================
# Paso 3 — dimensiones de la cadena
# ===========================================================================

def test_content_corruption_is_a_fail():
    """`hash_errors > 0` es corrupción de CONTENIDO y no es exceptuable."""
    r = _run_verdict('_verdict_audit_chain 3 0 False VERIFIED 100')
    assert r["fail"] == 1
    assert "NO exceptuable" in r["salida"]


def test_corruption_wins_over_an_accepted_exception():
    """Ni con una excepción vigente: una firma no convierte un hash malo en
    otra cosa."""
    r = _run_verdict('_verdict_audit_chain 1 0 True ACCEPTED_WITH_DOCUMENTED_EXCEPTION 100')
    assert r["fail"] == 1
    assert r["pass"] == 0


def test_a_new_fork_is_a_fail():
    """Un fork nuevo para todo y se investiga. El baseline no lo cubre."""
    r = _run_verdict('_verdict_audit_chain 0 1 True BROKEN_NEW 100')
    assert r["fail"] == 1
    assert "NUEVO" in r["salida"]


def test_the_historical_fork_was_a_warn_before_g7():
    """Antes de G7 la excepción no puede existir, y dejar Gate 0 en rojo
    permanente hasta entonces garantiza que se deje de leer.

    Se fuerza `FORK_HISTORICO_ES_FAIL=0` porque desde el cierre de G7
    (2026-07-30, AUDIT_EXCEPTION-2026-002) el valor por defecto es 1. La rama
    sigue existiendo y se sigue probando: describe la fase anterior, y borrarla
    dejaria sin cubrir el unico camino por el que este gate fue WARN durante
    semanas.
    """
    r = _run_verdict('FORK_HISTORICO_ES_FAIL=0; '
                     '_verdict_audit_chain 0 0 True BROKEN_HISTORICAL 21884')
    assert r["fail"] == 0
    assert r["warn"] == 1
    assert r["pass"] == 1
    assert "G7" in r["salida"]


def test_a_fork_left_without_its_exception_is_a_fail_now():
    """Y desde G7, esa MISMA situacion para la fabrica.

    Es lo que enciende el cambio de fase: si la excepcion desaparece —revocada,
    superseded, o un almacen que deje de resolverla— el fork se queda sin
    respaldo y el gate para la fabrica en vez de avisar.
    """
    r = _run_verdict('_verdict_audit_chain 0 0 True BROKEN_HISTORICAL 21884')
    assert r["fail"] == 1, r["salida"]
    assert "sin excepción firmada" in r["salida"]


def test_the_historical_fork_becomes_a_fail_from_g7():
    """El cambio de fase es UNA variable, no una reescritura del bloque.

    Este test es el que garantiza que la promesa "desde G7 esto bloquea" no sea
    un comentario: se activa la variable y el gate se pone rojo.
    """
    r = _run_verdict('_verdict_audit_chain 0 0 True BROKEN_HISTORICAL 21884',
                     env_extra={"FORK_HISTORICO_ES_FAIL": "1"})
    assert r["fail"] == 1
    assert "exigible desde G7" in r["salida"]


def test_an_accepted_exception_is_never_reported_as_no_errors():
    r = _run_verdict('_verdict_audit_chain 0 0 True ACCEPTED_WITH_DOCUMENTED_EXCEPTION 100')
    assert r["fail"] == 0
    assert r["warn"] == 1
    assert "nunca 'sin errores'" in r["salida"]


def test_a_clean_chain_passes_without_warnings():
    """El gate no es un "siempre no": una cadena íntegra pasa limpia."""
    r = _run_verdict('_verdict_audit_chain 0 0 False VERIFIED 100')
    assert (r["pass"], r["warn"], r["fail"]) == (1, 0, 0)


# ===========================================================================
# Paso 6 — versiones de artefactos
# ===========================================================================

def test_a_version_inconsistency_is_a_fail():
    r = _run_verdict('_verdict_artifact_versions FAIL 2 0')
    assert r["fail"] == 1
    assert "trazabilidad" in r["salida"]


def test_missing_version_records_are_a_warn_not_a_fail():
    """Un FAIL aquí pondría Gate 0 en rojo por una tarea pendiente, no por un
    defecto."""
    r = _run_verdict('_verdict_artifact_versions WARN 0 28 NO_VERSION_RECORD')
    assert r["fail"] == 0
    assert r["warn"] == 1
    assert r["pass"] == 1
    assert "bootstrap pendiente" in r["salida"]


def test_the_warn_message_names_its_real_cause():
    """Hay DOS motivos de WARN y el mensaje tiene que decir el correcto.

    Tras correr el bootstrap de G4 el gate seguía diciendo "sin version_record —
    bootstrap pendiente" sobre 28 artefactos que ya estaban fotografiados: un
    aviso cierto en el número y falso en la causa, que es peor que no avisar
    porque manda a corregir lo que ya está hecho.
    """
    r = _run_verdict('_verdict_artifact_versions WARN 0 28 NO_APPROVING_DECISION')
    assert r["warn"] == 1
    assert "SIN decision que lo apruebe" in r["salida"]
    assert "bootstrap pendiente" not in r["salida"]


def test_an_unknown_warn_code_does_not_invent_a_cause():
    """Si aparece un motivo nuevo, se dice que hay avisos y no se atribuye a
    ninguna causa concreta. Inventarla sería el mismo defecto al revés."""
    r = _run_verdict('_verdict_artifact_versions WARN 0 3 CODIGO_NUEVO')
    assert r["warn"] == 1
    assert "con avisos de versionado" in r["salida"]
    assert "bootstrap pendiente" not in r["salida"]


def test_an_unevaluable_guard_is_a_fail_not_a_pass():
    """"No sé" nunca se reporta como "sí"."""
    r = _run_verdict('_verdict_artifact_versions "" 0 0')
    assert r["fail"] == 1


def test_all_consistent_is_a_clean_pass():
    r = _run_verdict('_verdict_artifact_versions PASS 0 0')
    assert (r["pass"], r["warn"], r["fail"]) == (1, 0, 0)


# ===========================================================================
# Los pasos nuevos usan el intérprete correcto
# ===========================================================================

def test_the_new_steps_use_the_venv_interpreter():
    """El paso 3 usaba `python3` del sistema, que no tiene jsonschema.

    Desde G1.14 las dimensiones consultan el resolver; con el intérprete del
    sistema el módulo degrada a "sin excepción demostrable" y el `2>/dev/null`
    del script haría que el fallo se viera como "cadena INVÁLIDA", no como un
    error de import. Los dos pasos nuevos usan $PYBIN.
    """
    texto = SELFCHECK.read_text(encoding="utf-8")
    bloque3 = texto.split('section "3/6')[1].split('section "4/6')[0]
    assert '"$PYBIN" -' in bloque3, "el paso 3 no usa $PYBIN"

    bloque6 = texto.split('section "6/6')[1]
    assert '"$PYBIN" -' in bloque6, "el paso 6 no usa $PYBIN"


def test_the_summary_reports_warnings_instead_of_hiding_them():
    """Un Gate 0 que anuncia PASS=6 FAIL=0 ocultando 29 avisos colapsa las
    dimensiones igual que el `part11_compliant` booleano de G1.14."""
    texto = SELFCHECK.read_text(encoding="utf-8")
    assert "WARNS=$((WARNS+1))" in texto, "warn_ no cuenta"
    assert 'WARN=%d' in texto, "el resumen no muestra los WARN"


def test_warnings_do_not_block_the_gate():
    """Un WARN informa; solo FAIL bloquea. El exit code depende de FAIL."""
    texto = SELFCHECK.read_text(encoding="utf-8")
    assert "if [[ $FAIL -eq 0 ]]; then" in texto
    assert "$WARNS -eq 0" not in texto, "un WARN no puede bloquear el gate"


# ===========================================================================
# Estado real de hoy, extremo a extremo
# ===========================================================================

def test_the_real_artifact_guard_reports_the_g6_matrix_regularization_closed():
    """G4a (2026-07-30): se redacto el pack de 21_CFR_211.68(b) -- el
    catalogo cambio de contenido (hash) y `catalog_version` se dejo en 1.0 a
    proposito (ver docstring de artifact_version_guard.py: bumpearlo ahora,
    antes de que Cesar revise/termine el contenido, arriesgaria versionar dos
    veces si el borrador cambia en la revision). Eso fue exactamente
    CONTENT_CHANGED_VERSION_SAME -- 1 FAIL real y esperado, no una
    regresion, hasta que G4c lo cerrara.

    2026-07-31: Cesar firmo D2-2026-009 (CORRECTION, aprobacion real del
    pack) -- se registro un version_record nuevo con
    approved_by_decision='D2-2026-009', asi que ese artefacto en particular
    ya no figuraba en warn_count (27, no 28). El FAIL del catalogo no
    cambiaba todavia.

    G4c (2026-08-01): Cesar firmo ARTIFACT_VERSION-2026-002 por el Panel G, y
    `apply_catalog_version_bump()` aplico el bump real (`catalog_version`
    1.0 -> 2.0), congelando la copia historica desde HEAD. El FAIL
    desaparece (fail_count 0) y el catalogo tampoco figura ya en warn_count
    (26, no 27) -- queda totalmente resuelto, ni FAIL ni WARN.

    G4c otra vez + G6 (2026-08-05, panel ARQ desbloqueo de firma):
    ARTIFACT_VERSION-2026-007 aplico el segundo bump real del catalogo
    (2.0 -> 2.1, mismo artefacto ya resuelto -- warn_count no cambia por
    esto). ARTIFACT_VERSION-2026-009 aplico la primera aprobacion del
    golden dataset (`apply_artifact_first_approval()`) -- ese artefacto SI
    sale de warn_count (25, no 26).

    G5/D2-A (2026-08-05, mismo dia): la matriz de aplicabilidad cambio de
    contenido (document_types +4 codigos) y matrix_version paso de 2.1 a
    2.2 -- el MISMO patron que el catalogo antes de G4c. FAIL vuelve a
    aparecer (1, no 0): VERSION_CHANGED_WITHOUT_DECISION para
    applicability_matrix, honesto y esperado hasta que Cesar firme
    APPLICABILITY_MATRIX-2026-005.

    G6-MVR (2026-08-07, plan W5V2_ARQ_RETOMAR_Y_FINALIZAR.md Bloque 2.2):
    Cesar firmo ARTIFACT_VERSION-2026-011, regularizando la transicion
    2.1->2.2 (el cambio YA estaba en disco, sin decision ARTIFACT_VERSION
    que lo cubriera) enlazando APPLICABILITY_MATRIX-2026-006 (aprobacion de
    contenido ya firmada) como fundamento humano.
    `apply_regularization_for_applied_change()` escribio el version_record.
    El FAIL desaparece de nuevo (fail_count 0) y la matriz sale de
    warn_count (24, no 25)."""
    from factory.core import artifact_version_guard as guard
    r = guard.guard_report()
    assert r["status"] == "WARN"
    assert r["fail_count"] == 0
    assert r["warn_count"] == 24
    fails = [f for f in r["findings"] if f["severity"] == "FAIL"]
    assert len(fails) == 0
    assert not any(f["artifact"] == "applicability_matrix" for f in r["findings"])
    assert not any(f["artifact_id"].endswith("requirements.yaml") for f in r["findings"])
    assert not any(f["artifact_id"].endswith("semantic_verification_golden_dataset.py")
                  for f in r["findings"])


def test_the_real_chain_dimensions_land_on_warn_not_fail(real_audit_chain):
    """Y el paso 3 sobre la cadena REAL: nada corrupto, ningun fork nuevo.

    Fijaba `part11_compliant == NOT_DETERMINED`, que era el valor hasta que Cesar
    firmo la excepcion. Lo que sostiene el "no hay FAIL" no es ese valor concreto
    sino las dos dimensiones que si mandan en el veredicto: hash_errors y
    new_forks_since_baseline. El fork historico sigue presente, aceptado no es
    corregido.
    """
    from factory.core import audit_writer as aw
    r = aw.verify_chain()
    assert r["hash_errors"] == 0
    assert r["new_forks_since_baseline"] == 0
    assert r["historical_fork_present"] is True
    assert r["part11_compliant"] != aw.PART11_COMPLIANT
    # Y si esta aceptada, el gate exige que la excepcion se resuelva de verdad.
    if r["part11_compliant"] == aw.PART11_ACCEPTED_WITH_EXCEPTION:
        assert r["unbacked_known_fork_entry_ids"] == []
