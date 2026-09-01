# PAQUETE D-5 — ADJUDICACIÓN HUMANA (H-8, evidencia real de desempeño)

**Fecha:** 2026-08-30 · **Autoridad:** Capa 9 = Cesar · **Gate:** **D-5** (STOP humano obligatorio).
**Precede:** `docs_plan/CIERRE_H7_ENFORCE_D2_20260830.md` (H-7 cerrado, ENFORCE gobernado).

`H8_INSTRUMENT_READY = YES`. **La máquina construyó el instrumento VACÍO; NO lo rellenó.**
La adjudicación (`TP`/`FP`/`COVERAGE_LIMITED`, oportunidades de detección, unidades negativas,
firma del held-out) es **trabajo humano**. Sin ella:
`REAL_RECALL = UNKNOWN`, `REAL_SPECIFICITY = UNKNOWN`, `QA40_SAMPLE_PRECISION = UNKNOWN`
(fail-closed, por diseño).

La IA **no puede** auto-asignar: `TP` · `FP` · `COVERAGE_LIMITED` · ground truth ·
oportunidad de detección real · unidad negativa real. Ausencia de evidencia recuperada **no**
se convierte en `FP`/`TP` automáticamente.

---

## 0 · Qué hay pendiente (números exactos)

| Instrumento | Fichero | Pendiente |
|---|---|---|
| **QA40 — revisión de hallazgos EMITIDOS** (mide precisión/PPV) | `factory/regulatory/requirement_catalog/qa40_adjudication_sheet.yaml` | **40 casos** con `label: PENDING` |
| **Oportunidades de detección** (mide recall real / FN) | `factory/regulatory/requirement_catalog/real_corpus_opportunities.yaml` → `opportunities:` | **0 enumeradas** — QA lee el corpus y las escribe |
| **Unidades negativas** (mide especificidad / TN) | mismo fichero → `negative_units:` | **0 enumeradas** — QA las escribe |
| **Held-out técnico — firma** | `factory/regulatory/requirement_catalog/held_out_technical_corpus.yaml` | `status: DRAFT_UNSIGNED`, `rules_author = null` → requiere revisión + firma humana |

**Muestra QA40 — INMUTABLE.** `qa40_finding_ids_sha256 = 02b6d3d0b6fadb1f882c4e63b7f7421dd387268ddabe5b5f16abfa5d9d360d32`.
**No se re-muestrea** salvo razón gobernada nueva. Direccionamiento por `finding_record_id`
(H-3). ENFORCE (D-2) **no** altera esta muestra (`finding_id` no depende de la banda de riesgo).

**Corpus de referencia:** RW-0005, RW-0006, RW-0009, RW-0011, RW-0012, RW-0014
(originales en `GMPAI/source/Rockwell/`, canónico en `factory/regulatory/canonical_store/`).

**Ruta protegida:** los 4 ficheros viven en `factory/regulatory/requirement_catalog/`, que el
runtime endurecido monta **read-only** (H-5F). El analizador **no puede modificarlos**; solo
QA/Validation los edita, en el host.

---

## 1 · QA40 — cómo adjudicar (`qa40_adjudication_sheet.yaml`)

Para **cada uno de los 40 casos**, la hoja ya trae TODA la evidencia disponible (no hay que
buscarla): `finding_record_id`, `finding_id`, `finding_class`, `subtype`, `criterion` /
`subcriterion_ref`, `regulatory_basis` / `technical_basis`, `document`, `section`, `page`,
`source_hash`, `anchored_quote` (texto exacto, sin truncar), `evidence_basis`,
`coverage_status`, `would_degrade`, `graph_path` (referencia al snapshot de grafo cuando
aplica), y `proposed_machine_finding` (severidad, banda de riesgo pre/post-ENFORCE,
`machine_state`, `confidence`, `rationale`).

**QA rellena SOLO estos campos por caso:**

| Campo | Valores | Regla |
|---|---|---|
| `label` | `TP` \| `FP` \| `COVERAGE_LIMITED` | `TP` = el hallazgo es una desviación real y correctamente caracterizada · `FP` = no es una desviación real, o la caracterización es incorrecta · `COVERAGE_LIMITED` = no es sólidamente evaluable en ESTE corpus (p.ej. depende de la mitad de prueba vacía / RW-0009 `NOT_ANALYZABLE`). **`COVERAGE_LIMITED` se excluye del numerador y denominador de precisión.** |
| `human_evidence_anchor` | texto | cita / página EXACTA del documento que sustenta la decisión |
| `adjudicator_note` | texto | por qué |
| `held_out_provenance_tag` | `REG` \| `DOM` \| `ADV` \| (vacío si N/A) | `REG` = la expectativa sale de una cláusula regulatoria citable · `DOM` = juicio de dominio GMP del revisor · `ADV` = caso adversarial/sintético (requiere `human_approved`) |

**PROHIBIDO** en esta hoja: etiquetas `FN` o `TN` — no son derivables de hallazgos emitidos.
Si aparecen, `score_emitted_review()` **falla cerrado**. FN/recall → §2. TN/especificidad → §3.

**Al terminar los 40:** `status: SIGNED`, `adjudicator: "<nombre real>"`,
`adjudicated_at: "<ISO-8601>"`.

---

## 2 · Oportunidades de detección — cómo enumerar (`real_corpus_opportunities.yaml` → `opportunities:`)

QA **lee el corpus** (URS/FS/DS reales, NO los hallazgos emitidos) y registra **toda
desviación que DEBERÍA detectarse**, exista o no en la salida del analizador. Una lista por
oportunidad, con **todos** estos campos (los valida `score_recall`, si falta uno falla cerrado):

```
opportunity_id                 OPP-0001, OPP-0002, …
expected_class                 RegulatoryFinding | FunctionalFinding | TechnicalFinding |
                               TraceabilityFinding | DataIntegrityFinding | SecurityFinding |
                               TestCoverageFinding
expected_subtype               p.ej. BACKUP_RECOVERY_GAP, REQUIREMENT_NOT_TESTED, …
document                       RW-00xx
page_band                      [int, int]  (start <= end, ambos > 0)
expected_topic_or_requirement  qué se espera y por qué (referencia normativa/tema)
human_evidence_anchor          cita/página exacta del documento                     <- QA
basis                          fundamento regulatorio/técnico de por qué es una desviación  <- QA
reviewer_note                  observación del revisor                              <- QA
```

**Confirmación de match (la pone QA al adjudicar; la IA NO):**
```
matched_finding_id   finding EMITIDO que QA confirma que corresponde a esta oportunidad
match_confirmed_by   quién confirma
match_note           por qué corresponde
```
- `matched_finding_id` + `match_confirmed_by` van juntos; el finding debe existir en la corrida.
- **Uno-a-uno:** un `matched_finding_id` no puede confirmarse en dos oportunidades.
- Sin los 3 campos de confirmación → esa oportunidad cuenta como **FN**.
- `page_match_policy.tolerance_pages` (hoy `0`) solo gobierna la PROPUESTA de candidatos
  estructurales, **no** el TP. Súbelo solo con justificación documentada.

`recall = TP / (TP + FN)` · `TP` = oportunidad con match confirmado · `FN` = sin él.

---

## 3 · Unidades negativas — cómo enumerar (`real_corpus_opportunities.yaml` → `negative_units:`)

Solo con esto se publica `REAL_SPECIFICITY` (si no, `UNKNOWN`). Una lista por unidad:

```
unit_id                NEG-0001, …
analysis_unit          section | document | page_range   (qué ES una unidad negativa aquí)
document               RW-00xx
scope                  [int, int]  (start <= end, ambos > 0)
expected_class         la clase que el analizador NO debe emitir en esta unidad
expected_subtype       el subtipo que NO debe emitir
human_evidence_anchor  cita: el control está presente y COMPLETO                    <- QA
basis                  por qué NO debe haber hallazgo aquí                          <- QA
reviewer_note          observación                                                 <- QA
human_verified         true
```
`TN` = unidad negativa donde el analizador **no** emitió el hallazgo prohibido ·
`FP`(especificidad) = donde sí lo emitió. **No se inventan TN.**

**Al terminar:** en `real_corpus_opportunities.yaml` → `status: SIGNED`,
`adjudicator: "<nombre real>"`, `adjudicated_at: "<ISO-8601>"`.

---

## 4 · Held-out técnico — firma (`held_out_technical_corpus.yaml`)

Revisar el ground-truth (`case_id`, `provenance_tag` ∈ {REG, DOM, ADV}, `expected`, `match`),
confirmar que `REG` traen `source_clause` y `ADV` traen `human_approved: true`, y firmar:
`status: SIGNED`, `rules_author: "<nombre real>"` (≠ el autor del corpus semilla).
Sin firma → los números del held-out son **INDICATIVOS**, no gate.

---

## 5 · Qué pasa DESPUÉS de D-5 (continuación automática de la misión, ya definida)

Con los conjuntos firmados, la máquina calcula (sin volver a pedir nada):

```
QA40_SAMPLE_PRECISION   = TP / (TP + FP)         sobre los 40 casos etiquetados no-COVERAGE_LIMITED
                          + reportable_range (intervalo de Wilson) + declaración de contaminación
REAL_RECALL             = TP / (TP + FN)         sobre las oportunidades de detección
REAL_SPECIFICITY        = TN / (TN + FP_spec)    sobre las unidades negativas
```
Cada métrica se publica con el **metric_envelope** (5 campos: `metric`, `suite_version`,
`definition`, `reportable_range`, `contamination_statement`). **Si una métrica carece de
denominador/evidencia válida → `UNKNOWN`** (no se estima).

Salida: `docs_plan/CIERRE_H8_EVIDENCIA_REAL.md`. Luego la misión sigue: H-9 (benchmark de
extracción; gate **D-3** para descargas) → D-4 → H-10 → WP-F → **D-6**.

---

## 6 · Resumen para Capa 9

```
GATE                          = D-5   (STOP humano; NO preautorizado)
QA40_PENDING_CASES            = 40    (factory/regulatory/requirement_catalog/qa40_adjudication_sheet.yaml)
DETECTION_OPPORTUNITIES_PENDING = 0 enumeradas  (QA las escribe leyendo el corpus)
NEGATIVE_UNITS_PENDING         = 0 enumeradas  (QA las escribe)
HELD_OUT_SIGNATURE_PENDING     = YES  (held_out_technical_corpus.yaml: status DRAFT_UNSIGNED, rules_author null)

QA40_SHA (inmutable)          = 02b6d3d0b6fadb1f882c4e63b7f7421dd387268ddabe5b5f16abfa5d9d360d32
CORPUS                        = RW-0005/0006/0009/0011/0012/0014
RUTA PROTEGIDA                = factory/regulatory/requirement_catalog/  (runtime :ro, H-5F)
IA_PUEDE_ADJUDICAR            = NO  (TP/FP/COVERAGE_LIMITED/ground-truth/opportunity/negative_unit = humano)

FICHEROS A COMPLETAR/FIRMAR:
  1. factory/regulatory/requirement_catalog/qa40_adjudication_sheet.yaml       (40× label + anchor + note + provenance_tag ; luego status:SIGNED)
  2. factory/regulatory/requirement_catalog/real_corpus_opportunities.yaml     (opportunities: [...] + negative_units: [...] ; luego status:SIGNED)
  3. factory/regulatory/requirement_catalog/held_out_technical_corpus.yaml     (revisar + status:SIGNED + rules_author)
```

**STOP en D-5.** No se calcula ninguna métrica real hasta recibir la adjudicación humana válida.
