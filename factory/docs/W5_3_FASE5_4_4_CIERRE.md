# W5.3 — Fase 5.4.4: diagnóstico real de los 21 rechazos de schema + canario ETAPA 2 + ETAPA 3 (cierre final)

Fecha: 2026-07-18 (ETAPA 1/2) / 2026-07-20 (cierre de ETAPA 3, este addendum).
Gobernanza y diagnóstico (ETAPA 1/2) ya commiteados en `f85bb37`. Este
documento se actualiza in-place para registrar el cierre de **ETAPA 3**
(la regresión completa de 57 llamadas que quedó pendiente de autorización
al final de la sección "Pendiente real" original) — no es una fase nueva,
es el cierre pendiente de esta misma Fase 5.4.4.

## Punto de partida

Al revisar el diff pendiente de Fase 5.4 aparecieron cambios no documentados
en el cierre original ("ETAPA 1" en los comentarios del código):
`finding_llm_v1.json` (`evidence_page` de `type:[integer,null]` a
`anyOf:[{integer},{null}]`) y persistencia de `raw_response`/`errors` en
`run_validation_evidence.py`. La hipótesis registrada en el propio schema
era que `type` como array es incompatible con el conversor JSON-Schema a
gramática de Ollama/llama.cpp — **hipótesis pendiente de confirmar**, sin
llamada canario todavía.

Se pidió ejecutar el protocolo de 3 etapas del usuario antes de repetir las
57 llamadas del piloto de Fase 5.4.3.

## ETAPA 1 — diagnóstico sin llamadas a Ollama

**Paso 1-2 (analizar y clasificar los 21 rechazos reales por causa
exacta): imposible con los datos existentes.** Los `raw_response` reales de
esos 21 casos nunca se persistieron (bug corregido en Fase 5.4, pero
retroactivo — los datos ya se habían perdido). Sin el JSON crudo no hay
causa exacta que clasificar para esos 21 casos puntuales.

**Reconstrucción forense alternativa (sin llamar a Ollama):** el archivo
real (`w5v3-validation-40523ef722ef.json`) no guarda `requirement_id` por
registro, solo `prompt_sha256`/`chunk_sha256`. Se recalcularon los 57
`prompt_sha256` posibles (19 requisitos × 3 chunks) y se compararon contra
los reales. La primera pasada (venv del host, `pypdf==4.3.1`) no coincidió
con ningún hash — la corrida original se había ejecutado dentro del
contenedor `factory-api` (`pypdf==6.14.2`), cuya extracción de texto
difiere de la del host. Repetido dentro del contenedor: **57/57 registros
identificados con exactitud** (`requirement_id` + índice de chunk para
cada uno, incluidos los 21 rechazados).

**Hallazgo estructural real** (no hipotético):
- Chunk índice 2 (de 3): 0 fallos de schema en los 19 requisitos.
- Los 5 requisitos 21 CFR Part 11: 0 fallos de schema (100% `verified`).
- Los 21 rechazos se concentran exclusivamente en los 9 requisitos ALCOA+
  (chunks 0 y 1) y 5 requisitos Annex 11 (solo chunk 0).
- Esta concentración por categoría de requisito/chunk es **inconsistente**
  con una causa puramente estructural del schema (que afectaría por igual
  a todos los requisitos) — ya en esta etapa había señal de que la
  hipótesis `evidence_page`/`anyOf` no explicaba el patrón real, sin poder
  todavía confirmarlo sin una llamada real.

**Paso 4-6 (corrección sin relajar el contrato + tests + regresión
sintética):** ejecutados en el commit pendiente de Fase 5.4 — `anyOf` para
`evidence_page` (forma, no contrato), 8 tests nuevos en
`test_schema_enforcement.py` (1 de regresión del contrato tras el cambio de
forma + 6 sintéticos por causa, ya que los reales no existen + 1 de
no-regresión de un payload válido). `additionalProperties:false` intacto,
0 campos requeridos eliminados, 0 estados nuevos aceptados, 0 reparaciones
silenciosas.

**Bug adicional encontrado** (no corregido en esta fase, documentado como
pendiente): `rejection_reason` queda hardcodeado a
`"schema_validation_failed"` incluso cuando la causa real es "JSON
inválido" (no parseable) — las dos causas se distinguen en `errors[0]`
pero no en el campo `rejection_reason`. No bloquea nada porque `errors` sí
tiene la causa real, pero es una etiqueta engañosa para lectura rápida.

**Archivo `w5v3-validation-7dd36dad0c77.json` encontrado antes de esta
fase:** usaba `21_CFR_11.10(d)` — un requisito que **nunca falló por
schema** en la corrida original (0/57 fallos en Part 11). No sirve como
prueba canario válida (no reproduce el fallo real) — descartado como
evidencia de esta fase, no se usó para ninguna conclusión.

**Exclusión formal del directorio activo** (2026-07-18, tras revisión de
diff pendiente de commit):
- `document_sha256` (dato interno, run real sobre FS_v1.2): `56095a7541fbb62e30d00e77308fde4c2ac0f4ec945adbf19a968b79debc82eb`
- `sha256` del archivo de evidencia en sí (`w5v3-validation-7dd36dad0c77.json`): `edbb03d9c16b52d71c7b95ab62f40f4b3c7e05c7f1cc5bc0618af6abe74430e1`
- Fecha de la corrida original: 2026-07-18T02:03:40 UTC (mtime del archivo: 2026-07-18 02:06:47 UTC)
- Motivo de exclusión: usa `requirement_id=21_CFR_11.10(d)`, que en la
  corrida real de Fase 5.4.3 tuvo 0/6 rechazos por schema (todos los
  registros Part 11 fueron `verified`) — no reproduce ningún fallo
  histórico real, por lo tanto no cumple el requisito del protocolo ETAPA 2
  ("un requirement_id que anteriormente fallo por schema"). No se usó para
  ninguna conclusión de esta fase ni de la anterior.
- Acción: retirado del directorio activo `factory/regulatory/validation_evidence/`
  (no commiteado nunca — nunca estuvo tracked en git). Este registro (hash +
  fecha + motivo) es la evidencia de su existencia y exclusión.

## ETAPA 2 — canario real (dos llamadas: una falla, una pasa)

Par elegido con la reconstrucción forense: `requirement_id=ALCOA_ACCURATE`,
chunk índice 0 (`chunk_sha256=6f602ae0...`, uno de los que sí falló en la
corrida real), mismo documento FS_v1.2, `run_context=validation`, schema ya
con el fix `anyOf` aplicado.

**Primera llamada (`run_id w5v3-validation-18da5e36a51a`, 2026-07-18T02:48
UTC): FALLÓ.** Causa real (ahora sí capturada vía `raw_response`/`errors`):

```
"confidence": 100 is greater than the maximum of 1
```

El modelo devolvió `confidence` en escala 0-100; el schema exige `[0,1]`.
JSON bien formado, `evidence_page=3` (entero, válido bajo `anyOf` sin
problema), `additionalProperties` respetado, todos los campos requeridos
presentes. **El campo que motivó el fix `anyOf` (`evidence_page`) no fue la
causa de este fallo real** — la hipótesis original queda sin confirmar por
esta vía.

**Corrección aplicada** (`_default_prompt()` en `run_validation_evidence.py`,
único cambio, sin tocar el schema): se añadió una instrucción explícita
sobre la escala de `confidence` (decimal 0.0–1.0, con ejemplos, prohibiendo
valores tipo "100"/"85"). No se relajó `additionalProperties`, no se
eliminó ningún campo obligatorio, no se aceptó ningún estado fuera del
catálogo, no hay normalización/clamping silencioso del valor devuelto por
el modelo.

**Segunda llamada (mismo requisito, mismo chunk, mismo documento;
`run_id w5v3-validation-4455c94588e0`, 2026-07-18T02:51 UTC): PASS.**

| Criterio del protocolo | Resultado |
|---|---|
| JSON válido al primer intento | PASS — sin reintento |
| Schema válido | PASS — `confidence: 0.95` |
| 0 campos adicionales | PASS — 7 campos exactos del schema |
| 0 estados fuera del catálogo | PASS — `chunk_observation: "observed"` |
| Manifest completo | PASS — `manifest_incomplete: false`, digest presente |
| Evidencia persistida | PASS — `VALIDATION_EVIDENCE_COMPLETE`, `golden_dataset_eligible: true` |
| Verificador ejecutado | PASS — `status: review_required` por `RELEVANCE_REVIEW_REQUIRED` (V5 activo, no bypaseado) |
| Sin reparación silenciosa | PASS — el modelo generó `0.95` directamente |
| Producción sigue bloqueada | PASS — `run_context="validation"` en ambas llamadas |

Por instrucción explícita del usuario ("no ejecutes las 57 llamadas" si el
canario falla en el primer intento, "repite únicamente la prueba canario"),
se detuvo la ejecución tras el PASS de la repetición. **ETAPA 3 (regresión
completa de 57 llamadas) NO se ejecutó** — queda pendiente de autorización
explícita.

## ETAPA 3 — regresión completa (57 llamadas, ejecutada 2026-07-18, cerrada 2026-07-20)

Autorizada explícitamente tras el PASS del canario y la gobernanza
commiteada (`f85bb37`). **No se repiten llamadas para este cierre** — se
documenta la corrida real ya ejecutada.

- `run_id`: `w5v3-validation-49de4fd0d1d1`
- `run_by`: "Cesar (autorizado via instruccion explicita ETAPA 3, sesion
  2026-07-18, tras canario PASS y gobernanza commiteada f85bb37)"
- Mismo documento real (`document_sha256=56095a75...b82eb`, FS_v1.2),
  mismo catálogo completo (19/19 requisitos × 3 chunks = 57), mismo
  modelo/digest (`qwen2.5:7b-instruct-q4_K_M`,
  `845dbda0...31a0b697e`), mismo `schema_sha256` que el schema
  actualmente commiteado (`aef8f84a...186ae1e`) — sin desviación de
  contrato entre lo ejecutado y lo versionado.
- Ventana real: `2026-07-18T04:13:45Z` → `2026-07-18T06:27:50Z` (~2h14m).
  Manifiesto sanitizado escrito a las `06:30:08Z`.

| Métrica | Fase 5.4.3 (pre-fix) | ETAPA 3 (post-fix) |
|---|---|---|
| `verified` | 31 | **40** |
| `review_required` (`RELEVANCE_REVIEW_REQUIRED`) | 5 | **16** |
| `rejected_by_verifier` | 21 (100% `schema_validation_failed`) | **1** (`citation_not_found` — causa distinta) |
| `errors_count` agregado | — | 0/57 |
| `manifest_incomplete` | 0/57 | 0/57 |
| `golden_dataset_eligible` | true | true |

**Lectura de resultado**: el fix de prompt de escala de `confidence`
(ETAPA 2) elimina el 100% de los rechazos por `schema_validation_failed`
en la regresión completa (21→0), confirmando a escala de las 57 llamadas
lo que el canario n=1 solo insinuaba. El único rechazo real de ETAPA 3
(`citation_not_found`) es una causa **no relacionada** con el patrón
original — no reabre la hipótesis de escala, es un caso nuevo y aislado
(n=1, sin patrón visible en el resto de la corrida).

El aumento de `review_required` (5→16) es el mecanismo de relevancia (V5,
Fase 2) disparándose más veces, no una regresión: al dejar de perderse
registros por rechazo de schema, más registros llegan hasta el verificador
de relevancia, que sigue activo y sin bypasear (protección del patrón
C1/C3 — cita anclada pero fuera de tema — confirmada funcionando sobre
datos reales, no solo sobre el Golden Dataset reconstruido).

**Conclusiones documento-nivel (19/19, `coverage=partial`, 3/29 chunks
reales por requisito) — comparación con Fase 5.4.3:**

| Conclusión | Fase 5.4.3 | ETAPA 3 |
|---|---|---|
| `DOCUMENTED_AND_SUPPORTED` | 5 | **18** |
| `DOCUMENTATION_GAP` | 11 | **1** (`ALCOA_CONTEMPORANEOUS`, 0/2 chunks observados) |
| `CROSS_REFERENCE_MISSING` | 2 | 0 |
| `PARTIALLY_DOCUMENTED` | 1 | 0 |

El salto de 5→18 documentos "documentados y soportados" es consecuencia
directa de que la evidencia ya no se pierde por rechazo de schema — **no
es evidencia nueva del documento**, es evidencia que antes existía pero
se descartaba antes de llegar a una conclusión. 15 de los 18
`DOCUMENTED_AND_SUPPORTED` llevan la bandera `SUPPORTING_EVIDENCE_UNDER_
REVIEW` (heredada de sus registros `review_required`) — la conclusión es
técnica, no es un veredicto de cumplimiento sin revisión humana pendiente.

**Limitación que sigue igual que en Fase 5.4.3**: un solo documento, 3 de
29 chunks reales por requisito (`coverage=partial`). ETAPA 3 confirma el
fix de prompt a escala de 57 llamadas sobre este documento — no confirma
que la tasa de rechazo/relevancia se generalice a otros documentos o al
100% de los chunks.

### Gate 0 de este cierre (solo verificación, sin tocar `validation_evidence/`)

- Suite completa: **712 passed, 1 skipped, 0 failed** (venv del proyecto,
  `.venv/bin/python3 -m pytest factory/tests -q`).
- `factory_selfcheck.sh`: **PASS=5 FAIL=0** (pytest embebido PASS=712,
  cadena de auditoría íntegra — 2285 entradas, 1 fork concurrente aceptado
  sin `hash_errors`, `factory_status.sh` sin FAILs, escáner de
  `validation_evidence` en git PASS — solo allowlist tracked).
- Ningún archivo de `validation_evidence/` fue escrito, movido ni
  commiteado como parte de este cierre; el manifiesto sanitizado de
  ETAPA 3 (`w5v3-validation-49de4fd0d1d1.manifest.json`) ya existía en
  disco de la corrida real y queda listado en el diff para commit.

### Actualización de estado de producción (reemplaza el bloque de la sección "Estado de producción" más abajo)

```
OLLAMA_SCHEMA_COMPATIBILITY = PASS_FOR_CONTROLLED_PILOT  (antes: CANARY_PASS_N1_PENDING_SCALE_VALIDATION)
REGULATORY_EVALUATION_COMPLETE = false   (sin cambio — un solo documento, coverage partial)
DOCUMENT_COVERAGE = PARTIAL              (sin cambio — 3/29 chunks reales por requisito, un solo documento)
PRODUCTION_ENABLEMENT = BLOCKED          (sin cambio — toda la corrida fue run_context="validation")
FASE_5_4_4_STATUS = CLOSED_WITH_FOLLOW_UP
```

`OLLAMA_SCHEMA_COMPATIBILITY` pasa a `PASS_FOR_CONTROLLED_PILOT` (no a
`PASS` sin calificar) porque la regresión completa (n=57, no n=1) confirma
0 rechazos por `schema_validation_failed` **sobre un solo documento y
piloto controlado** — no es una validación pendiente de escala dentro de
ese piloto, pero tampoco es una confirmación general del comportamiento de
Ollama frente al schema en otros documentos. No se toca
`REGULATORY_EVALUATION_COMPLETE` ni `PRODUCTION_ENABLEMENT`: ninguna
llamada de ETAPA 3 usó `run_context` distinto de `validation`, y la
cobertura sigue siendo parcial sobre un solo documento
(`DOCUMENT_COVERAGE = PARTIAL`). `FASE_5_4_4_STATUS = CLOSED_WITH_FOLLOW_UP`
porque la fase queda cerrada (ETAPA 1/2/3 completas) pero con pendientes
explícitos abiertos hacia W5.5 (ver "Pendiente real / recomendación").

## Conclusión de causa raíz

La causa raíz real y confirmada (n=1, ver limitación abajo) de al menos
parte de los 21 rechazos de Fase 5.4.3 es una **ambigüedad de escala en el
campo `confidence`** (el modelo interpreta "confidence" como porcentaje
0-100 en vez de fracción 0-1 según el contexto/requisito), no el problema
estructural de `type` array vs `anyOf` que motivó el fix original de
`evidence_page`. El fix `anyOf` queda aplicado (es inocuo, no relaja el
contrato) pero **no está confirmado como causa de ningún fallo real** — se
mantiene por prudencia estructural documentada, no por evidencia.

**Limitación honesta:** el canario confirma la corrección para **un solo
par** (`ALCOA_ACCURATE`, chunk 0, n=1). Los otros 20 rechazos históricos
(incluida la mitad de los mismos requisitos ALCOA+ contra chunk 1, y los 5
Annex 11) no fueron re-verificados — es plausible que compartan la misma
causa (ambigüedad de escala), pero no está confirmado por llamada real.
Eso es exactamente lo que decidiría la ETAPA 3, todavía no autorizada.

## Corrección de `rejection_reason` (post-revisión de diff, antes del commit)

Al revisar el diff pendiente se detectó (y se pidió corregir) que
`rejection_reason` quedaba **siempre** hardcodeado a
`"schema_validation_failed"` en dos lugares (`run_validation_evidence.py` y
`verified_pipeline.py`), incluso cuando `generate_controlled()` ya sabía que
la causa real era otra. Peor aún: un fallo de transporte HTTP real (Ollama
caído, timeout, conexión rechazada) **no se capturaba en absoluto** —
`_call()` dejaba propagar la excepción de `httpx`, lo que habría abortado
una corrida completa (57 llamadas) a mitad de camino, perdiendo el análisis
ya hecho de los requisitos anteriores pese al contrato de persistencia de
Fase 5.4.

**Corrección** (`ollama_client.generate_controlled()`): se separó la
llamada HTTP (`_call()`, ahora captura `httpx.HTTPError` en vez de dejarlo
propagar) de la clasificación (`_classify()`), que devuelve exactamente una
de 4 causas:
- `ollama_transport_failed` — fallo de conexión/HTTP con Ollama.
- `json_parse_failed` — respuesta recibida pero no es JSON válido.
- `schema_validation_failed` — JSON válido que no cumple `finding_llm_v1`.
- `manifest_incomplete` — **decisión explícita del usuario: NO se
  implementó como causa de rechazo.** El código ya tenía una doctrina
  documentada (P1, `ollama_client.py` línea ~88) de que un manifiesto
  incompleto (`model_digest` no disponible) no invalida el hallazgo.
  Convertirlo en causa de rechazo habría degradado registros `verified`
  existentes a rechazados — un cambio de política, no una corrección de
  bug. Se preguntó explícitamente y se confirmó mantener P1: sigue
  expuesto solo como `execution_manifest["manifest_incomplete"]`, nunca
  como `rejection_reason`.

`errors` y `raw_response` se conservan completos en los 3 casos de rechazo
real (antes, en el caso de fallo de transporte, ni siquiera existían —
la excepción abortaba antes de construir el record).

Mismo fix aplicado en `verified_pipeline.py:109` (mismo patrón de fallback
hardcodeado, mismo caller-contrato de `generate_controlled()`).

**Tests nuevos** (`test_ollama_client.py`, 7 tests): uno por cada causa
(transporte/JSON/schema/válido), uno que confirma que las 3 causas de
rechazo son mutuamente distintas (`test_generate_controlled_rejection_
reasons_are_never_confused`), y uno que fija la doctrina P1 explícitamente
(`test_generate_controlled_manifest_incomplete_never_becomes_rejection_
reason` — JSON válido + schema válido + `manifest_incomplete=True` sigue
siendo `verified`, `rejection_reason=None`).

## Limpieza de gobernanza (post-revisión de diff)

- **Permisos**: los 2 archivos de evidencia del canario (ETAPA 2) habían
  quedado `root:root 0640` (el contenedor `factory-api` corre como root) —
  corregidos a `1001:1004` (`ing_cpmo:ing_cpmo`) vía `docker exec chown`.
- **Archivo canario inválido retirado**: `w5v3-validation-7dd36dad0c77.json`
  — hash, fecha y motivo de exclusión quedaron registrados arriba antes de
  borrarlo. Nunca estuvo tracked en git.
- **Verificación de permisos tras una escritura real nueva**: se ejecutó
  una llamada real adicional (mismo par `ALCOA_ACCURATE`/chunk 0, solo para
  verificar el criterio de permisos) — el archivo resultante
  (`w5v3-validation-37cac8694a80.json`) **volvió a aparecer `root:root`**.
  Esto confirma que el problema de propiedad es **estructural, no
  resuelto**: cada escritura real desde el contenedor (que corre como root)
  va a seguir generando archivos `root:root` hasta que `write_validation_
  evidence()` haga el `chown` explícito después de escribir, o el
  contenedor deje de correr como root. El `chown` manual aplicado en esta
  fase (y en Fase 5.4.3) es un parche por corrida, no una corrección de
  raíz — **no reportar esto como resuelto**. Se corrigió el permiso de este
  archivo también, pero como no aportaba evidencia nueva (mismo par ya
  documentado en el canario PASS) se retiró del directorio en vez de
  conservarlo.
- **Estado final de `validation_evidence/`** (3 archivos, todos
  `ing_cpmo:ing_cpmo 640`, todos legibles):
  - `w5v3-validation-40523ef722ef.json` — corrida real completa de Fase
    5.4.3 (57 registros).
  - `w5v3-validation-18da5e36a51a.json` — canario ETAPA 2, primer intento
    (falló).
  - `w5v3-validation-4455c94588e0.json` — canario ETAPA 2, repetición
    (PASS).

## Gate 0

- Suite completa: **699 passed, 1 skipped, 0 failed** (693 de la revisión
  anterior + 7 tests nuevos de clasificación de `rejection_reason`, menos 1
  ya contado por duplicado en el conteo previo).
- Selfcheck host: `PASS=4 FAIL=0` (2125 entradas de auditoría, 1 fork
  concurrente aceptado, sin `hash_errors`).
- 3 llamadas reales a Ollama en total en esta fase (canario fallido +
  repetición + 1 de verificación de permisos, esta última descartada),
  todas `run_context=validation`.

## Diff acumulado (Fase 5.4 + 5.4.4, aún sin commitear)

```
 M factory/regulatory/schemas/finding_llm_v1.json        (evidence_page: anyOf, sin confirmar como causa real)
 M factory/regulatory/tools/run_validation_evidence.py   (persistencia raw_response/errors + document_sha256 [5.4] + fix de prompt confidence 0-1 [5.4.4])
 M factory/tests/test_run_context_audit.py               (aislamiento VALIDATION_EVIDENCE_BASE [5.4])
 M factory/tests/test_run_validation_evidence_runner.py  (fixtures de aislamiento + tests de persistencia [5.4])
 M factory/tests/test_schema_enforcement.py               (8 tests, 6 sinteticos por causa [5.4/5.4.4])
?? factory/docs/W5_3_FASE5_4_CIERRE.md
?? factory/docs/W5_3_FASE5_4_4_CIERRE.md
?? factory/regulatory/validation_evidence/w5v3-validation-40523ef722ef.json   (57 registros, corrida real Fase 5.4.3)
?? factory/regulatory/validation_evidence/w5v3-validation-18da5e36a51a.json   (canario fallido, causa real capturada)
?? factory/regulatory/validation_evidence/w5v3-validation-4455c94588e0.json   (canario PASS)
```

**Diff adicional de este cierre (ETAPA 3, 2026-07-20 — no repite llamadas,
solo documenta la corrida ya ejecutada el 2026-07-18):**

```
 M factory/docs/W5_3_FASE5_4_4_CIERRE.md                                        (este addendum)
?? factory/regulatory/validation_evidence/manifests/w5v3-validation-49de4fd0d1d1.manifest.json  (manifiesto sanitizado, 57 registros)
```

El JSON crudo de ETAPA 3 (`w5v3-validation-49de4fd0d1d1.json`, ~110 KB)
permanece fuera del índice de Git por diseño (`.gitignore` de Fase 5.4.4,
punto 1 más abajo) — mismo tratamiento que los 3 archivos reales
anteriores.

## Estado de producción

```
PERSISTENCE_OF_EVIDENCE = PASS
VALIDATION_PRODUCTION_ISOLATION = PASS
GOLDEN_DATASET_TECHNICAL_ELIGIBILITY = true
DOCUMENT_COVERAGE = PARTIAL
OLLAMA_SCHEMA_COMPATIBILITY = PASS_FOR_CONTROLLED_PILOT  (actualizado por ETAPA 3, ver sección de arriba — histórico: CANARY_PASS_N1_PENDING_SCALE_VALIDATION al cierre del canario, antes CRITICAL_FAIL)
REGULATORY_EVALUATION_COMPLETE = false
PRODUCTION_ENABLEMENT = BLOCKED
FASE_5_4_4_STATUS = CLOSED_WITH_FOLLOW_UP
```

Estado histórico al cierre del canario (ETAPA 2, previo a este addendum):
`OLLAMA_SCHEMA_COMPATIBILITY` dejaba de ser `CRITICAL_FAIL` pero no pasaba
a `PASS` porque solo un par de 57 había sido re-verificado. **Ese estado
quedó superado por ETAPA 3** (regresión completa, n=57, 0 rechazos por
`schema_validation_failed`) — ver sección "ETAPA 3" arriba para el detalle
y la fecha de cierre. Sin cambios en `PRODUCTION_ENABLEMENT` ni en
`REGULATORY_EVALUATION_COMPLETE`: ninguna llamada de ETAPA 2 ni ETAPA 3
usó `run_context` distinto de `validation`, y la cobertura sigue siendo
parcial (un documento, 3/29 chunks por requisito).

## Gobernanza de `validation_evidence/` en Git (post-revisión, misma fase)

Definida e implementada completa, sin dejar la decisión pendiente:

1. **Ningún JSON crudo entra a Git** — ni los 3 actuales ni futuros.
   `factory/regulatory/validation_evidence/.gitignore` (nuevo, tracked)
   ignora `*.json`/`*.tmp`/`*.partial` en la raíz del directorio, con
   excepción explícita de `manifests/*.manifest.json`.
2. **README.md versionado** (`factory/regulatory/validation_evidence/
   README.md`) — finalidad, clasificación `INTERNAL_VALIDATION_EVIDENCE`,
   contenido prohibido, permisos, retención (sin expiración automática,
   igual que Fase 5.2), legal hold, procedimiento de eliminación auditada.
3. **Manifiesto sanitizado por corrida** (`factory/regulatory/
   validation_evidence_manifest.py`, nuevo) — diseño **allowlist** (no
   blocklist): se reconstruye campo por campo desde una lista explícita de
   claves permitidas (hashes, `model_digest`, `prompt_sha256`,
   `chunk_sha256`, estados, conclusiones agregadas), nunca copiando un
   dict de origen completo. Esto significa que `raw_response`,
   `llm_output` (contiene `evidence_quote`/`rationale` = texto del
   documento), `source_text`, `_by_req_candidates`, o cualquier campo
   nuevo que alguien agregue a un record en el futuro sin pensar en esto,
   se descarta por construcción. Wireado en `run_validation_evidence()`
   (se genera automáticamente después de cada corrida real, con su propio
   estado de 2 valores `MANIFEST_WRITTEN`/`MANIFEST_WRITE_FAILED`,
   independiente del estado de la escritura cruda).
4. **Test de allowlist** (`test_validation_evidence_git_governance.py`) —
   corre contra el índice real de Git (`git ls-files`), falla si aparece
   cualquier archivo tracked que no sea `.gitignore`/`README.md`/
   `manifests/*.manifest.json`, y además escanea el CONTENIDO de los
   manifiestos tracked buscando `raw_response`/`source_text`/
   `_by_req_candidates`/patrones de API key/claves JSON sospechosas de
   credencial.
5. **Escáner de pre-commit + modo CI**
   (`factory/scripts/ops/scan_validation_evidence_staged.py`) — reutiliza
   los mismos patrones de `factory/core/report_sanitizer.py` (un solo
   lugar de verdad sobre "qué parece un secreto"). Verificado en vivo: un
   `git add -f` forzando el JSON crudo real fue bloqueado (`exit 1`,
   mensaje explícito) antes de escribir esta línea. Instalado como hook
   real via `factory/scripts/ops/install_git_hooks.sh` (`.git/hooks/` no
   es versionable, por eso el instalador sí lo es — cualquier clone nuevo
   debe correrlo una vez).
6. **Corrección de raíz del propietario de archivos futuros**
   (`validation_evidence_writer.py` y `validation_evidence_manifest.py`):
   - Escritura atómica: `<nombre>.<pid>.tmp` en el mismo directorio +
     `os.replace()` (nunca un archivo parcial visible con el nombre final).
   - Modo de archivo `0640`, modo de directorio `0750` (aplicado en cada
     escritura, idempotente).
   - Propietario/grupo **heredados del directorio ya autorizado**
     (`os.chown(tmp, dir_stat.st_uid, dir_stat.st_gid)`) — nunca un
     UID/GID hardcodeado en el código. El `chown` manual aplicado en
     sesiones anteriores (Fase 5.4.3, y el intento inicial de esta misma
     fase) era un parche por corrida; esto es la corrección real.
   - **Verificado con una escritura real** desde `factory-api` (que corre
     como root): archivo final `ing_cpmo:ing_cpmo 640`, directorio
     `ing_cpmo:ing_cpmo 750`, legible por `ing_cpmo` sin intervención
     manual. Cero archivos `root:root` nuevos — ver sección de resultados
     más abajo.
7. **Incidente propio detectado y corregido en esta misma fase**: al
   revisar el diff antes de este commit, `git status` mostró 6
   manifiestos sintéticos (`document_sha256` de `dummy.pdf`) tracked en
   `manifests/` — la fixture `autouse` de `test_run_validation_evidence_
   runner.py` aislaba `validation_evidence_writer.VALIDATION_EVIDENCE_
   BASE` pero NO `validation_evidence_manifest.VALIDATION_EVIDENCE_BASE`
   (módulo nuevo, con su propio path por defecto) — los tests de ese
   archivo escribían manifiestos reales sin darse cuenta. Corregido antes
   de comitear nada (fixture ahora aísla ambos módulos); los 6 archivos
   sintéticos se borraron sin llegar a stage.
8. **Los 3 JSON reales existentes se conservan fuera del índice de Git**
   como evidencia local controlada (permisos `ing_cpmo:ing_cpmo 640`,
   legibles, con legal hold implícito porque sustentan las conclusiones de
   Fase 5.4.3/5.4.4). Hashes registrados:

   | Archivo | SHA-256 |
   |---|---|
   | `w5v3-validation-40523ef722ef.json` (corrida real completa, 57 registros) | `20c14f9294b7781a16f27786c6bf9cfa3f18dfb63c6ff6e575155cca3ed2b4cf` |
   | `w5v3-validation-18da5e36a51a.json` (canario ETAPA 2, falló) | `eeb07806f2303c950742c3100a6a3d6a3b1688600c24380bf428bdf3889552e7` |
   | `w5v3-validation-4455c94588e0.json` (canario ETAPA 2, PASS) | `d9e8a8ec172b180f62aeb00a34499ade04bc0aca999cd25d19decdd018c773ba` |

   Sus 3 manifiestos sanitizados correspondientes **sí** quedan en el
   índice de Git (`manifests/*.manifest.json`), verificados sin ninguna de
   las subcadenas prohibidas.

## Pendiente real / recomendación

- ~~**ETAPA 3** (57 llamadas, comparación completa contra Fase 5.4.3) sigue
  sin autorizar~~ — **CERRADA** (ver sección "ETAPA 3" arriba,
  `run_id w5v3-validation-49de4fd0d1d1`, cierre 2026-07-20). El fix de
  prompt resuelve el patrón completo a escala (21→0 rechazos por
  `schema_validation_failed`); el único rechazo real de ETAPA 3 es una
  causa distinta y aislada (`citation_not_found`, n=1).
- Nota de gobernanza (Fase 5.4, todavía sin corregir en el código, ya no
  bloqueante para este cierre): el bug de `rejection_reason` hardcodeado a
  `"schema_validation_failed"` (no distingue "JSON inválido" de "schema
  inválido" en ese campo, aunque `errors` sí lo hace) queda documentado
  pero sin corregir — mejora de legibilidad para W5.5.
- Sigue sin decidirse la gobernanza de `validation_evidence/` en git a
  largo plazo (mecanismo de manifiesto sanitizado ya implementado y
  probado con 4 corridas reales, incluida ETAPA 3; la pregunta abierta es
  solo de volumen/retención a futuro, no de diseño).
- **Nuevo pendiente real, abierto por este cierre**: el manifiesto
  sanitizado de ETAPA 3
  (`factory/regulatory/validation_evidence/manifests/w5v3-validation-49de4fd0d1d1.manifest.json`)
  y este mismo documento están sin commitear — ver diff actualizado.
- **Fuera de alcance de este cierre, señalado para decisión humana**: el
  salto de 5→18 conclusiones `DOCUMENTED_AND_SUPPORTED` (con 15/18 bajo
  `SUPPORTING_EVIDENCE_UNDER_REVIEW`) es un efecto correcto de dejar de
  perder evidencia por rechazo de schema, pero no ha pasado por juicio QA
  humano — no usar estas conclusiones como aceptación de cumplimiento sin
  esa revisión.
- **Pendiente explícito para W5.5** — `DOCUMENTATION_GAP` (1 caso:
  `ALCOA_CONTEMPORANEOUS`, 0/2 chunks observados sobre `coverage=partial`):
  queda registrado como pendiente, **no se corrige en este cierre**. No se
  sabe todavía si es un gap real del documento FS_v1.2 o un artefacto de
  la cobertura parcial (3/29 chunks reales por requisito) — solo se podrá
  distinguir ampliando cobertura o evaluando el 100% de los chunks, lo cual
  queda fuera de alcance de Fase 5.4.4.
