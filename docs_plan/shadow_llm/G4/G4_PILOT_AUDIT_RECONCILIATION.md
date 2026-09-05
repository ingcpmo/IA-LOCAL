# SHADOW · G4.PILOT — RECONCILIACIÓN POST-AUDITORÍA EXTERNA

**Corrección MÍNIMA.** La auditoría externa de `shadow-G4` (`8fceed5`) falló **exclusivamente en
G4.PILOT**. G4a–G4e NO se re-ejecutan · 0 llamadas LLM nuevas · G5 NO se ejecuta · el tag
`shadow-G4` NO se mueve ni se reemplaza.

---

## 1 · Causa del FAIL de auditoría

`shadow-G4` se creó en el worktree `shadow/llm-interpretation-layer`. La copia **git-trackeada**
de `factory/layer9/decisions/decisions_v2.jsonl` en ese árbol estaba congelada en el commit
`4ae446e` (**255 líneas**, sha `42fa47f712e95732aac62fd4b53098e481ea31d554e67c1d38564535d4aaee92`)
— versión que **no contiene** `PILOT_EXECUTION-2026-035` ni `-036`.

La evidencia de gobernanza **sí existía** en el **ledger autoritativo vivo**
(`/home/cmay/ivr-ia/factory/layer9/decisions/decisions_v2.jsonl`, el fichero que el servicio
`factory-api` bind-montea y al que escribe), pero ese estado **nunca se llevó a la rama del
arco shadow**. Resultado: `git show shadow-G4:factory/layer9/decisions/decisions_v2.jsonl` muestra
un ledger antiguo sin la autorización → Devin no pudo auditar `-035`/`-036` desde el tag.

**El fix es documental/de congelado, no de ejecución.** La autorización era real y previa a la
1ª llamada LLM (§4); lo único que faltaba era hacerla auditable desde Git.

---

## 2 · Ledger autoritativo vivo — verificación (solo lectura)

`/home/cmay/ivr-ia/factory/layer9/decisions/decisions_v2.jsonl`

```
SHA256   d7a15efa461495cbd818110da6e32afa8ae86a12d41a9f57895db0542ea89f87
LÍNEAS   266
```

**Append-only demostrado:** las primeras **255** líneas del ledger vivo son **byte-idénticas** a
la copia git-trackeada del worktree (`head -255 vivo` → sha `42fa47f712e95732aac62fd4b53098e481ea31d554e67c1d38564535d4aaee92`,
== la trackeada). El ledger vivo = `committed(255) + 11 registros anexados por el servicio`.
`git diff` de este commit sobre el fichero: **11 inserciones, 0 borrados, 0 líneas modificadas**
(`git diff --numstat` = `11  0`).

### Los 11 registros delta (L256–L266) — todos `decision_record_v1` escritos por el servicio

| L | familia / instancia | origin | proposed_by / approved_by | confirms | fecha (UTC) |
|---|---|---|---|---|---|
| 256 | `ARTIFACT_VERSION-2026-022` | agent_proposed | `mission_control_ui` / — | — | 2026-09-01T15:57:50 |
| 257 | `ARTIFACT_VERSION-2026-023` | human_confirmed | — / `Cesar` | `-022` | 2026-09-01T15:57:54 |
| 258 | `ARTIFACT_VERSION-2026-024` | agent_proposed | `mission_control_ui` / — | — | 2026-09-01T16:00:52 |
| 259 | `ARTIFACT_VERSION-2026-025` | human_confirmed | — / `Cesar` | `-024` | 2026-09-01T16:00:56 |
| 260 | `ARTIFACT_VERSION-2026-026` | agent_proposed | `mission_control_ui` / — | — | 2026-09-02T00:46:43 |
| 261 | `ARTIFACT_VERSION-2026-027` | human_confirmed | — / `Cesar` | `-026` | 2026-09-02T00:46:48 |
| 262 | `ARTIFACT_VERSION-2026-028` | agent_proposed | `mission_control_ui` / — | — | 2026-09-02T00:47:02 |
| 263 | `ARTIFACT_VERSION-2026-029` | human_confirmed | — / `Cesar` | `-028` | 2026-09-02T00:47:06 |
| 264 | `ARTIFACT_VERSION-2026-030` | agent_proposed | `mission_control_ui` / — | — | 2026-09-03T00:59:42 |
| **265** | **`PILOT_EXECUTION-2026-035`** | **agent_proposed** | **`mission_control_ui`** / — | — | **2026-09-03T01:13:50.404334** |
| **266** | **`PILOT_EXECUTION-2026-036`** | **human_confirmed** | — / **`Cesar`** (`cesar may`) | **`PILOT_EXECUTION-2026-035`** | **2026-09-03T01:26:05.789596** |

L256–L264 son firmas de la reconciliación F9 (E1/E2/E3-A → `ARTIFACT_VERSION`) + una propuesta
`ARTIFACT_VERSION-2026-030` posterior, **ya aceptadas por Capa 9** — parte del mismo ledger
append-only autoritativo. **No son ediciones manuales:** todas llevan `schema_version:
decision_record_v1`, `target_set_hash`, `families_registry_hash`, `decision_origin` y el par
propose/confirm del servicio `governance_service`. Ninguna línea previa (1–255) cambió.

---

## 3 · Registros `-035` / `-036` — contenido exacto

### `PILOT_EXECUTION-2026-035` — `agent_proposed`

```
schema_version         decision_record_v1
decision_family        PILOT_EXECUTION            decision_type   ORIGINAL
decision_origin        agent_proposed            proposed_by_id  mission_control_ui
approved_by_id         null                      confirms_instance_id  null
status                 ACTIVE                    supersedes_instance_id  null   invalid_reason  null
decision_date          2026-09-03T01:13:50.404334+00:00
resolved_target_ids    [RW-0005, RW-0006, RW-0011, RW-0012, RW-0014]
target_set_hash        95264ab9b4fab88952900d72c8205445599bc01a76487c1128979e204ef61a85
families_registry_hash d5b998fac31dc00c5d17b766c8af94576a8b50daa40398d307aec7c392def45d
payload.max_calls           1000
payload.authorizes_corpus   false
payload.authorizes_baseline false
payload.scope               23 unidades (document × agente shadow_g4a..g4e), 5 documentos
```

### `PILOT_EXECUTION-2026-036` — `human_confirmed`

```
decision_family        PILOT_EXECUTION            decision_type   ORIGINAL
decision_origin        human_confirmed           proposed_by_id  null
approved_by_id         Cesar                     approved_by_display_name  cesar may
confirms_instance_id   PILOT_EXECUTION-2026-035
status                 ACTIVE                    supersedes_instance_id  null   invalid_reason  null
decision_date          2026-09-03T01:26:05.789596+00:00
resolved_target_ids    [RW-0005, RW-0006, RW-0011, RW-0012, RW-0014]
target_set_hash        95264ab9b4fab88952900d72c8205445599bc01a76487c1128979e204ef61a85   (== -035)
payload.max_calls           1000
```

**Relación `propose → human_confirmed`:** `-036.confirms_instance_id == "PILOT_EXECUTION-2026-035"`;
mismo `target_set_hash` (`95264ab9…`); `approved_by_id = "Cesar"` (identidad humana real,
resuelta por `require_identity` desde `X-Identity-Key`, no viaja en el body). Ambos `status:
ACTIVE`, ninguno superseded, `invalid_reason: null`.

---

## 4 · Timestamps — confirmación ANTES de la 1ª llamada LLM

```
propose  PILOT_EXECUTION-2026-035   2026-09-03T01:13:50.404334Z
confirm  PILOT_EXECUTION-2026-036   2026-09-03T01:26:05.789596Z
1ª llamada LLM real (G4 driver)    ~2026-09-03T01:34Z   (primer _progress.json: stage G4a, done 2, ts 2026-09-03T01:35:47Z)
```

`confirm (01:26:05Z)  <  1ª llamada LLM (~01:34Z)` → **autorización efectiva previa a cualquier
llamada al modelo.** El `agent_proposed` (01:13:50Z) también es previo.

---

## 5 · Reconciliación del documento histórico `03_PROPUESTA_PILOT_EXECUTION_035.md`

`docs_plan/REVISION_CIERRE_H1_H10_Y_INSTRUCCIONES_20260901/03_PROPUESTA_PILOT_EXECUTION_035.md`
(no se reescribe ni se borra).

| Pregunta del auditor | Evidencia / conclusión |
|---|---|
| ¿Era solo una propuesta/draft histórica no materializada? | **Sí.** Su cabecera dice literalmente *"Estado: PROPUESTA. `agent_proposed`. **NO ejecutada. 0 llamadas consumidas.**"* Nunca se envió al `governance_service`: hasta `2026-09-03T01:13:50Z` el ledger vivo tenía `PILOT_EXECUTION` **solo hasta `-034`**. |
| ¿Por qué `hard_call_cap ≤ 20`? | Porque es un **diagnóstico R2 acotado** de OTRO problema: aislar si el fallo de recall del 7B está en el *paso A* o el *paso B* del juicio V2, sobre una **sub-muestra dirigida de 3 positivos del fixture 7P+2N (P1/P2/P5) + N1**. Su propia tabla estima *"3 unidades × (1–2 subcriterios + Critic) ≈ 8–12 llamadas; `stop_reason` forzado a las 20"*. Es un experimento de 3 unidades, no una corrida de interpretación de 415 findings. |
| ¿Por qué la instancia materializada `-035` tiene `max_calls = 1000`? | Porque **es otra instancia, con otro propósito y otro alcance**: interpretación experta SHADOW de G4 (5 agentes: Technical/Cross-domain/Functional-Traceability/Regulatory-triage/Composer) sobre `RW-0005/0006/0011/0012/0014` — 17 + 15 + 98 + 285 findings + 66 secciones. Dimensionada para las **481** llamadas reales que consumió G4 (`481 / 1000`). Coincide el **número** de instancia porque `decision_store_v2.next_instance_id` acuña `max()` del JSONL (que estaba en `-034`), no del propósito; el mismo defecto de generación de IDs ya documentado en la reconciliación F0-F9 (§13.2 de `FINAL_HUMAN_REVIEW_POST_RECONCILIATION.md`). |
| ¿El documento histórico es el registro autoritativo de ejecución? | **No.** Es un borrador de propuesta nunca materializado. El **registro autoritativo** es el par de eventos append-only del ledger `-035` (`agent_proposed`) + `-036` (`human_confirmed`, `approved_by_id=Cesar`), §3. |
| Autoridad efectiva | **El par `-035`/`-036` del ledger canónico `factory/layer9/decisions/decisions_v2.jsonl`.** El `.md` histórico queda como contexto de diseño de un experimento R2 distinto, sin efecto de gobernanza. |

---

## 6 · Congelado de la evidencia en Git (este commit)

Este commit correctivo `fix(shadow): freeze G4 pilot governance evidence` (tag `shadow-G4.1`):

- **Actualiza `factory/layer9/decisions/decisions_v2.jsonl`** del worktree para que refleje el
  estado autoritativo append-only del servicio (255 → 266 líneas; **+11 inserciones, 0 borrados**;
  copia verbatim del fichero vivo, **sin editar ninguna línea manualmente**). sha del ledger
  congelado: `d7a15efa461495cbd818110da6e32afa8ae86a12d41a9f57895db0542ea89f87`.
- **Añade este documento** `docs_plan/shadow_llm/G4/G4_PILOT_AUDIT_RECONCILIATION.md`.
- **No toca** el commit `8fceed5` ni el tag `shadow-G4` (sigue en
  `8fceed59f64a7fe66078da4e1213f8519a758137`).

---

## 7 · Confirmaciones — G4 no se re-ejecutó · L2/human_state intactos

| | |
|---|---|
| **G4 re-ejecutado** | **NO.** 0 llamadas LLM nuevas. Los artefactos `docs_plan/shadow_llm/G4/g4{a..e}.jsonl`, `g4_call_log.json`, `G4_SUMMARY.json` no se regeneran ni se tocan. |
| **`LLM_CALLS`** | **481** (sin cambio) — `g4_call_log.json` sha `242df99f30b19752de9621c9a1967d3663147451e845f24906ef6cb209110c3f`, `G4_SUMMARY.json.llm_calls = 481`. Presupuesto `481 / 1000`. |
| **`L2_MUTATIONS`** | **0** — `docs_plan/shadow_llm/FINAL_GMP_CORPUS_FINDINGS.json` sha `95a79f9b6276ff2a7972100764b308fa4b09f0027c6679ea831b441eb880f02c` (== baseline, sin cambio). |
| **`HUMAN_STATE_CHANGES`** | **0** — `human_state` de los 457 findings L2 = `UNREVIEWED`. |
| **`related_finding_ids`** | sin cambios. |
| **`FINDINGS_FINGERPRINT`** | `235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23` (sin mover). |
| **Fase G5** | **NO ejecutada.** |

---

*Corrección mínima post-auditoría de G4.PILOT. La evidencia de gobernanza (`-035`/`-036`) era
real y previa a la ejecución; este commit sólo la hace auditable desde Git y reconcilia el
documento histórico. `shadow-G4` intacto. Sin re-ejecución, sin G5, sin edición manual del
ledger.*
