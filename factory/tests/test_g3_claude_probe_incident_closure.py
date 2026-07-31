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

REQ_211_68B = "21_CFR_211.68(b)"


def _registro(family, dtype, target_ids, *, decision_instance_id, origin,
              approved_by_id=None, supersedes_instance_id=None, amendment_sequence=0):
    rec = store.build_record(
        decision_family=family, decision_type=dtype, selection_mode="EXPLICIT_LIST",
        resolved_target_ids=target_ids, decision="APPROVE",
        decision_origin=origin, decision_instance_id=decision_instance_id,
        supersedes_instance_id=supersedes_instance_id, amendment_sequence=amendment_sequence,
        proposed_by_id="mission_control_ui" if origin == "agent_proposed" else None,
        approved_by_id=approved_by_id, approved_by_display_name=approved_by_id,
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
                  origin="human_confirmed", approved_by_id="claude_probe"),
        _registro("D2", "REVOCATION", [REQ_211_68B], decision_instance_id="D2-2026-004",
                  origin="agent_proposed", supersedes_instance_id="D2-2026-003"),
        _registro("D2", "REVOCATION", [REQ_211_68B], decision_instance_id="D2-2026-005",
                  origin="human_confirmed", approved_by_id="cesar",
                  supersedes_instance_id="D2-2026-003"),
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
