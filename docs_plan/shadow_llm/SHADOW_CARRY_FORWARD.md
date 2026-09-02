# SHADOW · REGISTRO DE CARRY-FORWARD Y REVISIONES CORRECTIVAS

Registro de los hallazgos de auditoría externa sobre fases ya cerradas del arco
"Capa LLM de interpretación sobre findings deterministas" (diseño v1.1) y sus correcciones
puntuales. No reabre fases; cada corrección es un commit/tag independiente sobre la punta de
`shadow/llm-interpretation-layer`.

---

## CF-1 · `related_finding_ids` ausente de `MUST_NOT_CHANGE_FIELDS` (G2)

| | |
|---|---|
| **Origen** | Auditoría externa de G2 (carry-forward). |
| **Hallazgo** | `MUST_NOT_CHANGE_FIELDS` (contrato de inmutabilidad L2 del verificador fail-closed G2.1) tenía 11 campos y **omitía `related_finding_ids`** — campo de L2 que la capa shadow no escribe (corr. 2 del auditor de diseño). Una envoltura de experto que lo alterase no era rechazada por ese motivo. |
| **Corrección puntual** | `shadow-G2-r1`. `contracts.MUST_NOT_CHANGE_FIELDS` pasa de 11 a **12 campos** (+ `related_finding_ids`); `_l2_snapshot` lo resuelve a `list(finding.get("related_finding_ids") or [])`. `verifier.adversarial_demo` gana un 4º fixture obligatorio: `related_finding_ids` alterado → `SHADOW_REJECTED`. Artefactos congelados regenerados: `G2_contracts.json`, `G2_verifier_report.json`. |
| **Ficheros tocados** | `factory/regulatory/shadow/{contracts,verifier}.py`, `factory/tests/test_shadow_{contracts,verifier}.py`, `docs_plan/shadow_llm/{G2_contracts.json,G2_verifier_report.json}`. **Nada más.** |
| **No cambia** | L0/L1/L2 · `FINAL_GMP_CORPUS_FINDINGS.json` · `report_v2.py` · `factory/regulatory/validation_v2/` · `FINDINGS_FINGERPRINT` (`235f724a…`) · `INPUT_CONFIG` (`3fcb3ae8…`) · `GRAPH_SNAPSHOT` (`2fdda0e2…`) · counts 342/90/25 · ledger/audit trail · tags previos. |
| **CRIT** | CRIT-0 ✅ · CRIT-H ✅ · CRIT-L2 ✅ · CRIT-E ✅. |
| **Tests** | `pytest test_shadow_{router,contracts,verifier,cross_domain,composer}` → 62 passed. |
| **Comportamiento** | Único cambio: una envoltura cuyo bloque `MUST_NOT_CHANGE` omita o altere `related_finding_ids` ahora → `SHADOW_REJECTED` (más estricto, correcto). Los controles positivos (bloque construido con `must_not_change_block()`) no cambian. |
| **Nota de consistencia** | `G2_CONTRACTS.md` (§2, texto auditado a `shadow-G2`) dice "11 campos" — **representa el estado auditado**; el conteo autoritativo tras `shadow-G2-r1` es **12** (ver `G2_contracts.json` regenerado). El .md no se reabre. |
| **Estado** | `PENDIENTE` de auditoría externa **solo de este carry-forward**. Si `PASS` → **CERRADO**. |

---

## CF-2 · Composer esqueleto determinista faltante (G3)

| | |
|---|---|
| **Origen** | Auditoría externa de G3. |
| **Hallazgo** | G3 entregó el post-pass cross-domain y la especificación del Gateway, pero **no** el Composer esqueleto determinista que exige el plan (diseño v1.1 §3 paso 7). |
| **Corrección** | **`shadow-G3.1`** (`9e819bf`) — commit/tag independiente sobre `shadow-G3` (`bd79541`, **no movido**). `factory/regulatory/shadow/composer.py`: agrupación documento × regulación (66 secciones), cobertura exacta 457/457, cada finding trazable (cita + rationale L2 verbatim), narrativa LLM y opinión de experto = PENDIENTE, `no_rejudge_l2 = true`. Verificación de `report_v2` frente a la baseline: `same_finding_record_id_set = true`, `l2_fact_mismatches = 0`, `report_v2.py` intacto. 60/60 tests. CRIT-0/H/L2/E ✅. |
| **Estado** | **`shadow-G3.1` es la revisión correctiva ACEPTADA de G3.** La nomenclatura (G3 vs G3.1) no bloquea nada: el estado vigente de la fase 3 del arco es `shadow-G3.1`. `shadow-G3` permanece como el punto exacto auditado. |

---

## Cadena de tags del arco

```
0e1e88a  reconc-acceptance-v1   (baseline)
3bacfd0  shadow-G0
3ccc485  shadow-G1
e5458d3  shadow-G2
bd79541  shadow-G3              (estado auditado — no se mueve)
9e819bf  shadow-G3.1            (revisión correctiva ACEPTADA de G3 — CF-2)
<r1>     shadow-G2-r1           (corrección puntual del contrato de G2 — CF-1)
```

`shadow-G2-r1` se ancla en la punta de la rama (después de `shadow-G3.1`) por historia lineal;
el nombre indica que corrige el **contrato de G2**, no que reabra la fase.

---

*Registro de gobernanza del arco shadow. Cada corrección es puntual, independiente y trazable.
Ningún tag previo se mueve.*
