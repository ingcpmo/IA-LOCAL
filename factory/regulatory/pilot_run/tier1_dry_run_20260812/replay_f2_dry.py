"""R3-T1.5 bloque 1 -- F2-DRY, REPLAY ACOTADO (aprobado por Cesar
2026-08-12, tras confirmar que evaluate_chunked() rehusa reabrir un
checkpoint completed=True -- ver docs_plan/R3_T1_5_F2_DRY.md bloque 1 para
el hallazgo completo).

evaluate_chunked() no ofrece un modo "reprocesar un checkpoint ya
completado con codigo corregido" -- CheckpointStore.find_resumable()
rechaza deliberadamente reabrir runs completed=True sin fallos tecnicos
("jamas re-analizar contenido ya evaluado", chunked_engine.py linea 865).
Esa guardia NO se toca aqui.

En su lugar, este script reproduce el mismo tramo de GLUE que
evaluate_chunked() corre tras el bucle de ejecucion en vivo (chunked_engine.py
lineas ~1180-1899) -- construccion de by_req/criterion_assessments_by_req,
Finding por requisito, consolidacion A/B/C/D y verified_conclusions --
llamando DIRECTAMENTE a las mismas funciones de produccion que esa
seccion ya llama (sev.verify_sufficiency_aggregated -- fix B3 incluido,
absence_consolidator.consolidate, apply_conclusion_preconditions,
evidence_pack_gate, Finding, compute_substantive_support, applicability,
_positive_conclusion_eligibility), alimentadas con los datos YA
GUARDADOS en el checkpoint historico (chunk_executions[i]['_by_req_candidates'],
chunk_executions[i]['_criterion_assessments_for_d'], verified_records_by_req).
Ninguna funcion de decision/validacion se reimplementa; solo se reordena
la orquestacion (el propio "glue" de evaluate_chunked(), no un validador).

CERO llamadas LLM: no se importa ModelProvider, no se instancia ningun
provider, no hay red. Escrituras: cola de revision aislada a este
directorio (mismo patron que factory/tests/conftest.py:isolated_review_queue).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/home/ing_cpmo")

from factory.engines.gmpai_integrity import chunked_engine as ce
from factory.engines.gmpai_integrity.models import Finding
from factory.regulatory.corpus_runner import _PROMPT_PATH_BY_AGENT
from factory.regulatory import tier1_report as t1

DRY_DIR = Path("/home/ing_cpmo/factory/regulatory/pilot_run/tier1_dry_run_20260812")
DRY_REVIEW_QUEUE = DRY_DIR / "review_queue_dry_run.jsonl"
CHECKPOINT_PATH = Path(
    "/home/ing_cpmo/factory/regulatory/pilot_run/checkpoints/chunked-943a62bcbb85.checkpoint.json")

AGENT_ID = "fda_part11_agent"
AGENT_VERSION = "v1-pilot-2026-08"
DOCUMENT_ID = "RW-0005"
DOCUMENT_TYPE = "FS"
SISTEMA = "tier1_report_dry_run"


def main() -> None:
    checkpoint = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    chunk_executions = checkpoint["chunk_executions"]
    resumed_verified_records_by_req = checkpoint.get("verified_records_by_req") or {}
    document_sha256 = checkpoint["document_sha256"]
    assert document_sha256 == checkpoint["fingerprint"]["document_sha256"]

    meta = ce.load_prompt_meta(_PROMPT_PATH_BY_AGENT[AGENT_ID])
    model_name = chunk_executions[0]["model"]

    DRY_REVIEW_QUEUE.unlink(missing_ok=True)
    import factory.layer9.human_review_queue as hrq
    original_queue_file = hrq.REVIEW_QUEUE_FILE
    hrq.REVIEW_QUEUE_FILE = DRY_REVIEW_QUEUE

    try:
        # ---- mismo tramo que evaluate_chunked() lineas 1180-1234 ----
        by_req: dict[str, list[dict]] = {cp["req_id"]: [] for cp in meta["checkpoints"]}
        criterion_assessments_by_req: dict[str, list[tuple]] = {cp["req_id"]: [] for cp in meta["checkpoints"]}
        # R3-T1.7: verified_records_by_req se RECONSTRUYE desde cero (no se
        # reusa resumed_verified_records_by_req, el guardado en el
        # checkpoint) -- esos registros fueron calculados con la logica de
        # Ruta B PRE-fix (sin el rescate B4/B5). Reusarlos habria hecho que
        # el replay demostrara el fix en la Ruta A (Finding) pero siguiera
        # mostrando el bucket viejo en la Ruta B (conclusion real) -- el
        # error exacto que este bloque 3 existe para evitar (medir SOLO en
        # la salida final, no en una capa intermedia).
        verified_records_by_req: dict[str, list[dict]] = {cp["req_id"]: [] for cp in meta["checkpoints"]}
        known_verified_requirement_ids: set = set(by_req.keys())
        from factory.regulatory.evidence_verifier import load_requirement_terms
        requirement_terms_by_req = {req_id: load_requirement_terms(req_id) for req_id in by_req}
        from factory.regulatory.candidate_validity import resolve_candidate_evidence
        from factory.regulatory.verified_pipeline_adapter import build_finding_record
        from factory.regulatory import semantic_evidence_verification as sev

        for chunk_exec in chunk_executions:
            # Este checkpoint es ANTERIOR a la instrumentacion del fix B3
            # (commit e823015, 2026-08-12): _criterion_assessments_for_d no
            # trae 'estado' (campo agregado por ese mismo commit). Sin el,
            # _classify_criteria_for_chunk() recibe chunk_estado=None para
            # TODOS los chunks y el fix no tiene nada que reclasificar --
            # mismo gap de instrumentacion que R3_T1_4_FIX_AGREGACION_B3.md
            # seccion 3.1 ya documento y resolvio de la MISMA forma:
            # recuperar 'estado' del raw_response completo de cada chunk
            # (el propio checkpoint.json['chunk_executions'][i]['raw_response'],
            # JSON crudo con 'checkpoints'[].estado por req_id) en vez de
            # confiar en el campo que ese chunk nunca guardo. MISMO
            # mecanismo se reutiliza para recuperar 'evidencia_exacta'
            # ORIGINAL (R3-T1.6, fix B4): el candidato YA GUARDADO en
            # '_by_req_candidates' colapsa el headline vacio y el headline
            # con texto-que-no-ancla al MISMO placeholder "(no anclado en
            # el chunk, descartado)" (chunked_engine.py, construccion del
            # candidato) -- indistinguibles una vez persistidos. El
            # raw_response crudo SI conserva el valor real que emitio el
            # modelo, necesario para aplicar la regla B4 correctamente
            # sobre datos de un checkpoint historico (nunca sobre datos
            # inventados).
            estado_by_req_this_chunk: dict[str, str] = {}
            evidencia_by_req_this_chunk: dict[str, str] = {}
            try:
                # raw_response inline puede venir truncado en el checkpoint
                # (raw_response_truncated_in_log=True) -- el crudo completo
                # vive comprimido en raw_response_full_path (mismo mecanismo
                # que CheckpointStore.load_raw_response()).
                if chunk_exec.get("raw_response_truncated_in_log") and chunk_exec.get("raw_response_full_path"):
                    import gzip
                    full_path = CHECKPOINT_PATH.parent / chunk_exec["raw_response_full_path"]
                    with gzip.open(full_path, "rb") as fh:
                        raw_text = fh.read().decode("utf-8")
                else:
                    raw_text = chunk_exec.get("raw_response") or "{}"
                raw = json.loads(raw_text)
                for cp_raw in raw.get("checkpoints", []):
                    if cp_raw.get("req_id") and cp_raw.get("estado"):
                        estado_by_req_this_chunk[cp_raw["req_id"]] = cp_raw["estado"]
                    if cp_raw.get("req_id") is not None:
                        evidencia_by_req_this_chunk[cp_raw["req_id"]] = str(cp_raw.get("evidencia_exacta") or "")
            except (json.JSONDecodeError, TypeError, OSError):
                pass

            criterion_assessments_this_chunk_by_req = {
                item["req_id"]: item for item in chunk_exec.get("_criterion_assessments_for_d", [])
            }

            # R3-T1.7: Ruta B (verified_records_by_req) recorre TODOS los
            # (chunk, requisito) que respondieron -- incluidos los
            # 'evidencia_insuficiente', que _by_req_candidates NUNCA guardo
            # (chunked_engine.py hace `continue` para esos ANTES de
            # construir el candidato de Ruta A) pero que la Ruta B real SI
            # necesita para que coverage_complete sea honesta. Se usa
            # `_criterion_assessments_for_d` como driver -- ese SI tiene una
            # entrada por cada (chunk, requisito) sin excepcion (se captura
            # antes de cualquier `continue` de estado, ver chunked_engine.py).
            for req_id, cad_item in criterion_assessments_this_chunk_by_req.items():
                if req_id not in verified_records_by_req:
                    continue
                estado_this = estado_by_req_this_chunk.get(req_id, "evidencia_insuficiente")
                requires_anchor = estado_this in ("cumple", "cumple_parcialmente")
                original_evidencia = evidencia_by_req_this_chunk.get(req_id, "")
                chunk_text = cad_item.get("chunk_text", "")
                # d_detail para esta ruta se recalcula con verify_sufficiency
                # single-chunk (identico a lo que abcd.d_detail habria dado
                # en vivo) -- no viene de ningun candidate guardado (los
                # evidencia_insuficiente nunca tuvieron uno).
                _, _, d_detail_this = sev.verify_sufficiency(
                    req_id, cad_item.get("criterion_assessments"), chunk_text)
                resolved = resolve_candidate_evidence(
                    evidencia=original_evidencia, requires_anchor=requires_anchor, chunk_text=chunk_text,
                    criterion_assessments=cad_item.get("criterion_assessments"), d_detail=d_detail_this,
                )
                v_candidate = {
                    "page_start": chunk_exec.get("page_start"), "page_end": chunk_exec.get("page_end"),
                    "estado": estado_this if resolved.anchored else "evidencia_insuficiente",
                    "evidencia_exacta": resolved.verifiable_quote if resolved.anchored else "",
                }
                chunk_dict = {
                    "text": chunk_text,
                    "page_start": chunk_exec.get("page_start"), "page_end": chunk_exec.get("page_end"),
                }
                verified_records_by_req[req_id].append(build_finding_record(
                    f"vrec-replay-{chunk_exec.get('chunk_index')}-{req_id}", v_candidate, req_id,
                    chunk_dict, known_verified_requirement_ids,
                    requirement_terms_by_req.get(req_id, []),
                ))

            # Ruta A (candidate/Finding) -- solo los chunks que YA tenian un
            # candidato guardado (estado != evidencia_insuficiente, mismo
            # alcance que siempre tuvo la Ruta A). Reusa el MISMO
            # `resolve_candidate_evidence()`, nunca una segunda decision.
            for cand in chunk_exec.get("_by_req_candidates", []):
                candidate = cand["candidate"]
                candidate.setdefault("has_evidence", True)
                req_id = cand["req_id"]
                requires_anchor = candidate.get("estado") in ("cumple", "cumple_parcialmente")
                original_evidencia = evidencia_by_req_this_chunk.get(req_id, "")
                cad_item = criterion_assessments_this_chunk_by_req.get(req_id)
                chunk_text = (cad_item or {}).get("chunk_text", "")
                resolved = resolve_candidate_evidence(
                    evidencia=original_evidencia, requires_anchor=requires_anchor, chunk_text=chunk_text,
                    criterion_assessments=(cad_item or {}).get("criterion_assessments"),
                    d_detail=candidate.get("d_detail"),
                )
                # MISMO filtro adicional de relevancia tematica que
                # chunked_engine.py aplica solo en la Ruta A (legacy, nunca
                # fusionado con la superficie unica -- R1.7 lo dejo fuera de
                # la Ruta B a proposito).
                route_a_anchored = resolved.anchored
                if resolved.headline_source == "model_headline" and requires_anchor and original_evidencia:
                    label = next((cp["label"] for cp in meta["checkpoints"] if cp["req_id"] == req_id), "")
                    if not ce._is_topically_relevant(original_evidencia, label):
                        route_a_anchored = False
                candidate["evidencia_exacta"] = resolved.evidencia_exacta
                candidate["anchored"] = route_a_anchored
                candidate["has_evidence"] = resolved.has_evidence
                candidate["headline_source"] = resolved.headline_source
                by_req.setdefault(req_id, []).append(candidate)

            for item in chunk_exec.get("_criterion_assessments_for_d", []):
                estado = item.get("estado") or estado_by_req_this_chunk.get(item["req_id"])
                criterion_assessments_by_req.setdefault(item["req_id"], []).append(
                    (item["criterion_assessments"], item["chunk_text"], estado))

        admitted_checkpoints, blocked_packs = ce.evidence_pack_gate(meta)
        blocked_req_ids = {v.req_id: v for v in blocked_packs}
        any_unresolved_technical_failure = any(
            c.get("technical_execution_failure") for c in chunk_executions)

        from factory.regulatory import semantic_evidence_verification as sev

        # ---- mismo tramo que evaluate_chunked() lineas 1550-1772 (Finding por requisito) ----
        findings: list[Finding] = []
        finding_by_req: dict[str, Finding] = {}
        contradictions: list[dict] = []

        for cp in meta["checkpoints"]:
            req_id, label = cp["req_id"], cp["label"]
            if req_id not in by_req:
                continue  # requisito fuera del subconjunto cubierto por este checkpoint historico

            if req_id in blocked_req_ids:
                verdict = blocked_req_ids[req_id]
                finding = Finding(
                    sistema=SISTEMA, documento=DOCUMENT_ID, version="v1", archivo=checkpoint["archivo"],
                    pagina_o_seccion="(no evaluado: llamada bloqueada por el gate 4)",
                    requisito_regulatorio=f"{req_id} — {label}", evidencia_exacta="",
                    estado="evidencia_insuficiente",
                    brecha=f"EVIDENCE_PACK_INCOMPLETE: {verdict.detail}",
                    severidad="no_determinada", riesgo="No evaluado (gate 4).",
                    recomendacion="Completar Evidence Pack.", confianza="baja",
                    agente_responsable=AGENT_ID, revision_humana_requerida=True,
                    agent_version=AGENT_VERSION, prompt_version=meta.get("prompt_version"),
                    model=model_name, verifier_version=meta.get("verifier_version"),
                )
                findings.append(finding)
                finding_by_req.setdefault(req_id, finding)
                continue

            all_candidates = [c for c in by_req.get(req_id, []) if c["anchored"]]
            candidates = [c for c in all_candidates if c.get("has_evidence", True)]
            not_observed = [c for c in all_candidates if not c.get("has_evidence", True)]
            distinct_estados = {c["estado"] for c in candidates}

            if not candidates:
                if not_observed:
                    pages = ", ".join(f"pag {c['page_start']}-{c['page_end']}" for c in not_observed)
                    findings.append(Finding(
                        sistema=SISTEMA, documento=DOCUMENT_ID, version="v1", archivo=checkpoint["archivo"],
                        pagina_o_seccion=f"{pages} (not_observed_in_chunk en todas las secciones evaluadas)",
                        requisito_regulatorio=f"{req_id} — {label}",
                        evidencia_exacta="(ninguna seccion citó evidencia positiva ni negativa para este checkpoint)",
                        estado="no_cumple",
                        brecha="Ninguna de las secciones que mencionaron este checkpoint aporto una cita verificable.",
                        severidad="mayor", riesgo="Ausencia de evidencia documental; no confirma ausencia del control en el sistema.",
                        recomendacion="Revisar expediente completo (SOPs/IQ/OQ) antes de concluir incumplimiento real.",
                        confianza="baja", agente_responsable=AGENT_ID, revision_humana_requerida=True,
                        agent_version=AGENT_VERSION, prompt_version=meta["prompt_version"],
                        model=model_name, verifier_version=meta["verifier_version"],
                        technical_execution_failure_pending=any_unresolved_technical_failure,
                        substantive_support="NOT_APPLICABLE",
                    ))
                else:
                    findings.append(Finding(
                        sistema=SISTEMA, documento=DOCUMENT_ID, version="v1", archivo=checkpoint["archivo"],
                        pagina_o_seccion=f"paginas 1-{checkpoint.get('total_chunks', 0)} (todo el documento, por chunks)",
                        requisito_regulatorio=f"{req_id} — {label}",
                        evidencia_exacta="(sin evaluar)", estado="evidencia_insuficiente",
                        brecha="Ningun chunk del documento completo aporto evidencia anclada para este checkpoint.",
                        severidad="no_determinada", riesgo="No evaluable automaticamente; requiere revision manual.",
                        recomendacion="Revisar manualmente o reintentar el analisis LLM.",
                        confianza="baja", agente_responsable=AGENT_ID, revision_humana_requerida=True,
                        agent_version=AGENT_VERSION, prompt_version=meta["prompt_version"],
                        model=model_name, verifier_version=meta["verifier_version"],
                        technical_execution_failure_pending=any_unresolved_technical_failure,
                        substantive_support="NOT_APPLICABLE",
                    ))
                finding_by_req[req_id] = findings[-1]
                continue

            if len(distinct_estados) > 1:
                pages = ", ".join(f"pag {c['page_start']}-{c['page_end']}:{c['estado']}" for c in candidates)
                contradictions.append({"req_id": req_id, "label": label, "detalle": pages})
                findings.append(Finding(
                    sistema=SISTEMA, documento=DOCUMENT_ID, version="v1", archivo=checkpoint["archivo"],
                    pagina_o_seccion=pages, requisito_regulatorio=f"{req_id} — {label}",
                    evidencia_exacta=" | ".join(c["evidencia_exacta"] for c in candidates),
                    estado="cumple_parcialmente",
                    brecha=f"CONTRADICCION entre secciones del mismo documento: {pages}. No se resuelve automaticamente.",
                    severidad="mayor", riesgo="Inconsistencia interna del documento sobre este requisito.",
                    recomendacion="Revision humana obligatoria: confirmar cual seccion es la vigente.",
                    confianza="media", agente_responsable=AGENT_ID, revision_humana_requerida=True,
                    agent_version=AGENT_VERSION, prompt_version=meta["prompt_version"],
                    model=model_name, verifier_version=meta["verifier_version"],
                    substantive_support="NOT_SUPPORTED",
                ))
                finding_by_req[req_id] = findings[-1]
                continue

            best = candidates[0]
            brecha = best["brecha"]
            if not_observed:
                brecha += f" ({len(not_observed)} seccion(es) adicionales no trataron este checkpoint.)"

            if "a_anchor" in best:
                agg_d_status, agg_d_reason, agg_d_detail = sev.verify_sufficiency_aggregated(
                    req_id, criterion_assessments_by_req.get(req_id, []))
                abcd_aggregated = sev.ABCDResult(
                    a_anchor=best["a_anchor"], a_match_type=best.get("a_match_type", ""),
                    b_source=best["b_source"], c_semantic=best["c_semantic"], c_flags=best.get("c_flags", []),
                    d_sufficiency=agg_d_status, d_reason=agg_d_reason, d_detail=agg_d_detail,
                )
                d_sufficiency = abcd_aggregated.d_sufficiency
                substantive_evidence_accepted = abcd_aggregated.substantive_evidence_accepted
                operational_result = abcd_aggregated.operational_result
            else:
                d_sufficiency = best.get("d_sufficiency")
                substantive_evidence_accepted = best.get("substantive_evidence_accepted")
                operational_result = best.get("operational_result")

            substantive_support = ce.compute_substantive_support(best["estado"], substantive_evidence_accepted)
            findings.append(Finding(
                sistema=SISTEMA, documento=DOCUMENT_ID, version="v1", archivo=checkpoint["archivo"],
                pagina_o_seccion=f"pag {best['page_start']}-{best['page_end']} (chunk {best['chunk_index']})",
                requisito_regulatorio=f"{req_id} — {label}",
                evidencia_exacta=best["evidencia_exacta"], estado=best["estado"],
                brecha=brecha, severidad="mayor" if best["estado"] == "no_cumple" else "menor",
                riesgo="Ver brecha.", recomendacion=best["recomendacion"] or f"Confirmar '{label}' con SOP.",
                confianza="media", agente_responsable=AGENT_ID, revision_humana_requerida=True,
                agent_version=AGENT_VERSION, prompt_version=meta["prompt_version"],
                model=model_name, verifier_version=meta["verifier_version"],
                d_sufficiency=d_sufficiency,
                substantive_evidence_accepted=substantive_evidence_accepted,
                operational_result=operational_result,
                substantive_support=substantive_support,
            ))
            finding_by_req[req_id] = findings[-1]

        # ---- mismo tramo que evaluate_chunked() lineas 1793-1953 (verified_conclusions) ----
        from factory.regulatory.absence_consolidator import (
            apply_conclusion_preconditions as _apply_preconditions,
            consolidate as _consolidate,
        )
        from factory.regulatory.applicability import applicability as _applicability, matrix_approved as _matrix_approved

        applicability_rule_approved = _matrix_approved()
        contradicted_req_ids = {c["req_id"] for c in contradictions}
        governed_exceptions: list[dict] = []
        verified_conclusions: dict[str, dict] = {}

        for req_id in finding_by_req:
            label = next(cp["label"] for cp in meta["checkpoints"] if cp["req_id"] == req_id)
            try:
                app = _applicability(req_id, DOCUMENT_TYPE)
                conclusion = _consolidate(
                    req_id, DOCUMENT_TYPE, app["value"], verified_records_by_req.get(req_id, []),
                    coverage_complete=True,  # BASELINE = cobertura real del documento completo
                )
                finding = finding_by_req.get(req_id)
                conclusion = _apply_preconditions(
                    conclusion,
                    d_sufficiency=finding.d_sufficiency if finding else None,
                    substantive_evidence_accepted=(
                        finding.substantive_evidence_accepted if finding else None),
                    operational_result=finding.operational_result if finding else None,
                    applicability_value=app["value"],
                    positive_conclusion_eligibility=ce._positive_conclusion_eligibility(req_id),
                    has_open_contradiction=req_id in contradicted_req_ids,
                    applicability_rule_approved=applicability_rule_approved,
                )
            except Exception as exc:  # noqa: BLE001 -- mismo patron de excepcion gobernada que evaluate_chunked()
                governed_exceptions.append({
                    "req_id": req_id, "stage": "verified_conclusions",
                    "exception": type(exc).__name__, "detail": str(exc),
                })
                from factory.regulatory.absence_consolidator import DocumentConclusion as _DocumentConclusion
                conclusion = _DocumentConclusion(
                    requirement_id=req_id, document_type=DOCUMENT_TYPE,
                    conclusion="EVALUATION_INCOMPLETE", review_flags=["CONSOLIDATION_EXCEPTION"])

            verified_conclusions[req_id] = {
                "conclusion": conclusion.conclusion,
                "chunks_evaluated": conclusion.chunks_evaluated,
                "chunks_observed": conclusion.chunks_observed,
                "chunks_review_pending": conclusion.chunks_review_pending,
                "review_flags": list(conclusion.review_flags),
            }
            if conclusion.conclusion == "SUPPORTING_EVIDENCE_UNDER_REVIEW":
                ce._dispatch_review_finding(
                    "chunked-943a62bcbb85", req_id, DOCUMENT_ID, AGENT_ID,
                    verified_records_by_req.get(req_id, []), list(conclusion.review_flags), governed_exceptions)
            elif conclusion.conclusion in ("DOCUMENTATION_GAP", "PROVISIONAL_GAP"):
                ce._dispatch_baseline_gap_review(
                    "chunked-943a62bcbb85", req_id, DOCUMENT_ID, AGENT_ID, conclusion.conclusion,
                    list(conclusion.review_flags), governed_exceptions)
            elif (conclusion.conclusion == "EVALUATION_INCOMPLETE"
                  and "ABCD_D_NOT_ASSESSABLE" in conclusion.review_flags):
                ce._dispatch_contradiction_blocked_review(
                    "chunked-943a62bcbb85", req_id, DOCUMENT_ID, AGENT_ID,
                    list(conclusion.review_flags), governed_exceptions)

        print(f"findings={len(findings)} contradictions={len(contradictions)} "
              f"governed_exceptions={len(governed_exceptions)}")
        for req_id, vc in verified_conclusions.items():
            print(f"  {req_id}: {vc['conclusion']} flags={vc['review_flags']}")
        print("\n=== FINDINGS (d_sufficiency / evidencia_exacta) ===")
        for f in findings:
            print(f" {f.requisito_regulatorio}: d_sufficiency={f.d_sufficiency} "
                  f"evidencia={f.evidencia_exacta[:80]!r}")

        # ---- post-proceso identico a tier1_report.generate_tier1_report() lineas 235-267 ----
        findings_by_req = {f.requisito_regulatorio.split(" — ")[0]: f.to_dict() for f in findings}
        from factory.layer9.human_review_queue import list_pending
        pending_by_req = {
            e["summary"]["requirement_id"]: e["rc_id"]
            for e in list_pending()
            if e.get("summary", {}).get("run_id") == "chunked-943a62bcbb85"
        }

        requirements = []
        for req_id, vc in verified_conclusions.items():
            bucket = t1._bucket_for_conclusion(vc["conclusion"])
            finding = findings_by_req.get(req_id)
            cross_reference_target = None
            if bucket == t1.CROSS_REFERENCE:
                cross_reference_target = list(_applicability(req_id, DOCUMENT_TYPE)["evidence_expected_in"]) or None
            requirements.append(t1.RequirementOutcome(
                requirement_id=req_id, bucket=bucket, conclusion=vc["conclusion"],
                review_flags=list(vc.get("review_flags") or []),
                evidence_quote=(finding.get("evidencia_exacta") or None) if bucket == t1.CONFIRMED and finding else None,
                page_or_section=t1._normalize_page_or_section(finding.get("pagina_o_seccion")) if finding else None,
                review_queue_rc_id=pending_by_req.get(req_id) if bucket == t1.NEEDS_HUMAN_REVIEW else None,
                cross_reference_target=cross_reference_target,
            ))

        report = t1.Tier1Report(
            document_id=DOCUMENT_ID, agent_id=AGENT_ID, run_id="chunked-943a62bcbb85",
            generated_at=datetime.now(timezone.utc).isoformat(),
            requirements=sorted(requirements, key=lambda r: r.requirement_id),
        )

        md = t1.render_tier1_markdown(report)
        banner = (
            "\n> **DRY_RUN_FROM_HISTORICAL_CHECKPOINT (R3-T1.5 bloque 1, replay "
            "acotado, 2026-08-12)** -- este informe NO es un producto entregable. "
            "Se generó reconstruyendo la consolidación A/B/C/D con las mismas "
            "funciones de producción (absence_consolidator.consolidate, "
            "apply_conclusion_preconditions, semantic_evidence_verification."
            "verify_sufficiency_aggregated con el fix B3 -- commit `e823015`) "
            "sobre los datos ya guardados del checkpoint histórico "
            "`chunked-943a62bcbb85` (perfil BASELINE, 2026-08-11). "
            "evaluate_chunked() no soporta reabrir un checkpoint completed=True "
            "(guardia deliberada, ver docs_plan/R3_T1_5_F2_DRY.md bloque 1), así "
            "que este informe NO pasó por esa función -- es una reconstrucción "
            "fiel de su tramo de consolidación, no una corrida nueva del motor. "
            "No reemplaza una corrida H2H4 real ni constituye un informe Tier-1 "
            "válido para revisión de producto.\n"
        )
        md = md.replace("\n\n## Resumen por bucket", banner + "\n## Resumen por bucket")

        (DRY_DIR / "informe_tier1_DRY_RUN.md").write_text(md, encoding="utf-8")
        (DRY_DIR / "verified_conclusions_DRY_RUN.json").write_text(
            json.dumps(verified_conclusions, ensure_ascii=False, indent=2), encoding="utf-8")
        (DRY_DIR / "governed_exceptions_DRY_RUN.json").write_text(
            json.dumps(governed_exceptions, ensure_ascii=False, indent=2), encoding="utf-8")
        review_queue_content = []
        if DRY_REVIEW_QUEUE.exists():
            review_queue_content = [json.loads(l) for l in DRY_REVIEW_QUEUE.read_text(encoding="utf-8").splitlines() if l.strip()]
        (DRY_DIR / "review_queue_entries_DRY_RUN.json").write_text(
            json.dumps(review_queue_content, ensure_ascii=False, indent=2), encoding="utf-8")

        print("\n=== BUCKETS ===")
        print(json.dumps(report.counts_by_bucket(), indent=2, ensure_ascii=False))
        print("\n=== POR REQUISITO ===")
        for r in report.requirements:
            print(f"{r.requirement_id}: bucket={r.bucket} conclusion={r.conclusion} "
                  f"page={r.page_or_section!r} rc={r.review_queue_rc_id!r} flags={r.review_flags}")
        print(f"\nreview_queue_dry_run entries: {len(review_queue_content)}")

    finally:
        hrq.REVIEW_QUEUE_FILE = original_queue_file


if __name__ == "__main__":
    main()
