# D5-D — HOJA DE DECISIÓN DEL AUTOR INDEPENDIENTE (revisión ÚNICA)

**Autor independiente designado:** Maria Torres (QA Validation Engineer)
**Fecha de emisión de la hoja:** 2026-08-31 · **Estructura por:** Capa 8 (Claude Code)
**Autoridad del ground truth held-out:** exclusivamente Maria Torres. La IA NO decide ni completa estos juicios.

> Artefacto destino: `factory/regulatory/requirement_catalog/held_out_technical_corpus.yaml`
> (hoy `status: DRAFT_UNSIGNED`, `author: null`, `rules_author` ausente).
> Paquete de contexto: `docs_plan/D5_HELD_OUT_INDEPENDENT_AUTHOR_PACKET_20260831.md`.

---

## 0. Verificación de independencia (hecha antes de emitir esta hoja)

| Condición | Resultado |
|---|---|
| `Maria Torres (QA Validation Engineer)` != `Cesar` | ✅ distinta persona |
| ∉ `excluded_authors = ["Capa 9 (Cesar)"]` | ✅ no está |
| != autor/firmante de `technical_completeness_rules.yaml` (`authored_by: "Capa 8"`, `signed_by: "Capa 9 (Cesar)"`) | ✅ ninguno |
| != autor semilla del held-out (`held_out_technical_corpus.yaml.author = null`; semilla sintética `build_seed_corpus`) | ✅ sin autor humano previo |
| `"Maria Torres"` ya presente en el repo | ✅ no aparecía — identidad nueva, sin acoplamiento |

**INDEPENDENT_AUTHOR_VALID = YES** — **alcance: independencia NOMINAL / a nivel de repo únicamente.**
Git **no** acredita la identidad física de María ni su rol real de QA/Validation. La condición de
gobernanza es que **las cinco decisiones de abajo las emita realmente María** y **no** las fabrique
Cesar (Capa 9) ni Capa 8 (la IA). Capa 8 solo transcribe literalmente lo que María devuelva.
No se firma nada todavía.

---

## 1. Reglas de la revisión (fijadas ex-ante — no cambian con el resultado)

```
match_policy.by                 = [finding_class, subtype, document, page_band]   # ESTRUCTURAL, sin frase literal
match_policy.page_band_tolerance = 3
thresholds:
  TECHNICAL_RECALL_MIN          = 0.90
  TECHNICAL_FALSE_POSITIVE_MAX  = 0.05
  FABRICATED_CITATIONS_MAX      = 0
provenance:
  REG -> source_clause OBLIGATORIA (cláusula normativa citada)
  DOM -> rationale del revisor (conocimiento de QA/Validation)
  ADV -> propuesto por máquina; entra SOLO con human_approved: true explícito
```

El analizador **no** se ha ejecutado. Estos 5 casos describen QUÉ debe encontrar (o no) el analizador,
por posición y tipo. La redacción del documento held-out la define María en la materialización (punto 4
del plan); aquí solo se fija el ground truth.

---

## 2. Los 5 casos — hoja compacta PRE-RUN (SIN page_band definitivo todavía)

**Corrección de secuencia:** `HELD_OUT_CANONICAL = NONE`. El corpus held-out **aún no existe**,
así que **NO se pide un `page_band` canónico definitivo en esta fase**. El `page_band` real de cada
caso se determina **después** de la materialización (punto D) y María lo confirma en la revisión
PRE-RUN de materialización (punto E). Aquí María fija **solo el ground truth de tipo/expectativa**.

Para cada caso, María devuelve **exclusivamente**:

```
DECISION        = CONFIRM | REJECT
EXPECTED_FINDING = true | false
EXPECTED_CLASS   = <FindingClass>            # None si EXPECTED_FINDING=false
EXPECTED_SUBTYPE = <subtype>                 # None si EXPECTED_FINDING=false
PROVENANCE       = REG | DOM | ADV
SOURCE_CLAUSE    = <cláusula normativa>       # OBLIGATORIA solo si PROVENANCE=REG
RATIONALE_NOTE   = <texto>                    # juicio del revisor (obligatorio si DOM; recomendable siempre)
HUMAN_REVIEWED   = true
HUMAN_APPROVED   = true                       # OBLIGATORIO explícito solo si PROVENANCE=ADV
```

Opcional: María puede describir en `RATIONALE_NOTE` la **estructura o ubicación lógica** esperada de
la evidencia (p. ej. "sección de audit trail del FS", "tabla de roles"). Eso **no** es el `page_band`
real y no se registra como tal; orienta la materialización.

`CONFIRM` = María acepta el `expected` que se le muestra (puede ajustar cualquier campo).
`REJECT` = María descarta el caso o lo redefine por completo (debe entonces dar el `expected` nuevo).
Sin `HUMAN_REVIEWED=true` el caso no se registra.

---

### HO-T-001 — esqueleto que se le muestra a María

| Campo | Valor del esqueleto (propuesta, NO decisión) |
|---|---|
| `provenance_tag` | **REG** |
| `expected.finding` | `true` |
| `expected.finding_class` | `DataIntegrityFinding` |
| `expected.subtype` | `AUDIT_TRAIL_INTEGRITY_GAP` |
| `source_clause` | `"21 CFR 11.10(e) -- audit trail: fecha/hora, quién, valor anterior/nuevo"` |
| documento held-out previsto | `HO-FS` (ubicación lógica: sección de audit trail) |
| `page_band` | **se determina tras materializar — no se pide ahora** |

**Qué decide María:** confirmar/ajustar la cláusula 21 CFR 11.10(e) y el tipo del hallazgo esperado.

```
HO-T-001:
  DECISION=            CONFIRM | REJECT
  EXPECTED_FINDING=    true | false
  EXPECTED_CLASS=      ______
  EXPECTED_SUBTYPE=    ______
  PROVENANCE=          REG | DOM | ADV
  SOURCE_CLAUSE=       ______        # obligatoria si PROVENANCE=REG
  RATIONALE_NOTE=      ______
  HUMAN_REVIEWED=      true
  HUMAN_APPROVED=      (n/a salvo ADV)
```

---

### HO-T-002 — esqueleto

| Campo | Valor del esqueleto (propuesta, NO decisión) |
|---|---|
| `provenance_tag` | **REG** |
| `expected.finding` | `true` |
| `expected.finding_class` | `TechnicalFinding` |
| `expected.subtype` | `BACKUP_RECOVERY_GAP` |
| `source_clause` | `"EU GMP Annex 11 §7.2 -- backups regulares Y verificación de restauración"` |
| documento held-out previsto | `HO-FS` (ubicación lógica: sección de backup/recuperación) |
| `page_band` | **se determina tras materializar — no se pide ahora** |

**Qué decide María:** confirmar/ajustar la cláusula Annex 11 §7.2 y el tipo del hallazgo esperado.

```
HO-T-002:
  DECISION=            CONFIRM | REJECT
  EXPECTED_FINDING=    true | false
  EXPECTED_CLASS=      ______
  EXPECTED_SUBTYPE=    ______
  PROVENANCE=          REG | DOM | ADV
  SOURCE_CLAUSE=       ______        # obligatoria si PROVENANCE=REG
  RATIONALE_NOTE=      ______
  HUMAN_REVIEWED=      true
  HUMAN_APPROVED=      (n/a salvo ADV)
```

---

### HO-T-003 — esqueleto

| Campo | Valor del esqueleto (propuesta, NO decisión) |
|---|---|
| `provenance_tag` | **DOM** |
| `expected.finding` | `true` |
| `expected.finding_class` | `SecurityFinding` |
| `expected.subtype` | `AUTHORITY_CHECK_GAP` |
| `source_clause` | `null` (DOM no la exige) |
| `reviewer_rationale` | `"El FS nombra 'roles' pero no describe verificación de autoridad por operación."` |
| documento held-out previsto | `HO-FS` (ubicación lógica: sección de control de acceso / roles) |
| `page_band` | **se determina tras materializar — no se pide ahora** |

**Qué decide María:** confirmar/redefinir el rationale del revisor. Si lo reclasifica a REG,
`SOURCE_CLAUSE` pasa a ser obligatoria.

```
HO-T-003:
  DECISION=            CONFIRM | REJECT
  EXPECTED_FINDING=    true | false
  EXPECTED_CLASS=      ______
  EXPECTED_SUBTYPE=    ______
  PROVENANCE=          REG | DOM | ADV
  SOURCE_CLAUSE=       ______        # obligatoria solo si la reclasifica a REG
  RATIONALE_NOTE=      ______        # obligatorio si PROVENANCE=DOM
  HUMAN_REVIEWED=      true
  HUMAN_APPROVED=      (n/a salvo ADV)
```

---

### HO-T-004 — esqueleto

| Campo | Valor del esqueleto (propuesta, NO decisión) |
|---|---|
| `provenance_tag` | **ADV** |
| `expected.finding` | `true` |
| `expected.finding_class` | `SecurityFinding` |
| `expected.subtype` | `ACCESS_CONTROL_GAP` |
| `source_clause` | `null` |
| `machine_proposal_note` | `"Detector de completitud propuso ACCESS_CONTROL_GAP; revisor humano lo aprobó."` |
| `human_approved` | `true` (placeholder — **requiere ratificación explícita de María**) |
| documento held-out previsto | `HO-FS` (ubicación lógica: sección de control de acceso) |
| `page_band` | **se determina tras materializar — no se pide ahora** |

**Qué decide María:** **aprobar o rechazar** la propuesta de máquina. `HUMAN_APPROVED=true`
solo si María lo aprueba explícitamente; si no, el caso ADV **no entra**.

```
HO-T-004:
  DECISION=            CONFIRM | REJECT
  EXPECTED_FINDING=    true | false
  EXPECTED_CLASS=      ______
  EXPECTED_SUBTYPE=    ______
  PROVENANCE=          REG | DOM | ADV
  SOURCE_CLAUSE=       ______        # obligatoria si la promueve a REG
  RATIONALE_NOTE=      ______
  HUMAN_REVIEWED=      true
  HUMAN_APPROVED=      true | false  # OBLIGATORIO explícito si PROVENANCE=ADV
```

---

### HO-T-N01 — esqueleto (caso NEGATIVO)

| Campo | Valor del esqueleto (propuesta, NO decisión) |
|---|---|
| `provenance_tag` | **DOM** |
| `expected.finding` | `false` |
| `expected.finding_class` | `None` |
| `expected.subtype` | `None` |
| `source_clause` | `null` |
| `reviewer_rationale` | `"FS conforme separado: audit trail completo + protección anti-modificación."` |
| documento held-out previsto | `HO-FSOK` (ubicación lógica: FS conforme, sección de audit trail) |
| `page_band` | **se determina tras materializar — no se pide ahora** |

**Qué decide María:** confirmar que el FS "OK" describe el control **completo** → el analizador
**NO** debe emitir nada en esa unidad.

```
HO-T-N01:
  DECISION=            CONFIRM | REJECT
  EXPECTED_FINDING=    false
  EXPECTED_CLASS=      None
  EXPECTED_SUBTYPE=    None
  PROVENANCE=          REG | DOM | ADV
  SOURCE_CLAUSE=       ______        # obligatoria si PROVENANCE=REG
  RATIONALE_NOTE=      ______
  HUMAN_REVIEWED=      true
  HUMAN_APPROVED=      (n/a salvo ADV)
```

---

## 3. Casos adicionales (opcional)

María **puede** añadir casos positivos o negativos extra si su revisión del FS held-out lo justifica.
Cada caso adicional debe traer los mismos campos completos.

---

## 4. Qué NO puede hacer nadie con estas decisiones

- No inferirlas ni completarlas la IA. Capa 8 solo transcribe literalmente.
- No modificarlas retroactivamente tras conocer los resultados del analizador.
- Tras recibirlas, Capa 8 las escribe literales en `held_out_technical_corpus.yaml` y calcula
  `PRE_RUN_GROUND_TRUTH_SHA256` sobre: `expected_finding`, `expected_class`, `expected_subtype`,
  `provenance`, `source_clause`/`rationale` y las marcas humanas (`human_reviewed`, `human_approved`).
  **El `page_band` NO entra en ese hash** — no existe todavía; se fija tras la materialización (punto D)
  y María lo confirma en la revisión PRE-RUN de materialización (punto E), sin poder alterar el `expected`.
- Congelado el hash: no se tocan `expected`, thresholds, `technical_completeness_rules.yaml`,
  prompts ni detectores en respuesta al resultado held-out.

---

## 5. Secuencia posterior (referencia — no se ejecuta hasta tener los 5 bloques)

```
B  decisiones PRE-RUN de María (esta hoja)           -> ground truth de tipo/expectativa
C  escribir literal + PRE_RUN_GROUND_TRUTH_SHA256    -> freeze (sin page_band)
D  materializar corpus canónico held-out (no RW-00x, no corpus de desarrollo H10)
   -> HELD_OUT_CANONICAL, source SHA-256 por doc, source attestation, page_band REALES
E  María confirma MATERIALIZATION_MATCHES_GROUND_TRUTH=YES|NO por caso
   (solo verifica que el material reproduce su expected; no cambia el expected)
   -> fingerprint de la versión canónica pre-run
F  ejecutar pipeline productivo 1 vez -> analyzer_version, INPUT_CONFIG / GRAPH_SNAPSHOT /
   FINDINGS fingerprints, findings, evidence_provenance, document_egress_bytes=0
G  María revisa expected vs actual (FN / FP / fabricated citation) -> confirma/rechaza match
H  firma: status=SIGNED, author=rules_author="Maria Torres (QA Validation Engineer)", signed_at
   -> assert_usable_as_gate() = PASS
I  scorer: TECHNICAL_HELD_OUT_RECALL >= 0.90 · FALSE_POSITIVE_RATE <= 0.05 · FABRICATED_CITATIONS = 0
```

---

### Entrega de María

Responder con los 5 bloques `HO-T-001..004` / `HO-T-N01` (más adicionales si los hay), **sin `page_band`**.
Con eso, Capa 8: los escribe **literales** en `held_out_technical_corpus.yaml`, calcula
`PRE_RUN_GROUND_TRUTH_SHA256`, y continúa con D → E → F → G → H → I.

---

## 6. Registro de ejecución D5-D (puntos 1–4)  ·  2026-08-31

### 6.1 Decisión humana recibida (punto 1)

- **independent_author:** `Maria Torres (QA Validation Engineer)`
- **declaración literal:** `"HO-T-001 through HO-T-N01 all CONFIRM as skeleton"`
- Expandida literalmente a los 5 bloques (sin inferir valores distintos) y escrita en
  `held_out_technical_corpus.yaml` con `human_reviewed: true` y `human_decision: CONFIRM` por caso;
  `human_approved: true` en HO-T-004 (ADV).

### 6.2 Freeze del ground truth PRE-RUN (punto 2)

- `held_out_technical_corpus.yaml`: `status: DRAFT_UNSIGNED` (sin cambio), `ground_truth_frozen: true`.
- `PRE_RUN_GROUND_TRUTH_SHA256 = 125accf9d08cca76dde5f5fdc441f154fafa0a4099e2c4fdd93016013ce05b6e`
  — cubre por caso {case_id, expected_finding, expected_class, expected_subtype, provenance,
  source_clause/rationale, human_reviewed, human_approved} + thresholds + match_policy. **No cubre page_band.**
- `GROUND_TRUTH_FROZEN = YES`. Prohibido tocar expected/class/subtype/provenance/thresholds a partir de aquí.

### 6.3 Materialización del corpus canónico held-out (punto 3)

- **HELD_OUT_CANONICAL:** `factory/regulatory/pilot_run/held_out_d5d_20260831/`
  (`canonical/`, `graph/`, `source_attestation.json`). Corpus NUEVO y SEPARADO — **no** RW-00xx,
  **no** corpus de desarrollo, **no** documentos de H10. Builder: `held_out_corpus.build_seed_corpus`
  (la redacción del texto la elige el builder; el ground truth solo aporta class/subtype/document).
- **source SHA-256 (contenido canónico determinista) por documento:**
  - `HO-URS`  → `21424264c47b1454cb4088091a2854bc9491800f88399e9a9c357507416731cd` (2 claims)
  - `HO-FS`   → `14519b03b704ad671063cdef2556729a86acdbfceaf8ceccc9c684c068612f9d` (5 claims)
  - `HO-FSOK` → `9dba93d05acf2a42be6d2ba3fe843efc849ce912f8e7f7db1bbe2feaf241401d` (1 claim)

### 6.4 PRE-RUN materialization review — para confirmación de María (punto 4)

| case_id | expected congelado (finding / class / subtype) | provenance | documento canónico | **page_band REAL** | source text real materializado |
|---|---|---|---|---|---|
| HO-T-001 | true / DataIntegrityFinding / AUDIT_TRAIL_INTEGRITY_GAP | REG | HO-FS | **[12, 12]** | "An audit log table exists in the application database." |
| HO-T-002 | true / TechnicalFinding / BACKUP_RECOVERY_GAP | REG | HO-FS | **[14, 14]** | "System data is copied to a network share periodically." |
| HO-T-003 | true / SecurityFinding / AUTHORITY_CHECK_GAP | DOM | HO-FS | **[15, 15]** | "Three named roles are available in the configuration screen." |
| HO-T-004 | true / SecurityFinding / ACCESS_CONTROL_GAP | ADV (human_approved) | HO-FS | **[15, 15]** | "Three named roles are available in the configuration screen." |
| HO-T-N01 | false / — / — (negativo) | DOM | HO-FSOK | **[3, 3]** | "The audit trail records the user identity, timestamp, the previous value and the new value for every change, and cannot be modified or disabled by any role including administrators." |

Los `page_band` reales caen dentro de las bandas provisionales del esqueleto ([10,16] / [1,10])
y del tolerance ±3. `source_attestation.json` contiene el detalle completo + sqlite paths + hashes.

**María debe responder únicamente, para los cinco:**

```
MATERIALIZATION_MATCHES_GROUND_TRUTH = YES | NO   (por caso)
```

- `YES` en los cinco ⇒ Capa 8 fija `HELD_OUT_PRE_RUN_CANONICAL_SHA256`, escribe los `page_band`
  reales en el yaml y ejecuta el analizador **una** vez (punto 5).
- Cualquier `NO` ⇒ Capa 8 corrige **solo la materialización** para reproducir el ground truth
  congelado (nunca el expected), con trazabilidad de la corrección.

Esta confirmación **no** puede cambiar el `expected` PRE-RUN para acomodarlo a resultados futuros.

### 6.5 Confirmación de materialización de María (punto 4 — RECIBIDA)   — ⚠️ RETRACTADA (ver banner §7–§9)

`MATERIALIZATION_MATCHES_GROUND_TRUTH = YES` para los cinco (HO-T-001/002/003/004/N01), 2026-08-31.
~~`page_band` reales escritos en `held_out_technical_corpus.yaml`.~~ **Retirado:** esos `page_band`
provenían de una materialización prematura y se removieron del `match` operativo
(`page_bands_canonical: UNRESOLVED`). Ground truth PRE-RUN sigue congelado
(`PRE_RUN_GROUND_TRUTH_SHA256 = 125accf9…`, recalculado reproducible, sin drift).
La confirmación de materialización de María deberá **re-emitirse** sobre el corpus canónico
que se materialice a continuación.

---

> ## ⚠️ SECCIONES 7–9 SUPERSEDED / INVALIDADAS — 2026-08-31
>
> La materialización y la corrida del analizador descritas en §6.3–§9 se ejecutaron de forma
> **prematura**: usaban los `page_band` provisionales del esqueleto (`[10,16]` / `[1,10]`)
> como si fueran **canónicos**, antes de resolver la integridad PRE-RUN del artefacto.
>
> Corrección aplicada (D5-D punto 1–5, sólo sobre `held_out_technical_corpus.yaml`):
> - YAML normalizado, `YAML_DUPLICATE_KEYS=0` (verificado con parser estricto anti-duplicados).
> - `match` de cada caso = sólo `document`; `page_band` **retirado** del match operativo
>   (`page_bands_canonical: UNRESOLVED`, `held_out_canonical: NONE`). Las bandas provisionales
>   viven en `provisional_match` y el matcher no las lee.
> - `PRE_RUN_GROUND_TRUTH_SHA256` recalculado de forma reproducible desde disco (2×):
>   `125accf9d08cca76dde5f5fdc441f154fafa0a4099e2c4fdd93016013ce05b6e` — `HASH_MATCH=YES`.
>   Placeholder previo `7a3f…` invalidado (no reproducible; era un placeholder, no un digest).
> - Bloques `held_out_post_run_review` / `held_out_gate_verdict` **eliminados** del yaml.
>   La corrida previa queda registrada como `prior_premature_run: {status: INVALIDATED,
>   is_gate_verdict: false}` y el directorio
>   `factory/regulatory/pilot_run/held_out_d5d_20260831/` queda huérfano/invalidado.
> - `FREEZE_VALIDATION = PASS` (18/18). `status = DRAFT_UNSIGNED`, `assert_usable_as_gate()` fail-closed.
>
> **Estado vigente:** `D5_D = GROUND_TRUTH_FROZEN_READY_FOR_MATERIALIZATION` · `D5_COMPLETE = NO`.
> Lo de §6.3–§9 **NO es un veredicto de gate**. La próxima acción es re-materializar el corpus
> held-out canónico separado desde el ground truth congelado `125accf9…`, resolver los
> `page_band` reales, obtener `MATERIALIZATION_MATCHES_GROUND_TRUTH=YES` de María y **entonces**
> ejecutar el analizador una vez. `ANALYZER_REMEDIATION` no se abre hasta: materialización
> aprobada → corrida → scorer → threshold FAIL sobre el corpus canónico real.
>
> Las métricas 0.50 / 1.0 de §8 quedan **sin valor de gate** — se recalcularán sobre el
> corpus canónico materializado.

---

## 7. Corrida ÚNICA del analizador (punto 5) + post-run review (punto 6)  ·  2026-08-31   — ⚠️ SUPERSEDED (ver banner arriba)

**Sin modificar reglas / prompts / detectores.** Pipeline determinista `graph_technical_findings`
(`include_completeness=True`) sobre el corpus held-out, bajo `network_locked()`.

```
ANALYZER_VERSION                 = canonical-v1-2026-08
HELD_OUT_PRE_RUN_CANONICAL_SHA256 = 577e5eb9b64a94cc7f4e493bc1edfb2e08ba2c7319e3592754e252ef9d106522
INPUT_CONFIG_FINGERPRINT         = cc7b31849f262905aaa5e7e630b811b7cebed63cb025fe23cd4d0a5aeebfc08b
GRAPH_SNAPSHOT_FINGERPRINT       = a5e4046f34a39ddc1320399f4b276b2eae7db994463093b02b3dda1c4606e05f
FINDINGS_FINGERPRINT             = 2f3fb8b35c82d03d69c40cae7efbbe4c294d9eb85832fc8473c69a9990073701
HELD_OUT_ANALYZER_RUN            = factory/regulatory/pilot_run/held_out_d5d_20260831/analyzer_run/
DOCUMENT_EGRESS_BYTES            = 0        (local_only = True)
n_findings                       = 8
```

Cross-check independiente `run_held_out_dry()`: `recall_indicative = 0.5`, `TP = [HO-T-001, HO-T-004]`,
`FN = [HO-T-002, HO-T-003]`, `FP_count = 1`, `document_egress_bytes = 0`, `reportable_range = NOT_A_GATE`.

### 7.1 Expected vs actual — para revisión de María (punto 6)

| case_id | expected (finding / class / subtype) | actual en banda (class/subtype @ page) | matched_finding_id | outcome estructural |
|---|---|---|---|---|
| HO-T-001 | true / DataIntegrityFinding / AUDIT_TRAIL_INTEGRITY_GAP | DataIntegrityFinding/AUDIT_TRAIL_INTEGRITY_GAP @12 · TechnicalFinding/AUDIT_TRAIL_DESIGN_GAP @12 · SecurityFinding/ACCESS_CONTROL_GAP @15 | `fnd-2634c00eff3217c3` | **TP_STRUCTURAL** |
| HO-T-002 | true / TechnicalFinding / BACKUP_RECOVERY_GAP | (ningún BACKUP_RECOVERY_GAP en HO-FS ±3) | — | **FN** |
| HO-T-003 | true / SecurityFinding / AUTHORITY_CHECK_GAP | (ningún AUTHORITY_CHECK_GAP en HO-FS p.15±3; solo ACCESS_CONTROL_GAP) | — | **FN** |
| HO-T-004 | true / SecurityFinding / ACCESS_CONTROL_GAP | SecurityFinding/ACCESS_CONTROL_GAP @15 | `fnd-9b9acb670836401e` | **TP_STRUCTURAL** |
| HO-T-N01 | false (negativo) | SecurityFinding/ACCESS_CONTROL_GAP @3 en HO-FSOK | — | **FP** |

Findings completos: `analyzer_run/technical_findings.json`. Provenance por finding + fingerprints:
`analyzer_run/run_record.json`.

### 7.2 Lo que decide María (punto 6) — confirma/rechaza el MATCH, sin tocar el expected congelado

```
HO-T-001:  MATCH_CONFIRMED = YES | NO   (finding fnd-2634c00eff3217c3 corresponde al expected)
HO-T-002:  FN_CONFIRMED    = YES | NO   (no hay finding que corresponda -> falso negativo real)
HO-T-003:  FN_CONFIRMED    = YES | NO
HO-T-004:  MATCH_CONFIRMED = YES | NO   (finding fnd-9b9acb670836401e corresponde al expected)
HO-T-N01:  FP_CONFIRMED    = YES | NO   (fnd-9fbf5f6b80cd2b02 en el doc conforme -> falso positivo real)
           FABRICATED_CITATION = YES | NO   (¿la cita del finding está anclada a texto real del doc?)
```

### 7.3 Consecuencia previsible sobre los thresholds congelados (punto 8, tras la firma)

Con el resultado actual (si María confirma los outcomes tal cual):

```
TECHNICAL_HELD_OUT_RECALL      = 2/4 = 0.50   <  0.90   -> FALLA
TECHNICAL_FALSE_POSITIVE_RATE  = 1 FP / (1 FP + 1 TN sobre negativos) = 0.50   >  0.05   -> FALLA
FABRICATED_CITATIONS          = (pendiente juicio de María en HO-T-N01)
```

⇒ salvo que la revisión post-run de María cambie legítimamente la adjudicación del match,
**`D5_D` no puede firmarse como PASS** y `D5_COMPLETE = NO`. No se permite modificar reglas,
prompts, detectores, thresholds ni el ground truth congelado para mejorar estos números.

### 7.4 Revisión post-run de María (punto 6 — RECIBIDA)  ·  2026-08-31

```
HO-T-001:  MATCH_CONFIRMED = YES   (implícito; no disputado)   -> TP
HO-T-002:  FN_CONFIRMED    = YES                               -> FN
HO-T-003:  FN_CONFIRMED    = YES                               -> FN
HO-T-004:  MATCH_CONFIRMED = YES   (implícito; no disputado)   -> TP
HO-T-N01:  FP_CONFIRMED    = YES · FABRICATED_CITATION = NO    -> FP (no fabricada)
```

Registrado literal en `held_out_technical_corpus.yaml` → `held_out_post_run_review`.

## 8. Scorer + veredicto de gate (punto 8/9)  ·  2026-08-31   — ⚠️ SUPERSEDED (ver banner §7–§9)

> Estas métricas NO son un veredicto de gate. Se calcularon sobre una materialización prematura
> con `page_band` provisionales. Se recalcularán sobre el corpus canónico real. `D5_D` vigente =
> `GROUND_TRUTH_FROZEN_READY_FOR_MATERIALIZATION`, no `FAIL`.

Calculado con el scorer existente (`held_out_corpus.run_held_out_dry`), no manualmente:

| métrica | valor | threshold congelado | resultado |
|---|---|---|---|
| `TECHNICAL_HELD_OUT_RECALL` | **0.50**  (TP/(TP+FN) = 2/4) | ≥ 0.90 | **FALLA** |
| `TECHNICAL_FALSE_POSITIVE_RATE` | **1.0**  (FP/(FP+TN) = 1/(1+0)) | ≤ 0.05 | **FALLA** |
| `FABRICATED_CITATIONS` | **0** | = 0 | pasa |
| `document_egress_bytes` | 0 | = 0 | pasa |

`by_provenance_tag`: REG 1/2 · DOM 0/1 · ADV 1/1.

**Veredicto D5-D = FAIL.** Firma RETENIDA: `held_out_technical_corpus.yaml` permanece
`status: DRAFT_UNSIGNED`; `assert_usable_as_gate()` sigue fail-closed. Los dos tests
`test_held_out_*` siguen verdes.

**Qué significa:** el instrumento held-out (desacoplado de validez de constructo, autor
independiente ≠ Cesar) hizo su trabajo y detectó una limitación **real** del analizador técnico
determinista sobre corpus independiente de señal mínima:
- no emite `BACKUP_RECOVERY_GAP` (HO-T-002) ni `AUTHORITY_CHECK_GAP` (HO-T-003) → recall 0.50;
- sobre-emite `ACCESS_CONTROL_GAP` en un documento **conforme** (HO-T-N01) → FP.

Prohibido "arreglar" esto tocando reglas / prompts / detectores / thresholds / ground truth
congelado. La remediación (si se decide) es un cambio de ingeniería del analizador, fuera de
este instrumento, seguido de una **nueva** corrida held-out contra el **mismo** ground truth congelado.

## 9. Cierre D5 (punto 9)   — ⚠️ SUPERSEDED (ver banner §7–§9)

> El bloque de abajo reflejaba el estado tras la corrida prematura. **Estado vigente:**

```
D5_A = SIGNED   (QA40 40/40 · TP=9 · FP=0 · COVERAGE_LIMITED=31 · PENDING=0 · precision 1.0 Wilson [0.7008,1.0])
D5_B = SIGNED   (9 oportunidades · MATCHED 9 · FN 0 · recall 1.0 Wilson [0.7008,1.0])
D5_C = SIGNED   (1 negative_unit NEG-CAND-03=NEGATIVE_YES · specificity 1.0 Wilson [0.2065,1.0])
D5_D = GROUND_TRUTH_FROZEN_READY_FOR_MATERIALIZATION   (PRE_RUN_GROUND_TRUTH_SHA256=125accf9… · status DRAFT_UNSIGNED · assert_usable_as_gate fail-closed)
D5_COMPLETE = NO   (bloqueo: falta materializar el corpus held-out canónico y correr contra él)
```

~~D5_D = FAIL~~ era el estado tras la corrida prematura y queda invalidado. No se avanza a E5.
Sin commit. Sin E6. Sin production enablement. `ANALYZER_REMEDIATION` no se abre hasta:
materialización canónica → aprobación de María → corrida → scorer → threshold FAIL real.

---

## 10. Materialización canónica del held-out desde el ground truth congelado  ·  2026-08-31   (VIGENTE)

Materializado desde `PRE_RUN_GROUND_TRUTH_SHA256 = 125accf9d08cca76dde5f5fdc441f154fafa0a4099e2c4fdd93016013ce05b6e`
(revalidado, sin drift). Corpus **nuevo y separado**: no RW-00xx, no corpus de desarrollo,
no documentos de H10. Builder `held_out_corpus.build_seed_corpus`. **Analizador NO ejecutado.**

```
HELD_OUT_CANONICAL          = factory/regulatory/pilot_run/held_out_d5d_canonical_20260831/
HELD_OUT_CANONICAL_SHA256   = 7b2ba82c9effa95df923814ea43efef0681f70b6ddc41dcb62c769e716203d94
ANALYZER_VERSION            = canonical-v1-2026-08
INPUT_CONFIG_FINGERPRINT    = c0338f555dc156642d0369efbb02370313897f997dcf3b62279457f9066206a7
GRAPH_SNAPSHOT_FINGERPRINT  = a5e4046f34a39ddc1320399f4b276b2eae7db994463093b02b3dda1c4606e05f
FINDINGS_FINGERPRINT        = (pendiente — analizador no ejecutado)
```

**source SHA-256 (contenido canónico determinista) por documento:**

| doc | canonical_content_sha256 | claims |
|---|---|---|
| HO-URS  | `21424264c47b1454cb4088091a2854bc9491800f88399e9a9c357507416731cd` | 2 |
| HO-FS   | `14519b03b704ad671063cdef2556729a86acdbfceaf8ceccc9c684c068612f9d` | 5 |
| HO-FSOK | `9dba93d05acf2a42be6d2ba3fe843efc849ce912f8e7f7db1bbe2feaf241401d` | 1 |

Detalle: `held_out_d5d_canonical_20260831/source_attestation.json`.

### 10.1 PRE-RUN materialization review — para confirmación de María

`page_band` reales escritos en `held_out_technical_corpus.yaml → cases[].match.page_band`;
`page_bands_canonical: RESOLVED_PENDING_HUMAN_CONFIRMATION`; `match_operational_resolved: false`
en los 5 (→ `true` sólo tras `YES` de María). Ground truth congelado **sin cambios** (page_band
excluido del hash — verificado: la escritura de las bandas no alteró `125accf9…`).

| case_id | expected congelado (finding / class / subtype) | provenance | doc canónico | **page_band REAL** | source text materializado |
|---|---|---|---|---|---|
| HO-T-001 | true / DataIntegrityFinding / AUDIT_TRAIL_INTEGRITY_GAP | REG | HO-FS | **[12, 12]** | "An audit log table exists in the application database." |
| HO-T-002 | true / TechnicalFinding / BACKUP_RECOVERY_GAP | REG | HO-FS | **[14, 14]** | "System data is copied to a network share periodically." |
| HO-T-003 | true / SecurityFinding / AUTHORITY_CHECK_GAP | DOM | HO-FS | **[15, 15]** | "Three named roles are available in the configuration screen." |
| HO-T-004 | true / SecurityFinding / ACCESS_CONTROL_GAP | ADV (human_approved) | HO-FS | **[15, 15]** | "Three named roles are available in the configuration screen." |
| HO-T-N01 | false / — / — (negativo) | DOM | HO-FSOK | **[3, 3]** | "The audit trail records the user identity, timestamp, the previous value and the new value for every change, and cannot be modified or disabled by any role including administrators." |

**María responde únicamente, por caso:** `MATERIALIZATION_MATCHES_GROUND_TRUTH = YES | NO`.

- 5×`YES` ⇒ Capa 8 pone `match_operational_resolved: true`, fija el fingerprint canónico pre-run
  y ejecuta el analizador **una** vez (D5-D punto 5).
- Cualquier `NO` ⇒ Capa 8 corrige **sólo la materialización** para reproducir el ground truth
  congelado (nunca el `expected`), con trazabilidad.

Esta confirmación **no** puede cambiar el `expected` PRE-RUN. `status` sigue `DRAFT_UNSIGNED`;
`assert_usable_as_gate()` fail-closed.
