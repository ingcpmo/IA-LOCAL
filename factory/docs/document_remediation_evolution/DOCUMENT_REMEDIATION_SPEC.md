# DOCUMENT_REMEDIATION_SPEC — Especificación de generación de documento completo

Diseño únicamente. Cierra el hallazgo NOT_VALIDATED más importante de
`CURRENT_STATE_AUDIT.md` §6: hoy no existe ninguna capacidad que genere una
copia completa y versionada del documento original — solo un memo de
remediación independiente (`gmpai_docx_draft.py`) y, en los 2 paquetes
reales de esta sesión, un extracto Markdown de 446–1498 bytes que el propio
objetivo del usuario excluye explícitamente como "documento candidato
completo".

## 1. Invariante no negociable: el original nunca se toca

Ya vigente en todo el sistema auditado (`gmpai_docx_draft.py`: *"Nunca toca
los originales en GMPAI/source/"*; `remediation_package_schemas.py`:
`document_role` distingue `SOURCE_DOCUMENT` de `CANDIDATE_DOCUMENT`). Se
conserva sin cambios: `source_document` sigue siendo `classification:
SOURCE_IMMUTABLE`, referenciado por ruta+hash, nunca copiado con
modificaciones.

## 2. De dónde sale el documento candidato completo (fuente única gobernada)

```
source_document (PDF/DOCX real, inmutable, hash verificado)
        │
        ▼
  extracción estructurada por página/sección
  (YA EXISTE: pdfplumber, mismo extractor que sources/registry.json
   ya usa para las 3 fuentes regulatorias — reutilizar, no reinventar)
        │
        ▼
  representación intermedia con estructura preservada:
  { secciones: [{numero, titulo, paginas, parrafos: [...]}], ... }
  (NUEVO — no existe hoy; chunked_engine.py trabaja sobre
   ExtractionResult.per_unit_text, texto plano por página, sin
   jerarquía de secciones/numeración explícita)
        │
        ▼
  aplicación de N RemediationChange (ya validados, ya existen)
  sobre la representación intermedia, por document_location/
  citation_locator — inserción/reemplazo localizado, nunca reescritura
  global del documento
        │
        ▼
  documento candidato completo (mismo formato que el original —
  DOCX si el original es DOCX, con numeración/estilos preservados
  vía python-docx, mismo patrón ya usado y validado en
  gmpai_docx_draft.py para estilos/RGBColor/Pt, pero aplicado a una
  copia completa, no a un memo aparte)
```

**Esto es diseño, no implementación.** El componente nuevo es la
"representación intermedia con estructura preservada" — hoy no existe
ningún extractor que preserve jerarquía de secciones/numeración en el
pipeline de `chunked_engine.py` (que deliberadamente aplana todo a texto por
chunk para el LLM, correcto para análisis, insuficiente para regeneración).

## 3. Redline completo (diseño)

Un redline real (no el resumen de 2 líneas usado en los paquetes reales de
esta sesión) debe operar sobre la representación intermedia de §2, marcando:
- Texto **sin cambios**: idéntico al original, para contexto de lectura.
- Texto **insertado**: el `proposed_content` de cada `RemediationChange`
  aplicado, en la ubicación exacta de `citation_locator`.
- Texto **eliminado/reemplazado**: solo si `change_type=CONTENT_REPLACEMENT`
  (ya existe en el schema, nunca usado todavía en los 3 casos reales — los 3
  fueron `CONTENT_ADDITION`).

Formato: mismo patrón `python-docx` con `RGBColor` ya usado en
`gmpai_docx_draft.py` (verde/rojo por tipo de cambio), pero sobre la copia
completa, no sobre un memo.

## 4. Manifest y matriz de trazabilidad (extensión de lo ya existente)

`ArtifactReference` (schema real, `remediation_package_schemas.py`) ya
cubre `package_manifest` como clasificación de artefacto — se mantiene sin
cambios de schema. Lo que se añade es **contenido real** del manifest: hoy
(en los 2 paquetes reales) el manifest es una lista plana de rutas+hashes;
el diseño objetivo agrega la matriz de trazabilidad completa:

```
requisito → evidencia → hallazgo → gap_o_desviacion → recomendacion →
cambio (change_id) → ubicacion_en_candidato (offset real dentro del DOCX
generado, no solo citation_locator del documento fuente) → resultado_de_
revalidacion (ver §5)
```

Esta matriz es el mismo modelo de `GAP_AND_DEVIATION_MODEL.md` §3,
serializado como artefacto versionado adicional (`classification: MANIFEST`
o una clasificación nueva `TRACEABILITY_MATRIX` — decisión de diseño para
`IMPLEMENTATION_ROADMAP.md`, no zanjada aquí).

## 5. Revalidación (diseño de los 3 chequeos separados que exige el objetivo)

```
DOCUMENT_CONFORMANCE:
  verificación AUTOMATIZABLE — el texto insertado en el candidato (§2/§3)
  coincide byte a byte con proposed_content del RemediationChange
  correspondiente, en la ubicación declarada. Falla → CHANGE_NOT_APPLIED.

IMPLEMENTATION_VERIFICATION:
  NUNCA automatizable por este sistema — requiere evidencia externa
  (protocolo IQ/OQ/PQ, prueba real). El sistema solo puede registrar
  "evidencia de implementación todavía requerida" (campo que ya exige
  el objetivo del usuario en la reseña final, §6) — nunca puede
  marcarla como satisfecha por sí mismo.

REGULATORY_COMPLIANCE:
  SIEMPRE humana. Ya protegido por diseño vigente: create_release_record()
  sin endpoint expuesto, PRODUCTION_ENABLEMENT=BLOCKED. Este documento no
  propone tocar esa barrera — la reafirma.
```

## 6. Reseña de cambios y fundamento regulatorio (diseño de la sección final)

Sección nueva a incorporar al final del documento candidato completo. Cada
fila usa exclusivamente campos que **ya existen** en el `RemediationChange`
real y en la matriz de §4 — no requiere inventar datos nuevos:

```
| ID (change_id) | Sección modificada (document_location) |
  Hallazgo (evidencia_encontrada) | Gap o desviación (clasificación §1 de
  GAP_AND_DEVIATION_MODEL.md) | Cambio realizado (proposed_content) |
  Motivo (change_reason) | Regulación y numeral (regulatory_catalog_entry_id
  + citation.section_page_paragraph) | Enlace oficial (official_source_url,
  con REGULATORY_SOURCE_UNVERIFIED si aplica) | Estado de validación
  (DOCUMENT_CONFORMANCE de §5) | Evidencia de implementación todavía
  requerida (texto fijo: nunca se marca como resuelta por el sistema) |
```

Texto de cierre obligatorio de la sección (invariante, no editable por el
sistema): una declaración explícita de que los cambios documentales no
garantizan por sí solos cumplimiento final — mismo principio que ya aplica
`dossier_generator_service.py` ("SIN VALOR REGULATORIO" en cada borrador) y
`gmpai_docx_draft.py` ("NO se marca automáticamente como compliant").

## 7. Qué se reutiliza vs. qué es nuevo (resumen)

| Pieza | Estado |
|---|---|
| `RemediationChange` (contenido del cambio) | REUTILIZA — sin cambios |
| Reglas deterministas de mapeo finding→change | REUTILIZA `gap_assessment_finding_mapper.py`, con la unificación de §6 de `TARGET_REGULATORY_ARCHITECTURE.md` |
| Extracción de texto por página | REUTILIZA `pdfplumber`, ya usado en `sources/registry.json` |
| Representación intermedia con estructura/numeración | **NUEVO** — no existe |
| Generación de DOCX con estilos preservados | REUTILIZA el patrón `python-docx` de `gmpai_docx_draft.py`, aplicado a copia completa en vez de memo |
| Redline real (no resumen) | **NUEVO** — no existe |
| Matriz de trazabilidad requisito→revalidación | **NUEVO** — no existe como artefacto, aunque el modelo de datos ya existe disperso |
| Reseña de cambios y fundamento regulatorio | **NUEVO** — no existe |
| `DOCUMENT_CONFORMANCE` automatizado | **NUEVO** — hoy se verificó a mano vía scripts ad hoc en esta sesión |
| `IMPLEMENTATION_VERIFICATION` / `REGULATORY_COMPLIANCE` | Permanecen fuera del sistema por diseño, sin cambio |
