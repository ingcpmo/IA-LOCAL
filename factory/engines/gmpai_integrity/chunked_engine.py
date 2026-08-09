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

import gzip
import hashlib
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

# Ratio caracteres/token medido en vivo el 2026-07-28 sobre el prompt real de
# annex11 (15 347 chars -> 3903 tokens de prompt_eval_count reportados por
# Ollama). Se usa SOLO para la guardia de preflight, que necesita una
# estimacion conservadora del prompt antes de hacer ninguna llamada; el
# conteo real lo hace el runtime. Se redondea a la baja (3.6 en vez de 3.95)
# a proposito: sobreestimar el prompt hace la guardia mas estricta, que es el
# lado seguro.
PROMPT_CHARS_PER_TOKEN = 3.6

# Dimensionamiento del presupuesto de SALIDA (medido en vivo el 2026-07-28
# contra qwen2.5:7b-instruct-q4_K_M: 8 criterios + 2 envelopes ~= 1000 tokens
# de salida). Vive aqui, no en ollama_client, porque se deriva del contrato
# del PROMPT -- no del runtime de inferencia.
TOKENS_PER_CRITERION = 130   # ~110 medidos + 18 % de margen
TOKENS_PER_CHECKPOINT = 60   # envelope: estado/evidencia_exacta/brecha/recomendacion
TOKENS_JSON_OVERHEAD = 120   # llaves, "checkpoints", indentacion


def output_token_budget(n_checkpoints: int, n_criteria: int) -> int:
    """Presupuesto de tokens de salida derivado del CONTRATO REAL del prompt
    (numero de checkpoints y de criterios minimos de evidencia del catalogo),
    redondeado hacia arriba a multiplo de 512.

    Existe para que el presupuesto no vuelva a ser una constante que queda
    atras cuando crece el contrato de salida -- que es exactamente lo que
    paso con NUM_PREDICT=1024 al agregarse criterion_assessments en la
    ampliacion D de la Fase F. Si el catalogo gana criterios, este numero
    sube solo; nunca se escribe un presupuesto a mano.

    Valores actuales, calculados con esta funcion y confirmados contra
    corridas reales: eu_annex11_agent (5 cp, 20 crit) -> 3072
    (preflight_metadata de la corrida de FS_v1.2 del 2026-07-28);
    alcoa_plus_agent (9 cp, 25 crit) -> 4096."""
    if n_checkpoints < 0 or n_criteria < 0:
        raise ValueError(f"contrato invalido: {n_checkpoints=} {n_criteria=}")
    raw = (
        TOKENS_JSON_OVERHEAD
        + n_checkpoints * TOKENS_PER_CHECKPOINT
        + n_criteria * TOKENS_PER_CRITERION
    )
    return max(512, -(-raw // 512) * 512)


class TokenBudgetError(RuntimeError):
    """El presupuesto de salida no cabe en la ventana de contexto junto al
    prompt. Se lanza en el PREFLIGHT, antes de la primera inferencia.

    Por que es un error duro y no un aviso: si prompt + num_predict supera
    num_ctx, Ollama no falla -- trunca el PROMPT para que quepa, y lo que se
    pierde es el principio, donde viven common_contract y la lista de req_id.
    El modelo responderia algo bien formado sobre un contrato mutilado. Ese
    fallo silencioso es estrictamente peor que el truncamiento de salida que
    motivo esta guardia (que al menos deja done_reason='length')."""

_MARKER_START = "[DOCUMENTO INICIO]"
_MARKER_END = "[DOCUMENTO FIN]"
_VALID_ESTADOS = {"cumple", "cumple_parcialmente", "no_cumple", "evidencia_insuficiente", "no_aplica"}


def load_prompt_meta(prompt_path: Path) -> dict:
    return _yaml.safe_load(prompt_path.read_text(encoding="utf-8"))


def sanitize_document(text: str) -> str:
    text = text.replace(_MARKER_START, "[documento-inicio]").replace(_MARKER_END, "[documento-fin]")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return text


def _lookup_regulatory_text(req_id: str) -> str | None:
    """W5 V2, Fase E -- intenta obtener texto normativo canónico real del
    Requirement Evidence Pack (Fase C, requirements.yaml) para este req_id.

    Regla dura que esto corrige (REQUIREMENT_EVIDENCE_PACK_SPEC.md, W5 V2):
    'una LLM NUNCA recibe únicamente requirement_id + descripción breve'.
    Antes de esta fase, build_prompt() solo inyectaba req_id + label (el
    antipatrón confirmado del baseline de 121 llamadas -- causa raíz del
    falso positivo ANNEX11_4).

    Retorna None si el req_id no está en el catálogo o si el catálogo no
    valida. Este None YA NO degrada el prompt en silencio: desde el cierre
    del gate 4 (2026-07-28) es `evidence_pack_gate()` quien decide, y un
    req_id sin pack completo queda EXCLUIDO del prompt en vez de viajar con
    solo label. Solo se captura CatalogValidationError/ImportError (fallos
    de catálogo ya cubiertos por sus propios tests dedicados,
    test_requirement_catalog_loader.py) -- cualquier otro error se
    propaga, no se enmascara."""
    try:
        from factory.regulatory.requirement_catalog.requirement_catalog_loader import (
            CatalogValidationError, get_requirement, get_source,
        )
    except ImportError:
        return None
    try:
        entry = get_requirement(req_id)
        source = get_source(entry["source_id"])
    except CatalogValidationError:
        return None
    citation = entry["citation"]
    return (
        f'Texto normativo canonico (fuente: {source["official_source_description"]}, '
        f'{citation["section_page_paragraph"]}): "{citation["citation_text"]}"'
    )


def _lookup_evidence_min_criteria(req_id: str) -> list[str] | None:
    """W5 V2, Fase F (ampliación D) -- criterios mínimos de evidencia
    reales del catálogo (Fase C, human_drafted_provisional) para este
    req_id, en el ORDEN real del catálogo (el índice 1-based de esta lista
    es el mismo `criterion_index` que criterion_assessments debe usar --
    ver build_prompt() y semantic_evidence_verification.verify_sufficiency()).
    Mismo contrato de fallback silencioso que _lookup_regulatory_text():
    None si el req_id no está en el catálogo o no tiene
    evidence_min_criteria todavía -- nunca rompe la construcción del
    prompt por esto."""
    try:
        from factory.regulatory.requirement_catalog.requirement_catalog_loader import (
            CatalogValidationError, get_requirement,
        )
    except ImportError:
        return None
    try:
        entry = get_requirement(req_id)
    except CatalogValidationError:
        return None
    criteria = entry.get("evidence_min_criteria")
    return list(criteria) if criteria else None


# ---------------------------------------------------------------------------
# GATE 4 (ACCEPTANCE_AND_VALIDATION_GATES.md): "100% prompts con Evidence Pack
# completo -- validacion del pack ANTES de invocar la LLM. FAIL: pack
# incompleto. Efecto: BLOQUEA LA LLAMADA, NO LA CORRIDA."
#
# Defecto que esto cierra (auditoria del 2026-07-28, informe de validacion
# corregido §5): _lookup_regulatory_text() y _lookup_evidence_min_criteria()
# devolvian None en silencio y build_prompt() seguia adelante con solo
# req_id + label -- es decir, FAIL-OPEN, exactamente el antipatron del
# baseline de 121 llamadas que la Fase E existe para erradicar (§3.1.5-6 del
# plan: "una LLM NUNCA recibe unicamente requirement_id + descripcion breve").
# El gate declaraba una cosa y el codigo hacia la contraria.
#
# Campos exigidos: son los que el prompt REALMENTE inyecta. No se exige aqui
# `ready_for_regulatory_use` ni `runtime_eligibility=ENABLED_FULL`: esos
# gobiernan la LIBERACION (FORMAL_RELEASE_GATE), no la completitud del pack
# para construir el prompt. Confundirlos bloquearia hoy los 19 requisitos y
# dejaria el motor sin poder evaluar nada en contexto de validacion.
_EVIDENCE_PACK_REQUIRED = (
    "citation.citation_text",
    "citation.section_page_paragraph",
    "source_id->registry",
    "evidence_min_criteria",
)


@dataclass(frozen=True)
class EvidencePackVerdict:
    """Resultado de la validacion del Evidence Pack de UN req_id."""
    req_id: str
    complete: bool
    missing: tuple[str, ...]
    detail: str


def validate_evidence_pack(req_id: str) -> EvidencePackVerdict:
    """Gate 4, fail-CLOSED: un req_id solo llega a la LLM si su Evidence Pack
    trae todo lo que el prompt inyecta. Cualquier ausencia -> pack incompleto.

    Nunca lanza: devuelve un veredicto. Un catalogo ausente o invalido
    (ImportError / CatalogValidationError) es pack incompleto para TODOS los
    req_id -- que es el lado seguro: sin catalogo no hay texto normativo que
    inyectar, y evaluar sin el es justo lo que produjo el falso positivo de
    ANNEX11_4."""
    try:
        from factory.regulatory.requirement_catalog.requirement_catalog_loader import (
            CatalogValidationError, get_requirement, get_source,
        )
    except ImportError as e:
        return EvidencePackVerdict(
            req_id, False, _EVIDENCE_PACK_REQUIRED,
            f"catalogo de requisitos no disponible ({type(e).__name__}: {e})",
        )
    try:
        entry = get_requirement(req_id)
    except CatalogValidationError as e:
        return EvidencePackVerdict(
            req_id, False, _EVIDENCE_PACK_REQUIRED,
            f"sin entrada valida en el catalogo ({e})",
        )

    missing: list[str] = []
    citation = entry.get("citation") or {}
    if not str(citation.get("citation_text") or "").strip():
        missing.append("citation.citation_text")
    if not str(citation.get("section_page_paragraph") or "").strip():
        missing.append("citation.section_page_paragraph")
    try:
        source = get_source(entry["source_id"])
        if not str(source.get("official_source_description") or "").strip():
            missing.append("source_id->registry")
    except (CatalogValidationError, KeyError):
        missing.append("source_id->registry")
    if not (entry.get("evidence_min_criteria") or []):
        missing.append("evidence_min_criteria")

    if missing:
        return EvidencePackVerdict(
            req_id, False, tuple(missing),
            "Evidence Pack incompleto: faltan " + ", ".join(missing),
        )
    return EvidencePackVerdict(req_id, True, (), "Evidence Pack completo")


def evidence_pack_gate(meta: dict) -> tuple[list[dict], list[EvidencePackVerdict]]:
    """Particiona los checkpoints del prompt en (admitidos, bloqueados).

    Los bloqueados NO se envian al modelo. La corrida continua con los
    admitidos -- el gate bloquea la llamada, nunca la corrida."""
    admitted, blocked = [], []
    for cp in meta["checkpoints"]:
        verdict = validate_evidence_pack(cp["req_id"])
        if verdict.complete:
            admitted.append(cp)
        else:
            blocked.append(verdict)
    return admitted, blocked


def build_prompt(meta: dict, doc_text: str, max_chars: int = CHUNK_MAX_CHARS) -> str:
    """Construye el prompt SOLO con los checkpoints cuyo Evidence Pack esta
    completo (gate 4). Un checkpoint sin pack no aparece en el prompt: no se
    le pregunta al modelo por un requisito que no le podemos describir."""
    doc = sanitize_document(doc_text)
    truncated = len(doc) > max_chars
    if truncated:
        doc = doc[:max_chars]
    admitted, _blocked = evidence_pack_gate(meta)
    lines = []
    for c in admitted:
        lines.append(f"  - {c['req_id']}: {c['label']}")
        reg_text = _lookup_regulatory_text(c["req_id"])
        if reg_text:
            lines.append(f"    {reg_text}")
        criteria = _lookup_evidence_min_criteria(c["req_id"])
        if criteria:
            lines.append(
                "    Criterios minimos de evidencia (usar el indice EXACTO en criterion_index, "
                "el texto EXACTO en criterion_text):"
            )
            for i, crit in enumerate(criteria, start=1):
                lines.append(f"      {i}. {crit}")
    checkpoints_desc = "\n".join(lines)
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


# Causas EXPLICITAS de fallo de una respuesta del modelo (2026-07-28).
# Antes las cuatro se colapsaban en un unico mensaje generico -- ver
# W5v2_POSTMORTEM_TRUNCAMIENTO_NUM_PREDICT.md defecto D-1: nueve chunks se
# marcaron como "el modelo no devolvio JSON valido" cuando en realidad la
# respuesta se habia truncado por presupuesto de tokens, que es un error de
# CONFIGURACION del operador, no un fallo del modelo.
FAILURE_OUTPUT_TRUNCATED = "output_truncated"
FAILURE_NO_JSON_OBJECT = "no_json_object"
FAILURE_JSON_PARSE = "json_parse_failed"
FAILURE_SCHEMA_VALIDATION = "schema_validation_failed"

_FAILURE_DETAIL = {
    FAILURE_OUTPUT_TRUNCATED: (
        "technical_execution_failure: la generacion se TRUNCO por presupuesto de tokens "
        "(done_reason='length'). NO es un fallo del modelo: el presupuesto de salida es "
        "insuficiente para el contrato del prompt. Subir num_predict "
        "(ollama_client.output_token_budget) -- reintentar sin cambiarlo dara el mismo resultado."
    ),
    FAILURE_NO_JSON_OBJECT: (
        "technical_execution_failure: la respuesta del modelo no contiene ningun objeto JSON"
    ),
    FAILURE_JSON_PARSE: (
        "technical_execution_failure: la respuesta del modelo no es JSON valido "
        "(tras reparacion acotada)"
    ),
    FAILURE_SCHEMA_VALIDATION: (
        "technical_execution_failure: la respuesta del modelo es JSON valido pero no cumple "
        "checkpoint_llm_response_v1"
    ),
}

# Extracto inline en el checkpoint (para que el JSON del checkpoint siga
# siendo manejable de leer/diffear a mano). NUNCA es la unica copia cuando
# hay checkpoint_store: la respuesta completa se persiste aparte via
# CheckpointStore.save_raw_response (gzip, referenciada por
# raw_response_full_path/raw_response_full_sha256) -- ver
# W5V2_REMEDIACION_RECALL_MODELO.md 1.2. Antes de esa correccion (2026-08-08)
# este cap era la unica copia y una llamada real del Piloto 1 quedo
# inauditable mas alla de los primeros 8192 caracteres.
_RAW_PERSIST_MAX_CHARS = 8192


def _count_contract_criteria(meta: dict) -> int:
    """Numero total de criterios minimos de evidencia que el prompt pedira
    evaluar, leido del MISMO catalogo que build_prompt() usa para
    construirlo. Es la unica fuente del dimensionamiento -- si el catalogo
    gana criterios, el presupuesto sube solo.

    Cuenta los checkpoints ADMITIDOS por el gate 4, que son los unicos que
    build_prompt() escribe: contar los bloqueados dimensionaria el
    presupuesto para un contrato que nunca se envia."""
    admitted, _blocked = evidence_pack_gate(meta)
    return sum(
        len(_lookup_evidence_min_criteria(cp["req_id"]) or [])
        for cp in admitted
    )


def _assert_token_budget_fits(chunks: list[dict], meta: dict, num_predict: int,
                              num_ctx: int | None) -> dict:
    """Verifica que el PEOR chunk (el de prompt mas largo) quepa junto al
    presupuesto de salida. Lanza TokenBudgetError antes de gastar una sola
    llamada. Devuelve el detalle para preflight_metadata.

    num_ctx None = el provider no declara ventana de contexto. Entonces NO
    se aplica la guardia: no se puede verificar un limite que no se conoce, y
    suponer uno bloquearia corridas legitimas (p. ej. providers de test) por
    un numero inventado. Queda declarado en `context_window_declared`. La
    guardia sigue plenamente activa donde importa: OllamaProvider si declara
    su ventana."""
    worst_chars, worst_index = 0, -1
    for chunk in chunks:
        prompt_chars = len(build_prompt(meta, sanitize_document(chunk["text"])))
        if prompt_chars > worst_chars:
            worst_chars, worst_index = prompt_chars, chunk["chunk_index"]

    worst_prompt_tokens = int(worst_chars / PROMPT_CHARS_PER_TOKEN) + 1
    required = worst_prompt_tokens + num_predict
    detail = {
        "num_ctx": num_ctx,
        "context_window_declared": num_ctx is not None,
        "num_predict": num_predict,
        "worst_chunk_index": worst_index,
        "worst_prompt_chars": worst_chars,
        "worst_prompt_tokens_estimated": worst_prompt_tokens,
        "required_context_tokens": required,
        "headroom_tokens": None if num_ctx is None else num_ctx - required,
    }
    if num_ctx is None:
        return detail
    if required > num_ctx:
        raise TokenBudgetError(
            f"el presupuesto no cabe en la ventana de contexto: prompt del chunk "
            f"{worst_index} ~{worst_prompt_tokens} tokens + num_predict {num_predict} "
            f"= {required} > num_ctx {num_ctx}. Ollama truncaria el PROMPT en silencio. "
            f"Subir FACTORY_OLLAMA_NUM_CTX a >= {required}, o reducir el contrato del prompt."
        )
    return detail


def _provider_honors_token_budget(provider: ModelProvider) -> bool:
    """True si generate() del provider acepta el keyword num_predict. Se
    comprueba una sola vez, con inspect -- nunca con un try/except TypeError,
    que enmascararia un TypeError real lanzado DENTRO del provider."""
    import inspect
    try:
        params = inspect.signature(provider.generate).parameters
    except (TypeError, ValueError):
        return False
    return "num_predict" in params or any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()
    )


def classify_model_response(raw: dict | None) -> tuple[dict | None, str | None, str]:
    """Clasifica la respuesta CRUDA del provider en (parsed, failure_reason,
    raw_text). `failure_reason` es None si la respuesta es utilizable, o una
    de las cuatro causas explicitas de arriba.

    El truncamiento se decide con `done_reason`, que ya viene en la propia
    respuesta de Ollama -- no es heuristica. Se comprueba ANTES de intentar
    parsear porque una respuesta truncada casi siempre falla tambien el
    parseo, y reportar 'json_parse_failed' escondería la causa real."""
    raw_text = raw.get("response", "") if isinstance(raw, dict) else ""
    done_reason = raw.get("done_reason") if isinstance(raw, dict) else None

    if done_reason == "length":
        return None, FAILURE_OUTPUT_TRUNCATED, raw_text

    stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text.strip())
    if not re.search(r"\{.*\}", stripped, re.DOTALL):
        return None, FAILURE_NO_JSON_OBJECT, raw_text

    parsed = _extract_json(raw_text)
    if parsed is not None:
        return parsed, None, raw_text

    # _extract_json ya no distingue entre "no parsea" y "parsea pero viola el
    # esquema"; se re-deriva aqui para dar la causa exacta.
    candidate = re.search(r"\{.*\}", stripped, re.DOTALL).group(0)
    for attempt in (candidate, _repair_json(candidate)):
        try:
            json.loads(attempt)
        except json.JSONDecodeError:
            continue
        return None, FAILURE_SCHEMA_VALIDATION, raw_text
    return None, FAILURE_JSON_PARSE, raw_text


def _validate_checkpoint_schema(parsed) -> bool:
    """Valida que el JSON parseado tenga la forma minima esperada por el
    contrato del prompt (fix TE-01: una respuesta puede ser JSON valido y
    aun asi no tener la estructura que el verificador necesita).

    W5 V2 Fase F (ampliacion D, 2026-07-25): ADEMAS del chequeo estructural
    original (checkpoints no vacio, req_id presente), valida CADA
    checkpoint completo contra el schema formal checkpoint_llm_response_v1
    (estado/evidencia_exacta/brecha/recomendacion/criterion_assessments) --
    una violacion de schema en CUALQUIER checkpoint invalida TODO el
    chunk_result (mismo criterio fail-closed que ya aplicaba antes: no se
    rescatan checkpoints parcialmente validos de una respuesta mal
    formada)."""
    if not isinstance(parsed, dict):
        return False
    checkpoints = parsed.get("checkpoints")
    if not isinstance(checkpoints, list) or not checkpoints:
        return False
    if not all(
        isinstance(entry, dict) and isinstance(entry.get("req_id"), str) and entry.get("req_id")
        for entry in checkpoints
    ):
        return False

    from factory.regulatory.schema_loader import validate_against
    for entry in checkpoints:
        ok, _errors = validate_against(entry, "checkpoint_llm_response_v1")
        if not ok:
            return False
    return True


_POSITIVE_ESTADOS = {"cumple", "cumple_parcialmente"}
# Valores de substantive_support. UNKNOWN no es un estado alcanzable por el
# motor (las 4 ramas de consolidacion lo fijan siempre): existe para que un
# Finding sin veredicto -- historico o construido por otro codigo -- se
# CUENTE como desconocido en vez de colarse como NOT_APPLICABLE.
SUBSTANTIVE_SUPPORT_VALUES = ("SUPPORTED", "NOT_SUPPORTED", "NOT_APPLICABLE", "UNKNOWN")


def compute_substantive_support(estado, substantive_evidence_accepted) -> str:
    """W5 V2 Fase F (cableado de D a decision, 2026-07-25). Veredicto
    determinista: un estado positivo (cumple/cumple_parcialmente) solo se
    presenta como sustentado si la evidencia sustantiva fue aceptada
    (A^B^C^D==MET, ver semantic_evidence_verification.ABCDResult.
    substantive_evidence_accepted). Fail-closed: None/False para un positivo
    -> NOT_SUPPORTED (solo True explicito -> SUPPORTED). Un estado no positivo
    (no_cumple/evidencia_insuficiente/no_aplica) no es sujeto de sustento
    sustantivo -> NOT_APPLICABLE."""
    if estado not in _POSITIVE_ESTADOS:
        return "NOT_APPLICABLE"
    return "SUPPORTED" if substantive_evidence_accepted is True else "NOT_SUPPORTED"


# Nombre publico desde la deuda I-1 (2026-07-27): finding_substantive_adapter
# necesita ESTA funcion -- no una copia -- para que siga habiendo una sola
# autoridad del veredicto sustantivo. Alias historico conservado.
_compute_substantive_support = compute_substantive_support


def _positive_conclusion_eligibility(req_id: str) -> str:
    """Gobernanza de fuente por requisito (W5 V2 §10). Lee el campo real del
    Requirement Evidence Pack -- hasta 2026-07-27 este campo existia en el
    catalogo y en el schema para los 19 requisitos, y NINGUN codigo lo leia.

    Fail-closed: un requisito sin entrada en el catalogo no tiene fuente
    gobernada, asi que no puede sostener ninguna conclusion -> BLOCKED."""
    from factory.regulatory.requirement_catalog.requirement_catalog_loader import (
        CatalogValidationError, get_requirement,
    )
    try:
        entry = get_requirement(req_id)
    except CatalogValidationError:
        return "BLOCKED"
    return entry.get("positive_conclusion_eligibility") or "BLOCKED"


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
    bloquea (True).

    Fix R1.6 (2026-08-09, docs_plan/R1_6_VALIDADOR_RELEVANCIA_IDIOMA.md):
    algunos labels (familia ALCOA, alcoa_prompts.yaml) siguen el patron
    bilingue "Termino en ingles — glosa en espanol" (ej. "Contemporaneous
    — registrado en el momento"). El codigo anterior descartaba la mitad
    ANTERIOR al guion largo (`label.split("—", 1)[-1]`) y se quedaba solo
    con la glosa en espanol -- para un documento fuente en ingles (caso
    real RW-0005/Rockwell), ninguna palabra espanola puede aparecer nunca
    en una cita literal en ingles, asi que el termino en ingles ya
    presente en el propio label (contenido gobernado, no una fuente
    externa nueva) se descartaba exactamente cuando mas hacia falta. Se
    usan AMBAS mitades del label ahora -- nunca se resta vocabulario,
    solo se deja de tirar a la basura la parte que ya estaba ahi.

    Nota de alcance, verificada, no maquillada (ver R1_6, seccion
    'alcance del defecto'): esta correccion resuelve el caso general
    donde el termino de anclaje SI aparece literal en el label bilingue
    (p.ej. futuros documentos ALCOA en ingles que reutilicen la palabra
    "Contemporaneous"/"Attributable"/etc. del propio label). NO resuelve
    el caso P5 especifico (evidencia parafraseada por el modelo que no
    repite NINGUNA palabra clave gobernada, ni en ingles ni en espanol) --
    ese es un defecto de diseno mas profundo (esta heuristica de
    coincidencia literal es demasiado estricta para 'cumple_parcialmente'
    inferido/parafraseado) y su correccion requiere una decision separada
    de Cesar, no autorizada en este alcance (ver R1_6_VALIDADOR_
    RELEVANCIA_IDIOMA.md seccion 3: cualquier fuente de comparacion nueva
    -- p.ej. requirement_terms.yaml como aceptacion alternativa -- se
    evaluo y se descarto: rompe test_topically_irrelevant_citation_is_
    rejected, un caso real y monolingue de cita anclada pero fuera de
    tema, que debe seguir rechazado)."""
    if not label:
        return True
    parts = label.split("—") if "—" in label else [label]
    desc = " ".join(parts)
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


def build_run_fingerprint(meta: dict, *, model_digest: str, document_sha256: str, agent_version: str,
                          use_verified_pipeline: bool,
                          evaluation_profile: str = "BASELINE",
                          target_requirement_ids: tuple[str, ...] | None = None) -> dict:
    """W5 V2 Fase F (invalidacion de checkpoint, 2026-07-25). Combina todo
    lo que, si cambia, vuelve un checkpoint viejo no confiable para
    reanudar: contrato del prompt (prompt_version/schema_version), modelo,
    documento, agente y catalogo de requisitos (version + sha256 del
    archivo completo). Un mismatch en CUALQUIER componente impide el
    resume (ver CheckpointStore.find_resumable) -- fuerza una corrida
    nueva en vez de mezclar chunk_executions de contratos distintos.

    use_verified_pipeline (2026-07-27, reanudacion verificada): forma parte
    del fingerprint porque un checkpoint escrito SIN el pipeline verificado
    no trae los registros verificados de sus chunks; reanudarlo con el flag
    activo produciria una cobertura parcial presentada como completa. Es
    keyword-only y SIN default a proposito: omitirlo es un TypeError, no un
    fingerprint silenciosamente incompleto.

    evaluation_profile/target_requirement_ids (R1.5, 2026-08-09, defaults
    BASELINE/None -- cero cambio de comportamiento para todo llamador
    existente): un checkpoint de perfil H2H4 (1 requirement_id/llamada,
    ver evaluate_chunked()) NUNCA debe poder reanudarse como si fuera un
    checkpoint BASELINE del mismo agente/documento -- el prompt real que
    vio el modelo es distinto (subconjunto de checkpoints), aunque
    prompt_version/schema_version del YAML no cambien (el filtrado es en
    tiempo de ejecucion, no en el archivo gobernado). Sin esto, resumir un
    run BASELINE con perfil H2H4 (o viceversa) mezclaria chunk_executions
    de dos contratos de prompt distintos -- el mismo defecto que este
    fingerprint ya existe para impedir en las demas dimensiones."""
    from factory.regulatory.requirement_catalog.requirement_catalog_loader import catalog_fingerprint
    cat = catalog_fingerprint()
    return {
        "prompt_version": meta["prompt_version"],
        "schema_version": meta.get("schema_version"),
        "model_digest": model_digest,
        "document_sha256": document_sha256,
        "agent_version": agent_version,
        "catalog_version": cat["catalog_version"],
        "catalog_sha256": cat["catalog_sha256"],
        "use_verified_pipeline": bool(use_verified_pipeline),
        "evaluation_profile": evaluation_profile,
        "target_requirement_ids": sorted(target_requirement_ids) if target_requirement_ids else None,
    }


def verified_records_coverage_gap(state: dict, req_ids: list[str]) -> dict | None:
    """Reanudacion verificada (2026-07-27): decide si un checkpoint puede
    reanudarse con use_verified_pipeline=True.

    El fingerprint ya impide reanudar un checkpoint escrito con otro valor
    del flag, pero eso solo prueba la INTENCION del run que lo escribio, no
    que los registros verificados esten realmente ahi y completos. Esta
    funcion comprueba el hecho: cada chunk ya ejecutado tuvo que aportar al
    menos un registro verificado por CADA requisito del prompt (observado,
    no-observado o rejected_by_verifier -- el motor nunca omite ninguno).

    Importa porque `consolidate(..., coverage_complete=True)` de mas abajo
    afirma que la cobertura es total: si un resume arrancara con registros
    faltantes, esa afirmacion seria falsa y la conclusion se decidiria sobre
    una fraccion del documento sin que nada lo delatara.

    Retorna None si el checkpoint es apto, o el detalle del descarte."""
    stored = state.get("verified_records_by_req")
    chunks_completed = len(state.get("chunk_executions") or [])
    if not isinstance(stored, dict):
        return {
            "discarded_run_id": state.get("run_id"),
            "reason": "checkpoint_without_verified_records",
            "detail": "checkpoint anterior al soporte de reanudacion verificada",
        }
    below = {
        req_id: len(stored.get(req_id) or [])
        for req_id in req_ids
        if len(stored.get(req_id) or []) < chunks_completed
    }
    if below:
        return {
            "discarded_run_id": state.get("run_id"),
            "reason": "checkpoint_verified_records_incomplete",
            "detail": {"chunks_completed": chunks_completed, "records_below_coverage": below},
        }
    return None


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

    def save_raw_response(self, run_id: str, task_id: str, raw_response_text: str) -> dict:
        """Persiste la respuesta CRUDA completa del modelo (sin el recorte de
        `_RAW_PERSIST_MAX_CHARS` que vive en el checkpoint) en un archivo
        aparte, gzip, uno por llamada. Existe porque un run regulatorio debe
        poder auditar el razonamiento completo del modelo post-hoc -- el
        checkpoint solo conserva un extracto para que el JSON del checkpoint
        siga siendo manejable, nunca para ocultar lo que el modelo dijo (ver
        W5V2_REMEDIACION_RECALL_MODELO.md 1.2). Devuelve la ruta relativa al
        checkpoint_dir y el SHA-256 del texto completo (sin comprimir), para
        que el checkpoint pueda referenciarlo y para poder verificar
        integridad al leerlo de vuelta."""
        raw_dir = self.checkpoint_dir / "raw_responses" / run_id
        raw_dir.mkdir(parents=True, exist_ok=True)
        path = raw_dir / f"{task_id}.txt.gz"
        payload = raw_response_text.encode("utf-8")
        with gzip.open(path, "wb") as f:
            f.write(payload)
        return {
            "path": str(path.relative_to(self.checkpoint_dir)),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "chars": len(raw_response_text),
        }

    def load_raw_response(self, relative_path: str) -> str:
        """Contraparte de save_raw_response: lee y descomprime el raw
        completo a partir de la ruta relativa guardada en el checkpoint."""
        path = self.checkpoint_dir / relative_path
        with gzip.open(path, "rb") as f:
            return f.read().decode("utf-8")

    def find_resumable(self, document_sha256: str, agent_id: str, expected_fingerprint: dict,
                       *, include_completed_with_failures: bool = False) -> tuple[dict | None, dict | None]:
        """Busca un checkpoint incompleto previo para el mismo documento
        (por SHA-256) y agente, para reanudar en vez de reiniciar.

        include_completed_with_failures (2026-07-28, default False = cero
        cambio de comportamiento): permite ademas reabrir un run COMPLETADO
        que dejo chunks con technical_execution_failure. Sin esto, el
        reintento dirigido solo servia para runs interrumpidos, y un run que
        termina con fallos tecnicos —el caso normal desde que existe la
        marca PROVISIONAL— quedaba irrecuperable.

        Un run completado SIN fallos tecnicos nunca se reabre: solo se
        permite volver sobre lo que fallo tecnicamente, jamas re-analizar
        contenido ya evaluado.

        W5 V2 Fase F: SOLO se considera resumable si su fingerprint
        (prompt_version/schema_version/model_digest/document_sha256/
        agent_version/catalog_version/catalog_sha256) coincide EXACTO con
        expected_fingerprint. Un checkpoint sin fingerprint (formato
        anterior a esta fase) o con cualquier componente distinto NUNCA se
        resume -- se descarta explicitamente (nunca en silencio: retorna
        el detalle del mismatch para que el llamador lo registre en
        preflight_metadata) y la corrida siguiente empieza de cero.

        Retorna (resumable_state_or_None, mismatch_detail_or_None)."""
        for f in self.checkpoint_dir.glob("*.checkpoint.json"):
            try:
                state = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if state.get("document_sha256") != document_sha256 or state.get("agent_id") != agent_id:
                continue
            reopenable = include_completed_with_failures and any(
                execution.get("technical_execution_failure")
                for execution in state.get("chunk_executions", [])
            )
            if not state.get("completed", False) or reopenable:
                if state.get("fingerprint") == expected_fingerprint:
                    return state, None
                return None, {
                    "discarded_run_id": state.get("run_id"),
                    "old_fingerprint": state.get("fingerprint"),
                    "expected_fingerprint": expected_fingerprint,
                    "reason": "checkpoint_fingerprint_mismatch",
                }
        return None, None


def evaluate_chunked(prompt_path: Path, agent_id: str, agent_version: str,
                      per_unit_text: list[str], sistema: str, documento: str,
                      version: str, archivo: str, document_sha256: str,
                      *, run_context: str,
                      checkpoint_store: "CheckpointStore | None" = None,
                      run_id: str | None = None,
                      use_verified_pipeline: bool = False,
                      document_type: str | None = None,
                      retry_technical_failures: bool = False,
                      provider: ModelProvider | None = None,
                      evaluation_profile: str = "BASELINE",
                      target_requirement_ids: "list[str] | tuple[str, ...] | None" = None) -> dict:
    """Procesa TODO el documento (todas las páginas reales) en chunks
    acotados, con metadata de runtime completa por chunk, checkpoints de
    reanudación opcionales, y consolida un Finding final por checkpoint.

    Si checkpoint_store se provee: intenta reanudar un run incompleto del
    mismo documento+agente (find_resumable) antes de empezar de cero, y
    guarda progreso tras cada chunk (nunca se pierden llamadas ya hechas a
    Ollama si el proceso se interrumpe).

    run_context (W5 Ciclo 1 v2, Fase 4 Bloque 4.1 / Fase 5.0 W5.3):
    OBLIGATORIO, sin default -- 'production' | 'validation' | 'pilot'.
    Corrección de Fase 5.0: el default anterior ('production') permitía que
    un caller descuidado etiquetara silenciosamente un run como productivo.
    Ahora omitirlo es un TypeError de Python (parámetro keyword-only sin
    default), no un ValueError en runtime -- falla en la firma de la
    función, antes de ejecutar una sola línea. Se registra en el evento de
    auditoría de este run -- UNA sola cadena de auditoría (Part 11), nunca
    fragmentada; los reportes filtran en lectura vía
    GET /missions/{project_id}/audit?context=.

    'pilot' (W5 V2 PILOTO_DIAGNOSTICO_PRECORPUS, 2026-08-08): mismo motor
    real, para un run de diagnóstico aislado que NUNCA cuenta para D4-A ni
    para CORPUS_AUTHORIZATION -- esa exclusión se garantiza fuera de esta
    función (checkpoint_dir/manifest_dir propios y la familia de decisión
    separada PILOT_EXECUTION en el caller, ver corpus_runner.py), nunca
    filtrando aquí por valor de string. Se comporta como 'production' en
    todo lo demás (persistencia de evidencia de validación: NOT_APPLICABLE,
    igual que 'production' -- ver _persist_validation_evidence).

    use_verified_pipeline (Fase 3, document_remediation_evolution, default
    False -- cero cambio de comportamiento para todo llamador existente):
    si True, ADEMÁS de los Finding de siempre, corre el pipeline verificado
    real (evidence_verifier.verify_llm_output + absence_consolidator.
    consolidate, vía verified_pipeline_adapter) sobre los mismos chunks ya
    ejecutados -- nunca reemplaza los Finding existentes, solo agrega
    result['verified_conclusions'] (dict req_id -> conclusion real). Exige
    document_type (ValueError si falta).

    Reanudacion con use_verified_pipeline=True (2026-07-27): soportada. El
    checkpoint persiste tambien verified_records_by_req, y reanudar exige
    (a) fingerprint identico -- que ahora incluye el propio flag -- y (b)
    cobertura verificada completa de los chunks ya ejecutados
    (verified_records_coverage_gap). Si alguna falla, no se reanuda nada y
    el descarte queda en preflight_metadata. Antes de esta fecha la
    combinacion era un ValueError.

    evaluation_profile/target_requirement_ids (R1.5, 2026-08-09, defaults
    'BASELINE'/None -- cero cambio de comportamiento para todo llamador
    existente): BASELINE es el contrato de siempre, sin tocar -- todos los
    checkpoints admitidos del agente evaluados en UNA sola llamada por
    chunk (config que midio 0/7 de recall en el fixture set, ver
    docs_plan/W5V2_RECALL_EXPERIMENTS_RESULTADOS.md).

    H2H4 productiza la configuracion H2 (desempaquetado: UN solo
    requirement_id por llamada) que midio 2/7 -- la unica que supero el
    baseline en cualquier experimento -- llevandola del script de
    diagnostico aislado (h2_experiment.py/h4_experiment.py, scratchpad,
    nunca versionados) al motor real. Exige target_requirement_ids no
    vacio: filtra meta['checkpoints'] a ESOS req_id ANTES de
    evidence_pack_gate/build_prompt/output_token_budget/
    build_run_fingerprint -- ningun otro punto de la funcion cambia, asi
    que evidence_pack_gate, build_prompt (el mismo common_contract/schema
    GOBERNADO, sin editar), _extract_json, _validate_checkpoint_schema y
    la validacion A real (evidence_verifier via verified_pipeline_adapter,
    cuando use_verified_pipeline=True) se reutilizan sin cambios -- es
    literalmente el mismo prompt que vería un checkpoint BASELINE, con
    menos checkpoints en la lista.

    Nota honesta de alcance (no reproduce H4 al pie de la letra): la
    minimizacion del SCHEMA de salida (H4 -- eliminar criterion_text/
    evidence_location/justification/limitations del JSON pedido) vive en
    el common_contract GOBERNADO de cada prompt YAML
    (factory/engines/gmpai_integrity/prompts/*.yaml), no en esta funcion
    -- cambiarlo es un cambio de CONTENIDO gobernado (prompt_version
    nuevo, aprobacion de Cesar), fuera de alcance de esta corrida de
    codigo minimo. El filtrado a 1 requirement_id YA reduce
    output_token_budget()/num_predict automaticamente (escala con
    n_checkpoints Y n_criteria, ambos ya filtrados a 1 requirement), asi
    que se obtiene la mayor parte de la ganancia de velocidad de H4 sin
    tocar el schema -- pero la ganancia de RECALL medida (2/7, identica
    con o sin H4 segun W5V2_RECALL_EXPERIMENTS_RESULTADOS.md: 'mismos dos
    casos que H2: P1 y P5 -- exactamente igual') es enteramente atribuible
    a H2 (el desempaquetado), no al schema minimo. Por eso este perfil
    reproduce fielmente el recall medido aunque no reproduzca el schema
    minimo de H4 al pie de la letra.

    retry_technical_failures (2026-07-28, default False -- cero cambio de
    comportamiento para todo llamador existente): al reanudar, reejecuta los
    chunks que quedaron con technical_execution_failure en vez de saltarlos.
    Sin esto, un fallo tecnico es PERMANENTE (el chunk ya figura en
    chunk_executions y start_index lo salta), asi que un error de
    configuracion como el de NUM_PREDICT obliga a descartar la corrida
    entera -- ver W5v2_POSTMORTEM_TRUNCAMIENTO_NUM_PREDICT.md.

    El intento anterior NUNCA se borra: se conserva en
    chunk_execution['superseded_attempts'], porque un run regulatorio debe
    poder demostrar que hubo un fallo y que se resolvio, no aparentar que
    nunca ocurrio. Los verified_records del intento viejo se purgan por
    record_id para no duplicar cobertura.

    provider (W5 V2 Fase D, default None -- cero cambio de comportamiento
    para todo llamador existente): implementación de ModelProvider a usar;
    None usa DEFAULT_PROVIDER (OllamaProvider, mismo cliente Ollama de
    siempre). Este motor NUNCA importa ollama_client directamente -- toda
    llamada al modelo pasa por esta interfaz (ver model_provider.py)."""
    if run_context not in ("production", "validation", "pilot"):
        raise ValueError(
            f"run_context invalido: {run_context!r} (debe ser 'production', 'validation' o 'pilot')")
    if use_verified_pipeline and not document_type:
        raise ValueError("use_verified_pipeline=True exige document_type (obligatorio, sin default)")
    if evaluation_profile not in ("BASELINE", "H2H4"):
        raise ValueError(
            f"evaluation_profile invalido: {evaluation_profile!r} (debe ser 'BASELINE' o 'H2H4')")
    provider = provider or DEFAULT_PROVIDER
    meta = load_prompt_meta(prompt_path)

    # R1.5 -- perfil H2H4: filtra ANTES de evidence_pack_gate/build_prompt/
    # output_token_budget/build_run_fingerprint, para que ese subconjunto de
    # checkpoints sea la UNICA vista del prompt que el resto de la funcion
    # conoce -- ningun otro punto de evaluate_chunked necesita saber que el
    # perfil existe.
    if evaluation_profile == "H2H4":
        if not target_requirement_ids:
            raise ValueError("evaluation_profile='H2H4' exige target_requirement_ids no vacio")
        target_requirement_ids = tuple(target_requirement_ids)
        filtered_checkpoints = [cp for cp in meta["checkpoints"] if cp["req_id"] in target_requirement_ids]
        found = {cp["req_id"] for cp in filtered_checkpoints}
        missing = set(target_requirement_ids) - found
        if missing:
            raise ValueError(
                f"target_requirement_ids {sorted(missing)!r} no existen en el prompt real de {agent_id!r}")
        meta = {**meta, "checkpoints": filtered_checkpoints}
    else:
        target_requirement_ids = None
    # Captura de metadata de reproducibilidad ANTES de la primera inferencia
    # (fix TE-02 / requisito de preflight): modelo, model_digest, version de
    # Ollama, agent_version, prompt_version, verifier_version, documento,
    # SHA-256 y run_id. Si el runtime no esta disponible, falla aqui —
    # explicito y antes de gastar ninguna llamada de chunk — en vez de
    # capturar la excepcion en silencio y seguir con metadata incompleta.
    model_name = provider.model_name
    model_digest = provider.show_digest()
    ollama_version_str = provider.runtime_version()

    run_fingerprint = build_run_fingerprint(
        meta, model_digest=model_digest, document_sha256=document_sha256, agent_version=agent_version,
        use_verified_pipeline=use_verified_pipeline,
        evaluation_profile=evaluation_profile, target_requirement_ids=target_requirement_ids,
    )

    chunks = build_page_chunks(per_unit_text)

    # Presupuesto de salida derivado del contrato REAL del prompt + guardia
    # de contexto, ambos ANTES de la primera inferencia (2026-07-28). Ningun
    # numero se escribe a mano: si el catalogo gana criterios, sube solo.
    # Gate 4 (2026-07-28): se evalua UNA vez por corrida, antes de la primera
    # inferencia. Los req_id sin Evidence Pack completo no entran al prompt y
    # no generan ninguna llamada; la corrida sigue con los admitidos.
    admitted_checkpoints, blocked_packs = evidence_pack_gate(meta)
    blocked_req_ids = {v.req_id: v for v in blocked_packs}

    n_criteria = _count_contract_criteria(meta)
    num_predict = output_token_budget(len(admitted_checkpoints), n_criteria)
    context_window = getattr(provider, "context_window", None)
    token_budget = _assert_token_budget_fits(chunks, meta, num_predict, context_window)
    token_budget["contract_criteria"] = n_criteria
    token_budget["contract_checkpoints"] = len(meta["checkpoints"])
    honors_budget = _provider_honors_token_budget(provider)
    token_budget["provider_honors_token_budget"] = honors_budget

    chunk_executions: list[dict] = []
    start_index = 0

    resumed = None
    fingerprint_mismatch = None
    verified_coverage_discard = None
    if checkpoint_store is not None:
        resumed, fingerprint_mismatch = checkpoint_store.find_resumable(
            document_sha256, agent_id, run_fingerprint,
            include_completed_with_failures=retry_technical_failures,
        )
        # Segunda barrera, independiente del fingerprint: comprobar que los
        # registros verificados estan REALMENTE en el checkpoint y cubren
        # todos los chunks ya ejecutados (ver verified_records_coverage_gap).
        # Nunca en silencio: si no cumplen, se descarta y queda en preflight.
        if resumed is not None and use_verified_pipeline:
            verified_coverage_discard = verified_records_coverage_gap(
                resumed, [cp["req_id"] for cp in meta["checkpoints"]],
            )
            if verified_coverage_discard is not None:
                resumed = None

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
        "run_fingerprint": run_fingerprint,
        "evaluation_profile": evaluation_profile,
        "target_requirement_ids": list(target_requirement_ids) if target_requirement_ids else None,
        # W5 V2 Fase F: nunca en silencio -- si un checkpoint previo existia
        # pero su fingerprint no coincidia, queda explicito aqui que se
        # descarto y la corrida empezo de cero (no se resumio nada).
        "checkpoint_fingerprint_mismatch_discarded": fingerprint_mismatch is not None,
        "checkpoint_fingerprint_mismatch_detail": fingerprint_mismatch,
        # Reanudacion verificada (2026-07-27): mismo principio que arriba --
        # un checkpoint descartado por no traer cobertura verificada completa
        # queda registrado, nunca se descarta en silencio.
        "checkpoint_verified_coverage_discarded": verified_coverage_discard is not None,
        "checkpoint_verified_coverage_detail": verified_coverage_discard,
        "resumed_from_checkpoint": resumed is not None,
        "resumed_chunk_count": start_index,
        # Presupuesto de tokens (2026-07-28): queda en el preflight para que
        # un dossier pueda declarar con que presupuesto se produjo, y para
        # que un truncamiento futuro sea diagnosticable sin re-ejecutar.
        "token_budget": token_budget,
        "retry_technical_failures_requested": retry_technical_failures,
        "retried_chunk_indices": [],
        # Gate 4 (evidence_pack_validation): queda SIEMPRE en el preflight,
        # tambien cuando no bloquea nada -- un dossier debe poder demostrar
        # que el gate se evaluo, no solo que no salto.
        "evidence_pack_gate": {
            "checkpoints_total": len(meta["checkpoints"]),
            "admitted_req_ids": [cp["req_id"] for cp in admitted_checkpoints],
            "blocked": [
                {"req_id": v.req_id, "missing": list(v.missing), "detail": v.detail}
                for v in blocked_packs
            ],
            "all_checkpoints_blocked": not admitted_checkpoints,
        },
    }

    by_req: dict[str, list[dict]] = {cp["req_id"]: [] for cp in meta["checkpoints"]}
    cp_label_by_req = {cp["req_id"]: cp["label"] for cp in meta["checkpoints"]}

    verified_records_by_req: dict[str, list[dict]] = {cp["req_id"]: [] for cp in meta["checkpoints"]}
    # Reanudacion verificada (2026-07-27): restaurar los registros verificados
    # de los chunks ya ejecutados. Sin esto, reanudar arrancaria la
    # consolidacion con los registros de los chunks restantes UNICAMENTE, y
    # coverage_complete=True mentiria. Solo se llega aqui si
    # verified_records_coverage_gap() ya confirmo que estan completos.
    if resumed is not None:
        for req_id, records in (resumed.get("verified_records_by_req") or {}).items():
            verified_records_by_req.setdefault(req_id, []).extend(records)
    known_verified_requirement_ids: set = set(by_req.keys())
    # W5 V2 Fase F: se computa siempre (no solo bajo use_verified_pipeline)
    # -- ahora tambien lo consume la validacion C real (verify_evidence_abcd)
    # para D, ver el bucle de consolidacion mas abajo.
    from factory.regulatory.evidence_verifier import load_requirement_terms
    requirement_terms_by_req: dict[str, list] = {req_id: load_requirement_terms(req_id) for req_id in by_req}
    from factory.regulatory import semantic_evidence_verification as sev
    # Re-derivar by_req de chunk_executions ya completados (reanudación real,
    # no solo saltar llamadas — la consolidación final también debe verlos).
    # has_evidence puede faltar en checkpoints generados antes del fix
    # 2026-07-16; se asume True (comportamiento previo) para no romper
    # reanudaciones de runs viejos.
    for ce in chunk_executions:
        for cand in ce.get("_by_req_candidates", []):
            cand["candidate"].setdefault("has_evidence", True)
            by_req.setdefault(cand["req_id"], []).append(cand["candidate"])

    # Plan de ejecucion: primero los chunks a REEMPLAZAR (reintento dirigido
    # de fallos tecnicos, 2026-07-28), luego los que faltan por ejecutar. Un
    # reintento reemplaza su entrada en chunk_executions en vez de anadir una
    # nueva -- si se anadiera, len(chunk_executions) dejaria de ser el indice
    # de reanudacion y la cobertura verificada contaria doble.
    pending: list[tuple[dict, int | None]] = []
    if retry_technical_failures and resumed is not None:
        by_index = {c["chunk_index"]: c for c in chunks}
        for position, previous in enumerate(chunk_executions):
            if not previous.get("technical_execution_failure"):
                continue
            chunk_to_retry = by_index.get(previous["chunk_index"])
            if chunk_to_retry is None:
                continue  # el chunking cambio; el fingerprint ya lo habria detectado
            pending.append((chunk_to_retry, position))
            preflight_metadata["retried_chunk_indices"].append(previous["chunk_index"])
    pending.extend((chunk, None) for chunk in chunks[start_index:])

    for chunk, replace_at in pending:
        task_id = f"task-{uuid.uuid4().hex[:12]}"
        text = sanitize_document(chunk["text"])
        started_at = datetime.now(timezone.utc).isoformat()
        t0 = time.monotonic()

        if replace_at is not None:
            # Purga de los registros verificados del intento anterior, por
            # record_id: sin esto el chunk reintentado aportaria DOS registros
            # por requisito (el rechazado y el nuevo) y coverage_complete
            # contaria una cobertura que no existe.
            stale_task_id = chunk_executions[replace_at].get("task_id")
            for req_id, records in verified_records_by_req.items():
                verified_records_by_req[req_id] = [
                    r for r in records
                    if r.get("record_id") != f"vrec-{stale_task_id}-{req_id}"
                ]

        # Fix TE-01: distinguir "chunk sin texto extraible" (no es un fallo
        # tecnico, es una pagina vacia legitima) de un fallo TECNICO real de
        # ejecucion (llamada fallida, JSON invalido o esquema invalido pese
        # a 'format':'json' + temperatura 0 + reparacion acotada). Un fallo
        # tecnico NUNCA debe terminar convertido silenciosamente en
        # 'evidencia_insuficiente' a nivel de finding sin quedar marcado.
        technical_execution_failure = False
        failure_reason = None
        raw_response_text = ""
        if not admitted_checkpoints:
            # Gate 4: ningun checkpoint tiene Evidence Pack completo, asi que
            # no hay nada que preguntarle al modelo. Se BLOQUEA la llamada
            # (no la corrida): el chunk queda registrado, la corrida termina
            # y cada requisito sale como no evaluado, nunca como incumplido.
            # No es technical_execution_failure: no fallo nada tecnico, se
            # aplico un control de gobernanza.
            chunk_result = None
            error = (
                "evidence_pack_gate: llamada bloqueada -- ningun checkpoint del prompt "
                "tiene Evidence Pack completo (gate 4)"
            )
        elif not text.strip():
            chunk_result = None
            error = "chunk sin texto extraible"
        else:
            prompt = build_prompt(meta, text)
            try:
                raw = (provider.generate(prompt, num_predict=num_predict)
                       if honors_budget else provider.generate(prompt))
                chunk_result, failure_reason, raw_response_text = classify_model_response(raw)
                if failure_reason is None:
                    error = None
                else:
                    error = _FAILURE_DETAIL[failure_reason]
                    technical_execution_failure = True
            except Exception as e:
                chunk_result = None
                failure_reason = "provider_call_failed"
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
                # relevante al checkpoint (ver _is_topically_relevant). Este
                # gate (legacy, result["findings"]) se queda igual: no tiene
                # ningun consumidor downstream capaz de manejar una senal
                # suave -- ver R1.7 mas abajo para el pipeline verificado.
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
                #
                # R1.7 (2026-08-09, docs_plan/R1_6_VALIDADOR_RELEVANCIA_IDIOMA.md):
                # el pipeline verificado (el que usa corpus_runner/produccion)
                # deja de usar _is_topically_relevant -- es un pre-filtro propio,
                # mas crudo que la validacion C real y ya probada del sistema
                # (semantic_evidence_verification.verify_semantic_relevance /
                # detect_reference_list_context, language-agnostic via
                # requirement_terms.yaml, que ademas NUNCA rechaza duro por
                # relevancia lexica -- solo marca NOT_VERIFIABLE/review_required).
                # build_finding_record() -> verify_llm_output() ya calcula esa
                # misma relevancia lexica (V5, sin tocar aqui) y la traduce a
                # status='review_required' cuando es debil; absence_consolidator
                # ya sabe tratar ese status de forma segura (SUPPORTING_EVIDENCE_
                # UNDER_REVIEW, nunca lo promueve a una conclusion positiva
                # confirmada) -- pero esa maquinaria nunca llegaba a ejecutarse
                # de verdad porque este pre-filtro ya blanqueaba la evidencia
                # antes. Se mantiene UNICAMENTE el componente estructural y
                # deterministico de la validacion C real (deteccion de listas de
                # referencias numeradas, el mecanismo que de verdad rechaza
                # ANNEX11_4 -- antes se rechazaba por coincidencia accidental de
                # idioma, no por esto). `sev` ya esta importado mas arriba en
                # esta funcion.
                valid_candidate_verified = (
                    anchored and not sev.detect_reference_list_context(evidencia, chunk["text"])
                    if requires_anchor else True
                )
                if use_verified_pipeline and req_id in verified_records_by_req:
                    from factory.regulatory.verified_pipeline_adapter import build_finding_record
                    v_candidate = {
                        "page_start": chunk["page_start"], "page_end": chunk["page_end"],
                        "estado": estado if valid_candidate_verified else "evidencia_insuficiente",
                        "evidencia_exacta": evidencia if valid_candidate_verified else "",
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

                # W5 V2 Fase F (ampliacion D, 2026-07-25): criterion_assessments
                # de la respuesta del modelo NUNCA se ignora en silencio --
                # se extrae y se pasa a verify_evidence_abcd() (A/B/C/D
                # completo, no solo D), y el resultado se persiste en el
                # candidate. Ausente (None) -> D queda NOT_ASSESSABLE
                # explicito (ver semantic_evidence_verification.py), nunca
                # un campo vacio sin explicacion.
                criterion_assessments = entry.get("criterion_assessments")
                abcd = sev.verify_evidence_abcd(
                    evidencia, chunk["text"], req_id, requirement_terms_by_req.get(req_id, []),
                    criterion_assessments=criterion_assessments,
                )
                candidate["d_sufficiency"] = abcd.d_sufficiency
                candidate["d_reason"] = abcd.d_reason
                candidate["d_detail"] = abcd.d_detail
                candidate["substantive_evidence_accepted"] = abcd.substantive_evidence_accepted
                candidate["operational_result"] = abcd.operational_result

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
                    # Gate 4: un requisito bloqueado por pack incompleto nunca
                    # se registra como "el modelo no lo devolvio" -- jamas se
                    # le pregunto. La causa real viaja en el registro.
                    req_reason = (
                        "evidence_pack_incomplete" if req_id in blocked_req_ids else reason
                    )
                    verified_records_by_req[req_id].append(
                        rejected_record(f"vrec-{task_id}-{req_id}", req_reason))

        # El extracto de _RAW_PERSIST_MAX_CHARS que vive en el checkpoint no
        # es la unica copia de la respuesta: cuando hay checkpoint_store, el
        # texto COMPLETO se persiste aparte (gzip, referenciado por hash) --
        # ver W5V2_REMEDIACION_RECALL_MODELO.md 1.2 / CheckpointStore.
        # save_raw_response. El cap del checkpoint mismo impidio auditar el
        # razonamiento real de una corrida de piloto (2026-08-08); nunca mas
        # debe ser la unica copia.
        raw_response_full_ref = (
            checkpoint_store.save_raw_response(run_id, task_id, raw_response_text)
            if (checkpoint_store is not None and raw_response_text)
            else None
        )

        execution = {
            "run_id": run_id, "task_id": task_id, "chunk_index": chunk["chunk_index"],
            "page_start": chunk["page_start"], "page_end": chunk["page_end"],
            "has_overlap_prefix": chunk["has_overlap_prefix"], "text_chars": chunk["text_chars"],
            "started_at": started_at, "finished_at": finished_at, "wall_clock_ms": wall_ms,
            "model": model_name, "model_digest": model_digest,
            "ollama_version": ollama_version_str,
            "ok": chunk_result is not None, "error": error,
            "technical_execution_failure": technical_execution_failure,
            # Causa EXPLICITA del fallo (2026-07-28): output_truncated /
            # no_json_object / json_parse_failed / schema_validation_failed /
            # provider_call_failed. Antes las cuatro primeras compartian un
            # unico mensaje y un truncamiento por presupuesto era
            # indistinguible de un modelo devolviendo basura.
            "failure_reason": failure_reason,
            "num_predict": num_predict if honors_budget else None,
            # La respuesta CRUDA se conserva (acotada) para que un fallo sea
            # diagnosticable post-hoc sin re-ejecutar el chunk, y para poder
            # auditar que dijo el modelo en un run regulatorio.
            "raw_response": raw_response_text[:_RAW_PERSIST_MAX_CHARS],
            "raw_response_truncated_in_log": len(raw_response_text) > _RAW_PERSIST_MAX_CHARS,
            "raw_response_full_path": raw_response_full_ref["path"] if raw_response_full_ref else None,
            "raw_response_full_sha256": raw_response_full_ref["sha256"] if raw_response_full_ref else None,
            "_by_req_candidates": by_req_candidates,
        }

        if replace_at is None:
            chunk_executions.append(execution)
        else:
            # El intento fallido NUNCA se borra: un run regulatorio debe poder
            # demostrar que hubo un fallo y que se resolvio.
            previous = chunk_executions[replace_at]
            history = list(previous.pop("superseded_attempts", []))
            history.append(previous)
            execution["superseded_attempts"] = history
            chunk_executions[replace_at] = execution

        if checkpoint_store is not None:
            checkpoint_store.save(run_id, {
                "run_id": run_id, "document_sha256": document_sha256, "agent_id": agent_id,
                "documento": documento, "archivo": archivo, "total_chunks": len(chunks),
                "chunk_executions": chunk_executions, "completed": False,
                "fingerprint": run_fingerprint,
                # Reanudacion verificada (2026-07-27): los registros
                # verificados viajan CON el checkpoint. Se guardan siempre
                # (vacios si el flag esta apagado) para que la comprobacion
                # de cobertura del resume sea un hecho verificable y no una
                # suposicion sobre quien lo escribio.
                "verified_records_by_req": verified_records_by_req,
            })

    any_unresolved_technical_failure = any(
        ce.get("technical_execution_failure") for ce in chunk_executions
    )

    findings: list[Finding] = []
    # W5 V2 Fase F (cierre del hueco de verified_conclusions, 2026-07-25):
    # indice req_id -> Finding ya consolidado, para que la degradacion de la
    # conclusion verificada lea el veredicto ABCD YA DECIDIDO aqui y no
    # re-derive D por su cuenta (una sola autoridad de decision).
    finding_by_req: dict[str, Finding] = {}
    # P1 (2026-07-27): un req_id repetido en el prompt haria que el segundo
    # Finding sobrescribiera al primero en el indice. `findings` conserva
    # ambos; estos req_id se marcan para que la conclusion verificada nunca
    # se decida sobre un indice ambiguo.
    duplicate_req_ids: set[str] = set()
    contradictions = []
    for cp in meta["checkpoints"]:
        if cp["req_id"] in finding_by_req:
            duplicate_req_ids.add(cp["req_id"])
        req_id, label = cp["req_id"], cp["label"]

        # Gate 4: requisito cuya llamada se BLOQUEO por Evidence Pack
        # incompleto. Sale explicitamente como NO EVALUADO. Nunca puede caer
        # en las ramas de abajo: sin candidatos, la rama de ausencia lo
        # convertiria en 'no_cumple / mayor' -- un incumplimiento afirmado
        # sobre un requisito que jamas se le mostro al modelo.
        if req_id in blocked_req_ids:
            verdict = blocked_req_ids[req_id]
            finding = Finding(
                sistema=sistema, documento=documento, version=version, archivo=archivo,
                pagina_o_seccion="(no evaluado: llamada bloqueada por el gate 4)",
                requisito_regulatorio=f"{req_id} — {label}",
                evidencia_exacta="",
                estado="evidencia_insuficiente",
                brecha=(
                    "EVIDENCE_PACK_INCOMPLETE: este requisito NO fue evaluado. Su Evidence "
                    f"Pack no esta completo ({verdict.detail}), asi que el checkpoint no se "
                    "incluyo en el prompt y no hubo ninguna llamada al modelo. La ausencia de "
                    "hallazgo NO es evidencia de cumplimiento ni de incumplimiento: es ausencia "
                    "de evaluacion. Completar el pack en el catalogo de requisitos y re-ejecutar."
                ),
                severidad="no_determinada",
                riesgo="No evaluado: el requisito nunca se sometio al modelo (gate 4).",
                recomendacion=(
                    f"Completar en requirements.yaml los campos faltantes de {req_id} "
                    f"({', '.join(verdict.missing)}) y volver a ejecutar este documento."
                ),
                confianza="baja",
                agente_responsable=agent_id,
                revision_humana_requerida=True,
                agent_version=agent_version,
                prompt_version=meta.get("prompt_version"),
                model=model_name,
                verifier_version=meta.get("verifier_version"),
            )
            findings.append(finding)
            finding_by_req.setdefault(req_id, finding)
            continue

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
                brecha_no_cumple = (
                    f"Ninguna de las {len(not_observed)} secciones que mencionaron este checkpoint "
                    "aporto una cita verificable; la conclusion se basa en ausencia generalizada, "
                    "no en una demostracion positiva de incumplimiento del sistema. No documentado "
                    "en el FS != control inexistente en el sistema — requiere revision del expediente "
                    "completo (SOPs, IQ/OQ) antes de asumir incumplimiento real."
                )
                # Fix D-5 (2026-07-28): esta rama emitia un incumplimiento
                # MAYOR sin marcarlo provisional aunque hubiera chunks
                # fallidos, a diferencia de la rama `else` de abajo que si lo
                # hacia. Un "no_cumple/mayor" presentado como definitivo con
                # parte del documento sin evaluar es exactamente lo que el
                # fail-closed de la Fase F existe para impedir.
                if any_unresolved_technical_failure:
                    n_fail = sum(1 for ce in chunk_executions if ce.get("technical_execution_failure"))
                    brecha_no_cumple = (
                        f"PROVISIONAL (technical_execution_failure_pending): {n_fail} chunk(s) de este "
                        "run tuvieron un fallo tecnico de ejecucion sin reintento agotado. La ausencia "
                        "de evidencia que sostiene este no_cumple puede deberse al fallo tecnico y no a "
                        "una ausencia real en el documento. Reintentar los chunks fallidos "
                        "(retry_technical_failures=True) antes de tratar este incumplimiento como "
                        "definitivo. " + brecha_no_cumple
                    )
                findings.append(Finding(
                    sistema=sistema, documento=documento, version=version, archivo=archivo,
                    pagina_o_seccion=f"{pages} (not_observed_in_chunk en todas las secciones evaluadas)",
                    requisito_regulatorio=f"{req_id} — {label}",
                    evidencia_exacta="(ninguna seccion citó evidencia positiva ni negativa para este checkpoint)",
                    estado="no_cumple",
                    brecha=brecha_no_cumple,
                    severidad="mayor",
                    riesgo="Ausencia de evidencia documental; no confirma ausencia del control en el sistema.",
                    recomendacion=(
                        "Reintentar los chunks con technical_execution_failure antes de aceptar este "
                        "incumplimiento." if any_unresolved_technical_failure else
                        "Revisar expediente completo (SOPs/IQ/OQ) antes de concluir incumplimiento real."
                    ),
                    confianza="baja", agente_responsable=agent_id, revision_humana_requerida=True,
                    agent_version=agent_version, prompt_version=meta["prompt_version"],
                    model=model_name, verifier_version=meta["verifier_version"],
                    technical_execution_failure_pending=any_unresolved_technical_failure,
                    substantive_support="NOT_APPLICABLE",  # no_cumple no es sujeto de sustento sustantivo
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
                    substantive_support="NOT_APPLICABLE",  # evidencia_insuficiente no es sujeto de sustento sustantivo
                ))
            finding_by_req[req_id] = findings[-1]
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
                # Una contradiccion abierta (cumple vs no_cumple) nunca esta
                # sustancialmente sustentada mientras no se resuelva, sin
                # importar D de un candidato individual.
                substantive_support="NOT_SUPPORTED",
            ))
            finding_by_req[req_id] = findings[-1]
            continue

        best = candidates[0]
        brecha = best["brecha"]
        if not_observed:
            brecha += (f" ({len(not_observed)} seccion(es) adicionales no trataron este checkpoint — "
                       "not_observed_in_chunk, no cuentan como evidencia en contra.)")
        # W5 V2 Fase F (cableado de D a decision): un estado positivo cuya
        # evidencia sustantiva no fue aceptada (D != MET, incl. None por
        # checkpoint reanudado pre-fase) queda NOT_SUPPORTED -- nunca se
        # presenta como sustentado (revision_humana_requerida ya es True).
        substantive_support = _compute_substantive_support(
            best["estado"], best.get("substantive_evidence_accepted"),
        )
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
            # W5 V2 Fase F (ampliacion D): propagados desde el candidate
            # ganador -- ausentes (None) si el candidate viene de un
            # checkpoint reanudado de un run anterior a esta fase (formato
            # viejo, sin estos campos) -- nunca inventados.
            d_sufficiency=best.get("d_sufficiency"),
            substantive_evidence_accepted=best.get("substantive_evidence_accepted"),
            operational_result=best.get("operational_result"),
            substantive_support=substantive_support,
        ))
        finding_by_req[req_id] = findings[-1]

    technical_execution_failures = [
        {"chunk_index": ce["chunk_index"], "task_id": ce["task_id"], "error": ce["error"]}
        for ce in chunk_executions if ce.get("technical_execution_failure")
    ]

    # W5 V2 Fase F (cableado de D a decision): superficie la decision para
    # que un reporte/consumidor pueda actuar sobre "N hallazgos positivos NO
    # sustentados sustantivamente" sin re-derivarlo del detalle por finding.
    # UNKNOWN explicito: un Finding sin veredicto se cuenta como desconocido,
    # nunca se absorbe en NOT_APPLICABLE (eso ocultaria el vacio).
    substantive_support_summary = {k: 0 for k in SUBSTANTIVE_SUPPORT_VALUES}
    for f in findings:
        key = f.substantive_support if f.substantive_support in SUBSTANTIVE_SUPPORT_VALUES else "UNKNOWN"
        substantive_support_summary[key] += 1

    # W5 V2 §13.4.5 / gate "0 fallos recuperables bloqueando toda la corrida":
    # una excepcion consolidando UN requisito no puede tumbar la corrida
    # entera. Se registra como excepcion gobernada y el requisito queda
    # EVALUATION_INCOMPLETE.
    governed_exceptions = []
    verified_conclusions = None
    if use_verified_pipeline:
        from factory.regulatory.absence_consolidator import (
            DocumentConclusion as _DocumentConclusion,
            apply_conclusion_preconditions as _apply_preconditions,
            consolidate as _consolidate,
        )
        from factory.regulatory.applicability import (
            applicability as _applicability,
            matrix_approved as _matrix_approved,
            require_matrix_approved_for_production as _require_matrix_approved,
        )
        # §13.3 "aplicabilidad aprobada": guardia ya implementada y hasta
        # 2026-07-27 sin ningun llamador de runtime. Si la matriz no esta
        # human_confirmed, solo run_context='validation' puede continuar.
        _require_matrix_approved(run_context)
        # P2 (2026-07-27): esta guardia NO demuestra que la matriz este
        # aprobada -- con run_context='validation' pasa con la matriz
        # pending_human_confirmation. La precondicion §13.3 "aplicabilidad
        # aprobada" se consulta aparte; darla por cierta aqui afirmaba una
        # aprobacion humana inexistente.
        applicability_rule_approved = _matrix_approved()
        contradicted_req_ids = {c["req_id"] for c in contradictions}
        # coverage_complete=True es real, no asumido: evaluate_chunked()
        # siempre procesa TODOS los chunks del documento -- cada uno aporto
        # un registro (observado, no-observado o rejected_by_verifier) para
        # cada requisito, nunca un subconjunto parcial.
        #
        # 2026-07-27: esto sigue siendo cierto al reanudar. Antes se apoyaba
        # en que checkpoint_store estaba prohibido con este flag; ahora se
        # apoya en dos barreras verificadas al arrancar: el fingerprint
        # incluye use_verified_pipeline (no se mezcla con checkpoints de otro
        # contrato) y verified_records_coverage_gap() comprueba que los
        # registros de los chunks ya ejecutados esten completos, restaurados
        # arriba en verified_records_by_req. Si cualquiera falla, no se
        # reanuda: la corrida empieza de cero y queda dicho en preflight.
        verified_conclusions = {}
        for cp in meta["checkpoints"]:
            req_id = cp["req_id"]
            if req_id in duplicate_req_ids:
                # P1: un req_id duplicado en el prompt hace que finding_by_req
                # (y verified_conclusions) conserven solo el ultimo. Ningun
                # Finding se pierde -- `findings` los lleva todos -- pero la
                # conclusion seria no determinista, asi que se degrada y se
                # registra como excepcion gobernada en vez de resolverse a
                # ciegas.
                if req_id not in verified_conclusions:
                    governed_exceptions.append({
                        "req_id": req_id, "stage": "verified_conclusions",
                        "exception": "DUPLICATE_REQUIREMENT_CHECKPOINT",
                        "detail": "req_id repetido en meta['checkpoints']; conclusion no determinista",
                    })
                verified_conclusions[req_id] = {
                    "conclusion": "EVALUATION_INCOMPLETE", "chunks_evaluated": 0,
                    "chunks_observed": 0, "chunks_review_pending": 0,
                    "review_flags": ["DUPLICATE_REQUIREMENT_CHECKPOINT"],
                }
                continue
            try:
                app = _applicability(req_id, document_type)
                conclusion = _consolidate(
                    req_id, document_type, app["value"], verified_records_by_req.get(req_id, []),
                    coverage_complete=True,
                )
                finding = finding_by_req.get(req_id)
                conclusion = _apply_preconditions(
                    conclusion,
                    d_sufficiency=finding.d_sufficiency if finding else None,
                    substantive_evidence_accepted=(
                        finding.substantive_evidence_accepted if finding else None),
                    operational_result=finding.operational_result if finding else None,
                    applicability_value=app["value"],
                    positive_conclusion_eligibility=_positive_conclusion_eligibility(req_id),
                    has_open_contradiction=req_id in contradicted_req_ids,
                    applicability_rule_approved=applicability_rule_approved,
                )
            except Exception as exc:  # noqa: BLE001 -- excepcion gobernada, ver arriba
                governed_exceptions.append({
                    "req_id": req_id, "stage": "verified_conclusions",
                    "exception": type(exc).__name__, "detail": str(exc),
                })
                conclusion = _DocumentConclusion(
                    requirement_id=req_id, document_type=document_type,
                    conclusion="EVALUATION_INCOMPLETE",
                    review_flags=["CONSOLIDATION_EXCEPTION"],
                )
            verified_conclusions[req_id] = {
                "conclusion": conclusion.conclusion,
                "chunks_evaluated": conclusion.chunks_evaluated,
                "chunks_observed": conclusion.chunks_observed,
                "chunks_review_pending": conclusion.chunks_review_pending,
                "review_flags": list(conclusion.review_flags),
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
        "substantive_support_summary": substantive_support_summary,
        "governed_exceptions": governed_exceptions,
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
            "fingerprint": run_fingerprint,
            "verified_records_by_req": verified_records_by_req,
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
                # W5 V2 Fase F (cableado de D): hallazgos positivos NO
                # sustentados sustantivamente quedan en la cadena de
                # auditoria, nunca solo en el JSON de salida.
                "substantive_support_summary": result.get("substantive_support_summary"),
                # W5 V2 §13.4: toda excepcion gobernada queda en la cadena de
                # auditoria -- un requisito que no se pudo consolidar nunca
                # desaparece en silencio del registro de la corrida.
                "governed_exceptions": result.get("governed_exceptions"),
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
