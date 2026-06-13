# Capa 8 — Motor de Ejecución Controlada

## Tier-1: Diseño y Planificación (F4.5b)

| Módulo | Responsabilidad |
|--------|----------------|
| `requirement_interpreter.py` | Parsea misiones de Capa 9, extrae dominios y alcance regulatorio |
| `agent_design_engine.py` | Árbol heredar/perfil/nuevo; genera propuesta de agentes |
| `regulatory_compliance_engine.py` | Matriz regulatoria, corpus manifest, gate anti-texto-normativo |
| `workspace_builder.py` | Crea/reanuda workspaces (idempotente, modo resume) |
| `validation_manager.py` | Validación estática de artefactos + envoltorio de quality gates |
| `diff_manager.py` | Recolecta y archiva diffs de workspaces |
| `recovery_manager.py` | Detecta estados parciales y genera planes de recuperación |
| `job_queue.py` | Cola de jobs basada en archivos JSON |
| `layer8_orchestrator.py` | Orquesta el ciclo completo en modo plan-only |

## Tier-2: Runtime Controlado (F4.5c)

| Módulo | Responsabilidad |
|--------|----------------|
| `claude_account_status.py` | Verifica CLI de Claude (sin credenciales) |
| `claude_runtime.py` | Valida workspace, task safety; prepara comando manual |
| `code_generation_manager.py` | Gestiona la generación en modo manual_assisted |

## Reglas de operación

- **Headless OFF por defecto** (`factory/runtime/runtime_config.yaml`)
- `layer8_orchestrator.run_mission()` siempre opera en `plan_only=True` hasta F4.5c
- Ningún módulo emite texto regulatorio — toda fuente ausente → `PENDING_DOCUMENT`
- `validate_no_unsupported_regulatory_claims()` es un gate duro que aborta si detecta párrafos normativos
- Workspace builder es idempotente: workspace existente → modo `resume`, nunca sobrescribe
- Job queue: `factory/jobs/{pending,running,completed,failed}/`
- Artefactos de diseño: `factory/designs/<project_id>/`
