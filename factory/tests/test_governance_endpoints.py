"""Endpoints de gobernanza — W5 V2 G1.15 (GOVERNANCE_UI_SPEC.md §1 y §3).

Se prueban las cinco reglas transversales, que son lo que hace que estos
endpoints sean gobernanza y no un CRUD:

    U-1  GET de solo lectura: jamas escribe auditoria ni promueve nada
    U-2  cada POST emite EXACTAMENTE un evento
    U-3  422 identidad generica, con la funcion UNICA (cierra A-4)
    U-4  409 por duplicacion Y por state_hash obsoleto
    U-5  registrar != ejecutar

TODO test que escriba usa un almacen TEMPORAL. El almacen real
(`decisions_v2.jsonl`) no existe todavia -- la migracion es lo primero de G2 --
y un test que lo creara al pasar dejaria la fabrica en un estado que nadie
firmo. Hay un test al final que congela justo eso.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.core import audit_writer as aw
from factory.core import identity_policy as idp
from factory.services import decision_store_v2 as store
from factory.services import governance_service as gov

REPO = Path(__file__).resolve().parents[2]


def _store_matches_git_head(path: Path) -> bool:
    """El almacen v2 esta TRACKEADO, asi que "intacto" es "igual que HEAD".

    Mejor que fijar un numero de registros: si un test escribe, difiere de HEAD
    y salta; si Cesar firma algo, EL lo commitea y vuelve a coincidir. Un
    `== 14` convertiria una firma humana legitima en un build rojo -- que es
    exactamente lo que paso con `test_v1_no_record_is_lost`.
    """
    import subprocess
    rel = path.relative_to(REPO).as_posix()
    r = subprocess.run(["git", "-C", str(REPO), "diff", "--quiet", "HEAD", "--", rel])
    return r.returncode == 0


@pytest.fixture()
def tmp_store(tmp_path, monkeypatch) -> Path:
    """Almacen de decisiones y cadena de auditoria aislados.

    La auditoria tambien: cada POST emite un evento real, y sin aislarla los
    tests engordarian la cadena de produccion en cada corrida.
    """
    audit = tmp_path / "audit" / "factory_audit.jsonl"
    audit.parent.mkdir(parents=True)
    monkeypatch.setattr(aw, "AUDIT_FILE", audit)
    monkeypatch.setattr(aw, "_last_entry_hash", None)
    path = tmp_path / "decisions_v2.jsonl"
    path.write_text("", encoding="utf-8")
    return path


def _propose(tmp_store, **over) -> dict:
    kwargs = dict(target_ids=["ecfr_21cfr_part211"], proposed_by_id="layer8_agent",
                  reason="propuesta de prueba")
    kwargs.update(over)
    return gov.propose("D1", store_file=tmp_store, **kwargs)


# ===========================================================================
# U-1 -- los GET no escriben nada
# ===========================================================================

def test_u1_get_state_writes_no_audit_event(tmp_store, tmp_path):
    audit = aw.AUDIT_FILE
    antes = audit.read_text(encoding="utf-8") if audit.exists() else ""
    gov.get_state(store_file=tmp_store)
    gov.get_coverage("D1", store_file=tmp_store)
    despues = audit.read_text(encoding="utf-8") if audit.exists() else ""
    assert antes == despues


def test_u1_get_state_does_not_create_the_decision_store(tmp_path, monkeypatch):
    """Leer no puede materializar el almacen."""
    inexistente = tmp_path / "no_existe.jsonl"
    monkeypatch.setattr(aw, "AUDIT_FILE", tmp_path / "a.jsonl")
    gov.get_state(store_file=inexistente)
    assert not inexistente.exists()


def test_u1_state_reports_the_five_families_and_the_audit_dimensions(tmp_store):
    state = gov.get_state(store_file=tmp_store)
    for family in gov.GOVERNED_FAMILIES:
        assert family in state["coverage"]
    # Las dimensiones de G1.14 viajan al panel: NUNCA un booleano de conformidad.
    assert state["audit"]["part11_compliant"] in aw.PART11_VALUES
    assert "content_hash_integrity" in state["audit"]


def test_u5_the_notice_travels_with_the_data_not_only_in_the_html(tmp_store):
    """Un cliente que solo consuma la API ve la misma advertencia que la UI."""
    state = gov.get_state(store_file=tmp_store)
    assert "NO ejecuta" in state["notice"]


def test_the_critical_path_says_why_a_gate_is_blocked(tmp_store):
    """U-7: un bloqueo sin motivo es indistinguible de un fallo."""
    state = gov.get_state(store_file=tmp_store)
    bloqueados = [g for g in state["critical_path"] if g["status"] == "BLOQUEADO"]
    assert bloqueados
    for g in bloqueados:
        assert g["blocked_by"], f"{g['gate']} bloqueado sin decir por que"


# ===========================================================================
# U-2 -- un POST, un evento
# ===========================================================================

def _audit_events() -> list[dict]:
    if not aw.AUDIT_FILE.exists():
        return []
    return [json.loads(l) for l in aw.AUDIT_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_u2_propose_emits_exactly_one_event(tmp_store):
    antes = len(_audit_events())
    _propose(tmp_store)
    assert len(_audit_events()) == antes + 1


def test_u2_confirm_emits_exactly_one_event(tmp_store):
    p = _propose(tmp_store)
    antes = len(_audit_events())
    gov.confirm(p["decision_instance_id"], approved_by_id="Cesar",
                state_hash=gov.compute_state_hash(store_file=tmp_store),
                store_file=tmp_store)
    assert len(_audit_events()) == antes + 1


# ===========================================================================
# U-3 -- identidad, con la funcion UNICA (A-4)
# ===========================================================================

@pytest.mark.parametrize("generica", ["human", "HUMAN", "  agent ", "system",
                                      "admin", "user", "factory", "claude", ""])
def test_u3_generic_identities_cannot_sign(tmp_store, generica):
    """La regla estricta protege la FIRMA, que es el acto que autoriza."""
    p = _propose(tmp_store)
    with pytest.raises(idp.IdentityValidationError):
        gov.confirm(p["decision_instance_id"], approved_by_id=generica,
                    state_hash=gov.compute_state_hash(store_file=tmp_store),
                    store_file=tmp_store)


def test_u3_an_agent_may_propose_under_its_own_name(tmp_store):
    """Proponer y firmar son actos distintos y se validan distinto.

    Exigir nombre humano a quien propone produciria un campo falso o un agente
    haciendose pasar por una persona. Lo que impide que sea un bypass es que
    la propuesta no otorga cobertura, no que mienta sobre su autor.
    """
    from factory.core import decision_scope_resolver as resolver
    rec = _propose(tmp_store, proposed_by_id="layer8_agent")
    assert rec["proposed_by_id"] == "layer8_agent"
    assert rec["decision_origin"] == "agent_proposed"
    assert not resolver.resolve("D1", "ecfr_21cfr_part211",
                                store_file=tmp_store).authorized


def test_u3_an_empty_proposer_is_still_rejected(tmp_store):
    with pytest.raises(idp.IdentityValidationError):
        _propose(tmp_store, proposed_by_id="   ")


def test_u3_there_is_a_single_reserved_identity_list():
    """A-4: habia OCHO conjuntos distintos y no coincidian.

    `admin` se rechazaba al firmar en Capa 9 y se aceptaba al aprobar un
    deployment. Este test congela que las superficies de gobernanza comparten
    una sola lista, por identidad de objeto y no por igualdad de contenido:
    dos listas iguales hoy se separan manana.
    """
    from factory.services import w5_human_decisions as w5
    assert store.RESERVED_IDENTITIES is idp.RESERVED_IDENTITIES
    assert w5.RESERVED_IDENTITIES is idp.RESERVED_IDENTITIES


def test_u3_no_governance_surface_defines_its_own_reserved_list():
    """Guardia por AST. Las superficies que aun tienen copia propia se
    enumeran como DEUDA DECLARADA, no se ocultan: la lista es el trabajo que
    queda y encogerla es el progreso (se retiran en G8 con los escritores
    legacy).
    """
    import ast
    DEUDA = {
        "factory/layer9/mission_control.py",
        "factory/api/routes/approvals.py",
        "factory/layer8/release_candidate_builder.py",
        "factory/services/test_console_service.py",
        "factory/core/quality_gate_runner.py",
    }
    ofensores = []
    for path in (REPO / "factory").rglob("*.py"):
        rel = path.relative_to(REPO).as_posix()
        if any(p in rel for p in ("__pycache__", "workspaces/", "deployments/",
                                  "factory/tests/")):
            continue
        if rel in DEUDA or rel == "factory/core/identity_policy.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            nombres = [getattr(t, "id", "") for t in node.targets]
            if not any("RESERVED" in n for n in nombres):
                continue
            # Una asignacion literal es una lista propia; una referencia al
            # modulo de politica es delegacion.
            if isinstance(node.value, (ast.Set, ast.List, ast.Tuple, ast.Dict)):
                ofensores.append(f"{rel}:{node.lineno} {nombres}")
    assert not ofensores, (
        "lista de identidades reservadas propia, fuera de identity_policy:\n  "
        + "\n  ".join(ofensores))


def test_u3_the_debt_list_only_shrinks():
    """Congela la deuda: anadir una superficie con lista propia exige tocar
    este test y justificarlo, como con TRANSITIONAL_DIRECT_READERS."""
    import ast
    con_lista = set()
    for path in (REPO / "factory").rglob("*.py"):
        rel = path.relative_to(REPO).as_posix()
        if any(p in rel for p in ("__pycache__", "workspaces/", "deployments/",
                                  "factory/tests/")) or rel == "factory/core/identity_policy.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(
                    "RESERVED" in getattr(t, "id", "") for t in node.targets):
                if isinstance(node.value, (ast.Set, ast.List, ast.Tuple, ast.Dict)):
                    con_lista.add(rel)
    assert con_lista == {
        "factory/layer9/mission_control.py",
        "factory/api/routes/approvals.py",
        "factory/layer8/release_candidate_builder.py",
        "factory/services/test_console_service.py",
        "factory/core/quality_gate_runner.py",
    }, f"la deuda de A-4 cambio: {sorted(con_lista)}"


# ===========================================================================
# U-4 -- control optimista
# ===========================================================================

def test_u4_state_hash_is_stable_when_nothing_changes(tmp_store):
    a = gov.compute_state_hash(store_file=tmp_store)
    b = gov.compute_state_hash(store_file=tmp_store)
    assert a == b, "un hash inestable convierte el 409 en permanente"


def test_u4_state_hash_changes_when_a_decision_is_written(tmp_store):
    antes = gov.compute_state_hash(store_file=tmp_store)
    _propose(tmp_store)
    assert gov.compute_state_hash(store_file=tmp_store) != antes


def test_u4_confirming_with_a_stale_hash_is_409(tmp_store):
    """El escenario real: dos pestanas abiertas.

    Es el fork de la cadena de auditoria trasladado a la capa humana -- dos
    lectores con el estado cacheado, uno escribe y el otro firma sobre lo que
    recordaba.
    """
    p = _propose(tmp_store)
    leido = gov.compute_state_hash(store_file=tmp_store)
    _propose(tmp_store, target_ids=["eu_gmp_annex11"])   # otra pestana escribe

    with pytest.raises(gov.StaleStateError):
        gov.confirm(p["decision_instance_id"], approved_by_id="Cesar",
                    state_hash=leido, store_file=tmp_store)


def test_u4_a_post_without_state_hash_is_rejected(tmp_store):
    """Un POST sin `state_hash` es un cliente que no leyo, no uno al dia."""
    p = _propose(tmp_store)
    with pytest.raises(gov.StaleStateError):
        gov.confirm(p["decision_instance_id"], approved_by_id="Cesar",
                    store_file=tmp_store)


def test_u4_confirming_twice_is_409(tmp_store):
    p = _propose(tmp_store)
    gov.confirm(p["decision_instance_id"], approved_by_id="Cesar",
                state_hash=gov.compute_state_hash(store_file=tmp_store),
                store_file=tmp_store)
    with pytest.raises(store.DecisionConflictError):
        gov.confirm(p["decision_instance_id"], approved_by_id="Cesar",
                    state_hash=gov.compute_state_hash(store_file=tmp_store),
                    store_file=tmp_store)


def test_u4_confirming_something_that_does_not_exist_is_404(tmp_store):
    with pytest.raises(gov.GovernanceNotFoundError):
        gov.confirm("D1-2026-999", approved_by_id="Cesar",
                    state_hash=gov.compute_state_hash(store_file=tmp_store),
                    store_file=tmp_store)


# ===========================================================================
# El ciclo: proponer no autoriza, confirmar si
# ===========================================================================

def test_a_proposal_authorizes_nothing(tmp_store):
    from factory.core import decision_scope_resolver as resolver
    _propose(tmp_store)
    assert not resolver.resolve("D1", "ecfr_21cfr_part211",
                                store_file=tmp_store).authorized


def test_confirming_authorizes(tmp_store):
    from factory.core import decision_scope_resolver as resolver
    p = _propose(tmp_store)
    gov.confirm(p["decision_instance_id"], approved_by_id="Cesar",
                approved_by_display_name="Cesar Perez",
                state_hash=gov.compute_state_hash(store_file=tmp_store),
                store_file=tmp_store)
    assert resolver.resolve("D1", "ecfr_21cfr_part211",
                            store_file=tmp_store).authorized


# ===========================================================================
# Rechazo y devolucion
# ===========================================================================

def test_a_rejected_proposal_authorizes_nothing(tmp_store):
    """DEFECTO REAL cazado al construir este endpoint.

    Hasta G1.15 el resolver miraba `decision_type` y NO `decision`: un
    registro con decision="REJECT" y decision_type="ORIGINAL" pasaba las doce
    invariantes y AUTORIZABA. Un rechazo firmado concedia exactamente lo que
    rechazaba. Ver `GRANTING_DECISIONS`.
    """
    from factory.core import decision_scope_resolver as resolver
    p = _propose(tmp_store)
    gov.reject(p["decision_instance_id"], rejected_by_id="Cesar",
               reason="fuera de alcance",
               state_hash=gov.compute_state_hash(store_file=tmp_store),
               store_file=tmp_store)
    assert not resolver.resolve("D1", "ecfr_21cfr_part211",
                                store_file=tmp_store).authorized


@pytest.mark.parametrize("verdict,granting", [
    ("APPROVE", True), ("PARTIAL", True), ("REJECT", False), ("DEFER", False),
])
def test_only_approve_and_partial_grant_coverage(tmp_store, verdict, granting):
    """Los cuatro veredictos, uno por uno. Sin esto solo se probaria el feliz."""
    from factory.core import decision_scope_resolver as resolver
    rec = store.build_record(
        decision_family="D1", decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", resolved_target_ids=["ecfr_21cfr_part211"],
        decision=verdict, decision_origin="human_confirmed",
        approved_by_id="Cesar", approved_by_display_name="Cesar",
        decision_instance_id="D1-2026-001")
    tmp_store.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")
    assert resolver.resolve("D1", "ecfr_21cfr_part211",
                            store_file=tmp_store).authorized is granting


def test_rejecting_does_not_delete_the_proposal(tmp_store):
    """Append-only: rechazar es anadir el rechazo, no borrar lo rechazado.

    Quien audite tiene que poder ver que se propuso y que se dijo que no.
    """
    p = _propose(tmp_store)
    gov.reject(p["decision_instance_id"], rejected_by_id="Cesar", reason="no",
               state_hash=gov.compute_state_hash(store_file=tmp_store),
               store_file=tmp_store)
    ids = [r["decision_instance_id"] for r in store.read_all(tmp_store)]
    assert p["decision_instance_id"] in ids
    assert len(ids) == 2


def test_rejecting_without_a_reason_is_422(tmp_store):
    p = _propose(tmp_store)
    with pytest.raises(store.DecisionValidationError):
        gov.reject(p["decision_instance_id"], rejected_by_id="Cesar", reason="   ",
                   state_hash=gov.compute_state_hash(store_file=tmp_store),
                   store_file=tmp_store)


def test_returning_without_a_comment_is_422(tmp_store):
    """Sin comentario, el proponente no sabe que ajustar."""
    p = _propose(tmp_store)
    with pytest.raises(store.DecisionValidationError):
        gov.return_to_proposer(p["decision_instance_id"], returned_by_id="Cesar",
                               comment="",
                               state_hash=gov.compute_state_hash(store_file=tmp_store),
                               store_file=tmp_store)


def test_a_returned_proposal_authorizes_nothing(tmp_store):
    from factory.core import decision_scope_resolver as resolver
    p = _propose(tmp_store)
    gov.return_to_proposer(p["decision_instance_id"], returned_by_id="Cesar",
                           comment="falta la cadencia",
                           state_hash=gov.compute_state_hash(store_file=tmp_store),
                           store_file=tmp_store)
    assert not resolver.resolve("D1", "ecfr_21cfr_part211",
                                store_file=tmp_store).authorized


def test_you_cannot_confirm_something_that_is_not_a_proposal(tmp_store):
    """Confirmar una confirmacion no es un ciclo valido."""
    p = _propose(tmp_store)
    c = gov.confirm(p["decision_instance_id"], approved_by_id="Cesar",
                    state_hash=gov.compute_state_hash(store_file=tmp_store),
                    store_file=tmp_store)
    with pytest.raises(store.DecisionConflictError):
        gov.confirm(c["decision_instance_id"], approved_by_id="Cesar",
                    state_hash=gov.compute_state_hash(store_file=tmp_store),
                    store_file=tmp_store)


# ===========================================================================
# HTTP
# ===========================================================================

@pytest.fixture()
def client(tmp_store, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from factory.api.routes import layer9

    monkeypatch.setattr(store, "STORE_FILE", tmp_store)
    app = FastAPI()
    app.include_router(layer9.router)
    return TestClient(app)


def test_http_state_is_200_and_carries_the_state_hash(client):
    r = client.get("/api/v1/layer9/governance/state")
    assert r.status_code == 200
    assert len(r.json()["state_hash"]) == 64


def test_http_unknown_family_is_404(client):
    r = client.get("/api/v1/layer9/governance/coverage/FAMILIA_INVENTADA")
    assert r.status_code == 404


def test_http_generic_signature_is_422(client):
    """El 422 protege la FIRMA, no la propuesta.

    Un `proposed_by_id` generico no autoriza nada -- `layer8_agent` es incluso
    el valor correcto ahi, y esta en la lista de reservadas justamente porque
    no puede FIRMAR. Exigirle nombre humano al proponente rechazaria el caso
    legitimo y no cerraria ningun hueco.
    """
    p = client.post("/api/v1/layer9/governance/decisions/D1/propose",
                    json={"target_ids": ["ecfr_21cfr_part211"],
                          "proposed_by_id": "layer8_agent"})
    assert p.status_code == 201
    iid = p.json()["decision_instance_id"]
    state = client.get("/api/v1/layer9/governance/state").json()

    r = client.post(f"/api/v1/layer9/governance/decisions/{iid}/confirm",
                    json={"approved_by_id": "human",
                          "state_hash": state["state_hash"]})
    assert r.status_code == 422


def test_http_an_empty_proposer_is_422(client):
    r = client.post("/api/v1/layer9/governance/decisions/D1/propose",
                    json={"target_ids": ["ecfr_21cfr_part211"],
                          "proposed_by_id": "  "})
    assert r.status_code == 422


def test_http_stale_state_hash_is_409(client):
    p = client.post("/api/v1/layer9/governance/decisions/D1/propose",
                    json={"target_ids": ["ecfr_21cfr_part211"],
                          "proposed_by_id": "layer8_agent"})
    assert p.status_code == 201
    iid = p.json()["decision_instance_id"]

    r = client.post(f"/api/v1/layer9/governance/decisions/{iid}/confirm",
                    json={"approved_by_id": "Cesar", "state_hash": "0" * 64})
    assert r.status_code == 409


def test_http_confirming_a_missing_proposal_is_404(client):
    state = client.get("/api/v1/layer9/governance/state").json()
    r = client.post("/api/v1/layer9/governance/decisions/D1-2026-999/confirm",
                    json={"approved_by_id": "Cesar",
                          "state_hash": state["state_hash"]})
    assert r.status_code == 404


def test_http_full_cycle_propose_then_confirm(client):
    p = client.post("/api/v1/layer9/governance/decisions/D1/propose",
                    json={"target_ids": ["ecfr_21cfr_part211"],
                          "proposed_by_id": "layer8_agent", "reason": "alta"})
    iid = p.json()["decision_instance_id"]
    state = client.get("/api/v1/layer9/governance/state").json()

    r = client.post(f"/api/v1/layer9/governance/decisions/{iid}/confirm",
                    json={"approved_by_id": "Cesar",
                          "approved_by_display_name": "Cesar Perez",
                          "state_hash": state["state_hash"]})
    assert r.status_code == 201
    assert r.json()["decision_origin"] == "human_confirmed"


# ===========================================================================
# Nada se migra en esta fase
# ===========================================================================

def test_the_migrated_store_authorizes_nothing():
    """G2: el almacen v2 YA EXISTE. Lo que sigue siendo cierto es lo que importa.

    Hasta G2 este test afirmaba que el fichero no existia. Ese cambio es el
    registro de que la migracion ocurrio, y por eso el test se reescribe en vez
    de borrarse: la invariante que SOBREVIVE a la migracion es que proyectar
    historia no crea autorizacion.

    Los 14 registros son de tres clases y ninguna otorga:
      RECONSTRUCTED_SNAPSHOT       reconstruir != tener la firma
      INVALID_PENDING_RESIGNATURE  firmadas sin objetivo (G2')
      LEGACY_UNMAPPED              never_authorizes por registro de familias
    ...mas las de SOURCE_REGISTRATION / APPLICABILITY_MATRIX, cuya confirmacion
    humana ya estaba en la cadena y cuyo enforcement no cambia aqui.
    """
    from factory.core import decision_scope_resolver as resolver

    assert store.STORE_FILE.exists(), "el almacen v2 deberia existir tras G2"
    records = store.read_all()
    assert records, "el almacen v2 esta vacio"

    # Ninguna de las cinco familias gobernadas autoriza a nadie todavia.
    for family in ("D1", "D2", "D3", "D4", "D5"):
        c = resolver.coverage_report(family)
        assert c.covered_ids == (), (
            f"{family} autoriza {list(c.covered_ids)} solo por haber migrado")


def test_the_migration_did_not_touch_the_legacy_stores():
    """V-2: las entradas se abren en LECTURA. El rollback es `rm` del derivado."""
    from factory.services import decision_legacy_adapter as adapter

    for legacy in (adapter.LEGACY_A_FILE, adapter.LEGACY_B_FILE):
        assert legacy.is_file(), f"almacen legacy desaparecido: {legacy}"


def test_the_two_stores_stayed_independent():
    """Migrar decisiones y fotografiar artefactos son dos actos separados.

    Este test afirmaba que el almacen de versiones NO existia; tras el bootstrap
    de G4 existe, y lo que sigue importando es que los dos almacenes tengan
    tamanos y semanticas propias -- que nadie los haya llenado en una sola
    pasada confundiendo migrar con aprobar.
    """
    from factory.core import artifact_version_guard as guard

    assert _store_matches_git_head(store.STORE_FILE), (
        "el almacen de decisiones difiere de HEAD: algun test escribio en el real")
    assert len(guard.read_version_records()) == 28, "el de versiones cambio de tamano"
    # Y ninguno de los 28 nombra una decision: el bootstrap no aprueba.
    assert all(r["approved_by_decision"] is None
               for r in guard.read_version_records())
