# REPORTE COMPARATIVO PRE vs POST-MEJORAS — Analizador Documental GMP

**Fecha:** 2026-08-31 · **Propósito:** evidencia objetiva para la mesa de diseño — ¿las mejoras
técnicas (remediation D5-D → reglas de completitud **v1.2**) se traducen en mejores conclusiones
regulatorias y en un mejor reporte para el auditor humano?

**Corrida de medición:** `postmejoras_v4_20260831` (NUEVA, full rerun; no reutiliza findings previos).
`FULL_DOCUMENT_ANALYZER_RERUN=YES` · `NEW_FINDINGS_GENERATED=YES` · `ORIGINAL_DOCUMENTS_MODIFIED=NO`.

> Esta corrida es de OBSERVACIÓN. No se corrigió nada durante ni después de verla.

---

## 1. Configuración PRE vs POST

| | PRE | POST |
|---|---|---|
| Analizador | v2 determinista (`run_v2_pipeline`) | **igual** |
| Reglas de completitud técnica | `technical_completeness_rules` **v1.1** (SIGNED 2026-08-27, OD-6) | **v1.2** (D5-D remediation; `pending_approval.approved=false`) |
| Motor | `technical_findings.py` v1.1 | v1.2 (`topic_anchor_patterns`, `incidental_anchor_guard`, `additional_suppressor_families`) |
| `analysis_coverage_mode` | ENFORCE | ENFORCE |
| `EXTRACTION_VERSION` | `canonical-v1-2026-08` | **igual** |
| LLM en el pipeline documental | 0 llamadas (determinista) | **0 llamadas** |
| `AI_RUNTIME` / `DOCUMENT_EGRESS` / `EXTERNAL_LLM_API` | LOCAL_ONLY / 0 / 0 | LOCAL_ONLY / 0 / 0 |
| Método de la corrida PRE | swap controlado a v1.1 **entre** corridas (reglas fijas durante cada corrida), luego restaurado a v1.2 (SHA-256 verificado) | corrida directa sobre el árbol actual |

`HEAD = 946bff0` · rama `fix/clon-local-validacion` · working tree lleva el cambio v1.2 sin commitear.

### Fingerprints

| | PRE (v1.1) | POST (v1.2) | ¿cambia? |
|---|---|---|---|
| `INPUT_CONFIG_FINGERPRINT` | `8f1fe9bbd91999490c4c8c1b9852326bd703ebe3e40b60c4696588d4e848d95e` | `df76bebf74981ced286c49d81d0c7be2399b8503c63253de2f05f4c908470a34` | **sí** — el artefacto gobernado cambió de versión (correcto: `identity != resultado`, WP-A) |
| `GRAPH_SNAPSHOT_FINGERPRINT` | `88f15b69bf2cea9a09d5a179300496d3685b18c58c1adb1dfa601f191b73ae05` | `88f15b69bf2cea9a09d5a179300496d3685b18c58c1adb1dfa601f191b73ae05` | **NO — el grafo no se mueve** |
| `FINDINGS_FINGERPRINT` | `fdc29721e9566dfea6f4969c74c2324f348fc00827ccbd36e35730deb512f08d` | `3d8988045f85655021e6da889bf9048739c6f6c2c1c4c58e75d5974316a5543d` | sí — +2 findings |
| `content_fp` (class+subtype+doc+page+cita) | `65957e745c8ea3d97d819c2c85eb50c57a6547d991f4a24fabb7c4c46d534fab` | `429fb1d162ac78ea2c502be4954adafb65e77b6f9c14b89c8de43f9ff8b0a417` | sí |

---

## 2. Corpus utilizado

**Rockwell 6-doc** (idéntico PRE y POST → comparación válida):

| ID | Tipo | Documento | SHA-256 (PDF original, READ_ONLY, sin cambio) |
|---|---|---|---|
| RW-0005 | FS | `215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf` | `56095a7541fbb62e30d00e77308fde4c2ac0f4ec945adbf19a968b79debc82eb` |
| RW-0006 | URS | `215115305 SCADA-PCS Misc PLC System URS v2.1.pdf` | `d9e24467a66d52fb1a641b6de901ceff1dcdaf66af1ae80cb94a433c40c939c8` |
| RW-0009 | SAT (transmittal) | `215115305-T-039 …` | — |
| RW-0011/0012/0014 | DS | narrativas de control | — |

Extracción/canonicalización: se reutiliza el **store canónico persistido** (deterministo, derivado
de los PDF originales, no re-extraído). El pipeline re-ejecuta desde los claims: grafo → retrieval →
análisis regulatorio → completeness técnica → findings → risk/coverage → provenance → trazabilidad.
`ORIGINAL_DOCUMENTS_MODIFIED=NO`.

---

## 3. Métricas PRE vs POST

| Métrica | PRE | POST | Clasificación |
|---|---|---|---|
| **findings regulatory** | 342 | 342 | **SIN_CAMBIO** |
| **findings functional** | 90 | 90 | **SIN_CAMBIO** |
| **findings technical** | **24** | **26** | **MEJORÓ** (+2 detección; 0 FP nuevos) |
| **QA40 sample precision** | **1.0** [0.7008, 1.0] (D5-A, adjudicado) | **UNKNOWN** (re-muestra POST **sin adjudicar** — pendiente humano) | **NO_COMPARABLE** hasta re-adjudicación |
| QA40 FP (muestra) | 0 (D5-A) | pendiente adjudicación | NO_COMPARABLE |
| QA40 COVERAGE_LIMITED (muestra) | 31/40 (D5-A) | pendiente adjudicación | NO_COMPARABLE |
| **REAL_RECALL** (D5-B, oportunidades de detección) | **1.0** [0.7008, 1.0] (9/9, match confirmado por humano, corrida H-10) | **9/9 estructural mantenido** en la corrida POST (recall formal exige re-confirmación humana del match) | **SIN_CAMBIO** (estructural) |
| **REAL_SPECIFICITY** (D5-C, NEG-CAND-03) | **1.0** [0.2065, 1.0] (1 TN) | **1.0** — NEG-CAND-03 (RW-0005 p.40 `ACCESS_CONTROL_GAP`) sigue **TN** (0 emitido ahí) | **SIN_CAMBIO** |
| **FABRICATED_CITATIONS** | 0 | 0 (toda cita anclada a `source_text` literal + `source_hash`) | **SIN_CAMBIO** |
| **LOCAL_LLM_CALLS** | 0 | 0 | **SIN_CAMBIO** |
| **DOCUMENT_EGRESS_BYTES** | 0 | 0 | **SIN_CAMBIO** |
| **DETERMINISM** | — | **PASS** (r1 == r2, 3 fingerprints + content_fp idénticos) | PASS |
| **GRAPH_SNAPSHOT_FINGERPRINT** | `88f15b69…` | `88f15b69…` | **SIN_CAMBIO** (el grafo no se mueve) |

`QA40_PRE = 1.0` · `QA40_POST = UNKNOWN` (pendiente). `REAL_RECALL_PRE = REAL_RECALL_POST = 1.0`.
`REAL_SPECIFICITY_PRE = REAL_SPECIFICITY_POST = 1.0`.

---

## 4. Findings MANTENIDOS

**PRE 24 technical → POST 26 technical; 23 preservados idénticos** (mismo class/subtype/doc/page/cita).
Regulatory (342) y functional (90): **0 cambios**, todos preservados.

Preservados técnicos: `ORPHAN_DESIGN_ELEMENT` ×8 · `AUDIT_TRAIL_DESIGN_GAP` ×2 · `BACKUP_RECOVERY_GAP` ×2 ·
`ACCESS_CONTROL_GAP` ×2 · `AUTHORITY_CHECK_GAP` ×1 (RW-0005 p.13) · `TECHNICAL_DESIGN_GAP` ×2 ·
`AUDIT_TRAIL_INTEGRITY_GAP` ×2 · `ALCOA_ATTRIBUTABLE_GAP` ×4.

---

## 5. Findings CORREGIDOS

| Tipo | Detalle |
|---|---|
| FP corregido | **1** — `AUTHORITY_CHECK_GAP` en RW-0006 p.5, anclado sobre la línea de glosario "21CFRP11 21 CFR Part 11 Electronic Records, Electronic Signatures". Era `COVERAGE_LIMITED` en D5-A (case `ADJ-2db49caa65`), **no un TP**. v1.2 acota `C05.topic_anchor` (retira `electronic signature`/`login`/`authentication`/`access control` a secas) → deja de anclar sobre glosarios. |
| FN corregido | **candidatos (3)** — ver §8. Son detecciones nuevas de "modelo de autorización descrito sin chequeo de autoridad por operación"; su clasificación TP/FP la decide QA. |

`FP_CORRECTED = YES` (1) · `FN_CORRECTED = PENDIENTE_ADJUDICACION` (3 candidatos).

---

## 6. FP corregidos

- **RW-0006 · p.5 · `SecurityFinding / AUTHORITY_CHECK_GAP`** — anclaje sobre glosario/tabla de
  acrónimos. CHANGE_REASON: `C05.topic_anchor` v1.2 excluye términos de mecanismo de auth que no
  describen el modelo de autorización. En la muestra QA40 D5-A este caso fue `COVERAGE_LIMITED`
  (sale del numerador y denominador de precisión), por lo que su retirada **no** altera
  `QA40_SAMPLE_PRECISION` PRE y es una mejora neta de señal para el auditor.

---

## 7. FN corregidos

No hay ground truth humano de FN sobre el corpus RW que declare estas 3 posiciones como FN
confirmados (el `real_corpus_opportunities.yaml` firmado tiene FN=0 en su alcance). Por tanto:

- `FN_CORRECTED` **no se puede afirmar como demostrado** sin re-adjudicación.
- Lo demostrable: v1.2 **detecta 3 loci adicionales** donde el documento define un modelo de
  roles/niveles/grupos de seguridad y **no** describe verificación de autoridad en tiempo de
  operación — exactamente el patrón que el held-out D5-D2 (diseño) declara como brecha esperada
  `AUTHORITY_CHECK_GAP`. Ver §8.

---

## 8. Findings NUEVOS (3)

Todos `SecurityFinding / AUTHORITY_CHECK_GAP`, `machine_state = MACHINE_INCONCLUSIVE`,
`confidence = LOW`, `evidence_basis = INDETERMINATE` (candidato débil → cola de revisión humana;
v1.2 **no** los promueve a CANDIDATE).

| DOCUMENT | PAGE | SECTION | CITA ANCLADA | CHANGE_REASON |
|---|---|---|---|---|
| RW-0006 | 16 | `sec-caa61dcd3e461fab` | «Engineer security level privileges.» | v1.2 `C05.topic_anchor_patterns` reconoce `security level privileges` como modelo de autorización parafraseado; v1.1 exigía la frase literal `role based access`. Co-localizado con el `ACCESS_CONTROL_GAP` de RW-0006 p.16 que en D5-A fue **TP**. |
| RW-0012 | 5 | `sec-a82a30b1cff7d458` | «Only a user part of the Maintenance or Administrator security group is permitted to» | v1.2 patrón reconoce `... security group ...` (autorización por grupo). El texto restringe una operación a dos grupos pero no describe el chequeo técnico de autoridad en el punto de uso. |
| RW-0014 | 5 | `sec-5fa50879acbbdf49` | «Only a user part of the Maintenance or Administrator security group is permitted to» | Mismo patrón que RW-0012 p.5 (texto de DS reutilizado). Mismo `source_hash`. |

`NEW_FINDINGS = 3`.

---

## 9. Findings ELIMINADOS (1)

| DOCUMENT | PAGE | SECTION | CITA | CHANGE_REASON | ¿REGRESIÓN? |
|---|---|---|---|---|---|
| RW-0006 | 5 | `sec-e32114a96b4cb3a5` | «21CFRP11 21 CFR Part 11 Electronic Records, Electronic Signatures» | v1.2 acota `C05.topic_anchor` — deja de anclar sobre glosario | **NO** — era `COVERAGE_LIMITED` en D5-A, no un TP |

`REMOVED_FINDINGS = 1`.

---

## 10. Regresiones

`REGRESSIONS = 0`.

- 0 findings TP/preservados perdidos (regulatory 342=342, functional 90=90, 23/24 technical preservados;
  el 24º eliminado era un FP/COVERAGE_LIMITED, no un TP).
- 0 `ACCESS_CONTROL_GAP` nuevos (2 PRE = 2 POST) — v1.2 **no** introduce falsos positivos de acceso
  pese a ampliar el reconocimiento de "roles".
- `GRAPH_SNAPSHOT_FINGERPRINT` idéntico (el grafo, la extracción y la canonicalización no se movieron).
- `DETERMINISM = PASS`.
- `UNEXPLAINED_DELTAS = 0` — los 4 deltas (3 nuevos + 1 eliminado) tienen CHANGE_REASON trazado a un
  mecanismo concreto de v1.2.
- Tests de baseline afectados por el cambio de reglas (findings-fingerprint pins H4/H5f/H7) se re-pinnean
  tras `APPROVE_REMEDIATION_V1_2` — no son regresión de comportamiento (`graph_snapshot_fingerprint` no
  se mueve; determinismo intacto).

---

## 11. Cambios de evidencia / provenance

- **Sin cambios** en el mecanismo de evidencia: cada finding lleva `source_text` literal + `source_hash`
  (sha256 del pasaje) + `section` + `provenance{document_id, extraction_version, run_id, agent_id,
  subcriterion_ref}`. `FABRICATED_CITATIONS = 0`.
- Los 3 findings nuevos citan pasajes reales del documento (`Engineer security level privileges.` /
  `Only a user part of the Maintenance or Administrator security group is permitted to`) con
  `source_hash` verificable contra el store canónico.
- El finding eliminado tenía una cita real pero sobre una **fila de glosario**, no sobre una
  descripción de control → su retirada mejora la relación señal/ruido de la evidencia presentada al auditor.

---

## 12. Calidad del contexto regulatorio observado (para la mesa)

Estado REAL actual, sin arreglar nada:

- **Base regulatoria por finding:** presente y específica (`21_CFR_11.10(g)` para C05,
  `ANNEX11_7 §7.2` para C03, etc.), tomada del artefacto gobernado `technical_completeness_rules`.
- **Expectativa regulatoria:** el `rationale` de cada finding enuncia el comportamiento requerido
  (p.ej. "chequeo de autoridad ejecutado por el sistema en el momento de cada operación aplicable").
- **Párrafo completo relevante:** **NO** se incluye inline — el analizador ancla una cita corta
  (`source_text`); el párrafo circundante se recupera del store canónico por `source_hash`/`section`.
  **Limitación para el auditor:** debe abrir el documento maestro para ver el contexto completo.
- **Qué afirma realmente el documento vs comportamiento esperado vs evidencia observada:** el
  `rationale` es plantillado ("El documento describe el tema pero NO se encontró el comportamiento
  requerido: …"). **No** hay un análisis por finding de *por qué* el pasaje concreto no cumple, ni
  una cita del pasaje que *sí* describiría el control si existiera. **Limitación conocida**, no
  corregida en v1.2.
- **Brecha concreta:** enunciada a nivel de regla (genérica por subtype), no particularizada al
  pasaje. **Limitación conocida.**
- **Trazabilidad:** claim → `section` → regla/criterio → `SOURCE_REQUIREMENT_ID`. Completa a nivel
  estructural.
- **Estado de máquina honesto:** los 3 nuevos son `MACHINE_INCONCLUSIVE` / `LOW` — el sistema
  **no** afirma que sean brechas; los envía a revisión humana con cobertura declarada.

---

## 13. Limitaciones

1. `QA40_POST` sin adjudicar → precisión POST = `UNKNOWN`. La comparación de precisión PRE vs POST
   **no está cerrada** hasta que Cesar/QA etiquete la muestra POST.
2. `REAL_RECALL` / `REAL_SPECIFICITY` POST son **estructurales** (co-localización class+subtype+doc+página);
   el recall formal de D5-B exige re-confirmación humana uno-a-uno del match, que no se rehízo.
3. El pipeline documental v2 es determinista sin LLM → esta corrida **no** ejercita el track de
   recall LLM (chunked_engine → Ollama → evidence_verifier, perfil H2H4). `LOCAL_LLM_CALLS=0` es
   correcto para ESTE pipeline, no una omisión.
4. La corrida PRE se obtuvo por swap controlado de reglas entre corridas; aunque el SHA-256 confirma
   la restauración a v1.2, un PRE "de fábrica" idéntico requeriría un checkout limpio de v1.1.
5. Contexto regulatorio del reporte: cita corta anclada, no párrafo completo; `rationale` plantillado,
   no particularizado al pasaje. Sin cambio vs PRE.
6. `technical_completeness_rules` v1.2 sigue `pending_approval.approved=false` — la corrida es
   evidencia, no una corrida sobre reglas aprobadas.

---

## 14. Mejoras DEMOSTRADAS

- **Precisión de anclaje (C05):** eliminado 1 anclaje sobre glosario (RW-0006 p.5). El anclaje de
  C05 ya no dispara sobre términos de mecanismo de auth aislados. `ACCESS_CONTROL_GAP` sin FP nuevos.
- **Cobertura de detección (C05):** +3 loci donde el documento define un modelo de
  roles/niveles/grupos y omite el chequeo de autoridad por operación — antes invisibles para v1.1
  (que exigía la frase literal `role based access`). Reconoce paráfrasis ("security level privileges",
  "security group … permitted to").
- **Estabilidad estructural:** grafo, extracción, canonicalización, regulatory y functional
  **sin cambio** (`GRAPH_SNAPSHOT_FINGERPRINT` idéntico) → el cambio está acotado a la capa de
  completeness técnica, como se diseñó.
- **Determinismo:** `PASS` (2 corridas idénticas).
- **Sin regresión:** 0 TP perdidos, 0 FP nuevos de acceso, `UNEXPLAINED_DELTAS=0`.
- **Higiene de local-only:** `DOCUMENT_EGRESS_BYTES=0`, `EXTERNAL_LLM_CALLS=0` mantenidos.

---

## 15. Mejoras NO demostradas

- **QA40_SAMPLE_PRECISION mejor que PRE:** NO demostrada — POST sin adjudicar (`UNKNOWN`).
  Podría subir (menos ruido de glosario), bajar (3 candidatos débiles nuevos que QA podría marcar FP)
  o quedar igual. **Se requiere re-adjudicación humana.**
- **"Mejores conclusiones regulatorias" a nivel de contenido:** NO demostrada. El `rationale` sigue
  siendo plantillado; no hay análisis particularizado por pasaje, ni cita del pasaje que *sí*
  satisfaría el control. El reporte para el auditor mejora en **señal/ruido** (menos glosario, más
  loci reales) pero **no** en profundidad de la explicación regulatoria por finding.
- **Recall real (FN corregidos confirmados):** NO demostrada — no hay ground truth de FN sobre RW
  que valide los 3 nuevos como FN previos.
- **Mejora en el track de recall LLM (H2H4):** NO evaluada en esta corrida (pipeline determinista).

---

## Salida final

```
FULL_DOCUMENT_ANALYZER_RERUN   = YES
NEW_RUN_ID                     = postmejoras_v4_20260831  (r1 + r2 para determinismo)
DOCUMENTS_REPROCESSED          = 6  (RW-0005, RW-0006, RW-0009, RW-0011, RW-0012, RW-0014)
LOCAL_LLM_CALLS                = 0   (pipeline documental v2 = determinista, sin LLM)
EXTERNAL_LLM_CALLS             = 0
DOCUMENT_EGRESS_BYTES          = 0

NEW_FINDINGS_GENERATED         = YES  (458 findings: 342 reg + 90 func + 26 tech)
QA40_PRE                       = 1.0  [0.7008, 1.0]   (D5-A, adjudicado)
QA40_POST                      = UNKNOWN  (re-muestra POST sin adjudicar — pendiente humano)
REAL_RECALL_PRE                = 1.0  [0.7008, 1.0]
REAL_RECALL_POST              = 1.0  (estructural 9/9 mantenido; recall formal exige re-confirmación humana)
REAL_SPECIFICITY_PRE           = 1.0  [0.2065, 1.0]
REAL_SPECIFICITY_POST         = 1.0  (NEG-CAND-03 sigue TN)

FP_CORRECTED                   = 1   (RW-0006 p.5, glosario — era COVERAGE_LIMITED, no TP)
FN_CORRECTED                   = PENDIENTE_ADJUDICACION  (3 candidatos débiles nuevos)
NEW_FINDINGS                   = 3   (AUTHORITY_CHECK_GAP: RW-0006 p.16, RW-0012 p.5, RW-0014 p.5)
REMOVED_FINDINGS               = 1
REGRESSIONS                    = 0

DETERMINISM                    = PASS
UNEXPLAINED_DELTAS             = 0

MEJORA_REGULATORIA_DEMOSTRADA        = PARCIAL  (precisión de anclaje + cobertura C05 sí;
                                                 profundidad de la explicación regulatoria por finding NO)
MEJORA_REPORTE_AUDITOR_DEMOSTRADA    = PARCIAL  (mejor señal/ruido; sin cambio en párrafo completo /
                                                 rationale particularizado)

QA40_PACKET        = docs_plan/QA40_HUMAN_REVIEW_PACKET_POST_MEJORAS_V4_20260831.md
COMPARATIVE_REPORT = docs_plan/REPORTE_COMPARATIVO_PRE_POST_MEJORAS_20260831.md

LISTO_PARA_MESA_DE_DISENO = SI   (evidencia objetiva completa; la única pieza pendiente —
                                  QA40_POST precision — requiere re-adjudicación humana y está
                                  explícitamente marcada como tal)
```

*Corrida de medición. NO commiteado. Reglas y código restaurados a v1.2 tras capturar el PRE (SHA-256 verificado).*
