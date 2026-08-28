# WP-F — CONTRATO DE CUALIFICACIÓN (artefacto declarativo + checker re-ejecutable)

**Fecha:** 2026-08-28 · **Autoridad:** Capa 9 = Cesar
**Baseline de código:** `fix/clon-local-validacion` @ `ccf4d67` (WP-E cerrado).
**Motiva:** D-5. **Precondición (satisfecha):** WP-A (fingerprint) + WP-E (independencia de medición) cerrados.

---

## Qué entrega WP-F

| Componente | Ruta | Estado |
|---|---|---|
| Contrato declarativo | `factory/regulatory/requirement_catalog/qualification_contract.yaml` | **`status: DRAFT`** |
| Checker re-ejecutable | `factory/regulatory/validation_v2/qualification_contract.py` | implementado |
| Tests | `factory/tests/test_qualification_contract.py` | 17 |

El contrato liga, por caso: `intended_use → requirement → test_objective → acceptance_criterion →
FUENTE AUTORIZADA del valor esperado (cita) → test_artifact → found_value → delta → evidence
(test_artifact + timestamp) → reviewer → status`.

El checker (`run_contract()`) **re-ejecuta** cada caso, **lee** el umbral de su fuente citada,
calcula `found/expected/delta`, **reproduce** el fingerprint (WP-A) y **compara los SHA** de los
disparadores de requalification.

---

## Reglas duras (fail-closed en el loader / checker)

1. **Ningún valor esperado literal.** Un caso con `expected_value:` → el loader lanza. Solo
   `expected_value_source:` con una de estas formas:
   - `{const_module, const}` — lee una constante de código (p.ej. `gates.TECHNICAL_RECALL_MIN`).
   - `{yaml, key}` — lee una clave de un YAML del repo.
   - `{zero: true, authority: "<cita>"}` — el cero autorizado por un documento.
   - `{assertion: "<qué>", authority: "<cita>"}` — aserción estructural con autoridad.
2. **Todo nace `DRAFT`** (contrato y cada caso).
3. **El sistema NUNCA se auto-cualifica.** `qualified_version` y cualquier `QUALIFIED` los fija
   **exclusivamente un humano firmando el YAML**. `decide_overall()` solo puede devolver
   `DRAFT_BASELINE` · `GATES_MET_AS_QUALIFIED` (si status==SIGNED **y** fingerprint coincide) ·
   `FAIL_REQUALIFICATION_REQUIRED` — **nunca** `QUALIFIED` ni `COMPLIANT`.
4. **El contrato no declara cumplimiento** — solo `gates_status` + `contingencies` +
   `requalification`.
5. **Se apoya en el fingerprint de WP-A.** Si el contrato declara `fingerprints:` y no coinciden con
   los de una corrida fresca → `FAIL_REQUALIFICATION_REQUIRED`. En `DRAFT` (sin fingerprint declarado)
   el checker **captura el baseline** y marca `match: "N/A (contrato DRAFT)"` — no un pase silencioso.
6. **`found/expected/delta` viven en la evidencia del caso**, no en la taxonomía GMP.

---

## Casos de cualificación (10) — resultado del checker en DRAFT (baseline)

| case_id | actual | expected (fuente citada) | op | status |
|---|---|---|---|---|
| QC-TECH-RECALL | 0.90 | `gates.TECHNICAL_RECALL_MIN` = 0.90 | `>=` | PASS |
| QC-TECH-FABRICATED-CITATIONS | 0 | `gates.FABRICATED_CITATIONS_MAX` = 0 | `<=` | PASS |
| QC-FUNC-RECALL | 1.0 | `gates.FUNCTIONAL_RECALL_MIN` = 0.90 | `>=` | PASS |
| QC-FUNC-FALSE-POSITIVE | 0 | `zero` — `REPORTE_B8B_SUITE_B_RECALL.md` | `<=` | PASS |
| QC-DOCUMENT-EGRESS | 0 | `zero` — `ADR §SECURITY` / `CLAUDE.md` | `<=` | PASS |
| QC-LLM-CALLS | 0 | `zero` — `REPORTE_FINAL... §K` | `<=` | PASS |
| QC-FORBIDDEN-STATES | `False` | aserción — `taxonomy.FORBIDDEN_STATES` | `is_false` | PASS |
| QC-HUMAN-GATE-INTACT | `True` | aserción — `taxonomy.set_human_state` | `is_true` | PASS |
| QC-EXTRACTION-ADEQUACY-RW0009 | `True` | aserción — `WP_C_BENCHMARK...` | `is_true` | PASS |
| QC-REPRODUCIBILITY | `True` | aserción — WP-A `598e60e` | `is_true` | PASS |

`overall = DRAFT_BASELINE`. `qualified_version = null`. `fingerprint.current = {input_config c46fbe67…,
findings b5196a71…}`, `fingerprint.match = "N/A (contrato DRAFT)"`.

**Cada métrica publicada viaja con su `metric_envelope` (WP-E):** `suite_version + size + definition +
reportable_range + contamination_statement`. Los gates técnico/funcional llevan
`reportable_range = SYNTHETIC_ONLY` — su rango real depende del held-out firmado (WP-E.3) y la
muestra real adjudicada (WP-E.4).

---

## Contingencias declaradas (NO son gates pasables)

| id | estado | qué es |
|---|---|---|
| CT-REGULATORY-LLM | `FAIL_ACCEPTED_CONTINGENCY` | `REGULATORY_LLM_GATE = FAIL` (0/7) → Regulatory Tier-1 / Palanca C |
| CT-EXCEPTIONS-1-5 | `ACCEPTED_EXCEPTION` | 5 tests fallan por ruta de clon / servicios en vivo; aceptadas por Capa 9 |
| CT-PYTEST-EXIT-1 | `ACCEPTED` | pytest exit code 1 por lo anterior; la suite global NO se declara PASS |
| CT-HELD-OUT-PENDING | `PENDING_HUMAN_WORK` | gates técnico/funcional = `SYNTHETIC_ONLY` hasta WP-E.3/E.4 |
| CT-WP-D-REAL | `BLOCKED_GOVERNANCE` | extracción de Test validada solo sintéticamente; RW-0003 bloqueado |

---

## Disparadores de requalification (lista explícita; el checker compara SHA)

`extract_document.py` · `extract_tests.py` · OCR assets (N/A) · `canonical/model.py` ·
`canonical/persistence.py` · `graph/store.py` · `graph/build.py` ·
`technical_completeness_rules.yaml` · `decomposition.yaml` · `technical_suite_c.yaml` ·
`risk_matrix.yaml` · `extraction_adequacy_thresholds.yaml` · `gates.py` · `routing.txt`.

En `DRAFT` (sin SHA congelados) el checker reporta el SHA actual de cada uno y `changed: "UNKNOWN"`.
Al firmar, el humano congela `qualified_against.artifact_sha256` + `qualified_against.fingerprints`;
a partir de ahí, cualquier cambio de SHA de un disparador → `FAIL_REQUALIFICATION_REQUIRED`.

---

## Lo que necesita un humano (no es código)

1. **Capa 9 / QA** revisa el DRAFT, fija `qualified_version`, congela los SHA de los disparadores y
   los fingerprints en `qualified_against`, pone `reviewer` en cada caso y `status: SIGNED`.
2. Antes de firmar como cualificado con rango REAL: WP-E.3 (held-out firmado por autor independiente)
   y WP-E.4 (muestra adjudicada por QA) — hasta entonces los gates técnico/funcional son
   `SYNTHETIC_ONLY` y así lo dice el contrato.
3. El contrato **no** cambia `PRODUCTION_ENABLEMENT` / `REGULATORY_COMPLIANCE` / `CORPUS_READY` —
   siguen siendo decisiones de gobernanza separadas.

---

## Rollback

Artefacto y checker son **independientes del runtime**: borrar `qualification_contract.{yaml,py}` +
el test revierte sin efecto. No toca suites, fixtures firmados, `EXTRACTION_VERSION` ni routing.

---

*Aditivo. Sin re-puntuación de fixtures firmados. Sin LLM, sin red. El contrato nace `DRAFT` y el
sistema no se auto-cualifica.*
