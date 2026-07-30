# VDR-GMPAI-001 — Version Decision Record

Fuente estructurada: `gmpai_version_decision_record.json` (mismo contenido, sin
parsear markdown). Cubre las 2 familias Rockwell marcadas `version_conflict`
por `version_selection.py` dentro de los 5 documentos `REANALYSIS_REQUIRED`.

## 1. FS_v1.2.pdf vs FS_v1.2-2.pdf

- **SHA-256 idéntico** en ambos archivos (`56095a75...82eb`, 578,088 bytes) —
  no son versiones distintas, son el **mismo archivo duplicado** con dos
  nombres.
- Corroborado por el transmittal `215115305-T-039 Design Docs for
  ASantiago.pdf` (ver abajo), que lista `FS_v1.2.pdf` (sin sufijo) como el
  documento oficialmente transmitido.
- **Versión seleccionada:** `FS_v1.2.pdf`. `-2` queda marcado como duplicado
  bit-idéntico, no como versión superada.
- **version_conflict: false** (corregido — el conflicto original era un falso
  positivo de `version_selection.py`, que no deduplica por hash antes de
  declarar empate). Confianza: alta. Sin necesidad de decisión humana sobre
  cuál analizar.

## 2. T-039 Design Docs — .docm vs .pdf

- El `.pdf` (3 páginas, 5,591 chars) **no es "Design Docs"**: es un
  **TRANSMITTAL** (MAVERICK/215115305/039, 2023-03-27) — portada de envío con
  firmas y sección de aprobación. Se autoidentifica como tal en su propio
  texto.
- El `.docm` (194 páginas, 3,786 chars, contiene `vbaProject.bin` + ActiveX +
  >10 imágenes WMF/PNG/JPG embebidas — **no se ejecutaron macros**) es
  consistente con un paquete de planos/CAD exportado, no con el mismo tipo de
  contenido que el `.pdf`.
- **No es un conflicto de versión real** — es un **error de agrupamiento**
  (`FAMILY_GROUPING_ERROR`): ambos archivos comparten base de nombre pero son
  documentos distintos.
- **Acción recomendada:** reclasificar el `.pdf` de `DS` a `TRANSMITTAL`
  (cambia su aplicabilidad a `NO_APPLICABLE_CORRECTION` — Part11/Annex11/
  ALCOA+ no aplican a una portada de transmisión). El `.docm` sigue
  `OCR_OR_EXTRACTION_REQUIRED` (ver evidence_request, sección 5 del encargo).
- **revision_humana_requerida: true** — confirmar con Cesar la reclasificación
  antes de excluirlo del reanálisis de los 5.
