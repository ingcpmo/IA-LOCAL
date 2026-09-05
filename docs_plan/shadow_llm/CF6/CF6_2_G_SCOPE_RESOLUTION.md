# CF-6 v1.2 · CF6-2.G — resolución de `PILOT_SCOPE_MATCH_CF6 = NO`

**Fecha:** 2026-09-04 · **Autoridad:** Capa 9 = Cesar
**Instrucción:** preparar únicamente la propuesta gobernada; STOP tras la propuesta.
**Sin LLM · sin red · sin tocar L2 / `human_state` / `FINDINGS_FINGERPRINT` / el ledger canónico / el SAMPLE_MANIFEST.**

---

## 1 · ¿El mecanismo oficial permite ampliar la PILOT vigente conservando su trazabilidad?

### `SCOPE_EXTENSION_SUPPORTED = YES` — vía `decision_type = ADDENDUM`

| Evidencia | Detalle |
|---|---|
| `decision_store_v2.COVERING_TYPES` | `{ORIGINAL, CORRECTION, ADDENDUM, SUPERSESSION}` — el `decision_scope_resolver` **une** los `target_ids` de todos los registros `human_confirmed` ACTIVE de esos tipos |
| `decision_store_v2.AMENDING_TYPES` | `{CORRECTION, SUPERSESSION, REVOCATION}` — **`ADDENDUM` NO está** → no supersede |
| Invariante **I-7** | "ADDENDUM amplía, no supersede — no puede referenciar `supersedes_*`" + `amendment_sequence >= 1` |
| Familia `PILOT_EXECUTION` | `requires_human_confirmation: true`, `selection_modes: [EXPLICIT_LIST]`, sin lista blanca de `decision_type` |
| Resolver | "union de los que otorgan menos la union de los que revocan … la que domina sobre un ADDENDUM posterior del mismo id" |

**Trazabilidad conservada:** `PILOT_EXECUTION-2026-035` (propose) y `-036` (human_confirmed · Cesar)
**permanecen `ACTIVE` y cubriendo**. El ADDENDUM es una instancia nueva de la MISMA familia que
**suma** el scope de CF-6 y referencia `-035/-036` en su `reason`; no los supersede ni los invalida.

---

## 2 · `propose` de ampliación de scope — PREPARADO (no registrado)

Artefacto: `CF6_2_G_SCOPE_ADDENDUM_PROPOSE.json` (`cf6_scope_addendum.package()`).

```
family                 = PILOT_EXECUTION
decision               = APPROVE
decision_type          = ADDENDUM
amendment_sequence     = 1
selection_mode         = EXPLICIT_LIST
supersedes_instance_id = null                     (I-7)
decision_origin        = agent_proposed
proposed_by_id         = Capa 8 (Claude Code)
target_ids             = [RW-0005, RW-0006, RW-0009, RW-0011, RW-0012, RW-0014]
written_to_ledger      = NO   → se somete por el canal gobernado (Mission Control), igual que -035
```

### `payload` — autoriza EXPLÍCITAMENTE los 4 ítems que CF6-2.G marcó `NO`

```
composer_prompt_version = shadow-cf6-composer-struct-v2      (firmado por Capa 9, tag cf6-G2)
execution_type          = structured_json_composer
authorizes              = ["CF6-2.5 SMALL QUALITY PILOT", "CF6-3 corrida completa post-gate"]
extends_instances       = [PILOT_EXECUTION-2026-035, PILOT_EXECUTION-2026-036]
scope                   = 10 unidades {document_id, agent_id: shadow_composer_expert,
                          requirement_id: SHADOW_CF6_COMPOSER, purpose: structured_json_composer,
                          execution_phase: CF6-2.5 | CF6-3, composer_prompt_version}
max_calls               = 250   (tope duro CF-6 aditivo; el tope de 1000 de -035 sigue acotando
                                 el total de la familia — 481 usadas por G4)
sample_manifest_hash    = 7422faaf569430dbc8a19647a2d2b64ff6b53b5231fc4e7962b4486e3165f5a0
authorizes_corpus       = false ; authorizes_baseline = false
not_authorized          = [CORPUS_AUTHORIZATION, D4, FORMAL_BASELINE_READY, flip/adjudication/production]
```

### Llamada equivalente (para el canal gobernado)

```python
factory.services.governance_service.propose(
    family="PILOT_EXECUTION", target_ids=[...6 RW...], decision="APPROVE",
    decision_type="ADDENDUM", selection_mode="EXPLICIT_LIST", amendment_sequence=1,
    proposed_by_id="<actor>", reason=<reason>, payload=<payload>)
```

### Validación de forma (dry-run contra `decision_store_v2`, almacén SCRATCH)

```
build_record OK · I-7 (ADDENDUM sin supersede, amendment_sequence>=1) OK · dry_run PASS = true
ledger canónico factory/layer9/decisions/decisions_v2.jsonl : NO escrito
```

---

## 3 · STOP — pendiente de aprobación de Capa 9

**No se registró `human_confirmed`.** Para cerrar CF6-2.G, Capa 9 (Cesar):

1. Somete el `propose` del ADDENDUM por el canal gobernado (Mission Control).
2. Lo confirma (`human_confirmed`) → `-035/-036` siguen ACTIVE; el ADDENDUM añade el scope CF-6.
3. Re-ejecutar CF6-2.G: con el ADDENDUM `human_confirmed`, `PILOT_SCOPE_MATCH_CF6` debe pasar a `YES`.
4. Recién entonces: **CF6-2.5** (congelar el SAMPLE_MANIFEST — hoy DRAFT — y generar B por sección → HUMAN_QUALITY_GATE).

**No se ejecuta CF6-2.5 ni CF6-3.** El `SAMPLE_MANIFEST` se conserva `DRAFT_PENDING_CF6_2_G_PASS`, sin cambios.

---

## 4 · Verificación de esta corrida

```
SCOPE_EXTENSION_SUPPORTED = YES  (mecanismo: ADDENDUM en PILOT_EXECUTION)
PROPOSE preparado          = YES  (agent_proposed, written_to_ledger = NO)
HUMAN_CONFIRMED             = NO   (detenido para Capa 9)
LLM_CALLS                   = 0
G4D_CALLS                   = 0
L2_MUTATIONS                = 0
HUMAN_STATE_CHANGES         = 0
FINDINGS_FINGERPRINT        = 235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23
ledger decisions_v2.jsonl   : sin cambios   ·   SAMPLE_MANIFEST : sin cambios (DRAFT)
tests: test_shadow_cf6_scope_addendum.py 5/5 · suite shadow sin regresión
tags cf6-G1 / cf6-G1-r1 / cf6-G2-draft / cf6-G2 intactos · sin tag nuevo
```
