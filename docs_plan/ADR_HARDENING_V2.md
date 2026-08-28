# ADR — HARDENING DEL ANALIZADOR DOCUMENTAL GMP LOCAL V2

**ADR-V2-HARD-001** · 2026-08-28 · Estado: **PROPUESTO** (pendiente de decisión de Capa 9)
**Baseline de código:** `fix/clon-local-validacion` @ `c4e8296`
**Documento hermano:** `docs_plan/PLAN_HARDENING_ANALIZADOR_GMP_LOCAL_V2.md`

---

## CONTEXT

El Analizador GMP V2 está en producción local (`routing = v2`, `active_engine = V2`,
`regulatory_modality = REGULATORY_TIER1_PALANCA_C`), con cutover controlado ejecutado y CURRENT
retenido como rollback. Los gates declarados son `FUNCTIONAL = PASS (16/16, FP 0)`,
`TECHNICAL = PASS (recall 0.90, FP 0)` y `REGULATORY_LLM = FAIL (recall 0/7)`, este último mitigado
—no resuelto— por Tier-1 determinista con revisión humana.

La verificación del código real en HEAD localizó seis deudas y, sobre todo, corrigió la atribución de
la más visible: `tested_by = 0` **no** es un defecto del grafo. El linker (`_link_to_tests`, `verifies`)
está correctamente implementado y solo carece de datos. La causa está en extracción, con dos sub-fallos
independientes: `extract_document.py` no tiene etapa de extracción de objetos `Test` (`build_test()`
con cero llamadores de producción, `test rows = 0` en los seis documentos), y el PDF del SAT (RW-0009)
no tiene capa de texto en su cuerpo, con un pipeline que carece de OCR. El diagnóstico read-only del
2026-08-28 registró además que `refers_to` no lo puebla el builder del grafo (lo describe el docstring,
pero no hay `add_edge`) — deuda separada (**D-8**), fuera del alcance de este hardening.

El análisis de este ADR añade un hallazgo que reencuadra la prioridad. RW-0009 fue procesado sin error,
produjo 62 claims de portada/carta/encuesta, 0 secciones y `toc_anchored = false`, y **el pipeline
continuó**. No existe estado, gate ni precondición que distinga *"el documento dice que no"* de
*"el documento no se pudo leer"*. El diagnóstico del 2026-08-28 sobre `v2e2e-20260828T035243Z` precisó
la manifestación: **0 findings anclados en RW-0009** en las tres clases; la contaminación **confirmada**
son los **70 `REQUIREMENT_NOT_TESTED`** funcionales (de 90), artefacto de `tested_by = 0` (D-1) sobre
los cinco documentos legibles. Los 24 findings técnicos **no se generalizan como inválidos**: requieren
adjudicación (NG-3) pero no son contaminación confirmada.

Esto contradice la invariante `fail-closed` que el sistema declara, y reproduce el problema que originó
el rediseño V2: *un analizador que no encuentra evidencia presente produce NCRs falsos.*

Se añade un problema de validez de la medición: `real_corpus_technical.py` corre sobre el corpus real
pero **no puntúa**, y no existe equivalente funcional. Todos los gates aprobados provienen de corpus
sintético construido por el mismo autor de las reglas. La contradicción del reporte maestro (§E
*"0 findings emitidos"* vs §I `functional_findings.json (90)`) quedó **reconciliada** por el diagnóstico
del 2026-08-28: es desincronización de versión — el "0" contó 3 subtipos el 2026-08-27, el "90" es la
E2E posterior con `REQUIREMENT_NOT_TESTED` (70) + `IMPLEMENTATION_WITHOUT_REQUIREMENT` (20) ya activos.
Línea base funcional real sobre corpus = **90 (70 artefacto de D-1 + 20)**; el "0 / 0 FP" de §E queda obsoleto.

---

## DECISION

**No se rediseña V2.** Se aplica hardening aditivo en siete paquetes, con dos adiciones conceptuales:

1. **Contrato de adecuación de extracción en la frontera de ingesta.** Se separan
   `EXTRACTION_COMPLETE` (el proceso terminó) de `ANALYZABLE` (el resultado representa al documento),
   con **señales TÉCNICAS de adecuación de extracción** (deterministas, versionadas): `sections_total`,
   `toc_anchored`, `claims_per_page`, `tables_total`, `n_paginas`, `tipo`. **Estas señales NO son
   requisitos GMP** — miden si el parser recuperó estructura y capa de texto, no si el documento cumple.
   Los umbrales del artefacto `DRAFT` son **HEURÍSTICAS a validar, no requisitos regulatorios**. Único
   criterio **decisivo** de `NOT_ANALYZABLE` = un **piso absoluto independiente del rol**
   (`sections_total==0 ∧ toc_anchored==false ∧ claims_per_page < piso`); medianas/bandas por rol son
   **OBSERVACIONALES** mientras el corpus (6 docs, ~1 por rol) no dé muestra suficiente. El verdict es un
   **artefacto de LIMITACIÓN DEL ANÁLISIS** (`analysis_coverage.json`, metadata): **no es un Finding
   GMP**, no entra en `all_findings`, no recibe `risk`, no genera `RemediationDirective`, no aparece en
   `*_findings.json`. Extiende el `COVERAGE_STATEMENT`. En **OBSERVE** solo etiqueta; en **ENFORCE**
   (decisión posterior) degrada a `MACHINE_INCONCLUSIVE` con `COVERAGE_LIMITATION` los findings cuya
   conclusión dependa de una región portada por un documento no adecuado. Los findings de presencia
   nunca se tocan.

2. **Atributo `evidence_basis ∈ {PRESENCE, ABSENCE_DEPENDENT, INDETERMINATE}` + metadata
   `coverage_dependencies` por finding.** `evidence_basis`: `PRESENCE` (conclusión sobre texto presente),
   `ABSENCE_DEPENDENT` (ancla presente **y** elemento ausente afirmable solo si la región del corpus está
   completa — **todas las desviaciones GMP por ausencia en HEAD**), `INDETERMINATE` (el método
   determinista no pudo concluir: `REGULATORY_INCONCLUSIVE` —juicio semántico fuera de alcance, limitación
   de método, no del documento— y completeness ya degradadas por `inconclusive_downgraders`). **No hay
   valor `ABSENCE` puro.** `coverage_dependencies` (en `analysis_coverage.json`, **no** en la taxonomía
   GMP): `{finding_id, evidence_basis, required_roles, required_documents, required_capabilities,
   coverage_status, would_degrade, reason}` — base segura para un futuro ENFORCE, que solo leerá
   `would_degrade`. Campo aditivo, sin tocar la lógica interna de ningún detector.

Paquetes y orden: `WP-A` (INPUT_CONFIG_FINGERPRINT + FINDINGS_FINGERPRINT + RUN_ATTESTATION, con
SOURCE_ATTESTATION = conjunto estático y reproducible de fuentes runtime alcanzables desde el entrypoint
—cierre estático de imports `factory.*` por AST, no los módulos cargados en ejecución— y solo los
artefactos que cada tipo de corrida consume) → `WP-B` adecuación en modo observación → [diagnóstico de contradicciones y
familias de aristas vacías: EJECUTADO 2026-08-28] → `WP-B` en modo enforce → `WP-C` benchmark de
extracción sin código de producción → `WP-D` extracción de `Test` y linker bidireccional → `WP-E`
independencia de medición y muestra adjudicada del corpus real → `WP-F` contrato de cualificación.
`WP-G` (panel UI read-only) en paralelo.

El principio de ordenación es: **medir antes de cambiar, contener antes de mejorar, y posponer el
cambio que invalida mediciones hasta que exista instrumentación que lo mida.**

---

## ALTERNATIVES CONSIDERED

**A1 — Atacar `tested_by = 0` primero (extracción de `Test` + OCR).**
Es la deuda más visible y la de mayor valor GMP aparente. Rechazada como *primer* paquete, no como
paquete: cambia `EXTRACTION_VERSION`, obliga a re-derivar `canonical_store` y `graph_store`, invalida
toda medición anclada a ellos, y se ejecutaría sin fingerprint, sin corpus held-out y sin haber
reconciliado la contradicción 0-vs-90. Es el orden de máximo riesgo. Se conserva como `WP-D`.

**A2 — Adoptar Docling directamente como extractor.**
Rechazada. Docling ataca solo el sub-fallo del documento; aunque el SAT se leyera perfectamente,
`tested_by` seguiría en 0 porque no existe etapa de extracción de `Test`. Además implica descarga de
modelos (decisión de Capa 9), licencias de modelos distintas de la licencia MIT del código, y fetch
remoto por defecto que habría que desactivar. Se conserva como benchmark (`WP-C`), no como adopción.

**A3 — Usar PyMuPDF / pymupdf4llm.**
Rechazada para producción. AGPL-3.0 o licencia comercial de Artifex; el HANDOFF prohíbe copyleft fuerte
en producción sin decisión específica. Admisible únicamente como comparador aislado si Capa 9 lo
autoriza expresamente.

**A4 — Crear `TechnicalCheckResult` u otra abstracción de resultado.**
Rechazada por duplicación. `Finding` + `machine_state` + `evidence` + `provenance` + reglas
deterministas + risk ya cubren ese contrato en HEAD.

**A5 — Crear una capa "Test-to-Clause".**
Rechazada. Las relaciones `verifies` / `tested_by` / `regulated_by` ya están modeladas en el grafo. El
problema es de población, no de modelado. Construir una capa nueva sobre un linker correcto sería
reabrir un componente sano.

**A6 — Introducir `found_value / expected_value / delta` en el `Finding` general.**
Rechazada en esa ubicación. Es excelente para controles cuantificables y artificial para hallazgos
cualitativos. Se acepta dentro de la evidencia del qualification case (`WP-F`).

**A7 — Reactivar juicio LLM o capa HYBRID para cerrar el recall regulatorio.**
Rechazada por alcance. `REGULATORY_LLM_GATE = FAIL` se mantiene sin reinterpretar. Cualquier
reactivación exige `PILOT_EXECUTION` firmada y es un proyecto separado.

**A8 — Adoptar el stack de AlcoaBase o ParaQualis como runtime.**
Rechazada por sobre-ingeniería (vLLM/Postgres/MinIO/OpenSearch/React, o un plugin de Claude Code). Solo
se cosechan patrones documentales.

**A9 — Corregir la contradicción 0-vs-90 asumiendo cuál de los dos números es correcto.**
Rechazada; se diagnosticó primero. Resultado (2026-08-28): desincronización de versión, no defecto —
línea base funcional real sobre corpus = 90 (70 artefacto de D-1 + 20). El "0 / 0 FP" del reporte
maestro §E queda obsoleto. Asumirlo sin diagnóstico habría sido el error que este hardening corrige.

---

## CONSEQUENCES

**Positivas.** La ausencia deja de ser indistinguible de la no-lectura, que es la corrección de
soundness más importante disponible. Cada corrida pasa a ser reproducible y verificable por un tercero.
Los gates adquieren rango reportable declarado en vez de un PASS sin contexto. Aparece por primera vez
medición sobre datos reales. El sistema se vuelve cualificable de forma re-ejecutable en lugar de a
través de prosa.

**Negativas y costes aceptados.** `WP-B` en modo enforce **reducirá** el número de hallazgos emitidos
sobre documentos degradados; es una pérdida aparente de cobertura que en realidad es eliminación de
hallazgos no sólidos, y debe comunicarse así a QA para que no se lea como regresión. `WP-D` obliga a un
salto de `EXTRACTION_VERSION` con re-derivación de stores y re-medición de gates. Se recomienda agrupar
todos los cambios que alteren `EXTRACTION_VERSION` en un único salto gobernado, para no pagar dos
requalifications.

**Consecuencia derivada que debe declararse ahora.** El shadow histórico se sostiene sobre
`same_input_hash` frente a una corrida CURRENT persistida. Si `EXTRACTION_VERSION` cambia, esa premisa
deja de valer **para comparaciones futuras**. El shadow sigue siendo válido como cierre histórico; deja
de ser reutilizable como referencia de requalification. Una prueba dual-runtime fresca costaría 158
llamadas LLM bajo `PILOT_EXECUTION` y solo se plantea si Capa 9 la requiere.

**Riesgo residual.** El matcher requisito↔test de `WP-D`, si es laxo, puede generar
`REQUIREMENT_NOT_TESTED` falsos. Se mitiga con el gate de muestra verificada a mano y con el
anti-falso-positivo explícito en los tests del paquete.

---

## SECURITY

Ningún paquete abre superficie de red. Todo corre bajo `network_locked()`; `DOCUMENT_EGRESS = 0` se
mantiene como gate verificable en cada corrida, incluido el benchmark de `WP-C`, que además debe forzar
ruta local y desactivar cualquier fetch remoto por defecto de la librería evaluada.

Descargas: ningún modelo, dependencia ni recurso se descarga sin decisión firmada de Capa 9. Si se
autoriza un modelo OCR, sus artefactos se pre-provisionan, se hashean y su hash entra en el fingerprint
lógico de `WP-A`.

Licencias: AGPL excluido de producción. Las licencias de los **modelos** se verifican por separado de la
licencia del código que los invoca.

`WP-G` es read-only estricto: el front no puede mutar ningún estado GMP.

---

## PRIVACY

Los documentos del cliente no salen del servidor en ninguna fase, incluida la evaluación comparativa de
extractores, que se ejecuta en local y aislada. Ningún paquete introduce telemetría, proveedor externo
ni API de modelo. `EXTERNAL_LLM_API = 0` y `llm_calls = 0` se conservan en el camino operacional.

El fingerprint de `WP-A` contiene hashes y versiones, nunca contenido documental.

---

## GMP IMPACT

Ningún paquete puede producir `QA_APPROVED`, `RELEASED`, `CAPA_CLOSED`, `FINAL_GMP_APPROVAL` ni
`APPROVED`. `FORBIDDEN_STATES` y `_guard_no_forbidden` permanecen intactos. Todo artefacto nuevo nace
`human_state = UNREVIEWED` y `qa_status = NOT_QA_APPROVED`, con la marca
`MACHINE GENERATED — BORRADOR, NO APROBADO`.

El sistema sigue sin declarar cumplimiento. `WP-F` produce estado de gates y contingencias, nunca una
declaración regulatoria, y **el sistema no puede auto-cualificarse**: la firma es siempre humana.

`PRODUCTION_ENABLEMENT`, `REGULATORY_COMPLIANCE` y `CORPUS_READY` no se modifican por ningún paquete;
son decisiones de gobernanza separadas y no son bugs.

Los fixtures y reglas firmados (`technical_completeness_rules.yaml` v1.1, `technical_suite_c.yaml`,
`decomposition.yaml` v1.1, `risk_matrix.yaml` v1.0) no se tocan ni se re-puntúan retrospectivamente. El
corpus held-out de `WP-E` es adicional, no sustituto, y requiere firma independiente.

Dirección regulatoria emergente: el borrador de EU GMP Annex 22 (consulta cerrada el 7-oct-2025, **sin
texto adoptado**, finalización esperada en 2026) advierte contra probar modelos con datos artificiales
sin justificación y exige datos de prueba independientes. Esto respalda `WP-E` y motiva el registro de
justificación de datos sintéticos como ítem de gobernanza. **No se usa para convertir un gate FAIL en
PASS ni para declarar cumplimiento.** Su estado debe reverificarse antes de citarlo.

---

## ROLLBACK

| Paquete | Mecanismo |
|---|---|
| WP-A | Campos aditivos en manifest/audit; eliminarlos no afecta a nada aguas arriba |
| WP-B | Flag `observe \| enforce`; en `observe` el comportamiento es idéntico al actual |
| WP-C | No aplica — no toca producción |
| WP-D | Etapa desactivable por flag; `EXTRACTION_VERSION` nueva, stores anteriores conservados y no sobrescritos |
| WP-E | Aditivo; las suites actuales siguen corriendo sin cambios |
| WP-F | Artefacto y checker independientes del runtime; retirables sin efecto |
| WP-G | Eliminar módulo JS y entrada de menú |
| **Global** | `routing = 'current'` (archivo) o `V2_ANALYZER_ROUTING=current` (env). Motor CURRENT intacto |

`CURRENT_ROLLBACK_AVAILABLE = YES` se conserva sin degradación en todos los paquetes.

---

## ACCEPTANCE GATES

**Transversales — se verifican en cada paquete, sin excepción:**
```
DOCUMENT_EGRESS = 0 · llm_calls = 0 · FABRICATED_CITATIONS = 0
human_gate_intact = true · forbidden_states_present = false
fixtures y reglas firmados sin modificar · routing y governance sin modificar
CURRENT intacto y reversible
NEW_REGRESSION_FAILURES = 0 · EXC-1..EXC-5 no aumentan (ni en número ni en identidad)
```

**Por paquete:**

- **WP-A** — dos corridas sobre el mismo input+config+conjunto-estático-de-fuentes ⇒
  `INPUT_CONFIG_FINGERPRINT` y `FINDINGS_FINGERPRINT` idénticos; cambiar un input (`document_id`+`sha256`),
  un artefacto firmado realmente consumido, un threshold aplicado o el `source_attestation_digest`
  (`module_manifest_sha256` del cierre estático de imports + `python_version_mm`) cambia el fingerprint que
  corresponda; cambiar reloj/host/pid no cambia ninguno; `FINDINGS_FINGERPRINT` es inmune al orden de la
  lista y a `provenance.run_id`; `RUN_ATTESTATION` incluye `active_engine` y `routing_source`
  (env|file|default) en toda corrida; cada entrypoint incluye SOLO los artefactos que consume
  (`technical_suite_c.yaml` no entra en el fingerprint de `v2_runtime`); `git_commit`/`git_dirty` son
  advisory, no identidad; sin repo git ⇒ degradación limpia; ninguna ruta absoluta en los digests.
- **WP-B (OBSERVE, este paso)** — baseline = corrida fresca de 6 documentos en HEAD `6335588`
  (`INPUT_CONFIG_FINGERPRINT cc130aa5…`, `FINDINGS_FINGERPRINT 434f7d42…`, `342/90/24/8`). RW-0009 →
  `NOT_ANALYZABLE` (por el piso absoluto), los otros cinco → `ANALYZABLE`; señales relativas quedan
  OBSERVACIONALES por tamaño de muestra. **0 supresiones · 0 Findings GMP nuevos · 0 cambio de
  `risk`/`remediation`/`state`**; misma población de findings; el único cambio por finding es el campo
  aditivo `evidence_basis` — por eso `*_findings.json` no es byte-idéntico, `FINDINGS_FINGERPRINT` cambia
  y `INPUT_CONFIG_FINGERPRINT` de `v2_runtime`/`real_corpus` cambia (nuevo artefacto consumido);
  esperado, no regresión. `analysis_coverage.json` presente como metadata (no Finding, no risk, no
  remediation): verdicts + señales con su `n` por rol + `coverage_dependencies` por finding
  (`would_degrade` informativo). `REGULATORY_INCONCLUSIVE` → `evidence_basis = INDETERMINATE`.
  Fail-closed **solo** en la ruta de gate ENFORCE si las heurísticas no están firmadas; en OBSERVE corre
  con `thresholds_signed=false` registrado.
- **WP-B (ENFORCE, decisión posterior de Capa 9)** — degradar a `MACHINE_INCONCLUSIVE` +
  `COVERAGE_LIMITATION` los findings con `coverage_dependencies.would_degrade == true`
  (`evidence_basis ∈ {ABSENCE_DEPENDENT, INDETERMINATE}` cuya región dependa de un doc
  `NOT_ANALYZABLE`/`DEGRADED`); `PRESENCE` intacto; requiere heurísticas firmadas + regla de degradación
  firmada.
- **WP-C** — métricas y criterio de decisión firmados **antes** de correr; adopción solo si el
  candidato recupera el cuerpo de pruebas verificado a mano **y** no regresa la extracción de los cinco
  documentos que hoy funcionan.
- **WP-D** — `tested_by > 0` con muestra verificada a mano, no por conteo; cero regresión en
  `implemented_by` y `designed_by`; ningún `REQUIREMENT_NOT_TESTED` sin arista trazable.
- **WP-E** — toda métrica publicada viaja con `suite_version + tamaño + definición + rango reportable +
  declaración de contaminación`; corpus held-out firmado por autor distinto del autor de las reglas;
  umbrales fijados antes de los resultados.
- **WP-F** — el checker re-ejecuta y reproduce el fingerprint declarado; si no coincide, `FAIL`; todo
  el pack nace `DRAFT`; ningún valor esperado escrito como literal en el test.
- **WP-G** — cero llamadas de escritura; ningún estado GMP mutable desde el front; `evidence_basis`,
  estado de adecuación y fingerprint visibles en la vista de corrida.

**Precondiciones bloqueantes:** `WP-B` no se implementa sin confirmar el alcance de la emisión de
hallazgos por ausencia sobre documentos degradados. `WP-D` no se implementa sin el resultado de `WP-C`.
`WP-F` no se implementa antes de `WP-A` y `WP-E`. Ambas confirmaciones pendientes son read-only.

---

## DECISION REQUIRED FROM LAYER 9

1. Aprobar el enfoque (hardening aditivo, sin V3) y el orden propuesto.
2. Autorizar `WP-A` como primer paquete de implementación.
3. Los tres diagnósticos read-only previos (alcance de la emisión por ausencia; reconciliación 0-vs-90;
   veredicto por familia de aristas vacías) están EJECUTADOS (2026-08-28) y aceptados; resultados en el
   `PLAN` NG-1 / NG-2 / NG-5. No cambian el enfoque ni el orden. Registran además la deuda separada D-8
   (`refers_to` no poblado).
4. Decidir por separado, cuando corresponda: firma de las HEURÍSTICAS de adecuación (no requisitos) + regla de degradación ENFORCE · descarga de modelos OCR ·
   salto de `EXTRACTION_VERSION` · firma del corpus held-out · registro de justificación de datos
   sintéticos.

*Estado: PROPUESTO. Sin implementación, instalación, descargas, cambios de fixtures/reglas firmados,
routing, gobernanza, commit ni push.*
