# SHADOW · G3.1 — COMPOSER ESQUELETO DETERMINISTA (corrección de auditoría)

**Arco:** Capa LLM de interpretación sobre findings deterministas (diseño v1.1).
**Fase:** G3.1 — completar el **Composer esqueleto determinista** que exige el plan y que la
auditoría externa de G3 detectó como faltante.
**Alcance:** SOLO G3.1. No se rediseña G3; se conserva lo ya implementado (post-pass cross-domain
`cross_domain.py` + especificación del Gateway). El tag `shadow-G3` (`bd79541`) **no se toca**:
representa el estado auditado.
**Modo:** DETERMINISTA · SIN LLM · SIN red · sin re-juzgar L2 · SIN mover el `FINDINGS_FINGERPRINT`.
**Rama:** `shadow/llm-interpretation-layer` · **Base:** `shadow-G3` → `bd79541`.

---

## 1 · Hallazgo de la auditoría

> "Falta el Composer esqueleto determinista exigido por el plan."

Correcto. G3 entregó el post-pass cross-domain y la spec del Gateway, pero **no** el esqueleto
del reporte narrativo (diseño v1.1 §3 paso 7: *narrativa por documento × regulación, cada
afirmación anclada a `finding_record_id`*). G3.1 lo completa **en modo determinista**: la
estructura, la agrupación y la trazabilidad; la narrativa del LLM y la opinión de experto quedan
**PENDIENTES** (G4).

---

## 2 · Qué produce G3.1

| Artefacto | Ruta | Naturaleza |
|---|---|---|
| Composer esqueleto (módulo) | `factory/regulatory/shadow/composer.py` | determinista, CERO LLM/red, solo lectura de L2 |
| Test | `factory/tests/test_shadow_composer.py` | 11 tests |
| Esqueleto congelado | `docs_plan/shadow_llm/G3_1_composer_skeleton.json` | 66 secciones (documento × regulación), 457 entradas |
| Cross-check contra `report_v2` | `docs_plan/shadow_llm/G3_1_report_v2_check.json` | verificación del criterio congelado de G3.1 |

Es un artefacto **hermano** de `factory/regulatory/findings/report_v2.py` (el reporte factual de
L2). **No lo toca ni lo reemplaza** — `report_v2.py` queda byte-idéntico (`git diff --stat HEAD`
vacío).

---

## 3 · Contrato del esqueleto (criterio prefijado)

### 3.1 · Modo determinista, sin LLM

`mode = "DETERMINISTIC_SKELETON"`, `llm = "NONE"`, `narrative_status = "PENDING_LLM_COMPOSER"`.
0 llamadas a modelo, 0 red.

### 3.2 · Cobertura exacta 457/457

`build_composer_skeleton()` → cada `finding_record_id` L2 en **exactamente una** sección.
Verificado con `verifier.verify_report_coverage` (G2.2):

```
total_findings            457
unique_finding_record_id  457
coverage                  covered=true · total_l2=457 · referenced_valid=457 · missing=[] · unsupported=[]
every_finding_in_exactly_one_section  true
```

### 3.3 · Agrupación prevista por el plan — **documento × regulación**

`regulation_key(finding)` determinista:

| Tipo de finding | clave de regulación |
|---|---|
| `regulatory_tier1` | prefijo de familia del `requirement_id` (`21_CFR_11.10(d)`, `ANNEX11_9`, `ALCOA_ATTRIBUTABLE`, …) |
| completitud técnica (`technical_basis`) | primer token de regulación del `technical_basis` (orden estable); el resto en `also_regulations` |
| funcional / trazabilidad (sin regulación) | `"(trazabilidad — sin regulación directa)"` |
| documento `RW-0009` (NOT_ANALYZABLE) | `"(documento NOT_ANALYZABLE — requiere revisión humana)"` — sección propia |

Resultado: **66 secciones**. Secciones por documento: RW-0005 14 · RW-0006 14 · RW-0009 1 ·
RW-0011 12 · RW-0012 13 · RW-0014 12.
Entradas por documento (== L2): RW-0005 88 · RW-0006 133 · RW-0009 57 · RW-0011 58 · RW-0012 62 ·
RW-0014 59.
Entradas por bucket primario (== G1 routing): REGULATORY 285 · FUNCTIONAL_TRACEABILITY 98 ·
TECHNICAL 17 · HUMAN_ONLY 57.

`section_id` estable `sec-0001…sec-0066`, orden `(document, regulation)`; entradas dentro de la
sección por `(page, primary_bucket, finding_record_id)`.

### 3.4 · Cada finding trazable · narrativa LLM PENDIENTE · sin re-juzgar L2

Cada entrada:

```
finding_record_id · finding_id · primary_bucket (de G1) · finding_class · subtype ·
requirement_id · risk_band · machine_state · human_state · document · page ·
also_regulations · cross_domain_link_ids (de cross_domain_links.json) ·
anchored_quote_l2   <- cita L2 VERBATIM (trazabilidad)
rationale_l2        <- rationale L2 VERBATIM
shadow_expert_assessment = null   <- PENDIENTE (G4)
shadow_narrative         = null   <- PENDIENTE (G4e, se marcará [SHADOW / NO GOBERNADO])
narrative_status         = "PENDING_LLM_COMPOSER"
```

`acceptance.no_rejudge_l2 = true`: `subtype/risk_band/machine_state/human_state/document/page` de
cada entrada se re-comparan contra el finding L2 → **idénticos**. El esqueleto **no cambia** ni
interpreta ningún campo L2. `human_state = UNREVIEWED` en las 457.

`cross_domain_link_ids`: los 15 técnicos de `cross_domain_links.json` llevan su(s) `cdl-####`
(+ las contrapartes regulatorias); el resto, lista vacía.

### 3.5 · No muta L2

`build_composer_skeleton()` compara `findings` (JSON canónico) antes/después → idéntico
(test `test_composer_does_not_mutate_l2`; el `__main__` aborta si detecta mutación).

---

## 4 · G3.1 — verificación de `report_v2` frente a la baseline (criterio congelado)

`docs_plan/shadow_llm/G3_1_report_v2_check.json` — se corrió `run_v2_pipeline` sobre los 6 docs
(código del worktree, con `shadow/composer.py` presente) y se extrajo
`compliance_matrices/final_report_v2.json`. Criterio de G3.1: el esqueleto (a) cubre **el mismo
conjunto** de `finding_record_id` que `report_v2` y (b) **no altera** ningún hecho L2 que
`report_v2` reporta.

```
report_v2.py                     git diff --stat HEAD = VACÍO   (intacto)
report_v2 summary.total_findings  457
n finding_record_id (report_v2)   457
same_finding_record_id_set        true    (report_v2 ∩ composer = 457; 0 only-in-either)
l2_fact_mismatches                0       (subtype · risk_band · machine_state · human_state · page · document)
composer acceptance.PASS          true
FINDINGS_FINGERPRINT              235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23  (== baseline)
G3.1 report_v2 check PASS         true
```

---

## 5 · Verificación CRIT (intactos)

| CRIT | Estado en G3.1 |
|---|---|
| **CRIT-0** baseline sin tocar | **✅** `FINDINGS_FINGERPRINT = 235f724a…`, `INPUT_CONFIG 3fcb3ae8…`, `GRAPH_SNAPSHOT 2fdda0e2…`, counts 342/90/25 (re-atestado desde el código del worktree con `composer.py` presente); `report_v2.py` byte-idéntico |
| **CRIT-H** gate humano intacto | **✅** `human_gate_intact = True`; `HUMAN_STATE_CHANGES = 0`; las 457 entradas `human_state = UNREVIEWED`; narrativa y opinión de experto = PENDIENTE (nada auto-concluido) |
| **CRIT-L2** inmutabilidad de L2 | **✅** `L2_MUTATIONS = 0` (test dedicado + guarda en `__main__`); `no_rejudge_l2 = true` (facts L2 re-comparados y verbatim); `related_finding_ids` no se toca |
| **CRIT-E** (E1–E4) | **✅** G3.1 no abre red (0 sockets); el composer solo lee L2 ya extraído; `document_egress_bytes = 0`; 0 llamadas LLM; `LLM_PROVIDER = LOCAL`; canal regulatorio externo NO habilitado |

---

## 6 · Tests (resultado real)

```
pytest factory/tests/test_shadow_router.py factory/tests/test_shadow_contracts.py \
       factory/tests/test_shadow_verifier.py factory/tests/test_shadow_cross_domain.py \
       factory/tests/test_shadow_composer.py -q
  ->  60 passed in 1.24s
      (11 router + 16 contracts + 12 verifier + 10 cross_domain + 11 composer)
```

`test_shadow_composer.py` (11): modo determinista sin LLM · cobertura 457/457 · agrupación
documento × regulación disjunta · conteos por documento/bucket == L2 · cada entrada trazable y
sin re-juicio · narrativa/experto PENDIENTE · 15 `cross_domain_link_ids` en los técnicos · no
muta L2 · salida determinista · `assert_full_coverage_or_raise` pasa en baseline y falla con 456.

---

## 7 · REPORTE DE FASE — G3.1 (formato v1.1)

```
FASE                    = G3.1 (Composer esqueleto determinista — corrección de auditoría de G3)
PRE_COMMIT              = bd79541  (tag shadow-G3 — NO se mueve)
POST_COMMIT            = <pendiente — no se commitea hasta el gate humano de G3.1>
WORKTREE               = /home/cmay/ivr-ia/.claude/worktrees/shadow-llm  (rama shadow/llm-interpretation-layer)
DIFF (prohibidos)      = VACÍO
                         · 0 modificaciones a ficheros existentes (git diff --stat HEAD vacío)
                         · report_v2.py byte-idéntico · 0 cambios en L0/L1/L2 · 0 en ledger/audit trail
                         · 0 cambios a los artefactos ya auditados de G3 (cross_domain.py, cross_domain_links.json,
                           G3_CROSS_DOMAIN_AND_GATEWAY.md) · el tag shadow-G3 permanece en bd79541
                         · solo ficheros NUEVOS: factory/regulatory/shadow/composer.py,
                           factory/tests/test_shadow_composer.py,
                           docs_plan/shadow_llm/{G3_1_COMPOSER_SKELETON.md,G3_1_composer_skeleton.json,G3_1_report_v2_check.json}
COMMANDS               = pytest factory/tests/test_shadow_{router,contracts,verifier,cross_domain,composer}.py -q
                         python -m factory.regulatory.shadow.composer  FINAL_GMP_CORPUS_FINDINGS.json  G3_1_composer_skeleton.json  (×2, byte-idéntico)
                         PYTHONHASHSEED=random python <g3_1_report_v2_check: run_v2_pipeline + cross-check contra final_report_v2.json>
TEST_RESULTS           = 60 passed in 1.24s
OUTPUT_HASHES          = docs_plan/shadow_llm/G3_1_composer_skeleton.json  sha256 32572ad7a2123ae7441e76e8b5bb5b2f982176ac07bdd11058c28ff8a42cb885
                         docs_plan/shadow_llm/G3_1_report_v2_check.json     sha256 03115ba37f243cf949e9d1f69c5f39b5ad7d2fc116a7979e5bff0db2aac8fc16
                         factory/regulatory/shadow/composer.py             sha256 09dc9cb065524809b713374dfddd8ac792a6e5a515133f8181ff0d0aaf66e70f
                         factory/tests/test_shadow_composer.py             sha256 5d9bc4eda250d674b0ffcd56c356d30e781300da46f4b167ed42d0925e865c14
                         docs_plan/shadow_llm/G3_1_COMPOSER_SKELETON.md
FINGERPRINTS           = INPUT_CONFIG   3fcb3ae859091000b0e6c6cf2b4f51515e74665d658451b753c723d6e6e51668   ✅
                         GRAPH_SNAPSHOT 2fdda0e2ce513bc48b54038c5890a0b060e87a6e5c0d6d98b3d31fb149be3620   ✅
                         FINDINGS       235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23   ✅ (== baseline)
                         counts 342/90/25 · el composer NO mueve el fingerprint · report_v2.py intacto
LLM_CALLS              = 0
CLIENT_DATA_EGRESS     = 0
LLM_PROVIDER           = LOCAL  (N/A — G3.1 no ejecuta ningún modelo)
ARTIFACTS              = G3_1_composer_skeleton.json (66 secciones documento × regulación, 457 entradas)
                         G3_1_report_v2_check.json (same_id_set=true, l2_fact_mismatches=0, PASS=true)
GOVERNANCE_EVENTS      = ninguno
HUMAN_STATE_CHANGES    = 0
L2_MUTATIONS           = 0
CRIT                   = CRIT-0 ✅ · CRIT-H ✅ · CRIT-L2 ✅ · CRIT-E (E1–E4) ✅   (ver §5)
DEVIATIONS             = ninguna
EXPECTED_VS_ACTUAL     = esperado: composer esqueleto DETERMINISTA (0 LLM) que cubre 457/457, agrupa por
                                   documento × regulación, mantiene cada finding trazable con narrativa LLM
                                   PENDIENTE y sin re-juzgar L2; report_v2 verificado contra la baseline;
                                   CRIT-0/H/L2/E intactos; tag shadow-G3 sin mover
                         actual:   457/457 cubiertos (66 secciones, disjuntas), by_document/by_bucket == L2/G1,
                                   no_rejudge_l2=true, narrative_all_pending=true, L2_MUTATIONS=0,
                                   report_v2 same_id_set=true / l2_fact_mismatches=0 / PASS=true,
                                   FINDINGS_FINGERPRINT=235f724a…, shadow-G3 en bd79541. 60/60 tests.
PROPOSED_VERDICT       = PASS  (G3.1 completada; cierra el hallazgo de la auditoría de G3)
```

---

## 8 · Qué decide el gate humano de G3.1

1. **Aceptar el Composer esqueleto determinista** (`composer.py`) y `G3_1_composer_skeleton.json`
   (66 secciones documento × regulación, 457 entradas, sha256 `32572ad7…`).
2. **Confirmar** cobertura 457/457, agrupación prevista, trazabilidad verbatim, narrativa LLM
   PENDIENTE, 0 re-juicio de L2, `report_v2` verificado (`G3_1_report_v2_check.json`).
3. **Confirmar** CRIT-0/H/L2/E intactos y que el tag `shadow-G3` no se movió.
4. **Autorizar el commit de cierre de G3.1** (sobre `bd79541`) y el tag correspondiente.

El paso a **G4** sigue exigiendo, además, una **`PILOT_EXECUTION` vigente firmada**. Nada de
esto habilita LLM, embeddings, PILOT nuevo, R2, PILOT-035, el canal regulatorio externo ni
producción.

---

*G3.1 · Composer esqueleto determinista. Sin LLM, sin red, sin re-juzgar L2, sin mover el
fingerprint, sin tocar `report_v2.py` ni el tag `shadow-G3`. 60/60 tests. Detenido en el gate
humano. NO se inicia G4.*
