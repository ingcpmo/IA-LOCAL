# INFORME DE VALIDACIÓN W5 V2 — VERSIÓN CORREGIDA

**Fecha:** 2026-07-28
**Alcance:** corrección del informe de validación de W5 V2 (rediseño regulatorio, fases A–P).
**Naturaleza de este documento:** SOLO INFORME. No se implementó código, no se
commiteó, no se invocó Ollama, no se cambió ningún estado gobernado.
**ALCOA+ (FSV12-11):** CONGELADA. Verificado: 0 procesos de `schedule_alcoa.sh`
activos; snapshot intacto en `c2d58e8`. No se tocó.
**HEAD de referencia:** `d69a2f6` (`docs(w5v2): first real nine-artifact QA package (FS_v1.2)`).

---

## 0. Qué se corrigió respecto del informe anterior

| # | Defecto del informe anterior | Corrección aplicada |
|---|---|---|
| 1 | Matriz A–P incompleta/truncada (faltaba el detalle G–M; la línea de F estaba corrupta) | §4 regenera las 16 fases completas, A–P, sin excepción |
| 2 | `FORMAL_BASELINE_READY` tratado como un solo indicador | §2 lo separa en `HISTORICAL_URS_BASELINE_EXISTS` y `CURRENT_W5_FORMAL_BASELINE_READY=false` |
| 3 | Un único eje PASS/FAIL | §1 define 6 estados: GLOBAL_PASS, PILOT_PASS, PARTIAL, FAIL, BLOCKED, NOT_EXECUTED |
| 4 | Gates 23–30 contabilizados como PASS global | §5 los reclasifica a PILOT_PASS: toda su evidencia proviene de **un solo candidato** |
| 5 | Fases E, F, K, L, M, O sin nivel de validación | §1.2 define 4 niveles y §4 los asigna por fase |
| 6 | `PHASES_NOT_EXECUTED=0` | §6 lo elimina y lo sustituye por 5 métricas independientes |
| 7 | Aprobar la cadencia de reverificación confundido con reverificar | §7 los separa como tareas distintas |
| 8 | Evidence Packs presentados como aprobables por sí solos | §8 fija sus dos precondiciones |
| 9 | — | §9 mantiene los tres estados globales bloqueados |

---

## 1. Taxonomías usadas

### 1.1 Estados de gate

| Estado | Significado |
|---|---|
| `GLOBAL_PASS` | Criterio satisfecho sobre **todo** el alcance declarado del gate |
| `PILOT_PASS` | Criterio satisfecho, pero la evidencia proviene de un subconjunto (1 documento / 1 agente / 1 candidato). No generaliza |
| `PARTIAL` | Mecanismo existe y funciona, pero cubre solo parte del criterio o deja condiciones sin medir |
| `FAIL` | Criterio no satisfecho, con defecto identificado |
| `BLOCKED` | No evaluable porque depende de una decisión o insumo externo aún no disponible |
| `NOT_EXECUTED` | Nunca se ejecutó; la condición no se dio o requiere una acción humana no realizada |

### 1.2 Niveles de validación por fase

| Nivel | Requiere |
|---|---|
| `IMPLEMENTATION_VALIDATED` | Código existe, commiteado, con pruebas unitarias verdes |
| `PILOT_VALIDATED` | Además: ejecutado sobre datos reales, en alcance reducido (1 documento o subconjunto de requisitos) |
| `FULL_SCOPE_VALIDATED` | Además: ejecutado sobre el alcance completo declarado (14/14 documentos Rockwell, los 4 conjuntos de agentes) |
| `FORMAL_VALIDATED` | Además: con las fuentes regulatorias **reverificadas** y con **revisión humana documentada** de los resultados |

Los niveles son acumulativos: nadie alcanza `PILOT_VALIDATED` sin `IMPLEMENTATION_VALIDATED`.

---

## 2. Separación de baselines

> El informe anterior mezclaba dos cosas distintas bajo un mismo nombre.

| Indicador | Valor | Base |
|---|---|---|
| `HISTORICAL_URS_BASELINE_EXISTS` | **true** | Existe la corrida histórica URS v2.1 con sus artefactos en `factory/docs/gmpai_reanalysis/urs_v2_1/`. Es un hecho histórico, no un estado de aprobación |
| `CURRENT_W5_FORMAL_BASELINE_READY` | **false** | Requiere (a) las 3 fuentes fuera de `pending_reverification` y (b) Evidence Packs fuera de `PROVISIONAL_ONLY`. Ninguna de las dos se cumple hoy |

Estado real de las precondiciones, verificado sobre disco:

- `factory/regulatory/sources/registry.json`: **3/3** fuentes con
  `regulatory_currency_status = pending_reverification`
  (`ecfr_21cfr_part11`, `eu_gmp_annex11`, `mhra_gxp_di_guidance_2018`).
- `factory/regulatory/requirement_catalog/requirements.yaml`: 19 requisitos,
  `catalog_version 1.0`, con `regulatory_currency_disclaimer` explícito de que
  **ninguna fuente está declarada vigente-verificada**. Los packs son
  `human_drafted_provisional` ⇒ **`EVIDENCE_PACKS = PROVISIONAL_ONLY`**.

Que exista la baseline histórica **no** hace formal a la baseline actual.

---

## 3. Alcance realmente cubierto (no confundir con alcance implementado)

| Dimensión | Cubierto | Total | Nota |
|---|---|---|---|
| Documentos Rockwell analizados por LLM | **1** | 14 | Solo FS_v1.2 (`RW-0005`) |
| Conjuntos de agentes ejecutados sobre ese documento | **1** | 4 | Solo `eu_annex11_agent` (27/27 chunks, 0 fallos técnicos). ALCOA+ congelada; Part 11 y trazabilidad no re-ejecutados bajo el presupuesto corregido |
| Fuentes regulatorias reverificadas formalmente | **0** | 3 | Ver §7 |
| Candidatos con paquete de 9 artefactos | **1** | — | `PKG-FS-V1-2-REAL-CONTROLLED` |
| Decisiones QA humanas sobre paquete completo | **0** | — | `qa_package_ready = false` |
| Estados terminales del inventario | 14 | 14 | 10 `ORIGINAL_SOURCE_CONFIRMED`, 2 `OCR_REQUIRED`, 1 `DUPLICATE`, 1 `HUMAN_REVIEW_REQUIRED` |

---

## 4. Matriz completa de fases A–P (regenerada)

Sin truncamientos. `IMPL` = IMPLEMENTATION_VALIDATED, `PILOT` = PILOT_VALIDATED,
`FULL` = FULL_SCOPE_VALIDATED, `FORMAL` = FORMAL_VALIDATED.

| Fase | Objetivo | Commit | IMPL | PILOT | FULL | FORMAL | Estado | Evidencia / limitación real |
|---|---|---|---|---|---|---|---|---|
| **A** | Inventario Rockwell y allowlist | `d212011` | ✅ | ✅ | ✅ | ❌ | `GLOBAL_PASS` | 14/14 archivos con estado terminal en `source_baseline_allowlist.yaml`. FULL aplica al inventario, no al análisis. Pendientes: 2 OCR, 1 revisión humana (T-039) |
| **B** | Gobernanza de fuentes | `a6a1128` | ✅ | ✅ | ❌ | ❌ | `PARTIAL` | Catálogo de 3 fuentes con hash íntegro (`local_integrity_status=PASS`), pero 3/3 en `pending_reverification`; 2 URLs no apuntan al artefacto gobernado; `ecfr` es artefacto derivado, no verificable por hash contra el original |
| **C** | Requirement Evidence Packs | `6372592`, `46ca69f` | ✅ | ✅ | ❌ | ❌ | `PARTIAL` | 19 requisitos con cita anclada y `evidence_min_criteria`; todos `human_drafted_provisional` ⇒ `PROVISIONAL_ONLY`. Sin revisión humana documentada |
| **D** | ModelProvider y runtime independiente | `ab271c5` + `b2ae2ec` (gate 14) | ✅ | ✅ | ❌ | ❌ | `PARTIAL` | Gate 14 cerrado (0 imports directos de Ollama fuera de la interfaz) y ejercitado en corrida real. **Limitación real: la ampliación al motor legacy vive en un workspace gitignorado — esa parte del alcance NO está bajo control de versiones** |
| **E** | Inyección de texto regulatorio | `647fe53` | ✅ | ✅ | ❌ | ❌ | `PARTIAL` | El catálogo SÍ está cableado (`chunked_engine.py:143,171`) — el `production_status` de `requirements.yaml` está **desactualizado** y afirma lo contrario. Defecto real: `_lookup_regulatory_text()` hace **fallback silencioso** a solo `label` si el req_id no está en el catálogo (`chunked_engine.py:135-141`), es decir **fail-open**, contra lo que exige el gate 4 |
| **F** | Validación A/B/C/D | `68152c5`, `424762c`, `e1a740b`, `18b046f` | ✅ | ✅ | ❌ | ❌ | `PILOT_PASS` | `A∧B∧C∧D==MET` incondicional; `apply_conclusion_preconditions()` §13.3 como única autoridad, fail-closed. Ejercitado en corrida real: chunk 19 aceptó la misma cita para ANNEX11_9 y la rechazó para ANNEX11_4 por relevancia temática. Alcance: 5 checkpoints de 1 agente sobre 1 documento |
| **G** | Golden Dataset y calificación del modelo | `e622da7` + `5c83525` | ✅ | ❌ | ❌ | ❌ | `PARTIAL` | Golden Dataset 14/14. `model_qualification_gate.py` operativo, registro persistido: estado **`QUALIFIED_FOR_VALIDATION_ONLY`**, 9/13 métricas medidas y **4 declaradas `NOT_MEASURED`** (exigen inferencia real; no se rellenan con 0). Sin PILOT: el Golden Dataset no es documento real |
| **H** | Baseline formal | `66cd4b9` (mecánica) | ✅ | ❌ | ❌ | ❌ | `BLOCKED` | La adjudicación humana de los 25 `review_required` + 3 `rejected_by_verifier` de URS v2.1 **no se ha hecho**. Es el único punto del roadmap que depende de una decisión externa al código. `CURRENT_W5_FORMAL_BASELINE_READY=false` |
| **I** | Hallazgos, gaps y remediación | `cb3add5` + `18b046f` (deuda I-1) | ✅ | ✅ | ❌ | ❌ | `PILOT_PASS` | El veredicto ABCD viaja del `Finding` al narrative y el mapper no emite `FULL_COVERAGE` sin él. Destapó que FSV12-07 y FSV12-11 reales mapeaban con D nunca evaluada. Alcance: findings de 1 documento |
| **J** | Motor de generación por formato | `9fb5806` + `1396894` | ✅ | ✅ | ❌ | ❌ | `PILOT_PASS` | Generadores DOCX/PDF/XLSX/DOCM reales; allowlist de Fase A conectada. Ejecutado sobre 1 de 14 documentos (DOCX de FS_v1.2) |
| **K** | Aplicación gobernada de cambios | `b86a86b` | ✅ | ✅ | ❌ | ❌ | `PILOT_PASS` | 2 cambios reales (COR-5, COR-2), ambos `HIGH_RISK` ⇒ ninguno autoaplicado; ambos con `exception_review` y decisión humana registrada (`Cesar (ing_cpmo)`, `ACCEPTED_WITH_JUSTIFICATION`). Alcance: 2 cambios, 1 documento |
| **L** | Generación del documento candidato completo | `f4ba879` | ✅ | ✅ | ❌ | ❌ | `PILOT_PASS` | `candidate_document.docx` generado y abierto correctamente en la revalidación. **Hasta 2026-07-28 L no tenía ningún llamador de producción**: solo pytest. Lo cerró el orquestador `fcceeb4` |
| **M** | Redline, matriz, reseña y manifest | `c6746e1` + `fcceeb4` | ✅ | ✅ | ❌ | ❌ | `PILOT_PASS` | Los 9 artefactos generados de forma consistente; **primer manifest con `manifest_fingerprint_complete=true`** (`da0ad429…`). Mismo hallazgo estructural que L: sin llamador de producción hasta `fcceeb4` |
| **N** | `CORRECTED_DOCUMENT_GENERATION_GATE` | `1c0ef9f` + `1791ff5` (fix) | ✅ | ✅ | ❌ | ❌ | `PARTIAL` | Ejecutado sobre el paquete real: resultado **`DOCUMENT_GENERATION_PARTIAL`**, `gate_passed=false`, criterio en rojo `reporte_de_calidad_existe`. `1791ff5` corrigió un defecto real (comparaba conteo de PÁRRAFOS contra conteo de SECCIONES ⇒ 14 vs 8, fallaba con las 8 secciones intactas; podía dar también el error inverso) |
| **O** | Revalidación independiente (AGT-RVL) | `87d351f` + `da3349f` | ✅ | ✅ | ❌ | ❌ | `PILOT_PASS` | Revalidación **ejecutada** sobre el candidato real: `revalidation_passed=true`, COR-5 y COR-2 `CLOSED`, `new_gaps_introduced=[]`, `all_hashes_valid=true`, `artifacts_consistent=true`. Alcance: 1 candidato |
| **P** | Paquete final para QA | `8623403` + `bfe11ba` | ✅ | ❌ | ❌ | ❌ | `NOT_EXECUTED` | Las 4 decisiones, identidad real, idempotencia 409 y `decision_origin=human_confirmed` existen y ahora sí están probados en HTTP (`bfe11ba` destapó que **no había ningún TestClient en la suite**). Pero **no se ha tomado ninguna decisión QA real**: `qa_package_ready=false` |

### Conteo por fase

| Estado | Fases | n |
|---|---|---|
| `GLOBAL_PASS` | A | **1** |
| `PILOT_PASS` | F, I, J, K, L, M, O | **7** |
| `PARTIAL` | B, C, D, E, G, N | **6** |
| `FAIL` | — | **0** |
| `BLOCKED` | H | **1** |
| `NOT_EXECUTED` | P | **1** |
| **Total** | | **16** |

---

## 5. Matriz completa de los 31 gates (§22 del plan)

| # | Gate | Estado | Base de la clasificación |
|---|---|---|---|
| 1 | Inventario 100%, 0 omitidos | `GLOBAL_PASS` | 14/14 en allowlist, estado terminal |
| 2 | Originales con SHA-256, 0 sobrescritos | `PARTIAL` | Hashes registrados e íntegros; la verificación **continua** no está programada |
| 3 | 100% requisitos con fuente gobernada (`LOCAL_CANONICAL_COPY_VERIFIED`) | **`FAIL`** | `source_registry_entry_v1.json` fija `regulatory_currency_status` a un enum de **un solo valor** (`pending_reverification`): 0/3 fuentes pueden alcanzar el estado exigido |
| 4 | 100% prompts con Evidence Pack completo | **`FAIL`** | El gate exige *bloquear la llamada* si el pack está incompleto. La implementación hace lo contrario: fallback silencioso a solo `label` (`chunked_engine.py:135-141`, `166-169`) — **fail-open** |
| 5 | Fuentes con URL, versión, SHA-256 | `PARTIAL` | Schema completo, pero `version="NO_DISPONIBLE"` en eCFR y 2 URLs que no apuntan al artefacto gobernado |
| 6 | Evidencias con anclaje documental (validación A) | `PILOT_PASS` | Ejercitado en corrida real (chunk 19); 1 agente / 1 documento |
| 7 | Conclusiones positivas con A/B/C/D | `PILOT_PASS` | Incondicional y fail-closed; ejercitado en corrida real |
| 8 | 0 citas inventadas / léxicas aisladas | `PARTIAL` | Golden Dataset 14/14 PASS, pero 4/13 métricas `NOT_MEASURED` y modelo `QUALIFIED_FOR_VALIDATION_ONLY` |
| 9 | 0 `DOCUMENTATION_GAP` con cobertura incompleta (§13.3) | `PILOT_PASS` | `apply_conclusion_preconditions()` aplicado en corrida real |
| 10 | 0 cambios sin requisito/evidencia/explicación/fuente | `PILOT_PASS` | 2 cambios reales completos |
| 11 | 0 cambios con redacción inválida (AGT-QLT) | `PARTIAL` | AGT-QLT corrió, pero 2 controles quedaron `NOT_EVALUATED` (terminología sin tabla real; ortografía sin herramienta determinista) ⇒ `quality_applied=false` |
| 12 | 0 afirmaciones de implementación sin evidencia | `PILOT_PASS` | Control `ausencia_afirmacion_no_demostrada` PASS en los 2 cambios |
| 13 | 0 dependencias runtime de Claude Code | `GLOBAL_PASS` | Auditoría de runtime: los 8 agentes son scripts Python autónomos |
| 14 | 100% agentes híbridos con ModelProvider | `GLOBAL_PASS` | Cerrado en `b2ae2ec`: `generate_controlled` detrás de ModelProvider, fail-closed con `ControlledGenerationNotSupportedError` |
| 15 | 0 llamadas LLM para tareas deterministas | `PARTIAL` | Sostenido por revisión de diseño; sin check automatizado que lo impida |
| 16 | 100% salidas LLM validadas por schema | `PILOT_PASS` | `checkpoint_llm_response_v1`; 27/27 chunks, 0 `technical_execution_failure` |
| 17 | 100% llamadas con `run_id` y `task_id` | `PILOT_PASS` | Verificado en el JSON real de la corrida: ambos campos presentes por chunk |
| 18 | 0 cambios automáticos a proveedor externo | `PARTIAL` | El código declara error duro, no fallback (`model_provider.py:152`); la condición `LLM_SERVICE_UNAVAILABLE` nunca se ejercitó en corrida real |
| 19 | 0 `HIGH_RISK` autoaplicados | `PILOT_PASS` | COR-5 y COR-2, ambos `HIGH_RISK`, fueron a excepción con decisión humana; 0 autoaplicados |
| 20 | 0 fallos recuperables bloqueando la corrida | `PARTIAL` | La corrida válida tuvo 0 fallos técnicos ⇒ la continuidad no se ejercitó bajo fallo real |
| 21 | 100% excepciones dentro del paquete QA | `PILOT_PASS` | 2 excepciones generadas, 2 en `exception_package.json` |
| 22 | 100% documentos remediables con candidato completo | `PILOT_PASS` | 1 candidato, 1 documento |
| 23 | 100% candidatos con SHA-256 nuevo | `PILOT_PASS` | **Un solo candidato** |
| 24 | 100% candidatos con redline, matriz, reseña y manifest | `PILOT_PASS` | **Un solo candidato** |
| 25 | 100% candidatos revalidados | `PILOT_PASS` | **Un solo candidato** |
| 26 | 0 diferencias no explicadas candidato/redline | `PILOT_PASS` | **Un solo candidato** (`artifacts_consistent=true`) |
| 27 | 0 cambios rechazados incorporados silenciosamente | `PILOT_PASS` | **Un solo candidato**, y **vacuo**: `excluded_change_ids=[]`, no hubo ningún `REJECTED_BY_VALIDATOR` que pudiera colarse |
| 28 | 0 candidatos entregados como fragmentos | `PILOT_PASS` | **Un solo candidato**; válido solo tras el fix `1791ff5` del criterio de estructura |
| 29 | 0 paquetes sin documento candidato | `PILOT_PASS` | **Un solo candidato** |
| 30 | 0 divergencias entre los 9 artefactos | `PARTIAL` | `manifest_fingerprint_complete=true` y `artifacts_consistent=true`, pero quedan **2 hallazgos reales del candidato sin resolver y deliberadamente no parcheados**: `referencias_cruzadas` FAIL (refs a 2.1.1/3.1.12/3.1.3/7.1.1 inexistentes en la estructura extraída) y `sin_duplicaciones` FAIL (76 párrafos duplicados). Probable artefacto del extractor, no confirmado |
| 31 | 0 liberaciones automáticas; aprobación QA obligatoria | `NOT_EXECUTED` | No ha habido ninguna liberación. La mecánica (`decision_origin=human_confirmed`, 409) está probada en HTTP, pero **la decisión QA real sobre este paquete no se ha tomado** |

### Conteo de gates corregido

| Estado | Gates | n |
|---|---|---|
| `GLOBAL_PASS` | 1, 13, 14 | **3** |
| `PILOT_PASS` | 6, 7, 9, 10, 12, 16, 17, 19, 21, 22, 23, 24, 25, 26, 27, 28, 29 | **17** |
| `PARTIAL` | 2, 5, 8, 11, 15, 18, 20, 30 | **8** |
| `FAIL` | 3, 4 | **2** |
| `BLOCKED` | — | **0** |
| `NOT_EXECUTED` | 31 | **1** |
| **Total** | | **31** |

> **Corrección explícita al informe anterior:** los gates **23–30 no son PASS
> global**. Los ocho derivan su evidencia del mismo y único candidato
> `PKG-FS-V1-2-REAL-CONTROLLED` (1 de 14 documentos). Siete quedan
> `PILOT_PASS` y el 30 queda `PARTIAL` por dos defectos abiertos del candidato.
> Un gate expresado como "100% de los candidatos" no puede declararse global
> con n=1.

---

## 6. Métricas de ejecución (sustituyen a `PHASES_NOT_EXECUTED=0`)

`PHASES_NOT_EXECUTED=0` era engañoso: mezclaba "el código existe" con "se
ejecutó sobre el alcance real". Se sustituye por cinco métricas independientes.

| Métrica | Valor | Definición |
|---|---|---|
| `PHASES_CODE_PRESENT` | **16 / 16** | Implementación existe con pruebas verdes (caveat: parte de D fuera de control de versiones) |
| `PHASES_PILOT_EXECUTED` | **13 / 16** | Ejecutadas sobre datos reales en alcance reducido. Excluye G (solo Golden Dataset), H (bloqueada) y P (sin decisión real) |
| `PHASES_FULL_SCOPE_EXECUTED` | **1 / 16** | Solo A (inventario 14/14). Ninguna fase analítica cubre los 14 documentos |
| `PHASES_FORMAL_VALIDATED` | **0 / 16** | Requiere fuentes reverificadas + revisión humana documentada. Ninguna |
| `PHASES_BLOCKED_OR_NOT_EXECUTED` | **2 / 16** | H (BLOCKED), P (NOT_EXECUTED) |

Métricas de alcance de datos, que son las que realmente limitan el informe:

| Métrica | Valor |
|---|---|
| `DOCUMENTS_ANALYZED` | 1 / 14 |
| `AGENT_SUITES_EXECUTED_ON_THAT_DOCUMENT` | 1 / 4 |
| `SOURCES_FORMALLY_REVERIFIED` | 0 / 3 |
| `QA_PACKAGES_WITH_HUMAN_DECISION` | 0 / 1 |
| `EVIDENCE_PACKS_APPROVED` | 0 / 19 |

---

## 7. Reverificación de fuentes: dos tareas distintas

> **Aprobar la política de cadencia de reverificación NO reverifica ninguna
> fuente.** Son dos tareas separadas, y ninguna de las dos está hecha.

**Tarea 7.A — Aprobar la política de cadencia** *(decisión de gobernanza,
pendiente de Cesar)*. Define cada cuánto se reverifica cada fuente y quién
responde. **No cambia el estado de ninguna fuente.**

**Tarea 7.B — Reverificación efectiva de las 3 fuentes** *(tarea de ejecución,
separada y no realizada)*. Requiere, por fuente: contrastar contra la URL
oficial, registrar el evento en la cadena de auditoría con `run_by` real, y
que una autoridad definida declare la vigencia.

Estado real, medido el 2026-07-28 con `check_source()` (función pura, sin
escribir en el log append-only ni en la cadena de auditoría; `check_all_governed_sources`
**no** se llamó porque exige `run_by` real y persiste evento — identidad humana):

| Fuente | Alcanzable | Hash | Obstáculo real |
|---|---|---|---|
| `eu_gmp_annex11` | HTTP 200 | **COINCIDE** byte a byte | Ninguno técnico. Falta el acto formal de declaración |
| `mhra_gxp_di_guidance_2018` | HTTP 200 | **COINCIDE** byte a byte (456031 B, `e05dda11…`) | `official_source_url` apunta a la página de aterrizaje de GOV.UK (76 KB de HTML), no al PDF. **Corregir la URL** |
| `ecfr_21cfr_part11` | HTTP 200 | **NO verificable por hash, nunca** | La copia gobernada es un artefacto **derivado** (texto ensamblado con cabecera propia del proyecto), no una descarga oficial. Alternativa comprobada en vivo: la API oficial con fecha fijada `…/api/versioner/v1/full/2026-07-01/title-21.xml?part=11` responde 200 XML y contiene 11.10 |

**Corrección importante sobre el plan previo:** decir que "reverificar
desbloquea el gate 3" era **falso**. `source_registry_entry_v1.json` fija el
enum a un solo valor a propósito y `source_currency_checker` declara
explícitamente que nunca lo reinterpreta. Desbloquear el gate 3 exige, **además**
de reverificar: (a) ampliar el enum del schema, (b) decidir quién tiene
autoridad para declarar vigente una fuente, (c) corregir las 2 URLs. Es una
decisión de gobernanza, no un paso mecánico.

---

## 8. Aprobación de Evidence Packs: dependencias

Los 19 Evidence Packs están hoy en `PROVISIONAL_ONLY` y **no pueden aprobarse
por sí solos**. Su aprobación depende de dos condiciones, ambas externas al
código:

1. **Reverificación de la fuente de la que derivan** (§7.B). Un pack no puede
   ser más firme que su fuente. Distribución actual por fuente:
   `mhra_gxp_di_guidance_2018` → 9 packs, `ecfr_21cfr_part11` → 5,
   `eu_gmp_annex11` → 5. Con 3/3 fuentes en `pending_reverification`,
   **0/19 packs** son aprobables hoy.
2. **Revisión humana documentada** de los criterios interpretativos
   (`evidence_min_criteria`), que hoy son `human_drafted_provisional`. Se
   requiere revisor identificado, fecha y registro persistido.

Mientras cualquiera de las dos falte, `EVIDENCE_PACKS = PROVISIONAL_ONLY` y
`CURRENT_W5_FORMAL_BASELINE_READY = false`.

---

## 9. Estados globales (sin cambio)

| Indicador | Valor | Razón |
|---|---|---|
| `FORMAL_RELEASE_GATE` | **BLOCKED** | 3/3 fuentes `pending_reverification`; gates 3 y 4 en FAIL; H sin adjudicación humana |
| `REGULATORY_COMPLIANCE` | **NOT_DETERMINED** | 1/14 documentos analizados, 1/4 agentes sobre ese documento. No hay base para afirmar ni negar cumplimiento |
| `PRODUCTION_ENABLEMENT` | **BLOCKED** | Modelo `QUALIFIED_FOR_VALIDATION_ONLY`; `run_context=validation`; ninguna corrida con contexto de producción |
| `CURRENT_W5_FORMAL_BASELINE_READY` | **false** | §2 |
| `HISTORICAL_URS_BASELINE_EXISTS` | true | §2 — hecho histórico, no aprobación |

---

## 10. Pendientes identificados (NO resueltos en este informe)

Listados para trazabilidad. Ninguno se ejecutó aquí.

| # | Pendiente | Tipo | Bloqueado por |
|---|---|---|---|
| 1 | Aprobar política de cadencia de reverificación | Gobernanza | Decisión de Cesar |
| 2 | Reverificación efectiva de las 3 fuentes con `run_by` real | Ejecución | #1 + identidad humana |
| 3 | Ampliar el enum de `regulatory_currency_status` y definir autoridad declarante | Diseño + gobernanza | #1 |
| 4 | Corregir `official_source_url` de MHRA y de eCFR | Datos | #3 |
| 5 | Revisión humana documentada de los 19 `evidence_min_criteria` | Humano | — |
| 6 | Adjudicación de los 25 `review_required` + 3 `rejected_by_verifier` de URS v2.1 (Fase H) | Humano | — |
| 7 | Corregir el fail-open del gate 4 (`_lookup_regulatory_text`) | Código | Aprobación |
| 8 | Actualizar el `production_status`/disclaimer desactualizado de `requirements.yaml` | Documentación | — |
| 9 | Investigar los 2 FAIL del candidato (`referencias_cruzadas`, `sin_duplicaciones`): ¿defecto del extractor o del documento? | Investigación | — |
| 10 | Identidad formal de AGT-RSG, AGT-EVD, AGT-VER, AGT-GAP | Diseño | Decidir schemas |
| 11 | Corridas LLM del resto del corpus (13/14 documentos) + OCR de 2 escaneados | Ejecución | Costo (12–15 h/corrida) + aprobación |
| 12 | Reanudar ALCOA+ (FSV12-11) desde el snapshot congelado `c2d58e8` | Ejecución | Orden explícita de Cesar |
| 13 | Versionar la ampliación de Fase D al motor legacy (hoy en workspace gitignorado) | Código | Decidir política del workspace |

---

**Fin del informe corregido.** No se implementó nada, no se commiteó, no se
llamó a Ollama, no se modificó ningún estado gobernado. ALCOA+ sigue congelada.
