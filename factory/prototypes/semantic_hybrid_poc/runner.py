"""Runner de un SemanticContextAssessment de extremo a extremo (POC).
compose -> generate (pinned) -> validate (fail-closed) -> gate de citas (R5) -> resultado.
Escribe SU PROPIO log (poc_log.jsonl), NUNCA el audit trail real. FASE 2, aislado."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from factory.prototypes.semantic_hybrid_poc import pinned_client as pc
from factory.prototypes.semantic_hybrid_poc.context_composer import compose
from factory.prototypes.semantic_hybrid_poc.prompt import build_prompt
from factory.prototypes.semantic_hybrid_poc.schema import SCTA_V1, SCHEMA_VERSION
from factory.prototypes.semantic_hybrid_poc.validator import validate
from factory.prototypes.semantic_hybrid_poc.citation_gate import apply_gate

POC_DIR = Path("factory/prototypes/semantic_hybrid_poc")
LOG = POC_DIR / "poc_log.jsonl"


def _cache_key(finding: dict, model_digest: str) -> str:
    parts = [finding.get("source_hash", ""), finding.get("subtype", ""),
             pc.PROMPT_VERSION, model_digest, str(pc.PINNED_OPTIONS["num_ctx"])]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def assess(finding: dict, model: str, *, inject_response: dict | None = None,
           options: dict | None = None) -> dict:
    """inject_response: si se pasa, se salta Ollama y se usa ese dict como respuesta
    del modelo (para el test de cita fabricada, R5). options: override de pinning
    (para probar num_ctx variable, etc.)."""
    t0 = time.time()
    ctx = compose(finding)
    prompt = build_prompt(finding, ctx)

    if inject_response is not None:
        digest = "INJECTED"
        gen = {"model": model, "model_digest": digest, "prompt_version": pc.PROMPT_VERSION,
               "options": dict(pc.PINNED_OPTIONS), "input_fingerprint": "INJECTED",
               "wall_time_s": 0.0, "raw_response": json.dumps(inject_response),
               "output_hash": hashlib.sha256(json.dumps(inject_response).encode()).hexdigest(),
               "done_reason": "stop", "eval_count": None, "prompt_eval_count": None,
               "transport_error": None}
    else:
        gen = pc.generate(model, prompt, SCTA_V1, options=options)
        digest = gen["model_digest"]

    payload, status, errs = validate(gen)

    if status == "FAILED":
        result = {
            "assessment_status": "FAILED", "failure_reason": "; ".join(errs)[:400],
            "semantic_coverage": "INDETERMINATE",
            "quote_verification_rate": None, "quotes_emitted": 0, "quotes_verified": 0,
            "fabricated_quotes": [], "required_elements": [], "grounded_quotes": [],
            "near_matches": 0, "elements_forced_unclear": 0,
        }
    else:
        gated = apply_gate(payload, ctx["scope_texts"])
        result = {
            "assessment_status": gated["assessment_status"],
            "failure_reason": None,
            "semantic_coverage": gated["semantic_coverage"],
            "quote_verification_rate": gated["quote_verification_rate"],
            "quotes_emitted": gated["quotes_emitted"],
            "quotes_verified": gated["quotes_verified"],
            "fabricated_quotes": gated["fabricated_quotes"],
            "near_matches": gated["near_matches"],
            "elements_forced_unclear": gated["elements_forced_unclear"],
            "required_elements": gated["elements_gated"],
            "grounded_quotes": gated["grounded_quotes"],
            "auditor_explanation": payload.get("auditor_explanation"),
            "contradictory_evidence": payload.get("contradictory_evidence"),
            "limitations": payload.get("limitations"),
        }

    record = {
        "schema_version": SCHEMA_VERSION,
        "finding_id": finding.get("finding_id"),
        "document_id": finding["document"], "page": finding.get("page"),
        "subtype": finding["subtype"], "rule_source": finding.get("technical_basis"),
        "analyzed_section": ctx["analyzed_section"],
        "document_scope_status": ctx["document_scope_status"],
        "context_chars": ctx["context_chars"], "n_local_claims": ctx["n_local_claims"],
        "model": model, "model_digest": digest, "prompt_version": pc.PROMPT_VERSION,
        "options": gen["options"], "input_fingerprint": gen["input_fingerprint"],
        "output_hash": gen["output_hash"], "done_reason": gen["done_reason"],
        "eval_count": gen["eval_count"], "prompt_eval_count": gen["prompt_eval_count"],
        "wall_time_s": gen["wall_time_s"], "total_time_s": round(time.time() - t0, 2),
        "cache_key": _cache_key(finding, digest),
        **result,
    }
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record
