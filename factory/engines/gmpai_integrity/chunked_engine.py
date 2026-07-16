"""
Motor de integridad regulatoria por CHUNKS (páginas reales, con solapamiento,
checkpoints de reanudación, run_id/task_id, consolidación y detección de
contradicciones).

Ruta git-trackeada: reemplaza la copia original en
factory/workspaces/gmpai_document_validation/app/chunked_llm_integrity_engine.py
(gitignorada por factory/.gitignore 'workspaces/*'). Misma lógica de
consolidación validada con el piloto real sobre "215115305 SCADA-PCS Misc PLC
System URS v2.1.pdf" (incluye el fix de anclaje en no_cumple: no se exige cita
positiva anclada para una afirmación de AUSENCIA).

Reemplaza para documentos largos el enfoque de un solo llamado
(_MAX_DOC_CHARS=6000, trunca todo lo que sigue) por procesamiento secuencial
de TODO el documento en fragmentos reales basados en páginas
(ExtractionResult.per_unit_text), sin exceder ~6000 caracteres por llamada.

Trazabilidad registrada por documento/chunk:
  - documento y SHA-256 (document_sha256, pasado por el llamador)
  - página, sección y chunk (page_start/page_end/chunk_index)
  - run_id y task_id (uno por documento, uno por chunk)
  - agente y agent_version
  - modelo Ollama y digest (model / model_digest)
  - timestamps (started_at/finished_at por chunk)
  - checkpoints y reanudación (ver resume_from_checkpoint / CheckpointStore)
  - findings por chunk, consolidación y deduplicación (evaluate_chunked)
  - citas de página/sección (pagina_o_seccion en cada Finding)
  - auditoría (factory/audit/factory_audit.jsonl vía audit_writer, un evento
    resumen por documento analizado)

Regla de consolidación por checkpoint (req_id): igual que la versión
original — el estado no-insuficiente gana si existe alguno; contradicción
real entre fragmentos (cumple vs no_cumple) queda como
cumple_parcialmente + revision_humana_requerida=True, sin descartar ninguna
fuente.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml as _yaml

from . import ollama_client
from .models import Finding

CHUNK_MAX_CHARS = 6000
CHUNK_OVERLAP_CHARS = 500

_MARKER_START = "[DOCUMENTO INICIO]"
_MARKER_END = "[DOCUMENTO FIN]"
_VALID_ESTADOS = {"cumple", "cumple_parcialmente", "no_cumple", "evidencia_insuficiente", "no_aplica"}


def load_prompt_meta(prompt_path: Path) -> dict:
    return _yaml.safe_load(prompt_path.read_text(encoding="utf-8"))


def sanitize_document(text: str) -> str:
    text = text.replace(_MARKER_START, "[documento-inicio]").replace(_MARKER_END, "[documento-fin]")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return text


def build_prompt(meta: dict, doc_text: str, max_chars: int = CHUNK_MAX_CHARS) -> str:
    doc = sanitize_document(doc_text)
    truncated = len(doc) > max_chars
    if truncated:
        doc = doc[:max_chars]
    checkpoints_desc = "\n".join(f"  - {c['req_id']}: {c['label']}" for c in meta["checkpoints"])
    note = f"\n\n[NOTA: fragmento truncado a los primeros {max_chars} caracteres]" if truncated else ""
    return (
        meta["common_contract"]
        + "\nLista de req_id a evaluar (uno por checkpoint, en este orden):\n"
        + checkpoints_desc
        + f"\n\n{_MARKER_START}\n{doc}{note}\n{_MARKER_END}\n"
    )


def _extract_json(raw: str) -> dict | None:
    raw = raw.strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _is_anchored(evidencia: str, source_text: str) -> bool:
    if not evidencia or not evidencia.strip():
        return False
    return _normalize(evidencia) in _normalize(source_text)


_LABEL_STOPWORDS = {
    "y", "de", "del", "la", "el", "los", "las", "en", "a", "un", "una", "para", "con",
    "quien", "que", "es", "su", "sus", "o", "sin", "no", "al", "por",
}


def _is_topically_relevant(evidencia: str, label: str) -> bool:
    """Fix 2026-07-16 (post-mortem C1-FDA-11.10d / C3-ANNEX11-12, ver
    factory/docs/gmpai_reanalysis/fs_v1_2/): el anclaje literal (la cita
    existe textualmente en el chunk) NO garantiza que la cita sea SOBRE el
    requisito evaluado — el modelo puede anclar correctamente una frase
    real que habla de otro tema (ej. una cita sobre audit trail de login
    aceptada como evidencia de "control de acceso"). Heuristica ligera (sin
    llamada adicional al LLM): al menos una palabra significativa (>=4
    caracteres, fuera de stopwords) del label del checkpoint debe aparecer
    en la cita. Ante ausencia de label o de palabras significativas, no
    bloquea (True)."""
    if not label:
        return True
    desc = label.split("—", 1)[-1] if "—" in label else label
    words = [w.lower() for w in re.findall(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]+", desc) if len(w) >= 4]
    words = [w for w in words if w not in _LABEL_STOPWORDS]
    if not words:
        return True
    ev_lower = evidencia.lower()
    return any(w in ev_lower for w in words)


def build_page_chunks(per_unit_text: list[str], max_chars: int = CHUNK_MAX_CHARS,
                       overlap_chars: int = CHUNK_OVERLAP_CHARS) -> list[dict]:
    """Agrupa páginas reales (1 entrada por página) en chunks de hasta
    max_chars, con solapamiento real (cola del chunk anterior). Cada chunk
    declara su rango real de páginas (1-indexado)."""
    chunks: list[dict] = []
    current_pages: list[int] = []
    current_text = ""
    overlap_prefix = ""

    def _flush():
        nonlocal current_pages, current_text, overlap_prefix
        if not current_pages:
            return
        text = overlap_prefix + current_text
        chunks.append({
            "chunk_index": len(chunks),
            "page_start": current_pages[0],
            "page_end": current_pages[-1],
            "text": text,
            "text_chars": len(text),
            "has_overlap_prefix": bool(overlap_prefix),
        })
        overlap_prefix = current_text[-overlap_chars:] if len(current_text) > overlap_chars else current_text
        current_pages = []
        current_text = ""

    for i, page_text in enumerate(per_unit_text, start=1):
        page_text = page_text or ""
        if current_text and len(current_text) + len(page_text) > max_chars:
            _flush()
        current_pages.append(i)
        current_text += ("\n\f\n" if current_text else "") + page_text
    _flush()
    return chunks


class CheckpointStore:
    """Persistencia de reanudación: guarda chunk_executions ya completados
    (por run_id) en disco tras cada chunk, para poder reanudar un análisis
    largo interrumpido (fallo de Ollama, reinicio, Ctrl-C) sin repetir
    llamadas ya realizadas. Formato: 1 archivo JSON por run_id."""

    def __init__(self, checkpoint_dir: Path):
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, run_id: str) -> Path:
        return self.checkpoint_dir / f"{run_id}.checkpoint.json"

    def load(self, run_id: str) -> dict | None:
        p = self._path(run_id)
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def save(self, run_id: str, state: dict) -> None:
        p = self._path(run_id)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)

    def find_resumable(self, document_sha256: str, agent_id: str) -> dict | None:
        """Busca un checkpoint incompleto previo para el mismo documento
        (por SHA-256) y agente, para reanudar en vez de reiniciar."""
        for f in self.checkpoint_dir.glob("*.checkpoint.json"):
            try:
                state = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if (state.get("document_sha256") == document_sha256
                    and state.get("agent_id") == agent_id
                    and not state.get("completed", False)):
                return state
        return None


def evaluate_chunked(prompt_path: Path, agent_id: str, agent_version: str,
                      per_unit_text: list[str], sistema: str, documento: str,
                      version: str, archivo: str, document_sha256: str,
                      checkpoint_store: "CheckpointStore | None" = None,
                      run_id: str | None = None) -> dict:
    """Procesa TODO el documento (todas las páginas reales) en chunks
    acotados, con metadata de runtime completa por chunk, checkpoints de
    reanudación opcionales, y consolida un Finding final por checkpoint.

    Si checkpoint_store se provee: intenta reanudar un run incompleto del
    mismo documento+agente (find_resumable) antes de empezar de cero, y
    guarda progreso tras cada chunk (nunca se pierden llamadas ya hechas a
    Ollama si el proceso se interrumpe)."""
    meta = load_prompt_meta(prompt_path)
    model_digest = ollama_client.show_digest()

    chunks = build_page_chunks(per_unit_text)
    chunk_executions: list[dict] = []
    start_index = 0

    resumed = None
    if checkpoint_store is not None:
        resumed = checkpoint_store.find_resumable(document_sha256, agent_id)

    if resumed is not None:
        run_id = resumed["run_id"]
        chunk_executions = resumed.get("chunk_executions", [])
        start_index = len(chunk_executions)
    else:
        run_id = run_id or f"chunked-{uuid.uuid4().hex[:12]}"

    by_req: dict[str, list[dict]] = {cp["req_id"]: [] for cp in meta["checkpoints"]}
    cp_label_by_req = {cp["req_id"]: cp["label"] for cp in meta["checkpoints"]}
    # Re-derivar by_req de chunk_executions ya completados (reanudación real,
    # no solo saltar llamadas — la consolidación final también debe verlos).
    # has_evidence puede faltar en checkpoints generados antes del fix
    # 2026-07-16; se asume True (comportamiento previo) para no romper
    # reanudaciones de runs viejos.
    for ce in chunk_executions:
        for cand in ce.get("_by_req_candidates", []):
            cand["candidate"].setdefault("has_evidence", True)
            by_req.setdefault(cand["req_id"], []).append(cand["candidate"])

    for chunk in chunks[start_index:]:
        task_id = f"task-{uuid.uuid4().hex[:12]}"
        text = sanitize_document(chunk["text"])
        started_at = datetime.now(timezone.utc).isoformat()
        t0 = time.monotonic()

        if not text.strip():
            chunk_result = None
            error = "chunk sin texto extraible"
        else:
            prompt = build_prompt(meta, text)
            try:
                raw = ollama_client.generate(prompt)
                response_text = raw.get("response", "") if isinstance(raw, dict) else ""
                chunk_result = _extract_json(response_text)
                error = None if chunk_result else "respuesta del modelo no es JSON valido"
            except Exception as e:
                chunk_result = None
                error = f"fallo de llamada al modelo ({type(e).__name__}: {e})"

        wall_ms = round((time.monotonic() - t0) * 1000, 1)
        finished_at = datetime.now(timezone.utc).isoformat()

        by_req_candidates = []
        if chunk_result and isinstance(chunk_result.get("checkpoints"), list):
            for entry in chunk_result["checkpoints"]:
                if not isinstance(entry, dict) or not entry.get("req_id"):
                    continue
                estado = entry.get("estado") if entry.get("estado") in _VALID_ESTADOS else "evidencia_insuficiente"
                if estado == "evidencia_insuficiente":
                    continue
                evidencia = str(entry.get("evidencia_exacta") or "")
                anchored = _is_anchored(evidencia, chunk["text"]) if evidencia else False
                requires_anchor = estado in ("cumple", "cumple_parcialmente")
                valid_candidate = anchored if requires_anchor else True
                # Fix 2026-07-16: anclaje literal no basta para cumple/
                # cumple_parcialmente — la cita debe ademas ser tematicamente
                # relevante al checkpoint (ver _is_topically_relevant).
                topically_relevant = (
                    _is_topically_relevant(evidencia, cp_label_by_req.get(entry["req_id"], ""))
                    if (requires_anchor and evidencia) else True
                )
                valid_candidate = valid_candidate and topically_relevant
                has_evidence = bool(evidencia.strip())
                candidate = {
                    "chunk_index": chunk["chunk_index"], "page_start": chunk["page_start"],
                    "page_end": chunk["page_end"], "estado": estado,
                    "evidencia_exacta": evidencia if (anchored or not requires_anchor) else "(no anclado en el chunk, descartado)",
                    "brecha": str(entry.get("brecha") or ""),
                    "recomendacion": str(entry.get("recomendacion") or ""),
                    "anchored": valid_candidate,
                    "has_evidence": has_evidence,
                }
                by_req.setdefault(entry["req_id"], []).append(candidate)
                by_req_candidates.append({"req_id": entry["req_id"], "candidate": candidate})

        chunk_executions.append({
            "run_id": run_id, "task_id": task_id, "chunk_index": chunk["chunk_index"],
            "page_start": chunk["page_start"], "page_end": chunk["page_end"],
            "has_overlap_prefix": chunk["has_overlap_prefix"], "text_chars": chunk["text_chars"],
            "started_at": started_at, "finished_at": finished_at, "wall_clock_ms": wall_ms,
            "model": ollama_client.OLLAMA_MODEL, "model_digest": model_digest,
            "ok": chunk_result is not None, "error": error,
            "_by_req_candidates": by_req_candidates,
        })

        if checkpoint_store is not None:
            checkpoint_store.save(run_id, {
                "run_id": run_id, "document_sha256": document_sha256, "agent_id": agent_id,
                "documento": documento, "archivo": archivo, "total_chunks": len(chunks),
                "chunk_executions": chunk_executions, "completed": False,
            })

    findings: list[Finding] = []
    contradictions = []
    for cp in meta["checkpoints"]:
        req_id, label = cp["req_id"], cp["label"]
        all_candidates = [c for c in by_req.get(req_id, []) if c["anchored"]]
        # Fix 2026-07-16: separar afirmaciones POSITIVAS (con cita real,
        # has_evidence=True) de no_cumple "por defecto" sin cita
        # (not_observed_in_chunk — el chunk simplemente no trato el tema,
        # no es prueba de ausencia). Una contradiccion real exige DOS
        # afirmaciones positivas incompatibles; un no_cumple sin cita nunca
        # contradice por si solo a un cumple/cumple_parcialmente anclado.
        candidates = [c for c in all_candidates if c.get("has_evidence", True)]
        not_observed = [c for c in all_candidates if not c.get("has_evidence", True)]
        distinct_estados = {c["estado"] for c in candidates}

        if not candidates:
            if not_observed:
                pages = ", ".join(f"pag {c['page_start']}-{c['page_end']}" for c in not_observed)
                findings.append(Finding(
                    sistema=sistema, documento=documento, version=version, archivo=archivo,
                    pagina_o_seccion=f"{pages} (not_observed_in_chunk en todas las secciones evaluadas)",
                    requisito_regulatorio=f"{req_id} — {label}",
                    evidencia_exacta="(ninguna seccion citó evidencia positiva ni negativa para este checkpoint)",
                    estado="no_cumple",
                    brecha=(f"Ninguna de las {len(not_observed)} secciones que mencionaron este checkpoint "
                            "aporto una cita verificable; la conclusion se basa en ausencia generalizada, "
                            "no en una demostracion positiva de incumplimiento del sistema. No documentado "
                            "en el FS != control inexistente en el sistema — requiere revision del expediente "
                            "completo (SOPs, IQ/OQ) antes de asumir incumplimiento real."),
                    severidad="mayor",
                    riesgo="Ausencia de evidencia documental; no confirma ausencia del control en el sistema.",
                    recomendacion="Revisar expediente completo (SOPs/IQ/OQ) antes de concluir incumplimiento real.",
                    confianza="baja", agente_responsable=agent_id, revision_humana_requerida=True,
                    agent_version=agent_version, prompt_version=meta["prompt_version"],
                    model=ollama_client.OLLAMA_MODEL, verifier_version=meta["verifier_version"],
                ))
            else:
                findings.append(Finding(
                    sistema=sistema, documento=documento, version=version, archivo=archivo,
                    pagina_o_seccion=f"paginas 1-{len(per_unit_text)} (todo el documento, por chunks)",
                    requisito_regulatorio=f"{req_id} — {label}",
                    evidencia_exacta="(sin evaluar)", estado="evidencia_insuficiente",
                    brecha="Ningun chunk del documento completo aporto evidencia anclada para este checkpoint.",
                    severidad="no_determinada",
                    riesgo="No evaluable automaticamente; requiere revision manual.",
                    recomendacion="Revisar manualmente o reintentar el analisis LLM.",
                    confianza="baja", agente_responsable=agent_id, revision_humana_requerida=True,
                    agent_version=agent_version, prompt_version=meta["prompt_version"],
                    model=ollama_client.OLLAMA_MODEL, verifier_version=meta["verifier_version"],
                ))
            continue

        if len(distinct_estados) > 1:
            pages = ", ".join(f"pag {c['page_start']}-{c['page_end']}:{c['estado']}" for c in candidates)
            contradictions.append({"req_id": req_id, "label": label, "detalle": pages})
            findings.append(Finding(
                sistema=sistema, documento=documento, version=version, archivo=archivo,
                pagina_o_seccion=pages,
                requisito_regulatorio=f"{req_id} — {label}",
                evidencia_exacta=" | ".join(c["evidencia_exacta"] for c in candidates),
                estado="cumple_parcialmente",
                brecha=f"CONTRADICCION entre secciones del mismo documento: {pages}. No se resuelve automaticamente.",
                severidad="mayor", riesgo="Inconsistencia interna del documento sobre este requisito.",
                recomendacion="Revision humana obligatoria: confirmar cual seccion es la vigente.",
                confianza="media", agente_responsable=agent_id, revision_humana_requerida=True,
                agent_version=agent_version, prompt_version=meta["prompt_version"],
                model=ollama_client.OLLAMA_MODEL, verifier_version=meta["verifier_version"],
            ))
            continue

        best = candidates[0]
        brecha = best["brecha"]
        if not_observed:
            brecha += (f" ({len(not_observed)} seccion(es) adicionales no trataron este checkpoint — "
                       "not_observed_in_chunk, no cuentan como evidencia en contra.)")
        findings.append(Finding(
            sistema=sistema, documento=documento, version=version, archivo=archivo,
            pagina_o_seccion=f"pag {best['page_start']}-{best['page_end']} (chunk {best['chunk_index']})",
            requisito_regulatorio=f"{req_id} — {label}",
            evidencia_exacta=best["evidencia_exacta"], estado=best["estado"],
            brecha=brecha, severidad="mayor" if best["estado"] == "no_cumple" else "menor",
            riesgo="Ver brecha.", recomendacion=best["recomendacion"] or f"Confirmar '{label}' con SOP.",
            confianza="media", agente_responsable=agent_id, revision_humana_requerida=True,
            agent_version=agent_version, prompt_version=meta["prompt_version"],
            model=ollama_client.OLLAMA_MODEL, verifier_version=meta["verifier_version"],
        ))

    result = {
        "run_id": run_id,
        "agent_id": agent_id,
        "agent_version": agent_version,
        "document_sha256": document_sha256,
        "documento": documento,
        "archivo": archivo,
        "total_pages": len(per_unit_text),
        "chunks_total": len(chunks),
        "chunk_executions": [{k: v for k, v in ce.items() if k != "_by_req_candidates"} for ce in chunk_executions],
        "contradictions": contradictions,
        "findings": [f.to_dict() for f in findings],
        "model": ollama_client.OLLAMA_MODEL,
        "model_digest": model_digest,
    }

    if checkpoint_store is not None:
        checkpoint_store.save(run_id, {
            "run_id": run_id, "document_sha256": document_sha256, "agent_id": agent_id,
            "documento": documento, "archivo": archivo, "total_chunks": len(chunks),
            "chunk_executions": chunk_executions, "completed": True,
        })

    _write_audit_event(result)
    return result


def _write_audit_event(result: dict) -> None:
    try:
        from factory.core import audit_writer
        audit_writer.write_event(
            "gmpai_chunked_analysis_run",
            "gmpai_document_validation",
            {
                "run_id": result["run_id"],
                "agent_id": result["agent_id"],
                "agent_version": result["agent_version"],
                "documento": result["documento"],
                "archivo": result["archivo"],
                "document_sha256": result["document_sha256"],
                "total_pages": result["total_pages"],
                "chunks_total": result["chunks_total"],
                "chunks_ok": sum(1 for ce in result["chunk_executions"] if ce["ok"]),
                "contradictions": len(result["contradictions"]),
                "findings_count": len(result["findings"]),
                "model": result["model"],
                "model_digest": result["model_digest"],
            },
        )
    except Exception:
        # La auditoria nunca debe tumbar el analisis; si falla, el resultado
        # completo sigue disponible en el JSON de salida del pipeline.
        pass
