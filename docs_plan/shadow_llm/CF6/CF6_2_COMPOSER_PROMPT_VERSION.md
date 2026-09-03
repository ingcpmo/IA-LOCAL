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

## 6 · Verificación de esta corrida

```
LLM_CALLS = 0 · G4D_CALLS = 0 · L2_MUTATIONS = 0 · HUMAN_STATE_CHANGES = 0
FINDINGS_FINGERPRINT = 235f724a738ce783…  (sin mover; no se tocó L2)
tags cf6-G1 y cf6-G1-r1 intactos ; tag cf6-G2 NO creado
tests: test_shadow_composer_prompt.py 12/12 · test_shadow_composer_gate.py 23/23
```
