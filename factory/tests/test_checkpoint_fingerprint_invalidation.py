"""
Tests de integración -- W5 V2 Fase F (corrección completa, 2026-07-25):
evaluate_chunked() consumiendo criterion_assessments real (D wireado a
runtime, no solo al módulo aislado semantic_evidence_verification.py) y
CheckpointStore invalidando checkpoints por fingerprint.

Todo con un FakeProvider determinista (mismo patrón que
factory/regulatory/golden_dataset/semantic_verification_golden_dataset.py)
-- nunca llama a Ollama real.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.engines.gmpai_integrity import chunked_engine as ce

PROMPT_PATH = Path(ce.__file__).parent / "prompts" / "part11_prompts.yaml"
_REQ_ID = "21_CFR_11.10(d)"
_ACCESS_CRITERIA = [
    "Mecanismo de control de acceso (propio o federado) sobre el sistema, descrito.",
    "Alta, cambio, revision periodica y revocacion de cuentas.",
    "Cuentas humanas individuales (no compartidas).",
    "Cuentas tecnicas no interactivas, si existen, gobernadas con propietario, proposito, privilegio "
    "minimo y prohibicion de firma electronica.",
    "Evidencia de prueba de acceso permitido y denegado.",
]
# Bilingue a proposito: las palabras en español satisfacen
# chunked_engine._is_topically_relevant (compara contra el label en
# español del checkpoint); las palabras en ingles satisfacen la
# relevancia semantica real de evidence_verifier.relevance_score contra
# requirement_terms.yaml (terminos reales en ingles para este requisito).
_EVIDENCIA = (
    "El acceso al sistema (access) esta limitado a individuos autorizados "
    "via role-based authentication with password login."
)


def _assessment(index: int, text: str, status: str, quote: str = "", location: str = "") -> dict:
    return {
        "criterion_index": index, "criterion_text": text, "status": status,
        "evidence_quote": quote, "evidence_location": location,
        "justification": "test", "limitations": "",
    }


def _checkpoints_payload(criterion_assessments: list | None) -> dict:
    meta = ce.load_prompt_meta(PROMPT_PATH)
    entries = []
    for cp in meta["checkpoints"]:
        if cp["req_id"] == _REQ_ID:
            entry = {"req_id": _REQ_ID, "estado": "cumple_parcialmente", "evidencia_exacta": _EVIDENCIA,
                      "brecha": "", "recomendacion": ""}
            if criterion_assessments is not None:
                entry["criterion_assessments"] = criterion_assessments
            entries.append(entry)
        else:
            entries.append({"req_id": cp["req_id"], "estado": "evidencia_insuficiente",
                             "evidencia_exacta": "", "brecha": "", "recomendacion": ""})
    return {"checkpoints": entries}


class _FakeProvider:
    def __init__(self, payload: dict, model_name: str = "fake-model"):
        self._payload = payload
        self._model_name = model_name
        self.generate_calls = 0

    @property
    def model_name(self) -> str:
        return self._model_name

    def generate(self, prompt: str) -> dict:
        self.generate_calls += 1
        return {"response": json.dumps(self._payload)}

    def show_digest(self) -> str:
        return "sha256:fake-digest"

    def runtime_version(self) -> str:
        return "0.0.0-fake"


def _find_finding(result: dict, req_id: str) -> dict:
    return next(f for f in result["findings"] if f["requisito_regulatorio"].startswith(req_id))


class TestEvaluateChunkedConsumesRealCriterionAssessments:

    def test_full_met_criterion_assessments_produce_real_d_and_acceptance(self):
        doc = _EVIDENCIA + " " + " ".join(_ACCESS_CRITERIA)
        assessments = [_assessment(i + 1, c, "MET", quote=c, location="pag 1") for i, c in enumerate(_ACCESS_CRITERIA)]
        provider = _FakeProvider(_checkpoints_payload(assessments))
        result = ce.evaluate_chunked(
            PROMPT_PATH, "fda_part11_agent", "v-test", [doc], "sys", "doc", "v1", "doc.pdf",
            "a" * 64, run_context="validation", provider=provider,
        )
        finding = _find_finding(result, _REQ_ID)
        assert finding["d_sufficiency"] == "MET"
        assert finding["substantive_evidence_accepted"] is True
        assert finding["operational_result"] == "EVALUATION_COMPLETE"

    def test_legacy_response_without_criterion_assessments_never_accepted(self):
        """Respuesta LEGACY (formato pre-Fase-F, sin criterion_assessments)
        -- D nunca se inventa, substantive_evidence_accepted nunca es True,
        aunque estado/evidencia serian suficientes bajo el contrato viejo."""
        doc = _EVIDENCIA
        provider = _FakeProvider(_checkpoints_payload(None))
        result = ce.evaluate_chunked(
            PROMPT_PATH, "fda_part11_agent", "v-test", [doc], "sys", "doc", "v1", "doc.pdf",
            "b" * 64, run_context="validation", provider=provider,
        )
        finding = _find_finding(result, _REQ_ID)
        assert finding["d_sufficiency"] == "NOT_ASSESSABLE"
        assert finding["substantive_evidence_accepted"] is False
        assert finding["operational_result"] == "EVALUATION_INCOMPLETE"

    def test_duplicate_criterion_index_never_inflates_result(self):
        doc = _EVIDENCIA + " " + " ".join(_ACCESS_CRITERIA)
        assessments = [_assessment(i + 1, c, "MET", quote=c, location="pag 1") for i, c in enumerate(_ACCESS_CRITERIA)]
        assessments.append(_assessment(1, _ACCESS_CRITERIA[0], "MET", quote=_ACCESS_CRITERIA[0], location="pag 1"))
        provider = _FakeProvider(_checkpoints_payload(assessments))
        result = ce.evaluate_chunked(
            PROMPT_PATH, "fda_part11_agent", "v-test", [doc], "sys", "doc", "v1", "doc.pdf",
            "c" * 64, run_context="validation", provider=provider,
        )
        finding = _find_finding(result, _REQ_ID)
        assert finding["d_sufficiency"] == "NOT_ASSESSABLE"
        assert finding["substantive_evidence_accepted"] is False

    def test_invented_criterion_never_inflates_result(self):
        doc = _EVIDENCIA + " " + " ".join(_ACCESS_CRITERIA)
        assessments = [_assessment(i + 1, c, "MET", quote=c, location="pag 1") for i, c in enumerate(_ACCESS_CRITERIA)]
        assessments.append(_assessment(6, "Criterio inventado fuera del catalogo", "MET",
                                        quote=doc, location="pag 1"))
        provider = _FakeProvider(_checkpoints_payload(assessments))
        result = ce.evaluate_chunked(
            PROMPT_PATH, "fda_part11_agent", "v-test", [doc], "sys", "doc", "v1", "doc.pdf",
            "d" * 64, run_context="validation", provider=provider,
        )
        finding = _find_finding(result, _REQ_ID)
        assert finding["d_sufficiency"] == "NOT_ASSESSABLE"
        assert finding["substantive_evidence_accepted"] is False


class TestCheckpointInvalidatedByFingerprintMismatch:

    def test_checkpoint_from_older_prompt_version_never_resumed(self, tmp_path):
        """Simula un checkpoint guardado bajo un contrato viejo
        (prompt_version=1.0.0, sin criterion_assessments) -- la corrida
        actual (prompt_version=1.1.0 real) nunca debe reanudarlo."""
        store = ce.CheckpointStore(tmp_path)
        old_fingerprint = {
            "prompt_version": "1.0.0", "schema_version": None,
            "model_digest": "sha256:fake-digest", "document_sha256": "e" * 64,
            "agent_version": "v-test", "catalog_version": "1.0", "catalog_sha256": "old-hash-simulado",
        }
        store.save("run-old-format", {
            "run_id": "run-old-format", "document_sha256": "e" * 64, "agent_id": "fda_part11_agent",
            "documento": "doc", "archivo": "doc.pdf", "total_chunks": 1,
            "chunk_executions": [{"dummy": True}], "completed": False,
            "fingerprint": old_fingerprint,
        })

        meta = ce.load_prompt_meta(PROMPT_PATH)
        real_fingerprint = ce.build_run_fingerprint(
            meta, model_digest="sha256:fake-digest", document_sha256="e" * 64, agent_version="v-test",
            use_verified_pipeline=False,
        )
        assert real_fingerprint != old_fingerprint  # confirma que la simulacion es realista

        resumable, mismatch = store.find_resumable("e" * 64, "fda_part11_agent", real_fingerprint)
        assert resumable is None
        assert mismatch is not None
        assert mismatch["discarded_run_id"] == "run-old-format"

    def test_evaluate_chunked_starts_fresh_run_when_checkpoint_fingerprint_mismatches(self, tmp_path):
        """Extremo a extremo: evaluate_chunked() con un checkpoint_store
        que solo tiene un checkpoint de contrato viejo -- debe iniciar una
        corrida NUEVA (no reanudar, no reusar chunk_executions viejos) y
        dejarlo explicito en preflight_metadata."""
        store = ce.CheckpointStore(tmp_path)
        store.save("run-old-format", {
            "run_id": "run-old-format", "document_sha256": "f" * 64, "agent_id": "fda_part11_agent",
            "documento": "doc", "archivo": "doc.pdf", "total_chunks": 1,
            "chunk_executions": [{"dummy": True}], "completed": False,
            "fingerprint": {"prompt_version": "1.0.0", "schema_version": None},
        })
        provider = _FakeProvider(_checkpoints_payload(None))
        result = ce.evaluate_chunked(
            PROMPT_PATH, "fda_part11_agent", "v-test", [_EVIDENCIA], "sys", "doc", "v1", "doc.pdf",
            "f" * 64, run_context="validation", provider=provider, checkpoint_store=store,
        )
        assert result["run_id"] != "run-old-format"
        assert result["preflight_metadata"]["checkpoint_fingerprint_mismatch_discarded"] is True
        assert result["preflight_metadata"]["checkpoint_fingerprint_mismatch_detail"]["discarded_run_id"] == "run-old-format"
        # El chunk se proceso desde cero -- 1 llamada real al provider, no 0.
        assert provider.generate_calls == 1

    def test_checkpoint_with_matching_fingerprint_resumes_normally(self, tmp_path):
        """Guardia de no-regresion: un fingerprint que SI coincide sigue
        permitiendo reanudar (ver tambien test_gmpai_chunked_engine.py)."""
        store = ce.CheckpointStore(tmp_path)
        meta = ce.load_prompt_meta(PROMPT_PATH)
        fingerprint = ce.build_run_fingerprint(
            meta, model_digest="sha256:fake-digest", document_sha256="g" * 64, agent_version="v-test",
            use_verified_pipeline=False,
        )
        store.save("run-matching", {
            "run_id": "run-matching", "document_sha256": "g" * 64, "agent_id": "fda_part11_agent",
            "documento": "doc", "archivo": "doc.pdf", "total_chunks": 2,
            "chunk_executions": [{"dummy": True}], "completed": False,
            "fingerprint": fingerprint,
        })
        resumable, mismatch = store.find_resumable("g" * 64, "fda_part11_agent", fingerprint)
        assert mismatch is None
        assert resumable is not None
        assert resumable["run_id"] == "run-matching"


class TestSubstantiveSupportWiredToDecision:
    """W5 V2 Fase F -- D cableada a la decision substantive_support en la
    consolidacion de evaluate_chunked (2026-07-25)."""

    def test_positive_finding_with_full_met_is_supported(self):
        doc = _EVIDENCIA + " " + " ".join(_ACCESS_CRITERIA)
        assessments = [_assessment(i + 1, c, "MET", quote=c, location="pag 1") for i, c in enumerate(_ACCESS_CRITERIA)]
        provider = _FakeProvider(_checkpoints_payload(assessments))
        result = ce.evaluate_chunked(
            PROMPT_PATH, "fda_part11_agent", "v-test", [doc], "sys", "doc", "v1", "doc.pdf",
            "s" * 64, run_context="validation", provider=provider,
        )
        finding = _find_finding(result, _REQ_ID)
        assert finding["estado"] == "cumple_parcialmente"      # observacion del modelo intacta
        assert finding["substantive_support"] == "SUPPORTED"
        assert result["substantive_support_summary"]["SUPPORTED"] >= 1

    def test_positive_finding_legacy_response_is_not_supported(self):
        """Sin criterion_assessments (D=NOT_ASSESSABLE) un estado positivo
        nunca se presenta como sustentado -- fail-closed, revision humana."""
        doc = _EVIDENCIA
        provider = _FakeProvider(_checkpoints_payload(None))
        result = ce.evaluate_chunked(
            PROMPT_PATH, "fda_part11_agent", "v-test", [doc], "sys", "doc", "v1", "doc.pdf",
            "t" * 64, run_context="validation", provider=provider,
        )
        finding = _find_finding(result, _REQ_ID)
        assert finding["estado"] == "cumple_parcialmente"      # el modelo dijo cumple_parcialmente
        assert finding["substantive_support"] == "NOT_SUPPORTED"
        assert finding["revision_humana_requerida"] is True
        assert result["substantive_support_summary"]["NOT_SUPPORTED"] >= 1

    def test_absence_findings_are_not_applicable(self):
        """Un checkpoint sin candidato positivo (evidencia_insuficiente en
        todos los chunks) -> substantive_support=NOT_APPLICABLE."""
        doc = _EVIDENCIA
        provider = _FakeProvider(_checkpoints_payload(None))
        result = ce.evaluate_chunked(
            PROMPT_PATH, "fda_part11_agent", "v-test", [doc], "sys", "doc", "v1", "doc.pdf",
            "u" * 64, run_context="validation", provider=provider,
        )
        # los otros 4 checkpoints del prompt quedan evidencia_insuficiente
        na = [f for f in result["findings"] if f["substantive_support"] == "NOT_APPLICABLE"]
        assert na, "debe haber al menos un finding NOT_APPLICABLE (checkpoints sin candidato positivo)"
        assert all(f["estado"] not in ("cumple", "cumple_parcialmente") for f in na)

    def test_summary_counts_cover_all_findings_and_reach_audit(self, monkeypatch, tmp_path):
        from factory.core import audit_writer
        audit_file = tmp_path / "factory_audit.jsonl"
        monkeypatch.setattr(audit_writer, "AUDIT_FILE", audit_file)
        monkeypatch.setattr(audit_writer, "_last_entry_hash", None)

        doc = _EVIDENCIA
        provider = _FakeProvider(_checkpoints_payload(None))
        result = ce.evaluate_chunked(
            PROMPT_PATH, "fda_part11_agent", "v-test", [doc], "sys", "doc", "v1", "doc.pdf",
            "v" * 64, run_context="production", provider=provider,
        )
        summary = result["substantive_support_summary"]
        assert sum(summary.values()) == len(result["findings"])  # cubre TODOS los findings
        entry = json.loads(audit_file.read_text(encoding="utf-8").strip().splitlines()[-1])
        assert entry["data"]["substantive_support_summary"] == summary
