"""W5.3 Fase 5.2 -- tests de los parámetros de persistencia de evidencia de
validación (_by_req_candidates), aprobados por el usuario: path_policy,
tamaño, retención, permisos, exclusión de paquetes productivos.

NOTA DE ALCANCE: este módulo NO está cableado en evaluate_chunked()
todavía (eso es Fase 5.4) -- estos tests prueban el MECANISMO de escritura
de forma aislada."""
from __future__ import annotations

import json
import stat

import pytest

from factory.core import path_policy
from factory.regulatory import validation_evidence_writer as writer

VALID_RUN_ID = "w5v3-validation-abcdef012345"


# ── path_policy ──────────────────────────────────────────────────────────

def test_resolve_validation_evidence_accepts_valid_run_id(tmp_path):
    target = path_policy.resolve_validation_evidence(VALID_RUN_ID, tmp_path)
    assert target == (tmp_path / f"{VALID_RUN_ID}.json").resolve()
    assert target.suffix == ".json"


@pytest.mark.parametrize("bad_run_id", [
    "../../../etc/passwd",
    "w5v3-validation-",  # sin hex
    "w5v3-validation-ZZZZZZZZZZZZ",  # no hex
    "production-run-abcdef012345",  # prefijo equivocado
    "w5v3-validation-abcdef0123456789",  # demasiado largo
    "",
])
def test_resolve_validation_evidence_rejects_invalid_run_id(tmp_path, bad_run_id):
    with pytest.raises(ValueError):
        path_policy.resolve_validation_evidence(bad_run_id, tmp_path)


def test_resolve_validation_evidence_confines_under_base(tmp_path):
    target = path_policy.resolve_validation_evidence(VALID_RUN_ID, tmp_path)
    assert target.is_relative_to(tmp_path.resolve())


# ── tamaño ───────────────────────────────────────────────────────────────

def test_write_validation_evidence_rejects_oversized_content(tmp_path):
    huge_content = {"padding": "x" * (writer.VALIDATION_EVIDENCE_MAX_BYTES + 1)}
    with pytest.raises(writer.EvidenceTooLargeError):
        writer.write_validation_evidence(
            VALID_RUN_ID, "sha-doc-1", "validation", huge_content,
            evidence_base=tmp_path,
        )
    # Fail-closed: no debe quedar ningun archivo parcial escrito.
    assert list(tmp_path.glob("*.json")) == []


def test_write_validation_evidence_never_truncates_silently(tmp_path):
    """Confirma que un contenido grande pero DENTRO del limite se escribe
    completo, sin recortar -- mismo principio de FS_v1.2 (no truncar)."""
    content = {"text": "y" * 100_000}
    path = writer.write_validation_evidence(
        VALID_RUN_ID, "sha-doc-1", "validation", content, evidence_base=tmp_path,
    )
    written = json.loads(path.read_text(encoding="utf-8"))
    assert len(written["content"]["text"]) == 100_000


# ── permisos ─────────────────────────────────────────────────────────────

def test_write_validation_evidence_sets_permissions_0640(tmp_path):
    path = writer.write_validation_evidence(
        VALID_RUN_ID, "sha-doc-1", "validation", {"k": "v"}, evidence_base=tmp_path,
    )
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o640


def test_write_validation_evidence_sets_directory_permissions_0750(tmp_path):
    base = tmp_path / "nested" / "evidence"
    writer.write_validation_evidence(
        VALID_RUN_ID, "sha-doc-1", "validation", {"k": "v"}, evidence_base=base,
    )
    assert stat.S_IMODE(base.stat().st_mode) == 0o750


def test_write_validation_evidence_owner_matches_directory_not_hardcoded(tmp_path):
    """Fase 5.4.4 (gobernanza): el propietario/grupo del archivo escrito
    debe coincidir con el del directorio ya autorizado -- nunca un
    UID/GID hardcodeado en el codigo. En un proceso sin privilegio de
    chown (caso normal fuera de un contenedor root) esto ya se cumple
    trivialmente porque el archivo nace con el UID/GID del proceso, que es
    el mismo que creo el directorio."""
    path = writer.write_validation_evidence(
        VALID_RUN_ID, "sha-doc-1", "validation", {"k": "v"}, evidence_base=tmp_path,
    )
    file_stat = path.stat()
    dir_stat = tmp_path.stat()
    assert file_stat.st_uid == dir_stat.st_uid
    assert file_stat.st_gid == dir_stat.st_gid


def test_write_validation_evidence_is_atomic_no_partial_file_left_on_success(tmp_path):
    writer.write_validation_evidence(
        VALID_RUN_ID, "sha-doc-1", "validation", {"k": "v"}, evidence_base=tmp_path,
    )
    leftovers = [p for p in tmp_path.iterdir() if p.suffix == ".tmp" or ".tmp" in p.name]
    assert leftovers == []


def test_write_validation_evidence_atomic_write_uses_rename(tmp_path, monkeypatch):
    """Confirma que la escritura pasa por os.replace() (atomica), no un
    write directo al nombre final -- una corrida interrumpida a mitad de
    escritura nunca deja el archivo final truncado/corrupto."""
    import os as os_mod
    calls = []
    real_replace = os_mod.replace

    def spy_replace(src, dst):
        calls.append((str(src), str(dst)))
        return real_replace(src, dst)

    monkeypatch.setattr(os_mod, "replace", spy_replace)
    path = writer.write_validation_evidence(
        VALID_RUN_ID, "sha-doc-1", "validation", {"k": "v"}, evidence_base=tmp_path,
    )
    assert len(calls) == 1
    assert calls[0][1] == str(path)
    assert ".tmp" in calls[0][0]


# ── retención (sin borrado automático) ──────────────────────────────────

def test_writer_module_exposes_no_delete_or_expiry_function():
    exported = [name for name in dir(writer) if not name.startswith("_")]
    forbidden_substrings = ("delete", "purge", "expire", "cleanup", "ttl", "remove")
    offending = [n for n in exported if any(s in n.lower() for s in forbidden_substrings)]
    assert offending == [], f"El modulo expone funciones de borrado/expiracion: {offending}"


def test_path_policy_module_exposes_no_delete_for_validation_evidence():
    exported = [name for name in dir(path_policy) if "validation_evidence" in name.lower()]
    forbidden_substrings = ("delete", "purge", "expire", "cleanup", "ttl", "remove")
    offending = [n for n in exported if any(s in n.lower() for s in forbidden_substrings)]
    assert offending == []


# ── run_context obligatorio (mismo gate que generate_controlled) ────────

def test_write_validation_evidence_blocks_production_context(tmp_path):
    with pytest.raises(writer.ProductionEvidenceWriteError):
        writer.write_validation_evidence(
            VALID_RUN_ID, "sha-doc-1", "production", {"k": "v"}, evidence_base=tmp_path,
        )
    assert list(tmp_path.glob("*.json")) == []


def test_write_validation_evidence_blocks_any_non_validation_context(tmp_path):
    for bad_context in ("production", "staging", "", "VALIDATION"):
        with pytest.raises(writer.ProductionEvidenceWriteError):
            writer.write_validation_evidence(
                VALID_RUN_ID, "sha-doc-1", bad_context, {"k": "v"}, evidence_base=tmp_path,
            )


# ── contenido: doble anclaje run_id/document_sha256 + hash no circular ──

def test_written_evidence_contains_run_id_and_document_sha256():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        from pathlib import Path
        path = writer.write_validation_evidence(
            VALID_RUN_ID, "sha-doc-real-123", "validation", {"k": "v"}, evidence_base=Path(d),
        )
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["run_id"] == VALID_RUN_ID
        assert data["document_sha256"] == "sha-doc-real-123"
        assert data["classification"] == "INTERNAL_VALIDATION_EVIDENCE"


def test_content_sha256_is_present_and_self_consistent(tmp_path):
    path = writer.write_validation_evidence(
        VALID_RUN_ID, "sha-doc-1", "validation", {"k": "v"}, evidence_base=tmp_path,
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "content_sha256" in data
    assert len(data["content_sha256"]) == 64


# ── exclusión de paquetes productivos ───────────────────────────────────

def test_default_evidence_base_is_outside_gmpai_reports_packaging_root():
    """El árbol de evidencia de validación vive completamente fuera de
    GMPAI/reports/<run_id>/, que es la raíz real que empaqueta
    gmpai_document_validation (ver package_v5.py de W5v2) -- por
    construcción, ningún ZIP final de esa fábrica puede arrastrar
    evidencia de validación sin un cambio explícito de alcance."""
    base_str = str(writer.VALIDATION_EVIDENCE_BASE)
    assert "GMPAI/reports" not in base_str
    assert "GMPAI" not in base_str
    assert "factory/regulatory/validation_evidence" in base_str


def test_default_evidence_base_is_outside_any_paquete_final_glob():
    assert "paquete_final" not in str(writer.VALIDATION_EVIDENCE_BASE)
