# FRS — Functional Requirements Specification

> **BORRADOR GENERADO POR LA FACTORY — sin valor regulatorio hasta revisión y aprobación humana.**
> Revisión humana: verifique cada afirmación contra la fuente citada antes de aprobar; las secciones "SIN EVIDENCIA" requieren aporte humano previo.
> Misión: `oos_hplc_investigator` · Generado: 2026-07-03T14:37:48Z · Por: Cesar

## Funciones por agente

**qa_oos_profile** (perfil de gmp_ai_copilot_base): OOS requiere vocabulario QC específico (Fase I/II, FDA OOS Guidance 2022, cálculos estadísticos). Un perfil derivado añade contexto sin redefinir flujos base.
**integrity_lims_profile** (perfil de gmp_ai_copilot_base): LIMS + Data Integrity comparten el dominio de audit trail y acceso a datos. Un perfil unificado reduce complejidad de routing y cubre ALCOA+ / Part 11 con un único agente especializado.
**hplc_data_review_agent** (agente nuevo): HPLC (SST, integración de picos, secuencias de inyección) requiere lógica de validación numérica y detección de anomalías cromatográficas no presentes en la capa base. Se crea agente nuevo con tools p

*Fuente: designs/·/agent_design_proposal.yaml*

## Matriz FRS — funciones esperadas verificables (catálogo curado W4)

| FRS | Agente | Función esperada (título curado W4) | Endpoint |
|---|---|---|---|
| FRS-01 | qa_oos_profile | Resultado dentro de especificación → no OOS | `POST /api/v1/oos/records` |
| FRS-02 | qa_oos_profile | Resultado fuera de especificación → OOS detectado | `POST /api/v1/oos/records` |
| FRS-03 | hplc_data_review_agent | SST dentro de criterios USP <621> → PASS | `POST /api/v1/hplc/sst/validate` |
| FRS-04 | hplc_data_review_agent | Platos teóricos por debajo del mínimo (2000) → SST FAIL | `POST /api/v1/hplc/sst/validate` |
| FRS-05 | hplc_data_review_agent | Pico dentro de rangos normales → 0 anomalías | `POST /api/v1/hplc/peaks/anomalies` |
| FRS-06 | hplc_data_review_agent | Área negativa → anomalía detectada | `POST /api/v1/hplc/peaks/anomalies` |
| FRS-07 | hplc_data_review_agent | %RSD sobre 4 valores sintéticos → cálculo completado (n=4) | `POST /api/v1/hplc/rsd` |
| FRS-08 | integrity_lims_profile | Los 9 atributos ALCOA+ presentes → compliant | `POST /api/v1/audit/alcoa/validate` |
| FRS-09 | integrity_lims_profile | Atributos 'consistent' y 'enduring' ausentes → no compliant | `POST /api/v1/audit/alcoa/validate` |
| FRS-10 | integrity_lims_profile | Sello de auditoría sobre registro completo → ALCOA validado embebido | `POST /api/v1/audit/stamp` |

*Fuente: test_catalogs/oos_hplc_investigator.yaml (catálogo curado W4)*

## Endpoints funcionales cubiertos por el catálogo W4

- POST /api/v1/audit/alcoa/validate
- POST /api/v1/audit/stamp
- POST /api/v1/hplc/peaks/anomalies
- POST /api/v1/hplc/rsd
- POST /api/v1/hplc/sst/validate
- POST /api/v1/oos/records

*Fuente: test_catalogs/oos_hplc_investigator.yaml*
