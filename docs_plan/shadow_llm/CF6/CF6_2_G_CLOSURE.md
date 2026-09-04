# CF-6 v1.2 · CF6-2.G — CIERRE. `PILOT_SCOPE_MATCH_CF6 = YES`

**Fecha:** 2026-09-04 · **Autoridad:** Capa 9 = Cesar (`approved_by_id = cesar`)
**Canal:** `factory.services.governance_service` (API gobernada) — **sin edición manual** de
`factory/layer9/decisions/decisions_v2.jsonl`.
**Sin LLM · sin red · sin tocar L2 / `human_state` / `FINDINGS_FINGERPRINT` / el SAMPLE_MANIFEST.**

---

## 1 · `propose → human_confirmed` del ADDENDUM (registrado en el ledger)

| | instancia | tipo | origen | firma |
|---|---|---|---|---|
| propose | `PILOT_EXECUTION-2026-037` | `ADDENDUM` (`amendment_sequence=1`, `supersedes_instance_id=null`) | `agent_proposed` (`cf6_scope_addendum_agent`) | — |
| human_confirmed | `PILOT_EXECUTION-2026-038` | `ADDENDUM` | `human_confirmed` | `approved_by_id = cesar` · `approved_by_display_name = "Capa 9 (Cesar)"` · `status = ACTIVE` |

- `PILOT_EXECUTION-2026-038.confirms_instance_id = PILOT_EXECUTION-2026-037`.
- `supersedes_instance_id = null` en ambos (I-7: ADDENDUM amplía, no supersede).
- Ledger **append-only**: las 266 líneas previas quedan byte-idénticas
  (sha256 `d7a15efa461495cbd818110da6e32afa8ae86a12d41a9f57895db0542ea89f87`); solo se
  anexaron 2 registros. 266 → 268 líneas.

### `payload` del ADDENDUM (autoriza EXPLÍCITAMENTE los 4 ítems)

```
composer_prompt_version = shadow-cf6-composer-struct-v2      (firmado por Capa 9, tag cf6-G2)
execution_type          = structured_json_composer
authorizes              = ["CF6-2.5 SMALL QUALITY PILOT", "CF6-3 corrida completa post-gate"]
extends_instances       = [PILOT_EXECUTION-2026-035, PILOT_EXECUTION-2026-036]
scope                   = 10 unidades (shadow_composer_expert / SHADOW_CF6_COMPOSER / phase CF6-2.5|CF6-3)
max_calls               = 250   (asignación CF-6 aditiva; el tope de 1000 de -035 sigue acotando la familia)
sample_manifest_hash    = 7422faaf569430dbc8a19647a2d2b64ff6b53b5231fc4e7962b4486e3165f5a0
authorizes_corpus/baseline = false ; not_authorized = [CORPUS_AUTHORIZATION, D4, FORMAL_BASELINE_READY, flip/adjudicación/producción]
```

### Trazabilidad conservada

`PILOT_EXECUTION-2026-035` y `-036` siguen `status = ACTIVE`, `superseded_by = null`,
`invalid_reason = null`. El ADDENDUM **suma** el scope de CF-6 a la familia; el
`decision_scope_resolver` une los `target_ids` de los `COVERING_TYPES` `human_confirmed`
ACTIVE (`ORIGINAL` -035/-036 + `ADDENDUM` -037/-038).

---

## 2 · CF6-2.G re-ejecutado — `GATE_RESULT = PASS`

`cf6_pilot_scope.evaluate()` sobre el ledger actualizado (artefacto `CF6_2_G_CLOSURE.json`):

```
pilot_instance              = PILOT_EXECUTION-2026-038  (ADDENDUM, human_confirmed)
PILOT_SCOPE_MATCH_CF6       = YES
  a_composer_prompt_version         = YES
  b_cf6_2_5                         = YES
  c_cf6_3                           = YES
  d_execution_type_json_structure  = YES
REMAINING_BUDGET_SUFFICIENT = YES   (remaining_calls = 250 — asignación CF-6 del ADDENDUM, 0 usadas)
ACTIVE                      = YES
NOT_SUPERSEDED              = YES
GATE_RESULT                 = PASS  → "proceder a CF6-2.5"
```

### Cambios menores de correctitud en `cf6_pilot_scope.py` (no aflojan el gate)

Entre el `FAIL` (`464b0c8`) y este `PASS`, dos ajustes de correctitud para el caso
**ADDENDUM**, no de umbral:

1. `_SCOPE_TOKENS["d_..."]` reconoce ahora la cadena canónica `structured_json_composer`
   (es exactamente el `execution_type` que el chequeo (d) debe detectar).
2. El presupuesto de un ADDENDUM es su asignación propia (aditiva): 0 llamadas CF-6
   hechas → `remaining = max_calls`, acotado por el remanente del tope del padre. Un
   `250 − 481 < 0` habría sido un falso negativo (las 481 se consumieron contra `-035`).

Verificado: `evaluate()` sobre el ledger **sin** el ADDENDUM sigue devolviendo
`PILOT_SCOPE_MATCH_CF6 = NO` / `GATE_RESULT = FAIL` (los 4 chequeos `NO`).

---

## 3 · Invariantes

```
LLM_CALLS            = 0
G4D_CALLS            = 0
L2_MUTATIONS         = 0
HUMAN_STATE_CHANGES  = 0   (los 457 findings siguen UNREVIEWED)
FINDINGS_FINGERPRINT = 235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23
  (L2 FINAL_GMP_CORPUS_FINDINGS.json sha256 95a79f9b… sin cambio)
SAMPLE_MANIFEST      : sin cambios (DRAFT_PENDING_CF6_2_G_PASS)
ledger               : append-only (+2 registros vía governance_service; 266 líneas previas intactas)
tests                : test_shadow_cf6_2_5.py + test_shadow_cf6_scope_addendum.py verdes ; suite shadow sin regresión nueva
```

---

## 4 · STOP tras el tag de cierre

CF6-2.G **cerrado** con `GATE_RESULT = PASS`. Se congela `propose → human_confirmed` +
resultado del gate en el commit y tag de cierre de CF6-2.G.

Tags conservados intactos: `cf6-G1`, `cf6-G1-r1`, `cf6-G2-draft`, `cf6-G2`, y el commit
`c35d163` (propuesta técnica del ADDENDUM).

**No se ejecuta CF6-2.5 ni CF6-3.** El `SAMPLE_MANIFEST` sigue `DRAFT`; su congelación
definitiva y la generación de B por sección + HUMAN_QUALITY_GATE son CF6-2.5, fuera de
esta corrida.
