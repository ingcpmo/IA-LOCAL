# FRS — Functional Requirements Specification

> **BORRADOR GENERADO POR LA FACTORY — sin valor regulatorio hasta revisión y aprobación humana.**
> Revisión humana: verifique cada afirmación contra la fuente citada antes de aprobar; las secciones "SIN EVIDENCIA" requieren aporte humano previo.
> Misión: `gmpai_document_validation` · Generado: 2026-08-04T02:03:26Z · Por: CESAR

## Funciones por agente

**doc_inventory_version_agent** (agente nuevo): Inventario recursivo, verificación SHA-256 contra manifiesto y selección de versión vigente (revisión/fecha/semver, con marcado de version_conflict ante ambigüedad) es una capacidad determinista de co
**doc_classification_agent** (agente nuevo): Clasificar documentos de ingeniería OT (URS/FS/DS/arquitectura/narrativa de control/listado de alarmas/protocolo/SAT/reporte) requiere heurísticas sobre estructura, nombre y metadatos del archivo — no
**fda_part11_agent** (perfil de integrity): El agente base integrity ya cubre ALCOA+, audit trail y 21 CFR Part 11 al ~70-75%. El delta especializa el contexto a registros/firmas electrónicas generados por sistemas OT (PLC/SCADA/HMI) en vez de 
**eu_annex11_agent** (perfil de integrity): Annex 11 comparte con Part 11/ALCOA+ el dominio de integridad de registros electrónicos y controles de sistemas computarizados (~70% de cobertura común). El delta cubre los clausulados propios de EU G
**alcoa_plus_agent** (agente nuevo): La evaluación de los 9 atributos ALCOA+ es la capacidad central ya descrita del agente base integrity ('ALCOA+ attribute assessment'). Se hereda directamente sin adaptación — crear un perfil aquí dupl
**requirements_traceability_agent** (perfil de csv): El agente base csv ya cubre IQ/OQ/PQ y clasificación GAMP5 (~70%). El delta añade trazabilidad explícita URS→FS→DS→IQ→OQ→PQ para documentación OT Rockwell/SCADA: verifica que cada requisito de URS ten
**compliance_risk_agent** (agente nuevo): Consolidar hallazgos de los demás agentes en una matriz de riesgo (severidad × probabilidad × detectabilidad) y priorizar brechas es una función de síntesis cruzada entre agentes, no una conversación 
**final_review_agent** (agente nuevo): El agente de revisión final consolida todos los hallazgos, aplica el gate de gobierno (no declarar cumplimiento GMP final ni aprobar documentos automáticamente) y prepara el paquete para decisión huma

*Fuente: designs/·/agent_design_proposal.yaml*

## Matriz FRS — funciones esperadas verificables (catálogo curado W4)

**SIN EVIDENCIA — requiere aporte humano**

## Endpoints funcionales cubiertos por el catálogo W4

**SIN EVIDENCIA — requiere aporte humano**
