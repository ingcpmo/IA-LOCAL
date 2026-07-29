"""
Tests -- factory/regulatory/source_currency_checker.py (Fase 1,
document_remediation_evolution).

CERO RED: _http_get se mockea siempre. Garantías fijadas:
  - reachable=True + hash coincide -> content_matches_governed_copy=True
  - reachable=True + hash NO coincide -> content_matches_governed_copy=False
    (nunca se confunde con "no verificable")
  - HTTP != 200 -> reachable=False, content_matches_governed_copy=None
    (nunca False -- False implicaría que SÍ se comparó y no coincidió)
  - excepción de red -> reachable=False, content_matches_governed_copy=None,
    nota con el motivo
  - sin official_source_url -> reachable=False, sin intentar red
  - run_by reservado -> HTTPException 422 (mismo validador que los demás
    conectores)
  - check_all_governed_sources(): 1 entrada en el log append-only por
    fuente, exactamente 1 evento de auditoría agregado
  - este módulo NUNCA escribe en registry.json ni en su
    regulatory_currency_status

W5 V2 G1.7 -- el módulo es ahora el consumidor C-1 del DecisionScopeResolver.
Todos los tests que ejercitan el camino real firman antes una decisión D1 que
cubra la fuente: no es andamiaje del test, es el contrato. Una fuente sin
cobertura no llega a la red, y eso se prueba explícitamente (L-05).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from fastapi import HTTPException

from factory.regulatory import source_currency_checker as checker
from factory.services import decision_store_v2 as store
from factory.services import paths as svc_paths

GOVERNED_SHA = "a" * 64


class FakeResp:
    def __init__(self, status_code=200, content=b""):
        self.status_code = status_code
        self.content = content


ENTRY = {
    "source_id": "fake_source",
    "official_source_url": "https://example.org/norma.pdf",
    "sha256_original": GOVERNED_SHA,
}


def _authorize(store_path: Path, *source_ids: str) -> Path:
    """Firma una D1 real que cubre `source_ids`. Sin esto, el checker deniega."""
    rec = store.build_record(
        decision_family="D1", decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", resolved_target_ids=list(source_ids),
        decision="APPROVE", decision_origin="human_confirmed",
        approved_by_id="Cesar", approved_by_display_name="Cesar",
        decision_instance_id="D1-2026-001",
    )
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")
    return store_path


@pytest.fixture()
def decisions(tmp_path):
    """Almacén con las fuentes de los fixtures ya cubiertas por D1."""
    return _authorize(tmp_path / "decisions_v2.jsonl",
                      "fake_source", "s1", "s2")


@pytest.fixture()
def checker_env(tmp_path, monkeypatch, isolated_audit):
    monkeypatch.setattr(svc_paths, "SOURCE_CURRENCY_LOG_FILE", tmp_path / "source_currency_log.jsonl")
    monkeypatch.setattr(checker, "MIN_INTERVAL_BETWEEN_SOURCES_S", 0)
    yield tmp_path


def _matching_content():
    import hashlib
    # busca un contenido cuyo sha256 == GOVERNED_SHA es inviable a mano;
    # en su lugar, el test de "coincide" fija sha256_original al hash real
    # del contenido fake usado.
    content = b"contenido real de la norma"
    return content, hashlib.sha256(content).hexdigest()


def test_reachable_and_hash_matches(checker_env, decisions, monkeypatch):
    content, real_sha = _matching_content()
    monkeypatch.setattr(checker, "_http_get", lambda url: FakeResp(200, content))
    entry = {**ENTRY, "sha256_original": real_sha}
    result = checker.check_source(entry, decision_store_file=decisions)
    assert result["reachable"] is True
    assert result["http_status"] == 200
    assert result["downloaded_sha256"] == real_sha
    assert result["content_matches_governed_copy"] is True


def test_reachable_but_hash_diverges(checker_env, decisions, monkeypatch):
    content, _ = _matching_content()
    monkeypatch.setattr(checker, "_http_get", lambda url: FakeResp(200, content))
    result = checker.check_source(ENTRY, decision_store_file=decisions)  # ENTRY.sha256_original no coincide con el contenido fake
    assert result["reachable"] is True
    assert result["content_matches_governed_copy"] is False


def test_http_error_status_is_unreachable_not_mismatch(checker_env, decisions, monkeypatch):
    monkeypatch.setattr(checker, "_http_get", lambda url: FakeResp(404, b""))
    result = checker.check_source(ENTRY, decision_store_file=decisions)
    assert result["reachable"] is False
    assert result["http_status"] == 404
    assert result["content_matches_governed_copy"] is None  # nunca False


def test_network_exception_is_unreachable_with_note(checker_env, decisions, monkeypatch):
    def boom(url):
        raise TimeoutError("simulated timeout")
    monkeypatch.setattr(checker, "_http_get", boom)
    result = checker.check_source(ENTRY, decision_store_file=decisions)
    assert result["reachable"] is False
    assert result["content_matches_governed_copy"] is None
    assert "TimeoutError" in result["note"]


def test_missing_url_never_attempts_network(checker_env, decisions, monkeypatch):
    def should_not_be_called(url):
        raise AssertionError("no debe llamar a la red sin URL")
    monkeypatch.setattr(checker, "_http_get", should_not_be_called)
    entry = {**ENTRY, "official_source_url": None}
    result = checker.check_source(entry, decision_store_file=decisions)
    assert result["reachable"] is False
    assert result["content_matches_governed_copy"] is None


def test_run_by_reserved_name_rejected(checker_env, decisions, monkeypatch):
    monkeypatch.setattr(checker, "_http_get", lambda url: FakeResp(200, b"x"))
    with pytest.raises(HTTPException) as exc:
        checker.check_all_governed_sources("system", [ENTRY], decision_store_file=decisions)
    assert exc.value.status_code == 422


def test_check_all_governed_sources_logs_and_audits_once(checker_env, decisions, monkeypatch):
    content, real_sha = _matching_content()
    monkeypatch.setattr(checker, "_http_get", lambda url: FakeResp(200, content))
    entries = [
        {**ENTRY, "source_id": "s1", "sha256_original": real_sha},
        {**ENTRY, "source_id": "s2", "sha256_original": "b" * 64},  # deliberadamente no coincide
    ]
    results = checker.check_all_governed_sources("QA Real", entries, decision_store_file=decisions)
    assert len(results) == 2
    assert results[0]["content_matches_governed_copy"] is True
    assert results[1]["content_matches_governed_copy"] is False

    log_lines = svc_paths.SOURCE_CURRENCY_LOG_FILE.read_text(encoding="utf-8").splitlines()
    assert len(log_lines) == 2
    logged = [json.loads(l) for l in log_lines]
    assert {e["source_id"] for e in logged} == {"s1", "s2"}
    assert all(e["run_by"] == "QA Real" for e in logged)

    # el evento de auditoria vive en factory.core.audit_writer.AUDIT_FILE,
    # ya redirigido por isolated_audit -- se verifica via el propio fixture
    from factory.core import audit_writer as aw
    aw_lines = aw.AUDIT_FILE.read_text(encoding="utf-8").splitlines()
    events = [json.loads(l) for l in aw_lines]
    currency_events = [e for e in events if e.get("event_type") == "regulatory_source_currency_checked"]
    assert len(currency_events) == 1
    assert currency_events[0]["data"]["sources_checked"] == 2
    assert currency_events[0]["data"]["reachable"] == 2
    assert currency_events[0]["data"]["content_matches_governed_copy"] == 1


# ===========================================================================
# G1.7 -- cobertura de decisión ANTES de la red (consumidor C-1)
# ===========================================================================

def test_l05_uncovered_source_generates_zero_outbound_traffic(checker_env, tmp_path, monkeypatch):
    """El test con más valor operativo del gate: una fuente sin cobertura no
    sale a la red. Protege contra la regresión más probable -- mover la
    comprobación a después del httpx.get."""
    def must_not_be_called(url):
        raise AssertionError(
            "se intentó acceder a la red para una fuente SIN cobertura humana")
    monkeypatch.setattr(checker, "_http_get", must_not_be_called)

    empty = tmp_path / "sin_decisiones.jsonl"
    empty.write_text("", encoding="utf-8")

    result = checker.check_source(ENTRY, decision_store_file=empty)
    assert result["authorized_by_decision"] is False
    assert result["reverification_allowed"] is False
    # reachable es None, no False: False afirmaría que se intentó y falló.
    assert result["reachable"] is None
    assert result["content_matches_governed_copy"] is None
    assert result["note"].startswith("REVERIFICATION_NOT_AUTHORIZED")


def test_missing_decision_store_denies_fail_closed(checker_env, tmp_path, monkeypatch):
    """Resolver indisponible ⇒ no se accede. Nunca 'siga adelante'."""
    monkeypatch.setattr(checker, "_http_get",
                        lambda url: (_ for _ in ()).throw(AssertionError("red tocada")))
    result = checker.check_source(ENTRY, decision_store_file=tmp_path / "no_existe.jsonl")
    assert result["authorized_by_decision"] is False
    assert result["coverage_basis"] == "RESOLVER_UNAVAILABLE"


def test_a_reconstructed_snapshot_does_not_allow_reverification(checker_env, tmp_path, monkeypatch):
    """Las 3 fuentes antiguas tras migrar: cubiertas solo por reconstrucción.
    G3 no puede adelantarse a G2 aunque alguien lo intente."""
    monkeypatch.setattr(checker, "_http_get",
                        lambda url: (_ for _ in ()).throw(AssertionError("red tocada")))
    rec = store.build_record(
        decision_family="D1", decision_type="ORIGINAL",
        selection_mode="ALL_SNAPSHOT", resolved_target_ids=["fake_source"],
        decision="APPROVE", decision_origin="human_confirmed",
        approved_by_id="Cesar", approved_by_display_name="Cesar",
        provenance="RECONSTRUCTED_SNAPSHOT",
        reconstruction_evidence={"method": "copied_at < firma"},
        decision_instance_id="D1-2026-001",
    )
    path = tmp_path / "reconstruido.jsonl"
    path.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")

    result = checker.check_source(ENTRY, decision_store_file=path)
    assert result["authorized_by_decision"] is False
    assert result["coverage_basis"] == "RECONSTRUCTED_PENDING_FORMAL_CORRECTION"


def test_authorized_result_carries_its_covering_decision(checker_env, decisions, monkeypatch):
    """Todo valor de gobernanza viaja con su procedencia."""
    content, real_sha = _matching_content()
    monkeypatch.setattr(checker, "_http_get", lambda url: FakeResp(200, content))
    result = checker.check_source({**ENTRY, "sha256_original": real_sha},
                                  decision_store_file=decisions)
    assert result["authorized_by_decision"] is True
    assert result["covering_decisions"] == ["D1-2026-001"]
    assert result["coverage_basis"] == "HUMAN_CONFIRMED_EXPLICIT"


def test_denied_sources_are_logged_and_audited_not_skipped(checker_env, tmp_path, monkeypatch):
    """Que se intentara reverificar algo no autorizado es un hecho auditable."""
    content, real_sha = _matching_content()
    monkeypatch.setattr(checker, "_http_get", lambda url: FakeResp(200, content))
    partial = _authorize(tmp_path / "parcial.jsonl", "s1")   # s2 sin cubrir

    entries = [
        {**ENTRY, "source_id": "s1", "sha256_original": real_sha},
        {**ENTRY, "source_id": "s2", "sha256_original": real_sha},
    ]
    results = checker.check_all_governed_sources("QA Real", entries,
                                                 decision_store_file=partial)
    assert results[0]["authorized_by_decision"] is True
    assert results[1]["authorized_by_decision"] is False

    # Las DOS quedan en el log: la denegada no se omite en silencio.
    log_lines = svc_paths.SOURCE_CURRENCY_LOG_FILE.read_text(encoding="utf-8").splitlines()
    assert len(log_lines) == 2

    from factory.core import audit_writer as aw
    events = [json.loads(l) for l in aw.AUDIT_FILE.read_text(encoding="utf-8").splitlines()]
    ev = [e for e in events if e["event_type"] == "regulatory_source_currency_checked"][0]
    assert ev["data"]["reverification_not_authorized"] == 1
    assert ev["data"]["not_authorized_source_ids"] == ["s2"]
    assert ev["data"]["reachable"] == 1


def test_the_gate_lives_before_the_http_call_in_the_source():
    """Guardia estructural: si alguien mueve la comprobación por debajo de
    `_http_get`, este test lo caza aunque los demás sigan en verde."""
    src = Path(checker.__file__).read_text(encoding="utf-8")
    body = src.split("def check_source(", 1)[1]
    gate = body.index("_resolver.resolve(")
    http = body.index("_http_get(url)")
    assert gate < http, "la comprobación de cobertura debe preceder al acceso HTTP"


def test_never_writes_registry_json():
    """Este modulo nunca abre registry.json para escritura ni usa
    write_text (que sobrescribiria un archivo entero) -- su unica
    escritura es el log append-only via open(...'a')."""
    src = Path("/home/ing_cpmo/factory/regulatory/source_currency_checker.py").read_text(encoding="utf-8")
    assert ".write_text(" not in src
    assert 'open(paths.SOURCE_CURRENCY_LOG_FILE, "a"' in src
