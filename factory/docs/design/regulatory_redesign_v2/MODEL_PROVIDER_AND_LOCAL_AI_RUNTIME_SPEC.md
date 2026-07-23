# MODEL_PROVIDER_AND_LOCAL_AI_RUNTIME_SPEC

## 1. Estado actual (confirmado por auditoría)

No existe ninguna clase `ModelProvider` ni abstracción de proveedor en
`factory/`. Dos clientes Ollama casi idénticos y duplicados:
`app/ollama_client.py:23-55` y
`factory/engines/gmpai_integrity/ollama_client.py:1-43`, ambos con
`httpx.post` directo a `/api/generate`. Toda la lógica regulatoria
(`llm_integrity_engine.py`, `llm_traceability_agent.py`) importa el cliente
directamente — acoplamiento total, sin capa intermedia.

## 2. Interfaz objetivo

```
ModelProvider (interfaz abstracta)
├── OllamaProvider            (implementación actual, default)
├── OpenAICompatibleProvider  (futuro, sin autorización requerida per se
│                               salvo que implique salida de datos fuera
│                               del entorno controlado)
├── AnthropicProvider         (SOLO con autorización explícita de Capa 9;
│                               NO se activa por defecto; requiere decisión
│                               humana documentada antes de cualquier
│                               llamada real)
└── LocalCompatibleProvider   (cualquier runtime local compatible con la
                                interfaz REST genérica, p.ej. otro backend
                                self-hosted)
```

Contrato mínimo de la interfaz: `generate(prompt, schema, timeout,
temperature, seed) -> StructuredOutput | LLM_OUTPUT_INVALID |
LLM_SERVICE_UNAVAILABLE`. Ningún agente regulatorio importa un cliente
concreto; solo consume `ModelProvider`.

## 3. Configuración por perfil

Cada agente híbrido se configura, no se reprograma, con: `provider`,
`endpoint`, `model_name`, `model_digest`, `context_window`, `timeout`,
`max_tokens`, `temperature`, `seed` (cuando exista), `retry_policy`,
`fallback_policy`, `prompt_version`, `schema_version`. Este perfil vive
versionado junto al agente (no en variables de entorno sueltas) para que el
fingerprint de la corrida (sección 18 del plan) pueda capturarlo
íntegramente.

## 4. Servicio de inferencia compartido (NO 11 contenedores Ollama)

Diseño de un único servicio de inferencia compartido con:
- cola central con prioridades;
- concurrencia configurable (límite de llamadas simultáneas por modelo);
- timeout por llamada;
- checkpoint/resume (ya existe un precedente parcial: `1c16686` —
  "checkpoint/resume + ejecución por lotes en run_validation_evidence",
  reutilizable como punto de partida técnico);
- retry limitado con backoff;
- circuit breaker (abre tras N fallos consecutivos, cierra tras verificar
  disponibilidad);
- métricas (latencia, tasa de reintento, tasa de invalidez de schema);
- trazabilidad por llamada (`run_id`, `task_id`, `agent_id`, `model_digest`).

Todos los agentes híbridos (AGT-APP en su tramo LLM, AGT-EVD, AGT-VER,
AGT-GAP en su explicación textual, AGT-REM, AGT-QLT, AGT-DOC en su reseña,
AGT-RVL) comparten esta única cola, diferenciados por `agent_id` y
prioridad, no por instancia de contenedor.

## 5. Cambio de modelo sin reprogramar el agente

Cambiar de modelo requiere: nuevo `model_digest`; ejecución del Golden
Dataset (sección 12.2 del plan + `SEMANTIC_EVIDENCE_VERIFICATION_SPEC.md`);
comparación contra baseline; reporte de regresión; aprobación humana del
nuevo perfil. La especialización del agente (prompts, schemas, reglas,
Evidence Packs, validadores) se llama **configuración y validación del
agente**, nunca "fine-tuning", salvo que exista entrenamiento real de pesos
(no es el caso de este diseño).

## 6. Model Qualification Gate

Métricas obligatorias antes de aceptar un modelo/perfil en producción:
`schema_valid_rate`, `citation_anchor_precision`, `semantic_precision`,
`semantic_recall`, `false_positive_rate`, `false_negative_rate`,
`contradiction_detection_rate`, `remediation_acceptance_rate`,
`unsupported_claim_rate`, `latency_p50`, `latency_p95`, `tokens_per_task`,
`retry_rate`.

Prioridades de decisión (en este orden, nunca invertido):
1. cero citas inventadas;
2. menor tasa de falsos positivos;
3. menor tasa de falsos negativos críticos;
4. cumplimiento de schema;
5. estabilidad;
6. calidad de remediación;
7. rendimiento.

**Nunca** elegir modelo solo por velocidad. Cambio de modelo = nuevo
fingerprint + Golden Dataset + comparación baseline + reporte de regresión
+ aprobación del perfil.

## 7. CLAUDE_CODE_REQUIRED_AT_RUNTIME = false

Confirmado por auditoría: el pipeline actual (`pipeline.py` y todos los
`app/*.py`) ya corre como scripts Python autónomos dependientes solo de
`httpx` + Ollama local — no de Claude Code. El diseño de ModelProvider
preserva esta propiedad: ningún agente objetivo requiere Claude Code para
ejecutarse, mantener estado de producción, hacer checkpoint/resume, decidir
conformidad o liberar documentos. Claude Code permanece como Capa 8:
diseña, implementa, prueba, depura, mantiene, prepara commits — nunca
runtime permanente.

## 8. Riesgo de migración

El acoplamiento directo actual (2 clientes Ollama duplicados, sin
interfaz) implica que introducir `ModelProvider` es un refactor real, no
solo una adición: `llm_integrity_engine.py`, `llm_traceability_agent.py`,
`llm_part11_agent.py`, `llm_annex11_agent.py`, `llm_alcoa_agent.py` y
`factory/engines/gmpai_integrity/chunked_engine.py` deben migrar sus
imports directos a la interfaz. Este refactor debe planificarse como fase
propia (Fase D del roadmap) con Golden Dataset como red de seguridad de
regresión, no como cambio incremental sin pruebas.
