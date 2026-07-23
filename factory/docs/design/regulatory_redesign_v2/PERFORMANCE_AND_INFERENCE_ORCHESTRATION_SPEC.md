# PERFORMANCE_AND_INFERENCE_ORCHESTRATION_SPEC

## 1. Corrección del patrón "todos los chunks × todos los requisitos"

El baseline confirmado (121 llamadas = 11 requirement_id × 11 chunks, ver
sanitización URS v2.1) es el patrón exacto que este spec prohíbe por
defecto. Antes de llamar a la LLM, aplicar en orden: matriz de
aplicabilidad (AGT-APP); tipo documental; índice de secciones; filtros
deterministas; búsqueda textual; recuperación semántica; deduplicación;
selección de contexto. Solo tras estos filtros se invoca al modelo, y solo
sobre los pares documento×requisito que sobrevivan al filtrado.

## 2. Diseño del servicio de inferencia compartido

Cola central; concurrencia configurable; prioridades; batching seguro;
checkpoint; resume; retry limitado; cache por fingerprint; deduplicación de
prompts; timeout; circuit breaker; métricas.

Precedente real reutilizable: commit `1c16686` ("checkpoint/resume +
ejecución por lotes en run_validation_evidence", ver memoria de proyecto
W5) ya implementó checkpoint/resume y batch para
`factory/regulatory/tools/run_validation_evidence.py`. Este componente es
la base técnica más cercana al servicio compartido objetivo, aunque hoy
sirve un solo motor CLI, no una cola compartida entre 11 agentes.

## 3. Invalidación de cache

**No** reutilizar resultados cuando cambie: documento o SHA-256; regulación
o SHA-256; Evidence Pack; prompt; schema; modelo o digest; matriz;
chunking. Cualquier cambio en estos 8 elementos invalida el cache
correspondiente — nunca invalidación parcial ambigua.

## 4. Registro por llamada

`run_id`; `task_id`; `agent_id`; `agent_version`; `document_sha256`;
`requirement_id`; `provider`; `model`; `model_digest`; `prompt_version`;
`schema_version`; Evidence Pack version; timestamps; duración; validación.

## 5. Fingerprint de corrida

`run_id` y fingerprint persistidos desde el inicio, incluyendo: documentos
+ SHA-256; commit; modelo + digest; `prompt_version`; `schema_version`;
`agent_id` + `agent_version` (todos); Evidence Pack versions; catálogo
(versión+hash); matriz de aplicabilidad (versión+hash); regulaciones +
hashes; parámetros; chunking; fecha; responsable (identidad real).
Reanudación con fingerprint distinto ⇒ **RECHAZADA** + auditada; se inicia
corrida nueva (nunca se mezclan resultados de dos fingerprints).

## 6. Fallback fail-closed

Cuando la LLM no esté disponible:
- no inventar resultados; no degradar a coincidencias de palabras;
- conservar checkpoint; continuar tareas deterministas;
- marcar `LLM_SERVICE_UNAVAILABLE`; reanudar al volver el servicio;
- impedir conclusiones positivas incompletas;
- **NO** cambiar automáticamente a un proveedor externo (ningún fallback
  silencioso de Ollama a un proveedor en la nube).

## 7. Riesgo de performance identificado en el inventario real

El archivo `215115305 SCADA-PCS Misc PLC SAT3 Scanned-1.pdf` (136.8 MB,
posible OCR) es el caso de mayor riesgo de cuello de botella: sin los
filtros deterministas de la sección 1, procesarlo chunk×requisito
generaría un volumen de llamadas desproporcionado respecto a los otros 13
archivos (todos <3 MB). Este archivo debe pasar primero por AGT-INV/AGT-APP
para acotar aplicabilidad antes de cualquier llamada LLM.

## 8. Estado actual y brecha

Existe precedente parcial de checkpoint/resume y batch (`1c16686`), y de
selección de contexto en `llm_traceability_agent.py` (extracción de
requisitos antes de verificar cobertura, evita reprocesar todo el
documento por cada requisito). No existe hoy: cola central compartida
entre agentes, circuit breaker, cache por fingerprint formal, ni el
fingerprint de corrida completo descrito en la sección 5. Brecha
significativa — gated a Fase D/G del roadmap junto con ModelProvider.
