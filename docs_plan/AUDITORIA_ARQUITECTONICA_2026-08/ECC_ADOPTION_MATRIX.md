# A. Matriz de adopción ECC (§4, §19, §24)

**Estado**: propuesta de diseño. PROHIBIDO instalar ECC como plugin
(`/plugin marketplace add` / `/plugin install`) — ver B.3 del brief. Toda
adopción es reescritura como skill propio del proyecto, con origen citado
(MIT), nunca copia mayorista.

## Naturaleza de ECC (confirmada, no asumida)

`github.com/affaan-m/ECC`, MIT (a nivel de repo — ningún `SKILL.md`
individual trae su propio header de licencia, se hereda del repo).
Estructura real: `agents/`, `skills/`, `commands/`, `rules/`, `hooks/`,
`scripts/`, `mcp-configs/`. Es un "agent harness operating system" para
Claude Code — **tooling de desarrollo, no producto documental**. Esta
inspección (fetch directo de cada `SKILL.md` vía raw.githubusercontent)
no encontró nada que contradiga o amplíe la nota previa sobre capacidad
documental: sigue sin evidencia de PDF/OCR/tablas más allá de
`nutrient-document-processing` (wrapper comercial) y `visa-doc-translate`.

## Regla de evaluación aplicada por fila (§24)

"¿Esto fortalece el PRODUCTO GMP (el analizador documental) o solo hace
más sofisticado el ENTORNO DE DESARROLLO de Claude Code?" — si es lo
segundo, puede seguir siendo valioso, pero se etiqueta como tal, sin
disfrazarlo de mejora de producto.

## Matriz completa

| Componente ECC | Qué hace | Mecanismo | a) Producto vs entorno | b) Filtro gobernanza IA | c) Equivalente GMP ya existente | Decisión | Prioridad |
|---|---|---|---|---|---|---|---|
| **contract-first** | Contrato único machine-checkable (OpenAPI/JSON Schema) entre productor y consumidor; validación de forma, sin inferencia IA | 100% determinista | **Producto** — previene directamente la clase de defecto ya documentada como Causa 2 en R3-T1 (B3→B4→B5, "no parchear el segundo sitio") | Sin riesgo — valida forma, no contenido de cumplimiento | Parcial: `requirement_catalog_entry_v1.json`/`source_registry_entry_v1.json` ya son schemas versionados fail-closed; falta un contrato formal end-to-end para el par prompt-YAML↔`evidence_verifier`↔`chunked_engine` | **ADOPTAR** | **P1** |
| **ai-regression-testing** | Secuencia obligatoria tests deterministas→build→revisión IA, antes de aceptar cambio | Determinista (tests) + comando manual antes de inferencia IA | Entorno (stack Node/TS original, no aplica 1:1 a Python/pytest) | Sin riesgo | Cubierto parcialmente por disciplina manual "diagnosticar antes de construir"; falta la parte mecánica (orden forzado) | ADAPTAR — reescribir en Python/pytest, no copiar stack TS | P2 |
| **agent-self-evaluation** | Autoevaluación en 5 ejes (accuracy/completeness/clarity/actionability/conciseness) con evidencia obligatoria por score bajo | Manual/hook + inferencia IA (autopuntuación) | Entorno — calidad de reporte de Capa 8 | **Riesgo real**: cerca de que la IA certifique su propio juicio sobre un hallazgo GMP — viola el filtro de gobernanza si se aplica al contenido del hallazgo | Ninguno directo | **ADAPTAR CON CONTROL EXPLÍCITO** — permitido solo para autoevaluar trabajo de Capa 8 (código/documentos/proceso); **prohibido explícitamente** para autoevaluar la corrección de un hallazgo o decisión de cumplimiento GMP, eso es siempre humano | P2 |
| **delivery-gate** | Hook `Stop` determinista que bloquea cerrar sesión hasta pasar checks | Determinista | Entorno — disciplina de sesión de Capa 8 | Sin riesgo — no aprueba nada | Gate 0 (`factory_selfcheck.sh`, 14 checks) ya cubre "no declarar terminado sin verificar" a nivel de producto | INSPIRAR — adaptar la idea a un hook que verifique que Gate 0 corrió PASS antes de cerrar sesión; no copiar el check de disco/rationalization original | P3 |
| **agent-architecture-audit** | Checklist de 12 capas de fallos de arquitectura de agentes (wrapper regressions, memory pollution, hidden repair loops, etc.) | Determinista/guiado (grep + checklist) | Entorno — audita al AGENTE, no al producto | Sin riesgo — diagnóstico, no acción | Ninguno directo; relevante porque el proyecto ya tiene 2 clientes Ollama duplicados sin abstracción histórica (hallazgo previo de W5 V2) | INSPIRAR — tomar 2-3 preguntas del checklist para una futura auditoría de Capa 8, no adoptar el framework completo (sobredimensionado) | P3 |
| **workspace-surface-audit** | Inventario de superficie disponible (`.mcp.json`, plugins, MCP servers) vs. lo usado | Determinista (inventario) | Entorno puro | Sin riesgo — constraint propia: nunca expone secretos, solo nombres de proveedor | Compatible con la prohibición ya existente de mostrar `.env` | INSPIRAR — ejercicio ocasional, no skill permanente | P3 |
| **iterative-retrieval** | Loop DISPATCH→EVALUATE→REFINE→LOOP (máx 3 iteraciones) para que subagentes aprendan terminología del código progresivamente | Manual/orquestado, sin componente determinista fuerte | Entorno — búsqueda de código genérica | Riesgo de confusión: el retrieval de EVIDENCIA GMP ya está resuelto y medido (fusión BM25+embeddings, 7/7 at_5) — iterar sobre eso no tiene sentido, el techo ya es de juicio del modelo | Cubierto y superado por la fusión RRF ya implementada | **RECHAZAR** para el pipeline de evidencia (problema ya resuelto en otra capa); INSPIRAR como técnica genérica de búsqueda de código, valor menor | REJECT (pipeline) / P3 (código) |
| **eval-harness** | "Evals as unit tests" — graders code-based/model-based/human | Mixto | Producto (en principio relevante al fixture set) | El grader model-based no puede aprobar cumplimiento GMP — debe excluirse de cualquier ruta que toque hallazgos reales | **Ya cubierto y más maduro**: el fixture set 7P+2N + golden dataset de 8 casos negativos ya implementan el concepto con criterio cuantitativo más estricto (`recall≥6/7 AND 2/2 negativos AND schema_valid_rate=100%`) | **RECHAZAR** adopción directa — GMP ya tiene una versión superior y gobernada | REJECT |
| **hooks/memory-persistence** | Hooks de lifecycle (`SessionStart`/`PreCompact`/`PostToolUse`/`Stop`) para persistir contexto entre sesiones, local-first, opt-out | Determinista, declarado "not driven by model decisions" | Entorno — persistencia de contexto de Capa 8 | **Filtro de gobernanza aplica directo**: persistencia automática de "aprendizaje" que influya silenciosamente un juicio GMP futuro es exactamente el anti-patrón que causó el incidente real de R1 (config H2+H4 ganadora en script ad hoc nunca productizada) | El proyecto YA tiene un sistema de memoria persistente equivalente (`.claude/projects/.../memory/`) con la regla dura correcta ya incorporada | **RECHAZAR** — adoptar el hook técnico agregaría una segunda fuente de persistencia no auditada; riesgo, no beneficio | REJECT |

**Patrones adicionales detectados pero no inspeccionados a fondo**
(mencionados solo por asociación en el listado del repo, fuera de
alcance de esta pasada): `continuous-learning`, `continuous-agent-loop`,
`autonomous-agent-harness`, `agent-introspection-debugging`,
`agent-eval`. No se recomienda nada sobre ellos — quedan como candidatos
sin evaluar, no como brecha confirmada.

## Resumen cuantitativo

```
ECC_ADOPTION_MATRIX:
  ADOPTAR        = 1  (contract-first)
  ADAPTAR        = 2  (ai-regression-testing, agent-self-evaluation)
  INSPIRAR       = 3  (delivery-gate, agent-architecture-audit, workspace-surface-audit)
  RECHAZAR       = 3  (eval-harness, hooks/memory-persistence, iterative-retrieval-para-pipeline)
  Total evaluados = 9

ECC_PRODUCT_VS_TOOLING:
  Fortalecen PRODUCTO GMP directamente = 1 de 9 (contract-first)
  Fortalecen solo ENTORNO de Capa 8    = 8 de 9
```

Ningún componente ECC evaluado se presenta como mejora de producto salvo
`contract-first`. Los 8 restantes son, en el mejor caso, disciplina de
desarrollo de Capa 8 — valiosa (la disciplina de desarrollo ha sido el
cuello de botella real del proyecto, ver memoria `feedback_workflow`),
pero nunca disfrazada de capacidad del analizador documental.
