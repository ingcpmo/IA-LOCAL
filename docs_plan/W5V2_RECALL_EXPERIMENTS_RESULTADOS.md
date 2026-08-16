# W5 V2 — Resultados de experimentos de recall (Bloque 3, post-Piloto 1)

Autoridad: Capa 9 = Cesar. Claude Code = Capa 8.
`PILOT_EXECUTION-2026-004` (confirmada por Cesar) autoriza estos experimentos,
tope duro 60 llamadas. Cada experimento corre EXACTAMENTE los 9 fixtures de
`W5V2_RECALL_FIXTURE_SET_DRAFT.md` (7 positivos + 2 negativos), fuera de
`evaluate_chunked()`/`corpus_runner` (diagnóstico aislado, nunca
`run_context='pilot'`/`'production'`, nunca cuenta para D4-A ni corpus).

Criterio de éxito de cualquier configuración: `recall >= 6/7` positivos con
cita anclada, `2/2` negativos rechazados, `schema_valid_rate = 100%`.

## H1 — IDIOMA — **FAIL**

**Configuración:** mismo modelo (`qwen2.5:7b-instruct-q4_K_M`), mismo
`num_predict`/`num_ctx`/`temperature=0.0`, mismos criterios mínimos de
evidencia y texto normativo del catálogo (sin tocar, ver nota de alcance
abajo) — SOLO se tradujo `common_contract` (instrucciones) y `label` de
cada checkpoint al inglés, para los 4 agentes (part11/annex11/alcoa/cgmp211).
Script: `h1_experiment.py` (scratchpad de sesión, no versionado — reproducible
desde este documento).

**Nota de alcance (deliberada):** el texto normativo canónico
(`citation_text`, ya en inglés por ser cita literal de la norma) y los
`evidence_min_criteria` (redactados en español en `requirements.yaml`) NO se
tradujeron — son contenido gobernado del catálogo, fuera de alcance de un
experimento de prompt. El prompt resultante queda parcialmente bilingüe
(instrucciones en inglés, criterios en español); ver "Pregunta abierta" al
final.

**Resultado (9/9 llamadas completadas, wall time total ~1h55m):**

| Fixture | Tipo | estado | anchored | Nota |
|---|---|---|---|---|
| P1 | positivo | cumple_parcialmente | **false** | citó el texto de la NORMA 21 CFR 11.10(e), no el documento |
| P2 | positivo | no_cumple | false | — |
| P3 | positivo | cumple_parcialmente | **false** | citó una paráfrasis razonable, no una transcripción literal |
| P4 | positivo | evidencia_insuficiente | false | — |
| P5 | positivo | — | — | **schema inválido** (JSON mal anidado, mismo patrón que el fallo técnico 1/8 del Piloto 1) |
| P6 | positivo | evidencia_insuficiente | false | — |
| P7 | positivo | no_cumple | false | — |
| N1 | negativo | evidencia_insuficiente | false | correcto — rechazo esperado |
| N2 | negativo | evidencia_insuficiente | false | correcto — rechazo esperado |

```
recall: 0/7  (igual que el baseline en español)
negativos correctamente rechazados: 2/2
schema_valid_rate: 8/9 = 0.89
veredicto: FAIL (recall no alcanza 6/7)
```

**Conclusión: el idioma NO es la causa raíz del problema de recall.**
Traducir instrucciones y etiquetas a inglés no movió el recall — sigue en
0/7, igual que la corrida original en español.

## Pregunta abierta de Cesar: ¿el análisis en inglés sería de mejor calidad, evitaría problemas de interpretación?

**Respuesta corta: no hay evidencia de eso en este experimento — si acaso, apunta a lo contrario.**

Lo que SÍ cambió entre español e inglés no fue el recall (0/7 en ambos), sino
el **modo de fallo**:

- **En español** (corrida real del Piloto 1): el modelo se queda callado.
  Los 9 registros verificados salieron con `evidencia_exacta=""` — cero
  intentos de cita, cero riesgo de cita falsa, pero también cero valor.
- **En inglés** (H1): en 2 de 7 positivos (P1, P3) el modelo SÍ produjo una
  cita — pero ninguna de las dos ancla en el documento real. P1 citó casi
  textualmente el propio texto de la norma 21 CFR 11.10(e) en vez de citar
  la página 45 del documento evaluado; P3 citó una paráfrasis razonable
  ("The system contains the Rockwell FactoryTalk Historian SE software...")
  que tampoco es una transcripción literal.

Esto es, si acaso, un modo de fallo **peor** para un sistema regulatorio: una
cita que "suena a evidencia real" pero está inventada o mal atribuida es más
peligrosa que el silencio, porque un revisor humano apurado puede confundirla
con evidencia genuina. El silencio total (patrón español) es más seguro
precisamente porque es obviamente inútil — nadie lo confunde con un hallazgo
válido. El verificador determinista (`_is_anchored`) atrapó ambos casos
correctamente, así que el control de seguridad siguió funcionando — pero la
señal cualitativa es que el inglés no mejoró la interpretación, cambió el
tipo de error de "omisión honesta" a "alucinación con apariencia de rigor".

**Advertencia de tamaño de muestra:** esto es UNA corrida sobre 9 fixtures,
no una caracterización estadística. No alcanza para afirmar con certeza que
el inglés empeora la calidad — alcanza para descartar que la mejore de forma
clara, y para registrar una observación cualitativa concreta que merece
seguimiento si se repite en H2-H6.

**Variable no probada, que sigue abierta:** un prompt COMPLETAMENTE en
inglés (incluyendo criterios del catálogo, no solo instrucciones) podría
comportarse distinto — este experimento no lo descarta, solo descarta que
la traducción parcial (solo instrucciones) alcance el criterio de éxito.
Traducir el catálogo es un cambio de contenido gobernado (fuera de alcance
de este bloque de experimentos) y no se recomienda solo para perseguir esta
hipótesis sin evidencia más fuerte primero.

## H2 — DESEMPAQUETADO (1 requirement/llamada) — **FAIL, recall final 2/7 (ver re-verificación abajo)**

**Configuración:** UNA variable respecto del baseline real del Piloto 1 —
mismo prompt GOBERNADO en español (mismo `common_contract`/`label` de
siempre; no se combina con H1 porque H1 no mostró ganancia), pero cada
llamada evalúa UN SOLO `requirement_id` (el del fixture) en vez de los 5-9
del agente completo. Script: `h2_experiment.py` (scratchpad de sesión).

**Resultado (9/9 llamadas completadas, 60.0 min total — 2.5-3x más rápido por llamada que H1):**

| Fixture | Tipo | estado | anchored | wall (s) |
|---|---|---|---|---|
| P1 | positivo | cumple_parcialmente | false* | 548.2 |
| P2 | positivo | evidencia_insuficiente | false | 246.9 |
| P3 | positivo | evidencia_insuficiente | false | 363.7 |
| P4 | positivo | evidencia_insuficiente | false | 436.6 |
| P5 | positivo | **cumple_parcialmente** | **true** | 245.4 |
| P6 | positivo | evidencia_insuficiente | false | 568.4 |
| P7 | positivo | evidencia_insuficiente | false | 323.8 |
| N1 | negativo | evidencia_insuficiente | false | 368.5 |
| N2 | negativo | evidencia_insuficiente | false | 497.0 |

```
recall: 1/7  (P5 -- primer positivo anclado en las 3 corridas hasta ahora)
negativos correctamente rechazados: 2/2
schema_valid_rate: 9/9 = 1.00  (antes 0.89 en H1; el desempaquetado tambien
  parece reducir el fallo estructural de JSON mal anidado, consistente con
  menos carga por llamada)
veredicto: FAIL (recall no alcanza 6/7)
```

**P5 (ALCOA_CONTEMPORANEOUS, RW-0005 p.45) ancló de verdad**: cita real y
literal sobre la función de firma electrónica de FactoryTalk View SE.

**Hallazgo colateral en P1 (llevó al fix de abajo):** el modelo citó, casi
palabra por palabra, un pasaje real de la página 45 (tabla de campos del
Audit Trail de cambio de umbral de alarma crítica) — pero `anchored=false`.
Investigado a fondo: no fue alucinación.

## Fix aplicado entre H2 y H3: normalización de marcadores de viñeta

**Causa raíz de la cita "fantasma" de P1:** el PDF fuente usa un glifo de
viñeta de la fuente Wingdings/Symbol del propio PDF (carácter de zona de
uso privado, ej. U+F0B7) para cada ítem de una lista de 9 campos; el modelo,
al citar la MISMA lista palabra por palabra, la reformatea con un guión
ASCII `"- "`. Contenido idéntico, marcador de viñeta distinto. Con 9 ítems
de lista, 9 caracteres distintos bastan para tirar el ratio de
`SequenceMatcher` del verificador real (`evidence_verifier.match_citation`)
por debajo del umbral fuzzy (0.93 → medido en 0.80), así que una cita
genuina caía como `not_found`.

**Verificación de que esto NO era solo un artefacto de mi script de
diagnóstico:** se probó también contra `evidence_verifier.match_citation()`
— la función REAL que usa el pipeline verificado de producción (no la
`chunked_engine._is_anchored()` simplificada que usaban mis scripts H1/H2)
— y dio el mismo resultado (`not_found`, score 0.80). El defecto es real y
afecta al pipeline de producción, no solo al instrumento de medición.

**Fix aplicado** (`factory/regulatory/evidence_verifier.py`, función
`_normalize`): mismo principio que el fix W5.6 ya documentado en ese mismo
archivo (page furniture) — remoción determinística de RUIDO DE FORMATO,
nunca de contenido, nunca relaja el umbral fuzzy ni acepta una cita
semánticamente similar. Se agregó `_strip_bullet_markers()`: elimina el
marcador de viñeta al INICIO de cada línea (glifos Unicode/PDF conocidos, o
un guión/asterisco ASCII) SOLO cuando va seguido de espacio — una palabra
compuesta con guión que quedó al inicio de renglón por el salto de línea
del PDF (sin espacio después del guión) nunca se toca.

**Verificado:** la cita de P1 pasa de `('not_found', 0.80)` a
`('normalized', 1.0)` — coincidencia literal real tras quitar el ruido de
formato, no una relajación del umbral. 2 tests nuevos en
`test_evidence_verifier_v2.py` (el caso real de P1 reproducido en miniatura,
y un test negativo que confirma que una palabra compuesta con guión
partida en el salto de línea nunca se trata como viñeta). Suite completa
corrida sin regresiones nuevas.

**Re-verificación retroactiva (sin gastar llamadas nuevas):** se re-corrieron
las citas YA CAPTURADAS de H1 y H2 contra `evidence_verifier.match_citation()`
con el fix aplicado, para ver si el recall oficial cambia:

- **H1: sigue en 0/7.** El fix no ayuda aquí porque los fallos de H1 son de
  contenido real (P1 citó la norma en vez del documento, score 0.38; P3
  parafraseó en vez de transcribir, score 0.879 — ambos genuinamente no
  anclan, no es un problema de viñetas).
- **H2: sube de 1/7 a 2/7 oficialmente.** La cita de P1 (antes `not_found`
  0.80) ahora da `normalized` 1.0 con el verificador real corregido — es el
  mismo caso que motivó el fix, confirmado con el path de producción real
  (no el `_is_anchored` simplificado del script de diagnóstico).

**H2 recall final, oficial: 2/7.** Sigue sin alcanzar el criterio de éxito
(≥6/7), pero es la primera mejora medible sobre el baseline (0/7) en toda
la remediación.

La corrida real del Piloto 1 original (2026-08-08, antes de H1/H2) no se
re-verificó retroactivamente porque sus checkpoints no capturaron
`evidencia_exacta` en ningún caso (0 citas intentadas en español) — no hay
nada que re-verificar ahí; el defecto de viñetas solo puede afectar casos
donde el modelo SÍ produjo una cita.

## H3 — DOS ETAPAS (extraer → evaluar) — **FAIL, peor que H2**

**Configuración:** sobre la base de H2 (1 requirement/llamada, prompt
gobernado en español), se separó en dos llamadas: Etapa 1 pide SOLO
extraer citas literales relevantes (sin clasificar nada); cada cita se
verifica de inmediato contra `evidence_verifier.match_citation()` (la
validación A real); Etapa 2 clasifica los criterios usando ÚNICAMENTE las
citas que sobrevivieron la Etapa 1 -- si ninguna sobrevive, la Etapa 2 ni
se llama. Script: `h3_experiment.py`.

**Resultado (9 fixtures, 10 llamadas reales de un máximo posible de 18, 23.4 min total):**

| Fixture | quotes candidatas (etapa 1) | quotes verificadas | etapa 2 llamada | estado | anchored |
|---|---|---|---|---|---|
| P1 | 1 | 1 | sí | cumple | **true** |
| P2 | 0 | 0 | no | evidencia_insuficiente | false |
| P3 | 0 | 0 | no | evidencia_insuficiente | false |
| P4 | 0 | 0 | no | evidencia_insuficiente | false |
| P5 | **0** | 0 | no | evidencia_insuficiente | false |
| P6 | 0 | 0 | no | evidencia_insuficiente | false |
| P7 | 0 | 0 | no | evidencia_insuficiente | false |
| N1 | 0 | 0 | no | evidencia_insuficiente | false |
| N2 | 0 | 0 | no | evidencia_insuficiente | false |

```
recall: 1/7  (peor que el 2/7 oficial de H2)
negativos correctamente rechazados: 2/2
schema_valid_rate: 1.00
total_calls: 10 (de hasta 18 posibles -- 8 fixtures pararon en etapa 1)
veredicto: FAIL
```

**Hallazgo negativo relevante:** la premisa de H3 ("extraer es una tarea
fácil para un 7B") NO se sostuvo. **P5 es el caso más revelador**: en H2 el
modelo SÍ encontró y ancló correctamente el pasaje de firma electrónica de
esa misma página (recall confirmado). En H3, con el mismo modelo y la
misma página, la Etapa 1 (solo extracción, sin pedir clasificación)
devolvió `{"quotes": []}` -- nada. Las 8 llamadas de extracción sin
resultado fueron además sospechosamente rápidas (71-150s, muy por debajo de
los 250-570s típicos de una llamada de clasificación completa), consistente
con que el modelo trata la tarea de "solo extraer, sin evaluar cumplimiento"
como de bajo esfuerzo/bajo riesgo y responde superficialmente en vez de
peinar la página a fondo.

**Conclusión: separar extracción de evaluación, tal como está diseñado
aquí, no ayuda -- empeora.** Pedirle al modelo que clasifique criterios
directamente (H2) lo obliga a comprometerse con una lectura más completa de
la página que pedirle solo que "busque citas relevantes" de forma aislada.
H3 queda descartada en esta forma; no se recomienda combinarla con las
hipótesis siguientes.

## H4 — SCHEMA SIMPLIFICADO — **FAIL, recall igual a H2 pero 2.4x más rápido**

**Configuración:** sobre la base de H2 (1 requirement/llamada, prompt
gobernado en español, catálogo real sin tocar) -- la única variable nueva:
el schema de salida por criterio se redujo al mínimo
(`criterion_index`/`status`/`evidence_quote`), eliminando `criterion_text`
(redundante), `evidence_location`, `justification` y `limitations`. Sin
llamada de explicación posterior (no hacía falta para medir recall).
Script: `h4_experiment.py`.

**Resultado (9/9 llamadas, 24.6 min total -- vs 60.0 min de H2):**

| Fixture | estado | anchored | match | wall (s) |
|---|---|---|---|---|
| P1 | cumple | **true** | normalized 1.0 | 277.1 |
| P2 | no_cumple | false | not_found | 150.2 |
| P3 | no_cumple | false | not_found | 120.9 |
| P4 | no_cumple | false | not_found | 153.5 |
| P5 | cumple | **true** | normalized 1.0 | 146.6 |
| P6 | no_cumple | false | not_found | 190.7 |
| P7 | no_cumple | false | not_found | 125.3 |
| N1 | no_cumple/evidencia_insuficiente | false | not_found | 122.6 |
| N2 | no_cumple | false | not_found | 186.3 |

```
recall: 2/7  (mismos dos casos que H2: P1 y P5 -- exactamente igual)
negativos correctamente rechazados: 2/2
schema_valid_rate: 9/9 = 1.00
total_wall_seconds: 1473.2 (24.6 min)
veredicto: FAIL (recall no alcanza 6/7)
```

**Conclusión: el schema verboso NO era el cuello de botella del recall.**
Simplificar los campos por criterio no encontró ni un caso nuevo -- los
mismos P1/P5 que ya detectaba H2, ni uno más, ni uno menos. Pero **sí hubo
una ganancia real de eficiencia**: 2.4x más rápido en wall time total
(24.6 min vs 60.0 min) con el mismo recall e igual `schema_valid_rate`
(100% en ambos). Como cambio de costo (no de recall), H4 es una
combinación candidata a quedar en la configuración final una vez que
alguna otra hipótesis (H5/H6) mejore el recall en sí -- reduce el costo
por llamada sin perder nada de lo que H2 ya lograba.

## Síntesis H1-H4

| Experimento | Recall | Negativos | Schema válido | Wall total | Veredicto |
|---|---|---|---|---|---|
| Baseline (Piloto 1 real) | 0/7 | 2/2 | 7/8 (1 fallo técnico) | ~2h10m (8 llamadas) | NO-GO |
| H1 (idioma) | 0/7 | 2/2 | 8/9 | ~1h55m | FAIL |
| H2 (desempaquetado) | 2/7 | 2/2 | 9/9 | 60.0 min | FAIL, primera mejora real |
| H3 (dos etapas) | 1/7 | 2/2 | 9/9 | 23.4 min | FAIL, peor recall que H2 |
| **H4 (schema simple, sobre H2)** | **2/7** | 2/2 | 9/9 | **24.6 min** | FAIL, igual recall que H2, 2.4x más rápido |

**Configuración recomendada para seguir combinando:** H2 + H4 (desempaquetado
a 1 requirement/llamada + schema simplificado) -- mismo recall que H2 solo,
a una fracción del costo. Techo actual: 2/7, lejos del criterio de éxito
(≥6/7). Ninguna hipótesis de prompt/formato probada hasta ahora resuelve el
problema de fondo. Siguiente paso del plan: **H5 (modelo alternativo)** --
la matriz de experimentos solo la contempla "si H1-H4 no alcanzan el
criterio de éxito", que es exactamente donde estamos.
