# CF-6 v2.0 · R1 — Relevance Model + contrato requirement-centric + ProfessionalAssessmentRecord

**Fecha:** 2026-09-04 · **Fase:** R1 (de las instrucciones de ejecución CF-6 v2.0 R1–R3) ·
**Diseño de referencia:** `CF6_v2_REDISENO_AUDITORIA_PROFESIONAL.md` §3, §4, §5 (paso 1), §10 ·
**Autoridad:** Capa 9 = Cesar. **LLM invocado en esta fase: NINGUNO.**

## Qué se implementó

- `factory/regulatory/shadow/relevance_model.py` — Requirement↔Evidence Relevance Model
  (determinista, fail-closed). Clasifica cada `entry` de una sección del Composer contra
  `decomposition.yaml` (GOBERNADO, sin modificarlo) en
  `RELEVANT / PARTIALLY_RELEVANT / IRRELEVANT / INCONCLUSIVE`, usando solapamiento léxico
  ponderado por una IDF local calculada sobre los propios sub-criterios del requisito (sin
  lista de stopwords de dominio hecha a mano). Nota de alcance honesta: a este nivel (entradas
  de sección derivadas de L2, no candidatos crudos de `EvidenceBundle`) no hay `bm25_score` por
  entrada — se usa cuando está disponible, se documenta su ausencia cuando no.
- `factory/regulatory/shadow/requirement_centric.py`:
  - `group_by_requirement_id()` — reagrupa las `entries` del composer skeleton
    (`document×regulation` hoy) usando `requirement_id` como clave primaria, conservando
    `section_type`/`document`/`regulation` de origen como metadato.
  - `requirement_text_and_intent()` — `requirement_text`/`requirement_intent` **sourced de
    `decomposition.yaml`**, nunca autoría del LLM.
  - `build_relevance_filtered_context()` — construye el contexto de sección que vería un
    Composer LLM usando **solo `relevant_evidence[]`**; devuelve `excluded_evidence[]` por
    separado, exclusivamente para auditoría.
  - `ctx_excludes_excluded_evidence()` — verificación de código (no solo declaración) de que
    ningún `finding_record_id` excluido aparece en el material que se enviaría al LLM.
  - `ProfessionalAssessmentRecord` — esquema interno versionado (diseño §10); en esta fase se
    puebla SOLO con lo determinista (`requirement_intent`, `evidence_basis`, `assessment_state`,
    `provenance`); los campos que en el diseño final vienen del Composer LLM
    (`system_response`, `technical_assessment`, `procedural_responsibility`,
    `required_verification`) quedan `None` — pendientes de R2. **Sin renderer externo, sin ruta
    de exportación/distribución a cliente** (`machine_adjudicated` fijo en `False`).
- `factory/tests/test_shadow_cf6_v2_r1.py` — 15 tests nuevos.

## PRE/POST_COMMIT

Antes de esta fase: worktree limpio, HEAD `7dd2713` (CF6-2.5 v3 run2, `HUMAN_QUALITY_GATE(v3)
PENDIENTE`), sin cambios sin commitear. Después: 3 archivos nuevos (los dos módulos + el test),
más este reporte y el artefacto de medición retroactiva — **0 archivos existentes modificados**.

## DIFF (prohibidos = VACÍO)

```
git diff HEAD --stat -- factory/regulatory/shadow/composer_prompt.py \
  factory/regulatory/shadow/composer_prompt_v3.py factory/regulatory/shadow/composer_gate.py \
  factory/regulatory/requirement_catalog/decomposition.yaml \
  factory/layer9/ factory/regulatory/shadow/cf6_pilot_scope.py
→ (vacío)
```
No se tocó ningún prompt firmado, ni Q-STATE, ni el renderer determinista, ni G4d, ni el
ledger de gobernanza, ni `decomposition.yaml`.

## COMMANDS

```
python3 -m pytest factory/tests/test_shadow_cf6_v2_r1.py -q         → 15 passed
python3 -m pytest factory/tests -k shadow -q                        → 206 passed, 1 failed*
sha256sum decomposition.yaml (antes/después de correr todo lo de arriba) → sin cambio
```
\* La única falla (`test_shadow_run_v2_no_effects_and_reversible`,
`current_real_run_calls == 158` vs `None`) es **PRE-EXISTENTE**: reproducida de forma idéntica
retirando temporalmente los 3 archivos nuevos de R1 del árbol de trabajo y corriendo el mismo
test aislado — falla igual sin ningún código de R1 presente. No relacionada con este trabajo.

## TEST_RESULTS

15/15 nuevos, 0 regresiones atribuibles a R1 (ver nota arriba). Cobertura:
reproducibilidad (clasificar dos veces = mismo resultado), aceptación de `sec-0016`,
verificación de código de `excluded_evidence[]`, agrupamiento requirement-centric,
`ProfessionalAssessmentRecord` sin LLM, fail-closed sin `requirement_id` / con
`relevant_evidence` vacío, 0 escrituras a `decomposition.yaml`.

## FINGERPRINTS

`L2_MUTATIONS = 0` confirmado por hash: `sha256(FINAL_GMP_CORPUS_FINDINGS.json)` idéntico antes
y después de correr toda la suite de R1 y de `-k shadow` completo.

**Nota de gobernanza, no atribuible a R1**: recomputar `FINDINGS_FINGERPRINT` con la función
canónica (`factory.regulatory.validation_v2.run_fingerprint.findings_fingerprint()`) sobre el
`FINAL_GMP_CORPUS_FINDINGS.json` actual de esta rama da
`648b44daae927362b39ff236a2ebedd721781b0e4e21fc9a3c241883825ce004`, **distinto** de la
constante histórica `235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23` grabada
en `composer_prompt_v3.py`/`cf6_pilot_runner*.py`. `git log -- FINAL_GMP_CORPUS_FINDINGS.json`
muestra un único commit tocando ese archivo: `3bacfd0 shadow(G0): consolidación/formalización
de baseline — congelado de los 457 findings deterministas` — anterior a esta sesión, no forma
parte de R1. Se reporta a Capa 9 como hallazgo abierto, no se investiga ni se corrige aquí
(fuera del alcance autorizado de R1); el invariante que R1 sí controla y verifica
(`L2_MUTATIONS=0` durante esta fase) se cumple.

## LLM_CALLS

`0`. `LLM_CALLS_AFTER_QSTATE = 0` (no aplica: Q-STATE no se invocó en esta fase, ninguna sección
se renderizó).

## RELEVANCE_MODEL_OUTPUT_SAMPLE (incl. veredicto sec-0016)

`docs_plan/shadow_llm/CF6/CF6_v2_R1_SEC0016_RETROACTIVE_CHECK.json`. Resumen:

| finding_record_id | relevance_state | sub-criterio | ratio |
|---|---|---|---|
| `rec-5bfe094286d91b6d` (security/access control) | `PARTIALLY_RELEVANT` | sc1 | 0.123 |
| **`rec-6b0c9965fd2f4e05`** ("measure the critical process parameters") | **`INCONCLUSIVE`** | sc3 | 0.065 |
| `rec-8e51ef14590a270e` | `IRRELEVANT` | — | 0.0 |
| `rec-8f15c82009c5642f` / `-af05e920bad158fb` / `-d86dfb79cc5b4996` / `-e0b35452eeb06071` / `-4c6611081bdfdeec` | `INCONCLUSIVE` | sc2/sc4/sc5/sc8/sc7 | 0.04–0.08 |

**`rec-6b0c9965fd2f4e05` cae en `excluded_evidence[]`, confirmado.** Es exactamente el
candidato diagnosticado en `CF6_v2_REDISENO_AUDITORIA_PROFESIONAL.md` §0 como el defecto de raíz
de `sec-0016`: "medición de parámetros críticos" recuperado para `sc3` ("proceso de cambio de
privilegios de cuentas") de `21_CFR_11.10(d)` — sin relación real. Bajo el Relevance Model,
nunca habría llegado al Composer LLM.

## EXCLUDED_EVIDENCE_NEVER_SENT_TO_LLM (verificación de código, no solo declaración)

`ctx_excludes_excluded_evidence(ctx, relevance_record) == True` para `sec-0016` (y para el caso
sintético de `TestFailClosed`). Verificación estática adicional
(`TestExcludedEvidenceNeverSentToLLM.test_static_code_never_references_excluded_evidence_in_prompt_build`):
el bucle que arma `entries`/`anchored_quotes`/`normalized_opinions` en
`build_relevance_filtered_context()` itera únicamente sobre `relevant_rids` — no existe ninguna
ruta de código que itere `excluded_rids` hacia el `ctx`.

## PILOT_SCOPE_MATCH_CF6

No aplica a R1 (sin LLM, no se invoca el Composer). Se evalúa explícitamente en R2 (ver
`CF6_v2_R2_SCOPE_CHECK.md`).

## HUMAN_QUALITY_GATE_BY_SECTION (ambas dimensiones)

No aplica a R1 (no hay salida de Composer que evaluar; nada nuevo se le muestra al humano en
esta fase salvo este reporte).

## FUSION_COMPARISON

No aplica a R1 (exclusivo de R3).

## EXPECTED_VS_ACTUAL

Esperado (criterio de aceptación de las instrucciones de ejecución): "clasificación
reproducible; el candidato problemático de `sec-0016` cae en `excluded_evidence[]`; ningún test
existente de v1.2/v1.3 regresa; `decomposition.yaml` con 0 escrituras." **Los cuatro se
cumplen**, con la única salvedad reportada arriba (fingerprint histórico, pre-existente, fuera
de alcance de R1).

## PROPOSED_VERDICT

**R1: PASS.** Propuesto para tag `cf6-v2-R1`. R2 (regeneración bajo el nuevo contrato,
LLM, PILOT-gated) requiere verificación explícita de `PILOT_SCOPE_MATCH_CF6` contra el nuevo
tipo de ejecución antes de proceder — ver documento separado, **no se asume cubierto**.
