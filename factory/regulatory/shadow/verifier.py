"""SHADOW · G2.1 / G2.2 — verificadores deterministas fail-closed.

G2.1  verify_expert_envelope()  — verificador fail-closed de la envoltura de
      OPINIÓN de un experto. Combina la validación estructural (contracts.py)
      con el ANCLAJE real de cada cita contra L1/L2 (reutiliza
      evidence_verifier.match_citation, umbrales intactos). Cualquier check que
      no se pueda evaluar -> SHADOW_REJECTED (nunca pasa por duda).
      Solo una envoltura SHADOW_ACCEPTED puede llegar al composer / reporte.

G2.2  verify_report_coverage() / assert_full_coverage() — verificador de
      cobertura: cada uno de los 457 finding_record_id L2 debe estar
      referenciado por el reporte; 0 referencias a ids que no existen en L2.
      Omitir 1 finding -> covered=False y assert_full_coverage() falla.

CERO LLM · CERO red · determinista · no muta ningún Finding.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from factory.regulatory.evidence_verifier import match_citation
from factory.regulatory.shadow import contracts as _c

SHADOW_ACCEPTED = "SHADOW_ACCEPTED"
SHADOW_REJECTED = "SHADOW_REJECTED"

#: tipos de coincidencia de cita que cuentan como "ancla en L1/L2".
_ANCHOR_MATCH_TYPES = ("exact", "normalized", "despaced", "fuzzy")


# ───────────────────────────── G2.1 ─────────────────────────────────────

@dataclass
class VerifierResult:
    status: str                              # SHADOW_ACCEPTED | SHADOW_REJECTED
    finding_record_id: str | None
    expert: str | None
    structural_violations: list = field(default_factory=list)
    anchoring_violations: list = field(default_factory=list)

    @property
    def reasons(self) -> list:
        return self.structural_violations + self.anchoring_violations

    @property
    def accepted(self) -> bool:
        return self.status == SHADOW_ACCEPTED


def _evidence_texts(l2_finding: dict, evidence_index) -> list[str]:
    """Textos de L1/L2 contra los que se ancla una cita: la cita anclada del
    propio finding + los source_text de los claims candidatos entregados en el
    paquete de entrada (si los hay)."""
    out: list[str] = []
    q = (l2_finding.get("evidence") or {}).get("anchored_quote") or l2_finding.get("source_text")
    if q:
        out.append(q)
    for c in (evidence_index or []):
        t = c.get("source_text") or c.get("quote") or c.get("text")
        if t:
            out.append(t)
    return out


def _quote_anchors(quote: str, evidence_texts: list[str]) -> bool:
    if not (quote or "").strip():
        return False
    for src in evidence_texts:
        mtype, _ = match_citation(quote, src or "")
        if mtype in _ANCHOR_MATCH_TYPES:
            return True
    return False


def verify_expert_envelope(envelope: dict, *, l2_finding: dict,
                           evidence_index: list | None = None,
                           declared_counterparts: list | None = None) -> VerifierResult:
    """Fail-closed. `evidence_index`: claims candidatos del paquete de entrada
    (opcional). `declared_counterparts`: finding_record_id que la envoltura
    puede citar además del propio (p.ej. contrapartes cross-domain)."""
    expert = envelope.get("expert")
    frid = envelope.get("finding_record_id")

    structural = _c.validate_output_envelope(envelope, l2_finding=l2_finding)

    anchoring: list = []
    ev_texts = _evidence_texts(l2_finding, evidence_index)
    allowed_ids = {l2_finding.get("finding_record_id"), *(declared_counterparts or [])}
    cites = envelope.get("anchored_citations")

    is_composer = expert == "COMPOSER"
    if not is_composer:
        # evidencia vacía -> rechazo (fixture G2.1 obligatorio)
        if not isinstance(cites, list) or not cites or all(
                not (c.get("quote") or "").strip() for c in (cites or [])):
            anchoring.append("empty_evidence: >=1 cita anclada no vacía es obligatoria")
        # sin texto de L1/L2 para comparar -> no se puede verificar el anclaje -> rechazo
        if not ev_texts:
            anchoring.append("fail_closed: sin texto de evidencia L1/L2 para verificar el anclaje")

    for i, c in enumerate(cites or []):
        if not isinstance(c, dict):
            anchoring.append(f"anchored_citations[{i}] no es objeto")
            continue
        q = c.get("quote") or ""
        if not q.strip():
            anchoring.append(f"anchored_citations[{i}] quote vacío")
            continue
        if ev_texts and not _quote_anchors(q, ev_texts):
            anchoring.append(f"anchored_citations[{i}] cita NO ancla en L1/L2: {q[:60]!r}")
        rid = c.get("finding_record_id")
        if rid is not None and rid not in allowed_ids:
            anchoring.append(f"anchored_citations[{i}] finding_record_id {rid!r} no declarado")
        sh = c.get("source_hash")
        if sh is not None and sh != l2_finding.get("source_hash"):
            anchoring.append(f"anchored_citations[{i}] source_hash {sh!r} != L2 "
                             f"{l2_finding.get('source_hash')!r}")

    status = SHADOW_ACCEPTED if (not structural and not anchoring) else SHADOW_REJECTED
    return VerifierResult(status, frid, expert, structural, anchoring)


def filter_accepted(pairs: list[tuple[dict, dict]], **kw) -> tuple[list, list]:
    """`pairs`: [(envelope, l2_finding), …]. Devuelve (aceptadas, resultados_rechazo).
    Ninguna envoltura rechazada llega al reporte."""
    accepted, rejected = [], []
    for env, l2 in pairs:
        r = verify_expert_envelope(env, l2_finding=l2, **kw)
        (accepted if r.accepted else rejected).append((env, r) if r.accepted else r)
    return [e for e, _ in accepted], rejected


# ───────────────────────────── G2.2 ─────────────────────────────────────

class CoverageError(AssertionError):
    pass


@dataclass
class CoverageResult:
    covered: bool
    total_l2: int
    referenced_valid: int
    missing: list = field(default_factory=list)          # L2 ids no referenciados
    unsupported: list = field(default_factory=list)      # ids referenciados que no existen en L2


def verify_report_coverage(l2_findings: list[dict],
                           referenced_finding_record_ids) -> CoverageResult:
    l2_ids = {f["finding_record_id"] for f in l2_findings}
    ref = set(referenced_finding_record_ids)
    missing = sorted(l2_ids - ref)
    unsupported = sorted(ref - l2_ids)
    return CoverageResult(
        covered=(not missing and not unsupported),
        total_l2=len(l2_ids),
        referenced_valid=len(ref & l2_ids),
        missing=missing,
        unsupported=unsupported,
    )


def assert_full_coverage(l2_findings: list[dict],
                         referenced_finding_record_ids) -> CoverageResult:
    r = verify_report_coverage(l2_findings, referenced_finding_record_ids)
    if not r.covered:
        raise CoverageError(
            f"cobertura incompleta: {len(r.missing)} finding(s) sin referenciar "
            f"(p.ej. {r.missing[:3]}), {len(r.unsupported)} referencia(s) sin finding "
            f"(p.ej. {r.unsupported[:3]}). total L2 = {r.total_l2}, "
            f"referenciados válidos = {r.referenced_valid}.")
    return r


# ───────── demostración adversarial (artefacto congelado de G2.1/G2.2) ──

def _mnc(f):
    return dict(_c.must_not_change_block(f))


def _base_envelope(f, expert="TECHNICAL", assessment="INDETERMINATE"):
    quote = ((f.get("evidence") or {}).get("anchored_quote") or f.get("source_text") or "x")[:60]
    return {
        "schema": "SHADOW_OUTPUT_ENVELOPE/v1", "expert": expert,
        "finding_record_id": f["finding_record_id"], "shadow_layer": "L3",
        "assessment": assessment,
        "rationale": f"Observación del experto. {_c.SHADOW_MARK}",
        "anchored_citations": [{"finding_record_id": f["finding_record_id"], "quote": quote,
                                "page": f.get("page"), "source": _c.CLIENT_EVIDENCE,
                                "source_hash": f.get("source_hash")}],
        "external_reg_references": [],
        "MUST_NOT_CHANGE": _mnc(f),
        "confidence": "LOW",
        "model": {"provider": "LOCAL", "model_name": "m", "digest": "d",
                  "prompt_id": "p", "prompt_version": "1"},
        "produced_at": "2026-09-02T00:00:00Z",
    }


def adversarial_demo(findings: list[dict]) -> dict:
    """G2.1: 3 fixtures adversariales obligatorios -> 100% SHADOW_REJECTED +
    control positivo -> SHADOW_ACCEPTED.
    G2.2: cobertura 457/457 y omisión deliberada de 1 -> falla detectada."""
    f = next(x for x in findings if (x.get("technical_basis") or "").strip())

    # control positivo (bien formado + cita que ancla)
    ok_env = _base_envelope(f)
    ok = verify_expert_envelope(ok_env, l2_finding=f)

    # fixture 1 — cita/hash inexistente
    adv_cite = _base_envelope(f)
    adv_cite["anchored_citations"] = [{"quote": "TEXTO QUE NO EXISTE EN NINGUN CLAIM NI EVIDENCIA L1/L2",
                                       "source": _c.CLIENT_EVIDENCE}]
    r_cite = verify_expert_envelope(adv_cite, l2_finding=f)

    # fixture 2 — MUST_NOT_CHANGE alterado
    adv_mnc = _base_envelope(f)
    adv_mnc["MUST_NOT_CHANGE"] = dict(adv_mnc["MUST_NOT_CHANGE"])
    adv_mnc["MUST_NOT_CHANGE"]["risk_band"] = "LOW__tampered"
    r_mnc = verify_expert_envelope(adv_mnc, l2_finding=f)

    # fixture 3 — evidencia vacía
    adv_empty = _base_envelope(f)
    adv_empty["anchored_citations"] = []
    r_empty = verify_expert_envelope(adv_empty, l2_finding=f)

    adv = {"citation_or_hash_nonexistent": r_cite, "must_not_change_altered": r_mnc,
           "empty_evidence": r_empty}
    all_rejected = all(v.status == SHADOW_REJECTED for v in adv.values())

    # G2.2
    all_ids = [x["finding_record_id"] for x in findings]
    full = verify_report_coverage(findings, all_ids)
    omitted_id = all_ids[len(all_ids) // 2]
    partial = verify_report_coverage(findings, [i for i in all_ids if i != omitted_id])
    try:
        assert_full_coverage(findings, [i for i in all_ids if i != omitted_id])
        omission_detected = False
    except CoverageError:
        omission_detected = True

    return {
        "schema": "SHADOW_G2_VERIFIER_DEMO/v1",
        "G2_1_fail_closed_verifier": {
            "positive_control": {"status": ok.status, "reasons": ok.reasons},
            "adversarial": {k: {"status": v.status,
                                "structural_violations": v.structural_violations,
                                "anchoring_violations": v.anchoring_violations}
                            for k, v in adv.items()},
            "all_adversarial_rejected": all_rejected,
            "EXPECTED": "100% -> SHADOW_REJECTED; positive_control -> SHADOW_ACCEPTED",
            "PASS": all_rejected and ok.status == SHADOW_ACCEPTED,
        },
        "G2_2_coverage_verifier": {
            "full_457": {"covered": full.covered, "total_l2": full.total_l2,
                         "referenced_valid": full.referenced_valid,
                         "missing": full.missing, "unsupported": full.unsupported},
            "omit_one": {"omitted_finding_record_id": omitted_id,
                         "covered": partial.covered, "missing": partial.missing,
                         "assert_full_coverage_raised": omission_detected},
            "EXPECTED": "full -> covered; omitir 1 -> covered=False y assert_full_coverage falla",
            "PASS": (full.covered and full.total_l2 == 457
                     and not partial.covered and partial.missing == [omitted_id]
                     and omission_detected),
        },
    }


if __name__ == "__main__":  # pragma: no cover
    import json
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else "docs_plan/shadow_llm/FINAL_GMP_CORPUS_FINDINGS.json"
    out = sys.argv[2] if len(sys.argv) > 2 else "docs_plan/shadow_llm/G2_verifier_report.json"
    findings = json.loads(open(src, encoding="utf-8").read())["findings"]
    demo = adversarial_demo(findings)
    open(out, "w", encoding="utf-8").write(json.dumps(demo, indent=1, ensure_ascii=False, default=str))
    print("WROTE", out)
    print(json.dumps({"G2.1_PASS": demo["G2_1_fail_closed_verifier"]["PASS"],
                      "G2.2_PASS": demo["G2_2_coverage_verifier"]["PASS"]}, indent=1))
