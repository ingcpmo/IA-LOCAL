# R1 smoke — chunked-2ef3d38d2538 — DEMO / SMOKE, NO APROBADO

**Origen:** `docs_plan/ARQ_RESOLVER_BLOQUEO_R1.md`, Partes 3 y 4.
**Fecha de la corrida:** 2026-08-09.
**Estado:** DEMO/SMOKE — no es baseline formal, no está aprobado, no mide
recall (eso es R2 del roadmap).

## Qué es esto

La primera llamada real a Ollama ejecutada a través del mecanismo de
producción real (`factory/regulatory/corpus_runner.run_pilot_sample_batch`)
después de resolver el bloqueo de gobernanza documentado en
`docs_plan/ROADMAP_ANALIZADOR_GMP.md` (múltiples `PILOT_EXECUTION` vigentes
sobre `RW-0005` que hacían fallar cerrado al resolver). Demuestra que la
cadena **localización → juicio → informe → cola de revisión humana**
ensambla de punta a punta y produce artefactos trazables.

## Resultado, sin maquillar

El requisito objetivo del smoke (`ALCOA_CONTEMPORANEOUS`, caso P5 del
fixture set de recall) **no ancló evidencia** en esta corrida —
`sin_evidencia_localizada`. Ver `informe_hallazgos.md` para el detalle y
la explicación honesta de por qué (el pipeline de producción real evalúa
las 9 requirement_id del agente en una sola llamada — configuración
"baseline", no la configuración H2+H4 de los experimentos de recall, que
nunca se llevó a producción).

## Contenido de esta carpeta

| Archivo | Contenido |
|---|---|
| `checkpoint.json` | Checkpoint real completo del `chunked_engine` (incluye `verified_records_by_req` para las 9 requirement_id evaluadas) |
| `manifest.json` | Manifest del batch (`run_pilot_sample_batch`) |
| `raw_response/task-70b3354a5168.txt.gz` | Respuesta cruda completa del modelo, sin truncar (fix de cap de 8192 chars) |
| `informe_hallazgos.md` | Los 6 campos de Cesar + estado honesto + cobertura, para `ALCOA_CONTEMPORANEOUS` |
| `borrador_o_sin_cambios.md` | "Sin cambios propuestos" — y por qué (sin evidencia anclada, no por cumplimiento) + verificación de integridad del original |
| `trazabilidad.json` | hallazgo → requirement_id → catálogo → cita (null) → página → checkpoint → autorización → auditoría → cola de revisión |

## Trazabilidad hacia atrás

- Autorización usada: `PILOT_EXECUTION-2026-006` (seleccionada
  automáticamente, sin proponer una nueva — `co_covering_instances`:
  `PILOT_EXECUTION-2026-004`).
- Evento de auditoría: `factory/audit/factory_audit.jsonl`, entry_id
  `80796d46-223b-42c9-992b-355616c03bcd`.
- Cola de revisión humana: `factory/layer9/review_queue.jsonl`, rc_id
  `r1-smoke-chunked-2ef3d38d2538`, `status: pending`.
