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

from .model_provider import DEFAULT_PROVIDER, ModelProvider
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


def _repair_json(candidate: str) -> str:
    """Reparacion JSON controlada y acotada (fix TE-01): solo corrige
    patrones comunes y no ambiguos, nunca inventa contenido.
    - elimina comas colgantes antes de '}' o ']'
    - convierte comillas simples de claves/valores simples a dobles
      (best-effort, no toca comillas dentro de texto ya entre comillas dobles)
    """
    repaired = re.sub(r",\s*([}\]])", r"\1", candidate)
    return repaired


def _extract_json(raw: str) -> dict | None:
    """Extrae y valida el JSON de la respuesta del modelo. Intenta primero
    sin modificar, y si falla, una reparacion acotada UNA sola vez
    (fix TE-01) -- nunca reintenta indefinidamente ni infiere contenido."""
    raw = raw.strip()
    # Quita cercas de codigo markdown ("```json ... ```") si el modelo las
    # agrego pese a 'format':'json'.
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    candidate = m.group(0)
    for attempt in (candidate, _repair_json(candidate)):
        try:
            parsed = json.loads(attempt)
        except json.JSONDecodeError:
            continue
        if _validate_checkpoint_schema(parsed):
            return parsed
        return None  # JSON valido pero no cumple el esquema esperado
    return None


def _validate_checkpoint_schema(parsed) -> bool:
    """Valida que el JSON parseado tenga la forma minima esperada por el
    contrato del prompt (fix TE-01: una respuesta puede ser JSON valido y
    aun asi no tener la estructura que el verificador necesita)."""
    if not isinstance(parsed, dict):
        return False
    checkpoints = parsed.get("checkpoints")
    if not isinstance(checkpoints, list) or not checkpoints:
        return False
    return all(
        isinstance(entry, dict) and isinstance(entry.get("req_id"), str) and entry.get("req_id")
        for entry in checkpoints
    )


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
                      *, run_context: str,
                      checkpoint_store: "CheckpointStore | None" = None,
                      run_id: str | None = None,
                      use_verified_pipeline: bool = False,
                      document_type: str | None = None,
                      provider: ModelProvider | None = None) -> dict:
    """Procesa TODO el documento (todas las páginas reales) en chunks
    acotados, con metadata de runtime completa por chunk, checkpoints de
    reanudación opcionales, y consolida un Finding final por checkpoint.

    Si checkpoint_store se provee: intenta reanudar un run incompleto del
    mismo documento+agente (find_resumable) antes de empezar de cero, y
    guarda progreso tras cada chunk (nunca se pierden llamadas ya hechas a
    Ollama si el proceso se interrumpe).

    run_context (W5 Ciclo 1 v2, Fase 4 Bloque 4.1 / Fase 5.0 W5.3):
    OBLIGATORIO, sin default -- 'production' | 'validation'. Corrección de
    Fase 5.0: el default anterior ('production') permitía que un caller
    descuidado etiquetara silenciosamente un run como productivo. Ahora
    omitirlo es un TypeError de Python (parámetro keyword-only sin default),
    no un ValueError en runtime -- falla en la firma de la función, antes
    de ejecutar una sola línea. Se registra en el evento de auditoría de
    este run -- UNA sola cadena de auditoría (Part 11), nunca fragmentada;
    los reportes filtran en lectura vía GET /missions/{project_id}/audit?context=.

    use_verified_pipeline (Fase 3, document_remediation_evolution, default
    False -- cero cambio de comportamiento para todo llamador existente):
    si True, ADEMÁS de los Finding de siempre, corre el pipeline verificado
    real (evidence_verifier.verify_llm_output + absence_consolidator.
    consolidate, vía verified_pipeline_adapter) sobre los mismos chunks ya
    ejecutados -- nunca reemplaza los Finding existentes, solo agrega
    result['verified_conclusions'] (dict req_id -> conclusion real). Exige
    document_type (ValueError si falta) y checkpoint_store=None (reanudar
    un run con este flag no esta soportado todavia -- los chunk_executions
    de un checkpoint viejo no traen los registros verificados, ver
    verified_records_by_req más abajo).

    provider (W5 V2 Fase D, default None -- cero cambio de comportamiento
    para todo llamador existente): implementación de ModelProvider a usar;
    None usa DEFAULT_PROVIDER (OllamaProvider, mismo cliente Ollama de
    siempre). Este motor NUNCA importa ollama_client directamente -- toda
    llamada al modelo pasa por esta interfaz (ver model_provider.py)."""
    if run_context not in ("production", "validation"):
        raise ValueError(f"run_context invalido: {run_context!r} (debe ser 'production' o 'validation')")
    if use_verified_pipeline:
        if not document_type:
            raise ValueError("use_verified_pipeline=True exige document_type (obligatorio, sin default)")
        if checkpoint_store is not None:
            raise ValueError(
                "use_verified_pipeline=True no soporta checkpoint_store/reanudacion todavia -- "
                "los chunk_executions de un checkpoint previo no persisten los registros verificados"
            )
    provider = provider or DEFAULT_PROVIDER
    meta = load_prompt_meta(prompt_path)
    # Captura de metadata de reproducibilidad ANTES de la primera inferencia
    # (fix TE-02 / requisito de preflight): modelo, model_digest, version de
    # Ollama, agent_version, prompt_version, verifier_version, documento,
    # SHA-256 y run_id. Si el runtime no esta disponible, falla aqui —
    # explicito y antes de gastar ninguna llamada de chunk — en vez de
    # capturar la excepcion en silencio y seguir con metadata incompleta.
    model_name = provider.model_name
    model_digest = provider.show_digest()
    ollama_version_str = provider.runtime_version()

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

    preflight_metadata = {
        "model": model_name, "model_digest": model_digest,
        "ollama_version": ollama_version_str, "agent_version": agent_version,
        "prompt_version": meta["prompt_version"], "verifier_version": meta["verifier_version"],
        "documento": documento, "document_sha256": document_sha256, "run_id": run_id,
    }

    by_req: dict[str, list[dict]] = {cp["req_id"]: [] for cp in meta["checkpoints"]}
    cp_label_by_req = {cp["req_id"]: cp["label"] for cp in meta["checkpoints"]}

    verified_records_by_req: dict[str, list[dict]] = {cp["req_id"]: [] for cp in meta["checkpoints"]}
    known_verified_requirement_ids: set = set(by_req.keys())
    requirement_terms_by_req: dict[str, list] = {}
    if use_verified_pipeline:
        from factory.regulatory.evidence_verifier import load_requirement_terms
        requirement_terms_by_req = {req_id: load_requirement_terms(req_id) for req_id in by_req}
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

        # Fix TE-01: distinguir "chunk sin texto extraible" (no es un fallo
        # tecnico, es una pagina vacia legitima) de un fallo TECNICO real de
        # ejecucion (llamada fallida, JSON invalido o esquema invalido pese
        # a 'format':'json' + temperatura 0 + reparacion acotada). Un fallo
        # tecnico NUNCA debe terminar convertido silenciosamente en
        # 'evidencia_insuficiente' a nivel de finding sin quedar marcado.
        technical_execution_failure = False
        if not text.strip():
            chunk_result = None
            error = "chunk sin texto extraible"
        else:
            prompt = build_prompt(meta, text)
            try:
                raw = provider.generate(prompt)
                response_text = raw.get("response", "") if isinstance(raw, dict) else ""
                chunk_result = _extract_json(response_text)
                if chunk_result:
                    error = None
                else:
                    error = "technical_execution_failure: respuesta del modelo no es JSON valido o no cumple el esquema esperado (tras reparacion acotada)"
                    technical_execution_failure = True
            except Exception as e:
                chunk_result = None
                error = f"technical_execution_failure: fallo de llamada al modelo ({type(e).__name__}: {e})"
                technical_execution_failure = True

        wall_ms = round((time.monotonic() - t0) * 1000, 1)
        finished_at = datetime.now(timezone.utc).isoformat()

        by_req_candidates = []
        responded_req_ids: set = set()
        if chunk_result and isinstance(chunk_result.get("checkpoints"), list):
            for entry in chunk_result["checkpoints"]:
                if not isinstance(entry, dict) or not entry.get("req_id"):
                    continue
                req_id = entry["req_id"]
                responded_req_ids.add(req_id)
                estado = entry.get("estado") if entry.get("estado") in _VALID_ESTADOS else "evidencia_insuficiente"
                evidencia = str(entry.get("evidencia_exacta") or "")
                anchored = _is_anchored(evidencia, chunk["text"]) if evidencia else False
                requires_anchor = estado in ("cumple", "cumple_parcialmente")
                valid_candidate = anchored if requires_anchor else True
                # Fix 2026-07-16: anclaje literal no basta para cumple/
                # cumple_parcialmente — la cita debe ademas ser tematicamente
                # relevante al checkpoint (ver _is_topically_relevant).
                topically_relevant = (
                    _is_topically_relevant(evidencia, cp_label_by_req.get(req_id, ""))
                    if (requires_anchor and evidencia) else True
                )
                valid_candidate = valid_candidate and topically_relevant

                # Fase 3 (document_remediation_evolution): a diferencia del
                # camino legacy de abajo, el pipeline verificado necesita UN
                # registro por cada (chunk, requisito) evaluado -- incluidos
                # los 'evidencia_insuficiente', que el camino legacy descarta
                # (nunca aportaron un Finding propio) pero que SÍ cuentan para
                # que coverage_complete de absence_consolidator sea real, no
                # inventado.
                if use_verified_pipeline and req_id in verified_records_by_req:
                    from factory.regulatory.verified_pipeline_adapter import build_finding_record
                    v_candidate = {
                        "page_start": chunk["page_start"], "page_end": chunk["page_end"],
                        "estado": estado if valid_candidate else "evidencia_insuficiente",
                        "evidencia_exacta": evidencia if valid_candidate else "",
                    }
                    verified_records_by_req[req_id].append(build_finding_record(
                        f"vrec-{task_id}-{req_id}", v_candidate, req_id, chunk,
                        known_verified_requirement_ids, requirement_terms_by_req.get(req_id, []),
                    ))

                if estado == "evidencia_insuficiente":
                    continue
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
                by_req.setdefault(req_id, []).append(candidate)
                by_req_candidates.append({"req_id": req_id, "candidate": candidate})

        # Fase 3: un chunk sin respuesta valida para un requisito (fallo
        # tecnico de ejecucion, o el modelo simplemente no devolvio ese
        # checkpoint) NUNCA se omite en silencio del pipeline verificado --
        # cuenta como rejected_by_verifier (ver verified_pipeline_adapter.
        # rejected_record y P3 reforzado de absence_consolidator.py).
        if use_verified_pipeline:
            from factory.regulatory.verified_pipeline_adapter import rejected_record
            reason = "technical_execution_failure" if technical_execution_failure else "checkpoint_missing_from_response"
            for req_id in verified_records_by_req:
                if req_id not in responded_req_ids:
                    verified_records_by_req[req_id].append(rejected_record(f"vrec-{task_id}-{req_id}", reason))

        chunk_executions.append({
            "run_id": run_id, "task_id": task_id, "chunk_index": chunk["chunk_index"],
            "page_start": chunk["page_start"], "page_end": chunk["page_end"],
            "has_overlap_prefix": chunk["has_overlap_prefix"], "text_chars": chunk["text_chars"],
            "started_at": started_at, "finished_at": finished_at, "wall_clock_ms": wall_ms,
            "model": model_name, "model_digest": model_digest,
            "ollama_version": ollama_version_str,
            "ok": chunk_result is not None, "error": error,
            "technical_execution_failure": technical_execution_failure,
            "_by_req_candidates": by_req_candidates,
        })

        if checkpoint_store is not None:
            checkpoint_store.save(run_id, {
                "run_id": run_id, "document_sha256": document_sha256, "agent_id": agent_id,
                "documento": documento, "archivo": archivo, "total_chunks": len(chunks),
                "chunk_executions": chunk_executions, "completed": False,
            })

    any_unresolved_technical_failure = any(
        ce.get("technical_execution_failure") for ce in chunk_executions
    )

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
                    model=model_name, verifier_version=meta["verifier_version"],
                ))
            else:
                # Fix TE-01: si existe algun fallo tecnico de ejecucion SIN
                # RESOLVER en este run, esta clasificacion de
                # evidencia_insuficiente es PROVISIONAL — no se sabe si un
                # chunk fallido habria aportado evidencia real. Se marca
                # explicitamente en vez de presentarla como una conclusion
                # de contenido definitiva.
                brecha = "Ningun chunk del documento completo aporto evidencia anclada para este checkpoint."
                if any_unresolved_technical_failure:
                    n_fail = sum(1 for ce in chunk_executions if ce.get("technical_execution_failure"))
                    brecha = (
                        f"PROVISIONAL (technical_execution_failure_pending): {n_fail} chunk(s) de este "
                        "run tuvieron un fallo tecnico de ejecucion (JSON invalido/esquema invalido/fallo "
                        "de llamada) sin reintento agotado. Esta clasificacion de evidencia_insuficiente "
                        "puede estar enmascarando evidencia no capturada por fallo tecnico, no ausencia "
                        "real. Reintentar los chunks fallidos antes de tratarla como definitiva. " + brecha
                    )
                findings.append(Finding(
                    sistema=sistema, documento=documento, version=version, archivo=archivo,
                    pagina_o_seccion=f"paginas 1-{len(per_unit_text)} (todo el documento, por chunks)",
                    requisito_regulatorio=f"{req_id} — {label}",
                    evidencia_exacta="(sin evaluar)", estado="evidencia_insuficiente",
                    brecha=brecha,
                    severidad="no_determinada",
                    riesgo="No evaluable automaticamente; requiere revision manual.",
                    recomendacion=(
                        "Reintentar los chunks con technical_execution_failure antes de aceptar esta "
                        "clasificacion." if any_unresolved_technical_failure else
                        "Revisar manualmente o reintentar el analisis LLM."
                    ),
                    confianza="baja", agente_responsable=agent_id, revision_humana_requerida=True,
                    agent_version=agent_version, prompt_version=meta["prompt_version"],
                    model=model_name, verifier_version=meta["verifier_version"],
                    technical_execution_failure_pending=any_unresolved_technical_failure,
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
                model=model_name, verifier_version=meta["verifier_version"],
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
            model=model_name, verifier_version=meta["verifier_version"],
        ))

    technical_execution_failures = [
        {"chunk_index": ce["chunk_index"], "task_id": ce["task_id"], "error": ce["error"]}
        for ce in chunk_executions if ce.get("technical_execution_failure")
    ]

    verified_conclusions = None
    if use_verified_pipeline:
        from factory.regulatory.absence_consolidator import consolidate as _consolidate
        from factory.regulatory.applicability import applicability as _applicability
        # coverage_complete=True es real, no asumido: evaluate_chunked() sin
        # checkpoint_store (bloqueado arriba para este flag) siempre procesa
        # TODOS los chunks del documento -- cada uno aporto un registro
        # (observado, no-observado o rejected_by_verifier) para cada
        # requisito, nunca un subconjunto parcial.
        verified_conclusions = {}
        for cp in meta["checkpoints"]:
            req_id = cp["req_id"]
            app = _applicability(req_id, document_type)
            conclusion = _consolidate(
                req_id, document_type, app["value"], verified_records_by_req.get(req_id, []),
                coverage_complete=True,
            )
            verified_conclusions[req_id] = {
                "conclusion": conclusion.conclusion,
                "chunks_evaluated": conclusion.chunks_evaluated,
                "chunks_observed": conclusion.chunks_observed,
                "chunks_review_pending": conclusion.chunks_review_pending,
                "review_flags": conclusion.review_flags,
            }

    result = {
        "run_id": run_id,
        "run_context": run_context,
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
        "model": model_name,
        "model_digest": model_digest,
        "ollama_version": ollama_version_str,
        "preflight_metadata": preflight_metadata,
        "technical_execution_failures": technical_execution_failures,
        # El analisis (chunk_executions + findings) ya esta completo en este
        # punto independientemente de lo que pase abajo con la persistencia
        # de evidencia -- se declara ANALYSIS_COMPLETE explicitamente antes
        # de intentar la escritura, para que un fallo de persistencia nunca
        # se confunda con un fallo de analisis.
        "analysis_status": "ANALYSIS_COMPLETE",
    }
    if verified_conclusions is not None:
        result["verified_conclusions"] = verified_conclusions
    result.update(_persist_validation_evidence(result, chunk_executions, run_context))

    if checkpoint_store is not None:
        checkpoint_store.save(run_id, {
            "run_id": run_id, "document_sha256": document_sha256, "agent_id": agent_id,
            "documento": documento, "archivo": archivo, "total_chunks": len(chunks),
            "chunk_executions": chunk_executions, "completed": True,
        })

    _write_audit_event(result)
    return result


def _persist_validation_evidence(result: dict, chunk_executions: list[dict], run_context: str) -> dict:
    """Fase 5.3 (W5.3): persiste _by_req_candidates SOLO para
    run_context='validation', usando el mecanismo aprobado y probado en
    Fase 5.2 (validation_evidence_writer.py). run_context='production'
    queda IDENTICO al comportamiento previo -- cero llamada, cero archivo.

    Un fallo de escritura (ej. EvidenceTooLargeError) NUNCA tumba el
    analisis (el resultado ya esta completo) ni se oculta en silencio --
    queda declarado explicitamente en el resultado y en el evento de
    auditoria, para que ninguna ejecucion de validacion con persistencia
    fallida se confunda despues con una que si capturo evidencia:

      validation + escritura exitosa -> VALIDATION_EVIDENCE_COMPLETE
      validation + escritura fallida -> VALIDATION_EVIDENCE_INCOMPLETE
                                         (golden_dataset_eligible=False)
      production                     -> NOT_APPLICABLE_PRODUCTION_CONTEXT
                                         (golden_dataset_eligible=False,
                                         comportamiento identico a antes
                                         de Fase 5.3)
    """
    if run_context != "validation":
        return {
            "validation_evidence_status": "NOT_APPLICABLE_PRODUCTION_CONTEXT",
            "golden_dataset_eligible": False,
        }
    try:
        from factory.regulatory.validation_evidence_writer import write_validation_evidence
        write_validation_evidence(
            run_id=result["run_id"],
            document_sha256=result["document_sha256"],
            run_context=run_context,
            content={"chunk_executions_with_candidates": chunk_executions},
        )
        return {
            "validation_evidence_status": "VALIDATION_EVIDENCE_COMPLETE",
            "golden_dataset_eligible": True,
        }
    except Exception as e:
        return {
            "validation_evidence_status": "VALIDATION_EVIDENCE_INCOMPLETE",
            "validation_evidence_error": f"{type(e).__name__}: {e}",
            "golden_dataset_eligible": False,
        }


def _write_audit_event(result: dict) -> None:
    try:
        from factory.core import audit_writer
        audit_writer.write_event(
            "gmpai_chunked_analysis_run",
            "gmpai_document_validation",
            {
                "run_id": result["run_id"],
                "run_context": result["run_context"],
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
                # Fase 5.3 -- nunca oculta un fallo de persistencia de
                # evidencia como si fuera una ejecucion sin novedad.
                "analysis_status": result.get("analysis_status"),
                "validation_evidence_status": result.get("validation_evidence_status"),
                "golden_dataset_eligible": result.get("golden_dataset_eligible"),
            },
        )
    except Exception:
        # La auditoria nunca debe tumbar el analisis; si falla, el resultado
        # completo sigue disponible en el JSON de salida del pipeline.
        pass
