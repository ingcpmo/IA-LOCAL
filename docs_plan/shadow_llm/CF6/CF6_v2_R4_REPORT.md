# CF-6 v2.0 · R4 — Reconciliación post-R2 + medición del Relevance Model (E1→E5)

> **Adenda 2026-09-05 (iteración de fixture autorizada por Capa 9)**: la v1 de
> `TECHNICAL_PARAPHRASE` (sustitución de la primera ocurrencia, ~10 patrones) resultó
> demasiado leve (recall trivial 1.0). Se autorizó iterar el fixture ANTES de recalibrar. La
> v2 (`_paraphrase`, sustitución de TODAS las ocurrencias, ~50 sinónimos de dominio GMP/21 CFR)
> reduce el solapamiento léxico de forma deliberada. Nuevo `FIXTURE_HASH =
> df35ab12999498d4...`. Resultado de la remedición: **ver "Adenda — resultado de la iteración
> v2" al final de este documento — cambia la lectura de la atribución de forma importante.**
> El cuerpo original de R4 (v1, `fixture_hash a...`→`dd135f5c...`) se conserva íntegro abajo,
> sin editar, para trazabilidad.

**Fecha:** 2026-09-04 · **Instrucción:** "RECONCILIACIÓN POST-R2 + EJECUCIÓN R4" (Capa 9) ·
**Régimen:** ejecución continua E1→E5, sin gates intermedios, validación única al final.
**LLM_CALLS en toda la ronda: 0.**

---

## Reporte final (formato §4)

```
CONFIG_R4_HASH        = 6474960820cd911f281d928f40e6612196cab74f0c51c7e8cb8091e785027c70
FIXTURE_HASH          = dd135f5c44df477150effc5bc6c512e2177480815cea254849fb1c447d5366b6
SEMILLA_DE_PARTICIÓN  = 20260904

QSTATE7_IMPLEMENTADO      = YES
QSTATE7_TASA_DISPARO_SOBRE_R2 = 1/1  (la única sección RENDERED de R2 -- sec-0016 -- habría
                                      caído a SAFE_MODE bajo Q-STATE-7; 8 violaciones, todas en
                                      procedural_responsibility/observed_system_capability/
                                      technical_assessment/assessment_rationale)

TABLA_EQUIVALENCIA_FASES_COMMITEADA = YES  (factory/regulatory/shadow/phase_equivalence_table.py,
                                            versión 1, firmada Capa 9 2026-09-04)

BARRIDO_RUTAS: módulos con patrón dry-run/producción compartido =
  cf6_pilot_runner.py (run_cf6_2_5), cf6_pilot_runner_v3.py (run_cf6_2_5_v3)
  -- ambos corregidos con el mismo mecanismo que cf6_r2_runner.py (nunca disparado en la
  práctica: los tests ya pasaban out_dir=tmp_path por disciplina, no por diseño)

FIXTURE: 361 pares construidos · 8 categorías, todas ≥15 pares (mínimo real: 29,
  PROCEDURAL_VS_TECHNICAL) · ambos perfiles de forma presentes en las 8 categorías (mínimo
  real: 2, PROCEDURAL_VS_TECHNICAL/FEW_LONG -- limitación declarada abajo) · partición
  CALIBRATION=98 / HELDOUT=263, disjunta por requirement_id, ambos perfiles en ambas
  particiones

MÉTRICAS (fixture construido, umbral CONGELADO actual):
  global:       precisión 0.667 · recall 1.000  (TP=188 FP=94 FN=0 TN=79, n=361)
  CALIBRATION:  precisión 0.691 · recall 1.000  (n=98)
  HELDOUT:      precisión 0.659 · recall 1.000  (n=263)
  por perfil:   MANY_SHORT precisión 0.678 recall 1.000 (n=232)
                FEW_LONG   precisión 0.648 recall 1.000 (n=129)
  → divergencia por perfil: 0.030 (NO marcada -- ver atribución §5 abajo)

ACHIEVABLE_OPTIMUM (CALIBRATION, barrido sobre el ratio YA EXISTENTE, umbral NO modificado
en relevance_model.py):
  SÍ existe un punto (threshold=0.44) que alcanza T_recall=0.90 y T_precision=0.80
  simultáneamente en CALIBRATION: recall=0.905, precisión-sobre-IRRELEVANT_SIMILAR_DOMAIN=1.000
  Verificación en HELDOUT con ese MISMO umbral (no re-optimizado):
  recall=0.865 (< 0.90, por 0.035) · precisión=1.000 (cumple)
  → el óptimo de CALIBRATION NO se sostiene con margen en HELDOUT

MÉTRICAS (REAL_ADJUDICATED, 27 pares, R2, adjudicados por Capa 9 -- reportadas por separado,
NUNCA mezcladas con el fixture construido):
  precisión = 0.0 · recall = 0.0  (TP=0 FP=1 FN=2 TN=24) -- sin cambio respecto de R2

ELABORACIÓN_NO_ANCLADA (medición, no bloqueo, misma lógica que Q-STATE-7):
  1 de 1 narrativa real (sec-0016) presenta el patrón -- 8 instancias

INVARIANTES:
  L2_MUTATIONS=0 · FINDINGS_FINGERPRINT intacto (sin recorrer L2) · human_state sin cambios ·
  LLM_CALLS=0 · G4d=0 · decomposition.yaml 0 escrituras (hash sin cambio, verificado en test) ·
  egress=0 (sin red en ningún módulo de esta ronda)

VEREDICTO_R4 = PASS (ver §5.1 abajo)
ATRIBUCIÓN   = CALIBRACIÓN (Relevance Model), con reserva de generalización HELDOUT ·
               COMPOSER = INDETERMINADO (ver §5.2 abajo)
```

---

## §5.1 · Aceptación de R4

```
fixture congelado ANTES de la primera medición         ✓ (commit del fixture antes del de medición)
≥150 pares construidos                                  ✓ 361
≥15 por categoría                                       ✓ mínimo 29 (PROCEDURAL_VS_TECHNICAL)
ambos perfiles de forma en cada categoría               ✓ (mínimo 2, ver limitación abajo)
particiones CALIBRATION/HELDOUT disjuntas por req_id    ✓
CONFIG_R4 sin cambios entre congelamiento y medición    ✓ (un solo hash, sin recomputar)
LLM_CALLS = 0 · invariantes todos verdes                ✓
medición reproducible (dos corridas → resultados idénticos) ✓ (test_shadow_r4_fixture_builder,
                                                              mismo seed → mismo fixture_hash)
justificación de datos sintéticos producida             ✓ (campo synthetic_data_justification
                                                              del fixture, ver abajo)
```

**R4 = PASS.** El experimento es válido con independencia de que el Relevance Model salga bien
o mal medido (y de hecho sale con resultados mixtos, ver abajo).

**Limitación declarada, no oculta** (per instrucción E2: "si `decomposition.yaml` no ofrece
suficientes requisitos de un perfil, documentarlo... no rellenar con duplicados"):
`PROCEDURAL_VS_TECHNICAL` tiene solo 2 pares en el perfil `FEW_LONG` (contra 27 en
`MANY_SHORT`) -- la mayoría de los requisitos `FEW_LONG` de `decomposition.yaml` no tienen
sub-criterios con fraseo explícitamente procedimental ("proceso"/"process") detectable por la
regla léxica fija usada; no se generaron pares duplicados para forzar el balance.

**Limitación adicional, descubierta al medir (no anticipada en E2)**: la transformación
`TECHNICAL_PARAPHRASE` (sustitución léxica fija) preserva demasiado solapamiento con el texto
original -- alcanzó recall 1.0 con el umbral actual, sin tensionar el mecanismo. El caso REAL
que motivó R1/R4 (`sec-0005`, "*With the FactoryTalk View SE electronic signature feature...*")
es una paráfrasis MUCHO más agresiva (reformulación completa, no sustitución palabra-por-
palabra) que ninguna transformación de este fixture reproduce. **El fixture construido mide el
mecanismo bajo paráfrasis leve; no reproduce la dificultad real observada en R2.** Esto es
precisamente lo que `synthetic_data_justification` debe declarar que el dato sintético NO puede
demostrar -- y aquí se confirma con evidencia, no como advertencia genérica.

---

## §5.2 · Atribución

**Paso 1 — ¿el mecanismo separa las clases?**

`ACHIEVABLE_OPTIMUM` en CALIBRATION: **SÍ existe** un umbral (0.44) que alcanza `T_recall≥0.90`
y `T_precision≥0.80` simultáneamente. Confirmación por perfil de forma: la divergencia
MANY_SHORT vs. FEW_LONG en el umbral actual es de 0.030 (0.678 vs. 0.648) -- **no marcada**, no
confirma la inestabilidad del IDF local como causa dominante bajo esta medición.

**→ CAUSA = CALIBRACIÓN.** El Relevance Model no requiere rediseño de fórmula según esta
medición; requiere recalibración de umbral, con la reserva siguiente:

**Reserva, sin resolver aquí (decisión de Capa 9)**: el umbral óptimo hallado en CALIBRATION
(0.44) **no se sostiene con margen en HELDOUT** (recall 0.865 < 0.90) y el fixture que produjo
este resultado tiene la limitación de paráfrasis-demasiado-leve documentada en §5.1. Esto
significa que "CALIBRACIÓN" es la atribución que la regla mecánica de §5.2 indica con los datos
de hoy, pero **no implica que recalibrar a 0.44 (u otro valor) resuelva el problema real
observado en R2** -- el instrumento que produjo este veredicto no reprodujo la dificultad real
de `sec-0005`. Recalibrar y volver a medir contra un fixture con paráfrasis más agresiva (o
directamente contra más casos `REAL_ADJUDICATED`) es la verificación pendiente antes de que
§6 pueda cumplirse.

**Paso 2 — ¿se puede juzgar al Composer?**

El Relevance Model, bajo el umbral CONGELADO actual (sin recalibrar), **no alcanza los
objetivos** (`REAL_ADJUDICATED`: precisión/recall 0.0/0.0; fixture global: precisión 0.667 <
0.80).

**→ COMPOSER = INDETERMINADO.** No se remedia el Composer en esta ronda ni se le atribuye
responsabilidad por la rúbrica 3/5 de `sec-0016` -- coherente con el hallazgo ya reportado en
R2: esa narrativa se construyó sobre el único candidato que Capa 9 adjudicó como no relevante.

**Paso 3.** No aplica (no se remedia ninguno de los dos componentes en esta ronda).

---

## Qué se implementó (sin remediar nada del Relevance Model ni del Composer)

- `qstate7.py` (7 tests) — Q-STATE-7, detector de SCOPE_DRIFT en la salida, reutiliza
  `relevance_model._tokenize` por lectura, constante propia `_DRIFT_MIN_MATCHED=2` sin relación
  con los umbrales del Relevance Model.
- `phase_equivalence_table.py` (5 tests) — tabla versionada y firmada, reconcilia vocabulario
  `CF6-3` ↔ `CF6-v2-R5` en `cf6_pilot_scope.py` sin relajar el chequeo `c_cf6_3`.
- Corrección del patrón dry-run/producción en `cf6_pilot_runner.py` y `cf6_pilot_runner_v3.py`
  (4 tests nuevos), mismo mecanismo que `cf6_r2_runner.py`.
- `CF6_v2_R4_CONFIG_R4.json` — hash congelado de todos los componentes relevantes.
- `r4_fixture_builder.py` (11 tests) — 361 pares construidos, `CF6_v2_R4_FIXTURE.json`.
- `r4_measure.py` (4 tests) — medición completa, `CF6_v2_R4_MEASUREMENT.json`.

**31 tests nuevos en total**, 0 llamadas LLM en su ejecución. `-k shadow`: 281 passed, 1 failed
(misma falla pre-existente no relacionada, reproducida igual sin ningún código de esta ronda).

---

## §6 · Condición para repetir R2 — estado actual

Ninguna de las 8 condiciones está satisfecha todavía (ninguna remediación se aplicó en esta
ronda, por diseño de la instrucción). **La repetición de R2 sigue sin autorizar.**

## Cierre

E1→E5 ejecutados de forma continua, sin gates intermedios, 0 llamadas LLM. Se detiene aquí,
conforme a la instrucción. Ninguna remediación se aplicó al Relevance Model, al prompt del
Composer, ni a `decomposition.yaml`. Decisión de Capa 9 pendiente: (a) si recalibrar el umbral
del Relevance Model dado el hallazgo de §5.2, y (b) si autorizar una iteración del fixture que
corrija la limitación de paráfrasis-demasiado-leve antes de esa recalibración.

---

## Adenda — resultado de la iteración v2 del fixture (autorizada por Capa 9, 2026-09-05)

```
FIXTURE_HASH (v2) = df35ab12999498d4...
```

**Métricas (fixture v2, umbral CONGELADO actual, sin recalibrar):**
```
global:       precisión 0.663 · recall 0.984  (TP=185 FP=94 FN=3 TN=79, n=361)
CALIBRATION:  precisión 0.682 · recall 0.957  (n=98)
HELDOUT:      precisión 0.657 · recall 0.993  (n=263)
por perfil:   MANY_SHORT precisión 0.672 recall 0.975 (n=232)
              FEW_LONG   precisión 0.648 recall 1.000 (n=129)
```
El recall global bajó de 1.0 (v1) a 0.984 (v2) -- la paráfrasis más agresiva SÍ logró que el
umbral actual perdiera 3 casos que antes pasaba trivialmente. El fixture ahora tensiona
genuinamente el mecanismo, a diferencia de v1.

**ACHIEVABLE_OPTIMUM (CALIBRATION, v2):** el óptimo se DESPLAZÓ de `threshold=0.44` (v1) a
**`threshold=0.2667`** -- alcanza `T_recall=0.905` y `T_precision=1.0`. Verificado en HELDOUT
con el MISMO umbral: **recall=0.952, precisión=1.0** -- **esta vez SÍ se sostiene con margen en
HELDOUT** (0.952 > 0.90), a diferencia de v1 (que se quedaba en 0.865 < 0.90). La reserva de
generalización de la versión v1 de este reporte queda, en ese sentido, resuelta.

**Hallazgo crítico, no anticipado, que cambia la lectura de la atribución**: el umbral óptimo
hallado en el fixture v2 (`0.2667`) es **más alto** que el `weighted_ratio` de LOS DOS ÚNICOS
candidatos que Capa 9 confirmó como genuinamente `RELEVANT` en `REAL_ADJUDICATED`:

```
rec-f2c131db4e52163d (sec-0005, sc1, "electronic signature" / nombre del firmante) ratio=0.0909
rec-33acbc832665ade8 (sec-0005, sc2, "electronic signature" / fecha y hora)        ratio=0.0811
umbral óptimo hallado (fixture v2, CALIBRATION+HELDOUT)                            = 0.2667
```

**Recalibrar el umbral del Relevance Model al valor que este fixture (incluso ya endurecido)
recomienda NO recuperaría ninguno de los 2 casos reales confirmados** -- ambos ratios reales
quedan muy por debajo del óptimo sintético. Es decir: **incluso la paráfrasis v2, deliberadamente
más agresiva que v1, sigue siendo más FÁCIL que la paráfrasis real observada en `sec-0005`.** El
patrón real (reformulación completa a nivel de oración, mención de una *característica* del
sistema sin ecoar el sub-criterio específico) no está capturado por ninguna transformación
puramente léxica (sustitución de sinónimos), por agresiva que sea -- el fenómeno parece
depender de una reestructuración semántica/sintáctica que un diccionario de sinónimos, sin
LLM, no puede replicar de forma fiel.

**REAL_ADJUDICATED sin cambio** (no depende del fixture): precisión 0.0 / recall 0.0.

### Atribución revisada

`ACHIEVABLE_OPTIMUM` v2 SÍ alcanza ambos objetivos en CALIBRATION **y** se sostiene en HELDOUT
(a diferencia de v1) → mecánicamente, **CAUSA = CALIBRACIÓN** se confirma con más fuerza que en
v1 para el INSTRUMENTO SINTÉTICO. Pero el hallazgo del umbral-vs-ratios-reales de arriba
demuestra que **ese resultado no es transferible al problema real que motivó R1/R4** -- el
instrumento (incluso mejorado) sigue sin reproducir la dificultad observada. La atribución
mecánica de la regla §5.2 y la utilidad práctica de esa atribución divergen aquí, y se reportan
ambas, sin resolver la divergencia por decisión propia:

```
ATRIBUCIÓN MECÁNICA (regla §5.2 aplicada al fixture v2)     = CALIBRACIÓN
UTILIDAD DE ESA ATRIBUCIÓN PARA EL PROBLEMA REAL             = NULA (el umbral recomendado no
                                                                 habría cambiado el resultado
                                                                 real de R2)
COMPOSER = INDETERMINADO (sin cambio -- el Relevance Model, con el umbral actual, sigue sin
           alcanzar los objetivos sobre REAL_ADJUDICATED)
```

### Qué implica esto para §6 (condición de repetir R2)

La condición 3 de §6 ("El Relevance Model alcanza T_recall y T_precision en HELDOUT") **se
cumple para el fixture sintético** pero **NO hay evidencia de que se cumpliría sobre
documentos reales** -- el único dato real disponible (`REAL_ADJUDICATED`, n=27, 2 positivos)
indica lo contrario. Recalibrar y repetir R2 sobre esa base sería, con la evidencia actual,
una decisión no respaldada por datos reales, solo por el instrumento sintético.

**Recomendación técnica, no una decisión** (Claude Code no autoriza, solo señala): antes de
recalibrar, el paso de mayor valor parece ser ampliar `REAL_ADJUDICATED` -- más pares
etiquetados por un humano sobre documentos reales, no más iteraciones del generador sintético.
La construcción determinista (sin LLM) tiene un techo demostrado: no reproduce paráfrasis real.

### Invariantes de esta adenda

`LLM_CALLS=0` · `decomposition.yaml` sin escrituras (verificado en test) · `relevance_model.py`
sin modificar · `CONFIG_R4` sin cambio (no depende de `r4_fixture_builder.py`) · 15/15 tests de
`r4_fixture_builder`/`r4_measure` pasan con la v2 · `-k shadow`: 281 passed, 1 failed (misma
falla pre-existente no relacionada).

**STOP.** No se recalibró nada. No se tocó el Composer. Decisión de Capa 9 pendiente: si
autoriza ampliar `REAL_ADJUDICATED` (más pares reales etiquetados) antes de cualquier
recalibración, dado que el camino sintético demostró, dos veces, un techo de fidelidad.
