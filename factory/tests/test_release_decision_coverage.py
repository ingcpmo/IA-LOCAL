"""G15_decision_coverage + bloqueo de release — W5 V2 G1.11 (consumidor C-5).

Cierra el ultimo de los cinco consumidores de DECISION_SCOPE_RESOLVER_SPEC.md
§6. Lo que se prueba aqui no es que el gate "funcione", sino que NO se pueda
liberar material regulatorio que nadie firmo -- que es el estado en que la
fabrica llevaba desde el principio y que ningun gate detectaba (ver
GOVERNANCE_STATE_AUDIT.md §6: "ningun gate resuelve un decision_id").

Los tests construyen cobertura REAL contra los registries reales en vez de
mockear el resolver: un mock del resolver aqui probaria el mock.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.core import decision_scope_resolver as resolver
from factory.core import quality_gate_runner as qgr
from factory.core import release_manager as rm
from factory.core.audit_writer import chain_break_entry_ids, _compute_entry_hash
from factory.services import decision_store_v2 as store

GOVERNED = ("D1", "D2", "D3", "D4", "D5")


# ---------------------------------------------------------------------------
# Utilidades: almacen de decisiones y cadena de auditoria sinteticos
# ---------------------------------------------------------------------------

def _write_store(path: Path, records) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path


def _registry_ids(family: str) -> list[str]:
    """Ids reales que hoy tiene el registry de la familia, o [] si no tiene."""
    try:
        ids, _ = store.resolve_all_snapshot(family)
        return list(ids)
    except Exception:
        return []


def _approve(family: str, target_ids, *, instance_id: str) -> dict:
    return store.build_record(
        decision_family=family,
        decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST",
        resolved_target_ids=list(target_ids),
        decision="APPROVE",
        decision_origin="human_confirmed",
        approved_by_id="Cesar",
        approved_by_display_name="Cesar",
        decision_instance_id=instance_id,
    )


@pytest.fixture()
def fully_covered_store(tmp_path) -> Path:
    """Almacen que cubre TODOS los ids reales de D1..D5 con firma humana.

    Es el unico estado en el que G15 puede pasar. Construirlo explicitamente
    deja ver cuanto hace falta firmar de verdad.
    """
    records = []
    for i, family in enumerate(GOVERNED, start=1):
        ids = _registry_ids(family)
        if ids:
            records.append(_approve(family, ids, instance_id=f"{family}-2026-{i:03d}"))
    return _write_store(tmp_path / "decisions_v2.jsonl", records)


def _chain(entries: list[dict], path: Path, *, break_at: int | None = None) -> Path:
    """Escribe una cadena de auditoria valida, opcionalmente rota en un indice.

    La ruptura se hace SOLO en `prev_entry_hash` y se rehashea la entrada, que
    es exactamente la forma del fork real: enlace roto, contenido autentico.
    """
    prev = "GENESIS"
    lines = []
    for i, e in enumerate(entries):
        body = dict(e)
        body["prev_entry_hash"] = "sha256:" + "0" * 64 if i == break_at else prev
        h = f"sha256:{_compute_entry_hash(body)}"
        body["entry_hash"] = h
        prev = h
        lines.append(json.dumps(body, separators=(",", ":"), ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _entries(n: int) -> list[dict]:
    return [
        {"timestamp": f"2026-06-15T13:5{i}:00+00:00", "entry_id": f"evt-{i}",
         "event_type": "gates_executed", "project_id": "p", "data": {}}
        for i in range(n)
    ]


@pytest.fixture()
def clean_chain(tmp_path) -> Path:
    return _chain(_entries(4), tmp_path / "clean.jsonl")


@pytest.fixture()
def forked_chain(tmp_path) -> Path:
    return _chain(_entries(4), tmp_path / "forked.jsonl", break_at=2)


# ===========================================================================
# El estado real de hoy
# ===========================================================================

def test_gate_blocks_today_because_nothing_is_covered():
    """Sin inyectar nada: G15 sobre el almacen y la cadena REALES.

    Debe FALLAR. Si algun dia este test empieza a pasar sin que se haya
    registrado la Correccion D1 de G2, es que alguien aflojo el gate.
    """
    gate = qgr.g15_decision_coverage()
    assert gate["gate"] == "G15"
    assert gate["status"] == "FAIL"
    assert "BLOCKED" in gate["evidence"]


def test_today_the_block_is_indeterminacy_not_denial():
    """Hoy el almacen v2 NO EXISTE: nada se ha migrado (la migracion es G2).

    El gate debe decir NOT_DETERMINED, no "cubierto" ni "denegado". Es la
    distincion que este trabajo entero defiende: no saber no es saber que no,
    y ninguna de las dos es saber que si. Cuando G2 cree el almacen, este test
    tendra que cambiar -- y ese cambio es el registro de que algo se migro.
    """
    gate = qgr.g15_decision_coverage()
    assert "NOT_DETERMINED" in gate["evidence"]
    assert "indeterminada" in gate["evidence"]


def test_the_real_fork_blocks_and_is_named():
    """La ruptura real de la cadena bloquea, y el gate dice CUAL es.

    `ab689c7c-…` es el fork localizado en AUDIT_FORK_REMEDIATION_SPEC.md §2.
    Un humano solo puede firmar una excepcion sobre un id concreto.
    """
    gate = qgr.g15_decision_coverage()
    assert "ab689c7c-3e0a-4c77-936b-152851f51a30" in gate["evidence"]


def test_part211_appears_by_name_once_the_store_exists(tmp_path, clean_chain):
    """El gate no dice "falta cobertura": dice QUE falta.

    Con un almacen que cubre las tres fuentes originales pero no Part 211 --
    exactamente el estado del 2026-07-29 -- el id que sobra tiene que salir
    listado. Es la diferencia entre un gate accionable y uno que solo molesta.
    """
    three_originals = [s for s in _registry_ids("D1") if s != "ecfr_21cfr_part211"]
    partial = _write_store(
        tmp_path / "sin_part211.jsonl",
        [_approve("D1", three_originals, instance_id="D1-2026-001")])

    gate = qgr.g15_decision_coverage(
        decision_store_file=partial, audit_file=clean_chain)
    assert gate["status"] == "FAIL"
    assert "ecfr_21cfr_part211" in gate["evidence"]


# ===========================================================================
# Cobertura: lo que hace pasar y lo que no
# ===========================================================================

def test_gate_passes_only_with_full_coverage_and_clean_chain(
        fully_covered_store, clean_chain):
    gate = qgr.g15_decision_coverage(
        decision_store_file=fully_covered_store, audit_file=clean_chain)
    assert gate["status"] == "PASS", gate["evidence"]
    assert "sin rupturas de cadena" in gate["evidence"]


def test_a_single_uncovered_id_blocks_the_whole_release(
        tmp_path, fully_covered_store, clean_chain):
    """Cobertura completa MENOS una fuente => BLOCKED.

    No hay release parcial: liberar el 99% de un corpus regulatorio no es el
    99% de una release, es una release sin autorizar.
    """
    records = [json.loads(l) for l in fully_covered_store.read_text().splitlines()]
    d1_ids = _registry_ids("D1")
    assert len(d1_ids) > 1, "el registry real debe tener mas de una fuente"
    for r in records:
        if r["decision_family"] == "D1":
            r["resolved_target_ids"] = sorted(d1_ids[:-1])
            r["target_set_hash"] = store.compute_target_set_hash(r["resolved_target_ids"])

    partial = _write_store(tmp_path / "partial.jsonl", records)
    gate = qgr.g15_decision_coverage(
        decision_store_file=partial, audit_file=clean_chain)
    assert gate["status"] == "FAIL"
    assert d1_ids[-1] in gate["evidence"]


def test_agent_signature_never_covers(tmp_path, clean_chain):
    """decision_origin != human_confirmed no cubre nada.

    Es la invariante que impide que la fabrica se autorice a si misma.
    """
    records = []
    for family in GOVERNED:
        ids = _registry_ids(family)
        if not ids:
            continue
        rec = _approve(family, ids, instance_id=f"{family}-2027-001")
        rec["decision_origin"] = "agent_proposed"
        records.append(rec)
    agent_store = _write_store(tmp_path / "agent.jsonl", records)

    gate = qgr.g15_decision_coverage(
        decision_store_file=agent_store, audit_file=clean_chain)
    assert gate["status"] == "FAIL"


def test_reconstructed_snapshot_does_not_authorize(tmp_path, clean_chain):
    """RECONSTRUCTED_SNAPSHOT se declara, pero no cubre.

    Es la distincion de DECISION_SCOPE_RESOLVER_SPEC.md §5: reconstruir lo que
    probablemente se firmo no es lo mismo que tener la firma.
    """
    records = []
    for family in GOVERNED:
        ids = _registry_ids(family)
        if not ids:
            continue
        rec = _approve(family, ids, instance_id=f"{family}-2028-001")
        rec["provenance"] = "RECONSTRUCTED_SNAPSHOT"
        # I-10 del store: una reconstruccion sin evidencia no es ni siquiera
        # un registro valido. Se la damos para probar el escalon siguiente --
        # que aun siendo VALIDA, no autoriza.
        rec["reconstruction_evidence"] = {
            "method": "test fixture", "source": "test_release_decision_coverage",
        }
        records.append(rec)
    recon = _write_store(tmp_path / "recon.jsonl", records)

    gate = qgr.g15_decision_coverage(
        decision_store_file=recon, audit_file=clean_chain)
    assert gate["status"] == "FAIL"
    assert "no autoriza" in gate["evidence"]


def test_unreadable_store_blocks_instead_of_passing(tmp_path, clean_chain):
    """"No se" nunca se reporta como "si"."""
    gate = qgr.g15_decision_coverage(
        decision_store_file=tmp_path / "no_existe.jsonl", audit_file=clean_chain)
    assert gate["status"] == "FAIL"
    assert "indeterminada" in gate["evidence"]


def test_families_without_registry_are_declared_not_silently_covered(
        fully_covered_store, clean_chain):
    """D4/D5 no tienen target_registry: se declaran, no se dan por cubiertas.

    Decir COVERED sobre un conjunto vacio seria fabricar una garantia -- el
    mismo colapso de dimensiones que `drift_determinable` existe para evitar.
    """
    gate = qgr.g15_decision_coverage(
        decision_store_file=fully_covered_store, audit_file=clean_chain)
    for family in ("D4", "D5"):
        assert f"{family}: NO_REGISTRY_TO_COMPARE" in gate["evidence"], gate["evidence"]
        assert f"{family}: COVERED" not in gate["evidence"]


# ===========================================================================
# Fork de auditoria: la segunda condicion de C-5
# ===========================================================================

def test_chain_break_entry_ids_finds_the_break(forked_chain, clean_chain):
    assert chain_break_entry_ids(clean_chain) == ()
    assert chain_break_entry_ids(forked_chain) == ("evt-2",)


def test_chain_break_ids_are_real_on_the_production_chain():
    """La cadena real tiene exactamente un fork, y el helper lo identifica.

    `verify_chain()` ya reportaba "1 ruptura"; lo nuevo es poder decir CUAL,
    que es el unico nivel de detalle sobre el que un humano puede firmar.
    """
    ids = chain_break_entry_ids()
    assert len(ids) == 1, ids
    assert ids[0]


def test_fork_without_signed_exception_blocks(fully_covered_store, forked_chain):
    gate = qgr.g15_decision_coverage(
        decision_store_file=fully_covered_store, audit_file=forked_chain)
    assert gate["status"] == "FAIL"
    assert "evt-2" in gate["evidence"]


def test_fork_with_signed_exception_passes(tmp_path, fully_covered_store, forked_chain):
    """Una excepcion humana sobre ESE evento desbloquea; sobre otro, no."""
    records = [json.loads(l) for l in fully_covered_store.read_text().splitlines()]
    records.append(_approve("AUDIT_EXCEPTION", ["evt-2"], instance_id="AUDIT_EXCEPTION-2026-001"))
    covered = _write_store(tmp_path / "with_exception.jsonl", records)

    gate = qgr.g15_decision_coverage(
        decision_store_file=covered, audit_file=forked_chain)
    assert gate["status"] == "PASS", gate["evidence"]


def test_exception_for_a_different_event_does_not_cover_this_fork(
        tmp_path, fully_covered_store, forked_chain):
    records = [json.loads(l) for l in fully_covered_store.read_text().splitlines()]
    records.append(_approve("AUDIT_EXCEPTION", ["evt-0"], instance_id="AUDIT_EXCEPTION-2026-002"))
    wrong = _write_store(tmp_path / "wrong_exception.jsonl", records)

    gate = qgr.g15_decision_coverage(
        decision_store_file=wrong, audit_file=forked_chain)
    assert gate["status"] == "FAIL"
    assert "evt-2" in gate["evidence"]


# ===========================================================================
# release_manager: el bloqueo de verdad
# ===========================================================================

def test_create_release_is_blocked_and_leaves_nothing_behind(tmp_path, monkeypatch):
    """Una release bloqueada no debe dejar directorio, tar ni meta a medias."""
    releases = tmp_path / "releases"
    monkeypatch.setattr(rm, "RELEASES_DIR", releases)
    events = []
    monkeypatch.setattr(rm, "write_event",
                        lambda et, pid, data: events.append((et, pid, data)))

    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "manifest.yaml").write_text("project: {id: p}\n")

    with pytest.raises(rm.DecisionCoverageBlocked) as exc:
        rm.create_release("proj_x", "v1.0", ws)

    assert "G15_decision_coverage" in str(exc.value)
    assert not releases.exists(), "el bloqueo dejo restos en disco"
    assert [e[0] for e in events] == ["release_blocked"]
    assert events[0][2]["gate"] == "G15"


def test_create_release_proceeds_when_coverage_is_real(
        tmp_path, monkeypatch, fully_covered_store, clean_chain):
    """El bloqueo no es incondicional: con cobertura real, la release se crea."""
    releases = tmp_path / "releases"
    monkeypatch.setattr(rm, "RELEASES_DIR", releases)
    monkeypatch.setattr(rm, "write_event", lambda *a, **k: None)

    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "manifest.yaml").write_text("project: {id: p}\n")

    meta = rm.create_release("proj_x", "v1.0", ws,
                             decision_store_file=fully_covered_store,
                             audit_file=clean_chain)
    assert meta["status"] == "pending_approval"
    assert (releases / "proj_x" / "v1.0" / "release_meta.json").exists()


def test_blocked_release_is_not_a_version_conflict():
    """DecisionCoverageBlocked no es ValueError.

    Si lo fuera, el endpoint lo devolveria como 409 y el llamador creeria que
    se arregla cambiando el numero de version. No se arregla: falta una firma.
    """
    assert not issubclass(rm.DecisionCoverageBlocked, ValueError)


def test_endpoint_returns_423_not_409(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from factory.api.routes import releases as releases_route

    monkeypatch.setattr(rm, "RELEASES_DIR", tmp_path / "releases")
    monkeypatch.setattr(rm, "write_event", lambda *a, **k: None)

    ws = tmp_path / "ws"
    ws.mkdir()

    app = FastAPI()
    app.include_router(releases_route.router)
    client = TestClient(app)

    resp = client.post("/api/v1/releases/proj_x/v1.0",
                       json={"workspace_path": str(ws)})
    assert resp.status_code == 423, resp.text
    assert "G15" in resp.json()["detail"]


# ===========================================================================
# Cableado en el runner
# ===========================================================================

def test_g15_runs_even_when_not_deploying(tmp_path, monkeypatch):
    """G15 no es un requisito de deploy sino del material de construccion.

    Con for_deploy=False, G14 se salta pero G15 NO: un reporte que lo omitiera
    diria "todo bien" sobre un corpus que nadie autorizo.
    """
    monkeypatch.setattr(qgr, "write_event", lambda *a, **k: None)
    ws = tmp_path / "ws"
    ws.mkdir()

    report = qgr.run_all_gates(
        manifest={"project": {"id": "proj_x"}, "deployment": {"api_port": 0}},
        workspace_path=str(ws),
        for_deploy=False,
    )
    gates = {g["gate"]: g for g in report["gates"]}
    assert gates["G14"]["status"] == "SKIPPED"
    assert gates["G15"]["status"] == "FAIL"
