# E1 — HISTORIAL DE FIRMAS (append-only)

Registro de las revisiones humanas del gate E1 (verificación de la muestra de relaciones
nuevas H-10). El almacén de gobernanza es append-only: **cada revisión se conserva**; una
revisión posterior no borra ni invalida la anterior — la contextualiza.

---

## E1-1 · 2026-08-31 · pre FIX-A · **FAIL**

```
sample_sha256       = f56d4babe7e8466368c9a6dbefe26e3716186f96e2658c68cf2f0469f5244f20
verdict_set_sha256  = a533bf4aa11d58acf2dd881cd5abaf52f85175c90db3c50d0bb1a79b352de085
TOTAL=77   CORRECT=26   WRONG_NODE=30   SPURIOUS=11   AMBIGUOUS=10
E1_ACCEPTANCE       = FAIL / REMEDIATION_REQUIRED
```

- Muestra: `refers_to=350` / `tested_by=17` en el grafo; 60 primeras `refers_to` por `edge_id` + 17 `tested_by`.
- Causa dominante identificada: `_link_refers_to` sin resolución de especificidad → genérico
  (subcadena de un término específico) = nodo equivocado.
- Evidencia: `docs_plan/E1_REVIEW_Y_FIX_H10_REFERS_TO_20260831.md`.
- Los veredictos por fila **no** se registraron individualmente (sólo el agregado y el
  `verdict_set_sha256`). `PREVIOUS_VERDICT` por fila = NOT_AVAILABLE.
- Registro gobernado: **pendiente** (el humano reportó el resultado; la firma
  `ARTIFACT_VERSION` de E1-1 se registra junto con E1-2 o por separado, ambas se conservan).

## E1-2 · post FIX-A · **PENDING**

```
sample_sha256       = c2ca5aaa36e9904b77cecf266cfa6645ab76949828074c857a360a5bf75ad3fd
verdict_set_sha256  = (pendiente — se calcula al completar 77/77)
E1_POST_FIX_ACCEPTANCE = PENDING
```

- Muestra regenerada tras FIX-A (`refers_to=202` / `tested_by=17`); misma política de muestreo.
- Revisión **independiente**: no se reutiliza ningún veredicto de E1-1 aunque la arista sea idéntica.
- Paquete de revisión: `docs_plan/E1_REVIEW_PACKET_POST_FIXA_20260831.md` (77 filas, cada una con
  `SAME_RELATION_AS_PREVIOUS` y `PREVIOUS_VERDICT=NOT_AVAILABLE_PER_ROW`).
- Esqueleto de veredictos: `docs_plan/E_GATES_GOVERNED_PAYLOADS_20260831/E1_2_verdicts_skeleton.json`.
- UI: panel `gate-e1` (Mission Control › Gobernanza), `sample_sha256` = `c2ca5aaa…`,
  `decision_ref = E1-2-H10-RELATIONS-20260831`, payload lleva `previous_e1` con los hashes de E1-1.
- Registro: `propose → confirm` de `ARTIFACT_VERSION` con la Identity Key del humano.
