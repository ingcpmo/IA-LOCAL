"""Consolidacion documento-nivel de observaciones chunk-nivel. Deterministico
(W5 Ciclo 1, Fase 2, Bloque 2.2).

Regla central (P3): DOCUMENTATION_GAP solo puede emitirse cuando TODOS los
chunks relevantes del documento para un requisito reportan
not_observed_in_chunk y la matriz marca la evidencia como 'expected' en ese
tipo documental. El LLM (finding_llm_v1) nunca emite esta conclusion --
la produce exclusivamente esta funcion, agregando finding_record_v1 ya
verificados.

Regla reforzada (W5.5, tras el hallazgo de ETAPA 3/Fase 5.4.4: un
DOCUMENTATION_GAP se emitio con solo 2/29 chunks reales evaluados porque el
3er chunk quedo rejected_by_verifier y el modulo no tenia forma de saberlo
ni de saber si esos 2 eran todos los chunks relevantes): `coverage_complete`
es ahora un parametro obligatorio, sin default -- el llamador debe declarar
explicitamente si `records` cubre TODOS los chunks relevantes del documento
para este requisito. DOCUMENTATION_GAP nunca se emite si `coverage_complete`
es False, o si algun chunk quedo `rejected_by_verifier` (un chunk rechazado
nunca fue observado con exito -- no puede contar como "ausencia
confirmada"). En cualquiera de los dos casos la conclusion es
EVALUATION_INCOMPLETE, nunca DOCUMENTATION_GAP. Esta regla reforzada aplica
solo a DOCUMENTATION_GAP (P3), no a CROSS_REFERENCE_MISSING ni
NOT_OBSERVED_OPTIONAL -- fuera de alcance de este fix.

Regla reforzada (W5.6, ETAPA 4): DOCUMENTED_AND_SUPPORTED/PARTIALLY_
DOCUMENTED exigen al menos un registro observed/partially_observed con
status verified o verified_with_deviation -- un requisito cuya UNICA
evidencia observada esta en status review_required (sin verificar aun)
concluye SUPPORTING_EVIDENCE_UNDER_REVIEW, nunca un estado que implique
soporte documental confirmado (mismo principio P1 que la regla reforzada de
P3: no afirmar mas de lo que el verificador confirmo)."""
from __future__ import annotations

from dataclasses import dataclass, field

_OBSERVED_STATES = ("observed", "partially_observed")
_VALID_RECORD_STATUSES = ("verified", "verified_with_deviation", "review_required")
_REJECTED_STATUS = "rejected_by_verifier"


@dataclass
class DocumentConclusion:
    requirement_id: str
    document_type: str
    conclusion: str                 # ver catalogo abajo
    chunks_evaluated: int = 0
    chunks_observed: int = 0
    chunks_review_pending: int = 0
    supporting_records: list = field(default_factory=list)
    review_flags: list = field(default_factory=list)


def consolidate(requirement_id: str, document_type: str, applicability_value: str,
                 records: list, *, coverage_complete: bool) -> DocumentConclusion:
    """records: finding_record de TODOS los chunks relevantes evaluados
    para este requisito en este documento (status != rejected_by_verifier
    cuentan como evidencia; los rechazados no aportan).

    coverage_complete (obligatorio, sin default): True solo si `records`
    incluye TODOS los chunks relevantes del documento para este requisito
    (evaluados o rechazados) -- no un subconjunto parcial. Determina si
    DOCUMENTATION_GAP puede emitirse (ver regla reforzada W5.5 arriba)."""
    valid = [r for r in records if r["status"] in _VALID_RECORD_STATUSES]
    rejected = [r for r in records if r["status"] == _REJECTED_STATUS]
    observed = [r for r in valid
                if r["llm_output"]["chunk_observation"] in _OBSERVED_STATES]
    pending = [r for r in valid if r["status"] == "review_required"]

    c = DocumentConclusion(requirement_id, document_type, "",
                            chunks_evaluated=len(valid),
                            chunks_observed=len(observed),
                            chunks_review_pending=len(pending),
                            supporting_records=[r["record_id"] for r in observed])

    if len(valid) == 0:
        # nada evaluable (todo rechazado o sin chunks): jamas concluir ausencia
        c.conclusion = "EVALUATION_INCOMPLETE"
        c.review_flags.append("NO_VALID_RECORDS")
        return c

    if observed:
        # W5.6 (hallazgo real, ETAPA 4): "observed" incluye tanto verified/
        # verified_with_deviation como review_required -- antes de este fix,
        # un requisito con evidencia UNICAMENTE en registros review_required
        # (ninguno verificado) igual concluia DOCUMENTED_AND_SUPPORTED, pese
        # a que ningun chunk_observation paso el verificador. Documentar como
        # "soportado" algo que nadie verifico viola P1. Ahora
        # DOCUMENTED_AND_SUPPORTED/PARTIALLY_DOCUMENTED exigen al menos un
        # observed con status verified/verified_with_deviation; si toda la
        # evidencia observada esta sin verificar, la conclusion es
        # SUPPORTING_EVIDENCE_UNDER_REVIEW (pendiente de juicio humano, no
        # una afirmacion de soporte documental).
        observed_verified = [r for r in observed
                              if r["status"] in ("verified", "verified_with_deviation")]
        if observed_verified:
            fully = [r for r in observed_verified
                     if r["llm_output"]["chunk_observation"] == "observed"]
            c.conclusion = ("DOCUMENTED_AND_SUPPORTED" if fully
                             else "PARTIALLY_DOCUMENTED")
            if pending:
                c.review_flags.append("SUPPORTING_EVIDENCE_UNDER_REVIEW")
        else:
            c.conclusion = "SUPPORTING_EVIDENCE_UNDER_REVIEW"
            c.review_flags.append("OBSERVED_ONLY_UNVERIFIED")
        return c

    # ningun chunk observo evidencia
    if pending:
        c.conclusion = "EVALUATION_INCOMPLETE"
        c.review_flags.append("ABSENCE_BLOCKED_BY_PENDING_REVIEW")
        return c

    if applicability_value == "expected":
        # P3 reforzado (W5.5): cobertura incompleta o chunks rechazados
        # nunca pueden sostener una ausencia confirmada.
        if not coverage_complete:
            c.conclusion = "EVALUATION_INCOMPLETE"
            c.review_flags.append("ABSENCE_BLOCKED_BY_PARTIAL_COVERAGE")
        elif rejected:
            c.conclusion = "EVALUATION_INCOMPLETE"
            c.review_flags.append("ABSENCE_BLOCKED_BY_REJECTED_CHUNKS")
        else:
            c.conclusion = "DOCUMENTATION_GAP"
    elif applicability_value == "cross_reference_expected":
        c.conclusion = "CROSS_REFERENCE_MISSING"
    elif applicability_value == "optional":
        c.conclusion = "NOT_OBSERVED_OPTIONAL"
    else:
        c.conclusion = "EVALUATION_INCOMPLETE"
        c.review_flags.append("APPLICABILITY_UNRESOLVED")
    return c


# ---------------------------------------------------------------------------
# W5 V2 §13.3 -- precondiciones de conclusion que consolidate() no puede
# conocer (2026-07-27).
#
# consolidate() decide sobre los chunk records: cobertura, observacion y
# status del verificador. §13.3 exige ADEMAS, para toda conclusion que
# afirme soporte documental o ausencia consolidada: fuente verificada,
# aplicabilidad aprobada, 0 contradicciones abiertas y evidencia sustantiva
# A∧B∧C∧D (§12.1). Nada de eso es derivable de `records`.
#
# Estas precondiciones viven AQUI y no en cada llamador para que exista UNA
# sola autoridad de conclusion: consolidate() propone sobre los registros,
# apply_conclusion_preconditions() aplica las reglas duras. Ningun llamador
# debe re-derivar D, aplicabilidad ni gobernanza de fuente por su cuenta.
# ---------------------------------------------------------------------------

# Conclusiones que AFIRMAN soporte documental (sujetas a A∧B∧C∧D, §12.1).
_SUPPORT_ASSERTING = frozenset({"DOCUMENTED_AND_SUPPORTED", "PARTIALLY_DOCUMENTED"})
# Conclusiones que AFIRMAN una ausencia consolidada (sujetas a §13.3).
_ABSENCE_ASSERTING = frozenset({"DOCUMENTATION_GAP"})
# Aplicabilidad que excluye el requisito de este documento (matriz v2).
_NOT_APPLICABLE_VALUES = frozenset({"out_of_document_scope"})
_APPLICABILITY_RESOLVED = frozenset({"expected", "optional", "cross_reference_expected"})

# Estados NO finales bajo fuente PENDING_REVERIFICATION: no afirman soporte
# documental ni ausencia consolidada -- ya exigen revision o registran una
# no-observacion sin consecuencia regulatoria. El modelo de evidencia
# provisional no los gobierna (no estan en ALLOWED ni en PROHIBITED), asi que
# quedan exentos de validate_result_status_allowed; SI conservan la marca
# SOURCE_PENDING_REVERIFICATION. Hacerlos fallar detendria el analisis
# provisional que §10 habilita expresamente.
_NON_FINAL_UNDER_PENDING = frozenset({
    "SUPPORTING_EVIDENCE_UNDER_REVIEW",
    "CROSS_REFERENCE_MISSING",
    "NOT_OBSERVED_OPTIONAL",
})

# §10 + provisional_evidence_model: con la fuente PENDING_REVERIFICATION el
# resultado solo puede ser PROVISIONAL. Mapeo final -> provisional.
_PROVISIONAL_EQUIVALENT = {
    "DOCUMENTED_AND_SUPPORTED": "PROVISIONALLY_DOCUMENTED",
    "PARTIALLY_DOCUMENTED": "PROVISIONALLY_PARTIALLY_DOCUMENTED",
    "DOCUMENTATION_GAP": "PROVISIONAL_GAP",
    "DEVIATION_IDENTIFIED": "PROVISIONAL_DEVIATION",
}


def _replace(c: DocumentConclusion, conclusion: str, flag: str) -> DocumentConclusion:
    """Nueva DocumentConclusion degradada. Nunca muta la entrada ni pierde
    los contadores/registros de soporte ya calculados (P1: ningun dato de
    consolidacion se descarta al degradar)."""
    return DocumentConclusion(
        requirement_id=c.requirement_id, document_type=c.document_type, conclusion=conclusion,
        chunks_evaluated=c.chunks_evaluated, chunks_observed=c.chunks_observed,
        chunks_review_pending=c.chunks_review_pending,
        supporting_records=list(c.supporting_records),
        review_flags=list(c.review_flags) + ([flag] if flag not in c.review_flags else []),
    )


def apply_conclusion_preconditions(
    c: DocumentConclusion, *,
    d_sufficiency: str | None,
    substantive_evidence_accepted: bool | None,
    operational_result: str | None,
    applicability_value: str,
    positive_conclusion_eligibility: str,
    has_open_contradiction: bool,
    applicability_rule_approved: bool,
) -> DocumentConclusion:
    """Aplica las precondiciones de §13.3 sobre una conclusion ya producida
    por consolidate(). Determinista, sin LLM, sin efectos secundarios.

    Los tres campos ABCD provienen de semantic_evidence_verification.ABCDResult
    a traves del Finding ya consolidado -- esta funcion NUNCA re-evalua D.

    Orden (de mas fuerte a mas debil; cada paso solo puede degradar):
      1. Aplicabilidad -- NOT_APPLICABLE no puede coexistir con una
         conclusion de soporte ni de ausencia (invariante W5 V2).
      2. Contradiccion abierta -- §12.2: bloquea conclusion positiva; §13.3:
         bloquea DOCUMENTATION_GAP.
      3. Evidencia sustantiva A∧B∧C∧D (§12.1) -- techo de la conclusion
         positiva. §12.2: evidencia parcial ⇒ maximo PARTIALLY_DOCUMENTED.
      4. Gobernanza de fuente (§10) -- con la fuente sin verificar el
         resultado solo puede ser PROVISIONAL, nunca final.
    """
    # ── 1. Aplicabilidad ───────────────────────────────────────────────
    if applicability_value in _NOT_APPLICABLE_VALUES:
        # Invariante duro: consolidate() decide `if observed:` ANTES de mirar
        # la aplicabilidad, asi que un requisito fuera del alcance documental
        # con evidencia observada salia DOCUMENTED_AND_SUPPORTED. Un
        # requisito que no aplica no puede estar "documentado y soportado".
        if c.conclusion != "NOT_APPLICABLE":
            c = _replace(c, "NOT_APPLICABLE", "NOT_APPLICABLE_BY_APPLICABILITY_MATRIX")
        return c
    if applicability_value not in _APPLICABILITY_RESOLVED:
        # review_required o valor no contemplado: la aplicabilidad no esta
        # resuelta, ninguna conclusion terminal puede sostenerse.
        if c.conclusion in _SUPPORT_ASSERTING or c.conclusion in _ABSENCE_ASSERTING:
            c = _replace(c, "EVALUATION_INCOMPLETE", "APPLICABILITY_UNRESOLVED")

    # ── 2. Contradiccion abierta ───────────────────────────────────────
    if has_open_contradiction:
        if c.conclusion in _SUPPORT_ASSERTING:
            c = _replace(c, "SUPPORTING_EVIDENCE_UNDER_REVIEW",
                          "POSITIVE_BLOCKED_BY_OPEN_CONTRADICTION")
        elif c.conclusion in _ABSENCE_ASSERTING:
            c = _replace(c, "EVALUATION_INCOMPLETE",
                          "ABSENCE_BLOCKED_BY_OPEN_CONTRADICTION")

    # ── 3. Evidencia sustantiva A∧B∧C∧D ────────────────────────────────
    if c.conclusion in _SUPPORT_ASSERTING and substantive_evidence_accepted is not True:
        if operational_result == "EVALUATION_INCOMPLETE" or d_sufficiency == "NOT_ASSESSABLE":
            # D no se pudo evaluar: no es "sin soporte", es "sin evaluar".
            c = _replace(c, "EVALUATION_INCOMPLETE", "ABCD_D_NOT_ASSESSABLE")
        elif d_sufficiency == "PARTIALLY_MET":
            # §12.2: evidencia parcial ⇒ FAIL en D ⇒ maximo PARTIALLY_DOCUMENTED.
            if c.conclusion != "PARTIALLY_DOCUMENTED":
                c = _replace(c, "PARTIALLY_DOCUMENTED", "ABCD_D_PARTIALLY_MET")
            elif "ABCD_D_PARTIALLY_MET" not in c.review_flags:
                c = _replace(c, c.conclusion, "ABCD_D_PARTIALLY_MET")
        elif d_sufficiency == "NOT_MET":
            c = _replace(c, "SUPPORTING_EVIDENCE_UNDER_REVIEW",
                          "SUBSTANTIVE_EVIDENCE_NOT_ACCEPTED")
        else:
            # Sin datos ABCD para una conclusion que afirma soporte: el
            # verificador nunca corrio sobre esta evidencia. Fail-closed.
            c = _replace(c, "EVALUATION_INCOMPLETE", "ABCD_NOT_EVALUATED")

    # ── 4. Gobernanza de fuente (§10) ──────────────────────────────────
    if positive_conclusion_eligibility == "BLOCKED":
        if c.conclusion != "NOT_APPLICABLE":
            c = _replace(c, "EVALUATION_INCOMPLETE", "SOURCE_CONCLUSION_BLOCKED")
        return c
    if positive_conclusion_eligibility == "PROVISIONAL_ONLY":
        provisional = _PROVISIONAL_EQUIVALENT.get(c.conclusion)
        if provisional is not None:
            c = _replace(c, provisional, "SOURCE_PENDING_REVERIFICATION")
        elif "SOURCE_PENDING_REVERIFICATION" not in c.review_flags:
            # CROSS_REFERENCE_MISSING / NOT_OBSERVED_OPTIONAL / estados ya
            # degradados: conservan su valor, pero jamas pierden la marca de
            # que su base regulatoria sigue pendiente de reverificacion.
            c = _replace(c, c.conclusion, "SOURCE_PENDING_REVERIFICATION")
        # Conecta el control ya implementado (y hasta ahora sin llamador) que
        # prohibe resultados finales con la fuente PENDING_REVERIFICATION.
        #
        # P3 (2026-07-27): este llamado estaba condicionado a que la
        # conclusion YA estuviera en ALLOWED_RESULTS_WHILE_PENDING_
        # REVERIFICATION, es decir, solo se validaba lo que por definicion
        # iba a pasar -- un resultado final prohibido que se escapara del
        # mapeo _PROVISIONAL_EQUIVALENT quedaba sin validar. La validacion
        # es ahora incondicional salvo para los estados NO finales de abajo.
        from factory.regulatory.requirement_catalog.provisional_evidence_model import (
            validate_result_status_allowed,
        )
        if c.conclusion not in _NON_FINAL_UNDER_PENDING:
            validate_result_status_allowed(
                c.conclusion, "PENDING_REVERIFICATION",
                applicability_determined_by_independent_rule=applicability_rule_approved,
            )
    return c
