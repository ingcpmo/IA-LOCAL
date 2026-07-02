# W6 — Mission Control Enterprise + Operational Agent Tasks + Regulatory Case Memory

**Fase A — Análisis y diseño.** 2026-07-02. Basado en inventario real del sistema
(7 vistas actuales, ~70 endpoints existentes, 11 módulos JS de W5.2, paleta CSS actual).
Ningún archivo de código modificado en esta fase.

---

## 1. Diagnóstico UX actual de Mission Control

### Lo que existe (evidencia real, no suposición)

Navegación plana de 7 vistas: `01 Panel general · 02 Crear misión · 03 Aprobación
de misión · 04 Pipeline Capa 8 · 05 Revisión humana · 06 Auditoría · 07 Estado del
sistema`, más un detail panel lateral por misión (7 grupos de evidencia: design,
code, tests, headless, RCs, deploy, audit), consola de pruebas W4 y dashboard GMP
W4.1 con PDF. Frontend: 361 líneas HTML + 243 CSS + 1 672 JS en 11 módulos ES.

### Fortalezas (conservar, no rediseñar desde cero)

- **Evidence-first**: todo lo mostrado sale de endpoints reales; no hay datos inventados.
- Paleta semántica ya correcta: `--pass/--warn/--fail`, `--accent` dorado = sello de
  auditoría, `--human` violeta = decisión humana Part 11. Ese lenguaje de color es un
  activo GMP: se mantiene.
- Detail panel con carga perezosa por grupo de evidencia — patrón correcto.
- Módulos ES limpios tras W5.2 — base sólida para reorganizar sin reescribir.

### Debilidades UX (el diagnóstico brutal)

| # | Problema | Impacto | Usuario afectado |
|---|----------|---------|------------------|
| D1 | Navegación plana de 7 ítems ordenada por flujo técnico, no por rol ni frecuencia de uso | Un QA que solo quiere ver el estado GMP pasa por vocabulario de Capa 8 | QA/QC, cliente |
| D2 | No existe vista ejecutiva: el "Panel general" es operativo (misiones + cola), no responde "¿cómo está el sistema hoy?" en 5 segundos | Dirección no tiene entrada propia | Dirección, cliente |
| D3 | JSON crudo como presentación primaria en evidencia técnica y auditoría | Ilegible para no-desarrolladores; el JSON debe ser el *detalle*, no la *portada* | QA/QC, auditor |
| D4 | Trazabilidad objetivo→agente→prueba→evidencia existe en datos (mission YAML → agents → test-catalog → test-results → audit) pero ninguna vista la dibuja como cadena | El argumento central GMP del producto es invisible | Auditor, cliente |
| D5 | Riesgos: `GET /status/risks` existe y ninguna vista lo consume | Información de gobierno ya pagada y no mostrada | Arquitecto, QA |
| D6 | Estética de consola dev (mono denso, índices 01-07 sin semántica de secuencia real) | Transmite "herramienta interna", no "producto enterprise" | Cliente, dirección |
| D7 | Sin breadcrumb ni contexto de misión persistente: al cambiar de vista se pierde "en qué misión estoy" | Reorientación constante | Todos |
| D8 | Agentes: `GET /agents/profiles` y `GET /missions/{id}/agents` existen; no hay vista de agentes | Capa 6 invisible en la UI | Todos |
| D9 | Readiness piloto/go-live: no existe ni endpoint ni vista | Decisión go/no-go sin soporte visual | QA, dirección |
| D10 | Sin estados vacíos diseñados: vistas sin datos muestran tablas vacías sin explicar qué falta | Confusión en misiones tempranas | Todos |

**Nota UX global actual: 62/100.** Sólido en datos y auditabilidad, débil en
jerarquía, roles, legibilidad no-técnica y narrativa de trazabilidad.

---

## 2. Propuesta visual y funcional del nuevo browser

### Principios

1. **La evidencia manda, la presentación se adapta al rol.** Mismo dato, tres
   altitudes: KPI (ejecutivo) → tabla legible (QA) → JSON/log crudo (técnico,
   siempre disponible tras un toggle "Evidencia técnica", nunca eliminado).
2. **El color semántico existente es ley**: pass/warn/fail + dorado auditoría +
   violeta decisión humana. Se conserva y se aplica con más consistencia (pills,
   franjas de severidad, sellos).
3. **Read-only por defecto.** Toda acción de escritura queda visualmente marcada
   (botón "humano" violeta) y concentrada en las vistas de gobierno.
4. **Sin pérdida**: las 7 vistas actuales sobreviven; el rediseño reagrupa y añade,
   no elimina evidencia ni funciones W4/W4.1/W4.1.1.

### Sistema visual (tokens W6, evolución de los actuales)

- Mantener modo oscuro como primario (coherente con operación 24/7 y contraste de
  sellos); subir contraste de `--muted` para legibilidad QA.
- Tipografía: sans actual para UI; mono SOLO para hashes, IDs, timestamps y JSON —
  nunca para labels de navegación (hoy el mono en nav grita "dev console").
- Jerarquía por tarjetas con franja de severidad izquierda (2 px) en lugar de
  bordes completos de color; `tabular-nums` en toda columna numérica.
- Navegación agrupada por dominio con secciones tituladas (ver mapa), badge de
  conteo en cola de revisión, breadcrumb superior `Misión: <id> · <estado>`
  persistente cuando hay misión seleccionada.
- Estados vacíos con texto explicativo y siguiente acción sugerida.
- Vistas 11-13 llevan banner permanente `MODO DISEÑO — sin ejecución real` (ámbar).

### Navegación propuesta (5 grupos, 13 vistas)

```
VISIÓN        01 Executive Overview
MISIONES      02 Mission Detail   03 Agents   04 Functional Tests
              05 GMP Dashboard    06 Reports / PDF
GOBIERNO      07 Crear/Aprobar misión  08 Revisión humana (RC)
              09 Pipeline Capa 8       10 Deployments
CUMPLIMIENTO  11 Audit Trail  12 Risks & Readiness  13 Validation / GAMP 5
INTELIGENCIA  14 Operational Agent Tasks  15 Regulatory Sources  16 Case Memory
              (grupo completo en MODO DISEÑO)
```

(La numeración es de navegación, no de secuencia. Las 13 vistas pedidas mapean:
Crear/Aprobar y Revisión/Pipeline se conservan del actual como vistas de gobierno.)

---

## 3. Mapa de vistas enterprise (13 vistas)

Formato: **Propósito · Usuario · Datos · Acciones · Endpoints · Riesgos · Pruebas.**
"END existente" = ya está en producción; "END diseño" = read-only nuevo propuesto.

### V1 — Executive Overview
- **Propósito**: estado del sistema en 5 segundos: misiones activas, semáforo GMP por misión, cola de revisión, salud de stacks, riesgos abiertos.
- **Usuario**: dirección, cliente, QA lead.
- **Datos**: nº misiones por estado, semáforo (pass/warn/fail agregado del gmp-report), pendientes de decisión humana, deployments vivos, top-3 riesgos.
- **Acciones**: solo navegación (drill-down a misión). Cero escritura.
- **Endpoints**: existentes — `/layer9/missions`, `/layer9/review-queue`, `/status/full`, `/status/risks`, `/layer9/missions/{id}/summary`.
- **Riesgos**: agregación engañosa si un KPI resume mal (mitigar: cada KPI enlaza a su evidencia).
- **Pruebas**: JS render con datos reales de misión OOS; estado vacío sin misiones; agregación pass/warn/fail correcta contra gmp-report conocido.

### V2 — Mission Detail
- **Propósito**: hoy es panel lateral; pasa a vista completa con cabecera de misión (estado, aprobador, fechas) + **cadena de trazabilidad dibujada**: objetivo → agentes → pruebas → evidencia → RC → deploy (D4).
- **Usuario**: QA/QC, arquitecto, auditor.
- **Datos**: mission YAML legible, agentes asignados, resumen de tests, RCs, deployment, últimos eventos de auditoría de la misión.
- **Acciones**: lectura; enlaces a vistas hermanas; las decisiones siguen en Gobierno.
- **Endpoints**: existentes — `/layer9/missions/{id}`, `/summary`, `/agents`, `/tests`, `/rcs`, `/deployment`, `/audit`, `/layer8/missions/{id}/artifacts`.
- **Riesgos**: sobrecarga (mitigar: cargas perezosas por sección, patrón ya probado en detail panel).
- **Pruebas**: smoke de grafo de módulos; render de cadena de trazabilidad con misión OOS real; todos los enlaces resuelven.

### V3 — Agents
- **Propósito**: capa 6 visible: agentes base, perfiles derivados, agentes por misión, corpus/colección asociada (D8).
- **Usuario**: arquitecto, QA, cliente.
- **Datos**: catálogo (agent_id, nombre, alcance, colección RAG, misión que lo usa), origen (base / perfil / custom).
- **Acciones**: lectura.
- **Endpoints**: existentes — `/agents/profiles`, `/layer9/missions/{id}/agents`.
- **Riesgos**: no exponer system prompts completos si contienen detalles sensibles (mostrar alcance, no prompt íntegro).
- **Pruebas**: render con perfiles reales; agente sin misión asignada; misión sin agentes.

### V4 — Functional Tests (evolución de la consola W4)
- **Propósito**: consola W4 actual + resumen por agente (pass rate, última corrida) encima del detalle crudo.
- **Usuario**: QA/QC, técnico.
- **Datos**: catálogo curado, resultados históricos, latencias, run_by.
- **Acciones**: ejecutar test/suite (existente, humano, sin cambios de lógica W4).
- **Endpoints**: existentes — `/test-catalog`, `/test-results`, `/tests`, `POST /test/run`, `POST /test/run-suite`.
- **Riesgos**: NO tocar executor ni contratos W4 — el rediseño es solo de presentación.
- **Pruebas**: regresión completa test_functional_testing; UI pinta PASS/FAIL/ERROR idéntico al contrato actual.

### V5 — GMP Dashboard (W4.1, intacto)
- **Propósito**: el dashboard actual con mejor jerarquía visual (KPIs arriba, secciones colapsables).
- **Usuario**: QA/QC, auditor, cliente.
- **Datos**: los 18 bloques del gmp-report (sin cambio de fuente).
- **Acciones**: lectura + descargar PDF (existente).
- **Endpoints**: existentes — `/gmp-report`, `/gmp-report.pdf`.
- **Riesgos**: regla dura — cero cambio de lógica W4.1/W4.1.1; solo CSS/estructura de presentación.
- **Pruebas**: `/gmp-report` y PDF byte-idénticos tras el cambio; test_gmp_report + test_pdf_robust en verde.

### V6 — Reports / PDF
- **Propósito**: biblioteca de reportes generados por misión (PDF GMP, gates report) con fecha, tamaño, hash — hoy dispersos.
- **Usuario**: QA, auditor, cliente.
- **Datos**: lista de PDFs/reportes existentes por misión (solo los ya generados; no genera nuevos).
- **Acciones**: descargar (existente).
- **Endpoints**: existentes — `/gmp-report.pdf`, `/deployments/{id}/gates-report`; **END diseño** — `GET /layer9/missions/{id}/reports` (lista read-only de artefactos de reporte ya presentes en disco, sin escribir nada).
- **Riesgos**: listar solo rutas permitidas por path_policy; jamás exponer .env ni secretos.
- **Pruebas**: listado coincide con disco; path traversal negado; misión sin reportes → estado vacío.

### V7 — Audit Trail
- **Propósito**: auditoría legible: tabla evento/actor/misión/timestamp con sello de verificación de cadena arriba; JSON por entrada bajo toggle (D3).
- **Usuario**: auditor, QA.
- **Datos**: entradas de auditoría, verify_chain (267+ entradas, forks explicados en lenguaje Part 11).
- **Acciones**: lectura, filtro por misión/tipo.
- **Endpoints**: existentes — `/audit/verify`, `/audit/summary`, `/audit/entries`, `/layer9/missions/{id}/audit`.
- **Riesgos**: nunca escribir; paginación con `limit` existente para no releer archivo completo por render.
- **Pruebas**: sello WARN de fork se explica; entradas coinciden con archivo; filtros correctos.

### V8 — Deployments
- **Propósito**: los deployments vivos con puerto, health, versión canónica del RC, uptime.
- **Usuario**: arquitecto, técnico, dirección.
- **Datos**: deployment por misión, gates report, RC canónico.
- **Acciones**: lectura (deploy sigue en pipeline Capa 8 con aprobación, sin cambios).
- **Endpoints**: existentes — `/deployments/{id}`, `/gates-report`, `/layer9/projects/{id}/canonical`, `/status/full`.
- **Riesgos**: no mostrar API keys de deployments; no acciones de restart desde UI.
- **Pruebas**: health real del OOS 8102 se refleja; deployment caído → estado claro, no error JS.

### V9 — Risks & Readiness
- **Propósito**: consumir `/status/risks` (D5) + matriz de readiness piloto/go-live por misión con semáforo por dimensión (corpus, CSV, roles, LIMS…), basada en hechos del sistema, no en juicios inventados.
- **Usuario**: QA lead, dirección, arquitecto.
- **Datos**: riesgos vivos, aceptaciones de riesgo (`/layer9/risks/{id}/accept` history), checklist de readiness con estado derivado de evidencia (ej. "corpus regulatorio: NO — 0 fuentes conectadas").
- **Acciones**: lectura; aceptar riesgo permanece como acción humana existente.
- **Endpoints**: existentes — `/status/risks`, decisiones; **END diseño** — `GET /layer9/missions/{id}/readiness` (read-only, deriva el checklist de datos existentes; donde no hay dato dice `sin evidencia`, nunca inventa).
- **Riesgos**: el mayor riesgo GMP de la vista es sugerir readiness optimista — regla: cada dimensión cita su evidencia o dice "sin evidencia".
- **Pruebas**: readiness de misión OOS refleja exactamente lo que existe; dimensión sin datos → "sin evidencia".

### V10 — Validation / GAMP 5
- **Propósito**: estado del paquete documental CSV por misión según diseño W5 FASE 3 (22 documentos): cuáles existen, cuáles faltan, quién aprueba.
- **Usuario**: QA/validación, auditor.
- **Datos**: matriz de 22 documentos × estado (`no iniciado / generado / aprobado`) — hoy casi todo `no iniciado`, y eso se muestra honestamente.
- **Acciones**: lectura (la generación del paquete es backlog 85→90, requiere aprobación futura).
- **Endpoints**: **END diseño** — `GET /layer9/missions/{id}/validation-package` (lee un `dossier.yaml` si existe; si no, devuelve la plantilla de 22 docs todos `not_started`).
- **Riesgos**: no simular avance documental; estados solo desde disco.
- **Pruebas**: sin dossier → 22 not_started; dossier parcial → estados correctos.

### V11 — Operational Agent Tasks (MODO DISEÑO)
- **Propósito**: ver y (a futuro) gobernar tareas operativas asignadas a agentes. En W6: catálogo de especificaciones de tarea en estado `draft_design`, sin ejecutor, sin cron.
- **Usuario**: QA/QC (responsable humano), arquitecto.
- **Datos**: TaskSpecs (sección 4), matriz A-F, historial vacío con estado vacío explicando que no existe ejecutor.
- **Acciones**: SOLO lectura en W6. Crear/activar/pausar = deshabilitado con tooltip "requiere aprobación de fase futura".
- **Endpoints**: **END diseño** — `GET /layer9/agent-tasks` (lee `factory/agent_tasks/tasks.yaml`, specs marcadas `draft_design`), `GET /layer9/agent-tasks/{task_id}`.
- **Riesgos**: que un usuario crea que las tareas corren (mitigar: banner MODO DISEÑO + estado `draft_design` en cada fila + historial "0 ejecuciones").
- **Pruebas**: render de specs; imposibilidad de POST (405/404); banner presente.

### V12 — Regulatory Sources (MODO DISEÑO)
- **Propósito**: source registry visible: qué fuentes oficiales están definidas, su modo de acceso, rate limit, y estado `not_connected`.
- **Usuario**: QA, arquitecto, auditor.
- **Datos**: registro de las 7 fuentes (sección 7) con URL oficial real, autoridad, tipo de acceso (API/listado), límites diseñados, `last_checked: null`.
- **Acciones**: SOLO lectura. "Conectar" deshabilitado (aprobación futura).
- **Endpoints**: **END diseño** — `GET /layer9/regulatory-sources` (lee `factory/regulatory/source_registry.yaml`).
- **Riesgos**: cero tráfico saliente en W6 — el endpoint lee YAML local, nunca hace HTTP externo.
- **Pruebas**: sin conexiones salientes (verificable: no httpx a dominios externos en el módulo); URLs bien formadas; estado not_connected visible.

### V13 — Case Memory (MODO DISEÑO)
- **Propósito**: la memoria de casos regulatorios (sección 6): buscador + tarjetas de caso. En W6 la memoria está vacía y la vista muestra el esquema y el flujo de 6 pasos.
- **Usuario**: QA/QC, analista de desviaciones.
- **Datos**: case records (0 en W6), esquema del record, explicación del flujo pointer→metadata→summary→embedding→selective fetch.
- **Acciones**: SOLO lectura; búsqueda opera sobre memoria local (vacía en W6).
- **Endpoints**: **END diseño** — `GET /layer9/case-memory` y `GET /layer9/case-memory/search?q=` (leen `factory/regulatory/case_memory/*.jsonl`, vacío en W6; sin llamadas externas).
- **Riesgos**: confusión de memoria vacía con fallo (mitigar: estado vacío pedagógico); jamás poblar con casos inventados.
- **Pruebas**: memoria vacía → estado vacío correcto; search sin resultados no rompe; cero HTTP externo.

---

## 4. Modelo de tareas operativas de agentes

### TaskSpec (esquema YAML — `factory/agent_tasks/tasks.yaml`)

```yaml
task_id: string (snake_case, único)
status: draft_design | pending_approval | approved | active | paused | ended
agent_id: string            # agente/perfil existente (catálogo Capa 6)
objective: string           # objetivo verificable, una frase
task_type: enum             # ver tipos abajo
source: enum                # uploaded_docs | mission_evidence | test_results |
                            # regulatory_source:<id> | case_memory
connector: string           # ruta local o source_id del registry (nunca URL libre)
schedule:
  mode: reactive | scheduled
  frequency: null | cron-expr    # null en reactive
  window: "HH:MM-HH:MM"          # horario permitido
limits:
  max_runtime_s: int             # p.ej. 300
  max_items: int                 # volumen máximo por ejecución
  max_external_requests: int     # 0 salvo task_type regulatorio aprobado
access_mode: read_only | write_controlled   # write solo a su carpeta de salida
ollama:
  allowed: bool
  purpose: summarize | classify | compare | draft_report | none
  template_id: string            # SOLO prompts de plantillas aprobadas
success_criteria: [string]       # verificables por reglas Python
alert_criteria: [string]         # qué dispara alerta QA/QC
output: enum                     # summary_md | evidence_json | alert | qa_report
report_path: factory/agent_tasks/outputs/<task_id>/   # única ruta de escritura
audit: true                      # SIEMPRE: 1 evento por ejecución (inicio+resultado)
human_owner: string              # nombre real (regla run_by de W4)
autonomy_level: A | B | C | D | E | F
pause: {enabled: true}           # pausable siempre, desde Mission Control
escalation: string               # a quién y cuándo escala
approval_required: bool          # true para activar; siempre true en E
```

### Tipos de tarea × matriz de autonomía (asignación por diseño)

| Tipo de tarea | Nivel máx. | Justificación |
|---|---|---|
| Analizar documentación cargada | B | Read-only sobre docs internos |
| Revisar evidencia de misión | B | Read-only sobre evidencia existente |
| Validar resultados contra reglas Python | C | Genera evidencia determinista |
| Consultar fuentes regulatorias oficiales | B→D | Read-only externo con rate limit; hallazgo crítico → alerta (D) |
| Buscar casos similares (OOS/HPLC/DI) | B | Búsqueda en memoria local |
| Generar resumen técnico | C | Evidencia, marcada "generado por agente" |
| Generar reporte QA/QC | C+E | El reporte se genera (C) pero su USO requiere aprobación (E) |
| Generar alerta | D | Alerta a humano, nunca acción |
| Preparar evidencia para revisión humana | C | Paquete para decisión humana |
| Liberar lote, cerrar desviación, aprobar investigación, modificar datos originales, cambiar SOP, aprobar CSV, decisión GMP final | **F** | **Prohibido automatizar — sin excepción** |

### Ciclo de vida y gobierno

```
draft_design → pending_approval → approved → active ⇄ paused → ended
                     ↑ humano                ↑ humano activa
```
- Toda transición la ejecuta un humano identificado (regla run_by) y se audita.
- Sin loops libres: toda ejecución tiene task_id, límites duros de tiempo/volumen,
  y termina. No hay auto-reprogramación ni tareas que crean tareas.
- Registro por ejecución (`factory/agent_tasks/runs/<task_id>.jsonl`): timestamp,
  duración, items procesados, resultado, alertas, hash del output, evento de audit.
- **En W6 solo existe el esquema + specs draft_design + vista read-only. El
  ejecutor/scheduler NO se implementa (aprobación futura).**

---

## 5. Modelo de gobierno Ollama (LLM Governance)

**Regla central: Ollama razona y asiste · Reglas Python validan · Mission Control
gobierna · Auditoría registra · QA/QC decide.**

| Dimensión | Regla |
|---|---|
| Cuándo puede consultar | Solo dentro de una tarea aprobada cuyo TaskSpec tenga `ollama.allowed: true`, y solo para el `purpose` declarado |
| Datos que PUEDE recibir | Resúmenes de casos de la memoria, evidencia de misión ya sanitizada, texto de documentos internos cargados, plantilla aprobada |
| Datos que NO puede recibir | Secretos/.env/API keys, datos de paciente o lote reales no anonimizados, auditoría cruda completa, credenciales, contenido fuera del connector declarado |
| Registro por llamada | `llm_call_record`: task_id, template_id, hash del prompt, contexto (refs, no copia), modelo+versión (p.ej. llama3.2), respuesta, timestamp, latencia, resultado de validación — en `factory/agent_tasks/runs/` + evento de auditoría |
| Validación de salida | Toda cifra/spec/cita pasa por reglas Python; salida sin fuente citada se marca `unverified` y no puede entrar a un reporte QA |
| Escalación a humano | Confianza baja declarada, contradicción con reglas, alerta disparada, o task_type nivel D/E |
| Anti-invención | Prompts de plantilla exigen "solo del contexto provisto, cita source_pointer o responde 'sin evidencia'"; validador de citas rechaza afirmaciones sin pointer |
| Fallback | Timeout/error de Ollama → la tarea termina `degraded` con parte determinista completa; nunca reintenta en loop; alerta si es crítico |
| Regresión | Set de prompts conocidos con salidas esperadas (marcador, no igualdad exacta): correr tras cambio de modelo/plantilla; guardar en `factory/agent_tasks/regression/` |
| Prohibiciones | Aprobar, cerrar, liberar, modificar datos, disposición de lote, reemplazar QA/QC — nivel F |

En W6 esto es diseño: no se toca la integración Ollama existente de los deployments.

---

## 6. Modelo Regulatory Case Memory & Selective Retrieval

**Estrategia: source pointer + metadata + summary + embedding + selective fetch.**
Nunca descarga masiva; nunca almacenar documentos completos por defecto.

### Case record (esquema — `factory/regulatory/case_memory/cases.jsonl`)

```yaml
case_id: string
url: string                    # documento original
source_id: string              # FK a source_registry
authority: FDA | EMA | EudraGMDP | internal
consulted_at: timestamp        # primera consulta
last_checked: timestamp        # revalidación de frescura
case_type: warning_letter | 483 | recall | non_compliance | oos | data_integrity | internal
summary: string (≤ 1200 chars) # resumen corto, NO el documento
tags: [string]                 # taxonomía de desviaciones
keywords: [string]
content_hash: string           # SHA-256 del contenido consultado (detecta cambios)
embedding_ref: string          # id del vector del RESUMEN (no del documento)
retrieval_path: string         # cómo volver al detalle (URL + selector/página)
relevance: float               # score asignado en indexación
```

### Flujo de recuperación (6 pasos, cada uno auditado)

1. El agente busca en la memoria local (vector search sobre embeddings de resúmenes).
2. Encuentra casos similares por embedding + tags + keywords.
3. Identifica los source pointers relevantes (URLs oficiales).
4. **Selective fetch**: recupera SOLO el caso específico necesario (1 documento,
   rate-limited, respetando robots), nunca el corpus.
5. Cita obligatoriamente: autoridad + URL + fecha de consulta + hash.
6. Genera análisis bajo reglas Python + plantilla Ollama aprobada + revisión humana.

### Los 11 componentes

Clasificación honesta (skill gmp-agent-design): 6 son **servicios Python
deterministas** (no necesitan LLM ni son "agentes"), 5 son **agentes/perfiles**.
Perfiles derivados propuestos: `audit` (FDA 483 Inspector) cubre ~75 % de
interpretación GMP → `audit_regintel_profile`; `capa` cubre taxonomía de
desviaciones → `capa_taxonomy_profile`. Cero agentes nuevos hasta que un corpus
propio lo justifique (checklist de 60+ chunks citables).

| Componente | Tipo | Responsabilidad | Input → Output | Puede guardar | NO puede guardar | Límites / Riesgos | Auditoría / Pruebas |
|---|---|---|---|---|---|---|---|
| source_registry | Servicio (YAML+loader) | Catálogo de fuentes oficiales | — → registro validado | URL, autoridad, modo acceso, rate limit, robots, last_checked | Credenciales, contenido | Solo fuentes aprobadas por humano / fuente maliciosa añadida | Alta/edición de fuente = evento audit; test: esquema válido, URL oficial |
| source_connector_readonly | Servicio | Único punto de salida HTTP; GET only, rate-limited, User-Agent identificado | source_id+ruta → respuesta cruda | Nada (pasa a extractor) | Nada persistente | 1 req/s por fuente, backoff, respeta robots.txt, timeout 30 s / bloqueo por la fuente | Cada request = registro (URL, status, bytes); test: rechaza POST, rechaza dominio fuera de registry |
| metadata_extractor | Servicio | Extraer título, fecha, autoridad, tipo de la respuesta | HTML/JSON → metadata dict | Metadata estructurada | Documento completo | Best-effort; cambio de estructura de la fuente → marca `extract_failed`, no inventa | Test: fixtures de páginas reales archivadas; extracción parcial no rompe |
| case_indexing_agent | Agente (Ollama resumen) | Crear case record: resumen ≤1200 chars + keywords | metadata+texto → case record | El record (resumen, tags, hash) | Texto completo, adjuntos | Resumen debe derivar solo del texto provisto / alucinación en resumen (mitigar: validador de citas) | Evento por caso indexado; test: resumen no contiene afirmaciones sin soporte en fixture |
| deviation_taxonomy_agent | Perfil de `capa` | Clasificar caso en taxonomía (OOS, DI, ALCOA+, esterilidad…) | case record → tags | Tags | Nada nuevo | Taxonomía cerrada y versionada; no crea categorías / clasificación errónea (mitigar: multi-label + revisión muestral humana) | Test: ≥5 casos fixture con clasificación esperada |
| case_memory_agent | Servicio | Persistir/actualizar records + embeddings de resúmenes | record → memoria actualizada | Records + vectores de resúmenes | Documentos, PII | Append-only con dedupe por content_hash / crecimiento sin control (mitigar: tope + política retención) | Escrituras auditadas; test: dedupe, corrupción de línea no rompe lectura |
| case_retrieval_agent | Servicio | Búsqueda semántica+filtros sobre memoria | query → top-k casos con pointers | Log de consulta | Nada | Solo memoria local, nunca sale a internet / resultados irrelevantes (mitigar: umbral score) | Test: query OOS/HPLC devuelve fixture esperado; memoria vacía → [] |
| selective_fetch_agent | Servicio | Recuperar 1 documento específico bajo demanda vía connector | case_id → contenido temporal | Hash actualizado, extracto citado (≤ límite) | Documento completo por defecto | 1 doc por invocación, humano o tarea aprobada lo dispara / fetch masivo encadenado (mitigar: presupuesto de requests por tarea) | Evento por fetch; test: segundo fetch mismo doc usa cache/hash |
| evidence_citation_agent | Servicio | Validar que todo análisis cita pointer válido y vigente | análisis → pass/fail + citas | Reporte de validación | Nada | Cita rota o hash cambiado → bloquea el análisis | Test: análisis sin citas → fail; cita con hash viejo → warn revalidar |
| source_freshness_agent | Servicio | Revalidar fuentes/casos (HEAD/hash), detectar cambios de estructura | registry/memoria → estados frescura | last_checked, diffs de hash | Contenido | Solo HEAD/GET puntual rate-limited; programable máx. nivel B / fuente reorganizada silenciosamente (detectado por extract_failed) | Test: hash cambiado → flag stale; fuente caída → warn, no error |
| ollama_interpretation_agent | Perfil de `audit` | Interpretar relevancia del caso para el sitio/misión; redactar análisis borrador | casos+contexto misión → borrador con citas | Borrador marcado `draft-agent` | Decisiones, aprobaciones | Todo output es borrador para humano; nivel máx. D / tono conclusivo (mitigar: plantilla exige lenguaje "sugerencia") | llm_call_record por uso; test regresión: prompts conocidos, salida cita fuentes |

---

## 7. Modelo de fuentes online read-only

### Source registry inicial (`factory/regulatory/source_registry.yaml` — estado `not_connected` en W6)

| source_id | Fuente | Autoridad | Acceso diseñado | Rate limit diseño |
|---|---|---|---|---|
| fda_warning_letters | FDA Warning Letters | FDA | Listado HTML público paginado, filtro drugs/GMP | 1 req/2 s, ≤ 20 págs/día |
| fda_483_public | Inspection Observations / 483 públicas (FOIA reading room, si aplica) | FDA | Listados públicos; muchos 483 no están online — se registra la limitación, no se simula | 1 req/2 s |
| fda_data_dashboard | FDA Data Dashboard | FDA | API pública JSON | según ToS API, ≤ 1 req/s |
| openfda_enforcement | openFDA Drug Enforcement/Recalls | FDA | API REST JSON oficial (api.fda.gov, key gratuita) | límite oficial openFDA |
| eudragmdp_nc | EudraGMDP Non-Compliance | EMA/EU | Búsqueda pública del portal | 1 req/2 s, consultas puntuales |
| ema_gmp_public | EMA public GMP info | EMA | Páginas públicas de guidance | 1 req/2 s |
| internal_docs | Documentos internos cargados | interna | Filesystem local (carpeta de carga) | n/a |

### Requisitos duros (aplican a cualquier implementación futura)

read-only por defecto · rate limits por fuente · sin scraping agresivo (sin
paralelismo, sin crawling recursivo, User-Agent identificado, robots.txt) · sin
descarga masiva · sin almacenar documentos completos por defecto · citación
obligatoria · trazabilidad completa (cada byte externo tiene URL+fecha+hash) ·
revalidación de frescura · no inventar · sin decisiones GMP autónomas.

**En W6: el registry es un YAML local y la vista lo muestra. CERO tráfico saliente.**

---

## 8. Riesgos GMP / CSV / seguridad del W6

| # | Riesgo | Severidad | Mitigación en diseño |
|---|---|---|---|
| R1 | Usuario confunde vistas MODO DISEÑO con capacidades reales | Alta (integridad) | Banner permanente, estados `draft_design`/`not_connected`, historial "0 ejecuciones", botones de acción deshabilitados |
| R2 | Rediseño rompe W4/W4.1/W4.1.1 | Alta | Solo presentación; contratos intactos; regresión completa en Fase C |
| R3 | Nuevos endpoints read-only filtran rutas/secretos | Alta | path_policy + sanitizador existentes; endpoints leen SOLO yaml/jsonl de carpetas nuevas dedicadas |
| R4 | Futuro: memoria de casos con derechos de autor/PII | Media | Solo resúmenes+pointers; documentos completos nunca por defecto |
| R5 | Futuro: fuente oficial bloquea por abuso | Media | Rate limits, robots, UA identificado, presupuesto por tarea |
| R6 | Futuro: Ollama alucina en análisis regulatorio | Alta | Validador de citas, plantillas, borrador-para-humano, regresión |
| R7 | Vista readiness sugiere preparación inexistente | Alta (GMP) | Cada dimensión cita evidencia o dice "sin evidencia" |
| R8 | Crecimiento del frontend vuelve a monolito | Baja | Mantener módulos ES por vista (patrón W5.2) |

---

## 9. Qué se puede implementar AHORA sin riesgo (propuesta Fase B)

1. **Reorganización de navegación** en 5 grupos + breadcrumb de misión (HTML/CSS/JS).
2. **Refinamiento visual**: contraste, pills de estado, franjas de severidad, mono
   solo para datos, tabular-nums, estados vacíos diseñados.
3. **V1 Executive Overview** — solo endpoints existentes.
4. **V9 Risks** (mitad riesgos) consumiendo `/status/risks` existente.
5. **Vistas V11/V12/V13 en MODO DISEÑO** (mock read-only, banner, cero red externa).
6. **Archivos de diseño**: `factory/agent_tasks/tasks.yaml` (2-3 TaskSpecs
   `draft_design`), `factory/regulatory/source_registry.yaml` (7 fuentes
   `not_connected`), carpeta `case_memory/` vacía con README.
7. **Endpoints read-only de diseño** (aditivos, sin tocar auditoría):
   `GET /layer9/agent-tasks`, `GET /layer9/regulatory-sources`,
   `GET /layer9/case-memory` (+search local).
8. **Tests**: pytest de los endpoints nuevos + JS check + smoke de módulos.
9. **Este documento** como documentación técnica.

Fuera de Fase B aunque serían "seguros": V2 completa, V6, V10 y readiness — son
más frontend del que conviene meter en un solo commit; propuestos como W6.1.

## 10. Qué requiere aprobación futura (NO en W6)

- Ejecutor/scheduler real de tareas (cron, procesos) — toca runtime.
- Conectores online reales y cualquier tráfico saliente a FDA/EMA.
- Embeddings reales de la memoria (elige modelo/deps — posible dependencia).
- Perfiles derivados `audit_regintel_profile` / `capa_taxonomy_profile` (checklist
  gmp-agent-design completo + corpus citable + aprobación).
- Nuevos eventos de auditoría para tareas (estructura de auditoría = aprobación).
- Generación del paquete CSV/GAMP 5 (backlog 85→90).
- Roles/firma electrónica, CORS, endpoints de escritura de tareas.
- Cualquier dato regulatorio real en la memoria de casos.
