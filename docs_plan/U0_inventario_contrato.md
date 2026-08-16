# U0 — Inventario del Contrato de Datos
**GMP AI Factory · Capa 9 · Restructura UI a consola de diagnóstico**
Generado: 2026-06-24 | Solo lectura — sin cambios de código

---

## Auth confirmada
- Variable: `FACTORY_API_KEY`
- Header exacto: `x-api-key` (FastAPI `Header(default="")` en `main.py:31`)
- Nota: el HTML actual envía `X-Api-Key` (capital K) → FastAPI normaliza headers a minúsculas; **funciona igual**.

---

## PASO 1 — OpenAPI: 51 rutas en factory-api (:9000)

```
GET    /health
GET    /api/v1/status/full
GET    /api/v1/status/resources
GET    /api/v1/agents
GET    /api/v1/agents/profiles
GET    /api/v1/audit/verify
GET    /api/v1/deployments
GET    /api/v1/deployments/{project_id}
GET    /api/v1/layer8/claude/status
GET    /api/v1/layer8/jobs
GET    /api/v1/layer8/jobs/{job_id}
GET    /api/v1/layer8/missions/{project_id}/artifacts
GET    /api/v1/layer8/missions/{project_id}/diff      ← ROTO (500)
GET    /api/v1/layer8/missions/{project_id}/headless/logs
GET    /api/v1/layer8/status
GET    /api/v1/layer9/decisions
GET    /api/v1/layer9/decisions/{project_id}
GET    /api/v1/layer9/missions
GET    /api/v1/layer9/missions/{project_id}
GET    /api/v1/layer9/review-queue
GET    /api/v1/layer9/review/{rc_id}
GET    /api/v1/projects
GET    /api/v1/projects/{project_id}
GET    /api/v1/projects/{project_id}/pipeline
GET    /api/v1/releases
GET    /api/v1/releases/{project_id}
GET    /api/v1/workspaces
GET    /api/v1/workspaces/{project_id}
... + 23 POST/DELETE rutas
```

---

## PASO 2 — Resultados de GETs seguros

| Endpoint | HTTP | Shape / nota |
|----------|------|--------------|
| `/health` | 200 | `api, service, timestamp` |
| `/api/v1/status/full` | 200 | `timestamp, summary{stacks_total:4, stacks_ok:3, stacks_error:1, audit_verified:false, audit_entries:190}, docker_1_base, docker_2_factory, custom_solutions, audit` |
| `/api/v1/status/resources` | 200 | `compliant:true, memory{used_pct:11.3}, disk{used_pct:50.6}, custom_solutions{active:2, max:2}` |
| `/api/v1/layer9/missions` | 200 | lista 3 misiones (c8_alcoa_validator, lab_qc_project, r6_change_control) |
| `/api/v1/layer9/decisions` | 200 | lista 3 decisiones |
| `/api/v1/layer9/review-queue` | 200 | `pending:[lab_qc v0.3.0, c8_alcoa v0.1.0-rc1], summary:{pending:2}` |
| `/api/v1/layer8/status` | 200 | `headless_enabled:false, jobs:{pending:0,running:0,completed:7,failed:1}` |
| `/api/v1/layer8/jobs` | 200 | lista jobs |
| `/api/v1/layer8/missions/lab_qc_project/artifacts` | 200 | `project_id, artifacts[…]` |
| `/api/v1/layer8/missions/lab_qc_project/diff` | **500** | `{"detail":"[Errno 2] No such file or directory: 'git'"}` |
| `/api/v1/layer8/missions/c8_alcoa_validator/artifacts` | 200 | `project_id, artifacts[…]` |
| `/api/v1/projects/lab_qc_project/pipeline` | 200 | `project_id, project, workspace, releases, deployment, registry` |
| `/api/v1/projects/c8_alcoa_validator/pipeline` | **404** | proyecto no registrado en /api/v1/projects |
| `/api/v1/projects` | 200 | lista 1 proyecto (lab_qc_project) |
| `/api/v1/deployments` | 200 | lista 1 deployment |
| `/api/v1/deployments/lab_qc_project` | **404** | no encontrado (deployment file inconsistente) |
| `/api/v1/releases` | 200 | lista 2 releases |
| `/api/v1/releases/lab_qc_project` | 200 | lista 2 |
| `/api/v1/agents` | 200 | `base_agents:{csv, audit, automation, …}` |
| `/api/v1/agents/profiles` | 200 | perfiles por base_agent |
| `/api/v1/workspaces` | 200 | lista 4 workspaces |
| `/api/v1/workspaces/lab_qc_project` | 200 | metadata + has_* flags |
| `/api/v1/audit/verify` | 200 | `verified:false, log_count:191, verified_count:190, chain_errors:1, part11_compliant:false` |
| `/api/v1/layer8/claude/status` | 200 | `cli_found, version, auth_status, mode` |

---

## PASO 3 — Fetch reales en el HTML (solo 3)

```javascript
fetch("/health")                                         // conn check, no auth
fetch("/api/v1/status/full", {headers:headers()})        // actualiza m-audit
fetch("/api/v1/layer9/missions", {headers:headers()})    // actualiza m-active
```

### URLs referenciadas en el HTML (no fetch):
```
/api/v1/         (API_BASE)
/workspaces/r6_change_control   (literal en texto de diseño)
```

---

## PASO 4 — Tabla de Contrato de Datos

| # | Valor en UI | Sección | ¿fetch en HTML? | Endpoint origen | ¿existe en OpenAPI? | HTTP | Veredicto |
|---|-------------|---------|-----------------|-----------------|---------------------|------|-----------|
| 1 | Misiones activas = "2" | dash | YES → `/layer9/missions` | `/api/v1/layer9/missions` | SI | 200 | **LIVE OK** (count; real=3) |
| 2 | Decisiones pendientes = "1" | dash | NO | `/api/v1/layer9/decisions` | SI | 200 | **MOCK** — endpoint existe, no wired |
| 3 | Release candidates = "1/revisar" | dash | NO | `/api/v1/layer9/review-queue` | SI | 200 | **MOCK** — endpoint existe, no wired (real=2) |
| 4 | Cadena auditoría = "OK·65" | dash | YES → `/status/full` | `/api/v1/status/full` + `/api/v1/audit/verify` | SI | 200 | **LIVE ROTO** — con conexión actualiza texto, pero real=FALLA·190; UI sin conexión muestra stale "65" |
| 5 | Flow diagram (r6 "en curso") | dash | NO | — | NO | — | **MOCK puro** |
| 6 | Misiones card (lab_qc·r6 hardcoded) | dash | NO | `/api/v1/layer9/missions` | SI | 200 | **MOCK** — datos disponibles, no renderizados dinámicamente |
| 7 | Riesgos card (3 riesgos hardcoded) | dash | NO | — | NO | — | **MOCK puro** |
| 8 | Stacks Docker 1/2/3 (hardcoded "ok") | dash | NO | `/api/v1/status/full` | SI | 200 | **MOCK** — real: stacks_ok=3, stacks_error=1 |
| 9 | "lab_qc 8101·v0.2.0" sidebar | sidebar | NO | `/api/v1/deployments/lab_qc_project` | SI | 404 | **MOCK** + FALTA ENDPOINT funcional |
| 10 | "headless: revisar estado" sidebar | sidebar | NO | `/api/v1/layer8/status` | SI | 200 | **MOCK** — real: headless_enabled=false |
| 11 | r6_change_control card (approve) | approve | NO | `/api/v1/layer9/missions/r6_change_control` | SI | ? | **MOCK** |
| 12 | hl-state chip "verificar" (pipeline) | pipeline | NO | `/api/v1/layer8/status` | SI | 200 | **MOCK** — real: headless_enabled=false → "OFF" |
| 13 | Diseño agentes/workspace (pipeline) | pipeline | NO | `/api/v1/layer8/missions/{id}/artifacts` | SI | 200 | **MOCK** |
| 14 | Tests/gates estado (pipeline) | pipeline | NO | — | NO | — | **MOCK puro** |
| 15 | RC "rc-v0.2.0 · gates 12/12" (review) | review | NO | `/api/v1/layer9/review-queue` | SI | 200 | **MOCK** — real: v0.3.0 + v0.1.0-rc1, ninguno v0.2.0 |
| 16 | Diff resumen (review) | review | NO | `/api/v1/layer8/missions/{id}/diff` | SI | **500** | **LIVE ROTO** — git no en PATH |
| 17 | "Cadena verificada·65 entradas" (audit) | audit | NO | `/api/v1/audit/verify` | SI | 200 | **MOCK** — real: 191 entries, chain_error=1, part11_compliant=false |
| 18 | Eventos de cadena (timestamps) | audit | NO | FALTA endpoint GET audit/entries | NO | — | **MOCK puro** |
| 19 | RAM = "29.5% usado" | system | NO | `/api/v1/status/resources` | SI | 200 | **MOCK** — real: 11.3% |
| 20 | Disco = "49.5% usado" | system | NO | `/api/v1/status/resources` | SI | 200 | **MOCK** — real: 50.6% |
| 21 | Soluciones custom = "1/2 máx" | system | NO | `/api/v1/status/resources` | SI | 200 | **MOCK** — real: 2/2 |
| 22 | Stacks Base/Factory/lab_qc status | system | NO | `/api/v1/status/full` | SI | 200 | **MOCK** — real: 3 ok + 1 error |

**Resumen:** LIVE OK: 1 · LIVE ROTO: 2 · MOCK (endpoint existe): 14 · MOCK puro (sin endpoint): 5 · FALTA ENDPOINT: 1

---

## A) Endpoints del plan §4: falta vs existe

| Endpoint del plan | ¿Existe en OpenAPI? | Estado | Acción |
|-------------------|---------------------|--------|--------|
| `GET /layer9/audit/summary` | NO | Falta crear | Alternativa: usar `/api/v1/audit/verify` directamente (tiene todos los campos) |
| `GET /layer8/workspaces/{id}/tree` | NO | Falta crear | `/api/v1/workspaces/{id}` existe pero solo devuelve metadata + flags |
| `GET /layer8/workspaces/{id}/file` | NO | Falta crear | No existe; necesita leer archivo del workspace por path |
| `GET /layer8/jobs/{job_id}` | **SI** | Existe y OK | No crear — ya disponible en `/api/v1/layer8/jobs/{job_id}` |
| `GET /api/v1/agents/by-layer` | NO | Opcional | `/api/v1/agents` + `/api/v1/agents/profiles` tienen todos los datos; `by-layer` sería solo agrupación |

---

## B) Endpoints existentes pero rotos

| Endpoint | Código | Causa | Fix en U1 |
|----------|--------|-------|-----------|
| `GET /api/v1/layer8/missions/{project_id}/diff` | 500 | `git` no está en PATH dentro del contenedor | Agregar git al Dockerfile o usar subprocess con PATH absoluto |
| `GET /api/v1/projects/c8_alcoa_validator/pipeline` | 404 | c8_alcoa_validator no registrado en `/api/v1/projects` | Registrar proyecto o no llamar este endpoint para ese proyecto |
| `GET /api/v1/deployments/lab_qc_project` | 404 | Archivo de deployment inconsistente (lista OK pero detail 404) | Investigar ruta del deployment file |
| `GET /api/v1/audit/verify` (datos) | 200 | chain_errors=1, part11_compliant=false | Diagnóstico separado: identificar qué entrada rompió la cadena |

---

## Confirmación de no-cambios

```
git status --short
```
(ver PASO 5 — solo este archivo untracked en docs_plan/)
