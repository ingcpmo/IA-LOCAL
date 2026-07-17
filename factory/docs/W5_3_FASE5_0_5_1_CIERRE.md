# W5.3 (Fase 5) — Cierre de Fase 5.0 y Fase 5.1 + Checkpoint D1

Fecha: 2026-07-17. Estado: **sin commit** (pendiente tu revisión, mismo
patrón que Checkpoints A/B/C de W5v2). `requirements.yaml` definitivo **NO
construido** — solo inventario (`inventory_draft_v1.json`), tal como
pediste.

## Fase 5.0 — Corrección `run_context` + runner versionado

| Control | Estado |
|---|---|
| 5. `run_context` obligatorio en `generate_controlled()` (sin default) | ✅ Hecho — `TypeError` si se omite, keyword-only |
| Corrección previa: `run_context` obligatorio en `evaluate_chunked()` (sin default) | ✅ Hecho — mismo patrón |
| 6. Runner versionado (no depender del script gitignorado) | ✅ Hecho — `factory/regulatory/tools/run_validation_evidence.py` (tracked), `run_context` no es ni siquiera un parámetro configurable ahí: está fijo en `'validation'` en el código |
| 7. Parámetros de persistencia `_by_req_candidates` (solo diseño) | Ver sección dedicada abajo |

**Archivos**: `chunked_engine.py`, `ollama_client.py` modificados; 5 archivos de test actualizados (`test_gmpai_chunked_engine.py` ×14 llamadas, `test_w5v2_regulatory_schemas.py` ×4, `test_run_context_audit.py`, `test_w5v2_governance_gates.py`); `w5v2_evidence_run.py` **NO se editó** — es un registro histórico congelado de una ejecución real, editarlo lo desincronizaría de lo que efectivamente corrió (nota explícita agregada en su docstring en su lugar); 2 archivos nuevos: `factory/regulatory/tools/run_validation_evidence.py` + `factory/tests/test_run_validation_evidence_runner.py` (5 tests, incluye 1 integración real opt-in vía `W5V3_REAL_OLLAMA=1`, skip por defecto).

**Verificación**: 584 passed (antes 580), 60 fallos idénticos al baseline `262917e` (nombre+causa, diff exacto sin salida). Selfcheck en curso al momento de escribir esto.

## Fase 5.1 — Inventario de fuentes (solo lectura)

### Control #1 — Fuente canónica sin duplicación manual

**Hallazgo real que cambia el diseño**: los documentos oficiales
(`OFFICIAL_ECFR_21CFR_part11.txt`, `OFFICIAL_EU_GMP_ANNEX11.pdf`,
`OFFICIAL_MHRA_GXP_DI_GUIDANCE_2018.pdf`) y su `corpus_manifest.yaml`
**viven en `factory/workspaces/lab_qc_project/`, que está gitignorado**
(`factory/.gitignore:1 workspaces/*`, confirmado con `git check-ignore`).
El hash SHA-256 por archivo, sin embargo, SÍ está trackeado — pero en un
lugar distinto y no obvio: `factory/deployments/lab_qc_project/
ingest_manifest.yaml` (paso 6). Es decir, hoy la "fuente canónica" está
**partida en dos** (metadata de autoridad/URL en un archivo gitignorado,
hash en un archivo trackeado) y los documentos físicos mismos no tienen
ninguna copia bajo control de versiones.

**Diseño aplicado en este inventario** (sin copiar nada todavía): el hash
se computó **en vivo, directo del archivo** (`sha256_file()`, nunca tecleado
a mano) y se cruzó contra AMBAS referencias existentes
(`REGULATORY_SOURCE_CHECK.json` para Part11/Annex11, `ingest_manifest.yaml`
para MHRA) — los 3 coinciden exactamente. Ningún valor de hash de este
inventario fue copiado manualmente de ningún YAML: es siempre el resultado
de `sha256_file()` ejecutado ahora mismo.

**Decisión pendiente para Fase 5.2** (no tomada todavía, te la presento
como pregunta, no como hecho consumado): dado que los documentos físicos no
están versionados en absoluto, ¿copiamos los 3 archivos oficiales que
necesita `gmpai_document_validation` a una ruta trackeada dentro de
`factory/regulatory/requirement_catalog/official_sources/` (mismos bytes,
mismo hash, con manifiesto explícito de origen apuntando al `ingest_manifest.yaml`
de `lab_qc_project` como procedencia), o aceptamos la dependencia cruzada a
un workspace gitignorado de otro proyecto? Mi recomendación es copiar (con
manifiesto de procedencia, no como "documento nuevo ingerido" sino como
"mismo documento oficial, ahora también versionado aquí") — pero no lo
hice todavía porque implica escribir archivos nuevos y tú pediste
diseño/inventario solamente en esta fase.

### Control #2 — 3 status separados por fuente

Aplicado a las 3 fuentes usadas:

| Fuente | `local_integrity_status` | `official_origin_status` | `regulatory_currency_status` |
|---|---|---|---|
| `OFFICIAL_ECFR_21CFR_part11.txt` | **PASS** (hash recomputado == `REGULATORY_SOURCE_CHECK.json`) | `INHERITED_FROM_2026-07-06_INGESTION` — no re-verificado contra eCFR.gov en este ciclo | `INHERITED_LAST_VERIFIED_2026-07-16` — sin enmiendas a 11.10/11.50/11.70 desde la regla final de 1997 (afirmación heredada, no re-chequeada hoy) |
| `OFFICIAL_EU_GMP_ANNEX11.pdf` | **PASS** | `INHERITED_FROM_2026-07-06_INGESTION` | `INHERITED_LAST_VERIFIED_2026-07-16` — vigente desde 2013, sin revisión posterior conocida (heredado) |
| `OFFICIAL_MHRA_GXP_DI_GUIDANCE_2018.pdf` | **PASS** (hash recomputado == `ingest_manifest.yaml`, dato que `REGULATORY_SOURCE_CHECK.json` había dejado `sha256_manifest: null` — gap real que este inventario cierra) | `INHERITED_FROM_2026-07-06_INGESTION` | `INHERITED_LAST_VERIFIED_2026-07-16` (heredado) |

**Principio aplicado literalmente**: un hash válido (`local_integrity_status=PASS`)
NO se presenta en ningún punto como evidencia de vigencia regulatoria — los
tres campos son independientes y ninguno se infiere de otro. Ninguno de los
tres fue re-verificado contra la fuente oficial en internet en este ciclo
(no había necesidad ni autorización para eso en una fase de solo lectura);
se documenta explícitamente como `INHERITED`, con la fecha y el archivo del
que se hereda, en vez de presentarlo como una verificación fresca que no
ocurrió.

### Control #3 — Cita verificable con anclaje mecánico

`factory/regulatory/requirement_catalog/citation_locator.py` (nuevo, 4
tests). Reutiliza `match_citation()` de `evidence_verifier.py` — **misma
vara para las citas del catálogo que para las citas de un finding**, sin
excepción especial. Resultado real sobre los 19 requirement_id:

**16/19 verificados (`exact` o `normalized`)** — cita localizada, con
página real dentro del PDF/archivo fuente.

**3/19 con hallazgo real, NO forzado a pasar**:

| requirement_id | Resultado | Causa raíz real |
|---|---|---|
| `ANNEX11_4` | `not_found` (score 0.869) | Artefacto de extracción de `pypdf`: el PDF real inserta espacios espurios dentro de palabras ("s hould" en vez de "should", "ab le" en vez de "able") — confirmado inspeccionando el texto extraído línea por línea |
| `ANNEX11_7.1` | `fuzzy` (score 0.9737, sobre el umbral 0.93 pero NO aceptado para catálogo) | Mismo artefacto ("a nd" en vez de "and") — decisión de diseño: el catálogo exige `exact`/`normalized`, un umbral MÁS estricto que el runtime (`verified_with_deviation` no es suficiente para una cita de catálogo que otros van a citar como fuente de verdad) |
| `ANNEX11_17` | `fuzzy` (score 0.9368) | Mismo artefacto ("ch ecked" en vez de "checked") |

**Esto no es una cita inventada ni un requisito sin fuente** — el contenido
real está ahí, confirmado visualmente en las 3 líneas exactas del PDF; es
un problema de **extracción**, no de **existencia** de la fuente. Queda
marcado `CITATION_NOT_VERIFIED_NEEDS_REVISION`, no se fuerza a
`COVERED`. Resolución propuesta para Fase 5.2: re-extraer con
normalización de espacios intra-palabra antes de proponer el
`citation_text`, o (más robusto) usar `pdfplumber` en vez de `pypdf` para
este documento específico (ya está instalado en `factory-api`, usado por
`extraction.py` del workspace) y comparar.

### Control #4 — normative_type / jurisdiction / binding_status

Aplicado a los 19: `regulation` (US, `binding_regulation`) para los 5 de
Part 11; `official_guidance` (EU, `binding_requirement`) para los 5 de
Annex 11; `official_guidance` (UK, `non_binding_guidance`) para los 9 de
ALCOA+ vía MHRA — **MHRA es guía, no regulación** (el documento mismo se
titula "Guidance and Definitions"), diferencia real que el catálogo debe
preservar: ALCOA+ no es un requisito regulatorio directo en la misma forma
que 21 CFR Part 11, es una guía de expectativas ampliamente adoptada. Esto
ya estaba implícito en cómo se usa hoy (`riesgo`/`recomendacion` en los
findings nunca citan ALCOA+ como "violación legal"), pero ahora queda
declarado explícitamente en el catálogo en vez de solo en la prosa.

## Control #7 — Diseño de persistencia de `_by_req_candidates` (Fase 5.4, NO implementado)

Parámetros definidos para cuando se implemente (Fase 5.4):

- **Ruta autorizada por `path_policy`**: nueva función
  `resolve_validation_evidence(run_id: str, path_policy_base: Path) -> Path`
  siguiendo el MISMO patrón que `resolve_workspace`/`resolve_rc_artifact`
  (`factory/core/path_policy.py`) — valida `run_id` contra un patrón
  `^w5v3-validation-[0-9a-f]{12}$` (sin traversal posible), confina bajo
  `factory/regulatory/validation_evidence/{run_id}/`, extensión única
  permitida `.json`.
- **Permisos**: archivo `0o640` (lectura para el grupo del proceso, sin
  ejecución, sin escritura por otros) — mismo criterio que
  `factory/audit/factory_audit.jsonl`.
- **Hash**: SHA-256 del contenido calculado y registrado en el mismo JSON
  (`content_sha256`) antes de escribir a disco, mismo patrón
  no-circular que `package_receipt.json` de `gmpai_document_validation`
  (calculado, luego escrito, nunca recalculado después).
- **`run_id` / `document_sha256`**: ambos campos obligatorios en el
  nombre de archivo Y en el contenido (doble anclaje) — un archivo sin
  ambos campos coincidentes se considera corrupto, no se lee.
- **Tamaño máximo**: 10 MB por archivo de evidencia (chunk de texto real ×
  N candidatos, acotado) — si se excede, error explícito fail-closed, NO
  truncamiento silencioso del texto (violaría el principio "no truncar"
  ya aplicado en el generador de reportes de FS_v1.2).
- **Retención**: mismo régimen que el resto de `factory/audit/` — sin
  fecha de expiración automática (registro GxP, borrado requiere decisión
  humana explícita registrada como evento de auditoría, nunca un cron).
- **Clasificación de confidencialidad**: `INTERNAL_VALIDATION_EVIDENCE` —
  mismo nivel que el resto de `factory/regulatory/`, no expuesto por
  ningún GET público sin autenticación (mismo `x-api-key` que protege
  `/missions/*`).

## Inventario completo (19/19 requirement_id)

Persistido en `factory/regulatory/requirement_catalog/inventory_draft_v1.json`
(borrador, NO es `requirements.yaml` definitivo). Resumen:

| requirement_id | Fuente canónica | Tipo normativo | Cita localizada | Hash (local_integrity) | Vigencia regulatoria | Cobertura |
|---|---|---|---|---|---|---|
| 21_CFR_11.10(a) | OFFICIAL_ECFR_21CFR_part11.txt | regulation (US) | exact, pág 1 | PASS | INHERITED 2026-07-16 | COVERED |
| 21_CFR_11.10(d) | OFFICIAL_ECFR_21CFR_part11.txt | regulation (US) | exact, pág 1 | PASS | INHERITED 2026-07-16 | COVERED |
| 21_CFR_11.10(e) | OFFICIAL_ECFR_21CFR_part11.txt | regulation (US) | exact, pág 1 | PASS | INHERITED 2026-07-16 | COVERED |
| 21_CFR_11.10(g) | OFFICIAL_ECFR_21CFR_part11.txt | regulation (US) | exact, pág 1 | PASS | INHERITED 2026-07-16 | COVERED |
| 21_CFR_11.50_11.70 | OFFICIAL_ECFR_21CFR_part11.txt | regulation (US) | exact, pág 1 | PASS | INHERITED 2026-07-16 | COVERED |
| ANNEX11_4 | OFFICIAL_EU_GMP_ANNEX11.pdf | official_guidance (EU) | **not_found** | PASS | INHERITED 2026-07-16 | **NEEDS_REVISION** |
| ANNEX11_7.1 | OFFICIAL_EU_GMP_ANNEX11.pdf | official_guidance (EU) | **fuzzy 0.97** | PASS | INHERITED 2026-07-16 | **NEEDS_REVISION** |
| ANNEX11_9 | OFFICIAL_EU_GMP_ANNEX11.pdf | official_guidance (EU) | normalized, pág 4 | PASS | INHERITED 2026-07-16 | COVERED |
| ANNEX11_12 | OFFICIAL_EU_GMP_ANNEX11.pdf | official_guidance (EU) | normalized, pág 4 | PASS | INHERITED 2026-07-16 | COVERED |
| ANNEX11_17 | OFFICIAL_EU_GMP_ANNEX11.pdf | official_guidance (EU) | **fuzzy 0.94** | PASS | INHERITED 2026-07-16 | **NEEDS_REVISION** |
| ALCOA_ATTRIBUTABLE | OFFICIAL_MHRA_GXP_DI_GUIDANCE_2018.pdf | official_guidance (UK), non_binding | exact, pág 8 | PASS | INHERITED 2026-07-16 | COVERED |
| ALCOA_LEGIBLE | ídem | ídem | exact, pág 8 | PASS | INHERITED 2026-07-16 | COVERED |
| ALCOA_CONTEMPORANEOUS | ídem | ídem | normalized, pág 5 | PASS | INHERITED 2026-07-16 | COVERED |
| ALCOA_ORIGINAL | ídem | ídem | exact, pág 8 | PASS | INHERITED 2026-07-16 | COVERED |
| ALCOA_ACCURATE | ídem | ídem | exact, pág 4 | PASS | INHERITED 2026-07-16 | COVERED |
| ALCOA_COMPLETE | ídem | ídem | normalized, pág 4 | PASS | INHERITED 2026-07-16 | COVERED |
| ALCOA_CONSISTENT | ídem | ídem | exact, pág 8 | PASS | INHERITED 2026-07-16 | COVERED |
| ALCOA_ENDURING | ídem | ídem | exact, pág 5 | PASS | INHERITED 2026-07-16 | COVERED |
| ALCOA_AVAILABLE | ídem | ídem | exact, pág 8 | PASS | INHERITED 2026-07-16 | COVERED |

**16/19 `COVERED`, 3/19 `NEEDS_REVISION`** (causa raíz real y documentada,
no ambigüedad de fuente).

## Checkpoint D1 — Preguntas para ti antes de Fase 5.2

1. ¿Autorizas copiar (con manifiesto de procedencia) los 3 archivos
   oficiales a una ruta trackeada dentro de `factory/regulatory/
   requirement_catalog/`, o prefieres mantener la referencia cruzada al
   workspace gitignorado de `lab_qc_project`?
2. Para los 3 `NEEDS_REVISION`: ¿autorizas que pruebe re-extracción con
   `pdfplumber` (ya instalado, sin dependencia nueva) para confirmar si
   resuelve el artefacto de espaciado?
3. ¿`official_origin_status`/`regulatory_currency_status` quedan como
   `INHERITED` (heredados de la verificación de 2026-07-06/07-16) para
   Fase 5.2, o quieres que re-verifique alguno contra la fuente oficial
   en internet antes de construir `requirements.yaml` definitivo? (Esto
   requeriría acceso a internet, no usado en este inventario.)
4. ¿Confirmas los parámetros de persistencia de `_by_req_candidates`
   (control #7) para que queden fijados antes de Fase 5.4, o hay algo que
   ajustar?

No avanzo a Fase 5.2 (construcción de `requirements.yaml` definitivo) sin
tu confirmación.
