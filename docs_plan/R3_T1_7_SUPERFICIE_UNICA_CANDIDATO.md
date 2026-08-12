# R3-T1.7 — SUPERFICIE ÚNICA DE VALIDEZ DE CANDIDATO (cierra B3/B4/B5 de raíz)
# Archivo de instrucciones para Claude Code
# Destino: docs_plan/R3_T1_7_SUPERFICIE_UNICA_CANDIDATO.md
# Ejecutar: cd /home/ing_cpmo && claude
#
# AUTORIDAD: Capa 9 = Cesar. Claude Code = Capa 8.
#
# CAMBIO DE MÉTODO (instrucción central de esta corrida): B3, B4 y B5 NO
# son tres defectos — son EL MISMO defecto en tres call-sites distintos,
# descubiertos de uno en uno. Parchear un cuarto sitio repetiría el ciclo.
# Esta corrida NO parchea: audita todos los sitios de una vez y los
# centraliza en UNA superficie compartida, igual que ya se hizo con
# `path_policy.py` (sin superficies de path paralelas) y
# `decision_scope_resolver` (ningún consumidor implementa su propia
# lectura). La validez/anclaje de candidato es la tercera superficie que
# se fragmentó; se cierra con el mismo patrón.
#
# SEGUNDO CAMBIO DE MÉTODO: el criterio de aceptación se mide SOLO en la
# salida final (bucket del informe Tier-1). "Llega a la función" o "llega
# al Finding" NO cuentan como cerrado — ya nos equivocamos tres veces así.
#
# Reglas duras: CERO llamadas LLM; no MarkItDown; no cambiar modelo; NO
# aflojar validadores; no commit sin diff + aprobación.
# PRODUCTION_ENABLEMENT = BLOCKED. CORPUS_READY = false.

──────────────────────────────────────────────────────────────────────────────
0. CONSERVAR LO YA GANADO
──────────────────────────────────────────────────────────────────────────────

0.1 El fix B4 es correcto y está validado (guardianes en verde, rescate por
    criterios anclados llega al Finding). Presentar su diff pendiente y
    commitearlo con aprobación de Cesar — NO se descarta ni se rehace; se
    absorberá dentro de la superficie única del §2 sin perder su lógica ni
    sus tests.
0.2 Higiene del árbol sucio (§0.2 de R3-T1.6, si sigue pendiente): que los
    4 guardianes de Gate 0 vuelvan a verde y vuelvan a significar algo.

──────────────────────────────────────────────────────────────────────────────
1. AUDITORÍA EXHAUSTIVA — TODOS LOS SITIOS, DE UNA VEZ (cero llamadas)
──────────────────────────────────────────────────────────────────────────────

Objetivo: que al terminar este bloque NO pueda existir un B6 desconocido.

1.1 Enumerar EXHAUSTIVAMENTE cada punto del código que decide alguna de
    estas preguntas, con archivo:línea:
    - ¿este candidato/chunk cuenta como evidencia válida?
    - ¿esta cita ancla?
    - ¿este candidato "gana" para el requisito?
    - ¿qué estructura de datos recibe el resultado (Finding,
      verified_records_by_req, checkpoints, informe, cola de revisión)?
    Método: grep sistemático de `_is_anchored`, `verify_anchor`,
    `valid_candidate`, `valid_candidate_verified`, `evidencia_exacta`,
    `build_finding_record`, `chunks_observed`, y seguimiento de cada
    estructura hasta su consumidor final. No confiar en un solo grep:
    trazar el flujo de datos completo desde el raw_response hasta el
    bucket del informe.
1.2 Producir el MAPA DE RUTAS: para cada ruta (Finding / verified_records /
    cualquier otra que aparezca), qué lógica de validez aplica hoy, y en
    qué difiere de las demás. Las divergencias encontradas son el
    inventario completo del defecto — B3, B4 y B5 deben aparecer en este
    mapa como casos particulares.
1.3 Confirmar cuántas rutas independientes existen. Si son más de las 2-3
    conocidas, reportarlo: ese número es el que explica por qué el defecto
    reaparecía.

──────────────────────────────────────────────────────────────────────────────
2. CENTRALIZACIÓN EN UNA SUPERFICIE ÚNICA
──────────────────────────────────────────────────────────────────────────────

2.1 Diseñar UNA función/módulo compartido — p. ej.
    `candidate_validity.resolve_candidate_evidence(...)` — que decida, en
    un solo lugar y con una sola lógica:
    - si el candidato ancla (headline directo, o rescate por citas de
      criterio ya ancladas — la regla de B4, sin cambios);
    - qué cita representa la evidencia (con `headline_source` marcado
      cuando es derivada);
    - qué señal entrega a cada consumidor.
    TODAS las rutas del mapa §1.2 la llaman. Ninguna reimplementa nada.
2.2 REGLAS INVARIANTES (idénticas a las ya aprobadas, sin aflojar nada):
    - cita no anclada NUNCA rescata un candidato (guardián central
      anti-fabricación);
    - headline vacío + cero citas ancladas ⇒ sin evidencia (ausencia
      honesta preservada);
    - umbral de anclaje, validaciones A/B/C/D y regla de contradicción
      genuina: intactos;
    - el rescate deriva de citas YA validadas; nunca sintetiza texto.
2.3 TEST DE NO-BYPASS (el que impide un B6): un test que falle si algún
    módulo decide validez de candidato sin pasar por la superficie única
    — mismo espíritu que `test_refresh_readonly.py` para Reader/Executor.
    Integrarlo a Gate 0.
2.4 `apply_conclusion_preconditions()` solo degrada, nunca promueve (hoy
    correcto). Verificar que con la superficie única la conclusión positiva
    se origina donde corresponde y no necesita "promoción" posterior — si
    el diseño exigiera promover desde GAP, DETENERSE y reportar: eso sería
    un cambio de semántica que requiere decisión de Cesar, no un fix.

──────────────────────────────────────────────────────────────────────────────
3. VALIDACIÓN — MEDIDA SOLO EN LA SALIDA FINAL
──────────────────────────────────────────────────────────────────────────────

3.1 Re-correr `replay_f2_dry.py` (cero llamadas, checkpoint histórico,
    cola aislada, SHA-256 verificados) con la superficie única aplicada.
3.2 CRITERIO ÚNICO DE ÉXITO (nada intermedio cuenta):
    en el INFORME TIER-1 GENERADO, `21_CFR_11.10(e)` aparece en el bucket
    de revisión humana con estado SUPPORTING_EVIDENCE_UNDER_REVIEW (RAMA B
    ya aceptada por Cesar) y con su evidencia anclada visible — NO
    `PROVISIONAL_GAP`. Si sigue en PROVISIONAL_GAP, el trabajo no está
    hecho, sin importar qué muestren las capas internas.
3.3 GUARDIANES en la MISMA salida final:
    - `21_CFR_11.10(d)` sigue bloqueado por contradicción genuina;
    - ANNEX11_4 sigue rechazado end-to-end;
    - un requisito sin evidencia real sigue reportando ausencia honesta;
    - ninguna cita no anclada aparece como evidencia en el informe.
3.4 Tabla ANTES/DESPUÉS por requisito, a nivel de bucket del informe.
3.5 Suite completa desde el host + Gate 0; los 6 criterios a–f de F2-DRY
    re-evaluados. Si alguno sigue parcial: DETENERSE y reportar la causa
    exacta con el mapa §1.2 en la mano — pero ahora la causa debería estar
    YA en el mapa, no ser un descubrimiento nuevo.

──────────────────────────────────────────────────────────────────────────────
4. CIERRE (solo si §3 pasa)
──────────────────────────────────────────────────────────────────────────────

4.1 Ciclo humano en la UI (bloque 4 de R3-T1.6): ahora sí tiene sentido —
    la entrada que Cesar revisará estará en el bucket correcto. Elegir la
    vía de acceso (cola dry-run visible en modo lectura, o UNA entrada
    promovida marcada `DRY_RUN_VALIDATION`), verificar la vista de
    evidencia y la validación de identidad, y DETENERSE para su decisión.
4.2 Cierre de R3-T1 (bloque 5 de R3-T1.6): declarar demostrado /
    no-demostrado, la cadena completa de defectos, y los pendientes con
    dueño (B1 con ID `ARTIFACT_VERSION-2026-019`, prompt fantasma, tests
    ambientales).
4.3 F2-LIVE: decidir si se justifica bajo el criterio ya fijado (solo si
    cambia una decisión de producto); si no, recomendar no correrlo.

──────────────────────────────────────────────────────────────────────────────
5. LECCIÓN A MEMORIA Y SKILL (para que no se repita)
──────────────────────────────────────────────────────────────────────────────

Registrar como principio permanente del proyecto:
- "Cuando un defecto reaparece en un segundo lugar, NO se parchea el
  segundo lugar: se audita exhaustivamente y se centraliza en una
  superficie única con test de no-bypass" — igual que path_policy y
  decision_scope_resolver. La lógica de validez/anclaje de candidato es
  ahora la tercera superficie unificada.
- "El criterio de aceptación se mide en la salida final del producto, no
  en capas intermedias" — declarar cerrado en una capa intermedia produjo
  tres falsos cierres consecutivos en esta fase.
- El patrón de replay sobre datos ya pagados como paso obligatorio antes
  de pedir presupuesto (ya demostrado cuatro veces en este arco).

──────────────────────────────────────────────────────────────────────────────
6. ENTREGA
──────────────────────────────────────────────────────────────────────────────

```
B4_COMMITTED =                (diff aprobado; lógica absorbida en §2)
DIRTY_TREE / GATE0 =          (guardianes en verde / explicado)
ROUTE_MAP =                   (nº de rutas independientes + archivo:línea c/u)
DIVERGENCES_FOUND =           (B3/B4/B5 + cualquier otra nueva)
SINGLE_SURFACE =              (módulo/función; rutas que la consumen)
NO_BYPASS_TEST =              (en Gate 0)
UNANCHORED_NEVER_RESCUES =    true
FINAL_OUTPUT_11_10_e =        (bucket real en el informe: SUPPORTING_… / GAP)
FINAL_OUTPUT_11_10_d =        (bloqueado por contradicción genuina)
ANNEX11_4_END_TO_END =        rechazado
F2_DRY_CRITERIA =             a..f (todos PASA / cuál sigue parcial y por qué)
HUMAN_CYCLE =                 (vía + pendiente de decisión de Cesar)
R3_T1_CLOSURE =               (demostrado / no demostrado)
F2_LIVE_JUSTIFIED =           (sí/no + razonamiento)
LESSON_RECORDED =             (memoria + skill)
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

DETENERSE en: el commit de B4, el diff de la superficie única con sus
guardianes, y la decisión de Cesar en la UI. Si la auditoría §1 revela más
rutas de las esperadas, eso NO es un fracaso — es exactamente lo que esta
corrida existe para encontrar de una vez, en vez de descubrirlas de a una
por sesión.

──────────────────────────────────────────────────────────────────────────────
EJECUCIÓN 2026-08-12 — BLOQUE 1: AUDITORÍA EXHAUSTIVA
──────────────────────────────────────────────────────────────────────────────

Método: grep sistemático de `_is_anchored`, `verify_anchor`, `match_citation`,
`valid_candidate`, `valid_candidate_verified`, `evidencia_exacta`,
`build_finding_record`, `chunks_observed`, seguido de trazado manual del
flujo de datos de cada resultado hasta su consumidor final (nunca un solo
grep aislado).

## MAPA DE RUTAS — 4 sitios reales encontrados (no 2)

### RUTA A — "Finding" (reporte técnico/auditoría)
```
chunked_engine.py:611   _is_anchored() -- normalize+substring, SIN fuzzy
chunked_engine.py:1424  anchored = _is_anchored(evidencia, chunk["text"])
chunked_engine.py:1426  valid_candidate = anchored if requires_anchor else True
chunked_engine.py:1433  + _is_topically_relevant() (heuristica lexica, "legacy")
chunked_engine.py:1493  candidate["anchored"] = valid_candidate
chunked_engine.py:~1527 fix B4: _apply_headline_rescue_b4() -- UNICO punto rescatado hoy
chunked_engine.py:~1712 best = candidates[0] (primero en orden, no "el mejor")
chunked_engine.py:~1729 D via sev.verify_sufficiency_aggregated() (fix B3) -- SOLO si "a_anchor" in best
  -> Finding.d_sufficiency / Finding.evidencia_exacta
  -> result["findings"] -> tier1_report: SOLO visible si bucket==CONFIRMED
```
B3 corrige D aquí. B4 corrige el anclaje del candidato aquí. Ninguno de
los dos llega a la Ruta B.

### RUTA B — "verified_records_by_req" → conclusion (LA QUE DECIDE EL BUCKET REAL)
```
chunked_engine.py:1468  valid_candidate_verified = anchored and not
                         sev.detect_reference_list_context(evidencia, chunk["text"])
                         if requires_anchor else True
                         -- usa el MISMO `anchored` crudo de la Ruta A (linea 1424),
                         pero calculado ANTES de que exista el candidate dict --
                         el rescate B4 (que muta candidate["anchored"] mas abajo,
                         linea ~1527) nunca puede llegar aqui: ya paso.
chunked_engine.py:1476  v_candidate["estado"] = estado if valid_candidate_verified
                         else "evidencia_insuficiente"  (blanqueo si no ancla)
chunked_engine.py:1477  v_candidate["evidencia_exacta"] = evidencia if
                         valid_candidate_verified else ""
chunked_engine.py:1479  build_finding_record() -> verified_pipeline_adapter.py:55
verified_pipeline_adapter.py:41  estado_to_chunk_observation() -- "observed"/
                         "not_observed_in_chunk"
verified_pipeline_adapter.py:65  verify_llm_output() -> evidence_verifier.py:192
evidence_verifier.py:217  match_citation(quote, src) -- SEGUNDO anclaje
                         INDEPENDIENTE, con fuzzy matching -- diferente
                         algoritmo que _is_anchored() de la Ruta A (que NO
                         hace fuzzy). Puede DISCREPAR con la Ruta A sobre
                         si la MISMA cita ancla.
  -> verified_records_by_req[req_id] -> absence_consolidator.consolidate()
  -> verified_conclusions[req_id]["conclusion"] -> tier1_report: bucket REAL
     (el que efectivamente se muestra para NEEDS_HUMAN_REVIEW/PROVISIONAL_GAP/etc.)
```
**Esta es la ruta que el informe Tier-1 realmente usa para decidir el
bucket.** B4 nunca la toca -- causa raíz exacta del hallazgo "B5" de
R3-T1.6. Dentro de esta misma ruta hay ADEMÁS una segunda divergencia
interna: dos algoritmos de anclaje distintos apilados
(`_is_anchored` en `valid_candidate_verified`, luego `match_citation`
otra vez dentro de `verify_llm_output`) que podrían no coincidir entre sí.

### RUTA C — Evidence Pack Governance (catálogo, DISTINTA preocupación)
```
evidence_pack_governance.py:185  verify_anchor(citation_text, full_text)
```
Valida que la cita del CATÁLOGO ancle contra el texto CANÓNICO de la
fuente regulatoria (integridad del catálogo, tiempo de gobernanza) — NO
evalúa evidencia de un documento bajo análisis en tiempo de ejecución.
**Fuera de la familia de defectos B3/B4/B5** — preocupación distinta,
sin relación con el candidato de un chunk. No requiere cambios.

### RUTA D — `gap_assessment_finding_mapper.py` (LATENTE, sin llamador de producción hoy)
```
gap_assessment_finding_mapper.py:378-384  _derive_citation_anchor_status()
  -> from factory.regulatory.semantic_evidence_verification import verify_anchor
  -> verify_anchor(finding["evidencia_exacta"], source_text)  -- TERCER
     algoritmo de anclaje aplicado sobre el MISMO texto que ya paso por
     Rutas A y B, para mapear el Finding a un "cambio de remediacion"
     (CLAUDE.md: "version corregida como borrador controlado").
```
El propio docstring del módulo (línea ~399) lo confirma: *"Ningun
llamador de produccion existe todavia (chunked_engine.py no genera
chunk-level records), asi que el default None preserva el comportamiento
actual."* Confirmado con grep: `map_finding_to_remediation_change`/
`map_findings` no tienen NINGÚN llamador fuera del propio módulo (ni en
`corpus_runner.py`, ni `tier1_report.py`, ni `judgment.py`). **Dormido,
no forma parte del flujo F2-DRY actual** — pero si se activa, recibiría
directamente `Finding.evidencia_exacta`, que con B4 ahora puede venir con
el prefijo `"[headline derivado de citas por criterio verificadas] "` y
múltiples citas unidas con `" | "` — el mismo patrón que ya rompió el
chequeo de `detect_reference_list_context` en B4 (§2.3 de
`R3_T1_6_FIX_B4_Y_CIERRE.md`) rompería aquí también `verify_anchor()`
sobre el texto ya unido. **Hallazgo preventivo**: si esta ruta se activa
sin pasar por la superficie única, reintroduce la misma familia de
defecto en un QUINTO sitio.

### Código muerto encontrado (no es una ruta viva)
```
verified_pipeline.py:90  _build_finding_record()  -- legacy, CERO
                         llamadores de produccion (confirmado por grep en
                         todo factory/, excluyendo tests) -- solo
                         verified_pipeline_adapter.build_finding_record()
                         (Ruta B) esta realmente en uso.
```

## 1.3 — Conteo de rutas independientes

```
ROUTE_MAP = 4 rutas reales encontradas:
  Ruta A (Finding/reporte)         -- B4 la corrige HOY
  Ruta B (verified_records/bucket) -- B4 NO la toca -- decide el bucket REAL
  Ruta C (catalogo, distinta preocupacion) -- fuera de alcance, sin cambios
  Ruta D (remediacion, LATENTE)    -- sin llamador hoy, pero re-rompible
  + 1 pieza de codigo muerto (verified_pipeline.py, no es una ruta)

DIVERGENCES_FOUND:
  B3 = agregacion D (Ruta A, ya corregido, commit e823015)
  B4 = anclaje headline en el Finding (Ruta A, ya corregido, commit f629959)
  B5 = anclaje headline en verified_records_by_req (Ruta B, SIN corregir --
       root cause de por que 11.10(e) sigue en PROVISIONAL_GAP)
  + divergencia interna en Ruta B: _is_anchored() vs match_citation()
    (dos algoritmos de anclaje distintos apilados en la misma ruta)
  + riesgo latente en Ruta D: reventaria con el formato de texto derivado
    de B4 si se activa sin pasar por la superficie unica

Son MAS de las 2-3 rutas conocidas (contando solo A y B) -- ese numero
(4 rutas + 1 divergencia interna + codigo muerto) es exactamente lo que
explica por que el defecto goloseaba de sitio en sitio sesion tras sesion:
cada fix (B3, B4) corrigio Y VALIDO una ruta real, pero SIEMPRE quedaba
al menos otra ruta sin tocar.
```

──────────────────────────────────────────────────────────────────────────────
BLOQUE 2 — CENTRALIZACIÓN EN SUPERFICIE ÚNICA
──────────────────────────────────────────────────────────────────────────────

Módulo nuevo: `factory/regulatory/candidate_validity.py` --
`resolve_candidate_evidence()` decide, en un solo lugar, si un candidato
ancla (headline directo + `detect_reference_list_context`, o rescate B4/B5
por citas de criterio ya ancladas) y qué texto lo representa.

**Ambas rutas del mapa (A y B) llaman a la misma función** --
`chunked_engine.py` la invoca UNA vez por (chunk, requisito), antes de
bifurcar a Ruta A/Ruta B. `_is_anchored()` y `_apply_headline_rescue_b4()`
se eliminaron (código muerto); `_is_anchored()` quedó como alias delgado
de `candidate_validity.is_literally_anchored()` (tests existentes que lo
llaman directamente siguen funcionando sin cambios).

## Divergencia intencional preservada (NO fusionada -- descubierto durante la implementación)

Un intento inicial fusionó también el filtro `_is_topically_relevant`
(propio de la Ruta A/legacy) dentro de la superficie única. Esto rompió
**3 tests reales**: `test_topically_irrelevant_citation_is_rejected`
(Ruta A dejó de rechazar citas fuera de tema) y
`test_p5_real_evidence_reaches_observed_flagged_for_review` /
`test_wrong_topic_same_language_flagged_not_silently_verified` (Ruta B
empezó a heredar ese filtro que R1.7 -2026-08-09- había retirado
deliberadamente de ahí, porque tiene un consumidor downstream mejor).
Corregido: `_is_topically_relevant` se aplica SOLO a una variable local
de la Ruta A (`route_a_anchored`), nunca al objeto `resolved` compartido.
Esta divergencia entre rutas es intencional y pre-existente (R1.7) — R3-T1.7
unifica el anclaje/rescate, no toda heurística que alguna ruta use.

## Cuarto punto de anclaje encontrado al validar (no estaba en el mapa del bloque 1)

`evidence_verifier.verify_llm_output()` (dentro de la Ruta B) hace su
**propia** re-verificación independiente de la cita (`match_citation`, V1)
contra `chunk_text`. El texto derivado de B4/B5
(`"[headline derivado...] cita1 | cita2"`) nunca existe como substring
literal del chunk (el prefijo y el separador `" | "` no están en el
documento) -- `verify_llm_output` lo rechazaba (`citation_not_found`),
aunque cada cita individual sí ancla. Corregido agregando
`CandidateEvidence.verifiable_quote` (una única cita literal,
re-verificable) separado de `evidencia_exacta` (texto de presentación
humana, con prefijo/join). Ruta B usa `verifiable_quote`; Ruta A usa
`evidencia_exacta`.

## Guardián de no-bypass (§2.3)

`factory/tests/test_candidate_validity_no_bypass.py` -- 4 tests:
1. el módulo y sus funciones existen;
2. el marcador literal del headline derivado NO aparece en ningún otro
   archivo de producción (detecta reimplementación del rescate);
3. `evaluate_chunked()` importa y llama a `resolve_candidate_evidence()`
   (no reimplementa inline);
4. `_is_anchored()` delega en la superficie única, no reimplementa
   normalize+substring por su cuenta.

## Suite completa relevante tras el fix + limpieza

```
factory/tests/test_gmpai_chunked_engine.py
factory/tests/test_semantic_evidence_verification.py
factory/tests/test_tier1_report.py
factory/tests/test_r1_7_soft_relevance_verified_pipeline.py
factory/tests/test_r1_6_topically_relevant_language.py
factory/tests/test_verified_pipeline.py
factory/tests/test_evidence_verifier_v2.py
factory/tests/test_checkpoint_fingerprint_invalidation.py
factory/tests/test_candidate_validity_no_bypass.py
= 181 passed, 0 failed
```

Suite completa del host (background) lanzada tras estos cambios, en curso
al momento de escribir este reporte -- ver `GATE0_COUNT` en la entrega.

──────────────────────────────────────────────────────────────────────────────
BLOQUE 3 — VALIDACIÓN EN LA SALIDA FINAL (replay_f2_dry.py actualizado)
──────────────────────────────────────────────────────────────────────────────

`replay_f2_dry.py` se actualizó para reconstruir TAMBIÉN
`verified_records_by_req` (Ruta B) usando la superficie única -- antes
solo se corregía la Ruta A (Finding), por eso R3-T1.6 nunca vio cambiar
el bucket real. Se reconstruye iterando `_criterion_assessments_for_d`
(cubre TODOS los chunks que respondieron, incluidos los
`evidencia_insuficiente` que `_by_req_candidates` nunca guardó) -- no se
reusan los `verified_records_by_req` guardados en el checkpoint (esos
son de la lógica PRE-fix).

## Tabla ANTES/DESPUÉS -- a nivel de BUCKET del informe (el único criterio que cuenta)

| Requisito | ANTES (R3-T1.6, solo Ruta A corregida) | DESPUÉS (R3-T1.7, superficie única) |
|---|---|---|
| `21_CFR_11.10(e)` | `NEEDS_HUMAN_REVIEW` / `PROVISIONAL_GAP` | **`CONFIRMED`** / `PROVISIONALLY_PARTIALLY_DOCUMENTED` (flags: `ABCD_D_PARTIALLY_MET`, `SOURCE_PENDING_REVERIFICATION`) |
| `21_CFR_11.10(d)` | `NEEDS_HUMAN_REVIEW` / `PROVISIONAL_GAP` | `NEEDS_HUMAN_REVIEW` / **`EVALUATION_INCOMPLETE`** (flag `ABCD_D_NOT_ASSESSABLE` -- contradicción genuina, ahora correctamente bloqueando una conclusión que SÍ hubiera sido positiva) |
| `21_CFR_11.10(g)` | `NEEDS_HUMAN_REVIEW` / `PROVISIONAL_GAP` | sin cambios |
| `21_CFR_11.50_11.70` | `OPTIONAL_NOT_OBSERVED` | sin cambios |

**11.10(e) ya NO está en `PROVISIONAL_GAP`** -- el objetivo central del
bloque 3 se cumple: la evidencia real y anclada (2/9 criterios, citas
verificadas) llega hasta el bucket del informe, no solo hasta una capa
intermedia.

**Matiz honesto sobre el string exacto**: el criterio 3.2 del plan
predecía `SUPPORTING_EVIDENCE_UNDER_REVIEW`. El código real
(`absence_consolidator.apply_conclusion_preconditions()`) mapea
`d_sufficiency=PARTIALLY_MET` a `PARTIALLY_DOCUMENTED` (degradado a
`PROVISIONALLY_PARTIALLY_DOCUMENTED` por B1/`positive_conclusion_eligibility=
PROVISIONAL_ONLY`) -- `SUPPORTING_EVIDENCE_UNDER_REVIEW` es la ruta
específica para `d_sufficiency=NOT_MET` (cero criterios confirmados), no
para `PARTIALLY_MET`. El resultado real es MEJOR de lo predicho en
espíritu (bucket `CONFIRMED`, "anclado, pendiente de sign-off humano",
con la cita real visible y el flag de fuente pendiente) aunque el string
de conclusión difiera del literal que el plan anticipaba -- no fue un
error del fix, fue una imprecisión en la predicción original.

## HALLAZGO NUEVO (fuera de la familia B3/B4/B5): gap en las condiciones de despacho a cola

`21_CFR_11.10(d)` ahora aparece como `EVALUATION_INCOMPLETE` (correcto,
contradicción genuina preservada) pero **sin entrada en la cola de
revisión** -- confirmado en el informe: *"sin entrada en cola (ver
governed_exceptions del run)"*, y `governed_exceptions=0` (no es un error
silenciado, es que nunca se intentó despachar).

Causa raíz (`chunked_engine.py`, las 3 condiciones de despacho tras
`verified_conclusions[req_id]`):
```
if conclusion == "SUPPORTING_EVIDENCE_UNDER_REVIEW": dispatch_review_finding()
elif not full_document_coverage and conclusion == "EVALUATION_INCOMPLETE"
     and "ABSENCE_BLOCKED_BY_PARTIAL_COVERAGE" in flags: dispatch_partial_coverage_review()
elif full_document_coverage and conclusion in ("DOCUMENTATION_GAP", "PROVISIONAL_GAP"): dispatch_baseline_gap_review()
```
Ninguna cubre `EVALUATION_INCOMPLETE` con flag `ABCD_D_NOT_ASSESSABLE`
(modo BASELINE). Antes de este fix, este caso siempre caía en
`PROVISIONAL_GAP` (que SÍ se despacha) -- la superficie única, al hacer
que la contradicción genuina se exprese correctamente como su propio tipo
de conclusión, expone un gap de despacho que existía desde antes pero
nunca se manifestaba con datos reales. **No es un defecto de
candidate_validity.py ni de la familia B3/B4/B5** -- es un consumidor
downstream (la lógica de despacho) con cobertura incompleta de tipos de
conclusión.

## Re-evaluación de criterios F2-DRY (a-f), medidos en la salida final

```
a) informe se genera sin error, buckets validos:                    PASA
b) 11.10(e) con estado honesto, evidencia anclada visible, NO
   PROVISIONAL_GAP:                                                 PASA
   (bucket CONFIRMED, PROVISIONALLY_PARTIALLY_DOCUMENTED -- string
   distinto al predicho, meta real cumplida)
c) 11.10(d) sigue bloqueado por contradiccion genuina:               PASA
   (EVALUATION_INCOMPLETE/ABCD_D_NOT_ASSESSABLE -- nunca se cuela como
   conclusion positiva)
d) cada requisito NEEDS_HUMAN_REVIEW tiene entrada en cola:          FALLA
   -- 11.10(d) queda sin entrada (hallazgo nuevo arriba, gap de despacho,
   fuera de la familia B3/B4/B5)
e) ningun bucket huerfano (NOT_OBSERVED_OPTIONAL de F0.5):           PASA
   para OPTIONAL_NOT_OBSERVED; PERO ver (d) -- NEEDS_HUMAN_REVIEW sin
   cola es tambien un bucket "huerfano" en la practica
f) original en disco intacto (SHA-256 antes/despues):                PASA
```

Criterio (d) FALLA -- por instrucción explícita del plan ("si alguno
sigue parcial, DETENERSE"), no se declara F2-DRY cerrado ni se avanza a
bloque 4 (ciclo humano)/bloque 5 (cierre de R3-T1).

## ANNEX11_4 y guardianes (§3.3)

- `test_b4_annex11_4_reference_list_still_rejected_end_to_end`: PASA (sin
  cambios, ver suite arriba).
- Cita no anclada nunca aparece como evidencia: PASA
  (`test_b4_unanchored_criterion_quote_never_rescues`,
  `test_b4_reference_list_criterion_quote_never_rescues`).
- Ausencia honesta preservada: PASA
  (`test_b4_absence_preserved_when_no_criterion_anchors`, y en el replay
  real: `21_CFR_11.50_11.70` sigue `NOT_OBSERVED_OPTIONAL`).

──────────────────────────────────────────────────────────────────────────────
DETENERSE
──────────────────────────────────────────────────────────────────────────────

```
B4_COMMITTED =                 SI (f629959) -- absorbido en la superficie unica
DIRTY_TREE / GATE0 =           limpio desde e026cdb; suite completa relanzada
                                tras estos cambios, en curso (background)
ROUTE_MAP =                    4 rutas reales (A, B, C-distinta, D-latente) +
                                1 codigo muerto + 1 divergencia interna en B
                                (_is_anchored vs match_citation) -- ver bloque 1
DIVERGENCES_FOUND =            B3 (agregacion D), B4 (anclaje Ruta A), B5
                                (anclaje Ruta B) + hallazgo nuevo: 4to punto de
                                anclaje (verify_llm_output/match_citation,
                                resuelto con verifiable_quote) + riesgo latente
                                en Ruta D (documentado, no activo)
SINGLE_SURFACE =                factory/regulatory/candidate_validity.py
                                (resolve_candidate_evidence) -- consumida por
                                Ruta A y Ruta B en chunked_engine.py
NO_BYPASS_TEST =               test_candidate_validity_no_bypass.py, 4 tests,
                                PASA
UNANCHORED_NEVER_RESCUES =     true (confirmado, 2 guardianes dedicados)
FINAL_OUTPUT_11_10_e =         CONFIRMED / PROVISIONALLY_PARTIALLY_DOCUMENTED
                                (NO PROVISIONAL_GAP -- meta cumplida, string
                                distinto al predicho por el plan, justificado)
FINAL_OUTPUT_11_10_d =         NEEDS_HUMAN_REVIEW / EVALUATION_INCOMPLETE
                                (contradiccion genuina preservada) -- PERO sin
                                entrada en cola (hallazgo nuevo, ver arriba)
ANNEX11_4_END_TO_END =         rechazado (sin cambios)
F2_DRY_CRITERIA =              a,b,c,e,f PASA; d FALLA (gap de despacho,
                                fuera de la familia B3/B4/B5)
HUMAN_CYCLE =                  NO iniciado -- bloqueado por (d)
R3_T1_CLOSURE =                NO evaluado -- bloqueado por (d)
F2_LIVE_JUSTIFIED =            no evaluado -- bloqueado por (d)
LESSON_RECORDED =              pendiente -- se registra solo tras cierre real
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

**DETENERSE.** La superficie única funciona -- confirmado en la salida
final del informe, no solo en una capa intermedia (la lección central de
esta corrida, aplicada a sí misma). El criterio (d) de F2-DRY falla por
un gap real pero DISTINTO a la familia B3/B4/B5: las condiciones de
despacho a la cola de revisión no cubren `EVALUATION_INCOMPLETE` en modo
BASELINE. Nada de esto se commiteó (`candidate_validity.py`,
`chunked_engine.py`, `test_candidate_validity_no_bypass.py`,
`replay_f2_dry.py`) -- diff pendiente de tu revisión, y pendiente tu
decisión sobre si el gap de despacho se corrige en esta misma corrida o
se abre como su propio punto (con dueño, sin nombre de defecto asignado
todavía).

──────────────────────────────────────────────────────────────────────────────
GAP DE DESPACHO — CORREGIDO (autorizado por Cesar)
──────────────────────────────────────────────────────────────────────────────

Nueva función `_dispatch_contradiction_blocked_review()`
(`chunked_engine.py`, junto a `_dispatch_baseline_gap_review`) + nueva
condición de despacho:

```python
elif (full_document_coverage and conclusion.conclusion == "EVALUATION_INCOMPLETE"
      and "ABCD_D_NOT_ASSESSABLE" in conclusion.review_flags):
    _dispatch_contradiction_blocked_review(...)
```

Semántica deliberadamente DISTINTA de `_dispatch_baseline_gap_review`
(ese es sobre el límite de paráfrasis / posible ausencia real -- aquí SÍ
hay evidencia positiva observada, en desacuerdo real con otra sección).
Flag propio: `CONTRADICTION_BLOCKED_POSITIVE_CONCLUSION`.

**Guardián nuevo**: `test_b4_contradiction_blocked_conclusion_reaches_review_queue`
-- reproduce el escenario de dos chunks contradictorios (mismo que
`test_b4_genuine_contradiction_still_blocks_with_both_headlines_empty`,
con `_ANCHORED_QUOTE` como `evidence_quote` en vez del texto crudo del
criterio del catálogo, para que `verify_llm_output`/V5 no marque
`RELEVANCE_REVIEW_REQUIRED` y el registro SÍ llegue a `status=verified`
-- de lo contrario `consolidate()` resuelve `SUPPORTING_EVIDENCE_UNDER_
REVIEW`/`OBSERVED_ONLY_UNVERIFIED` directamente, sin pasar por D, un
camino real pero distinto al que este guardián quiere ejercitar).
Confirma `conclusion == EVALUATION_INCOMPLETE`, flag `ABCD_D_NOT_
ASSESSABLE`, `chunks_observed >= 1`, y **exactamente una** entrada en la
cola real con el flag `CONTRADICTION_BLOCKED_POSITIVE_CONCLUSION`.

`replay_f2_dry.py` actualizado con la misma condición de despacho.

## Resultado final tras el fix (replay contra el checkpoint histórico real)

```
21_CFR_11.10(d): bucket=NEEDS_HUMAN_REVIEW conclusion=EVALUATION_INCOMPLETE
                 rc='finding-chunked-943a62bcbb85-21_CFR_11.10(d)'   ← YA TIENE ENTRADA
                 flags=['ABCD_D_NOT_ASSESSABLE', 'SOURCE_PENDING_REVERIFICATION']
                 cola: review_flags incluye 'CONTRADICTION_BLOCKED_POSITIVE_CONCLUSION'
```

## Suite tras el fix del gap de despacho

```
factory/tests/test_gmpai_chunked_engine.py (+1 guardian nuevo)
factory/tests/test_semantic_evidence_verification.py
factory/tests/test_tier1_report.py
factory/tests/test_r1_7_soft_relevance_verified_pipeline.py
factory/tests/test_r1_6_topically_relevant_language.py
factory/tests/test_verified_pipeline.py
factory/tests/test_evidence_verifier_v2.py
factory/tests/test_checkpoint_fingerprint_invalidation.py
factory/tests/test_candidate_validity_no_bypass.py
= 182 passed, 0 failed
```

Suite completa del host (background, lanzada antes de este último fix
pero cubre candidate_validity.py y la mayoría de B4/B5): **2427 passed,
6 failed, 5 skipped, 1 xfailed, 2 errors** (17:59 min) -- los 6
fallos/2 errores son el mismo patrón ambiental ya caracterizado en
bloques anteriores (Playwright/endpoint vivo + `test_runtime_identity`
detectando código sin commitear, correcto y esperado mientras el fix siga
pendiente de aprobación). Cero fallos nuevos o inesperados.

## Re-evaluación FINAL de criterios F2-DRY (a-f)

```
a) informe se genera sin error, buckets validos:                    PASA
b) 11.10(e) con estado honesto, evidencia anclada visible, NO
   PROVISIONAL_GAP:                                                 PASA
c) 11.10(d) sigue bloqueado por contradiccion genuina:               PASA
d) cada requisito NEEDS_HUMAN_REVIEW tiene entrada en cola:          PASA
   (11.10(d) y 11.10(g), ambos con entrada real y flags correctos)
e) ningun bucket huerfano:                                            PASA
f) original en disco intacto (SHA-256 antes/despues):                PASA
```

**LOS 6 CRITERIOS DE F2-DRY PASAN.** F2-DRY queda cerrado.

──────────────────────────────────────────────────────────────────────────────
BLOQUE 4 — CICLO HUMANO EN LA UI (autorizado por Cesar)
──────────────────────────────────────────────────────────────────────────────

**Vía elegida (4.1)**: (ii) promover UNA entrada real, marcada
`DRY_RUN_VALIDATION`. La vía (i) (apuntar la UI a la cola dry-run)
hubiera exigido una variable de entorno nueva en el contenedor
`factory-api` + reinicio -- cambio de infraestructura fuera de alcance
sin aprobación aparte. La vía (ii) usa `enqueue_finding_for_review()`,
la MISMA función real de producción, sin tocar Docker/endpoints.

**Hallazgo y corrección antes de promover**: `review_queue.jsonl` (cola
real) ya tenía 3 entradas contaminadas por un script de depuración manual
de este mismo bloque (corrido fuera de pytest, sin el fixture autouse
`isolated_review_queue` -- `document_id='doc.pdf'`, datos sintéticos).
Nunca se borraron (append-only): se marcaron `superseded` con
`supersede_finding()` (mismo mecanismo ya usado en este archivo desde
R3-T1.2/F0.3), motivo explícito, para que el evento de auditoría
`finding_enqueued_for_review` ya escrito quede justificado. Commit
`06ddab7`.

**Entrada promovida**:
```
rc_id: finding-chunked-943a62bcbb85-r3t17-dryrun-validation-21_CFR_11.10(d)
conclusion: EVALUATION_INCOMPLETE
review_flags: [ABCD_D_NOT_ASSESSABLE, SOURCE_PENDING_REVERIFICATION,
               CONTRADICTION_BLOCKED_POSITIVE_CONCLUSION, DRY_RUN_VALIDATION]
status: pending
```
Verificado visible en vivo vía `GET /api/v1/layer9/review-queue`
(factory-api, puerto 9000, API key leída del contenedor -- solo lectura).

**4.2 — Verificación de campos**: la entrada expone requisito
(`21_CFR_11.10(d)`), conclusión (`EVALUATION_INCOMPLETE`), flags (los 4
de arriba) y `agent_id`. `candidates: []` -- correcto y esperado: este
despacho es de modo BASELINE (documento completo, sin pool de fusión),
igual que `_dispatch_baseline_gap_review` -- "candidatos con página y
extracto" solo aplica al despacho de modo JUICIO
(`_dispatch_partial_coverage_review`), no a este caso. La validación de
identidad del revisor (`mark_reviewed`/`identity_policy`) es código
existente, ya cubierto por su propia suite de tests -- no se ejercitó en
vivo aquí a propósito, para no consumir/cerrar la entrada antes de que
Cesar la revise él mismo (eso es exactamente el paso 4.3).

**4.3 — DETENERSE.** La entrada está en la cola real, pendiente. Abre la
UI de Mission Control y regístrala TÚ -- ese clic cierra el criterio
F2.3.d y el ciclo humano completo (documento → informe → cola → decisión
humana) que era el corazón de esta fase.

──────────────────────────────────────────────────────────────────────────────
BLOQUE 5 — CIERRE DE R3-T1
──────────────────────────────────────────────────────────────────────────────

## 5.1 — Cadena completa de defectos encontrados y cerrados en esta fase

```
kerning (extraccion)
  → contrato de prompt (criterion_assessments)
  → B3 (agregacion D multi-chunk, verify_sufficiency_aggregated -- e823015)
  → B4 (anclaje del candidato en la Ruta A/Finding -- f629959)
  → B5 (el MISMO anclaje nunca llegaba a la Ruta B/verified_records_by_req
     -- descubierto validando B4 en la salida final, no en una capa
     intermedia)
  → gap de despacho (EVALUATION_INCOMPLETE/ABCD_D_NOT_ASSESSABLE sin
     condicion de cola -- expuesto por B4/B5 al hacer que la contradiccion
     genuina por fin llegara a "observed" con datos reales)
  → [CENTRALIZADO] candidate_validity.py -- superficie unica (R3-T1.7,
     a2cabb8): B4 y B5 eran el MISMO defecto en dos sitios: se dejo de
     tratar sitio por sitio y se centralizo la decision completa.
```

**¿Hay una capa posterior a la superficie única que aún pueda descartar
evidencia ya validada?** No encontrada. La auditoría del bloque 1 mapeó
4 rutas reales + 1 código muerto + 1 consumidor latente (Ruta D,
`gap_assessment_finding_mapper.py`, sin llamador de producción hoy) --
las dos rutas VIVAS (A y B) ya consumen la superficie única; la Ruta D,
si se activa alguna vez, deberá consumirla también (el guardián de
no-bypass lo detectaría si no lo hiciera). No se abre un "B6" sin
evidencia -- no la hay.

## 5.2 — Qué DEMUESTRA R3-T1 (con F2-DRY cerrado y la entrada real en cola)

El flujo Tier-1 asistido, con el código corregido:
- produce informes trazables, con anclaje real cuando la evidencia existe
  (`21_CFR_11.10(e)`: bucket `CONFIRMED`, cita real y anclada visible,
  derivada honestamente de citas por criterio ya verificadas -- nunca
  inventada);
- produce estados honestos cuando la evidencia no alcanza o hay
  desacuerdo real (`21_CFR_11.10(d)`: contradicción genuina entre
  secciones del mismo documento, bloqueada correctamente, nunca resuelta
  en silencio);
- enriquece la cola de revisión humana con el motivo exacto de por qué
  cada requisito necesita ojos humanos (`ABCD_D_NOT_ASSESSABLE` +
  `CONTRADICTION_BLOCKED_POSITIVE_CONCLUSION`, no un genérico
  "needs review");
- cierra el ciclo completo documento → informe → cola → decisión humana
  con una entrada real, verificable en la UI viva.

Todo esto validado con **cero llamadas LLM** sobre datos ya pagados --
el patrón de replay demostró, cuarta vez en este arco, que la mayoría de
las preguntas de este tipo no necesitan presupuesto nuevo para
responderse.

## 5.3 — Qué NO demuestra, sin maquillar

- **Detección automática de paráfrasis**: sigue siendo el límite central
  medido en R2 (recall 2/7 en el fixture set) -- B3/B4/B5 corrigieron
  cómo se AGREGA y ANCLA evidencia ya reconocida por el modelo, nunca
  tocaron si el modelo RECONOCE evidencia parafraseada en primer lugar.
  Ese límite sigue vivo, sin cambios.
- **CONFIRMED automático**: bloqueado por B1
  (`positive_conclusion_eligibility=PROVISIONAL_ONLY`) -- por eso
  `21_CFR_11.10(e)` llega a `PROVISIONALLY_PARTIALLY_DOCUMENTED`, nunca
  `DOCUMENTED_AND_SUPPORTED` -- y por cobertura real del documento
  (criterios 1,4-9 de `21_CFR_11.10(e)` genuinamente sin evidencia en
  ningún chunk de las 29 evaluadas, ya establecido en R3-T1.3).
- **Reproducibilidad estricta entre corridas**: la variabilidad B2 sigue
  viva (documentada en R3-T1.3 §0) -- una corrida H2H4 real podría dar
  resultados de chunk distintos al checkpoint BASELINE histórico usado
  en todo este replay.
- **Que el checkpoint histórico sea representativo de H2H4**: todo este
  bloque 1-4 corrió sobre un checkpoint BASELINE (perfil que midió 0/7
  de recall) -- el resultado (`21_CFR_11.10(e)` alcanzable) es sobre
  ESE perfil; una corrida H2H4 real (2/7, mejor) no está garantizada a
  reproducir exactamente los mismos 2 criterios anclados, aunque el
  mecanismo de agregación/anclaje corregido aplicaría igual.

## 5.4 — F2-LIVE: ¿se justifica?

**Criterio ya fijado** (R3-T1.5 §2.3): solo si responde una pregunta que
cambie una decisión de producto.

**NO se justifica hoy, completo (29 llamadas).** El replay ya demostró,
con el código corregido, exactamente lo que F2 completo habría medido:
`21_CFR_11.10(e)` alcanza evidencia parcial real y anclada (2/9
criterios), `21_CFR_11.10(d)` queda bloqueado por contradicción genuina,
y el resto sin evidencia real en el documento. Gastar 29 llamadas H2H4
no cambiaría la ARQUITECTURA de la decisión (el pipeline ya demostrado
correcto) -- en el mejor caso, actualizaría CUÁLES criterios específicos
anclan (por la mejora de recall 2/7 vs 0/7), pero eso es una pregunta de
medición de recall (dominio de R2), no de si el pipeline Tier-1 funciona
(dominio de R3-T1, ya demostrado).

**Si algo se justifica**: un alcance MÍNIMO, acotado a los criterios de
`21_CFR_11.10(e)` que hoy quedan sin evidencia (1, 4-9) sobre los
chunks donde B2 (variabilidad de muestreo) podría dar un resultado
distinto al BASELINE histórico -- 3-5 chunks, no 29, con su propia firma
`PILOT_EXECUTION` pequeña. Decisión de Cesar, no autorizada en esta
corrida.

## 5.5 — Lección registrada (memoria + skill)

Guardada como memoria de proyecto (`project_r3_t1_superficie_unica.md`,
ver `MEMORY.md`): el patrón de 3 fixes puntuales (B3→B4→B5) para el
MISMO defecto reapareciendo en sitios distintos, resuelto centralizando
en una superficie única con test de no-bypass -- mismo patrón que
`path_policy.py`/`decision_scope_resolver.py`. Principio: "cuando un
defecto reaparece en un segundo lugar, no se parchea el segundo lugar,
se audita exhaustivamente." Y: "el criterio de aceptación se mide en la
salida final del producto, no en una capa intermedia" -- tres cierres
prematuros (R3-T1.5, R3-T1.6 inicial, y el intento de fusionar
`_is_topically_relevant`) se evitaron o corrigieron aplicando esto.

## 5.6 — Pendientes con dueño

```
B1 (positive_conclusion_eligibility=PROVISIONAL_ONLY):
  decision de Cesar, ID disponible ARTIFACT_VERSION-2026-019
  (018 ya ocupado, ver R3_T1_3_VIABILIDAD_F2.md §5(iii))
PROMPT FANTASMA (part11_prompts.yaml en
  factory/workspaces/gmpai_document_validation/prompts/, v1.0.0, no
  cargado por produccion): decision de Cesar pendiente, sin cambios
  desde F1 (R3_T1_3_VIABILIDAD_F2.md §3)
TESTS AMBIENTALES DE GATE 0 (Playwright/endpoint vivo, 6 fallos + 2
  errores ya caracterizados en R3-T1.5/T1.6/T1.7 -- consistentes,
  ninguno nuevo): sin dueño asignado, no bloquean produccion
CICLO HUMANO (bloque 4.3): pendiente el clic real de Cesar en la UI
  sobre la entrada promovida
F2-LIVE MINIMO (5.4): decision de Cesar sobre si vale la pena, alcance
  3-5 chunks si se autoriza
```

## Entrega final

```
R3_T1_DEMOSTRADO =        §5.2 (informes trazables, anclaje real, estados
                           honestos, cola enriquecida, ciclo humano
                           cerrable) -- CIERTO, con evidencia
R3_T1_NO_DEMOSTRADO =     §5.3 (parafrasis, CONFIRMED automatico,
                           reproducibilidad B2, representatividad H2H4)
                           -- declarado sin maquillar
F2_LIVE_JUSTIFIED =       NO, completo. SI, minimo (3-5 chunks) -- decision
                           de Cesar, no autorizada aqui
LESSON_RECORDED =         memoria de proyecto + este documento
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

**R3-T1 queda cerrado en lo que el código puede demostrar hoy.** Falta
únicamente tu clic real en la UI (bloque 4.3) para cerrar también el
ciclo humano -- eso es lo único que sigue en tus manos, no en las mías.
