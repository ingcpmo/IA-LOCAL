"""Preparacion de G7 — medidas preventivas §4.2/§7 de AUDIT_FORK_REMEDIATION_SPEC.

Lo que se prueba aqui no es la excepcion —esa la firma un humano y un agente no
puede— sino la condicion que la hace firmable: **aceptar una excepcion cuya
prevencion no esta implementada es aceptar que vuelva a pasar.**

De las cinco medidas de §7, la primera (flock + invalidacion de cache) ya estaba
cerrada por `8c033fa` y la cubren F-10/F-11 en `test_audit_fork_governance.py`.
Aqui van las dos que faltaban:

  - guardia de escritor unico (writer_pid / writer_host / writer_identity)
  - F-13: `write_event` que no logra el lock falla RUIDOSAMENTE y no escribe

Mas el invariante que las gobierna: el estado de las cinco medidas se DERIVA de
la cadena y del codigo, nunca se declara. La version anterior de esa lista eran
cinco literales `ok:false` en `governance.js` para flipear a mano, y de esa lista
depende el boton "Aceptar" del panel G7 — un `true` a mano habilita una firma
regulatoria sobre una prevencion que puede no existir. Es el mismo defecto que
`ecc7fa6` corrigio en el guard de riesgos: fotografiar el mundo en vez de medir
la regla.
"""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.core import audit_writer as aw

REPO = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _line(entry: dict, prev: str) -> tuple[str, str]:
    body = dict(entry)
    body["prev_entry_hash"] = prev
    h = f"sha256:{aw._compute_entry_hash(body)}"
    body["entry_hash"] = h
    return json.dumps(body, separators=(",", ":"), ensure_ascii=False), h


def _chain_with_identity(path: Path, flags: list[bool]) -> Path:
    """Una cadina valida donde `flags[i]` dice si la entrada i trae identidad.

    Se construye con el hash real de cada cuerpo: los campos de identidad viajan
    DENTRO del cuerpo hasheado, asi que una cadena de prueba que los omitiera
    del hash no probaria lo que dice probar.
    """
    prev = "GENESIS"
    lines = []
    for i, has_id in enumerate(flags):
        entry = {"timestamp": f"2026-07-30T00:0{i % 10}:00+00:00",
                 "entry_id": f"e-{i}", "event_type": "gates_executed",
                 "project_id": "p", "data": {}}
        if has_id:
            entry.update({"writer_pid": 1000 + i, "writer_host": "ivr-ia",
                          "writer_identity": "ing_cpmo@uid:1001"})
        line, prev = _line(entry, prev)
        lines.append(line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@pytest.fixture()
def redirected(tmp_path, monkeypatch):
    """Aisla el escritor: cadena, lock y log de fallos en tmp_path.

    Ningun test de este fichero escribe en la cadena REAL. Un test que anexe a
    `factory_audit.jsonl` contamina el registro de auditoria de la fabrica, que
    es append-only y no se puede limpiar despues.
    """
    chain = tmp_path / "factory_audit.jsonl"
    monkeypatch.setattr(aw, "AUDIT_FILE", chain)
    monkeypatch.setattr(aw, "AUDIT_WRITE_FAILURES_FILE", tmp_path / "failures.log")
    monkeypatch.setattr(aw, "_last_entry_hash", None)
    return tmp_path


# ===========================================================================
# Medida 2 -- guardia de escritor unico
# ===========================================================================

def test_write_event_stamps_the_three_identity_fields(redirected):
    entry = aw.write_event("gates_executed", "p", {"k": "v"})
    assert "error" not in entry
    for field in aw.WRITER_IDENTITY_FIELDS:
        assert entry.get(field), f"falta {field}"
    assert entry["writer_pid"] == os.getpid()


def test_the_identity_is_inside_the_hashed_body(redirected):
    """Falsificar la identidad invalida el `entry_hash`.

    Es lo que hace que la guardia sirva de algo: una identidad de escritor
    editable sin coste no delata a nadie.
    """
    entry = aw.write_event("gates_executed", "p")
    tampered = {k: v for k, v in entry.items() if k != "entry_hash"}
    tampered["writer_identity"] = "otro@uid:0"
    assert entry["entry_hash"] != f"sha256:{aw._compute_entry_hash(tampered)}"


def test_the_written_chain_verifies_with_the_new_fields(redirected):
    """Anadir campos al cuerpo no rompe la verificacion de la cadena."""
    for _ in range(5):
        aw.write_event("gates_executed", "p")
    walk = aw._walk_chain(aw.AUDIT_FILE)
    assert (walk["total"], walk["hash_errors"], walk["chain_errors"]) == (5, 0, 0)


def test_an_entry_written_outside_write_event_is_reported(redirected):
    """El riesgo residual real: un escritor que no pasa por `write_event`.

    No toma el lock, asi que ningun locking lo detecta. Lo delata que no sabe
    poner los tres campos sin invalidar el hash.
    """
    chain = _chain_with_identity(redirected / "c.jsonl", [True, True, False, True])
    rep = aw.writer_identity_audit(chain)
    assert rep["guard_live"] is True
    assert rep["missing_writer_identity_ids"] == ["e-2"]


def test_entries_before_the_anchor_are_not_violations(redirected):
    """Las 21 000 entradas historicas no son violaciones.

    Reportarlas dejaria el indicador en rojo permanente por historia, y un
    indicador que nunca puede estar verde deja de leerse.
    """
    chain = _chain_with_identity(redirected / "c.jsonl", [False, False, True, True])
    rep = aw.writer_identity_audit(chain)
    assert rep["anchor_entry_id"] == "e-2"
    assert rep["entries_after_anchor"] == 2
    assert rep["missing_writer_identity_ids"] == []


def test_the_anchor_is_derived_not_declared(redirected):
    """No hay fichero que mover para esconder una entrada sin identidad.

    Si el ancla se declarara en un JSON, adelantarla ocultaria las violaciones
    anteriores. Derivada, la unica forma de mover el ancla es BORRAR entradas, y
    eso rompe la cadena y lo detecta `_walk_chain`.
    """
    chain = _chain_with_identity(redirected / "c.jsonl", [True, False, True])
    assert aw.writer_identity_audit(chain)["missing_writer_identity_ids"] == ["e-1"]

    # Borrar la primera entrada para "adelantar el ancla" rompe el enlace.
    lines = chain.read_text(encoding="utf-8").splitlines()
    chain.write_text("\n".join(lines[1:]) + "\n", encoding="utf-8")
    assert aw._walk_chain(chain)["chain_errors"] > 0


def test_a_partial_identity_does_not_count_as_present(redirected):
    """Dos de tres campos no es la guardia: es una guardia que no distingue."""
    prev = "GENESIS"
    line1, prev = _line({"entry_id": "a", "event_type": "gates_executed",
                         "project_id": "p", "data": {}, "writer_pid": 1,
                         "writer_host": "h", "writer_identity": "u@uid:1"}, prev)
    line2, _ = _line({"entry_id": "b", "event_type": "gates_executed",
                      "project_id": "p", "data": {}, "writer_pid": 2,
                      "writer_host": "h"}, prev)
    chain = redirected / "c.jsonl"
    chain.write_text(line1 + "\n" + line2 + "\n", encoding="utf-8")
    assert aw.writer_identity_audit(chain)["missing_writer_identity_ids"] == ["b"]


def test_writer_identity_distinguishes_host_from_container():
    """Los escritores reales tienen identidad de SO distinta (host vs contenedor).

    §4.2 lo documenta con los propietarios de los dos almacenes: `ing_cpmo` en
    el host, `root` en el contenedor. La identidad tiene que poder distinguirlos.
    """
    ident = aw.writer_identity()
    assert str(os.getuid()) in ident["writer_identity"]
    assert ident["writer_host"]
    assert ident["writer_pid"] == os.getpid()


# ===========================================================================
# F-13 -- write_event nunca falla en silencio
# ===========================================================================

def test_f13_a_lock_that_never_frees_does_not_write(redirected, monkeypatch):
    """Agotados los reintentos: no escribe, y no se cuelga esperando.

    `LOCK_EX` bloqueante esperaba PARA SIEMPRE. Un lock huerfano —hubo uno,
    creado por root mientras el host escribia como 1001— colgaba al escritor sin
    decir nada.
    """
    monkeypatch.setattr(aw, "LOCK_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(aw, "LOCK_RETRIES", 2)

    import fcntl
    def _always_taken(fh, op):
        if op & fcntl.LOCK_NB:
            raise OSError(11, "Resource temporarily unavailable")
    monkeypatch.setattr(aw.fcntl, "flock", _always_taken)

    res = aw.write_event("gates_executed", "p")
    assert "error" in res
    assert not aw.AUDIT_FILE.exists() or aw.AUDIT_FILE.read_text() == ""


def test_f13_the_failure_is_reported_to_the_file_and_stderr(redirected, monkeypatch,
                                                            capsys):
    monkeypatch.setattr(aw, "LOCK_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(aw, "LOCK_RETRIES", 1)

    import fcntl
    def _always_taken(fh, op):
        if op & fcntl.LOCK_NB:
            raise OSError(11, "busy")
    monkeypatch.setattr(aw.fcntl, "flock", _always_taken)

    aw.write_event("gates_executed", "proyecto_x")

    assert "AUDIT WRITE FAILURE" in capsys.readouterr().err
    logged = aw.AUDIT_WRITE_FAILURES_FILE.read_text(encoding="utf-8").strip()
    rec = json.loads(logged.splitlines()[-1])
    assert rec["reason"] == "AuditLockError"
    assert "proyecto_x" in rec["detail"]
    assert rec["writer_pid"] == os.getpid()


def test_f13_an_unwritable_chain_is_reported_too(redirected, monkeypatch, capsys):
    """Cualquier fallo, no solo el del lock. Un evento perdido en silencio es el
    defecto; la causa del fallo es secundaria."""
    def _boom(*a, **k):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(aw, "_get_prev_hash", _boom)

    res = aw.write_event("gates_executed", "p")
    assert "error" in res
    assert "AUDIT WRITE FAILURE" in capsys.readouterr().err
    assert aw.AUDIT_WRITE_FAILURES_FILE.exists()


def test_f13_reporting_a_failure_never_raises(redirected, monkeypatch):
    """El reporte es best-effort: una excepcion AQUI taparia el fallo que
    intenta hacer visible."""
    monkeypatch.setattr(aw, "AUDIT_WRITE_FAILURES_FILE",
                        Path("/proc/no-se-puede-escribir/x.log"))
    aw._report_write_failure("Prueba", "detalle")  # no debe lanzar


def test_the_lock_is_never_bypassed_on_failure():
    """No hay rama que escriba sin lock.

    El unico `open(AUDIT_FILE, "a")` de escritura vive dentro del `with` del
    lock. Escribir sin lock reintroduciria la condicion que produjo el fork.
    """
    src = (REPO / "factory/core/audit_writer.py").read_text(encoding="utf-8")
    body = src.split("def write_event(", 1)[1].split("\ndef ", 1)[0]
    antes, _, despues = body.partition("_acquire_lock(")
    assert 'open(AUDIT_FILE, "a"' not in antes
    assert despues.count('open(AUDIT_FILE, "a"') == 1


# La regresion de concurrencia con el lock NUEVO (`LOCK_NB` + reintentos, en vez
# del `LOCK_EX` bloqueante) no se duplica aqui: la cubre F-10 en
# `test_audit_fork_governance.py`, que ya lanza dos procesos con 500 eventos cada
# uno sobre `write_event` y exige `chain_errors == 0`. Reescribirla con 50
# eventos seria la misma prueba, mas debil.


# ===========================================================================
# El estado de las medidas se DERIVA
# ===========================================================================

def _guard(path):
    return next(m for m in aw.preventive_measures(path)
                if m["id"] == "writer_identity_guard")["implemented"]


def test_the_measure_status_is_derived_from_the_real_chain(redirected):
    """La medida 2 sigue a la cadena que se le pase, no a un literal."""
    violada = _chain_with_identity(redirected / "mala.jsonl", [True, False, True])
    limpia = _chain_with_identity(redirected / "buena.jsonl", [True, True])

    assert _guard(violada) is False
    assert _guard(limpia) is True


def test_an_unexercised_chain_is_not_a_missing_measure(redirected):
    """Prevencion implementada != prevencion ya ejercitada.

    Exigir que la cadena YA trajera una entrada sellada creaba un abrazo mortal:
    las entradas nuevas las produce la actividad gobernada, y la actividad que
    faltaba era justo la firma que esta medida bloquea. La medida habria estado
    esperando el efecto de la firma para permitir la firma.
    """
    virgen = _chain_with_identity(redirected / "virgen.jsonl", [False, False])
    assert aw.writer_identity_audit(virgen)["guard_live"] is False
    assert _guard(virgen) is True


def test_the_measure_still_needs_the_writer_to_stamp(redirected, monkeypatch):
    """Y no se regala: si `write_event` dejara de sellar, la medida se reabre."""
    monkeypatch.setattr(aw, "_write_event_stamps_identity", lambda: False)
    assert _guard(_chain_with_identity(redirected / "c.jsonl", [True, True])) is False


def test_a_single_entry_without_identity_reopens_the_measure(redirected):
    """Una sola escritura fuera del canal vuelve a abrir la medida.

    Si no lo hiciera, la guardia seria un sello de una sola vez en vez de un
    invariante.
    """
    chain = _chain_with_identity(redirected / "c.jsonl", [True] * 5 + [False])
    guard = next(m for m in aw.preventive_measures(chain)
                 if m["id"] == "writer_identity_guard")
    assert guard["implemented"] is False
    assert aw.preventive_measures_complete(chain) is False


def test_the_five_measures_are_reported_with_their_evidence_kind():
    """Cada medida declara COMO se sabe lo que dice.

    Medir sobre la cadena y leer el codigo fuente no son la misma clase de
    prueba, y colapsarlas en un booleano es como el reporte de auditoria decia
    `part11_compliant: true` sobre una cadena no verificada.
    """
    ms = aw.preventive_measures()
    assert len(ms) == 5
    assert {m["id"] for m in ms} == {
        "flock_and_cache_invalidation", "writer_identity_guard",
        "baseline_validated", "new_forks_fail_gate0", "no_silent_write_failure"}
    for m in ms:
        assert m["evidence_kind"] in (aw.EVIDENCE_DERIVED, aw.EVIDENCE_SOURCE)
        assert m["evidence"], f"{m['id']} sin evidencia declarada"
        assert isinstance(m["implemented"], bool)


def test_moving_the_invalidation_out_of_the_lock_reopens_measure_one():
    """La medida 1 mide el ORDEN, no la presencia de las lineas.

    Fuera del lock, la invalidacion de cache no vale nada: es lo unico que
    cierra §3.2, donde habia 3 min 10 s entre las dos escrituras.
    """
    assert aw._cache_invalidation_is_inside_the_lock() is True

    body = (REPO / "factory/core/audit_writer.py").read_text(encoding="utf-8")
    body = body.split("def write_event(", 1)[1].split("\ndef ", 1)[0]
    i_lock = body.index("_acquire_lock(")
    i_inval = body.index("_last_entry_hash = None")
    i_read = body.index("_get_prev_hash()")
    assert i_lock < i_inval < i_read


def test_the_ui_no_longer_carries_the_measures_hardcoded():
    """El boton "Aceptar" no puede depender de literales editables a mano.

    Con la lista en el JS, poner `ok:true` habilitaba una firma regulatoria sin
    tocar ni una linea de la prevencion que dice existir.
    """
    js = (REPO / "factory/ui/js/mission_control/governance.js").read_text(encoding="utf-8")
    assert "GOV?.preventive_measures" in js
    assert "{ ok:false, txt:'writer_pid" not in js
    assert "{ ok:true,  txt:'flock" not in js


def test_the_ui_keeps_the_button_shut_when_the_backend_says_nothing():
    """Sin datos, faltan todas. Degradar hacia "estan todas" abriria la firma
    justo cuando no se sabe nada."""
    js = (REPO / "factory/ui/js/mission_control/governance.js").read_text(encoding="utf-8")
    fn = js.split("function medidas()", 1)[1].split("\n}", 1)[0]
    assert "ok:false" in fn
    assert "!Array.isArray(ms)" in fn


def test_the_governance_state_exposes_the_measures():
    from factory.services import governance_service as gov
    st = gov.get_state()
    assert len(st["preventive_measures"]) == 5
    assert st["preventive_measures_complete"] == all(
        m["implemented"] for m in st["preventive_measures"])


# ===========================================================================
# El gate G7 no puede bloquearse con la firma que el panel registra
# ===========================================================================

def _g7(measures_complete: bool, forks: list[str]) -> dict:
    from factory.services import governance_service as gov
    import unittest.mock as mock
    cov = {f: {"uncovered_ids": [], "reconstructed_only_ids": []}
           for f in ("D1", "D2", "D3", "D4", "D5")}
    audit = {"unbacked_known_fork_entry_ids": forks}
    with mock.patch.object(gov._audit, "preventive_measures_complete",
                           return_value=measures_complete):
        path = gov._critical_path(cov, audit, {"records_in_store": 1})
    return next(g for g in path if g["gate"] == "G7")


def test_g7_is_not_blocked_by_the_signature_it_exists_to_collect():
    """"Falta tu firma" no es una precondicion: es el trabajo pendiente.

    Decia `blocked_by: "fork sin excepcion firmada"`, y `panelCard` deshabilita
    "Abrir panel" en todo gate BLOQUEADO — asi que la unica superficie para
    firmar la excepcion quedaba detras de un boton que la propia falta de firma
    apagaba. La tarjeta se veia en el indice y no se podia abrir.

    Es la misma trampa que la medida 2 tenia dentro: esperar el efecto de la
    firma para permitir la firma.
    """
    g7 = _g7(True, ["ab689c7c-3e0a-4c77-936b-152851f51a30"])
    assert g7["status"] == "LISTO"
    assert g7["blocked_by"] == []


def test_g7_is_blocked_by_incomplete_prevention_which_is_a_real_precondition():
    """La precondicion de verdad: aceptar una excepcion sin prevencion es
    aceptar que vuelva a pasar (§7)."""
    g7 = _g7(False, ["ab689c7c-3e0a-4c77-936b-152851f51a30"])
    assert g7["status"] == "BLOQUEADO"
    assert "medidas preventivas" in g7["blocked_by"][0]


def test_g7_closes_only_when_no_fork_is_left_unbacked():
    assert _g7(True, [])["status"] == "CERRADO"


def test_the_live_gate_is_reachable_today():
    """Sobre el estado REAL: G7 abierto para decidir, no bloqueado.

    Es la asercion que le faltaba a la sesion anterior — verifique el panel
    llamando a `govOpen` a mano, que salta justo el enlace roto.
    """
    from factory.services import governance_service as gov
    st = gov.get_state()
    g7 = next(g for g in st["critical_path"] if g["gate"] == "G7")
    assert st["preventive_measures_complete"] is True
    assert g7["status"] == "LISTO", g7
    assert st["audit"]["unbacked_known_fork_entry_ids"], (
        "sin fork sin respaldo no habria nada que firmar")


# ===========================================================================
# Lo que sigue siendo de un humano
# ===========================================================================

def test_no_measure_grants_the_exception(redirected):
    """Implementar las cinco medidas NO acepta el fork.

    Es la frontera de esta fase: la prevencion la construye Capa 8, la
    aceptacion la firma Capa 9. Si `preventive_measures_complete` moviera
    `part11_compliant`, un agente habria firmado una conclusion regulatoria.
    """
    chain = _chain_with_identity(redirected / "c.jsonl", [True, True])
    assert aw.preventive_measures_complete(chain) is True

    real = aw.verify_chain()
    assert real["part11_compliant"] == aw.PART11_NOT_DETERMINED
    assert real["unbacked_known_fork_entry_ids"]


def test_the_real_baseline_still_has_no_human_acceptance():
    """El baseline lo congelo Capa 8 y lo dice de si mismo.

    §5 pide `frozen_by` con identidad humana real. Hasta la firma, el fichero
    declara que su congelacion NO es una aceptacion.
    """
    baseline = json.loads((REPO / "factory/audit/fork_baseline.json")
                          .read_text(encoding="utf-8"))
    assert baseline["frozen_by_is_human_acceptance"] is False
    assert baseline["known_forks"][0]["accepted_by_decision"] is None
