"""SHADOW · CF-6 v2.0 · R1 — Relevance Model + contrato requirement-centric +
ProfessionalAssessmentRecord. Aceptación de la fase (ver instrucciones de
ejecución CF-6 v2.0 R1-R3, PARTE A / R1):

  - clasificación reproducible (correr dos veces, mismo resultado);
  - el candidato problemático de sec-0016 (rec-6b0c9965fd2f4e05, "medición de
    parámetros críticos" recuperado para 21_CFR_11.10(d)) cae en
    excluded_evidence[];
  - excluded_evidence[] nunca se serializa hacia el prompt del Composer
    (verificación de código, no solo declaración);
  - `decomposition.yaml` con 0 escrituras durante la fase (hash antes/después).
"""
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import pytest

from factory.regulatory.requirement_catalog.requirement_decomposition_loader import (
    DECOMPOSITION_PATH,
)
from factory.regulatory.shadow import composer as _skel
from factory.regulatory.shadow import relevance_model as rm
from factory.regulatory.shadow import requirement_centric as rc

SL = Path("docs_plan/shadow_llm")
SEC0016_BAD_CANDIDATE = "rec-6b0c9965fd2f4e05"


@pytest.fixture(scope="module")
def findings():
    return json.loads((SL / "FINAL_GMP_CORPUS_FINDINGS.json").read_text(encoding="utf-8"))["findings"]


@pytest.fixture(scope="module")
def l2_by_rid(findings):
    return {f["finding_record_id"]: f for f in findings}


@pytest.fixture(scope="module")
def skeleton(findings):
    return _skel.build_composer_skeleton(findings)


@pytest.fixture()
def sec0016(skeleton):
    return next(s for s in skeleton["sections"] if s["section_id"] == "sec-0016")


def _decomposition_hash() -> str:
    return hashlib.sha256(DECOMPOSITION_PATH.read_bytes()).hexdigest()


class TestDecompositionUntouched:
    def test_zero_writes_to_decomposition_yaml(self, sec0016, l2_by_rid):
        before = _decomposition_hash()
        rm.partition_entries(sec0016["entries"])
        rc.build_relevance_filtered_context(sec0016, l2_by_rid, {})
        after = _decomposition_hash()
        assert before == after, "decomposition.yaml fue escrito durante R1 -- prohibido"


class TestReproducibility:
    def test_classify_entry_is_deterministic(self, sec0016):
        for entry in sec0016["entries"]:
            v1 = rm.classify_entry(entry)
            v2 = rm.classify_entry(entry)
            assert v1 == v2

    def test_partition_entries_is_deterministic(self, sec0016):
        p1 = rm.partition_entries(sec0016["entries"])
        p2 = rm.partition_entries(sec0016["entries"])
        rids1 = [i["finding_record_id"] for i in p1["relevant_evidence"]]
        rids2 = [i["finding_record_id"] for i in p2["relevant_evidence"]]
        assert rids1 == rids2
        exc1 = [i["finding_record_id"] for i in p1["excluded_evidence"]]
        exc2 = [i["finding_record_id"] for i in p2["excluded_evidence"]]
        assert exc1 == exc2


class TestSec0016Acceptance:
    """El candidato de 'medición de parámetros críticos' (sc3, 'proceso de
    cambio de privilegios de cuentas') NUNCA debió llegar a un Composer LLM
    juzgando 21_CFR_11.10(d) -- diagnóstico real de CF-6 v1.3, diseño §0/§4."""

    def test_bad_candidate_is_excluded(self, sec0016):
        partition = rm.partition_entries(sec0016["entries"])
        relevant_rids = {i["finding_record_id"] for i in partition["relevant_evidence"]}
        excluded_rids = {i["finding_record_id"] for i in partition["excluded_evidence"]}
        assert SEC0016_BAD_CANDIDATE in excluded_rids
        assert SEC0016_BAD_CANDIDATE not in relevant_rids

    def test_bad_candidate_verdict_state_is_not_relevant(self, sec0016):
        entry = next(e for e in sec0016["entries"] if e["finding_record_id"] == SEC0016_BAD_CANDIDATE)
        verdict = rm.classify_entry(entry)
        assert verdict.relevance_state in (rm.IRRELEVANT, rm.INCONCLUSIVE)
        assert verdict.relevance_state != rm.RELEVANT
        assert verdict.relevance_state != rm.PARTIALLY_RELEVANT


class TestExcludedEvidenceNeverSentToLLM:
    def test_excluded_rids_absent_from_ctx(self, sec0016, l2_by_rid):
        ctx, relevance_record = rc.build_relevance_filtered_context(sec0016, l2_by_rid, {})
        assert rc.ctx_excludes_excluded_evidence(ctx, relevance_record)
        excluded_rids = {e["finding_record_id"] for e in relevance_record["excluded_evidence"]}
        assert SEC0016_BAD_CANDIDATE in excluded_rids

    def test_ctx_has_no_excluded_evidence_key(self, sec0016, l2_by_rid):
        ctx, _ = rc.build_relevance_filtered_context(sec0016, l2_by_rid, {})
        assert "excluded_evidence" not in ctx
        assert "candidate_evidence" not in ctx

    def test_static_code_never_references_excluded_evidence_in_prompt_build(self):
        """Inspección estática (R1.2 / CRIT-FILTER): la función que arma el
        contexto de sección para el Composer no construye ningún campo a
        partir de `excluded_evidence` -- solo lo devuelve por separado para
        auditoría."""
        src = inspect.getsource(rc.build_relevance_filtered_context)
        assert "for rid in relevant_rids" in src
        assert "for rid in excluded_rids" not in src
        assert "for rid in candidate_evidence" not in src


class TestRequirementCentricGrouping:
    def test_group_by_requirement_id_covers_all_entries(self, skeleton):
        grouped = rc.group_by_requirement_id(skeleton)
        total_entries = sum(len(s["entries"]) for s in skeleton["sections"] if any(
            e.get("requirement_id") for e in s["entries"]))
        n_grouped = sum(len(v) for v in grouped.values())
        n_with_rid = sum(1 for s in skeleton["sections"] for e in s["entries"] if e.get("requirement_id"))
        assert n_grouped == n_with_rid

    def test_group_by_requirement_id_preserves_origin_metadata(self, skeleton):
        grouped = rc.group_by_requirement_id(skeleton)
        rid, entries = next(iter(grouped.items()))
        for e in entries:
            assert "origin_section_id" in e
            assert "origin_document" in e
            assert "origin_section_type" in e

    def test_requirement_text_and_intent_sourced_from_decomposition(self):
        meta = rc.requirement_text_and_intent("21_CFR_11.10(d)")
        assert "privilegios" in meta["requirement_text"]
        assert meta["requirement_intent"]
        assert len(meta["subcriteria_ids"]) == 8


class TestProfessionalAssessmentRecord:
    def test_builds_without_llm(self, sec0016, l2_by_rid):
        _, relevance_record = rc.build_relevance_filtered_context(sec0016, l2_by_rid, {})
        rec = rc.build_professional_assessment_record(
            sec0016, "21_CFR_11.10(d)", relevance_record, fingerprint="235f724a…")
        assert rec.machine_adjudicated is False
        assert rec.system_response is None          # pendiente de R2 (LLM), no inventado aquí
        assert SEC0016_BAD_CANDIDATE not in rec.evidence_basis

    def test_record_to_dict_is_json_serializable(self, sec0016, l2_by_rid):
        _, relevance_record = rc.build_relevance_filtered_context(sec0016, l2_by_rid, {})
        rec = rc.build_professional_assessment_record(sec0016, "21_CFR_11.10(d)", relevance_record)
        json.dumps(rc.record_to_dict(rec), ensure_ascii=False)  # no debe lanzar


class TestFailClosed:
    def test_entry_without_requirement_id_is_excluded(self):
        entries = [{"finding_record_id": "rec-x", "requirement_id": None,
                    "anchored_quote_l2": "algo", "rationale_l2": ""}]
        partition = rm.partition_entries(entries)
        assert len(partition["relevant_evidence"]) == 0
        assert len(partition["excluded_evidence"]) == 1
        assert partition["excluded_evidence"][0]["verdict"].relevance_state == rm.INCONCLUSIVE

    def test_empty_relevant_evidence_flagged(self, l2_by_rid):
        section = {
            "section_id": "sec-test-empty", "document": "DOC-X", "regulation": "21_CFR_11.10(d)",
            "entries": [{"finding_record_id": "rec-y", "requirement_id": "21_CFR_11.10(d)",
                         "anchored_quote_l2": "zzz nada que ver zzz", "rationale_l2": "",
                         "subtype": "REGULATORY_INCONCLUSIVE", "risk_band": "LOW"}],
        }
        ctx, relevance_record = rc.build_relevance_filtered_context(section, l2_by_rid, {})
        assert relevance_record["fail_closed_empty_relevant"] is True
        assert ctx["anchored_quotes"] == "(sin citas ancladas)"
