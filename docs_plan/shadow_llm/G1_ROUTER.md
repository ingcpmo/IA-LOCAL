# SHADOW · G1 — ROUTER DETERMINISTA

**Arco:** Capa LLM de interpretación sobre findings deterministas (diseño v1.1).
**Fase:** G1 — router determinista primario exclusivo (457) + `cross_domain_flag` (15).
**Modo:** SIN LLM · SIN red · SIN embeddings · solo LECTURA de L2 · SIN mover el `FINDINGS_FINGERPRINT`.
**Rama:** `shadow/llm-interpretation-layer` · **Base de fase:** `shadow-G0` → `3bacfd0`.
**Gate previo:** G0 aprobado.

---

## 1 · Qué produce G1

| Artefacto | Ruta | Naturaleza |
|---|---|---|
| Router (módulo) | `factory/regulatory/shadow/router.py` (+ `factory/regulatory/shadow/__init__.py`) | código nuevo, determinista, pure-function, CERO LLM/red |
| Test de aceptación | `factory/tests/test_shadow_router.py` | 11 tests |
| Routing congelado | `docs_plan/shadow_llm/G1_routing.json` | salida del router sobre el corpus baseline |

El router **solo lee** findings L2 (`FINAL_GMP_CORPUS_FINDINGS.json` en el congelado; los
`*_findings.json` de `<run_dir>` en runtime) y **escribe únicamente** el artefacto de routing.
No importa nada del lado LLM/engine. No muta ningún `Finding` (test
`test_router_does_not_mutate_input_findings`).

---

## 2 · Reglas de routing (congeladas — de G0 §4 / `FINAL_GMP_CORPUS_ANALYSIS_REPORT.md`)

### 2.1 · Primario (exclusivo, primer match gana)

| Orden | Bucket | Regla determinista | Nº baseline |
|---|---|---|---:|
| 1 | `HUMAN_ONLY` | `document == "RW-0009"` (`adequacy_verdict = NOT_ANALYZABLE`) | **57** |
| 2 | `REGULATORY` | `provenance.agent_id == "regulatory_tier1"` | **285** |
| 3 | `TECHNICAL` | `technical_basis` no vacío (regla de completitud gobernada) | **17** |
| 4 | `FUNCTIONAL_TRACEABILITY` | `evidence_basis == "ABSENCE_DEPENDENT"` ∧ `agent_id ∈ {test_coverage_agent, cross_document_agent, requirements_traceability_agent, functional_consistency_agent}` | **98** |
| — | `UNROUTED` | cualquier finding que no encaje → **FALLO** del self-check | **0** |
| | | **TOTAL** | **457** |

El orden importa: los 57 de RW-0009 son `regulatory_tier1` pero la regla 1 los captura antes
(invariante I-7: RW-0009 nunca al LLM). Los 8 `ORPHAN_DESIGN_ELEMENT` (emitidos por
`technical_findings.py` pero **sin** `technical_basis`, `agent_id = requirements_traceability_agent`)
caen en la regla 4, no en la 3 → FUNCTIONAL/TRACEABILITY (70 + 20 + 8 = 98).

### 2.2 · Secundario — `cross_domain_flag`

`cross_domain_flag = YES` para un finding F **sii**:

1. `route_primary(F) == "TECHNICAL"`, **y**
2. `F.technical_basis` nombra ≥1 token de regulación
   (`21_CFR_11.\d+\([a-z]\)` · `ANNEX11_\d+(\.\d+)?` · `ALCOA_[A-Z]+` · `21_CFR_11.50_11.70`), **y**
3. ese token coincide con el prefijo de familia (`requirement_id.split("::")[0]`) de algún finding
   `regulatory_tier1` del **mismo documento**.

Es un **flag sobre un finding ya ruteado** — NO un 5º bucket, NO se suma a 457. El artefacto
adjunta, por cada flag, `cross_domain_regulations` (tokens compartidos) y
`cross_domain_regulatory_counterparts` (`finding_record_id` de los findings regulatorios
contraparte del mismo documento). El grafo completo de relaciones cross-domain
(`shadow/cross_domain_links.json`) es **G3**, no G1.

**Baseline: 15 flags.** Idénticos (mismos 15 `finding_record_id`) a
`CURRENT_FINDING_AGENT_ROUTING.json → summary.cross_domain_same_requirement_family_detail`
(test `test_cross_domain_ids_match_g0_diagnostic`):

| Documento(s) | subtype técnico | regulación compartida |
|---|---|---|
| RW-0005, RW-0006 | `AUDIT_TRAIL_DESIGN_GAP` | `21_CFR_11.10(e)` |
| RW-0005, RW-0006 | `AUDIT_TRAIL_INTEGRITY_GAP` | `21_CFR_11.10(e)` |
| RW-0005, RW-0006 | `ACCESS_CONTROL_GAP` | `21_CFR_11.10(g)` |
| RW-0005, RW-0006, RW-0014 | `AUTHORITY_CHECK_GAP` | `21_CFR_11.10(g)` |
| RW-0005, RW-0006 | `TECHNICAL_DESIGN_GAP` | `ANNEX11_17` |
| RW-0005, RW-0011, RW-0012, RW-0014 | `ALCOA_ATTRIBUTABLE_GAP` | `21_CFR_11.10(d)` + `ALCOA_ATTRIBUTABLE` |

---

## 3 · Resultado sobre el corpus baseline (`G1_routing.json`)

```
total_records            457
by_primary_bucket        REGULATORY 285 · FUNCTIONAL_TRACEABILITY 98 · TECHNICAL 17 · HUMAN_ONLY 57
sum_primary              457
UNROUTED                 0
unique_finding_record_id 457
cross_domain_flags       15   (todos primary_bucket == TECHNICAL; flag secundario)
acceptance.PASS          true
acceptance.matches_expected_baseline   true
```

`G1_routing.json` sha256: `212b5514c599728e83e22f7949cf6526fe948762eb0b1ab55ba084bc024826b1`
(determinista — 2ª ejecución byte-idéntica).

---

## 4 · Tests

```
pytest factory/tests/test_shadow_router.py -q   ->   11 passed in 0.76s
```

| test | verifica |
|---|---|
| `test_human_only_wins_over_everything` | regla 1 gana aun con agent=regulatory_tier1 + technical_basis + ABSENCE_DEPENDENT |
| `test_regulatory_before_technical_and_functional` | precedencia de la regla 2 |
| `test_technical_requires_non_empty_technical_basis` | `technical_basis` vacío ⇒ no TECHNICAL |
| `test_functional_requires_absence_dependent_and_known_agent` | `evidence_basis != ABSENCE_DEPENDENT` ⇒ UNROUTED |
| `test_cross_domain_flag_only_on_technical` | el flag nunca aplica a un finding regulatorio |
| `test_acceptance_primary_routing_sums_457` | 285/98/17/57 = 457 |
| `test_acceptance_no_unrouted_and_unique_records` | 0 UNROUTED · 457 record_id únicos · PASS · matches_expected_baseline |
| `test_acceptance_15_cross_domain_flags_secondary_only` | 15 flags, todos TECHNICAL, con regulación + contraparte |
| `test_cross_domain_ids_match_g0_diagnostic` | los 15 `finding_record_id` == diagnóstico de G0 |
| `test_router_does_not_mutate_input_findings` | L2 intacto tras `build_routing` |
| `test_human_only_are_all_rw0009_and_never_routed_to_llm` | 57 HUMAN_ONLY, todos RW-0009, ninguno a experto LLM |

---

## 5 · REPORTE DE FASE — G1 (formato v1.1)

```
FASE                    = G1 (router determinista)
PRE_COMMIT              = 3bacfd0  (tag shadow-G0)
POST_COMMIT            = <pendiente — no se commitea hasta el gate humano de G1>
WORKTREE               = /home/cmay/ivr-ia/.claude/worktrees/shadow-llm  (rama shadow/llm-interpretation-layer)
DIFF (prohibidos)      = VACÍO
                         · 0 modificaciones a ficheros existentes (git diff --stat HEAD vacío)
                         · 0 cambios en factory/regulatory/{findings,validation_v2,canonical,graph,retrieval}/
                         · 0 cambios en factory/layer9/ · 0 cambios en L0/L1/L2 · 0 en ledger/audit trail
                         · solo ficheros NUEVOS: factory/regulatory/shadow/{__init__,router}.py,
                           factory/tests/test_shadow_router.py, docs_plan/shadow_llm/{G1_ROUTER.md,G1_routing.json}
COMMANDS               = pytest factory/tests/test_shadow_router.py -q
                         python -m factory.regulatory.shadow.router  FINAL_GMP_CORPUS_FINDINGS.json  G1_routing.json  (×2, byte-idéntico)
                         PYTHONHASHSEED=random python <atestación run_v2_pipeline desde el código del worktree>
TEST_RESULTS           = 11 passed in 0.76s   (factory/tests/test_shadow_router.py)
INPUT_HASHES           = FINAL_GMP_CORPUS_FINDINGS.json  sha256 95a79f9b6276ff2a7972100764b308fa4b09f0027c6679ea831b441eb880f02c
OUTPUT_HASHES          = docs_plan/shadow_llm/G1_routing.json  sha256 212b5514c599728e83e22f7949cf6526fe948762eb0b1ab55ba084bc024826b1
                         factory/regulatory/shadow/router.py · factory/regulatory/shadow/__init__.py
                         factory/tests/test_shadow_router.py · docs_plan/shadow_llm/G1_ROUTER.md
FINGERPRINTS           = atestación desde el código del worktree (que YA contiene factory/regulatory/shadow/):
                         INPUT_CONFIG   3fcb3ae859091000b0e6c6cf2b4f51515e74665d658451b753c723d6e6e51668   ✅
                         GRAPH_SNAPSHOT 2fdda0e2ce513bc48b54038c5890a0b060e87a6e5c0d6d98b3d31fb149be3620   ✅
                         FINDINGS       235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23   ✅ (== baseline)
                         counts 342/90/25 · el paquete shadow NO mueve el fingerprint
LLM_CALLS              = 0
CLIENT_DATA_EGRESS     = 0  (el router no abre red; atestación bajo network_locked(), egress 0)
LLM_PROVIDER           = LOCAL  (N/A — no se ejecutó ningún modelo en G1)
ARTIFACTS              = ver OUTPUT_HASHES + docs_plan/shadow_llm/G1_routing.json (457 filas de routing)
GOVERNANCE_EVENTS      = ninguno  (G1 no crea ninguna decisión; ledger/audit trail sin tocar)
HUMAN_STATE_CHANGES    = 0
L2_MUTATIONS           = 0  (test test_router_does_not_mutate_input_findings)
DEVIATIONS             = ninguna
EXPECTED_VS_ACTUAL     = esperado: routing primario 285+98+17+57=457 · 0 UNROUTED · 15 cross_domain_flag
                                   secundarios · FINDINGS_FINGERPRINT sin mover
                         actual:   idéntico — 285/98/17/57 · 0 UNROUTED · 15 flags (== IDs del diagnóstico G0) ·
                                   FINDINGS_FINGERPRINT = 235f724a…
PROPOSED_VERDICT       = PASS
                         Router determinista implementado y probado (11/11). Routing primario exclusivo
                         reproduce 285/98/17/57 = 457 con 0 UNROUTED y 457 record_id únicos; 15
                         cross_domain_flag secundarios coinciden exactamente con los 15 del diagnóstico
                         de G0. Sin LLM, sin red, sin mutar L2, sin mover el fingerprint. Listo para el
                         gate humano de Capa 9 y la auditoría independiente de Devin; con su OK se
                         commitea el cierre de G1 y se crea el tag shadow-G1, habilitando G2 (contratos
                         de experto + evaluación de reutilización selectiva de v2_judgment).
```

---

## 6 · Qué decide el gate humano de G1

1. **Aceptar las reglas de routing** (§2) como contrato determinista de asignación experto↔finding.
2. **Aceptar `G1_routing.json`** (457 filas, sha256 `212b5514…`) como la asignación congelada para el arco.
3. **Aceptar el router** `factory/regulatory/shadow/router.py` como pieza de la capa shadow
   (nuevo paquete `factory/regulatory/shadow/`, aditivo, sin dependencias del lado LLM).
4. **Autorizar el commit de cierre de G1 y el tag `shadow-G1`**, y el paso a **G2**.

Nada de lo anterior habilita LLM, embeddings, PILOT nuevo, R2, PILOT-035 ni producción.

---

*G1 · router determinista. Sin LLM, sin red, sin mutar L2, sin mover el fingerprint. Detenido en
el gate humano. NO se inicia G2.*
