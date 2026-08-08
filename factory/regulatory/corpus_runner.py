"""W5 V2 ARQ — runner real de la corrida del corpus (plan
`W5V2_ARQ_RETOMAR_Y_FINALIZAR.md` Bloque 6, spec
`MODEL_REQUALIFICATION_AND_D4A_SPEC.md` §5.3): la pieza declarada
`NOT_IMPLEMENTED_YET` a propósito en `corpus_authorization.py` -- "batches,
checkpoints per_document, resume por fingerprint, hard stops de D4-A".

Orquesta `chunked_engine.evaluate_chunked()` -- el MISMO camino de
producción que ya corrió realmente (eu_annex11 sobre FS_v1.2, 2026-07-28,
27 chunks/481 min/0 fallos) -- sobre los 5 documentos reales de
`corpus_budget_formula.CORPUS_PLAN_DOCUMENTS` (RW-0005/0006/0011/0012/0014),
un `evaluate_chunked()` por (documento, agente) con R(d,a) ≠ ∅
(`corpus_plan.resolve_document_agent_plan`), `use_verified_pipeline=True` +
`document_type` (para que la matriz de aplicabilidad filtre por requisito
DESPUÉS de la llamada, mismo patrón que las corridas reales previas --
`evaluate_chunked()` no filtra checkpoints individuales por tipo documental
ANTES de preguntarle al modelo, ver docstring de `corpus_plan.py`: R(d,a)
decide qué AGENTES corren, no qué checkpoints se preguntan dentro de un
agente que sí corre).

Guardias, en orden, TODAS antes de la primera llamada real:
  1. `CORPUS_AUTHORIZATION` vigente y con un único `run_fingerprint` (mismo
     criterio fail-closed que `corpus_authorization.apply_corpus_authorization`)
     para TODOS los `document_ids` del lote.
  2. `require_inference_authorized(status, call_type=INFERENCE,
     run_context='production')` -- exige `QUALIFIED` pleno.
  3. Hard stops de D4-A (`compute_d4a()`, nunca un número escrito a mano):
     antes de EMPEZAR cada unidad (documento, agente) se verifica que su
     costo esperado (`chunks(d)` llamadas) no exceda el presupuesto
     restante -- si no cabe, el lote se detiene ahí (nunca arranca una
     unidad a medias para luego cortarla: `evaluate_chunked()` no acepta un
     tope de llamadas dentro de una misma invocación, así que el corte real
     ocurre SOLO entre unidades, nunca dentro de una).

Resume: cada unidad usa el MISMO `CheckpointStore` (por SHA-256 + agente +
`run_fingerprint`, mecanismo ya real de `chunked_engine.py`, Fase F) -- una
invocación interrumpida (proceso muerto, límite de tiempo del turno) se
retoma exactamente donde quedó con una nueva llamada a
`run_corpus_batch()`, sin repetir ninguna llamada real ya hecha."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

from factory.core import decision_scope_resolver as resolver
from factory.core.audit_writer import write_event
from factory.engines.gmpai_integrity import chunked_engine as ce
from factory.engines.gmpai_integrity.model_provider import DEFAULT_PROVIDER, ModelProvider
from factory.regulatory import corpus_authorization as ca
from factory.regulatory import model_qualification_gate as mqg
from factory.regulatory.corpus_budget_formula import CORPUS_PLAN_DOCUMENTS, compute_d4a
from factory.regulatory.corpus_plan import AGENT_PROMPT_FILES, PROMPTS_DIR, resolve_document_agent_plan
from factory.regulatory.pilot_execution import DECISION_FAMILY as PILOT_DECISION_FAMILY
from factory.regulatory.requirement_catalog.citation_locator import sha256_file
from factory.services import decision_store_v2 as decision_store

ALLOWLIST_PATH = Path(__file__).parent / "scope" / "source_baseline_allowlist.yaml"
#: Raíz declarada por el propio inventario de Fase A
#: (`build_source_baseline_allowlist.py --manifest-root`, default real,
#: NUNCA modificado por esta corrida -- solo lectura).
GMPAI_ROOT = Path("/home/ing_cpmo/GMPAI")

DEFAULT_CHECKPOINT_DIR = Path(__file__).parent / "corpus_run" / "checkpoints"
DEFAULT_MANIFEST_DIR = Path(__file__).parent / "corpus_run" / "manifests"

#: Aislamiento físico del piloto (plan `W5V2_PILOTO_DIAGNOSTICO_PRECORPUS.md`
#: §2): rutas DISTINTAS de las de la corrida formal, nunca compartidas --
#: para que un resume/manifest formal no pueda, ni por accidente, leer nada
#: escrito por un piloto (ver test_pilot_isolation.py).
PILOT_CHECKPOINT_DIR = Path(__file__).parent / "pilot_run" / "checkpoints"
PILOT_MANIFEST_DIR = Path(__file__).parent / "pilot_run" / "manifests"
PILOT_OUTPUT_DIR = Path(__file__).parents[1] / "generated_documents" / "pilot"

#: Etiqueta real y fechada de esta corrida (no un número de versión de
#: agente formal -- no existe un registro de versiones de agente todavía,
#: ver hallazgo de `model_requalification_calibration.py`). Estable a
#: propósito entre invocaciones: cambiarla invalidaría el `run_fingerprint`
#: de resume de TODAS las unidades ya empezadas.
CORPUS_RUN_AGENT_VERSION = "v1-corpus-2026-08"

#: Etiqueta distinta a `CORPUS_RUN_AGENT_VERSION` a propósito -- un `run_id`
#: de piloto nunca debe poder confundirse por prefijo con uno de la corrida
#: formal (plan §2: "fingerprint propio: prefijo pilot-<fecha>-").
PILOT_RUN_AGENT_VERSION = "v1-pilot-2026-08"

_PROMPT_PATH_BY_AGENT = {agent_id: PROMPTS_DIR / filename for filename, agent_id in AGENT_PROMPT_FILES}


class CorpusRunNotAuthorizedError(Exception):
    """El lote propuesto no tiene `CORPUS_AUTHORIZATION` vigente y coherente
    para TODOS sus documentos -- fail-closed, nunca arranca una sola
    llamada real sin esto."""


class CorpusDocumentDriftError(Exception):
    """El SHA-256 real del archivo fuente ya no coincide con el
    registrado en `source_baseline_allowlist.yaml` -- el documento pudo
    haber cambiado desde que se autorizó el corpus. Nunca se analiza un
    archivo que no es demostrablemente el mismo que se autorizó."""


@dataclass
class CorpusRunUnit:
    document_id: str
    document_type: str
    document_path: Path
    document_sha256: str
    agent_id: str
    prompt_path: Path
    expected_calls: int


@dataclass
class UnitOutcome:
    document_id: str
    agent_id: str
    status: str  # COMPLETED | NOT_STARTED_HARD_STOP | FAILED
    run_id: str | None = None
    calls_made_this_invocation: int = 0
    resumed_chunk_count: int = 0
    technical_execution_failures: int = 0
    wall_seconds: float = 0.0
    error: str | None = None


@dataclass
class CorpusRunSummary:
    units: list = field(default_factory=list)
    stop_reason: str = "CORPUS_COMPLETE"
    total_calls_made: int = 0
    total_wall_seconds: float = 0.0
    manifest_path: str | None = None


def _load_allowlist_entry(document_id: str) -> dict:
    data = yaml.safe_load(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    entry = next((e for e in data if e["file_id"] == document_id), None)
    if entry is None:
        raise CorpusDocumentDriftError(
            f"{document_id!r} no está en {ALLOWLIST_PATH} -- inventario de Fase A desactualizado")
    return entry


def _resolve_document_path(document_id: str) -> tuple[Path, str]:
    """Ruta real + SHA-256 VERIFICADO en el momento (nunca el hash leído
    del YAML sin recomprobar contra el archivo real en disco)."""
    entry = _load_allowlist_entry(document_id)
    path = (GMPAI_ROOT / entry["path"]).resolve()
    if not path.is_file():
        raise CorpusDocumentDriftError(f"{document_id!r}: archivo no encontrado en {path}")
    live_sha256 = sha256_file(path)
    if live_sha256 != entry["sha256"]:
        raise CorpusDocumentDriftError(
            f"{document_id!r}: SHA-256 real ({live_sha256}) no coincide con el "
            f"registrado en la allowlist ({entry['sha256']}) -- el archivo cambió")
    return path, live_sha256


def plan_corpus_units(documents=CORPUS_PLAN_DOCUMENTS) -> list[CorpusRunUnit]:
    """Una `CorpusRunUnit` por (documento, agente) con R(d,a) ≠ ∅, en el
    MISMO orden que `compute_d4a()` -- para que los hard stops de D4-A
    (calculados sobre ese mismo orden) sean comparables 1:1 con el orden de
    ejecución real."""
    units: list[CorpusRunUnit] = []
    for doc_id, doc_type, chunks in documents:
        path, doc_sha256 = _resolve_document_path(doc_id)
        plan = resolve_document_agent_plan(doc_type)
        for agent_id in plan:
            units.append(CorpusRunUnit(
                document_id=doc_id, document_type=doc_type, document_path=path,
                document_sha256=doc_sha256, agent_id=agent_id,
                prompt_path=_PROMPT_PATH_BY_AGENT[agent_id], expected_calls=chunks,
            ))
    return units


@dataclass
class PilotSampleUnit:
    """Una llamada real del Piloto 1 (§3.1): NO un (documento, agente)
    completo como `CorpusRunUnit` -- un extracto CORTO y real (páginas
    concretas, elegidas a mano tras leer el PDF, nunca el documento entero)
    para que cubrir 4 agentes en 8-12 llamadas reales sea posible. El costo
    de una `CorpusRunUnit` completa (mínimo 7 chunks reales) haría
    imposible ese presupuesto."""
    document_id: str
    document_type: str
    agent_id: str
    requirement_id: str
    page_indices: tuple[int, ...]  # 0-based, reales, dentro de las páginas del PDF
    selection_reason: str


def _check_pilot_execution(document_ids: list[str], *,
                           decision_store_file: Path | None = None) -> dict:
    """Fail-closed igual que `_check_corpus_authorization`, pero contra la
    familia SEPARADA `PILOT_EXECUTION` -- nunca `CORPUS_AUTHORIZATION`/`D4`.
    Devuelve el payload de la decisión vigente (trae `max_calls`, el tope
    duro real de ESTE piloto)."""
    instances = set()
    for doc_id in document_ids:
        scope = resolver.resolve(PILOT_DECISION_FAMILY, doc_id, store_file=decision_store_file)
        if not scope.authorized:
            raise CorpusRunNotAuthorizedError(
                f"{doc_id!r} sin PILOT_EXECUTION vigente: {scope.denial_reason}")
        instances.update(scope.covering_instances)
    if len(instances) != 1:
        raise CorpusRunNotAuthorizedError(
            "las unidades del piloto no comparten una única PILOT_EXECUTION vigente "
            f"({instances!r})")
    instance_id = instances.pop()
    decision = next((r for r in decision_store.read_all(decision_store_file)
                     if r.get("decision_instance_id") == instance_id), None)
    if decision is None:
        raise CorpusRunNotAuthorizedError(f"{instance_id!r} no se encuentra en el almacén")
    return decision.get("payload") or {}


def _extract_pilot_excerpt(path: Path, page_indices: tuple[int, ...]) -> list[str]:
    """Solo las páginas reales pedidas -- nunca el documento completo. Cada
    página se procesa como una unidad propia de `per_unit_text` (mismo
    contrato que `_default_extractor`), así que `evaluate_chunked` la trata
    como un extracto corto real, no como el corpus formal."""
    import pypdf

    reader = pypdf.PdfReader(str(path))
    n_pages = len(reader.pages)
    out_of_range = [i for i in page_indices if i < 0 or i >= n_pages]
    if out_of_range:
        raise CorpusDocumentDriftError(
            f"{path}: page_indices fuera de rango {out_of_range!r} (el PDF tiene {n_pages} páginas)")
    return [(reader.pages[i].extract_text() or "") for i in page_indices]


def run_pilot_sample_batch(units: list[PilotSampleUnit], *,
                           provider: ModelProvider | None = None,
                           checkpoint_dir: Path = PILOT_CHECKPOINT_DIR,
                           manifest_dir: Path = PILOT_MANIFEST_DIR,
                           decision_store_file: Path | None = None,
                           persist_manifest: bool = True) -> CorpusRunSummary:
    """Piloto 1 (representatividad, §3 del plan): ejecuta la lista EXPLÍCITA
    de `PilotSampleUnit` -- nunca `plan_corpus_units()`/barrido completo.
    `run_context='pilot'` en cada llamada real; el tope duro de llamadas
    viene de la decisión `PILOT_EXECUTION` vigente (`payload['max_calls']`),
    NUNCA de `compute_d4a()` (ese presupuesto es de la corrida formal).
    Checkpoints/manifests en `PILOT_CHECKPOINT_DIR`/`PILOT_MANIFEST_DIR`
    (nunca los de producción) -- misma garantía de aislamiento físico que
    documenta `test_pilot_isolation.py`."""
    provider = provider or DEFAULT_PROVIDER
    if not units:
        return CorpusRunSummary(stop_reason="NO_UNITS")

    document_ids = sorted({u.document_id for u in units})
    pilot_payload = _check_pilot_execution(document_ids, decision_store_file=decision_store_file)
    max_calls = pilot_payload.get("max_calls")
    if not isinstance(max_calls, int) or max_calls <= 0:
        raise CorpusRunNotAuthorizedError(
            f"PILOT_EXECUTION vigente sin max_calls válido: {max_calls!r}")

    status = mqg.evaluate_model_qualification(provider).status
    mqg.require_inference_authorized(status, call_type=mqg.CALL_TYPE_INFERENCE, run_context="pilot")

    checkpoint_store = ce.CheckpointStore(checkpoint_dir)
    excerpt_cache: dict[tuple[str, tuple[int, ...]], list[str]] = {}

    summary = CorpusRunSummary()
    for unit in units:
        expected_calls = len(unit.page_indices)
        if summary.total_calls_made + expected_calls > max_calls:
            summary.units.append(UnitOutcome(
                document_id=unit.document_id, agent_id=unit.agent_id,
                status="NOT_STARTED_HARD_STOP"))
            summary.stop_reason = "HARD_STOP_CALLS"
            break

        path, doc_sha256 = _resolve_document_path(unit.document_id)
        cache_key = (unit.document_id, unit.page_indices)
        if cache_key not in excerpt_cache:
            excerpt_cache[cache_key] = _extract_pilot_excerpt(path, unit.page_indices)

        t0 = time.monotonic()
        try:
            result = ce.evaluate_chunked(
                _PROMPT_PATH_BY_AGENT[unit.agent_id], agent_id=unit.agent_id,
                agent_version=PILOT_RUN_AGENT_VERSION,
                per_unit_text=excerpt_cache[cache_key],
                sistema="pilot_run_sample", documento=unit.document_id,
                version="v1", archivo=str(path), document_sha256=doc_sha256,
                run_context="pilot", checkpoint_store=checkpoint_store,
                use_verified_pipeline=True, document_type=unit.document_type,
                retry_technical_failures=True, provider=provider,
            )
        except Exception as e:  # noqa: BLE001 -- nunca se traga: se registra y se relanza
            wall = time.monotonic() - t0
            summary.units.append(UnitOutcome(
                document_id=unit.document_id, agent_id=unit.agent_id, status="FAILED",
                wall_seconds=wall, error=f"{type(e).__name__}: {e}"))
            summary.total_wall_seconds += wall
            summary.stop_reason = "TECHNICAL_FAILURE"
            if persist_manifest:
                summary.manifest_path = _persist_manifest(summary, manifest_dir)
            _write_batch_event(summary, document_ids, run_context="pilot")
            raise

        wall = time.monotonic() - t0
        preflight = result["preflight_metadata"]
        resumed_at_start = preflight.get("resumed_chunk_count", 0)
        retried = len(preflight.get("retried_chunk_indices") or [])
        new_calls = (len(result["chunk_executions"]) - resumed_at_start) + retried
        reused_without_new_call = resumed_at_start - retried
        n_failures = len(result.get("technical_execution_failures") or [])

        summary.units.append(UnitOutcome(
            document_id=unit.document_id, agent_id=unit.agent_id, status="COMPLETED",
            run_id=result["run_id"], calls_made_this_invocation=new_calls,
            resumed_chunk_count=reused_without_new_call, technical_execution_failures=n_failures,
            wall_seconds=wall,
        ))
        summary.total_calls_made += new_calls
        summary.total_wall_seconds += wall

    if persist_manifest:
        summary.manifest_path = _persist_manifest(summary, manifest_dir)
    _write_batch_event(summary, document_ids, run_context="pilot")
    return summary


def _default_extractor(path: Path) -> list[str]:
    """Mismo extractor ya usado en `run_validation_evidence.py` (pypdf,
    sin dependencia nueva) -- solo lectura, el PDF original nunca se toca."""
    import pypdf

    reader = pypdf.PdfReader(str(path))
    return [(p.extract_text() or "") for p in reader.pages]


def _check_corpus_authorization(document_ids: list[str], *,
                                decision_store_file: Path | None = None) -> None:
    """Fail-closed: TODOS los `document_ids` deben estar cubiertos por la
    MISMA decisión `CORPUS_AUTHORIZATION` vigente (mismo criterio que
    `corpus_authorization._d4_covering_instance`, aplicado aquí a la
    familia de autorización de corpus, no a la de presupuesto)."""
    instances = set()
    for doc_id in document_ids:
        scope = resolver.resolve(ca.DECISION_FAMILY, doc_id, store_file=decision_store_file)
        if not scope.authorized:
            raise CorpusRunNotAuthorizedError(
                f"{doc_id!r} sin CORPUS_AUTHORIZATION vigente: {scope.denial_reason}")
        instances.update(scope.covering_instances)
    if len(instances) != 1:
        raise CorpusRunNotAuthorizedError(
            f"los documentos del lote no comparten una única CORPUS_AUTHORIZATION "
            f"({instances!r}) -- nunca se ejecuta un lote con cobertura mixta o parcial")


def run_corpus_batch(units: list[CorpusRunUnit] | None = None, *,
                     provider: ModelProvider | None = None,
                     checkpoint_dir: Path = DEFAULT_CHECKPOINT_DIR,
                     manifest_dir: Path = DEFAULT_MANIFEST_DIR,
                     decision_store_file: Path | None = None,
                     persist_manifest: bool = True) -> CorpusRunSummary:
    """Ejecuta unidades (documento, agente) en orden hasta agotar el
    corpus o un hard stop de D4-A. Nunca arranca una unidad cuyo costo
    esperado no cabe en el presupuesto restante -- el corte real es SIEMPRE
    entre unidades. Cada unidad reintentada/retomada usa el mismo
    `checkpoint_dir`: una invocación interrumpida se retoma sin repetir
    llamadas ya hechas."""
    provider = provider or DEFAULT_PROVIDER
    units = units if units is not None else plan_corpus_units()
    if not units:
        return CorpusRunSummary(stop_reason="NO_UNITS")

    document_ids = sorted({u.document_id for u in units})
    _check_corpus_authorization(document_ids, decision_store_file=decision_store_file)

    status = mqg.evaluate_model_qualification(provider).status
    mqg.require_inference_authorized(
        status, call_type=mqg.CALL_TYPE_INFERENCE, run_context="production")

    d4a = compute_d4a(documents=tuple(d for d in CORPUS_PLAN_DOCUMENTS if d[0] in document_ids))
    hard_stop_calls = d4a["hard_stop_calls"]
    hard_stop_wall_seconds = d4a["hard_stop_wall_time_hours"] * 3600

    checkpoint_store = ce.CheckpointStore(checkpoint_dir)
    page_cache: dict[str, list[str]] = {}

    summary = CorpusRunSummary()
    for unit in units:
        if summary.total_calls_made + unit.expected_calls > hard_stop_calls:
            summary.units.append(UnitOutcome(
                document_id=unit.document_id, agent_id=unit.agent_id,
                status="NOT_STARTED_HARD_STOP"))
            summary.stop_reason = "HARD_STOP_CALLS"
            break
        if summary.total_wall_seconds > hard_stop_wall_seconds:
            summary.units.append(UnitOutcome(
                document_id=unit.document_id, agent_id=unit.agent_id,
                status="NOT_STARTED_HARD_STOP"))
            summary.stop_reason = "HARD_STOP_WALL_TIME"
            break

        if unit.document_id not in page_cache:
            page_cache[unit.document_id] = _default_extractor(unit.document_path)

        t0 = time.monotonic()
        try:
            result = ce.evaluate_chunked(
                unit.prompt_path, agent_id=unit.agent_id,
                agent_version=CORPUS_RUN_AGENT_VERSION,
                per_unit_text=page_cache[unit.document_id],
                sistema="corpus_run", documento=unit.document_id,
                version="v1", archivo=str(unit.document_path),
                document_sha256=unit.document_sha256,
                run_context="production", checkpoint_store=checkpoint_store,
                use_verified_pipeline=True, document_type=unit.document_type,
                retry_technical_failures=True, provider=provider,
            )
        except Exception as e:  # noqa: BLE001 -- nunca se traga: se registra y se relanza
            wall = time.monotonic() - t0
            outcome = UnitOutcome(
                document_id=unit.document_id, agent_id=unit.agent_id, status="FAILED",
                wall_seconds=wall, error=f"{type(e).__name__}: {e}")
            summary.units.append(outcome)
            summary.total_wall_seconds += wall
            summary.stop_reason = "TECHNICAL_FAILURE"
            if persist_manifest:
                summary.manifest_path = _persist_manifest(summary, manifest_dir)
            _write_batch_event(summary, document_ids)
            raise

        wall = time.monotonic() - t0
        preflight = result["preflight_metadata"]
        # "resumed_chunk_count" de preflight es cuántos chunks YA estaban
        # checkpointeados al EMPEZAR esta invocación -- no dice cuántos de
        # esos se reintentaron (retry_technical_failures=True puede
        # reemplazar un chunk "resumido" con una llamada real nueva). Los
        # genuinamente reusados sin ninguna llamada nueva son
        # resumed_at_start - retried; las llamadas nuevas reales son los
        # chunks que no existían al empezar MÁS los reintentados.
        resumed_at_start = preflight.get("resumed_chunk_count", 0)
        retried = len(preflight.get("retried_chunk_indices") or [])
        new_calls = (len(result["chunk_executions"]) - resumed_at_start) + retried
        reused_without_new_call = resumed_at_start - retried
        n_failures = len(result.get("technical_execution_failures") or [])

        summary.units.append(UnitOutcome(
            document_id=unit.document_id, agent_id=unit.agent_id, status="COMPLETED",
            run_id=result["run_id"], calls_made_this_invocation=new_calls,
            resumed_chunk_count=reused_without_new_call, technical_execution_failures=n_failures,
            wall_seconds=wall,
        ))
        summary.total_calls_made += new_calls
        summary.total_wall_seconds += wall

    if persist_manifest:
        summary.manifest_path = _persist_manifest(summary, manifest_dir)
    _write_batch_event(summary, document_ids)
    return summary


def _persist_manifest(summary: CorpusRunSummary, manifest_dir: Path) -> str:
    manifest_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = manifest_dir / f"corpus_run_{ts}.json"
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stop_reason": summary.stop_reason,
        "total_calls_made": summary.total_calls_made,
        "total_wall_seconds": round(summary.total_wall_seconds, 1),
        "units": [vars(u) for u in summary.units],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _write_batch_event(summary: CorpusRunSummary, document_ids: list[str], *,
                       run_context: str = "production") -> None:
    write_event("corpus_run_batch_completed", "regulatory_intel", {
        "document_ids": document_ids,
        "run_context": run_context,
        "stop_reason": summary.stop_reason,
        "total_calls_made": summary.total_calls_made,
        "total_wall_seconds": round(summary.total_wall_seconds, 1),
        "units_completed": sum(1 for u in summary.units if u.status == "COMPLETED"),
        "units_failed": sum(1 for u in summary.units if u.status == "FAILED"),
        "manifest_path": summary.manifest_path,
    })
