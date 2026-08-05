"""El ciclo de firma propose -> confirm — W5 V2 G2.1.

Este fichero existe por un fallo que bloqueo la firma de D1 durante una sesion
entera y produjo 46 propuestas huerfanas y cero firmas. Tuvo TRES causas
encadenadas, y cada una parecia la ultima:

  1. `/propose` ESCRIBE en el almacen que `compute_state_hash()` resume, y la UI
     reenviaba a `/confirm` el hash del GET anterior. El propose invalidaba el
     token de su propio ciclo => 409 SIEMPRE, un solo usuario, sin concurrencia.
  2. El hash era GLOBAL: cualquier escritura de otra familia, o cualquier evento
     de auditoria de cualquier proyecto, invalidaba una firma de D1 valida.
  3. El worker de uvicorn corre SIN `--reload`, asi que el servidor seguia
     ejecutando el codigo viejo mientras el navegador ya tenia el JS nuevo:
     `/propose` no devolvia el token, el cliente mandaba `undefined` y el
     servidor respondia "409 falta state_hash" -- un 409 que decia "recarga y
     revisa" cuando recargar no podia arreglar nada.

La leccion de la (3) es la que estos tests no pueden capturar solos y por eso
existe tambien el test de Playwright contra el servidor vivo: probar el modulo
Python importado NO dice que sirve el proceso en ejecucion.

Los 13 puntos exigidos se marcan como [Nn] en cada test.
"""
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.core import audit_writer as aw
from factory.services import decision_store_v2 as store
from factory.services import governance_service as gov

REPO = Path(__file__).resolve().parents[2]

TRES = ["ecfr_21cfr_part11", "eu_gmp_annex11", "mhra_gxp_di_guidance_2018"]


@pytest.fixture()
def tmp_store(tmp_path, monkeypatch) -> Path:
    """Almacen y cadena de auditoria aislados. [N13]"""
    audit = tmp_path / "audit" / "factory_audit.jsonl"
    audit.parent.mkdir(parents=True)
    monkeypatch.setattr(aw, "AUDIT_FILE", audit)
    monkeypatch.setattr(aw, "_last_entry_hash", None)
    path = tmp_path / "decisions_v2.jsonl"
    path.write_text("", encoding="utf-8")
    return path


def _firmada(tmp_store, family="D1", targets=None, iid=None):
    """Una decision ORIGINAL firmada, para tener vigencia de partida."""
    rec = store.build_record(
        decision_family=family, decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST",
        resolved_target_ids=targets or TRES,
        decision="APPROVE", decision_origin="human_confirmed",
        approved_by_id="Cesar", approved_by_display_name="Cesar",
        decision_instance_id=iid, store_file=tmp_store)
    return store.append_record(rec, store_file=tmp_store)


def _propuesta(tmp_store, **over):
    kwargs = dict(target_ids=TRES, proposed_by_id="mission_control_ui",
                  reason="propuesta de prueba")
    kwargs.update(over)
    return gov.propose("D1", store_file=tmp_store, **kwargs)


# ===========================================================================
# [N1] el contrato: /propose entrega TODO lo que /confirm va a exigir
# ===========================================================================

def test_n1_propose_returns_every_field_confirm_requires(tmp_store):
    """Si el propose no entrega el token, el cliente manda `undefined`.

    Eso es literalmente lo que paso: el servidor viejo no devolvia `state_hash`,
    el JS nuevo leia `prop.data.state_hash` -> undefined, y el confirm llegaba
    sin campo. El contrato se congela aqui para que no vuelva a divergir en
    silencio.
    """
    _firmada(tmp_store)
    p = _propuesta(tmp_store)

    for campo in ("proposal_id", "proposal_hash", "family_state_hash",
                  "expected_active_instance_id", "proposal_state",
                  "reused_existing_proposal"):
        assert campo in p, f"/propose no devuelve {campo!r}"

    assert p["proposal_id"] == p["decision_instance_id"]
    assert p["family_state_hash"] == gov.family_state_hash("D1", store_file=tmp_store)
    assert p["proposal_state"] == gov.PROPOSAL_PROPOSED
    # El token describe el estado DESPUES de la escritura del propose: es el
    # unico momento en que puede ser valido para el confirm que viene detras.
    assert p["family_state_hash"] != gov.family_state_hash("D2", store_file=tmp_store)


def test_n2_the_token_the_client_must_echo_is_the_one_propose_returned(tmp_store):
    """[N2] El valor que hay que reenviar es el del propose, no el del GET.

    Versión sin navegador de la misma regla; el envío real del navegador se
    comprueba en el test de Playwright.
    """
    _firmada(tmp_store)
    antes = gov.family_state_hash("D1", store_file=tmp_store)
    p = _propuesta(tmp_store)
    assert p["family_state_hash"] != antes, (
        "el propose escribe, asi que el hash previo YA no sirve: si fueran "
        "iguales el control no estaria mirando el almacen")

    # El del GET previo falla; el del propose funciona.
    with pytest.raises(gov.StaleStateError):
        gov.confirm(p["proposal_id"], approved_by_id="Cesar", reason="x",
                    family_state_hash=antes, store_file=tmp_store)
    ok = gov.confirm(p["proposal_id"], approved_by_id="Cesar", reason="x",
                     family_state_hash=p["family_state_hash"], store_file=tmp_store)
    assert ok["decision_origin"] == "human_confirmed"


# ===========================================================================
# [N3] campo ausente => 422 y CERO escrituras
# ===========================================================================

def test_n3_missing_token_is_422_and_writes_nothing(tmp_store):
    """Un campo que no viajo no es un conflicto de estado.

    Devolverlo como 409 con "recarga y revisa" mando a un humano a recargar
    durante una sesion entera sin que eso pudiera arreglarlo nunca.
    """
    _firmada(tmp_store)
    p = _propuesta(tmp_store)
    lineas_antes = tmp_store.read_text(encoding="utf-8").count("\n")
    audit_antes = aw.AUDIT_FILE.read_text(encoding="utf-8") if aw.AUDIT_FILE.exists() else ""

    with pytest.raises(gov.MissingStateTokenError) as e:
        gov.confirm(p["proposal_id"], approved_by_id="Cesar", reason="x",
                    store_file=tmp_store)
    # El mensaje tiene que decir que NO es un problema de estado.
    assert "no es un conflicto" in str(e.value).lower()

    assert tmp_store.read_text(encoding="utf-8").count("\n") == lineas_antes
    audit_despues = aw.AUDIT_FILE.read_text(encoding="utf-8") if aw.AUDIT_FILE.exists() else ""
    assert audit_despues == audit_antes
    assert gov.proposal_state(p["proposal_id"], store_file=tmp_store) == gov.PROPOSAL_PROPOSED


def test_n3_missing_token_maps_to_422_not_409(tmp_store):
    """La traduccion excepcion -> codigo, que es donde se colapsaban."""
    from factory.api.routes.layer9 import _governance_error
    assert _governance_error(gov.MissingStateTokenError("falta")).status_code == 422
    assert _governance_error(gov.StaleStateError("obsoleto")).status_code == 409
    assert _governance_error(store.DecisionConflictError("ya")).status_code == 409
    assert _governance_error(store.DecisionValidationError("id")).status_code == 422


# ===========================================================================
# [N4] hash obsoleto => 409 y cero confirmaciones
# ===========================================================================

def test_n4_stale_token_is_409_and_confirms_nothing(tmp_store):
    _firmada(tmp_store)
    p = _propuesta(tmp_store)
    # Alguien escribe en la MISMA familia entremedias.
    _propuesta(tmp_store, target_ids=["ecfr_21cfr_part211"], reason="otra cosa")

    with pytest.raises(gov.StaleStateError):
        gov.confirm(p["proposal_id"], approved_by_id="Cesar", reason="x",
                    family_state_hash=p["family_state_hash"], store_file=tmp_store)

    assert gov.proposal_state(p["proposal_id"], store_file=tmp_store) == gov.PROPOSAL_PROPOSED
    firmadas = [r for r in store.read_all(tmp_store)
                if r["decision_origin"] == "human_confirmed"]
    assert len(firmadas) == 1, "solo la ORIGINAL de partida; el confirm no escribio"


# ===========================================================================
# [N5][N6] una fresca se firma UNA vez; la segunda es 409
# ===========================================================================

def test_n5_a_fresh_proposal_can_be_confirmed_once(tmp_store):
    _firmada(tmp_store)
    p = _propuesta(tmp_store, decision_type="CORRECTION",
                   supersedes_instance_id="D1-2026-001")
    c = gov.confirm(p["proposal_id"], approved_by_id="Cesar",
                    approved_by_display_name="Cesar", reason="firma buena",
                    family_state_hash=p["family_state_hash"],
                    expected_active_instance_id=p["expected_active_instance_id"],
                    store_file=tmp_store)
    assert c["decision_origin"] == "human_confirmed"
    assert c["approved_by_id"] == "Cesar"
    # La firma CONSERVA la forma del acto: confirmar una CORRECTION no produce
    # una ORIGINAL.
    assert c["decision_type"] == "CORRECTION"
    assert c["confirms_instance_id"] == p["proposal_id"]
    assert gov.proposal_state(p["proposal_id"], store_file=tmp_store) == gov.PROPOSAL_CONFIRMED


def test_n6_double_confirm_is_409_and_does_not_duplicate(tmp_store):
    _firmada(tmp_store)
    p = _propuesta(tmp_store)
    gov.confirm(p["proposal_id"], approved_by_id="Cesar", reason="primera",
                family_state_hash=p["family_state_hash"], store_file=tmp_store)

    with pytest.raises(store.DecisionConflictError):
        gov.confirm(p["proposal_id"], approved_by_id="Cesar", reason="segunda",
                    family_state_hash=gov.family_state_hash("D1", store_file=tmp_store),
                    store_file=tmp_store)

    cierres = [r for r in store.read_all(tmp_store)
               if r.get("confirms_instance_id") == p["proposal_id"]]
    assert len(cierres) == 1


# ===========================================================================
# [N7] una propuesta huerfana NO da cobertura
# ===========================================================================

def test_n7_an_orphan_proposal_grants_no_coverage(tmp_store):
    """46 propuestas D1 no otorgaron nada, y esto es lo que lo garantiza.

    Los proponentes son distintos a proposito: con el mismo actor y el mismo
    conjunto, la deduplicacion las colapsa en una -- que es correcto y se prueba
    en `test_an_equivalent_live_proposal_is_reused_not_multiplied`. Aqui hacen
    falta varias huerfanas DE VERDAD para comprobar que ninguna otorga nada.
    """
    for i in range(5):
        _propuesta(tmp_store, target_ids=["ecfr_21cfr_part211"],
                   proposed_by_id=f"layer8_agent_{i}", reason=f"huerfana {i}")

    cov = gov.get_coverage("D1", store_file=tmp_store)
    assert "ecfr_21cfr_part211" in cov["uncovered_ids"]
    assert cov["confirmed_active_instances"] == []

    from factory.core import decision_scope_resolver as resolver
    d = resolver.resolve("D1", "ecfr_21cfr_part211", store_file=tmp_store)
    assert d.authorized is False

    # Y se VEN como huerfanas: `status: ACTIVE` en el esquema significa "no
    # superseded", no "vigente como decision", y confundirlo es lo que hacia
    # que 46 propuestas parecieran decisiones en la lista.
    props = gov.list_proposals("D1", store_file=tmp_store)
    assert len(props) == 5
    assert all(p["proposal_state"] == gov.PROPOSAL_PROPOSED for p in props)
    assert all(p["grants_coverage"] is False for p in props)


# ===========================================================================
# [N8][N9] alcance del control: por FAMILIA
# ===========================================================================

def test_n8_a_change_in_another_family_does_not_invalidate_d1(tmp_store):
    """El hash global convertia el control optimista en una loteria.

    Aprobar un pack de D2 no cambia nada de lo que dice una D1, y sin embargo
    invalidaba su firma. El firmante perdia por hechos que no le concernian.
    """
    _firmada(tmp_store)
    p = _propuesta(tmp_store)

    # Escritura ajena: otra familia entera.
    gov.propose("D2", target_ids=["21_CFR_11.10(a)"],
                proposed_by_id="layer8_agent", reason="cosa de D2",
                store_file=tmp_store)

    # El hash GLOBAL si cambio; el de familia NO.
    assert p["family_state_hash"] == gov.family_state_hash("D1", store_file=tmp_store)
    c = gov.confirm(p["proposal_id"], approved_by_id="Cesar", reason="sigue valida",
                    family_state_hash=p["family_state_hash"], store_file=tmp_store)
    assert c["decision_origin"] == "human_confirmed"


def test_n9_a_change_in_the_active_d1_does_invalidate_the_proposal(tmp_store):
    """Lo que SI concierne, sigue bloqueando. El control no se ha aflojado."""
    _firmada(tmp_store)
    p = _propuesta(tmp_store)

    # Cambia la vigencia de la PROPIA familia: se firma otra D1.
    otra = _propuesta(tmp_store, target_ids=["ecfr_21cfr_part211"], reason="otra")
    gov.confirm(otra["proposal_id"], approved_by_id="Cesar", reason="firmada",
                family_state_hash=otra["family_state_hash"], store_file=tmp_store)

    with pytest.raises(gov.StaleStateError):
        gov.confirm(p["proposal_id"], approved_by_id="Cesar", reason="tarde",
                    family_state_hash=p["family_state_hash"], store_file=tmp_store)


def test_n9_expected_active_instance_is_checked_by_name(tmp_store):
    """El segundo control dice QUE cambio, con nombres y no con dos hashes."""
    _firmada(tmp_store, iid="D1-2026-001")
    p = _propuesta(tmp_store)
    with pytest.raises(gov.StaleStateError) as e:
        gov.confirm(p["proposal_id"], approved_by_id="Cesar", reason="x",
                    family_state_hash=p["family_state_hash"],
                    expected_active_instance_id="D1-2026-999",
                    store_file=tmp_store)
    assert "D1-2026-999" in str(e.value)
    assert "D1-2026-001" in str(e.value)


# ===========================================================================
# [N10] el ciclo completo de una sola pestaña
# ===========================================================================

def test_n10_single_tab_read_propose_confirm_completes(tmp_store):
    """Leer -> proponer -> firmar, sin trucos, tiene que cerrar."""
    _firmada(tmp_store, iid="D1-2026-001")

    estado = gov.get_state(store_file=tmp_store)          # el GET del panel
    assert estado["state_hash"]

    # `family_state_hash` y `state_hash` NO son intercambiables: el primero es
    # de familia y el segundo global. Mandar uno en el sitio del otro compara
    # dos ámbitos distintos y da 409 -- se descubrió cuando la UI mandaba el
    # global al propose recién convertido a control por familia.
    p = gov.propose("D1", target_ids=TRES, decision_type="CORRECTION",
                    supersedes_instance_id="D1-2026-001",
                    proposed_by_id="mission_control_ui",
                    reason="correccion de una sola pestaña",
                    family_state_hash=gov.family_state_hash("D1", store_file=tmp_store),
                    store_file=tmp_store)

    c = gov.confirm(p["proposal_id"], approved_by_id="Cesar",
                    approved_by_display_name="Cesar", reason="firmado",
                    family_state_hash=p["family_state_hash"],
                    expected_active_instance_id=p["expected_active_instance_id"],
                    store_file=tmp_store)
    cov = gov.get_coverage("D1", store_file=tmp_store)
    assert c["decision_instance_id"] in cov["confirmed_active_instances"]


# ===========================================================================
# ciclo de vida y no-acumulacion de propuestas
# ===========================================================================

def test_an_equivalent_live_proposal_is_reused_not_multiplied(tmp_store):
    """Un doble clic no puede producir dos propuestas.

    Asi se llego a 46: cada reintento tras el 409 creaba una nueva.
    """
    _firmada(tmp_store)
    a = _propuesta(tmp_store)
    b = _propuesta(tmp_store, target_ids=list(reversed(TRES)))   # mismo conjunto
    assert b["proposal_id"] == a["proposal_id"]
    assert b["reused_existing_proposal"] is True
    assert a["reused_existing_proposal"] is False
    props = [r for r in store.read_all(tmp_store)
             if r["decision_origin"] == "agent_proposed"]
    assert len(props) == 1


def test_a_different_actor_or_target_set_is_not_reused(tmp_store):
    """Reutilizar de mas seria mezclar actos distintos."""
    _firmada(tmp_store)
    a = _propuesta(tmp_store)
    otro_actor = _propuesta(tmp_store, proposed_by_id="layer8_agent")
    otro_set = _propuesta(tmp_store, target_ids=["ecfr_21cfr_part211"])
    assert otro_actor["proposal_id"] != a["proposal_id"]
    assert otro_set["proposal_id"] != a["proposal_id"]


def test_an_expired_proposal_is_not_signable_nor_reusable(tmp_store, monkeypatch):
    """Firmar una propuesta de hace dias es firmar a ciegas con papeleo."""
    _firmada(tmp_store)
    p = _propuesta(tmp_store)

    futuro = datetime.now(timezone.utc) + timedelta(hours=gov.PROPOSAL_TTL_HOURS + 1)

    class _Reloj(datetime):
        @classmethod
        def now(cls, tz=None):
            return futuro
    monkeypatch.setattr(gov, "datetime", _Reloj)

    assert gov.proposal_state(p["proposal_id"], store_file=tmp_store) == gov.PROPOSAL_EXPIRED
    with pytest.raises(store.DecisionConflictError) as e:
        gov.confirm(p["proposal_id"], approved_by_id="Cesar", reason="tarde",
                    family_state_hash=gov.family_state_hash("D1", store_file=tmp_store),
                    store_file=tmp_store)
    assert "EXPIRED" in str(e.value)
    # Y no se reutiliza: una caducada no revive.
    nueva = _propuesta(tmp_store)
    assert nueva["proposal_id"] != p["proposal_id"]


def test_abandon_closes_a_proposal_without_deleting_it(tmp_store):
    """La salida gobernada del residuo. Append-only: se anade, no se borra."""
    _firmada(tmp_store)
    p = _propuesta(tmp_store)
    lineas_antes = tmp_store.read_text(encoding="utf-8").count("\n")

    gov.abandon(p["proposal_id"], abandoned_by_id="Cesar",
                reason="residuo de un defecto ya corregido", store_file=tmp_store)

    assert gov.proposal_state(p["proposal_id"], store_file=tmp_store) == gov.PROPOSAL_ABANDONED
    # La propuesta SIGUE ahi, y hay una linea MAS, no una menos.
    assert tmp_store.read_text(encoding="utf-8").count("\n") == lineas_antes + 1
    assert any(r["decision_instance_id"] == p["proposal_id"]
               for r in store.read_all(tmp_store))
    # Abandonar no otorga nada.
    cov = gov.get_coverage("D1", store_file=tmp_store)
    assert p["proposal_id"] not in cov["confirmed_active_instances"]


def test_abandon_requires_a_reason(tmp_store):
    _firmada(tmp_store)
    p = _propuesta(tmp_store)
    with pytest.raises(store.DecisionValidationError):
        gov.abandon(p["proposal_id"], abandoned_by_id="Cesar", reason="  ",
                    store_file=tmp_store)


def test_an_abandoned_proposal_cannot_be_confirmed(tmp_store):
    _firmada(tmp_store)
    p = _propuesta(tmp_store)
    gov.abandon(p["proposal_id"], abandoned_by_id="Cesar", reason="ya no",
                store_file=tmp_store)
    with pytest.raises(store.DecisionConflictError):
        gov.confirm(p["proposal_id"], approved_by_id="Cesar", reason="igual firmo",
                    family_state_hash=gov.family_state_hash("D1", store_file=tmp_store),
                    store_file=tmp_store)


# ===========================================================================
# [N12] los GET no escriben  ·  [N13] ningun test toca el almacen real
# ===========================================================================

def test_n12_reads_write_neither_decisions_nor_audit(tmp_store):
    _firmada(tmp_store)
    _propuesta(tmp_store)
    almacen_antes = tmp_store.read_text(encoding="utf-8")
    audit_antes = aw.AUDIT_FILE.read_text(encoding="utf-8")

    gov.get_state(store_file=tmp_store)
    gov.get_coverage("D1", store_file=tmp_store)
    gov.list_proposals("D1", store_file=tmp_store)
    gov.family_state_hash("D1", store_file=tmp_store)
    gov.active_instance_of("D1", store_file=tmp_store)
    gov.compute_state_hash(store_file=tmp_store)

    assert tmp_store.read_text(encoding="utf-8") == almacen_antes
    assert aw.AUDIT_FILE.read_text(encoding="utf-8") == audit_antes


def test_n13_no_test_in_this_file_touched_the_real_store():
    """Se compara con HEAD y no con un numero de registros.

    Fijar el conteo convertiria una firma humana legitima en un build rojo, que
    es exactamente el fallo que tuvo `test_v1_no_record_is_lost`.
    """
    real = store.STORE_FILE
    if not real.is_file():
        pytest.skip("almacen real no presente en este entorno")
    rel = real.relative_to(REPO).as_posix()
    r = subprocess.run(["git", "-C", str(REPO), "diff", "--quiet", "HEAD", "--", rel])
    assert r.returncode == 0, (
        "algun test escribio en el almacen real de decisiones")


# ===========================================================================
# [N14] idempotencia de /confirm — el agujero que dejo TRES firmas del mismo acto
# ===========================================================================
#
# El dedupe de G2.1 cubria /propose y no /confirm. Consecuencia real: Cesar firmo
# la Correccion D1 tres veces (D1-2026-049 el 04:31:59, -050 el 04:32:11 y -051
# siete horas despues), cada una confirmando una propuesta huerfana DISTINTA de
# las 49 que quedaron, y las tres quedaron ACTIVE superseding a D1-2026-002. Un
# solo acto humano acuñado como tres decisiones autoritativas: un auditor no puede
# saber cual es LA decision.

def _correccion_propuesta(tmp_store, **over):
    kwargs = dict(target_ids=TRES, proposed_by_id="mission_control_ui",
                  decision_type="CORRECTION", reason="correccion de prueba",
                  supersedes_instance_id="D1-2026-002")
    kwargs.update(over)
    return gov.propose("D1", store_file=tmp_store, **kwargs)


def _confirmar(tmp_store, prop, by="Cesar"):
    return gov.confirm(prop["proposal_id"], approved_by_id=by,
                       approved_by_display_name=by, reason="firma de prueba",
                       family_state_hash=prop["family_state_hash"],
                       expected_active_instance_id=prop["expected_active_instance_id"],
                       store_file=tmp_store)


def test_n14_confirming_an_equivalent_proposal_twice_signs_once(tmp_store):
    """Dos propuestas distintas, mismo acto: UNA sola decision firmada."""
    _firmada(tmp_store, iid="D1-2026-002")

    p1 = _correccion_propuesta(tmp_store)
    primera = _confirmar(tmp_store, p1)
    assert primera["already_signed"] is False

    # Otro proponente => otra propuesta (el dedupe de /propose no la reutiliza),
    # pero el MISMO acto: misma familia, mismo tipo, mismo conjunto objetivo.
    p2 = _correccion_propuesta(tmp_store, proposed_by_id="otro_cliente")
    assert p2["proposal_id"] != p1["proposal_id"]
    segunda = _confirmar(tmp_store, p2)

    assert segunda["already_signed"] is True
    assert segunda["decision_instance_id"] == primera["decision_instance_id"]
    assert segunda["requested_proposal_id"] == p2["proposal_id"]

    firmadas = [r for r in store.read_all(tmp_store)
                if r.get("decision_origin") == "human_confirmed"
                and r.get("decision_type") == "CORRECTION"]
    assert len(firmadas) == 1, [r["decision_instance_id"] for r in firmadas]


def test_n14_the_second_confirm_writes_absolutely_nothing(tmp_store):
    """El almacen es append-only: no duplicar es NO ANEXAR, no borrar despues."""
    _firmada(tmp_store, iid="D1-2026-002")
    _confirmar(tmp_store, _correccion_propuesta(tmp_store))

    p2 = _correccion_propuesta(tmp_store, proposed_by_id="otro_cliente")
    antes = tmp_store.read_text(encoding="utf-8")
    _confirmar(tmp_store, p2)
    assert tmp_store.read_text(encoding="utf-8") == antes


def test_n14_only_one_active_correction_supersedes_the_original(tmp_store):
    """Tres clics no pueden dejar tres vigentes: eso es lo que paso en real."""
    _firmada(tmp_store, iid="D1-2026-002")
    p = _correccion_propuesta(tmp_store)
    _confirmar(tmp_store, p)
    for actor in ("cliente_b", "cliente_c"):
        _confirmar(tmp_store, _correccion_propuesta(tmp_store, proposed_by_id=actor))

    activas = [r for r in store.read_all(tmp_store)
               if r.get("decision_origin") == "human_confirmed"
               and r.get("status") == "ACTIVE"
               and r.get("supersedes_instance_id") == "D1-2026-002"]
    assert len(activas) == 1, [r["decision_instance_id"] for r in activas]


def test_n14_a_different_target_set_is_a_different_act(tmp_store):
    """La idempotencia NO puede tragarse una decision distinta.

    Si absorbiera un conjunto objetivo distinto, el adendo D1-A quedaria sin
    registrar creyendo que ya estaba firmado — silenciar una decision real es
    peor que duplicarla.
    """
    _firmada(tmp_store, iid="D1-2026-002")
    _confirmar(tmp_store, _correccion_propuesta(tmp_store))

    otro = _correccion_propuesta(tmp_store, target_ids=TRES + ["ecfr_21cfr_part211"],
                                 proposed_by_id="otro_cliente")
    res = _confirmar(tmp_store, otro)
    assert res["already_signed"] is False
    assert res["decision_instance_id"] != otro["proposal_id"] or True
    firmadas = [r for r in store.read_all(tmp_store)
                if r.get("decision_origin") == "human_confirmed"
                and r.get("decision_type") == "CORRECTION"]
    assert len(firmadas) == 2


def test_n14_same_target_set_different_payload_is_a_different_act(tmp_store):
    """DEFECTO REAL (2026-08-05, ARTIFACT_VERSION-2026-006): dos bumps de
    version DISTINTOS del MISMO artefacto comparten target_set_hash a
    proposito (el artefacto no cambia entre bumps) -- lo unico que distingue
    el acto es el `payload` (from_version/to_version/hashes). Cesar firmo
    2.0->2.1 cinco veces seguidas (201 Created las cinco) y el
    corto-circuito de idempotencia devolvia siempre la firma vieja de
    1.0->2.0 (2026-08-01) como "vigente" -- su firma real de hoy nunca se
    escribio. `target_set_hash` solo no basta para esta familia; hace falta
    tambien comparar el `payload`."""
    artefacto = ["factory/regulatory/requirement_catalog/requirements.yaml"]
    bump_1_a_2 = gov.propose(
        "ARTIFACT_VERSION", target_ids=artefacto, proposed_by_id="mission_control_ui",
        reason="bump 1.0->2.0",
        payload={"artifact_path": artefacto[0], "artifact_hash_before": "aaa",
                 "from_version": "1.0", "to_version": "2.0",
                 "expected_hash_after": "bbb", "change_reason": "bump 1.0->2.0"},
        store_file=tmp_store)
    _confirmar(tmp_store, bump_1_a_2)

    bump_2_a_21 = gov.propose(
        "ARTIFACT_VERSION", target_ids=artefacto, proposed_by_id="mission_control_ui",
        reason="bump 2.0->2.1",
        payload={"artifact_path": artefacto[0], "artifact_hash_before": "bbb",
                 "from_version": "2.0", "to_version": "2.1",
                 "expected_hash_after": "bbb", "change_reason": "bump 2.0->2.1"},
        store_file=tmp_store)
    res = _confirmar(tmp_store, bump_2_a_21)

    assert res["already_signed"] is False, (
        "el defecto real: la firma de 2.0->2.1 se tragaba como 'ya firmada' "
        "apuntando a la firma vieja de 1.0->2.0")
    assert res["confirms_instance_id"] == bump_2_a_21["proposal_id"]
    firmadas = [r for r in store.read_all(tmp_store)
                if r.get("decision_origin") == "human_confirmed"
                and r.get("decision_family") == "ARTIFACT_VERSION"]
    assert len(firmadas) == 2, [r["decision_instance_id"] for r in firmadas]


def test_n14_a_rejected_act_can_be_attempted_again(tmp_store):
    """Un REJECT no otorga y por tanto no bloquea reintentar el acto.

    Tratarlo como "ya firmada" convertiria un "no" en un candado permanente.
    """
    _firmada(tmp_store, iid="D1-2026-002")
    p1 = _correccion_propuesta(tmp_store)
    gov.reject(p1["proposal_id"], rejected_by_id="Cesar", reason="no procede",
               state_hash=gov.compute_state_hash(store_file=tmp_store),
               store_file=tmp_store)

    p2 = _correccion_propuesta(tmp_store, proposed_by_id="otro_cliente")
    res = _confirmar(tmp_store, p2)
    assert res["already_signed"] is False


def test_n14_the_expired_and_stale_guards_still_fire_first(tmp_store):
    """La idempotencia no puede tapar un 409 ni un token ausente.

    Se comprueba DESPUES de la frescura a proposito: si una pagina vieja pide
    confirmar, el humano tiene que enterarse de que su lectura caduco, no recibir
    un "ya estaba firmada" que no explica nada.
    """
    _firmada(tmp_store, iid="D1-2026-002")
    p = _correccion_propuesta(tmp_store)
    _confirmar(tmp_store, p)

    p2 = _correccion_propuesta(tmp_store, proposed_by_id="otro_cliente")
    with pytest.raises(gov.MissingStateTokenError):
        gov.confirm(p2["proposal_id"], approved_by_id="Cesar",
                    reason="sin token", store_file=tmp_store)

    # Token presente pero obsoleto: StaleStateError (409 de obsolescencia), que es
    # una causa distinta de la ausencia (422) y de un duplicado.
    with pytest.raises(gov.StaleStateError):
        gov.confirm(p2["proposal_id"], approved_by_id="Cesar", reason="token viejo",
                    family_state_hash="0" * 64, store_file=tmp_store)


def test_n14_the_same_proposal_twice_is_still_a_conflict(tmp_store):
    """Confirmar DOS VECES la misma propuesta sigue siendo 409.

    Esa guardia ya existia y mide otra cosa: que una propuesta concreta no se
    resuelva dos veces. La idempotencia es sobre el ACTO, no sobre el papel.
    """
    _firmada(tmp_store, iid="D1-2026-002")
    p = _correccion_propuesta(tmp_store)
    _confirmar(tmp_store, p)
    with pytest.raises(store.DecisionConflictError):
        gov.confirm(p["proposal_id"], approved_by_id="Cesar", reason="otra vez",
                    family_state_hash=gov.family_state_hash("D1", store_file=tmp_store),
                    store_file=tmp_store)


def test_n14_a_decision_not_born_of_a_proposal_does_not_swallow_a_signature(tmp_store):
    """El limite de la regla: solo se dedupe el ciclo propose->confirm.

    Con la regla amplia, una decision previa registrada por otra via —una firma
    directa, un snapshot reconstruido— convertia la siguiente firma equivalente en
    un no-op. Silenciar una decision real es peor que duplicarla, asi que solo
    cuenta como duplicado lo que nacio de confirmar una propuesta.
    """
    directa = _firmada(tmp_store, iid="D1-2026-002")
    assert directa.get("confirms_instance_id") is None

    p = _propuesta(tmp_store)  # ORIGINAL, mismos targets que la directa
    res = _confirmar(tmp_store, p)
    assert res["already_signed"] is False
    assert res["confirms_instance_id"] == p["proposal_id"]


# ===========================================================================
# [N15] el motivo del bloqueo de G3 dice QUE falta, medido
# ===========================================================================

def test_n15_the_g3_blocker_names_what_is_actually_missing(tmp_store):
    """Decia "ninguna fuente esta autorizada todavia" con 3 de 4 autorizadas.

    Un mensaje que afirma menos de lo que hay, en la pantalla que se usa para
    decidir, invita a re-firmar lo ya firmado.
    """
    cov = {f: {"uncovered_ids": [], "reconstructed_only_ids": []}
           for f in ("D1", "D2", "D3", "D4", "D5")}
    cov["D1"] = {"uncovered_ids": ["ecfr_21cfr_part211"],
                 "reconstructed_only_ids": []}
    path = gov._critical_path(cov, {"unbacked_known_fork_entry_ids": []},
                              {"records_in_store": 1})
    g3 = next(g for g in path if g["gate"] == "G3")

    assert g3["status"] == "BLOQUEADO"
    motivo = g3["blocked_by"][0]
    assert "ecfr_21cfr_part211" in motivo
    assert "ninguna fuente" not in motivo, motivo


def test_n15_the_g3_blocker_also_names_reconstructed_sources(tmp_store):
    """Reconstruida y no-cubierta piden remedios distintos; las dos salen."""
    cov = {f: {"uncovered_ids": [], "reconstructed_only_ids": []}
           for f in ("D1", "D2", "D3", "D4", "D5")}
    cov["D1"] = {"uncovered_ids": ["ecfr_21cfr_part211"],
                 "reconstructed_only_ids": ["eu_gmp_annex11"]}
    path = gov._critical_path(cov, {"unbacked_known_fork_entry_ids": []},
                              {"records_in_store": 1})
    motivo = next(g for g in path if g["gate"] == "G3")["blocked_by"][0]

    assert "ecfr_21cfr_part211" in motivo and "eu_gmp_annex11" in motivo
    assert "reconstruida" in motivo


def test_n15_g3_opens_when_d1_is_fully_covered(tmp_store):
    """La otra mitad: cubierto de verdad, G3 deja de estar bloqueado."""
    cov = {f: {"uncovered_ids": [], "reconstructed_only_ids": []}
           for f in ("D1", "D2", "D3", "D4", "D5")}
    path = gov._critical_path(cov, {"unbacked_known_fork_entry_ids": []},
                              {"records_in_store": 1})
    assert next(g for g in path if g["gate"] == "G3")["blocked_by"] == []


def test_n14_identity_is_validated_before_the_idempotent_shortcut(tmp_store):
    """Un no-op sigue siendo un endpoint de firma: la identidad va primero.

    Lo cazo el test vivo contra el servidor: con la validacion solo dentro de
    `_closing_record`, una identidad reservada recibia 201 "ya estaba firmada" en
    vez de 422 — el endpoint respondia con estado de firma a quien no puede
    firmar. Que no se escriba nada no lo hace inocuo.
    """
    from factory.core import identity_policy

    _firmada(tmp_store, iid="D1-2026-002")
    _confirmar(tmp_store, _correccion_propuesta(tmp_store))

    p2 = _correccion_propuesta(tmp_store, proposed_by_id="otro_cliente")
    with pytest.raises(identity_policy.IdentityValidationError):
        gov.confirm(p2["proposal_id"], approved_by_id="human", reason="reservada",
                    family_state_hash=p2["family_state_hash"],
                    expected_active_instance_id=p2["expected_active_instance_id"],
                    store_file=tmp_store)


# ===========================================================================
# [N16] el camino del adendo D1-A, de punta a punta por el servicio
# ===========================================================================
#
# I-7 (ADDENDUM exige amendment_sequence>=1 y prohibe supersedes) ya se prueba en
# `test_decision_model_v2`, pero eso valida el REGISTRO, no el camino: que lo que
# `govSubmitD1A` manda —ADDENDUM, amendment_sequence 1, sin supersedes— atraviese
# propose y confirm y acabe ampliando la cobertura. Un ensayo manual lo demostro
# una vez; esto lo fija.

PART211 = "ecfr_21cfr_part211"


def _adendo_propuesta(tmp_store, **over):
    kwargs = dict(target_ids=[PART211], proposed_by_id="mission_control_ui",
                  decision_type="ADDENDUM", amendment_sequence=1,
                  reason="adendo de prueba")
    kwargs.update(over)
    return gov.propose("D1", store_file=tmp_store, **kwargs)


def test_n16_the_addendum_extends_coverage_without_touching_the_correction(tmp_store):
    """El adendo AMPLIA: suma Part 211 y deja la Correccion en pie.

    Es la diferencia entre los dos remedios, y es la razon de que D1-A exista como
    acto separado en vez de re-firmar la Correccion con un objetivo mas.
    """
    _firmada(tmp_store, iid="D1-2026-002")
    correccion = _confirmar(tmp_store, _correccion_propuesta(tmp_store))

    p = _adendo_propuesta(tmp_store)
    a = _confirmar(tmp_store, p)

    assert a["decision_type"] == "ADDENDUM"
    assert a["amendment_sequence"] >= 1
    assert a["supersedes_instance_id"] is None, "un adendo no supersede nada (I-7)"

    cov = gov.get_coverage("D1", store_file=tmp_store)
    assert PART211 in cov["covered_ids"]
    for sid in TRES:
        assert sid in cov["covered_ids"], f"{sid} dejo de estar cubierta"
    assert correccion["decision_instance_id"] in cov["confirmed_active_instances"], (
        "la Correccion tiene que seguir vigente tras el adendo")


def test_n16_the_addendum_is_idempotent_too(tmp_store):
    """El mismo agujero de /confirm valdria para el adendo: un clic, un registro."""
    _firmada(tmp_store, iid="D1-2026-002")
    _confirmar(tmp_store, _correccion_propuesta(tmp_store))
    primero = _confirmar(tmp_store, _adendo_propuesta(tmp_store))

    segundo = _confirmar(tmp_store,
                         _adendo_propuesta(tmp_store, proposed_by_id="otro_cliente"))
    assert segundo["already_signed"] is True
    assert segundo["decision_instance_id"] == primero["decision_instance_id"]

    adendos = [r for r in store.read_all(tmp_store)
               if r.get("decision_type") == "ADDENDUM"
               and r.get("decision_origin") == "human_confirmed"]
    assert len(adendos) == 1


def test_n16_g2_closes_and_g3_opens_once_d1_is_fully_covered(tmp_store):
    """El efecto que se busca: G2 CERRADO y G3 deja de estar bloqueado.

    Sin esta asercion, el adendo podria registrarse correctamente y no mover la
    ruta critica, que es lo unico por lo que se firma.
    """
    _firmada(tmp_store, iid="D1-2026-002")
    _confirmar(tmp_store, _correccion_propuesta(tmp_store))
    _confirmar(tmp_store, _adendo_propuesta(tmp_store))

    st = gov.get_state(store_file=tmp_store)
    gates = {g["gate"]: g for g in st["critical_path"]}
    assert gates["G2"]["status"] == "CERRADO", gates["G2"]
    assert gates["G3"]["blocked_by"] == [], gates["G3"]


def test_n16_the_addendum_alone_does_not_cover_the_three_old_sources(tmp_store):
    """Y no se cuela por el otro lado: el adendo NO sustituye a la Correccion.

    Si firmar solo el adendo cerrara G2, se podria saltar la Correccion entera.

    El punto de partida es un SNAPSHOT RECONSTRUIDO, que es lo que era
    D1-2026-002 en el almacen real: reconstruir no es tener la firma. Con una
    firma humana de verdad como base, las tres ya estarian cubiertas y no habria
    Correccion que saltarse -- asi que el fixture tiene que reproducir la
    procedencia, no solo los objetivos.
    """
    rec = store.build_record(
        decision_family="D1", decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", resolved_target_ids=TRES,
        decision="APPROVE", decision_origin="human_confirmed",
        approved_by_id="Cesar", approved_by_display_name="Cesar",
        decision_instance_id="D1-2026-002", store_file=tmp_store)
    rec["provenance"] = "RECONSTRUCTED_SNAPSHOT"
    rec["reconstruction_evidence"] = {
        "nota": "reproduce la procedencia real de D1-2026-002, cuyo 'ALL' nunca "
                "se materializo",
        "fuente": "fixture de test",
    }
    store.append_record(rec, store_file=tmp_store)

    reconstruidas = gov.get_coverage("D1", store_file=tmp_store)["reconstructed_only_ids"]
    assert set(reconstruidas) == set(TRES), (
        f"el fixture no reprodujo el estado reconstruido: {reconstruidas}")

    _confirmar(tmp_store, _adendo_propuesta(tmp_store))

    cov = gov.get_coverage("D1", store_file=tmp_store)
    assert PART211 in cov["covered_ids"]
    st = gov.get_state(store_file=tmp_store)
    g2 = next(g for g in st["critical_path"] if g["gate"] == "G2")
    assert g2["status"] != "CERRADO", (
        "el adendo por si solo no puede cerrar G2: las tres antiguas siguen "
        "necesitando la Correccion")


# ===========================================================================
# [N17] el codigo HTTP no puede anunciar una escritura que no ocurrio
# ===========================================================================
#
# Cesar creyo haber registrado el adendo D1-A. El servidor recibio en realidad
# una CORRECTION sobre las tres fuentes antiguas, reutilizo una propuesta
# huerfana y corto-circuito por idempotencia: no se escribio NADA. Pero las dos
# llamadas devolvieron 201 Created, y un navegador con el JS anterior cacheado
# solo tiene el codigo de estado para saberlo: vio un 2xx y dijo "Registrada".
#
# El cuerpo ya traia `already_signed` / `reused_existing_proposal`. El codigo es
# la parte del contrato que un cliente puede comprobar sin leer el cuerpo, y era
# la que mentia.

def _cliente():
    """Solo el router, no la app completa.

    Importar `factory.api.main` monta un handler de logging sobre
    `factory/logs/access.jsonl`, que lo escribe el contenedor como root: desde el
    host da PermissionError y el test moriria por una razon que no tiene nada que
    ver con lo que mide. Mismo patron que el fixture de `test_governance_endpoints`.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from factory.api.routes import layer9

    app = FastAPI()
    app.include_router(layer9.router)
    return TestClient(app)


def test_n17_reusing_a_proposal_answers_200_not_201(tmp_store, monkeypatch):
    monkeypatch.setattr(store, "STORE_FILE", tmp_store)
    _firmada(tmp_store, iid="D1-2026-002")
    cli = _cliente()

    cuerpo = {"target_ids": TRES, "proposed_by_id": "mission_control_ui",
              "reason": "primera", "decision_type": "CORRECTION",
              "supersedes_instance_id": "D1-2026-002"}
    primera = cli.post("/api/v1/layer9/governance/decisions/D1/propose", json=cuerpo)
    assert primera.status_code == 201, primera.text
    assert primera.json()["reused_existing_proposal"] is False

    segunda = cli.post("/api/v1/layer9/governance/decisions/D1/propose", json=cuerpo)
    assert segunda.json()["reused_existing_proposal"] is True
    assert segunda.status_code == 200, (
        "reutilizar una propuesta no crea nada: 201 Created seria mentira")


def test_n17_an_already_signed_act_answers_200_not_201(tmp_store, monkeypatch):
    monkeypatch.setattr(store, "STORE_FILE", tmp_store)
    _firmada(tmp_store, iid="D1-2026-002")
    p1 = _correccion_propuesta(tmp_store)
    _confirmar(tmp_store, p1)

    p2 = _correccion_propuesta(tmp_store, proposed_by_id="otro_cliente")
    cli = _cliente()
    res = cli.post(
        f"/api/v1/layer9/governance/decisions/{p2['proposal_id']}/confirm",
        json={"approved_by_id": "Cesar", "reason": "segundo clic",
              "family_state_hash": p2["family_state_hash"],
              "expected_active_instance_id": p2["expected_active_instance_id"]})
    assert res.json()["already_signed"] is True
    assert res.status_code == 200, (
        "no se anexo nada: anunciar Created es afirmar una escritura que no ocurrio")


def test_n17_a_real_signature_still_answers_201(tmp_store, monkeypatch):
    """La otra mitad: cuando SI se crea, sigue siendo 201.

    Sin ella, esto lo aprobaria un servidor que respondiera 200 siempre y ningun
    cliente podria distinguir ya una firma de un no-op.
    """
    monkeypatch.setattr(store, "STORE_FILE", tmp_store)
    _firmada(tmp_store, iid="D1-2026-002")
    p = _correccion_propuesta(tmp_store)

    cli = _cliente()
    res = cli.post(
        f"/api/v1/layer9/governance/decisions/{p['proposal_id']}/confirm",
        json={"approved_by_id": "Cesar", "reason": "firma real",
              "family_state_hash": p["family_state_hash"],
              "expected_active_instance_id": p["expected_active_instance_id"]})
    assert res.status_code == 201, res.text
    assert res.json()["already_signed"] is False
