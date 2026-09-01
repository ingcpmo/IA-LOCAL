# REVISIÓN DE CIERRE H-1…H-10 + INSTRUCCIONES PARA CLAUDE CODE

**Fecha:** 2026-09-01 · **Autoridad:** Capa 9 = Cesar · **Autor del reporte:** Capa 8 (Claude Code)
**Origen:** AUTORIZACIÓN Capa 9 «continuar ejecución» (2026-09-01) + reversión del hand-edit no gobernado.
**Rama:** `fix/clon-local-validacion` · **HEAD:** `6be0626` (== `origin`).

Este directorio consolida qué se ejecutó, qué queda pendiente, las evidencias, y las
instrucciones para la siguiente sesión. No modifica ningún artefacto gobernado por sí mismo.

| Archivo | Contenido |
|---|---|
| `00_REVISION_DE_CIERRE.md` | este resumen |
| `01_EVIDENCIAS.md` | commits, tests, estado de gobernanza, diffs verificados |
| `02_INSTRUCCIONES_CLAUDE_CODE.md` | qué debe hacer la siguiente sesión, en orden, con sus condiciones |
| `03_PROPUESTA_PILOT_EXECUTION_035.md` | propuesta concreta de medición R2 (≤ 20 llamadas), sin ejecutar |

---

## 1. EJECUTADO en esta sesión

| # | Acción | Mecanismo | Evidencia | Estado |
|---|---|---|---|---|
| 1 | **FASE 2 del modelo híbrido → CERRADA = PASS / PARKED** | decisión de diseño por mensaje de Capa 9 (no gate formal) | commit `6be0626`; informe `docs_plan/BAKEOFF_MODELOS_SEMANTIC_POC_20260901.md` §10 | ✅ |
| 2 | **Prototipo semántico aislado + bake-off (2 corridas) + H-4 + prueba de recall** | código en `factory/prototypes/semantic_hybrid_poc/` (aislado, no producto) | commits `647b710`, `9d6c86f`; `test_poc.py` 18/18 | ✅ |
| 3 | **H1 = APPROVE_REMEDIATION_V1_2 → REGISTRADA** | metadata + commit (verificado: NO existe servicio/panel de gobernanza para este artefacto — no es clase `ARTIFACT_VERSION`) | commit `24549a3`; `technical_completeness_rules.yaml` `pending_approval.approved: true` | ✅ |
| 4 | **D5-D2 → DEFERRED / NON_BLOCKING_FOR_DEVELOPMENT** | metadata + commit | commit `24549a3`; `held_out_technical_corpus.yaml` bloque `d5d2_gate_status` | ✅ |
| 5 | **Reversión del hand-edit NO gobernado de `decisions_v2.jsonl`** | `git checkout HEAD -- factory/layer9/decisions/decisions_v2.jsonl` (solo ese archivo) | 11 líneas `ARTIFACT_VERSION-2026-022..032` con `recorded_by: null` eliminadas; 45 `PILOT_EXECUTION` + 21 `ARTIFACT_VERSION` gobernados preservados | ✅ |
| 6 | **Validación v1.2** | pytest | targeted v1.2 **124/124**; `qualification_contract` **17/17**; sin regresiones en el set v1.2 | ✅ |
| 7 | **Reconstrucción READ-ONLY del estado de R2** | lectura de docs + ledger | ver `01_EVIDENCIAS.md` §R2 y `03_PROPUESTA_PILOT_EXECUTION_035.md` | ✅ |

### Firmas humanas registradas por Mission Control DURANTE la sesión (por Cesar, no por Claude)

| Gate | Ledger | Fecha | Resultado |
|---|---|---|---|
| **E1-3** (`E1-3-H10-RELATIONS-20260831`) | `ARTIFACT_VERSION-2026-022` (propose, `mission_control_ui`) + `-023` (confirm, Cesar) | 2026-09-01 15:57 | verdict_set 66/67 CORRECT · 1 WRONG_NODE · 0 SPURIOUS · 0 AMBIGUOUS |
| **E1_ACCEPTANCE** (`E1-ACCEPTANCE-20260831`) | `ARTIFACT_VERSION-2026-024` (propose) + `-025` (confirm, Cesar) | 2026-09-01 16:00 | `e1_acceptance = PASS` · RC-2 RESOLVED · RC-3 RESOLVED |

Estas 4 líneas están en `decisions_v2.jsonl` (árbol de trabajo, **sin commitear**) y son
**legítimas** (generadas por el servicio, `proposed_by_id: "mission_control_ui"`, par
propose→confirm, `approved_by_id: "Cesar"`). **NO se revierten.**

---

## 2. PENDIENTE

| # | Pendiente | Responsable | Mecanismo exacto | Bloquea |
|---|---|---|---|---|
| P1 | **E2** (`E2-RPAR-20260831`) — delta R-PAR v1↔v2 | Cesar | Mission Control → Gobernanza → panel **`gate-e2`** (`http://localhost:9000/ui/mission_control.html`) | cierre del arco E1–E3-A |
| P2 | **E3-A** (`E3A-CLEANBASE-20260831`) — base canónica CLEAN | Cesar | Mission Control → panel **`gate-e3a`** | cierre del arco E1–E3-A |
| P3 | **Actualizar `docs_plan/E1_SIGNATURE_HISTORY.md`** con E1-3 (2026-022/023) y E1_ACCEPTANCE (2026-024/025) | Capa 8, próxima sesión | append-only al doc (no reescribir historial) | trazabilidad (el doc de registro va detrás del ledger) |
| P4 | **Commitear `decisions_v2.jsonl`** con las 4 líneas UI legítimas | Capa 8 con OK de Capa 9 | `git add` + commit del ledger; NO editar a mano | persistencia en git del ledger |
| P5 | **D5-D2** (held-out fresco, ground truth de autora independiente) | **Maria Torres** (o autora independiente real ≠ Cesar/IA) | `docs_plan/D5_D2_FRESH_HELD_OUT_DECISION_SHEET_20260831.md` | cualificación final; `reportable_range != SYNTHETIC_ONLY`; cierre formal de D5. **NO** bloquea desarrollo (DEFERRED) |
| P6 | **R2 — medición diagnóstica** (aislar paso A vs paso B del juicio) | Capa 9 aprueba `PILOT_EXECUTION-2026-035`; Capa 8 ejecuta | ver `03_PROPUESTA_PILOT_EXECUTION_035.md`. ≤ 20 llamadas. **0 llamadas consumidas.** | decisión "Palanca C permanente" vs "hay avenida en paso A" |
| P7 | **Rollback de v1.2** si D5-D2 falla umbrales (0.90 / 0.05 / 0) | Capa 9 | condición escrita en `technical_completeness_rules.yaml` `pending_approval.downstream_condition` | — (contingente) |

### Contexto que la siguiente sesión DEBE tener presente

- **R1.5 ya está CLOSED** (Cesar 2026-08-09, commit `484d103`): `evaluation_profile=H2H4` productizado. No hay nada que "ejecutar" en R1.5.
- **R2 recall de juicio = techo confirmado.** 6 vías independientes: baseline 0/7 · H1 0/7 · H2/H4 **2/7** · Palanca A (14b) 2/7 · V2 fusión 2/7 · R2 pool perfecto 1/6 · **B4b V2 completo 0/7** · B4b no-estricta 0/7. En las 56 subcriterios de B4b: **0 `SATISFIES`, 0 `PARTIAL`**. Causa: el 7B local no compromete que ninguna descripción operativa satisfaga un sub-criterio regulatorio.
- **FUNCTIONAL / TECHNICAL no dependen de ese techo:** B8b `FUNCTIONAL_RECALL = 16/16`, FP `0/16`. Salen del grafo determinista, no del juicio de paráfrasis.
- **Roadmap y R2.2/R2.3 están DESACTUALIZADOS** frente al ledger (PILOT_EXECUTION hasta -034; B4b/B8b son posteriores). El doc de estado vigente de R2 es `docs_plan/REPORTE_B4B_MEDICION_RECALL_V2.md`.
- **Decisión de Capa 9 ya enmarcada (B4b §6):** por `0/7 ≤ 2/7` → adoptar **Palanca C (Tier-1) permanente para Regulatory** (ADR §10). La opción "un diagnóstico más" ya se corrió (B4b no-estricta). P6 es un último aislamiento barato antes de cerrar formalmente esa vía.

---

## 3. INVARIANTES respetados en toda la sesión

`AI_RUNTIME = LOCAL_ONLY` · `EXTERNAL_LLM_CALLS = 0` · `DOCUMENT_EGRESS = 0` ·
**0 / 20 llamadas LLM consumidas** · ningún validador relajado · ningún prompt gobernado
modificado · ningún artefacto `ARTIFACT_VERSION` tocado por Claude · `decisions_v2.jsonl`
solo revertido al estado válido de HEAD (y luego reescrito por el propio Mission Control, no
por Claude).
