# 01 — EVIDENCIAS

Anexo de evidencias de `00_REVISION_DE_CIERRE.md`. Todo verificable desde disco / git / ledger.

---

## Commits de la sesión (continuación)

```
6be0626  docs(mesa-diseno): FASE 2 CERRADA = PASS / PARKED por Capa 9 (2026-09-01)
24549a3  feat(D5/v1.2): registrar H1 APPROVE_REMEDIATION_V1_2 + D5-D2 DEFERRED (Capa 9 2026-09-01)
9d6c86f  feat(mesa-diseno): H-4 (gate de estabilidad) + prueba de recall (REFUTADA)
647b710  feat(mesa-diseno): prototipo aislado de la capa semantica + bake-off (FASE 2)
```
`HEAD == origin/fix/clon-local-validacion == 6be0626`.

---

## H1 — APPROVE_REMEDIATION_V1_2

**Mecanismo (verificado, no asumido):** `technical_completeness_rules.yaml` **no** está en
`ARTIFACT_CLASSES = (catalog, applicability_matrix, evidence_pack, prompt, golden_dataset)`
de `factory/core/artifact_version_guard.py` ni en `enumerate_artifacts()`. Por tanto:
- no hay proposal `ARTIFACT_VERSION` para él,
- no hay panel en Mission Control,
- no hay CLI `sign_artifact_version_proposal.py` aplicable.

El mecanismo válido para este gate a la medida es **metadata + commit**, idéntico al
precedente D5-A/B/C (`qa40_adjudication_sheet.yaml`, `real_corpus_opportunities.yaml`, que se
firmaron editando `status: SIGNED` / `adjudicator` en el propio YAML).

**Cambio aplicado** (`factory/regulatory/requirement_catalog/technical_completeness_rules.yaml`,
bloque `pending_approval`):
```yaml
pending_approval:
  gate: APPROVE_REMEDIATION_V1_2
  approved: true                       # <- era false
  approved_by: "Capa 9 (Cesar)"
  approved_at: "2026-09-01"
  approval_channel: "metadata + commit (sin servicio/panel de gobernanza para este artefacto -- verificado)"
  approval_authorization: "AUTORIZACION Capa 9 -- 'continuar ejecucion' 2026-09-01"
  downstream_condition: >
    D5-D2 (umbrales recall 0.90 / FP 0.05 / fabricated 0) sigue siendo CONFIRMACION
    INDEPENDIENTE OBLIGATORIA; si falla -> rollback de v1.2.
  requalification_note: >
    Cambiar este archivo dispara requalification per qualification_contract.yaml;
    CT-HELD-OUT-PENDING permanece ABIERTO.
```

---

## D5-D2 — DEFERRED / NON_BLOCKING_FOR_DEVELOPMENT

`factory/regulatory/requirement_catalog/held_out_technical_corpus.yaml`, bloque nuevo
`d5d2_gate_status`:
- `status: DEFERRED` · `classification: NON_BLOCKING_FOR_DEVELOPMENT`
- `authorized_by: "Capa 9 (Cesar)"` · `authorized_at: "2026-09-01"`
- `still_required_for: [FINAL_QUALIFICATION, "reportable_range != SYNTHETIC_ONLY", D5_FORMAL_CLOSURE]`
- `independent_author_still_required: true` (Maria Torres o autora independiente real ≠ Cesar)
- `does_not_imply`: aprobación de v1.2 sin confirmación independiente.

---

## Reversión de `decisions_v2.jsonl`

Antes de la reversión: árbol de trabajo = 266 líneas (HEAD = 255). El diff eran **11 líneas
añadidas** `ARTIFACT_VERSION-2026-022..032`, todas con `recorded_by: null` y mitad con
`approved_by_id: null` — escritas a mano, **fuera** del flujo del servicio.

Acción: `git checkout HEAD -- factory/layer9/decisions/decisions_v2.jsonl` (solo ese archivo).

Después: 255 líneas == HEAD. Preservados: **45** `PILOT_EXECUTION`, **21**
`ARTIFACT_VERSION` gobernados. Ninguna decisión gobernada perdida.

**Post-reversión, el propio Mission Control** (no Claude) escribió 4 líneas nuevas legítimas:

| instance_id | origin | by | fecha (UTC) | gate / ref |
|---|---|---|---|---|
| `ARTIFACT_VERSION-2026-022` | `agent_proposed` (`mission_control_ui`) | — | 2026-09-01T15:57:50 | E1 / `E1-3-H10-RELATIONS-20260831` |
| `ARTIFACT_VERSION-2026-023` | `human_confirmed` | Cesar (`cesar may`) | 2026-09-01T15:57:54 | E1 / `E1-3-H10-RELATIONS-20260831` |
| `ARTIFACT_VERSION-2026-024` | `agent_proposed` (`mission_control_ui`) | — | 2026-09-01T16:00:52 | E1 / `E1-ACCEPTANCE-20260831` — `e1_acceptance: PASS` |
| `ARTIFACT_VERSION-2026-025` | `human_confirmed` | Cesar (`cesar may`) | 2026-09-01T16:00:56 | E1 / `E1-ACCEPTANCE-20260831` — `e1_acceptance: PASS` |

E1-3 `verdict_set_sha256 = 4e23a1466ef12bc4286f25ba1700a768df0a794eb16a5d58c46e63d3d287bd97`
(`sample_size: 67`, counts `{CORRECT: 66, WRONG_NODE: 1, SPURIOUS: 0, AMBIGUOUS: 0}`).
E1_ACCEPTANCE `PASS`, basis "66/67 CORRECT, 0 WRONG_NODE, 0 SPURIOUS, 1 AMBIGUOUS por
truncación OCR no atribuible a H-10", `rc2: RESOLVED`, `rc3: RESOLVED`.

**Nota de consistencia:** el payload de `-024` cita en `based_on` la numeración/hash antiguos
(`ARTIFACT_VERSION-2026-030`, verdict_set `7c905e2…`) — proviene de la UI; los registros en sí
son válidos y del servicio. `docs_plan/E1_SIGNATURE_HISTORY.md` (mtime 2026-08-31) **aún no
refleja** E1-3 ni E1_ACCEPTANCE — pendiente P3.

---

## Validación v1.2 (sin regresiones en el set v1.2)

```
pytest factory/tests/test_completeness_rules_v1_2.py factory/tests/test_technical_findings.py \
       factory/tests/test_run_fingerprint.py factory/tests/test_wp_e_measurement_independence.py \
       factory/tests/test_extraction_adequacy.py
  -> 124 passed

pytest factory/tests/test_qualification_contract.py
  -> 17 passed
```
YAML de los 2 archivos editados: parsean OK. `pending_approval.approved == True`,
`d5d2_gate_status.status == DEFERRED`.

---

## Prototipo semántico (FASE 2) — evidencia

`factory/prototypes/semantic_hybrid_poc/` (13 .py). `test_poc.py` **18/18** (incluye el test
obligatorio de cita fabricada inyectada → gate R5 → `INDETERMINATE`, + H-1/H-2/H-3 + H-4).

Bake-off (gate endurecido, corrida B): schema 1.00 · 0 citas fabricadas sobreviven al gate
(20 pre-gate en la prueba de recall, 0 sobreviven) · señal útil qwen 79 % vs mistral 14 % ·
reproducibilidad baja (qwen 0.33 salida bit-idéntica) → `REPRODUCIBLE_UNDER_PINNED_CONDITIONS`,
nunca `DETERMINISTIC`.

**Prueba de red de seguridad de recall — REFUTADA:** `recall_probe.py` sobre el fixture 7P+2N,
retrieval por código a nivel documento (R9). Positivos recuperados **1/7** (solo P2, con cita
literal verificada) vs **2/7** del pipeline de juicio → la capa recupera menos. Negativos 2/2
correctos. Detalle en `docs_plan/BAKEOFF_MODELOS_SEMANTIC_POC_20260901.md` §9.

Artefactos crudos (`bakeoff_results/`, `poc_log*.jsonl`, `recall_probe_summary.json`) NO
versionados (gitignored): citan texto del store canónico y el repo es público.

---

## R2 — estado vigente (READ-ONLY)

**Fuente autoritativa:** `docs_plan/REPORTE_B4B_MEDICION_RECALL_V2.md` (2026-08-27,
`PILOT_EXECUTION-2026-032`, run `b4b-20260827T201816Z`) + su §7 (B4b no-estricta,
`PILOT_EXECUTION-2026-034`, run `b4b-nonstrict-20260827T205418Z`).

| Vía | Recall positivos | Autorización |
|---|---|---|
| Baseline Piloto 1 | 0/7 | — |
| H1 (idioma) | 0/7 | — |
| H2 / H4 (desempaquetado + schema mínimo) | **2/7** | — |
| Palanca A (qwen2.5:14b) | 2/7 | — |
| V2 fusión (top_k) | 2/7 | — |
| R2 (fusión, pool perfecto) | 1/6 | `PILOT_EXECUTION-2026-011/012` |
| **B4b — V2 completo** | **0/7** | `PILOT_EXECUTION-2026-032` (203 llamadas) |
| **B4b no-estricta** (paso B ve claims) | **0/7** | `PILOT_EXECUTION-2026-034` (205 llamadas) |

B4b: `DOCUMENT_EGRESS = 0` · `FABRICATED_CITATIONS = 0` · `REGULATORY_NEGATIVE = 2/2` ·
`SCHEMA_VALID_RATE = 100%` · subcriterios (56): 30 `EVIDENCE_NOT_FOUND` + 20 `INCONCLUSIVE`,
**0 `MACHINE_CONFIRMED` / 0 `MACHINE_PARTIAL` / 0 `MACHINE_REJECTED`**.
B4b no-estricta: 40 `INCONCLUSIVE` + 10 `EVIDENCE_NOT_FOUND`, **0 `SATISFIES` / 0 `PARTIAL`**.

**FUNCTIONAL (B8b, determinista, sin LLM):** `FUNCTIONAL_RECALL = 16/16 = 1.00` (umbral ≥ 0.90,
PASS) · `FUNCTIONAL_FALSE_POSITIVE = 0/16 = 0.00` (umbral ≤ 0.05, PASS). Fuente:
`docs_plan/REPORTE_B8B_SUITE_B_RECALL.md`, `factory/regulatory/validation_v2/defect_corpus.py`.

**Prompts de juicio V2 firmados** (Cesar 2026-08-27, `prompt_version 1.0`):
`factory/engines/gmpai_integrity/prompts/v2_draft/{step_a_neutral_description,
step_b_criterion_mapping, step_b_criterion_mapping_nonstrict, critic}.yaml`.

**Código R2:** `factory/regulatory/retrieval/{bm25,embed,embed_index,embed_runner,fusion,
indexer,query_builder,retriever,rerank,judgment,judgment_candidate_pool,evidence_bundle}.py`.
`build_fusion_candidate_pool()` = RRF (BM25 + embeddings), 1 llamada de embedding/consulta,
gobernada por `EMBED_EXECUTION`.

**PILOT_EXECUTION:** hasta `-034` (240 llamadas, `human_confirmed` por Cesar 2026-08-27).
