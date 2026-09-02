# SHADOW · G2 — CONTRATOS DE EXPERTO + EVALUACIÓN DE REUTILIZACIÓN

**Arco:** Capa LLM de interpretación sobre findings deterministas (diseño v1.1).
**Fase:** G2 — contratos de entrada/salida por experto (paquete acotado y trazable; `assessment ∈ enum`;
bloque `MUST_NOT_CHANGE`) + evaluación de qué piezas de `v2_judgment` cumplen el contrato de
*interpretación* (reutilización selectiva). **Sin ejecutar nada.**
**Modo:** SIN LLM · SIN red · solo estructura · SIN mover el `FINDINGS_FINGERPRINT`.
**Rama:** `shadow/llm-interpretation-layer` · **Base de fase:** `shadow-G1` → `3ccc485`.
**Gate previo:** G1 aprobado.

---

## 1 · Qué produce G2

| Artefacto | Ruta | Naturaleza |
|---|---|---|
| Contratos (módulo) | `factory/regulatory/shadow/contracts.py` | declaraciones + validador ESTRUCTURAL (no de anclaje), CERO LLM/red |
| Test | `factory/tests/test_shadow_contracts.py` | 16 tests |
| Contratos congelados | `docs_plan/shadow_llm/G2_contracts.json` | volcado machine-readable del contrato + evaluación de reutilización |

**G2 no ejecuta ningún modelo ni pipeline.** El validador solo comprueba la *forma* de una
envoltura de salida (dict). El anclaje real de citas contra L1/L2 y el fail-closed
`SHADOW_REJECTED` son **G3**.

---

## 2 · Frontera dura — `MUST_NOT_CHANGE`

Campos L2 inmutables que el verificador de G3 re-lee de `FINAL_GMP_CORPUS_FINDINGS.json` y exige
**idénticos** en el bloque `MUST_NOT_CHANGE` de la envoltura de cada experto. Cualquier
divergencia ⇒ `SHADOW_REJECTED`, el finding no entra al reporte narrativo.

```
finding_record_id · finding_class · subtype · severity · risk_band · requirement_id ·
machine_state · human_state · document · page · source_hash
```

Prohibido como valor de `assessment` en cualquier experto (tokens de cumplimiento/adjudicación):
`COMPLIANT · NON_COMPLIANT · APPROVED · REJECTED · PASS · FAIL · MACHINE_CONFIRMED · SATISFIES ·
RELEASED · CAPA_CLOSED · OBSERVED` (test `test_no_expert_assessment_is_a_compliance_verdict`).

---

## 3 · Contrato de ENTRADA (paquete acotado y trazable)

Envoltura común (`build_input_package`):

```
{
  "schema": "SHADOW_INPUT_PACKAGE/v1",
  "expert": <REGULATORY|FUNCTIONAL_TRACEABILITY|TECHNICAL|CROSS_DOMAIN|COMPOSER>,
  "finding_record_id": <ancla L2>,
  "l2_snapshot":    { …campos whitelisted de L2, verbatim… },
  "MUST_NOT_CHANGE": { …los 11 campos inmutables, verbatim… },
  "context":        { …solo las claves declaradas en INPUT_CONTEXT_SPEC[expert]… },
  "provenance":     { run_id, agent_id, graph_path, baseline_findings_fingerprint },
  "network": "LOCAL_ONLY"
}
```

**Exclusión dura** (`FORBIDDEN_PACKAGE_KEYS`, `build_input_package` falla si aparecen): `pdf`,
`pdf_bytes`, `canonical_store`, `raw_document`, `full_text`, `graph_store`, `other_findings`.
El experto **nunca ve** el PDF de cliente ni el `canonical_store` completo.

Contexto acotado por experto (`INPUT_CONTEXT_SPEC`):

| Experto | `context` keys | Tarea |
|---|---|---|
| **REGULATORY** | `subcriterion_ref`, `subcriterion_text` (ES + glosa EN), `requirement_terms`, `candidate_claims` (≤5 de `EvidenceBundle` con provenance) | **triage/orden** de los ≤5 candidatos de recuperación para el revisor — **NUNCA juicio de cumplimiento** |
| **FUNCTIONAL_TRACEABILITY** | `anchored_source_text`, `graph_path` (edge_family_checked), `reference_ids`, `neighbor_claims`, `downstream_claims` | ¿la ausencia de arista es un gap real o un límite de extracción? |
| **TECHNICAL** | `case_id`, `control_objective`, `required_behavior`, `source_requirement_id` (de `technical_completeness_rules.yaml` SIGNED), `scope_claims` (sección ancla + subsecciones + xref), `family_signals` | ¿el comportamiento requerido está, parafraseado, dentro del alcance? |
| **CROSS_DOMAIN** | `technical_finding_package`, `regulatory_counterpart_packages`, `prior_expert_opinions` (verificadas), `shared_regulations` (de G1) | reconciliar "gap concreto" ↔ "no puedo juzgar" para el revisor |
| **COMPOSER** | `verified_expert_opinions`, `l2_findings` (457), `routing` (G1) | narrativa por documento × regulación, cada afirmación anclada a `finding_record_id` |

---

## 4 · Contrato de SALIDA (envoltura de opinión — L3)

Claves requeridas: `schema · expert · finding_record_id · shadow_layer("L3") · assessment ·
rationale · anchored_citations · MUST_NOT_CHANGE · confidence · model · produced_at`.
Opcionales: `external_reg_references`, `ranked_candidate_claim_ids`.

Reglas estructurales (`validate_output_envelope`, G2 — no verifica anclaje real):

- `assessment ∈ ASSESSMENT_VALUES[expert]` y sin token de cumplimiento prohibido.
- `MUST_NOT_CHANGE` presente e **idéntico** a los 11 campos L2 del finding.
- `finding_record_id` de la envoltura == L2.
- `rationale` contiene la marca **`[SHADOW / NO GOBERNADO]`** (salvo `COMPOSER`, que marca la
  narrativa por bloques).
- `anchored_citations` es lista; cada cita tiene `quote` no vacío y `source ∈ {CLIENT_EVIDENCE, None}`.
- `external_reg_references[*]`: **nunca** `source == CLIENT_EVIDENCE`; requiere `regulation` +
  `retrieved_at`. Contextualiza, no es evidencia de que el cliente cumple.
- `model.provider == "LOCAL"`; `model.{model_name,digest,prompt_id,prompt_version}` presentes.
- `confidence ∈ {LOW, MEDIUM, HIGH}`.

### `assessment` — enum por experto (OPINIÓN, no veredicto)

| Experto | valores |
|---|---|
| REGULATORY | `CANDIDATE_RANKING_PROVIDED` · `NO_USEFUL_CANDIDATE` · `NEEDS_HUMAN_SEARCH` (+ `ranked_candidate_claim_ids`) |
| FUNCTIONAL_TRACEABILITY | `LIKELY_REAL_GAP` · `LIKELY_EXTRACTION_LIMIT` · `INDETERMINATE` |
| TECHNICAL | `BEHAVIOR_LIKELY_PRESENT_PARAPHRASED` · `BEHAVIOR_NOT_FOUND_IN_SCOPE` · `INDETERMINATE` |
| CROSS_DOMAIN | `RECONCILED_CONSISTENT` · `DISAGREEMENT_PERSISTS` · `INDETERMINATE` |
| COMPOSER | `NARRATIVE_DRAFTED` · `NARRATIVE_BLOCKED` |

`CROSS_DOMAIN == DISAGREEMENT_PERSISTS` ⇒ la relación se marca `HUMAN_REVIEW_REQUIRED` en
`shadow/cross_domain_links.json` (G3); nunca se resuelve sola.

---

## 5 · Evaluación de reutilización selectiva de `v2_judgment` (corrección 5)

Frente al **contrato de INTERPRETACIÓN** (asistir al revisor, NO adjudicar cumplimiento).
Veredictos: **REUSE 5 · REUSE_WITH_ADAPTATION 1 · DISCARD 5**.

| Pieza (`factory/…`) | Veredicto | Por qué |
|---|---|---|
| `engines/gmpai_integrity/model_provider.py` — `ModelProvider` (Protocol) + `OllamaProvider` | **REUSE** | abstracción de modelo intercambiable (corr. 4). Se **congela como abstracción**; el 7B es candidato de piloto, no arquitectónico |
| `engines/gmpai_integrity/ollama_client.py::generate()` | **REUSE** | canal 1 LOCAL, httpx, temperature 0, format:json, timeouts/reintentos probados. Genera OPINIÓN |
| `engines/gmpai_integrity/ollama_client.py::generate_controlled()` | **DISCARD** | fuerza el schema `finding_llm_v1` de EVIDENCIA regulatoria (semántica de adjudicación) |
| `v2_judgment/prompts.py` (`load_prompt`/`is_signed`/`assert_all_signed`/`render`/`temperature`) | **REUSE** | infra de carga/render/firma de prompts YAML — para los prompts de interpretación nuevos |
| `v2_judgment` prompts de contenido `v2_draft/{step_a,step_b,step_b_nonstrict,critic}.yaml` | **DISCARD** | hoy `status: SIGNED`, pero su tarea es JUZGAR un sub-criterio (SATISFIES/PARTIAL/NO). El shadow no juzga cumplimiento → prompts nuevos de interpretación (a firmar antes de G4) |
| `evidence_verifier.py` — `match_citation` / `relevance_score` / `verify_llm_output` / `load_requirement_terms` | **REUSE** | núcleo determinista de anclaje de cita (exact/normalized/despaced/fuzzy ≥ 0.93). **Base del verificador fail-closed de G3.** Umbrales NO se tocan |
| `judgment_v2.py` — `_extract_json` / `_resp_text` / `_claims_index` | **REUSE** | helpers puros de parseo, sin semántica de adjudicación |
| `judgment_v2.py::evaluate_bundle` (orquestador A→B→verify→critic→adjudicator) | **DISCARD** | ensambla un VEREDICTO de cumplimiento por sub-criterio (`MACHINE_CONFIRMED` = "se cumple"). Se reutiliza el **patrón** (paso A neutro; verificación de cita; parseo), no el ensamblaje ni su salida |
| `v2_judgment/adjudicator.py::adjudicate` + estados (`MACHINE_CONFIRMED` / `EVIDENCE_NOT_FOUND` / …) | **DISCARD** | los estados son conclusiones de cumplimiento. El shadow usa su enum `ASSESSMENT_VALUES` (opinión) |
| `v2_judgment/critic.py::review` + `CriticResult` (AGREE/DISAGREE/CANNOT_CONFIRM) | **REUSE_WITH_ADAPTATION** | el **patrón** "segunda lectura adversarial que SOLO degrada, fail-closed hacia la duda" es valioso. El enum (`AGREE` = confirmo cumplimiento) se adapta a duda sobre la OPINIÓN |
| `judgment_v2.py` — `SubcriterionVerdict` / `CandidateOutcome` | **DISCARD** | modelan veredicto por sub-criterio; el shadow modela opinión por finding (envoltura de G2) |

**Principio (corr. 5):** el diseño gobierna el código. Se toma `ModelProvider`, la infra de
prompts, el verificador de citas y los helpers de parseo; se descarta toda la maquinaria de
*adjudicación de cumplimiento*.

---

## 6 · G2.1 — Verificador fail-closed (implementado y ejecutado)

`factory/regulatory/shadow/verifier.py::verify_expert_envelope(envelope, *, l2_finding,
evidence_index=None, declared_counterparts=None) -> VerifierResult`

Combina la validación **estructural** (`contracts.validate_output_envelope`) con el **anclaje
real** de cada cita contra L1/L2 (reutiliza `evidence_verifier.match_citation`,
`FUZZY_THRESHOLD 0.93` intacto). **Fail-closed:** cualquier check que no se pueda evaluar
(p.ej. sin texto de evidencia L1/L2) ⇒ `SHADOW_REJECTED`. Solo una envoltura
`SHADOW_ACCEPTED` llega al composer/reporte (`filter_accepted()` descarta el resto).

**Fixtures adversariales obligatorios — resultado real** (`docs_plan/shadow_llm/G2_verifier_report.json`,
determinista; test `test_g21_all_three_mandatory_adversarial_fixtures_100pct_rejected`):

| Fixture | Resultado | Motivo registrado |
|---|---|---|
| **control positivo** (envoltura bien formada + cita que ancla) | `SHADOW_ACCEPTED` | `reasons: []` |
| **cita / hash inexistente** | `SHADOW_REJECTED` | `anchored_citations[0] cita NO ancla en L1/L2` (+ `source_hash != L2` en el test dedicado) |
| **MUST_NOT_CHANGE alterado** (`risk_band` / `subtype`) | `SHADOW_REJECTED` | `MUST_NOT_CHANGE.risk_band = 'LOW__tampered' != L2 'HIGH'` |
| **evidencia vacía** (`anchored_citations: []` o `quote` vacío) | `SHADOW_REJECTED` | `empty_evidence: >=1 cita anclada no vacía es obligatoria` |

```
all_adversarial_rejected = true      -> 100% -> SHADOW_REJECTED
positive_control          = SHADOW_ACCEPTED
G2.1 PASS                 = true
```

---

## 7 · G2.2 — Verificador de cobertura (implementado y ejecutado)

`verifier.py::verify_report_coverage(l2_findings, referenced_finding_record_ids) -> CoverageResult`
y `assert_full_coverage(...)` (lanza `CoverageError` si falta cobertura).

**Resultado real** (`G2_verifier_report.json`; tests `test_g22_full_457_coverage`,
`test_g22_omitting_one_finding_is_detected_and_fails`):

| Caso | `covered` | `total_l2` | `referenced_valid` | `missing` | `assert_full_coverage` |
|---|---|---|---|---|---|
| **457/457 referenciados** | `true` | 457 | 457 | `[]` | pasa |
| **omitir 1 deliberadamente** (`rec-3d6ae852c098f83d`) | `false` | 457 | 456 | `["rec-3d6ae852c098f83d"]` | **lanza `CoverageError`** |
| referencia a id inexistente | `false` | 457 | 457 | `[]` (`unsupported: ["rec-does-not-exist"]`) | lanza |

```
full_457.covered           = true
omit_one.covered           = false   ·   missing == [omitted_id]
assert_full_coverage_raised = true
G2.2 PASS                  = true
```

---

## 8 · Verificación de criterios CRIT aplicables a G2

| CRIT | Enunciado (mapeado de los invariantes v1.1) | Estado en G2 |
|---|---|---|
| **CRIT-0** | Baseline sin tocar: `FINDINGS_FINGERPRINT == 235f724a…`, `INPUT_CONFIG 3fcb3ae8…`, `GRAPH_SNAPSHOT 2fdda0e2…`, counts 342/90/25 | **✅** atestado por re-corrida de `run_v2_pipeline` desde el código del worktree (con `shadow/{contracts,verifier}.py` presentes) |
| **CRIT-H** | Gate humano intacto: `human_state` de los 457 = `UNREVIEWED`; 0 aprobación automática; ningún experto/verificador cambia `human_state` | **✅** `human_gate_intact = True`; `HUMAN_STATE_CHANGES = 0`; `assessment` sin token de cumplimiento (test) |
| **CRIT-L2** | Inmutabilidad de L2: 0 mutaciones de `class/subtype/severity/risk/requirement_id/machine_state/human_state/related_finding_ids`; el verificador **rechaza** cualquier envoltura que altere `MUST_NOT_CHANGE` | **✅** `L2_MUTATIONS = 0` (tests `test_validator_does_not_mutate_inputs`, `test_g21_verifier_does_not_mutate_inputs`); fixture `MUST_NOT_CHANGE alterado` → `SHADOW_REJECTED` |
| **CRIT-E** (E1–E4) | E1 `UNAUTHORIZED_CLIENT_DATA_EGRESS = 0` · E2 consultas externas auditadas · E3 sin contenido de cliente a Internet · E4 (G0–G5) `LLM_PROVIDER = LOCAL`, canal regulatorio externo NO habilitado | **✅** G2 no abre red (0 sockets); `build_input_package` **excluye** por construcción `pdf`/`canonical_store`/`full_text` (`FORBIDDEN_PACKAGE_KEYS`, test); `network: "LOCAL_ONLY"` en la envoltura; `document_egress_bytes = 0` en la atestación; 0 llamadas LLM |

---

## 9 · REPORTE DE FASE — G2 (formato v1.1)

```
FASE                    = G2 (contratos de experto + evaluación de reutilización + G2.1 verificador
                              fail-closed + G2.2 verificador de cobertura)
PRE_COMMIT              = 3ccc485  (tag shadow-G1)
POST_COMMIT            = <pendiente — no se commitea hasta el gate humano de G2>
WORKTREE               = /home/cmay/ivr-ia/.claude/worktrees/shadow-llm  (rama shadow/llm-interpretation-layer)
DIFF (prohibidos)      = VACÍO
                         · 0 modificaciones a ficheros existentes (git diff --stat HEAD vacío)
                         · 0 cambios en factory/regulatory/{findings,validation_v2,canonical,graph,retrieval,v2_judgment}/
                         · 0 cambios en factory/engines/ · 0 en L0/L1/L2 · 0 en ledger/audit trail
                         · solo ficheros NUEVOS: factory/regulatory/shadow/{contracts,verifier}.py,
                           factory/tests/{test_shadow_contracts,test_shadow_verifier}.py,
                           docs_plan/shadow_llm/{G2_CONTRACTS.md,G2_contracts.json,G2_verifier_report.json}
COMMANDS               = pytest factory/tests/test_shadow_router.py factory/tests/test_shadow_contracts.py factory/tests/test_shadow_verifier.py -q
                         python -m factory.regulatory.shadow.contracts  G2_contracts.json          (×2, byte-idéntico)
                         python -m factory.regulatory.shadow.verifier   G2_verifier_report.json    (×2, byte-idéntico)
                         PYTHONHASHSEED=random python <atestación run_v2_pipeline desde el código del worktree>
TEST_RESULTS           = 39 passed in 0.89s
                         (11 test_shadow_router + 16 test_shadow_contracts + 12 test_shadow_verifier)
INPUT_HASHES           = FINAL_GMP_CORPUS_FINDINGS.json  sha256 95a79f9b6276ff2a7972100764b308fa4b09f0027c6679ea831b441eb880f02c
OUTPUT_HASHES          = docs_plan/shadow_llm/G2_contracts.json         sha256 9719e8300ccb4d2c9eb57e11dfa69f2758159405443cb1d84d2aad626d9a4f56
                         docs_plan/shadow_llm/G2_verifier_report.json   sha256 b065df312e11e017f365f06a3556838735bb20946196dcdb4a1af36a3af1967f
                         factory/regulatory/shadow/contracts.py         sha256 964a4d452abadfbd690094d751de3bc6d8bd80056c42abfa6e330fd2d13629c4
                         factory/regulatory/shadow/verifier.py          sha256 84f8dee4cd6ee2bbd749b994a1d56c35c6a55862ae7ca3d6ed03a89f2a50bbea
                         factory/tests/test_shadow_contracts.py         sha256 e80a463516d311d30bf27396518dad547fc7283cdd33203887c34552ceed2f4d
                         factory/tests/test_shadow_verifier.py          sha256 6b54ac285f13696bdfcd5f7add227e72aebc4486871d758f0a00aeec08aa77ac
                         docs_plan/shadow_llm/G2_CONTRACTS.md
FINGERPRINTS           = atestación desde el código del worktree (con factory/regulatory/shadow/{contracts,verifier}.py presentes):
                         INPUT_CONFIG   3fcb3ae859091000b0e6c6cf2b4f51515e74665d658451b753c723d6e6e51668   ✅
                         GRAPH_SNAPSHOT 2fdda0e2ce513bc48b54038c5890a0b060e87a6e5c0d6d98b3d31fb149be3620   ✅
                         FINDINGS       235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23   ✅ (== baseline)
                         counts 342/90/25 · los módulos shadow NO mueven el fingerprint
LLM_CALLS              = 0
CLIENT_DATA_EGRESS     = 0  (G2 no abre red; atestación bajo network_locked(), egress 0)
LLM_PROVIDER           = LOCAL  (N/A — G2 no ejecuta ningún modelo)
ARTIFACTS              = G2_contracts.json (experts, enums, MUST_NOT_CHANGE, context specs, reuse_evaluation)
                         G2_verifier_report.json (G2.1 3 fixtures adversariales + control; G2.2 cobertura 457 + omisión)
GOVERNANCE_EVENTS      = ninguno
HUMAN_STATE_CHANGES    = 0
L2_MUTATIONS           = 0  (tests test_validator_does_not_mutate_inputs, test_g21_verifier_does_not_mutate_inputs)
CRIT                   = CRIT-0 ✅ · CRIT-H ✅ · CRIT-L2 ✅ · CRIT-E (E1–E4) ✅   (ver §8)
DEVIATIONS             = ninguna
EXPECTED_VS_ACTUAL     = G2.1 esperado: 100% de los 3 fixtures adversariales -> SHADOW_REJECTED; ninguna salida
                                        inválida pasa al reporte
                              actual:   cita/hash inexistente -> REJECTED · MUST_NOT_CHANGE alterado -> REJECTED ·
                                        evidencia vacía -> REJECTED · control positivo -> ACCEPTED · G2.1 PASS = true
                         G2.2 esperado: 457/457 -> covered; omitir 1 -> el verificador detecta la omisión y falla
                              actual:   full_457 covered=true (total_l2=457) · omit_one covered=false,
                                        missing==[omitted_id], assert_full_coverage lanza CoverageError · G2.2 PASS = true
PROPOSED_VERDICT       = PASS
                         Contratos de entrada/salida por experto definidos y validados por estructura;
                         `assessment` es OPINIÓN, no veredicto (0 tokens de cumplimiento); MUST_NOT_CHANGE
                         cubre el conjunto inmutable L2; el paquete de entrada excluye por construcción el
                         PDF y el store de cliente. Evaluación de reutilización de v2_judgment cerrada
                         (REUSE 5 / REUSE_WITH_ADAPTATION 1 / DISCARD 5). **G2.1**: verificador fail-closed
                         implementado y ejecutado — los 3 fixtures adversariales obligatorios (cita/hash
                         inexistente, MUST_NOT_CHANGE alterado, evidencia vacía) → 100% SHADOW_REJECTED,
                         control positivo → SHADOW_ACCEPTED. **G2.2**: verificador de cobertura implementado
                         y ejecutado — 457/457 covered; omisión deliberada de 1 detectada y `assert_full_coverage`
                         falla. 39/39 tests. Sin LLM, sin red, sin mutar L2, sin mover el fingerprint.
                         CRIT-0/H/L2/E ✅. Listo para el gate humano de Capa 9 y la auditoría independiente de
                         Devin; con su OK se commitea el cierre de G2 y se crea el tag shadow-G2, habilitando
                         G3 (post-pass cross-domain → shadow/cross_domain_links.json + especificación del
                         Regulatory Retrieval Gateway).
```

---

## 10 · Qué decide el gate humano de G2

1. **Aceptar los 5 contratos de experto** (§3–§4): paquete de entrada acotado, envoltura de
   salida, `MUST_NOT_CHANGE`, enums de `assessment` sin veredicto de cumplimiento.
2. **Aceptar `G2_contracts.json`** (sha256 `9719e830…`) como el contrato congelado del arco.
3. **Aceptar la evaluación de reutilización** de `v2_judgment` (§5): qué se toma y qué se descarta.
4. **Aceptar el verificador fail-closed G2.1** (§6) y su demostración adversarial
   (`G2_verifier_report.json`, sha256 `b065df31…`): 3 fixtures obligatorios → 100% `SHADOW_REJECTED`.
5. **Aceptar el verificador de cobertura G2.2** (§7): 457/457 y detección de omisión de 1.
6. **Autorizar el commit de cierre de G2 y el tag `shadow-G2`**, y el paso a **G3**.

Nada de lo anterior habilita LLM, embeddings, PILOT nuevo, R2, PILOT-035, el canal regulatorio
externo ni producción.

---

*G2 · contratos + evaluación de reutilización + verificadores deterministas G2.1/G2.2. Sin LLM,
sin red, sin mutar L2, sin mover el fingerprint. 39/39 tests. Detenido en el gate humano. NO se
inicia G3.*
