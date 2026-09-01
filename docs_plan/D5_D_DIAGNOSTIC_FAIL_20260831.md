# D5-D — DIAGNOSTIC FAIL (NON-GATE) + APERTURA DE ANALYZER REMEDIATION

**Fecha:** 2026-08-31 · **Estado:** `D5_D = REMEDIATION_REQUIRED` · `D5_COMPLETE = NO`
**Autora independiente:** Maria Torres (QA Validation Engineer) — validez nominal / repo-level.

> Esta NO es una métrica final D5. Es evidencia diagnóstica de una corrida del analizador que
> **no** califica como held-out gate formal por desviación de secuencia (ver §2).

---

## 1. Clasificación de la corrida existente

```
CURRENT_RUN_CLASSIFICATION      = NON_GATE_DIAGNOSTIC_FAIL
analyzer_run_dir                = factory/regulatory/pilot_run/held_out_d5d_20260831/analyzer_run/
preserve_unmodified             = true   (no borrar, no recalcular findings, no sobrescribir fingerprints)

FINDINGS_FINGERPRINT            = 2f3fb8b35c82d03d69c40cae7efbbe4c294d9eb85832fc8473c69a9990073701
INPUT_CONFIG_FINGERPRINT        = cc7b31849f262905aaa5e7e630b811b7cebed63cb025fe23cd4d0a5aeebfc08b
GRAPH_SNAPSHOT_FINGERPRINT      = a5e4046f34a39ddc1320399f4b276b2eae7db994463093b02b3dda1c4606e05f
DOCUMENT_EGRESS_BYTES           = 0
```

### Resultados por caso (diagnósticos)

| case_id | expected | outcome | detalle |
|---|---|---|---|
| HO-T-001 | DataIntegrityFinding / AUDIT_TRAIL_INTEGRITY_GAP | **TP** | C09 emitió AUDIT_TRAIL_INTEGRITY_GAP en HO-FS p.12 ("An audit log table exists…") |
| HO-T-002 | TechnicalFinding / BACKUP_RECOVERY_GAP | **FN** | ninguna regla C03 se ancló en HO-FS |
| HO-T-003 | SecurityFinding / AUTHORITY_CHECK_GAP | **FN** | C05 no se ancló en HO-FS (sí en HO-URS, fuera de scope) |
| HO-T-004 | SecurityFinding / ACCESS_CONTROL_GAP | **TP** | C04 emitió ACCESS_CONTROL_GAP en HO-FS p.15 ("Three named roles are available…") |
| HO-T-N01 | (negativo, HO-FSOK) | **FP** | C04 emitió ACCESS_CONTROL_GAP en HO-FSOK p.3 (documento conforme) |

```
DIAGNOSTIC_TP                    = 2   (HO-T-001, HO-T-004)
DIAGNOSTIC_FN                    = 2   (HO-T-002, HO-T-003)
DIAGNOSTIC_FP                    = 1   (HO-T-N01)
DIAGNOSTIC_RECALL               = 0.50   (TP/(TP+FN) = 2/4)
DIAGNOSTIC_FALSE_POSITIVE_RATE  = 1.0    (FP/(FP+TN) = 1/(1+0))
DIAGNOSTIC_FABRICATED_CITATIONS = 0
```

Los 8 findings crudos: `analyzer_run/technical_findings.json`. Provenance + fingerprints: `analyzer_run/run_record.json`.

---

## 2. Desviación de secuencia (por qué NO es gate formal)

```
materialization human confirmation received AFTER analyzer execution
-> run NOT eligible as final governed held-out gate

MATERIALIZATION_CONFIRMATION_TIMING = POST_ANALYZER_RUN
FORMAL_GATE_SEQUENCE_VALID          = NO
```

La confirmación humana literal `"MATERIALIZATION_MATCHES_GROUND_TRUTH=YES for all five"`
(Maria Torres) se **recibió** el 2026-08-31, **después** de que existiera la evidencia post-run.
No se afirma que ocurriera antes. Esto **no** cambia el ground truth congelado.

---

## 3. Integridad PRE-RUN (verificada)

```
YAML_PARSE                       = PASS   (parser estricto que FALLA ante duplicate keys)
YAML_DUPLICATE_KEYS              = 0
CASE_COUNT                       = 5      (HO-T-001, HO-T-002, HO-T-003, HO-T-004, HO-T-N01; ids únicos)
thresholds schema               = {TECHNICAL_RECALL_MIN, TECHNICAL_FALSE_POSITIVE_MAX, FABRICATED_CITATIONS_MAX}
match_policy schema              = {by, page_band_tolerance}   (separado; sin fuga a thresholds)

CANONICAL_MATERIALIZATION_VERIFIABLE = YES   (leído desde held_out_d5d_20260831/canonical/*.sqlite3)
HELD_OUT_CANONICAL              = factory/regulatory/pilot_run/held_out_d5d_20260831/
source SHA-256 (canonical_content, verificado):
  HO-URS  = 21424264c47b1454cb4088091a2854bc9491800f88399e9a9c357507416731cd  (2 claims)
  HO-FS   = 14519b03b704ad671063cdef2556729a86acdbfceaf8ceccc9c684c068612f9d  (5 claims)
  HO-FSOK = 9dba93d05acf2a42be6d2ba3fe843efc849ce912f8e7f7db1bbe2feaf241401d  (1 claim)
page_band real (verificado desde claims):
  HO-T-001 HO-FS [12,12] · HO-T-002 HO-FS [14,14] · HO-T-003 HO-FS [15,15] ·
  HO-T-004 HO-FS [15,15] · HO-T-N01 HO-FSOK [3,3]
PAGE_BANDS_CANONICAL            = RESOLVED_DIAGNOSTIC

PRE_RUN_HASH_PERSISTED          = 125accf9d08cca76dde5f5fdc441f154fafa0a4099e2c4fdd93016013ce05b6e
PRE_RUN_HASH_RECOMPUTED         = 125accf9d08cca76dde5f5fdc441f154fafa0a4099e2c4fdd93016013ce05b6e
HASH_MATCH                      = YES
```

`status` = `DRAFT_UNSIGNED`; `assert_usable_as_gate()` sigue fail-closed; WP-E suite 40/40.

---

## 4. Root-cause analysis (READ-ONLY — sin cambios de código del analizador)

Mecanismo de `completeness_findings` (B6b v2, `technical_completeness_rules.yaml` SIGNED):
para cada regla Cxx y documento, se busca el PRIMER claim (por página) cuyo `source_text`
contiene ALGÚN término de `topic_anchor`. Si no hay ancla → la regla se salta (no hay finding).
Si hay ancla y **no** aparece la `family` de evidencia aceptable en el scope → se emite el gap.

### 4.1 `ROOT_CAUSE_HO_T_002` — FN, BACKUP_RECOVERY_GAP (regla C03)

- **Evidencia:** claim HO-FS p.14 `"System data is copied to a network share periodically."`
- **C03.topic_anchor** = `["backup", "back-up", "back up", "respaldo", "copia de seguridad"]`
- El claim NO contiene ninguno → **no se ancla C03** → la lógica absence-dependent
  (`family: restore_verified`) **nunca se evalúa** → FN.
- Extracción / canonicalización: correctas (claim literal, íntegro).
- **Categoría de causa raíz:** `RULE_TRIGGER / TOPIC_ANCHOR_LEXICAL_COVERAGE`.
  El set de `topic_anchor` de C03 no reconoce la paráfrasis "copied … periodically / to a
  network share" como el tópico de backup/respaldo.
- **Código:** `factory/regulatory/findings/technical_findings.py::completeness_findings`
  (bucle `anchor_rec = next(... any(t in source_text.lower() for t in topics) ...)`, ~línea 235).
  Datos: `technical_completeness_rules.yaml` C03 `DETERMINISTIC_DETECTION_RULE.topic_anchor` (~línea 291).

### 4.2 `ROOT_CAUSE_HO_T_003` — FN, AUTHORITY_CHECK_GAP (regla C05)

- **Evidencia:** claim HO-FS p.15 `"Three named roles are available in the configuration screen."`
- **C04.topic_anchor** incluye `"role"` / `"roles"` (token suelto) → **C04 SÍ se ancló** y emitió
  ACCESS_CONTROL_GAP en HO-FS p.15 (ese es el TP de HO-T-004).
- **C05.topic_anchor** = `["access control", "role based access", "authentication", "login",
  "electronic signature", "control de acceso"]` → exige la **frase** "role based access";
  "named roles are available" no coincide → **no se ancla C05 en HO-FS** → FN.
- C05 sí disparó en HO-URS p.2 (`"...role based access"`), pero fuera del scope del caso.
- **Categoría de causa raíz:** `SUBTYPE_DISCRIMINATION / TOPIC_ANCHOR_SCOPE`.
  La misma evidencia ("existen roles") ancla C04 pero no C05: el `topic_anchor` de C05 es más
  estrecho que el de C04 para evidencia estructuralmente equivalente. El ground truth espera
  que "roles existen, sin descripción de verificación de autoridad por operación" dispare
  **ambos** (C04 y C05).
- **Código/datos:** mismo bucle de anclaje; `technical_completeness_rules.yaml` C04 `topic_anchor`
  (~línea 330) vs C05 `topic_anchor` (~línea 364).

### 4.3 `ROOT_CAUSE_HO_T_N01` — FP, ACCESS_CONTROL_GAP en negativo (regla C04)

- **Evidencia:** claim HO-FSOK p.3 `"The audit trail records the user identity, timestamp, the
  previous value and the new value for every change, and cannot be modified or disabled by any
  role including administrators."`
- **C04.topic_anchor** incluye `"role"` → el token en "by any role including administrators"
  **ancla C04 de forma incidental**.
- `scope_text` = ese único claim (HO-FSOK tiene 1 claim). No hay señales de
  `family: per_operation_authorization` (`["authorization level","operation"]` …) → C04 concluye
  "tópico presente, comportamiento ausente" → emite ACCESS_CONTROL_GAP → **FP**.
- El tópico real del claim es **protección/integridad del audit trail** (territorio C01/C09),
  no estructura de control de acceso.
- **Categoría de causa raíz:** `TOPIC_ANCHOR_OVER_BROAD + MISSING_CROSS_TOPIC / NEGATIVE_EVIDENCE_SUPPRESSION`.
  No existe supresor que reconozca que el match de `"role"` es incidental en una frase cuyo
  sujeto es otro control. La lógica absence-dependent dispara sobre un tópico que en realidad
  no está presente.
- **Código:** `completeness_findings` — chequeo `xref` (`anchor_low` vs `cross_reference_suppressors`,
  ~línea 241) y `family_present(scope_text, fam_name, fam_sig)` (~línea 247). Ninguno cubre este caso.
  Datos: `technical_completeness_rules.yaml` C04 `topic_anchor` (~línea 330) + `family_signals`
  `per_operation_authorization` + `cross_reference_suppressors`.

### 4.4 Ubicación de la causa (clasificación pedida)

| caso | extraction | canonicalization | rule trigger | completeness logic | absence-dependent logic | subtype discrimination | suppression / negative evidence | graph relation |
|---|---|---|---|---|---|---|---|---|
| HO-T-002 FN | ok | ok | **PRIMARIA** (topic_anchor no ancla) | secundaria (no se alcanza) | no se ejecuta | — | — | n/a |
| HO-T-003 FN | ok | ok | **PRIMARIA** (topic_anchor C05 estrecho) | — | — | **PRIMARIA** (C04 sí / C05 no) | — | n/a |
| HO-T-N01 FP | ok | ok | **PRIMARIA** (topic_anchor "role" demasiado amplio) | contribuye | dispara sobre tópico no real | — | **PRIMARIA** (falta supresor cross-topic) | n/a |

---

## 5. Reglas de contaminación / cierre

```
ANALYZER_REMEDIATION                     = OPEN
CURRENT_HELD_OUT_REUSE_FOR_FINAL_GATE    = PROHIBITED
```

Una vez que HO-T-002 / HO-T-003 / HO-T-N01 se usen para diseñar o modificar el analizador,
los 5 casos HO-T-001…HO-T-N01 quedan **contaminados** y **no** pueden servir como prueba final
independiente. El cierre formal de D5 requerirá:

**D5-D2 — FRESH INDEPENDENT HELD-OUT**: casos nuevos, no observados durante la remediation,
definidos por la autora independiente (≠ Cesar), materializados como corpus canónico separado,
con la secuencia de gate formal correcta (confirmación de materialización ANTES de la corrida).

No cambiar: ground truth, held-out expected, thresholds. No E5. No E6. No commit. No production enablement.
