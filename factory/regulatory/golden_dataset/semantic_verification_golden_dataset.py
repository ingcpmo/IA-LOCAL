"""W5 V2, Fase G -- Golden Dataset mínimo de validación semántica
(SEMANTIC_EVIDENCE_VERIFICATION_SPEC.md §12.2).

Formaliza los 8 casos negativos obligatorios del plan como casos
ejecutables reales, cada uno reutilizando código YA existente y probado
(nunca reimplementa lógica de validación aquí):

  1. ANNEX11_4 (falso positivo real, lista de referencias) -> Fase F,
     semantic_evidence_verification.detect_reference_list_context.
  2. Cita inventada -> Fase F, verify_anchor.
  3. Evidencia de otro archivo (hash/documento distinto) -> Fase F,
     verify_anchor contra el texto de un documento distinto al reclamado.
  4. Numeral inexistente -> Fase F, verify_regulatory_source.
  5. Evidencia parcial -> D real (PARTIALLY_MET, ver ampliación abajo).
  6. Contradicción entre secciones -> chunked_engine.evaluate_chunked
     (detección ya real y probada, test_gmpai_chunked_engine.py).
  7. Ausencia con cobertura incompleta -> absence_consolidator.consolidate
     (coverage_complete=False -> EVALUATION_INCOMPLETE, nunca
     DOCUMENTATION_GAP; regla P3 ya reforzada W5.5).
  8. Evidencia fuera de contexto (tópicamente irrelevante) -> Fase F,
     verify_semantic_relevance (RELEVANCE_REVIEW_REQUIRED).

Ampliación 2026-07-25 (D real, SUFFICIENCY_VERIFICATION, corrección
completa post-auditoría): el contrato pasó de dos listas separadas
(matched_criteria/unmet_criteria) a un array unificado
`criterion_assessments` (criterion_index/criterion_text/status/
evidence_quote/evidence_location/justification/limitations), con rechazo
ATÓMICO de todo el array ante violaciones de contrato (duplicados, índice
fuera de rango, texto desincronizado, estado inválido, MET sin evidencia/
ubicación) -- ver semantic_evidence_verification.verify_sufficiency().
`substantive_evidence_accepted` (antes `accepted`) es ahora A∧B∧C∧D
INCONDICIONAL, sin excepción para D=NOT_ASSESSABLE.

Casos 9-14 nuevos (sin renumerar los 8 originales; el caso 5 se reescribió
para usar el contrato unificado, misma cobertura conceptual):
MET, NOT_MET, cobertura incompleta -> NOT_ASSESSABLE explícito, criterio
inventado -> rechazo atómico, índice duplicado -> rechazo atómico, MET sin
evidencia/ubicación -> rechazo atómico.

Este módulo es el punto de entrada reutilizable para el futuro Model
Qualification Gate (MODEL_PROVIDER_AND_LOCAL_AI_RUNTIME_SPEC.md §6):
cualquier cambio de modelo/prompt/schema debe correr run_all() y comparar
contra el baseline de PASS=14/14 ya establecido aquí."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from factory.engines.gmpai_integrity import chunked_engine as ce
from factory.regulatory import semantic_evidence_verification as sev
from factory.regulatory.absence_consolidator import consolidate

_PROMPT_PATH = (
    Path(__file__).parent.parent.parent / "engines" / "gmpai_integrity" / "prompts" / "part11_prompts.yaml"
)


@dataclass
class GoldenCaseResult:
    case_id: str
    category: str
    description: str
    expected: str
    actual: str
    passed: bool
    detail: dict = field(default_factory=dict)


class _ContradictionFakeProvider:
    """Provider determinista (Fase D) para el caso 6: dos chunks del mismo
    documento con estados incompatibles para el mismo checkpoint."""

    def __init__(self, responses: list[dict]):
        self._responses = responses
        self._i = 0

    @property
    def model_name(self) -> str:
        return "golden-dataset-fake"

    def generate(self, prompt: str) -> dict:
        import json
        payload = self._responses[min(self._i, len(self._responses) - 1)]
        self._i += 1
        return {"response": json.dumps(payload)}

    def show_digest(self) -> str:
        return "sha256:golden-dataset-fake"

    def runtime_version(self) -> str:
        return "0.0.0-golden"


def _case_annex11_4_reference_list() -> GoldenCaseResult:
    doc = (
        "[6]  21 CFR Part 11 Electronic Records, Electronic Signatures\n"
        "[7]  21 CFR Part 211 Current GMP for finished Pharmaceuticals\n"
        "[8]  Good Automated Manufacturing Practice, Guide for Validation\n"
        "[9]  Control programming specification\n"
    )
    quote = "Good Automated Manufacturing Practice, Guide for Validation"
    result = sev.verify_evidence_abcd(quote, doc, "ANNEX11_4", requirement_terms=["risk", "validation"])
    passed = result.a_anchor == "PASS" and result.c_semantic == "NOT_VERIFIABLE" and not result.substantive_evidence_accepted
    return GoldenCaseResult(
        "ANNEX11_4_reference_list", "C",
        "Cita anclada dentro de una lista de referencias numeradas nunca debe aceptarse como evidencia sustantiva.",
        expected="C=NOT_VERIFIABLE, accepted=False",
        actual=f"C={result.c_semantic}, substantive_evidence_accepted={result.substantive_evidence_accepted}",
        passed=passed, detail={"flags": result.c_flags},
    )


def _case_invented_citation() -> GoldenCaseResult:
    status, match_type = sev.verify_anchor(
        "Esta frase completa jamas aparecio en el documento original.",
        "El documento real contiene texto completamente distinto sin relacion alguna.",
    )
    passed = status == "FAIL"
    return GoldenCaseResult(
        "invented_citation", "A",
        "Una cita inventada (no presente en el documento) debe fallar el anclaje.",
        expected="A=FAIL", actual=f"A={status}", passed=passed,
        detail={"match_type": match_type},
    )


def _case_evidence_from_wrong_document() -> GoldenCaseResult:
    real_quote_from_doc_b = "Procedimiento de calibracion del sensor de temperatura del reactor."
    doc_a_text = "Este documento A trata sobre control de acceso y auditoria de usuarios del sistema SCADA."
    status, match_type = sev.verify_anchor(real_quote_from_doc_b, doc_a_text)
    passed = status == "FAIL"
    return GoldenCaseResult(
        "evidence_from_wrong_document", "A",
        "Evidencia real de OTRO documento (distinto al reclamado) debe fallar el anclaje contra el documento correcto.",
        expected="A=FAIL", actual=f"A={status}", passed=passed,
        detail={"match_type": match_type},
    )


def _case_nonexistent_clause() -> GoldenCaseResult:
    status = sev.verify_regulatory_source("21_CFR_99.99_INEXISTENTE")
    passed = status == "FAIL"
    return GoldenCaseResult(
        "nonexistent_clause", "B",
        "Un numeral/requirement_id inexistente en el catalogo gobernado debe fallar la verificacion de fuente.",
        expected="B=FAIL", actual=f"B={status}", passed=passed,
    )


_ACCESS_CRITERIA = [
    "Mecanismo de control de acceso (propio o federado) sobre el sistema, descrito.",
    "Alta, cambio, revision periodica y revocacion de cuentas.",
    "Cuentas humanas individuales (no compartidas).",
    "Cuentas tecnicas no interactivas, si existen, gobernadas con propietario, proposito, privilegio "
    "minimo y prohibicion de firma electronica.",
    "Evidencia de prueba de acceso permitido y denegado.",
]


def _assessment(index: int, text: str, status: str, quote: str = "", location: str = "") -> dict:
    return {
        "criterion_index": index, "criterion_text": text, "status": status,
        "evidence_quote": quote, "evidence_location": location,
        "justification": "golden dataset", "limitations": "",
    }


def _all_met(criteria=_ACCESS_CRITERIA) -> list:
    return [_assessment(i + 1, c, "MET", quote=c, location="pag 1") for i, c in enumerate(criteria)]


def _all_not_met(criteria=_ACCESS_CRITERIA) -> list:
    return [_assessment(i + 1, c, "NOT_MET") for i, c in enumerate(criteria)]


def _case_partial_evidence_sufficiency() -> GoldenCaseResult:
    """Escenario real 'evidencia parcial' del plan §12.2: 1 de 5 criterios
    minimos confirmado y anclado, los otros 4 declarados explicitamente
    NOT_MET -> PARTIALLY_MET, nunca MET ni substantive_evidence_accepted."""
    quote = _ACCESS_CRITERIA[0]
    doc = f"El sistema implementa lo siguiente: {quote}"
    assessments = [_assessment(1, quote, "MET", quote=quote, location="pag 1")]
    assessments += [_assessment(i + 2, c, "NOT_MET") for i, c in enumerate(_ACCESS_CRITERIA[1:])]
    result = sev.verify_evidence_abcd(
        quote, doc, "21_CFR_11.10(d)", requirement_terms=["control de acceso"],
        criterion_assessments=assessments,
    )
    passed = result.d_sufficiency == "PARTIALLY_MET" and not result.substantive_evidence_accepted
    return GoldenCaseResult(
        "partial_evidence_sufficiency", "D",
        "Evidencia parcial: solo 1 de 5 criterios minimos de evidencia confirmado y anclado -- "
        "D debe quedar PARTIALLY_MET, nunca MET ni substantive_evidence_accepted.",
        expected="D=PARTIALLY_MET, substantive_evidence_accepted=False",
        actual=f"D={result.d_sufficiency}, substantive_evidence_accepted={result.substantive_evidence_accepted}",
        passed=passed, detail=result.d_detail,
    )


def _case_sufficiency_met_all_criteria_anchored() -> GoldenCaseResult:
    doc = " ".join(_ACCESS_CRITERIA)
    status, reason, detail = sev.verify_sufficiency("21_CFR_11.10(d)", _all_met(), doc)
    passed = status == "MET"
    return GoldenCaseResult(
        "sufficiency_met_all_criteria_anchored", "D",
        "Los 5 criterios minimos reales, cada uno MET con cita anclada real -> D=MET.",
        expected="D=MET", actual=f"D={status}", passed=passed, detail=detail,
    )


def _case_sufficiency_not_met_all_criteria_unmet() -> GoldenCaseResult:
    status, reason, detail = sev.verify_sufficiency(
        "21_CFR_11.10(d)", _all_not_met(), "documento sin ninguna evidencia real de control de acceso",
    )
    passed = status == "NOT_MET"
    return GoldenCaseResult(
        "sufficiency_not_met_all_criteria_unmet", "D",
        "Los 5 criterios minimos reales, todos NOT_MET -> D=NOT_MET.",
        expected="D=NOT_MET", actual=f"D={status}", passed=passed, detail=detail,
    )


def _case_sufficiency_incomplete_coverage_stays_not_assessable() -> GoldenCaseResult:
    """Solo 2 de 5 criterios clasificados -- nunca se adivina sobre los 3
    restantes, ni con 1 ya confirmado en MET real."""
    assessments = [
        _assessment(1, _ACCESS_CRITERIA[0], "MET", quote=_ACCESS_CRITERIA[0], location="pag 1"),
        _assessment(2, _ACCESS_CRITERIA[1], "NOT_MET"),
    ]
    status, reason, detail = sev.verify_sufficiency("21_CFR_11.10(d)", assessments, _ACCESS_CRITERIA[0])
    passed = status == "NOT_ASSESSABLE" and len(detail.get("missing", [])) == 3
    return GoldenCaseResult(
        "sufficiency_incomplete_coverage_never_guessed", "D",
        "Cobertura incompleta (2 de 5 criterios clasificados) nunca produce un veredicto de D -- "
        "queda NOT_ASSESSABLE explicito, igual que EVALUATION_INCOMPLETE en absence_consolidator.",
        expected="D=NOT_ASSESSABLE, 3 criterios missing",
        actual=f"D={status}, missing={detail.get('missing')}",
        passed=passed, detail=detail,
    )


def _case_sufficiency_invented_criterion_rejected_atomically() -> GoldenCaseResult:
    """El modelo 'inventa' un criterio fuera de la whitelist real del
    catalogo -- rechazo ATOMICO de todo el array de criterion_assessments
    (nivel de contrato), ni siquiera los 5 reales bien formados se
    rescatan."""
    doc = " ".join(_ACCESS_CRITERIA)
    assessments = _all_met()
    assessments.append(_assessment(6, "Criterio inventado que no existe en el catalogo real", "MET",
                                    quote=doc, location="pag 1"))
    status, reason, detail = sev.verify_sufficiency("21_CFR_11.10(d)", assessments, doc)
    passed = status == "NOT_ASSESSABLE" and bool(detail.get("contract_violations"))
    return GoldenCaseResult(
        "sufficiency_invented_criterion_rejected_atomically", "D",
        "Un criterio fuera de la whitelist real del catalogo (indice fuera de rango) rechaza TODO el "
        "array atomicamente -- nunca se rescatan los criterios reales bien formados.",
        expected="D=NOT_ASSESSABLE, contract_violations no vacio",
        actual=f"D={status}, contract_violations={detail.get('contract_violations')}",
        passed=passed, detail=detail,
    )


def _case_sufficiency_duplicate_criterion_index_rejected_atomically() -> GoldenCaseResult:
    doc = " ".join(_ACCESS_CRITERIA)
    assessments = _all_met()
    assessments.append(_assessment(1, _ACCESS_CRITERIA[0], "MET", quote=_ACCESS_CRITERIA[0], location="pag 1"))
    status, reason, detail = sev.verify_sufficiency("21_CFR_11.10(d)", assessments, doc)
    passed = status == "NOT_ASSESSABLE" and any(
        "duplicado" in v.lower() for v in detail.get("contract_violations", [])
    )
    return GoldenCaseResult(
        "sufficiency_duplicate_criterion_rejected_atomically", "D",
        "criterion_index duplicado en la respuesta del modelo rechaza TODO el array atomicamente.",
        expected="D=NOT_ASSESSABLE, violacion de duplicado registrada",
        actual=f"D={status}, contract_violations={detail.get('contract_violations')}",
        passed=passed, detail=detail,
    )


def _case_sufficiency_met_without_evidence_rejected_atomically() -> GoldenCaseResult:
    """MET sin evidence_quote/evidence_location -- el modelo afirma
    cumplimiento sin aportar la evidencia que la propia respuesta exige
    para ese status -- rechazo atomico, nunca se confia en la sola
    afirmacion."""
    doc = " ".join(_ACCESS_CRITERIA)
    assessments = _all_met()
    assessments[0] = _assessment(1, _ACCESS_CRITERIA[0], "MET")  # sin quote ni location
    status, reason, detail = sev.verify_sufficiency("21_CFR_11.10(d)", assessments, doc)
    passed = status == "NOT_ASSESSABLE" and any(
        "evidence_quote" in v or "evidence_location" in v for v in detail.get("contract_violations", [])
    )
    return GoldenCaseResult(
        "sufficiency_met_without_evidence_rejected_atomically", "D",
        "status=MET sin evidence_quote/evidence_location rechaza TODO el array atomicamente.",
        expected="D=NOT_ASSESSABLE, violacion de MET-sin-evidencia registrada",
        actual=f"D={status}, contract_violations={detail.get('contract_violations')}",
        passed=passed, detail=detail,
    )


def _case_contradiction_between_sections() -> GoldenCaseResult:
    meta = ce.load_prompt_meta(_PROMPT_PATH)
    req_id = meta["checkpoints"][0]["req_id"]

    # Evidencia con solapamiento lexico real con el label del checkpoint
    # ("Validacion del sistema (accuracy/reliability)") -- necesario para
    # pasar _is_topically_relevant() de chunked_engine.py, ademas del
    # anclaje literal.
    quote = "The system was validated to ensure accuracy and reliability of records."

    def _payload(estado: str) -> dict:
        return {"checkpoints": [
            {"req_id": cp["req_id"],
             "estado": estado if cp["req_id"] == req_id else "evidencia_insuficiente",
             "evidencia_exacta": quote if estado != "evidencia_insuficiente" else "",
             "brecha": "n/a", "recomendacion": "n/a"}
            for cp in meta["checkpoints"]
        ]}

    # Cada pagina debe superar CHUNK_MAX_CHARS por si sola para forzar 2
    # chunks reales separados (build_page_chunks fusiona paginas cortas en
    # un unico chunk, lo que haria imposible una contradiccion entre
    # "secciones" -- solo habria una llamada al provider).
    pages = [
        f"Pagina 1. {quote} " * 400,
        f"Pagina 2. {quote} " * 400,
    ]
    provider = _ContradictionFakeProvider([_payload("cumple"), _payload("no_cumple")])
    result = ce.evaluate_chunked(
        _PROMPT_PATH, agent_id="golden_dataset", agent_version="v-golden",
        per_unit_text=pages, sistema="sys", documento="doc-contradiccion", version="v1",
        archivo="doc.pdf", document_sha256="c" * 64,
        run_context="validation", provider=provider,
    )
    findings_for_req = [f for f in result["findings"] if f["requisito_regulatorio"].startswith(req_id)]
    contradiction_found = bool(result["contradictions"])
    blocked_positive = all(f["estado"] != "cumple" or f.get("revision_humana_requerida") for f in findings_for_req)
    passed = contradiction_found and blocked_positive
    return GoldenCaseResult(
        "contradiction_between_sections", "pipeline",
        "Estados incompatibles (cumple vs no_cumple) para el mismo checkpoint en distintas secciones "
        "deben registrarse como contradiccion abierta, nunca resolverse en silencio a una conclusion positiva.",
        expected="contradictions no vacio, ninguna conclusion positiva sin revision humana",
        actual=f"contradictions={result['contradictions']}",
        passed=passed,
    )


def _case_incomplete_coverage_never_documentation_gap() -> GoldenCaseResult:
    not_observed_record = {
        "record_id": "vrec-1", "llm_output": {"chunk_observation": "not_observed_in_chunk"},
        "status": "verified", "rejection_reason": None, "review_flags": [],
    }
    conclusion = consolidate(
        "21_CFR_11.10(a)", "FS", "expected", [not_observed_record], coverage_complete=False,
    )
    passed = conclusion.conclusion == "EVALUATION_INCOMPLETE"
    return GoldenCaseResult(
        "incomplete_coverage_never_gap", "pipeline",
        "Ausencia con cobertura incompleta (coverage_complete=False) nunca debe concluir DOCUMENTATION_GAP.",
        expected="EVALUATION_INCOMPLETE", actual=conclusion.conclusion,
        passed=passed, detail={"review_flags": conclusion.review_flags},
    )


def _case_evidence_out_of_context() -> GoldenCaseResult:
    doc = "El manual describe el color y las dimensiones fisicas del gabinete metalico del panel electrico."
    quote = "el color y las dimensiones fisicas del gabinete metalico"
    status, flags = sev.verify_semantic_relevance(quote, doc, requirement_terms=["audit trail", "timestamp", "firma electronica"])
    passed = status == "NOT_VERIFIABLE" and "RELEVANCE_REVIEW_REQUIRED" in flags
    return GoldenCaseResult(
        "evidence_out_of_context", "C",
        "Cita anclada pero tematicamente ajena al requisito debe marcarse para revision, nunca aceptarse.",
        expected="C=NOT_VERIFIABLE con RELEVANCE_REVIEW_REQUIRED",
        actual=f"C={status}, flags={flags}",
        passed=passed,
    )


_ALL_CASES = [
    _case_annex11_4_reference_list,
    _case_invented_citation,
    _case_evidence_from_wrong_document,
    _case_nonexistent_clause,
    _case_partial_evidence_sufficiency,
    _case_contradiction_between_sections,
    _case_incomplete_coverage_never_documentation_gap,
    _case_evidence_out_of_context,
    _case_sufficiency_met_all_criteria_anchored,
    _case_sufficiency_not_met_all_criteria_unmet,
    _case_sufficiency_incomplete_coverage_stays_not_assessable,
    _case_sufficiency_invented_criterion_rejected_atomically,
    _case_sufficiency_duplicate_criterion_index_rejected_atomically,
    _case_sufficiency_met_without_evidence_rejected_atomically,
]


def run_all() -> list[GoldenCaseResult]:
    return [case() for case in _ALL_CASES]


def summarize(results: list[GoldenCaseResult]) -> dict:
    return {
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "failed_case_ids": [r.case_id for r in results if not r.passed],
    }
