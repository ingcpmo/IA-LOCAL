"""W5 V2, Fase F -- validación A/B/C/D (SEMANTIC_EVIDENCE_VERIFICATION_SPEC.md).

Diagnóstico previo a esta fase: A ya existía, probada y con historial real
de fixes (W5.5/W5.6) en `evidence_verifier.match_citation`/
`verify_llm_output`. Existía una versión parcial de C (heurística de
solapamiento léxico, `relevance_score`/`RELEVANCE_REVIEW_REQUIRED`). B no
existía como chequeo explícito a nivel de hallazgo. D originalmente no
podía implementarse con juicio regulatorio real porque `evidence_min_criteria`
seguía `PENDING_HUMAN_INTERPRETATION` -- ese bloqueo se cerró en Fase C
(commit `46ca69f`, 19/19 requisitos con `evidence_min_criteria` real y
aprobado). D real se agrega aquí (ampliación 2026-07-25), reutilizando
`verify_anchor` para el anclaje individual -- nunca reimplementado.

Este módulo compone las 4 validaciones sin reemplazar la lógica existente:
  A -- delega en evidence_verifier.match_citation (anclaje en el documento).
  B -- NUEVO: el requirement_id resuelve en el catálogo gobernado (Fase C)
       Y la fuente regulatoria tiene hashes_match=True (integridad real,
       no solo presencia).
  C -- reusa evidence_verifier.relevance_score (heurística léxica existente)
       MÁS una regla determinista GENÉRICA nueva (no requiere
       weak_keywords por requisito): detecta si la cita vive dentro de una
       LISTA DE REFERENCIAS NUMERADAS del documento bajo revisión (patrón
       real confirmado: '[6] ... [7] ... [8] Good Automated Manufacturing
       Practice... GAMP5' en el propio corpus Rockwell -- exactamente el
       caso real ANNEX11_4 de la corrida URS v2.1). Esta regla es
       estructural (formato del documento), no interpretación regulatoria
       por requisito.
  D -- SUFFICIENCY_VERIFICATION real (ver verify_sufficiency()): clasifica
       cada evidence_min_criteria del catálogo real vía un array unificado
       `criterion_assessments` (criterion_index/criterion_text/status/
       evidence_quote/evidence_location/justification/limitations). Dos
       niveles de rechazo, deliberadamente distintos:
         (A) violación de CONTRATO (índice/texto duplicado, fuera de
             whitelist, estado inválido, MET sin evidencia/ubicación) ->
             rechazo ATÓMICO de todo el array, nunca se rescatan entradas
             buenas de una respuesta corrupta (mismo criterio que
             chunked_engine._extract_json ya aplica a JSON malformado).
         (B) validación FACTUAL por criterio (evidence_quote que no ancla
             en el documento) -> descarte individual, no rompe el resto.
       Si el llamador no provee criterion_assessments (default None,
       compatibilidad con resultados históricos como la corrida URS v2.1,
       que nunca tuvo este campo), D queda NOT_ASSESSABLE explícito --
       nunca inventado.

Evidencia sustantiva aceptada (`substantive_evidence_accepted`): conjunción
INCONDICIONAL A ∧ B ∧ C ∧ D == MET. Un resultado sin D evaluado
(NOT_ASSESSABLE) NUNCA se acepta -- no hay excepción de compatibilidad
retroactiva aquí (a diferencia de una versión anterior de este módulo, no
commiteada, que sí la tenía). `operational_result` distingue por separado
si D fue evaluado (`EVALUATION_COMPLETE`) o no (`EVALUATION_INCOMPLETE`,
mismo principio que absence_consolidator.EVALUATION_INCOMPLETE) -- para
que un caller pueda diferenciar "rechazado por D=NOT_MET real" de
"todavía no evaluado", sin que ninguno de los dos casos cuente como
aceptado."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from factory.regulatory.evidence_verifier import match_citation, relevance_score

# Patrón de referencia numerada entre corchetes ('[6]', '[12]', ...) --
# convención tipográfica generica de listas de referencias tecnicas,
# independiente del dominio o del requisito evaluado.
_BRACKETED_REF_RE = re.compile(r"\[\d{1,3}\]")
_REFERENCE_LIST_MIN_MARKERS = 2
_REFERENCE_LIST_WINDOW_CHARS = 250


_D_ASSESSED_STATUSES = frozenset({"MET", "NOT_MET", "PARTIALLY_MET"})


@dataclass
class ABCDResult:
    a_anchor: str               # PASS | FAIL
    a_match_type: str           # exact | normalized | despaced | fuzzy | not_found
    b_source: str               # PASS | FAIL | NOT_VERIFIABLE
    c_semantic: str             # PASS | FAIL | NOT_VERIFIABLE
    c_flags: list = field(default_factory=list)
    d_sufficiency: str = "NOT_ASSESSABLE"
    d_reason: str = "evidence_min_criteria pendiente de interpretacion humana (Fase C)"
    d_detail: dict = field(default_factory=dict)

    @property
    def substantive_evidence_accepted(self) -> bool:
        """A ∧ B ∧ C ∧ D==MET, SIEMPRE incondicional -- sin excepcion para
        D=NOT_ASSESSABLE. Un resultado historico (sin evaluacion D) o con
        D=PARTIALLY_MET/NOT_MET nunca queda aceptado."""
        return (
            self.a_anchor == "PASS" and self.b_source == "PASS" and self.c_semantic == "PASS"
            and self.d_sufficiency == "MET"
        )

    @property
    def operational_result(self) -> str:
        """EVALUATION_INCOMPLETE si D nunca se evaluo (NOT_ASSESSABLE,
        incl. resultados historicos sin criterion_assessments);
        EVALUATION_COMPLETE si D fue realmente evaluado (MET/NOT_MET/
        PARTIALLY_MET), independientemente de si substantive_evidence_
        accepted termino en True o False."""
        return "EVALUATION_COMPLETE" if self.d_sufficiency in _D_ASSESSED_STATUSES else "EVALUATION_INCOMPLETE"


def verify_anchor(quote: str, source_text: str) -> tuple[str, str]:
    """Validación A. Reusa evidence_verifier.match_citation sin
    reimplementar la lógica de anclaje ya probada."""
    match_type, _score = match_citation(quote, source_text)
    return ("PASS" if match_type in ("exact", "normalized", "despaced", "fuzzy") else "FAIL", match_type)


def verify_regulatory_source(requirement_id: str) -> str:
    """Validación B (nueva). El requisito resuelve en el catálogo gobernado
    Y la fuente regulatoria tiene integridad verificada (hashes_match).
    Import local para no crear un ciclo con requirement_catalog_loader en
    tiempo de import de este módulo (mismo patrón que otros módulos de
    factory/regulatory/ que importan el catálogo bajo demanda)."""
    from factory.regulatory.requirement_catalog.requirement_catalog_loader import (
        CatalogValidationError, get_requirement, get_source,
    )
    try:
        entry = get_requirement(requirement_id)
        source = get_source(entry["source_id"])
    except CatalogValidationError:
        return "FAIL"
    return "PASS" if source.get("hashes_match") is True else "FAIL"


def detect_reference_list_context(quote: str, source_text: str) -> bool:
    """Regla determinista genérica (no requiere weak_keywords por
    requisito): True si la cita vive dentro de una lista de referencias
    numeradas entre corchetes ('[N]') -- patrón real confirmado en el
    corpus Rockwell (caso ANNEX11_4 de la corrida URS v2.1: 'GAMP5' citado
    dentro de '[8] Good Automated Manufacturing Practice... GAMP5', junto a
    '[6]'/'[7]'/'[9]'/'[10]' en la misma lista). Busca la posición de la
    cita (misma normalización que match_citation) y cuenta marcadores
    '[N]' en una ventana alrededor -- ≥2 marcadores en la ventana indica
    una lista de referencias, no prosa regulatoria real."""
    if not quote or not quote.strip() or not source_text:
        return False
    idx = source_text.find(quote)
    if idx == -1:
        # Intenta con normalizacion basica de espacios (mismo criterio
        # relajado que 'normalized' en match_citation, sin duplicar su
        # lógica completa aquí -- solo para ubicar una posición aproximada).
        collapsed_source = re.sub(r"\s+", " ", source_text)
        collapsed_quote = re.sub(r"\s+", " ", quote).strip()
        idx = collapsed_source.find(collapsed_quote)
        if idx == -1:
            return False
        source_text = collapsed_source
    start = max(0, idx - _REFERENCE_LIST_WINDOW_CHARS)
    end = min(len(source_text), idx + len(quote) + _REFERENCE_LIST_WINDOW_CHARS)
    window = source_text[start:end]
    return len(_BRACKETED_REF_RE.findall(window)) >= _REFERENCE_LIST_MIN_MARKERS


def verify_semantic_relevance(
    quote: str, source_text: str, requirement_terms: list
) -> tuple[str, list[str]]:
    """Validación C: heurística léxica existente (relevance_score) MÁS la
    regla estructural nueva de lista de referencias. Cualquiera de las dos
    señales negativas degrada a NOT_VERIFIABLE (nunca PASS silencioso) --
    consistente con el principio ya establecido en evidence_verifier.py de
    nunca auto-rechazar por heurística, solo marcar para revisión."""
    flags: list[str] = []
    if detect_reference_list_context(quote, source_text):
        flags.append("REFERENCE_LIST_CONTEXT_SUSPECTED")

    rscore = relevance_score(quote, requirement_terms)
    if rscore == -1.0:
        flags.append("RELEVANCE_NOT_EVALUABLE")
    elif rscore < 0.15:  # mismo umbral que evidence_verifier.RELEVANCE_THRESHOLD
        flags.append("RELEVANCE_REVIEW_REQUIRED")

    if flags:
        return ("NOT_VERIFIABLE", flags)
    return ("PASS", flags)


_VALID_CRITERION_STATUSES = frozenset({"MET", "NOT_MET", "NOT_ASSESSABLE"})

# Fix B3 (R3-T1.4, 2026-08-12, docs_plan/R3_T1_4_FIX_AGREGACION_B3.md):
# estados de chunked_engine._VALID_ESTADOS en los que el propio modelo, a
# nivel de checkpoint (mas alto nivel que criterion_assessments), ya
# declaro que este chunk NO trato el tema del requisito en absoluto. El
# prompt real (part11_prompts.yaml, regla 4 y 6) instruye explicitamente
# "que no mencione un control no implica incumplimiento" y "si no estas
# seguro... usa NOT_ASSESSABLE, nunca NOT_MET" -- pero el modelo (qwen2.5:7b)
# viola esa regla de forma sistematica (confirmado con datos reales de
# chunked-943a62bcbb85 y chunked-50534e75927c, R3_T1_3_VIABILIDAD_F2.md
# secc.1): emite NOT_MET con justificacion boilerplate ("no se menciona X")
# en chunks que su PROPIO campo `estado` ya califica como
# evidencia_insuficiente/no_aplica para ese req_id. Sin este ajuste, esos
# NOT_MET colisionan en la agregacion con un MET real anclado en otro
# chunk y fuerzan NOT_ASSESSABLE por "contradiccion" -- una contradiccion
# FALSA (el chunk nunca trato el tema) disfrazada de contradiccion real.
_OFF_TOPIC_CHUNK_ESTADOS = frozenset({"evidencia_insuficiente", "no_aplica"})


def _find_contract_violations(criterion_assessments: list, ordered_real_criteria: list) -> list[str]:
    """Nivel A de verify_sufficiency(): violaciones de CONTRATO que
    invalidan el array COMPLETO (nunca se rescatan entradas buenas de una
    respuesta corrupta -- mismo criterio que chunked_engine._extract_json
    ya aplica a JSON malformado). Retorna la lista de violaciones (vacia
    si el array es valido)."""
    violations: list[str] = []
    seen_indexes: set = set()
    seen_texts: set = set()
    n = len(ordered_real_criteria)

    for i, entry in enumerate(criterion_assessments):
        if not isinstance(entry, dict):
            violations.append(f"entrada #{i} no es un objeto")
            continue

        idx = entry.get("criterion_index")
        text = entry.get("criterion_text")
        status = entry.get("status")

        if not isinstance(idx, int) or not (1 <= idx <= n):
            violations.append(f"criterion_index invalido o fuera de rango (1..{n}): {idx!r}")
        elif idx in seen_indexes:
            violations.append(f"criterion_index duplicado: {idx!r}")
        else:
            seen_indexes.add(idx)
            if text != ordered_real_criteria[idx - 1]:
                violations.append(
                    f"criterion_text no coincide EXACTO con el criterio real en la posicion {idx}: {text!r}"
                )

        if text in seen_texts:
            violations.append(f"criterion_text duplicado: {text!r}")
        elif isinstance(text, str):
            seen_texts.add(text)

        if status not in _VALID_CRITERION_STATUSES:
            violations.append(f"status invalido: {status!r} (permitidos: {sorted(_VALID_CRITERION_STATUSES)})")
        elif status == "MET" and (not entry.get("evidence_quote") or not entry.get("evidence_location")):
            violations.append(f"status=MET sin evidence_quote/evidence_location (criterion_index={idx!r})")

    return violations


def verify_sufficiency(
    requirement_id: str, criterion_assessments: list | None, source_text: str
) -> tuple[str, str, dict]:
    """Validación D (SUFFICIENCY_VERIFICATION). Clasifica cada
    evidence_min_criteria REAL del catálogo (Fase C) vía el array unificado
    `criterion_assessments` (criterion_index/criterion_text/status/
    evidence_quote/evidence_location/justification/limitations). Reglas
    duras fail-closed:

    - criterion_assessments en None (default) -> NOT_ASSESSABLE explícito,
      sin evaluar nada (compatibilidad con resultados históricos, p.ej. la
      corrida URS v2.1, que nunca tuvo este campo).
    - requirement_id sin evidence_min_criteria en el catálogo ->
      NOT_ASSESSABLE.
    - NIVEL A (contrato, ver _find_contract_violations): índice/texto
      duplicado, índice fuera de rango, texto que no coincide EXACTO con
      el catálogo en esa posición, estado inválido, o MET sin evidencia/
      ubicación -> rechazo ATÓMICO de TODO el array -> NOT_ASSESSABLE,
      con el detalle de cada violación (nunca se rescatan las entradas
      buenas de una respuesta corrupta).
    - NIVEL B (factual, por criterio): un MET cuyo evidence_quote no
      ancla realmente en source_text (verify_anchor, reusado) se descarta
      individualmente -- no invalida el resto del array.
    - Cobertura incompleta (algún criterio real sin una entrada válida) ->
      NOT_ASSESSABLE explícito, nunca se adivina sobre lo no cubierto
      (mismo principio que EVALUATION_INCOMPLETE en
      absence_consolidator.py).
    - Cobertura completa: si algún criterio individual quedó
      NOT_ASSESSABLE (declarado por el modelo) o un MET fue descartado por
      anclaje -> agregado NOT_ASSESSABLE (no se confirma sin certeza
      real). Si no: todos MET -> MET; todos NOT_MET -> NOT_MET; mezcla ->
      PARTIALLY_MET.

    Retorna (d_sufficiency, d_reason, detail)."""
    default_reason = "evidence_min_criteria pendiente de interpretacion humana (Fase C)"
    if criterion_assessments is None:
        return "NOT_ASSESSABLE", default_reason, {}

    from factory.regulatory.requirement_catalog.requirement_catalog_loader import (
        CatalogValidationError, get_requirement,
    )
    try:
        entry = get_requirement(requirement_id)
    except CatalogValidationError:
        return "NOT_ASSESSABLE", f"requirement_id desconocido en el catalogo: {requirement_id!r}", {}

    ordered_real_criteria = list(entry.get("evidence_min_criteria") or [])
    if not ordered_real_criteria:
        return "NOT_ASSESSABLE", f"{requirement_id} no tiene evidence_min_criteria en el catalogo", {}

    violations = _find_contract_violations(criterion_assessments, ordered_real_criteria)
    if violations:
        detail = {"contract_violations": violations}
        return "NOT_ASSESSABLE", f"contrato de criterion_assessments violado: {len(violations)} problema(s)", detail

    confirmed_met, confirmed_not_met, confirmed_not_assessable_individual, discarded_unanchored = (
        _classify_criteria_for_chunk(criterion_assessments, source_text)
    )
    return _finalize_sufficiency(ordered_real_criteria, confirmed_met, confirmed_not_met,
                                  confirmed_not_assessable_individual, discarded_unanchored)


def _classify_criteria_for_chunk(
    criterion_assessments: list, source_text: str, chunk_estado: str | None = None,
) -> tuple[set, set, set, list]:
    """Clasifica los criterios de UN chunk ya validado a nivel de contrato
    (ver _find_contract_violations, corrida ANTES de llamar esto). Extraido
    de verify_sufficiency() (R2.1 Opcion C, 2026-08-10) para que el mismo
    criterio de anclaje se reutilice tanto para un solo chunk
    (verify_sufficiency) como para agregar varios (verify_sufficiency_aggregated)
    -- nunca reimplementado dos veces.

    `chunk_estado` (fix B3, R3-T1.4, 2026-08-12): default None preserva el
    comportamiento exacto previo a este fix (verify_sufficiency(), un solo
    chunk, nunca lo pasa -- no cambia). Cuando SI se provee (agregacion
    multi-chunk) y esta en _OFF_TOPIC_CHUNK_ESTADOS, un NOT_MET de este
    chunk se reclasifica como NOT_ASSESSABLE: el chunk no vota sobre un
    criterio que su propio `estado` de mas alto nivel ya declaro fuera de
    tema para este requisito -- MAS conservador que antes (NOT_ASSESSABLE
    nunca contribuye a MET ni destrababa nada por si solo, ver
    _finalize_sufficiency), nunca menos: esto NUNCA convierte un NOT_MET en
    MET, ni rescata un criterio sin evidencia real -- solo evita que un
    chunk irrelevante contradiga en falso a un chunk que si aporto
    evidencia."""
    confirmed_met: set = set()
    confirmed_not_met: set = set()
    confirmed_not_assessable_individual: set = set()
    discarded_unanchored: list = []
    off_topic_chunk = chunk_estado in _OFF_TOPIC_CHUNK_ESTADOS

    for e in criterion_assessments:
        text = e["criterion_text"]
        status = e["status"]
        if status == "NOT_MET":
            if off_topic_chunk:
                confirmed_not_assessable_individual.add(text)
            else:
                confirmed_not_met.add(text)
        elif status == "NOT_ASSESSABLE":
            confirmed_not_assessable_individual.add(text)
        else:  # MET, ya validado a nivel de contrato (evidence_quote/evidence_location presentes)
            anchor_status, _ = verify_anchor(e["evidence_quote"], source_text)
            if anchor_status != "PASS":
                discarded_unanchored.append(text)
            else:
                confirmed_met.add(text)

    return confirmed_met, confirmed_not_met, confirmed_not_assessable_individual, discarded_unanchored


def _finalize_sufficiency(
    ordered_real_criteria: list, confirmed_met: set, confirmed_not_met: set,
    confirmed_not_assessable_individual: set, discarded_unanchored: list,
) -> tuple[str, str, dict]:
    """Reglas finales de decision, identicas a las que verify_sufficiency()
    ya aplicaba para un solo chunk (R2.1 Opcion C: extraidas sin cambiar su
    logica, para que un solo chunk y varios chunks agregados usen
    exactamente el mismo criterio de cierre)."""
    real_criteria = set(ordered_real_criteria)
    covered = confirmed_met | confirmed_not_met | confirmed_not_assessable_individual | set(discarded_unanchored)
    missing = sorted(real_criteria - covered)
    detail = {
        "met": sorted(confirmed_met), "not_met": sorted(confirmed_not_met),
        "not_assessable_individual": sorted(confirmed_not_assessable_individual),
        "discarded_unanchored": discarded_unanchored, "missing": missing,
    }

    if missing:
        return "NOT_ASSESSABLE", f"cobertura incompleta: {len(missing)} criterio(s) sin clasificar", detail
    if confirmed_not_assessable_individual or discarded_unanchored:
        return "NOT_ASSESSABLE", "cobertura completa pero con incertidumbre real en al menos un criterio", detail
    if len(confirmed_met) == len(real_criteria):
        return "MET", "todos los criterios minimos confirmados y anclados", detail
    if not confirmed_met:
        return "NOT_MET", "ningun criterio minimo confirmado con anclaje real", detail
    return "PARTIALLY_MET", f"{len(confirmed_met)}/{len(real_criteria)} criterios confirmados", detail


def verify_sufficiency_aggregated(
    requirement_id: str, per_chunk: list[tuple[list | None, str] | tuple[list | None, str, str | None]],
) -> tuple[str, str, dict]:
    """R2.1 Opcion C (2026-08-10, docs_plan/R2_1_C_DISENO_AGREGACION_D.md):
    version agregada de verify_sufficiency() -- mismo contrato de retorno
    (d_sufficiency, d_reason, detail), pero el input es la evidencia de
    TODOS los chunks de una misma unidad (documento + requirement_id), no
    uno solo. verify_sufficiency() (un solo chunk) queda intacta y sigue
    siendo el camino usado internamente aqui, chunk por chunk, antes de
    combinar -- nunca se reimplementa el anclaje ni la validacion de
    contrato.

    `per_chunk`: lista de (criterion_assessments, chunk_source_text) o
    (criterion_assessments, chunk_source_text, chunk_estado) -- un
    elemento por cada chunk real que la unidad evaluo (incluidos los que
    no aportaron evidencia -- se excluyen naturalmente al combinar, nunca
    se filtran a mano antes de llamar esto). El 3er elemento (`chunk_estado`,
    fix B3, R3-T1.4, 2026-08-12) es opcional y retrocompatible: si se omite
    o es None, el comportamiento es IDENTICO al de antes de este fix.

    Reglas de combinacion (nuevas, explicitas, nunca aflojan el criterio
    de anclaje de cada chunk individual):
    - Un chunk cuyo criterion_assessments viola el contrato
      (_find_contract_violations) se EXCLUYE de la agregacion -- no
      invalida a los demas chunks. Si TODOS los chunks violan contrato (o
      no hay chunks), cae a NOT_ASSESSABLE explicito.
    - Un criterio queda confirmado MET si ALGUN chunk lo ancla
      (verify_anchor PASS contra el texto de ESE chunk).
    - Fix B3 (R3-T1.4, 2026-08-12, docs_plan/R3_T1_4_FIX_AGREGACION_B3.md):
      un NOT_MET que viene de un chunk cuyo propio `chunk_estado` ya es
      evidencia_insuficiente/no_aplica para este requisito (el chunk no
      trato el tema en absoluto, segun el JUICIO DE MAS ALTO NIVEL del
      propio modelo) se reclasifica como NOT_ASSESSABLE antes de agregar --
      ver _classify_criteria_for_chunk. Esto NUNCA fabrica un MET ni
      rescata un criterio sin evidencia: solo impide que un chunk fuera de
      tema vote NOT_MET por defecto y colisione en falso con un chunk que
      SI ancla evidencia real para ese mismo criterio.
    - CONTRADICCION (dura, nunca resuelta en silencio): un criterio con
      MET anclado en un chunk Y NOT_MET GENUINO (de un chunk relevante,
      tras el ajuste anterior) en otro se mueve a un set `contradicted` --
      fuerza NOT_ASSESSABLE con
      d_reason='contradiccion real entre chunks en al menos un criterio'
      y el detalle de que criterios contradijeron. Mismo principio que
      la deteccion de contradiccion ya existente a nivel de
      estado/checkpoint (chunked_engine.py). Esta regla SIGUE intacta para
      contradicciones reales (dos chunks relevantes en desacuerdo) -- el
      fix B3 nunca la desactiva, solo evita que dispare en falso.
    - Sin contradiccion: mismas reglas finales de _finalize_sufficiency
      (missing -> NOT_ASSESSABLE; incertidumbre en algun criterio ->
      NOT_ASSESSABLE; todos MET -> MET; ninguno MET -> NOT_MET; mezcla ->
      PARTIALLY_MET)."""
    from factory.regulatory.requirement_catalog.requirement_catalog_loader import (
        CatalogValidationError, get_requirement,
    )
    try:
        entry = get_requirement(requirement_id)
    except CatalogValidationError:
        return "NOT_ASSESSABLE", f"requirement_id desconocido en el catalogo: {requirement_id!r}", {}

    ordered_real_criteria = list(entry.get("evidence_min_criteria") or [])
    if not ordered_real_criteria:
        return "NOT_ASSESSABLE", f"{requirement_id} no tiene evidence_min_criteria en el catalogo", {}

    all_met: set = set()
    all_not_met: set = set()
    all_not_assessable: set = set()
    all_discarded_unanchored: list = []
    excluded_chunks_contract_violations: list = []
    valid_chunk_count = 0

    for chunk_entry in per_chunk:
        criterion_assessments, source_text, *rest = chunk_entry
        chunk_estado = rest[0] if rest else None
        if criterion_assessments is None:
            continue
        violations = _find_contract_violations(criterion_assessments, ordered_real_criteria)
        if violations:
            excluded_chunks_contract_violations.append(violations)
            continue
        valid_chunk_count += 1
        met, not_met, not_assessable, discarded = _classify_criteria_for_chunk(
            criterion_assessments, source_text, chunk_estado)
        all_met |= met
        all_not_met |= not_met
        all_not_assessable |= not_assessable
        all_discarded_unanchored.extend(discarded)

    if valid_chunk_count == 0:
        detail = {"excluded_chunks_contract_violations": excluded_chunks_contract_violations}
        return ("NOT_ASSESSABLE",
                "ningun chunk de la unidad tuvo criterion_assessments validos para agregar", detail)

    contradicted = sorted(all_met & all_not_met)
    if contradicted:
        detail = {"contradicted": contradicted, "met": sorted(all_met), "not_met": sorted(all_not_met)}
        return ("NOT_ASSESSABLE",
                f"contradiccion real entre chunks en {len(contradicted)} criterio(s): "
                "MET anclado en un chunk y NOT_MET en otro -- nunca resuelto en silencio",
                detail)

    # Un criterio NOT_ASSESSABLE/no-anclado en UN chunk no debe contar como
    # incierto si OTRO chunk ya lo confirmo (MET anclado o NOT_MET real) --
    # sin esta resta, la union ingenua de "not_assessable" de todos los
    # chunks incluiria criterios ya resueltos en otro lado, anulando el
    # proposito mismo de agregar.
    resolved = all_met | all_not_met
    final_not_assessable = all_not_assessable - resolved
    final_discarded_unanchored = [c for c in all_discarded_unanchored if c not in resolved]

    return _finalize_sufficiency(ordered_real_criteria, all_met, all_not_met,
                                  final_not_assessable, final_discarded_unanchored)


def verify_evidence_abcd(
    quote: str, source_text: str, requirement_id: str, requirement_terms: list,
    *, criterion_assessments: list | None = None,
) -> ABCDResult:
    """Composición completa A/B/C/D para un hallazgo puntual (una cita de
    un chunk del documento bajo revisión, para un requirement_id dado).

    criterion_assessments (Fase F, ampliación D): clasificación real del
    modelo por criterio (ver verify_sufficiency()). Default None -- cero
    cambio de comportamiento para todo llamador existente / resultados
    históricos."""
    a_status, a_match_type = verify_anchor(quote, source_text)
    b_status = verify_regulatory_source(requirement_id)
    c_status, c_flags = verify_semantic_relevance(quote, source_text, requirement_terms)
    d_status, d_reason, d_detail = verify_sufficiency(requirement_id, criterion_assessments, source_text)
    return ABCDResult(
        a_anchor=a_status, a_match_type=a_match_type,
        b_source=b_status,
        c_semantic=c_status, c_flags=c_flags,
        d_sufficiency=d_status, d_reason=d_reason, d_detail=d_detail,
    )
