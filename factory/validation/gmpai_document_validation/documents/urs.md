# URS — User Requirements Specification

> **BORRADOR GENERADO POR LA FACTORY — sin valor regulatorio hasta revisión y aprobación humana.**
> Revisión humana: verifique cada afirmación contra la fuente citada antes de aprobar; las secciones "SIN EVIDENCIA" requieren aporte humano previo.
> Misión: `gmpai_document_validation` · Generado: 2026-08-04T02:03:26Z · Por: CESAR

## Requisito de usuario principal (URS-01, verbatim)

**URS-01 — requisito principal (verbatim de la misión):**

Analizar los 32 documentos de Rockwell y SCADA (URS, FS, DS, arquitectura, listados de alarmas, narrativas de control, protocolos SAT y documentacion de red/CSV), inventariarlos y verificarlos contra SHA256SUMS.txt, seleccionar las versiones vigentes ante posibles conflictos, crear agentes especializados, y determinar si la documentacion esta completa, trazable (URS-FS-DS-IQ-OQ-PQ) y alineada con FDA 21 CFR Part 11, EU GMP Annex 11 y principios ALCOA+, generando matrices de cumplimiento, evaluacion de riesgos y brechas con evidencia trazable a pagina/seccion de cada documento fuente. El sistema no declara cumplimiento GMP final ni aprueba documentos automaticamente: produce hallazgos para revision y decision humana (accept/reject/request_changes).

Cliente: pharma_mfg_site

*Fuente: layer9/missions/gmpai_document_validation.yaml*

## Alcance regulatorio declarado

- 21_CFR_PART_11
- EU_GMP_ANNEX_11
- ALCOA_PLUS

*Fuente: misión · regulatory_scope*

## Restricciones/acciones declaradas en la misión (verbatim)

Declaradas en la misión (verbatim). Pueden ser requisitos de usuario o acciones autorizadas del pipeline; su clasificación como URS formales requiere juicio QA:
- no inventar texto regulatorio — toda fuente no disponible queda como PENDING_DOCUMENT
- no tocar producto base (gmp-api puerto 8000)
- no modificar, eliminar ni sobrescribir los originales en GMPAI/source/
- no ejecutar macros de archivos .docm
- workspace confinado a /home/ing_cpmo/factory/workspaces/gmpai_document_validation/
- sin Docker — analisis documental puro, sin despliegue de contenedor
- trazabilidad completa via factory_audit.jsonl (21 CFR Part 11)
- no guardar credenciales ni tokens en codigo ni en git
- no usar --dangerously-skip-permissions
- ausencia de evidencia se clasifica como evidencia insuficiente, nunca como cumplimiento
- el sistema no puede declarar cumplimiento GMP final ni aprobar documentos automaticamente

*Fuente: misión · constraints*

## Documentos regulatorios requeridos por la misión

- Rockwell/215115305 MCCPDC PLC Panel Rev 0 09-07-22.pdf: available
- Rockwell/215115305 MCCPDC SCADA-PCS Misc PLC SI Prop for MCCPDCa.pdf: available
- Rockwell/215115305 SCADA-PCS Misc PLC SAT3 Scanned-1.pdf: available
- Rockwell/215115305 SCADA-PCS Misc PLC System FS_v1.2-2.pdf: available
- Rockwell/215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf: available
- Rockwell/215115305 SCADA-PCS Misc PLC System URS v2.1.pdf: available
- Rockwell/215115305-T-039 Design Docs for ASantiago.docm: available
- Rockwell/215115305-T-039 Design Docs for ASantiago.pdf: available
- Rockwell/215115305-T-041 SAT3 Completed.pdf: available
- Rockwell/215115305_SYS_ARCH_10-11-2022.pdf: available
- Rockwell/MCCPDC EMS Control Block Narrative revB.pdf: available
- Rockwell/MCCPDC PCS Signal Interface Control Block Narrative.pdf: available
- Rockwell/MCCPDC PCS-CP01 Alarms Hard Soft IO Listing revH.xlsx: available
- Rockwell/MCCPDC WFI Control Block Narrative revB.pdf: available
- SCADA/ASDATA/10.docx: available
- SCADA/ASDATA/Autoclave URS V2.docx: available
- SCADA/ASDATA/CSV GAP Assessment Jul2023.xlsx: available
- SCADA/ASDATA/CSV-Template.docx: available
- SCADA/ASDATA/Copy of Mark Cuban Cost Plus Drug Company PBC 3 WEEKS Quote 002.xlsx: available
- SCADA/ASDATA/Copy of Network Integration Status_.xlsx: available
- SCADA/ASDATA/Copy of scada inventory.xlsx: available
- SCADA/ASDATA/Cost Plus Drugs Network and Validation Readiness Assessment.doc: available
- SCADA/ASDATA/Downflow Booth URS 13oct2022 V2.docx: available
- SCADA/ASDATA/Formulation Tanks URS.docx: available
- SCADA/ASDATA/MCCPDC CSV Documentation Needs AS_v1.docx: available
- SCADA/ASDATA/Operations Readiness.pptx: available
- SCADA/ASDATA/Process Equipment_Open Items.xlsx: available
- SCADA/ASDATA/Task Items1.xlsx: available
- SCADA/ASDATA/Unidirectional Ceiling Modules URS 13OCT2022 V2.docx: available
- SCADA/ASDATA/Vial Labeler URS.docx: available
- SCADA/ETG_ET_[System Name]_IQ w appendices.pdf: available
- SCADA/IP Addresses for SA25.pdf: available

*Fuente: misión · documents*

## Descomposición en URS individuales verificables (juicio QA)

**SIN EVIDENCIA — requiere aporte humano**
