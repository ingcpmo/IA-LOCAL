# SHADOW · G4 — CAPA LLM DE INTERPRETACIÓN (ejecución real)

**Arco:** Capa LLM de interpretación sobre findings deterministas (diseño v1.1).
**Fase:** G4 — agentes expertos LLM (G4a Technical · G4b Cross-domain · G4c Functional/Traceability
· G4d Regulatory-triage · G4e Report Composer) con **LLM REAL** vía `ModelProvider`.
**Modo:** L3/L4 aditivo · salidas SOLO en `docs_plan/shadow_llm/G4/` · L2 inmutable · `LLM_PROVIDER = LOCAL`.
**Rama:** `shadow/llm-interpretation-layer` · **Base de fase:** `shadow-G2-r1` → `62fbb44`.
**Gate previo:** G0/G1/G2+CF-1/G3.1 PASS + `PILOT_EXECUTION-2026-035` firmada por Capa 9.

---

## 1 · Gate de gobernanza — verificado en el ledger canónico

`/home/cmay/ivr-ia/factory/layer9/decisions/decisions_v2.jsonl` (266 líneas):

| Condición | Resultado |
|---|---|
| propuesta `PILOT_EXECUTION-2026-035` (`agent_proposed`) | ✅ presente · `decision_date 2026-09-03T01:13:50Z` |
| confirmación humana asociada | ✅ `PILOT_EXECUTION-2026-036` · `decision_origin: human_confirmed` · `confirms_instance_id: PILOT_EXECUTION-2026-035` · `2026-09-03T01:26:05Z` |
| `approved_by_id` humano real | ✅ `"Cesar"` (`approved_by_display_name: "cesar may"`) — no reservado |
| `status = ACTIVE` | ✅ (propose y confirm) |
| no superseded | ✅ (`supersedes_instance_id: null`, `invalid_reason: null`) |
| scope | ✅ `[RW-0005, RW-0006, RW-0011, RW-0012, RW-0014]` — exacto |
| RW-0009 excluido | ✅ (HUMAN_ONLY) |
| `max_calls` | ✅ `1000` |
| presupuesto no excedido | ✅ **481 / 1000** llamadas reales |
| autorización previa a la 1ª llamada LLM | ✅ confirm `01:26:05Z` < 1ª llamada `~01:34Z` |
| `authorizes_corpus` / `authorizes_baseline` | ✅ `false` / `false` |

---

## 2 · Provider / modelo / configuración

| | |
|---|---|
| `LLM_PROVIDER` | **LOCAL** |
| provider | `factory.engines.gmpai_integrity.model_provider.OllamaProvider` (reutilizado — corr. 4: abstracción congelada, modelo NO hardcodeado) |
| base_url | `http://localhost:11434` |
| modelo | **`qwen2.5:7b-instruct-q4_K_M`** |
| digest | `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e` |
| prompt_version | `shadow-g4-interp-v1` (NO GOBERNADO — capa L3/L4) |
| temperature / num_ctx | 0.0 / 16384 (config de `ollama_client`) |

---

## 3 · LLM_CALLS reales

```
LLM_CALLS            = 481   (ok 481 · failed 0)
wall LLM total       = 13468.9 s  (avg 28.0 s · min 10.4 s · max 199.0 s)

por sub-fase:
  G4a Technical                 17
  G4b Cross-domain              15
  G4c Functional/Traceability   98
  G4d Regulatory-triage        285
  G4e Composer (secciones)      66
```

Módulo nuevo: `factory/regulatory/shadow/experts.py` — reutiliza `ModelProvider`,
`ollama_client.generate` y el patrón de parseo (`_extract_json`); **descarta** la maquinaria de
adjudicación de `v2_judgment` (evaluación de reutilización de G2). Prompts de interpretación
propios, marcados SHADOW.

---

## 4 · Resultados por sub-fase

### G4a Technical — 17/17

`SHADOW_ACCEPTED` **17 / 17** · `SHADOW_REJECTED` 0.
`assessment`: `BEHAVIOR_NOT_FOUND_IN_SCOPE` ×17 (el 7B no halló el comportamiento requerido,
parafraseado, en el alcance — coherente con el gap determinista).

### G4b Cross-domain — 15/15

`SHADOW_ACCEPTED` **15 / 15** · `SHADOW_REJECTED` 0.
`assessment`: `DISAGREEMENT_PERSISTS` ×15 → **las 15 relaciones marcan `HUMAN_REVIEW_REQUIRED`**
(el flujo congelado de G3: `apply_review_outcome` nunca auto-resuelve un desacuerdo).
Cada envoltura preserva **ambas opiniones**: la técnica (`assessment` del experto técnico en el
`rationale`) y las contrapartes regulatorias (`declared_counterparts` = los `finding_record_id`
de los `REGULATORY_INCONCLUSIVE` del mismo documento y regla).

### G4c Functional/Traceability — 98/98

`SHADOW_ACCEPTED` **98 / 98** · `SHADOW_REJECTED` 0.
`assessment`: `LIKELY_REAL_GAP` ×64 · `LIKELY_EXTRACTION_LIMIT` ×34 (juicio diferenciado real,
no colapsa a un único valor).

### G4d Regulatory-triage — 285/285

`SHADOW_ACCEPTED` **242 / 285** · `SHADOW_REJECTED` **43 / 285** (todas por ANCLAJE — la cita del
modelo no ancla literalmente en los candidatos de recuperación; **0 rechazos estructurales**).
`assessment`: `CANDIDATE_RANKING_PROVIDED` ×278 · `NO_USEFUL_CANDIDATE` ×7.
**Triage ≤5:** `ranked_candidate_claim_ids` de longitud ≤ 5 en los 285 (distrib. 5:178, 4:43,
3:29, 2:20, 1:8, 0:7).
**0 INCONCLUSIVE → observed:** los 285 findings L2 siguen `subtype = REGULATORY_INCONCLUSIVE`;
`MUST_NOT_CHANGE == L2 verbatim` en los 285; `assessment` sin ningún token de cumplimiento.

### G4e Report Composer — 66 secciones

`NARRATIVE_DRAFTED` **63** · `NARRATIVE_BLOCKED` **3**.
**Cobertura del reporte narrativo: 457 / 457** (`verify_report_coverage`: `covered=true`,
`missing=[]`, `unsupported=[]`).
**0 afirmaciones sin `finding_record_id`:** `cited_finding_record_ids` ⊆ los `finding_record_id`
de su sección en las 63 narrativas; 0 citas fuera de sección.
**Marca `[SHADOW / NO GOBERNADO]`** presente en las 63 narrativas emitidas.

---

## 5 · Verificador G2 fail-closed — evidencia

```
expert envelopes                     415  (17 + 15 + 98 + 285)
  SHADOW_ACCEPTED                     372
  SHADOW_REJECTED                      43   (todas G4d, todas por anchoring_violations)
  rechazos con structural_violations    0
```

Solo las 372 envolturas `SHADOW_ACCEPTED` alimentaron el composer (`filter_accepted`). El
verificador **no selló en automático**: descartó 43 opiniones cuya cita del modelo no anclaba en
L1/L2. Detalle de los 43 en `G4_SUMMARY.json → g2_verifier.rejected_detail`.

---

## 6 · Invariantes y CRIT

| Invariante / CRIT | Resultado |
|---|---|
| `L2_MUTATIONS` | **0** — `FINAL_GMP_CORPUS_FINDINGS.json` sha `95a79f9b…` **antes == después** |
| `HUMAN_STATE_CHANGES` | **0** — `human_state` de los 457 = `UNREVIEWED` |
| cambios en `related_finding_ids` | **0** — 2 findings con valor (baseline C09→C01), sin cambios; ninguna envoltura lo escribe |
| salidas | **solo** bajo `docs_plan/shadow_llm/G4/` |
| `unauthorized client data egress` | **0** — único tráfico saliente = Ollama LOCAL (`localhost:11434`); 0 bytes de cliente a Internet |
| external regulatory calls | **0** — canal 2 deshabilitado; `external_reg_references` vacío en las 415 envolturas |
| `CLIENT_EVIDENCE` vs `EXTERNAL_REG_REFERENCE` | separados: 415/415 `anchored_citations` con `source = CLIENT_EVIDENCE`; 0 `external_reg_reference` marcada `CLIENT_EVIDENCE` |
| 0 declaraciones de compliance/approval/CAPA/release | **0 tokens prohibidos** (`COMPLIANT/APPROVED/OBSERVED/PASS/SATISFIES/…`) en las 481 salidas |
| **CRIT-0** baseline sin tocar | ✅ `FINDINGS_FINGERPRINT = 235f724a…` · `INPUT_CONFIG 3fcb3ae8…` · `GRAPH_SNAPSHOT 2fdda0e2…` · counts 342/90/25 (re-atestado desde el código del worktree con `experts.py` presente); `report_v2.py` / `validation_v2/` / `findings/` byte-idénticos |
| **CRIT-H** gate humano intacto | ✅ `human_gate_intact = True`; nada auto-concluido; los 15 cross-domain `DISAGREEMENT_PERSISTS` → revisión humana |
| **CRIT-L2** inmutabilidad L2 | ✅ `L2_MUTATIONS = 0`; verificador rechaza toda envoltura que altere `MUST_NOT_CHANGE` (incl. `related_finding_ids`, shadow-G2-r1) |
| **CRIT-E1** `UNAUTHORIZED_CLIENT_DATA_EGRESS = 0` | ✅ |
| **CRIT-E2** consultas externas auditadas | ✅ N/A — 0 consultas externas |
| **CRIT-E3** sin contenido de cliente a Internet | ✅ |
| **CRIT-E4** (G0–G5) `LLM_PROVIDER = LOCAL`, canal regulatorio externo NO habilitado | ✅ |

### Fingerprints antes / después

```
                         antes (baseline)                                    después (atestación G4)
INPUT_CONFIG      3fcb3ae859091000b0e6c6cf2b4f51515e74665d658451b753c723d6e6e51668   idéntico
GRAPH_SNAPSHOT    2fdda0e2ce513bc48b54038c5890a0b060e87a6e5c0d6d98b3d31fb149be3620   idéntico
FINDINGS         235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23   idéntico
```

---

## 7 · Artefactos G4 generados

| Fichero | sha256 |
|---|---|
| `factory/regulatory/shadow/experts.py` | `645ac98ba6c2c70f8704d71829c8417ec8991f61c8c43949fdbf6e61c5d2bf14` |
| `factory/tests/test_shadow_experts.py` (8 tests, mock provider, 0 LLM real) | `101a485dc4f95488714a660b3e69954ee01ac430b680103f141347b5c37d3e34` |
| `docs_plan/shadow_llm/G4/g4a_technical.jsonl` (17) | `35f09cebd1fbc7a135a3caf578b3345053581877ddfcbe527187e9310dd5d2e8` |
| `docs_plan/shadow_llm/G4/g4b_cross_domain.jsonl` (15) | `339e24a83033e6d92d3ea006d3653eaa8cf1f5b09ab488fde0323fe60c9c5025` |
| `docs_plan/shadow_llm/G4/g4c_functional.jsonl` (98) | `27780c0ffed9a8a84baac13c8af90f1fd904c593f4b045e3f68298e58e521a63` |
| `docs_plan/shadow_llm/G4/g4d_regulatory_triage.jsonl` (285) | `7198a77e38c751cb4909b04c6cc93c8a750c475cab6698f445d68c808414255c` |
| `docs_plan/shadow_llm/G4/g4e_composer.jsonl` (66) | `6f07762ffa2eb4dd5f9824c122ad9af1cee405d3eb990733ccb5006b760aec3c` |
| `docs_plan/shadow_llm/G4/g4_call_log.json` (481 llamadas) | `242df99f30b19752de9621c9a1967d3663147451e845f24906ef6cb209110c3f` |
| `docs_plan/shadow_llm/G4/G4_SUMMARY.json` | `5775b92d0073d3be0e91dd44789e7d6ac0ef685ead02c4602e51af6bd7870339` |
| `docs_plan/shadow_llm/G4/_progress.json` (marcador DONE) | `de1dc9ab97bec46ac881a98c735d735352470abea4e0fc05eaaaacbdf861194f` |
| `docs_plan/shadow_llm/G4_LLM_INTERPRETATION.md` | (este fichero) |

Tests: `pytest test_shadow_{router,contracts,verifier,cross_domain,composer,experts}.py` → **70 passed**.

---

## 8 · REPORTE DE FASE — G4 (formato v1.1)

```
FASE                    = G4 (capa LLM de interpretación — G4a..G4e con LLM REAL)
PRE_COMMIT              = 62fbb44  (tag shadow-G2-r1)
POST_COMMIT            = <pendiente — commit exclusivo de G4>
WORKTREE               = /home/cmay/ivr-ia/.claude/worktrees/shadow-llm
DIFF (prohibidos)      = VACÍO — 0 modificaciones a ficheros existentes (git diff --stat HEAD vacío);
                         report_v2.py / findings/ / validation_v2/ / decisions_v2.jsonl SIN TOCAR;
                         solo ficheros NUEVOS bajo factory/regulatory/shadow/experts.py,
                         factory/tests/test_shadow_experts.py, docs_plan/shadow_llm/G4*, G4/
PILOT_EXECUTION        = PILOT_EXECUTION-2026-035  (human_confirmed vía PILOT_EXECUTION-2026-036,
                         approved_by_id=Cesar, ACTIVE, no superseded, scope exacto, 481/1000)
PROVIDER / MODELO      = OllamaProvider LOCAL · qwen2.5:7b-instruct-q4_K_M · digest 845dbda0ea48…
LLM_PROVIDER           = LOCAL
LLM_CALLS              = 481   (G4a 17 · G4b 15 · G4c 98 · G4d 285 · G4e 66)
G2 VERIFIER            = 372 SHADOW_ACCEPTED · 43 SHADOW_REJECTED (todas anchoring, 0 estructurales)
G4e COVERAGE           = 457/457  (missing 0 · unsupported 0)
FINGERPRINTS           = INPUT_CONFIG 3fcb3ae8… · GRAPH_SNAPSHOT 2fdda0e2… · FINDINGS 235f724a…  (== baseline)
HUMAN_STATE_CHANGES    = 0
L2_MUTATIONS           = 0
related_finding_ids    = sin cambios
CLIENT_DATA_EGRESS     = 0 (unauthorized) · external regulatory calls = 0
CRIT                   = CRIT-0 ✅ · CRIT-H ✅ · CRIT-L2 ✅ · CRIT-E1 ✅ · CRIT-E2 ✅ · CRIT-E3 ✅ · CRIT-E4 ✅
VERIFICACIONES ESPECIALES = 0 INCONCLUSIVE→observed ✅ · triage ≤5 ✅ · ambas opiniones cross-domain ✅ ·
                            composer 0 afirmaciones sin finding_record_id ✅ · marca [SHADOW / NO GOBERNADO] ✅ ·
                            CLIENT_EVIDENCE ≠ EXTERNAL_REG_REFERENCE ✅ · 0 declaraciones compliance/approval/CAPA/release ✅
DEVIATIONS             = ninguna
PROPOSED_VERDICT       = PASS
```

---

*G4 · capa LLM de interpretación ejecutada con LLM real (481 llamadas, `qwen2.5:7b` LOCAL). L2
inmutable, gate humano intacto, verificador G2 fail-closed aplicado, 0 egress no autorizado.
Detenido antes de `shadow-G4`. NO se ejecuta G5. La auditoría externa no la ejecuta Capa 8.*
