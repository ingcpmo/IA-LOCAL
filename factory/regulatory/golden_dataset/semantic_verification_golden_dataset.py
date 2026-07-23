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
  5. Evidencia parcial -> FAIL en D: NOT_APPLICABLE_YET (evidence_min_criteria
     sigue PENDING_HUMAN_INTERPRETATION desde Fase C -- D nunca se evalúa
     con juicio real todavía, ver ABCDResult.d_sufficiency).
  6. Contradicción entre secciones -> chunked_engine.evaluate_chunked
     (detección ya real y probada, test_gmpai_chunked_engine.py).
  7. Ausencia con cobertura incompleta -> absence_consolidator.consolidate
     (coverage_complete=False -> EVALUATION_INCOMPLETE, nunca
     DOCUMENTATION_GAP; regla P3 ya reforzada W5.5).
  8. Evidencia fuera de contexto (tópicamente irrelevante) -> Fase F,
     verify_semantic_relevance (RELEVANCE_REVIEW_REQUIRED).

Este módulo es el punto de entrada reutilizable para el futuro Model
Qualification Gate (MODEL_PROVIDER_AND_LOCAL_AI_RUNTIME_SPEC.md §6):
cualquier cambio de modelo/prompt/schema debe correr run_all() y comparar
contra el baseline de PASS=8/8 ya establecido aquí."""
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
    passed = result.a_anchor == "PASS" and result.c_semantic == "NOT_VERIFIABLE" and not result.accepted
    return GoldenCaseResult(
        "ANNEX11_4_reference_list", "C",
        "Cita anclada dentro de una lista de referencias numeradas nunca debe aceptarse como evidencia sustantiva.",
        expected="C=NOT_VERIFIABLE, accepted=False",
        actual=f"C={result.c_semantic}, accepted={result.accepted}",
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


def _case_partial_evidence_sufficiency() -> GoldenCaseResult:
    result = sev.verify_evidence_abcd(
        "control de acceso mediante autenticacion", "el sistema implementa control de acceso mediante autenticacion",
        "21_CFR_11.10(d)", requirement_terms=["control de acceso"],
    )
    passed = result.d_sufficiency == "NOT_ASSESSABLE"
    return GoldenCaseResult(
        "partial_evidence_sufficiency", "D",
        "Evaluacion de suficiencia por criterio (D) -- NOT_APPLICABLE_YET: "
        "evidence_min_criteria sigue pendiente de interpretacion humana (decision de Fase C). "
        "Este caso NO valida 'FAIL en D -> PARTIALLY_DOCUMENTED' del plan original; "
        "confirma que D nunca se inventa mientras siga pendiente.",
        expected="D=NOT_ASSESSABLE (declarado, no evaluado)",
        actual=f"D={result.d_sufficiency}",
        passed=passed, detail={"status": "NOT_APPLICABLE_YET", "reason": result.d_reason},
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
