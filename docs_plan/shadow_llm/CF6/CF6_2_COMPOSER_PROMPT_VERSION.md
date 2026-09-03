# CF-6 v1.2 · CF6-2 — nuevo `composer_prompt_version` (sin LLM, **DRAFT_UNSIGNED**)

**Fecha:** 2026-09-03 · **Autoridad:** Capa 9 = Cesar
**Hold cf6-G1-r1:** levantado (auditoría externa = PASS).
**Alcance autorizado:** *solo redactar el prompt/contrato — sin firma* (Capa 9).
**Sin LLM · sin red · sin tocar L2 / `human_state` / `FINDINGS_FINGERPRINT` / core / G0–G3 / G4d.**

---

## 1 · Qué entrega CF6-2

| Artefacto | Estado |
|---|---|
| `factory/regulatory/shadow/prompts/composer_structured_v2.yaml` | **`status: DRAFT_UNSIGNED`** |
| `factory/regulatory/shadow/composer_prompt.py` | loader + `assert_signed()` fail-closed + `validate_structure_contract()` |
| `factory/tests/test_shadow_composer_prompt.py` | 12 tests (pasan con `.venv` del repo) |

`prompt_version = shadow-cf6-composer-struct-v2` · `supersedes = shadow-g4-interp-v1`
(COMPOSER, prosa libre — marcado PROTOTIPO en CF6-0).

---

## 2 · El cambio de contrato (CF-6 v1.2 §2, §3.1)

El Composer v1 (`experts._PROMPTS["COMPOSER"]`) pedía `narrative` — **prosa libre**.
El nuevo prompt pide **únicamente un objeto JSON**, `output: json_only`, `temperature: 0.0`:

```
section_type          ∈ REGULATORY | FUNCTIONAL_TRACEABILITY | TECHNICAL | CROSS_DOMAIN   (copiado de L2, verificado)
regulatory_state      ∈ INCONCLUSIVE | NOT_ANALYZABLE | NOT_APPLICABLE                    (copiado de L2, verificado)
evidence_observed[]   {finding_record_id (de la lista), quote (subcadena EXACTA de la cita anclada L2)}
evidence_limitation[] strings en lenguaje neutro (ausencia documental / límite de extracción)
technical_findings[]  strings (subtypes técnicos reales de la sección) o []
reviewer_action       string — acción PARA EL REVISOR; nunca correctiva / CAPA / apertura de desviación
prohibited_conclusion literal "NONE"
```

Prohibiciones dentro del prompt (system): no declarar cumplimiento / incumplimiento /
conformidad / aprobación / desviación confirmada / CAPA / liberación; no convertir
`INCONCLUSIVE` en observado/incumple; no inventar citas; no usar vocabulario interno
(`candidate ranking`, `rango de candidatos`, `rec-…`, estados de máquina).
`forbidden_keys = [narrative, assessment, conclusion, verdict, compliance, capa]`.

`section_type` y `regulatory_state` se pasan **ya determinados por L2** y el modelo los
copia; **Q-STATE-1..6** (`composer_gate.verify_qstate`) sigue siendo la garantía: si el
modelo desvía el estado, la sección cae a **modo determinista seguro**.

---

## 3 · Dos validadores complementarios

| Validador | Qué comprueba | Dónde |
|---|---|---|
| `composer_prompt.validate_structure_contract(obj)` | ESTRUCTURA de la salida del modelo: claves, enums, tipos, `prohibited_conclusion == "NONE"`, sin `forbidden_keys` | CF6-2 (este) |
| `composer_gate.verify_qstate(obj, section, l2)` | ESTADO contra L2: Q-STATE-1..6 (incl. anclaje de cita reusando G2) | CF6-1 (cf6-G1) |

Ninguno llama a un LLM.

---

## 4 · Fail-closed hasta la firma

```python
composer_prompt.is_signed()      # -> False (status DRAFT_UNSIGNED)
composer_prompt.assert_signed()  # -> PromptNotSignedError
```

`experts.run_composer` **no** se ha reconectado a este prompt: ese wiring es **CF6-3**,
y sólo después de la firma. Mientras `status: DRAFT_UNSIGNED`, ninguna corrida LLM
(CF6-2.5 / CF6-3) puede usar el prompt.

---

## 5 · Lo que falta para cerrar CF6-2 (paso gobernado, NO en esta corrida)

Según CF-6 v1.2 §6:

1. **Firma de Capa 9 (Cesar)** del `composer_prompt_version`: en el YAML,
   `status: SIGNED`, `signed_by`, `signed_at`, `signed_on`.
2. **Evidencia `propose → human_confirmed` congelada en el tag `cf6-G2`** — no basta
   con que exista en runtime / Mission Control (lección de `shadow-G4`).
3. Sólo entonces: **CF6-2.G** (`PILOT_SCOPE_MATCH_CF6`, los 4 chequeos) →
   **CF6-2.5** (`SAMPLE_MANIFEST` congelado + HUMAN_QUALITY_GATE por sección).

**No** se creó el tag `cf6-G2`. **No** se avanza a CF6-2.5 / CF6-3.

---

## 6 · Verificación (cf6-G2-draft)

```
LLM_CALLS = 0 · G4D_CALLS = 0 · L2_MUTATIONS = 0 · HUMAN_STATE_CHANGES = 0
FINDINGS_FINGERPRINT = 235f724a738ce783…  (sin mover; no se tocó L2)
tags cf6-G1 y cf6-G1-r1 intactos ; tag cf6-G2 NO creado
tests: test_shadow_composer_prompt.py 12/12 · test_shadow_composer_gate.py 23/23
```

---

## 7 · Completado de CF6-2 — few-shot profesional + registro `propose` (sin LLM)

Tras la auditoría de `cf6-G2-draft` (implementación técnica correcta, CF6-2 incompleto),
se incorporan **solo los faltantes ya definidos por el plan**. Sin cambiar contrato
estructural, Q-STATE, renderer, G4d, L2, routing ni ningún otro componente.

### 7.1 · Few-shot profesional (`21 CFR 11.10(e)`)

`composer_structured_v2.yaml` → clave `few_shot`, basada en la sección **real**
`sec-0031` (RW-0011, `21_CFR_11.10(e)`, 9 findings `REGULATORY_INCONCLUSIVE`). Demuestra
el comportamiento correcto que v1 no tenía:

| Aspecto | Qué modela el ejemplo |
|---|---|
| Estado | `regulatory_state = INCONCLUSIVE` **preservado** — no elevado a incumplimiento |
| Citas | cada `quote` de `evidence_observed` es **subcadena EXACTA** de la cita anclada L2 (`"setpoint, and any time-delay associated with the alarm."`, `"When, after a configurable time"`) |
| Límite de evidencia | lenguaje neutro (representación normalizada de G4d): *"no se ancló eco léxico … solo hay pasajes de recuperación pendientes de verificación humana"* |
| Acción | `reviewer_action` = verificación **para el revisor**, sin acción correctiva/CAPA/desviación |
| `prohibited_conclusion` | `"NONE"` |

**Demostración doble** (tests `test_few_shot_expected_output_passes_*`):
el `expected_output` del few-shot pasa `validate_structure_contract()` **y**
`composer_gate.verify_qstate()` contra la sección real `sec-0031` (Q-STATE-1..6 = PASS,
0 violaciones). `render()` inserta el bloque `EJEMPLO DE REFERENCIA` en el prompt.

### 7.2 · Registro `propose`

`docs_plan/shadow_llm/CF6/CF6_2_PROPOSE_shadow-cf6-composer-struct-v2.json`
(`composer_prompt.propose_record()`) — mitad `propose` de la evidencia gobernada
`propose → human_confirmed`:

```
prompt_version = shadow-cf6-composer-struct-v2
prompt_sha256  = <sha256 del YAML>            (recalculado al firmar)
status_at_propose = DRAFT_UNSIGNED
few_shot_present = YES ; few_shot_based_on = 21_CFR_11.10(e) (sec-0031)
structure_contract_unchanged / qstate_unchanged / renderer_unchanged /
  g4d_unchanged / routing_unchanged = true
invariants = { LLM_CALLS 0 · G4D_CALLS 0 · L2_MUTATIONS 0 · HUMAN_STATE_CHANGES 0 ·
               FINDINGS_FINGERPRINT 235f724a738ce783… }
proposed_by = Capa 8 (Claude Code)
awaiting = { action: human_confirmed · authority: Capa 9 (Cesar) }
```

### 7.3 · Firma de Capa 9 y evidencia `propose → human_confirmed` — CERRADO

Capa 9 (Cesar) aprobó explícitamente el `composer_prompt_version` con el few-shot
(mensaje de sesión, 2026-09-03). Capa 8 registró:

- **YAML firmado** (`composer_structured_v2.yaml`): `status: SIGNED`,
  `signed_by: "Capa 9 (Cesar)"`, `signed_at: "2026-09-03"`,
  `signed_on: "aprobación explícita … registro propose sha256 694000…f6c79"`.
  `composer_prompt.assert_signed()` ya **no** falla.
- **Registro `propose`** congelado:
  `CF6_2_PROPOSE_shadow-cf6-composer-struct-v2.json`
  (`status_at_propose = DRAFT_UNSIGNED`, `prompt_sha256 = 694000…f6c79`).
- **Registro `human_confirmed`** + **bundle gobernado**:
  `CF6_2_GOVERNED_EVIDENCE_shadow-cf6-composer-struct-v2.json` —
  `propose_to_human_confirmed_consistent = true`,
  `signed_prompt_sha256 = b363d2a6…c2b693`,
  `confirms_propose.proposed_prompt_sha256 = 694000…f6c79`,
  `frozen_in_tag = cf6-G2`.

Todo congelado en **un único commit + tag `cf6-G2`**. `cf6-G2-draft` intacto.

### 7.4 · Confirmación de cierre CF6-2

```
PROMPT_VERSION           = shadow-cf6-composer-struct-v2
FEW_SHOT_PRESENT         = YES   (21 CFR 11.10(e) / sec-0031, pasa contrato + Q-STATE)
PROPOSE_PRESENT          = YES
HUMAN_CONFIRMED          = YES   (Capa 9 · Cesar · 2026-09-03 · mensaje de sesión)
SIGNATURE_FROZEN_IN_TAG  = YES
TAG                      = cf6-G2
LLM_CALLS                = 0
G4D_CALLS                = 0
L2_MUTATIONS             = 0
HUMAN_STATE_CHANGES      = 0
FINDINGS_FINGERPRINT     = 235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23
```

`experts.run_composer` **no** se reconecta a este prompt: ese wiring es **CF6-3**.
**No** se ejecuta CF6-2.G ni CF6-2.5. STOP después de `cf6-G2`.
