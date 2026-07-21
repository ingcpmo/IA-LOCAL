# CURRENT_STATE_AUDIT — Auditoría del estado actual

Modo: solo lectura y diseño. No se modificó código, paquetes, decisiones ni
auditoría histórica. `PRODUCTION_ENABLEMENT=BLOCKED` durante toda la
auditoría.

Fecha: 2026-07-21. Fuente de verdad: código y tests reales del repo en
`/home/ing_cpmo`, `git log`, y los 2 paquetes reales creados en esta misma
sesión (`PKG-FS-V1-2-MEDIUM-RISK-REAL`, `PKG-FS-V1-2-REAL-CONTROLLED`).

## Leyenda

- **VALIDATED**: código real + tests reales que lo ejercitan + (cuando aplica)
  verificación en vivo contra factory-api.
- **PARTIALLY_VALIDATED**: código real y testeado en aislamiento, pero con un
  hueco de integración, cobertura o vigencia declarado por el propio código.
- **NOT_VALIDATED**: existe una necesidad declarada en este objetivo pero no
  hay código, o el código existente resuelve otra cosa.
- **DESIGN_ONLY**: código y tests existen pero no está cableado a ningún
  camino de producción — el propio código lo declara.
- **BLOCKED**: bloqueado a propósito por diseño (no es una carencia).

## 1. Generación de hallazgos/gaps por documento (motor de análisis)

**`factory/engines/gmpai_integrity/chunked_engine.py`** — **VALIDATED**.
Motor de producción real: procesa el documento completo por chunks de página
(`CHUNK_MAX_CHARS=6000`, solapamiento 500 caracteres), con checkpoints de
reanudación (`CheckpointStore`), llama a Ollama vía `ollama_client`, valida
schema del output LLM (`_validate_checkpoint_schema`), verifica anclaje de
cita (`_is_anchored`) y relevancia temática (`_is_topically_relevant`).
Probado con el piloto real sobre
`215115305 SCADA-PCS Misc PLC System URS v2.1.pdf` y `FS_v1.2.pdf` (los 19
findings de `findings_completos_FS_v1_2_v4.json`/`_v5.json` son su salida
real). Tests: `test_gmpai_chunked_engine.py`,
`test_chunked_engine_validation_evidence.py`. Escribe evento de auditoría
real por documento analizado.

**Limitación real declarada por el propio motor** (docstring
`chunked_engine.py`): la consolidación por checkpoint usa la regla "el
estado no-insuficiente gana" con contradicción → `cumple_parcialmente +
revision_humana_requerida=True` — es una regla más simple que la del
pipeline verificado (ver §2).

## 2. Pipeline de verificación rigurosa (evidence_verifier / absence_consolidator / applicability)

**`factory/regulatory/evidence_verifier.py`** — **VALIDATED en aislamiento**.
Verificador determinístico ternario (`PASS`/`FAIL`/`NOT_VERIFIABLE`), 5
niveles de coincidencia de cita (`exact`/`normalized`/`despaced`/`fuzzy≥0.93`/
`not_found`). Corrigió un bug real de producción (W5.6: cita literal correcta
rechazada por kerning de PDF y membrete de página repetido — commit
`fefe258`). Test: `test_evidence_verifier_v2.py`.

**`factory/regulatory/absence_consolidator.py`** — **VALIDATED en
aislamiento**. Regla P3 dura: `DOCUMENTATION_GAP` solo se emite si
`coverage_complete=True` (parámetro obligatorio, sin default, forzado tras un
incidente real — W5.5, commit `490fbf1`: un gap se declaró con 2/29 chunks
reales) y ningún chunk relevante quedó `rejected_by_verifier`. Test:
`test_absence_consolidator.py`.

**`factory/regulatory/applicability.py` + `applicability_matrix.yaml`** —
**VALIDATED y aprobado humanamente** (`approval.status: human_confirmed`,
checkpoint MC-0001 en `factory/layer9/decisions/decisions.jsonl`) — pero
**restringido a `run_context='validation'`** por
`require_matrix_approved_for_production()` (fail-closed, P1): cualquier otro
`run_context` exige la aprobación humana explícita que hoy solo existe para
validación.

**`factory/regulatory/verified_pipeline.py`** — **DESIGN_ONLY**. El propio
docstring del módulo lo declara: *"esta orquestación NO está todavía cableada
dentro del POST HTTP de producción (`chunked_engine.evaluate_chunked()`)"*.
Verificado independientemente por `grep`: ningún archivo de producción
(`factory/api/`, `factory/services/`) importa `verified_pipeline` — solo sus
propios tests lo hacen. **Consecuencia real**: el motor que efectivamente
corre en producción (`chunked_engine.py`, §1) usa una regla de consolidación
más simple y NO pasa por `evidence_verifier`/`absence_consolidator` en el
camino HTTP real, aunque ambos módulos existen, están probados y uno de ellos
(`absence_consolidator`) ya corrigió un incidente de producción real.

## 3. Catálogo regulatorio y fuentes gobernadas

**`factory/regulatory/regulatory_catalog.py` + `requirement_catalog/`** —
**VALIDATED**. 19 entradas (5 × 21 CFR Part 11, 5 × EU Annex 11, 8 × 8+1
ALCOA+/MHRA — nota: son 9 checkpoints ALCOA+ reales, ver §Regulatory Source
Access Audit), `citation_sha256` recalculado y comparado al cargar
(fail-closed: una cita editada sin recalcular el hash rompe la carga). Tests:
`test_regulatory_catalog.py` (19/19 entradas verificadas 1:1 contra el
canónico), `test_requirement_catalog_loader.py`.

**Declaración explícita del propio catálogo** (docstring
`regulatory_catalog.py`): *"production_status: PRODUCTION_ENABLEMENT=BLOCKED
— este catálogo NO está cableado en `chunked_engine.py` ni en los prompts
YAML de producción"*. Confirma independientemente el hallazgo de §2: el
catálogo canónico con hashes verificados existe, pero el motor de producción
todavía no lo consume — sus prompts (`factory/engines/gmpai_integrity/
prompts/*.yaml`) no citan `regulatory_catalog_entry_id`.

**`factory/regulatory/sources/registry.json`** — **PARTIALLY_VALIDATED**. 3
fuentes con hash real verificado en la ingesta (`hashes_match: true`,
`local_integrity_status: PASS`), URL oficial declarada, `derived_artifacts`
con extracción `pdfplumber` trazada por hash. Pero **las 3 declaran
`regulatory_currency_status: pending_reverification`** — la vigencia
(¿sigue siendo la versión vigente de la norma, no superseded?) se verificó
una sola vez en la ingesta original (2026-07-06) y nunca se ha
re-verificado desde entonces. Detalle completo en
`REGULATORY_SOURCE_ACCESS_AUDIT.md`.

## 4. BATCH_AND_EXCEPTION — flujo de paquete de remediación (revisión humana, sin release)

**`factory/services/remediation_package_service.py` +
`remediation_package_schemas.py` + `factory/api/routes/
remediation_packages.py`** — **VALIDATED**, el subsistema más maduro de los
auditados. 94+ tests unitarios/concurrencia/aislamiento de auditoría, y
**verificado en vivo contra factory-api dos veces en esta sesión**:
- `PKG-FS-V1-2-REAL-CONTROLLED` v1 — 2 changes HIGH_RISK reales (contenido
  real de `215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf`), ciclo completo
  `AWAITING_HUMAN_EXCEPTION_REVIEW→AWAITING_PACKAGE_DECISION→
  PACKAGE_READY_FOR_RELEASE`, decisión `APPROVE_WITH_EXCEPTIONS` por Cesar.
- `PKG-FS-V1-2-MEDIUM-RISK-REAL` v1 — 1 change MEDIUM_RISK real, primer caso
  real que ejercita `medium-risk-batch`, decisión `APPROVE_CLEAN` por Cesar.

Invariantes duras verificadas por test y en vivo: `create_release_record()`
existe en el servicio pero **ningún router lo expone** (comentario explícito
en `remediation_packages.py`: *"Deliberadamente NO expone ningún endpoint de
ReleaseRecord todavía"*); locking por `package_id` (fcntl, verificado con
procesos e hilos reales concurrentes, `test_remediation_package_concurrency.py`);
escritura atómica (`temp+fsync+os.replace+fsync de directorio`); aislamiento
de auditoría por test (`test_remediation_package_audit_isolation.py`).

**`factory/services/gap_assessment_finding_mapper.py`** — **PARTIALLY_VALIDATED**.
17 tests contra el JSON real de findings (`ee03234`, `b975ad7`). Mapea
finding real → `RemediationChange` con reglas deterministas documentadas.
Verificado en vivo con 3 findings reales (`FSV12-07→COR-5`, `FSV12-13→COR-2`,
`FSV12-11→COR-1`). **Huecos declarados en su propio docstring** (no
corregidos):
- `chunk_sha256` es un **hash proxy** (`sha256(documento|chunk_id)`), no el
  hash real del motor de chunking de `chunked_engine.py` — no hay adaptador
  que conecte la ejecución real de chunking con este mapeo.
- `regulatory_source_sha256`/`requirement_catalog_sha256` se calculan desde
  contenido real pero **`remediation_package_schemas.py` solo valida su
  formato** (hex sha256), nunca los recalcula/compara — a diferencia de
  `citation_text_sha256`, que sí se recalcula y rechaza en discrepancia. Un
  valor con forma de sha256 pero contenido arbitrario pasaría igual.
- La regla de cobertura (`coverage_status`) para el caso multi-rango sigue
  dependiendo de un campo `resolucion_humana_incorporada` que solo existe
  para un finding (`FSV12-07`) resuelto manualmente por Cesar en otra
  sesión — no hay una regla generalizable para el caso multi-rango sin esa
  resolución previa.
- **Este módulo reimplementa una versión más simple y NO endurecida de la
  misma pregunta que ya resuelve `absence_consolidator.py` (§2)**: "¿cuándo
  puedo declarar ausencia con evidencia completa?". `absence_consolidator.py`
  ya incorpora las lecciones de dos incidentes reales de producción
  (W5.5/W5.6); `gap_assessment_finding_mapper.py` es una implementación
  independiente y más joven que no las reutiliza. Ver
  `GAP_AND_DEVIATION_MODEL.md` para la recomendación de unificación.
- **`automatic_evaluation_basis` (expected_chunks/evaluated_chunks/
  execution_errors/rejected_records) se construyó A MANO en los 2 paquetes
  reales de esta sesión** (yo mismo, como operador humano, tecleé esos
  valores) — no existe ningún adaptador que calcule ese basis a partir de la
  ejecución real de `chunked_engine.py` sobre el documento. `
  automatic_evaluation_complete=True` en ambos paquetes reales es, en la
  práctica actual, una afirmación manual, no una medición automática.

## 5. `known_issue` declarado de COR-2 — investigado, INCONCLUSO

Cesar declaró como `known_issue` de `PKG-FS-V1-2-REAL-CONTROLLED`: *"COR-2
tenía `ABSENCE_CONFIRMATION` desactualizado"*. Investigación real realizada en
esta auditoría:
- `COR-2` viene de `FSV12-13` en `findings_completos_FS_v1_2_v4.json` (v4.1).
- Existe `findings_completos_FS_v1_2_v5.json` (v5) del mismo documento,
  **generado con el mismo `generated_at`** que v4.1 — el contenido de
  `FSV12-13` es **idéntico** en ambos archivos (mismo `clasificacion_brecha`,
  mismo texto de `evidencia`).
- `matriz_correcciones_v4_1_corrected_a_v5.json` documenta 8 correcciones
  reales entre v4.1-corrected y v5 (D1–D8: encabezado DOCX acumulado,
  truncamiento de tabla, página casi vacía, referencias a archivos `_v4`
  obsoletos, etc.) — **ninguna de las 8 menciona `FSV12-13`, `COR-2` ni
  `ALCOA_CONTEMPORANEOUS`**.

**Conclusión honesta**: con la evidencia disponible **no pude confirmar ni
descartar** la afirmación de Cesar. `EVALUATION_INCOMPLETE`. Hipótesis
abiertas no verificadas: (a) el "desactualizado" se refiere a una versión del
documento fuente posterior a v5 no revisada en esta auditoría; (b) se refiere
a que la propia noción de `ABSENCE_CONFIRMATION` en el mapper (§4) no
reutiliza las reglas endurecidas de `absence_consolidator.py` (§2), lo cual
sí es un hecho verificado, aunque distinto de "el finding cambió". Esto
permanece como bloqueo de cuarentena declarado para
`PKG-FS-V1-2-REAL-CONTROLLED` — no se reclasifica en esta auditoría.

## 6. Generación de documento candidato completo

**NOT_VALIDATED — no existe la capacidad pedida.** Dos módulos generan
documentos, ninguno hace lo que pide el objetivo (nueva versión completa del
documento original, con estructura/numeración/formato preservados):

- **`factory/services/gmpai_docx_draft.py`**: genera un **memo de
  remediación DOCX independiente**, no una edición del original. Cita
  textual del propio docstring: *"No es una edición del documento
  original... Este módulo genera una PROPUESTA CONTROLADA: un memo de
  remediación versionado... Nunca toca los originales"*.
- **`factory/services/dossier_generator_service.py`**: genera los 22
  documentos del **dossier de validación GAMP 5 de la propia solución
  custom de la fábrica** (W6.2) — es documentación sobre el software que
  construye la fábrica, no remediación de un documento regulatorio externo
  cargado por el cliente.

En los 2 paquetes reales de esta sesión, el "candidato" (`candidate_document`)
fue un **extracto Markdown corto** (446–1498 bytes) que lista solo las
secciones nuevas propuestas — exactamente el tipo de artefacto que el
objetivo #5 excluye explícitamente ("No aceptes un extracto Markdown como
documento candidato completo"). Esto se declara aquí como hallazgo de
auditoría sobre el propio trabajo de esta sesión, no se corrige.

## 7. Calidad de redacción / coherencia / trazabilidad de cambios

**NOT_VALIDATED.** No existe ningún módulo que valide claridad, coherencia,
terminología consistente con el documento, o ausencia de afirmaciones de
implementación no demostrada en el texto propuesto. `claim_verifier.py`
(§8) verifica anclaje de **citas regulatorias**, no calidad de redacción del
cambio propuesto en sí.

## 8. Verificador de citas de agente (pipeline W7, distinto de BATCH_AND_EXCEPTION)

**`factory/services/claim_verifier.py`** — **VALIDATED, pero en un pipeline
distinto**. Verificador v2 determinista (W6.5.1), detecta
`unverified_reference` (cita sin respaldo declarado en corpus del agente) y
relevancia temática — advisory, nunca bloquea ni reescribe. Corrigió un
incidente real (v05 citó §11.30(a)/(c) fuera de alcance declarado). Vive en
el pipeline de dossier/case-memory (W6–W9), **no está conectado a
BATCH_AND_EXCEPTION** ni al mapeo finding→RemediationChange.

## 9. Cadena de auditoría

**VALIDATED con un WARN preexistente conocido.** `factory/core/audit_writer.py`
+ endpoint `/api/v1/audit/verify`: cadena hash SHA-256, `hash_errors=0`
consistentemente en todas las verificaciones de esta sesión. `chain_errors=1`
("fork concurrente") **preexistente desde 2026-06-15**, documentado y
aceptado en `factory/docs/BATCH_AND_EXCEPTION_CIERRE.md` — no introducido por
ningún trabajo de esta sesión, confirmado en cada verificación repetida.

## 10. Estado de la suite de tests (evidencia cuantitativa)

`/home/ing_cpmo/.venv/bin/python3 -m pytest factory/tests/ -q` →
**830 passed, 1 skipped**, sin fallos, ejecutado en esta misma auditoría (no
es una cifra heredada de memoria). Nota operativa: requiere el venv del
proyecto (`/home/ing_cpmo/.venv/bin/python3`) — el `python3` del sistema no
tiene `jsonschema`, exigido fail-closed por
`factory/regulatory/schema_loader.py`.

## Resumen de clasificación

| Componente | Clasificación |
|---|---|
| `chunked_engine.py` (motor de análisis producción) | VALIDATED |
| `evidence_verifier.py` / `absence_consolidator.py` (aislado) | VALIDATED en aislamiento |
| `applicability.py` + matriz | VALIDATED, restringido a `run_context=validation` |
| `verified_pipeline.py` (orquestación rigurosa) | **DESIGN_ONLY** — 0 llamadores de producción |
| `regulatory_catalog.py` + `requirement_catalog/` | VALIDATED, no cableado a prompts de producción |
| `sources/registry.json` (fuentes gobernadas) | PARTIALLY_VALIDATED — vigencia pendiente de reverificación |
| BATCH_AND_EXCEPTION (`remediation_package_service.py`+API) | VALIDATED, verificado en vivo 2×, sin release |
| `gap_assessment_finding_mapper.py` | PARTIALLY_VALIDATED — 3 huecos declarados, no unificado con `absence_consolidator` |
| `automatic_evaluation_basis` real (chunking→basis) | **NOT_VALIDATED** — hoy es manual |
| Generación de documento candidato completo | **NOT_VALIDATED** — no existe, solo memo/dossier de otro alcance |
| Calidad de redacción/coherencia del cambio | **NOT_VALIDATED** — no existe |
| `claim_verifier.py` (anclaje de citas de agente) | VALIDATED, en pipeline distinto (W7), no conectado |
| Cadena de auditoría | VALIDATED, WARN preexistente conocido, sin regresión |
| `known_issue` COR-2 | INCONCLUSO — investigado, sin confirmar ni descartar |
| `ReleaseRecord` / liberación | **BLOCKED por diseño** — sin endpoint, confirmado en cada verificación |
