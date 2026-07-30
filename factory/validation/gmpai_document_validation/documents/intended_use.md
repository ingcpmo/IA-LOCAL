# Intended Use

> **BORRADOR GENERADO POR LA FACTORY — sin valor regulatorio hasta revisión y aprobación humana.**
> Revisión humana: verifique cada afirmación contra la fuente citada antes de aprobar; las secciones "SIN EVIDENCIA" requieren aporte humano previo.
> Misión: `gmpai_document_validation` · Generado: 2026-07-29T12:46:47Z · Por: cesar

## Uso previsto declarado en la misión

**URS-01 — requisito principal (verbatim de la misión):**

Analizar los 32 documentos de Rockwell y SCADA (URS, FS, DS, arquitectura, listados de alarmas, narrativas de control, protocolos SAT y documentacion de red/CSV), inventariarlos y verificarlos contra SHA256SUMS.txt, seleccionar las versiones vigentes ante posibles conflictos, crear agentes especializados, y determinar si la documentacion esta completa, trazable (URS-FS-DS-IQ-OQ-PQ) y alineada con FDA 21 CFR Part 11, EU GMP Annex 11 y principios ALCOA+, generando matrices de cumplimiento, evaluacion de riesgos y brechas con evidencia trazable a pagina/seccion de cada documento fuente. El sistema no declara cumplimiento GMP final ni aprueba documentos automaticamente: produce hallazgos para revision y decision humana (accept/reject/request_changes).

Cliente: pharma_mfg_site

*Fuente: layer9/missions/gmpai_document_validation.yaml*

## Contexto regulatorio

- 21_CFR_PART_11
- EU_GMP_ANNEX_11
- ALCOA_PLUS

*Fuente: misión · regulatory_scope*

## Límites de uso (constraints)

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

## Evaluación de idoneidad del uso previsto (juicio QA)

**SIN EVIDENCIA — requiere aporte humano**
