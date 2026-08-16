# Reporte de sesión — 2026-08-12 (actualizado)
## R3-T1.4 (fix B3) → R3-T1.3 (addendum) → R3-T1.5 → R3-T1.6 (fix B4) → R3-T1.7 (superficie única, cierre)

Autoridad: Capa 9 = Cesar. Claude Code = Capa 8. Este reporte cubre TODO
lo ejecutado en esta sesión, en orden cronológico, con resultado de cada
paso, qué se commiteó y qué queda pendiente. **Estado final: R3-T1
cerrado, ciclo humano cerrado con tu firma real.**

──────────────────────────────────────────────────────────────────────────
## Índice de esta carpeta
──────────────────────────────────────────────────────────────────────────

```
REPORTE_SESION_2026-08-12/
├── 00_REPORTE_EJECUTIVO.md          ← este archivo
├── diffs/                            (12 commits, uno por archivo .patch)
│   ├── e823015_fix_b3.patch
│   ├── 42cdcd6_addendum_r3t13.patch
│   ├── 822b32e_bloque0_gate0.patch
│   ├── 98147df_f2dry_bloque1_y_hallazgo_headline.patch
│   ├── e026cdb_gobernanza_f1_pilot_execution.patch
│   ├── f629959_fix_b4.patch
│   ├── a2cabb8_superficie_unica_candidato.patch
│   ├── 06ddab7_correccion_contaminacion_y_promocion.patch
│   ├── 5e52682_bloque4_ciclo_humano.patch
│   ├── a8fab81_bloque5_cierre_r3t1.patch
│   ├── 1238b4f_incidente_contenedor.patch
│   └── faa181d_cierre_ciclo_humano.patch
├── documentos/                       (los 5 documentos de fase, completos)
│   ├── R3_T1_3_VIABILIDAD_F2.md
│   ├── R3_T1_4_FIX_AGREGACION_B3.md
│   ├── R3_T1_5_F2_DRY.md
│   ├── R3_T1_6_FIX_B4_Y_CIERRE.md
│   └── R3_T1_7_SUPERFICIE_UNICA_CANDIDATO.md   ← el más completo (bloques 1-5)
├── f2_dry_run_artefactos/
│   ├── replay_f2_dry.py                  (script final, Rutas A+B unificadas)
│   ├── informe_tier1_DRY_RUN.md          (informe final: 11.10(e) CONFIRMED)
│   ├── verified_conclusions_DRY_RUN.json
│   ├── governed_exceptions_DRY_RUN.json
│   ├── review_queue_entries_DRY_RUN.json (cola aislada del dry-run)
│   └── entrada_firmada_por_cesar.json    ← LA firma real, cola de producción
└── codigo_final/
    ├── candidate_validity.py             (la superficie única)
    └── test_candidate_validity_no_bypass.py
```

──────────────────────────────────────────────────────────────────────────
## 1. Punto de partida de la sesión
──────────────────────────────────────────────────────────────────────────

La sesión retomó el trabajo de `R3_T1_4_FIX_AGREGACION_B3.md`: un fix ya
diseñado y validado por replay (cero llamadas LLM) para el defecto B3
(falsa contradicción por agregación multi-chunk en
`verify_sufficiency_aggregated()`), pendiente de tu revisión de diff y
aprobación para commit.

──────────────────────────────────────────────────────────────────────────
## 2. Commit 1 — Fix B3 (`e823015`)
──────────────────────────────────────────────────────────────────────────

**Qué se hizo**: se mostró el diff completo de los 3 archivos afectados
(`factory/regulatory/semantic_evidence_verification.py`,
`factory/engines/gmpai_integrity/chunked_engine.py`,
`factory/tests/test_semantic_evidence_verification.py`), recibiste
aprobación explícita ("lo apruebo"), y se commiteó junto con el reporte
`docs_plan/R3_T1_4_FIX_AGREGACION_B3.md`.

**El defecto B3**: `verify_sufficiency_aggregated()` contaba `NOT_MET`
boilerplate de chunks "fuera de tema" (`estado=evidencia_insuficiente/
no_aplica`) como voto genuino, colisionando con un `MET` real anclado en
otro chunk y forzando `NOT_ASSESSABLE` por una contradicción fabricada.

**El fix**: usar el campo `estado` (ya emitido por el modelo, solo
faltaba propagarse hasta la agregación) para reclasificar esos `NOT_MET`
de chunks off-topic a `NOT_ASSESSABLE` -- nunca a `MET`. La contradicción
genuina entre chunks relevantes queda intacta y sigue bloqueando.

**Validación**: replay sobre checkpoint histórico `chunked-943a62bcbb85`
(29/29 chunks, cero llamadas LLM nuevas) + 5 tests nuevos + suite
existente (103 passed en ese momento, dentro del contenedor).

**Diff completo**: `diffs/e823015_fix_b3.patch`

──────────────────────────────────────────────────────────────────────────
## 3. Commit 2 — Addendum a R3-T1.3 (`42cdcd6`)
──────────────────────────────────────────────────────────────────────────

Registraste dos decisiones sobre `docs_plan/R3_T1_3_VIABILIDAD_F2.md`:

- **RAMA B — ACEPTADA**: F2.3.a' (`SUPPORTING_EVIDENCE_UNDER_REVIEW` con
  ancla + cola de revisión humana) queda como criterio de F2, en vez del
  original F2.3.a (que exigía CONFIRMED, inalcanzable estructuralmente).
- **B3 — DIFERIDA**: la decisión de habilitar/usar formalmente el fix en
  una corrida de F2 queda para después (el fix en sí ya estaba commiteado
  en ese momento).

**Hallazgo colateral encontrado y documentado**: el ID `ARTIFACT_VERSION-2026-018`,
que el plan original asumía usar para la promoción de B1 (elegibilidad de
conclusión positiva), **ya está tomado** por una propuesta de una sesión
anterior (R3-T1.2/F0.6) que cubre algo distinto (sincronización de
`source_verification_status`) y nunca fue confirmada ni aplicada. Promover
B1 necesitará un ID nuevo (`ARTIFACT_VERSION-2026-019`).

**Diff completo**: `diffs/42cdcd6_addendum_r3t13.patch`

──────────────────────────────────────────────────────────────────────────
## 4. Commit 3 — Bloque 0 de R3-T1.5 (`822b32e`)
──────────────────────────────────────────────────────────────────────────

Se creó `docs_plan/R3_T1_5_F2_DRY.md` con las instrucciones completas de
la nueva fase (R3-T1.5), y se ejecutaron sus dos primeros puntos:

### 0.1 — Corrección de divergencia entre reportes
`R3_T1_4_FIX_AGREGACION_B3.md` seguía diciendo "Sin commit" pese a que el
fix ya estaba commiteado con tu aprobación. Se corrigió el encabezado y el
cierre del documento para que coincida con `R3_T1_3_VIABILIDAD_F2.md`
§5(ii), que sí lo reportaba bien. **Conclusión: no fue una desviación de
proceso** -- el commit sí tuvo tu aprobación explícita antes de ejecutarse,
solo el texto del reporte había quedado desactualizado.

### 0.2 — Gate 0 real, corrido desde el host
La suite completa no termina dentro del contenedor `factory-api` (falta
el CLI `docker`, tests que exigen Mission Control vivo). Se corrió desde
el host (`.venv`, con Docker CLI y red disponibles):

```
2434 tests → 2418 passed, 8 failed, 5 skipped, 1 xfailed, 2 errors
(1010.90s / 16:51 min)
```

Cada uno de los 10 fallos se investigó con reintentos aislados antes de
caracterizarlo:
- **Cero solapamiento confirmado en la corrida real** (no solo por grep):
  los dos archivos que el fix B3 modifica quedaron 100% en verde.
- **4 fallos**: guardianes que comparan `decisions_v2.jsonl`/
  `review_queue.jsonl` contra HEAD -- causa real: esos archivos YA estaban
  modificados en el árbol de trabajo desde ANTES de esta sesión (trabajo
  de otra sesión, no relacionado).
- **1 fallo**: `TimeoutError` real conectando a un endpoint vivo --
  ambiental, el servicio no está alcanzable así desde el host en ese momento.
- **5 fallos/errores**: Playwright esperando la UI de Mission Control
  vivo (`#apikey`, `wait_for_function`) -- reejecutados en aislamiento,
  siguen fallando por timeout. Coincide EXACTAMENTE con la caracterización
  ya documentada en Gate 0 de F0.

**Conclusión**: no es "Gate 0 verde" en sentido estricto, pero SÍ confirma
cero regresión del fix B3 -- los 10 fallos se explican íntegramente por
dos categorías ya conocidas, ninguna nueva.

**Diff completo**: `diffs/822b32e_bloque0_gate0.patch`

──────────────────────────────────────────────────────────────────────────
## 5. Commit 4 — Bloque 1 de R3-T1.5: F2-DRY (`98147df`)
──────────────────────────────────────────────────────────────────────────

### 5.1 — Intento 1 (fallido, informativo): `evaluate_chunked()` rehúsa reabrir un checkpoint completado

Se intentó pasar el checkpoint histórico `chunked-943a62bcbb85` por
`ce.evaluate_chunked()` directamente, con un "guard provider" que revienta
si intenta una llamada real al modelo (cero llamadas salieron, confirmado).
El motor NO lo reconoció como reanudable -- generó un run_id nuevo e
intentó ejecutar los 29 chunks desde cero (el guard los bloqueó, resultado
vacío/inútil).

**Causa raíz**: `CheckpointStore.find_resumable()` tiene una barrera
deliberada -- *"Un run completado SIN fallos tecnicos nunca se reabre...
jamas re-analizar contenido ya evaluado"*. Es una guardia de gobernanza
intencional, no un bug. **Se te preguntó si bypasearla** (aunque fuera
solo en un script aislado, sin tocar el motor real) y decidiste que NO --
"replay acotado" en su lugar.

### 5.2 — Intento 2 (aprobado por ti): replay acotado sobre funciones reales

En vez de forzar `evaluate_chunked()`, se reconstruyó el tramo de
consolidación A/B/C/D llamando DIRECTAMENTE a las mismas funciones de
producción que ese tramo ya usa. Ningún validador se reimplementó -- solo
se reordenó la orquestación. Script (versión inicial):
`f2_dry_run_artefactos/replay_f2_dry.py` (actualizado varias veces más
adelante, ver §7-8).

**Resultado de la función D, validado con datos reales, cero llamadas:**

| Requisito | D agregado (con fix B3) | contradicted |
|---|---|---|
| `21_CFR_11.10(e)` | **PARTIALLY_MET, 2/9** | vacío -- falsa contradicción CORREGIDA |
| `21_CFR_11.10(d)` | NOT_ASSESSABLE, contradicción real | `Mecanismo de control de acceso...` -- GENUINA, preservada |

### 5.3 — Hallazgo B4: un gate independiente impide que D llegue al producto final

`Finding.d_sufficiency` solo se puebla si existe un candidato "headline"
anclado a nivel de la cita RESUMEN del requisito, no de las citas por
criterio. Causa raíz confirmada en el `raw_response` real: el modelo
dejaba `evidencia_exacta` (headline) VACÍA mientras `criterion_assessments`
(mismo chunk) sí traía citas reales y ancladas. **Tu decisión en ese
momento**: documentar y detener -- sin diseñar fix todavía.

### 5.4 — Criterios de aceptación F2-DRY en ese punto: (b) y (c) PARCIAL

**Diff completo**: `diffs/98147df_f2dry_bloque1_y_hallazgo_headline.patch`

──────────────────────────────────────────────────────────────────────────
## 6. Commit 5 — Gobernanza F1 (`e026cdb`)
──────────────────────────────────────────────────────────────────────────

Antes de seguir, se investigó por qué 4 guardianes de Gate 0 seguían en
rojo: `decisions_v2.jsonl`/`review_queue.jsonl` tenían cambios sin
commitear de una sesión anterior. Verificado como **gobernanza legítima**
(par `PILOT_EXECUTION-2026-015/016`, autorización + confirmación real de
Cesar, y el hallazgo real que esa corrida F1 despachó a la cola) -- no
residuo de prueba. Commiteado tal cual, append-only.

**Diff completo**: `diffs/e026cdb_gobernanza_f1_pilot_execution.patch`

──────────────────────────────────────────────────────────────────────────
## 7. Commit 6 — R3-T1.6: fix B4 (`f629959`)
──────────────────────────────────────────────────────────────────────────

Nueva fase (`R3_T1_6_FIX_B4_Y_CIERRE.md`): caracterizar y corregir el
gate headline encontrado en el bloque anterior.

**Regla implementada**: si el headline viene vacío pero al menos un
criterio `MET` trae cita real y anclada (`verify_sufficiency()` Nivel B
ya lo verifica), el candidato se considera anclado -- DERIVADO de esas
citas, nunca inventado. Guardia adicional encontrada al diseñar: había
que aplicar el mismo chequeo anti-lista-de-referencias
(`detect_reference_list_context`) que protege al headline normal, o el
rescate podía colar una cita tipo ANNEX11_4.

**7 tests guardianes** (6 del plan + 1 propio): caso real, ausencia
preservada, cita no anclada nunca rescata, cita de lista de referencias
nunca rescata, contradicción genuina sigue bloqueando, ANNEX11_4
end-to-end sigue rechazado, retrocompatibilidad. 125 tests en verde.

**Hallazgo al re-correr F2-DRY con B4**: el fix corregía el `Finding`
(Ruta A) pero el bucket final del informe NO cambiaba -- `chunks_observed:
0` seguía en 0. Causa: `verified_records_by_req` (Ruta B, la que
realmente decide el bucket) es una estructura de datos SEPARADA que B4
nunca tocó -- este es el hallazgo que abrió R3-T1.7.

**Diff completo**: `diffs/f629959_fix_b4.patch`

──────────────────────────────────────────────────────────────────────────
## 8. Commit 7 — R3-T1.7: superficie única de validez de candidato (`a2cabb8`)
──────────────────────────────────────────────────────────────────────────

**Cambio de método** (instrucción explícita tuya): B3, B4 y el hallazgo
de la Ruta B no eran tres defectos -- eran el MISMO defecto en sitios
distintos. En vez de parchear un cuarto sitio, se auditó exhaustivamente
y se centralizó.

### 8.1 — Auditoría (bloque 1): 4 rutas reales, no 2

```
Ruta A (Finding/reporte)          -- B4 la corrigió
Ruta B (verified_records/bucket)  -- decide el bucket REAL, B4 nunca la tocó
Ruta C (catálogo, distinta preocupación) -- fuera de la familia, sin cambios
Ruta D (remediación, LATENTE, sin llamador de producción hoy) -- riesgo
  documentado: se rompería igual si se activa sin la superficie única
+ código muerto (verified_pipeline.py, sin llamadores)
+ divergencia interna en la Ruta B (dos algoritmos de anclaje distintos
  apilados: _is_anchored vs match_citation)
```

### 8.2 — Centralización (bloque 2)

Módulo nuevo `factory/regulatory/candidate_validity.py` --
`resolve_candidate_evidence()`, la ÚNICA decisión de si un candidato
ancla. Ambas rutas vivas (A y B) la llaman una vez por (chunk,
requisito). `_is_anchored()`/`_apply_headline_rescue_b4()` (código de
B4) eliminados -- absorbidos aquí.

**Dos hallazgos encontrados al implementar** (documentados con detalle
en `R3_T1_7_SUPERFICIE_UNICA_CANDIDATO.md`):
1. Un intento inicial de fusionar `_is_topically_relevant` (propio de la
   Ruta A) rompió 3 tests reales -- R1.7 ya había retirado ese filtro de
   la Ruta B a propósito. Corregido: se aplica solo a una variable local.
2. `evidence_verifier.verify_llm_output()` (dentro de la Ruta B) hace su
   PROPIA re-verificación de la cita -- el texto derivado (con prefijo +
   citas unidas) nunca existe literalmente en el chunk. Corregido con
   `CandidateEvidence.verifiable_quote` (cita única, re-verificable,
   separada del texto de presentación).

**Guardián de no-bypass**: `test_candidate_validity_no_bypass.py` (4
tests) -- falla si algún módulo reimplementa la lógica en vez de llamar
a la superficie única.

### 8.3 — Validación en la SALIDA FINAL (bloque 3) — el criterio único que cuenta

Tabla ANTES/DESPUÉS a nivel de **bucket del informe**:

| Requisito | ANTES (solo Ruta A corregida) | DESPUÉS (superficie única) |
|---|---|---|
| `21_CFR_11.10(e)` | `NEEDS_HUMAN_REVIEW` / `PROVISIONAL_GAP` | **`CONFIRMED`** / `PROVISIONALLY_PARTIALLY_DOCUMENTED` |
| `21_CFR_11.10(d)` | `NEEDS_HUMAN_REVIEW` / `PROVISIONAL_GAP` | `NEEDS_HUMAN_REVIEW` / `EVALUATION_INCOMPLETE` (contradicción genuina) |

`21_CFR_11.10(e)` YA NO está en `PROVISIONAL_GAP` -- su evidencia real
(2/9 criterios anclados) llega hasta el bucket final del informe, no
solo hasta una capa intermedia.

**Gap nuevo encontrado y corregido en la misma corrida** (autorizado por
Cesar): `21_CFR_11.10(d)` ahora es `EVALUATION_INCOMPLETE` (correcto)
pero ninguna de las 3 condiciones de despacho a la cola de revisión lo
cubría -- quedaba `NEEDS_HUMAN_REVIEW` en el informe SIN entrada en la
cola. Nueva función `_dispatch_contradiction_blocked_review()` + su
propio guardián end-to-end. **Los 6 criterios de F2-DRY (a-f) pasan tras
esta corrección.**

182 tests en verde. Suite completa del host: 2427 passed (mismos 6
fallos ambientales ya caracterizados, ninguno nuevo).

**Diff completo**: `diffs/a2cabb8_superficie_unica_candidato.patch`

──────────────────────────────────────────────────────────────────────────
## 9. Commits 8-9 — Bloque 4: ciclo humano (`06ddab7`, `5e52682`)
──────────────────────────────────────────────────────────────────────────

**Vía elegida**: promover UNA entrada real de la cola dry-run a la cola
de producción, marcada `DRY_RUN_VALIDATION` -- en vez de tocar
infraestructura (variable de entorno + reinicio de contenedor solo para
apuntar la UI a la cola aislada).

**Contaminación encontrada y corregida antes de promover**: un script de
depuración manual (corrido fuera de pytest, sin el fixture autouse
`isolated_review_queue`) había escrito 3 entradas sintéticas
(`document_id='doc.pdf'`) en la cola REAL por accidente. Nunca se
borraron (append-only): se marcaron `superseded` con `supersede_finding()`
(mismo mecanismo ya usado en este archivo), motivo explícito, para que
el evento de auditoría ya escrito quedara justificado.

**Entrada promovida** (confirmada visible vía `GET /api/v1/layer9/
review-queue` en vivo):
```
rc_id: finding-chunked-943a62bcbb85-r3t17-dryrun-validation-21_CFR_11.10(d)
conclusion: EVALUATION_INCOMPLETE
review_flags: [ABCD_D_NOT_ASSESSABLE, SOURCE_PENDING_REVERIFICATION,
               CONTRADICTION_BLOCKED_POSITIVE_CONCLUSION, DRY_RUN_VALIDATION]
```

**Diffs**: `diffs/06ddab7_correccion_contaminacion_y_promocion.patch`,
`diffs/5e52682_bloque4_ciclo_humano.patch`

──────────────────────────────────────────────────────────────────────────
## 10. Commit 10 — Bloque 5: cierre de R3-T1 (`a8fab81`)
──────────────────────────────────────────────────────────────────────────

**Cadena completa de defectos**: kerning → contrato de prompt → B3
(agregación D) → B4 (anclaje Ruta A) → B5/hallazgo (anclaje Ruta B) →
gap de despacho → centralizado en `candidate_validity.py`.

**Qué demuestra R3-T1**: informes trazables, anclaje real cuando la
evidencia existe (`11.10(e)`), estados honestos cuando no
(`11.10(d)` bloqueado por contradicción genuina, nunca resuelta en
silencio), cola enriquecida con el motivo exacto, ciclo humano cerrable.
Todo validado con **cero llamadas LLM** -- cuarta vez en este arco que
el replay sobre datos ya pagados resuelve lo que parecía necesitar
presupuesto nuevo.

**Qué NO demuestra**: el límite de paráfrasis del modelo (R2, recall
2/7, sin cambios); CONFIRMED automático (bloqueado por B1 + cobertura
real del documento); reproducibilidad estricta entre corridas
(variabilidad B2); que un checkpoint BASELINE sea representativo de una
corrida H2H4 real.

**F2-LIVE completo (29 llamadas): NO se justifica** -- el replay ya
midió lo que esas llamadas medirían. Un alcance mínimo (3-5 chunks)
queda como decisión tuya, no autorizado en esta corrida.

**Memoria de proyecto guardada**: `project_r3_t1_superficie_unica.md` --
el patrón "cuando un defecto reaparece en un segundo sitio, no se
parchea el segundo sitio, se audita y centraliza" (mismo patrón que
`path_policy.py`/`decision_scope_resolver.py`), y "el criterio de
aceptación se mide en la salida final, nunca en una capa intermedia".

**Diff completo**: `diffs/a8fab81_bloque5_cierre_r3t1.patch`

──────────────────────────────────────────────────────────────────────────
## 11. Commits 11-12 — Incidente de contenedor + cierre real del ciclo humano (`1238b4f`, `faa181d`)
──────────────────────────────────────────────────────────────────────────

Al intentar firmar la entrada promovida en la UI, Cesar reportó
**"Hallazgo no encontrado"**. Diagnóstico en vivo, sin asumir nada:

- Archivo idéntico dentro y fuera del contenedor (bind mount) -- descartado.
- `get_entry(rc_id)` en un proceso Python fresco dentro del contenedor SÍ
  encontraba la entrada -- descartado problema de datos/lógica.
- El 404 real, probado contra el servidor vivo, era el 404 GENÉRICO de
  FastAPI ("ninguna ruta coincide"), no nuestro mensaje custom.
- Confirmado con el propio `/openapi.json` del servidor VIVO: la ruta
  `/api/v1/layer9/review/findings/{rc_id}/decide` no estaba registrada.

**Causa raíz**: el contenedor `factory-api` arrancó el 2026-08-11 12:38 --
ese endpoint se commiteó DESPUÉS, el 2026-08-12 02:16 (`713f8a5`, sesión
anterior). El contenedor nunca se reinició desde entonces.

**Corrección** (autorizada explícitamente por Cesar antes de tocar
infraestructura): `docker compose -f docker-compose.factory.yml restart
factory-api`. Como `factory/` está bind-mounted, no hizo falta rebuild de
imagen. Verificado post-restart: `/health` OK, la ruta aparece en
`/openapi.json`, la entrada de cola intacta.

**Resultado**: Cesar reintentó la firma en la UI real -- **funcionó**.
La entrada quedó:
```
status: confirmed
reviewer: cesar
reviewed_at: 2026-08-12T18:57:45Z
human_confirmed_evidence.quote: "mejora"
```
Ver `f2_dry_run_artefactos/entrada_firmada_por_cesar.json` (copia exacta
del registro real, tal como quedó en `factory/layer9/review_queue.jsonl`).

**Diffs**: `diffs/1238b4f_incidente_contenedor.patch`,
`diffs/faa181d_cierre_ciclo_humano.patch`

──────────────────────────────────────────────────────────────────────────
## 12. Qué queda pendiente (con dueño)
──────────────────────────────────────────────────────────────────────────

```
B1 (positive_conclusion_eligibility=PROVISIONAL_ONLY):
  decision de Cesar, ID disponible ARTIFACT_VERSION-2026-019
PROMPT FANTASMA (part11_prompts.yaml en
  factory/workspaces/gmpai_document_validation/prompts/, v1.0.0, no
  cargado por produccion): decision de Cesar pendiente, sin cambios
TESTS AMBIENTALES DE GATE 0 (Playwright/endpoint vivo, mismos 6
  fallos/2 errores ya caracterizados en cada bloque, ninguno nuevo):
  sin dueño asignado, no bloquean producción
F2-LIVE MINIMO (3-5 chunks, no 29): decision de Cesar sobre si vale la
  pena medir variabilidad de muestreo (B2) sobre los criterios de
  21_CFR_11.10(e) aun sin evidencia
```

──────────────────────────────────────────────────────────────────────────
## 13. Estado final de gobernanza
──────────────────────────────────────────────────────────────────────────

```
R3-T1: CERRADO (código + ciclo humano, con firma real de Cesar)
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

Cero llamadas LLM en toda la sesión (todo el trabajo de validación fue
replay sobre datos ya pagados o código puro). Una acción real sobre
infraestructura compartida (restart de `factory-api`), autorizada
explícitamente antes de ejecutarse, verificada segura antes y después
(salud del servicio, integridad de la cola). Una entrada real y
permanente en la cola de gobernanza de producción, con la firma humana
que CLAUDE.md exige para cualquier conclusión -- el sistema nunca
declaró cumplimiento ni aprobó nada por sí mismo.
