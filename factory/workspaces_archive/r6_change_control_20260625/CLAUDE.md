# Workspace: r6_change_control
# GMP AI Factory — Módulo de Gestión de Cambios

## Misión
Proyecto: r6_change_control
Cliente: pharma_mfg_site
Generado por: Layer 8 Orchestrator — 2026-06-15

## Objetivo
Módulo GMP de gestión de cambios: registro de change requests con audit trail ALCOA+
(21 CFR Part 11), evaluación de impacto, workflow de aprobación con CAPA vinculado,
trazabilidad completa de cambios implementados.

## Dominios
- LIMS (Laboratory Information Management)
- DATA_INTEGRITY (ALCOA+ / 21 CFR Part 11)
- CAPA (Corrective and Preventive Action)

## Agentes Diseñados (Layer 8)
- capa_inherited: hereda gmp_ai_copilot_base — cubre CAPA básico sin adaptación
- integrity_lims_profile: perfil derivado — LIMS + Data Integrity (ALCOA+ / Part 11)

## Restricciones ABSOLUTAS
- NO inventar texto regulatorio — toda fuente no disponible queda como PENDING_DOCUMENT
- NO tocar producto base (gmp-api puerto 8000), aria-* ni hotelbot-*
- Docker en puertos: API=8102, Postgres=5434, Redis=6381
- Trazabilidad completa via factory_audit.jsonl (21 CFR Part 11)
- NO guardar credenciales en código ni en git
- NO usar --dangerously-skip-permissions
- Workspace confinado a /home/ing_cpmo/factory/workspaces/r6_change_control/

## Documentos Regulatorios (PENDING_DOCUMENT)
Los siguientes documentos son OBLIGATORIOS antes de go-live pero aún no están ingestados:
- ICH Q10 Pharmaceutical Quality System → PENDING_DOCUMENT
- FDA Process Validation Guidance 2011 → PENDING_DOCUMENT
- ISPE GAMP 5 Computer System Validation → PENDING_DOCUMENT

NO afirmar cumplimiento con estos documentos en el código ni en outputs.

## API Endpoints (a implementar)
- GET /health → health check
- GET /api/v1/status → estado del módulo + corpus status
- POST /api/v1/change-request → crear change request con audit trail ALCOA+
- GET /api/v1/change-request/{cr_id} → consultar CR
- GET /api/v1/change-request/{cr_id}/impact → evaluación de impacto
- POST /api/v1/change-request/{cr_id}/approve → aprobar CR
- GET /api/v1/audit-trail → audit trail ALCOA+ completo
- GET /api/v1/knowledge/stats → estadísticas corpus (PENDING hasta ingesta)
