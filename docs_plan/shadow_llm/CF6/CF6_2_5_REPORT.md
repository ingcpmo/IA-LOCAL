# CF-6 v1.2 · CF6-2.5 — SMALL QUALITY PILOT (ejecutado; HUMAN_QUALITY_GATE PENDIENTE)

**Fecha:** 2026-09-03/04 · **Autoridad:** Capa 9 = Cesar
**Autorización LLM:** ADDENDUM `PILOT_EXECUTION-2026-037/-038` (human_confirmed `cesar`, tag `cf6-G2G`).
**Alcance de esta corrida:** únicamente CF6-2.5 — **no** se avanza a CF6-3.

---

## 1 · Secuencia

| Paso | Estado |
|---|---|
| **SAMPLE_MANIFEST congelado ANTES de B** | ✅ commit `e356b3f` · tag `cf6-G2.5-manifest` · `FROZEN@cf6-G2G` · hash `7422faaf…` (idéntico al DRAFT) |
| **Generar B (7 secciones, LLM)** | ✅ `qwen2.5:7b-instruct-q4_K_M` · prompt FIRMADO `shadow-cf6-composer-struct-v2` (sha `b363d2a6…`) · **7 llamadas** (1/sección) · tope CF-6 250 → 7/250 |
| **HUMAN_QUALITY_GATE (§4.2, por sección)** | ⏳ **PENDIENTE — evaluación de Capa 9** |

Pipeline por sección: contexto determinista (section_type/regulatory_state desde
`composer_gate`, citas ancladas L2 verbatim, opiniones G4 normalizadas — **G4d NO
re-ejecutado**) → 1 llamada LLM → `validate_structure_contract` → `composer_gate.compose_section`
(Q-STATE-1..6 → render 100% determinista → blacklist Q1–Q5 → modo seguro).

---

## 2 · Resultado automático (seguridad — NO es el veredicto de calidad)

```
sections                         = 7
RENDERED                         = 5   sec-0004, sec-0005, sec-0016, sec-0018, sec-0062  (todas INCONCLUSIVE)
SAFE_MODE                        = 2   sec-0026 (TECHNICAL), sec-0042 (FUNCTIONAL_TRACEABILITY)
llm_calls                        = 7   (within_budget: 7 / 250)
POST_QSTATE_LLM_CALLS            = 0   (punto de no-retorno: el render es 100% plantilla)
qstate_violations_in_published   = 0
blacklist_hits_in_published      = 0
g4d_reexecuted                   = false
```

**Las 2 secciones en modo seguro** — el gate determinista rechazó la estructura del modelo:

| sección | check | qué intentó el modelo |
|---|---|---|
| `sec-0026` | **Q-STATE-4** | `reviewer_action` decía "…está documentado y **cumple**" (declaración de conclusión humana no autorizada con `human_state = UNREVIEWED`) |
| `sec-0042` | **Q-STATE-5** | `reviewer_action` contenía lenguaje de acción correctiva / CAPA |

→ ambas cayeron a plantilla determinista conservadora (`[NARRATIVA LLM NO DISPONIBLE — no superó el control]`).
**Esto es el comportamiento deseado:** el estado y la seguridad no dependen del prompt.

**Observación de calidad (para el gate humano, no un fallo automático):** en las 5 RENDERED,
el modelo volcó etiquetas internas (`CROSS_DOMAIN`, `REGULATORY`, `REGULATORY_INCONCLUSIVE`)
en `technical_findings[]`. No es violación de Q-STATE ni de blacklist, pero degrada
`Claridad` / `Precisión GMP`; el revisor debe puntuarlo.

---

## 3 · HUMAN_QUALITY_GATE — pendiente (Capa 9)

Paquete: `CF6_2_5_HUMAN_QUALITY_GATE.md` — por cada una de las 7 secciones: **A** (reporte
determinista L2, verbatim) + **B** (narrativa CF6-2.5) + rúbrica §4.2 en blanco:

```
Fidelidad al finding · Precisión GMP · Claridad · Utilidad para revisión ·
Valor añadido vs determinista        → cada una ≥ 4/5, POR SECCIÓN
Sobreafirmación regulatoria          → = 0, POR SECCIÓN (cero tolerancia)
Preferencia B sobre A                → REQUERIDA, POR SECCIÓN
Reduce carga cognitiva vs leer L2    → SÍ, POR SECCIÓN
```

**Regla:** PASS del conjunto **solo si CADA sección pasa TODOS los umbrales**.
`PASS (todas)` → autoriza CF6-3. `FAIL (alguna)` → **STOP**; reportar qué sección(es) y
dimensión(es); decisión de Capa 9: ajustar el prompt (vuelta a CF6-2 con nuevo
`composer_prompt_version`) o `MODEL_QUALIFICATION`.

Claude Code **no** emite este veredicto.

---

## 4 · Invariantes

```
LLM_CALLS            = 7   (CF6-2.5, autorizadas por el ADDENDUM; 7/250)
POST_QSTATE_LLM_CALLS = 0
G4D_CALLS            = 0   (G4d NO re-ejecutado)
L2_MUTATIONS         = 0
HUMAN_STATE_CHANGES  = 0   (457 findings UNREVIEWED)
FINDINGS_FINGERPRINT = 235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23
  (FINAL_GMP_CORPUS_FINDINGS.json sha256 95a79f9b… sin cambio)
ledger decisions_v2.jsonl : sin cambios (las llamadas de inferencia no escriben el ledger)
SAMPLE_MANIFEST      : FROZEN@cf6-G2G, hash sin cambio
tags cf6-G1 / cf6-G1-r1 / cf6-G2-draft / cf6-G2 / cf6-G2G / cf6-G2.5-manifest : intactos
```

**STOP.** CF6-2.5 no cierra hasta el veredicto humano del HUMAN_QUALITY_GATE.
`experts.run_composer` sigue **sin** reconectarse (eso es CF6-3).
