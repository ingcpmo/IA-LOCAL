# W5 V2 — PILOTO GOBERNADO PRE-CORPUS: DIAGNÓSTICO ANTES DE LAS 232 LLAMADAS

AUTORIDAD: Capa 9 = Cesar. Claude Code = Capa 8.
Objetivo: responder "¿el código cumple los objetivos de W5 V2?" con
evidencia real y barata ANTES de comprometer 80-94h de la corrida formal.
El piloto NO es el corpus. NO autoriza el corpus. NO alimenta el baseline
formal. Aislado por run_context, fingerprint y ruta de salida propios.

PRODUCTION_ENABLEMENT = BLOCKED. REGULATORY_COMPLIANCE = NOT_DETERMINED.

(Secciones 0-6 completas: ver historial de conversación de la sesión
2026-08-08. Este archivo registra el ESTADO REAL de ejecución del plan,
actualizado a medida que avanza — no repite el texto íntegro del plan.)

## Estado del checkpoint 0 (cierre de sesión anterior)

Verificado 2026-08-08: diff de `corpus_budget_formula.py` +
`test_corpus_budget_formula.py` coincide con lo documentado en memoria
(extensión `p50_measured`/`p95_measured`, spec §5.3). Suite completa
corrida: 2225 passed, 4 failed (los 4 son el mismo guard
`git diff --quiet HEAD -- decisions_v2.jsonl`, fallan porque
`D4-2026-004` sigue sin commitear — no una regresión). `D4-2026-004`
confirmado `agent_proposed`, sin firmar. Sin procesos huérfanos, sin
locks activos. **Commit de checkpoint 0 sigue PENDIENTE de confirmación
explícita de Cesar** — no se ha hecho.

## Infraestructura de aislamiento construida (§2/§2.5 del plan)

Brecha encontrada antes de poder ejecutar nada: la infraestructura de
aislamiento no existía (run_context solo aceptaba 'production'/
'validation', el runner no tenía modo pilot, no había familia de decisión
separada, no había script de estado). Construida en esta sesión:

1. `factory/engines/gmpai_integrity/chunked_engine.py`: `run_context`
   acepta ahora `'pilot'` además de `'production'`/`'validation'`.
2. `factory/registry/decision_families.yaml`: familia nueva
   `PILOT_EXECUTION` (consumer `pilot_runner`) — separada de
   `CORPUS_AUTHORIZATION`/`D4`, ninguna otra familia la consulta.
3. `factory/regulatory/pilot_execution.py`: `propose_pilot_execution()` —
   solo propone, nunca ejecuta; payload fija `authorizes_corpus=False`/
   `authorizes_baseline=False` siempre.
4. `factory/regulatory/corpus_runner.py`: `PilotSampleUnit` +
   `run_pilot_sample_batch()` (Piloto 1) — checkpoint_dir/manifest_dir
   propios (`pilot_run/`), tope duro de llamadas desde
   `PILOT_EXECUTION.payload['max_calls']` (NUNCA `compute_d4a()`),
   excertos cortos por página real (no barrido de documento completo).
   Piloto 2 (cadena completa) NO implementado todavía — pendiente,
   requiere leer y wirear ~6 módulos de producción existentes
   (`gap_assessment_finding_mapper`, `remediation_package_service`,
   `governed_candidate_document_pipeline`,
   `remediation_traceability_and_manifest`,
   `independent_candidate_revalidation`,
   `corrected_document_generation_gate`).
5. `factory/tests/test_pilot_isolation.py`: 17 tests nuevos — familia
   separada, tope duro correcto, rutas físicamente distintas de
   producción, `run_context='pilot'` registrado en auditoría, guard duro
   (`PILOT_EXECUTION` firmada NUNCA autoriza `run_corpus_batch()` formal).
6. `factory/scripts/ops/run_corpus_pilot.py` (entrypoint para
   `systemd-run`/`tmux`, modo `--sample`) +
   `factory/scripts/ops/pilot_status.sh` (solo lectura).

Suite completa corrida tras estos cambios: pendiente de confirmar
resultado final en este documento (ver conversación).

## Selección real del Piloto 1 (§3.1) — documentada ANTES de ejecutar

Todos los 20 `requirement_id` del catálogo están `D2_A_READY` hoy
(verificado con `evidence_pack_governance.d2a_ready()`, 20/20 ready — el
pack `21_CFR_211.68(b)` que en la sesión de auditoría original tenía 0
criterios ya está listo). 8 llamadas, 4 agentes × 2, contenido REAL (sin
sintético), incluye el caso conocido ANNEX11_4 (lista de referencias
numeradas) sobre el mismo documento donde se confirmó originalmente.

| # | document_id | agent_id | requirement_id | página real (0-based) | motivo |
|---|---|---|---|---|---|
| 1 | RW-0005 (FS_v1.2) | fda_part11_agent | 21_CFR_11.10(e) | 45 | "Audit trail records shall be archived... Logins, logouts and login attempts must be recorded" — evidencia sustantiva real de audit trail |
| 2 | RW-0005 (FS_v1.2) | fda_part11_agent | 21_CFR_11.10(g) | 39 | Sección 4 "Security"/F09.00 Physical Security, control de acceso al operador — evidencia sustantiva de autoridad/acceso |
| 3 | RW-0005 (FS_v1.2) | eu_annex11_agent | ANNEX11_4 | 1 | Caso CONOCIDO: "GAMP5" aparece dentro de la lista de referencias numeradas `[6]-[12]` — el mismo caso real que produjo el falso positivo semántico en la corrida URS v2.1 (Fase F). Verifica que el rechazo determinista (`detect_reference_list_context`) sigue funcionando contra el documento real, no solo el Golden Dataset |
| 4 | RW-0005 (FS_v1.2) | eu_annex11_agent | ANNEX11_12 | 44 | "UR3.3.6 Data retention... 1 year... archived in an alternate location for safe keeping" — evidencia sustantiva real de almacenamiento de datos |
| 5 | RW-0011 (EMS Control Block Narrative) | alcoa_plus_agent | ALCOA_ATTRIBUTABLE | 12 | "with the proper credentials, the input points can be simulated for calibration or other maintenance activities" — ata la acción a credenciales/identidad real |
| 6 | RW-0005 (FS_v1.2) | alcoa_plus_agent | ALCOA_CONTEMPORANEOUS | 45 | Mismo pasaje de audit trail (#1): "manual interactions... sent to a database for event logging, including user name, action and timestamp" — evidencia sustantiva de contemporaneidad real |
| 7 | RW-0011 (EMS Control Block Narrative) | fda_cgmp_211_agent | 21_CFR_211.68(b) | 12 | Mismo pasaje de credenciales/calibración (#5) — equipo automatizado bajo control de acceso, relevante a 211.68(b) |
| 8 | RW-0012 (PCS Signal Interface Control Block Narrative) | fda_cgmp_211_agent | 21_CFR_211.68(b) | 13 | Pasaje casi idéntico a #7 pero en un documento REAL DISTINTO (SHA-256 distinto) — prueba si el agente juzga consistente el mismo patrón en dos documentos reales separados |

`PILOT_1_SAMPLE_SIZE = 8`. `PILOT_1_AGENTS_COVERED = 4/4`.
`PILOT_1_REAL_CONTENT_USED = true`.

## Selección real del Piloto 2 (§4.1) — documentada ANTES de ejecutar

Documento analizable con menos chunks: `RW-0011` (EMS Control Block
Narrative revB, 7 chunks — empatado con RW-0012, también 7; RW-0011 se
elige por ser el primero en el orden declarado de `CORPUS_PLAN_DOCUMENTS`,
sin otro criterio de desempate declarado por el plan). Los 4 agentes
tienen R(d,a)≠∅ para `document_type=DS`, y los 20 `requirement_id` están
`D2_A_READY` hoy — cobertura completa, sin requisitos
`NOT_EVALUATED_PILOT_SCOPE`.

**Bloqueado**: la ejecución de la cadena completa (§4.2) requiere primero
construir el orquestador de Piloto 2 (pendiente, ver arriba) — no
ejecutar nada de §4 hasta que ese código exista y tenga su propia pasada
de tests.

## Autorización pendiente

Cesar confirmó la tabla del Piloto 1 (2026-08-08). `PILOT_EXECUTION-2026-001`
**PROPUESTA** (`agent_proposed`, `status=ACTIVE`, sin firmar todavía) con
`max_calls=8`, `resolved_target_ids=[RW-0005, RW-0011, RW-0012]`,
`authorizes_corpus=false`, `authorizes_baseline=false` — visible en
Mission Control / `decisions_v2.jsonl` (sin commitear todavía, igual que
`D4-2026-004`). Piloto 2 explícitamente NO incluido en este alcance
(orquestador aún no construido).

**Pendiente**: firma de Cesar (`confirm`) antes de que Claude Code pueda
ejecutar ninguna llamada real a Ollama del piloto. Ninguna llamada real se
ha hecho en esta sesión.
