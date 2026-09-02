# F9 — PAQUETE DE DECISIÓN PARA EL GATE HUMANO (Capa 9 / Cesar)

**Plan de reconciliación v1.1 · FASE 9 · gate humano.**
**F9 la decide Capa 9.** Claude Code entrega este paquete y **se detiene**. Claude Code NO
firma E2/E3-A, NO ejecuta `PILOT_EXECUTION-2026-035`, NO reanuda R2 sin autorización explícita
en esta fase.

**HEAD = `4233df7` → (tras este commit) `reconc-F9`.** Rama `fix/clon-local-validacion`.

---

## 1. Estado del arco de reconciliación

| gate | resultado |
|---|---|
| F0 … F7 (fase a fase, Devin + Capa 9) | **PASS** |
| F7 acumulativa (coherencia del conjunto) | **PASS** |
| **F8 — cruce Plan ↔ Claude Code ↔ Devin (LA MESA)** | **`VERDICT_F8 = PASS`**, `ALL_CRITICAL_PASS = YES`, `BLOCKING_INCONSISTENCIES = 0`, `F8_CAN_ADVANCE_TO_F9 = YES` |

9 tags en cadena lineal (`reconc-F0`, `-F1`, `-F1-r1`, `-F2`, `-F2-r1`, `-F3`, `-F4`, `-F5`,
`-F6`, `-F7`, `-F8`); tags históricos no movidos. Las 8 discrepancias D1–D8 concuerdan entre
Plan, Claude Code y Devin.

### Invariantes congeladas — estado al cierre de F8

Todas **intactas** (detalle y evidencia en `F8_COMPARISON_INPUT.md §4`): `LLM_CALLS = 0` ·
`E2 / E3-A` no firmadas · `PILOT_EXECUTION-2026-035` no ejecutada · `HYBRID FASE 3` no iniciada
· `PRODUCTION_ENABLEMENT = BLOCKED` · prompts gobernados sin tocar · validadores no relajados ·
`decisions_v2.jsonl` sha `1b0c7cf8…` inicio==fin · audit trail sin reescribir · 0 rutas
efímeras · sin `QUALIFIED` / `READY_FOR_PRODUCTION` · sin contenido de cliente en el repo
público · tags históricos intactos.

---

## 2. Las tres decisiones de F9

### 2.1 `E2_READY` — paridad v1 ↔ v2

| | |
|---|---|
| **Precondición del plan** | `E2_READY = YES sii F4 = PASS ∧ F5 = PASS ∧ F6(A/B/C) = PASS` |
| **Estado** | F4 = PASS · F5 = PASS · **F6(A/B/C) = PASS** (deterministas RUN1==RUN2; **clone-drift A↔B = 0**, findings byte-idénticos `b43b548b`; `document_egress_bytes = 0`; `human_gate_intact = True`) |
| **Evidencia** | `F6_R_PAR_DELTA_FINAL.md §2-3-5`, `F6_hashes.json`, baseline F5 `3fcb3ae8 / 2fdda0e2 / 235f724a` |
| **Qué habilita `E2_READY = YES`** | Declarar formalmente que v2 reproduce v1 sobre RW-6 sin drift de clon. Es un flag de *readiness*, **no** la firma de E2. |
| **Qué NO habilita** | No firma E2 (invariante `E2 = NO FIRMAR` sigue vigente hasta acto gobernado aparte por panel `gate-e2`). No toca `PRODUCTION_ENABLEMENT`. |
| **Recomendación de Claude Code** | **Condiciones cumplidas para `E2_READY = YES`.** El escenario D (RW-0003) `SKIPPED_NO_STORE` **no** es precondición (corrección 5). |

### 2.2 `E3A_READY` — base limpia para E3-A

| | |
|---|---|
| **Precondición del plan** | `E3A_READY = YES sii F1 = PASS ∧ F2 = PASS ∧ F6(A/B/C) = PASS` |
| **Estado** | F1 = PASS (`F1_GLOBAL = PASS`, ground truth humano `2f7a00dc…`, HEAD 0/8 vs WT 8/8) · F2-r1 = PASS (clon limpio, `--runs 3` determinista, RW-0012 des-contaminado 8 secc) · F6(A/B/C) = PASS |
| **Evidencia** | `F1_FINAL_CORRECTIVE_REPORT.md`, `F2_R1_CORRECTIVE_REPORT.md`, `VALIDATION_BASELINE_MANIFEST.json` |
| **Qué habilita `E3A_READY = YES`** | Declarar que la base de extracción/grafo está limpia y reproducible para construir E3-A. Flag de *readiness*, **no** la firma de E3-A. |
| **Qué NO habilita** | No firma E3-A (`E3-A = NO FIRMAR` vigente hasta panel `gate-e3a`). |
| **Recomendación de Claude Code** | **Condiciones cumplidas para `E3A_READY = YES`.** |

### 2.3 `R2_READY_TO_RESUME` — reanudación del track de recall

| | |
|---|---|
| **Precondición del plan** | Base de extracción/grafo estable y auditada (F1..F6 PASS) + presupuesto LLM local autorizado. |
| **Estado** | Base estable (F1..F8 PASS). Autorización previa de Capa 9 (mensaje del 2026-08-31): **R1.5 + preparación/ejecución de R2 con tope de 20 llamadas LLM locales**, `AI_RUNTIME = LOCAL_ONLY`, `EXTERNAL_LLM_CALLS = 0`, `DOCUMENT_EGRESS = 0`; "detente al terminar R1.5/R2 o al consumir las 20 llamadas". FASE 2 del track híbrido cerrada = PASS/PARKED (el `recall_probe` **refutó** la hipótesis de red de seguridad: 1/7 < 2/7 baseline). |
| **Qué habilita `R2_READY_TO_RESUME = YES`** | Reanudar R1.5/R2 (roadmap `ROADMAP_ANALIZADOR_GMP.md`) — la palanca real de recall, gate bloqueante de R3–R5. |
| **Qué NO habilita** | No inicia HYBRID FASE 3. No supera las 20 llamadas. No hace egress de documento. No avanza a fase posterior sin nueva aprobación. |
| **Recomendación de Claude Code** | **Habilitable.** Si Capa 9 confirma en F9, se ejecuta bajo el presupuesto ya fijado y se **detiene** al terminar R1.5/R2 o al consumir las 20 llamadas. |

---

## 3. Ítems abiertos — decisión de Capa 9 (no bloquean F9, sí conviene resolver)

| # | ítem | recomendación de Claude Code |
|---|---|---|
| 1 | 3 tests de hardening con fingerprint stale (`88f15b69`/`fdc29721`/`b5196a71` → `2fdda0e2`/`235f724a`/`693fc746`) — `test_h4_graph_snapshot`, `test_h5f_hardening:33-34`, `test_h7_coverage_governance:21-24` | **Autorizar corrección mecánica** (mismo tipo que `test_extraction_adequacy.py:214` en F2-r1). Es consecuencia de la de-contaminación de RW-0012, no de un fix. Mientras no se corrija, esos 3 tests fallan sobre el HEAD limpio. |
| 2 | Corrección del generador de IDs `decision_store_v2.next_instance_id:189` (acuña `max()` del JSONL revertible) | **Fase/decisión propia.** Opciones: `max()` sobre JSONL ∪ audit trail, o contador monótono dedicado. El ledger NO se reescribe. |
| 3 | `ARTIFACT_VERSION-2026-024..028` (2026-08-31) `NO_RECONCILIABLE` justificada | **Aceptación explícita** de Capa 9 (artefactos no identificables desde el audit trail; históricos quedan en el append-only). |
| 4 | Escenario D del R-PAR (RW-0003 SAT) `SKIPPED_NO_STORE` | Capacidad nueva, NO paridad. Para habilitar: `rw0003_store.status = AVAILABLE` + store gobernado (`CT-WP-D-REAL` / `D-4-H9`). **No** condiciona `E2_READY`/`E3A_READY`. |
| 5 | Commit P4 — 4 líneas de servicio de `decisions_v2.jsonl` (E1-3 + E1_ACCEPTANCE, Mission Control) sin persistir en git | **OK explícito** de Capa 9 para commitear (son del servicio, no hand-edit). |
| 6 | Out-of-scope pre-sesión: `remediation_directive.py`, `test_remediation_directive.py`, `test_r4_t1_1v2_cold_chain_validation.py`, `test_release_decision_coverage.py` | Decisión aparte. Congelados como patches en `F0_diffs/`. Ninguna fase del arco los commitea. |
| 7 | D5-D2 — autor independiente (Maria Torres ≠ Cesar) para el corpus técnico held-out | Requerido para `FINAL_QUALIFICATION` y `reportable_range != SYNTHETIC_ONLY`. Ya `DEFERRED / NON_BLOCKING_FOR_DEVELOPMENT`. |

---

## 4. Lo que Claude Code hará / no hará según la respuesta de F9

| respuesta de Capa 9 | acción de Claude Code |
|---|---|
| `E2_READY = YES` y/o `E3A_READY = YES` | Registrar el flag donde Capa 9 indique. **NO firmar** E2/E3-A (eso es acto gobernado por panel `gate-e2`/`gate-e3a`, decisión humana aparte). |
| `R2_READY_TO_RESUME = YES` | Ejecutar R1.5/R2 con tope de 20 llamadas LLM **locales**, `AI_RUNTIME = LOCAL_ONLY`, `EXTERNAL_LLM_CALLS = 0`, `DOCUMENT_EGRESS = 0`. Detenerse al terminar o al consumir las 20. NO avanzar a fase posterior sin nueva aprobación. |
| Autorización de los ítems abiertos 1/5 | Aplicar la corrección mecánica de los 3 tests / commitear P4, con diff mostrado. |
| Sin respuesta / `NO` | Detenerse. El arco `reconc-F0..F8` queda cerrado y auditado; sin más acción. |

---

## REPORTE FORMATO OBLIGATORIO — F9

```
FASE            = F9 (gate humano ; decide Capa 9 / Cesar)
PRE_COMMIT      = 4233df7  (reconc-F8, con veredicto de la mesa relevado en §7)
POST_COMMIT     = <commit reconc-F9>  (solo este paquete de decisión)
WORKTREE_PRE    = igual que reconc-F8
WORKTREE_POST   = + docs_plan/reconc/F9_DECISION_PACKAGE.md ;
                  docs_plan/reconc/F8_COMPARISON_INPUT.md (+ §7 veredicto de la mesa)
DIFF            = docs_plan/reconc/F9_DECISION_PACKAGE.md (nuevo) ;
                  docs_plan/reconc/F8_COMPARISON_INPUT.md (+§7)
COMMANDS        = ninguno ejecutable (F9 es decisión humana) ; paquete derivado de F0..F8
TEST_RESULTS    = n/a (F9 no ejecuta)
INPUT_HASHES    = VALIDATION_BASELINE_MANIFEST.json ; F6_hashes.json ; ledger 1b0c7cf8…
OUTPUT_HASHES   = n/a
FINGERPRINTS    = baseline F5: 3fcb3ae8 / 2fdda0e2 / 235f724a (ENFORCE) / 693fc746 (OBSERVE)
ARTIFACTS       = docs_plan/reconc/F9_DECISION_PACKAGE.md ; arco reconc-F0..F8
GOVERNANCE_EVENTS = ninguno escrito por Claude en F9
DEVIATIONS      = ninguna. Claude Code entrega el paquete y se detiene ; no firma E2/E3-A ;
                  no reanuda R2 sin el OK de F9.
EXPECTED_VS_ACTUAL:
  EXPECTED: paquete de decisión con las 3 preguntas de F9, sus precondiciones ya satisfechas,
            y los ítems abiertos para Capa 9.
  ACTUAL:   E2_READY / E3A_READY / R2_READY_TO_RESUME con precondiciones = cumplidas (F1..F8
            PASS, F8 = PASS por la mesa) ; 7 ítems abiertos con recomendación ; matriz de
            acciones de Claude Code según la respuesta ; invariantes intactas.
PROPOSED_VERDICT = (lo decide Capa 9 / Cesar ; Claude Code no adjudica F9)
```

---

## Resumen para Cesar

El arco `reconc-F0..F8` está **cerrado y auditado**: Devin fase a fase, la mesa en el cruce
final (`VERDICT_F8 = PASS`, 0 inconsistencias bloqueantes). Las 3 decisiones de F9 tienen sus
**precondiciones cumplidas**:

- **`E2_READY`** → recomendado YES (F4/F5/F6 PASS, clone-drift 0).
- **`E3A_READY`** → recomendado YES (F1/F2/F6 PASS, base limpia).
- **`R2_READY_TO_RESUME`** → habilitable bajo el presupuesto ya autorizado (20 llamadas locales,
  0 egress).

Ninguna de estas decisiones firma E2/E3-A ni toca `PRODUCTION_ENABLEMENT` — son flags de
*readiness*; la firma es un acto gobernado aparte por los paneles `gate-e2` / `gate-e3a`.
Claude Code queda **detenido** a la espera de tu decisión F9.
