# CF-6 v1.2 · CF6-1 — Gate de estado + render determinista + línea base v1

**Fecha:** 2026-09-03 · **Autoridad:** Capa 9 = Cesar · **Fase:** CF6-1 (sin LLM)
**Fuente de datos:** `docs_plan/shadow_llm/CF6/CF6_1_BASELINE.json` (generado por
`python -m factory.regulatory.shadow.composer_gate docs_plan/shadow_llm`).
**Sin LLM · sin red · sin mutación de L2 / `human_state` / fingerprint.**

---

## 1 · Composer real localizado (CF-6 v1.2 §7 — no crear ruta paralela)

| Componente | Archivo | Rol |
|---|---|---|
| Esqueleto determinista (G3.1) | `factory/regulatory/shadow/composer.py` | 457 findings → **66 secciones** documento×regulación; narrativa PENDING |
| **Composer LLM real (G4e)** | `factory/regulatory/shadow/experts.py::run_composer` + prompt `COMPOSER` | produjo `G4/g4e_composer.jsonl` con **prosa libre** → informe v1 |
| Render v1 | `factory/regulatory/shadow/render_narrative.py` | ensambla `INFORME_NARRATIVO_SHADOW_v1.md` |
| Verificador de anclaje G2 | `factory/regulatory/shadow/verifier.py` | reutilizado intacto por Q-STATE-6 |

CF6-1 **no** duplica el Composer: añade el gate/render/blacklist/fallback como capa
determinista nueva (`factory/regulatory/shadow/composer_gate.py`) que la ruta de
producción (CF6-3) invocará **después** de que el LLM emita solo estructura JSON.

---

## 2 · Clasificación determinista de las 66 secciones (§3, precisión 2)

`infer_section_type()` y `expected_regulatory_state()` derivan el tipo y el estado
**100% de L2** (del `primary_bucket_mix` del esqueleto y del `machine_state` de los
findings) — el modelo no interviene.

| `section_type` | nº | `regulatory_state` forzado |
|---|---|---|
| `REGULATORY` | 50 | `INCONCLUSIVE` (49) · `NOT_ANALYZABLE` (1 = RW-0009) |
| `CROSS_DOMAIN` | 11 | `INCONCLUSIVE` |
| `FUNCTIONAL_TRACEABILITY` | 3 | `NOT_APPLICABLE` |
| `TECHNICAL` | 2 | `NOT_APPLICABLE` |

`REGULATORY_STATE_COUNTS_EXPECTED = { INCONCLUSIVE: 60, NOT_APPLICABLE: 5, NOT_ANALYZABLE: 1 }`.

Todos los 457 findings tienen `machine_state ∈ {MACHINE_INCONCLUSIVE (377), MACHINE_DEVIATION_CANDIDATE (80)}`
y `human_state = UNREVIEWED`. `MACHINE_DEVIATION_CANDIDATE` **no** es desviación
confirmada (lo bloquea Q-STATE-4), así que ninguna sección regulatoria puede salir de
`INCONCLUSIVE` en esta fase.

---

## 3 · Verificador Q-STATE-1..6 (determinista, fail-closed)

`verify_qstate(structured, section, l2_by_rid)` — el contrato JSON del Composer se
rechaza si cualquier check falla o no es evaluable:

| Check | Regla implementada |
|---|---|
| Q-STATE-1 | sección con componente regulatorio + finding inconcluso en L2 → `regulatory_state` DEBE ser `INCONCLUSIVE` |
| Q-STATE-2 | `FUNCTIONAL_TRACEABILITY`/`TECHNICAL` sin componente regulatorio → DEBE ser `NOT_APPLICABLE`; `INCONCLUSIVE` aquí = RECHAZO |
| Q-STATE-3 | documento `NOT_ANALYZABLE` (RW-0009) → DEBE ser `NOT_ANALYZABLE` (domina sobre 1/2) |
| Q-STATE-4 | `human_state == UNREVIEWED` → ningún campo puede declarar confirmed/compliant/noncompliant/deviation |
| Q-STATE-5 | sin desviación humana confirmada → `reviewer_action` no puede contener acción correctiva/CAPA |
| Q-STATE-6 | cada `evidence_observed` → `finding_record_id` de la sección **y** cita que ancla en L2 (reusa `verifier._quote_anchors`) |

Además: `section_type` declarado debe coincidir con el determinista, y
`prohibited_conclusion` debe autodeclararse `NONE`.

---

## 4 · Render determinista (PUNTO DE NO-RETORNO — §2, §3.3, precisión 1)

`render_section()` es una **plantilla fija por `section_type` × `regulatory_state`**.
El único grado de libertad del modelo está en el **contenido** de los campos ya
validados (qué cita, qué limitación, qué acción); nunca en la forma ni en el estado.

- `post_qstate_llm_calls = 0` en todas las secciones — verificado por test
  (`test_render_is_byte_deterministic_and_llm_free`, `test_render_of_every_section_passes_blacklist`).
- Render **byte-reproducible** desde la misma estructura validada.
- El render nunca emite `rec-…` en prosa (Q4).

`safe_mode_section()` — fallback §3.5: declara el estado determinista, lista evidencia
L2 verbatim, `ACCIÓN PARA EL REVISOR: revisar directamente los findings L2`, y marca
`[NARRATIVA LLM NO DISPONIBLE — no superó el control]`. Blacklist-limpio en las 66.

`normalize_g4d()` — capa determinista §5: `CANDIDATE_RANKING_PROVIDED` →
"se recuperaron pasajes potencialmente relevantes que requieren revisión humana", etc.
**G4d no se re-ejecuta.**

---

## 5 · Blacklist Q1–Q5 (segunda defensa sobre el render)

| Regla | Cubre |
|---|---|
| Q1 | conclusiones de cumplimiento ("no cumple", "cumple con", "inconsistencias en el cumplimiento", "evidencia … insuficiente para satisfacer") |
| Q2 | acción correctiva / medidas correctivas / CAPA / acción preventiva |
| Q3 | vocabulario interno (`candidate ranking`, enums de experto, `auditólico`) |
| Q4 | fuga de `rec-[0-9a-f]{8,}` en prosa |
| Q5 | fuga de tokens de máquina (`MACHINE_*`, `EVIDENCE_NOT_FOUND`, `NARRATIVE_*`, `[[SHADOW`, `assessment`) |

Un hit en cualquier regla → la sección va a **modo determinista seguro**.

---

## 6 · Línea base v1 — el fallo, cuantificado (§1) · **medición cf6-G1-r1**

Medido sobre `G4/g4e_composer.jsonl` (66 secciones v1). **No** se re-ejecutó nada.
Cifras tras la corrección D3 (detectores de línea base ampliados; ver §9).

| Métrica | Valor (r1) |
|---|---|
| Secciones v1 totales | 66 |
| Secciones con **violación de estado** (elevan `INCONCLUSIVE` / afirman conformidad / proponen CAPA) | **17** — incl. `sec-0018`, `sec-0062` (nuevas en r1), `sec-0002, 0004, 0011, 0024, 0025, 0028, 0034, 0035, 0036, 0041, 0044, 0049, 0050, 0059, 0064` |
| Secciones con **fuga de vocabulario interno** (Q3) | **37** — incl. `sec-0016` (`rango de candidatos…`, nueva en r1) |
| Hits blacklist **Q1** (conclusión de cumplimiento) | 5 secciones — `sec-0002, 0024, 0028, 0044, 0050` |
| Hits blacklist **Q2** (acción correctiva/CAPA) | 6 |
| Hits blacklist **Q3** (vocabulario interno) | 46 ocurrencias / 37 secciones |
| Hits blacklist **Q4** (fuga `rec-…` en prosa) | 63 secciones · 305 ocurrencias |
| Hits blacklist **Q5** (token de máquina) | 63 |
| Secciones con marca corrupta `[[SHADOW` (doble corchete) | 63 |
| Secciones con narrativa `NARRATIVE_BLOCKED` | 3 — `sec-0001, 0015, 0029` |
| `post_qstate_llm_calls` · `G4D_CALLS` · `LLM_CALLS` · `L2_MUTATIONS` · `HUMAN_STATE_CHANGES` | 0 / 0 / 0 / 0 / 0 |

Ejemplos:
- `sec-0002` (`REGULATORY`, esperado `INCONCLUSIVE`): *"Se observaron inconsistencias en el
  cumplimiento de la regulación 21 CFR 11.10(d) … la implementación de medidas correctivas"* — Q1 + Q2.
- `sec-0018` (`REGULATORY`, esperado `INCONCLUSIVE`): *"el control de acceso y el chequeo de
  autoridad **no estaban en conformidad con las regulaciones** 21 CFR 11.10(g)"* — elevación
  de `INCONCLUSIVE` (detectada en r1).
- `sec-0062` (`REGULATORY`, esperado `INCONCLUSIVE`): *"se proporcionó la clasificación del
  candidato, pero **no se cumplió con la regulación** ALCOA_ORIGINAL … la **falta de
  conformidad** …"* — elevación de `INCONCLUSIVE` (detectada en r1).
- `sec-0016` (`REGULATORY`): *"…con un **rango de candidatos** no resueltos…"* — fuga
  conceptual del candidate-ranking interno de G4d (detectada en r1).

---

## 7 · Estado de aceptación CF-6 v1.2 tras CF6-1

| Criterio | Estado |
|---|---|
| ESTRUCTURAL — cobertura 457/457, L2 sin mutar, fingerprint sin mover, G4d no re-ejecutado | ✅ (CF6-1 no toca L2/core; esqueleto G3.1 intacto) |
| PUNTO DE NO-RETORNO — 0 llamadas LLM tras Q-STATE | ✅ implementado y testeado |
| SEGURIDAD SEMÁNTICA — Q-STATE-1..6 + blacklist + modo seguro | ✅ implementado y testeado (23/23) |
| VALOR — SAMPLE_MANIFEST + HUMAN_QUALITY_GATE por sección | ⏳ CF6-2.5 (requiere firma humana) |
| GOBERNANZA — `PILOT_SCOPE_MATCH_CF6`, firma CF6-2 congelada en tag `cf6-G2` | ⏳ CF6-2 / CF6-2.G (requiere Capa 9) |
| COMPARATIVO v1 vs v2 | ⏳ CF6-4 (tras CF6-3) |

**CF6-1 no ejecuta ninguna llamada LLM.** CF6-2 en adelante están bloqueados hasta
firma de Capa 9 y verificación de scope de la PILOT.

---

## 8 · Archivos de esta corrida (CF6-0 + CF6-1)

```
cf6-G1 (commit 50417c6)
  NUEVOS
    factory/regulatory/shadow/composer_gate.py
    factory/tests/test_shadow_composer_gate.py
    docs_plan/shadow_llm/CF6/CF6_0_PROTOTYPE_MARKER.md
    docs_plan/shadow_llm/CF6/CF6_1_BASELINE.{json,md}
  MODIFICADOS (solo marca CF6-0 — PROTOTIPO — NO PRODUCTO)
    docs_plan/shadow_llm/G4/INFORME_NARRATIVO_SHADOW_v1.md   banner + sufijo en H1
    factory/regulatory/shadow/render_narrative.py            nota en docstring
    factory/regulatory/shadow/experts.py                     nota en docstring de run_composer

cf6-G1-r1 (corrección D3 — solo detector de línea base)
  MODIFICADOS
    factory/regulatory/shadow/composer_gate.py     _V1_STATE_VIOLATION + Q3_internal_vocab ampliados;
                                                   integrity + D3_demonstration en el baseline
    factory/tests/test_shadow_composer_gate.py     +3 tests (D3 / integrity)
    docs_plan/shadow_llm/CF6/CF6_1_BASELINE.{json,md}   re-generado (r1)
```

Nota de entorno: `factory/tests/test_shadow_and_cutover.py::test_shadow_run_v2_no_effects_and_reversible`
falla en este checkout por `current_real_run_calls == None` (esperado 158) — depende de un
store persistido ausente, **no relacionado con CF6-1** (los archivos nuevos no son
importados por ese test). Resto de la suite `-k shadow`: 103 passed.

---

## 9 · CF6-1-r1 — corrección D3 (auditoría externa de cf6-G1 = PARTIAL, CRIT-* = YES)

**Alcance:** corrección mínima al **detector determinista de la línea base v1** para cerrar
el criterio de aceptación ya definido de CF6-1. **D1 y D2** aceptadas por Capa 9 como
desviaciones no críticas documentadas — sin cambio. **No** se tocó Q-STATE, arquitectura,
normalización, renderer, G4d, L2 ni `human_state`.

| Cambio | Antes | Después (r1) |
|---|---|---|
| `_V1_STATE_VIOLATION` (detector de línea base v1, **no** Q-STATE) | no capturaba "no estaban en conformidad con…" ni "no se cumplió con…" / "falta de conformidad" | añadidos `no\s+…conform\w+`, `no\s+…\bconformidad\b`, `falta de conformidad`, `no se cumpl\w+` → **`sec-0018` y `sec-0062` detectadas** |
| `Q3_internal_vocab` (blacklist) | no capturaba "rango de candidatos" | añadidos `rango de candidatos` y las formas equivalentes `clasificación/ordenamiento de(l) candidato(s)` → **`sec-0016` detectada** como fuga conceptual del candidate-ranking interno |

**Demostración** (`CF6_1_BASELINE.json` → `D3_demonstration` / `integrity`, tests
`test_d3_*`):

```
sec-0018 → v1_state_violation             = True   ✅
sec-0062 → v1_state_violation             = True   ✅
sec-0016 → v1_internal_vocab_violation    = True   ✅
D3_demonstration.PASS                     = True

l2_sha256 = 95a79f9b6276ff2a7972100764b308fa4b09f0027c6679ea831b441eb880f02c  (byte-idéntico a G0)
FINDINGS_FINGERPRINT = 235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23  (sin mover)
human_states_present = ["UNREVIEWED"]
G4D_CALLS = 0 · LLM_CALLS = 0 · L2_MUTATIONS = 0 · HUMAN_STATE_CHANGES = 0 · post_qstate_llm_calls = 0
```

**Efecto de la ampliación** (todo son verdaderos positivos reales en la prosa v1):
violaciones de estado 9 → **17**; secciones con fuga de vocabulario interno 13 → **37**.
El `tag cf6-G1` **no se movió ni se borró**; la corrección se congela en `cf6-G1-r1`.
