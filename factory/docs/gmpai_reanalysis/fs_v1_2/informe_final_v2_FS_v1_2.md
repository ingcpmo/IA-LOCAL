# Informe final v2 — Cierre validado de FS_v1.2 (Piloto B)

**Proyecto:** gmpai_document_validation (Rockwell)
**Documento analizado:** `215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf`
**SHA-256 documento original:** `56095a7541fbb62e30d00e77308fde4c2ac0f4ec945adbf19a968b79debc82eb`
**Commit de referencia:** `0d69f8409d9bd8b936e1eed8b4551e3423e9d713`
**Decisión Capa 9 de referencia:** `ff640643-b767-426b-af5f-720f4edee78b` (Cesar, `conditional_approve`, 2026-07-16T14:03:21Z)
**Estado del borrador:** `DRAFT_READY_AWAITING_HUMAN_REVIEW`
**Generado:** 2026-07-16 (paquete de cierre run `20260716T150408Z`)

---

## 0. Propósito de este informe

Este documento existe para **evitar una confusión concreta**: sumar o mezclar
resultados de dos ejercicios de alcance y metodología distintos sobre el
mismo proyecto. Cada sección de abajo separa explícitamente qué es
**histórico** (generado antes del Piloto B / antes del commit `0d69f84`) de
qué es **vigente** (generado por el Piloto B y confirmado por la decisión
humana `ff640643`).

## 1. RC v1.4 histórico (alcance: 32 documentos, motor no-chunked)

- Release Candidate canónico: `gmpai_document_validation-rc-v1.4-20260715T031540`, **approved por Cesar** el 2026-07-15.
- Cobertura: 32 documentos declarados en la misión (14 Rockwell + 18 SCADA), analizados por 4 agentes deterministas/LLM sin chunking por página.
- **267 findings totales históricos** (Part 11 + Annex 11 + ALCOA+ + trazabilidad), consolidados en `pipeline_pilot_llm.json` de ese RC.
- El paquete de descarga asociado a este RC (`paquete_final.zip`, run `20260715T171646Z`) queda clasificado como:
  - `LEGACY_RC_V1.4_PRE_FS_REANALYSIS`
  - `SUPERSEDED_FOR_OPERATIONAL_USE`
  - Se conserva íntegro para auditoría, ver `LEGACY_STATUS.json` en ese run. **No se sobrescribió ni se eliminó.**

## 2. Piloto A — URS (histórico, ejercicio previo)

- Ejercicio de trazabilidad documental (`requirements_traceability_agent`) sobre el URS de Rockwell contra el V-model GAMP 5, ejecutado antes del Piloto B.
- Su único finding real de trazabilidad vigente (familia `Rockwell::MCCPDC-215115305`, gap de etapa `PROTOCOL_TEMPLATE`) es la base del ítem abierto **REM-GMPAI-001** (ver sección 6). Este finding **no se recalculó ni se reevaluó** en el Piloto B — sigue vigente tal como fue registrado.

## 3. Piloto B — FS_v1.2 (VIGENTE, este cierre)

- Motor: `chunked_engine` (chunking por página, 27 chunks, corrige el bug de anclaje en `no_cumple` de sesiones anteriores).
- Documento: `215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf` (58 páginas, 132,506 caracteres extraídos).
- Cobertura: **100% en los 3 agentes deterministas** (`fda_part11_agent`, `eu_annex11_agent`, `alcoa_plus_agent`), 27/27 chunks OK cada uno. Ver `run_id`/`task_id`/timestamps completos en `agent_reports/*.json` de este paquete.
- `alcoa_plus_agent` tuvo un reintento parcial documentado (`retry-9a750a168a00` sobre 6 de 27 chunks: `[1,6,7,18,19,20]`), fusionado el 2026-07-16T13:14:18Z — ver `alcoa_plus_agent.pre_retry.json` (estado ANTES del retry) vs `alcoa_plus_agent.json` (estado final fusionado). Ambos se incluyen en este paquete para trazabilidad completa del cambio.
- **19 findings específicos consolidados del FS_v1.2** (no se suman a los 267 históricos — son de alcance, motor y momento distintos).
- **4 contradicciones internas** detectadas por el motor chunked (evidencia contradictoria entre páginas/chunks para un mismo requisito) — **las 4 fueron resueltas con decisión humana** (`ff640643`, Cesar, `conditional_approve`):

| Contradicción | Requisito | Tipo de resolución |
|---|---|---|
| C1 | `21_CFR_11.10(d)` | falso positivo (evidencia mal asignada a checkpoint) |
| C2 | `ANNEX11_7.1` | diferencia de alcance (no contradicción real) |
| C3 | `ANNEX11_12` | falso positivo (evidencia mal asignada a checkpoint) |
| C4 | `ALCOA_AVAILABLE` | diferencia de alcance (no contradicción real) |

**Importante:** esta resolución es una aprobación de la **interpretación técnica** de las 4 contradicciones, **no** una declaración de cumplimiento GMP, ni de aprobación/efectividad/liberación del documento. El borrador permanece `DRAFT_READY_AWAITING_HUMAN_REVIEW`.

## 4. Ejecuciones `RESULT_RECOVERED` históricas vs ejecuciones chunked verificadas

- **Históricas (`RESULT_RECOVERED`):** ejecuciones del RC v1.4 y de ciclos anteriores donde el resultado se recuperó de una corrida previa (ver `agent_execution_status.json` de los runs `paquete_final.zip` legados) — no vuelven a ejecutarse ni se reprocesan aquí.
- **Vigentes (chunked verificadas):** las 3 corridas del Piloto B sobre FS_v1.2 (`chunked-26e4369b44f1`, `chunked-a652a0ef1f18`, `chunked-14079f37e579` + su retry `retry-9a750a168a00`) están **verificadas chunk a chunk** (27/27 `ok: true` con `task_id`, `started_at`/`finished_at` individuales — ver `agent_reports/*.json`). No son una recuperación de resultado anterior: son ejecución real y trazable del motor de chunking corregido.

## 5. Artefactos históricos vs artefactos vigentes en este paquete

| Categoría | Histórico (NO tocar, solo auditoría) | Vigente (cierre FS_v1.2) |
|---|---|---|
| Paquete de descarga | `paquete_final.zip` run `20260715T171646Z` (`LEGACY_RC_V1.4_PRE_FS_REANALYSIS`) | `paquete_final.zip` run `20260716T150408Z` (este) |
| Borrador SAT3 | `PILOTO_..._SAT3_..._draft_v1.docx` dentro del run legado — reclasificado `LEGACY_PRE_FIX` / `SUPERSEDED_FOR_OPERATIONAL_USE` / `PENDING_REEVALUATION` | No aplica en este cierre (SAT3 no es objeto del Piloto B) |
| Findings | 267 findings del RC v1.4 (32 documentos, motor no-chunked) | 19 findings del FS_v1.2 (1 documento, motor chunked) |
| Decisión humana | Aprobaciones de RC v1.0–v1.4 (Cesar) | Decisión `ff640643` (Cesar, `conditional_approve`, contradicciones C1–C4) |

## 6. Ítems abiertos — NO se cierran en este paquete

- **COR-1** (control de acceso y autorización) — **abierto**.
- **COR-5** (almacenamiento, retención y disponibilidad) — **abierto**.
- **COR-2, COR-3, COR-4** — sin evidencia de implementación; se documentan como pendientes, sin asumir cierre.
- **REM-GMPAI-001** (protocolo IQ/OQ/PQ del SAT no disponible) — **abierto**, sin relación de cierre con el Piloto B (pertenece al Piloto A / trazabilidad SAT).

## 7. Auditoría

Ver `audit_summary/audit_post_commit.json` de este paquete: snapshot real de `verify_chain()` al momento de generar este paquete (estado reportado tal cual, sin editar), más los eventos de la cadena de auditoría relacionados con `gmpai_document_validation` desde el inicio del reanálisis de FS_v1.2 (2026-07-16) hasta la fecha, incluyendo el registro de la decisión `ff640643`.

## 8. Conclusión

Este cierre corresponde **únicamente** a `FS_v1.2.pdf`. No se avanza al siguiente documento del corpus Rockwell hasta que este paquete sea verificado (ver matriz PASS/FAIL) y se declare `SAFE_TO_ADVANCE = true`. No se modificó ningún documento original. No se cerraron COR-1, COR-5 ni REM-GMPAI-001. No se volvió a ejecutar Ollama para este cierre (todos los agentes reutilizan resultados ya generados el 2026-07-16).
