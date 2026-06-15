"""
Tests de audit chain de fábrica (factory/audit/factory_audit.jsonl).

Cubre:
- write_event escribe entradas válidas con hash SHA-256
- La cadena encadena prev_entry_hash correctamente
- verify_chain detecta integridad correcta e incorrecta
- Eventos no reconocidos son rechazados con ValueError
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.core.audit_writer import (
    VALID_EVENTS,
    verify_chain,
    write_event,
)


# ── write_event ───────────────────────────────────────────────────────────────

class TestWriteEvent:
    def test_write_single_event_returns_entry(self, isolated_audit):
        entry = write_event("project_created", "test_proj", {"key": "value"})
        assert entry["event_type"] == "project_created"
        assert entry["project_id"] == "test_proj"
        assert entry["data"] == {"key": "value"}

    def test_entry_has_sha256_hash(self, isolated_audit):
        entry = write_event("project_created", "test_proj")
        assert entry["entry_hash"].startswith("sha256:")
        hash_hex = entry["entry_hash"][7:]
        assert len(hash_hex) == 64
        assert all(c in "0123456789abcdef" for c in hash_hex)

    def test_first_entry_has_genesis_prev_hash(self, isolated_audit):
        entry = write_event("project_created", "test_proj")
        assert entry["prev_entry_hash"] == "GENESIS"

    def test_second_entry_chains_to_first(self, isolated_audit):
        e1 = write_event("project_created", "p1")
        e2 = write_event("workspace_created", "p1")
        assert e2["prev_entry_hash"] == e1["entry_hash"]

    def test_chain_of_three_entries(self, isolated_audit):
        e1 = write_event("project_created", "p1")
        e2 = write_event("workspace_created", "p1")
        e3 = write_event("gates_executed", "p1", {"summary": {"PASS": 12}})
        assert e2["prev_entry_hash"] == e1["entry_hash"]
        assert e3["prev_entry_hash"] == e2["entry_hash"]

    def test_event_written_to_file(self, isolated_audit):
        write_event("project_created", "p1")
        assert isolated_audit.exists()
        lines = [l for l in isolated_audit.read_text().splitlines() if l.strip()]
        assert len(lines) == 1

    def test_multiple_events_appended(self, isolated_audit):
        for i in range(5):
            write_event("project_created", f"proj_{i}")
        lines = [l for l in isolated_audit.read_text().splitlines() if l.strip()]
        assert len(lines) == 5

    def test_each_line_is_valid_json(self, isolated_audit):
        write_event("project_created", "p1")
        write_event("workspace_created", "p1")
        for line in isolated_audit.read_text().splitlines():
            if line.strip():
                parsed = json.loads(line)
                assert "entry_hash" in parsed
                assert "event_type" in parsed

    def test_invalid_event_type_raises_value_error(self, isolated_audit):
        with pytest.raises(ValueError, match="Evento desconocido"):
            write_event("evento_inventado_xyzabc", "test_proj")

    def test_another_invalid_event_raises(self, isolated_audit):
        with pytest.raises(ValueError, match="Evento desconocido"):
            write_event("auto_deploy_bypassing_human", "test_proj")

    def test_all_valid_events_are_accepted(self, isolated_audit):
        """Todos los eventos en VALID_EVENTS deben ser aceptados."""
        for event_type in list(VALID_EVENTS):
            entry = write_event(event_type, "test_proj")
            assert "entry_hash" in entry, f"Evento válido '{event_type}' no escribió entry_hash"

    def test_entry_has_required_fields(self, isolated_audit):
        entry = write_event("project_created", "test_proj", {"x": 1})
        for field in ("timestamp", "entry_id", "event_type", "project_id", "data",
                      "prev_entry_hash", "entry_hash"):
            assert field in entry, f"Campo requerido ausente: {field}"


# ── verify_chain ──────────────────────────────────────────────────────────────

class TestVerifyChain:
    def test_empty_log_returns_verified_true_not_part11(self, isolated_audit):
        """Log vacío: verified=True (no hay errores) pero part11_compliant=False."""
        result = verify_chain()
        assert result["verified"] is True
        assert result["log_count"] == 0
        assert result["part11_compliant"] is False

    def test_single_event_chain_verifies(self, isolated_audit):
        write_event("project_created", "p1")
        result = verify_chain()
        assert result["verified"] is True
        assert result["hash_errors"] == 0
        assert result["chain_errors"] == 0

    def test_three_event_chain_verifies(self, isolated_audit):
        write_event("project_created", "p1")
        write_event("workspace_created", "p1")
        write_event("gates_executed", "p1", {"summary": {"PASS": 12}})
        result = verify_chain()
        assert result["verified"] is True
        assert result["log_count"] == 3
        assert result["verified_count"] == 3
        assert result["part11_compliant"] is True

    def test_corrupted_hash_is_detected(self, isolated_audit):
        """Si se modifica el hash almacenado, verify_chain debe reportar hash_error."""
        write_event("project_created", "p1")
        write_event("workspace_created", "p1")
        # Corromper la primera línea
        lines = isolated_audit.read_text().splitlines()
        first_entry = json.loads(lines[0])
        first_entry["entry_hash"] = "sha256:" + "0" * 64  # hash falso
        lines[0] = json.dumps(first_entry)
        isolated_audit.write_text("\n".join(lines) + "\n")
        result = verify_chain()
        assert result["verified"] is False
        assert result["hash_errors"] > 0

    def test_modified_body_is_detected(self, isolated_audit):
        """Si se modifica el cuerpo de una entrada, el hash ya no coincide."""
        write_event("project_created", "p1", {"original": True})
        lines = isolated_audit.read_text().splitlines()
        first_entry = json.loads(lines[0])
        # Cambiar el cuerpo sin actualizar el hash
        first_entry["data"]["original"] = False
        lines[0] = json.dumps(first_entry)
        isolated_audit.write_text("\n".join(lines) + "\n")
        result = verify_chain()
        assert result["verified"] is False

    def test_broken_chain_link_detected(self, isolated_audit):
        """Si prev_entry_hash no encadena correctamente, chain_error es detectado."""
        write_event("project_created", "p1")
        write_event("workspace_created", "p1")
        lines = isolated_audit.read_text().splitlines()
        # Modificar el segundo entry para romper la cadena:
        # cambiar prev_entry_hash manteniendo el hash correcto del body modificado
        second_entry = json.loads(lines[1])
        # Recalcular hash con prev_entry_hash alterado
        second_entry["prev_entry_hash"] = "sha256:" + "a" * 64  # enlace roto
        # Recalcular entry_hash para que no dé hash_error (solo chain_error)
        import hashlib
        body = {k: v for k, v in second_entry.items() if k != "entry_hash"}
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        new_hash = "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
        second_entry["entry_hash"] = new_hash
        lines[1] = json.dumps(second_entry)
        isolated_audit.write_text("\n".join(lines) + "\n")
        result = verify_chain()
        # El chain_error o hash_error debe ser detectado
        assert result["verified"] is False

    def test_verify_returns_correct_log_count(self, isolated_audit):
        for i in range(7):
            write_event("project_created", f"proj_{i}")
        result = verify_chain()
        assert result["log_count"] == 7

    def test_verify_reports_hash_algo(self, isolated_audit):
        write_event("project_created", "p1")
        result = verify_chain()
        assert result.get("hash_algo") == "sha256"

    def test_nonexistent_audit_file_returns_safe_result(self, isolated_audit):
        """Si el archivo no existe, verify_chain retorna estado vacío sin excepción."""
        # isolated_audit apunta a un archivo que aún no fue creado
        assert not isolated_audit.exists()
        result = verify_chain()
        assert result["verified"] is True
        assert result["log_count"] == 0
