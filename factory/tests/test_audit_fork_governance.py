"""Gobernanza del fork de auditoria — F-01..F-12 de AUDIT_FORK_REMEDIATION_SPEC §9.

Lo que se cierra aqui es una frase que el sistema decia de si mismo:

    {"verified": false, ..., "part11_compliant": true}

Se declaraba conforme a Part 11 sobre una cadena que el mismo reportaba como
no verificada. La regla anterior era CORRECTA en su analisis tecnico -- un
fork sin errores de hash deja el contenido autentico -- y EQUIVOCADA en su
conclusion: la continuidad verificable de la secuencia es otra condicion, y
esta rota.

F-11 es el test que mas sostiene: reproduce la causa raiz establecida en §3
(cache de cabeza en memoria, no invalidada) y demuestra que `8c033fa` la
cierra. Sin el, "corregido por 8c033fa" se apoya solo en la ausencia de forks
posteriores, que es correlacion, no mecanismo.

F-13 (write_event falla ruidosamente si no logra el lock) NO esta aqui: es
una de las medidas preventivas marcadas PENDIENTE/G7 en el paquete de
excepcion (§7), junto con writer_pid/writer_host. Adelantarla seria implementar
G7 dentro de G1.14.
"""
import json
import multiprocessing
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.core import audit_writer as aw
from factory.services import decision_store_v2 as store

REAL_FORK_ENTRY_ID = "ab689c7c-3e0a-4c77-936b-152851f51a30"
REPO = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Utilidades: cadenas sinteticas
# ---------------------------------------------------------------------------

def _entries(n: int, prefix: str = "evt") -> list[dict]:
    return [
        {"timestamp": f"2026-06-15T13:5{i % 10}:00+00:00", "entry_id": f"{prefix}-{i}",
         "event_type": "gates_executed", "project_id": "p", "data": {}}
        for i in range(n)
    ]


def _chain(entries: list[dict], path: Path, *, break_at: int | None = None,
           corrupt_at: int | None = None) -> Path:
    """Cadena valida, opcionalmente rota (enlace) o corrupta (contenido).

    Son dos patologias distintas y el fixture las produce por separado a
    proposito: una es exceptuable por un humano y la otra no.
    """
    prev = "GENESIS"
    lines = []
    for i, e in enumerate(entries):
        body = dict(e)
        body["prev_entry_hash"] = "sha256:" + "0" * 64 if i == break_at else prev
        h = f"sha256:{aw._compute_entry_hash(body)}"
        body["entry_hash"] = h
        prev = h
        if i == corrupt_at:
            # El contenido cambia DESPUES de hashear: el hash almacenado deja
            # de corresponder al cuerpo. Eso es corrupcion, no fork.
            body["project_id"] = "alterado"
        lines.append(json.dumps(body, separators=(",", ":"), ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _baseline(path: Path, entry_ids) -> Path:
    path.write_text(json.dumps({
        "baseline_version": 1,
        "known_forks": [{"fork_id": f"F-{i}", "entry_id": eid}
                        for i, eid in enumerate(entry_ids)],
    }), encoding="utf-8")
    return path


def _exception_store(path: Path, entry_ids) -> Path:
    rec = store.build_record(
        decision_family="AUDIT_EXCEPTION", decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", resolved_target_ids=list(entry_ids),
        decision="APPROVE", decision_origin="human_confirmed",
        approved_by_id="Cesar", approved_by_display_name="Cesar",
        decision_instance_id="AUDIT_EXCEPTION-2026-001")
    path.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


@pytest.fixture()
def empty_store(tmp_path) -> Path:
    p = tmp_path / "sin_decisiones.jsonl"
    p.write_text("", encoding="utf-8")
    return p


def _dims(tmp_path, *, break_at=None, corrupt_at=None, known=(), store_file=None,
          n=6):
    chain = _chain(_entries(n), tmp_path / "chain.jsonl",
                   break_at=break_at, corrupt_at=corrupt_at)
    walk = aw._walk_chain(chain)
    return aw._dimensions(
        walk["hash_errors"], walk["chain_errors"], walk["total"],
        break_ids=walk["break_ids"],
        baseline_file=_baseline(tmp_path / "baseline.json", known),
        decision_store_file=store_file)


# ===========================================================================
# F-01 / F-04 -- la afirmacion que se cierra
# ===========================================================================

def test_f01_part11_is_never_true_with_chain_errors():
    """Sobre la cadena REAL de hoy. El test central de esta fase."""
    r = aw.verify_chain()
    assert r["chain_errors"] > 0
    assert r["part11_compliant"] != aw.PART11_COMPLIANT
    assert r["part11_compliant"] in aw.PART11_VALUES


def test_f01_part11_compliant_is_no_longer_a_boolean():
    """Cambiar el TIPO es lo que obliga a que cada lector se revise.

    Si siguiera siendo `bool`, los lectores que ramifican por veracidad
    seguirian compilando y mintiendo al reves.
    """
    r = aw.verify_chain()
    assert not isinstance(r["part11_compliant"], bool)
    assert isinstance(r["part11_compliant"], str)


def test_f04_without_an_exception_part11_is_not_determined(tmp_path, empty_store):
    d = _dims(tmp_path, break_at=2, known=["evt-2"], store_file=empty_store)
    assert d["part11_compliant"] == aw.PART11_NOT_DETERMINED
    assert d["chain_continuity"] == aw.CHAIN_CONTINUITY_BROKEN_HISTORICAL


def test_f04_the_real_chain_never_claims_plain_compliance():
    """Sobre la cadena REAL: con una ruptura, NUNCA se llega a COMPLIANT.

    Afirmaba `NOT_DETERMINED` y `unbacked == [el fork]`, que era el estado hasta
    que Cesar firmo AUDIT_EXCEPTION-2026-002 el 2026-07-30. Al firmarla, ambos
    valores cambiaron —a ACCEPTED_WITH_DOCUMENTED_EXCEPTION y a lista vacia— y el
    test se puso rojo por el exito del proceso que existe para producir ese
    cambio.

    La regla que NO cambia: mientras `chain_errors > 0`, la unica diferencia que
    una firma humana puede introducir es entre "no determinada" y "aceptada con
    excepcion documentada". COMPLIANT queda fuera del alcance de cualquier firma,
    y `unbacked` vacio SOLO puede venir de una excepcion registrada.
    """
    r = aw.verify_chain()
    assert r["chain_errors"] > 0, "sin ruptura este test no mide nada"
    assert r["part11_compliant"] != aw.PART11_COMPLIANT, (
        "ninguna firma puede declarar la cadena integra")
    assert r["part11_compliant"] in (aw.PART11_NOT_DETERMINED,
                                     aw.PART11_ACCEPTED_WITH_EXCEPTION)

    if r["part11_compliant"] == aw.PART11_ACCEPTED_WITH_EXCEPTION:
        assert r["unbacked_known_fork_entry_ids"] == [], (
            "aceptada con excepcion pero quedan forks sin respaldo")
        assert aw.unbacked_known_forks() == ()
    else:
        assert r["unbacked_known_fork_entry_ids"] == [REAL_FORK_ENTRY_ID]


# ===========================================================================
# F-02 -- las dimensiones no se derivan unas de otras
# ===========================================================================

def test_f02_content_integrity_stays_green_while_continuity_is_broken(tmp_path,
                                                                      empty_store):
    """La buena noticia real debe poder decirse sin arrastrar una conclusion.

    `hash_errors == 0` significa que ningun contenido fue alterado, y eso es
    cierto tambien con la cadena rota.
    """
    d = _dims(tmp_path, break_at=2, known=["evt-2"], store_file=empty_store)
    assert d["content_hash_integrity"] == aw.CONTENT_HASH_INTEGRITY_VERIFIED
    assert d["chain_continuity"] == aw.CHAIN_CONTINUITY_BROKEN_HISTORICAL
    assert d["part11_compliant"] == aw.PART11_NOT_DETERMINED


def test_f02_the_real_chain_reports_all_five_dimensions():
    r = aw.verify_chain()
    for key in ("content_hash_integrity", "chain_continuity",
                "historical_fork_present", "new_forks_since_baseline",
                "part11_compliant"):
        assert key in r
    # La dimension buena en verde SIN arrastrar una conclusion de conformidad:
    # el contenido es autentico y la cadena sigue rota, y las dos cosas se dicen
    # a la vez. Fijaba `NOT_DETERMINED`, que era el valor de aquel dia; lo que no
    # cambia con la firma de la excepcion es que VERIFIED aqui no implica
    # COMPLIANT alli.
    assert r["content_hash_integrity"] == aw.CONTENT_HASH_INTEGRITY_VERIFIED
    assert r["chain_continuity"] != aw.CHAIN_CONTINUITY_VERIFIED, (
        "la continuidad NUNCA vuelve a VERIFIED: la ruptura sigue ahi")
    assert r["part11_compliant"] != aw.PART11_COMPLIANT


def test_f02_a_clean_chain_is_compliant(tmp_path, empty_store):
    """La guardia no es un "siempre no": una cadena integra si concluye."""
    d = _dims(tmp_path, store_file=empty_store)
    assert d["content_hash_integrity"] == aw.CONTENT_HASH_INTEGRITY_VERIFIED
    assert d["chain_continuity"] == aw.CHAIN_CONTINUITY_VERIFIED
    assert d["historical_fork_present"] is False
    assert d["part11_compliant"] == aw.PART11_COMPLIANT


# ===========================================================================
# F-03 / F-05 -- la excepcion, y su alcance
# ===========================================================================

def test_f03_accepted_requires_an_active_exception_for_that_entry(tmp_path):
    exc = _exception_store(tmp_path / "exc.jsonl", ["evt-2"])
    d = _dims(tmp_path, break_at=2, known=["evt-2"], store_file=exc)

    assert d["chain_continuity"] == aw.CHAIN_CONTINUITY_ACCEPTED
    assert d["part11_compliant"] == aw.PART11_ACCEPTED_WITH_EXCEPTION
    # NUNCA "verificada" ni "sin errores".
    assert d["chain_continuity"] != aw.CHAIN_CONTINUITY_VERIFIED
    assert d["part11_compliant"] != aw.PART11_COMPLIANT
    assert d["historical_fork_present"] is True


def test_f03_an_agent_signature_cannot_accept_a_fork(tmp_path):
    """La excepcion la firma un humano. La fabrica no se exculpa a si misma."""
    rec = store.build_record(
        decision_family="AUDIT_EXCEPTION", decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", resolved_target_ids=["evt-2"],
        decision="APPROVE", decision_origin="agent_proposed",
        approved_by_id="Cesar", approved_by_display_name="Cesar",
        decision_instance_id="AUDIT_EXCEPTION-2026-002")
    path = tmp_path / "agente.jsonl"
    path.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")

    d = _dims(tmp_path, break_at=2, known=["evt-2"], store_file=path)
    assert d["part11_compliant"] == aw.PART11_NOT_DETERMINED


def test_f05_an_exception_for_another_entry_does_not_cover_this_fork(tmp_path):
    """La excepcion cubre UN entry_id y solo uno."""
    exc = _exception_store(tmp_path / "exc.jsonl", ["evt-0"])
    d = _dims(tmp_path, break_at=2, known=["evt-2"], store_file=exc)

    assert d["chain_continuity"] == aw.CHAIN_CONTINUITY_BROKEN_HISTORICAL
    assert d["part11_compliant"] == aw.PART11_NOT_DETERMINED
    assert d["unbacked_known_fork_entry_ids"] == ["evt-2"]


# ===========================================================================
# F-06 / F-07 -- forks nuevos
# ===========================================================================

def test_f06_no_new_forks_on_the_real_chain():
    """El unico fork de la cadena real esta en el baseline."""
    assert aw.new_forks_since_baseline() == ()
    assert aw.verify_chain()["new_forks_since_baseline"] == 0


def test_f07_an_injected_fork_counts_as_new_and_blocks(tmp_path):
    """Un fork nuevo NO es exceptuable por el baseline existente."""
    exc = _exception_store(tmp_path / "exc.jsonl", ["evt-2"])
    d = _dims(tmp_path, break_at=4, known=["evt-2"], store_file=exc)

    assert d["new_forks_since_baseline"] == 1
    assert d["new_fork_entry_ids"] == ["evt-4"]
    assert d["chain_continuity"] == aw.CHAIN_CONTINUITY_BROKEN_NEW
    assert d["part11_compliant"] == aw.PART11_NOT_DETERMINED


def test_f07_new_forks_are_identified_by_entry_id_not_line_number(tmp_path):
    """Si el fichero se rota, la linea cambia y el evento no.

    Se construye la MISMA entrada rota (`evt-x`) en dos posiciones distintas:
    linea 2 en una cadena y linea 5 en otra mas larga. El baseline la reconoce
    en ambas, porque identifica por `entry_id`.
    """
    baseline = _baseline(tmp_path / "b.json", ["evt-x"])

    corta = _entries(4)
    corta[2]["entry_id"] = "evt-x"
    chain_corta = _chain(corta, tmp_path / "corta.jsonl", break_at=2)

    larga = _entries(8, prefix="otro")
    larga[5]["entry_id"] = "evt-x"
    chain_larga = _chain(larga, tmp_path / "larga.jsonl", break_at=5)

    # Misma entrada, dos posiciones. Detectada en ambas y nueva en ninguna.
    assert aw.chain_break_entry_ids(chain_corta) == ("evt-x",)
    assert aw.chain_break_entry_ids(chain_larga) == ("evt-x",)
    assert aw.new_forks_since_baseline(chain_corta, baseline) == ()
    assert aw.new_forks_since_baseline(chain_larga, baseline) == ()


# ===========================================================================
# F-08 -- el baseline no puede ser una alfombra
# ===========================================================================

def test_f08_a_known_fork_without_a_backing_decision_is_reported(tmp_path,
                                                                 empty_store):
    """No se puede silenciar un fork editando el JSON.

    El baseline se valida contra las excepciones REGISTRADAS: un `known_fork`
    sin decision que lo respalde sale listado y mantiene la continuidad rota.
    """
    baseline = _baseline(tmp_path / "b.json", ["evt-2"])
    assert aw.unbacked_known_forks(baseline, decision_store_file=empty_store) \
        == ("evt-2",)

    d = _dims(tmp_path, break_at=2, known=["evt-2"], store_file=empty_store)
    assert d["unbacked_known_fork_entry_ids"] == ["evt-2"]
    assert d["chain_continuity"] == aw.CHAIN_CONTINUITY_BROKEN_HISTORICAL


def test_f08_adding_a_fork_to_the_baseline_does_not_grant_acceptance(tmp_path,
                                                                     empty_store):
    """El escenario de abuso, explicito: alguien mete el fork nuevo al JSON.

    Deja de contar como NUEVO -- eso es lo que el baseline hace -- pero pasa a
    contar como conocido SIN respaldo, y la conclusion sigue sin determinarse.
    Silenciarlo exige una firma humana, no un editor de texto.
    """
    d = _dims(tmp_path, break_at=4, known=["evt-2", "evt-4"], store_file=empty_store)
    assert d["new_forks_since_baseline"] == 0
    assert "evt-4" in d["unbacked_known_fork_entry_ids"]
    assert d["part11_compliant"] == aw.PART11_NOT_DETERMINED


def test_f08_an_unreadable_baseline_knows_nothing_instead_of_everything(tmp_path):
    """Fail-closed: baseline ilegible => TODO fork cuenta como nuevo."""
    roto = tmp_path / "roto.json"
    roto.write_text("{no es json", encoding="utf-8")
    chain = _chain(_entries(6), tmp_path / "c.jsonl", break_at=2)

    assert aw.known_fork_entry_ids(roto) == ()
    assert aw.new_forks_since_baseline(chain, roto) == ("evt-2",)


def test_f08_the_real_baseline_names_the_real_fork():
    """El baseline congelado apunta al evento que existe de verdad."""
    baseline = aw.load_fork_baseline()
    ids = [f["entry_id"] for f in baseline["known_forks"]]
    assert ids == [REAL_FORK_ENTRY_ID]
    assert ids == list(aw.chain_break_entry_ids())

    fork = baseline["known_forks"][0]
    assert fork["root_cause"] == "stale_in_process_head_cache"
    assert fork["fixed_by_commit"] == "8c033fa"

    # Congelar el baseline NO es aceptar el fork, ni antes ni despues de la
    # firma: son dos actos distintos y el fichero tiene que seguir diciendolo.
    assert baseline["frozen_by_is_human_acceptance"] is False

    # Y lo que el baseline AFIRMA sobre la aceptacion tiene que coincidir con el
    # almacen. Fijaba `accepted_by_decision is None`, o sea el mundo previo a la
    # firma de Cesar; la regla real es que el fichero no puede declararse
    # aceptado por su cuenta -- si nombra una decision, esa decision tiene que
    # existir y cubrir este entry_id.
    declarada = fork.get("accepted_by_decision")
    if declarada is None:
        assert aw.unbacked_known_forks() == (REAL_FORK_ENTRY_ID,)
    else:
        assert aw.unbacked_known_forks() == (), (
            f"el baseline dice aceptado por {declarada} y el resolver no lo ve")
        cubre = [r for r in store.read_all()
                 if r.get("decision_instance_id") == declarada]
        assert cubre, f"{declarada} no existe en el almacen"
        assert REAL_FORK_ENTRY_ID in cubre[0]["resolved_target_ids"]
        assert cubre[0]["decision_origin"] == "human_confirmed"


# ===========================================================================
# F-09 -- la corrupcion no es exceptuable
# ===========================================================================

def test_f09_hash_errors_are_never_exceptable(tmp_path):
    """Aunque exista una excepcion firmada sobre esa entrada.

    Un fork es corrupcion de ENLACE y un humano puede aceptarla explicando el
    mecanismo. Un hash malo es corrupcion de CONTENIDO: el registro no dice lo
    que decia, y ninguna firma lo convierte en otra cosa.
    """
    exc = _exception_store(tmp_path / "exc.jsonl", ["evt-2", "evt-3"])
    d = _dims(tmp_path, corrupt_at=2, known=["evt-2", "evt-3"], store_file=exc)

    assert d["content_hash_integrity"] == aw.CONTENT_HASH_INTEGRITY_COMPROMISED
    assert d["part11_compliant"] == aw.PART11_NOT_DETERMINED


def test_f09_a_corrupt_entry_is_not_reported_as_a_fork(tmp_path):
    """No se gobierna con una excepcion, asi que no entra en la lista."""
    chain = _chain(_entries(6), tmp_path / "c.jsonl", corrupt_at=2)
    walk = aw._walk_chain(chain)
    assert walk["hash_errors"] == 1
    assert "evt-2" not in walk["break_ids"]


# ===========================================================================
# F-10 / F-11 -- regresion del arreglo 8c033fa
# ===========================================================================

def _mp_worker_write_events(args):
    """Escribe N eventos en el almacen indicado. Top-level para picklear."""
    audit_path, count, tag = args
    import importlib
    from factory.core import audit_writer as _aw
    importlib.reload(_aw)
    _aw.AUDIT_FILE = Path(audit_path)
    _aw._last_entry_hash = None
    written = 0
    for i in range(count):
        r = _aw.write_event("gates_executed", f"proj_{tag}", {"i": i})
        if "error" not in r:
            written += 1
    return written


def test_f10_two_concurrent_writers_produce_no_chain_errors(tmp_path):
    """Dos procesos, 500 eventos cada uno, sobre el MISMO fichero.

    Es la regresion del arreglo `8c033fa`. Si alguien retirara el `flock` o la
    invalidacion de cache, esto volveria a producir rupturas.
    """
    audit_path = tmp_path / "audit" / "concurrent.jsonl"
    audit_path.parent.mkdir(parents=True)
    audit_path.touch()

    ctx = multiprocessing.get_context("fork")
    with ctx.Pool(processes=2) as pool:
        escritos = pool.map(_mp_worker_write_events,
                            [(str(audit_path), 500, "a"), (str(audit_path), 500, "b")])

    assert escritos == [500, 500]
    walk = aw._walk_chain(audit_path)
    assert walk["total"] == 1000
    assert walk["hash_errors"] == 0
    assert walk["chain_errors"] == 0, f"rupturas: {walk['break_ids']}"


def test_f11_a_stale_head_cache_is_invalidated_by_the_lock(tmp_path, monkeypatch):
    """Reproduce la causa raiz de §3.2 y prueba que el arreglo la cierra.

    Sin este test, "corregido por 8c033fa" se apoya solo en la ausencia de
    forks posteriores -- correlacion, no mecanismo.

    El escenario real: dos procesos con `_last_entry_hash` cacheado apuntando
    a la misma entrada; uno escribe y avanza la cabeza, el otro escribe DESPUES
    con su valor de hace minutos. Aqui se simula ensuciando la cache a mano
    entre dos escrituras.
    """
    audit_path = tmp_path / "audit" / "stale.jsonl"
    audit_path.parent.mkdir(parents=True)
    monkeypatch.setattr(aw, "AUDIT_FILE", audit_path)
    monkeypatch.setattr(aw, "_last_entry_hash", None)

    aw.write_event("gates_executed", "p", {"n": 1})
    cabeza_vieja = aw._last_entry_hash
    aw.write_event("gates_executed", "p", {"n": 2})
    assert aw._last_entry_hash != cabeza_vieja, "la cabeza deberia haber avanzado"

    # El escritor "olvidado": vuelve a poner en memoria la cabeza de hace dos
    # escrituras, exactamente como el proceso de lab_qc_project el 2026-06-15.
    monkeypatch.setattr(aw, "_last_entry_hash", cabeza_vieja)
    aw.write_event("gates_executed", "p", {"n": 3})

    walk = aw._walk_chain(audit_path)
    assert walk["total"] == 3
    assert walk["chain_errors"] == 0, (
        "la cache obsoleta produjo un fork: la invalidacion dentro del lock "
        f"no esta funcionando ({walk['break_ids']})")


def test_f11_the_invalidation_line_is_still_inside_the_lock():
    """Estructural: `_last_entry_hash = None` DENTRO del `with` del lock.

    La linea que cierra la causa raiz no es el `flock` -- es la invalidacion.
    Un refactor que la sacara del lock dejaria el bug abierto con los tests de
    comportamiento aun en verde, porque en un test no hay contencion real.
    """
    import ast
    tree = ast.parse((REPO / "factory" / "core" / "audit_writer.py")
                     .read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "write_event")

    dentro = []
    for node in ast.walk(fn):
        if isinstance(node, ast.With):
            for inner in ast.walk(node):
                if (isinstance(inner, ast.Assign)
                        and any(getattr(t, "id", "") == "_last_entry_hash"
                                for t in inner.targets)
                        and isinstance(inner.value, ast.Constant)
                        and inner.value.value is None):
                    dentro.append(inner.lineno)
    assert dentro, ("`_last_entry_hash = None` ya no esta dentro del bloque del "
                    "lock: la causa raiz del fork de 2026-06-15 vuelve a estar abierta")


# ===========================================================================
# F-12 -- read-only
# ===========================================================================

def test_f12_verify_chain_is_read_only(tmp_path, monkeypatch):
    """100 llamadas no cambian ni una entrada."""
    audit_path = tmp_path / "audit" / "ro.jsonl"
    audit_path.parent.mkdir(parents=True)
    _chain(_entries(5), audit_path)
    monkeypatch.setattr(aw, "AUDIT_FILE", audit_path)

    antes = audit_path.read_bytes()
    counts = {aw.verify_chain()["log_count"] for _ in range(100)}
    assert counts == {5}
    assert audit_path.read_bytes() == antes


def test_f12_verify_chain_survives_without_the_governance_dependency(tmp_path, monkeypatch):
    """`verify_chain()` no puede depender de que `jsonschema` esté instalado.

    Regresion real cazada por Gate 0 al implementar G1.14: el resolver importa
    `schema_loader`, que exige `jsonschema` fail-closed al importarse, y
    `factory_selfcheck.sh` / `factory_status.sh` llaman a `verify_chain()` con
    el `python3` del SISTEMA, que no lo tiene. Preguntar por la integridad de
    la cadena empezaba a reventar justo en los dos sitios donde más falta hace
    que funcione.

    Se simula rompiendo el import y comprobando que la lectura sobrevive y
    degrada hacia el lado seguro (ninguna excepción demostrable => ninguna
    cuenta), nunca hacia una absolución.

    Escribirlo bien costo dos intentos y los dos fallos valen la pena anotarlos:

    1. Parchear `builtins.__import__` filtrando por nombre no rompe nada:
       `from factory.core import decision_scope_resolver` invoca
       `__import__("factory.core", ...)`, asi que el nombre buscado nunca
       llega.
    2. Poner `None` en `sys.modules` TAMPOCO basta: el paquete `factory.core`
       ya tiene el submodulo como atributo y `from ... import` lo resuelve por
       `getattr`, sin mirar `sys.modules`.

    Y aun roto el import, hacia falta un fixture que DISCRIMINE: con el
    almacen real (sin excepciones) las dos ramas dan el mismo resultado, asi
    que el test pasaba sin probar nada. Se necesita una excepcion VALIDA -- de
    modo que la rama sana diga "aceptado" y la degradada diga "sin respaldo".
    """
    from unittest.mock import patch

    from factory.core import decision_scope_resolver as _r  # noqa: F401
    import factory.core as core_pkg

    chain = _chain(_entries(6), tmp_path / "c.jsonl", break_at=2)
    baseline = _baseline(tmp_path / "b.json", ["evt-2"])
    exc = _exception_store(tmp_path / "exc.jsonl", ["evt-2"])
    walk = aw._walk_chain(chain)

    # Con el resolver sano, la excepcion firmada SI cubre el fork.
    sano = aw._dimensions(walk["hash_errors"], walk["chain_errors"], walk["total"],
                          break_ids=walk["break_ids"], baseline_file=baseline,
                          decision_store_file=exc)
    assert sano["part11_compliant"] == aw.PART11_ACCEPTED_WITH_EXCEPTION

    # Con el resolver inalcanzable, la MISMA excepcion deja de poder probarse.
    monkeypatch.delattr(core_pkg, "decision_scope_resolver")
    with patch.dict(sys.modules, {"factory.core.decision_scope_resolver": None}):
        with pytest.raises(ImportError):
            from factory.core import decision_scope_resolver  # noqa: F401
        degradado = aw._dimensions(
            walk["hash_errors"], walk["chain_errors"], walk["total"],
            break_ids=walk["break_ids"], baseline_file=baseline,
            decision_store_file=exc)

    assert degradado["unbacked_known_fork_entry_ids"] == ["evt-2"]
    assert degradado["part11_compliant"] == aw.PART11_NOT_DETERMINED


def test_f12_verify_chain_needs_no_governance_dependency_at_module_level():
    """El import del resolver vive DENTRO de la funcion, no arriba del modulo.

    `schema_loader` exige `jsonschema` fail-closed al importarse, y
    `factory_selfcheck.sh` / `factory_status.sh` llaman a `verify_chain()` con
    el `python3` del SISTEMA, que no lo tiene. Subir ese import al nivel de
    modulo rompe los dos scripts en silencio -- ambos hacen `2>/dev/null`, asi
    que el fallo se ve como "cadena INVALIDA", no como un error de import.
    """
    import ast
    tree = ast.parse((REPO / "factory" / "core" / "audit_writer.py")
                     .read_text(encoding="utf-8"))
    for node in tree.body:  # solo el nivel superior
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            texto = ast.dump(node)
            assert "decision_scope_resolver" not in texto, (
                f"linea {node.lineno}: el resolver importado a nivel de modulo "
                "rompe factory_selfcheck.sh y factory_status.sh")


def test_f12_the_baseline_is_never_written(tmp_path, empty_store):
    baseline = tmp_path / "no_existe.json"
    aw.load_fork_baseline(baseline)
    aw.unbacked_known_forks(baseline, decision_store_file=empty_store)
    assert not baseline.exists()


# ===========================================================================
# Radio de impacto del cambio de tipo
# ===========================================================================

def test_no_reader_branches_on_the_truthiness_of_part11_compliant():
    """`"NOT_DETERMINED"` es truthy: `if not audit["part11_compliant"]` seria
    siempre falso y el riesgo dejaria de emitirse justo cuando hace falta.

    Se comprueba por AST sobre los lectores reales, no por confianza en que
    alguien recordo revisarlos.
    """
    import ast
    sospechosos = []
    for rel in ("factory/api/routes/status.py",
                "factory/services/gmpai_artifact_service.py",
                "factory/core/quality_gate_runner.py"):
        path = REPO / rel
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for node in ast.walk(tree):
            # `not <algo>.get("part11_compliant")` o `not <algo>["part11_compliant"]`
            if not (isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not)):
                continue
            if "part11_compliant" in ast.dump(node.operand):
                sospechosos.append(f"{rel}:{node.lineno}")
    assert not sospechosos, (
        "lector ramificando por veracidad de un enum:\n  " + "\n  ".join(sospechosos))


def test_the_javascript_reader_compares_against_the_exact_value():
    """El sello de Mission Control no puede ponerse verde con NOT_DETERMINED."""
    js = (REPO / "factory" / "ui" / "js" / "mission_control" / "dash.js").read_text(
        encoding="utf-8")
    assert "d.part11_compliant==='COMPLIANT'" in js.replace(" ", "")
    assert "d.verified&&d.part11_compliant;" not in js.replace(" ", "")
