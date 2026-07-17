# W5.3 — Fase 5.2: catálogo atómico de requisitos + validación cruzada

Fecha: 2026-07-17. Estado: **sin commit** (pendiente tu revisión).
`run_context=validation` en todo el catálogo. `PRODUCTION_ENABLEMENT`
sigue **BLOCKED**.

## regulatory_currency_status — confirmado, sin cambios

Las 3 fuentes mantienen `regulatory_currency_status=pending_reverification`
(enum del schema `source_registry_entry_v1.json` restringido a ese único
valor — `"verified_current"`/`"current"` no son valores válidos, el schema
lo rechazaría). `requirements.yaml` incluye un `regulatory_currency_disclaimer`
explícito al tope del archivo. Ninguna fuente se presenta como vigente
verificada en ningún artefacto de esta fase.

## Arquitectura construida

```
factory/regulatory/
├── sources/
│   ├── registry.json                     [enriquecido v1.1: + derived_artifacts]
│   ├── sha256/<hash>/OFFICIAL_*.{txt,pdf}  [copias inmutables, subfase 5.1.1]
│   └── derived/<hash>/pdfplumber_extraction_v1.json
├── requirement_catalog/
│   ├── requirements.yaml                 [NUEVO -- catálogo definitivo, 19/19]
│   ├── requirement_catalog_loader.py     [NUEVO -- fail-closed + validación cruzada]
│   ├── citation_locator.py               [subfase 5.1.1]
│   └── inventory_draft_v1.json / v2_pdfplumber.json  [borradores, conservados]
├── schemas/
│   ├── source_registry_entry_v1.json     [NUEVO]
│   └── requirement_catalog_entry_v1.json [NUEVO]
├── validation_evidence_writer.py         [NUEVO -- control #7 formalizado]
└── tools/run_validation_evidence.py      [Fase 5.0]

factory/core/path_policy.py                [MODIFICADO -- resolve_validation_evidence()]
```

## requirements.yaml — fila por fila (19/19)

| requirement_id | source_id | match_type | section/page/paragraph | review_status |
|---|---|---|---|---|
| 21_CFR_11.10(a) | ecfr_21cfr_part11 | exact | § 11.10, paragraph (a) | **covered** |
| 21_CFR_11.10(d) | ecfr_21cfr_part11 | exact | § 11.10, paragraph (d) | **covered** |
| 21_CFR_11.10(e) | ecfr_21cfr_part11 | exact | § 11.10, paragraph (e) | **covered** |
| 21_CFR_11.10(g) | ecfr_21cfr_part11 | exact | § 11.10, paragraph (g) | **covered** |
| 21_CFR_11.50_11.70 | ecfr_21cfr_part11 | exact | § 11.50, paragraph (a)(1) | **covered** |
| ANNEX11_4 | eu_gmp_annex11 | exact | Section 4 (Validation), 4.1 | **covered** |
| ANNEX11_7.1 | eu_gmp_annex11 | exact | Section 7 (Data Storage), 7.1 | **covered** |
| ANNEX11_9 | eu_gmp_annex11 | exact | Section 9 (Audit Trails) | **covered** |
| ANNEX11_12 | eu_gmp_annex11 | exact | Section 12 (Security), 12.1 | **covered** |
| ANNEX11_17 | eu_gmp_annex11 | exact | Section 17 (Archiving) | **covered** |
| ALCOA_ATTRIBUTABLE | mhra_gxp_di_guidance_2018 | exact | p.8, ALCOA definitions | **covered** |
| ALCOA_LEGIBLE | mhra_gxp_di_guidance_2018 | exact | p.8, ALCOA definitions | **covered** |
| ALCOA_CONTEMPORANEOUS | mhra_gxp_di_guidance_2018 | normalized | p.5, ALCOA acronym | **covered** |
| ALCOA_ORIGINAL | mhra_gxp_di_guidance_2018 | exact | p.8, ALCOA definitions | **covered** |
| ALCOA_ACCURATE | mhra_gxp_di_guidance_2018 | exact | p.4, ALCOA acronym | **covered** |
| ALCOA_COMPLETE | mhra_gxp_di_guidance_2018 | normalized | p.4, ALCOA+ intro | **covered** |
| ALCOA_CONSISTENT | mhra_gxp_di_guidance_2018 | exact | p.8, ALCOA+ definitions | **covered** |
| ALCOA_ENDURING | mhra_gxp_di_guidance_2018 | exact | p.5, ALCOA+ intro | **covered** |
| ALCOA_AVAILABLE | mhra_gxp_di_guidance_2018 | exact | p.8, ALCOA+ definitions | **covered** |

Cada fila incluye además (no repetido en la tabla por espacio):
`normative_type`, `jurisdiction`, `binding_status`, `citation_id`,
`citation_text` completo, `match_score`, `citation_sha256` — ver
`factory/regulatory/requirement_catalog/requirements.yaml` para el archivo
íntegro.

## Validación 19/19 (fail-closed, no eyeballing)

```
ValidationSummary(total=19, covered=19, review_required=0, requirement_ids_review_required=[])
```

**Reglas fail-closed probadas, no solo declaradas** (`test_requirement_catalog_loader.py`,
12 tests):
- `review_status=covered` sin que `source_id` resuelva Y `citation.match_type`
  sea `exact`/`normalized` → `CatalogValidationError` (probado con un
  requisito sintético inválido, confirma que el loader realmente bloquea).
- `citation_sha256` recalculado y comparado — una cita editada sin
  actualizar el hash → `CatalogValidationError` (probado).
- `derived_artifact.source_sha256` que no coincide con `sha256_copy` del
  source padre → `CatalogValidationError` (probado).
- Cada entrada valida contra su JSON Schema (`additionalProperties:false`)
  antes de cualquier otra verificación.

## Referencias cruzadas

- Los 19 `requirement_id` → `source_id` resuelven en `source_registry.json`
  (3 `source_id` únicos, cross-check automático en cada carga, no solo en
  esta verificación puntual).
- Los 2 `source_id` con fuente PDF (`eu_gmp_annex11`, `mhra_gxp_di_guidance_2018`)
  → cada uno con exactamente 1 `derived_artifact` (`pdfplumber_extraction_v1.json`),
  `source_sha256` verificado igual a `sha256_copy` del padre.
- `ecfr_21cfr_part11` (texto plano) → 0 `derived_artifacts` (correcto, no
  necesita extracción — el archivo original YA es el texto).
- Ningún `citation_sha256` declarado difiere del recalculado (19/19
  verificado en carga).

## Tamaños de binarios añadidos

| Archivo | Tipo | Tamaño |
|---|---|---|
| `OFFICIAL_ECFR_21CFR_part11.txt` | texto (copia inmutable) | 16,508 B |
| `OFFICIAL_EU_GMP_ANNEX11.pdf` | PDF binario (copia inmutable) | 22,461 B |
| `OFFICIAL_MHRA_GXP_DI_GUIDANCE_2018.pdf` | PDF binario (copia inmutable) | 456,031 B |
| **Total `factory/regulatory/sources/`** (binarios + derivados + registry) | — | **604 KB** |

Sin binarios adicionales más allá de las 3 copias inmutables ya presentadas
en la subfase 5.1.1 — Fase 5.2 no agregó ningún archivo binario nuevo,
solo JSON/YAML/Python (`requirements.yaml` 12 KB, `requirement_catalog_loader.py`
8 KB, 2 schemas 4 KB c/u).

## Persistencia `_by_req_candidates` — parámetros aprobados, formalizados

`factory/core/path_policy.py::resolve_validation_evidence()` +
`factory/regulatory/validation_evidence_writer.py` (19 tests,
`test_validation_evidence_persistence.py`):

| Parámetro | Implementado y probado |
|---|---|
| Ruta autorizada por `path_policy` | `resolve_validation_evidence(run_id, base)`, regex `^w5v3-validation-[0-9a-f]{12}$`, confinado bajo `base`, extensión `.json` única — 6 casos de traversal/formato inválido probados |
| Tamaño máximo | `VALIDATION_EVIDENCE_MAX_BYTES=10_000_000`; contenido que excede → `EvidenceTooLargeError`, **cero bytes escritos** (probado) |
| Retención | Sin función de borrado/expiración expuesta — probado con introspección (`dir()` del módulo, ninguna función con `delete/purge/expire/cleanup/ttl/remove`) |
| Permisos | `0o640` al escribir, verificado con `stat.S_IMODE()` |
| Exclusión de paquetes productivos | `VALIDATION_EVIDENCE_BASE` fuera de `GMPAI/reports/` y de cualquier `paquete_final*` — probado por construcción de ruta |
| `run_id`/`document_sha256` | Ambos exigidos en el contenido escrito (doble anclaje), probado |
| Hash sin circularidad | `content_sha256` calculado sobre el payload sin auto-incluirse, mismo patrón que `package_receipt.json` (W5v2) |
| Gate de contexto | `run_context != 'validation'` → `ProductionEvidenceWriteError`, cero bytes escritos — mismo gate que `generate_controlled()` |

**No cableado en `evaluate_chunked()` todavía** — eso sigue siendo Fase
5.4, explícitamente fuera de alcance de esta fase.

## Gate 0

- Suite completa: **615 passed** (antes 584), 1 skipped (integración real
  opt-in), **60 fallos idénticos al baseline `262917e`** por nombre y
  causa (`diff` sin salida, tercera verificación consecutiva en este
  ciclo).
- Selfcheck host: `PASS=4 FAIL=0`.

## Diff (resumen — nada en producción tocado más allá de Fase 5.0)

```
 M factory/core/path_policy.py                                    (+resolve_validation_evidence)
 M factory/docs/gmpai_reanalysis/w5v2_evidence/w5v2_evidence_run.py (nota de congelamiento, Fase 5.0)
 M factory/engines/gmpai_integrity/chunked_engine.py               (Fase 5.0, sin cambios en 5.2)
 M factory/engines/gmpai_integrity/ollama_client.py                (Fase 5.0, sin cambios en 5.2)
 M factory/tests/test_*.py (4 archivos, ajustes Fase 5.0)
?? factory/docs/W5_3_FASE5_0_5_1_CIERRE.md
?? factory/docs/W5_3_FASE5_1_1_CIERRE.md
?? factory/docs/W5_3_FASE5_2_CIERRE.md                             (este documento)
?? factory/regulatory/requirement_catalog/                         (incl. requirements.yaml)
?? factory/regulatory/schemas/requirement_catalog_entry_v1.json
?? factory/regulatory/schemas/source_registry_entry_v1.json
?? factory/regulatory/sources/                                     (subfase 5.1.1)
?? factory/regulatory/tools/                                       (Fase 5.0)
?? factory/regulatory/validation_evidence_writer.py
?? factory/tests/test_requirement_catalog_loader.py
?? factory/tests/test_validation_evidence_persistence.py
```

Ningún prompt YAML de producción, ningún archivo de `chunked_engine.py`
más allá de lo ya comiteado-pendiente de Fase 5.0, ningún cambio de
infraestructura.

## Estado de producción

```
PRODUCTION_ENABLEMENT = BLOCKED
```
Sin cambios respecto a W5v2/Fase 5.0/5.1: `generate_controlled()` sigue
rechazando cualquier `run_context` distinto de `'validation'`
(`ProductionNotEnabledError`), los prompts YAML de producción no fueron
tocados, `chunked_engine.py` no consume `requirements.yaml` en ningún
punto. El catálogo de Fase 5.2 es una capa de gobierno paralela, verificada
y probada, **no conectada al camino real de análisis**.
