# CF-6 v2.0 · R2 — verificación explícita de PILOT_SCOPE_MATCH_CF6 → STOP

**Fecha:** 2026-09-04 · **Instrucción aplicada:** PARTE A / R2, punto 1: *"Repetir el gate
`PILOT_SCOPE_MATCH_CF6` (4 chequeos) contra la PILOT vigente — el tipo de ejecución cambia
(nuevo contrato, Relevance Model activo), así que **no asumir** que el scope firmado la cubre;
verificarlo explícitamente. Si no cubre, STOP y reportar a Capa 9."*

## Resultado

```
python3 -m factory.regulatory.shadow.cf6_pilot_scope   # required_composer_prompt_version
                                                        # = 'shadow-cf6-composer-struct-v2-relevance-filtered'
```

```
PILOT_SCOPE_MATCH_CF6 = NO
  a_composer_prompt_version = NO   ← no existe ningún composer_prompt_version firmado para
                                      el Composer de 4 pasos con Relevance Model (R1/§5); el
                                      ledger solo cubre 'shadow-cf6-composer-struct-v3'
  b_cf6_2_5                 = YES
  c_cf6_3                   = YES
  d_execution_type_json_structure = YES  (el chequeo (d) es un token-match genérico sobre
                                      "estructura JSON" — detecta el FORMATO de salida, no
                                      distingue si el pipeline de entrada tiene o no el filtro
                                      de relevancia. No se confunde este YES con "el nuevo tipo
                                      de ejecución está cubierto")
REMAINING_BUDGET_SUFFICIENT = YES (250 disponibles)
ACTIVE = YES · NOT_SUPERSEDED = YES
GATE_RESULT = FAIL
```

Artefacto completo: salida cruda del gate, generado en esta sesión (no persistido como JSON
separado para no crear un artefacto de gobernanza con un `required_composer_prompt_version`
inventado — el nombre usado, `shadow-cf6-composer-struct-v2-relevance-filtered`, es un
placeholder de verificación, no una propuesta de nombre real).

## Por qué falla, específicamente

R1 (ya cerrado, tag `cf6-v2-R1`) construyó el Relevance Model y el contrato requirement-centric
**sin invocar ningún LLM y sin crear ningún `composer_prompt_version` nuevo** — no había
necesidad, R1 es puramente determinista. Eso significa que, a diferencia de la transición
v2→v3 (donde ya existía un YAML de prompt candidato para firmar), **hoy no existe ningún prompt
firmado, ni siquiera `DRAFT_UNSIGNED`, que represente el Composer de 4 pasos con evidencia
pre-filtrada por el Relevance Model.** El chequeo (a) del gate falla porque, literalmente,
todavía no hay nada que ese scope pudiera cubrir por nombre.

Esto no es un defecto del gate ni de R1 — es la secuencia correcta: el scope de una PILOT no
puede autorizar de antemano un prompt que aún no existe. Es exactamente el caso que la
instrucción anticipó ("el tipo de ejecución cambia... no asumir que el scope firmado la cubre").

## STOP

Conforme a la instrucción y a la regla ya establecida en `cf6_pilot_scope.py`
("Claude Code NO propone una nueva PILOT automáticamente"), **esta sesión no continúa a R2.2
(regeneración con LLM)**. No se redacta un nuevo prompt YAML candidato, no se propone una
ampliación de scope (ADDENDUM) ni una nueva `PILOT_EXECUTION` — eso requiere que primero exista
un diseño de prompt concreto (fuera del alcance mecánico de este chequeo) y luego una decisión
de Capa 9 sobre CÓMO cubrirlo, siguiendo el mismo patrón dos veces ya usado (`cf6-G2G`,
`cf6-G2G-r1`): (1) diseñar+redactar el prompt `DRAFT_UNSIGNED`, (2) proponer ADDENDUM de scope,
(3) Capa 9 firma ambos (prompt + ADDENDUM human_confirmed vía `governance_service`).

## R3

R3 (benchmark BM25 vs BM25+fusion) también es "LLM acotado, PILOT-gated" bajo el mismo régimen
(instrucciones, PARTE A/R3) y depende del mismo Composer de R1/R2 para medir
`evidence_relevance_accuracy`. Con R2 detenido en este punto, **R3 tampoco procede en esta
sesión** por la misma razón de fondo (ningún `composer_prompt_version` del pipeline nuevo está
firmado ni cubierto por scope).

## Qué queda listo para cuando Capa 9 decida

- El Relevance Model y el contrato requirement-centric (R1) están completos, probados y
  tageados (`cf6-v2-R1`) — no bloqueados, disponibles para que un futuro prompt de Composer los
  consuma.
- `build_relevance_filtered_context()` ya produce, por sección, exactamente el `ctx` con el que
  se podría renderizar un nuevo prompt v4 (mismas claves que `_section_context_v3`) — el
  siguiente paso de implementación (cuando Capa 9 autorice diseñar el prompt) es mínimo:
  redactar el YAML del prompt v4 sobre este contexto ya filtrado, no reconstruir el pipeline.

**Decisión pendiente de Capa 9**, no de Claude Code: autorizar el diseño de un
`composer_prompt_version` para el Composer de 4 pasos, y el mecanismo de scope (ADDENDUM o
nueva PILOT) que lo cubra.

## Actualización — ADDENDUM propuesto (mecanismo elegido por Cesar: ADDENDUM, no nueva PILOT)

`factory/regulatory/shadow/cf6_scope_addendum_v2_r1.py` (7 tests,
`factory/tests/test_shadow_cf6_v2_r2_scope_addendum.py`) — mismo patrón que
`cf6_scope_addendum.py`/`cf6_scope_addendum_v3.py`: `propose` de un ADDENDUM que extiende
`PILOT_EXECUTION-2026-035/-036/-037/-038/-039/-040` (no las supersede — I-7), sin tocar el
ledger real, sin `human_confirmed`. Artefacto:
`docs_plan/shadow_llm/CF6/CF6_v2_R2_SCOPE_ADDENDUM_PROPOSE.json`.

**Diferencia deliberada con los dos precedentes** (importante para Capa 9 al decidir): en v2 y
v3, el `composer_prompt_version` referenciado por el ADDENDUM ya existía como archivo YAML
(`DRAFT_UNSIGNED`) en el momento del propose. Aquí, por instrucción explícita de esta sesión
("no rediseñar R1 ni CF-6 v2.0, no implementar"), **no se redactó ningún prompt YAML nuevo**.
`RESERVED_COMPOSER_PROMPT_VERSION = "shadow-cf6-composer-v2.0-relevance-filtered"` es un
**nombre reservado**, marcado explícitamente `composer_prompt_version_status:
RESERVED_NAME_NOT_YET_DRAFTED` en el payload — no un artefacto existente.

**Consecuencia verificada en código** (`test_signing_this_addendum_alone_does_not_flip_the_gate_to_pass`):
firmar esta ADDENDUM, por sí sola, **no** deja `PILOT_SCOPE_MATCH_CF6 = YES` — el chequeo (a)
de `cf6_pilot_scope.evaluate()` exige que el `composer_prompt_version` exista con ese nombre
exacto (al menos `DRAFT_UNSIGNED`), y hoy no existe. Orden correcto, análogo al histórico
v2→v3:

```
1. Capa 9 firma este ADDENDUM (human_confirmed) — reserva el scope, NO reabre R1 ni implementa nada
2. Capa 9 decide, por separado, si autoriza redactar el prompt 'shadow-cf6-composer-v2.0-relevance-filtered'
3. (si se autoriza) se redacta y eventualmente se firma ese prompt
4. recién entonces cf6_pilot_scope.evaluate(required_composer_prompt_version=
   'shadow-cf6-composer-v2.0-relevance-filtered') puede dar GATE_RESULT=PASS
```

Este ADDENDUM resuelve la parte del gate que corresponde a esta sesión (scope reservado,
trazabilidad intacta, 0 LLM, 0 escrituras al ledger/decomposition.yaml) sin tocar R1 ni escribir
ningún prompt — el paso 2 sigue siendo, explícitamente, decisión de Capa 9.
