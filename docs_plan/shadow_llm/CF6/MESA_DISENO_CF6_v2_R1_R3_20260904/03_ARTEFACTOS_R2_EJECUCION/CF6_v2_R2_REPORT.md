# CF-6 v2.0 · R2.2 — regeneración de la muestra bajo el Composer de 4 pasos con Relevance Model

**Fecha:** 2026-09-04 · **Fase:** R2.2 (de las instrucciones de ejecución CF-6 v2.0 R1–R3) ·
**Autoriza:** Capa 9 (Cesar), tras `PILOT_SCOPE_MATCH_CF6 = PASS` (`CF6_v2_R2_REMEDIATION.md`) y
firma del prompt `shadow-cf6-composer-v2.0-relevance-filtered`.

## Qué se implementó

`factory/regulatory/shadow/cf6_r2_runner.py` (6 tests, `test_shadow_cf6_r2_runner.py`) —
orquesta, por cada sección de la muestra congelada (`CF6_2_5_SAMPLE_MANIFEST.json`, hash
`7422faaf…`, tag `cf6-G2.5-manifest`): (1) filtro de relevancia (R1, ya construido, sin
cambios), (2) UNA llamada LLM sin reintento con el prompt firmado, (3) validación estructural
(`composer_prompt_v2_0_relevance_filtered.validate_structure_contract`,
`evidence_basis ⊆ relevant_evidence` verificado en código), (4) Q-STATE-1..6
(`composer_gate.verify_qstate`, **sin modificar**) sobre una vista adaptada
(`_adapt_r1_to_legacy_view`, solo renombra claves, no reinterpreta datos), (5) render
determinista + blacklist (**sin modificar**).

**Hallazgo de alcance, descubierto al ejecutar (no anticipado en el diseño)**: 2 de las 7
secciones de la muestra no tienen `regulation` con descomposición en `decomposition.yaml`
(`sec-0026` → `ANNEX11_7`, sin descomponer; `sec-0042` → sin regulación directa, trazabilidad
pura). El contrato requirement-centric de R1 es, por construcción, inaplicable a esas 2
secciones — no se inventó descomposición ni se forzaron al pipeline nuevo. Caen a `SAFE_MODE`
(`reason="out_of_scope_r2_no_decomposition"`), la misma plantilla determinista de siempre, 0
LLM.

## PRE/POST_COMMIT

Antes: HEAD `c6b120a` (remediación del gate, PASS). Después: 3 archivos nuevos (runner + test +
este reporte) + 2 artefactos JSON de corrida — **0 archivos existentes modificados** salvo el
ledger (append-only, ver más abajo si aplica — en esta fase NO hubo escritura al ledger, solo
lectura para `assert_signed`/gate).

## DIFF (prohibidos = VACÍO)

```
git diff -- factory/regulatory/shadow/composer_gate.py factory/regulatory/shadow/relevance_model.py \
  factory/regulatory/shadow/requirement_centric.py factory/regulatory/requirement_catalog/decomposition.yaml \
  factory/regulatory/shadow/prompts/composer_structured_v2_0_relevance_filtered.yaml
→ (vacío)
```
Q-STATE, el renderer, el blacklist, R1 (Relevance Model + contrato requirement-centric) y el
prompt firmado quedan intactos.

## COMMANDS

```
python3 -m factory.regulatory.shadow.cf6_r2_runner --dry-run   → 0 LLM, forma verificada
python3 -m factory.regulatory.shadow.cf6_r2_runner             → corrida real (ver abajo)
python3 -m pytest factory/tests/test_shadow_cf6_r2_runner.py -q → 6 passed
python3 -m pytest factory/tests -k shadow -q                    → 248 passed, 1 failed*
```
\* Misma falla pre-existente no relacionada de siempre
(`test_shadow_run_v2_no_effects_and_reversible`).

## TEST_RESULTS

6/6 nuevos (in-scope/out-of-scope, adaptador de campos, dry-run sin LLM, 0 escrituras a
`decomposition.yaml`). 248/249 de `-k shadow` (1 fallo pre-existente, no relacionado).

## FINGERPRINTS

`L2_MUTATIONS = 0`, `human_state` sin cambios, `decomposition.yaml` sin escrituras (verificado
por hash antes/después en test). Ledger real: solo lectura (`cf6_pilot_scope`/`assert_signed`),
sin escritura en esta fase.

## LLM_CALLS

**`LLM_CALLS_TOTAL = 1`** (no 5). De las 5 secciones dentro de alcance (con `decomposition.yaml`),
**el Relevance Model dejó `relevant_evidence[]` vacío en 4 de 5** (`sec-0004`, `sec-0005`,
`sec-0018`, `sec-0062`) — fail-closed por diseño (§4: *"si `relevant_evidence[]` queda vacío, la
sección se renderiza con la plantilla determinista existente... sin invitar al LLM a
especular"*): **0 llamadas LLM** para esas 4, directo a `SAFE_MODE`. Solo `sec-0016` tuvo
evidencia relevante (1 candidato) y llegó al LLM. `LLM_CALLS_AFTER_QSTATE = 0` (siempre).

**Esto no estaba anticipado** en la magnitud observada — el diseño previó que el filtro
reduciría *ruido* (el caso confirmado de `sec-0016`), no que dejaría 4 de 5 secciones sin
ningún candidato para el LLM. Ver "Dato para juicio humano" abajo — no se ajustó ningún umbral
del Relevance Model al ver este resultado.

## RELEVANCE_MODEL_OUTPUT_SAMPLE (por sección, incl. veredicto sec-0016)

| sección | requirement_id | relevant | excluded | LLM llamado |
|---|---|---|---|---|
| sec-0004 | 21_CFR_11.10(g) | 0 | 5 | NO (fail-closed) |
| sec-0005 | 21_CFR_11.50_11.70 | 0 | 7 | NO (fail-closed) |
| **sec-0016** | **21_CFR_11.10(d)** | **1** | **7** | **SÍ** |
| sec-0018 | 21_CFR_11.10(g) | 0 | 5 | NO (fail-closed) |
| sec-0026 | ANNEX11_7 | — | — | NO (fuera de alcance, sin descomposición) |
| sec-0042 | (trazabilidad) | — | — | NO (fuera de alcance, sin regulación) |
| sec-0062 | ALCOA_ORIGINAL | 0 | 2 | NO (fail-closed) |

Detalle completo (incl. `weighted_ratio`/`matched_subcriterion_id` de cada candidato excluido):
`docs_plan/shadow_llm/CF6/CF6_v2_R2_B_OUTPUTS.jsonl`.

**Dato para juicio humano, sin interpretación de Claude Code** (diseño §6: *"Claude Code no
evalúa... reporta los datos, el humano juzga"*): en `sec-0005`, el candidato
`rec-33acbc832665ade8` ("*With the FactoryTalk View SE electronic signature feature, each entry
into the FactoryTalk View...*") quedó `INCONCLUSIVE` (ratio 0.081, 3 términos) para
`21_CFR_11.50_11.70` — un requisito sobre firma electrónica manifestada, donde el texto de la
cita menciona *electronic signature* explícitamente. Es el candidato con más señal léxica de
los 4 casos vacíos y el más discutible de los 12 candidatos excluidos en las 4 secciones. Se
señala explícitamente, sin ajustar el umbral, para que la revisión humana lo contemple al
evaluar `evidence_relevance_accuracy`.

## EXCLUDED_EVIDENCE_NEVER_SENT_TO_LLM (verificación de código, no solo declaración)

`assert _rc.ctx_excludes_excluded_evidence(ctx, relevance_record)` corre en el runner ANTES de
cualquier llamada LLM, por sección — el proceso aborta si falla. Pasó en las 5/5 secciones
dentro de alcance. Adicionalmente, para `sec-0016`, `sections_rendered_evidence_basis_all_
within_relevant = true`: el `evidence_basis` que el LLM realmente devolvió (no solo lo que se
le ofreció) está 100% contenido en `relevant_evidence[]`.

## SEC-0016 — SCOPE_DRIFT confirmado ausente (A vs B con salida REAL, no solo teórica)

**B (v3, `CF6_2_5_v3_PILOT_RUN.json`/`_B_OUTPUTS.jsonl`, RENDERED)** citaba 4 evidencias,
incluida **`rec-6b0c9965fd2f4e05`** ("*measure the critical process parameters*") y el
`reviewer_action` pedía verificar "*medición de parámetros críticos*" como si fuera parte de
`21_CFR_11.10(d)`:
```
reviewer_action (v3): "Revisar en RW-0006 si los sub-criterios de 21 CFR 11.10(d) sobre
seguridad y control de acceso, y medición de parámetros críticos quedan cubiertos..."
```

**B (R2, real, RENDERED, Q-STATE PASS)** cita ÚNICAMENTE la evidencia de control de acceso:
```
evidence_basis: [{"rec-5bfe094286d91b6d", "The system shall implement the security and access control"}]
gap_or_open_question: "Se debe verificar si el sistema tiene un mecanismo de control de acceso
  y si este se ha implementado según lo especificado en la sección 3.4.1 del documento."
```
`rec-6b0c9965fd2f4e05` no aparece en ningún campo de la salida R2 — confirmado por búsqueda
textual sobre el objeto completo, no solo por el filtro previo. **`SEC_0016_SCOPE_DRIFT_ABSENT
= true`.**

## PILOT_SCOPE_MATCH_CF6

No se re-evalúa en esta fase (ya `PASS`, `CF6_v2_R2_REMEDIATION.md`); esta corrida consumió 1 de
las 250 llamadas del tope aditivo del ADDENDUM `-041/-042/-043/-044`.

## HUMAN_QUALITY_GATE_BY_SECTION (ambas dimensiones — datos, sin veredicto de Claude Code)

**SAFETY/GOVERNANCE (determinista, heredado):**

| sección | Q-STATE | blacklist | SAFE_MODE correcto cuando aplica |
|---|---|---|---|
| sec-0004/0005/0018/0062 | n/a (sin estructura, correcto: `relevant_evidence` vacío) | n/a | SÍ — plantilla conservadora, 0 fabricación |
| sec-0016 | **PASS** | limpio | n/a (RENDERED) |
| sec-0026/0042 | n/a (fuera de alcance) | n/a | SÍ |

0 violaciones Q-STATE publicadas · 0 hits de blacklist publicados · `L2_MUTATIONS=0` ·
`human_state` sin cambios · `G4d` no re-ejecutado · 0 LLM tras Q-STATE.

**AUDIT QUALITY (nuevo, §6 — reportado, NO evaluado por Claude Code):**

- `evidence_relevance_accuracy`: sin muestra etiquetada por humano todavía (diseño §4: "se puede
  construir un conjunto etiquetado... medir precisión/recall del propio modelo de relevancia" —
  no existe ese conjunto en esta fase). El caso de `sec-0005` señalado arriba es el candidato a
  incluir en esa muestra.
- `citation_fidelity`: determinista, verificado — Q-STATE-6 confirmó el anclaje de la única
  cita de `sec-0016` contra L2.
- `unsupported_conclusions`: 0 (Q-STATE-4/5 limpios en la sección rendida).
- `regulatory_overstatement`: 0 (blacklist limpio).
- `requirement_interpretation_accuracy`, `gmp_assessment_accuracy`, `professional_clarity`,
  `audit_utility`/`value_added`, `cognitive_load_reduction`: rúbrica humana, **pendiente**
  (diseño §6 — igual que en v2/v3, Claude Code no las puntúa).

**Cobertura como dato de calidad, no de seguridad**: 1/5 secciones dentro de alcance llegó a
`RENDERED` (vs. 4/5 en la corrida v3 equivalente para las mismas secciones donde había
descomposición aplicable). Es un dato crudo para el juicio humano: puede leerse como el
Relevance Model funcionando según diseño (eliminando exactamente el tipo de ruido de
`sec-0016`) llevado a su consecuencia lógica en las otras 4 secciones, o como thresholds
calibrados de forma demasiado conservadora. Claude Code no toma esa decisión.

## FUSION_COMPARISON

No aplica (exclusivo de R3, no autorizado en esta ronda).

## EXPECTED_VS_ACTUAL

Esperado (criterio de aceptación de R2, instrucciones de ejecución): "SAFETY/GOVERNANCE íntegro
+ AUDIT QUALITY cumple umbrales (rúbrica humana, pendiente) + `sec-0016` sin SCOPE_DRIFT."
**SAFETY/GOVERNANCE: cumplido** (verificado, determinista). **`sec-0016` sin SCOPE_DRIFT:
cumplido** (verificado con salida real). **AUDIT QUALITY: datos entregados, umbral no evaluado**
— requiere juicio humano, como el diseño exige explícitamente. **No esperado**: la caída de
cobertura a 1/5 secciones renderizadas — reportado como hallazgo abierto, no resuelto ni
ocultado.

## PROPOSED_VERDICT

**R2.2: ejecutado conforme al plan, sin llamadas post-Q-STATE, sin relajar ningún gate.**
`SAFETY/GOVERNANCE = PASS` (determinista). `AUDIT QUALITY = PENDIENTE de adjudicación humana`
(Claude Code no decide). El tag `cf6-v2-R2` (que las instrucciones asocian al gate PASS
completo, ambas dimensiones) **no se aplica todavía** — falta la mitad humana del gate. Sin R3.
Sin cambios a R1. STOP para que Capa 9 evalúe `evidence_relevance_accuracy` (en particular el
caso `sec-0005` señalado) y las dimensiones de rúbrica pendientes.
