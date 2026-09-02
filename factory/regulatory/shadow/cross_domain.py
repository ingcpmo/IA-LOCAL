"""SHADOW · G3 — post-pass determinista de relaciones cross-domain.

Materializa las relaciones "gap técnico ↔ INCONCLUSIVE regulatorio sobre la
misma regla y el mismo documento" en `shadow/cross_domain_links.json`.

Corrección 2 del auditor: estas relaciones **NUNCA** se escriben en
`Finding.related_finding_ids` (campo de L2). El post-pass SOLO lee L2 y
escribe el artefacto shadow.

Regla: **la misma** que el router de G1 — `router.build_routing()` marca
`cross_domain_flag` sobre findings TÉCNICOS cuyo `technical_basis` nombra un
token de regulación que también es `requirement_id` de un `regulatory_tier1`
del mismo documento. Aquí se reutiliza esa salida (una sola fuente de verdad).

Estados de una relación:
  PENDING_CROSS_DOMAIN_REVIEW   estado inicial (G3)
  HUMAN_REVIEW_REQUIRED         lo fija apply_review_outcome() cuando el
                                Cross-domain Reviewer (G4b) devuelve
                                DISAGREEMENT_PERSISTS  (nunca se resuelve solo)

CERO LLM · CERO red · determinista · no muta ningún Finding.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from factory.regulatory.shadow import contracts as _c
from factory.regulatory.shadow import router as _r

RELATION = "TECHNICAL_GAP_vs_REGULATORY_INCONCLUSIVE_SAME_RULE"
STATUS_PENDING = "PENDING_CROSS_DOMAIN_REVIEW"
STATUS_HUMAN_REVIEW = "HUMAN_REVIEW_REQUIRED"

#: assessment del Cross-domain Reviewer (G4b) que fuerza revisión humana.
HUMAN_REVIEW_TRIGGER = _c.CROSS_DOMAIN_HUMAN_REVIEW_TRIGGER   # "DISAGREEMENT_PERSISTS"


class L2MutationError(AssertionError):
    pass


@dataclass
class _Ix:
    by_rid: dict


def _index(findings: list[dict]) -> _Ix:
    return _Ix(by_rid={f["finding_record_id"]: f for f in findings})


def _anchored_quote(f: dict) -> str:
    return (f.get("evidence") or {}).get("anchored_quote") or f.get("source_text") or ""


def build_cross_domain_links(findings: list[dict], *, source_ref: str | None = None) -> dict:
    """Detecta las relaciones cross-domain y devuelve el artefacto completo.
    NO toca `findings` (solo lectura)."""
    ix = _index(findings)
    routing = _r.build_routing(findings, source_ref=source_ref)
    flagged = [row for row in routing["routing"] if row["cross_domain_flag"]]

    raw = []
    for row in flagged:
        tech = ix.by_rid[row["finding_record_id"]]
        counterparts = []
        for rid in row["cross_domain_regulatory_counterparts"]:
            rf = ix.by_rid.get(rid)
            if rf is None:
                continue
            counterparts.append({
                "finding_record_id": rid,
                "requirement_id": rf.get("requirement") or rf.get("requirement_id"),
                "subtype": rf.get("subtype"),
                "page": rf.get("page"),
                "machine_state": rf.get("machine_state"),
            })
        raw.append({
            "document": row["document"],
            "technical": {
                "finding_record_id": row["finding_record_id"],
                "subtype": row["subtype"],
                "primary_bucket": row["primary_bucket"],
                "page": row["page"],
                "anchored_quote": _anchored_quote(tech)[:200],
                "technical_basis": tech.get("technical_basis"),
            },
            "shared_regulations": row["cross_domain_regulations"],
            "regulatory_counterparts": counterparts,
        })

    # orden determinista + link_id estable
    raw.sort(key=lambda d: (d["document"], d["technical"]["subtype"],
                            d["technical"]["finding_record_id"]))
    links = []
    for i, d in enumerate(raw, start=1):
        links.append({
            "link_id": f"cdl-{i:04d}",
            "relation": RELATION,
            "status": STATUS_PENDING,
            "human_review_required": False,
            "l2_mutation": False,
            **d,
        })

    reg_counter: Counter = Counter()
    for lk in links:
        for reg in lk["shared_regulations"]:
            reg_counter[reg] += 1

    # corr. 2: la relación cross-domain NO puede aparecer en el
    # related_finding_ids del finding técnico (ni por finding_record_id ni por
    # finding_id de su contraparte regulatoria). L2 tiene su propio
    # related_finding_ids legítimo (p.ej. C09->C01) — eso no se toca ni se cuenta.
    def _cross_leak_into_l2() -> bool:
        for lk in links:
            tech = ix.by_rid[lk["technical"]["finding_record_id"]]
            rel = set(tech.get("related_finding_ids") or [])
            for cp in lk["regulatory_counterparts"]:
                rf = ix.by_rid.get(cp["finding_record_id"], {})
                if cp["finding_record_id"] in rel or rf.get("finding_id") in rel:
                    return True
        return False

    acc = {
        "total_links_is_15": len(links) == 15,
        "all_links_technical_primary": all(
            lk["technical"]["primary_bucket"] == "TECHNICAL" for lk in links),
        "every_link_has_regulatory_counterpart": all(
            lk["regulatory_counterparts"] for lk in links),
        "link_ids_unique": len({lk["link_id"] for lk in links}) == len(links),
        "no_cross_domain_relation_in_l2_related_finding_ids": not _cross_leak_into_l2(),
    }
    acc["PASS"] = all(acc.values())

    return {
        "schema": "SHADOW_G3_CROSS_DOMAIN_LINKS/v1",
        "source_ref": source_ref,
        "rules_ref": ("router.build_routing().cross_domain_flag — misma regla que G1 "
                      "(docs_plan/shadow_llm/G1_ROUTER.md §2.2)"),
        "corr2_note": ("las relaciones viven SOLO aquí; NUNCA en Finding.related_finding_ids (L2)."),
        "summary": {
            "total_links": len(links),
            "by_shared_regulation": dict(reg_counter),
            "by_document": dict(Counter(lk["document"] for lk in links)),
            "by_technical_subtype": dict(Counter(lk["technical"]["subtype"] for lk in links)),
            "l2_related_finding_ids_written": 0,
            "status_counts": dict(Counter(lk["status"] for lk in links)),
        },
        "acceptance": acc,
        "links": links,
    }


def apply_review_outcome(artifact: dict, outcomes: dict) -> dict:
    """`outcomes`: {link_id: assessment del Cross-domain Reviewer (G4b)}.
    DISAGREEMENT_PERSISTS -> status HUMAN_REVIEW_REQUIRED. Determinista, no
    inventa: un link_id ausente en `outcomes` conserva su estado. NO toca L2.
    Devuelve un artefacto NUEVO (no muta el de entrada)."""
    import copy
    out = copy.deepcopy(artifact)
    for lk in out["links"]:
        a = outcomes.get(lk["link_id"])
        if a not in _c.ASSESSMENT_VALUES["CROSS_DOMAIN"] and a is not None:
            raise ValueError(f"{lk['link_id']}: assessment cross-domain inválido: {a!r}")
        lk["cross_domain_assessment"] = a
        if a == HUMAN_REVIEW_TRIGGER:
            lk["status"] = STATUS_HUMAN_REVIEW
            lk["human_review_required"] = True
    from collections import Counter as _C
    out["summary"]["status_counts"] = dict(_C(lk["status"] for lk in out["links"]))
    out["summary"]["human_review_required_count"] = sum(
        1 for lk in out["links"] if lk["human_review_required"])
    return out


def assert_no_l2_mutation(findings_before: list[dict], findings_after: list[dict]) -> None:
    """Fail-closed: los campos L2 (incl. related_finding_ids) no cambiaron."""
    import json
    a = json.dumps(findings_before, sort_keys=True)
    b = json.dumps(findings_after, sort_keys=True)
    if a != b:
        raise L2MutationError("el post-pass cross-domain modificó findings L2")


if __name__ == "__main__":  # pragma: no cover
    import json
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else "docs_plan/shadow_llm/FINAL_GMP_CORPUS_FINDINGS.json"
    out = sys.argv[2] if len(sys.argv) > 2 else "docs_plan/shadow_llm/cross_domain_links.json"
    findings = json.loads(open(src, encoding="utf-8").read())["findings"]
    before = json.dumps(findings, sort_keys=True)
    art = build_cross_domain_links(findings, source_ref=src)
    assert json.dumps(findings, sort_keys=True) == before, "L2 mutado por el post-pass"
    open(out, "w", encoding="utf-8").write(json.dumps(art, indent=1, ensure_ascii=False))
    print("WROTE", out)
    print(json.dumps({"summary": art["summary"], "acceptance": art["acceptance"]},
                     indent=1, ensure_ascii=False))
