"""SHADOW · G3.1 — Composer esqueleto DETERMINISTA (sin LLM).

Produce la ESTRUCTURA del reporte narrativo — agrupación por **documento ×
regulación**, una entrada por finding L2 — dejando la narrativa del LLM
(campo `shadow_narrative`) y la opinión de experto (`shadow_expert_assessment`)
como **PENDIENTE** (G4). No re-juzga L2: cada entrada copia
subtype/risk_band/machine_state/human_state/página/cita **verbatim** del
finding L2.

Cobertura exacta 457/457 `finding_record_id` (verificada con
`verifier.verify_report_coverage`). Cada finding cae en EXACTAMENTE una
sección.

Es un artefacto HERMANO de `report_v2.py` (el reporte factual de L2), no lo
toca ni lo reemplaza. CERO LLM · CERO red · determinista · no muta L2.
"""
from __future__ import annotations

import re
from collections import Counter, OrderedDict

from factory.regulatory.shadow import cross_domain as _x
from factory.regulatory.shadow import router as _r
from factory.regulatory.shadow import verifier as _v

_REG_TOKEN_RE = re.compile(
    r"21_CFR_11\.\d+\([a-z]\)|ANNEX11_\d+(?:\.\d+)?|ALCOA_[A-Z]+|21_CFR_11\.50_11\.70")

_NO_REGULATION = "(trazabilidad — sin regulación directa)"
_NOT_ANALYZABLE = "(documento NOT_ANALYZABLE — requiere revisión humana)"

NARRATIVE_PENDING = "PENDING_LLM_COMPOSER"      # lo llena G4e, marcado [SHADOW]

#: campos L2 que la entrada copia verbatim y que el self-check re-compara
#: (garantía de "no re-juzgar L2").
_ECHOED_L2_FIELDS = ("subtype", "risk_band", "machine_state", "human_state", "document", "page")


def _prov(f):
    return f.get("provenance") or {}


def _risk_band(f):
    return (f.get("risk") or {}).get("band") or f.get("risk_band")


def _anchored_quote(f):
    return (f.get("evidence") or {}).get("anchored_quote") or f.get("source_text") or ""


def _l2_rationale(f):
    return f.get("rationale") or ""


def regulation_key(finding: dict) -> str:
    """Clave de regulación determinista para agrupar. Un finding cae en
    EXACTAMENTE una regulación."""
    if finding.get("document") in _x._r._HUMAN_ONLY_DOCUMENTS:
        return _NOT_ANALYZABLE
    if _prov(finding).get("agent_id") == "regulatory_tier1":
        req = finding.get("requirement") or finding.get("requirement_id")
        return str(req).split("::")[0].strip() if req else _NO_REGULATION
    tb = finding.get("technical_basis") or ""
    if tb.strip():
        toks = sorted(set(_REG_TOKEN_RE.findall(tb)))
        return toks[0] if toks else tb.strip()
    return _NO_REGULATION


def _also_regulations(finding: dict, chosen: str) -> list[str]:
    tb = finding.get("technical_basis") or ""
    toks = sorted(set(_REG_TOKEN_RE.findall(tb)))
    return [t for t in toks if t != chosen]


def _link_index(findings: list[dict]) -> dict[str, list[str]]:
    """finding_record_id -> [link_id, …] de cross_domain_links.json."""
    art = _x.build_cross_domain_links(findings)
    out: dict[str, list[str]] = {}
    for lk in art["links"]:
        rids = [lk["technical"]["finding_record_id"]] + [
            cp["finding_record_id"] for cp in lk["regulatory_counterparts"]]
        for rid in rids:
            out.setdefault(rid, []).append(lk["link_id"])
    return out


def build_composer_skeleton(findings: list[dict], *, source_ref: str | None = None) -> dict:
    """Esqueleto determinista del reporte narrativo. NO toca `findings`."""
    routing = {row["finding_record_id"]: row["primary_bucket"]
               for row in _r.build_routing(findings)["routing"]}
    links = _link_index(findings)

    # agrupación (document, regulation)
    groups: "OrderedDict[tuple, list]" = OrderedDict()
    for f in findings:
        key = (f["document"], regulation_key(f))
        groups.setdefault(key, []).append(f)

    sections = []
    for i, (key, fs) in enumerate(
            sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1])), start=1):
        doc, reg = key
        fs_sorted = sorted(fs, key=lambda f: (f.get("page") or 0,
                                              routing.get(f["finding_record_id"], "Z"),
                                              f["finding_record_id"]))
        entries = []
        for f in fs_sorted:
            rid = f["finding_record_id"]
            entries.append({
                "finding_record_id": rid,
                "finding_id": f.get("finding_id"),
                "primary_bucket": routing.get(rid),
                "finding_class": f.get("class") or f.get("finding_class"),
                "subtype": f.get("subtype"),
                "requirement_id": f.get("requirement") or f.get("requirement_id"),
                "risk_band": _risk_band(f),
                "machine_state": f.get("machine_state"),
                "human_state": f.get("human_state"),
                "document": f.get("document"),
                "page": f.get("page"),
                "also_regulations": _also_regulations(f, reg),
                "cross_domain_link_ids": links.get(rid, []),
                # trazabilidad: cita y rationale L2 verbatim
                "anchored_quote_l2": _anchored_quote(f),
                "rationale_l2": _l2_rationale(f),
                # PENDIENTE — G4 (nunca re-juzga L2)
                "shadow_expert_assessment": None,
                "shadow_narrative": None,
                "narrative_status": NARRATIVE_PENDING,
            })
        sections.append({
            "section_id": f"sec-{i:04d}",
            "document": doc,
            "regulation": reg,
            "n_findings": len(entries),
            "primary_bucket_mix": dict(Counter(e["primary_bucket"] for e in entries)),
            "finding_record_ids": [e["finding_record_id"] for e in entries],
            "entries": entries,
        })

    all_rids = [e["finding_record_id"] for s in sections for e in s["entries"]]
    cov = _v.verify_report_coverage(findings, all_rids)

    l2_by_rid = {f["finding_record_id"]: f for f in findings}
    def _echo_ok(e) -> bool:
        f = l2_by_rid[e["finding_record_id"]]
        return (e["subtype"] == f.get("subtype")
                and e["risk_band"] == _risk_band(f)
                and e["machine_state"] == f.get("machine_state")
                and e["human_state"] == f.get("human_state")
                and e["document"] == f.get("document")
                and e["page"] == f.get("page"))

    entries_all = [e for s in sections for e in s["entries"]]
    acc = {
        "total_records": len(all_rids),
        "unique_finding_record_id": len(set(all_rids)),
        "every_finding_in_exactly_one_section": len(all_rids) == len(set(all_rids)) == len(findings),
        "coverage_457_of_457": cov.covered and cov.total_l2 == 457 and cov.referenced_valid == 457,
        "coverage_missing": cov.missing,
        "coverage_unsupported": cov.unsupported,
        "no_rejudge_l2": all(_echo_ok(e) for e in entries_all),
        "narrative_all_pending": all(
            e["shadow_narrative"] is None and e["narrative_status"] == NARRATIVE_PENDING
            for e in entries_all),
        "expert_all_pending": all(e["shadow_expert_assessment"] is None for e in entries_all),
    }
    acc["PASS"] = (acc["every_finding_in_exactly_one_section"]
                   and acc["coverage_457_of_457"]
                   and acc["no_rejudge_l2"]
                   and acc["narrative_all_pending"]
                   and acc["expert_all_pending"]
                   and not acc["coverage_missing"] and not acc["coverage_unsupported"])

    return {
        "schema": "SHADOW_G3_1_COMPOSER_SKELETON/v1",
        "mode": "DETERMINISTIC_SKELETON",
        "llm": "NONE",
        "narrative_status": NARRATIVE_PENDING,
        "source_ref": source_ref,
        "grouping": "document × regulation",
        "sibling_of": "factory/regulatory/findings/report_v2.py (no lo toca ni lo reemplaza)",
        "summary": {
            "total_findings": len(all_rids),
            "unique_finding_record_id": len(set(all_rids)),
            "sections": len(sections),
            "by_document": dict(Counter(s["document"] for s in sections)),
            "sections_by_document": dict(Counter(
                e["document"] for s in sections for e in s["entries"])),
            "by_primary_bucket": dict(Counter(
                e["primary_bucket"] for s in sections for e in s["entries"])),
            "coverage": {"covered": cov.covered, "total_l2": cov.total_l2,
                         "referenced_valid": cov.referenced_valid,
                         "missing": cov.missing, "unsupported": cov.unsupported},
        },
        "acceptance": acc,
        "sections": sections,
    }


def assert_full_coverage_or_raise(skeleton: dict) -> None:
    if not skeleton["acceptance"]["PASS"]:
        raise _v.CoverageError(f"composer skeleton no PASS: {skeleton['acceptance']}")


if __name__ == "__main__":  # pragma: no cover
    import json
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else "docs_plan/shadow_llm/FINAL_GMP_CORPUS_FINDINGS.json"
    out = sys.argv[2] if len(sys.argv) > 2 else "docs_plan/shadow_llm/G3_1_composer_skeleton.json"
    findings = json.loads(open(src, encoding="utf-8").read())["findings"]
    before = json.dumps(findings, sort_keys=True)
    sk = build_composer_skeleton(findings, source_ref=src)
    assert json.dumps(findings, sort_keys=True) == before, "L2 mutado por el composer"
    open(out, "w", encoding="utf-8").write(json.dumps(sk, indent=1, ensure_ascii=False))
    print("WROTE", out)
    print(json.dumps({"summary": sk["summary"], "acceptance": sk["acceptance"]},
                     indent=1, ensure_ascii=False))
