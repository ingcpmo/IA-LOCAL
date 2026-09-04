# CF-6 v1.2 · CF6-2.G + CF6-2.5 — gate de scope de la PILOT + SAMPLE_MANIFEST (sin LLM)

**Fecha:** 2026-09-04 · **Autoridad:** Capa 9 = Cesar
**Instrucción:** continuar únicamente con CF6-2.5; **no** avanzar a CF6-3.
**Sin LLM · sin red · sin tocar L2 / `human_state` / `FINDINGS_FINGERPRINT` / core / G0–G3 / G4d.**

---

## 1 · CF6-2.G — `PILOT_SCOPE_MATCH_CF6` = **NO** → GATE FAIL → STOP

`factory/regulatory/shadow/cf6_pilot_scope.py` · artefacto `CF6_2_G_PILOT_SCOPE_MATCH.json`.
Lectura del ledger `factory/layer9/decisions/decisions_v2.jsonl` (última PILOT:
`PILOT_EXECUTION-2026-035` propose / `-036` human_confirmed por Cesar).

| Chequeo (§6) | Resultado | Base |
|---|---|---|
| (a) nuevo `composer_prompt_version` (`shadow-cf6-composer-struct-v2`) | **NO** | el scope firmado de -035/-036 cubre `SHADOW_G4A..G4E` (`purpose: shadow_expert_interpretation`, composer de **prosa libre** `shadow-g4-interp-v1`). No menciona el prompt CF-6. |
| (b) ejecución CF6-2.5 (piloto de calidad) | **NO** | no está en `payload.scope` |
| (c) ejecución CF6-3 (corrida completa) | **NO** | no está en `payload.scope` |
| (d) nuevo TIPO de ejecución (emisión de estructura JSON) | **NO** | scope = interpretación experta / juicio, no composición estructurada JSON |
| `REMAINING_BUDGET_SUFFICIENT` | YES | `max_calls = 1000`, G4 consumió 481 → **519** restantes |
| `ACTIVE` | YES | -035 y -036 `status: ACTIVE`, `invalid_reason: null` |
| `NOT_SUPERSEDED` | YES | `supersedes_instance_id: null` en ambos; no hay PILOT posterior |

**`GATE_RESULT = FAIL`.** Regla §6: cualquier `NO` → **STOP. No proceder con la PILOT
existente.** No se genera B; no corre el HUMAN_QUALITY_GATE.

### Mecanismo correcto — decisión de Capa 9 (no de Claude Code)

Uno de:
1. **Ampliar el scope firmado** de `PILOT_EXECUTION-2026-035/-036` vía el canal gobernado
   (Mission Control) para autorizar EXPLÍCITAMENTE: `shadow-cf6-composer-struct-v2`,
   la ejecución CF6-2.5, la ejecución CF6-3, y el tipo de ejecución "emisión de
   estructura JSON del Composer". La evidencia de esa ampliación debe quedar
   **congelada en un tag** (lección `shadow-G4`: runtime ≠ tag auditado).
2. **Nueva PILOT_EXECUTION** con ese scope, firmada por Capa 9.

Claude Code **no** propone una nueva PILOT automáticamente (§6).

---

## 2 · CF6-2.5 — `SAMPLE_MANIFEST` (DRAFT, congelable sin LLM)

`factory/regulatory/shadow/sample_manifest.py` · artefacto
`CF6_2_5_SAMPLE_MANIFEST.json` · `status: DRAFT_PENDING_CF6_2_G_PASS`.

La muestra debe congelarse **antes de cualquier salida del piloto** (§4.1). Se deja
lista y verificada; su congelación definitiva (commit + tag) queda supeditada a que
CF6-2.G pase.

```
sample_manifest_hash = 7422faaf569430dbc8a19647a2d2b64ff6b53b5231fc4e7962b4486e3165f5a0
sections_selected    = [sec-0004, sec-0005, sec-0016, sec-0018, sec-0026, sec-0042, sec-0062]  (7)
categories_covered   = REGULATORY · FUNCTIONAL_TRACEABILITY · TECHNICAL · CROSS_DOMAIN
```

| section_id | doc | regulación | section_type | estado esperado | motivo |
|---|---|---|---|---|---|
| sec-0016 | RW-0006 | 21_CFR_11.10(d) | REGULATORY | INCONCLUSIVE | **OBLIGATORIA** — v1 fugó "rango de candidatos" |
| sec-0062 | RW-0014 | ALCOA_ORIGINAL | REGULATORY | INCONCLUSIVE | **OBLIGATORIA** — v1 elevó con "no se cumplió con" |
| sec-0018 | RW-0006 | 21_CFR_11.10(g) | CROSS_DOMAIN | INCONCLUSIVE | **OBLIGATORIA** — v1 elevó con "no estaban en conformidad" |
| sec-0005 | RW-0005 | 21_CFR_11.50_11.70 | REGULATORY | INCONCLUSIVE | 3ª REGULATORY/INCONCLUSIVE |
| sec-0004 | RW-0005 | 21_CFR_11.10(g) | CROSS_DOMAIN | INCONCLUSIVE | 2ª CROSS_DOMAIN |
| sec-0042 | RW-0012 | (trazabilidad) | FUNCTIONAL_TRACEABILITY | NOT_APPLICABLE | cobertura trazabilidad pura |
| sec-0026 | RW-0006 | ANNEX11_7 | TECHNICAL | NOT_APPLICABLE | cobertura técnica pura |

**Criterios de inclusión obligatorios (§4.1) — todos cumplidos:**

```
REGULATORY con findings INCONCLUSIVE  : 3  (≥ 2)  ✓
FUNCTIONAL_TRACEABILITY               : 1  (≥ 1)  ✓
TECHNICAL                             : 1  (≥ 1)  ✓
CROSS_DOMAIN                          : 2  (≥ 2)  ✓
OBLIGATORIAS sec-0016 / sec-0018 / sec-0062 : presentes (IDs exactos bajo la agrupación v2, sin remapeo)  ✓
inclusion_criteria_pass = true
```

La rúbrica del HUMAN_QUALITY_GATE (§4.2) se evalúa **por sección** (PASS del conjunto
solo si CADA sección pasa todos los umbrales) — pendiente de ejecución humana tras
generar B, que a su vez está bloqueada por CF6-2.G.

---

## 3 · Verificación de esta corrida

```
CF6-2.G          : PILOT_SCOPE_MATCH_CF6 = NO  → GATE FAIL → STOP (§6)
SAMPLE_MANIFEST  : DRAFT_PENDING_CF6_2_G_PASS · hash 7422faaf… · criterios §4.1 = PASS
LLM_CALLS        = 0
G4D_CALLS        = 0
L2_MUTATIONS     = 0
HUMAN_STATE_CHANGES = 0
FINDINGS_FINGERPRINT = 235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23  (L2 sha256 95a79f9b… sin cambio)
tests: test_shadow_cf6_2_5.py 8/8 · resto de la suite shadow sin regresión
tags: cf6-G1 / cf6-G1-r1 / cf6-G2-draft / cf6-G2 intactos ; NO se creó tag nuevo
```

**No se generó ninguna salida B. No se ejecutó el HUMAN_QUALITY_GATE. No se avanzó a CF6-3.**
CF6-2.5 permanece BLOQUEADO hasta que Capa 9 resuelva el scope de la PILOT (CF6-2.G).
