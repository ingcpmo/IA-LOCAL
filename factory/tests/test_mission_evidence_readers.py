"""
W3 — Tests de los endpoints lazy por sección y file readers.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def _get_api_key() -> str:
    import subprocess
    r = subprocess.run(
        ["docker", "exec", "factory-api", "printenv", "FACTORY_API_KEY"],
        capture_output=True, text=True, timeout=5,
    )
    key = r.stdout.strip()
    if not key:
        pytest.skip("factory-api no disponible")
    return key


PROJECT = "oos_hplc_investigator"
RC_ID   = "oos_hplc_investigator-rc-v1.1-20260626T191819"


# ── /design ─────────────────────────────────────────────────────────────────

def test_design_returns_files():
    import httpx
    key = _get_api_key()
    r = httpx.get(
        f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/design",
        headers={"x-api-key": key}, timeout=10,
    )
    assert r.status_code == 200
    d = r.json()
    assert "files" in d
    names = [f["name"] for f in d["files"]]
    assert "agent_design_proposal.yaml" in names


# ── /agents ──────────────────────────────────────────────────────────────────

def test_agents_parses_profiles_and_new():
    import httpx
    key = _get_api_key()
    r = httpx.get(
        f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/agents",
        headers={"x-api-key": key}, timeout=10,
    )
    assert r.status_code == 200
    d = r.json()
    assert "agents" in d and "summary" in d
    s = d["summary"]
    assert s["profiles_inherited"] == 2
    assert s["new_agents"] == 1
    profiles = [a for a in d["agents"] if a["is_inherited"]]
    new_agents = [a for a in d["agents"] if not a["is_inherited"]]
    assert len(profiles) == 2
    assert len(new_agents) == 1
    assert new_agents[0]["agent_id"] == "hplc_data_review_agent"


# ── /headless ────────────────────────────────────────────────────────────────

def test_headless_parses_log():
    import httpx
    key = _get_api_key()
    r = httpx.get(
        f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/headless",
        headers={"x-api-key": key}, timeout=10,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["found"] is True
    res = d["result"]
    assert res["num_turns"] == 20
    assert len(res["models_used"]) == 2
    assert res["total_cost_usd"] > 0
    assert res["terminal_reason"] == "completed"
    assert res["returncode"] == 0


# ── /tests ───────────────────────────────────────────────────────────────────

def test_tests_parses_report():
    import httpx
    key = _get_api_key()
    r = httpx.get(
        f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/tests",
        headers={"x-api-key": key}, timeout=10,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["found"] is True
    assert d["failed"] == 0
    assert d["passed"] >= 12
    assert d["returncode"] == 0


# ── /rcs ─────────────────────────────────────────────────────────────────────

def test_rcs_lists_with_canonical():
    import httpx
    key = _get_api_key()
    r = httpx.get(
        f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/rcs",
        headers={"x-api-key": key}, timeout=10,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["count"] >= 2
    canonicals = [rc for rc in d["rcs"] if rc.get("is_canonical")]
    assert len(canonicals) == 1
    assert canonicals[0]["rc_id"] == RC_ID


def test_rcs_includes_artifacts():
    import httpx
    key = _get_api_key()
    r = httpx.get(
        f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/rcs",
        headers={"x-api-key": key}, timeout=10,
    )
    assert r.status_code == 200
    canonical = next((rc for rc in r.json()["rcs"] if rc.get("is_canonical")), None)
    assert canonical is not None
    assert isinstance(canonical.get("artifacts"), list)
    assert len(canonical["artifacts"]) > 0


# ── /deployment ──────────────────────────────────────────────────────────────

def test_deployment_exists_and_health():
    import httpx
    key = _get_api_key()
    r = httpx.get(
        f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/deployment",
        headers={"x-api-key": key}, timeout=15,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["exists"] is True
    assert d.get("api_port") == 8102
    assert d.get("health_ok") is True


# ── /audit ───────────────────────────────────────────────────────────────────

def test_audit_filtered_by_project():
    import httpx
    key = _get_api_key()
    r = httpx.get(
        f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/audit",
        headers={"x-api-key": key}, params={"limit": 50}, timeout=10,
    )
    assert r.status_code == 200
    d = r.json()
    assert "events" in d
    for e in d["events"]:
        assert e.get("timestamp"), "Evento sin timestamp"
        assert e.get("event_type"), "Evento sin event_type"


def test_audit_respects_limit():
    import httpx
    key = _get_api_key()
    r = httpx.get(
        f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/audit",
        headers={"x-api-key": key}, params={"limit": 5}, timeout=10,
    )
    assert r.status_code == 200
    d = r.json()
    assert len(d["events"]) <= 5


# ── File readers ─────────────────────────────────────────────────────────────

def test_design_file_reader_yaml():
    import httpx
    key = _get_api_key()
    r = httpx.get(
        f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/design/file",
        headers={"x-api-key": key}, params={"path": "agent_design_proposal.yaml"},
        timeout=10,
    )
    assert r.status_code == 200
    d = r.json()
    assert "content" in d
    assert "hplc_data_review_agent" in d["content"]


def test_design_file_reader_blocks_traversal():
    import httpx
    key = _get_api_key()
    for bad in ["../../../etc/passwd", "../../etc/shadow"]:
        r = httpx.get(
            f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/design/file",
            headers={"x-api-key": key}, params={"path": bad}, timeout=10,
        )
        assert r.status_code in (400, 403, 404), f"Traversal {bad!r} devolvió {r.status_code}"


def test_design_file_reader_blocks_disallowed_ext():
    import httpx
    key = _get_api_key()
    r = httpx.get(
        f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/design/file",
        headers={"x-api-key": key}, params={"path": "something.py"}, timeout=10,
    )
    assert r.status_code in (403, 404)


def test_rc_artifact_file_reader():
    import httpx
    key = _get_api_key()
    r = httpx.get(
        f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/rc/{RC_ID}/file",
        headers={"x-api-key": key}, params={"path": "artifacts/rc_manifest.json"}, timeout=10,
    )
    # rc_manifest.json está en rc_dir raíz, no en artifacts/
    # intentar con un archivo real del rc
    r2 = httpx.get(
        f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/rc/{RC_ID}/file",
        headers={"x-api-key": key}, params={"path": "rc_manifest.json"}, timeout=10,
    )
    assert r2.status_code == 200
    d = r2.json()
    assert d["rc_id"] == RC_ID
    assert "content" in d


def test_rc_artifact_rejects_traversal_outside_rc_id():
    import httpx
    key = _get_api_key()
    r = httpx.get(
        f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/rc/{RC_ID}/file",
        headers={"x-api-key": key},
        params={"path": f"../oos_hplc_investigator-rc-v1.0-20260626T183854/rc_manifest.json"},
        timeout=10,
    )
    assert r.status_code in (400, 403, 404), f"Traversal fuera del rc_id devolvió {r.status_code}"


def test_deployment_file_reader_blocks_env():
    import httpx
    key = _get_api_key()
    for badpath in [".env", "env.example", "data/chroma/x", "data/audit_logs/x.log"]:
        r = httpx.get(
            f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/deployment/file",
            headers={"x-api-key": key}, params={"path": badpath}, timeout=10,
        )
        assert r.status_code in (403, 404), (
            f"deployment/file con path={badpath!r} devolvió {r.status_code} (esperado 403/404)"
        )


def test_deployment_file_reader_allows_compose():
    import httpx
    key = _get_api_key()
    r = httpx.get(
        f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/deployment/file",
        headers={"x-api-key": key}, params={"path": "docker-compose.yml"}, timeout=10,
    )
    assert r.status_code == 200
    d = r.json()
    assert "content" in d
    assert "oos_hplc_investigator_api" in d["content"]
