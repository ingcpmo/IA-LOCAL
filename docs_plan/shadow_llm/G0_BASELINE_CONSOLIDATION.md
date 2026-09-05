# SHADOW · G0 — CONSOLIDACIÓN / FORMALIZACIÓN DE LA BASELINE

**Arco:** Capa LLM de interpretación sobre findings deterministas (diseño v1.1).
**Fase:** G0 (primera del arco `G0 → G1 → G2 → G3 → gate + PILOT → G4a..e → G5`).
**Naturaleza:** CONSOLIDACIÓN / FORMALIZACIÓN — **no** es re-análisis del corpus ni nueva
caracterización. La caracterización ya existe (`diag-corpus-20260902`); G0 la **congela** como
punto de partida verificable y fija los invariantes que toda fase G debe respetar.
**Modo:** SIN LLM · SIN embeddings · SIN PILOT nuevo · SIN tocar L0/L1/L2 · SIN mover el
`FINDINGS_FINGERPRINT` · SIN commit hasta el gate humano.
**Rama:** `shadow/llm-interpretation-layer` (worktree `.claude/worktrees/shadow-llm`, base `0e1e88a`).

---

## 1 · Identidad de la baseline congelada

| Campo | Valor congelado en G0 |
|---|---|
| Rama de origen | `fix/clon-local-validacion` |
| Commit baseline | **`0e1e88a`** (`git worktree add … HEAD`) |
| Tag de aceptación | `reconc-acceptance-v1` → `0e1e88a` |
| Tag de código del arco de reconciliación | `reconc-arc-closure` → `56bd36a` |
| Recomendación de revisión humana previa | `ACCEPT_WITH_FOLLOW_UP` (`FINAL_HUMAN_REVIEW_POST_RECONCILIATION.md`) |
| `INPUT_CONFIG_FINGERPRINT` | `3fcb3ae859091000b0e6c6cf2b4f51515e74665d658451b753c723d6e6e51668` |
| `GRAPH_SNAPSHOT_FINGERPRINT` | `2fdda0e2ce513bc48b54038c5890a0b060e87a6e5c0d6d98b3d31fb149be3620` |
| `FINDINGS_FINGERPRINT` (ENFORCE, modo gobernado por defecto) | **`235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23`** |
| `FINDINGS_FINGERPRINT` (OBSERVE, variante) | `693fc746e645b168386537c7dbce8c6394b582fb6c031ebf62e44189b748a368` |
| Counts por módulo (reg / func / tech) | **342 / 90 / 25** |
| Total findings L2 | **457** |
| `analysis_coverage_mode` efectivo | `ENFORCE` (GATE D-2 `D-2-H7-20260830` + `extraction_adequacy_thresholds.yaml` SIGNED) |
| `LLM_CALLS` / `EMBEDDING_CALLS` / `DOCUMENT_EGRESS_BYTES` | 0 / 0 / 0 |
| `human_gate_intact` | True — 457/457 `human_state = UNREVIEWED` |
| `MULTI_AGENT_RUNTIME_CURRENTLY_ACTIVE` | NO |

Corpus (6 documentos, canonical_store de producción, `LOGICAL_CONTENT_HASH` == `VALIDATION_BASELINE_MANIFEST`, 6/6):
`RW-0005`, `RW-0006`, `RW-0009` (`NOT_ANALYZABLE`), `RW-0011`, `RW-0012`, `RW-0014`.

---

## 2 · Re-verificación de la baseline (G0 — atestación, no re-análisis)

`run_v2_pipeline(["RW-0005","RW-0006","RW-0009","RW-0011","RW-0012","RW-0014"])` ejecutado una vez
sobre los stores de producción con el código de `0e1e88a` (worktree = main checkout, byte-idéntico
para toda la ruta del pipeline; verificado por `git diff --stat HEAD` vacío + `md5sum` iguales):

```
RUN_ID                    diag-corpus-20260902  (re-ejecución de atestación G0)
TOTAL_FINDINGS            457   (reg 342 / func 90 / tech 25)
INPUT_CONFIG_FINGERPRINT  3fcb3ae859091000…     == baseline  ✅
GRAPH_SNAPSHOT_FINGERPRINT 2fdda0e2ce513bc4…    == baseline  ✅
FINDINGS_FINGERPRINT      235f724a738ce783…     == baseline  ✅
LLM_CALLS / EMBEDDING_CALLS / DOCUMENT_EGRESS_BYTES   0 / 0 / 0
HUMAN_GATE_INTACT         True
analysis_coverage_mode    ENFORCE
canonical_store LOGICAL vs VALIDATION_BASELINE_MANIFEST   6/6 match
```

**La baseline reproduce exacta.** `235f724a…` es el ancla inmutable del arco: cualquier fase G
que la mueva es un `PROPOSED_VERDICT = FAIL` automático.

---

## 3 · Arquitectura congelada (L0–L5) — del diseño v1.1

```
L0  PDF ORIGINAL                     inmutable
L1  EVIDENCIA EXTRAÍDA (canonical)    inmutable · hash lógico gobernado
L2  FINDING DETERMINISTA              inmutable · class/subtype/risk/requirement_id/machine_state/
                                                  human_state/evidencia/related_finding_ids
─────────────────────────────────────────────────────────────────────  ← FRONTERA DURA
L3  OPINIÓN DEL AGENTE EXPERTO (LLM)  aditiva · <run_dir>/shadow/*, nunca toca L2
L4  REDACCIÓN DEL COMPOSER (LLM)      aditiva · narrativa marcada [SHADOW / NO GOBERNADO]
L5  DECISIÓN HUMANA                   única autoridad que cambia human_state
```

- `related_finding_ids` es un campo de L2 y **la capa LLM no lo escribe** (corrección 2 del
  auditor). Toda relación descubierta/usada por la capa shadow —incluidos los enlaces
  cross-domain— vive en `shadow/cross_domain_links.json`.
- La narrativa distingue **dos fuentes**: `CLIENT_EVIDENCE` (del corpus, confidencial) vs
  `EXTERNAL_REG_REFERENCE` (pública, contextual). La referencia externa **contextualiza**; nunca
  se convierte en evidencia de que el documento del cliente cumple.
- El modelo que ejecuta los agentes es intercambiable: se congela **`ModelProvider` como
  abstracción**, no un modelo concreto (corrección 4). El 7B actual = primer candidato de piloto.

### Anclaje de la arquitectura efectiva actual a las capas

| Capa | Qué es hoy (código en `0e1e88a`) | Ruta |
|---|---|---|
| L0 | PDF de cliente | `GMPAI/source/Rockwell/*.pdf` (no en git) |
| L1 | `canonical_store/*.sqlite3` + `graph_store` + snapshot inmutable por `run_id` | `factory/regulatory/canonical/`, `factory/regulatory/graph/build.py` |
| L2 | 7 clases `Finding`, invariantes duros, `human_state` inmutable desde IA | `factory/regulatory/findings/taxonomy.py` (`Finding`, `FindingProvenance`, `build_finding`, `set_human_state`) |
| L2 productores | Tier-1 regulatorio · funcional B6a · técnico B6b — 100 % deterministas, 0 LLM | `findings/regulatory_tier1.py`, `findings/functional_findings.py`, `findings/technical_findings.py` |
| L2 reporte factual | transcripción estructurada por clase, sin LLM, cobertura 457/457 | `findings/report_v2.py` (`build_report`, `render_markdown`, `to_json`) |
| Orquestador | `run_v2_pipeline` (bajo `network_locked()`) | `factory/regulatory/validation_v2/v2_runtime.py` |
| L3/L4 | **NO EXISTEN** — código de juicio LLM presente (`v2_judgment/*`, `chunked_engine`, `model_provider`, `ollama_client`, `retrieval/judgment.py`, capa semántica) pero **NO cableado** a `run_v2_pipeline` | — |

---

## 4 · Routing congelado (para G1) — primario exclusivo 457 + flag secundario 15

Reconciliado contra `CURRENT_FINDING_AGENT_ROUTING.json` (copia congelada en `G0_inputs/`).

### 4.1 · Routing primario (exclusivo, suma exacta 457)

| Bucket primario | Nº | Composición (subtipos) | Bandas | Regla determinista de asignación |
|---|---:|---|---|---|
| **REGULATORY** | **285** | `REGULATORY_INCONCLUSIVE` 285 | `HIGH` 285 | `agent_id == regulatory_tier1` ∧ `document != RW-0009` |
| **FUNCTIONAL / TRACEABILITY** | **98** | `REQUIREMENT_NOT_TESTED` 70 · `IMPLEMENTATION_WITHOUT_REQUIREMENT` 20 · `ORPHAN_DESIGN_ELEMENT` 8 | `LOW` 78 · `MEDIUM` 20 | `evidence_basis == ABSENCE_DEPENDENT` ∧ `agent_id ∈ {test_coverage_agent, cross_document_agent, requirements_traceability_agent, functional_consistency_agent}` |
| **TECHNICAL** | **17** | `AUTHORITY_CHECK_GAP` 3 · `ALCOA_ATTRIBUTABLE_GAP` 4 · `AUDIT_TRAIL_DESIGN_GAP` 2 · `BACKUP_RECOVERY_GAP` 2 · `ACCESS_CONTROL_GAP` 2 · `TECHNICAL_DESIGN_GAP` 2 · `AUDIT_TRAIL_INTEGRITY_GAP` 2 | `HIGH` 13 · `MEDIUM` 2 · `CRITICAL` 2 | `technical_basis` presente (regla de completitud gobernada) |
| **HUMAN_ONLY** | **57** | `REGULATORY_INCONCLUSIVE` 57 (todos anclados en RW-0009) | `HIGH` 57 | `document == RW-0009` (`adequacy_verdict = NOT_ANALYZABLE`) → **NUNCA al LLM** |
| **TOTAL** | **457** | | | |

Nota de reconciliación con el diagnóstico: la clasificación por *bucket epistémico* del
`CURRENT_FINDING_AGENT_ROUTING.json` (`LLM_EXPERT_REVIEW_CANDIDATE` 372 + `LLM_EXPLANATION_USEFUL`
28 + `HUMAN_ONLY` 57) se **mapea** al routing primario del diseño así: los 28
`LLM_EXPLANATION_USEFUL` (20 `IMPLEMENTATION_WITHOUT_REQUIREMENT` + 8 `ORPHAN_DESIGN_ELEMENT`,
`MACHINE_INCONCLUSIVE` / LOW) quedan bajo el experto **FUNCTIONAL/TRACEABILITY** como
"explanation-only" (redacción para el revisor, no cambio de conclusión). `285 + (70+20+8) + 17 +
57 = 457`.

### 4.2 · Atributo secundario — `cross_domain_flag`

`CROSS_DOMAIN_REQUIRED = YES` sobre **15 relaciones** (no es un 5º bucket; no se suma a 457):
un hallazgo técnico/seguridad/integridad de completitud cuya **regulación fuente gobernada**
(`21_CFR_11.10(d)`, `21_CFR_11.10(e)`, `21_CFR_11.10(g)`, `ANNEX11_17`, `ALCOA_ATTRIBUTABLE`) es la
misma regla que `regulatory_tier1` marcó `INCONCLUSIVE` **en el mismo documento**. Detalle exacto
(15 `finding_record_id`) en `CURRENT_FINDING_AGENT_ROUTING.json →
summary.cross_domain_same_requirement_family_detail`.

El Cross-domain Reviewer procesa las **15 relaciones** *después* de que cada finding pasó por su
experto primario. Su salida va a `shadow/cross_domain_links.json`, **nunca** a
`related_finding_ids`.

### 4.3 · Distribución por documento (contexto)

`RW-0005` 88 · `RW-0006` 133 · `RW-0009` 57 (todos HUMAN_ONLY) · `RW-0011` 58 · `RW-0012` 62 · `RW-0014` 59.

---

## 5 · Redacción congelada sobre el recall (formulación obligatoria, §5 del diseño v1.1)

Se usa esta formulación exacta en G0 y en todo documento del arco. La formulación anterior
("el 7B produjo recall 0") queda **prohibida**.

```
HECHO (de la corrida diag-corpus-20260902):
  Los 342 REGULATORY_INCONCLUSIVE los produjo el MOTOR DETERMINISTA Tier-1 (Palanca C).
  En esa corrida: LLM_CALLS = 0, MODEL = null, PROVIDER = null.
  Tier-1 no encontró eco léxico anclado en 6 docs × 12 requisitos → todos INCONCLUSIVE.

RIESGO (de experimentos previos, NO de esta corrida):
  El juicio semántico del 7B sobre paráfrasis tiene techo medido (1–2/7; 4/7 confirmado por
  experimento directo; R2 CERRADO sin alcanzar el gate >= 6/7).

Ambos respaldan precaución. NO se afirma que "el 7B produjo recall 0 en esta corrida": el 7B no se
ejecutó. La precaución sobre el bloque regulatorio (triage, no juicio) se sostiene en el RIESGO
histórico, no en atribuir al 7B un resultado de una corrida determinista.
```

---

## 6 · Invariantes que TODA fase G debe respetar (checklist de gate)

```
I-1  L2_MUTATIONS = 0
     No mutar class/subtype/severity/risk/requirement_id/machine_state/human_state ni
     related_finding_ids de ningún Finding. human_state solo por set_human_state(reviewer=<humano>).
I-2  FINDINGS_FINGERPRINT == 235f724a738ce783…  al cerrar la fase (y INPUT_CONFIG 3fcb3ae8…,
     GRAPH_SNAPSHOT 2fdda0e2…).
I-3  Toda salida de la capa (routing, opiniones LLM, enlaces, narrativa) vive bajo
     <run_dir>/shadow/ o docs_plan/shadow_llm/. NUNCA en *_findings.json / final_report_v2.json.
I-4  Enlaces cross-domain SOLO en shadow/cross_domain_links.json.
I-5  UNAUTHORIZED_CLIENT_DATA_EGRESS = 0 (CRIT-E1). 0 bytes de PDF/canonical/evidencia/finding/
     graph/identificadores de cliente salen del host sin autorización específica.
I-6  G0–G3: LLM_CALLS = 0. G0–G5: LLM_PROVIDER = LOCAL; canal regulatorio externo NO habilitado
     (solo se DISEÑA el Gateway). (CRIT-E4)
I-7  Los 57 HUMAN_ONLY (RW-0009) nunca entran al LLM.
I-8  No declaración de cumplimiento · no aprobación automática · no cierre de CAPA · no liberación
     de lote · no convertir INCONCLUSIVE / NOT_ANALYZABLE en observed.
I-9  Régimen fase a fase: una fase por vez, estado congelado (tag shadow-G<n> tras gate humano),
     reporte por fase, PROPOSED_VERDICT → decisión humana.
I-10 Fuera de alcance del arco: bug del generador de IDs, 4 tests de hardening stale, RW-0009,
     R2, PILOT-035, PRODUCTION_ENABLEMENT.
```

---

## 7 · Alcance de las fases siguientes (declaración, NO diseño)

| Fase | Produce | LLM | Gate previo |
|---|---|---|---|
| **G0** (esta) | Baseline congelada + invariantes + routing spec + redacción de recall. Sin código. | no | — |
| **G1** | Router determinista: routing primario exclusivo (457) + `cross_domain_flag` (15). Test de aceptación `285+98+17+57=457` + 15 flags. Salida en `shadow/routing.json`. | no | gate humano de G0 |
| **G2** | Contratos de entrada/salida por experto (paquete acotado y trazable; `assessment ∈ enum`; bloque `MUST_NOT_CHANGE`). Evaluación de qué piezas de `v2_judgment` cumplen el contrato de *interpretación* (reutilización selectiva). Sin ejecutar nada. | no | gate humano de G1 |
| **G3** | Verificador determinista fail-closed (cita anclada en L1/L2, `MUST_NOT_CHANGE` intacto, `assessment ∈ enum`). Post-pass determinista de detección de las 15 relaciones cross-domain → `shadow/cross_domain_links.json`. Especificación (no implementación) del Regulatory Retrieval Gateway. | no | gate humano de G2 |
| **gate + PILOT** | Gate humano de G3 + `PILOT_EXECUTION` vigente firmada (no proponer nueva si hay vigente; selección por `corpus_runner._select_pilot_execution_instance`). | — | — |
| **G4a** | Technical Expert (17) → `shadow/expert_technical.json` + verificación. | LOCAL | gate + PILOT |
| **G4b** | Cross-domain Reviewer (15 relaciones + DISAGREEMENT). | LOCAL | G4a |
| **G4c** | Functional/Traceability Expert (98). | LOCAL | G4b |
| **G4d** | Regulatory triage (285 · triage de ≤5 candidatos, **NO juicio**). | LOCAL | G4c |
| **G4e** | Report Composer → `shadow/informe_narrativo_v2.md` (por documento × regulación, cada afirmación anclada a `finding_record_id`, narrativa marcada `[SHADOW]`, `CLIENT_EVIDENCE` vs `EXTERNAL_REG_REFERENCE` separadas) + verificador de reporte (cobertura 457/457, 0 afirmaciones sin finding, cabecera GxP). | LOCAL | G4d |
| **G5** | Cierre del arco: evidencia consolidada, atestación de invariantes, paquete para decisión humana. | — | G4e |

---

## 8 · Artefactos de entrada congelados en G0

### 8.1 · Artefactos G0 requeridos (criterios prefijados)

| Fichero (`docs_plan/shadow_llm/`) | sha256 | check |
|---|---|---|
| `FINAL_GMP_CORPUS_FINDINGS.json` | `95a79f9b6276ff2a7972100764b308fa4b09f0027c6679ea831b441eb880f02c` | 457/457 registros · 457 `finding_record_id` únicos · 457 `UNREVIEWED` ✅ |
| `FINAL_GMP_CORPUS_ANALYSIS_REPORT.md` | (ver `git show`) | formalización de baseline; 342 `REGULATORY_INCONCLUSIVE` → Tier-1 determinista (`adjudicator_state=TIER1` 342/342, `llm_involved=False`) ✅ |

### 8.2 · Insumos congelados

Copiados a `docs_plan/shadow_llm/G0_inputs/` (worktree), con sha256:

| Fichero | sha256 |
|---|---|
| `DESIGN_LLM_INTERPRETATION_LAYER_v1.1.md` (en `docs_plan/shadow_llm/`) | — (creado en esta fase; ver `git status`) |
| `CLAUDE_WEB_POST_RECONCILIATION_DESIGN_INPUT_V1.md` | `b28bbdcc634cd8310c033615f49b0224c3755491afe58ff11f0db37c0d727ecc` |
| `CURRENT_CORPUS_AGENT_DIAGNOSTIC.md` | `079f5ba385bd4d7d4755687f3a77ab84b293dcd7755e93dc81bf36d1379ae2fa` |
| `CURRENT_FINDING_AGENT_ROUTING.json` | `490a26b55e2d9f3538d49349a3181d68e33452c6aac9b66088136d4500e68ba6` |
| `CURRENT_RUNTIME_AGENT_MAP.json` | `49e7a58340e7cb3905d88ad61b61e1cd1cbf7d5429509cfd4ef5d1837f29c6f4` |
| `FINAL_HUMAN_REVIEW_POST_RECONCILIATION.md` | `c389e831b232e495a8c4f7b98e4cf9e623a0f9f263529561dbe1ec2a16713ce0` |

---

## 9 · REPORTE DE FASE — G0 (formato v1.1)

```
FASE                    = G0 (CONSOLIDACIÓN / FORMALIZACIÓN de la baseline)
PRE_COMMIT              = 0e1e88a  (worktree shadow/llm-interpretation-layer, base = HEAD de fix/clon-local-validacion)
POST_COMMIT            = <pendiente — no se commitea hasta el gate humano de G0>
WORKTREE               = /home/cmay/ivr-ia/.claude/worktrees/shadow-llm  (rama shadow/llm-interpretation-layer)
DIFF (prohibidos)      = VACÍO
                         · 0 cambios en factory/ (código, engines, prompts, governance)
                         · 0 cambios en L0/L1/L2 · 0 cambios en canonical_store / graph_store / ledger / audit trail
                         · solo ficheros nuevos bajo docs_plan/shadow_llm/
COMMANDS               = git worktree add .claude/worktrees/shadow-llm -b shadow/llm-interpretation-layer HEAD
                         PYTHONHASHSEED=random  python  <atestación run_v2_pipeline sobre los 6 docs>   (1×)
                         sha256sum docs_plan/shadow_llm/G0_inputs/*
TEST_RESULTS           = N/A en G0 (fase de consolidación documental; sin código nuevo, sin suite).
                         Atestación de baseline vía re-ejecución de run_v2_pipeline (ver abajo).
INPUT_HASHES           = canonical_store LOGICAL == VALIDATION_BASELINE_MANIFEST  (6/6 match)
                         artefactos de entrada: 5 ficheros con sha256 en §8
OUTPUT_HASHES          = docs_plan/shadow_llm/FINAL_GMP_CORPUS_FINDINGS.json
                             sha256 = 95a79f9b6276ff2a7972100764b308fa4b09f0027c6679ea831b441eb880f02c
                             457/457 registros · 457 finding_record_id únicos · 457 UNREVIEWED
                         docs_plan/shadow_llm/FINAL_GMP_CORPUS_ANALYSIS_REPORT.md        (formalización de baseline)
                         docs_plan/shadow_llm/DESIGN_LLM_INTERPRETATION_LAYER_v1.1.md    (diseño v1.1 congelado)
                         docs_plan/shadow_llm/G0_BASELINE_CONSOLIDATION.md               (este fichero)
                         docs_plan/shadow_llm/G0_inputs/*                                (5 copias congeladas)
FINGERPRINTS           = INPUT_CONFIG   3fcb3ae859091000b0e6c6cf2b4f51515e74665d658451b753c723d6e6e51668   ✅
                         GRAPH_SNAPSHOT 2fdda0e2ce513bc48b54038c5890a0b060e87a6e5c0d6d98b3d31fb149be3620   ✅
                         FINDINGS       235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23   ✅ (== baseline)
LLM_CALLS              = 0
CLIENT_DATA_EGRESS     = 0  (CRIT-E1 satisfecho; run_v2_pipeline bajo network_locked(), DOCUMENT_EGRESS_BYTES=0)
LLM_PROVIDER           = LOCAL  (N/A — no se ejecutó ningún modelo en G0; canal regulatorio externo NO habilitado)
ARTIFACTS              = ver OUTPUT_HASHES
GOVERNANCE_EVENTS      = ninguno  (G0 no crea ninguna decisión; ledger/audit trail sin tocar)
HUMAN_STATE_CHANGES    = 0
L2_MUTATIONS           = 0
DEVIATIONS             = ninguna
EXPECTED_VS_ACTUAL     = esperado: baseline reproduce (fingerprints + counts 342/90/25 + egress 0 + gate intacto)
                         actual:   idéntico — FINDINGS_FINGERPRINT = 235f724a…, TOTAL_FINDINGS = 457, LLM_CALLS = 0
PROPOSED_VERDICT       = PASS
                         G0 congela la baseline (0e1e88a / 235f724a…), la arquitectura L0–L5, el routing
                         primario exclusivo (285/98/17/57 = 457) + 15 cross_domain_flag, la redacción
                         obligatoria del recall (§5) y los 10 invariantes de gate (§6). Sin código, sin LLM,
                         sin mover el fingerprint, sin tocar L0/L1/L2, sin commit. Listo para el gate humano
                         de Capa 9; con su OK se tagea `shadow-G0` y se habilita G1 (router determinista).
```

---

## 10 · Qué decide el gate humano de G0

1. **Aceptar la baseline congelada** (`0e1e88a` / `235f724a…`) como punto de partida del arco SHADOW.
2. **Aceptar el routing primario exclusivo** `REGULATORY 285 · FUNCTIONAL 98 · TECHNICAL 17 ·
   HUMAN_ONLY 57 = 457` + `cross_domain_flag` sobre 15 relaciones, y el mapeo de reconciliación
   con el diagnóstico (§4.1 nota).
3. **Aceptar los 10 invariantes de gate** (§6) como criterio de PASS/FAIL de toda fase G.
4. **Aceptar la redacción obligatoria del recall** (§5) y la prohibición de la formulación anterior.
5. **Autorizar el tag `shadow-G0`** sobre la rama `shadow/llm-interpretation-layer` y el paso a **G1**.

Nada de lo anterior habilita LLM, embeddings, PILOT nuevo, R2, PILOT-035 ni producción. La
decisión final es humana.

---

*G0 · READ-ONLY sobre el código. Sin implementación, sin LLM, sin PILOT nuevo, sin mover el
fingerprint, sin tocar L0/L1/L2, sin commit. Detenido en el gate humano.*
