"""SHADOW · G1 — Router determinista sobre findings L2.

Asigna a CADA finding exactamente UN bucket primario (routing exclusivo, suma
457 sobre el corpus baseline) y marca `cross_domain_flag` sobre las relaciones
técnico↔regulatorio (15 sobre el corpus baseline).

100 % determinista · CERO LLM · CERO red · solo LECTURA de L2.
No muta ningún Finding. La salida es un artefacto aditivo
(`shadow/routing.json` en runtime; `docs_plan/shadow_llm/G1_routing.json` en el
congelado de fase).

Reglas (congeladas en G0 §4, `FINAL_GMP_CORPUS_ANALYSIS_REPORT.md`):

  PRIMARIO (en orden, primer match gana):
    HUMAN_ONLY               document == "RW-0009"  (adequacy_verdict NOT_ANALYZABLE)
    REGULATORY               provenance.agent_id == "regulatory_tier1"
    TECHNICAL               technical_basis no vacío  (regla de completitud gobernada)
    FUNCTIONAL_TRACEABILITY evidence_basis == "ABSENCE_DEPENDENT"
                            ∧ provenance.agent_id ∈ _FUNCTIONAL_AGENT_IDS
    (cualquier finding que no encaje -> UNROUTED, que el self-check trata como FALLO)

  SECUNDARIO — cross_domain_flag = YES  sii:
    bucket primario == TECHNICAL
    ∧ technical_basis nombra >=1 token de regulación (_REG_TOKEN_RE)
    ∧ ese token coincide con el prefijo de familia (requirement_id.split("::")[0])
      de algún finding regulatory_tier1 del MISMO documento.
"""
from __future__ import annotations

import re
from collections import Counter

PRIMARY_BUCKETS = ("REGULATORY", "FUNCTIONAL_TRACEABILITY", "TECHNICAL", "HUMAN_ONLY")

#: documento cuya extracción no es analizable -> nunca al LLM (invariante I-7).
_HUMAN_ONLY_DOCUMENTS = ("RW-0009",)

#: agent_id deterministas de la familia funcional / trazabilidad (functional_findings.py
#: + el ORPHAN_DESIGN_ELEMENT de technical_findings.py, que NO lleva technical_basis).
_FUNCTIONAL_AGENT_IDS = frozenset({
    "test_coverage_agent",
    "cross_document_agent",
    "requirements_traceability_agent",
    "functional_consistency_agent",
})

#: tokens de regulación que pueden aparecer en `technical_basis` de una regla de
#: completitud gobernada y en un `requirement_id` de la clase Regulatory.
_REG_TOKEN_RE = re.compile(
    r"21_CFR_11\.\d+\([a-z]\)|ANNEX11_\d+(?:\.\d+)?|ALCOA_[A-Z]+|21_CFR_11\.50_11\.70")

#: baseline esperado del corpus reconc (6 docs, FINDINGS_FINGERPRINT 235f724a…).
EXPECTED_BASELINE = {
    "total": 457,
    "by_bucket": {"REGULATORY": 285, "FUNCTIONAL_TRACEABILITY": 98,
                  "TECHNICAL": 17, "HUMAN_ONLY": 57},
    "cross_domain_flags": 15,
}


def _prov(f: dict) -> dict:
    return f.get("provenance") or {}


def route_primary(finding: dict) -> str:
    """Bucket primario EXCLUSIVO de un finding. Determinista, primer match gana."""
    if finding.get("document") in _HUMAN_ONLY_DOCUMENTS:
        return "HUMAN_ONLY"
    agent = _prov(finding).get("agent_id")
    if agent == "regulatory_tier1":
        return "REGULATORY"
    if (finding.get("technical_basis") or "").strip():
        return "TECHNICAL"
    if finding.get("evidence_basis") == "ABSENCE_DEPENDENT" and agent in _FUNCTIONAL_AGENT_IDS:
        return "FUNCTIONAL_TRACEABILITY"
    return "UNROUTED"


def _reg_families_by_document(findings: list[dict]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for f in findings:
        if _prov(f).get("agent_id") != "regulatory_tier1":
            continue
        req = f.get("requirement") or f.get("requirement_id")
        if not req:
            continue
        out.setdefault(f.get("document"), set()).add(str(req).split("::")[0].strip())
    return out


def cross_domain_matches(finding: dict, reg_families_by_doc: dict[str, set[str]]) -> list[str]:
    """Tokens de regulación compartidos entre este finding TÉCNICO y algún
    finding regulatory_tier1 del mismo documento. Lista vacía => sin flag."""
    if route_primary(finding) != "TECHNICAL":
        return []
    tb = finding.get("technical_basis") or ""
    tokens = set(_REG_TOKEN_RE.findall(tb))
    shared = tokens & reg_families_by_doc.get(finding.get("document"), set())
    return sorted(shared)


def build_routing(findings: list[dict], *, source_ref: str | None = None) -> dict:
    """Artefacto de routing completo: fila por finding + resumen + self-check.

    `findings` es la lista de dicts tal y como los persiste `run_v2_pipeline`
    (`regulatory_findings.json + functional_findings.json + technical_findings.json`)
    o el `findings` de `FINAL_GMP_CORPUS_FINDINGS.json`.
    """
    reg_fams = _reg_families_by_document(findings)
    rows: list[dict] = []
    counterparts_by_reg_family: dict[tuple[str, str], list[str]] = {}
    for f in findings:
        if _prov(f).get("agent_id") == "regulatory_tier1":
            req = f.get("requirement") or f.get("requirement_id")
            if req:
                key = (f.get("document"), str(req).split("::")[0].strip())
                counterparts_by_reg_family.setdefault(key, []).append(f["finding_record_id"])

    for f in findings:
        bucket = route_primary(f)
        shared = cross_domain_matches(f, reg_fams)
        counterparts: list[str] = []
        for tok in shared:
            counterparts.extend(counterparts_by_reg_family.get((f.get("document"), tok), []))
        rows.append({
            "finding_record_id": f["finding_record_id"],
            "finding_id": f.get("finding_id"),
            "document": f.get("document"),
            "page": f.get("page"),
            "finding_class": f.get("class") or f.get("finding_class"),
            "subtype": f.get("subtype"),
            "requirement_id": f.get("requirement") or f.get("requirement_id"),
            "risk_band": (f.get("risk") or {}).get("band"),
            "machine_state": f.get("machine_state"),
            "human_state": f.get("human_state"),
            "primary_bucket": bucket,
            "cross_domain_flag": bool(shared),
            "cross_domain_regulations": shared,
            "cross_domain_regulatory_counterparts": sorted(set(counterparts)),
        })

    by_bucket = Counter(r["primary_bucket"] for r in rows)
    n_cross = sum(1 for r in rows if r["cross_domain_flag"])
    unrouted = [r["finding_record_id"] for r in rows if r["primary_bucket"] == "UNROUTED"]
    rec_ids = [r["finding_record_id"] for r in rows]

    checks = {
        "total_records": len(rows),
        "unique_finding_record_id": len(set(rec_ids)),
        "all_records_routed_exclusively": not unrouted,
        "unrouted_finding_record_ids": unrouted,
        "sum_primary_equals_total": sum(by_bucket.values()) == len(rows),
        "human_only_never_llm": all(
            r["primary_bucket"] == "HUMAN_ONLY"
            for r in rows if r["document"] in _HUMAN_ONLY_DOCUMENTS),
        "cross_domain_is_secondary_flag_only": all(
            r["primary_bucket"] in PRIMARY_BUCKETS for r in rows),
        "matches_expected_baseline": (
            len(rows) == EXPECTED_BASELINE["total"]
            and dict(by_bucket) == EXPECTED_BASELINE["by_bucket"]
            and n_cross == EXPECTED_BASELINE["cross_domain_flags"]),
    }
    checks["PASS"] = (
        checks["all_records_routed_exclusively"]
        and checks["sum_primary_equals_total"]
        and checks["human_only_never_llm"]
        and checks["cross_domain_is_secondary_flag_only"]
        and checks["unique_finding_record_id"] == len(rows))

    return {
        "schema": "SHADOW_G1_ROUTING/v1",
        "source_ref": source_ref,
        "rules_ref": "docs_plan/shadow_llm/FINAL_GMP_CORPUS_ANALYSIS_REPORT.md §4",
        "summary": {
            "total_records": len(rows),
            "by_primary_bucket": dict(by_bucket),
            "cross_domain_flags": n_cross,
            "cross_domain_note": ("flag SECUNDARIO sobre findings ya ruteados; NO es un 5º bucket, "
                                  "NO se suma al total"),
        },
        "acceptance": checks,
        "routing": rows,
    }


if __name__ == "__main__":  # pragma: no cover
    import json
    import sys

    src = sys.argv[1] if len(sys.argv) > 1 else (
        "docs_plan/shadow_llm/FINAL_GMP_CORPUS_FINDINGS.json")
    out = sys.argv[2] if len(sys.argv) > 2 else "docs_plan/shadow_llm/G1_routing.json"
    payload = json.loads(open(src, encoding="utf-8").read())
    items = payload["findings"] if isinstance(payload, dict) else payload
    result = build_routing(items, source_ref=src)
    open(out, "w", encoding="utf-8").write(json.dumps(result, indent=1, ensure_ascii=False))
    print("WROTE", out)
    print(json.dumps({"summary": result["summary"], "acceptance": result["acceptance"]},
                     indent=1, ensure_ascii=False))
