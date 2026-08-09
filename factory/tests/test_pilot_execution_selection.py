"""Selección determinista entre múltiples PILOT_EXECUTION vigentes que
cubren el mismo lote de documentos (`corpus_runner._select_pilot_execution_
instance`, opción (b) del roadmap del analizador -- ver
`docs_plan/ROADMAP_ANALIZADOR_GMP.md`, sección "Estado de ejecución del
smoke" e "Intento de corrección").

Causa raíz que esto corrige: `_check_pilot_execution` fallaba cerrado
(`CorpusRunNotAuthorizedError`) en cuanto >1 instancia `PILOT_EXECUTION`
`human_confirmed`/`ACTIVE` cubría el mismo documento -- aunque todas
autorizaran exactamente el mismo trabajo. Ocurrió en producción el
2026-08-09 sobre `RW-0005` (`PILOT_EXECUTION-2026-002`/`-004`/`-006`).

TODO test usa un almacén de decisiones TEMPORAL (`tmp_decisions`, patrón
idéntico a `test_corpus_authorization.py`) -- nunca el almacén real. La
selección se ejercita vía `propose()`+`confirm()` reales (mismo circuito
que produce las decisiones en producción), no con dataclasses de resolver
simuladas -- para que estos tests reproduzcan el defecto real, no una
aproximación de él."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.core import decision_scope_resolver as resolver
from factory.regulatory import corpus_runner as runner
from factory.regulatory import model_qualification_gate as mqg
from factory.services import governance_service as gov
from factory.tests.test_corpus_runner import FakeCorpusProvider

DOC = "RW-0005"


@pytest.fixture()
def tmp_decisions(tmp_path) -> Path:
    path = tmp_path / "decisions_v2.jsonl"
    path.write_text("", encoding="utf-8")
    return path


def _sign_pilot_execution(tmp_decisions, *, target_ids=(DOC,), max_calls=12,
                          decision_type="ORIGINAL", supersedes_instance_id=None,
                          decision="APPROVE", reason="fixture de test") -> dict:
    """propose()+confirm() reales -- mismo circuito que produce las
    decisiones en producción (`pilot_execution.propose_pilot_execution` es
    un wrapper delgado sobre exactamente esto)."""
    fam_hash = gov.family_state_hash("PILOT_EXECUTION", store_file=tmp_decisions)
    prop = gov.propose(
        "PILOT_EXECUTION", target_ids=list(target_ids), decision=decision,
        decision_type=decision_type, selection_mode="EXPLICIT_LIST",
        proposed_by_id="claude_code_capa8", reason=reason,
        payload={"max_calls": max_calls, "authorizes_corpus": False,
                 "authorizes_baseline": False} if max_calls is not None else {},
        supersedes_instance_id=supersedes_instance_id,
        family_state_hash=fam_hash, store_file=tmp_decisions)
    conf = gov.confirm(
        prop["proposal_id"], approved_by_id="Cesar May", approved_by_display_name="Cesar May",
        reason=reason, family_state_hash=prop["family_state_hash"],
        store_file=tmp_decisions)
    return conf


def _sample_unit(document_id=DOC, page_indices=(0,)):
    return runner.PilotSampleUnit(
        document_id=document_id, document_type="DS", agent_id="fda_part11_agent",
        requirement_id="PART11_1", page_indices=page_indices,
        selection_reason="fixture de test, no un caso real seleccionado")


@pytest.fixture(autouse=True)
def _no_ollama(monkeypatch):
    monkeypatch.setattr(mqg, "require_inference_authorized", lambda *a, **k: None)
    monkeypatch.setattr(runner, "mqg", mqg)
    monkeypatch.setattr(runner, "_write_batch_event", lambda *a, **k: None)
    monkeypatch.setattr(runner, "_resolve_document_path",
                        lambda doc_id: (runner.PROMPTS_DIR, "0" * 64))
    monkeypatch.setattr(runner, "_extract_pilot_excerpt",
                        lambda path, page_indices: ["Texto corto real de prueba." * 10
                                                     for _ in page_indices])


# ===========================================================================
# 1. N instancias vigentes con presupuesto -> elige UNA, determinista
# ===========================================================================

def test_multiples_instancias_vigentes_eligen_una_de_forma_reproducible(tmp_decisions):
    older = _sign_pilot_execution(tmp_decisions, max_calls=60)
    newer = _sign_pilot_execution(tmp_decisions, max_calls=1)

    sel1 = runner._select_pilot_execution_instance([DOC], decision_store_file=tmp_decisions)
    sel2 = runner._select_pilot_execution_instance([DOC], decision_store_file=tmp_decisions)

    assert sel1 == sel2, "la selección debe ser reproducible entre corridas sobre el mismo estado"
    # desempate por decision_date más reciente: 'newer' se confirmó después
    assert sel1["selected_instance_id"] == newer["decision_instance_id"]
    assert sel1["co_covering_instances"] == [older["decision_instance_id"]]
    assert "presupuesto>0" in sel1["selection_rule_applied"]


# ===========================================================================
# 2. Una vigente + una SUPERSEDED -> ignora la superseded
# ===========================================================================

def test_instancia_superseded_se_ignora(tmp_decisions):
    to_close = _sign_pilot_execution(tmp_decisions, max_calls=8, reason="a cerrar")
    surviving = _sign_pilot_execution(tmp_decisions, max_calls=5, reason="sigue vigente, con presupuesto")
    # CORRECTION que supersede a 'to_close' -- status proyectado pasa a
    # SUPERSEDED (decision_scope_resolver.project_status), independiente
    # del veredicto: confirm() siempre escribe decision=APPROVE (ver nota
    # en _pilot_execution_budget), así que la corrección queda con
    # payload vacío (sin max_calls) a propósito, para no simular un
    # otorgante nuevo con presupuesto real -- mismo patrón que
    # PILOT_EXECUTION-2026-008 en producción.
    correction = _sign_pilot_execution(
        tmp_decisions, target_ids=(DOC,), max_calls=None,
        decision_type="CORRECTION", supersedes_instance_id=to_close["decision_instance_id"],
        reason="cierre de to_close")

    scope = resolver.resolve("PILOT_EXECUTION", DOC, store_file=tmp_decisions)
    assert to_close["decision_instance_id"] not in scope.covering_instances, (
        "la instancia superseded no debe seguir contando como vigente")
    assert set(scope.covering_instances) == {
        surviving["decision_instance_id"], correction["decision_instance_id"]}

    sel = runner._select_pilot_execution_instance([DOC], decision_store_file=tmp_decisions)
    assert sel["selected_instance_id"] == surviving["decision_instance_id"], (
        "la única con presupuesto real; la CORRECTION cubre pero no otorga presupuesto")
    assert sel["co_covering_instances"] == []


# ===========================================================================
# 3. Todas sin presupuesto -> falla cerrado, mensaje explícito
# ===========================================================================

def test_todas_sin_presupuesto_falla_cerrado_con_mensaje_explicito(tmp_decisions):
    _sign_pilot_execution(tmp_decisions, max_calls=None)
    _sign_pilot_execution(tmp_decisions, max_calls=0)

    with pytest.raises(runner.CorpusRunNotAuthorizedError, match="ninguna tiene presupuesto"):
        runner._select_pilot_execution_instance([DOC], decision_store_file=tmp_decisions)


# ===========================================================================
# 4. Fixture del caso REAL: RW-0005 con 3 instancias vigentes (patrón
#    -004/-006/-008 del 2026-08-09) -> elige la correcta
# ===========================================================================

def test_fixture_real_rw0005_tres_instancias_vigentes(tmp_decisions):
    """Reproduce la forma exacta del conflicto real: una autorización
    amplia con mucho presupuesto (patrón -004), una acotada con poco
    presupuesto (patrón -006), y una CORRECTION que cerró una tercera
    instancia pero quedó ella misma como otorgante sin presupuesto
    (patrón -008, payload vacío). La selección debe ignorar la de
    payload vacío (presupuesto 0) y elegir entre las dos restantes por
    decision_date más reciente."""
    broad = _sign_pilot_execution(
        tmp_decisions, target_ids=(DOC, "RW-0011", "RW-0012"), max_calls=60,
        reason="patrón -004: autorización amplia de H1-H6")
    narrow = _sign_pilot_execution(
        tmp_decisions, target_ids=(DOC,), max_calls=1,
        reason="patrón -006: smoke acotado de R1")
    to_supersede = _sign_pilot_execution(
        tmp_decisions, target_ids=(DOC, "RW-0011", "RW-0012"), max_calls=8,
        reason="instancia redundante a cerrar (patrón -002, presupuesto distinto de "
               "'broad' para que propose()/confirm() no la deduplique como equivalente)")
    correction = _sign_pilot_execution(
        tmp_decisions, target_ids=(DOC, "RW-0011", "RW-0012"), max_calls=None,
        decision_type="CORRECTION", supersedes_instance_id=to_supersede["decision_instance_id"],
        reason="patrón -008: CORRECTION sin max_calls, no debe competir por presupuesto")

    scope = runner.resolver.resolve("PILOT_EXECUTION", DOC, store_file=tmp_decisions)
    assert set(scope.covering_instances) == {
        broad["decision_instance_id"], narrow["decision_instance_id"], correction["decision_instance_id"]}, (
        "el caso real: 3 instancias vigentes cubriendo el mismo documento")

    sel = runner._select_pilot_execution_instance([DOC], decision_store_file=tmp_decisions)
    assert sel["selected_instance_id"] == narrow["decision_instance_id"], (
        "de las dos con presupuesto (broad, narrow), narrow es la confirmación más reciente")
    assert correction["decision_instance_id"] not in sel["co_covering_instances"], (
        "la instancia sin presupuesto (patrón -008) no debe aparecer como candidata usable"
    )
    assert set(sel["co_covering_instances"]) == {broad["decision_instance_id"]}


# ===========================================================================
# 5. Regresión: una sola instancia vigente -> comportamiento idéntico
# ===========================================================================

def test_una_sola_instancia_vigente_comportamiento_igual_que_antes(tmp_decisions):
    unica = _sign_pilot_execution(tmp_decisions, max_calls=12)
    sel = runner._select_pilot_execution_instance([DOC], decision_store_file=tmp_decisions)
    assert sel["selected_instance_id"] == unica["decision_instance_id"]
    assert sel["co_covering_instances"] == []
    # `_check_pilot_execution` (compatibilidad hacia atrás) sigue devolviendo
    # solo el payload, igual que antes de este cambio.
    payload = runner._check_pilot_execution([DOC], decision_store_file=tmp_decisions)
    assert payload["max_calls"] == 12


# ===========================================================================
# 6. Integración: run_pilot_sample_batch ya NO falla por el conflicto real,
#    y registra la selección en el summary
# ===========================================================================

def test_run_pilot_sample_batch_resuelve_el_conflicto_real_y_lo_registra(tmp_decisions, tmp_path):
    broad = _sign_pilot_execution(tmp_decisions, max_calls=60, reason="patrón -004")
    narrow = _sign_pilot_execution(tmp_decisions, max_calls=1, reason="patrón -006")

    summary = runner.run_pilot_sample_batch(
        [_sample_unit()], provider=FakeCorpusProvider(),
        checkpoint_dir=tmp_path / "ckpt", manifest_dir=tmp_path / "manifest",
        decision_store_file=tmp_decisions)

    assert summary.stop_reason == "CORPUS_COMPLETE"
    assert summary.units[0].status == "COMPLETED"
    assert summary.selected_pilot_instance_id == narrow["decision_instance_id"]
    assert summary.co_covering_pilot_instances == [broad["decision_instance_id"]]
    assert summary.pilot_selection_rule is not None
