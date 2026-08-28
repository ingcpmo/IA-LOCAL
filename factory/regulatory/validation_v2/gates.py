"""Evaluadores de gate deterministas (V2, B8) -- FASE 10 §2.

Dado el resultado por caso de una suite, computa las métricas y las
compara contra los umbrales fijados en
docs_plan/PLAN_VALIDACION_ANALIZADOR_GMP_LOCAL_V2.md §2. Sin LLM.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Umbrales (PLAN_VALIDACION §2). No se relajan aquí -- cambiarlos es
# decisión de Capa 9 en el propio plan.
REGULATORY_POSITIVE_MIN = 6        # de 7
REGULATORY_NEGATIVE_REQUIRED = 2  # de 2
FABRICATED_CITATIONS_MAX = 0
FUNCTIONAL_RECALL_MIN = 0.90
FUNCTIONAL_FP_MAX = 0.05
TECHNICAL_RECALL_MIN = 0.90
TECHNICAL_FP_MAX = 0.05


@dataclass
class GateResult:
    name: str
    value: object
    threshold: object
    passed: bool
    detail: str = ""


@dataclass
class GateReport:
    suite: str
    gates: list = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(g.passed for g in self.gates)

    def as_dict(self) -> dict:
        return {
            "suite": self.suite,
            "all_passed": self.all_passed,
            "gates": [g.__dict__ for g in self.gates],
        }


# ── Suite A -- Regulatory ───────────────────────────────────────────────

def evaluate_regulatory(case_results: list[dict]) -> GateReport:
    """`case_results`: [{case_id, kind: 'positive'|'negative',
    anchored: bool, fabricated_citation: bool, schema_valid: bool,
    latency_s: float|None}].
    - positive anclado con cita válida cuenta para REGULATORY_POSITIVE.
    - negative correctamente NO anclado cuenta para REGULATORY_NEGATIVE.
    """
    pos = [c for c in case_results if c["kind"] == "positive"]
    neg = [c for c in case_results if c["kind"] == "negative"]
    pos_ok = sum(1 for c in pos if c.get("anchored") and not c.get("fabricated_citation"))
    neg_ok = sum(1 for c in neg if not c.get("anchored"))
    fabricated = sum(1 for c in case_results if c.get("fabricated_citation"))
    schema_bad = sum(1 for c in case_results if c.get("schema_valid") is False)

    g = [
        GateResult("REGULATORY_POSITIVE", f"{pos_ok}/{len(pos)}",
                   f">={REGULATORY_POSITIVE_MIN}/7", pos_ok >= REGULATORY_POSITIVE_MIN),
        GateResult("REGULATORY_NEGATIVE", f"{neg_ok}/{len(neg)}",
                   f"=={REGULATORY_NEGATIVE_REQUIRED}/2", neg_ok >= REGULATORY_NEGATIVE_REQUIRED),
        GateResult("FABRICATED_CITATIONS", fabricated, f"=={FABRICATED_CITATIONS_MAX}",
                   fabricated == FABRICATED_CITATIONS_MAX,
                   "una sola cita fabricada que pasa es FALLO DURO"),
        GateResult("SCHEMA_VALID_RATE", f"{len(case_results) - schema_bad}/{len(case_results)}",
                   "100%", schema_bad == 0),
    ]
    lat = [c["latency_s"] for c in case_results if c.get("latency_s") is not None]
    g.append(GateResult("LATENCIA_POR_LLAMADA",
                        f"registrada ({len(lat)}/{len(case_results)})", "registrada", bool(lat) or not case_results,
                        "no es gate, es dato obligatorio"))
    return GateReport("A_regulatory", g)


# ── Suites B/C -- recall + falsos positivos ─────────────────────────────

def _recall_fp(case_results: list[dict]) -> tuple[float, float, int, int, int, int]:
    """case_results: [{case_id, expected_finding: bool, emitted_finding: bool,
    subtype_match: bool}]. Devuelve (recall, fp_rate, tp, fn, fp, emitted)."""
    expected = [c for c in case_results if c.get("expected_finding")]
    tp = sum(1 for c in expected if c.get("emitted_finding") and c.get("subtype_match", True))
    fn = len(expected) - tp
    emitted = [c for c in case_results if c.get("emitted_finding")]
    fp = sum(1 for c in emitted if not c.get("expected_finding"))
    recall = (tp / len(expected)) if expected else 1.0
    fp_rate = (fp / len(emitted)) if emitted else 0.0
    return recall, fp_rate, tp, fn, fp, len(emitted)


def evaluate_functional(case_results: list[dict]) -> GateReport:
    recall, fp_rate, tp, fn, fp, emitted = _recall_fp(case_results)
    return GateReport("B_functional", [
        GateResult("FUNCTIONAL_RECALL", round(recall, 3), f">={FUNCTIONAL_RECALL_MIN}",
                   recall >= FUNCTIONAL_RECALL_MIN, f"tp={tp} fn={fn}"),
        GateResult("FUNCTIONAL_FALSE_POSITIVE", round(fp_rate, 3), f"<={FUNCTIONAL_FP_MAX}",
                   fp_rate <= FUNCTIONAL_FP_MAX, f"fp={fp} emitidos={emitted}"),
    ])


def evaluate_technical(case_results: list[dict]) -> GateReport:
    recall, fp_rate, tp, fn, fp, emitted = _recall_fp(case_results)
    return GateReport("C_technical", [
        GateResult("TECHNICAL_RECALL", round(recall, 3), f">={TECHNICAL_RECALL_MIN}",
                   recall >= TECHNICAL_RECALL_MIN, f"tp={tp} fn={fn}"),
        GateResult("TECHNICAL_FALSE_POSITIVE", round(fp_rate, 3), f"<={TECHNICAL_FP_MAX}",
                   fp_rate <= TECHNICAL_FP_MAX, f"fp={fp} emitidos={emitted}"),
    ])


# ── Transversales ──────────────────────────────────────────────────────

def evaluate_transversal(*, local_only: bool, document_egress_bytes: int,
                         human_gate_intact: bool, audit_chain_status: str,
                         gate0_factory_pass: bool,
                         traceability_complete: bool) -> GateReport:
    return GateReport("transversal", [
        GateResult("LOCAL_ONLY", local_only, "YES", local_only is True),
        GateResult("DOCUMENT_EGRESS", document_egress_bytes, "0", document_egress_bytes == 0),
        GateResult("HUMAN_GATE_INTACT", human_gate_intact, "YES", human_gate_intact is True),
        GateResult("AUDIT_CHAIN", audit_chain_status,
                   "VERIFIED | ACCEPTED_WITH_DOCUMENTED_EXCEPTION",
                   audit_chain_status in ("VERIFIED", "ACCEPTED_WITH_DOCUMENTED_EXCEPTION")),
        GateResult("GATE_0_FACTORY", gate0_factory_pass, "PASS", gate0_factory_pass is True),
        GateResult("TRACEABILITY_COMPLETE", traceability_complete, "YES",
                   traceability_complete is True),
    ])


# ── Interpretación de Suite A (PLAN_VALIDACION §2.1) ────────────────────

def interpret_regulatory(report: GateReport) -> str:
    pos_gate = next(g for g in report.gates if g.name == "REGULATORY_POSITIVE")
    fab_gate = next(g for g in report.gates if g.name == "FABRICATED_CITATIONS")
    neg_gate = next(g for g in report.gates if g.name == "REGULATORY_NEGATIVE")
    pos_ok = int(str(pos_gate.value).split("/")[0])
    if not fab_gate.passed or not neg_gate.passed:
        return "FALLO_DURO -- cita fabricada o negativo no rechazado; el cambio se revierte"
    if pos_ok >= REGULATORY_POSITIVE_MIN:
        return "V2_RESUELVE_RECALL -- proceder a cutover (decisión de Capa 9)"
    if pos_ok >= 4:
        return "MEJORA_INSUFICIENTE -- presentar a Capa 9: iterar o adoptar Tier-1 para Regulatory"
    return "TECHO_NO_CRUZADO -- adoptar Palanca C (Tier-1) permanente para la clase Regulatory; no degradar validadores"
