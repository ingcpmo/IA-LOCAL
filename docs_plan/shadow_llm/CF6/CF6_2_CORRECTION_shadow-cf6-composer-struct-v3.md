# CF-6 v1.2 · CF6-2 (corrección) — `shadow-cf6-composer-struct-v3` (DRAFT_UNSIGNED)

**Fecha:** 2026-09-04 · **Autoridad:** Capa 9 = Cesar · **Corrida:** sin LLM.
**Disparador:** **diagnóstico técnico de Capa 8 (Claude Code)** del CF6-2.5 con
`shadow-cf6-composer-struct-v2` — 7/7 secciones del SAMPLE_MANIFEST con defectos
documentados frente a los umbrales §4.2 (`sec-0062` con sobreafirmación regulatoria
en `reviewer_action`). Detalle: `CF6_2_5_HUMAN_QUALITY_GATE_VERDICT.json`.
**La ADJUDICACIÓN HUMANA del HUMAN_QUALITY_GATE queda `PENDING_HUMAN_CONFIRMATION`** —
no hay registro gobernado ni artefacto firmado de adjudicación de Capa 9. La
corrección v3 se prepara sobre el diagnóstico técnico; su firma y el veredicto del
gate requieren confirmación explícita de Capa 9.
**Sustituye** a `shadow-cf6-composer-struct-v2` (firmado, tag `cf6-G2`) — **no lo modifica**.
`composer_structured_v2.yaml` queda intacto y `SIGNED`.

**No toca:** arquitectura · Q-STATE (`composer_gate.verify_qstate`) · renderer determinista
(`composer_gate.render_section`) · G4d · L2 · routing · `FINDINGS_FINGERPRINT` · `human_state` ·
tags previos (`cf6-G1` … `cf6-G2.5-manifest`).

```
NEW_PROMPT_VERSION      = shadow-cf6-composer-struct-v3
OLD_PROMPT_VERSION      = shadow-cf6-composer-struct-v2
prompt_sha256           = 1008f0be6f0d88a1091fa35a6ecd8ece054b32c27de3dc7e5f0355da7bdcf721
status                  = DRAFT_UNSIGNED   (fail-closed: assert_signed() lanza)
LLM_CALLS = 0 · G4D_CALLS = 0 · L2_MUTATIONS = 0 · HUMAN_STATE_CHANGES = 0
FINDINGS_FINGERPRINT   = 235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23
```

---

## `CORRECTION_REASON`

El HUMAN_QUALITY_GATE / diagnóstico de CF6-2.5 demostró que el prompt v2 **no daba reglas
explícitas** para tres puntos (matriz `REGLA_EN_PROMPT · PRESENTE=NO`):

| defecto demostrado | secciones |
|---|---|
| `technical_findings` = `section_type` / `REGULATORY_INCONCLUSIVE` en lugar de subtypes técnicos reales | sec-0004, sec-0005, sec-0016, sec-0018, sec-0062 |
| `reviewer_action` con páginas fabricadas ("pág. 2", "pág. 1-8") no presentes en el input | sec-0004, sec-0016 |
| `reviewer_action` afirma/consulta cumplimiento ("cumple", "cumplen") | sec-0026, sec-0062 |
| `reviewer_action` propone "acciones correctivas" | sec-0042 |
| `evidence_observed` con la misma cita repetida ×3 / ×4 | sec-0005, sec-0016 |

v3 añade **solo** esas reglas. La seguridad (Q-STATE + blacklist + modo seguro) ya funcionaba:
en CF6-2.5 las 2 secciones que sobreafirmaron cayeron a modo seguro (0 violaciones publicadas).

---

## Cambios de v2 → v3 (solo texto del prompt + validador estructural nuevo)

### 1 · `technical_findings`
- Regla explícita: **`technical_findings ⊆ allowed_technical_findings`**, lista determinista que
  el runner calcula y pasa al prompt (`composer_prompt_v3.allowed_technical_findings(section, l2)`
  = subtypes de findings de la sección cuyo `finding_class` **no** es `RegulatoryFinding` y cuyo
  subtype **no** es `REGULATORY_INCONCLUSIVE`).
- Prohibido usar `section_type`, `regulatory_state`, `REGULATORY_INCONCLUSIVE` ni otro subtype regulatorio.
- `allowed_technical_findings` vacío → `technical_findings = []`.

  Valores deterministas para las 7 secciones del piloto:
  ```
  sec-0004: [ACCESS_CONTROL_GAP, AUTHORITY_CHECK_GAP]      sec-0018: [ACCESS_CONTROL_GAP, AUTHORITY_CHECK_GAP]
  sec-0005: []                                             sec-0026: [BACKUP_RECOVERY_GAP]
  sec-0016: []                                             sec-0042: [IMPLEMENTATION_WITHOUT_REQUIREMENT, ORPHAN_DESIGN_ELEMENT]
  sec-0062: []
  ```

### 2 · `reviewer_action`
- Solo acciones de **verificación** para el revisor humano.
- Prohibido afirmar/preguntar/insinuar cumplimiento / incumplimiento / conformidad / "cumple" / comply / compliant.
- Prohibido CAPA / corrective action / acción correctiva / desviación / remediación.
- Prohibido **páginas / rangos de páginas / referencias documentales no presentes en el input**.
  El input no entrega números de página → `reviewer_action` **no** debe mencionar páginas.
- Prohibido introducir hechos nuevos no sustentados por L2 / citas ancladas.

### 3 · `evidence_observed`
- Solo `finding_record_id` de la lista de entradas; `quote` = subcadena exacta de cita anclada.
- **Deduplicar** citas textualmente idénticas; no repetir la misma evidencia por que varios
  findings compartan cita. `composer_prompt_v3.normalize_evidence_observed()` la elimina de forma
  determinista; el validador la marca.

### 4 · `evidence_limitation`
- Lenguaje neutro; **prohibido** convertir ausencia documental en ausencia real, declarar
  "gap/hueco confirmado", o usar cumplimiento/incumplimiento. (La negación "no implica ausencia
  real" sí es válida.)

### 5 · Few-shot
- **Conserva** el ejemplo regulatorio `21 CFR 11.10(e)` (sec-0031) con `technical_findings: []`.
- **Añade** `TECHNICAL + NOT_APPLICABLE` (sec-0012, `technical_findings: [BACKUP_RECOVERY_GAP]` real).
- **Añade** `FUNCTIONAL_TRACEABILITY + NOT_APPLICABLE` (sec-0001,
  `technical_findings: [IMPLEMENTATION_WITHOUT_REQUIREMENT, ORPHAN_DESIGN_ELEMENT]`).
- Los 3 `reviewer_action` sin "cumple", sin CAPA, sin páginas; los 3 pasan
  `validate_structure_contract` v3 **y** `composer_gate.verify_qstate` contra su sección real.

---

## 6 · `TEST_RESULTS` — validación determinista previa a nueva PILOT

`factory/tests/test_shadow_composer_prompt_v3.py` — **37 passed / 0 failed** (`.venv` del repo).

Demuestra:
- `technical_findings` rechaza `section_type` / `regulatory_state` / `REGULATORY_INCONCLUSIVE`
- `technical_findings ⊆ allowed_technical_findings`
- `[]` cuando `allowed_technical_findings` vacío
- `reviewer_action` rechaza `"cumple"`, `"cumplimiento"/"incumplimiento"`, `"no conformidad"`
- `reviewer_action` rechaza `"acción correctiva"` / `"CAPA"` / `"remediación"` / `"desviación"`
- `reviewer_action` rechaza páginas (`"(pág. 2)"`, `"(pág. 1-8)"`, `"página 4"`, `"p. 5"`)
- `evidence_observed` deduplicado textual (`normalize_evidence_observed`)

**Regresiones explícitas** (salida real del piloto v2, `structured_llm` de `CF6_2_5_B_OUTPUTS.jsonl`,
validada con `allowed_technical_findings` de la sección):

| sección | violación(es) v2 que v3 ahora detecta |
|---|---|
| sec-0004 | `technical_findings=["CROSS_DOMAIN"]` (valor prohibido) + `reviewer_action` "(pág. 2)" |
| sec-0005 | `technical_findings=["REGULATORY"]` (valor prohibido) + `evidence_observed` cita ×3 |
| sec-0016 | `technical_findings=["REGULATORY_INCONCLUSIVE"]` + citas ×4/×2 + `reviewer_action` "(pág. 1-8)" |
| sec-0018 | `technical_findings=["CROSS_DOMAIN"]` (valor prohibido) |
| sec-0026 | `reviewer_action` "…documentado y **cumple**…" (technical_findings `["BACKUP_RECOVERY_GAP"]` era **válido**; v3 no inventa violación) |
| sec-0042 | `reviewer_action` "…confirmar si requieren **acciones correctivas**" + `technical_findings` ∉ allowed |
| sec-0062 | `technical_findings=["REGULATORY_INCONCLUSIVE"]` + `reviewer_action` "…pasajes recuperados **cumplen**…" |

Regresión global `-k shadow`: **181 passed** (1 fallo pre-existente no relacionado:
`test_shadow_and_cutover::test_shadow_run_v2_no_effects_and_reversible`).

---

## 6bis · Demostración de invariantes (`CF6_2_CORRECTION_DEMONSTRATION.json`)

Verificado por sha256 de git (HEAD vs `cf6-G2.5-manifest`, el estado previo a la corrección):

```
OLD_PROMPT_VERSION   = shadow-cf6-composer-struct-v2
NEW_PROMPT_VERSION   = shadow-cf6-composer-struct-v3   (status DRAFT_UNSIGNED, sha 1008f0be…→ver JSON)
QSTATE_UNCHANGED     = YES   (composer_gate.py byte-idéntico; último cambio 415fe35 / CF6-1-r1)
RENDERER_UNCHANGED   = YES   (composer_gate.render_section byte-idéntico)
G4D_UNCHANGED        = YES   (experts.py sin cambios desde 50417c6; g4d_*.jsonl sin cambios)
L2_MUTATIONS         = 0     (FINAL_GMP_CORPUS_FINDINGS.json byte-idéntico, sha 95a79f9b…)
HUMAN_STATE_CHANGES  = 0     (457 findings UNREVIEWED)
LLM_CALLS            = 0
FINDINGS_FINGERPRINT = 235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23
composer_structured_v2.yaml  = byte-idéntico (SIGNED, NO modificado)
decisions_v2.jsonl           = byte-idéntico (sin escritura)
tags preservados             = cf6-G1 · cf6-G1-r1 · cf6-G2-draft · cf6-G2 · cf6-G2G · cf6-G2.5-manifest
```

Nota `input_has_pages`: `validate_structure_contract(..., input_has_pages=False)` por defecto —
el contrato de entrada de CF6-2.5/CF6-3 nunca entrega páginas, así que `reviewer_action`
no puede mencionar ninguna. `input_has_pages=True` desactiva ese chequeo para un contrato futuro
que sí las entregue.

---

## 7 · Gobernanza — `propose` preparado, **STOP** para firma de Capa 9

`CF6_2_CORRECTION_PROPOSE_shadow-cf6-composer-struct-v3.json` — `action: propose`,
`decision_origin: agent_proposed`, `written_to_ledger: false`, `status_at_propose: DRAFT_UNSIGNED`,
`awaiting: { action: human_confirmed, authority: Capa 9 (Cesar) }`.

Para cerrar la corrección, Capa 9:
1. Aprueba explícitamente `shadow-cf6-composer-struct-v3` (`prompt_sha256 = 1008f0be…`).
2. Se registra `status: SIGNED` + `signed_by/at/on` en `composer_structured_v3.yaml` y la evidencia
   `propose → human_confirmed` se congela en un **tag propio** (p. ej. `cf6-G2-r1`), sin tocar
   `cf6-G2` / `cf6-G2G` / `cf6-G2.5-manifest`.
3. Sólo entonces: nuevo CF6-2.5 (re-generar B con v3 sobre el mismo SAMPLE_MANIFEST congelado) →
   HUMAN_QUALITY_GATE por sección.

**No** se ejecutó un nuevo CF6-2.5. **No** se ejecutó CF6-3. **No** se sobrescribió `cf6-G2`,
`cf6-G2G`, `cf6-G2.5-manifest` ni los artefactos del piloto fallido.
