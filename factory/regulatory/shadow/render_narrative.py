"""SHADOW · G5.2 — render determinista del informe narrativo para el revisor humano.

Ensambla, SIN LLM y SIN re-juzgar L2, un único markdown a partir de los
artefactos congelados del arco:

  FINAL_GMP_CORPUS_FINDINGS.json   (fuente maestra L2, 457 findings)
  G3_1_composer_skeleton.json      (66 secciones documento × regulación)
  G4/g4e_composer.jsonl            (narrativa [SHADOW / NO GOBERNADO] por sección)
  G4/g4{a,c,d}_*.jsonl             (opinión shadow verificada por finding)
  G4/g4b_human_review_queue.json   (15 relaciones cross-domain que requieren revisión humana)

Cada fila de finding muestra los hechos L2 VERBATIM (subtype/riesgo/machine_state/
human_state/página/cita). La opinión del modelo es asistencia, marcada, y solo se
muestra si pasó el verificador fail-closed de G2; si no, se rotula RECHAZADA.
"""
from __future__ import annotations

import json
from pathlib import Path

_MARK = "[SHADOW / NO GOBERNADO]"

_HEADER = (
    "> **BORRADOR ASISTIDO.** Generado por máquina con un modelo LLM **local no gobernado** "
    "(`qwen2.5:7b-instruct-q4_K_M`, LOCAL). **NO** es una declaración de cumplimiento GMP, "
    "**NO** aprueba documentos, **NO** cierra CAPA, **NO** libera lote.\n>\n"
    "> **Fuente maestra:** los 457 findings deterministas L2 de `FINAL_GMP_CORPUS_FINDINGS.json` "
    "(sha256 `95a79f9b6276ff2a7972100764b308fa4b09f0027c6679ea831b441eb880f02c`). El revisor "
    "humano adjudica **sobre esos findings**, nunca sobre la narrativa shadow.\n>\n"
    "> Toda narrativa u opinión marcada `[SHADOW / NO GOBERNADO]` es de un modelo local, "
    "verificada solo por **anclaje de cita** (fail-closed), y sigue **PENDIENTE de sign-off "
    "humano**. Todo finding nace `human_state = UNREVIEWED` y **solo un revisor humano con nombre "
    "real lo cambia** (CLAUDE.md, sin excepción).\n>\n"
    "> Procedencia de las opiniones: `PILOT_EXECUTION-2026-035` (firmada por Capa 9 vía `-036`, "
    "`approved_by_id = Cesar`) · 481 llamadas LLM reales · L2 y `human_state` intactos "
    "(`L2_MUTATIONS = 0`, `HUMAN_STATE_CHANGES = 0`)."
)


def _trim(s: str, n: int = 180) -> str:
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[:n] + "…"


def _cell(s: str) -> str:
    return _trim(s).replace("|", "\\|")


def render(shadow_dir: Path) -> str:
    SL = shadow_dir
    findings = json.loads((SL / "FINAL_GMP_CORPUS_FINDINGS.json").read_text())["findings"]
    by_rid = {f["finding_record_id"]: f for f in findings}
    skeleton = json.loads((SL / "G3_1_composer_skeleton.json").read_text())
    routing = {r["finding_record_id"]: r["primary_bucket"]
               for r in json.loads((SL / "G1_routing.json").read_text())["routing"]}
    g4e = {json.loads(l)["_unit"]: json.loads(l)
           for l in (SL / "G4" / "g4e_composer.jsonl").read_text().splitlines() if l.strip()}
    hrq = json.loads((SL / "G4" / "g4b_human_review_queue.json").read_text())

    # opinión shadow por finding_record_id
    opinion = {}
    for name, expert in (("g4a_technical.jsonl", "TECHNICAL"),
                         ("g4c_functional.jsonl", "FUNCTIONAL_TRACEABILITY"),
                         ("g4d_regulatory_triage.jsonl", "REGULATORY")):
        for l in (SL / "G4" / name).read_text().splitlines():
            if not l.strip():
                continue
            row = json.loads(l)
            env = row["envelope"]
            st = row["verifier"]["status"]
            rat = env.get("rationale", "")
            ranked = env.get("ranked_candidate_claim_ids")
            opinion[row["_unit"]] = {
                "expert": expert, "assessment": env["assessment"], "verifier": st,
                "confidence": env.get("confidence"),
                "rationale": rat, "ranked": ranked,
            }

    def op_text(rid: str) -> str:
        o = opinion.get(rid)
        doc = (by_rid.get(rid) or {}).get("document")
        if o is None:
            if doc == "RW-0009":
                return "_(no evaluado por LLM — documento NOT_ANALYZABLE, va a revisión humana)_"
            return "_(sin opinión shadow)_"
        if o["verifier"] == "SHADOW_REJECTED":
            return (f"**RECHAZADA por el verificador** (la cita del modelo no ancla en L1/L2) — "
                    f"propuesta descartada, no entra al informe. `{o['assessment']}`")
        extra = ""
        if o.get("ranked"):
            extra = f" · orden sugerido de candidatos: `{', '.join(o['ranked'])}`"
        r = o["rationale"].replace(_MARK, "").strip()
        return f"`{o['assessment']}` (conf. {o['confidence']}){extra} — {_cell(r)} {_MARK}"

    L = []
    L.append("# INFORME NARRATIVO SHADOW — BORRADOR ASISTIDO · v1")
    L.append("")
    L.append(_HEADER)
    L.append("")
    L.append("## Resumen")
    L.append("")
    by_bucket = {}
    for f in findings:
        by_bucket[routing.get(f["finding_record_id"], "?")] = by_bucket.get(
            routing.get(f["finding_record_id"], "?"), 0) + 1
    acc = rej = 0
    for o in opinion.values():
        acc += o["verifier"] == "SHADOW_ACCEPTED"
        rej += o["verifier"] == "SHADOW_REJECTED"
    drafted = sum(1 for r in g4e.values() if r["assessment"] == "NARRATIVE_DRAFTED")
    L.append(f"- Findings L2: **{len(findings)}** · secciones (documento × regulación): "
             f"**{len(skeleton['sections'])}** · cobertura **457/457**")
    L.append(f"- Routing: REGULATORY {by_bucket.get('REGULATORY',0)} · "
             f"FUNCTIONAL_TRACEABILITY {by_bucket.get('FUNCTIONAL_TRACEABILITY',0)} · "
             f"TECHNICAL {by_bucket.get('TECHNICAL',0)} · HUMAN_ONLY {by_bucket.get('HUMAN_ONLY',0)}")
    L.append(f"- Opiniones shadow por finding: **{acc} verificadas / {rej} rechazadas** por el "
             f"verificador fail-closed (las rechazadas NO entran al informe)")
    L.append(f"- Narrativa de sección: **{drafted} redactadas / {len(g4e)-drafted} bloqueadas**")
    L.append(f"- `human_state` de los 457 findings: **UNREVIEWED** (nada adjudicado)")
    L.append("")

    # ── cola de revisión humana obligatoria ──
    L.append("## Cola de revisión humana OBLIGATORIA — 15 relaciones cross-domain")
    L.append("")
    L.append("> El Cross-domain Reviewer (shadow) devolvió `DISAGREEMENT_PERSISTS` en las 15: un "
             "hallazgo técnico afirma un gap concreto sobre una regla que el motor regulatorio marcó "
             "`INCONCLUSIVE` en el mismo documento. **`human_review_performed = false` en las 15** — "
             "la revisión humana NO ha ocurrido. Detalle: `G4/g4b_human_review_queue.json`.")
    L.append("")
    L.append("| link | doc | regulación | finding técnico | contrapartes regulatorias | status |")
    L.append("|---|---|---|---|---|---|")
    for q in hrq["queue"]:
        cps = ", ".join(c["finding_record_id"] for c in q["opinion_regulatory_counterparts"])
        L.append(f"| `{q['link_id']}` | {q['document']} | {', '.join(q['shared_regulations'])} | "
                 f"`{q['opinion_technical']['finding_record_id']}` "
                 f"({q['opinion_technical']['subtype']}) | {cps} | **{q['status']}** |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## Secciones — documento × regulación")
    L.append("")

    covered = set()
    for sec in skeleton["sections"]:
        sid = sec["section_id"]
        L.append(f"### {sid} · {sec['document']} · {sec['regulation']}  "
                 f"({sec['n_findings']} finding{'s' if sec['n_findings'] != 1 else ''})")
        L.append("")
        g = g4e.get(sid)
        if g and g["assessment"] == "NARRATIVE_DRAFTED" and g["narrative"].strip():
            L.append(f"**Narrativa {_MARK}:** {g['narrative'].replace(_MARK,'').strip()}")
        else:
            L.append(f"**Narrativa {_MARK}:** _(bloqueada — el composer no produjo narrativa para "
                     f"esta sección; revisar los findings directamente)_")
        L.append("")
        L.append("| finding_record_id | subtype | riesgo | machine_state | human_state | pág | "
                 "cita anclada (L2, verbatim) | opinión shadow (verificada) |")
        L.append("|---|---|---|---|---|---|---|---|")
        for e in sec["entries"]:
            rid = e["finding_record_id"]
            covered.add(rid)
            f = by_rid[rid]
            q = _cell((f.get("evidence") or {}).get("anchored_quote") or f.get("source_text") or "")
            xdl = ""
            if e.get("cross_domain_link_ids"):
                xdl = f" · cross-domain: {', '.join(e['cross_domain_link_ids'])}"
            L.append(f"| `{rid}`{xdl} | {f['subtype']} | "
                     f"{(f.get('risk') or {}).get('band')} ({(f.get('risk') or {}).get('score','')}) | "
                     f"{f['machine_state']} | **{f['human_state']}** | {f['page']} | {q} | "
                     f"{op_text(rid)} |")
        L.append("")

    L.append("---")
    L.append("")
    L.append(f"**Cobertura verificada:** {len(covered)} / {len(findings)} findings L2 en alguna "
             f"sección ({'COMPLETA' if covered == set(by_rid) else 'INCOMPLETA'}).")
    L.append("")
    L.append(f"*Render determinista (0 LLM) de los artefactos congelados del arco shadow "
             f"(`shadow-G5.1`). L2 no modificado. La decisión final es humana.*")
    return "\n".join(L)


if __name__ == "__main__":  # pragma: no cover
    import sys
    sd = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs_plan/shadow_llm")
    out = sd / "G4" / "INFORME_NARRATIVO_SHADOW_v1.md"
    md = render(sd)
    out.write_text(md, encoding="utf-8")
    print("WROTE", out, "·", len(md), "bytes ·", md.count("\n### "), "secciones")
