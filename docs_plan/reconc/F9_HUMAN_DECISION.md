# F9 — CIERRE POST-FIRMA HUMANA DE CAPA 9

**Plan de reconciliación v1.1 · FASE 9 · cierre.**
Las firmas humanas de **E2** y **E3-A** ya fueron realizadas por Capa 9 mediante Mission
Control. Este documento es la **verificación READ-ONLY** en el mecanismo gobernado (ledger
`factory/layer9/decisions/decisions_v2.jsonl` + audit trail `factory/audit/factory_audit.jsonl`)
y el registro del cierre.

**Claude Code NO creó firmas, NO simuló firmas, NO editó el ledger, NO reescribió el audit
trail, NO ejecutó fases nuevas, NO ejecutó PILOT-035, NO inició R2.**

**HEAD = `2a5e222` (`reconc-F9`).** Rama `fix/clon-local-validacion`. Cierre etiquetado
`reconc-F9-r1` (tag histórico `reconc-F9` **no movido**).

---

## 1. Verificación de las firmas en el mecanismo gobernado (READ-ONLY)

### 1.1 E2 — delta R-PAR v1↔v2 → **FIRMADO**

**Propuesta (Mission Control):**

| campo | valor real (del ledger) |
|---|---|
| `decision_instance_id` | `ARTIFACT_VERSION-2026-026` |
| `decision_family` / `decision_type` | `ARTIFACT_VERSION` / `ORIGINAL` |
| `decision` | `APPROVE` |
| `decision_origin` | `agent_proposed` |
| `proposed_by_id` | `mission_control_ui` |
| `decision_date` / `recorded_at` | `2026-09-02T00:46:43.681287+00:00` |
| `selection_mode` / `resolved_target_ids` | `EXPLICIT_LIST` / `["docs_plan/R_PAR_DELTA_V1_V2_20260831.md"]` |
| `target_set_hash` | `e10fc3a969e22cea7396286e1babb15f56637168314318af3f5ed63af57abe30` |
| `families_registry_hash` | `d5b998fac31dc00c5d17b766c8af94576a8b50daa40398d307aec7c392def45d` |
| `status` | `ACTIVE` |
| `provenance` | `NATIVE` |
| `payload` | `{gate: "E2", decision_ref: "E2-RPAR-20260831", evidence: "docs_plan/R_PAR_DELTA_V1_V2_20260831.md", r_par_5: "4/4 PASS", not_authorized: ["flip","qa40_adjudication","production"]}` |

**Confirmación humana:**

| campo | valor real (del ledger) |
|---|---|
| `decision_instance_id` | `ARTIFACT_VERSION-2026-027` |
| `decision_origin` | `human_confirmed` |
| `confirms_instance_id` | `ARTIFACT_VERSION-2026-026` |
| `approved_by_id` / `approved_by_display_name` | `Cesar` / `cesar may` |
| `decision` | `APPROVE` |
| `decision_date` / `recorded_at` | `2026-09-02T00:46:48.027088+00:00` |
| `target_set_hash` | `e10fc3a969e22cea7396286e1babb15f56637168314318af3f5ed63af57abe30` (idéntico a la propuesta) |
| `status` | `ACTIVE` |
| `provenance` | `NATIVE` |
| `payload` | idéntico a `-026` (`gate: "E2"`, `decision_ref: "E2-RPAR-20260831"`, `r_par_5: "4/4 PASS"`) |

**Eventos correspondientes en el audit trail** (`event_type = layer9_decision_recorded`,
`scope = governance_decision_v2`, `project_id = gmpai_document_validation`):

| instance_id | `entry_id` | `timestamp` | `entry_hash` | `prev_entry_hash` | `decision_origin` | `approved_by_id` | `side_effects_applied` |
|---|---|---|---|---|---|---|---|
| `-026` | `be29ee53-312f-4215-bff8-66e93f6e8ed3` | `2026-09-02T00:46:44.033688+00:00` | `sha256:2fe77ed45d2ede72d4fb2c04f194208bb60d26b834717158788dc1afea70971d` | `sha256:4df5a350f3eebd93dde6ad966549bab0aa6b1f41dc35c3e142ab3d9efaf1d1da` | `agent_proposed` | `null` | `false` |
| `-027` | `568b5e3a-c6db-4aec-af7a-466605b50d3b` | `2026-09-02T00:46:48.247021+00:00` | `sha256:f57f1a283ae31c0d00c58521071bddb4b1ec6ae5d5c73ffe0971bb7896ca449a` | `sha256:2fe77ed45d2ede72d4fb2c04f194208bb60d26b834717158788dc1afea70971d` | `human_confirmed` | `Cesar` | `false` |

Writer: `writer_identity = root@uid:0`, `writer_host = 5bfe98214b55`, `writer_pid = 1` (contenedor `factory-api`).

---

### 1.2 E3-A — base canónica CLEAN → **FIRMADO**

**Propuesta (Mission Control):**

| campo | valor real (del ledger) |
|---|---|
| `decision_instance_id` | `ARTIFACT_VERSION-2026-028` |
| `decision_family` / `decision_type` | `ARTIFACT_VERSION` / `ORIGINAL` |
| `decision` | `APPROVE` |
| `decision_origin` | `agent_proposed` |
| `proposed_by_id` | `mission_control_ui` |
| `decision_date` / `recorded_at` | `2026-09-02T00:47:02.837577+00:00` |
| `selection_mode` / `resolved_target_ids` | `EXPLICIT_LIST` / `["factory/regulatory/canonical_store_v2"]` |
| `target_set_hash` | `46758dfa79fa340eb075230831f2867e813d103ddb7ff316e553725a7de542e2` |
| `families_registry_hash` | `d5b998fac31dc00c5d17b766c8af94576a8b50daa40398d307aec7c392def45d` |
| `status` | `ACTIVE` |
| `provenance` | `NATIVE` |
| `payload` | `{gate: "E3-A", decision_ref: "E3A-CLEANBASE-20260831", evidence: "docs_plan/PAQUETE_GATES_HUMANOS_POST_RPAR_20260831.md", rw0012_claims_clean: 258, rw0012_claims_prod: 595, not_authorized: ["flip","qa40_adjudication","production"]}` |

**Confirmación humana:**

| campo | valor real (del ledger) |
|---|---|
| `decision_instance_id` | `ARTIFACT_VERSION-2026-029` |
| `decision_origin` | `human_confirmed` |
| `confirms_instance_id` | `ARTIFACT_VERSION-2026-028` |
| `approved_by_id` / `approved_by_display_name` | `Cesar` / `cesar may` |
| `decision` | `APPROVE` |
| `decision_date` / `recorded_at` | `2026-09-02T00:47:06.818667+00:00` |
| `target_set_hash` | `46758dfa79fa340eb075230831f2867e813d103ddb7ff316e553725a7de542e2` (idéntico a la propuesta) |
| `status` | `ACTIVE` |
| `provenance` | `NATIVE` |
| `payload` | idéntico a `-028` (`gate: "E3-A"`, `decision_ref: "E3A-CLEANBASE-20260831"`, `rw0012_claims_clean: 258`, `rw0012_claims_prod: 595`) |

**Eventos correspondientes en el audit trail:**

| instance_id | `entry_id` | `timestamp` | `entry_hash` | `prev_entry_hash` | `decision_origin` | `approved_by_id` | `side_effects_applied` |
|---|---|---|---|---|---|---|---|
| `-028` | `982f888c-4326-4309-a24a-9b2239e4c084` | `2026-09-02T00:47:03.235231+00:00` | `sha256:30e5ac240748e7c73529be822c56b401b104ca35b6b47255746a319312ef86fa` | `sha256:f57f1a283ae31c0d00c58521071bddb4b1ec6ae5d5c73ffe0971bb7896ca449a` | `agent_proposed` | `null` | `false` |
| `-029` | `21d377a8-781a-4e93-8cca-9682885a0919` | `2026-09-02T00:47:07.140831+00:00` | `sha256:88dfb1ec194da2760d72c8e4ec2d2e13a4e6124eec75c51f20087533ce3ab5f5` | `sha256:30e5ac240748e7c73529be822c56b401b104ca35b6b47255746a319312ef86fa` | `human_confirmed` | `Cesar` | `false` |

`21d377a8-…` (E3-A human confirm) es la **última entrada del audit trail completo** (101 097 líneas).

---

## 2. Prueba de que las firmas fueron escritas por el mecanismo gobernado (NO hand-edit)

| chequeo | resultado |
|---|---|
| `git diff HEAD -- decisions_v2.jsonl` | `@@ -253,3 +253,11 @@` — **0 líneas de contenido eliminadas / modificadas, 8 añadidas**. Ninguna línea ≤253 tocada → **append-only**. |
| Líneas añadidas | 4 pre-existentes a F0 (`-022..-025`, E1-3 + E1_ACCEPTANCE, 2026-09-01) + **4 nuevas de F9** (`-026..-029`, E2/E3-A, 2026-09-02). Todas con el esquema completo `decision_record_v1`. |
| Patrón propose→confirm | E2: `-026` (`agent_proposed`, `mission_control_ui`) → `-027` (`human_confirmed`, `confirms_instance_id=-026`, `approved_by_id=Cesar`). E3-A: `-028` → `-029` idéntico. |
| Cadena de hash del audit trail | `4df5a350…` → `2fe77ed4…` (-026) → `f57f1a28…` (-027) → `30e5ac24…` (-028) → `88dfb1ec…` (-029). **`prev_entry_hash` de cada entrada == `entry_hash` de la anterior — cadena continua, sin ruptura.** |
| Escritor de los eventos | `event_type = layer9_decision_recorded`, `writer_identity = root@uid:0` en el contenedor `factory-api` (`5bfe98214b55`) — es el servicio de decisiones de Capa 9, no una edición de fichero. |
| `factory_audit.jsonl` en `git status` | **no aparece** (untracked/gitignored) — F9 no lo tocó ni lo commitea. |
| `side_effects_applied` | `false` en las 4 entradas — la firma del gate **no** disparó flip / incorporación / producción. Coherente con `not_authorized: [flip, qa40_adjudication, production]`. |
| sha256 del ledger en disco | `e6d9335405c60680bfe11c561458a7a41fcaaee87526b24a5eb3fc9e0f0dceed` (263 líneas). El valor congelado en F4 (`1b0c7cf8…`, 259 líneas) era la baseline del **arco de reconciliación** (0 hand-edits de Claude); el delta a hoy son **+4 líneas append-only escritas por el servicio gobernado** para E2/E3-A. **No hubo hand-edit del ledger.** |

**Conclusión:** las firmas E2 y E3-A fueron escritas por el mecanismo gobernado (servicio de
decisiones de Capa 9 + audit trail encadenado). Claude Code sólo leyó.

---

## 3. CIERRE F9

```
E2_READY   = YES
E3A_READY  = YES

E2_GATE_SIGNED   = YES   (ARTIFACT_VERSION-2026-026 propose / -027 human_confirmed · approved_by_id=Cesar · status=ACTIVE)
E3A_GATE_SIGNED  = YES   (ARTIFACT_VERSION-2026-028 propose / -029 human_confirmed · approved_by_id=Cesar · status=ACTIVE)
```

### Fundamento técnico

```
E2   = F4 PASS  ∧  F5 PASS  ∧  F6(A/B/C) PASS
E3-A = F1 PASS  ∧  F2-r1 PASS  ∧  F6(A/B/C) PASS
```

- **F4 PASS** — reconciliación governance/ledger, 0 hand-edits (`decisions_v2.jsonl` sha inicio==fin en el arco), ID_COLLISION probado.
- **F5 PASS** — rebaseline `INPUT_CONFIG 3fcb3ae8…` / `GRAPH_SNAPSHOT 2fdda0e2…` / `FINDINGS(ENFORCE) 235f724a…`, counts 342/90/25, determinista.
- **F6(A/B/C) PASS** — R-PAR determinista (RUN1==RUN2), clone-drift A↔B = 0 (findings byte-idénticos `b43b548b`), `document_egress_bytes = 0`, `human_gate_intact = True`.
- **F1 PASS** (`F1_GLOBAL = PASS`) — extractor `\.?` contra ground truth humano `2f7a00dc…`, HEAD-limpio 0/8 vs con-cambio 8/8.
- **F2-r1 PASS** — stores regenerables y deterministas desde clon limpio, RW-0012 des-contaminado (258 claims limpios vs 595 en prod — coincide con el `payload` de la firma E3-A).

### Provenance real de las auditorías

| auditoría | provenance | dónde participó |
|---|---|---|
| **DEVIN** | `DEVIN` | Auditoría fase a fase F0..F6 desde clon independiente (gates relevados por Capa 9: F0..F6 = PASS) y auditoría acumulativa del arco en F7. |
| Auditorías externas posteriores (cruce F8 y revisiones cross-session) | `CROSS_SESSION_CLAUDE_CODE / READ_ONLY / CLEAN_CLONE` | Cruce Plan ↔ Claude Code ↔ Devin (F8, `VERDICT_F8 = PASS`) y verificaciones read-only sobre clon limpio. **No se denominan "Devin".** |

### Estado histórico F0 (preservado)

```
F0_HISTORICAL_VERDICT   = PARTIAL_ACCEPTED
F0_RESIDUALS_RECONCILED = YES
```

---

## 4. Carry-forward — `NON_BLOCKING_FOLLOW_UP` (abiertos, no bloquean el cierre F9)

| # | ítem | estado |
|---|---|---|
| 1 | 3 tests de hardening con fingerprint hardcodeado stale (`88f15b69`/`fdc29721`/`b5196a71` → `2fdda0e2`/`235f724a`/`693fc746`) | `NON_BLOCKING_FOLLOW_UP` — corrección mecánica pendiente de autorización de Capa 9 |
| 2 | Generador de IDs `decision_store_v2.next_instance_id` acuña `max()` del JSONL revertible → **`ARTIFACT_VERSION-2026-026..029` colisionan** con entradas *sólo-audit-trail* del 2026-08-31 (otros artefactos). Las firmas E2/E3-A del 2026-09-02 son inequívocamente distinguibles por `decision_date`, `decision_ref` (`E2-RPAR-20260831` / `E3A-CLEANBASE-20260831`), `target_set_hash` y `entry_id` de audit. | `NON_BLOCKING_FOLLOW_UP` — fix del generador pendiente de fase/decisión propia; el ledger NO se reescribe |
| 3 | `ARTIFACT_VERSION-2026-024..028` (2026-08-31, sólo-audit-trail) `NO_RECONCILIABLE` justificada | `NON_BLOCKING_FOLLOW_UP` — aceptación explícita de Capa 9 |
| 4 | Escenario D del R-PAR (RW-0003 SAT) `SKIPPED_NO_STORE` | `NON_BLOCKING_FOLLOW_UP` — capacidad nueva, no paridad; no condicionó E2/E3-A |
| 5 | Commit P4 — persistir en git las líneas de servicio de `decisions_v2.jsonl` | `NON_BLOCKING_FOLLOW_UP` — con OK explícito de Capa 9; nunca hand-edit |
| 6 | Out-of-scope pre-sesión (`remediation_directive.py` + 3 tests) | `NON_BLOCKING_FOLLOW_UP` — decisión de Capa 9 aparte; congelados como patches en `F0_diffs/` |
| 7 | D5-D2 — autor independiente (Maria Torres ≠ Cesar) | `NON_BLOCKING_FOLLOW_UP` — requerido para `FINAL_QUALIFICATION`, no para desarrollo |

---

## 5. Invariantes que SIGUEN vigentes tras el cierre F9

```
R2_READY_TO_RESUME        = NO
PILOT_EXECUTION-2026-035   = HOLD
LLM_CALLS                  = 0
PRODUCTION_ENABLEMENT      = BLOCKED
```

- Ninguna firma de F9 autoriza `flip`, `qa40_adjudication` ni `production` (`not_authorized` explícito en los 4 payloads).
- `E2_GATE_SIGNED` / `E3A_GATE_SIGNED` = flags de gate firmado; **no** habilitan producción, **no** reanudan R2, **no** ejecutan PILOT-035.

---

## REPORTE FORMATO OBLIGATORIO — F9

```
FASE            = F9 (cierre post-firma humana de Capa 9 ; verificación READ-ONLY)
PRE_COMMIT      = 2a5e222  (reconc-F9, paquete de decisión)
POST_COMMIT     = <commit del cierre>  (solo docs_plan/reconc/F9_HUMAN_DECISION.md)
WORKTREE_PRE    = decisions_v2.jsonl con +8 líneas de servicio SIN commitear (4 de E1 pre-F0 + 4 de E2/E3-A)
WORKTREE_POST   = idéntico (F9 NO tocó el ledger) + docs_plan/reconc/F9_HUMAN_DECISION.md
DIFF            = docs_plan/reconc/F9_HUMAN_DECISION.md (nuevo)
COMMANDS        = git diff HEAD -- decisions_v2.jsonl ; sha256sum decisions_v2.jsonl ;
                  grep/parse ledger (líneas -026..-029) ; grep/parse factory_audit.jsonl
                  (event_type=layer9_decision_recorded) ; wc -l audit trail — TODO READ-ONLY
TEST_RESULTS    = n/a (F9 no ejecuta código)
INPUT_HASHES    = ledger disco e6d93354… (263 líneas) ; audit trail 101097 líneas ;
                  evidencia E2 docs_plan/R_PAR_DELTA_V1_V2_20260831.md sha256 0f6045e802985d14… ;
                  evidencia E3-A docs_plan/PAQUETE_GATES_HUMANOS_POST_RPAR_20260831.md sha256 50937b46f2834c9b…
OUTPUT_HASHES   = n/a
FINGERPRINTS    = sin cambio — baseline F5 (3fcb3ae8 / 2fdda0e2 / 235f724a / 693fc746)
ARTIFACTS       = docs_plan/reconc/F9_HUMAN_DECISION.md
GOVERNANCE_EVENTS = ninguno escrito por Claude. Las firmas E2/E3-A (-026..-029) fueron escritas
                  por el servicio de decisiones de Capa 9 (audit entry_id be29ee53 / 568b5e3a /
                  982f888c / 21d377a8, cadena de hash continua) ANTES de esta verificación.
DEVIATIONS      = ninguna. Colisión de instance_id -026..-029 con entradas sólo-audit-trail del
                  2026-08-31 registrada como NON_BLOCKING_FOLLOW_UP (§4.2), distinguible por
                  decision_date / decision_ref / target_set_hash / entry_id.
EXPECTED_VS_ACTUAL:
  EXPECTED: E2 y E3-A aparecen FIRMADOS en el mecanismo gobernado ; datos reales recuperados ;
            prueba de no-hand-edit ; carry-forward mantenido ; R2/PILOT-035/producción sin habilitar.
  ACTUAL:   E2 FIRMADO (AV-2026-026/-027, approved_by_id=Cesar, ACTIVE) ; E3-A FIRMADO
            (AV-2026-028/-029, approved_by_id=Cesar, ACTIVE) ; ledger append-only (git diff
            0 borradas / 8 añadidas) ; audit trail encadenado (prev==entry_hash previo) ;
            side_effects_applied=false ; F0_HISTORICAL_VERDICT=PARTIAL_ACCEPTED preservado ;
            7 ítems NON_BLOCKING_FOLLOW_UP ; R2_READY_TO_RESUME=NO, PILOT-035=HOLD,
            LLM_CALLS=0, PRODUCTION_ENABLEMENT=BLOCKED.
PROPOSED_VERDICT = PASS (cierre F9 registrado ; firmas humanas verificadas READ-ONLY en el
                   mecanismo gobernado ; sin hand-edit)
```

---

**Claude Code detenido.** No se aprueba PILOT-035. No se reanuda R2. No se habilita producción.
