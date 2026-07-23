# ROCKWELL_SOURCE_INVENTORY_AND_SCOPE_SPEC

Reconocimiento de solo lectura ejecutado el 2026-07-23 sobre
`/home/ing_cpmo/GMPAI/source/Rockwell/`. Ningún archivo fue modificado,
movido ni escrito. Preview de hashes en `/tmp/rockwell_sha_preview.txt`
(fuera del repo, no persistido en `factory/`).

## 1. Totales

- **Total de archivos**: 14
- **Extensiones**: `.pdf` × 12, `.xlsx` × 1, `.docm` × 1
- **Duplicado exacto por SHA-256 confirmado**: `215115305 SCADA-PCS Misc PLC
  System FS_v1.2.pdf` y `215115305 SCADA-PCS Misc PLC System FS_v1.2-2.pdf`
  (mismo hash `56095a75...b82eb`, mismo tamaño 578088 bytes).
- **Formatos que requerirán OCR**: `215115305 SCADA-PCS Misc PLC SAT3
  Scanned-1.pdf` (136.8 MB, nombre indica "Scanned" — candidato casi seguro
  a imagen escaneada sin capa de texto; confirmar extracción real en Fase A,
  no asumido aquí).
- **Presencia de DOCM**: sí, `215115305-T-039 Design Docs for ASantiago.docm`
  — coexiste con una versión `.pdf` del mismo nombre base con hash distinto
  (no duplicado exacto; contenido a comparar, no ejecutar macros).

## 2. Listado completo (ruta relativa a `source/Rockwell/`, tamaño, SHA-256)

| # | Archivo | Tamaño (bytes) | SHA-256 |
|---|---|---|---|
| 1 | `215115305 MCCPDC PLC Panel Rev 0 09-07-22.pdf` | 2,980,690 | `dc733c64...fea15c71`* |
| 2 | `215115305 MCCPDC SCADA-PCS Misc PLC SI Prop for MCCPDCa.pdf` | 1,428,303 | `910e384d...955060c3` |
| 3 | `215115305 SCADA-PCS Misc PLC SAT3 Scanned-1.pdf` | 136,863,151 | `e96f67f7...091546371e2` |
| 4 | `215115305 SCADA-PCS Misc PLC System FS_v1.2-2.pdf` | 578,088 | `56095a75...9debc82eb` (DUP) |
| 5 | `215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf` | 578,088 | `56095a75...9debc82eb` (DUP) |
| 6 | `215115305 SCADA-PCS Misc PLC System URS v2.1.pdf` | 307,047 | `d9e24467...4a433c40c9` |
| 7 | `215115305-T-039 Design Docs for ASantiago.docm` | 155,571 | `12f6d2bb...480e1baa8767` |
| 8 | `215115305-T-039 Design Docs for ASantiago.pdf` | 291,392 | `84e7b4db...81af7f397f6d` |
| 9 | `215115305-T-041 SAT3 Completed.pdf` | 310,387 | `2edb00a3...79b0cb93e58e` |
| 10 | `215115305_SYS_ARCH_10-11-2022.pdf` | 444,781 | `3926e352...ffddb446c64f` |
| 11 | `MCCPDC EMS Control Block Narrative revB.pdf` | 344,955 | `13bc6f50...80aecac12eff` |
| 12 | `MCCPDC PCS Signal Interface Control Block Narrative.pdf` | 356,020 | `de7b70c2...97fc663b85fe` |
| 13 | `MCCPDC PCS-CP01 Alarms Hard Soft IO Listing revH.xlsx` | 164,757 | `20d75130...579c037be68f` |
| 14 | `MCCPDC WFI Control Block Narrative revB.pdf` | 316,734 | `8a67414d...f049b07ebe07` |

(*hashes truncados en tabla por legibilidad; hash completo disponible en
`/tmp/rockwell_sha_preview.txt` de esta corrida — no forma parte de los
entregables persistidos).

## 3. Clasificación preliminar de allowlist (propuesta, NO creada como YAML en esta corrida)

| file_id | doc_type propuesto | origin_class | duplicate_of | extraction_capability estimada | processing_state propuesto |
|---|---|---|---|---|---|
| RW-0001 | DRAWING (PLC Panel) | ORIGINAL | null | TEXT_NATIVE (a confirmar) | ORIGINAL_SOURCE_UNCONFIRMED |
| RW-0002 | PROPOSAL/OTHER | ORIGINAL | null | TEXT_NATIVE (a confirmar) | ORIGINAL_SOURCE_UNCONFIRMED |
| RW-0003 | REPORT (SAT escaneado) | ORIGINAL | null | OCR_REQUIRED (nombre "Scanned") | OCR_REQUIRED |
| RW-0004 | FS | ORIGINAL | RW-0005 (mismo hash) | TEXT_NATIVE (a confirmar) | DUPLICATE |
| RW-0005 | FS | ORIGINAL | RW-0004 (mismo hash) | TEXT_NATIVE (a confirmar) | DUPLICATE — requiere decisión humana de cuál es el file_id canónico |
| RW-0006 | URS | ORIGINAL | null | TEXT_NATIVE (a confirmar) | ORIGINAL_SOURCE_UNCONFIRMED |
| RW-0007 | OTHER (DOCM, diseño) | ORIGINAL | null | NOT_EXTRACTABLE sin ejecutar macro (prohibido); requiere método seguro de extracción sin macros | PROCESSING_BLOCKED hasta definir método |
| RW-0008 | OTHER (mismo doc que RW-0007 en PDF) | ORIGINAL o DERIVED — hash distinto de RW-0007, requiere confirmación de procedencia | null (no es duplicado exacto de RW-0007) | TEXT_NATIVE (a confirmar) | HUMAN_REVIEW_REQUIRED (relación con RW-0007 no determinada solo por nombre) |
| RW-0009 | PROTOCOL/REPORT (SAT completado) | ORIGINAL | null | TEXT_NATIVE (a confirmar) | ORIGINAL_SOURCE_UNCONFIRMED |
| RW-0010 | DS/ARCHITECTURE | ORIGINAL | null | TEXT_NATIVE (a confirmar) | ORIGINAL_SOURCE_UNCONFIRMED |
| RW-0011 | DS (narrativa de control) | ORIGINAL | null | TEXT_NATIVE (a confirmar) | ORIGINAL_SOURCE_UNCONFIRMED |
| RW-0012 | DS (narrativa de control) | ORIGINAL | null | TEXT_NATIVE (a confirmar) | ORIGINAL_SOURCE_UNCONFIRMED |
| RW-0013 | OTHER (listado I/O, XLSX) | ORIGINAL | null | TEXT_NATIVE (estructurado) | ORIGINAL_SOURCE_UNCONFIRMED |
| RW-0014 | DS (narrativa de control) | ORIGINAL | null | TEXT_NATIVE (a confirmar) | ORIGINAL_SOURCE_UNCONFIRMED |

Nota: `doc_type`, `extraction_capability` y `processing_state` reales deben
confirmarse en Fase A leyendo cada archivo (no asumidos por nombre). Esta
tabla es una hipótesis de trabajo, no la allowlist cerrada.

## 4. Regla determinista de cobertura (para Fase A)

Test obligatorio en implementación: `count(find source/Rockwell/) ==
count(allowlist)`. Con 14 archivos reales, cualquier allowlist futura con
≠14 entradas terminales debe fallar el gate. RW-0004/RW-0005 cuentan como 2
entradas (una `DUPLICATE`, no se colapsan a 1).

## 5. Formato de allowlist propuesto (no creado en esta corrida)

Ruta futura: `factory/regulatory/scope/source_baseline_allowlist.yaml`, con
el schema exacto de la sección 9 del plan de instrucciones (`file_id`,
`path`, `sha256`, `doc_type`, `origin_class`, `duplicate_of`,
`extraction_capability`, `processing_state`, `applicability`,
`related_requirements`, `justification`).

## 6. Riesgos identificados en esta corrida

- El archivo "Scanned" de 136.8 MB puede requerir OCR costoso y bloquear
  performance si se procesa completo por chunk × requisito sin filtros
  deterministas previos (ver PERFORMANCE_AND_INFERENCE_ORCHESTRATION_SPEC.md).
- El DOCM no puede procesarse por macro (prohibido). Se requiere decidir
  método seguro de extracción de texto (p.ej. librería que lea XML de Office
  sin ejecutar VBA) antes de Fase A.
- RW-0007/RW-0008 (mismo nombre base, hashes distintos) requieren
  HUMAN_REVIEW_REQUIRED explícito — no asumir automáticamente cuál es la
  fuente autorizada.
