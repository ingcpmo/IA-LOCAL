# SHADOW · G3 — POST-PASS CROSS-DOMAIN + ESPECIFICACIÓN DEL REGULATORY RETRIEVAL GATEWAY

**Arco:** Capa LLM de interpretación sobre findings deterministas (diseño v1.1).
**Fase:** G3 — post-pass determinista que materializa las relaciones cross-domain en
`shadow/cross_domain_links.json` (**nunca** en `Finding.related_finding_ids`, corr. 2) +
especificación (no implementación) del Regulatory Retrieval Gateway.
**Modo:** SIN LLM · SIN red · determinista · SIN mover el `FINDINGS_FINGERPRINT`.
**Rama:** `shadow/llm-interpretation-layer` · **Base de fase:** `shadow-G2` → `e5458d3`.
**Gate previo:** G2 aprobado.

---

## 0 · Nota de alcance — el verificador fail-closed ya está en G2.1

El plan original (G0 §7) listaba "verificador determinista fail-closed" bajo G3. Por instrucción
de Capa 9 (mensaje del 2026-09-02), los verificadores deterministas se exigieron y demostraron
**dentro de G2** (`G2.1` `verify_expert_envelope`, `G2.2` `verify_report_coverage`,
`factory/regulatory/shadow/verifier.py`, `G2_verifier_report.json`). G3 no los reimplementa.
Alcance real de G3: **(a)** post-pass cross-domain, **(b)** especificación del Gateway.

---

## 1 · Qué produce G3

| Artefacto | Ruta | Naturaleza |
|---|---|---|
| Post-pass cross-domain (módulo) | `factory/regulatory/shadow/cross_domain.py` | determinista, CERO LLM/red, solo lectura de L2 |
| Test | `factory/tests/test_shadow_cross_domain.py` | 10 tests |
| Relaciones congeladas | `docs_plan/shadow_llm/cross_domain_links.json` | las 15 relaciones técnico↔regulatorio |
| Especificación del Gateway | §4 de este documento | **diseño, no implementación; no se habilita en G0–G5** |

---

## 2 · Post-pass cross-domain determinista

`cross_domain.py::build_cross_domain_links(findings, *, source_ref=None) -> dict`

**Regla — la misma que el router de G1** (una sola fuente de verdad): reutiliza
`router.build_routing().cross_domain_flag`. Una relación es un finding **TÉCNICO** cuyo
`technical_basis` nombra un token de regulación (`21_CFR_11.10(d/e/g)`, `ANNEX11_17`,
`ALCOA_ATTRIBUTABLE`) que también es `requirement_id` de un finding `regulatory_tier1`
(`REGULATORY_INCONCLUSIVE`) **del mismo documento**.

**Corrección 2 (auditor):** las relaciones viven **solo** en `cross_domain_links.json`.
`Finding.related_finding_ids` (campo de L2) **no se toca** — la acceptance verifica que ninguna
contraparte regulatoria de una relación aparece en el `related_finding_ids` del finding técnico
(ni por `finding_record_id` ni por `finding_id`). `assert_no_l2_mutation()` compara L2 byte a byte
antes/después del pass.

### Resultado sobre el corpus baseline (`cross_domain_links.json`)

```
total_links                15
by_shared_regulation       21_CFR_11.10(g) 5 · 21_CFR_11.10(d) 4 · ALCOA_ATTRIBUTABLE 4 ·
                           21_CFR_11.10(e) 4 · ANNEX11_17 2
by_document                RW-0005 6 · RW-0006 5 · RW-0011 1 · RW-0012 1 · RW-0014 2
by_technical_subtype       ALCOA_ATTRIBUTABLE_GAP 4 · AUTHORITY_CHECK_GAP 3 · ACCESS_CONTROL_GAP 2 ·
                           AUDIT_TRAIL_DESIGN_GAP 2 · AUDIT_TRAIL_INTEGRITY_GAP 2 · TECHNICAL_DESIGN_GAP 2
status_counts              PENDING_CROSS_DOMAIN_REVIEW 15
l2_related_finding_ids_written  0
acceptance.PASS            true
  total_links_is_15                                    true
  all_links_technical_primary                          true
  every_link_has_regulatory_counterpart                true
  link_ids_unique                                      true
  no_cross_domain_relation_in_l2_related_finding_ids   true
```

`link_id` estable y determinista: `cdl-0001 … cdl-0015`, orden por
`(document, technical_subtype, technical_finding_record_id)`. Los 15
`technical.finding_record_id` coinciden **exactamente** con
`CURRENT_FINDING_AGENT_ROUTING.json → cross_domain_same_requirement_family_detail`
(test `test_link_technical_ids_match_g0_diagnostic`).

`cross_domain_links.json` sha256: `11d99bf803ba571a1ff579089ada2b90242bb7cbefa184c2d293b436e08fcdd7`
(determinista — 2ª ejecución byte-idéntica).

Cada relación:

```
{
  "link_id": "cdl-0001",
  "relation": "TECHNICAL_GAP_vs_REGULATORY_INCONCLUSIVE_SAME_RULE",
  "status": "PENDING_CROSS_DOMAIN_REVIEW",
  "human_review_required": false,
  "l2_mutation": false,
  "document": "RW-0005",
  "technical": { finding_record_id, subtype, primary_bucket, page, anchored_quote, technical_basis },
  "shared_regulations": ["21_CFR_11.10(e)"],
  "regulatory_counterparts": [ { finding_record_id, requirement_id, subtype, page, machine_state }, … ]
}
```

---

## 3 · Hook para el Cross-domain Reviewer (G4b)

`cross_domain.py::apply_review_outcome(artifact, outcomes) -> artifact_nuevo`

`outcomes = {link_id: assessment}` donde `assessment ∈ ASSESSMENT_VALUES["CROSS_DOMAIN"]`
(`RECONCILED_CONSISTENT` · `DISAGREEMENT_PERSISTS` · `INDETERMINATE`).

- `DISAGREEMENT_PERSISTS` ⇒ `status = HUMAN_REVIEW_REQUIRED`, `human_review_required = true`
  (nunca se resuelve solo — diseño v1.1 §3 paso 6).
- assessment inválido ⇒ `ValueError` (fail-closed).
- `link_id` ausente en `outcomes` ⇒ conserva `PENDING_CROSS_DOMAIN_REVIEW`.
- Devuelve un artefacto **nuevo**; no muta el de entrada; **nunca toca L2**.

Tests: `test_apply_review_outcome_flags_human_review_on_disagreement`,
`..._rejects_invalid_assessment`, `test_missing_link_id_in_outcomes_keeps_pending`.

---

## 4 · ESPECIFICACIÓN del Regulatory Retrieval Gateway (diseño — NO se implementa ni habilita)

> Diseño v1.1 §6: *permitir en la arquitectura ≠ abrir la red ahora*. En **G0–G5 el canal 2
> (retrieval regulatorio externo) NO está habilitado**. Aquí se especifica el mecanismo
> gobernado; **no hay código, no hay allowlist activa, no hay tráfico**. `CRIT-E4` se mantiene.

### 4.1 · Propósito

Permitir que un experto (G4) obtenga una **referencia regulatoria pública** (texto de
`21 CFR §11.10(e)`, guía de la FDA sobre audit trail, etc.) para **contextualizar** su opinión —
nunca como evidencia de que el documento del cliente cumple.

### 4.2 · Modelo de tres canales (diseño v1.1 §6)

| Canal | Destino | Estado en G0–G5 |
|---|---|---|
| 1 · LOCAL MODEL ACCESS | `127.0.0.1` / Ollama | PERMITIDO (solo G4+) |
| 2 · PUBLIC REGULATORY WEB ACCESS | eCFR / FDA / EMA / PIC-S / ICH / WHO | **NO habilitado** — solo se especifica |
| 3 · CLIENT DATA EGRESS | PDF / claims / evidencia / finding / graph / ids de cliente | **PROHIBIDO** (CRIT-E1, todas las fases) |

### 4.3 · Contrato del Gateway (cuando Capa 9 lo autorice, post-G5)

```
Expert  --(¿necesita referencia externa?)-->  SÍ
   -> Gateway.fetch(regulation_token, purpose)
        REQUEST:  solo términos  ("21 CFR 11.10(e)", "FDA audit trail guidance")
                  NUNCA contenido del cliente (0 bytes de L0/L1/L2)
        SOURCE:   fuente pública de una allowlist que decide governance (no congelada aún)
        RESPONSE: documento público  ->  { text, url, retrieved_at, response_hash }
   -> Expert  (lo usa como EXTERNAL_REG_REFERENCE en su envoltura, nunca CLIENT_EVIDENCE)
```

Requisitos duros:

- **`CRIT-E1`**: el Gateway no transporta ni un byte de PDF/canonical/evidencia/finding/graph/id
  de cliente. Payload de salida = lista blanca de tokens de regulación + `purpose`.
- **`CRIT-E2`**: toda consulta auditada — `destination · timestamp · purpose · classification ·
  response_hash`. Registro append-only, separado del audit trail de gobernanza.
- **`CRIT-E3`**: ningún contenido documental del cliente sale a Internet sin autorización explícita.
- **Cache local** de respuestas públicas por `(regulation_token, source)` con `response_hash` —
  la referencia citada por un experto es reproducible y verificable.
- **Fail-closed**: sin allowlist firmada o sin autorización de Capa 9 → el Gateway **no
  responde**; el experto sigue sin referencia externa (degrada, no inventa).
- **Superficie mínima**: se difiere a una **mesa de diseño propia post-G5** (diseño v1.1 §6).
  Abrir el canal 2 en la primera versión shadow amplía la superficie de ataque sin beneficio
  para G0–G5.

### 4.4 · Enganche con los contratos de G2

`contracts.validate_output_envelope` ya trata `external_reg_references`: **nunca**
`source == CLIENT_EVIDENCE`, requiere `regulation` + `retrieved_at`. El Gateway, cuando exista,
llena exactamente ese bloque. Hoy ese bloque está siempre vacío (G0–G5).

---

## 5 · REPORTE DE FASE — G3 (formato v1.1)

```
FASE                    = G3 (post-pass cross-domain + especificación del Regulatory Retrieval Gateway)
PRE_COMMIT              = e5458d3  (tag shadow-G2)
POST_COMMIT            = <pendiente — no se commitea hasta el gate humano de G3>
WORKTREE               = /home/cmay/ivr-ia/.claude/worktrees/shadow-llm  (rama shadow/llm-interpretation-layer)
DIFF (prohibidos)      = VACÍO
                         · 0 modificaciones a ficheros existentes (git diff --stat HEAD vacío)
                         · 0 cambios en factory/regulatory/{findings,validation_v2,canonical,graph,retrieval,v2_judgment}/
                         · 0 cambios en factory/engines/ · 0 en L0/L1/L2 · 0 en ledger/audit trail
                         · solo ficheros NUEVOS: factory/regulatory/shadow/cross_domain.py,
                           factory/tests/test_shadow_cross_domain.py,
                           docs_plan/shadow_llm/{G3_CROSS_DOMAIN_AND_GATEWAY.md,cross_domain_links.json}
COMMANDS               = pytest factory/tests/test_shadow_router.py factory/tests/test_shadow_contracts.py \
                                factory/tests/test_shadow_verifier.py factory/tests/test_shadow_cross_domain.py -q
                         python -m factory.regulatory.shadow.cross_domain  FINAL_GMP_CORPUS_FINDINGS.json  cross_domain_links.json  (×2, byte-idéntico)
                         PYTHONHASHSEED=random python <atestación run_v2_pipeline desde el código del worktree>
TEST_RESULTS           = 49 passed in 1.10s
                         (11 router + 16 contracts + 12 verifier + 10 cross_domain)
INPUT_HASHES           = FINAL_GMP_CORPUS_FINDINGS.json  sha256 95a79f9b6276ff2a7972100764b308fa4b09f0027c6679ea831b441eb880f02c
OUTPUT_HASHES          = docs_plan/shadow_llm/cross_domain_links.json  sha256 11d99bf803ba571a1ff579089ada2b90242bb7cbefa184c2d293b436e08fcdd7
                         factory/regulatory/shadow/cross_domain.py      sha256 50179dcb77517ddbf6578cb51be704aedc697c0127c8af2fb7d55e1eb61aa709
                         factory/tests/test_shadow_cross_domain.py
                         docs_plan/shadow_llm/G3_CROSS_DOMAIN_AND_GATEWAY.md
FINGERPRINTS           = atestación desde el código del worktree (con factory/regulatory/shadow/cross_domain.py presente):
                         INPUT_CONFIG   3fcb3ae859091000b0e6c6cf2b4f51515e74665d658451b753c723d6e6e51668   ✅
                         GRAPH_SNAPSHOT 2fdda0e2ce513bc48b54038c5890a0b060e87a6e5c0d6d98b3d31fb149be3620   ✅
                         FINDINGS       235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23   ✅ (== baseline)
                         counts 342/90/25 · el post-pass NO mueve el fingerprint
LLM_CALLS              = 0
CLIENT_DATA_EGRESS     = 0  (G3 no abre red; el Gateway es SOLO especificación, canal 2 NO habilitado)
LLM_PROVIDER           = LOCAL  (N/A — G3 no ejecuta ningún modelo)
ARTIFACTS              = cross_domain_links.json (15 relaciones, status PENDING_CROSS_DOMAIN_REVIEW)
GOVERNANCE_EVENTS      = ninguno
HUMAN_STATE_CHANGES    = 0
L2_MUTATIONS           = 0  (assert_no_l2_mutation; tests test_post_pass_does_not_mutate_l2_findings,
                             test_relation_not_present_in_any_related_finding_ids)
CRIT                   = CRIT-0 ✅ · CRIT-H ✅ · CRIT-L2 ✅ · CRIT-E (E1–E4) ✅   (ver §6)
DEVIATIONS             = ninguna
EXPECTED_VS_ACTUAL     = esperado: 15 relaciones cross-domain en shadow/cross_domain_links.json, NUNCA en
                                   related_finding_ids; hook DISAGREEMENT_PERSISTS -> HUMAN_REVIEW_REQUIRED;
                                   Gateway especificado pero NO habilitado; fingerprint sin mover
                         actual:   15 links (IDs == diagnóstico G0), acceptance.PASS=true,
                                   no_cross_domain_relation_in_l2_related_finding_ids=true, L2_MUTATIONS=0,
                                   apply_review_outcome flaggea HUMAN_REVIEW_REQUIRED, Gateway = §4 (solo diseño),
                                   FINDINGS_FINGERPRINT = 235f724a…
PROPOSED_VERDICT       = PASS
                         Post-pass determinista implementado y probado (10/10). 15 relaciones cross-domain
                         materializadas SOLO en shadow/cross_domain_links.json — 0 escritura en
                         Finding.related_finding_ids (corr. 2), L2 byte-idéntico antes/después. IDs de las
                         15 == diagnóstico de G0. Hook apply_review_outcome: DISAGREEMENT_PERSISTS del
                         Cross-domain Reviewer (G4b) -> HUMAN_REVIEW_REQUIRED, nunca se resuelve solo.
                         Regulatory Retrieval Gateway ESPECIFICADO (§4); canal 2 NO habilitado en G0–G5
                         (CRIT-E4 intacto). Sin LLM, sin red, sin mutar L2, sin mover el fingerprint. 49/49
                         tests. CRIT-0/H/L2/E ✅. Listo para el gate humano de Capa 9 y la auditoría
                         independiente de Devin; con su OK se commitea el cierre de G3 y se crea el tag
                         shadow-G3, habilitando el gate + PILOT firmada previo a G4a (Technical Expert).
```

---

## 6 · Verificación de criterios CRIT aplicables a G3

| CRIT | Estado en G3 |
|---|---|
| **CRIT-0** baseline sin tocar | **✅** `FINDINGS_FINGERPRINT = 235f724a…`, `INPUT_CONFIG 3fcb3ae8…`, `GRAPH_SNAPSHOT 2fdda0e2…`, 342/90/25 (re-atestado desde el código del worktree con `cross_domain.py` presente) |
| **CRIT-H** gate humano intacto | **✅** `human_gate_intact = True`; `HUMAN_STATE_CHANGES = 0`; las relaciones nacen `PENDING_CROSS_DOMAIN_REVIEW`; `DISAGREEMENT_PERSISTS` ⇒ `HUMAN_REVIEW_REQUIRED` (nunca auto-resuelto) |
| **CRIT-L2** inmutabilidad de L2 | **✅** `L2_MUTATIONS = 0` (`assert_no_l2_mutation` byte a byte; tests dedicados). Corr. 2: la relación cross-domain **no** se escribe en `related_finding_ids` (acceptance `no_cross_domain_relation_in_l2_related_finding_ids = true`) |
| **CRIT-E** (E1–E4) | **✅** G3 no abre red (0 sockets); el Regulatory Retrieval Gateway es **solo especificación** — canal 2 **NO habilitado** (CRIT-E4); `document_egress_bytes = 0`; 0 llamadas LLM; `LLM_PROVIDER = LOCAL` |

---

## 7 · Qué decide el gate humano de G3

1. **Aceptar el post-pass cross-domain** y `cross_domain_links.json` (15 relaciones,
   sha256 `11d99bf8…`) como el conjunto congelado de relaciones del arco.
2. **Confirmar corr. 2**: las relaciones viven solo en shadow; `Finding.related_finding_ids`
   intacto; L2 byte-idéntico.
3. **Aceptar el hook `apply_review_outcome`** (DISAGREEMENT_PERSISTS → HUMAN_REVIEW_REQUIRED)
   como contrato de entrada del Cross-domain Reviewer de G4b.
4. **Aceptar la especificación del Regulatory Retrieval Gateway** (§4) **como diseño**, con el
   canal 2 **NO habilitado** en G0–G5 (se difiere a mesa propia post-G5).
5. **Autorizar el commit de cierre de G3 y el tag `shadow-G3`**.

El paso a **G4** exige, además del gate de G3, una **`PILOT_EXECUTION` vigente firmada**
(`corpus_runner._select_pilot_execution_instance`; no proponer una nueva si hay vigente con
presupuesto). Nada de lo anterior habilita LLM, embeddings, PILOT nuevo, R2, PILOT-035, el canal
regulatorio externo ni producción.

---

*G3 · post-pass cross-domain determinista + especificación del Gateway. Sin LLM, sin red, sin
mutar L2, sin mover el fingerprint, sin abrir el canal regulatorio externo. 49/49 tests.
Detenido en el gate humano. NO se inicia G4.*
