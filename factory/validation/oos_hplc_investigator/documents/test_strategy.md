# Test Strategy

> **BORRADOR GENERADO POR LA FACTORY — sin valor regulatorio hasta revisión y aprobación humana.**
> Revisión humana: verifique cada afirmación contra la fuente citada antes de aprobar; las secciones "SIN EVIDENCIA" requieren aporte humano previo.
> Misión: `oos_hplc_investigator` · Generado: 2026-07-03T14:37:48Z · Por: Cesar

## Catálogo curado de pruebas funcionales (W4)

- Versión del catálogo: 1.0
- Deployment objetivo: http://localhost:8102
- Casos curados: 10 en 3 agentes

*Fuente: test_catalogs/oos_hplc_investigator.yaml*

## Cobertura de endpoints

- POST /api/v1/audit/alcoa/validate
- POST /api/v1/audit/stamp
- POST /api/v1/hplc/peaks/anomalies
- POST /api/v1/hplc/rsd
- POST /api/v1/hplc/sst/validate
- POST /api/v1/oos/records

*Fuente: test_catalogs/oos_hplc_investigator.yaml*

## Resultados de construcción (workspace)

- Suite del workspace: 12 passed · 0 failed (returncode 0)

*Fuente: workspace · test_report.json*

## Gates de calidad del sistema

14 quality gates obligatorios previos a release + selfcheck Gate 0 (py_compile, pytest, cadena de auditoría, estado).

*Fuente: factory/scripts/ops/factory_selfcheck.sh · quality_gate_runner*

## Justificación riesgo-basada de la estrategia y exclusiones (juicio QA)

**SIN EVIDENCIA — requiere aporte humano**
