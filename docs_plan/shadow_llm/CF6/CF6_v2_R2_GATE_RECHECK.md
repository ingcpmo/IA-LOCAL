# CF-6 v2.0 · R2 — ADDENDUM formalizado + prompt congelado → re-chequeo de los 4 gates → STOP

**Fecha:** 2026-09-04 · **Instrucción aplicada (Capa 9 / Cesar):** formalizar el ADDENDUM
(`human_confirmed`, registrado en ledger), autorizar redactar/validar/congelar
`composer_prompt_version = shadow-cf6-composer-v2.0-relevance-filtered` correspondiente
estrictamente al contrato requirement-centric de R1, **sin ejecutar R2, sin llamadas LLM**, y
re-ejecutar únicamente `PILOT_SCOPE_MATCH_CF6 / REMAINING_BUDGET_SUFFICIENT / ACTIVE /
NOT_SUPERSEDED`. Si algún gate = NO → STOP.

## 1. ADDENDUM formalizado

`human_confirmed = YES`, registrado en el ledger real **vía la API gobernada
`factory.services.governance_service`** (propose → confirm), sin edición manual:

```
PILOT_EXECUTION-2026-041  ADDENDUM  agent_proposed   (cf6_scope_addendum_agent)
PILOT_EXECUTION-2026-042  ADDENDUM  human_confirmed   approved_by_id=cesar
                          display "Capa 9 (Cesar)"  status ACTIVE
                          confirms_instance_id=PILOT_EXECUTION-2026-041
                          supersedes_instance_id=null  (I-7: amplía, no supersede)
```

Verificado append-only: las 270 líneas previas del ledger quedan byte-idénticas (diff vacío
contra `HEAD:factory/layer9/decisions/decisions_v2.jsonl`); solo +2 líneas al final.
`PILOT_EXECUTION-2026-035..-040` siguen `ACTIVE`, `superseded_by=null` — trazabilidad intacta.

## 2. Prompt redactado, validado y congelado (NO firmado, NO ejecutado)

- `factory/regulatory/shadow/prompts/composer_structured_v2_0_relevance_filtered.yaml`
  (`status: DRAFT_UNSIGNED`)
- `factory/regulatory/shadow/composer_prompt_v2_0_relevance_filtered.py` (loader + validador
  estructural)
- `factory/tests/test_shadow_cf6_v2_r2_prompt.py` — 23 tests, 0 LLM
- Congelado: `docs_plan/shadow_llm/CF6/CF6_v2_R2_PROMPT_FREEZE.json`,
  `prompt_sha256 = 907e2c30fe9d158366f78afebef53364e1d221db7cbb73de6e6c8e48f57814be`

Corresponde estrictamente al contrato §3 de R1 (verificado en test):
`requirement_text`/`requirement_intent` son **dato de entrada** (nunca campo de salida
pedido al LLM), `evidence_basis` **estructuralmente restringido** a
`relevant_evidence[]` (un `finding_record_id` fuera de esa lista es rechazo estructural, no
interpretación), `technical_assessment`/`procedural_responsibility` separados,
`gap_or_open_question` generaliza `reviewer_action`, `assessment_state` con los mismos 3
valores que `regulatory_state` (v2/v3). **NO firmado** (`SIGNED` requeriría un
`HUMAN_QUALITY_GATE` sobre salidas reales, que esta autorización excluye explícitamente). **0
llamadas LLM** en todo este paso.

No toca `shadow-cf6-composer-struct-v2`/`-v3` (siguen firmados, intactos), ni Q-STATE, ni el
renderer, ni G4d, ni L2, ni `decomposition.yaml` (hash antes/después idéntico, verificado en
test).

## 3. Re-chequeo de los 4 gates (únicamente estos, nada más)

```
python3 -m factory.regulatory.shadow.cf6_pilot_scope   # required_composer_prompt_version =
                                                        # 'shadow-cf6-composer-v2.0-relevance-filtered'
```

```
PILOT_SCOPE_MATCH_CF6       = NO
  a_composer_prompt_version = YES   (coincidencia de texto: el nombre aparece en el payload
                                      firmado de -042 — NOTA: este chequeo es un match de
                                      TEXTO contra el ledger, no verifica en disco si el YAML
                                      del prompt existe; existe y está congelado, §2, pero por
                                      una vía separada)
  b_cf6_2_5                 = YES   ("CF6-2.5" aparece literal en selection_reason)
  c_cf6_3                   = NO    ← ROMPE el gate, ver causa abajo
  d_execution_type_json_structure = YES
REMAINING_BUDGET_SUFFICIENT = YES  (250 disponibles, ADDENDUM = presupuesto propio)
ACTIVE                      = YES
NOT_SUPERSEDED               = YES
GATE_RESULT                  = FAIL
```

Artefacto completo: `docs_plan/shadow_llm/CF6/CF6_v2_R2_GATE_RECHECK_RESULT.json`.

## Causa exacta de la falla — error de redacción propio, no del mecanismo de gobernanza

El chequeo `(c)` de `cf6_pilot_scope.py` busca, literalmente, alguno de estos tokens en el
scope del ADDENDUM: `"CF6-3"`, `"cf6_3"`, `"corrida completa cf6"`, `"full cf6"`. Al redactar
el ADDENDUM (`cf6_scope_addendum_v2_r1.py`) usé la terminología de fases de R1/R2/R5 del
diseño CF-6 v2.0 (`execution_phase: "CF6-v2-R5"`, `selection_reason: "corrida completa bajo la
arquitectura R1-R3 (diseño §13, R5)..."`) en vez de repetir el token literal heredado del gate
de v1.2/v1.3 (`"CF6-3"`). El texto contiene "corrida completa" pero no la cadena exacta
`"corrida completa cf6"` que el chequeo exige — coincidencia de texto rota por elección de
palabras, no una falla de scope real ni de intención (la unidad de scope SÍ autoriza,
sustantivamente, "corrida completa bajo la arquitectura R1-R3" — el mismo concepto que R5 del
diseño). El registro ya está firmado y el ledger es append-only: **no se corrige editándolo**.

No se relaja ni se ajusta este chequeo para forzar un PASS — sería exactamente el tipo de
manipulación del instrumento de medición que este proyecto prohíbe de forma permanente
(`gmp-recall-pipeline`: "el problema... nunca es de la estrictez del verificador").

## STOP

Conforme a la instrucción explícita ("Si algún gate = NO → STOP"): **me detengo aquí.**
No se ejecuta R2.2 (regeneración con LLM). No se realizó ninguna llamada LLM en toda esta
fase. No se proponen cambios adicionales al scope sin que Capa 9 lo decida.

**Camino de remediación (decisión de Capa 9, no ejecutada aquí)**, análogo al patrón histórico
v2→v3 (`-037/-038` seguido de `-039/-040`): una ADDENDUM de corrección adicional, con la misma
unidad de scope pero incluyendo el token literal `"CF6-3"` (p.ej. en `selection_reason` o como
alias explícito de `"CF6-v2-R5"`), extendiendo (no supersediendo, I-7) `-041/-042`. Queda
propuesto como opción, **no ejecutado** — fuera del alcance explícito de esta ronda.

## Invariantes

`LLM_CALLS = 0` en toda la fase · `L2_MUTATIONS = 0` · `human_state` sin cambios ·
`decomposition.yaml` sin escrituras (hash idéntico) · ledger append-only verificado (+2 líneas,
270 previas byte-idénticas) · `decomposition_version` sin cambio · ningún prompt firmado
(v2/v3) tocado.

## Tests

`test_shadow_cf6_v2_r2_scope_addendum.py` (7, actualizado tras la confirmación real) +
`test_shadow_cf6_v2_r2_prompt.py` (23, nuevo) + 2 tests pre-existentes de
`test_shadow_cf6_2_5.py` actualizados para fijar su afirmación histórica a un snapshot del
ledger a la altura de `-040` (el chequeo `evaluate()` inspecciona solo el último `human_
confirmed`, no la unión de ACTIVE — comportamiento documentado de la herramienta, no defecto
introducido aquí; ver comentario en el test). `-k shadow`: 236 passed, 1 failed (la misma falla
pre-existente no relacionada, reproducida igual sin ningún código de esta sesión).
