# CURRENT_AGENT_RUNTIME_AUDIT

Corrida de diseño W5 V2 — 2026-07-23. Auditoría de solo lectura, código real
(no documentación) del pipeline actual bajo
`factory/workspaces/gmpai_document_validation/app/` y motores relacionados en
`factory/engines/gmpai_integrity/` y `factory/regulatory/`.

## 1. Matriz obligatoria (agente actual → destino W5 V2)

| Agente actual | Archivo (file:line) | Responsabilidad real | Tipo runtime | Usa LLM | Orquestador | Agente W5 V2 destino | Capacidad reutilizable | Capacidad faltante |
|---|---|---|---|---|---|---|---|---|
| doc_inventory_version_agent | `app/inventory_agent.py:57` (`build_inventory`), `:113` (`run`) + `app/version_selection.py` | SHA-256, comparación contra `SHA256SUMS.txt`, duplicados exactos por hash, familias de versión, superseded. | DETERMINISTIC | No | `pipeline.py:35` y standalone `python -m app.inventory_agent` | AGT-INV | Cálculo de hash, detección de duplicados, agrupación de versión | Allowlist con estados cerrados (sección 9 del plan); `path_policy.py` central; SOURCE_INTEGRITY_VIOLATION periódica |
| doc_classification_agent | `app/classification_agent.py:22-51` (regex/keywords), `:56-58` (placeholders), `:71-79` | Clasifica URS/FS/DS/ARCHITECTURE/... por nombre + contenido. | DETERMINISTIC | No | `pipeline.py:59` | AGT-APP (aplicabilidad) / AGT-DOC (tipo documental) | Reglas de clasificación por tipo documental | Matriz de aplicabilidad doc×requirement_id; reglas de exclusión DERIVED |
| fda_part11_agent | (a) `compliance_agents.py:57-66,150-153` keyword-scan; (b) `llm_part11_agent.py` + `llm_integrity_engine.py:76-79,126,159-163` | (a) escaneo de keywords fijas, nunca declara "cumple" sin cita. (b) 1 llamada Ollama/doc, exige anclaje literal o descarta. | (a) DETERMINISTIC; (b) LLM_BACKED | Sí en modo `--engine llm`: `ollama_client.generate()` en `llm_integrity_engine.py:126` | `pipeline.py:112-114` | AGT-VER (validación B/C/D específica de 21 CFR 11) | Contrato de anclaje de evidencia; `Finding` con `agent_version/prompt_version/model` | Evidence Pack con texto canónico; validación B (fuente); validación D (suficiencia por criterio) |
| eu_annex11_agent | `llm_annex11_agent.py` + `compliance_agents.py:68-76,155-157` + `llm_integrity_engine.py` (motor compartido) | Igual patrón, checkpoints `ANNEX11_CHECKPOINTS`. | (a) DETERMINISTIC; (b) LLM_BACKED | Sí, `llm_integrity_engine.py:126` | `pipeline.py:113` | AGT-VER | Igual que fda_part11_agent | Igual; además regla dura anti-falso-positivo ANNEX11_4 (ver §12.2 del plan) aún no codificada como validador determinista |
| alcoa_plus_agent | `llm_alcoa_agent.py` + `compliance_agents.py:78-96,159-161` + `llm_integrity_engine.py` | 9 checkpoints ALCOA+. | (a) DETERMINISTIC; (b) LLM_BACKED | Sí, `llm_integrity_engine.py:126` | `pipeline.py:114` | AGT-VER | Igual | Igual |
| requirements_traceability_agent | Simple: `compliance_agents.py:190-220`; Fase C real: `llm_traceability_agent.py:87-118` (`extract_requirements_llm`), `:120-155` (`check_coverage_llm`), `:75-79` (`_is_anchored`), `:196-201` (fallback) | Motor simple solo verifica presencia de tipo documental. Motor LLM extrae requisitos discretos del URS y verifica cobertura contra FS/DS/protocolo/SAT con anclaje. | HYBRID (fallback determinista + tramo LLM verificado) | Sí, 2 llamadas encadenadas: `llm_traceability_agent.py:98,143` | `pipeline.py:152-156` (por sistema, `sys_key`) | AGT-REP (trazabilidad) + parcialmente AGT-GAP | Extracción de requisitos en 2 pasos; verificación de anclaje; fallback sin crash | Evidence Pack por requisito; matriz de trazabilidad formal con requirement_id estable |
| compliance_risk_agent | `app/risk_agent.py:33-49` (`risk_score = severidad*confianza`), `:52-61` (resumen agregado) | Consolida `Finding` en matriz de riesgo agregada. No decide cumplimiento. | DETERMINISTIC | No | `pipeline.py:159-160` | AGT-GAP (parcial, clasificación de riesgo) | Fórmula de risk_score, agregación por severidad/estado | Criterios deterministas de LOW/MEDIUM/HIGH_RISK del §13.4 del plan (no existen hoy) |
| final_review_agent | `app/final_review_agent.py:21-30` (`governance_statement` fijo), `:37-49` (blockers si `version_conflicts_count>0` o críticas) | Ensambla `FinalReviewPackage`: totales, riesgo, bloqueadores. Nunca aprueba; remite a Capa 9 (humano). | DETERMINISTIC (el rol de decisión humana en sí es HUMAN_ROLE, fuera del código) | No | `pipeline.py:162-170` | QA-HUM (patrón de gate humano a preservar) + AGT-RVL (estructura de paquete) | Patrón "nunca autoaprueba", texto de gobernanza fijo | Las 4 decisiones (APPROVE_CLEAN/APPROVE_WITH_EXCEPTIONS/REQUEST_CHANGES/REJECT), idempotencia 409, identidad 422 |

## 2. Otros componentes reales relevantes (no en la lista de 8)

| Componente | Archivo | Rol | Clasificación |
|---|---|---|---|
| Extracción de texto | `app/extraction.py` | Extracción por formato, SHA-256; usado por inventory_agent y pipeline (`pipeline.py:60`) | DETERMINISTIC, reutilizable para AGT-INV/AGT-EVD |
| Motor de integridad genérico | `app/llm_integrity_engine.py`, `app/chunked_llm_integrity_engine.py` (316 líneas, `:1-24`) | Motor compartido por part11/annex11/alcoa; versión chunked usada por `run_chunked_pilot.py`, no por `pipeline.py` | HYBRID, contrato reutilizable para AGT-VER |
| Motor "v2" independiente | `factory/engines/gmpai_integrity/chunked_engine.py:250` (`evaluate_chunked()`), `ollama_client.py` (json+temp 0), `models.py` | Reescritura git-trackeada; invocado solo desde CLI (`factory/regulatory/tools/run_validation_evidence.py`, `reverify_offline.py`); **nunca** desde endpoint HTTP de producción, confirmado en `factory/regulatory/verified_pipeline.py:16-30` | HYBRID_INDEPENDENT (candidato más maduro para AGT-VER/AGT-QLT) |
| Capa de verificación requisito×documento | `factory/regulatory/verified_pipeline.py:31-36`, `evidence_verifier.py`, `absence_consolidator.py` | Probada aislada, **NO cableada** en el POST real ("violaría P1" según su propio docstring) | DESIGN_ONLY / PARTIALLY_IMPLEMENTED |
| Catálogo de agentes | `factory/api/routes/agents.py` (32 líneas) | `GET /api/v1/agents`, `/agents/profiles`; solo lee YAML estático de `factory/registry/agents_catalog.yaml` y `factory/profiles/*.yaml` | CONFIGURED_ONLY — no ejecuta nada |
| Gobernanza Capa 9 | `factory/api/routes/layer9.py` | Endpoints de misión/decisión/RC/aprobación | DETERMINISTIC, gobierna ciclo de vida, no ejecución de agentes |
| Servicios de lectura de reportes | `factory/services/gmp_report_service.py:88-90`, `gmpai_artifact_service.py:71-72` | Explícitos en código: "NO reprocesa documentos ni invoca agentes" / "No reprocesa nada" | DETERMINISTIC, solo lectura de JSON pre-generado |

## 3. Orquestador central / API

**No existe** un router HTTP que ejecute el pipeline de 8 agentes en vivo. No
hay `POST /api/v1/gmpai/run`. El único invocador real es el script CLI
`python -m app.pipeline --scope pilot --engine llm` (`pipeline.py:183-193`) o
los scripts standalone `run_chunked_pilot.py` / `run_pilot_verification.py`.
Todo lo que el dashboard/reportes muestran es lectura de artefactos JSON
pre-generados por corridas CLI manuales.

## 4. ¿Funciona con Claude Code cerrado?

**Sí**, para el pipeline de 8 agentes: son scripts Python autónomos que
dependen únicamente de `httpx` y un servidor Ollama en `localhost:11434`
(`ollama_client.py:16-17`). No dependen de Claude Code en ejecución.

## 5. Acoplamiento directo a Ollama (sin abstracción de provider)

- `app/ollama_client.py:23-55` — único cliente HTTP (`httpx.post` directo),
  importado directo en `llm_integrity_engine.py:24`, `llm_traceability_agent.py:26`.
- `factory/engines/gmpai_integrity/ollama_client.py:1-43` — segundo cliente
  casi idéntico y duplicado, con nota explícita de por qué ("movido aquí
  para que el motor sea git-trackeado").
- **No existe ninguna clase `ModelProvider`** ni abstracción de proveedor real
  en `factory/` (grep de `ModelProvider|class.*Provider` solo arrojó falsos
  positivos de dependencias de terceros en `.venv/`).

## 6. Bloque de estado (valores reales de esta sección)

```
CURRENT_REAL_AGENT_COUNT = 8 (de los 8 nombrados) + 1 motor v2 independiente
  (chunked_engine.py, no wireado a producción) + 1 capa de verificación
  requisito×documento (DESIGN_ONLY/PARTIALLY_IMPLEMENTED, no wireada)
CURRENT_IMPLEMENTED_AGENTS = 8/8 (inventory, classification, part11, annex11,
  alcoa, traceability, risk, final_review) — todos con código ejecutable real
CURRENT_DESIGN_ONLY_AGENTS = 0 de los 8 nombrados; SÍ design-only:
  verified_pipeline.py / evidence_verifier.py / absence_consolidator.py
CURRENT_DETERMINISTIC_AGENTS = 5 puros (inventory, classification, risk,
  final_review, y el motor keyword de part11/annex11/alcoa)
CURRENT_LLM_OR_HYBRID_AGENTS = 4 (part11 modo llm, annex11 modo llm, alcoa
  modo llm, traceability modo llm — todos HYBRID/LLM_BACKED, opt-in vía
  --engine llm, no son el modo por defecto)
CURRENT_CLAUDE_CODE_RUNTIME_DEPENDENCY = false (scripts Python autónomos,
  dependen solo de httpx + Ollama local)
```

## 7. Reutilizable para el pipeline objetivo de 11 agentes

- `inventory_agent.py` + `version_selection.py` → base directa AGT-INV.
- `classification_agent.py` → base para AGT-APP/AGT-DOC.
- `llm_integrity_engine.py` (contrato de anclaje, fallback sin crash,
  `Finding` versionado) → patrón para AGT-EVD/AGT-VER.
- `llm_traceability_agent.py` (extracción de requisitos en 2 pasos) → base
  para AGT-REP y parcialmente AGT-GAP.
- `risk_agent.py` → base para AGT-GAP (risk scoring, no para AGT-RSG que en
  este plan es gobernanza de fuentes — nombre similar pero responsabilidad
  distinta, ver nota de desambiguación en REGULATORY_SOLUTION_GAP_ASSESSMENT.md).
- `final_review_agent.py` (nunca autoaprueba) → patrón obligatorio a
  preservar en QA-HUM.
- `chunked_engine.py` + `verified_pipeline.py` (contrato `finding_llm_v1`,
  consolidación de ausencia) → candidato más maduro para AGT-VER/AGT-QLT,
  pero requiere decisión: retomar esa rama o reconstruir desde el motor del
  workspace.
- **Nada reutilizable para AGT-REM** (remediación) como agente de IA — lo
  existente (`remediation_package_service.py`) es gestión de estado, no
  generación de remediaciones.

## Nota de desambiguación de nombres

El código actual usa el nombre `risk_agent.py` para lo que en esta
arquitectura se llama **AGT-GAP** (clasificación de riesgo de hallazgos). El
plan W5 V2 usa el id `AGT-RSG` para un concepto distinto: **gobernanza de
fuentes regulatorias** (sección 10 del plan), que NO existe hoy como agente
de código — vive parcialmente en `factory/regulatory/sources/` (activos
estáticos) sin agente ejecutable. Esta ambigüedad debe resolverse
explícitamente en la Fase B del roadmap para evitar que se reutilice
`risk_agent.py` bajo el id equivocado.
