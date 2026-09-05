"""SHADOW · CF-6 v1.2 · CF6-2.5 — SAMPLE_MANIFEST (sin LLM).

Selección DETERMINISTA y congelable de las secciones del HUMAN_QUALITY_GATE,
con verificación de los criterios de inclusión obligatorios (§4.1) y hash
`sample_manifest_hash`. Debe existir ANTES de cualquier salida del piloto
(cualquier llamada LLM de CF6-2.5).

Criterios obligatorios (§4.1):
  ≥ 2 secciones REGULATORY con findings INCONCLUSIVE
  ≥ 1 sección FUNCTIONAL_TRACEABILITY
  ≥ 1 sección TECHNICAL
  ≥ 2 secciones CROSS_DOMAIN
  OBLIGATORIO: sec-0018, sec-0062, sec-0016 (o su equivalente exacto — aquí
  existen con esos IDs bajo la agrupación v2, sin remapeo).

CERO LLM · CERO red · determinista. No muta L2 / human_state / fingerprint.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from factory.regulatory.shadow import composer as _skel
from factory.regulatory.shadow import composer_gate as _cg

MANDATORY_SECTIONS = ("sec-0016", "sec-0018", "sec-0062")

#: selección determinista (7 secciones). Motivo por ID.
_SELECTION = {
    "sec-0016": "OBLIGATORIA — caso histórico v1 (fuga 'rango de candidatos'); REGULATORY/INCONCLUSIVE",
    "sec-0062": "OBLIGATORIA — caso histórico v1 (elevación 'no se cumplió con'); REGULATORY/INCONCLUSIVE",
    "sec-0018": "OBLIGATORIA — caso histórico v1 (elevación 'no estaban en conformidad'); CROSS_DOMAIN/INCONCLUSIVE",
    "sec-0005": "REGULATORY/INCONCLUSIVE adicional (21_CFR_11.50_11.70, RW-0005) — 2º+ REGULATORY exigido",
    "sec-0004": "CROSS_DOMAIN/INCONCLUSIVE (21_CFR_11.10(g), RW-0005) — 2ª CROSS_DOMAIN exigida",
    "sec-0042": "FUNCTIONAL_TRACEABILITY (RW-0012) — cobertura de trazabilidad pura (NOT_APPLICABLE)",
    "sec-0026": "TECHNICAL (ANNEX11_7, RW-0006) — cobertura técnica pura (NOT_APPLICABLE)",
}

_INCONCLUSIVE_MS = ("MACHINE_INCONCLUSIVE", "INCONCLUSIVE")


def _sections(shadow_dir: Path) -> dict:
    findings = json.loads(
        (shadow_dir / "FINAL_GMP_CORPUS_FINDINGS.json").read_text(encoding="utf-8"))["findings"]
    sk = _skel.build_composer_skeleton(findings)
    l2 = {f["finding_record_id"]: f for f in findings}
    return {s["section_id"]: s for s in sk["sections"]}, l2


def build(shadow_dir: str | Path = "docs_plan/shadow_llm", *,
          status: str = "DRAFT_PENDING_CF6_2_G_PASS") -> dict:
    SL = Path(shadow_dir)
    by_id, l2 = _sections(SL)

    rows = []
    for sid in _SELECTION:
        s = by_id[sid]
        st, has_reg = _cg.infer_section_type(s)
        rids = s.get("finding_record_ids") or [e["finding_record_id"] for e in s["entries"]]
        ms = sorted({(l2.get(r) or {}).get("machine_state") for r in rids})
        rows.append({
            "section_id": sid,
            "document": s["document"],
            "regulation": s["regulation"],
            "section_type": st,
            "regulatory_state_expected": _cg.expected_regulatory_state(s),
            "n_findings": s["n_findings"],
            "machine_states": ms,
            "has_inconclusive_finding": any(m in _INCONCLUSIVE_MS for m in ms),
            "selection_reason": _SELECTION[sid],
        })
    rows.sort(key=lambda r: r["section_id"])

    def _count(pred):
        return sum(1 for r in rows if pred(r))

    criteria = {
        "regulatory_with_inconclusive_>=2": _count(
            lambda r: r["section_type"] == "REGULATORY" and r["has_inconclusive_finding"]),
        "functional_traceability_>=1": _count(lambda r: r["section_type"] == "FUNCTIONAL_TRACEABILITY"),
        "technical_>=1": _count(lambda r: r["section_type"] == "TECHNICAL"),
        "cross_domain_>=2": _count(lambda r: r["section_type"] == "CROSS_DOMAIN"),
    }
    mandatory_present = [s for s in MANDATORY_SECTIONS if s in _SELECTION]
    criteria_pass = (
        criteria["regulatory_with_inconclusive_>=2"] >= 2
        and criteria["functional_traceability_>=1"] >= 1
        and criteria["technical_>=1"] >= 1
        and criteria["cross_domain_>=2"] >= 2
        and sorted(mandatory_present) == sorted(MANDATORY_SECTIONS)
    )

    sections_selected = [r["section_id"] for r in rows]
    categories_covered = sorted({r["section_type"] for r in rows})
    canonical = json.dumps(
        {"sections_selected": sections_selected,
         "rows": rows,
         "criteria_pass": criteria_pass},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    manifest_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    frozen = status.upper().startswith("FROZEN")
    return {
        "schema": "SHADOW_CF6_2_5_SAMPLE_MANIFEST/v1",
        "status": status,
        "llm_calls": 0,
        "note": ("CONGELADO antes de cualquier salida del piloto (§4.1). El hash es sobre "
                 "sections_selected + rows + criteria_pass — NO incluye `status`, así que "
                 "es idéntico al del DRAFT: prueba de que la selección no cambió."
                 if frozen else
                 "Congelar (commit + tag) ANTES de cualquier salida del piloto. Requiere "
                 "CF6-2.G PASS (PILOT_SCOPE_MATCH_CF6 = YES)."),
        "freeze_tag": "cf6-G2.5-manifest" if frozen else None,
        "cf6_2_g": ("PASS (CF6-2.G, tag cf6-G2G — cierre de scope previo). La congelación del "
                    "SAMPLE_MANIFEST se etiquetó por separado en cf6-G2.5-manifest."
                    if frozen else "PENDIENTE"),
        "sample_manifest_hash": manifest_hash,
        "sections_selected": sections_selected,
        "n_sections": len(sections_selected),
        "categories_covered": categories_covered,
        "mandatory_sections": list(MANDATORY_SECTIONS),
        "mandatory_all_present": sorted(mandatory_present) == sorted(MANDATORY_SECTIONS),
        "inclusion_criteria_counts": criteria,
        "inclusion_criteria_pass": criteria_pass,
        "selection_reason": {r["section_id"]: r["selection_reason"] for r in rows},
        "rows": rows,
        "integrity": {
            "L2_MUTATIONS": 0, "HUMAN_STATE_CHANGES": 0, "G4D_CALLS": 0, "LLM_CALLS": 0,
            "FINDINGS_FINGERPRINT": "235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23",
        },
    }


if __name__ == "__main__":  # pragma: no cover
    import sys
    sd = sys.argv[1] if len(sys.argv) > 1 else "docs_plan/shadow_llm"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
        "docs_plan/shadow_llm/CF6/CF6_2_5_SAMPLE_MANIFEST.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    m = build(sd)
    out.write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding="utf-8")
    print("WROTE", out)
    print(json.dumps({k: m[k] for k in (
        "status", "sample_manifest_hash", "sections_selected", "categories_covered",
        "mandatory_all_present", "inclusion_criteria_counts", "inclusion_criteria_pass")},
        indent=1, ensure_ascii=False))
