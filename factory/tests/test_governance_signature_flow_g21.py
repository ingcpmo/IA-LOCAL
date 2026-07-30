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
