"""H-5F (2026-08-29) -- hardening de GMP AI Factory (factory-api).

Cubre la parte de CÓDIGO (la parte de infra -- red aislada, mounts :ro -- se
demuestra con docker y queda en docs_plan/CIERRE_H5F_H6F_20260829.md):

  * CORS: allowlist explícita por `FACTORY_CORS_ALLOWED_ORIGINS`, nunca "*".
  * Egress: dos controles diferenciados (PROCESS vs NETWORK) y la regla dura
    `EGRESS_GUARANTEE=FORBIDDEN` solo con AMBOS enforced.
  * Atestación: `run_v2_pipeline` emite `egress_controls`; findings/graph
    fingerprints NO cambian.
"""
from __future__ import annotations

import importlib
import json
import tempfile
from pathlib import Path

import pytest

from factory.regulatory.validation_v2 import local_only as lo


@pytest.fixture()
def factory_main(monkeypatch):
    """`factory.api.main` hace fail-closed en el import si falta FACTORY_API_KEY
    (Fase M0). Para probar la lógica de CORS se inyecta una key de test y se
    recarga el módulo."""
    monkeypatch.setenv("FACTORY_API_KEY", "test-key-h5f")
    import factory.api.main as m
    return importlib.reload(m)

_FINDINGS_FP_BASELINE = "b5196a7177c92a913de638637a071d2027a78eb1b9f1233d814812d3ff6dc21e"
_GRAPH_FP_BASELINE = "88f15b69bf2cea9a09d5a179300496d3685b18c58c1adb1dfa601f191b73ae05"
_DOCS = ["RW-0005", "RW-0006", "RW-0009", "RW-0011", "RW-0012", "RW-0014"]


# ---------------------------------------------------------------------------
# CORS allowlist
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    ("", []),
    ("   ", []),
    ("https://ui.local", ["https://ui.local"]),
    ("https://a.local, https://b.local ,https://c.local", ["https://a.local", "https://b.local", "https://c.local"]),
])
def test_cors_allowlist_parsing(factory_main, monkeypatch, raw, expected):
    monkeypatch.setenv("FACTORY_CORS_ALLOWED_ORIGINS", raw)
    assert factory_main._cors_allowed_origins() == expected


def test_cors_allowlist_never_wildcard(factory_main, monkeypatch):
    monkeypatch.setenv("FACTORY_CORS_ALLOWED_ORIGINS", "https://ok.local,*")
    with pytest.raises(RuntimeError, match="no admite '\\*'"):
        factory_main._cors_allowed_origins()


def test_cors_empty_is_the_default(factory_main, monkeypatch):
    monkeypatch.delenv("FACTORY_CORS_ALLOWED_ORIGINS", raising=False)
    # ausente ⇒ [] ⇒ CORSMiddleware no emite Access-Control-Allow-Origin
    assert factory_main._cors_allowed_origins() == []


def test_cors_middleware_installed_with_allowlist_not_star(monkeypatch):
    monkeypatch.setenv("FACTORY_API_KEY", "test-key-h5f")
    monkeypatch.setenv("FACTORY_CORS_ALLOWED_ORIGINS", "https://ui.factory.local")
    import factory.api.main as m
    try:
        main = importlib.reload(m)
        cors = [mw for mw in main.app.user_middleware if mw.cls.__name__ == "CORSMiddleware"]
        assert cors, "CORSMiddleware no instalado"
        opts = getattr(cors[0], "kwargs", None) or getattr(cors[0], "options", {})
        origins = opts.get("allow_origins")
        assert origins == ["https://ui.factory.local"] and "*" not in origins
    finally:
        # no dejar el módulo recargado con un origen de test para el resto de la suite
        monkeypatch.undo()
        try:
            importlib.reload(m)
        except Exception:  # noqa: BLE001  -- si falta FACTORY_API_KEY en el env base, queda como estaba
            pass


# ---------------------------------------------------------------------------
# Egress -- dos controles diferenciados
# ---------------------------------------------------------------------------
def test_probe_external_reachability_returns_a_known_verdict():
    assert lo.probe_external_reachability(timeout=4.0) in {"BLOCKED", "REACHABLE", "UNKNOWN"}


@pytest.mark.parametrize("probe,ollama,exp_net,exp_guarantee", [
    ("BLOCKED",   True,  "ENFORCED",     "FORBIDDEN"),
    ("BLOCKED",   False, "ENFORCED",     "FORBIDDEN"),          # guarantee no depende de Ollama
    ("REACHABLE", True,  "NOT_ENFORCED", "BEST_EFFORT_PROCESS_ONLY"),
    ("UNKNOWN",   True,  "NOT_ENFORCED", "BEST_EFFORT_PROCESS_ONLY"),
    ("UNKNOWN",   False, "NOT_ENFORCED", "BEST_EFFORT_PROCESS_ONLY"),
])
def test_egress_control_state_logic(probe, ollama, exp_net, exp_guarantee):
    st = lo.egress_control_state(network_probe=probe, ollama_ok=ollama)
    assert st["process_level_control"] == "ENFORCED"          # el monkeypatch siempre está
    assert st["network_level_control"] == exp_net
    assert st["egress_guarantee"] == exp_guarantee
    assert st["network_probe_result"] == probe
    assert st["ollama_local_access"] == ("PASS" if ollama else "FAIL")


def test_forbidden_requires_network_level_not_just_monkeypatch():
    """Regla dura del rediseño: nunca declarar EGRESS_GUARANTEE=FORBIDDEN por el
    monkeypatch. Con la red alcanzable, la garantía es BEST_EFFORT_PROCESS_ONLY."""
    st = lo.egress_control_state(network_probe="REACHABLE", ollama_ok=True)
    assert st["egress_guarantee"] != "FORBIDDEN"
    st2 = lo.egress_control_state(network_probe="BLOCKED", ollama_ok=True)
    assert st2["egress_guarantee"] == "FORBIDDEN"


def test_network_locked_still_blocks_external_and_allows_local():
    import socket
    with lo.network_locked() as rep:
        # local permitido
        try:
            s = socket.socket(); s.settimeout(0.2)
            s.connect_ex(("127.0.0.1", 9)); s.close()
        except Exception:  # noqa: BLE001
            pass
        # externo bloqueado por el monkeypatch
        with pytest.raises(lo.EgressBlocked):
            socket.socket().connect(("140.82.112.3", 443))
    assert rep.local_only is False  # hubo un intento externo registrado


# ---------------------------------------------------------------------------
# Atestación en el pipeline -- egress_controls presente, fingerprints intactos
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def _run_audit():
    from factory.regulatory.validation_v2.v2_runtime import run_v2_pipeline
    from factory.regulatory.validation_v2 import coverage_mode as _cm
    # H-5F es infra y ortogonal al modo de cobertura. Tras D-2 el repo está en
    # ENFORCE; se fuerza OBSERVE aquí para comprobar contra la baseline `b5196a71…`
    # que el hardening NO altera el resultado analítico.
    _mp = pytest.MonkeyPatch()
    _cfg = Path(tempfile.mkdtemp(prefix="h5f-obs-cfg-")) / "analysis_coverage_mode.yaml"
    _cfg.write_text("mode: OBSERVE\ndecided_by: null\ndecision_ref: null\ndecision_date: null\n")
    _mp.setattr(_cm, "_MODE_PATH", _cfg)
    _mp.setattr(_cm, "_thresholds_signed", lambda: False)
    base = Path(tempfile.mkdtemp(prefix="h5f-att-"))
    run_v2_pipeline(_DOCS, project_id="H5F-ATT", run_id="a1", report_base=base)
    out = json.loads((base / "a1" / "audit_summary" / "audit_metadata.json").read_text())
    _mp.undo()
    return out


def test_audit_exposes_egress_controls(_run_audit):
    ec = _run_audit["egress_controls"]
    assert set(ec) >= {"process_level_control", "network_level_control", "egress_guarantee",
                       "ollama_local_access", "network_probe_result"}
    assert ec["process_level_control"] == "ENFORCED"
    assert ec["network_level_control"] in {"ENFORCED", "NOT_ENFORCED"}
    assert ec["egress_guarantee"] in {"FORBIDDEN", "BEST_EFFORT_PROCESS_ONLY"}
    # coherencia interna
    if ec["egress_guarantee"] == "FORBIDDEN":
        assert ec["network_level_control"] == "ENFORCED"


def test_h5f_does_not_move_findings_or_graph_fingerprint(_run_audit):
    assert _run_audit["findings_fingerprint"] == _FINDINGS_FP_BASELINE
    assert _run_audit["graph_snapshot_fingerprint"] == _GRAPH_FP_BASELINE


def test_h5f_preserves_human_gate_and_no_forbidden_states(_run_audit):
    assert _run_audit["human_gate_intact"] is True
    assert _run_audit["forbidden_states_present"] is False
    assert _run_audit["llm_calls"] == 0
    assert _run_audit["document_egress_bytes"] == 0
