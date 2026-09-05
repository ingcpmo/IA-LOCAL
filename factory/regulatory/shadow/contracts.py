"""SHADOW · G2 — Contratos de entrada/salida por experto + evaluación de reutilización.

Define, de forma declarativa y verificable por estructura:

  1. MUST_NOT_CHANGE_FIELDS  — los campos L2 inmutables que el verificador
     determinista de G3 re-comprueba byte a byte contra
     `FINAL_GMP_CORPUS_FINDINGS.json`. Si la envoltura de salida de un experto
     no los reproduce EXACTOS -> SHADOW_REJECTED.
  2. ASSESSMENT_VALUES        — enum de `assessment` POR experto. Ninguno
     contiene un veredicto de cumplimiento (COMPLIANT / APPROVED /
     MACHINE_CONFIRMED …): el shadow OPINA, no adjudica (CLAUDE.md, corr. 3).
  3. INPUT_CONTEXT_SPEC       — claves de contexto acotado que cada experto
     recibe. El paquete NUNCA incluye el PDF de cliente, el canonical_store
     completo, ni datos de otro finding más allá de lo declarado.
  4. build_input_package()    — ensambla la envoltura acotada desde un finding
     L2 (dict) + un contexto; copia SOLO los campos whitelisted de L2.
  5. validate_output_envelope() — validación ESTRUCTURAL (no de anclaje):
     assessment ∈ enum, MUST_NOT_CHANGE presente e idéntico a L2, marca
     [SHADOW], referencias externas nunca marcadas CLIENT_EVIDENCE. El anclaje
     real de citas contra L1/L2 lo hace el verificador fail-closed de G3.
  6. REUSE_EVALUATION         — veredicto de reutilización selectiva de
     `factory/regulatory/v2_judgment/*` frente al contrato de INTERPRETACIÓN.

CERO LLM · CERO red · solo estructura. No muta ningún Finding.
"""
from __future__ import annotations

from collections import OrderedDict

# ── 1 · campos L2 inmutables (frontera dura) ────────────────────────────
#: el verificador de G3 los re-lee de FINAL_GMP_CORPUS_FINDINGS.json y exige
#: igualdad exacta con el bloque MUST_NOT_CHANGE de la envoltura del experto.
MUST_NOT_CHANGE_FIELDS = (
    "finding_record_id",
    "finding_class",
    "subtype",
    "severity",
    "risk_band",
    "requirement_id",
    "machine_state",
    "human_state",
    "document",
    "page",
    "source_hash",
    # shadow-G2-r1 (carry-forward de la auditoría de G2): `related_finding_ids` es
    # un campo de L2 y la capa shadow no lo escribe (corr. 2). Se añade al bloque
    # inmutable para que el verificador fail-closed rechace cualquier envoltura
    # que lo altere.
    "related_finding_ids",
)

#: nunca deben aparecer como valor de `assessment` en ningún experto —
#: son conclusiones de cumplimiento/adjudicación, prohibidas al shadow.
FORBIDDEN_ASSESSMENT_TOKENS = (
    "COMPLIANT", "NON_COMPLIANT", "APPROVED", "REJECTED", "PASS", "FAIL",
    "MACHINE_CONFIRMED", "SATISFIES", "RELEASED", "CAPA_CLOSED", "OBSERVED",
)

SHADOW_MARK = "[SHADOW / NO GOBERNADO]"
CLIENT_EVIDENCE = "CLIENT_EVIDENCE"
EXTERNAL_REG_REFERENCE = "EXTERNAL_REG_REFERENCE"

EXPERTS = ("REGULATORY", "FUNCTIONAL_TRACEABILITY", "TECHNICAL", "CROSS_DOMAIN", "COMPOSER")

# ── 2 · enum de assessment por experto (OPINIÓN, no veredicto) ───────────
ASSESSMENT_VALUES = {
    # triage de los <=5 candidatos de recuperación — NUNCA juicio de cumplimiento
    "REGULATORY": (
        "CANDIDATE_RANKING_PROVIDED",   # el experto ordenó los candidatos para el revisor
        "NO_USEFUL_CANDIDATE",          # ninguno de los <=5 parece pertinente
        "NEEDS_HUMAN_SEARCH",           # el revisor debe buscar fuera del bundle
    ),
    "FUNCTIONAL_TRACEABILITY": (
        "LIKELY_REAL_GAP",              # la ausencia de arista parece real
        "LIKELY_EXTRACTION_LIMIT",      # el id existe pero la arista no se trazó
        "INDETERMINATE",
    ),
    "TECHNICAL": (
        "BEHAVIOR_LIKELY_PRESENT_PARAPHRASED",  # el comportamiento requerido parece estar, parafraseado
        "BEHAVIOR_NOT_FOUND_IN_SCOPE",          # no se encontró en el alcance context-scoped
        "INDETERMINATE",
    ),
    "CROSS_DOMAIN": (
        "RECONCILED_CONSISTENT",        # gap técnico e INCONCLUSIVE regulatorio son coherentes
        "DISAGREEMENT_PERSISTS",        # -> HUMAN_REVIEW_REQUIRED (nunca se resuelve solo)
        "INDETERMINATE",
    ),
    "COMPOSER": (
        "NARRATIVE_DRAFTED",            # compuso el borrador narrativo
        "NARRATIVE_BLOCKED",            # no pudo anclar cobertura 457/457 -> a revisión
    ),
}

#: CROSS_DOMAIN == DISAGREEMENT_PERSISTS obliga a marcar la relación
#: HUMAN_REVIEW_REQUIRED en shadow/cross_domain_links.json (G3).
CROSS_DOMAIN_HUMAN_REVIEW_TRIGGER = "DISAGREEMENT_PERSISTS"

# ── 3 · contexto acotado por experto ───────────────────────────────────
INPUT_CONTEXT_SPEC = {
    "REGULATORY": (
        "subcriterion_ref",            # id del sub-criterio firmado
        "subcriterion_text",           # texto gobernado (ES + glosa EN)
        "requirement_terms",           # requirement_terms.yaml (catálogo, no LLM)
        "candidate_claims",            # <=5 de EvidenceBundle: {claim_id, source_text, pagina, section_id, bm25_score, rerank_score, provenance}
    ),
    "FUNCTIONAL_TRACEABILITY": (
        "anchored_source_text",        # cita literal del claim/test ancla
        "graph_path",                  # snapshot ref + edge_family_checked
        "reference_ids",               # ids de referencia del claim (UR#, F#, …)
        "neighbor_claims",             # claims del mismo doc que citan esos ids
        "downstream_claims",           # claims de FS/DS/SAT que citan esos ids
    ),
    "TECHNICAL": (
        "case_id",                     # CASE_ID de technical_completeness_rules.yaml (SIGNED)
        "control_objective",
        "required_behavior",
        "source_requirement_id",
        "scope_claims",                # sección ancla + subsecciones relacionadas + xref
        "family_signals",              # señales de familia de la regla
    ),
    "CROSS_DOMAIN": (
        "technical_finding_package",   # envoltura del finding técnico
        "regulatory_counterpart_packages",  # envolturas de los INCONCLUSIVE del mismo doc/regla
        "prior_expert_opinions",       # opiniones verificadas de TECHNICAL y REGULATORY (shadow/expert_*.json)
        "shared_regulations",          # tokens de regulación compartidos (de G1 routing)
    ),
    "COMPOSER": (
        "verified_expert_opinions",    # todas las opiniones que pasaron el verificador de G3
        "l2_findings",                 # las 457 filas L2 completas (FINAL_GMP_CORPUS_FINDINGS.json)
        "routing",                     # G1_routing.json
    ),
}

# ── campos L2 que SÍ viajan en el snapshot de la envoltura (whitelist) ──
_L2_SNAPSHOT_FIELDS = MUST_NOT_CHANGE_FIELDS + (
    "section", "anchored_quote", "evidence_basis", "rationale_l2",
)

#: lo que NUNCA entra al paquete (exclusión dura).
FORBIDDEN_PACKAGE_KEYS = (
    "pdf", "pdf_bytes", "canonical_store", "raw_document", "full_text",
    "graph_store", "other_findings",
)


class ContractError(ValueError):
    pass


def _l2_snapshot(finding: dict) -> "OrderedDict[str, object]":
    def g(k):
        if k == "finding_class":
            return finding.get("class") or finding.get("finding_class")
        if k == "requirement_id":
            return finding.get("requirement") or finding.get("requirement_id")
        if k == "risk_band":
            return (finding.get("risk") or {}).get("band")
        if k == "related_finding_ids":
            return list(finding.get("related_finding_ids") or [])
        if k == "anchored_quote":
            return (finding.get("evidence") or {}).get("anchored_quote") or finding.get("source_text")
        if k == "rationale_l2":
            return finding.get("rationale")
        return finding.get(k)
    return OrderedDict((k, g(k)) for k in _L2_SNAPSHOT_FIELDS)


def must_not_change_block(finding: dict) -> "OrderedDict[str, object]":
    """Bloque que el experto debe REPRODUCIR verbatim en su envoltura de salida."""
    snap = _l2_snapshot(finding)
    return OrderedDict((k, snap[k]) for k in MUST_NOT_CHANGE_FIELDS)


def build_input_package(finding: dict, expert: str, context: dict, *,
                        provenance: dict | None = None) -> dict:
    """Envoltura de entrada ACOTADA y trazable para un experto.

    Copia SOLO los campos whitelisted de L2 + el contexto declarado en
    INPUT_CONTEXT_SPEC[expert]. Falla si falta una clave de contexto o si el
    contexto trae una clave prohibida.
    """
    if expert not in EXPERTS:
        raise ContractError(f"experto desconocido: {expert!r}")
    required = INPUT_CONTEXT_SPEC[expert]
    missing = [k for k in required if k not in context]
    if missing:
        raise ContractError(f"{expert}: faltan claves de contexto {missing}")
    bad = [k for k in context if k in FORBIDDEN_PACKAGE_KEYS]
    if bad:
        raise ContractError(f"{expert}: contexto con claves prohibidas {bad}")
    return {
        "schema": "SHADOW_INPUT_PACKAGE/v1",
        "expert": expert,
        "finding_record_id": finding["finding_record_id"],
        "l2_snapshot": dict(_l2_snapshot(finding)),
        "MUST_NOT_CHANGE": dict(must_not_change_block(finding)),
        "context": {k: context[k] for k in required},
        "provenance": dict(provenance or {}),
        "network": "LOCAL_ONLY",
        "note": ("Paquete acotado. El experto NO ve el PDF de cliente ni el "
                 "canonical_store completo. Su salida es OPINIÓN (L3), no cambia L2."),
    }


def validate_output_envelope(envelope: dict, *, l2_finding: dict) -> list[str]:
    """Validación ESTRUCTURAL de la envoltura de salida de un experto (G2).

    NO verifica el anclaje real de las citas contra L1/L2 — eso es el
    verificador fail-closed de G3. Devuelve lista de violaciones (vacía = ok).
    """
    v: list[str] = []
    expert = envelope.get("expert")
    if expert not in EXPERTS:
        return [f"expert desconocido: {expert!r}"]

    a = envelope.get("assessment")
    if a not in ASSESSMENT_VALUES[expert]:
        v.append(f"assessment {a!r} no ∈ {ASSESSMENT_VALUES[expert]}")
    if isinstance(a, str) and any(tok in a.upper() for tok in FORBIDDEN_ASSESSMENT_TOKENS):
        v.append(f"assessment contiene token de cumplimiento prohibido: {a!r}")

    mnc = envelope.get("MUST_NOT_CHANGE")
    if not isinstance(mnc, dict):
        v.append("MUST_NOT_CHANGE ausente o no es objeto")
    else:
        expected = must_not_change_block(l2_finding)
        for k in MUST_NOT_CHANGE_FIELDS:
            if mnc.get(k) != expected[k]:
                v.append(f"MUST_NOT_CHANGE.{k} = {mnc.get(k)!r} != L2 {expected[k]!r}")

    if envelope.get("finding_record_id") != l2_finding.get("finding_record_id"):
        v.append("finding_record_id de la envoltura != L2")

    rationale = envelope.get("rationale") or ""
    if expert != "COMPOSER" and SHADOW_MARK not in rationale:
        v.append(f"rationale sin marca {SHADOW_MARK!r}")

    cites = envelope.get("anchored_citations")
    if not isinstance(cites, list):
        v.append("anchored_citations ausente o no es lista")
    else:
        for i, c in enumerate(cites):
            if not isinstance(c, dict) or not (c.get("quote") or "").strip():
                v.append(f"anchored_citations[{i}] sin `quote`")
            if c.get("source") not in (CLIENT_EVIDENCE, None):
                v.append(f"anchored_citations[{i}].source inválido: {c.get('source')!r}")

    for i, r in enumerate(envelope.get("external_reg_references") or []):
        if not isinstance(r, dict):
            v.append(f"external_reg_references[{i}] no es objeto")
            continue
        if r.get("source") == CLIENT_EVIDENCE:
            v.append(f"external_reg_references[{i}] marcada CLIENT_EVIDENCE (prohibido)")
        for k in ("regulation", "retrieved_at"):
            if not r.get(k):
                v.append(f"external_reg_references[{i}] sin `{k}`")

    model = envelope.get("model") or {}
    if model.get("provider") != "LOCAL":
        v.append(f"model.provider != LOCAL: {model.get('provider')!r}")
    for k in ("model_name", "digest", "prompt_id", "prompt_version"):
        if not model.get(k):
            v.append(f"model.{k} ausente")

    if envelope.get("confidence") not in ("LOW", "MEDIUM", "HIGH"):
        v.append(f"confidence inválida: {envelope.get('confidence')!r}")

    return v


# ── 6 · evaluación de reutilización selectiva de v2_judgment ────────────
# Veredictos permitidos: REUSE | REUSE_WITH_ADAPTATION | DISCARD
REUSE_EVALUATION = OrderedDict([
    ("factory/regulatory/v2_judgment/... — evaluación frente al contrato de INTERPRETACIÓN", None),
    ("model_provider.ModelProvider (Protocol) + OllamaProvider", {
        "verdict": "REUSE",
        "why": ("abstracción de modelo intercambiable (corr. 4): generate(prompt, num_predict), "
                "show_digest(), runtime_version(), model_name. Es exactamente lo que la capa "
                "shadow necesita para trazar `model` en la envoltura. Se CONGELA como abstracción; "
                "el modelo concreto (7B) es candidato de piloto, no arquitectónico."),
    }),
    ("engines.gmpai_integrity.ollama_client.generate()", {
        "verdict": "REUSE",
        "why": ("canal 1 LOCAL, httpx directo, temperature 0, format:json, timeouts/reintentos ya "
                "probados. La generación simple sirve para producir OPINIÓN."),
    }),
    ("engines.gmpai_integrity.ollama_client.generate_controlled()", {
        "verdict": "DISCARD",
        "why": ("fuerza el schema `finding_llm_v1` de EVIDENCIA regulatoria (semántica de "
                "adjudicación). El shadow produce opinión con su propio envelope, no evidencia."),
    }),
    ("v2_judgment.prompts (load_prompt / is_signed / assert_all_signed / render / temperature)", {
        "verdict": "REUSE",
        "why": ("infra de carga/render/firma de prompts YAML, reutilizable tal cual para los "
                "prompts de INTERPRETACIÓN nuevos que se firmarán antes de G4."),
    }),
    ("v2_judgment prompts de contenido: step_a / step_b(_nonstrict) / critic (v2_draft/*.yaml)", {
        "verdict": "DISCARD",
        "why": ("hoy status=SIGNED, pero su tarea es JUZGAR un sub-criterio (SATISFIES/PARTIAL/NO). "
                "El shadow no juzga cumplimiento -> se necesitan prompts nuevos de interpretación "
                "asistida (triage regulatorio, gap vs límite de extracción, comportamiento "
                "parafraseado, reconciliación cross-domain)."),
    }),
    ("evidence_verifier.match_citation / relevance_score / verify_llm_output / load_requirement_terms", {
        "verdict": "REUSE",
        "why": ("núcleo determinista de anclaje de cita (exact/normalized/despaced/fuzzy>=0.93). "
                "Es la base del verificador fail-closed de G3: '¿la cita del experto existe "
                "literalmente en L1/L2?'. FUZZY_THRESHOLD y umbrales NO se tocan."),
    }),
    ("judgment_v2._extract_json / _resp_text / _claims_index", {
        "verdict": "REUSE",
        "why": "helpers puros de parseo de respuesta del modelo, sin semántica de adjudicación.",
    }),
    ("judgment_v2.evaluate_bundle (orquestador A->B->verify->critic->adjudicator)", {
        "verdict": "DISCARD",
        "why": ("ensambla un VEREDICTO de cumplimiento por sub-criterio (MACHINE_CONFIRMED = "
                "'el sub-criterio se cumple'). Incompatible con 'el shadow no concluye "
                "cumplimiento' (corr. 5). Se reutiliza el PATRÓN (paso A neutro; verificación de "
                "cita; parseo), no el ensamblaje ni su salida."),
    }),
    ("v2_judgment.adjudicator.adjudicate + estados (MACHINE_CONFIRMED / EVIDENCE_NOT_FOUND / …)", {
        "verdict": "DISCARD",
        "why": ("los estados son conclusiones de cumplimiento del sub-criterio. El shadow usa su "
                "propio enum ASSESSMENT_VALUES (opinión, no veredicto)."),
    }),
    ("v2_judgment.critic.review + CriticResult (AGREE/DISAGREE/CANNOT_CONFIRM)", {
        "verdict": "REUSE_WITH_ADAPTATION",
        "why": ("el PATRÓN 'segunda lectura adversarial que SOLO degrada, fail-closed hacia la "
                "duda' es muy valioso para el shadow. El enum (AGREE = confirmo cumplimiento) es "
                "de adjudicación -> se adapta a un enum de duda sobre la OPINIÓN, no sobre el "
                "cumplimiento."),
    }),
    ("judgment_v2.SubcriterionVerdict / CandidateOutcome (dataclasses)", {
        "verdict": "DISCARD",
        "why": ("modelan un veredicto de cumplimiento por sub-criterio. El shadow modela una "
                "opinión por finding -> estructura nueva (esta envoltura de G2)."),
    }),
])


def reuse_summary() -> dict:
    counts: "OrderedDict[str, int]" = OrderedDict(
        REUSE=0, REUSE_WITH_ADAPTATION=0, DISCARD=0)
    for k, val in REUSE_EVALUATION.items():
        if not val:
            continue
        counts[val["verdict"]] = counts.get(val["verdict"], 0) + 1
    return dict(counts)


def contract_spec() -> dict:
    """Volcado machine-readable del contrato (artefacto congelado de G2)."""
    return {
        "schema": "SHADOW_G2_CONTRACTS/v1",
        "experts": list(EXPERTS),
        "must_not_change_fields": list(MUST_NOT_CHANGE_FIELDS),
        "forbidden_assessment_tokens": list(FORBIDDEN_ASSESSMENT_TOKENS),
        "assessment_values": {k: list(v) for k, v in ASSESSMENT_VALUES.items()},
        "input_context_spec": {k: list(v) for k, v in INPUT_CONTEXT_SPEC.items()},
        "l2_snapshot_fields": list(_L2_SNAPSHOT_FIELDS),
        "forbidden_package_keys": list(FORBIDDEN_PACKAGE_KEYS),
        "shadow_mark": SHADOW_MARK,
        "cross_domain_human_review_trigger": CROSS_DOMAIN_HUMAN_REVIEW_TRIGGER,
        "output_envelope_required_keys": [
            "schema", "expert", "finding_record_id", "shadow_layer", "assessment",
            "rationale", "anchored_citations", "MUST_NOT_CHANGE", "confidence",
            "model", "produced_at",
        ],
        "output_envelope_optional_keys": ["external_reg_references", "ranked_candidate_claim_ids"],
        "reuse_evaluation": {k: v for k, v in REUSE_EVALUATION.items() if v},
        "reuse_summary": reuse_summary(),
        "verification_note": ("G2 define y valida ESTRUCTURA. El anclaje real de citas contra "
                              "L1/L2 y el fail-closed SHADOW_REJECTED son G3."),
    }


if __name__ == "__main__":  # pragma: no cover
    import json
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "docs_plan/shadow_llm/G2_contracts.json"
    open(out, "w", encoding="utf-8").write(json.dumps(contract_spec(), indent=1, ensure_ascii=False))
    print("WROTE", out)
    print(json.dumps({"experts": list(EXPERTS), "reuse_summary": reuse_summary()},
                     indent=1, ensure_ascii=False))
