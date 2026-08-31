# INFORME MAESTRO — EJECUCIÓN GMP AI FACTORY, PLAN H-1…H-10

**Fecha de cierre:** 2026-08-30 · **Autoridad:** Capa 9 = Cesar · **Capa 8:** Claude Code
**Rama:** `fix/clon-local-validacion` · **HEAD de código:** `ab40f3b` · **Entorno:** clon local
de validación en `/home/cmay/ivr-ia` (producción real en `ivr-ia:/home/ing_cpmo`).
**Sin commit, sin push, sin edición manual de ledgers gobernados.**

Este documento es **autosuficiente**: reconstruye el arco completo desde R0 y **sustituye** la
necesidad de leer los cierres parciales. Cuando dos cierres antiguos discrepan, se usa la
**evidencia ejecutada más reciente** y se marca la corrección.

---

## 1 · EXECUTIVE SUMMARY

El plan de fortalecimiento H-1…H-10 sobre el **Analizador Documental GMP** (GMP AI Factory,
`factory-api` :9000, separado del producto base `gmp-api` :8000) se ejecutó de forma
autónoma. Estado al cierre:

| Bloque | Estado |
|---|---|
| **H-1 … H-7** | ACCEPTED / PASS / CLOSED (firma humana pendiente) |
| **D-2** (firma de 3 artefactos + `analysis_coverage_mode` OBSERVE→ENFORCE) | APPROVE, registrado (`ARTIFACT_VERSION-2026-019/020`) |
| **H-8** (evidencia real de desempeño) | Instrumento **listo** · métricas reales **UNKNOWN** (falta adjudicación humana D-5) |
| **D-5** | **NOT_OCCURRED** |
| **D-3** (descargas OCR) | DONE (rapidocr + docling, offline) |
| **H-9** (benchmark de extracción, RW-0003 204 pág) | **PASS** · `RECOMMENDED_EXTRACTOR = docling` |
| **D-4** (selección de extractor) | **APPROVE · CONDITIONS_MET = YES · SELECTED = docling**, registrado (`ARTIFACT_VERSION-2026-021`) |
| **H-10** (habilitación agrupada de capacidad) | **`H10_TECHNICAL_ACCEPTANCE = PASS`** · `PRODUCTION_ACTIVATION = PENDING_HUMAN_VERIFICATION` |
| **WP-F** | `WP_F_STATUS = INCOMPLETE` (blockers humanos) |
| **D-6** (qualification) | NO preautorizado · `QUALIFIED_VERSION = NOT_ELIGIBLE_YET` |

**Lo que H-10 consiguió y que antes estaba inanido (R-5):** ingerir el SAT real RW-0003
(100 % imagen, 204 pág) con OCR docling **por lotes** (peak RSS 4.5 GB, `DOCUMENT_EGRESS=0`),
extraer **165 objetos `Test`** de sus tablas de ejecución con provenance completa, y producir
**17 aristas `tested_by`** cross-documento (URS/FS → SAT) por referencias reales (`3.2.3`,
`F05.05`). Además: `system_component=47`, `actor=13`, `refers_to=350` (deterministas,
ancladas, 0 fabricadas), sin regresión en `implemented_by` (1120) / `designed_by` (190).

**Lo que sigue bloqueado para qualification:** la adjudicación humana de H-8 (D-5) y la
verificación humana de la muestra de relaciones nuevas de H-10. Ninguna se inventa.

`NEW_REGRESSIONS = 0` · `DOCUMENT_EGRESS = 0` en todos los flujos.

---

## 2 · INTENDED USE / D-1

```
CURRENT_INTENDED_USE  = GMP_DECISION_SUPPORT_TOOL
SYSTEM_OF_RECORD      = NO
HUMAN_FINAL_AUTHORITY = REQUIRED
REGULATORY_COMPLIANCE = NOT_DETERMINED_BY_SYSTEM
PRODUCTION_ENABLEMENT = NOT_ENABLED
```

El sistema **lee y analiza** documentos técnicos/GMP contra regulación y gobernanza,
**identifica** anomalías/brechas/NCR-candidates/CAPA-candidates/change-control-candidates,
**genera** un informe de hallazgos con evidencia anclada del documento original y **genera**
una versión corregida como **borrador controlado — nunca aprobado automáticamente**.

Reglas GMP permanentes (no negociables): el documento original es la fuente maestra y nunca
se sobrescribe; todo hallazgo requiere evidencia anclada; sin declaración de cumplimiento
final por el sistema; sin aprobación automática de documentos; sin cierre automático de CAPA;
sin liberación de lote; la IA no sustituye a QA / Cesar / Capa 9.

D-1 queda **integrado explícitamente** en `WP_F_PAQUETE_EVIDENCIA_20260830.md` §0 y en este
informe (no "n/a").

---

## 3 · ARQUITECTURA FINAL

```
gmp-api      (:8000)  producto base GMP AI Copilot (query/RAG/audit/agents) — NO TOCADO
factory-api  (:9000)  GMP AI Factory, capas 7-9 (packs, evidence_verifier, chunked_engine,
                       estados, decisiones, gobernanza, Analizador Documental V2)
gmp-postgres / gmp-redis / aria-* / hotelbot-*  — NO TOCADOS
```

Pipeline del Analizador V2 (`factory/regulatory/validation_v2/v2_runtime.py::run_v2_pipeline`),
Tier-1 / Palanca C, **0 LLM**, determinista, bajo `network_locked()`:

```
canonical_store (extract_document: secciones, claims, tablas + [H-10] Test/SystemComponent/Actor)
   ↓ build.py  (grafo determinista por coincidencia de referencias literales)
graph_store  (nodos: requirement/regulation/document/section/claim/table/test/system_component/actor ;
              aristas: regulated_by, implemented_by, designed_by, tested_by, verifies, refers_to, contradicts, supports)
   ↓ findings  (regulatory Tier-1 + functional B6a + technical B6b v1/v2)
   ↓ H-7 coverage_mode (OBSERVE/ENFORCE) + risk.compute_risk(evidence_basis, coverage_status)
run package  (informe_hallazgos_v2.md, compliance_matrices, remediation drafts, RUN_ATTESTATION,
              graph_snapshot inmutable H-4, manifest + SHA256SUMS + package_receipt)
```

Nuevas piezas de H-10 (componentes internos, NO work packages nuevos):
`extract_document._docling_content` (OCR por lotes) · `extract_tests.extract_tests_from_tables` ·
`extract_entities.py` (NER cerrada anclada) · `build.py::_link_refers_to` + `_is_reference_list_line`.

---

## 4 · CRONOLOGÍA R0 → H-10

### 4.1 · Fase R (roadmap del Analizador — contexto)

| Fase | Estado | Resultado |
|---|---|---|
| **R0** | CLOSED | Verdad documental del analizador establecida. |
| **R1 / R1b** | CLOSED (2026-08-09) | Spec del contrato aprobada + smoke E2E ensambló punta a punta. R1.5 productizó `evaluation_profile=H2H4`; R1.6/1.7 convirtieron el pre-filtro de relevancia de rechazo-duro a señal-suave; R1.8 despacha `SUPPORTING_EVIDENCE_UNDER_REVIEW` a `human_review_queue`. |
| **R2** | CLOSED (2026-08-11) | Gate bloqueante (≥6/7 recall de JUICIO) **NO alcanzado** — 1/6 medibles `observed`. Capa semántica local (embeddings + RRF) resolvió la **recuperación** (`retrieval_recall_at_5` 4/7→7/7) pero **no el juicio** del 7B sobre evidencia parafraseada. |
| **R3 / R4 / R5** | Redefinidos bajo rumbo **Tier-1 / Palanca C** (0 LLM, determinista): automatizar sólo lo medido (eco léxico + rechazo de falsos positivos + recuperación semántica al revisor); el resto a revisión humana con cobertura declarada. R4 confirmó el techo del modelo también por dilución tabular (P4/P6, experimento directo). El plan H-1…H-10 opera sobre este Tier-1. |

### 4.2 · Fase R-0…R-5 del diseño (auditoría que produjo el plan H)

`docs_plan/DISENO_H1_H10_ACTUALIZADO_R0_R5_20260829 (1).md`. Resolvió 5 contradicciones del
diseño previo:

- **C-1/C-2 · H-3:** `finding_id` NO cambia el `findings_fingerprint` (`run_fingerprint.py`
  lo excluye). H-3 se rebaja a "cambio aditivo": campo `finding_record_id` determinista +
  adoptarlo como clave de direccionamiento; `finding_id` no se toca. Baseline `b5196a71…` estable.
- **C-3 · fork histórico:** causa reconstruida (`fork_baseline.json`:
  `stale_in_process_head_cache`, `fixed_by_commit 8c033fa`, `AUDIT_EXCEPTION-2026-002 / cesar`).
- **C-4 · identidad:** el gap real se concentra en **7 mutadores críticos** (H-1), no "casi
  todo el sistema" (`layer9.py` ya tiene identidad en 20 endpoints de gobernanza).
- **C-5 · `tested_by`/`verifies`/`refers_to`** inanidos: `build.py` crea las aristas
  (`_link_to_tests` / `verifies` línea ~211/250) pero **no había etapa de extracción de
  `Test`** (flag `V2_TEST_EXTRACTION` OFF) y **`refers_to` no se creaba** (sin builder ni
  extracción de `system_component`/`actor`). → **objetivo de H-10.**

### 4.3 · H-1 … H-10 (esta ejecución y las previas de la misión)

Ver §5 (gobernanza) y las tablas por-hito §15 y §23.

---

## 5 · GOBERNANZA D1–D6

| Gate | Estado | Mecanismo / registro |
|---|---|---|
| **D-1** intended use | GMP_DECISION_SUPPORT_TOOL · SYSTEM_OF_RECORD=NO (§2) | integrado en WP-F |
| **D-2** firma de `extraction_adequacy_thresholds.yaml` + `analysis_coverage_mode.yaml` (OBSERVE→ENFORCE) + `gxp_criticality.yaml` | **APPROVE** | `decision_store_v2.append_record` — `ARTIFACT_VERSION-2026-019` (ORIGINAL) + `-2026-020` (CORRECTION: decisor `cesar`→`Cesar` canónico del `identity_registry`). `decision_ref D-2-H7-20260830`. |
| **D-3** descarga OCRmyPDF+Tesseract / Docling | **DONE**, preautorizado | `D3_DOWNLOAD_MANIFEST_20260830.md`. Sustitución documentada: Tesseract→`rapidocr-onnxruntime` (host sin sudo). |
| **D-4** selección de extractor tras H-9 | **APPROVE · CONDITIONS_MET=YES · SELECTED=docling** | `decision_store_v2.append_record` — `ARTIFACT_VERSION-2026-021` (ORIGINAL). `decision_ref D-4-H9-20260830`. decisor `Cesar`. `provenance=NATIVE`. `validate_record: valid=True`. |
| **D-5** adjudicación humana de H-8 | **NOT_OCCURRED** (`D5_HUMAN_EVIDENCE_AVAILABLE=NO`) | Paquete listo: `PAQUETE_D5_ADJUDICACION_H8_20260830.md`. |
| **D-6** qualification | **NO PREAUTORIZADO** · `QUALIFIED_VERSION=NOT_ELIGIBLE_YET` | `PAQUETE_D6_QUALIFICATION_20260830.md`. No se registra decisión. |

**Corrección histórica:** una redacción previa de `CIERRE_H8_EVIDENCIA_REAL.md` decía
`D-5 = APPROVED`. **Normalizado** a `D5_ADJUDICATION=NOT_OCCURRED` — lo que existió fue
autorización de las *firmas* del gate, no adjudicación de *contenido* (los 40 casos QA40
siguen `PENDING`).

---

## 6 · CONTROLES GMP / 21 CFR PART 11 / ANNEX 11 / ALCOA+

- **Documento original = fuente maestra**, nunca sobrescrito (el analizador lee; el redline
  es un *borrador controlado* separado). Verificado en H-5F: montaje `:ro` del corpus.
- **Sin declaración de cumplimiento final por el sistema.** `REGULATORY_COMPLIANCE =
  NOT_DETERMINED_BY_SYSTEM` presente en todos los cierres y en el audit de cada corrida.
- **Sin aprobación automática de documentos / cierre de CAPA / liberación de lote.**
- **Evidencia anclada obligatoria:** todo `Test`/`SystemComponent`/`Actor` de H-10 lleva
  `Provenance` completa (`document_id · page · source_text · source_hash · extraction_version`).
  `build_*()` lanza `ProvenanceError` si falta. `DO_NOT_CREATE_TEST` si la fila de tabla no
  es trazable.
- **`human_gate_intact`**: en todas las corridas H-10, todos los findings quedan
  `human_state = UNREVIEWED` · `forbidden_states_present = false`.
- **H-7 ENFORCE:** `compute_risk` baja una banda (CRITICAL→HIGH→MEDIUM→LOW, suelo LOW) sólo
  si `evidence_basis == ABSENCE_DEPENDENT` AND `coverage_status ∈ {MISSING, DEGRADED}`.
  `findings_suppressed = 0` — **nunca** suprime hallazgos.

---

## 7 · IDENTIDAD Y SEPARACIÓN DE RESPONSABILIDADES

- **Capa 9 = Cesar** (autoridad). **Capa 8 = Claude Code** (ejecución técnica).
- Identidad del decisor en decisiones gobernadas: **del `identity_registry`**
  (`{Cesar, Andrea_Reviewer}`), validada por `identity_policy.validate_identity`, **no texto
  libre**. La CORRECCIÓN `ARTIFACT_VERSION-2026-020` existe precisamente para esto.
- **H-1** cerró el gap de identidad en los 7 mutadores críticos (`test_h1_identity_critical_mutators.py`).
- `factory-api` NO usa PostgreSQL/Redis; `gmp-api` SÍ (hecho confirmado en R-1b). H-5B/H-6B
  (producto base) quedan **fuera de alcance** — requieren autorización de scope Capa 9 separada.

---

## 8 · AUDIT TRAIL

- **H-2** aisló el audit trail de los tests (`conftest.py` fixture autouse; ningún test
  escribe en la cadena real).
- **Fork histórico preservado** (H-6F): `HISTORICAL_FORK_ID = FORK-2026-06-15-001`,
  `AUDIT_EXCEPTION-2026-002 = PRESERVED`, `NEW_FORKS = 0`. Nunca se reescribe el audit histórico.
- Cada `decision_store_v2.append_record` (D-2, D-4) emitió su evento `layer9_decision_recorded`
  en la cadena, `side_effects_applied=false`.
- **`AUDIT_TRAIL_CHANGED_BY_TESTS = NO`** en la regresión final.

---

## 9 · NETWORK / LOCAL-ONLY / DOCUMENT EGRESS

```
DOCUMENT_EGRESS = 0   en TODOS los flujos, MEDIDO (no declarado) por EgressReport:
  - H-9 benchmark (3 backends, 204 pág, 2x)
  - ingesta OCR de RW-0003 (docling por lotes)
  - H-10 fase aislada + salto gobernado + validación final (CONTROL/RUN1/RUN2)
  - run_v2_pipeline (network_locked interno)
EXTERNAL_LLM_API = FORBIDDEN — no usado (0 llamadas LLM; el pipeline es Palanca C determinista)
docling: enable_remote_services=False · HF_HUB_OFFLINE=1 · assets locales en _h9_assets/docling
```

**H-5F** (hardening `factory-api`): CORS allowlist `FACTORY_CORS_ALLOWED_ORIGINS` (vacío = deny,
nunca `*`); red aislada `factory_isolated` (172.29.71.0/24) + `NET_ADMIN` + `factory_egress_guard.sh`
(iptables OUTPUT DROP + allowlist Ollama gateway); montajes mínimos (`PYTHON_CODE_RW_MOUNTS=0`,
corpus/config `:ro`, sólo stores mutables RW; GMPAI input `:ro`, sólo `reports/gmpai_document_validation` RW).
Atestación: `PROCESS_LEVEL_CONTROL` (monkeypatch socket, defensa adicional) vs `NETWORK_LEVEL_CONTROL`
(sonda real a `1.1.1.1:53`/`8.8.8.8:53`); `EGRESS_GUARANTEE=FORBIDDEN` sólo si ambos ENFORCED.

---

## 10 · BACKUP / RESTORE (H-6F)

- **F-STATE backup** (`backup_factory_state.sh`): tar.zst + `MANIFEST.json` + `SHA256SUMS` +
  `SECRETS_MANIFEST.json`; `pg_dump` queda en H-6B (no aplica a `factory-api`).
- **Restore aislado** (`restore_factory_state.py --into /tmp/...`): **14/14 checks PASS**
  (SHA verificado, MANIFEST, decisiones cargables, `AUDIT_EXCEPTION-2026-002` presente,
  identity registry metadata, `SECRET_IDENTITY_KEYS_EXCLUDED`, requirement catalog,
  fork histórico preservado, `NEW_AUDIT_FORKS=0`, cadena tras restore == original,
  `GRAPH_SNAPSHOT_FINGERPRINT` coincide).
- **Secretos:** `identity_keys.yaml` guarda hashes (`key_sha256`), no plaintext; excluido del
  backup → `SECRET_BACKUP_STATUS = BLOCKED_PENDING_HUMAN_DECISION` (cuestión separada, no
  bloquea H-6F). `GOVERNED_STATE_RESTORABLE = YES` (la atribución de actor vive en
  `factory_audit.jsonl` + `decisions_v2.jsonl` en claro; las claves se re-aprovisionan por
  `identity_registry.load_registry()` + `IDENTITY_KEYS_FILE` — procedimiento gobernado existente).
- **Retención** 14 diarios / 8 semanales (lunes) / 6 mensuales (día 1), probada **sobre
  fixtures**, DRY-RUN por defecto.

---

## 11 · FINDINGS / RISK / COVERAGE (H-7 + D-2)

```
analysis_coverage_mode  = ENFORCE   (D-2, decision_ref D-2-H7-20260830)
extraction_adequacy_thresholds.yaml  = SIGNED
gxp_criticality.yaml                  = SIGNED
```

Validación D-2 (2 corridas frescas RW-6, sin monkeypatch del modo):
`findings_degraded = 78` · `findings_suppressed = 0` · `total_findings = 456` (342 reg / 90 func / 24 tech) ·
`human_gate_intact = true` · `forbidden_states_present = false`.

`compute_risk(subtype, severity, gxp_impact, *, evidence_basis, coverage_status, mode)`:
OBSERVE → `as_dict()` byte-idéntico al histórico (10 claves); ENFORCE → añade 6 claves y baja
la banda una posición sólo bajo la regla firmada. `RiskResult` es aditivo.

---

## 12 · GRAPH / PROVENANCE / FINGERPRINTS

**Los tres digests (WP-A) y su significado:**
- `INPUT_CONFIG_FINGERPRINT` = entradas (doc sha) + `source_attestation_digest` (cierre estático
  AST de imports `factory.*` desde el entrypoint) + esquemas + artefactos consumidos.
- `GRAPH_SNAPSHOT_FINGERPRINT` (H-4) = artefacto DERIVADO; **sólo topología** (node id/kind/
  document_id/label, edge src/dst/rel) — **excluye `attrs`** (que varían con PYTHONHASHSEED).
  Snapshot inmutable por `run_id` (`graph_snapshot/graph_snapshot.json`, overwrite → RuntimeError).
- `FINDINGS_FINGERPRINT` = whitelist de campos semánticos; **excluye `finding_id`** (por eso
  H-3 no lo movió).

| Escenario | INPUT_CONFIG | GRAPH_SNAPSHOT | FINDINGS |
|---|---|---|---|
| **Producción D-2** (canonical_store congelado, CON clone-drift, código HEAD) | `3c8b0036…` | `88f15b69…` | `fdc29721…` |
| Baseline OBSERVE (rollback H-7) | — | — | `b5196a71…` |
| **H-10 v2** (canonical_store_v2/graph_store_v2 ; RW-6 + RW-0003 ; código working tree ; re-extracción LIMPIA ; RUN1==RUN2) | `0de04225362a6f863617d63717e5da82a7e829a2594f95e53f8f36cd5d07598f` | `8ce23f30202991d87f6d867525306e50be1cdf191a40d57b6bd191a2d7b327f4` | `2b1a300ae26f76cbf09c6c7fac84053c7edf8603e893bcf75244e161127c834f` |

Los fingerprints v2 **no son comparables 1:1** con la baseline D-2: (a) el
`source_attestation_digest` cambió por el código nuevo de H-10; (b) `canonical_store_v2` es una
re-extracción **limpia** del clon — el store de producción arrastra *clone-drift* preexistente
(§17). La activación productiva de `+tests-v1` debe ir con re-extracción limpia del corpus.

---

## 13 · H-8 PERFORMANCE EVIDENCE

```
H8_INSTRUMENT_READY          = YES
D5_ADJUDICATION              = NOT_OCCURRED
D5_HUMAN_EVIDENCE_AVAILABLE  = NO
QA40_SAMPLE_PRECISION        = UNKNOWN     (40/40 casos label: PENDING)
REAL_RECALL                  = UNKNOWN     (0 oportunidades de detección firmadas)
REAL_SPECIFICITY             = UNKNOWN     (0 unidades negativas firmadas)
QA40_SHA (inmutable)         = 02b6d3d0b6fadb1f882c4e63b7f7421dd387268ddabe5b5f16abfa5d9d360d32
QA40_RESAMPLED               = NO
```

Instrumento construido y verificado: muestra QA40 determinista (seed=7, 40 findings EMITIDOS,
direccionada por `finding_record_id`), `real_corpus_opportunities.yaml` (oportunidades +
unidades negativas), `held_out_technical_corpus.yaml` (procedencia REG/DOM/ADV),
`metric_envelope.py` (5 campos + contaminación + Wilson). Ruta protegida
`requirement_catalog/` montada `:ro` en el runtime endurecido — el analizador no puede
modificarla (verificado: `touch … → Read-only file system`).

`score_emitted_review()` y `score_recall()` devuelven `UNKNOWN` (fail-closed) hasta que exista
la adjudicación humana. **La IA no auto-asigna** `TP`/`FP`/`COVERAGE_LIMITED`/ground truth/
oportunidad de detección/unidad negativa.

Impacto de H-10 sobre H-8: `QA40_SOURCE_UNITS_STILL_RESOLVABLE = YES` (production stores sin
cambio, `_EXT_VER` en v1); `H8_READJUDICATION_REQUIRED = NO` (sin activación y sin ground truth).

---

## 14 · H-9 EXTRACTION BENCHMARK (corrida completa, 204 páginas)

**Documento:** RW-0003 = `215115305 SCADA-PCS Misc PLC SAT3 Scanned-1.pdf` · sha `e96f67f7…` ·
**100 % imagen**. Cada backend 2× (determinism, sha256 byte a byte). Bajo `network_locked()`.

| Métrica | `current` (pdfplumber) | `ocr_rapidocr` | `docling` |
|---|---|---|---|
| source_page_fidelity | 204/204 | 204/204 | 204/204 |
| usable_text_recovery | 0 pág · 203 chars | 204 pág · 345 962 chars | 204 pág · 47 200 chars |
| sat_oq_iq_identifier_recovery | 0 | 3 (rótulos ronda) | 1 |
| insertion_false_positives | 0 | 0 | 0 |
| table_reconstruction | 0 | 0 | **199 tablas** |
| reading_order | vacío | palabras SIN espacios | **limpio + orden + campos** |
| determinism | PASS | PASS | PASS |
| runtime_s (1×) | 0.3 | 564.8 | 1 317.8 |
| peak_rss_mb | 303 | 1 069 | 9 563 |
| offline_execution | PASS | PASS | PASS |
| document_egress_bytes | 0 | 0 | 0 |

```
H9 = PASS
RECOMMENDED_EXTRACTOR = docling
```
Selección por el **orden de prioridad de la misión** (no popularidad): criterios 1
(source/page fidelity) y 2 (minimización de inserción falsa) → EMPATE; criterio 3
(fidelidad tabla / orden de lectura) → **docling desempata** (199 tablas + texto con espacios
vs rapidocr 0 tablas + palabras pegadas). El sesgo "menor superficie de validación → rapidocr"
sólo aplica ante empate, y en el criterio 3 no hay empate.

---

## 15 · H-10 FINAL CAPABILITY

**`H10_TECHNICAL_ACCEPTANCE = PASS`** · `PRODUCTION_ACTIVATION = PENDING_HUMAN_VERIFICATION`.

### 15.1 · Checklist de acceptance original (misión §13)

| Criterio | Resultado |
|---|---|
| docling SAT ingest **safely** | RW-0003, docling por lotes de 24 pág + `gc`: **peak RSS 4 475 MB** · 1 222 s · `DOCUMENT_EGRESS=0` · contenedores BD intactos |
| Test extraction from real SAT evidence | **165 `Test`** de tablas de ejecución, provenance completa |
| `tested_by > 0` | **17** (RW-0006→RW-0003: 6 · RW-0005→RW-0003: 11 · via `3.2.3`, `F05.05`) |
| `verifies > 0` where applicable | **0 — N/A**: el SAT cita refs de proyecto/función, no ids del catálogo regulatorio; la traza a regulación va por la cadena `tested_by`+`implemented_by`+`regulated_by` |
| `implemented_by` regression | **0** (1120→1120) |
| `designed_by` regression | **0** (190→190) |
| `refers_to` backed by real nodes/evidence | **350** · 100 % a `system_component`/`actor` real · 100 % con ancla · 0 dangling · edge-source-claims 100 % sustantivas |
| table semantics preserved/validated | RW-6: 97 tablas con rol (preservado) · RW-0003: 194/199 con rol determinista |
| canonical drift explained | `PREEXISTING_CLONE_DRIFT` (§17) — no causado por H-10 |
| fabricated tests / edges / evidence | **0 / 0 / 0** |
| deterministic runs | **PASS** (RUN1==RUN2: 3 fingerprints + todos los conteos) |
| `DOCUMENT_EGRESS = 0` | medido |
| `rollback = PASS` | v1 byte-idéntico · `_EXT_VER`/`_CANON` sin tocar · flag OFF reproduce v1 |
| `NEW_REGRESSIONS = 0` | sí (§16) |

### 15.2 · Cifras

```
EXTRACTION_VERSION_BEFORE = canonical-v1-2026-08
EXTRACTION_VERSION_AFTER  = canonical-v1-2026-08+tests-v1   (materializado en canonical_store_v2/ + graph_store_v2/)
OCR_EXTRACTOR             = docling (por lotes de 24 pág, offline)
TEST_OBJECTS_RW0003            = 165        TEST_NODES_TOTAL (RW-6+RW-0003) = 166
TESTS_WITH_REQUIREMENT_REF     = 3          TESTS_WITHOUT_REQUIREMENT_REF   = 162
TESTED_BY = 17   VERIFIES = 0 (N/A)   REFERS_TO = 350   SYSTEM_COMPONENT = 47   ACTOR = 13
IMPLEMENTED_BY 1120→1120     DESIGNED_BY 190→190     CONTRADICTS 0→0 (no modificado)
FABRICATED_TESTS/EDGES/EVIDENCE = 0/0/0    DETERMINISTIC_RUNS = PASS    DOCUMENT_EGRESS = 0    ROLLBACK = PASS
FINDINGS_TOTAL = 456 (RW-6) → 674 (RW-6 + RW-0003)
INPUT_CONFIG_FINGERPRINT   = 0de04225362a6f863617d63717e5da82a7e829a2594f95e53f8f36cd5d07598f
GRAPH_SNAPSHOT_FINGERPRINT = 8ce23f30202991d87f6d867525306e50be1cdf191a40d57b6bd191a2d7b327f4
FINDINGS_FINGERPRINT       = 2b1a300ae26f76cbf09c6c7fac84053c7edf8603e893bcf75244e161127c834f
H10_HUMAN_SAMPLE_VERIFICATION = PENDING   (H10_NEW_RELATIONS_SAMPLE_FOR_HUMAN.json, 77 filas: 17 tested_by + 60 refers_to)
```

### 15.3 · Muestra de aristas nuevas (extracto — completa en el JSON)

```
[tested_by] claim[RW-0006] '3.2.3 The Equipment shall have critical alarms…'  -->  test[RW-0003] 'UR3.2.3 …'   via=3.2.3   (page 192, source_hash 8b054b04…)
[tested_by] claim[RW-0005] 'screen, accessible by Admin and Maintenance personnel'  -->  test[RW-0003] 'F05.05: Input State and Simulation Review Screen'  via=F05.05  (page 157/158)
[refers_to] claim[RW-0005] '…ControlLogix 5580 Controller…'  -->  system_component 'ControlLogix'   (mención literal, diccionario cerrado)
```

---

## 16 · REGRESSION HISTORY

| Fecha / hito | PASSED | FAILED | SKIPPED | XFAILED | NEW_REGRESSIONS |
|---|---|---|---|---|---|
| D-2 / H-7 close | 2995 | 8 | 79 | 1 | 0 (vs baseline 9-EXC) |
| H-10 v1 (flag + refers_to inanido) | 2998 | 6 | 79 | 1 | 0 |
| **H-10 final (RW-0003 SAT, tested_by=17)** | **3002** | **6** | **79** | **1** | **0** |

Los 3 fallos de entorno extra en la corrida de D-2 (`test_governance_ui_deploy_consistency_live`,
`test_new_managers::test_passing_tests` / `test_failing_tests`) pasaron en las corridas
posteriores — intermitentes por dependencia de servicio en vivo. La composición **estable** de
fallos es: **2 de entorno + 4 guards de ledger sin commit**.

---

## 16-BIS · VALIDACIÓN R-PAR — PARIDAD E IMPACTO ANALÍTICO V1↔V2

**Fecha:** 2026-08-31 · **Tipo:** validación READ-ONLY. Detalle completo:
`docs_plan/R_PAR_DELTA_V1_V2_20260831.md`. Evidencia cruda: `docs_plan/_r_par/R_PAR_RAW.json`
+ `docs_plan/_r_par/findings_{A,B,C,D}.json`. Script: `factory/scripts/ops/r_par_delta_v1_v2.py`.
Ningún store real modificado. Corpus de paridad (6 docs): RW-0005/0006/0009/0011/0012/0014.
`SAME_CURRENT_HEAD=YES · SAME_GOVERNED_CONFIG=YES · SAME_COVERAGE_MODE=ENFORCE · SAME_REQUIREMENT_CATALOG=YES · SAME_RISK_CONFIG=YES`.

### 16-BIS.1 · Los cuatro escenarios

| Esc. | Descripción | findings | GRAPH_SNAPSHOT_FP | FINDINGS_FP | DETERMINISTIC | DOCUMENT_EGRESS |
|---|---|---|---|---|---|---|
| **A** | V1 PROD STATE (canonical de producción + código HEAD, corrida fresca) | **456** | `88f15b69bf2cea9a09d5a179300496d3685b18c58c1adb1dfa601f191b73ae05` | `fdc29721e9566dfea6f4969c74c2324f348fc00827ccbd36e35730deb512f08d` | YES | 0 |
| **B** | V1 CLEAN (re-extracción fresca HEAD, `V2_TEST_EXTRACTION=OFF`) | **456** | `2fdda0e2ce513bc48b54038c5890a0b060e87a6e5c0d6d98b3d31fb149be3620` | `926986c5f17c9bfb223522d295c53fb335964f9f8f951b612aa7044ba1d6d847` | YES | 0 |
| **C** | H10 CLEAN (re-extracción fresca HEAD, `V2_TEST_EXTRACTION=ON`, sin RW-0003) | **457** | `547157d6447fbefa3ccffdde3d809d57266c2e90cc20d0a12d748fbbed2d7732` | `ec4c5a7dd39cac9a35baa2961469687ecdfd537b8fcceef86b10b9755c0d9cb3` | YES | 0 |
| **D** | H10 + RW-0003 SAT (C + RW-0003 canonical ingerido determinista) | **674** | `8ce23f30202991d87f6d867525306e50be1cdf191a40d57b6bd191a2d7b327f4` | `2b1a300ae26f76cbf09c6c7fac84053c7edf8603e893bcf75244e161127c834f` | YES | 0 |

`INPUT_CONFIG_FINGERPRINT` A = B = C = `f5ed21cf…` (sólo depende de sha de PDFs + código +
`_EXT_VER` literal; no ve el contenido del canonical). D = `0de04225…` (añade un documento).

**Reconciliación con D-2:** el escenario **A** (canonical de producción + código HEAD) reproduce
**EXACTAMENTE** los fingerprints de la baseline D-2 (`GRAPH_SNAPSHOT 88f15b69…` ·
`FINDINGS fdc29721…`). → La baseline D-2 **no estaba obsoleta**: es lo que el HEAD produce
sobre el `canonical_store` de producción. Toda la diferencia D-2 ↔ H-10-v2 se descompone
limpiamente en **A→B (clone-drift) + B→C (H-10 puro) + C→D (RW-0003)**.

### 16-BIS.2 · A→B — CLONE DRIFT

```
CLONE_DRIFT_CHARACTERIZED = YES
MATERIAL_REGRESSION       = NO
UNEXPLAINED               = 0
```

- Localización: **100 % en RW-0012**. `production claims = 595` · `clean claims = 258`. Los
  otros 5 documentos tienen claims idénticos en A y B.
- Efecto: `findings reanchored = 35` (todas RW-0012, pág 5; 34 `REGULATORY_INCONCLUSIVE` +
  1 `ALCOA_ATTRIBUTABLE_GAP`, **las 35 band HIGH**). `n_A = n_B = 456` (conteo total idéntico).
  `matched_by_finding_record_id = 418` · `matched_by_semantic_fallback = 3` ·
  `in_both_band_changed = 0` · `evidence_basis_changed = 0` · `coverage_status_changed = 0`.
- **Reconciliación de las dos cifras — `findings reanchored = 35` vs `CLONE_DRIFT classifications = 38`:**
  la clasificación de desaparición se hace **primero por `finding_record_id`**: 38 findings de
  A no emparejan por `finding_record_id` con ninguno de B → los 38 se clasifican `CLONE_DRIFT`
  (RW-0012 prod tiene más claims, con páginas fantasma 17/18 y sobre-segmentación de la pág 5,
  que anclan las mismas conclusiones en claims distintos). **Después** se aplica un fallback
  semántico conservador (document + class/subtype + criterion + requirement_id + source_hash):
  **3** de esos 38 sí emparejan semánticamente con findings de B → quedan **35** verdaderamente
  "sólo en A". Las dos cifras describen el mismo fenómeno en dos etapas: **38 = sin emparejar
  por id ; 35 = sin emparejar ni por id ni por semántica**. No son contradictorias; `38 − 3 = 35`.
  Ninguna quedó `UNEXPLAINED`.
- Interpretación: **re-anclaje de provenance sobre la pág 5 de RW-0012, no divergencia
  analítica.** Mismo número, mismo documento, misma familia de subtipos, misma banda. Al menos
  1 finding de A está anclado en la **pág 18 inexistente** — la ruta LIMPIA es más correcta.

### 16-BIS.3 · B→C — EFECTO PURO DE H-10

```
+1  TEST_WITHOUT_REQUIREMENT   (RW-0009, band LOW, evidence_basis=ABSENCE_DEPENDENT,
                                coverage_status=MISSING, anclado, source_hash real — legítimo)
+348 refers_to
+45  system_component
+13  actor
+1   Test

removed_findings          = 0
material_changed_findings  = 0   (band_changed=0 · evidence_basis_changed=0 · coverage_status_changed=0)
implemented_by             = 1120 -> 1120
designed_by                = 190  -> 190
contradicts / supports     = 0 / —  (NO modificados)
tables con rol semántico   = 97 -> 97 (idéntico)

H10_EFFECT               = ADDITIVE_ON_SHARED_CORPUS
H10_MATERIAL_REGRESSION  = NO
```

El clone-drift (§16-BIS.2, sólo RW-0012 pág 5) y el efecto H-10 (aditivo, no toca RW-0012)
están **completamente separados**.

### 16-BIS.4 · C→D — EFECTO DE RW-0003 (SAT real)

```
+165 Test
+17  tested_by       (RW-0006→RW-0003: 6 · RW-0005→RW-0003: 11 · via refs reales 3.2.3 y F05.05)
+199 tables          (docling)
194  tables with semantic roles

REQUIREMENT_NOT_TESTED resolved = 2     (RW-0006 : 70 -> 68 sólo-RW-6 ; los casos SAT trazan a 2 requisitos URS)
REGULATORY_INCONCLUSIVE added  = 57     (band HIGH ; RW-0003 pasa de NOT_ANALYZABLE a analizado)
TEST_WITHOUT_REQUIREMENT added = 162    (band LOW ; casos SAT sin id de requisito recuperable en el OCR)
ACTIONABLE_NOW delta           = +8     (30 -> 38)
band_changed                   = 0
ORPHAN_DESIGN_ELEMENT          = 8 -> 8 (sin cambio)
VERIFIES_ADDED                 = 0      (N/A: el SAT no cita ids del catálogo regulatorio)
REFERS_TO_ADDED                = 2

only_in_D = 219 findings (TODAS en RW-0003 : 57 REGULATORY_INCONCLUSIVE + 162 TEST_WITHOUT_REQUIREMENT)
only_in_C = 2   findings (los REQUIREMENT_NOT_TESTED de RW-0006 RESUELTOS)
```

**Clasificación obligatoria (no llamar "mejora" al simple aumento de findings):**

| Categoría | Cantidad | Qué es |
|---|---|---|
| `RESOLVED_FINDINGS` | **2** | `REQUIREMENT_NOT_TESTED` de RW-0006 que dejan de emitirse porque el SAT real aporta casos de prueba trazables a esos requisitos (`tested_by` via `3.2.3` / `F05.05`) |
| `NEW_EVIDENCE_VISIBILITY` | **162** | `TEST_WITHOUT_REQUIREMENT` — casos SAT reales que el analizador ahora HACE VISIBLES por primera vez, sin traza recuperable (límite OCR o el SAT referencia tags/funciones). **RR-1: requiere juicio humano.** |
| `NEW_FINDINGS` | **57** | `REGULATORY_INCONCLUSIVE` sobre RW-0003 — cobertura Tier-1 extendida a un documento antes NO analizado |

### 16-BIS.5 · Conclusión de mejora (formalizada, separada)

```
EXTRACTION_IMPROVEMENT   = DEMONSTRATED
   sustento: RW-0003 (SAT real 100% imagen) : 204/204 páginas procesadas · 199 tablas · 194 con roles ·
             DOCUMENT_EGRESS=0. Para RW-6 la extracción NO cambia (B ≡ C en claims/tablas/secciones).

TRACEABILITY_IMPROVEMENT = DEMONSTRATED
   sustento: de 0 aristas tested_by en toda la historia del corpus a 165 Test + 17 tested_by
             cross-documento (URS/FS → SAT) por referencias reales · 2 REQUIREMENT_NOT_TESTED resueltos.

ANALYSIS_IMPROVEMENT     = DEMONSTRATED_WITH_LIMITATIONS
   sustento: -2 REQUIREMENT_NOT_TESTED · +8 ACTIONABLE_NOW · 0 findings materiales eliminados por H-10 ·
             0 regresiones de banda de riesgo.
   LÍMITE EXPLÍCITO:  QA40 precision = UNKNOWN · REAL_RECALL = UNKNOWN · REAL_SPECIFICITY = UNKNOWN.
                      NO se afirma mejora de precisión/recall hasta D-5.

REPORTING_IMPROVEMENT    = EVIDENCE_AVAILABLE
   sustento: provenance al 100% (ancla + página + source_hash) en A/B/C/D ; mismos artefactos en los 4 ;
             D muestra la nueva trazabilidad (tested_by, Test, tablas con rol) y las colas
             ACTIONABLE_NOW / BLOCKED_BY_COVERAGE_OR_EVIDENCE con by_reason íntegro.
```

### 16-BIS.6 · RR-1 — no sobreinterpretar 3/165

```
TEST_OBJECTS_RW0003                          = 165
TESTS_WITH_EXPLICIT_REQUIREMENT_REF          = 3
TESTED_BY                                    = 17
EXPLICIT_TEST_REQUIREMENT_REFERENCE_RECOVERY = 3/165
TEST_TRACEABILITY_COVERAGE                   = NO SE DECLARA  (el denominador 165 = casos recuperados por
                                              OCR, no el nº real de casos ni el nº que debería trazar)
INTERPRETATION_REQUIRES_HUMAN_REVIEW         = YES
```

### 16-BIS.7 · Conclusiones R-PAR

```
V1_V2_PARITY_CHARACTERIZED           = YES
CLONE_DRIFT_CHARACTERIZED            = YES
H10_EFFECT_CHARACTERIZED             = YES
RW0003_ANALYTIC_EFFECT_CHARACTERIZED = YES
H10_MATERIAL_REGRESSION              = NO
UNEXPLAINED_DELTAS                   = 0
ALL_MATERIAL_DELTAS_EXPLAINED        = YES
READY_FOR_HUMAN_E2_E3_REVIEW         = YES
R_PAR                                = PASS
```

---

## 17 · HISTORICAL ACCEPTED EXCEPTIONS

**Baseline 9-EXC** (post-D-2):

```
EXC-1..5 (entorno / servicios en vivo — intermitentes):
  test_corpus_runner::test_plan_corpus_units_real_reproduce_d4a_232_llamadas         [presente en la corrida final]
  test_mission_evidence_readers::test_deployment_exists_and_health                   [presente]
  test_governance_ui_deploy_consistency_live::test_deploy_freshness_all_source_routes_are_live  [pasó en la final]
  test_new_managers::TestTestExecutionManager::test_passing_tests                    [pasó en la final]
  test_new_managers::TestTestExecutionManager::test_failing_tests                    [pasó en la final]
EXC-6..9 (LEDGER_GUARD_FAILURES — store == git HEAD ; AUTO-CLEAR al commitear ; ahora 3 registros: D-2 x2 + D-4):
  test_artifact_version_signing::test_no_test_in_this_file_wrote_to_the_real_store
  test_governance_endpoints::test_the_two_stores_stayed_independent
  test_governance_signature_flow_g21::test_n13_no_test_in_this_file_touched_the_real_store
  test_resignature_g2prime::test_no_test_in_this_file_wrote_to_the_real_store
```

**Clone-drift preexistente** (independiente de esta misión) — `CIERRE_H10_DRIFT_CANONICAL_20260830.md`:

```
CLASSIFICATION = PREEXISTING_CLONE_DRIFT
RW-0012 producción = 595 claims  vs  re-extracción HEAD (flag OFF) = 258  vs  H-10 v2 = 258
  same PDF sha (de7b70c2…), same extraction_version, same code path.
  fresh ⊂ prod (only_fresh=0). prod tiene páginas fantasma 17/18 (doc = 14 pág) y sobre-segmenta la pág 5.
NEW_REGRESSION = NO   (no causado por H-10 ; el código HEAD flag-OFF reproduce el 258)
CANONICAL_DRIFT_EXPLAINED = YES
```

---

## 18 · OPEN DEVIATIONS

```
DEV-1  H-8 sin ground truth humano (D-5 NOT_OCCURRED). Métricas reales = UNKNOWN. No falsificable.
DEV-2  H-10 VERIFIES=0: el SAT cita refs de proyecto/función, no ids del catálogo regulatorio. N/A.
DEV-3  H-10 TESTS_WITHOUT_REQUIREMENT_REF=162: casos reales del SAT sin id de requisito recuperable
       en el OCR -> Test creado (evidencia real), sin arista de traza. No es fabricación.
DEV-4  H-10 refers_to (350): ancla de nodo de algunas entidades es una línea de lista de referencias;
       se prefiere prosa (_is_citation_anchor). Las ARISTAS parten 100% de claims sustantivas.
       -> H10_HUMAN_SAMPLE_VERIFICATION=PENDING.
DEV-5  LEDGER_UNCOMMITTED=YES (D-2 x2 + D-4). Los 4 guards store==git-HEAD fallan. AUTO-CLEAR al commitear.
DEV-6  Sustitución D-3: OCRmyPDF+Tesseract -> rapidocr-onnxruntime (host sin sudo). Documentada.
DEV-7  D-4 selecciona docling (footprint ~9.3 GB single-shot). H-10 ingirió POR LOTES (peak 4.5 GB) sin riesgo.
DEV-8  Clone-drift preexistente en canonical_store de producción (§17). No causado por H-10.
DEV-9  Actor/SystemComponent: el store admite objetos sin provenance (compat. histórica); los
       EXTRAÍDOS por extract_entities SIEMPRE la llevan (build_* la exige).
DEV-10 SECRET_BACKUP_STATUS = BLOCKED_PENDING_HUMAN_DECISION (H-6F, cuestión separada; no bloquea nada de H-1…H-10).
```

### RIESGOS RESIDUALES (R-PAR)

```
RR-1  EXPLICIT_TEST_REQUIREMENT_REFERENCE_RECOVERY = 3/165. El denominador (casos SAT recuperados
      por OCR) requiere interpretación humana antes de convertirse en cualquier métrica de
      cobertura de trazabilidad. INTERPRETATION_REQUIRES_HUMAN_REVIEW = YES.
RR-2  El canonical CLEAN (re-extracción HEAD) difiere del canonical de producción histórico
      (RW-0012: 258 vs 595 claims). La activación de +tests-v1 debe basarse en el canonical
      LIMPIO, no en un parche sobre el store con drift. La ruta limpia es más correcta
      (ancla en páginas reales; el store de producción ancla parcialmente en la pág 18 inexistente).
RR-3  verifies = 0 es ESTRUCTURAL para este SAT: referencia requisitos de proyecto (3.2.3) y
      funciones (F05.05), no ids del catálogo regulatorio. No es una carencia del pipeline.
RR-4  H-5B / H-6B (producto base: gmp-api / PostgreSQL / Redis) quedan FUERA DE ALCANCE —
      requieren autorización de scope de Capa 9 separada.
RR-5  Backup cifrado de secretos pendiente de decisión humana (DEV-10 / H-6F).
```

---

## 19 · QUALIFICATION BLOCKERS Y BLOCKERS DE ACTIVACIÓN (separados)

**No mezclar activación con qualification.**

### 19.1 · Activación v2 (flip de `_EXT_VER`/`_CANON`)

```
E1  Verificar la muestra H-10 de 77 relaciones (H10_NEW_RELATIONS_SAMPLE_FOR_HUMAN.json:
    17 tested_by + 60 refers_to). H10_HUMAN_SAMPLE_VERIFICATION = PENDING.
E2  Revisar y aceptar R-PAR (docs_plan/R_PAR_DELTA_V1_V2_20260831.md).
E3  Aceptar el canonical CLEAN (re-extracción HEAD, materializado en canonical_store_v2/) como
    nueva base — reemplaza al store de producción con clone-drift (RR-2).
```

### 19.2 · Qualification D-6

```
E4  D-5 / ground truth de H-8: adjudicar y firmar QA40 + oportunidades + unidades negativas +
    held-out. Dominante, no falsificable. (BLK-1)
E5  Firmas humanas requeridas de Capa 9 / QA sobre H-1…H-7 y D-2. (BLK-4)
E6  Commit controlado del ledger gobernado (ARTIFACT_VERSION-2026-019/020/021) y del código —
    limpia los 4 guards store==git-HEAD. (BLK-3)
```

### 19.3 · Blockers de qualification (resumen)

```
BLK-1  H8_HUMAN_GROUND_TRUTH_MISSING            — dominante, no falsificable   (E4)
BLK-2  H10_HUMAN_SAMPLE_VERIFICATION_PENDING                                    (E1)
BLK-3  LEDGER_UNCOMMITTED (D-2 x2 + D-4)        — se limpia al commitear        (E6)
BLK-4  HUMAN_SIGNATURES_PENDING (H-1…H-7, D-2)                                  (E5)
BLK-5  PRODUCTION_ACTIVATION not authorized (H-10 técnico PASS · R-PAR PASS;   (E1+E2+E3)
       _EXT_VER/_CANON sin flipar hasta verificación humana + canonical limpio)
```

### 19.4 · ESTADO DE GATES HUMANOS (2026-08-31) — según evidencia real

```
E1 = PENDING        (revisión humana de la muestra H-10 ; 77 filas ; 0 veredictos asignados ;
                     paquete listo: docs_plan/E1_H10_RELATION_REVIEW_PACKET_20260831.md)
E2 = PENDING        E3-A = PENDING        E4/D-5 = PENDING        E5 = PENDING        E6 = NOT_READY
```

| Gate | Estado | Artefacto de preparación (listo) | Qué falta |
|---|---|---|---|
| **E1** verificación de la muestra H-10 (77 relaciones) | **PENDING_HUMAN** | `docs_plan/E1_H10_RELATION_REVIEW_PACKET_20260831.md` (77 filas · flags estructurales · sin veredictos) · fuente `H10_NEW_RELATIONS_SAMPLE_FOR_HUMAN.json` (`sha f56d4bab…`) | veredicto humano por fila (`CORRECT`/`WRONG_NODE`/`SPURIOUS`/`AMBIGUOUS`) registrado por mecanismo autenticado |
| **E2** aceptación de R-PAR | **PENDING_HUMAN** | `docs_plan/R_PAR_DELTA_V1_V2_20260831.md` · `_r_par/R_PAR_RAW.json` (`sha c8d5fc22…`) | `E2_RPAR_ACCEPT = APPROVE / REJECT` (mecanismo autenticado) |
| **E3-A** aceptación de la baseline candidata `canonical-v1-2026-08+tests-v1` | **PENDING_HUMAN** | `docs_plan/CANDIDATE_BASELINE_MANIFEST_20260831.json` (DRAFT) · `docs_plan/CIERRE_H10_DRIFT_CANONICAL_20260830.md` | `E3A_CANONICAL_CLEAN_ACCEPT = APPROVE / REJECT`. NO es cutover ni production enablement. |
| **FASE 4** alineación de QA40 (caso `ADJ-34140454ec`) | **BLOCKED_UNTIL_E3A** | análisis en `PAQUETE_GATES_HUMANOS_POST_RPAR_20260831.md` §4 | sólo tras `E3A=APPROVE`; re-resolución determinista de 1/40 direccionamientos; SIN remuestreo |
| **FASE 5** freeze del candidato | **DRAFT_CREATED** | `docs_plan/CANDIDATE_BASELINE_MANIFEST_20260831.json` (`STATUS: DRAFT_PENDING_E3A_AND_QA40_ALIGNMENT`) | finalizar `qa40_finding_ids_sha256` tras FASE 4; recalcular `git_status_digest`/`git_diff_sha256` en el momento del freeze |
| **E4 / D-5** adjudicación humana de H-8 | **PENDING_HUMAN** (`D5=PENDING_HUMAN`) | `PAQUETE_D5_ADJUDICACION_H8_20260830.md` · hoja QA40 40/40 PENDING | requiere E1+E2+E3A APPROVED + QA40_ALIGNMENT=PASS + MANIFEST autoritativo ; la IA NO genera TP/FP/COVERAGE_LIMITED/ground truth |
| **E5** firmas humanas (H-1…H-7, D-2) | **PENDING_HUMAN** | mecanismo verificado: `decision_store_v2.append_record` + `identity_registry` (`{Cesar, Andrea_Reviewer}`) + `identity_policy.validate_identity` — **existe** | firma por identidad autenticada (una línea `SIGNED` en YAML NO es firma gobernada) |
| **E6** commit controlado | **NOT_READY** | `PAQUETE_GATES_HUMANOS_POST_RPAR_20260831.md` §5 (listas por categoría) | alcance definido por Capa 9 ; `.gitignore` para stores generados ; stage explícito archivo por archivo ; aprobación explícita de Capa 9 |
| **D-6** qualification | **PENDING_HUMAN** (`NOT_ELIGIBLE_YET`) | `PAQUETE_D6_QUALIFICATION_20260830.md` | requiere E1+E2+E3A+D-5+E5+E6 + post-commit regression aceptada |
| **PRODUCTION_ENABLEMENT** | **NOT_ENABLED** | — | decisión de gobernanza SEPARADA que exige `D6=QUALIFIED` ; luego cutover (flip `_EXT_VER`/`_CANON`/`_GRAPH`) + re-derivación limpia + post-cutover regression |

Ningún gate ha sido decidido por la máquina. `_EXT_VER`/`_CANON`/`_GRAPH` sin tocar.
`decisions_v2.jsonl` sin edición manual (254 líneas = HEAD 251 + los 3 registros D-2/D-4 de
misiones previas). QA40 sin tocar (40/40 PENDING, `sha 02b6d3d0…`).

---

## 20 · GIT / WORKING-TREE / LEDGER STATE

```
Rama            = fix/clon-local-validacion       HEAD = ab40f3b
COMMIT / PUSH   = NINGUNO (prohibido por la misión)
decisions_v2.jsonl = HEAD 251 líneas + 3 sin commitear:
   ARTIFACT_VERSION-2026-019  (D-2 ORIGINAL, APPROVE)
   ARTIFACT_VERSION-2026-020  (D-2 CORRECTION, seq=1, supersedes 019 — decisor 'Cesar')
   ARTIFACT_VERSION-2026-021  (D-4 ORIGINAL, APPROVE — SELECTED=docling)
   -> validate_record: valid=True (los 3)  ·  test_decision_migration (sync A/B/v2): PASS
   -> LEDGER_UNCOMMITTED = YES  (desviación conocida, NO regresión lógica)

Working tree (cambios de esta misión, sin commit):
 M factory/regulatory/canonical/model.py                +Provenance en Actor/SystemComponent ; +build_system_component / build_actor
 M factory/regulatory/canonical/extract_document.py     +_docling_content (lotes) ; +_looks_image_only ; +ocr= ; tablas docling -> Table + roles ; extract_tests_from_tables
 M factory/regulatory/canonical/extract_tests.py        +extract_tests_from_tables ; +_TABLE_REQREF_RE
 M factory/regulatory/graph/build.py                    +_link_refers_to ; +_is_reference_list_line
 ?? factory/regulatory/canonical/extract_entities.py    NUEVO
 ?? factory/tests/test_extract_entities.py              NUEVO (4)
 M factory/tests/test_graph_build_and_trace.py          +test_h10_refers_to_by_literal_entity_mention
 ?? factory/scripts/ops/h10_{test_extraction_rederivation,execute_version_jump,ingest_rw0003,final_validation}.py
 ?? factory/scripts/ops/h9_extraction_benchmark.py ; factory/scripts/ops/{factory_state_manifest,restore_factory_state,factory_backup_retention}.py
 ?? factory/regulatory/canonical_store_v2/ , graph_store_v2/   (stores del salto ; RW-6 + RW-0003)
 ?? factory/regulatory/pilot_run/h10_extraction_v2_20260830/   (paquete + muestra humana)
 (+ los cambios de H-1…H-7 / D-2 de misiones previas, ya documentados en sus cierres)

Producción intacta:
  canonical_store/RW-*  = BYTE-IDÉNTICO (md5 de árbol antes/después)
  graph_store/ (git)    = GIT-CLEAN
  contenedores gmp-api/factory-api/gmp-postgres/gmp-redis = Up, healthy
```

---

## 21 · PRODUCTION STATUS

```
PRODUCTION_ENABLEMENT   = NOT_ENABLED
PRODUCTION_ACTIVATION   = PENDING_HUMAN_VERIFICATION  (de la muestra H-10)
_EXT_VER (v2_runtime.py) = "canonical-v1-2026-08"     (NO flipado ; producción sigue en v1)
_CANON / _GRAPH (v2_runtime.py) = factory/regulatory/canonical_store , graph_store  (sin cambio)
analysis_coverage_mode  = ENFORCE  (D-2 ; efectivo en producción)
El extractor de producción sigue siendo pdfplumber (extract_document con ocr=None por defecto).
```

---

## 22 · ROLLBACK STRATEGY

| Cambio | Rollback |
|---|---|
| D-2 (ENFORCE) | poner `mode: OBSERVE` en `analysis_coverage_mode.yaml` → `FINDINGS_FINGERPRINT` vuelve a `b5196a71…` sin cambio de código |
| D-4 / H-10 salto | **no requiere acción** — `_EXT_VER`/`_CANON` nunca se flipó ; `canonical_store/` + `graph_store/` v1 byte-idénticos ; `canonical_store_v2/` es adicional (borrarlo no afecta a producción) |
| `V2_TEST_EXTRACTION` | OFF por defecto → ruta v1 ; CONTROL del harness reproduce `implemented_by`/`designed_by` idénticos, 0 test/entity/refers_to |
| Ledger (D-2/D-4) | append-only Part 11 ; se corrige por CORRECTION (como `-020`), nunca por borrado |

---

## 23 · FINAL STATUS MATRIX

| ITEM | STATUS | EVIDENCE | HUMAN_ACTION_REQUIRED |
|---|---|---|---|
| **H-1** identidad / mutadores | ACCEPTED | `test_h1_identity_critical_mutators.py` ; `CIERRE_H1_H2_H3_20260829.md` | firma Capa 9 / QA |
| **H-2** audit trail aislado | ACCEPTED | `test_h2_audit_trail_isolated_from_tests.py` | firma |
| **H-2b** review_queue aislado | ACCEPTED | `test_r2_3_judgment_relabel_consistency.py` ; `CIERRE_H2B_H4_20260829.md` | firma |
| **H-3** `finding_record_id` | ACCEPTED (aditivo, sin requalification) | `test_h3_finding_record_id.py` | firma |
| **H-4** graph snapshot inmutable | ACCEPTED (`b5196a71…` estable) | `test_h4_graph_snapshot.py` ; `CIERRE_H2B_H4_20260829.md` | firma |
| **H-5F** hardening Factory | PASS | `test_h5f_hardening.py` ; `CIERRE_H5F_H6F_20260829.md` | firma ; scope H-5B pendiente |
| **H-6F** backup/restore | PASS (14/14) | `restore_factory_state.py` ; `CIERRE_H5F_H6F_20260829.md` | firma ; decisión secret-backup (DEV-10) ; scope H-6B |
| **H-7** coverage_mode gobernado | CLOSED (ENFORCE) | `CIERRE_D2_H7_ENFORCE_20260830.md` | firma |
| **D-1** intended use | DEFINED | WP-F §0 ; este informe §2 | ratificar |
| **D-2** firma 3 artefactos + ENFORCE | APPROVE (registrado) | `ARTIFACT_VERSION-2026-019/020` ; `CIERRE_D2_H7_ENFORCE_20260830.md` | commit del ledger |
| **D-3** descargas OCR | DONE | `D3_DOWNLOAD_MANIFEST_20260830.md` | — |
| **H-8** evidencia real | INSTRUMENT_READY · métricas UNKNOWN | `CIERRE_H8_EVIDENCIA_REAL.md` ; `PAQUETE_D5_ADJUDICACION_H8_20260830.md` | **D-5: adjudicar y firmar QA40 + oportunidades + negativas + held-out** |
| **D-5** adjudicación humana | **NOT_OCCURRED** | — | **realizar la adjudicación** |
| **H-9** benchmark extracción | PASS | `CIERRE_H9_BENCHMARK_EXTRACCION_20260830.md` ; `_h9_full/H9_BENCH_RESULTS_FULL.json` | — |
| **D-4** selección extractor | APPROVE · CONDITIONS_MET=YES · docling | `ARTIFACT_VERSION-2026-021` | commit del ledger |
| **H-10** capacidad | **H10_TECHNICAL_ACCEPTANCE = PASS** | `CIERRE_H10_CAPACIDAD_20260830.md` ; `H10_FINAL_VALIDATION.json` ; `H10_VERSION_JUMP_RESULT.json` | **verificar `H10_NEW_RELATIONS_SAMPLE_FOR_HUMAN.json` (77 filas)** — E1 |
| **R-PAR** paridad e impacto V1↔V2 | **PASS** | `R_PAR_DELTA_V1_V2_20260831.md` ; `_r_par/R_PAR_RAW.json` ; `_r_par/findings_{A,B,C,D}.json` | **revisar y aceptar** — E2 |
| **WP-F** | INCOMPLETE | `WP_F_PAQUETE_EVIDENCIA_20260830.md` | resolver BLK-1..5 |
| **D-6** qualification | NOT_APPROVED · NOT_ELIGIBLE_YET | `PAQUETE_D6_QUALIFICATION_20260830.md` | decisión humana tras E4 (D-5) + E1 (muestra H-10) |
| **PRODUCTION ACTIVATION** | PENDING_HUMAN_VERIFICATION (E1 + E2 + E3) | `_EXT_VER`/`_CANON` sin flipar | verificar muestra H-10 (E1) + aceptar R-PAR (E2) + aceptar canonical limpio (E3) |
| **QUALIFICATION** | BLOCKED · NOT_ELIGIBLE_YET | blockers BLK-1..5 | E4 (D-5) + E1 (muestra H-10) + E6 (commit ledger) + E5 (firmas) |

### Flags de estado final

```
H1-H7                                = ACCEPTED / PASS / CLOSED
D1                                   = DEFINED
D2                                   = APPROVED
D3                                   = DONE
H8                                   = INSTRUMENT_READY / HUMAN_GROUND_TRUTH_MISSING
D5                                   = NOT_OCCURRED
H9                                   = PASS
D4                                   = APPROVED
H10_TECHNICAL_ACCEPTANCE             = PASS
R_PAR                                = PASS
WP_F                                 = INCOMPLETE
D6                                   = NOT_ELIGIBLE_YET

V1_V2_PARITY_CHARACTERIZED           = YES
H10_MATERIAL_REGRESSION              = NO
RW0003_ANALYTIC_EFFECT_CHARACTERIZED = YES
ALL_MATERIAL_DELTAS_EXPLAINED        = YES

EXTRACTION_IMPROVEMENT               = DEMONSTRATED
TRACEABILITY_IMPROVEMENT             = DEMONSTRATED
ANALYSIS_IMPROVEMENT                 = DEMONSTRATED_WITH_LIMITATIONS   (QA40 precision / REAL_RECALL / REAL_SPECIFICITY = UNKNOWN hasta D-5)
REPORTING_IMPROVEMENT                = EVIDENCE_AVAILABLE
```

---

## 24 · EXACT NEXT HUMAN ACTIONS

```
1. D-5 — adjudicar y firmar (host, fuera del contenedor; el runtime los ve :ro):
   factory/regulatory/requirement_catalog/qa40_adjudication_sheet.yaml       (40 casos -> TP/FP/COVERAGE_LIMITED + ancla + tag)
   factory/regulatory/requirement_catalog/real_corpus_opportunities.yaml     (oportunidades de detección + unidades negativas)
   factory/regulatory/requirement_catalog/held_out_technical_corpus.yaml     (firma + rules_author)
   -> luego la máquina calcula QA40_SAMPLE_PRECISION / REAL_RECALL / REAL_SPECIFICITY con metric_envelope.

2. H-10 — verificar la muestra:
   factory/regulatory/pilot_run/h10_extraction_v2_20260830/H10_NEW_RELATIONS_SAMPLE_FOR_HUMAN.json
   (77 filas: 17 tested_by + 60 refers_to; fijar HUMAN_VERIFIED / HUMAN_VERDICT / HUMAN_NOTE).

3. Si (2) se acepta -> activación gobernada de canonical-v1-2026-08+tests-v1:
   - flip de _EXT_VER y _CANON/_GRAPH en factory/regulatory/validation_v2/v2_runtime.py
   - re-extracción LIMPIA del corpus completo con el código HEAD (ya materializada en canonical_store_v2/)
   - registrar la nueva baseline de los 3 fingerprints.

4. Commit del ledger gobernado (ARTIFACT_VERSION-2026-019/020/021) -> limpia los 4 guards store==git-HEAD.

5. Firmas humanas de Capa 9 / QA sobre H-1…H-7 y D-2.

6. D-6 — decisión humana de qualification (hoy NOT_ELIGIBLE_YET).

7. (Fuera del plan H) H-5B / H-6B: autorización de scope Capa 9 para el producto base (PostgreSQL/Redis).
   DEV-10: decisión sobre mecanismo de backup cifrado de secretos.
```

---

## CLAIMS THAT MUST NOT BE MADE

```
QA_APPROVED            = NO
QUALIFIED              = NO
RELEASED               = NO
CAPA_CLOSED            = NO
FINAL_GMP_APPROVAL     = NO
PRODUCTION_ENABLEMENT  = NOT_ENABLED
REGULATORY_COMPLIANCE  = NOT_DETERMINED_BY_SYSTEM
```

Siguen aplicando **todas**. `H10_TECHNICAL_ACCEPTANCE = PASS` es una afirmación **técnica y
determinista**, NO una declaración de qualification ni de cumplimiento regulatorio. La
adjudicación humana de H-8 (D-5) no ocurrió; sin ella no hay métricas de desempeño reales y
no hay qualification.

---

## FINAL_MACHINE_VERIFICATION

Comprobación cruzada (2026-08-31) contra: `_r_par/R_PAR_RAW.json` · `_r_par/findings_{A,B,C,D}.json` ·
`_h9_full/H10_FINAL_VALIDATION.json` · `H10_VERSION_JUMP_RESULT.json` · `_h9_full/H10_RW0003_INGEST.json` ·
`_h9_full/final_regression_h10b.log` · `qa40_adjudication_sheet.yaml` · `decisions_v2.jsonl`.

```
REPORT_INTERNAL_CONSISTENCY        = PASS
ARTIFACT_REFERENCES_RESOLVABLE     = PASS   (todos los archivos citados existen)
FINAL_METRICS_MATCH_SOURCE_ARTIFACTS   = PASS
   TESTED_BY=17, REFERS_TO=350, TEST_OBJECTS_RW0003=165, SYSTEM_COMPONENT=47, ACTOR=13,
   IMPLEMENTED_BY=1120, DESIGNED_BY=190  == H10_FINAL_VALIDATION.json / H10_VERSION_JUMP_RESULT.json
   RW-0003 ingesta: peak_rss 4475 MB · DOCUMENT_EGRESS 0  == H10_RW0003_INGEST.json
   NEW_REGRESSIONS=0 ; PASSED=3002 / FAILED=6 / SKIPPED=79 / XFAILED=1  == _h9_full/final_regression_h10b.log
   QA40_SHA=02b6d3d0… ; QA40 40/40 PENDING (SIN TOCAR)  == qa40_adjudication_sheet.yaml
FINAL_FINGERPRINTS_MATCH_SOURCE_ARTIFACTS = PASS
   INPUT_CONFIG=0de04225… ; GRAPH_SNAPSHOT=8ce23f30… ; FINDINGS=2b1a300a…  == H10_VERSION_JUMP_RESULT.json (run1 == run2)
   producción D-2: 3c8b0036… / 88f15b69… / fdc29721…  == CIERRE_D2_H7_ENFORCE_20260830.md
R_PAR_VALUES_MATCH_RAW             = PASS
   A/B/C/D findings = 456/456/457/674  == R_PAR_RAW.json
   A GRAPH=88f15b69… A FINDINGS=fdc29721…  (reproducen la baseline D-2)
   B GRAPH=2fdda0e2… B FINDINGS=926986c5… · C GRAPH=547157d6… C FINDINGS=ec4c5a7d… · D GRAPH=8ce23f30… D FINDINGS=2b1a300a…
   DETERMINISTIC A/B/C/D = YES · DOCUMENT_EGRESS A/B/C/D = 0
   A↔B: only_in_A=35 · CLONE_DRIFT classifications=38 (38−3 fallback semántico=35) · UNEXPLAINED=0
   B↔C: only_in_C=1 · refers_to 0→348 · implemented_by/designed_by sin cambio
   C↔D: tested_by +17 · Test +165 · REQUIREMENT_NOT_TESTED resueltos=2 · REGULATORY_INCONCLUSIVE +57 ·
        TEST_WITHOUT_REQUIREMENT +162 · ACTIONABLE_NOW +8 · band_changed=0
CONTRADICTIONS_REMAINING           = NONE
   Corrección histórica aplicada:
     HISTORICAL_STATEMENT   = "D-5 = APPROVED" (CIERRE_H8_EVIDENCIA_REAL.md, redacción previa)
     CORRECTED_FINAL_STATEMENT = "D5_ADJUDICATION = NOT_OCCURRED ; D5_HUMAN_EVIDENCE_AVAILABLE = NO"
     EVIDENCE = qa40 40/40 PENDING ; opportunities [] ; held_out DRAFT_UNSIGNED ; score_* -> UNKNOWN
   Corrección histórica aplicada:
     HISTORICAL_STATEMENT   = "H10 = PARTIAL / tested_by = 0 no alcanzable en el corpus" (CIERRE_H10 previo)
     CORRECTED_FINAL_STATEMENT = "H10_TECHNICAL_ACCEPTANCE = PASS ; tested_by = 17 con SAT real RW-0003 ingerido por lotes"
     EVIDENCE = H10_FINAL_VALIDATION.json ; H10_RW0003_INGEST.json ; H10_VERSION_JUMP_RESULT.json
   Reconciliación R-PAR:
     HISTORICAL_STATEMENT   = "los fingerprints v2 no son comparables con la baseline D-2" (CIERRE_H10)
     CORRECTED_FINAL_STATEMENT = "la baseline D-2 = escenario A (canonical de producción + HEAD) ; la
                                  diferencia D-2↔v2 se descompone en A→B (clone-drift) + B→C (H-10 puro) + C→D (RW-0003)"
     EVIDENCE = R_PAR_RAW.json (A GRAPH=88f15b69… A FINDINGS=fdc29721… == baseline D-2)

TECHNICAL_VALIDATION_COMPLETE      = YES
READY_FOR_HUMAN_ACTIVATION_REVIEW  = YES
RETURN_TO_DESIGN_REQUIRED          = NO
```

R-PAR es evidencia de validación técnica. No decide activación, no ejecuta D-5, no realiza D-6.
Los blockers humanos (E1–E6) y los `CLAIMS THAT MUST NOT BE MADE` siguen en vigor sin cambio.
