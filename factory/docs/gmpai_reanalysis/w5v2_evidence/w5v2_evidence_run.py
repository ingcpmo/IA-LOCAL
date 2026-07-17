"""W5 Ciclo 1 (v2), Fase 4, Bloque 4.3 -- ejecucion de evidencia end-to-end
REAL (Ollama real, documento real FS_v1.2, run_context='validation').

CONGELADO (Fase 5.0, W5.3, 2026-07-17): este script es un REGISTRO
HISTORICO de la ejecucion real que produjo w5v2_evidence_run_result.json
-- no se actualiza para reflejar la firma actual de generate_controlled()
(que en Fase 5.0 paso a exigir run_context como keyword-only obligatorio,
sin default). Editar la llamada de la linea ~129 para "arreglarla" haria
que el codigo del script dejara de coincidir con lo que REALMENTE se
ejecuto para generar la evidencia -- lo cual es peor que dejarlo
desactualizado. Para una nueva ejecucion de evidencia, usar el runner
versionado (factory/regulatory/tools/run_validation_evidence.py, Fase 5.0)
en vez de este script.

Alcance declarado (coverage=partial, honesto por diseno -- no se corre la
mision completa de 19 requisitos x 27 chunks en esta evidencia, sino un
subconjunto representativo real, suficiente para demostrar que el
mecanismo funciona extremo a extremo con inferencia real):

  - Documento: 215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf (real,
    extraido con pypdf en este mismo script -- no reprocesado por el
    motor de produccion, solo lectura de texto).
  - document_type = 'FS', document_type_source = 'human_assigned'
    (asignacion explicita de este script, no inferida).
  - Requisitos: 3 con applicability='expected' para FS en la matriz
    aprobada (Checkpoint B, MC-0001): 21_CFR_11.10(d), ANNEX11_9,
    ALCOA_ATTRIBUTABLE. Mas 1 con out_of_document_scope para FS
    (21_CFR_11.10(a) evidence_expected_in=[RA,IQ,OQ,PQ] via
    cross_reference_expected... en realidad 11.10(a) es
    cross_reference_expected no OOS para FS: se usa
    21_CFR_11.10(d) contra IQ para demostrar el caso OOS real, sin
    llamar a Ollama, ver mas abajo) -- demuestra el filtro
    pre-inferencia real.
  - Chunks: los primeros 2 chunks reales (paginas 1-N segun
    build_page_chunks) del documento -- coverage='partial' declarado
    explicitamente en el resultado.

Conectividad: FACTORY_OLLAMA_BASE_URL no esta seteada en el entorno del
contenedor factory-api (default http://localhost:11434, INCORRECTO desde
dentro del contenedor). Verificado en este script que
http://host.docker.internal:11434 SI es alcanzable (mismo Ollama real,
modelo qwen2.5:7b-instruct-q4_K_M presente) -- se pasa como override de
proceso (variable de entorno de ESTE script unicamente), sin tocar
docker-compose ni la configuracion persistente del contenedor.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

os.environ["FACTORY_OLLAMA_BASE_URL"] = "http://host.docker.internal:11434"

sys.path.insert(0, "/app")

import pypdf

from factory.engines.gmpai_integrity import ollama_client
from factory.regulatory.applicability import applicability, pre_inference_filter
from factory.regulatory.evidence_verifier import load_requirement_terms, verify_llm_output
from factory.regulatory.absence_consolidator import consolidate
from factory.core import audit_writer

DOC_PATH = Path("/home/ing_cpmo/GMPAI/source/Rockwell/215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf")
DOCUMENT_TYPE = "FS"
RUN_ID = f"w5v2-validation-{uuid.uuid4().hex[:12]}"
RUN_CONTEXT = "validation"
RUN_BY = "Cesar (autorizado via instruccion explicita de ejecutar Fase 4, sesion 2026-07-17)"

REQUIREMENTS_TO_RUN = ["21_CFR_11.10(d)", "ANNEX11_9", "ALCOA_ATTRIBUTABLE"]
REQUIREMENT_LABELS = {
    "21_CFR_11.10(d)": "Limitar acceso a individuos autorizados",
    "ANNEX11_9": "Audit trail",
    "ALCOA_ATTRIBUTABLE": "Attributable — quien genero el dato",
}
OOS_DEMO_REQUIREMENT = "21_CFR_11.10(d)"
OOS_DEMO_DOCUMENT_TYPE = "IQ"  # 21_CFR_11.10(d).IQ = out_of_document_scope en la matriz


def build_observation_prompt(requirement_id: str, label: str, chunk_text: str) -> str:
    return (
        "Eres un revisor tecnico. Tu UNICA tarea es OBSERVAR si el fragmento de "
        "documento de abajo contiene evidencia relacionada con el siguiente "
        "requisito regulatorio. NO decidas si el sistema CUMPLE o NO CUMPLE el "
        "requisito -- eso lo decide un proceso separado. Responde EXCLUSIVAMENTE "
        "en el formato JSON solicitado.\n\n"
        f"requirement_id: {requirement_id}\n"
        f"requirement_label: {label}\n\n"
        "chunk_observation debe ser:\n"
        "  'observed' si el fragmento contiene evidencia clara y directa del "
        "requisito.\n"
        "  'partially_observed' si hay evidencia parcial o indirecta.\n"
        "  'not_observed_in_chunk' si el fragmento no trata el tema del "
        "requisito (esto NO significa que el sistema incumpla -- solo que "
        "este fragmento no lo menciona).\n\n"
        "Si observed o partially_observed: evidence_quote debe ser una cita "
        "LITERAL y EXACTA copiada del fragmento (no parafrasees). Si "
        "not_observed_in_chunk: evidence_quote debe ser cadena vacia.\n\n"
        f"[FRAGMENTO]\n{chunk_text}\n[FIN FRAGMENTO]\n"
    )


def main():
    # 1. Extraccion real (solo lectura, no reprocesa hallazgos del motor)
    reader = pypdf.PdfReader(str(DOC_PATH))
    per_unit_text = [(p.extract_text() or "") for p in reader.pages]
    total_pages_real = len(per_unit_text)

    from factory.engines.gmpai_integrity.chunked_engine import build_page_chunks, sanitize_document
    all_chunks = build_page_chunks(per_unit_text)
    chunks_used = all_chunks[:2]  # coverage=partial, declarado
    for c in chunks_used:
        c["text"] = sanitize_document(c["text"])

    # 2. Verificar conectividad real y capturar manifiesto de preflight
    model_digest = ollama_client.show_digest()
    ollama_version_str = ollama_client.ollama_version()

    # 3. Filtro pre-inferencia real (demuestra out_of_document_scope sin
    #    gastar ninguna llamada a Ollama)
    oos_result = pre_inference_filter(OOS_DEMO_REQUIREMENT, OOS_DEMO_DOCUMENT_TYPE)
    assert oos_result is not None and oos_result["conclusion"] == "OUT_OF_DOCUMENT_SCOPE"
    ollama_calls_avoided = 1  # el filtro evito exactamente esta llamada

    # 4. Inferencia real + verificacion + consolidacion por requisito
    per_requirement_results = {}
    all_records = []
    known_ids = set(REQUIREMENTS_TO_RUN)

    for req_id in REQUIREMENTS_TO_RUN:
        app = applicability(req_id, DOCUMENT_TYPE)
        label = REQUIREMENT_LABELS[req_id]
        terms = load_requirement_terms(req_id)
        records = []
        for chunk in chunks_used:
            prompt = build_observation_prompt(req_id, label, chunk["text"])
            gen = ollama_client.generate_controlled(prompt, chunk)
            record_id = f"rec-{uuid.uuid4().hex[:12]}"
            if not gen["ok"] or gen["llm_output"] is None:
                verification_status = "rejected_by_verifier"
                record = {
                    "record_id": record_id, "llm_output": None,
                    "execution_manifest": gen["execution_manifest"],
                    "status": "rejected_by_verifier",
                    "rejection_reason": gen.get("rejection_reason") or "schema_validation_failed",
                    "review_flags": [],
                }
            else:
                verification = verify_llm_output(gen["llm_output"], chunk, known_ids, terms)
                record = {
                    "record_id": record_id, "llm_output": gen["llm_output"],
                    "execution_manifest": gen["execution_manifest"],
                    "status": verification.status,
                    "rejection_reason": verification.rejection_reason,
                    "review_flags": verification.review_flags,
                    "verification_checks": verification.checks,
                }
            records.append(record)
            all_records.append(record)

        conclusion = consolidate(req_id, DOCUMENT_TYPE, app["value"], records)
        per_requirement_results[req_id] = {
            "applicability_value": app["value"],
            "records": records,
            "conclusion": {
                "requirement_id": conclusion.requirement_id,
                "conclusion": conclusion.conclusion,
                "chunks_evaluated": conclusion.chunks_evaluated,
                "chunks_observed": conclusion.chunks_observed,
                "chunks_review_pending": conclusion.chunks_review_pending,
                "supporting_records": conclusion.supporting_records,
                "review_flags": conclusion.review_flags,
            },
        }

    # 5. Resumen agregado (Bloque 4.3)
    status_counts = {"verified": 0, "verified_with_deviation": 0, "review_required": 0, "rejected_by_verifier": 0}
    manifest_incomplete_count = 0
    for r in all_records:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
        if r["execution_manifest"].get("manifest_incomplete"):
            manifest_incomplete_count += 1

    # El filtro de aplicabilidad no genero review_required en este subconjunto
    # (los 3 requisitos elegidos son 'expected' para FS); se deja la lista
    # explicita vacia en vez de omitir el campo.
    review_queue = []

    summary = {
        "run_id": RUN_ID,
        "run_context": RUN_CONTEXT,
        "run_by": RUN_BY,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "documento": DOC_PATH.name,
        "document_type": DOCUMENT_TYPE,
        "document_type_source": "human_assigned",
        "total_pages_real": total_pages_real,
        "total_chunks_real": len(all_chunks),
        "chunks_used_this_run": len(chunks_used),
        "coverage": "partial",
        "coverage_note": f"{len(chunks_used)}/{len(all_chunks)} chunks reales evaluados (subconjunto representativo de evidencia, no la mision completa)",
        "requirements_evaluated": REQUIREMENTS_TO_RUN,
        "records_by_status": status_counts,
        "records_total": len(all_records),
        "manifest_incomplete_count": manifest_incomplete_count,
        "manifest_incomplete_pct": round(100 * manifest_incomplete_count / len(all_records), 2) if all_records else 0.0,
        "model": ollama_client.OLLAMA_MODEL,
        "model_digest": model_digest,
        "ollama_version": ollama_version_str,
        "ollama_calls_avoided_by_applicability_filter": ollama_calls_avoided,
        "out_of_document_scope_demo": {
            "requirement_id": OOS_DEMO_REQUIREMENT,
            "document_type": OOS_DEMO_DOCUMENT_TYPE,
            "result": oos_result,
        },
        "review_queue": review_queue,
        "per_requirement_conclusions": {
            k: v["conclusion"] for k, v in per_requirement_results.items()
        },
    }

    out_path = Path("/tmp/w5v2_evidence_run_result.json")
    full_output = dict(summary)
    full_output["per_requirement_full_records"] = {
        k: v["records"] for k, v in per_requirement_results.items()
    }
    out_path.write_text(json.dumps(full_output, indent=2, ensure_ascii=False), encoding="utf-8")

    # 6. EXACTAMENTE 1 evento de auditoria nuevo, run_context=validation
    audit_writer.write_event(
        "w5v2_validation_evidence_run",
        "gmpai_document_validation",
        {
            "run_id": RUN_ID,
            "run_context": RUN_CONTEXT,
            "run_by": RUN_BY,
            "documento": DOC_PATH.name,
            "document_type": DOCUMENT_TYPE,
            "coverage": "partial",
            "requirements_evaluated": REQUIREMENTS_TO_RUN,
            "records_by_status": status_counts,
            "records_total": len(all_records),
            "manifest_incomplete_pct": summary["manifest_incomplete_pct"],
            "model": ollama_client.OLLAMA_MODEL,
            "model_digest": model_digest,
            "ollama_calls_avoided_by_applicability_filter": ollama_calls_avoided,
            "result_file": str(out_path),
        },
    )

    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
