"""Autorización de corpus — familia `CORPUS_AUTHORIZATION` (plan
`W5V2_ARQ_RETOMAR_Y_FINALIZAR.md` Bloque 6, spec
`MODEL_REQUALIFICATION_AND_D4A_SPEC.md` §6).

Distinta de D4-A (`corpus_budget_formula.compute_d4a`): D4-A dice CUÁNTO
cuesta (`max_calls`/tiempo/topes duros); esta familia dice SI se ejecuta,
atada al `run_fingerprint` EXACTO de configuración
(`model_qualification_gate.build_qualification_fingerprint`, reutilizado
sin reimplementar — incluye `catalog_sha256`, `prompt_versions`,
`model_digest`, `golden_dataset_sha256`, parámetros de generación). El spec
es explícito: "toda corrida queda atada a un run_fingerprint que incluye
catalog_sha256" — un cambio de cualquier campo del fingerprint tras esta
firma invalida la autorización, no se hereda, mismo criterio que la
calificación del modelo.

Precondición fail-closed: la familia D4 debe cubrir EXACTAMENTE el mismo
conjunto de documentos que se propone autorizar (nunca autorizar una
corrida sobre documentos sin presupuesto aprobado).

Este módulo NUNCA lanza ninguna corrida ni hace ninguna llamada a Ollama —
solo registra la decisión de gobernanza. El runner real que consumiría
esta autorización (batches, checkpoints per_document, resume por
fingerprint, hard stops de D4-A) es una pieza de infraestructura aparte,
declarada `NOT_IMPLEMENTED_YET` a propósito (plan Bloque 6: "en ESTA
corrida, llegar hasta dejar todo listo para la autorización de corpus").

Mismo ciclo propose -> confirm -> apply que el resto de la fábrica."""
from __future__ import annotations

from pathlib import Path

from factory.core import decision_scope_resolver as resolver
from factory.services import decision_store_v2 as store
from factory.services import governance_service as gov

DECISION_FAMILY = "CORPUS_AUTHORIZATION"
REQUIRED_PAYLOAD_FIELDS = (
    "document_ids", "d4_decision_instance_id", "run_fingerprint",
    "qualification_status_at_proposal",
)


class CorpusAuthorizationError(Exception):
    pass


def _d4_covering_instance(document_ids: tuple[str, ...], *,
                          decision_store_file: Path | None = None) -> str:
    """El mismo `decision_instance_id` de D4 debe cubrir TODOS los
    documentos propuestos -- fail-closed, nunca mezcla cobertura de dos
    decisiones D4 distintas ni acepta un subconjunto."""
    instances = set()
    for doc_id in document_ids:
        scope = resolver.resolve("D4", doc_id, store_file=decision_store_file)
        if not scope.authorized:
            raise CorpusAuthorizationError(
                f"{doc_id!r} no tiene cobertura D4 (presupuesto) vigente: {scope.denial_reason}")
        instances.update(scope.covering_instances)
    if len(instances) != 1:
        raise CorpusAuthorizationError(
            f"los documentos propuestos no comparten una única decisión D4 "
            f"que los cubra a todos ({instances!r}) -- autorizar exige un "
            "presupuesto único y coherente para todo el plan")
    return instances.pop()


def propose_corpus_authorization(document_ids: tuple[str, ...], *, proposed_by_id: str,
                                 decision_store_file: Path | None = None,
                                 provider=None) -> dict:
    """Propone (`agent_proposed`) la autorización de corpus sobre
    `document_ids`. El `run_fingerprint` se deriva del estado VIVO
    (`build_qualification_fingerprint`, nunca aceptado como parámetro
    humano) -- lo mismo que ya se firme más tarde compara contra este
    fingerprint exacto, no contra una descripción de él.

    `qualification_status_at_proposal` se declara honestamente en el
    payload (hoy: `QUALIFICATION_INVALIDATED`, el catálogo cambió desde la
    última calificación real) -- esta decisión autoriza el PRESUPUESTO Y
    ALCANCE de la corrida, no afirma que el modelo esté calificado; eso lo
    exige por separado `require_inference_authorized()` en el momento real
    de inferir, y es la razón por la que este mecanismo nunca ejecuta nada
    él mismo."""
    from factory.regulatory import model_qualification_gate as mqg

    if not document_ids:
        raise CorpusAuthorizationError("document_ids no puede estar vacío")
    d4_instance = _d4_covering_instance(tuple(document_ids), decision_store_file=decision_store_file)

    fingerprint = mqg.build_qualification_fingerprint(provider=provider)
    qualification = mqg.evaluate_model_qualification(provider=provider, persist=False)

    payload = {
        "document_ids": list(document_ids),
        "d4_decision_instance_id": d4_instance,
        "run_fingerprint": fingerprint,
        "qualification_status_at_proposal": qualification.status,
    }
    reason = (
        f"Autorización de corpus sobre {len(document_ids)} documentos, presupuesto "
        f"D4 {d4_instance!r}. Estado de calificación del modelo al proponer: "
        f"{qualification.status} -- esta firma NO afirma que el modelo esté "
        "calificado, solo autoriza presupuesto/alcance; la inferencia real exige "
        "QUALIFIED por separado en el momento de ejecutar.")
    return gov.propose(
        DECISION_FAMILY, target_ids=list(document_ids), decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", proposed_by_id=proposed_by_id,
        reason=reason, payload=payload, store_file=decision_store_file)


def verify_fingerprint_matches(decision_instance_id: str, *,
                               decision_store_file: Path | None = None,
                               provider=None) -> dict:
    """Único punto de comparación fingerprint vivo vs. firmado — extraído
    de `apply_corpus_authorization()` (Bloque de cierre del gap técnico,
    docs_plan, 2026-08-26) para que el camino REAL de ejecución
    (`corpus_runner._check_corpus_authorization()`) lo reutilice sin
    depender de que un humano recuerde invocar `apply_corpus_authorization()`
    aparte. No valida cobertura de `document_ids` -- eso es precondición
    propia de `apply_corpus_authorization()` (exige el conjunto EXACTO que
    la decisión autorizó), mientras que el runner real puede legítimamente
    ejecutar un lote que sea un SUBCONJUNTO de lo autorizado (resume/retry
    parcial) -- mezclar ambas exigencias en una sola función rompería esos
    lotes parciales que hoy funcionan.

    Fail-closed: `CorpusAuthorizationError` si el registro no existe, el
    payload está incompleto, o el fingerprint vivo difiere del firmado en
    cualquier campo (catálogo, prompts, modelo, golden dataset, parámetros
    de generación -- se compara el dict completo, no campo por campo)."""
    from factory.regulatory import model_qualification_gate as mqg

    decision = next((r for r in store.read_all(decision_store_file)
                     if r.get("decision_instance_id") == decision_instance_id), None)
    if decision is None:
        raise CorpusAuthorizationError(f"{decision_instance_id!r} no se encuentra en el almacén")
    payload = decision.get("payload") or {}
    missing = [f for f in REQUIRED_PAYLOAD_FIELDS if f not in payload]
    if missing:
        raise CorpusAuthorizationError(f"payload incompleto, faltan: {missing}")

    live_fingerprint = mqg.build_qualification_fingerprint(provider=provider)
    if live_fingerprint != payload["run_fingerprint"]:
        raise CorpusAuthorizationError(
            "el run_fingerprint vivo ya no coincide con el firmado -- la configuración "
            "cambió desde que se propuso (catálogo/prompts/modelo/golden dataset), "
            "esta autorización no se hereda, hay que re-proponer sobre el estado actual")
    return live_fingerprint


def apply_corpus_authorization(document_ids: tuple[str, ...], *, decision_instance_id: str,
                               decision_store_file: Path | None = None,
                               provider=None) -> dict:
    """Único punto de aplicación de `CORPUS_AUTHORIZATION`. Re-verifica AL
    MOMENTO DE APLICAR que el fingerprint vivo sigue siendo EXACTAMENTE el
    que se firmó -- cualquier cambio (catálogo, prompts, modelo, golden
    dataset) desde la propuesta invalida la autorización, no se hereda.
    NUNCA lanza ninguna corrida -- solo confirma que la autorización está
    lista para que el runner (aparte, no implementado aquí) la consuma."""
    scope = resolver.resolve(DECISION_FAMILY, document_ids[0] if document_ids else "",
                             store_file=decision_store_file)
    if not scope.authorized or decision_instance_id not in scope.covering_instances:
        raise CorpusAuthorizationError(
            f"{decision_instance_id!r} no es la decisión que autoriza este alcance")

    decision = next((r for r in store.read_all(decision_store_file)
                     if r.get("decision_instance_id") == decision_instance_id), None)
    if decision is None:
        raise CorpusAuthorizationError(f"{decision_instance_id!r} no se encuentra en el almacén")
    payload = decision.get("payload") or {}
    missing = [f for f in REQUIRED_PAYLOAD_FIELDS if f not in payload]
    if missing:
        raise CorpusAuthorizationError(f"payload incompleto, faltan: {missing}")
    if set(payload["document_ids"]) != set(document_ids):
        raise CorpusAuthorizationError(
            f"la decisión autoriza document_ids={payload['document_ids']!r}, no {list(document_ids)!r}")

    live_fingerprint = verify_fingerprint_matches(
        decision_instance_id, decision_store_file=decision_store_file, provider=provider)

    from factory.core.audit_writer import write_event
    write_event("corpus_authorization_applied", "regulatory_intel", {
        "document_ids": list(document_ids),
        "decision_instance_id": decision_instance_id,
        "d4_decision_instance_id": payload["d4_decision_instance_id"],
    })

    return {
        "document_ids": list(document_ids),
        "decision_instance_id": decision_instance_id,
        "run_fingerprint": live_fingerprint,
        "status": "AUTHORIZED_AWAITING_RUNNER",
    }
