# CF-6 v2.0 · R2 — remediación del gate: ADDENDUM correctivo + firma del prompt → 4/4 + 2/2 = YES → STOP

**Fecha:** 2026-09-04 · **Instrucción aplicada (Capa 9 / Cesar):** remediar exclusivamente el
gate de gobernanza de R2 vía (1) un ADDENDUM correctivo append-only que añade el token
`"CF6-3"`, sin tocar `PILOT_EXECUTION-2026-041/-042`, y (2) formalizar la firma del prompt ya
congelado, sin modificar su contenido. Sin ejecutar R2, sin llamadas LLM. Re-chequear los 4
gates + `PROMPT_SIGNED` + `PROMPT_SHA256`. Si algo = NO → STOP; si todo = YES → reportar y STOP
para autorización explícita antes de R2.

## 1. ADDENDUM correctivo — token `"CF6-3"` añadido, `-041/-042` sin tocar

`factory/regulatory/shadow/cf6_scope_addendum_v2_r1_correction.py` (5 tests) — reutiliza
**exactamente** las mismas unidades de scope de `-041/-042`
(`cf6_scope_addendum_v2_r1._scope_units()`, sin cambio, verificado en test), añade
`payload.legacy_token = "CF6-3"` + mención literal en `reason`.

Formalizado vía `factory.services.governance_service` (propose → confirm, sin edición manual):

```
PILOT_EXECUTION-2026-043  ADDENDUM  agent_proposed   (cf6_scope_addendum_agent)
PILOT_EXECUTION-2026-044  ADDENDUM  human_confirmed   approved_by_id=cesar
                          status ACTIVE · confirms_instance_id=PILOT_EXECUTION-2026-043
                          supersedes_instance_id=null  (I-7: amplía, no supersede)
```

Append-only verificado: `head -n -2` del ledger tras esta operación es byte-idéntico al ledger
en `HEAD` (que ya incluía `-041/-042`) — **`-041/-042` no se editaron**, quedan `ACTIVE`
exactamente como antes. `-035..-042` siguen `ACTIVE`, trazabilidad intacta.

## 2. Prompt firmado — contenido sin modificar

Se editaron **únicamente** 4 líneas del YAML (`status`, `signed_by`, `signed_at`, `signed_on`);
el resto del archivo (`contract`, `system`, `user_template`, `few_shot`) queda byte-idéntico —
verificado por `git diff`, que muestra exclusivamente esas 4 líneas añadidas/cambiadas.

Evidencia gobernada (mismo patrón que la firma de `shadow-cf6-composer-struct-v3`):
`docs_plan/shadow_llm/CF6/CF6_v2_R2_PROMPT_SIGN_PROPOSE.json` →
`CF6_v2_R2_PROMPT_SIGN_GOVERNED_EVIDENCE.json`.

```
prompt_sha256_before_signing (= contenido congelado)  = 907e2c30fe9d158366f78afebef53364e1d221db7cbb73de6e6c8e48f57814be
matches_frozen_content_sha256 (vs CF6_v2_R2_PROMPT_FREEZE.json)             = True
live_prompt_sha256_after_signing (archivo completo, incl. las 4 líneas nuevas) = f5382ae06ab56aab7f1a3110e414e380bdaf4d0eb940c97195517e56881cba5c
propose_to_human_confirmed_consistent                                       = True
status                                                                       = SIGNED
signed_by                                                                    = "Capa 9 (Cesar)"
```

El hash del ARCHIVO cambia (es inevitable: contiene la firma) pero el **contenido congelado —
el contrato que se redactó y validó en el paso anterior — es byte-idéntico**, confirmado por
`prompt_sha256_before_signing == 907e2c30…` (el mismo hash reportado en
`CF6_v2_R2_PROMPT_FREEZE.json`) y por el `git diff` mostrado arriba.

## 3. Re-chequeo — TODO YES

```
python3 -m factory.regulatory.shadow.cf6_pilot_scope   # required_composer_prompt_version =
                                                        # 'shadow-cf6-composer-v2.0-relevance-filtered'
```

```
PILOT_SCOPE_MATCH_CF6       = YES
  a_composer_prompt_version = YES
  b_cf6_2_5                 = YES
  c_cf6_3                   = YES   ← remediado
  d_execution_type_json_structure = YES
REMAINING_BUDGET_SUFFICIENT = YES (250)
ACTIVE                      = YES
NOT_SUPERSEDED               = YES
GATE_RESULT                  = PASS

PROMPT_SIGNED                = YES
PROMPT_SHA256 (congelado, sin modificar) = 907e2c30fe9d158366f78afebef53364e1d221db7cbb73de6e6c8e48f57814be  ✓ coincide con el freeze
```

`pilot_instance = PILOT_EXECUTION-2026-044` (el ADDENDUM correctivo, último `human_confirmed`
del ledger). Artefacto completo:
`docs_plan/shadow_llm/CF6/CF6_v2_R2_GATE_RECHECK_RESULT_2.json`.

## No relajado

`cf6_pilot_scope.py` no se tocó. `composer_prompt_v2_0_relevance_filtered.py` (validador
estructural) no se tocó. R1 (`relevance_model.py`, `requirement_centric.py`, tag `cf6-v2-R1`)
no se tocó. Ningún umbral, regex ni criterio de aceptación cambió — la remediación fue
exclusivamente de gobernanza (scope + firma), no de código de validación.

## Invariantes

`LLM_CALLS = 0` en toda la fase · `L2_MUTATIONS = 0` · `human_state` sin cambios ·
`decomposition.yaml` sin escrituras · ledger append-only (dos operaciones, +2 líneas cada una,
prefijo previo byte-idéntico en ambas) · `shadow-cf6-composer-struct-v2`/`-v3` (firmados)
intactos.

## Tests

`test_shadow_cf6_v2_r2_scope_correction.py` (5, nuevo) + actualizaciones de forma en
`test_shadow_cf6_v2_r2_prompt.py` (ahora `TestSigned`, refleja `status: SIGNED`) y
`test_shadow_cf6_v2_r2_scope_addendum.py` (pin actualizado a `-044`, el último `human_
confirmed`). `-k shadow`: 242 passed, 1 failed (la misma falla pre-existente no relacionada de
siempre).

## STOP

Las 4 condiciones de gobernanza + `PROMPT_SIGNED` + `PROMPT_SHA256` dan **YES/PASS**. Conforme
a la instrucción ("si todas = YES → reportar evidencia y STOP para autorización explícita de
Capa 9 antes de ejecutar R2"): **me detengo aquí.** No se ejecutó R2.2 (regeneración con LLM),
no se ejecutó R3, no se modificó R1, no se realizó ninguna llamada LLM en toda la fase. Queda
pendiente de Capa 9 la autorización explícita para iniciar R2.2.
