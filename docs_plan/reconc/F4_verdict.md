# F4 — VEREDICTO: reconciliación governance / audit / ledger (D5, D6, D7, D8 + corrección 8)

**Plan de reconciliación v1.1 · FASE 4 · precondición F3 PASS ✅.**
**CERO hand-edits.** `sha256(decisions_v2.jsonl)` inicio == fin == `1b0c7cf82ed7b2b056aade48c7e7dfa41142b108f94dfda0d0dc9836206a4af4`. Audit trail y `fork_baseline.json` sin tocar.

---

## Resultados por acción

| # | tema | resultado | doc |
|---|---|---|---|
| **1** | **Colisión / reuso de ID** (`ARTIFACT_VERSION-2026-022..032`) — obligatoria y primero | **VEREDICTO: ID_COLLISION** (probado: `-022..-025` emitidos 2×, `-024/-025` con `target_set_hash` distinto entre eventos). **Causa raíz:** `decision_store_v2.next_instance_id` (L189) acuña `max(ids en decisions_v2.jsonl) + 1` — lee el JSONL **mutable/revertible**, NO el audit trail append-only. Un `git checkout` del ledger → contador regresa → id reusado. **Corrección PROPUESTA** (no aplicada): `max()` sobre la unión JSONL ∪ audit trail (o contador monótono dedicado). Código de servicio → fase propia. | `F4_id_collision_analysis.md` |
| **2** | **D5 — reconciliación del ledger** | `-022..-025` (2026-09-01, E1-3 + E1_ACCEPTANCE) = **GOBERNADA_Y_RECUPERABLE**, ya en el ledger, **nada que re-emitir**. `-022/023, 029..032` (2026-08-31) = **HISTÓRICA_SIN_PERSISTENCIA + SUPERSEDIDA** por E1-3. `-024..028` (2026-08-31, `tsh e10fc3a969e2` / `46758dfa79fa`) = **NO_RECONCILIABLE** (justificada: artefacto no identificable desde el audit trail). Ninguna re-emisión por Mission Control necesaria. | `F4_ledger_reconciliation.md` |
| **3** | **D6 — ¿H1 requiere asiento gobernado?** | **CERRADO por contrato.** `technical_completeness_rules.yaml` **NO** está en `ARTIFACT_CLASSES = ("catalog","applicability_matrix","evidence_pack","prompt","golden_dataset")` (`artifact_version_guard.py:76-77`) ni en `enumerate_artifacts()`. El registro por metadata + commit (`24549a3`) es el **mecanismo correcto** para este gate a la medida. | `F4_h1_contract_determination.md` |
| **4** | **D7 — fork histórico** | **NO REQUIERE ACCIÓN.** `FORK-2026-06-15-001` **ya está aceptado** por `AUDIT_EXCEPTION-2026-002` (Capa 9 / Cesar, `ACTIVE`, 2026-07-30), campo `accepted_by_decision` poblado, `CHAIN_CONTINUITY = ACCEPTED_WITH_DOCUMENTED_EXCEPTION` (cadena NO reescrita). El flag raíz `frozen_by_is_human_acceptance: false` concierne al freeze del baseline, no al fork, y es correcto que siga `false` (spec `AUDIT_FORK_REMEDIATION_SPEC.md:442`). | `F4_fork_disposition.md` |
| **5** | **D8 — `E1_SIGNATURE_HISTORY.md` divergente** | **ALINEADO** (append-only). Añadidos los bloques **E1-3 FIRMADA** (`verdict_set_sha256 4e23a146…`, counts `{CORRECT:66, WRONG_NODE:1, SPURIOUS:0, AMBIGUOUS:0}`, ledger `-022/-023`) y **E1_ACCEPTANCE = PASS** (ledger `-024/-025`), con aviso de la colisión de `instance_id`. La decisión firmada NO se altera. | `docs_plan/E1_SIGNATURE_HISTORY.md` (append) |

---

## Verificación (Devin)

| chequeo F4 | resultado |
|---|---|
| (a) análisis de colisión de IDs correcto y reproducible | ✅ `grep -oE "ARTIFACT_VERSION-2026-0(2[2-9]\|3[0-2])" factory/audit/factory_audit.jsonl \| sort \| uniq -c` → 022..025 ×2, 026..032 ×1 · `sed -n '179,189p' decision_store_v2.py` → `max(used)` del JSONL |
| (b) decisiones clasificadas y tratadas | ✅ `F4_ledger_reconciliation.md` — 5 clases, disposición por id |
| (c) D6 cita el contrato | ✅ `F4_h1_contract_determination.md` cita `ARTIFACT_CLASSES` + `enumerate_artifacts()` |
| (d) fork con disposición formal, cadena no reescrita | ✅ `F4_fork_disposition.md` — `AUDIT_EXCEPTION-2026-002` ACTIVE; `fork_baseline.json` sin tocar |
| (e) counts E1-3 doc == payload | ✅ `E1_SIGNATURE_HISTORY.md` ahora lleva `{CORRECT:66, WRONG_NODE:1, SPURIOUS:0, AMBIGUOUS:0}` == ledger `-022`/`-023` payload |
| (f) CERO hand-edits (sha256 del ledger solo cambia por líneas del servicio) | ✅ `sha256(decisions_v2.jsonl)` inicio == fin == `1b0c7cf8…`. F4 no tocó ledger / audit trail / fork_baseline. |

---

## VEREDICTO

- Colisión de IDs: **resuelta como diagnóstico concluyente** (ID_COLLISION probado, causa raíz
  citada, corrección propuesta gobernada — no reescrita).
- Ledger reconciliado sin hand-edits; el estado 2026-09-01 (`-022..-025`) es correcto y
  autoritativo; las entradas históricas quedan en el audit trail append-only.
- D6 cerrado por contrato · D7 sin acción (ya gobernado) · D8 alineado (append-only).

**`PROPOSED_VERDICT F4 = PASS`** (todo lo anterior + CERO hand-edits + análisis de colisión
concluyente), **con PARTIAL residual**: `-024..-028` (2026-08-31) quedan **NO_RECONCILIABLE
justificada** (artefactos no identificables), y la **corrección del generador de IDs**
(`decision_store_v2.next_instance_id`) queda como **hallazgo para una fase/decisión propia de
Capa 9** — F4 no toca código de servicio.

---

## REPORTE FORMATO OBLIGATORIO — F4

```
FASE            = F4 (reconciliación governance / audit / ledger)
PRE_COMMIT      = 484abea  (reconc-F3)
POST_COMMIT     = <commit reconc-F4>
WORKTREE_PRE    = decisions_v2.jsonl con +4 líneas del servicio (2026-09-01) SIN commitear (estado F0)
WORKTREE_POST   = idéntico (F4 NO tocó el ledger) + docs_plan/reconc/F4_* + E1_SIGNATURE_HISTORY.md (append)
DIFF            = docs_plan/reconc/{F4_id_collision_analysis.md, F4_ledger_reconciliation.md,
                  F4_h1_contract_determination.md, F4_fork_disposition.md, F4_verdict.md} ;
                  docs_plan/E1_SIGNATURE_HISTORY.md (append-only, +40 líneas)
COMMANDS        = grep audit trail ; sed decision_store_v2.py:179-189 ; cat fork_baseline.json ;
                  PYTHONPATH=. python (resolución de target_set_hash / lectura del ledger) ; sha256sum ledger
TEST_RESULTS    = sha256(decisions_v2.jsonl) inicio == fin == 1b0c7cf82ed7b2b056aade48c7e7dfa41142b108f94dfda0d0dc9836206a4af4
                  (F4 no editó ledger / audit trail / fork_baseline)
INPUT_HASHES    = ledger 1b0c7cf8… ; target_set_hash H10 = 84c54618241c… ; e10fc3a969e2… ; 46758dfa79fa…
OUTPUT_HASHES   = n/a (F4 no congela artefactos binarios)
FINGERPRINTS    = n/a en F4 (F5)
ARTIFACTS       = docs_plan/reconc/F4_*.md ; docs_plan/E1_SIGNATURE_HISTORY.md
GOVERNANCE_EVENTS = ninguno escrito por Claude. (Las 4 líneas de servicio 2026-09-01 son pre-F4.)
DEVIATIONS      = ninguna. Toda propuesta de corrección (generador de IDs) es PROPUESTA, no aplicada.
EXPECTED_VS_ACTUAL:
  EXPECTED: colisión resuelta (o descartada con prueba) ; ledger reconciliado por servicio ;
            D6 por contrato ; fork documentado ; doc E1-3 alineada ; 0 hand-edits.
  ACTUAL:   ID_COLLISION PROBADO + causa raíz citada + corrección propuesta ; ledger sin tocar,
            estado 2026-09-01 autoritativo, históricos en audit trail ; D6 CERRADO (cita de
            código) ; D7 ya gobernado (AUDIT_EXCEPTION-2026-002) ; E1_SIGNATURE_HISTORY alineada
            (append) ; sha256 del ledger sin cambio.
PROPOSED_VERDICT = PASS (con NO_RECONCILIABLE justificada para -024..-028 y corrección del
                   generador de IDs pendiente de fase/decisión propia).
```
