# Capa 9 — Mission Control

Plano de gobierno que autoriza todo lo que Capa 8 puede ejecutar.

## Módulos

| Módulo | Responsabilidad |
|--------|----------------|
| `requirement_schema.py` | Dataclasses y validación de payloads (MissionPayload, RequirementPayload) |
| `mission_control.py` | Ciclo de vida de misiones: draft → approved → closed |
| `instruction_center.py` | Recepción y gestión de requerimientos de cliente |
| `approval_matrix.py` | 10 acciones aprobables con nivel de riesgo y obligatoriedad |
| `decision_log.py` | Registro inmutable de decisiones de gobernanza |
| `risk_acceptance.py` | Aceptación formal de riesgos identificados |

## Almacenamiento

```
factory/layer9/
├── missions/<project_id>.yaml        # Estado de cada misión
├── requirements/<req_id>.json        # Requerimientos individuales
├── decisions/decisions.jsonl         # Log de decisiones
├── risks/risks.jsonl                 # Log de riesgos aceptados
└── README.md
```

Sin postgres, sin redis. Archivos YAML/JSON/JSONL.

## Ciclo de misión

```
create_mission()   → status: draft
approve_mission()  → status: approved  [requiere aprobación humana]
close_mission()    → status: closed
```

## Acciones aprobables (approval_matrix)

| Acción | Riesgo | Obligatorio |
|--------|--------|-------------|
| mission | high | sí |
| agent_design | medium | sí |
| new_agent | high | sí |
| claude_execution | critical | sí |
| recovery_plan | high | sí |
| port_exposure | medium | sí |
| release | medium | sí |
| deploy | critical | sí |
| keep_running | high | sí |
| external_exposure | critical | sí |

## Eventos de auditoría (factory_audit.jsonl)

- `layer9_mission_created`
- `layer9_mission_approved`
- `layer9_requirement_submitted`
- `layer9_decision_recorded`
- `layer9_risk_accepted`

## Autonomy levels

| Nivel | Descripción |
|-------|-------------|
| `manual_only` | Ninguna acción automatizada; todo manual |
| `supervised` | Acciones automáticas con revisión humana en cada paso |
| `controlled_full` | Ejecución autónoma hasta create_release; deploy y expose siempre humano |

## Stop conditions

La Capa 8 debe detenerse si detecta cualquiera de estas:

- `product_base_change_detected`
- `forbidden_path_detected`
- `regulatory_source_missing_for_required_claim`
- `quality_gate_fail`
- `docker_runtime_fail`
- `resource_limit_exceeded`
- `claude_execution_failed`
- `content_filter_blocked`

## Decisiones siempre humanas

- `deploy_docker`
- `keep_docker_running`
- `expose_external_access`
