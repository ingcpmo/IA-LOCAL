# W5 — Evolución senior hacia Factory 99%

**Fecha:** 2026-07-02 · **Baseline:** HEAD `9072f61` (W4.1) + W4.1.1 sin commitear (activo en runtime)
**Autor:** Capa 8 (Claude, arquitecto técnico) · **Aprueba:** Cesar (Capa 9)
**Alcance:** análisis y diseño (FASES 1–8). No modifica lógica validada W4/W4.1/W4.1.1.

---

## FASE 0 — Baseline (evidencia verificada 2026-07-02)

- Selfcheck Gate 0: **PASS=4 FAIL=0** — py_compile 121 archivos, pytest **269 passed**, audit chain 267 entradas (1 fork aceptado, 0 hash_errors), disco 56 %.
- 4 stacks Up y `/health` 200: gmp-api:8000, factory-api:9000, lab_qc:8101, oos:8102.
- W4.1/W4.1.1 verificados: `/api/v1/layer9/missions/oos_hplc_api_test/gmp-report` → 200; `gmp-report.pdf` → 200 (38.9 KB, 18 secciones).
- Archivos sucios preexistentes (excluidos de W5): `layer9.py`, `oos_hplc_api_test.yaml`, `review_queue.jsonl`, `runtime_config.yaml`.
- **Hallazgo W5-F0-1 (riesgo operativo):** `factory-api` corre `uvicorn --reload --reload-dir /app/factory` con bind-mount RW de `/home/ing_cpmo/factory`. Toda edición de `.py` en el host modifica el servicio vivo sin gate. Ver backlog 75→85.

---

## FASE 1 — Diagnóstico técnico brutal (notas 1–100)

| # | Componente | Nota | Prioridad |
|---|------------|------|-----------|
| 1 | Arquitectura global (capas 6–9) | 78 | Media |
| 2 | Capa 6 — agentes de dominio | 65 | Alta |
| 3 | Capa 7 — infraestructura factory | 80 | Baja |
| 4 | Capa 8 — constructor técnico | 82 | Baja |
| 5 | Capa 9 — gobierno humano | 75 | Media |
| 6 | Mission Control (UI) | 70 | Media |
| 7 | Backend API | 74 | Media |
| 8 | Auditoría (hash chain) | 85 | Baja |
| 9 | Test-results / W4 | 85 | Baja |
| 10 | Release candidates | 84 | Baja |
| 11 | Deployments | 78 | Media |
| 12 | Reporting / PDF | 82 | Baja |
| 13 | Seguridad | 62 | **Alta** |
| 14 | Sanitización | 75 | Media |
| 15 | Observabilidad | 60 | **Alta** |
| 16 | Tests | 80 | Media |
| 17 | Preparación GAMP 5 / CSV | 35 | **Crítica** |
| 18 | 21 CFR Part 11 | 55 | **Alta** |
| 19 | ALCOA+ | 70 | Media |
| 20 | Integración LIMS/CDS | 10 | Crítica (fase 95→99) |
| 21 | Fuentes online regulatorias | 5 | Alta (fase 90→95) |
| 22 | Piloto con datos reales | 20 | Crítica (fase 95→99) |
| 23 | Producción GMP plena | 40 | — (resultado, no componente) |

**Nota global honesta: ~75/100** — coincide con el punto de partida del backlog 75→99.

### Detalle por componente

**1. Arquitectura global — 78.**
Fortalezas: separación real capa 7/8/9 en paquetes Python; audit chain transversal; releases inmutables; puertos con fuente única de verdad.
Debilidades: `factory/api/routes/layer9.py` = 1 868 líneas / 36 endpoints / 59 funciones — monolito router que mezcla HTTP, agregación de evidencia, validación y presentación. `mission_control.html` = 2 177 líneas monolíticas.
Riesgo: cada cambio W4+ toca el mismo archivo gigante → regresiones. Impacto: mantenibilidad.
Para 99 %: extraer servicios (`gmp_report_service`, `mission_evidence_service`, `test_console_service`) dejando el router como capa HTTP fina; particionar UI en módulos JS.

**2. Capa 6 — agentes de dominio — 65.**
Fortalezas: agentes OOS operativos en :8102 con reglas Python + Ollama; distinción LLM vs reglas (W3.5); pruebas funcionales por agente (W4).
Debilidades: sin scheduler, sin tareas programadas, sin autonomía gobernada; corpus regulatorio incompleto (colecciones `gmp_fda_regulations`, `gmp_iq_oq_pq` mínimas); sin memoria de casos.
Riesgo: los agentes solo responden si un humano pregunta; ninguna vigilancia continua. Para 99 %: FASE 5 (Agent Task Scheduler) + FASE 7 (inteligencia regulatoria) + corpus completo.

**3. Capa 7 — 80.** Fortalezas: `ports.yaml`, `resource_policy.yaml`, workspaces aislados, plantilla por git tag, límites de recursos. Debilidades: validación de puertos manual (`ss -tlnp`), sin reconciliación automática registry↔Docker real. Para 99 %: read-only drift check en selfcheck.

**4. Capa 8 — 82.** Fortalezas: ciclo 13/13 demostrado (lab_qc RC v0.3.0); módulos pequeños y cohesivos (orchestrator 224 líneas, managers dedicados); autonomy policy engine; recovery manager. Debilidades: `claude_runtime` depende de disponibilidad de cuenta (observado en sesiones previas); sin métricas de calidad de generación por misión. Para 99 %: score de generación por misión + fallback documentado.

**5. Capa 9 — 75.** Fortalezas: misiones YAML con historia y aprobación humana real (`human_confirmed`), approval matrix, decision log, risk acceptance, review queue con lock. Debilidades: sin paquete documental CSV por misión (FASE 3); sin roles diferenciados (autor/revisor/aprobador son la misma API key); decisiones sin firma electrónica. Para 99 %: FASE 3 + roles + firma.

**6. Mission Control — 70.** Fortalezas: vista por misión, evidencia lazy, consola de pruebas W4, dashboard GMP W4.1, PDF descargable. Debilidades: HTML monolítico sin componentes; sin vista ejecutiva de readiness; sin mapa de riesgos; sin trazabilidad visual objetivo→agente→prueba→evidencia. Para 99 %: FASE 4.

**7. Backend API — 74.** Fortalezas: middleware de rate-limit y access-log; routers por dominio; dependencia única `verify_api_key`. Debilidades: API key única compartida (sin roles ni expiración); CORS `allow_origins=["*"]`; `audit_entries` relee el archivo completo por request; rate limit en memoria (se resetea al reload). Para 99 %: roles, CORS restringido, paginación eficiente.

**8. Auditoría — 85.** Fortalezas: hash chain SHA-256, semántica U6 de forks, verify endpoint, 0 hash_errors. Debilidades: sin export firmado, sin política de retención formal escrita, fork concurrente aceptado pero no eliminado (falta lock de escritor único). Para 99 %: escritor serializado + export + SOP de retención.

**9. W4 test-results — 85.** Fortalezas: catálogo curado, executor auditado, resultados persistidos, distinción LLM/reglas. Debilidades: sin tendencia histórica por agente; criterios de éxito por prueba no versionados como especificación. Para 99 %: specs versionadas + series temporales.

**10. RC — 84.** Fortalezas: inmutables, manifest + SHA256SUMS + gates report + approval; RC canónico explícito; idempotencia approve. Debilidades: sin diff firmado entre RC consecutivos. Para 99 %: comparador de RC.

**11. Deployments — 78.** Fortalezas: aislados, límites de recursos, Ollama compartido controlado. Debilidades: **W5-F0-1** (`--reload` + bind RW = el código host es el runtime, sin gate entre editar y ejecutar); sin health-check compuesto por deployment. Para 99 %: modo inmutable (imagen build) para deployments; `--reload` solo en dev.

**12. Reporting/PDF — 82.** Fortalezas: 18 secciones, mismo agregador que el dashboard (una sola verdad), sanitizado, auditoría opt-in exacta de 1 evento. Debilidades: sin paquete de validación CSV (el PDF actual es informe de evidencia, no dossier); numeración de páginas/TOC mejorable. Para 99 %: FASE 3 → generador de paquete documental.

**13. Seguridad — 62.**
Fortalezas: API key en todos los routers, secretos fuera del repo, sanitizador de reportes, rate limit, UFW (previo).
Debilidades: (a) API key única sin roles/rotación/expiración; (b) CORS `*`; (c) sin firmas electrónicas Part 11; (d) `--reload` en servicio expuesto (W5-F0-1); (e) sanitizador no cubre passwords embebidos en connection strings (`postgresql://user:pass@`, `redis://:pass@`) — **corregido en FASE 9**; (f) sin escaneo de dependencias.
Riesgo: una fuga de la única key da control total. Impacto: crítico en GMP. Para 99 %: roles + rotación + firma electrónica + build inmutable.

**14. Sanitización — 75.** Base sólida (claves sensibles por nombre, valores conocidos, patrón `sk-ant-`). Gap: conn-strings (FASE 9) y URLs con credenciales. Para 99 %: catálogo de patrones versionado + test de regresión por patrón.

**15. Observabilidad — 60.** Fortalezas: access log JSONL rotado 30 días, audit chain, selfcheck. Debilidades: sin métricas (latencia por endpoint, errores 5xx, uso Ollama), sin alertas, sin dashboard de salud agregada de los 4 stacks, sin correlación request→audit. Para 99 %: `/metrics` read-only + panel de salud en Mission Control + alertas por umbral.

**16. Tests — 80.** 269 passing, dominios bien cubiertos (audit, gates, reporte, PDF, rate-limit, path policy). Debilidades: sin medición de cobertura, sin CI (selfcheck es manual), tests de UI inexistentes. Para 99 %: coverage ≥80 % medido + hook pre-commit + smoke E2E.

**17. GAMP 5 / CSV — 35.** Existe evidencia técnica (tests, gates, RC, audit) pero **no existe el paquete documental** (URS, FRS, DS, IQ/OQ/PQ, VSR, trazabilidad). La categoría GAMP correcta es 5 (software a medida) para las soluciones custom. Para 99 %: FASE 3 completa.

**18. Part 11 — 55.** Cumple: audit trail seguro, timestamps UTC, atribución (`recorded_by`), no borrado de evidencia. No cumple: firmas electrónicas (§11.50/§11.70), unicidad de credenciales por individuo (§11.10(d) — API key compartida), controles de acceso por rol, verificación de identidad. Para 99 %: usuarios individuales + firma con significado (autor/revisor/aprobador) + vinculación firma-registro.

**19. ALCOA+ — 70.** Atribuible (parcial: `recorded_by` textual), Legible (sí), Contemporáneo (sí), Original (sí, JSONL append-only), Exacto (sí, hash). Débiles: Completo (evidencia dispersa), Consistente (formatos varían), Perdurable (sin política de retención/backup formal de audit), Disponible (export limitado). Para 99 %: matriz ALCOA+ por tipo de registro + política de retención escrita.

**20. LIMS/CDS — 10.** Solo diseño conceptual. Para 99 %: conectores read-only (CSV/API) con validación de esquema, en tramo 95→99.

**21. Fuentes online — 5.** No existe. Diseño en FASE 7.

**22. Piloto real — 20.** Datos de demo/sintéticos. Para 99 %: dataset representativo anonimizado + protocolo de piloto con criterios de aceptación.

---

## FASE 2 — Arquitectura objetivo 99 %

### Capas definitivas

```
Capa 9 — Gobierno humano        misiones, aprobaciones, firmas, riesgos, CSV dossier
Capa 8 — Constructor técnico    interpreta misión → genera solución → RC
Capa 7 — Infraestructura        workspaces, puertos, recursos, plantillas, releases
Capa 6 — Agentes de dominio     reglas Python (deciden) + Ollama (asiste) + scheduler
────────────────────────────────────────────────────────────────────────
Transversales: Auditoría (hash chain) · Seguridad (roles+firma) ·
Observabilidad (métricas+alertas) · Sanitización · Evidencia inmutable
```

### Separación física objetivo (dentro de `/home/ing_cpmo/factory/`)

| Dominio | Ruta | Regla |
|---------|------|-------|
| Código | `api/`, `core/`, `layer{6,7,8,9}/` | versionado git, tests obligatorios |
| Configuración | `registry/`, `runtime/` | YAML, cambios auditados |
| Evidencia | `test_results/`, `audit/`, `logs/` | append-only, nunca en commits de código |
| Reportes | `reports/` (nuevo) | generados, reproducibles desde evidencia |
| Documentos CSV | `validation/<project>/` (nuevo) | dossier por misión, versionado |
| Datos | `data/` (por deployment) | jamás tocados por la factory |
| Deployments | `deployments/` | inmutables post-deploy |
| Releases | `releases/`, `release_candidates/` | inmutables |

### Módulos backend objetivo

- `factory/services/` (nuevo): `gmp_report_service.py`, `mission_evidence_service.py`, `test_console_service.py`, `validation_package_service.py` — la lógica sale de `routes/layer9.py`; los routers quedan como capa HTTP fina (<300 líneas cada uno).
- `factory/layer6/` (nuevo): `task_scheduler.py`, `task_registry.yaml`, `llm_governance.py`, `source_registry.yaml`, conectores read-only (FASES 5–7).
- `factory/observability/` (nuevo): `metrics.py` (contadores en memoria + snapshot JSON read-only), `health_aggregator.py`.

### Módulos frontend objetivo

`factory/ui/` particionado: `mission_control.html` (shell) + `js/views/{executive,technical,csv,agents,tests,audit,rc,deployments,risks,sources,tasks}.js` + `js/api_client.js` (un solo punto de fetch con manejo de errores). Sin framework ni build (restricción de dependencias): módulos ES nativos.

### Ciclo completo de una misión (objetivo)

```
1. Cesar crea misión (Capa 9)          → mission.yaml + audit
2. Aprobación de misión (humana)        → firma electrónica
3. Capa 8 interpreta y diseña           → design.json + agents spec
4. Generación en workspace aislado      → código + tests
5. Quality gates (14)                   → gates_report
6. Paquete CSV generado (FASE 3)        → URS/FRS/DS/TM/IQ/OQ/PQ draft
7. RC inmutable                         → rc_manifest + SHA256SUMS
8. Revisión humana (dossier + diff)     → aprobación firmada
9. Deploy controlado (imagen inmutable) → IQ ejecutado y registrado
10. OQ/PQ sobre deployment              → evidencia W4 vinculada a TM
11. VSR + go-live readiness             → semáforo en Mission Control
12. Operación: scheduler Capa 6 + monitoreo + periodic review
13. Cambios → change control → nueva versión (nunca editar release)
14. Retiro → retirement plan + retención de evidencia
```

---

## FASE 3 — Paquete documental GAMP 5 / CSV por misión

Principio: **la Factory genera borradores desde evidencia real; el humano aprueba; nada se inventa.** Todo campo sin fuente se emite como `NO DISPONIBLE — requiere entrada humana` (mismo patrón anti-invención de W4.1).

Convención: `factory/validation/<project_id>/<DOC>-vN.md` + índice `dossier.yaml` con estado (draft/reviewed/approved), aprobador y hash.

| Doc | Fuente de datos | Genera Factory | Aprueba humano | Nunca inventar |
|-----|-----------------|----------------|----------------|-----------------|
| Intended Use | mission.yaml (objective, scope) | borrador desde misión | QA + dueño de proceso | uso clínico/decisional no declarado |
| GxP Impact Assessment | mission.yaml + cuestionario | plantilla + respuestas registradas | QA | clasificación de impacto |
| System Risk Assessment | risks/ + gates + diseño | matriz inicial (severidad×probabilidad) | QA + técnico | probabilidades sin datos |
| Supplier / AI Model Assessment | modelo Ollama (nombre, versión, cuantización), Anthropic (Capa 8) | ficha técnica de modelos, límites conocidos | QA | benchmarks no medidos |
| URS | mission.yaml requirements | lista numerada URS-n | dueño de proceso | requisitos no pedidos |
| FRS | design.json + endpoints reales | FRS-n trazado a URS | técnico + QA | funciones no implementadas |
| Design Spec | design.json + árbol de código real | módulos, interfaces, datos | técnico | — |
| Configuration Spec | docker-compose del deployment + env (sanitizado) + ports.yaml | inventario exacto | técnico | valores de secretos (siempre redactados) |
| Data Integrity Assessment | audit chain + flujos de datos | matriz por flujo | QA | — |
| Part 11 Assessment | main.py auth + audit + firmas | checklist §11.10–§11.300 con evidencia | QA | cumplimiento no demostrado |
| ALCOA+ Assessment | tipos de registro reales | matriz 9 atributos × tipo de registro | QA | — |
| Traceability Matrix | URS↔FRS↔DS↔tests (test-catalog W4 + pytest ids) | matriz completa autogenerada | QA | vínculos sin test real |
| Test Strategy | catálogo W4 + gates + suite pytest | estrategia por nivel (unit/int/func) | QA | — |
| IQ | deployment real (docker inspect, puertos, versiones, checksums RC) | protocolo + ejecución automatizable read-only | técnico ejecuta, QA aprueba | resultados sin ejecutar |
| OQ | catálogo W4 (pruebas funcionales por agente) | protocolo desde catálogo; ejecución = W4 run-suite auditado | QA | resultados sin evidencia |
| PQ | casos de proceso con datos representativos | protocolo borrador; requiere datos reales del piloto | dueño de proceso + QA | datos de proceso |
| Validation Summary Report | todos los anteriores + gates + audit | compilación con semáforo | QA (firma) | conclusión "apto" sin gates PASS |
| SOP sugeridos | operación real (deploy, revisión, incidentes) | borradores: uso, revisión periódica, backup, incidentes, cambio | QA/documentación | vigencias y responsables |
| Change Control | git log + review_queue + decisiones | registro por cambio con diff y aprobación | QA | — |
| Periodic Review | audit + métricas + incidentes del período | informe programable (scheduler FASE 5, clase C) | QA | — |
| Incident/Deviation Handling | logs + fallos W4 + 5xx | plantilla de desviación pre-llenada con evidencia | QA decide disposición | causa raíz no investigada |
| Retirement Plan | inventario del deployment | plan de retiro + retención de datos/audit | QA + dueño | — |

Implementación futura: `validation_package_service.py` + endpoint read-only `GET /missions/{id}/validation-package` + generación PDF por documento reutilizando `pdf_report_robust`.

---

## FASE 4 — Mission Control objetivo (enterprise)

Cada vista: **propósito / usuario / datos / endpoints / acciones / riesgos / pruebas.**

1. **Vista ejecutiva (readiness).** Semáforo global por misión (gates, tests, CSV dossier, riesgos abiertos, deployment health). Usuario: dirección/QA. Datos: agregador read-only nuevo `GET /missions/{id}/readiness`. Acciones: ninguna (solo lectura). Riesgo: dar verde sin evidencia → el semáforo solo computa desde evidencia real, nunca editable. Pruebas: unit del agregador + contrato JSON.
2. **Vista técnica (actual, mejorada).** Detalle por misión: diseño, agentes, headless, tests, RC, deployment (ya existe W1–W4). Usuario: técnico. Mejora: trazabilidad objetivo→agente→prueba→evidencia como grafo navegable (datos de Traceability Matrix). Pruebas: las existentes + TM links.
3. **Vista GAMP 5/CSV.** Estado del dossier por documento (draft/reviewed/approved, hash, aprobador), botón "generar paquete de validación" (crea borradores, audita 1 evento). Usuario: QA. Endpoints: `GET/POST /missions/{id}/validation-package`. Riesgo: confundir borrador con aprobado → estados visualmente inequívocos. Pruebas: estados, no-invención, sanitizado.
4. **Vista agentes.** Ficha por agente: rol, reglas vs LLM, modelo/versión Ollama, pruebas W4 asociadas, historial de resultados. Usuario: técnico/QA. Endpoints existentes `/agents`, `/test-results` + serie temporal futura.
5. **Vista pruebas (W4 actual).** Se mantiene; añade tendencia histórica por prueba y export CSV. Riesgo: no alterar executor validado.
6. **Vista auditoría.** Timeline filtrable de la cadena, verificación en vivo (`/audit/verify`), export. Usuario: QA/auditor externo. Riesgo: volumen → paginación server-side.
7. **Vista RC.** Lista, canónico, diff entre RCs, manifest, aprobación firmada. Endpoints existentes + comparador futuro.
8. **Vista deployments.** Salud compuesta (api/pg/redis/ollama), recursos vs límites, IQ status. Read-only.
9. **Vista riesgos.** Mapa severidad×probabilidad, riesgos aceptados (con quién/cuándo), vencimientos de revisión. Endpoints `/risks` existentes + matriz.
10. **Vista fuentes regulatorias (FASE 7).** Source registry, frescura, casos indexados, citas.
11. **Vista PDFs/documentos.** Todos los PDFs generados por misión con hash y fecha; descarga.
12. **Vista tareas operativas de agentes (FASE 5).** Ver abajo.
13. **Panel de aprobaciones humanas.** Cola unificada: misiones, RCs, documentos CSV, tareas clase E — todo lo que espera firma. Usuario: Cesar/QA.

Métricas transversales en header: misiones activas, RCs pendientes, tests PASS %, auditoría OK, alertas abiertas.

---

## FASE 5 — Autonomía operativa Capa 6 (Agent Task Scheduler)

**Principio: cero loops libres.** Toda ejecución automática nace de una *TaskSpec* declarativa, registrada, con límites y dueño humano.

### TaskSpec (contrato declarativo — `factory/layer6/task_registry.yaml`)

```yaml
- task_id: oos_daily_summary
  agent: oos_hplc_investigator.summary_agent
  objective: "Resumen diario de investigaciones OOS abiertas"
  source: {type: internal_api, endpoint: "http://localhost:8102/api/v1/..."}
  connector: read_only_http          # read_only_http | file_watch | none
  schedule: {cron: "0 6 * * 1-5", timezone: America/Bogota}
  limits: {max_runtime_s: 120, max_items: 50, max_ollama_calls: 3, max_tokens_out: 2000}
  mode: read_only                    # read_only | write_controlled
  ollama: {allowed: true, model: "llama3.2:latest", prompt_template: tpl_daily_summary_v1}
  success_criteria: "output no vacío, 0 errores de conector, latencia < límite"
  alert_criteria: "conector caído, criterio de regla disparado, LLM sin respuesta"
  output: {type: report_md, path: "factory/reports/tasks/oos_daily_summary/"}
  audit: one_event_per_run           # siempre: task_id, run_id, inicio, fin, resultado, hash output
  human_owner: cesar
  autonomy_class: C                  # matriz A–F
  paused: false
  escalation: {on_alert: notify_qa, on_repeated_failure: pause_and_notify}
  approval_required: false           # true para clase E
```

### Matriz de autonomía A–F

| Clase | Definición | Ejemplos |
|-------|-----------|----------|
| **A** | Reactivo solamente — solo responde a petición humana | interpretación de un cromatograma puntual, Q&A regulatorio |
| **B** | Programado read-only — consulta y reporta, sin persistir evidencia GMP | health de fuentes, frescura de corpus, drift de configuración |
| **C** | Programado con evidencia — persiste output con hash y auditoría | resumen diario OOS, periodic review draft, tendencias W4 |
| **D** | Programado con alerta QA/QC — puede escalar a humanos | detección de patrón de fallos en pruebas, SST fuera de tendencia, recall relevante detectado (FASE 7) |
| **E** | Requiere aprobación humana previa por ejecución | generación de dossier CSV, borrador de desviación, cualquier `write_controlled` |
| **F** | **Prohibido automatizar** | aprobación/rechazo de RC o misión, disposición de lote, cierre de OOS/desviación, firma, decisión GMP final, deploy, cambios de configuración validada, borrado de cualquier cosa |

Reglas del scheduler: ejecuta desde el registro (nunca código ad-hoc); un `run_id` por ejecución; kill duro al exceder `max_runtime_s`; presupuesto Ollama por tarea y global; toda ejecución audita exactamente 1 evento; tareas nuevas o modificadas requieren aprobación humana antes de activarse (el registro es configuración validada); `paused: true` inmediato desde Mission Control sin deploy.

### Pestaña "Tareas operativas de agentes" (Mission Control)

- **Activas:** tabla task_id / agente / clase / próxima ejecución / último resultado / dueño.
- **Historial:** runs con duración, resultado, output (hash + link), uso Ollama.
- **Fallos y alertas:** abiertas primero, con escalamiento y acuse de recibo QA.
- **Configuración:** fuente, frecuencia, límites — editar crea *propuesta* que requiere aprobación (clase E) antes de activarse.
- **Acciones:** pausar/reanudar (auditado), ejecutar-ahora solo clases B/C con confirmación.
- **Reporte por tarea:** compilado de runs del período, exportable PDF (reusa pdf robusto).

---

## FASE 6 — Gobierno de Ollama local (LLM Governance)

**Regla central: Ollama razona y asiste. Las reglas validan. Mission Control gobierna. Auditoría registra. QA/QC decide.**

### División de responsabilidades

| Capacidad | Ollama (asistivo) | Reglas Python (normativo) | Humano QA/QC |
|-----------|-------------------|---------------------------|--------------|
| Interpretar/resumir texto | ✔ | — | revisa |
| Clasificar, comparar casos | ✔ (borrador) | valida taxonomía | confirma |
| Recuperar contexto (RAG) | ✔ | valida citas contra corpus | — |
| Redactar reportes | ✔ (borrador) | valida estructura/no-secretos | aprueba |
| Cálculos (RSD, SST, specs) | ✘ nunca autoritativo | ✔ único autorizado | — |
| Decisión ALCOA+/spec pass-fail | ✘ | ✔ reproducible | — |
| Aprobación, cierre, disposición de lote | ✘ | ✘ | ✔ exclusivo |

### Política LLM (a codificar en `factory/layer6/llm_governance.py` + YAML)

- **Cuándo consultar:** solo dentro de una TaskSpec o petición humana; nunca por iniciativa propia; presupuesto por tarea (`max_ollama_calls`) y global diario.
- **Datos permitidos de entrada:** evidencia sanitizada (mismo `sanitize_for_report`), corpus indexado, texto del caso. **Prohibidos:** secretos, API keys, conn-strings, datos personales identificables, `.env`, rutas fuera del workspace.
- **Salidas permitidas:** borradores marcados `llm_generated: true` con modelo+versión. **Prohibidas:** cifras no presentes en el contexto (regla anti-invención: post-validador exige que números/citas del output existan en el input o se marquen `[SIN FUENTE]` y disparen alerta).
- **Registro por llamada:** prompt template id + versión, contexto (hash), modelo, versión/digest del modelo, parámetros, respuesta (hash + texto), timestamp UTC, task/run id, latencia, resultado del post-validador. Persistido en `factory/logs/llm_calls.jsonl` (append-only) + 1 evento de auditoría por tarea (no por llamada, para no inflar la cadena).
- **Prompt templates aprobados:** versionados en `factory/layer6/prompts/tpl_*.md`, con hash; cambiar un template = change control (clase E). Ninguna llamada con prompt libre en tareas programadas.
- **Escalamiento a QA/QC:** post-validador falla, contradicción entre LLM y reglas, confianza fuera de umbral, o el caso matchea taxonomía crítica (OOS confirmado, recall, data integrity).
- **Fallback:** Ollama caído → la tarea reporta `llm_unavailable` y continúa con la parte de reglas (patrón W3.5 ya validado); nunca reintentos infinitos.
- **Pruebas de regresión LLM:** set dorado de casos con salidas esperadas por template; correr al cambiar modelo o template; métricas: exactitud de citas, tasa `[SIN FUENTE]`, latencia p95, tasa de escalamiento.

---

## FASE 7 — Fuentes online e inteligencia regulatoria

### Arquitectura (read-only, sin descarga masiva)

```
source_registry.yaml → conectores read-only → metadata extractor →
case indexing → case memory (JSONL + vector index de resúmenes) →
case retrieval con citación → dashboard de fuentes
```

- **Source registry (`factory/layer6/source_registry.yaml`):** por fuente: id, autoridad (FDA/EMA/EudraGMDP/interna), URL base oficial, tipo de acceso (API pública / página oficial / carga interna), rate limit propio (p.ej. openFDA 240 req/min con key, 40 sin — verificar al implementar), frecuencia máxima de consulta, vigencia, responsable humano.
- **Fuentes iniciales:** FDA Warning Letters, FDA Inspection Observations/Form 483 públicas, FDA Data Dashboard, openFDA Drug Enforcement/Recalls (API JSON oficial), EudraGMDP Non-Compliance Reports, EMA GMP, documentos internos cargados manualmente.
- **Conectores:** solo GET, sólo APIs/páginas oficiales, User-Agent identificado, respeto de robots/ToS, rate limit conservador, sin crawling recursivo, sin descarga masiva — consultas dirigidas por término/fecha/producto.
- **Metadata extractor:** autoridad, fecha, empresa, producto, sistema afectado, tipo de hallazgo. Todo campo con **source pointer**: URL + fecha de captura + autoridad + hash SHA-256 del contenido capturado.
- **Case memory:** `factory/layer6/case_memory/cases.jsonl` (append-only, cada caso con pointer) + vector index **solo de resúmenes** (no texto masivo) en colección ChromaDB nueva dedicada (no contaminar las colecciones del producto base).
- **Citación obligatoria:** toda respuesta que use un caso incluye pointer completo; sin pointer → la respuesta se marca inválida. **No inventar:** el post-validador de FASE 6 aplica.
- **Revalidación de fuentes:** tarea clase B (`source_freshness`) verifica accesibilidad y cambios de estructura; fuente rota → alerta, nunca degradar silenciosamente.
- **Dashboard:** vista 10 de FASE 4 — estado por fuente, última captura, casos indexados, alertas de frescura.

### Misión futura: `regulatory_deviation_intelligence`

| Agente | Clase | Función |
|--------|-------|---------|
| `source_discovery_agent` | B | verifica registry, propone fuentes nuevas (solo propone) |
| `case_indexing_agent` | C | extrae metadata + pointer de capturas dirigidas |
| `deviation_taxonomy_agent` | C→E | clasifica casos (borrador LLM, taxonomía validada por reglas; cambios de taxonomía = E) |
| `case_memory_agent` | C | mantiene cases.jsonl + vector index, dedup por hash |
| `case_retrieval_agent` | A | responde consultas humanas con casos citados |
| `gmp_interpretation_agent` | A/D | interpreta relevancia para el sitio; hallazgo crítico → alerta QA (D) |
| `evidence_citation_agent` | A | valida que toda cita tenga pointer válido y vigente |
| `source_freshness_agent` | B | revalida fuentes, detecta cambios de estructura |

Flujo de misión estándar: Capa 9 aprueba la misión → Capa 8 construye en workspace aislado → gates → RC → aprobación → deploy. Sin excepciones al flujo por ser "solo consultas".

---

## FASE 8 — Backlog 75→99

### 75→85 — Solidez técnica (bajo riesgo, sin cambio de contrato)
1. Extraer servicios de `layer9.py` a `factory/services/` (router fino, misma respuesta byte a byte, tests de contrato antes/después). *(requiere commit previo de W4.1.1)*
2. Sanitizador: patrones conn-string/URL-credentials **(hecho en W5-FASE 9)** + catálogo de patrones testeado.
3. Particionar `mission_control.html` en módulos ES (sin cambiar funcionalidad).
4. Observabilidad mínima: `/metrics` read-only (contadores por endpoint, 5xx, latencia p95, llamadas Ollama) + vista de salud 4 stacks.
5. **W5-F0-1:** eliminar `--reload` de factory-api → imagen inmutable + procedimiento de rebuild aprobado (requiere aprobación: toca deployment).
6. CORS restringido a orígenes conocidos (requiere aprobación: seguridad).
7. Escritor de auditoría serializado (lock) para eliminar forks futuros.
8. Coverage medido en selfcheck (umbral inicial 75 %).
9. PDF: TOC + numeración页 + metadatos de documento.
10. Reconciliación read-only ports.yaml ↔ `docker ps` en selfcheck.

### 85→90 — GAMP 5 / CSV
11. `validation_package_service` + dossier.yaml + 22 plantillas FASE 3.
12. Traceability Matrix autogenerada URS↔FRS↔tests (W4 catalog + pytest ids).
13. Vista CSV + vista ejecutiva readiness en Mission Control.
14. Risk assessment vivo (matriz desde risks/ + gates).
15. Roles de usuario (autor/revisor/aprobador) con keys individuales — base Part 11 §11.10(d). *(aprobación: seguridad)*
16. Firma electrónica con significado + vinculación al registro. *(aprobación: arquitectura)*

### 90→95 — Inteligencia regulatoria
17. `source_registry` + conector openFDA (API oficial JSON, la más estable) piloto clase B.
18. Case memory + indexing + citación con pointers.
19. Misión `regulatory_deviation_intelligence` por flujo estándar (Capa 9 → 8 → RC → aprobación).
20. Agent Task Scheduler (FASE 5) + pestaña de tareas operativas + clases A–F en producción controlada.
21. LLM Governance codificada (post-validador, templates versionados, llm_calls.jsonl, set dorado).

### 95→99 — Producción GMP
22. Conector LIMS/CDS read-only (CSV/API) con validación de esquema y mapeo aprobado.
23. Piloto con datos representativos anonimizados + protocolo con criterios de aceptación.
24. IQ/OQ/PQ ejecutados y firmados sobre el deployment piloto; VSR aprobado.
25. SOPs vigentes (uso, revisión periódica, backup/restore probado, incidentes, change control).
26. Revisión periódica programada (tarea clase C) + gestión de desviaciones operativa.
27. Go-live controlado con readiness 100 % verde y aprobación QA firmada.

**Lo que el 99 % NO incluye (honestidad):** validación formal ante inspección real sin acompañamiento de QA humano, decisiones GMP autónomas, reemplazo de LIMS. El sistema es *asistivo validado*, no autoridad de calidad.

---

*Documento generado desde evidencia real del sistema (selfcheck 2026-07-02, código en HEAD 9072f61 + runtime W4.1.1). Los diseños de FASES 2–7 son propuestas que requieren aprobación humana antes de implementarse.*
