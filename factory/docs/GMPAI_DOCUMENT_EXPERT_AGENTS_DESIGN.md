# GMP AI — Nuevo Diseño: Agentes Expertos de Validación Documental

**Fecha:** 2026-07-14
**Estado:** propuesta de diseño. **No implementado.** Requiere aprobación explícita de Cesar por fase antes de codificar (ver §18).
**Basado en:** hallazgos de `GMPAI_DOCUMENT_EXPERT_AGENTS_ASSESSMENT.md` — el gap central es que los 3 agentes de integridad regulatoria (Part 11/Annex 11/ALCOA+) están implementados como keyword-scan en vez de invocar el agente base `integrity` (Ollama) vía los perfiles ya diseñados en `factory/profiles/integrity_profiles.yaml`.

---

## 1. Arquitectura propuesta

Reutilizar, no reconstruir. El principio de diseño es: **el pipeline documental (`gmpai_document_validation`) se convierte en un cliente del motor de agentes que YA existe y funciona** (`case_analysis_service.py` / agente base `integrity`/`csv` vía Ollama en `gmp-api:8000`), en vez de mantener una segunda implementación paralela de "qué es un hallazgo Part 11".

```
┌─ Capa determinista (mantener, ya funciona bien) ──────────┐
│ doc_inventory_version_agent   → hash/versión (regla)      │
│ doc_classification_agent      → tipo doc (heurística)      │
│ compliance_risk_agent         → severidad×confianza (regla)│
└──────────────┬──────────────────────────────────────────────┘
               │ documento clasificado + texto extraído
               ▼
┌─ Capa de razonamiento LLM (NUEVA — el gap real) ───────────┐
│ fda_part11_agent      → gmp-api /api/v1/query (Ollama,     │
│ eu_annex11_agent         perfil integrity_part11_ot_profile│
│ alcoa_plus_agent          / integrity_annex11_ot_profile)  │
│ requirements_traceability_agent → perfil csv_ot_traceability│
└──────────────┬──────────────────────────────────────────────┘
               │ Finding[] con agent_version/prompt_version/model
               ▼
┌─ Capa de gobierno (mantener, ya es correcta) ──────────────┐
│ final_review_agent → nunca auto-aprueba, gate humano       │
│ report_writer       → + generador de borrador corregido    │
└──────────────────────────────────────────────────────────────┘
```

No se propone un contenedor Docker nuevo (la misión ya declara `sin Docker — analisis documental puro`, correcto: es análisis batch, no un servicio con SLA). Se propone que el workspace headless, en vez de reimplementar el razonamiento regulatorio, llame por HTTP a `gmp-api:8000` (el producto base, agentes reales) con el texto extraído de cada documento como contexto, exactamente como ya hace `case_analysis_service.py` para casos regulatorios.

## 2. Ciclo de vida del documento

`discovered → hashed → classified → version_resolved (o version_conflict) → routed_to_agents → agent_findings_collected → risk_scored → draft_proposed (si aplica) → pending_human_decision → {accepted | rejected | changes_requested}`. Estado persistente por documento en `factory/regulatory/doc_validation/<project_id>/documents.jsonl` (mismo patrón append-only con hash chain que `factory_audit.jsonl`).

## 3. Modelo de agentes y versionado

Cada agente que invoque Ollama declara, en un manifest `factory/agent_prompts/doc_validation_prompts.yaml` (mismo patrón que `case_analysis_prompts.yaml` ya existente):

```yaml
prompts:
  fda_part11_agent:
    prompt_version: "1.0.0"
    base_agent: integrity
    profile: integrity_part11_ot_profile
    model: <el que devuelva `docker exec gmp-api env | grep OLLAMA_MODEL`>
    verifier_version: "2.2"   # reusar el verificador ya validado en W7.1
```

`agent_version` = hash corto del prompt+lógica de postproceso (no del modelo, que es compartido). `corpus_version` = fecha+hash de `factory/profiles/*.yaml` relevante. Todo esto ya tiene precedente funcionando en `dossier_agent_review_service.py:544` — se replica el patrón, no se inventa uno nuevo.

## 4. Asignación documento-agente

Mantener `agent_design_engine.py::decide_inherited_profiles_custom` (ya correcto) como fuente de la matriz agente↔dominio. Para la matriz documento×agente×ejecución, reemplazar el bucle síncrono de `pipeline.py` por registros de tarea individuales:

```json
{"doc": "...", "sha256": "...", "version": "VIGENTE", "agent": "fda_part11_agent",
 "agent_version": "...", "status": "queued|running|completed|failed|awaiting_review",
 "started_at": null, "finished_at": null, "regulation": "21_CFR_PART_11",
 "findings_count": null, "errors": null}
```

Un documento puede generar N tareas (una por agente aplicable — Part11 + Annex11 + ALCOA+ + trazabilidad para el mismo URS, como ya ocurre hoy).

## 5. Gobernanza de Internet y corpus

**Reusar `regulatory_connector_service.py`/`regulatory_connector_extra_service.py` (ya probado con openFDA real)**, extendiendo `source_registry.yaml` con eCFR y EudraLex (únicas 2 fuentes nuevas necesarias, no MHRA/WHO/ICH salvo que Cesar las pida — la instrucción K dice explícitamente "no abras nuevas fuentes regulatorias" para esta sesión, así que **esto es diseño, no implementación**). Regla dura ya validada en W9: cupo compartido, `official=true`, hash+fecha+URL registrados, nunca se inyecta en el corpus oficial sin paso de revisión. El agente `fda_part11_agent` consulta el conector **solo** cuando el corpus local (`corpus_pending` en el perfil) no tiene el clausulado — y cita la fuente exacta o marca `evidencia_insuficiente`.

## 6. Integración con Ollama

Vía `gmp-api:8000` existente — **no** un nuevo cliente Ollama en el workspace (violaría "NO instalar paquete ollama", ya se usa `httpx` contra la API REST del producto base, que a su vez habla con `aria-ollama:11434`). El workspace headless de `gmpai_document_validation` hace `POST http://localhost:8000/api/v1/query` (o el endpoint interno equivalente que usa `case_analysis_service.py`) con el perfil como parámetro de contexto.

## 7. Cola y concurrencia

Ejecución **secuencial** (regla dura D del encargo, y limitación real de CPU del servidor). Reusar el patrón de `case_analysis_service.py`, que ya gestiona latencia/reintentos/truncamiento con Ollama real. Un `factory/runtime/doc_validation_queue.json` visible desde Mission Control muestra: documento actual, agente actual, posición en cola, tiempo transcurrido — igual que `claude_status.json` ya hace para jobs headless.

## 8. Contratos de entrada y salida

- **Entrada por agente:** `{doc_id, sha256, version_label, extracted_text, doc_type, profile_name}`.
- **Salida:** lista de `Finding` — **el contrato ya existe y es correcto** (`app/models.py::Finding`, 13 campos exactos pedidos en la sección E del encargo). No cambiar esa estructura; solo cambiar quién la puebla (Ollama en vez de regex).

## 9. Modelo de datos

Extender `Finding` con 3 campos nuevos: `agent_version`, `prompt_version`, `verifier_version` (hoy ausentes — hallazgo A9 de la auditoría). Persistencia: mismo append-only JSONL con hash chain que ya usa `factory_audit.jsonl`, un evento nuevo `doc_validation_finding_generated`.

## 10. Endpoints reales

Reusar el router `layer9` existente (`factory/api/routes/layer9.py`, ya expone `/missions/{project_id}/{agents,rcs,reports,test-results,...}`) — no crear un router paralelo. Nuevos endpoints mínimos:

- `GET /api/v1/layer9/missions/{project_id}/doc-validation/queue` — estado de la cola en tiempo real
- `GET /api/v1/layer9/missions/{project_id}/doc-validation/documents/{doc_id}` — matriz documento×agente×ejecución para un documento
- `POST /api/v1/layer9/missions/{project_id}/doc-validation/documents/{doc_id}/draft` — dispara generación de borrador corregido (§13)

## 11. Cambios en Mission Control

`agents_view.js::renderMissionAgents` — añadir `model`, `agent_version`, `prompt_version`, `verifier_version`, `corpus_version` (hoy solo muestra `agent_id`/`base_agent`/`profile_name`/`rationale`/`routing_key` — hallazgo G1). Nueva vista "Cola de documentos" en el panel Pipeline (reusa el patrón de `pipeline.js::refreshPipeline`, ya corregido hoy para no apuntar a proyectos muertos). Aplicar `_checkAuthFailure()` (ya escrito hoy en `refresh.js`, sin commitear) a **todos** los fetches, no solo los 2 actuales (cierre de H1).

## 12. Auditoría

Sin cambios de mecanismo — `factory_audit.jsonl` con hash chain ya es Part-11 compliant (validado en 315+ entradas, 0 hash_errors reales). Solo se agregan tipos de evento nuevos: `doc_validation_task_started/completed/failed`, `doc_validation_finding_generated`, `doc_validation_draft_proposed`.

## 13. Creación de borradores corregidos (gap F1 — hoy inexistente)

- Preservar el original: nunca escribir sobre `GMPAI/source/` (ya es una regla dura en la misión, se mantiene).
- Salida: **Markdown como formato primario** (determinista, diffable, auditable en git) con exportación opcional a DOCX vía `python-docx` (librería pura Python, sin macros — cumple "no ejecutar macros DOCM") para los casos `.docx`/`.doc` de origen. **XLSX** vía `openpyxl` para los orígenes `.xlsx` (listados de alarmas, IO listing). **PDF derivado**: no editar el PDF original — generar el Markdown/DOCX corregido y, si se pide, renderizarlo a PDF nuevo (nunca modificar el PDF fuente).
- Cada borrador: nueva versión semántica, SHA-256 propio, `changelog` con lista `{cambio, finding_id, requisito_regulatorio}`, campo `proposed_by_agent` + `agent_version`, `status: draft`, `human_review_required: true`. Nunca se autodeclara `compliant`.
- Relación cambio→hallazgo→requisito: cada línea del changelog referencia el `finding_id` que la originó (mismo patrón de referencia por ID que `dossier_case_reference_service.py` ya usa para casos — W9 Bloque 2).

## 14. Seguridad

Sin cambios de superficie: el workspace headless sigue sin Docker, sin credenciales propias, llama a `gmp-api:8000` (loopback, ya protegido por las reglas `DOCKER-USER` existentes). El endpoint nuevo de borrador corregido no debe aceptar rutas de archivo arbitrarias — solo `doc_id` validado contra el inventario existente (evitar path traversal hacia fuera de `GMPAI/source/` o del workspace).

## 15. Tests

Extender la suite ya real (37 tests actuales, corridos contra el corpus real de 32 archivos, no mockeada — buena práctica a preservar) con: tests de contrato del cliente Ollama (mock solo para CI, marcado explícitamente como mock — nunca ocultar que es mock), tests de generación de borrador (verificar que el original nunca cambia de hash), tests de los 3 nuevos campos de versión en `Finding`.

## 16. Quality gates

Los 14 gates estándar de fábrica (skill `gmp-quality-gates`) más un gate nuevo específico: **G_DOC_NO_AUTOCOMPLIANCE** — falla el release si cualquier reporte generado contiene la palabra "compliant"/"cumple GMP" en el `informe_ejecutivo_final` sin ir acompañada de `revision_humana_requerida: true`. Formaliza la regla de gobierno que hoy solo vive como disciplina de código.

## 17. Criterios de aceptación

1. Al menos 1 agente (`fda_part11_agent`) ejecuta contra Ollama real, no keyword-scan, con `prompt_version`/`model`/`verifier_version` visibles en Mission Control.
2. El piloto Rockwell (URS+FS de una familia) produce un borrador corregido real (Markdown mínimo) trazable a hallazgos.
3. Cero requests 401/403 silenciosos en Mission Control durante una sesión completa de navegación (cierre real de H, con Playwright).
4. `factory_selfcheck.sh` PASS=4, suite de tests ampliada sin regresión de las 37 actuales.

## 18. Fases de implementación (para aprobación una por una — regla del proyecto: una fase por sesión/commit)

1. **Fase A** — conectar `fda_part11_agent` a Ollama real vía `gmp-api`, sobre el piloto Rockwell únicamente (14 archivos), sin tocar Annex11/ALCOA+ todavía. Criterio de salida: hallazgos con `prompt_version` real, comparables lado a lado con los hallazgos keyword-scan actuales (regresión controlada, no reemplazo ciego).
2. **Fase B** — replicar a `eu_annex11_agent` y `alcoa_plus_agent` con el mismo patrón validado en A.
3. **Fase C** — trazabilidad requisito-por-requisito real (`requirements_traceability_agent` vía perfil `csv`).
4. **Fase D** — generador de borrador corregido (§13), solo Markdown primero, DOCX/XLSX después.
5. **Fase E** — Mission Control: campos de versión + cola visible + cierre completo de H.
6. **Fase F** — extensión a los 32 documentos completos (solo tras piloto Rockwell verde, regla 12 del encargo).

## 19. Rollback

Cada fase es aditiva sobre el pipeline determinista existente (que sigue funcionando igual si Ollama falla — fallback a keyword-scan con `confianza: baja` y nota explícita de degradación, nunca fallo silencioso). Revertir una fase = `git revert` del commit de esa fase; el estado persistente (`documents.jsonl`) es append-only, un rollback de código no borra histórico ya auditado.

## 20. Estimación de impacto

- **Código nuevo:** ~400-600 líneas (cliente Ollama para el pipeline + generador de borrador), reduce (no aumenta) las 660 líneas actuales de `compliance_agents.py`+lógica keyword al reemplazar el motor, no la estructura.
- **Runtime:** Fase A sobre 14 documentos Rockwell con Ollama secuencial — latencia estimada varios minutos por documento (varias llamadas por checkpoint regulatorio), muy superior a los 118s actuales del keyword-scan; es el costo esperado y aceptado explícitamente por la regla D ("calidad sobre velocidad").
- **Sin impacto en producto base** (`gmp-api` puerto 8000 no se modifica, solo se consume su API existente) ni en contenedores `aria-*`/`hotelbot-*`.
