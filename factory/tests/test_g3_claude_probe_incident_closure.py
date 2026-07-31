"""W5V2_FIX_FIRMA_SILENCIOSA §3 -- cierre de gobernanza del incidente
claude_probe (2026-07-30/31).

Verifica, con el resolver REAL sobre un almacen fixture que reproduce los
registros reales (D2-2026-003 fabricada + D2-2026-005 REVOCATION firmada
por Cesar), que la cobertura fabricada NO es resoluble hoy -- no se lee del
estado en vivo del servidor (que puede cambiar), se reconstruye el caso real
como fixture para que esta prueba no dependa de que nadie edite el almacen
de produccion despues.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from factory.core import decision_scope_resolver as resolver
from factory.services import decision_store_v2 as store
from factory.services import governance_service as gov

REQ_211_68B = "21_CFR_211.68(b)"


def _registro(family, dtype, target_ids, *, decision_instance_id, origin,
              approved_by_id=None, supersedes_instance_id=None, amendment_sequence=0,
              confirms_instance_id=None):
    rec = store.build_record(
        decision_family=family, decision_type=dtype, selection_mode="EXPLICIT_LIST",
        resolved_target_ids=target_ids, decision="APPROVE",
        decision_origin=origin, decision_instance_id=decision_instance_id,
        supersedes_instance_id=supersedes_instance_id, amendment_sequence=amendment_sequence,
        proposed_by_id="mission_control_ui" if origin == "agent_proposed" else None,
        approved_by_id=approved_by_id, approved_by_display_name=approved_by_id,
        confirms_instance_id=confirms_instance_id,
        reason="fixture del caso real",
    )
    return rec


@pytest.fixture()
def almacen_del_incidente(tmp_path):
    """Reconstruye D2-2026-002..005 tal como quedaron en el almacen real:
    propose -> confirm fabricado (claude_probe) -> propose revocacion ->
    confirm revocacion (cesar)."""
    path = tmp_path / "decisions_v2.jsonl"
    registros = [
        _registro("D2", "ORIGINAL", [REQ_211_68B], decision_instance_id="D2-2026-002",
                  origin="agent_proposed"),
        _registro("D2", "ORIGINAL", [REQ_211_68B], decision_instance_id="D2-2026-003",
                  origin="human_confirmed", approved_by_id="claude_probe",
                  confirms_instance_id="D2-2026-002"),
        _registro("D2", "REVOCATION", [REQ_211_68B], decision_instance_id="D2-2026-004",
                  origin="agent_proposed", supersedes_instance_id="D2-2026-003"),
        _registro("D2", "REVOCATION", [REQ_211_68B], decision_instance_id="D2-2026-005",
                  origin="human_confirmed", approved_by_id="cesar",
                  supersedes_instance_id="D2-2026-003",
                  confirms_instance_id="D2-2026-004"),
    ]
    with path.open("w", encoding="utf-8") as f:
        for r in registros:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path


def test_d2_2026_003_grants_no_coverage_after_the_real_revocation(almacen_del_incidente):
    """La firma fabricada por el agente, aunque human_confirmed/ACTIVE, no
    resuelve autorizacion: la REVOCATION real de Cesar la retira."""
    res = resolver.resolve("D2", REQ_211_68B, store_file=almacen_del_incidente)
    assert res.authorized is False


def test_coverage_report_lists_the_requirement_as_revoked_not_covered(almacen_del_incidente):
    report = resolver.coverage_report("D2", store_file=almacen_del_incidente)
    assert REQ_211_68B not in report.covered_ids
    assert REQ_211_68B in report.revoked_ids


def test_the_fabricated_confirm_is_never_silently_missing_from_the_record(almacen_del_incidente):
    """El registro fabricado SIGUE existiendo (append-only) -- esta prueba
    no verifica que se borro, sino que sigue ahi y ya no otorga nada."""
    records = store.read_all(almacen_del_incidente)
    fabricado = next(r for r in records if r["decision_instance_id"] == "D2-2026-003")
    assert fabricado["approved_by_id"] == "claude_probe"
    assert fabricado["decision_origin"] == "human_confirmed"
    # sigue "ACTIVE" en el sentido de "no reescrito" -- lo que lo neutraliza
    # es la REVOCATION posterior, no una reescritura de este registro.


def test_a_plain_original_still_cannot_reclaim_a_revoked_target(almacen_del_incidente):
    """Regla dura DELIBERADA y ya testeada en otro lado
    (test_t07_revocation_wins_over_a_later_addendum,
    test_decision_scope_resolver.py): una vez revocado un target, ningun
    ORIGINAL/ADDENDUM nuevo lo recupera -- "retirar autorizacion es la
    operacion segura y domina", a proposito, para que una firma valida no
    se desactive por accidente con un addendum posterior. Este test fija
    que el fix del incidente NO debilito esa regla: un ORIGINAL liso sobre
    21_CFR_211.68(b) sigue sin autorizar tras la revocacion real."""
    prop = gov.propose(
        "D2", target_ids=[REQ_211_68B], decision_type="ORIGINAL",
        proposed_by_id="mission_control_ui", reason="intento ingenuo, sin superseder la revocacion",
        store_file=almacen_del_incidente)
    conf = gov.confirm(
        prop["decision_instance_id"], approved_by_id="cesar",
        approved_by_display_name="Cesar", reason="intento ingenuo",
        family_state_hash=prop["family_state_hash"],
        expected_active_instance_id=prop["expected_active_instance_id"],
        store_file=almacen_del_incidente)
    assert conf["already_signed"] is False  # SI se firma -- el registro existe

    res = resolver.resolve("D2", REQ_211_68B, store_file=almacen_del_incidente)
    assert res.authorized is False, (
        "un ORIGINAL nuevo sin superseder la REVOCATION no debe reclamar "
        "el target -- eso violaria T-07, la regla de que revocar domina")
    assert res.coverage_basis == resolver.REVOKED


def test_confirming_a_real_new_approval_is_not_blocked_by_the_revoked_fabricated_one(
        almacen_del_incidente):
    """DEFECTO REAL cerrado tras el reporte de Cesar: intento firmar la
    aprobacion real de 21_CFR_211.68(b) y el servidor respondio "Ya estaba
    firmada: D2-2026-003 por claude_probe" -- la firma FABRICADA, ya
    revocada. Dos causas, dos fixes:

    (1) `equivalent_signed_decision()` solo miraba `status: ACTIVE` del
    propio registro, que una REVOCATION posterior nunca reescribe (el
    almacen es append-only) -- corregido restando `revoked_ids`.

    (2) Una vez corregido (1), el resolver SIGUE sin autorizar un ORIGINAL
    liso (ver test anterior) por diseño -- T-07. La via gobernada real es
    que la aprobacion nueva SUPERSEDA la REVOCATION misma (CORRECTION),
    afirmando explicitamente que esa revocacion ya cumplio su proposito.
    """
    prop = gov.propose(
        "D2", target_ids=[REQ_211_68B], decision_type="CORRECTION",
        supersedes_instance_id="D2-2026-005",
        proposed_by_id="mission_control_ui",
        reason="la revocacion de D2-2026-003 cumplio su proposito; se re-aprueba de verdad",
        store_file=almacen_del_incidente)
    assert prop["reused_existing_proposal"] is False, (
        "no debe reutilizar ninguna propuesta vieja del incidente")

    conf = gov.confirm(
        prop["decision_instance_id"], approved_by_id="cesar",
        approved_by_display_name="Cesar",
        reason="la revocacion de D2-2026-003 cumplio su proposito; se re-aprueba de verdad",
        family_state_hash=prop["family_state_hash"],
        expected_active_instance_id=prop["expected_active_instance_id"],
        store_file=almacen_del_incidente)

    assert conf["already_signed"] is False, (
        "el defecto real: respondia already_signed apuntando a la firma "
        "fabricada y ya revocada (D2-2026-003), impidiendo la firma real")
    assert conf["approved_by_id"] == "cesar"
    assert conf["decision_instance_id"] != "D2-2026-003"

    res = resolver.resolve("D2", REQ_211_68B, store_file=almacen_del_incidente)
    assert res.authorized is True
    assert conf["decision_instance_id"] in res.covering_instances


def test_equivalent_signed_decision_ignores_a_revoked_candidate(almacen_del_incidente):
    """Prueba directa de la funcion que tenia el defecto, sin pasar por todo
    el ciclo HTTP -- si esto vuelve a fallar, el mensaje senala la funcion
    exacta en vez de un sintoma end-to-end."""
    target_hash = store.compute_target_set_hash([REQ_211_68B])
    assert gov.equivalent_signed_decision(
        "D2", decision_type="ORIGINAL", target_set_hash=target_hash,
        store_file=almacen_del_incidente) is None
