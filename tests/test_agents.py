"""
GMP AI Copilot — Validation Test Suite
17 tests covering connectivity, API contract, data integrity, and regulatory quality.
"""
import httpx
import pytest

BASE_URL = "http://localhost:8000"
OLLAMA_TIMEOUT = 180


# ─── Connectivity (2) ───────────────────────────────────────────────────────


def test_health():
    r = httpx.get(f"{BASE_URL}/health", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["api"] == "ok"


def test_v1_query_returns_200():
    r = httpx.post(
        f"{BASE_URL}/api/v1/query",
        json={"question": "What is GMP?", "agent": "fda"},
        timeout=OLLAMA_TIMEOUT,
    )
    assert r.status_code == 200


# ─── API Contract (5) ────────────────────────────────────────────────────────


def test_response_field_exists():
    """P3: endpoint must return 'response' (primary) or 'answer' (alias)."""
    r = httpx.post(
        f"{BASE_URL}/api/v1/query",
        json={"question": "test", "agent": "fda"},
        timeout=OLLAMA_TIMEOUT,
    )
    assert r.status_code == 200
    data = r.json()
    assert "response" in data or "answer" in data


def test_elapsed_seconds_present():
    """P3: endpoint must return elapsed_seconds > 0."""
    r = httpx.post(
        f"{BASE_URL}/api/v1/query",
        json={"question": "test", "agent": "fda"},
        timeout=OLLAMA_TIMEOUT,
    )
    assert r.status_code == 200
    data = r.json()
    assert "elapsed_seconds" in data
    assert data["elapsed_seconds"] > 0


def test_knowledge_stats():
    r = httpx.get(f"{BASE_URL}/api/v1/knowledge/stats", timeout=10)
    assert r.status_code == 200


def test_audit_verify():
    r = httpx.get(f"{BASE_URL}/api/v1/audit/verify", timeout=10)
    assert r.status_code == 200


def test_knowledge_stats_structure():
    """P2: /knowledge/stats must contain fda_collection and iq_collection."""
    r = httpx.get(f"{BASE_URL}/api/v1/knowledge/stats", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert "fda_collection" in data
    assert "iq_collection" in data
    assert "count" in data["fda_collection"]
    assert "count" in data["iq_collection"]


def test_audit_verify_structure():
    """Audit verify must return verified, log_count, hash_algo."""
    r = httpx.get(f"{BASE_URL}/api/v1/audit/verify", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert "verified" in data
    assert "log_count" in data
    assert "hash_algo" in data
    assert isinstance(data["verified"], bool)
    assert isinstance(data["log_count"], int)


def test_protocol_template_iq():
    r = httpx.get(f"{BASE_URL}/api/v1/protocol-template/IQ", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["protocol_type"] == "IQ"
    assert "template" in data


# ─── Protocol Templates (3) ──────────────────────────────────────────────────


def test_protocol_template_oq():
    r = httpx.get(f"{BASE_URL}/api/v1/protocol-template/OQ", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["protocol_type"] == "OQ"
    assert "template" in data
    sections = data["template"]["sections"]
    assert len(sections) >= 3
    # Must have operational tests
    test_ids = [
        t["id"]
        for s in sections
        for t in s.get("tests", [])
    ]
    assert any(tid.startswith("OQ-") for tid in test_ids)


def test_protocol_template_pq():
    r = httpx.get(f"{BASE_URL}/api/v1/protocol-template/PQ", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["protocol_type"] == "PQ"
    assert "template" in data
    # PQ must require minimum 3 runs
    content = str(data)
    assert "3" in content or "three" in content.lower()


def test_protocol_template_invalid():
    """Unknown protocol type must return 404, not 500."""
    r = httpx.get(f"{BASE_URL}/api/v1/protocol-template/XX", timeout=10)
    assert r.status_code in (404, 400)


# ─── Regulatory Quality (5) ──────────────────────────────────────────────────


def test_query_context_used():
    """P1: ChromaDB must be populated — context_used=True for regulatory queries."""
    r = httpx.post(
        f"{BASE_URL}/api/v1/query",
        json={"question": "What does 21 CFR Part 11 require?", "agent": "fda"},
        timeout=OLLAMA_TIMEOUT,
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("context_used") is True, (
        "ChromaDB is empty or retriever failed. Run P1 corpus ingestion."
    )


def test_query_cita_21cfr_11():
    """Model must cite Part 11 concepts when asked about electronic records."""
    r = httpx.post(
        f"{BASE_URL}/api/v1/query",
        json={"question": "What are the requirements for electronic records under 21 CFR Part 11?", "agent": "fda"},
        timeout=OLLAMA_TIMEOUT,
    )
    assert r.status_code == 200
    data = r.json()
    answer = (data.get("response") or data.get("answer") or "").lower()
    assert any(kw in answer for kw in ["11.10", "part 11", "electronic record", "electronic signature", "audit trail"]), (
        f"Expected Part 11 keywords in answer. Got: {answer[:200]}"
    )


def test_query_alcoa_principles():
    """Model must mention ALCOA+ principles when asked about data integrity."""
    r = httpx.post(
        f"{BASE_URL}/api/v1/query",
        json={"question": "What are the ALCOA+ principles for data integrity in GMP?", "agent": "fda"},
        timeout=OLLAMA_TIMEOUT,
    )
    assert r.status_code == 200
    data = r.json()
    answer = (data.get("response") or data.get("answer") or "").lower()
    assert any(kw in answer for kw in ["attributable", "alcoa", "legible", "contemporaneous", "original"]), (
        f"Expected ALCOA keywords in answer. Got: {answer[:200]}"
    )


def test_query_iq_checks():
    """Model must mention installation checks when asked about IQ."""
    r = httpx.post(
        f"{BASE_URL}/api/v1/query",
        json={"question": "What must be verified during Installation Qualification (IQ)?", "agent": "fda"},
        timeout=OLLAMA_TIMEOUT,
    )
    assert r.status_code == 200
    data = r.json()
    answer = (data.get("response") or data.get("answer") or "").lower()
    assert any(kw in answer for kw in ["installation", "iq", "calibrat", "equipment", "specification"]), (
        f"Expected IQ keywords in answer. Got: {answer[:200]}"
    )


def test_query_equipment_reloc():
    """Model must mention requalification when asked about equipment relocation."""
    r = httpx.post(
        f"{BASE_URL}/api/v1/query",
        json={"question": "Does moving equipment to a new location require requalification?", "agent": "fda"},
        timeout=OLLAMA_TIMEOUT,
    )
    assert r.status_code == 200
    data = r.json()
    answer = (data.get("response") or data.get("answer") or "").lower()
    assert any(kw in answer for kw in ["requalif", "qualif", "oq", "validation", "iq"]), (
        f"Expected requalification keywords in answer. Got: {answer[:200]}"
    )


# ─── Standalone runner ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    tests = [
        test_health,
        test_v1_query_returns_200,
        test_knowledge_stats,
        test_audit_verify,
        test_response_field_exists,
        test_elapsed_seconds_present,
        test_knowledge_stats_structure,
        test_audit_verify_structure,
        test_protocol_template_iq,
        test_protocol_template_oq,
        test_protocol_template_pq,
        test_protocol_template_invalid,
        test_query_context_used,
        test_query_cita_21cfr_11,
        test_query_alcoa_principles,
        test_query_iq_checks,
        test_query_equipment_reloc,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except Exception as exc:
            print(f"FAIL  {t.__name__}: {exc}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
