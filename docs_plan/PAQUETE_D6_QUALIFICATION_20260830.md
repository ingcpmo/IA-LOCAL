# PAQUETE D-6 — QUALIFICATION (NO PREAUTORIZADO)

**Fecha:** 2026-08-30 · **Autoridad:** Capa 9 = Cesar · **Gate:** **D-6** — decisión humana,
**no preautorizada**. Este documento **prepara** la decisión; no la toma. Sin commit, sin push.

```
PROPOSED_QUALIFIED_VERSION = NOT_ELIGIBLE_YET
RECOMMENDATION             = NOT_ELIGIBLE_YET   (obligatorio: el D-5 humano nunca ocurrió)
```

---

## 0 · Regla aplicada

Misión: *"Si D-5 humano nunca ocurrió, la recomendación obligatoria es
`QUALIFIED_VERSION=NOT_ELIGIBLE_YET`."* → `D5_ADJUDICATION = NOT_OCCURRED` /
`D5_HUMAN_EVIDENCE_AVAILABLE = NO` (verificado). Recomendación = **NOT_ELIGIBLE_YET**, con
independencia de que `H10_TECHNICAL_ACCEPTANCE = PASS`.

---

## 1 · Estado por hito

```
D1  = CURRENT_INTENDED_USE=GMP_DECISION_SUPPORT_TOOL ; SYSTEM_OF_RECORD=NO ; HUMAN_FINAL_AUTHORITY=REQUIRED
H1  = ACCEPTED     (identidad / mutadores críticos ; test-only en regresión)
H2  = ACCEPTED     (audit trail aislado de tests)
H2b = ACCEPTED     (review_queue aislado)
H3  = ACCEPTED     (finding_record_id)
H4  = ACCEPTED     (GRAPH_SNAPSHOT_FINGERPRINT estable ; baseline b5196a71…)
H5F = PASS         (CORS allowlist ; egress PROCESS+NETWORK ; mounts mínimos ; DOCUMENT_EGRESS medido)
H6F = PASS         (backup/restore F-STATE 14/14 ; fork histórico preservado ; secretos excluidos)
H7  = CLOSED       (analysis_coverage_mode gobernado ; ENFORCE por D-2 ; findings_degraded=78 ; findings_suppressed=0)
D2  = APPROVE      (ARTIFACT_VERSION-2026-019/020 ; 3 artefactos firmados)
H8  = INSTRUMENT_READY ; QA40_SAMPLE_PRECISION=UNKNOWN ; REAL_RECALL=UNKNOWN ; REAL_SPECIFICITY=UNKNOWN
D5  = NOT_OCCURRED
D3  = DONE         (rapidocr + docling ; offline ; licencias compatibles ; DOCUMENT_EGRESS=0)
H9  = PASS         (benchmark 204 pág RW-0003 ; 3 backends deterministas/offline ; egress 0 ; RECOMMENDED=docling)
D4  = APPROVE ; CONDITIONS_MET=YES ; SELECTED=docling  (ARTIFACT_VERSION-2026-021 ; decision_ref D-4-H9-20260830)
H10 = H10_TECHNICAL_ACCEPTANCE=PASS ; PRODUCTION_ACTIVATION=PENDING_HUMAN_VERIFICATION
      TEST_OBJECTS_RW0003=165 · TESTED_BY=17 · VERIFIES=0 (N/A) · REFERS_TO=350 · SYSTEM_COMPONENT=47 · ACTOR=13
      implemented_by 1120→1120 · designed_by 190→190 · fabricated_*=0 · deterministic=PASS · DOCUMENT_EGRESS=0
      CANONICAL_DRIFT_EXPLAINED=YES (PREEXISTING_CLONE_DRIFT) · ROLLBACK=PASS · H10_HUMAN_SAMPLE_VERIFICATION=PENDING

QA40_SAMPLE_PRECISION = UNKNOWN
REAL_RECALL           = UNKNOWN
REAL_SPECIFICITY      = UNKNOWN
NEW_REGRESSIONS       = 0
```

---

## 2 · OPEN_DEVIATIONS

```
DEV-1  H-8 sin ground truth humano (D-5 NOT_OCCURRED). Métricas reales = UNKNOWN. No falsificable.
DEV-2  H-10 VERIFIES=0: el SAT real (RW-0003) referencia requisitos de proyecto (3.2.3) y funciones
       (F05.05), no ids del catálogo regulatorio. verifies (test→requirement de catálogo) es N/A
       para este SAT; la traza a regulación va por la cadena tested_by+implemented_by+regulated_by.
DEV-3  H-10 TESTS_WITHOUT_REQUIREMENT_REF=162: casos reales del SAT sin id de requisito recuperable
       en el OCR. Se crea el Test (evidencia real) pero NO produce arista de traza. No es fabricación.
DEV-4  H-10 refers_to (350): ancla de nodo de algunas entidades es una línea de lista de referencias
       (se prefiere prosa vía _is_citation_anchor; el resto para juicio humano). Las ARISTAS parten
       100% de claims sustantivas. -> H10_HUMAN_SAMPLE_VERIFICATION=PENDING.
DEV-5  Ledger gobernado con 3 registros sin commitear (D-2 x2 + D-4). LEDGER_UNCOMMITTED=YES.
       Los 4 guards store==git-HEAD fallan por esto. AUTO-CLEAR al commitear. La misión prohíbe commit.
DEV-6  Sustitución D-3: OCRmyPDF+Tesseract -> rapidocr-onnxruntime (host sin sudo). Documentada,
       misma categoría, licencias compatibles, offline verificado.
DEV-7  D-4 selecciona docling; footprint ~9.3 GB pico single-shot. H-10 lo ingirió POR LOTES
       (peak 4.5 GB) sin riesgo para contenedores de BD. Ingesta 204 pág completada.
DEV-8  Clone-drift preexistente en canonical_store de producción (RW-0012: 595 vs 258 claims, con
       páginas fantasma 17/18). CLASSIFICATION=PREEXISTING_CLONE_DRIFT ; no causado por H-10 ;
       la activación productiva debe re-extraer el corpus limpio (lo que H-10 v2 ya materializó).
DEV-9  Actor/SystemComponent: el store admite objetos sin provenance (compat. histórica) ; los
       EXTRAÍDOS por extract_entities SIEMPRE la llevan (build_* la exige).
```

---

## 3 · QUALIFICATION_BLOCKERS

```
BLK-1  H8_HUMAN_GROUND_TRUTH_MISSING            (DEV-1)  — dominante, no falsificable
BLK-2  H10_HUMAN_SAMPLE_VERIFICATION_PENDING    (DEV-4)
BLK-3  LEDGER_UNCOMMITTED (D-2 x2 + D-4)        (DEV-5)  — se limpia al commitear
BLK-4  HUMAN_SIGNATURES_PENDING (H-1…H-7, D-2)  — firma de Capa 9 / QA no registrada
BLK-5  PRODUCTION_ACTIVATION not authorized (H10 técnico PASS, pero _EXT_VER/_CANON sin flipar
       hasta verificación humana + re-extracción limpia del corpus)
```

---

## 4 · Qué habilitaría una futura qualification (no ahora)

1. Adjudicación humana D-5 completa y firmada → `QA40_SAMPLE_PRECISION` / `REAL_RECALL` /
   `REAL_SPECIFICITY` calculables con su `metric_envelope`.
2. Verificación humana de `H10_NEW_RELATIONS_SAMPLE_FOR_HUMAN.json` (77 filas: 17 tested_by + 60 refers_to).
3. Activación gobernada de `canonical-v1-2026-08+tests-v1`: flip de `_EXT_VER`/`_CANON` en
   `v2_runtime.py` + re-extracción LIMPIA del corpus con el código HEAD (materializada en
   `canonical_store_v2/`) → nueva baseline de los 3 fingerprints.
4. Commit del ledger gobernado (D-2 x2 + D-4) → limpia los 4 guards store==git-HEAD.
5. Firmas humanas de Capa 9 / QA sobre H-1…H-7 y D-2.

---

## 5 · Campos D-6

```
D6_STATUS                    = NOT_APPROVED  (no preautorizado ; falta decisión humana)
PROPOSED_QUALIFIED_VERSION   = NOT_ELIGIBLE_YET
RECOMMENDATION               = NOT_ELIGIBLE_YET   (obligatorio: D-5 humano nunca ocurrió)
H1..H10                      = ver §1
D1                           = CURRENT_INTENDED_USE=GMP_DECISION_SUPPORT_TOOL (integrado en WP-F §0)
D2                           = APPROVE (registrado)
D3                           = DONE
D4                           = APPROVE ; CONDITIONS_MET = YES ; SELECTED = docling (registrado)
QA40_SAMPLE_PRECISION        = UNKNOWN
REAL_RECALL                  = UNKNOWN
REAL_SPECIFICITY             = UNKNOWN
NEW_REGRESSIONS              = 0
OPEN_DEVIATIONS              = DEV-1 … DEV-9  (§2)
QUALIFICATION_BLOCKERS       = BLK-1 … BLK-5  (§3)
FINGERPRINTS (H-10 v2)       = INPUT_CONFIG 0de04225… · GRAPH_SNAPSHOT 8ce23f30… · FINDINGS 2b1a300a…
FINGERPRINTS (producción D-2)= INPUT_CONFIG 3c8b0036… · GRAPH_SNAPSHOT 88f15b69… · FINDINGS fdc29721…
HUMAN_FINAL_AUTHORITY        = REQUIRED
PRODUCTION_ENABLEMENT        = NOT_ENABLED
REGULATORY_COMPLIANCE        = NOT_DETERMINED_BY_SYSTEM
```

**No se registra ninguna decisión D-6.**
