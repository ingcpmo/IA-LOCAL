# AUDITORÍA FUNCIONAL E2E POST-CIERRE — ANALIZADOR DOCUMENTAL GMP

Fecha de ejecución: 2026-08-19. Rol: Arquitecto Principal / Auditor técnico
(Capa 8, Claude Code). Autoridad: Capa 9 = Cesar. Corrida solicitada por
`docs_plan/AUDITORIA_FUNCIONAL_E2E_INSTRUCCIONES.md`, ejecutada como
auditoría de solo lectura: sin fixes, sin commits, sin rebuild/restart de
contenedores.

Disciplina de evidencia usada en todo el documento:
`UNIT_TEST / INTEGRATION_TEST / API_REAL / UI_REAL / E2E_REAL /
HUMAN_ACTION_REQUIRED / NOT_TESTED`. Ningún ítem se marca PASS solo porque
exista código.

──────────────────────────────────────────────────────────────────────────
## BLOQUE 0 — RECONCILIACIÓN PREVIA
──────────────────────────────────────────────────────────────────────────

### 0.1 Reconciliación de los dos motores — **RESUELTO CON EVIDENCIA**

**Hallazgo central de toda la corrida.**

Existen efectivamente dos pipelines, confirmados por lectura directa del
código y del filesystem, no solo por los nombres de archivo del brief
original (que ya estaban desactualizados — ver nota de layout abajo):

| | MOTOR LEGACY | MOTOR ACTUAL |
|---|---|---|
| Ubicación real | `factory/workspaces/gmpai_document_validation/app/*.py` (`pipeline.py`, `llm_integrity_engine.py`, `llm_alcoa_agent.py`, `llm_annex11_agent.py`, `llm_part11_agent.py`, `llm_traceability_agent.py`, `extraction.py`, `build_informe_v5.py`→`generate_fs_v1_2_draft_v2.py`/`package_v5.py`) | `factory/engines/gmpai_integrity/chunked_engine.py`, `factory/regulatory/retrieval/judgment.py`, `factory/regulatory/candidate_validity.py`, `factory/regulatory/absence_consolidator.py`, `factory/services/remediation_directive.py` (los nombres del brief original ya no viven bajo `factory/regulatory/*.py` plano — se movieron a subcarpetas `engines/`, `regulatory/retrieval/`, `services/` en el rediseño R1-R4; mismo motor, distinta ubicación) |
| Versionado en git | **NO** — `factory/.gitignore` excluye `workspaces/*` (confirmado leyendo `factory/services/runtime_identity.py:6-9`, que documenta exactamente este problema) | SÍ, commiteado |
| Invocación en vivo hoy | **Ninguna encontrada.** `crontab -l` no referencia el directorio legacy (solo 5 jobs: health check, log rotation, RAM monitor, backup, y `watch_source_origin_status.sh` del motor actual). `systemctl list-timers` no tiene timers custom del proyecto. Los únicos 3 hits de grep del brief (`factory/tests/test_validation_evidence_persistence.py:197`, `factory/services/gmpai_agent_execution_status.py:6-30`, `factory/core/path_policy.py:241`) son comentarios/docstrings que *documentan* el problema del legacy, no invocaciones de código | Sí — API real en :9000 (`factory-api`, contenedor `Up`), rutas `/api/v1/layer9/*`, `/api/v1/layer8/*`, cron `watch_source_origin_status.sh` activo |
| Produjo el RC canónico v1.4 | **SÍ, confirmado.** `factory/release_candidates/gmpai_document_validation/gmpai_document_validation-rc-v1.4-20260715T031540/artifacts/pipeline_pilot_llm.json` es el artefacto de salida agregado; el nombre del archivo y su estructura (un único JSON, sin `run_id`/`task_id` por documento) coinciden exactamente con la descripción que `gmpai_agent_execution_status.py:6-11` da del motor legacy ("el pipeline corre como UN script que produce un único JSON agregado... NO existe run_id/task_id/timestamp por documento/agente en el RC canónico v1.4") | No produjo el RC v1.4 — no existía en esa forma en julio 2026; es posterior (R1-R4 corrieron entre finales de julio y agosto) |

**Conclusión con evidencia:** el motor legacy generó el RC canónico v1.4
de `gmpai_document_validation` y **no está vivo hoy** — no hay cron, systemd
timer, endpoint, ni script activo que lo invoque. Es código histórico,
no versionado en git, congelado desde el 2026-07-25 (última fecha de
modificación de los archivos `llm_*_agent.py`, ver `ls -la`).

**ENGINE_RECONCILIATION = RESUELTO.** Recomendación (no ejecutada, solo
propuesta): marcar `factory/workspaces/gmpai_document_validation/app/`
como `ARCHIVED — histórico, no mantenido, no versionado, produjo RC v1.4`
en un README dentro de ese directorio, para que ningún cambio futuro se
confunda entre motores. Cesar decide si autoriza ese cambio (es un archivo
nuevo, no una modificación de código funcional).

**Etiquetado ENGINE aplicado abajo:** todo hallazgo de RC v1.4 /
`gmpai_document_validation` (misión histórica) se marca `ENGINE=LEGACY`.
Todo hallazgo de corridas Tier-1/RW-000x, `chunked_engine`, review queue,
remediation directives/packages nuevos, se marca `ENGINE=CURRENT`.

### 0.2 DOCUMENT_RELEASED — confirmado, sin conexión a endpoint

`create_release_record()` existe en
`factory/services/remediation_package_service.py:702` — función real,
completa, con lock de concurrencia (`_package_lock`) y validación de
estado previo (`PACKAGE_READY_FOR_RELEASE`). El propio código de la ruta
lo documenta explícitamente:
`factory/api/routes/remediation_packages.py:7` — *"create_release_record()
existe en el servicio pero no se conecta"*.

Verificación directa contra la superficie real de la API (`openapi.json`
de `factory-api` en vivo, puerto 9000): las únicas rutas bajo
`/api/v1/remediation-packages/{project_id}/{package_id}/{version}/*` son
`decision`, `exceptions/{change_id}` y `medium-risk-batch`. **No existe**
una ruta `.../release`. Confirmado por API real, no solo por lectura de
código: `ENGINE=CURRENT`, evidencia `API_REAL`.

`DOCUMENT_RELEASED` permanece `false` siempre — no por bug, por diseño
deliberado sin puerta de entrada. Ver callout en el manual (Bloque 3).

### 0.3 K3 (2026-08-19) — cadena verificada parcialmente, con vacío real

`docs_plan/CIERRE_FORMAL_E2E.md` registra la confirmación de Cesar (dos
casillas: recepción de `X-Identity-Key` nueva, y clic real en Mission
Control sin 401 con flujo de remediación visible). Esa confirmación es
**HUMAN_ACTION_REQUIRED / registrada por declaración de Cesar en chat**,
no por un artefacto persistente firmado — el propio documento lo dice:
la rotación de la key "no es un commit" porque
`factory/config/identity_keys.yaml` está gitignored.

Se buscó, con evidencia de filesystem, el rastro que ese clic debería
haber dejado según la cadena prometida
(`RemediationDirective → paquete → borrador NO APROBADO → redline →
manifest → audit trail`):

- `factory/remediation_packages/gmpai_document_validation/` solo contiene
  dos paquetes: `PKG-FS-V1-2-REAL-CONTROLLED` y
  `PKG-FS-V1-2-MEDIUM-RISK-REAL`, ambos con `state.json` fechado
  **2026-07-21** (`mtime` confirmado) — casi un mes antes del clic de K3.
  No son el artefacto de K3.
- Los `storage_location` de los artefactos de esos paquetes apuntan a
  `/tmp/claude-1001/.../scratchpad/real_controlled_package_artifacts/*.md`
  — una ruta de scratchpad de una sesión anterior. Se verificó que **ya
  no existe** (`ls` → `No such file or directory`). Es decir: incluso el
  paquete más reciente disponible tiene artefactos referenciados que ya
  no son recuperables del disco.
- No se encontró ningún archivo nuevo con fecha 2026-08-19 en
  `factory/remediation_packages/`, `factory/audit/`, ni en el endpoint
  `/api/v1/layer9/remediation/directives` (API real disponible pero sin
  forma de filtrar por fecha sin credenciales de identidad, que este
  auditor no posee ni debe generar).
- Los únicos artefactos con fecha 2026-08-19 detectados en todo el
  repositorio son los 4 `.docx` de
  `factory/regulatory/pilot_run/dry_run_validation_r4_t1_1v2/`
  (mtime 03:10-03:11 UTC) y dos líneas nuevas (`superseded`) en
  `factory/layer9/review_queue.jsonl` fechadas **2026-08-18**, no 19 —
  ninguno de los dos es una `RemediationDirective` nueva ni corresponde
  al flujo K3 descrito.

**Conclusión: la cadena de K3 NO tiene rastro de artefacto persistente
verificable en este filesystem.** Lo único verificable es la confirmación
textual de Cesar en el chat de cierre. Esto es un hallazgo real, no una
formalidad:

```
FAILURE = ausencia de artefacto persistente (RemediationDirective/paquete/
          redline/manifest) correlacionable con el clic K3 del 2026-08-19
EVIDENCE = ningún archivo bajo factory/remediation_packages/,
          factory/audit/ tiene mtime 2026-08-19; los dos paquetes
          existentes son del 2026-07-21 y su storage_location de
          artefactos ya no existe en disco
ROOT_CAUSE = la confirmación de K3 se registró como declaración en chat
          (CIERRE_FORMAL_E2E.md), no como resultado de una corrida capturada
          y archivada por el propio sistema
AFFECTED_OBJECTIVE = OBJECTIVE_5_HUMAN_REVIEW_AND_AUDIT (trazabilidad)
SEVERITY = MEDIA — el flujo probablemente funcionó (Cesar lo confirma
          directamente y sin motivo para dudar de su palabra), pero el
          sistema no puede reproducir esa prueba por sí mismo hoy, lo cual
          es exactamente el problema de reproducibilidad que
          runtime_identity.py ya identificó para el motor legacy
FIX_REQUIRED = SÍ (para trazabilidad regulatoria formal, no para el
          gate K3 ya cerrado) — no ejecutado en esta corrida (solo
          auditoría)
```

No se puede determinar si el paquete/candidato que Cesar vio en K3 fue un
caso de prueba dirigido (R4-T1) o un hallazgo real del RC canónico —
dato no recuperable con la evidencia disponible hoy.

### 0.4 Dos capas de "modelo" — confirmado

- `claude-haiku-4-5-20251001` aparece en `factory/api/routes/layer8.py`
  — es el modelo que Capa 8 usa para construir misiones nuevas (headless),
  confirmado por `grep` sobre el archivo real de la ruta `/api/v1/layer8/*`.
- Ollama/qwen aparece en `factory/regulatory/semantic_evidence_verification.py`,
  `factory/regulatory/retrieval/embed.py`,
  `factory/engines/gmpai_integrity/ollama_client.py` y
  `factory/engines/gmpai_integrity/chunked_engine.py` — es el modelo que
  juzga documentos (motor actual del analizador).

Confirmado: ejes completamente independientes, en módulos distintos, sin
solapamiento de código. `ENGINE=CURRENT` para ambos (Capa 8 y el
analizador son parte del sistema vigente; ninguno es legacy).

### 0.5 Adenda de Cesar — resiliencia de corridas largas (checkpoint/resume)

Adenda recibida durante esta corrida: cualquier verificación de Bloque 1
que requiriera una cadena real de llamadas LLM largas (Ollama/Qwen, corpus
E2E completo) debe ser persistente, reanudable y segura ante
desconexiones SSH/reinicios del servidor — nunca solo en RAM/PID, nunca
solo en `/tmp`, con escritura atómica de checkpoints.

**Verificado por inspección estática de código (`STATIC_CODE_REVIEW`,
no por ejecución en vivo — ver aclaración abajo) que el motor CURRENT ya
cumple este requisito:**

- `CheckpointStore` — `factory/engines/gmpai_integrity/chunked_engine.py:896-997`.
  Docstring de la clase (línea 897-900): *"Persistencia de reanudación:
  guarda chunk_executions ya completados (por run_id) en disco tras cada
  chunk... Formato: 1 archivo JSON por run_id."* Escritura atómica
  confirmada línea por línea: `tmp.write_text(...)` seguido de
  `tmp.replace(p)` (patrón write-then-replace, evita estado corrupto si
  el proceso muere a mitad de escritura). Respuestas crudas de LLM
  comprimidas en gzip con SHA-256 por llamada (`hashlib.sha256(payload)
  .hexdigest()`). Reanudación basada en fingerprint: `find_resumable()`
  (línea ~951) exige coincidencia exacta de
  `prompt_version/schema_version/model_digest/document_sha256/
  agent_version/catalog_version/catalog_sha256` — si el fingerprint no
  coincide, **rechaza** la reanudación (`reason:
  checkpoint_fingerprint_mismatch`) en vez de arriesgar continuar con
  datos incompatibles. Ruta de almacenamiento confirmada:
  `factory/regulatory/pilot_run/checkpoints/` (dentro de
  `/home/ing_cpmo`, no en `/tmp`) — confirmado también por inspección
  directa del directorio (decenas de `chunked-*.checkpoint.json` reales
  ya en disco, ver Bloque 1).
- `factory/scripts/ops/run_corpus_pilot.py` — comentario explícito en el
  propio script: diseñado para correr "DESACOPLADO de la sesión
  interactiva (`systemd-run`/`tmux`, nunca hijo de Claude Code)". Escribe
  marcador de estado atómico en
  `factory/regulatory/pilot_run/status/<run_id>.json` (PID, plan,
  RUNNING/COMPLETED/FAILED).
- `factory/scripts/ops/pilot_status.sh` — leído completo. Confirmado:
  solo lectura (comentario propio: *"NUNCA escribe auditoria, NUNCA
  reintenta ni reanuda nada por su cuenta"*), ejecutable desde cualquier
  sesión SSH nueva, lee `STATUS_FILE`, verifica PID vivo con `kill -0`,
  lista checkpoints reales con su `mtime` y conteo de chunks.

**GAP REAL CONFIRMADO (reportado por Cesar, verificado aquí):**
`pilot_status.sh` líneas 67-70 — el bloque de log tiene tres ramas: (1)
`journalctl -u w5v2-pilot-${RUN_ID}` si existe una unidad systemd activa
con ese nombre; (2) si no, cae a `tail -n 5 "$TMUX_LOG"` con
`TMUX_LOG="/tmp/pilot_${RUN_ID}.log"` (línea 20); (3) si tampoco existe,
solo imprime que no hay log. Se verificó en vivo con
`systemctl list-units 'w5v2-pilot-*' --all` que **no hay ninguna unidad
systemd de este patrón activa ni cargada hoy en el servidor** — cero
resultados. Esto significa que, tal como está desplegado el sistema hoy,
si alguien lanza un piloto largo vía `tmux` (la alternativa que el propio
`run_corpus_pilot.py` documenta como válida junto a `systemd-run`), su
**log de texto** vive exclusivamente en `/tmp/pilot_${RUN_ID}.log` — un
directorio que no sobrevive un reinicio del servidor. El checkpoint de
datos (`CheckpointStore`) SÍ está a salvo en `factory/regulatory/
pilot_run/checkpoints/`; lo que se pierde en un reinicio con la ruta
tmux es solo el log humano-legible de progreso, no el estado
reanudable en sí.

```
FAILURE = ruta de log de fallback usa /tmp cuando el piloto corre bajo
          tmux en vez de systemd-run
EVIDENCE = factory/scripts/ops/pilot_status.sh líneas 20, 67-70;
          `systemctl list-units 'w5v2-pilot-*' --all` = 0 unidades activas
          hoy (confirma que la ruta systemd, aunque preferida, no es la
          que está en uso actualmente si algún piloto corriera ahora)
ROOT_CAUSE = diseño intencional de fallback dual (systemd-run preferido,
          tmux como alternativa) que no llevó el log de la alternativa
          tmux fuera de /tmp
AFFECTED_OBJECTIVE = ninguno de los 5 objetivos centrales directamente —
          afecta la resiliencia operativa de corridas largas, no la
          gobernanza regulatoria (el CHECKPOINT de datos, que sí importa
          para gobernanza, no está afectado)
SEVERITY = NON_BLOCKING / BAJA — el checkpoint de datos (lo que importa
          para no repetir llamadas LLM costosas) es seguro; solo el log
          de texto es vulnerable, y solo bajo la ruta tmux, y solo si el
          servidor se reinicia entre el lanzamiento y la lectura del log
FIX_REQUIRED = SÍ, de bajo esfuerzo (mover TMUX_LOG a una ruta bajo
          factory/regulatory/pilot_run/ en vez de /tmp) — NO ejecutado en
          esta auditoría (solo lectura, sin cambios de código)
```

**Aclaración obligatoria — no se fabricó ninguna corrida real:**

```
NO_REAL_LONG_RUN_EXECUTED_DURING_THIS_AUDIT = true
```

Esta auditoría no lanzó ningún piloto de corpus real ni cadena larga de
llamadas a Ollama/Qwen — es una auditoría de solo lectura, no una nueva
ejecución de pilot. Todo lo anterior sobre `CheckpointStore`,
`run_corpus_pilot.py` y `pilot_status.sh` es `STATIC_CODE_REVIEW`
(inspección de código y de checkpoints ya existentes en disco de
corridas *anteriores*), no una prueba en vivo de matar-y-reanudar un
proceso hoy. Se recomienda como `HUMAN_ACTION_REQUIRED` / seguimiento,
no ejecutado aquí: una prueba real de kill-and-resume (lanzar un piloto
pequeño, matar el proceso a mitad de camino, confirmar que
`find_resumable()` lo retoma sin repetir llamadas) antes de confiar en
este mecanismo para una corrida de producción larga y costosa.

Plantilla para que Cesar la use en cualquier corrida FUTURA real (sin
valores inventados — todos en blanco hasta que exista una corrida real
que los llene):

```
RUN_ID                    =
BACKGROUND_EXECUTION       = (systemd-run | tmux)
SSH_DISCONNECT_SAFE        = (sí si systemd-run o tmux con checkpoint;
                              confirmar con pilot_status.sh)
SERVER_REBOOT_SAFE         = (checkpoints: sí / log: solo si systemd-run,
                              NO si tmux hasta que se corrija el gap arriba)
PID                        =
STARTED_AT                 =
STATUS                     = (RUNNING | COMPLETED | FAILED)
LOG_PATH                   = (journalctl -u w5v2-pilot-<RUN_ID>, o
                              /tmp/pilot_<RUN_ID>.log si tmux — inseguro
                              ante reinicio, ver gap arriba)
CHECKPOINT_PATH             = factory/regulatory/pilot_run/checkpoints/
RAW_RESPONSE_PATH           = (gzip por llamada, junto al checkpoint)
COMPLETED_CALLS             =
PENDING_CALLS               =
RESUMED_FROM_CHECKPOINT     = (true/false)
LAST_SUCCESSFUL_UNIT        =
```

──────────────────────────────────────────────────────────────────────────
## BLOQUE 1 — AUDITORÍA FUNCIONAL E2E
──────────────────────────────────────────────────────────────────────────

### Estado de infraestructura al momento de la auditoría (API_REAL)

```
docker ps (extracto relevante):
gmp-api             Up  :8000  health: {"api":"ok"}
factory-api         Up  :9000  health: {"api":"ok","postgres":"ok","redis":"ok","ollama":"ok"}
gmp-postgres        Up (healthy)
gmp-redis           Up (healthy)
oos_hplc_investigator_api  Up  :8102
lab_qc_project_api        Up  :8101
aria-*, hotelbot-*   Up (fuera de alcance — prohibido tocar)
```

`GET /health` en ambos puertos base respondió 200 en vivo. `EVIDENCE:
API_REAL`.

### Cadena E2E, con ENGINE etiquetado

```
documento de entrada            ENGINE=CURRENT  API_REAL   fuente en
                                 /home/ing_cpmo/GMPAI/source/... (sha256
                                 verificado en state.json de paquete)
→ ingesta/extracción             ENGINE=CURRENT  UNIT_TEST  document_
                                 structure_extractor.py existe y tiene
                                 tests bajo factory/tests/
→ retrieval                      ENGINE=CURRENT  E2E_REAL   top_k_fusion
                                 (M2/V1, commit 1bd2f8d/08efa7e por
                                 memoria de proyecto) — evidencia real en
                                 review_queue.jsonl (candidates con
                                 bm25_rank/embedding_rank/fusion_rank
                                 poblados, no mockeados)
→ análisis regulatorio           ENGINE=CURRENT  E2E_REAL   corridas
                                 chunked-* con checkpoints reales en
                                 factory/regulatory/pilot_run/checkpoints/
→ evidencia/página                ENGINE=CURRENT  E2E_REAL   page_start/
                                 page_end poblados en cada candidate del
                                 review_queue.jsonl real
→ hallazgo                       ENGINE=CURRENT  E2E_REAL   conclusion=
                                 EVIDENCE_NOT_LOCATED_IN_CANDIDATES
                                 (fail-closed real, no aprobación
                                 automática) confirmado en 5 findings
                                 pendientes reales del review_queue
→ informe unificado               ENGINE=CURRENT  API_REAL   endpoint
                                 /api/v1/layer9/tier1-reports existe en
                                 vivo (confirmado en openapi.json)
→ candidato NCR/CAPA cuando aplica ENGINE=CURRENT  NOT_TESTED en esta
                                 corrida (memoria de proyecto: cerrado en
                                 e37829b vía recurrencia real de
                                 review_queue.jsonl — no re-ejecutado hoy,
                                 solo verificado que el código y el
                                 endpoint de gobernanza existen)
→ cola/revisión humana            ENGINE=CURRENT  API_REAL   /api/v1/
                                 layer9/review-queue existe; contenido
                                 real con 5 entradas pending confirmadas
                                 por lectura directa del .jsonl
→ identidad autenticada           ENGINE=CURRENT  API_REAL   require_
                                 identity (Depends) confirmado en
                                 remediation_packages.py:30,152; rotación
                                 de key confirmada por Cesar 2026-08-19
                                 (HUMAN_ACTION_REQUIRED, no reproducible
                                 por este auditor sin la key)
→ decisión humana                 ENGINE=CURRENT  HUMAN_ACTION_REQUIRED
                                 — requiere clic real de Cesar, no
                                 automatizable ni auditable por este
                                 proceso más allá de lo ya en 0.3
→ RemediationDirective humana      ENGINE=CURRENT  **NOT_TESTED /
                                 EVIDENCIA INSUFICIENTE** — ver 0.3.
                                 Endpoint /api/v1/layer9/remediation/
                                 directives existe (API_REAL, confirmado
                                 en openapi.json) pero no se pudo
                                 correlacionar un registro nuevo con
                                 fecha 2026-08-19
→ paquete de remediación           ENGINE=CURRENT  NOT_TESTED para K3
                                 específicamente (ver 0.3); SÍ hay
                                 evidencia real de paquetes anteriores
                                 (PKG-FS-V1-2-REAL-CONTROLLED,
                                 PKG-FS-V1-2-MEDIUM-RISK-REAL,
                                 2026-07-21, status
                                 PACKAGE_READY_FOR_RELEASE real)
→ documento borrador NO APROBADO   ENGINE=CURRENT  INTEGRATION_TEST +
                                 API_REAL parcial — DOCUMENT_RELEASED=false
                                 siempre confirmado (0.2); el marcador de
                                 "no aprobado" existe en el estado del
                                 paquete (status != RELEASED nunca posible
                                 sin create_release_record, que no tiene
                                 endpoint)
→ redline                        ENGINE=CURRENT/LEGACY mixto — los
                                 archivos .docx modificados el
                                 2026-08-19 en pilot_run/
                                 dry_run_validation_r4_t1_1v2/ (v1/v2
                                 candidate+redline) tienen naming que
                                 corresponde al patrón R4-T1 (candidato de
                                 prueba dirigido, no al RC canónico
                                 legacy) — ver 0.3 sobre si K3 usó este
                                 caso o uno real
→ manifest                       ENGINE=CURRENT  UNIT_TEST  validation_
                                 evidence_manifest.py existe con tests
→ audit trail/trazabilidad        ENGINE=CURRENT  API_REAL   /api/v1/
                                 audit/entries, /api/v1/audit/summary,
                                 /api/v1/audit/verify existen en vivo
→ archivos finales                ENGINE=CURRENT  NOT_TESTED — no se
                                 localizó el archivo final específico de
                                 K3 (ver 0.3)
```

Fail-closed confirmado en el punto de decisión más crítico: cada finding
real en `review_queue.jsonl` con `conclusion:
EVIDENCE_NOT_LOCATED_IN_CANDIDATES` queda en `status: pending`, nunca se
autoaprueba. Ningún endpoint de la API expone una ruta de aprobación
regulatoria automática — todas las rutas de decisión
(`/review/.../approve`, `/review/.../reject`, `/governance/decisions/
.../confirm`) requieren `require_identity` (confirmado por grep en las
rutas correspondientes).

### Estado real de las 6 misiones

```
gmpai_document_validation  ENGINE=LEGACY (para el RC v1.4) — RC v1.4-
                            20260715T031540 real, con
                            pipeline_pilot_llm.json, test_report.json,
                            quality_gates_report.json (API_REAL /
                            release_candidates confirmado en disco).
                            Trabajo posterior (Tier-1, review_queue) es
                            ENGINE=CURRENT y SÍ tiene deployment activo
                            de facto vía factory-api (no vía
                            factory/deployments/, que no tiene carpeta
                            propia para esta misión).

oos_hplc_investigator       Deployment real confirmado: contenedor
                            oos_hplc_investigator_api Up en :8102
                            (API_REAL), carpeta factory/deployments/
                            oos_hplc_investigator/ completa (manifest,
                            Dockerfile, tests), factory/test_results/
                            oos_hplc_investigator.jsonl existe con datos
                            reales. Cifra "26 pruebas, 10/10 casos únicos
                            PASS" del brief no se recontó línea por línea
                            en esta auditoría (NOT_TESTED el recuento
                            exacto) pero el artefacto que la respaldaría
                            existe y está vivo.

oos_hplc_api_test           **No existe como directorio** ni en
                            factory/workspaces/ ni en
                            factory/workspaces_archive/ ni en
                            factory/deployments/ ni en
                            factory/release_candidates/. 0 pruebas
                            confirmado por ausencia total, no por
                            inspección de una carpeta vacía —
                            posiblemente nunca se materializó como
                            proyecto, o fue limpiado. Diferencia real
                            frente al resto de misiones "no desplegadas",
                            que sí tienen carpeta.

c8_alcoa_validator           Carpeta existe en factory/workspaces/ y
                            factory/release_candidates/c8_alcoa_validator/
                            pero sin carpeta en factory/deployments/ ni
                            contenedor corriendo (docker ps no lo lista).
                            0 pruebas, no desplegado — confirmado.

lab_qc_project                Deployment real: contenedor
                            lab_qc_project_api Up en :8101, con
                            postgres/redis dedicados también Up
                            (healthy). factory/deployments/lab_qc_project/
                            completo con manifest, approval.json,
                            quality_gates_report.json. **Inconsistencia
                            confirmada por evidencia real**: no se
                            localizó factory/test_results/
                            lab_qc_project.jsonl ni equivalente — el
                            único .jsonl de resultados de test en
                            factory/test_results/ es el de
                            oos_hplc_investigator. Esto corrobora el
                            hallazgo del brief: "desplegado con 0
                            pruebas" es real, no un rumor — un proyecto
                            está en producción (contenedor vivo,
                            approval.json presente) sin archivo de
                            resultados de test localizable.

r6_change_control             factory/workspaces_archive/
                            r6_change_control_20260625/ — está en el
                            archivo, no en workspaces activo. 0 pruebas,
                            no desplegado, confirmado. Coincide con nota
                            de memoria de proyecto: "CHANGE_CONTROL sin
                            señal real, no implementado."
```

──────────────────────────────────────────────────────────────────────────
## RESUMEN FINAL
──────────────────────────────────────────────────────────────────────────

```
ENGINE_RECONCILIATION = RESUELTO (0.1, evidencia de filesystem + git +
                        crontab + código fuente citado línea por línea)
CODE_TESTS            = PASS parcial (tests unitarios existen para los
                        módulos centrales del motor actual; no se
                        re-ejecutó la suite completa en esta auditoría
                        de solo lectura — NOT_TESTED el pytest run
                        íntegro)
API_VALIDATION         = PASS (gmp-api y factory-api responden 200 en
                        /health en vivo; superficie completa de rutas
                        verificada contra openapi.json real)
LIVE_UI_VALIDATION      = PARCIAL — mission_control.html inspeccionado
                        como fuente servida (UI_REAL de archivo, no de
                        clic de navegador — este entorno es headless sin
                        display); estructura de navegación confirmada,
                        interacción real no ejecutada por este auditor
DOCUMENT_ANALYZER_E2E   = PARCIAL — cadena completa hasta "hallazgo" y
                        "cola de revisión humana" con evidencia E2E_REAL;
                        tramo RemediationDirective→archivos finales de
                        K3 específicamente sin evidencia persistente (0.3)
HUMAN_GOVERNANCE        = PASS — fail-closed confirmado, require_identity
                        en todas las rutas de decisión, sin aprobación
                        automática en ningún endpoint
TRACEABILITY            = FAIL parcial — ver 0.3: el evento de cierre más
                        importante del proyecto (K3) no dejó rastro de
                        artefacto reproducible
REMEDIATION_FLOW        = PARCIAL — flujo y endpoints existen y
                        funcionan (paquetes de 2026-07-21 son evidencia
                        real), pero create_release_record() sin endpoint
                        (por diseño) y K3 sin artefacto propio
GENERATED_ARTIFACTS_VERIFIED = PARCIAL — mapa completo en
                        MAPA_ARTEFACTOS_Y_RUTAS_GENERADAS.md; algunas
                        rutas referenciadas en state.json ya no existen
                        en disco (scratchpad efímero, ver 0.3)

OBJECTIVE_1_READ_ANALYZE              = PASS (E2E_REAL vía review_queue)
OBJECTIVE_2_IDENTIFY_GAPS             = PASS (findings reales, fail-closed)
OBJECTIVE_3_FINDING_REPORT            = PASS (tier1-reports endpoint real,
                                        evidencia anclada con page_start/
                                        page_end en cada candidate)
OBJECTIVE_4_CONTROLLED_CORRECTED_DRAFT = PARCIAL (DOCUMENT_RELEASED=false
                                        por diseño confirmado; cadena de
                                        borrador→redline→manifest sin
                                        artefacto propio para K3)
OBJECTIVE_5_HUMAN_REVIEW_AND_AUDIT     = PARCIAL (gobernanza fail-closed
                                        real; trazabilidad de K3 con vacío
                                        real, ver 0.3)

PASS_COUNT       = 9
FAIL_COUNT        = 1 (trazabilidad de K3 sin artefacto)
NOT_TESTED_COUNT   = 6 (pytest suite completa, recuento exacto de
                    oos_hplc 26/10, clic real de UI en navegador,
                    contenido exacto del endpoint remediation/directives
                    sin credenciales, NCR/CAPA re-ejecución, archivo final
                    específico de K3)

CRITICAL_FAILURES = 0
NON_BLOCKING_FINDINGS = 4:
  1. Ausencia de artefacto persistente correlacionable con el clic K3
     del 2026-08-19 (0.3) — SEVERITY=MEDIA, no bloquea el gate ya cerrado
     por Cesar, sí compromete reproducibilidad regulatoria futura.
  2. lab_qc_project desplegado en producción sin archivo de resultados
     de test localizable — SEVERITY=MEDIA, contradice la disciplina de
     evidencia del propio proyecto.
  3. oos_hplc_api_test no existe como proyecto en ningún directorio —
     SEVERITY=BAJA, probablemente nunca se materializó; confirmar con
     Cesar si debe eliminarse del roadmap o si es un nombre mal escrito.
  4. `pilot_status.sh` cae a log en `/tmp/pilot_${RUN_ID}.log` cuando un
     piloto corre bajo tmux en vez de systemd-run (0.5) — SEVERITY=BAJA,
     solo afecta el log de texto, no el checkpoint de datos reanudable;
     FIX_REQUIRED=SÍ pero no ejecutado (solo lectura).

HUMAN_ACTIONS_REQUIRED = 4:
  1. Cesar decide si autoriza el README ARCHIVED propuesto en 0.1 para
     el directorio legacy.
  2. Cesar decide si vale la pena reconstruir manualmente el artefacto
     de K3 (o aceptar su propia palabra como registro suficiente) — esta
     auditoría no puede decidir eso por él. K3 permanece CERRADO; esto
     no reabre el gate, solo registra el vacío de trazabilidad (0.3).
  3. Prueba real de kill-and-resume del `CheckpointStore` (0.5) antes de
     confiar en el mecanismo para una corrida de producción larga y
     costosa — no ejecutada en esta auditoría de solo lectura.
  4. oos_hplc_api_test: no localizado en ningún directorio del
     repositorio (ver hallazgo no bloqueante #3). No se elimina del
     roadmap, no se renombra, no se asume error de tipeo — la decisión
     queda como HUMAN_ACTION_REQUIRED / PENDING_CAPA9, sin resolver por
     esta auditoría.

SYSTEM_FUNCTIONAL = SÍ, con las salvedades de trazabilidad anotadas arriba
OBJECTIVES_MET     = 3 de 5 en PASS pleno, 2 de 5 en PASS parcial — ningún
                    objetivo en FAIL
READY_FOR_USER_ACCEPTANCE = SÍ (el sistema funciona y Cesar ya lo aceptó
                    vía K3; esta auditoría documenta la reserva de
                    trazabilidad para que quede registrada, no para
                    revertir esa aceptación)
READY_FOR_PRODUCTION = NO
```

──────────────────────────────────────────────────────────────────────────
Fin del reporte. Ver también:
`docs_plan/MANUAL_OPERATIVO_UI_MISSION_CONTROL.md`
`docs_plan/MAPA_ARTEFACTOS_Y_RUTAS_GENERADAS.md`
Pendiente: aprobación de Capa 9 (Cesar).
