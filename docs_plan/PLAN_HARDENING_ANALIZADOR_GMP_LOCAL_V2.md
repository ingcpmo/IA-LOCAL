# PLAN DE HARDENING — ANALIZADOR DOCUMENTAL GMP LOCAL V2

**Fecha:** 2026-08-28 · **Autoridad:** Capa 9 = Cesar · **Tipo:** DISEÑO. No implementación.
**Baseline de código:** `fix/clon-local-validacion` @ `c4e8296`.
**Fuentes:** `EVALUACION_REFERENCIAS_EXTERNAS_V2.md` (verificación de código en HEAD),
`REPORTE_FINAL_REDIESENO_..._20260828.md` (baseline documental), `HANDOFF_ARQ_HARDENING_V2_20260828.md`
(encuadre), revisión técnica externa no vinculante (`recomendacion_tecnica_4`).

---

## 0. PROCEDENCIA DE LA EVIDENCIA (leer primero)

Este diseño no re-verifica el árbol de trabajo. Se apoya en la verificación ya ejecutada contra
`HEAD c4e8296` y documentada en `EVALUACION_REFERENCIAS_EXTERNAS_V2.md`. Cada afirmación va etiquetada:

- `[VERIF]` — evidencia de código citada en la evaluación de HEAD.
- `[BASELINE]` — afirmación del reporte maestro, no re-verificada en código.
- `[HIPÓTESIS]` — deducción de este diseño. **Requiere confirmación antes de implementar.**

Las `[HIPÓTESIS]` marcadas `⛔` son bloqueantes: si se refutan, el paquete de trabajo asociado cambia
o desaparece. Ninguna se implementa sin confirmarla primero.

---

## 1. VEREDICTO

`REDESIGN_V3_REQUIRED = NO`. No hay defecto que invalide la arquitectura V2. El modelo canónico, el
grafo, los detectores deterministas, la cadena de remediación, el marcado `MACHINE GENERATED`, el
fail-closed de cargadores firmados y `network_locked()` están bien construidos y no se reabren.

Pero el reencuadre central de este diseño es distinto al del HANDOFF y al de la evaluación previa:

> **El problema dominante no es `tested_by = 0`. Es que el sistema no distingue entre "el documento
> dice que no" y "el documento no se pudo leer" — y emite hallazgos en ambos casos.**

`tested_by = 0` es un síntoma de esa clase de fallo, no la clase entera. La evaluación de HEAD ya
localizó su causa correctamente en extracción `[VERIF]`; lo que no se cerró es la consecuencia
arquitectónica: **la ausencia de datos se está convirtiendo en hallazgo sin precondición de
adecuación.** Eso contradice la invariante `fail-closed` que el propio sistema declara, y reproduce
exactamente el problema que motivó todo el rediseño V2 — que el reporte maestro enuncia así:
*"un analizador que no encuentra evidencia presente produce NCRs falsos"* `[BASELINE]`.

Prueba del reencuadre, con evidencia ya verificada:

```
RW-0009 (SAT): 62 claims · 0 sections · toc_anchored=false             [VERIF]
               contenido extraído = portada + carta + encuesta;
               el cuerpo (matriz de pruebas) NO está en la capa de texto
               → el pipeline no tiene OCR
La corrida real técnica incluyó RW-0009 entre los 6 documentos y emitió 24 findings [BASELINE]
La corrida E2E emitió 285 regulatory + 90 functional + 24 technical           [BASELINE]
```

El pipeline procesó un documento que no leyó, y siguió adelante. No hubo error, no hubo estado
degradado, no hubo supresión. **Falló abierto.**

---

## 2. QUÉ YA ESTÁ RESUELTO — NO DUPLICAR

Verificado en HEAD. Cualquier propuesta que reconstruya esto se rechaza por duplicación:

| Capacidad | Dónde vive |
|---|---|
| Modelo canónico + provenance obligatorio | `canonical/{model,persistence,extract_document}.py` |
| Grafo con aristas tipadas y linkers correctos | `graph/{store,build,queries}.py` — `_link_to_tests` y `verifies` **están bien implementados**, solo inanidos `[VERIF]` |
| Finding tipado con `machine_state`/`human_state`, provenance, risk determinista | `findings/{taxonomy,risk}.py` + `risk_matrix.yaml` |
| Fail-closed en cargadores firmados | `fixtures.assert_signed`, `technical_completeness_loader.assert_signed` |
| Egress bloqueado | `validation_v2/local_only.py::network_locked()` |
| Estados prohibidos | `taxonomy.FORBIDDEN_STATES` + `remediation_v2._guard_no_forbidden` |
| Cadena de remediación con DOCX físico y manifest | `remediation_v2.py` + `v2_runtime.py` |
| Golden datasets firmados e inmutables | `technical_suite_c.yaml`, `technical_completeness_rules.yaml` v1.1 |
| API V2 read-only (6 GET) | `api/routes/v2_analyzer.py`, registrada |
| Rollback de motor | `cutover.py` / `analyzer_router.py` |

**No crear `TechnicalCheckResult` ni ninguna abstracción paralela de resultado.** `Finding` +
`machine_state` + `evidence` + `provenance` + reglas + risk ya cubren ese contrato. Aceptado de la
revisión externa (§A).

---

## 3. PROBLEMAS REALES, CAUSAS Y CLASIFICACIÓN

### 3.1 Deudas confirmadas (reencuadradas)

| ID | Problema | Causa real `[VERIF]` | Clase |
|---|---|---|---|
| D-1 | Sin objetos `Test` canónicos | `extract_document.py` no tiene etapa de extracción de `Test`; `build_test()` con **0 llamadores de producción**; `test rows = 0` en los 6 documentos | Implementación incompleta |
| D-2 | SAT ilegible | RW-0009 sin capa de texto en el cuerpo; pipeline sin OCR | Documento + capacidad ausente |
| D-3 | Suites acopladas | `build_suite_c_corpus()` y `run_suite_c_*()` en el mismo módulo; los `anchor` del fixture son las frases literales que inserta el builder | Validez de constructo |
| D-4 | Sin fingerprint | `run_id` y `manifest.generated_at` son wall-clock; no se registran input-SHA, versiones/SHA de artefactos firmados, ni commit | Reproducibilidad |
| D-5 | Sin contrato de cualificación | Solo prosa + dict ad-hoc de `run_suite_c_formal()` | Cualificación |
| D-6 | UI no consume V2 | 23 módulos JS, 0 referencias a `/api/v1/v2-analyzer/*` | Operacional |
| D-7 | Semántica regulatoria | Techo del 7B, 6 vías | **FUERA DE ALCANCE** |
| D-8 | `refers_to` no poblado | `graph/build.py` no tiene ningún `add_edge("refers_to")`; el docstring L14 lo describe pero el builder no lo implementa `[DIAG 2026-08-28]` | Implementación incompleta — **deuda separada, NO se implementa en este hardening; sin paquete asignado** |

Corrección de atribución que mantengo de la evaluación previa y refuerzo: **D-1 no es deuda del grafo.**
El linker está correcto. Cualquier trabajo sobre `graph/` sería reabrir un componente sano.

### 3.2 Gaps materiales que el análisis anterior no cerró

Estos salen de cruzar la evidencia de código con el reporte maestro. Son la aportación propia de este
diseño.

**NG-1 — La ausencia no tiene precondición de adecuación (fail-closed roto en la frontera de ingesta).**
`[VERIF]` + `[DIAG 2026-08-28]`
Los detectores derivados de ausencia (`REQUIREMENT_NOT_TESTED`, `*_GAP`, `ORPHAN_DESIGN_ELEMENT`,
`completeness_findings`) concluyen sobre lo que **no** encuentran. No existe estado, gate ni
precondición que distinga *"el documento dice que no"* de *"el documento no se pudo leer"*.
*Diagnóstico read-only ejecutado sobre `v2e2e-20260828T035243Z`:* **0 findings anclados en RW-0009**
en las tres clases (regulatory 285 / functional 90 / technical 24; RW-0009 aporta 0 a cada una). La
contaminación **confirmada** no son "hallazgos marcados RW-0009" sino **los 70 `REQUIREMENT_NOT_TESTED`
funcionales** (de 90), con rationale literal *"…SIN ningún `test` transitivo en el grafo"* — artefacto
mecánico de `tested_by = 0` (D-1) repartido sobre los **5 documentos legibles**; RW-0009 es el SAT que
debía poblar esa mitad del grafo. **Los 24 findings técnicos NO se generalizan como inválidos**: son
derivados de ausencia dentro de documentos legibles (reglas de completitud / trazabilidad interna),
requieren adjudicación bajo NG-3 pero no son contaminación confirmada. Sigue siendo el problema más
grave del sistema y el más barato de contener (WP-B).

**NG-2 — Contradicción 0 vs 90 findings funcionales — RECONCILIADA.**
`[DIAG 2026-08-28]`
El reporte maestro §E afirma *"Corpus real Rockwell: 0 findings emitidos, 0 FP (dry run)"*, y §I lista
`functional_findings.json (90)` para `v2e2e-20260828T035243Z`. **No es un defecto de ningún número: es
desincronización de versión.** El "0" viene de `REPORTE_B8B_SUITE_B_DRY_RUN.md` (2026-08-27), que solo
contó 3 subtipos (`REQUIREMENT_NOT_TRACED`, `CONTRADICTORY_FUNCTIONAL_BEHAVIOR`, `TEST_WITHOUT_REQUIREMENT`),
los 3 en 0 con `designed_by = 184`. El "90" es la corrida E2E posterior, con `graph_functional_findings`
ya ampliado a `REQUIREMENT_NOT_TESTED` (70) + `IMPLEMENTATION_WITHOUT_REQUIREMENT` (20), `designed_by = 204`.
**Línea base funcional real sobre corpus = 90 (70 artefacto de D-1 + 20). El "0 findings / 0 FP" del
reporte maestro §E queda OBSOLETO y no debe citarse.** Confirma NG-3 y NG-4.

**NG-2b — Regulatory 285 vs 342 — RECONCILIADA (`[DIAG 2026-08-28]`).**
La corrida archivada `v2e2e-20260828T035243Z` (`audit_metadata.documents`) usó **5 documentos**
(`RW-0005, RW-0006, RW-0011, RW-0012, RW-0014`) — **RW-0009 no estuvo en esa invocación**. 285 = 57
findings de sub-criterio Tier-1 × 5 docs. Una corrida fresca con los **6 documentos** (incluido RW-0009)
da 342 = 57 × 6; RW-0009 aporta 57 `REGULATORY_INCONCLUSIVE` / `MACHINE_INCONCLUSIVE` (nunca desviación).
**No es cambio de código ni de comportamiento:** `git log 8d41b67..HEAD` para `regulatory_tier1.py`,
`evidence_bundle.py`, `bm25.py`, `decomposition.yaml`, `requirement_terms.yaml`, `requirements.yaml`
muestra **solo** el commit de WP-A, que no toca la ruta regulatoria. `regulatory_tier1_findings` sobre
RW-0009 tiene éxito de forma determinista (sus 62 claims de portada aún producen un candidato BM25 top
por sub-criterio → `REGULATORY_INCONCLUSIVE`). Es una elección de `document_ids` por invocación, no una
regla. **Baseline de WP-B = corrida fresca de 6 documentos** (fingerprints en §WP-B).

**NG-3 — Ningún gate está medido sobre datos reales.**
`[VERIF]`
`real_corpus_technical.py` corre sobre el corpus real **pero no puntúa** (sin TP/FN/FP). No existe
equivalente funcional. Por tanto `FUNCTIONAL_GATE = PASS (16/16)` y `TECHNICAL_GATE = PASS (0.90)`
provienen **exclusivamente de corpus sintético construido por el mismo autor que las reglas**. No es
que estén mal; es que su **rango reportable real es desconocido**. Esto es a la vez el gap de validez
más grande y la exposición regulatoria más clara (ver §7, Annex 22).

**NG-4 — El rango reportable de FUNCTIONAL no transfiere al corpus real.**
`[VERIF]` + `[HIPÓTESIS]`
El `defect_corpus` incluye 4 casos `REQUIREMENT_NOT_TESTED` (NT1-4), que puntúan porque en el corpus
sintético **existen** objetos `Test`. En el corpus real `test rows = 0` para todos los documentos. El
detector opera sobre una población donde su precondición no se cumple. Dos salidas posibles y ninguna
buena: o está suprimido por un filtro de confianza (y entonces 4/16 del recall no aplica a producción),
o dispara masivamente (y entonces contribuye a los 90 de NG-2 como falsos). **No cambiar el gate por
esto** — determinar y declarar el rango reportable, como pide la revisión externa (§F, aceptado).

**NG-5 — Familias de aristas vacías — DIAGNOSTICADAS una por una.**
`[DIAG 2026-08-28]`
`verifies`, `contradicts`, `refers_to`, `supports` = 0 en el corpus real. Veredicto por familia
(código en `graph/build.py`):

| Familia | Veredicto |
|---|---|
| `tested_by` | STARVED_FROM_EXTRACTION — linker correcto (L250), sin objetos `Test` (D-1) |
| `verifies` | STARVED_FROM_EXTRACTION — linker correcto (L211), misma raíz (D-1) |
| `contradicts` | CORPUS_LIMITATION — heurística conservadora correcta (L314); 0 pares modal-opuesto cross-doc con solapamiento ≥ 0.55 en el corpus real |
| `refers_to` | **NOT_IMPLEMENTED** en el builder — solo lo describe el docstring L14; ningún `add_edge("refers_to")`; se usa como etiqueta `graph_path` en `technical_findings.py:340`. → deuda separada **D-8**, no se implementa en este hardening |
| `supports` | CORRECT_BY_DESIGN — lo puebla el Adjudicator, no cableado en el camino determinista adoptado |

Consecuencia: `INTERFACE_INCONSISTENCY` (0 en el corpus real técnico) y `CONTRADICTORY_FUNCTIONAL_BEHAVIOR`
(0) **no están ejercitados sobre datos reales** — TP real 0/0, no 2/2. Aceptado de la revisión externa (§B).

**NG-6 — La cobertura de remediación de la corrida real es un artefacto del cap.**
`[BASELINE]`
El reporte §8 registra que las 8 propuestas anclaron todas en RW-0006 por `remediation_limit=8`. No hay
criterio de selección documentado ni orden por riesgo. El paquete entregado representa "los primeros 8
que salieron", no "los 8 más críticos", y el manifest no lo declara. Barato de corregir, y hoy es una
tergiversación silenciosa en un entregable GMP. **Se conserva como deuda pendiente SIN paquete asignado;
se asignará posteriormente a un WP propio. NO es WP-A.**

**NG-7 — El cambio de extracción invalida la premisa del shadow histórico.**
`[BASELINE]` + `[HIPÓTESIS]`
El shadow es `PARCIAL` y se sostiene sobre `same_input_hash` contra una corrida CURRENT persistida.
Si `EXTRACTION_VERSION` cambia (D-1 o D-2), la canonicalización de entrada cambia y **esa premisa deja
de valer para comparaciones futuras**. El shadow actual sigue siendo válido como cierre histórico; deja
de ser reutilizable como referencia de requalification. Debe declararse ahora, no descubrirse después.
Responde a la revisión externa (§P): *suficiente para el cierre histórico, no reutilizable tras un
cambio de extracción.*

**NG-8 — Sin provenance de configuración operativa.**
`[BASELINE]`
`routing.txt` está gitignored y el cutover solo tiene efecto local. Ninguna corrida registra qué motor
y qué configuración estuvieron activos. Reconstruir "qué produjo este paquete" hoy exige confianza, no
evidencia. Se resuelve dentro de D-4 sin tocar gobernanza. Responde a la revisión externa (§Q).

---

## 4. ARQUITECTURA MÍNIMA PROPUESTA

Dos adiciones conceptuales. Nada más. Ambas son aditivas y compatibles con todas las invariantes.

### 4.1 Contrato de adecuación de extracción (frontera de ingesta)

Separar dos estados que hoy son uno solo:

```
EXTRACTION_COMPLETE   — el proceso terminó sin error            (lo que existe hoy)
ANALYZABLE            — el resultado representa el documento    (no existe)
```

`ANALYZABLE` se decide con **señales técnicas de adecuación de extracción**, deterministas y
versionadas, tomadas de lo que YA está en el store: `sections_total`, `toc_anchored`, `n_paginas`,
`claims_per_page`, `tables_total`, `tipo` (rol). **Estas señales NO son requisitos GMP** — `toc_anchored`
y "secciones numeradas detectables" son propiedades de si el **parser recuperó estructura y capa de
texto**, no de si el documento *cumple*. Un documento GMP válido puede carecer de un TOC detectable por
máquina; la señal habla de la **extracción**, no del cumplimiento. Su lectura: estructura nula + densidad
de claims cercana a cero ⇒ el cuerpo no se extrajo, no que el documento esté vacío o sea deficiente.

```
NOT_ANALYZABLE : sections_total == 0  ∧  toc_anchored == false  ∧  claims_per_page < piso_absoluto
                 (piso independiente del rol; un documento que rinde ~1 claim/página y ninguna
                  estructura tuvo su cuerpo no extraído -- criterio empíricamente defendible de por sí)
DEGRADED       : señales parciales por debajo del perfil de extracción esperado -- OBSERVACIONAL
                 (se registra, no decide) mientras el corpus no tenga muestra suficiente por rol
ANALYZABLE     : en otro caso
```

**Los umbrales del artefacto `DRAFT` son HEURÍSTICAS a validar, no requisitos regulatorios.** Se revisan
contra los documentos disponibles y se documenta su base y sus límites; el borde **no se ajusta para
forzar un resultado**. Como *consecuencia observada* (no como definición): RW-0009 (0 secciones,
`toc_anchored=false`, 62 claims) cae `NOT_ANALYZABLE` por el piso absoluto; los otros cinco (8–13
secciones, `toc_anchored=true`, 300–1409 claims) caen `ANALYZABLE`. El resto de señales quedan
`OBSERVACIONALES` hasta que exista corpus para defenderlas (ver `SAMPLE_SIZE_LIMITATIONS`).

**El verdict de adecuación es un artefacto de LIMITACIÓN DEL ANÁLISIS, no un Finding GMP.** No entra en
`all_findings`, no recibe `risk`, no genera `RemediationDirective`, no aparece en `*_findings.json`. Vive
en el paquete de corrida como metadata (`analysis_coverage.json`) y extiende el `COVERAGE_STATEMENT` —
igual que `audit_metadata.json`. Declara, por documento: verdict, señales que lo motivan, y qué clases de
conclusión **no** puede sostener.

Comportamiento (dos modos, flag `observe|enforce`):

- **OBSERVE (WP-B ahora):** clasifica y etiqueta. **0 supresiones, 0 Findings GMP nuevos.** El verdict y
  el `analysis_coverage` se escriben; ningún finding se retira ni cambia de estado.
- **ENFORCE (decisión posterior de Capa 9):** para un documento `NOT_ANALYZABLE`/`DEGRADED`, los findings
  cuya conclusión dependa de una región del corpus que ese documento portaría (ver §4.2,
  `ABSENCE_DEPENDENT`) se **degradan a `MACHINE_INCONCLUSIVE`** con `COVERAGE_LIMITATION` declarada — o se
  suprimen, según lo que Capa 9 firme. Los findings `PRESENCE` nunca se tocan. Dirección estrictamente
  conservadora.

### 4.2 Epistemología del finding: `evidence_basis` + dependencias de cobertura

**(a) `evidence_basis ∈ {PRESENCE, ABSENCE_DEPENDENT, INDETERMINATE}`** — campo aditivo en el `Finding`
(no clase nueva). El binario PRESENCE/ABSENCE no modela bien el código; y "ausencia" no debe confundirse
con "el método no pudo concluir":

| valor | qué sostiene la conclusión | subtipos reales (HEAD) |
|---|---|---|
| `PRESENCE` | solo texto presente y anclado | `INTERFACE_INCONSISTENCY`, `CONTRADICTORY_FUNCTIONAL_BEHAVIOR`, `REGULATORY_COMPLIANT_EVIDENCE` |
| `ABSENCE_DEPENDENT` | un ancla presente **y** un elemento ausente cuya no-existencia solo es afirmable si la región del corpus que lo portaría está completa | `REQUIREMENT_NOT_TESTED`, `IMPLEMENTATION_WITHOUT_REQUIREMENT`, `REQUIREMENT_NOT_TRACED`, `TEST_WITHOUT_REQUIREMENT`, `ORPHAN_DESIGN_ELEMENT`, las 7 de `completeness_findings` cuando nacen `MACHINE_DEVIATION_CANDIDATE` |
| `INDETERMINATE` | el método determinista **no pudo concluir** (capacidad/evidencia insuficiente), no que el documento carezca de algo | `REGULATORY_INCONCLUSIVE` (Tier-1: sin eco léxico, juicio semántico **fuera de alcance** — es limitación de método, no del documento); `completeness_findings` ya degradadas a `MACHINE_INCONCLUSIVE` por `inconclusive_downgraders` |

**No se usa un valor `ABSENCE` puro:** en HEAD ninguna desviación GMP se sostiene solo sobre ausencia
(todas necesitan un positivo presente ⇒ `ABSENCE_DEPENDENT`), y `REGULATORY_INCONCLUSIVE` es
`INDETERMINATE`, no ausencia. Tier-1 además ya declara su `COVERAGE_STATEMENT` a nivel de modalidad.

Función: hacer implementable §4.1 **sin tocar la lógica interna de ningún detector** — la
degradación (enforce) se decide de forma transversal y auditable sobre `evidence_basis` +
`coverage_dependencies` (abajo), no parcheando siete detectores.

**(b) `coverage_dependencies` — metadata por finding en `analysis_coverage.json`** (NO modifica la
taxonomía GMP; NO es un Finding). Base segura para un futuro ENFORCE, que solo tendrá que leer
`would_degrade`:

```
por finding:
  finding_id
  evidence_basis            : PRESENCE | ABSENCE_DEPENDENT | INDETERMINATE
  required_roles            : roles documentales que deben estar ANALYZABLE para sostener la conclusión
                              (p.ej. REQUIREMENT_NOT_TESTED -> ["SAT"|"OQ"|"IQ"|"PQ"])
  required_documents        : ids del corpus actual que cumplen esos roles ([] si ninguno)
  required_capabilities     : capacidades del pipeline necesarias
                              (p.ej. "test_object_extraction", "graph.tested_by_edges")
  coverage_status           : OK | DEGRADED | MISSING   (según adecuación de los required_* y capacidades)
  would_degrade             : bool  -- true si bajo ENFORCE pasaría a MACHINE_INCONCLUSIVE
  reason                    : texto  -- p.ej. "requires SAT role; RW-0009 NOT_ANALYZABLE; 0 test nodes (D-1)"
```

Se calcula determinísticamente del mapa dependencia-por-subtipo + los verdicts de adecuación. `PRESENCE`
⇒ `would_degrade=false` siempre.

### 4.3 Lo que NO se propone

- No se crea capa "Test-to-Clause": las relaciones ya están modeladas, solo no se pueblan `[VERIF]`.
- No se toca `graph/` (linker correcto).
- No se reactiva LLM ni HYBRID.
- No se adopta ningún repositorio, framework ni dependencia externa.
- No se crea segunda UI.
- No se introducen `found_value/expected_value/delta` en el `Finding` general: solo tienen sentido en
  controles cuantificables y serían artificiales en los cualitativos. **Van en la evidencia del
  qualification case (WP-F), no en la taxonomía.** Aceptación parcial de la revisión externa (§J).

---

## 5. PAQUETES DE TRABAJO

Cada uno con evidencia, gate de aceptación, test y rollback. Ninguno modifica fixtures ni reglas
firmadas, routing ni gobernanza.

### WP-A — Fingerprint de corrida (identidad de ejecución ≠ resultado) + attestation de código
**Motiva:** D-4, NG-8. **Riesgo:** BAJO. **Cambio de comportamiento:** ninguno (100% aditivo).

**Se separan tres digests** para no mezclar identidad de ejecución con resultado (decidido tras la
precisión de Capa 9, 2026-08-28):

```
INPUT_CONFIG_FINGERPRINT = sha256( canonical_json({
    schema, entrypoint
    inputs:               [{document_id, sha256}]  ordenado por document_id   # sha256 = canonical Document.sha256 (hash del PDF)
    extraction_version
    canonical_schema_digest : sha256 de las FUENTES que definen el modelo canonico
                              (factory/regulatory/canonical/model.py + persistence.py)  # alcance en _SCHEMA_SOURCES
    graph_schema_digest     : sha256 de factory/regulatory/graph/store.py               # nodos + relaciones tipadas + DDL
    consumed_artifacts:   { nombre: {version, sha256} }   # SOLO los que ESE entrypoint consume
    applied_thresholds:   { ... }                         # SOLO los gates que ESE entrypoint usa
    source_attestation_digest                             # ver SOURCE_ATTESTATION (as-built)
}))

FINDINGS_FINGERPRINT = sha256( canonical_json({schema, count, findings:[...] ordenados por serializacion canonica}) )
    # Alcance DECLARADO: hashea SOLO los findings emitidos -- NO el paquete de corrida.
    # Por finding: finding_class, subtype, severity, document, page, section, source_hash,
    #   anchored_quote (=source_text, evidencia anclada), requirement_id, regulatory_basis, technical_basis,
    #   risk, confidence, machine_state, human_state, rationale, evidence_ids, related_finding_ids,
    #   provenance{agent_id, extraction_version, subcriterion_ref, adjudicator_state, graph_path}
    # EXCLUYE: finding_id, provenance.run_id, timestamps, y el ORDEN de la lista.

RUN_ATTESTATION / EXECUTION_METADATA        # NO es identidad -- es evidencia
    timestamp_utc, wall_clock_seconds, host, pid
    active_engine            = analyzer_router.active_engine()            # OBLIGATORIO (NG-8)
    routing_source           ∈ {env, file, default}                      # OBLIGATORIO (NG-8)
    source_attestation = { entrypoint, module_manifest:[{path, sha256}], module_manifest_sha256,
                           python_version_mm (identidad), python_version, key_deps, git{commit,dirty,describe} }
                         # python_version / key_deps / git SOLO advisory
```

**SOURCE_ATTESTATION (as-built) — NO es "el código ejecutado" literal.** Es un **conjunto estático y
reproducible de fuentes runtime alcanzables desde el entrypoint**: el cierre transitivo de imports
`factory.*` (`Import` / `ImportFrom`, incluidas las lazy imports), calculado por **AST sobre las fuentes
EN DISCO** a partir del módulo del entrypoint (`static_import_closure`). **NO** es el conjunto de módulos
efectivamente cargados en `sys.modules` durante una ejecución, ni una prueba de cobertura de ramas. Cada
archivo del cierre aporta `{ruta relativa al repo, sha256(contenido)}`; `module_manifest_sha256` (digest
agregado y ordenado) + `python_version_mm` forman `source_attestation_digest`, que entra en
`INPUT_CONFIG_FINGERPRINT`. `git_commit`/`git_dirty`/`describe`, `python_version` completo y `key_deps`
son **advisory** y no entran en ningún digest de identidad. Sin repo git ⇒ `commit="UNKNOWN"`,
`dirty=null`, sin excepción. Un tercero recomputa `module_manifest_sha256` desde el `module_manifest`
publicado. Alcance y límite documentados en el docstring de `run_fingerprint.py`.

**Artefactos/config consumidos por entrypoint (as-built — un registro explícito en
`run_fingerprint._CONSUMED_BY_ENTRYPOINT`):**

| Corrida (entrypoint) | consumed_artifacts (as-built) | applied_thresholds |
|---|---|---|
| `v2_runtime` | `technical_completeness_rules.yaml`, `risk_matrix.yaml`, `requirements.yaml`, `decomposition.yaml`, `requirement_terms.yaml`, + `_TIER1_REQUIREMENTS` (hash de la lista literal) | `{}` (no puntúa) |
| `suite_c_formal` | `technical_suite_c.yaml` (SIGNED), `technical_completeness_rules.yaml`, `risk_matrix.yaml`, `requirements.yaml` | `TECHNICAL_RECALL_MIN`, `TECHNICAL_FP_MAX`, `FABRICATED_CITATIONS_MAX` (leídos en vivo de `gates.py`) |
| `real_corpus_technical` | `technical_completeness_rules.yaml`, `risk_matrix.yaml`, `requirements.yaml` | `{}` (no puntúa) |

`technical_suite_c.yaml` **NO** entra en el fingerprint de `v2_runtime` (verificado por test).
`requirements.yaml` entra en los tres porque `build_project_graph` carga el catálogo de requisitos.

- **Persistencia:** los 3 digests → `audit_summary/audit_metadata.json` y `meta.json`; los 2 de identidad
  (`INPUT_CONFIG_FINGERPRINT`, `RESULT_FINGERPRINT`) → también `manifest.json`. Campos aditivos;
  `schema: "v2_analyzer_run"` sin cambio. Se exponen solos vía `get_v2_run` (sin tocar la API).
- **Gate:** dos corridas sobre el mismo input+config+código ⇒ `INPUT_CONFIG_FINGERPRINT` y
  `RESULT_FINGERPRINT` idénticos; cambiar un input (`document_id`+`sha256`), un artefacto consumido, un
  threshold aplicado o el código (`module_manifest_sha256`) cambia el fingerprint que corresponda;
  cambiar reloj/host/pid no cambia ninguno; `RUN_ATTESTATION` siempre trae `active_engine` y `routing_source`;
  cada tipo de corrida incluye SOLO los artefactos que consume.
- **Tests:** determinismo · inmunidad reloj/host/pid · sensibilidad por componente (uno por uno) ·
  estabilidad de `FINDINGS_FINGERPRINT` ante reordenamiento de la lista y ante `provenance.run_id` volátil ·
  scoping de artefactos consumidos (`technical_suite_c.yaml` no afecta a `v2_runtime`) · el
  `source_attestation_digest` refleja el cierre estático de fuentes (no la carga en runtime) ·
  degradación limpia sin git · sin rutas absolutas en la identidad.
- **Rollback:** campos 100% aditivos en manifest/audit/meta y en el dict de `run_suite_c_formal`; borrar
  `run_fingerprint.py` + sus llamadas + el test revierte sin efecto aguas arriba. **Sin cambio de
  `EXTRACTION_VERSION`, sin re-derivación de stores.**
- **Transversal (todo el hardening):** `NEW_REGRESSION_FAILURES = 0` y `EXC-1..EXC-5` no aumentan
  (ni en número ni en identidad).

### WP-B — Contrato de adecuación (`analysis_coverage`) + `evidence_basis` — SOLO modo OBSERVE aquí
**Motiva:** NG-1, D-2 (contención). **Riesgo OBSERVE:** BAJO (no suprime, no crea Findings GMP).

Implementa §4.1 y §4.2 en **modo OBSERVE**. Los umbrales nacen como artefacto
`extraction_adequacy_thresholds.yaml` **`status: DRAFT_UNSIGNED`**, **identificados como HEURÍSTICAS
técnicas de adecuación de extracción a validar — NO requisitos regulatorios** (§4.1). ENFORCE es una
decisión posterior de Capa 9 (firma de heurísticas + regla de degradación).

**`SAMPLE_SIZE_LIMITATIONS`:** el corpus piloto tiene **6 documentos** (~1 URS · 1 FS · ~3 DS · 1 SAT).
No hay muestra suficiente por rol para un estadístico por rol defendible. Por eso:
- Único criterio **decisivo** para `NOT_ANALYZABLE` = el piso **absoluto** e independiente del rol
  (`sections_total==0 ∧ toc_anchored==false ∧ claims_per_page < piso_absoluto`) — defendible de por sí.
- Medianas/bandas por rol y todo lo relativo = **OBSERVACIONAL**: se calcula y se registra en
  `analysis_coverage.json` con su `n` por rol, pero **no decide** el verdict hasta que exista corpus.

**Baseline de comparación (pinned):** corrida fresca de `v2_runtime.run_v2_pipeline` sobre los **6
documentos** `RW-0005, RW-0006, RW-0009, RW-0011, RW-0012, RW-0014` en HEAD `6335588`:
`INPUT_CONFIG_FINGERPRINT = cc130aa5bc669ebf21a1912a8cecb5df9c101ea4534d6afbdb3915c8cfc3b866`,
`FINDINGS_FINGERPRINT = 434f7d42e68fc4e6dd9793a4c513094a711744c52c07a0051b86d69c8ca1e219`,
counts `342 reg / 90 func / 24 tech / 8 remediation`. (La corrida archivada `v2e2e-20260828T035243Z` usó
**5 documentos** —sin RW-0009— y no sirve de baseline para WP-B; ver `REGULATORY_285_342_ROOT_CAUSE`.)

- **Gate OBSERVE:**
  - RW-0009 → `NOT_ANALYZABLE` (por el piso absoluto); RW-0005/0006/0011/0012/0014 → `ANALYZABLE`.
    Consecuencia observada de un criterio técnico, no ajuste ad hoc; señales relativas quedan
    `OBSERVACIONALES` (ver `SAMPLE_SIZE_LIMITATIONS`).
  - **0 supresiones · 0 Findings GMP nuevos · 0 cambio de `risk`/`remediation`/`state`.** Misma
    *población* de findings que el baseline: mismo conjunto de `finding_id`, mismo `count` (342/90/24),
    mismos subtypes, mismos anchors, mismo `machine_state`/`human_state`/`risk`. **El único cambio por
    finding es el campo aditivo `evidence_basis`** → `*_findings.json` **no** es byte-idéntico (gana una
    clave); `FINDINGS_FINGERPRINT` **cambia** (campo semántico nuevo); `INPUT_CONFIG_FINGERPRINT` de
    `v2_runtime`/`real_corpus` **cambia** (nuevo artefacto consumido). Esperado y declarado — no es regresión.
  - Todo finding emitido lleva `evidence_basis ∈ {PRESENCE, ABSENCE_DEPENDENT, INDETERMINATE}` coherente
    con el mapa por subtipo (§4.2 a).
  - `analysis_coverage.json` presente en el paquete (metadata, NO Finding): (i) verdict de adecuación por
    documento + señales + `n` por rol de las señales observacionales; (ii) `COVERAGE_STATEMENT` extendido;
    (iii) `coverage_dependencies` por finding (§4.2 b) con `would_degrade` — informativo, 0 efecto.
- **Tests:** clasificación por documento contra los 6 (piso absoluto decide; relativo no); `evidence_basis`
  correcto por subtipo, `REGULATORY_INCONCLUSIVE` → `INDETERMINATE`; `analysis_coverage` NO entra en
  `all_findings` ni en `risk`/`remediation`/`state`; `coverage_dependencies.would_degrade` calculado y
  determinista; fail-closed **solo** en la ruta de gate ENFORCE si el artefacto no está firmado (OBSERVE
  corre con `thresholds_signed=false` registrado); determinismo WP-A (2 corridas → fingerprints idénticos).
- **Rollback:** flag `observe|enforce` (default `observe`); borrar `extraction_adequacy.py` +
  `extraction_adequacy_thresholds.yaml` + el campo `evidence_basis` + las llamadas revierte sin efecto.
  Sin cambio de `EXTRACTION_VERSION`, sin re-derivación de stores.

### WP-C — Benchmark de extracción (⚠ sin código de producción)
**Motiva:** D-2. **Riesgo:** BAJO (aislado). **Precondición:** WP-A cerrado.

Comparar el extractor actual contra Docling (MIT) y, si se quiere una tercera vía, Tesseract, **solo
sobre RW-0009**, en entorno aislado. Métricas y criterio de decisión **firmados antes de correr**:

```
páginas con texto recuperado · secciones nivel-1 vs TOC impreso · tablas reconstruidas
identificadores de test recuperados (SAT-/OQ-/IQ-) · reading order (muestra manual)
provenance (página + bbox) · claims que representan el cuerpo de pruebas (revisión humana de muestra)
```

- **Gate:** solo se adopta un extractor nuevo si recupera el cuerpo de pruebas verificado a mano **y**
  no regresa la extracción de los 5 documentos que hoy funcionan.
- **Restricciones duras:** descarga de modelos = decisión de Capa 9; ejecución bajo `network_locked()`;
  fetch remoto por defecto de Docling desactivado y ruta local forzada; licencias de modelos
  verificadas por separado de la licencia MIT del código. **PyMuPDF/pymupdf4llm excluido** (AGPL) salvo
  decisión específica.
- **Rollback:** no aplica — no toca producción.

### WP-D — Extracción de `Test` + linker requisito↔test
**Motiva:** D-1. **Riesgo:** MEDIO-ALTO. **Precondición:** WP-C decidido (⛔).

Etapa determinista adicional en `extract_document.py` que produzca objetos `Test` vía `build_test()`,
más linker bidireccional (el SAT cita el requisito, y no solo al revés). **Aditiva**, no rediseño.

Razón del orden: construir extracción de `Test` contra un SAT que no se puede leer no produce nada
medible. Si WP-C concluye que RW-0009 sigue siendo ilegible, WP-D se diseña igual pero se valida contra
otro protocolo legible, y se declara sin evidencia sobre este corpus.

- **Gate:** `tested_by > 0` con **muestra verificada a mano**, no por conteo; 0 regresión en
  `implemented_by`/`designed_by`; ningún `REQUIREMENT_NOT_TESTED` nuevo sin arista trazable.
- **Tests:** extracción de `Test` sobre fixture; linker en ambos sentidos; anti-falso-positivo del
  matcher laxo.
- **Rollback:** etapa desactivable por flag; `EXTRACTION_VERSION` nueva ⇒ los stores anteriores se
  conservan, no se sobrescriben.
- **Consecuencia obligatoria:** cambia `EXTRACTION_VERSION` ⇒ re-derivación de `canonical_store` y
  `graph_store` ⇒ **toda medición anclada a ellos queda invalidada** ⇒ NG-7 se materializa. Debe ir
  acompañado de decisión de versión de Capa 9 y de re-medición, no ejecutarse de forma incremental.

### WP-E — Independencia de medición y medición sobre corpus real
**Motiva:** D-3, NG-2, NG-3, NG-4, NG-5. **Riesgo:** BAJO. **Es el paquete que más defendibilidad aporta.**

Cuatro piezas — **detalle y estado en `docs_plan/WP_E_INDEPENDENCIA_MEDICION_20260828.md`**:
1. **Diagnóstico previo (sin código) — EJECUTADO 2026-08-28.** NG-2 / NG-2b reconciliadas; NG-5
   diagnosticada por familia. Resultados en NG-2 / NG-2b / NG-5.
2. **Separación física** builder / runner + anchors ≠ frase literal — **entregado en el instrumento
   NUEVO** (`held_out_corpus.build_seed_corpus` separado del runner; match ESTRUCTURAL
   `[finding_class, subtype, document, page_band]`). `technical_suite_c` **NO se retrofitea ni se
   re-puntúa** (su resultado firmado queda con D-3 documentado como limitación conocida).
3. **Corpus held-out** — `held_out_technical_corpus.yaml` (`DRAFT_UNSIGNED`) +
   `held_out_corpus.py`. Independiente por construcción: `assert_usable_as_gate()` fail-closed exige
   `SIGNED` **y** `author ∉ {"Capa 9 (Cesar)"}` (autor de las reglas). Procedencia `REG/DOM/ADV`
   validada en el loader; umbrales ex-ante. **Semilla sintética placeholder** — la pueblan/firman un
   autor independiente + Capa 9.
4. **Muestra adjudicada del corpus real** — `real_corpus_adjudication.py` + `.yaml` (`DRAFT_UNSIGNED`).
   `sample_for_adjudication()` = muestra determinista, estratificada, prioriza `would_degrade`.
   Etiquetado **humano** (QA, no la máquina); `COVERAGE_LIMITED` excluido del cálculo. Sin etiquetas →
   `REPORTABLE_RANGE = UNKNOWN`. **Muestra de 40 casos generada hoy, PENDIENTE de adjudicación QA.**

- **Gate — `metric_envelope.py`:** `require_envelope()` es fail-closed sobre los 5 campos
  (`suite_version + size + definition + reportable_range + contamination_statement`).
  `reportable_range` ∈ `[lo,hi]` o `{UNKNOWN, INDICATIVE_ONLY, NOT_A_GATE, SYNTHETIC_ONLY}`.
  **Consecuencia:** `TECHNICAL_GATE` y `FUNCTIONAL_GATE` actuales quedan con
  `reportable_range = SYNTHETIC_ONLY` hasta que el held-out firmado (3) y la muestra adjudicada (4)
  den el rango real.
- **Restricción:** los fixtures ya firmados **no se tocan ni se re-puntúan retrospectivamente**. El
  corpus held-out es adicional, no sustituto.
- **Rollback:** aditivo (4 módulos + 2 yaml `DRAFT` + 1 test); las suites actuales corren igual. Sin
  cambio de `EXTRACTION_VERSION`.

### WP-F — Contrato de cualificación — ENTREGADO (código; contrato `DRAFT`)
**Motiva:** D-5. **Precondición:** WP-A + WP-E cerrados ✅. **Detalle:** `docs_plan/WP_F_CONTRATO_CUALIFICACION_20260828.md`.

Entregado: `requirement_catalog/qualification_contract.yaml` (`status: DRAFT`) +
`validation_v2/qualification_contract.py` (checker `run_contract()`). 10 casos, todos leyendo el
umbral de su **fuente autorizada citada** (`gates.py` consts / `zero`+authority / `assertion`+authority);
`found/expected/delta` por caso; `metric_envelope` (WP-E) obligatorio por métrica. Checker re-ejecuta
las suites, reproduce el fingerprint (WP-A) y compara los SHA de los disparadores de requalification.
`decide_overall()` puro: solo `DRAFT_BASELINE` / `GATES_MET_AS_QUALIFIED` / `FAIL_REQUALIFICATION_REQUIRED`
— **nunca `QUALIFIED` ni `COMPLIANT`** (el sistema no se auto-cualifica; eso lo firma un humano).
Baseline en DRAFT: 10/10 casos PASS, `overall = DRAFT_BASELINE`, fingerprint capturado.
Pendiente de humano: firma de `qualified_version` + congelado de SHAs/fingerprints + `reviewer` por caso.

Artefacto declarativo (YAML) + checker re-ejecutable que ligue, por requisito:
`Intended Use → Requirement → Test Objective → Acceptance Criterion → fuente autorizada del valor
esperado → Test artifact → Actual Result → Evidence (ruta + SHA) → Reviewer → Status`.

Debe además responder: qué versión está cualificada, contra qué dataset, con qué reglas, bajo qué
excepciones, y **qué cambio obliga a requalification** — con lista explícita de disparadores:
extractor, assets OCR, esquema canónico, linker/esquema de grafo, reglas, decomposition, fixture,
matriz de riesgo, thresholds, routing.

Reglas duras: ningún valor esperado se escribe como literal en el test (se lee de fuente autorizada y
se cita); todo nace `DRAFT`; **el sistema nunca se auto-cualifica**; el contrato no declara cumplimiento,
solo estado de gates y contingencias. Se apoya en el fingerprint de WP-A — sin él, el contrato podría
mentir. Aquí es donde entra `found_value/expected_value/delta`, en la evidencia del caso, no en la
taxonomía.

- **Gate:** el checker re-ejecuta y reproduce el fingerprint declarado; si no coincide, `FAIL`.
- **Rollback:** artefacto y checker son independientes del runtime; se pueden retirar sin efecto.

### WP-G — Panel V2 en Mission Control — ENTREGADO
**Motiva:** D-6. **Detalle:** `docs_plan/WP_G_PANEL_V2_MISSION_CONTROL_20260828.md`.

Entregado: `factory/ui/js/mission_control/v2_analyzer_view.js` (`refreshV2Analyzer()` + `openV2Run()`),
cableado en la UI existente (nav `data-v="v2analyzer"` + `<section id="v-v2analyzer">` + `main.js` +
`refresh.js`). **Sin backend nuevo** — consume los 6 endpoints GET ya publicados. **0 llamadas de
escritura** (verificado por test). Muestra explícitamente: fingerprint de la corrida (WP-A), adecuación
por documento (WP-B `adequacy_verdicts`), `evidence_basis` por finding (WP-B), y las marcas
`MACHINE GENERATED` / `NOT_QA_APPROVED`. Banner «solo lectura». `MISSION_CONTROL_V2 = API_VISIBLE=YES ·
UI_VISIBLE=YES` — D-6 cerrado. 6 tests. Regresión: 2891 passed / 5 EXC / exit 1 (NEW_REGRESSION_FAILURES = 0).

Módulo JS adicional en la UI existente que consuma los 6 endpoints ya publicados. Read-only estricto:
el front **no** replica adjudicación, riesgo, gobernanza ni cambio de estado. Debe mostrar
explícitamente `evidence_basis`, el estado de adecuación por documento y el fingerprint de la corrida —
si no, la UI reintroduce visualmente la confusión que WP-B elimina.

- **Gate:** 0 llamadas de escritura; ningún estado GMP mutable desde el front.
- **Rollback:** eliminar el módulo y la entrada de menú.

---

## 6. ORDEN DE IMPLEMENTACIÓN Y POR QUÉ REDUCE RIESGO

```
WP-A  fingerprint            →  primero: sin él no se puede DEMOSTRAR el efecto de ningún cambio posterior
WP-B  adecuación (observe)   →  contiene el fallo de soundness sin cambiar salida todavía
WP-E.1 diagnóstico (NG-2/5)  →  reconcilia 0-vs-90 y las aristas vacías antes de medir nada
WP-B  adecuación (enforce)   →  activar supresión una vez firmados los umbrales
WP-C  benchmark extracción   →  datos para decidir OCR; sin código de producción
WP-D  extracción de Test     →  único paquete que invalida mediciones; va cuando ya hay con qué medir
WP-E.2-4 independencia       →  corpus held-out + muestra real adjudicada sobre la extracción ya estable
WP-F  contrato cualificación →  último: se cualifica lo que dejó de moverse
WP-G  UI                     →  en paralelo, cuando convenga
```

La lógica es una sola: **medir antes de cambiar, contener antes de mejorar, y dejar el cambio que
invalida mediciones para cuando exista instrumentación que lo mida.** Hacer WP-D primero — la opción
intuitiva, porque `tested_by = 0` es la deuda más visible — obligaría a re-derivar stores y re-medir
gates sin fingerprint, sin corpus held-out y sin haber reconciliado NG-2. Sería el orden de máximo
riesgo.

Riesgo de versionado a decidir explícitamente: WP-B y WP-D tocan la capa de extracción. Si se ejecutan
como cambios separados, hay **dos** re-derivaciones y **dos** requalifications. Recomiendo agrupar
cualquier cambio que altere `EXTRACTION_VERSION` en un solo salto de versión gobernado.

---

## 7. LO QUE PERTENECE SOLO A GOBERNANZA

No son bugs y no se tocan desde el código:

- `PRODUCTION_ENABLEMENT = NOT_DECLARED`, `REGULATORY_COMPLIANCE = NOT_DETERMINED_BY_SYSTEM`,
  `CORPUS_READY = NO`. Decisiones separadas de Capa 9 / QA.
- Firma de los umbrales de adecuación (WP-B) y del corpus held-out (WP-E).
- Decisión de descarga de modelos OCR (WP-C) y decisión de `EXTRACTION_VERSION` (WP-D).
- Re-verificación de EXC-1..EXC-5 en el entorno de origen; la aceptación actual es específica del clon.
- Propagación del cutover a otros entornos (`routing.txt` gitignored).
- **Justificación documentada de datos sintéticos.** El borrador de EU GMP Annex 22 —consulta cerrada
  el 7-oct-2025, **sin texto final adoptado**, finalización esperada en 2026— advierte contra probar
  modelos con datos generados artificialmente sin justificación, y exige datos de prueba independientes.
  Los dos instrumentos de gate del V2 son sintéticos (NG-3). Esto se resuelve con un registro de
  justificación, no con código. Trátalo como dirección regulatoria emergente: **no sirve para convertir
  `REGULATORY_LLM_GATE = FAIL` en PASS, ni para declarar cumplimiento.** Verifica su estado antes de
  citarlo en cualquier entregable.

---

## 8. FUERA DE ALCANCE / INVESTIGACIÓN FUTURA

- **D-7 · semántica regulatoria.** Micro-aserciones, vocabulario semántico gobernado, calibración
  contrastiva, Suite S. Ninguna está demostrada como solución; son propuestas arquitectónicas derivadas,
  no capacidades respaldadas por los repositorios de referencia. Proyecto separado, con su propio
  benchmark y modo shadow. No se reactiva LLM ni HYBRID aquí.
- **Change control ampliado** (change request → impact → … → closure, patrón AlcoaBase): propio de
  Factory/Governance. El único mínimo que este hardening necesita es la lista de disparadores de
  requalification, que ya va dentro de WP-F.
- **Prueba dual-runtime fresca de shadow:** clasificada, no asumida como deuda. El shadow actual cierra
  el histórico; una prueba fresca solo será necesaria si Capa 9 requiere requalification comparativa
  tras un cambio de extracción (NG-7), y costaría 158 llamadas LLM bajo PILOT_EXECUTION.
- **Adopción de stacks externos** (ALC, paraqualis como runtime): sobre-ingeniería, rechazado.

---

## 9. NO TOCAR

`graph/{store,build,queries}.py` · `findings/{taxonomy,risk,functional_findings,technical_findings,
remediation_v2}.py` lógica interna de detección · `regulatory_tier1.py` · `validation_v2/{cutover,
analyzer_router,local_only}.py` · `technical_completeness_rules.yaml` v1.1 · `technical_suite_c.yaml` ·
`decomposition.yaml` v1.1 · `risk_matrix.yaml` v1.0 · `routing.txt` · `decisions_v2.jsonl` ·
`routing_history.jsonl` · motor CURRENT completo · los 18 archivos de drift preexistente.

Excepción única y acotada: `taxonomy.py` recibe el campo aditivo `evidence_basis` (WP-B) y
`extract_document.py` recibe etapas aditivas (WP-B, WP-D). Ninguna modifica lógica existente.

---

## 10. RESPUESTA A LA REVISIÓN TÉCNICA EXTERNA

```
EXTERNAL_REVIEW_ACCEPTED            = A (no duplicar TechnicalCheckResult) · B (diagnosticar cada familia
                                      de aristas vacías → NG-5) · C (separar document understanding /
                                      test normalization / traceability → WP-C vs WP-D) · D (extraction
                                      health contract → elevado a NG-1/WP-B, núcleo del diseño) ·
                                      E (Docling solo benchmark) · F (rango reportable funcional → NG-4) ·
                                      G (held-out + procedencia + thresholds ex-ante → WP-E) ·
                                      I (frontera fingerprint lógico vs metadata → WP-A) ·
                                      L/M/N (FUTURE_RESEARCH) · O (UI sin lógica GMP) · Q (provenance de
                                      configuración → NG-8) · T (estados de gobernanza no son bugs)
EXTERNAL_REVIEW_PARTIALLY_ACCEPTED  = H (qualification case: aceptado, pero condicionado a WP-A/WP-E —
                                      un contrato construido antes del fingerprint puede mentir) ·
                                      J (found/expected/delta: sí, pero en la evidencia del qualification
                                      case, NO en el Finding general — artificial en findings cualitativos) ·
                                      K (Test-to-Clause: aceptado como intención, rechazado como capa nueva —
                                      las relaciones ya están modeladas, solo inanidas) ·
                                      P (shadow: clasificado como suficiente para cierre histórico, pero
                                      NO reutilizable tras cambio de extracción → NG-7) ·
                                      S (Annex 22: usado solo para justificación documental y cualificación,
                                      nunca para reinterpretar gates)
EXTERNAL_REVIEW_REJECTED            = R (change control ampliado en este hardening — es Factory/Governance;
                                      solo se retiene la lista de disparadores de requalification)
DESIGN_CHANGES_CAUSED_BY_REVIEW     = §D elevó "extraction health" de métrica a contrato fail-closed y
                                      lo convirtió en el núcleo arquitectónico (WP-B) en lugar de un
                                      apéndice de la deuda de OCR.
```

---

## CIERRE

```
SKILLS_USED = NINGUNA. Revisadas todas las disponibles: acero-estructural-pr / ares / whatsapp-crm son
  de otros dominios; docx / pptx / xlsx / pdf no aplican (entregables Markdown); frontend-design solo
  sería relevante al construir WP-G, que en esta fase es design-only; skill-creator, import-memory,
  morning, product-self-knowledge, file-reading / pdf-reading sin valor para este análisis.

MATERIAL_GAPS_CONFIRMED =
  D-1 sin extracción de objetos Test (build_test con 0 llamadores de producción; test rows = 0 en 6 docs)
  D-2 SAT sin capa de texto y pipeline sin OCR (RW-0009: 62 claims, 0 sections, toc_anchored=false)
  D-3 builder de corpus acoplado al runner; anchors == frases del builder
  D-4 sin fingerprint determinista (run_id y manifest son wall-clock)
  D-5 sin contrato de cualificación máquina-legible
  D-6 UI no consume /api/v1/v2-analyzer/* (0 referencias en 23 módulos JS)
  D-8 refers_to no poblado por el builder del grafo (deuda separada; NO se implementa en este hardening;
      sin paquete asignado) [DIAG 2026-08-28]
  Corrección de atribución mantenida: D-1 NO es deuda del grafo; el linker está correcto y solo inanido.

NEW_GAPS_FOUND =
  NG-1 la ausencia no tiene precondición de adecuación → fail-closed roto en la frontera de ingesta.
       [DIAG 2026-08-28] 0 findings anclados en RW-0009 (285/90/24). Contaminación CONFIRMADA = 70
       REQUIREMENT_NOT_TESTED funcionales (artefacto de tested_by=0 sobre los 5 docs legibles).
       Los 24 technical NO se generalizan como inválidos (requieren adjudicación, NG-3).
  NG-2 RECONCILIADA [DIAG 2026-08-28]: desincronización de versión, no defecto. Línea base funcional
       real sobre corpus = 90 (70 artefacto de D-1 + 20). El "0 findings / 0 FP" del reporte maestro §E
       queda obsoleto.
  NG-3 ningún gate está medido sobre datos reales (real_corpus_technical no puntúa; no hay equivalente
       funcional) → los PASS provienen solo de corpus sintético del mismo autor que las reglas
  NG-4 el rango reportable de FUNCTIONAL no transfiere: 4/16 casos dependen de Test objects inexistentes
       en el corpus real (confirmado: 70 REQUIREMENT_NOT_TESTED sobre corpus real, todos artefacto de D-1)
  NG-5 DIAGNOSTICADAS [DIAG 2026-08-28]: tested_by / verifies = STARVED_FROM_EXTRACTION (D-1);
       contradicts = CORPUS_LIMITATION; refers_to = NOT_IMPLEMENTED (→ D-8); supports = CORRECT_BY_DESIGN.
       INTERFACE_INCONSISTENCY y CONTRADICTORY_FUNCTIONAL_BEHAVIOR no ejercitados sobre datos reales (TP 0/0).
  NG-6 la cobertura de remediación real es artefacto de remediation_limit=8, sin criterio de selección
       declarado en el manifest. DEUDA PENDIENTE sin paquete asignado; se asignará a un WP posterior.
  NG-7 un cambio de EXTRACTION_VERSION invalida la premisa same_input_hash del shadow para comparaciones
       futuras
  NG-8 sin provenance de configuración operativa (motor activo / origen del routing) en las corridas

REDESIGN_V3_REQUIRED = NO
  Ninguna deuda ni gap invalida la arquitectura V2. Todo se resuelve de forma aditiva. NG-1 es grave en
  soundness, no en arquitectura: es una precondición que falta, no un diseño equivocado.

HARDENING_RECOMMENDED =
  WP-A fingerprint + provenance de configuración
  WP-B contrato de adecuación (analysis_coverage, artefacto de LIMITACIÓN, no Finding) +
       evidence_basis {PRESENCE, ABSENCE_DEPENDENT, INDETERMINATE} + coverage_dependencies por finding -- SOLO OBSERVE
  WP-C benchmark de extracción (sin código de producción)
  WP-D extracción de Test + linker bidireccional
  WP-E independencia de medición + medición adjudicada sobre corpus real
  WP-F contrato de cualificación
  WP-G panel V2 read-only en Mission Control

BENCHMARKS_REQUIRED_BEFORE_IMPLEMENTATION =
  1. Diagnóstico NG-2 (reconciliar 0 vs 90) y NG-5 (veredicto por familia de aristas) — sin código.
  2. Alcance de NG-1: cuántos findings de la corrida real dependen de RW-0009 o de su ausencia.
  3. WP-C: Docling / Tesseract vs extractor actual sobre RW-0009, métricas firmadas antes de correr,
     bajo network_locked, con decisión de Capa 9 para cualquier descarga. PyMuPDF excluido (AGPL).
  Ninguno modifica producción.

GOVERNANCE_ONLY_ITEMS =
  PRODUCTION_ENABLEMENT · REGULATORY_COMPLIANCE · CORPUS_READY (D4) · firma de las HEURÍSTICAS de adecuación (no requisitos) + regla de degradación ENFORCE ·
  firma del corpus held-out · autorización de descarga de modelos OCR · decisión de EXTRACTION_VERSION ·
  re-verificación de EXC-1..EXC-5 en origen · propagación del cutover · justificación documentada de
  datos sintéticos (dirección Annex 22, borrador no adoptado)

FUTURE_RESEARCH =
  Semántica regulatoria (micro-aserciones, vocabulario gobernado, calibración contrastiva, Suite S) como
  proyecto separado con benchmark propio y modo shadow · change control ampliado en Factory/Governance ·
  prueba dual-runtime fresca de shadow si Capa 9 requiere requalification comparativa.
  REGULATORY_LLM_GATE = FAIL se mantiene, no se reinterpreta. No se reactiva LLM ni HYBRID.

RECOMMENDED_IMPLEMENTATION_ORDER =
  WP-A → WP-B(observe) → WP-E.1 diagnóstico → WP-B(enforce) → WP-C → WP-D → WP-E.2-4 → WP-F
  (WP-G en paralelo). Principio: medir antes de cambiar; contener antes de mejorar; dejar el cambio que
  invalida mediciones para cuando exista con qué medirlo.

FIRST_IMPLEMENTATION_PACKAGE = WP-A — INPUT_CONFIG_FINGERPRINT + RESULT_FINGERPRINT + RUN_ATTESTATION
  Cero cambio de comportamiento, riesgo bajo, puramente aditivo. Identidad de ejecución SEPARADA del
  resultado. `SOURCE_ATTESTATION` = conjunto estático y reproducible de fuentes runtime alcanzables desde
  el entrypoint (cierre transitivo de imports `factory.*` por AST sobre las fuentes en disco), NO el
  conjunto de módulos cargados en ejecución ni prueba de que ese código corriera. `git commit/dirty` es
  advisory, no identidad. Solo incluye los artefactos/config realmente consumidos por cada entrypoint.
  Inputs = document_id + sha256. Es la precondición para demostrar el efecto de los paquetes siguientes.
  Transversal de toda implementación: NEW_REGRESSION_FAILURES = 0 · EXC-1..EXC-5 no aumentan.

READY_FOR_LAYER9_DECISION = YES
  Los tres diagnósticos read-only previos están EJECUTADOS y aceptados (2026-08-28); resultados en
  NG-1 / NG-2 / NG-5. No cambian el enfoque ni el orden. Salvedad que se mantiene: WP-B depende del
  refinamiento de alcance de NG-1 (degradar findings con coverage_dependencies.would_degrade == true (evidence_basis ∈
  {ABSENCE_DEPENDENT, INDETERMINATE}) cuya región dependa de un doc NOT_ANALYZABLE/DEGRADED, NO "todos los
  findings del documento NOT_ANALYZABLE") y WP-D depende del resultado de WP-C.
```

---

*DESIGN ONLY. Sin implementación, instalación, descargas, cambios de fixtures/reglas firmados,
routing, gobernanza, commit ni push.*
