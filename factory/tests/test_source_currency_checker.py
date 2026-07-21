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
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from fastapi import HTTPException

from factory.regulatory import source_currency_checker as checker
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


def test_reachable_and_hash_matches(checker_env, monkeypatch):
    content, real_sha = _matching_content()
    monkeypatch.setattr(checker, "_http_get", lambda url: FakeResp(200, content))
    entry = {**ENTRY, "sha256_original": real_sha}
    result = checker.check_source(entry)
    assert result["reachable"] is True
    assert result["http_status"] == 200
    assert result["downloaded_sha256"] == real_sha
    assert result["content_matches_governed_copy"] is True


def test_reachable_but_hash_diverges(checker_env, monkeypatch):
    content, _ = _matching_content()
    monkeypatch.setattr(checker, "_http_get", lambda url: FakeResp(200, content))
    result = checker.check_source(ENTRY)  # ENTRY.sha256_original no coincide con el contenido fake
    assert result["reachable"] is True
    assert result["content_matches_governed_copy"] is False


def test_http_error_status_is_unreachable_not_mismatch(checker_env, monkeypatch):
    monkeypatch.setattr(checker, "_http_get", lambda url: FakeResp(404, b""))
    result = checker.check_source(ENTRY)
    assert result["reachable"] is False
    assert result["http_status"] == 404
    assert result["content_matches_governed_copy"] is None  # nunca False


def test_network_exception_is_unreachable_with_note(checker_env, monkeypatch):
    def boom(url):
        raise TimeoutError("simulated timeout")
    monkeypatch.setattr(checker, "_http_get", boom)
    result = checker.check_source(ENTRY)
    assert result["reachable"] is False
    assert result["content_matches_governed_copy"] is None
    assert "TimeoutError" in result["note"]


def test_missing_url_never_attempts_network(checker_env, monkeypatch):
    def should_not_be_called(url):
        raise AssertionError("no debe llamar a la red sin URL")
    monkeypatch.setattr(checker, "_http_get", should_not_be_called)
    entry = {**ENTRY, "official_source_url": None}
    result = checker.check_source(entry)
    assert result["reachable"] is False
    assert result["content_matches_governed_copy"] is None


def test_run_by_reserved_name_rejected(checker_env, monkeypatch):
    monkeypatch.setattr(checker, "_http_get", lambda url: FakeResp(200, b"x"))
    with pytest.raises(HTTPException) as exc:
        checker.check_all_governed_sources("system", [ENTRY])
    assert exc.value.status_code == 422


def test_check_all_governed_sources_logs_and_audits_once(checker_env, monkeypatch):
    content, real_sha = _matching_content()
    monkeypatch.setattr(checker, "_http_get", lambda url: FakeResp(200, content))
    entries = [
        {**ENTRY, "source_id": "s1", "sha256_original": real_sha},
        {**ENTRY, "source_id": "s2", "sha256_original": "b" * 64},  # deliberadamente no coincide
    ]
    results = checker.check_all_governed_sources("QA Real", entries)
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


def test_never_writes_registry_json():
    """Este modulo nunca abre registry.json para escritura ni usa
    write_text (que sobrescribiria un archivo entero) -- su unica
    escritura es el log append-only via open(...'a')."""
    src = Path("/home/ing_cpmo/factory/regulatory/source_currency_checker.py").read_text(encoding="utf-8")
    assert ".write_text(" not in src
    assert 'open(paths.SOURCE_CURRENCY_LOG_FILE, "a"' in src
