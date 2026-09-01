# F4 — RECONCILIACIÓN DEL LEDGER (D5) — clasificación de `ARTIFACT_VERSION-2026-022..032`

**Plan de reconciliación v1.1 · FASE 4 · acción 2 · READ-ONLY. CERO hand-edits a `decisions_v2.jsonl`.**
`sha256(decisions_v2.jsonl)` al inicio y al final de F4 = `1b0c7cf82ed7b2b056aade48c7e7dfa41142b108f94dfda0d0dc9836206a4af4` (sin cambio).

---

## Clasificación

| id(s) | fecha evento | `tsh` / artefacto | clase D5 | disposición |
|---|---|---|---|---|
| **`-022` / `-023`** | **2026-09-01** 15:57 | `84c54618` = `H10_NEW_RELATIONS_SAMPLE_FOR_HUMAN.json` · **E1-3** (`vss 4e23a146`, counts `{CORRECT:66,WRONG_NODE:1,SPURIOUS:0,AMBIGUOUS:0}`) | **GOBERNADA_Y_RECUPERABLE** | **Ya en el ledger.** Estado autoritativo actual. Mission Control `agent_proposed` (`mission_control_ui`) → `human_confirmed` (Cesar). **No requiere re-emisión.** Su `instance_id` colisiona con el evento 2026-08-31 (E1-2) → flag, no reescritura. |
| **`-024` / `-025`** | **2026-09-01** 16:00 | `84c54618` · **E1_ACCEPTANCE = PASS** (RC-2/RC-3 RESUELTOS) | **GOBERNADA_Y_RECUPERABLE** | **Ya en el ledger.** Autoritativo. No re-emisión. |
| `-022` / `-023` | 2026-08-31 15:10 | `84c54618` · **E1-2** (documentado en `E1_SIGNATURE_HISTORY.md`) | **HISTÓRICA_SIN_PERSISTENCIA** + **SUPERSEDIDA** | Firma E1-2 real, revertida del ledger, **preservada en el audit trail**. Supersedida por E1-3 (2026-09-01). El acto humano (Cesar firmó E1-2) queda en el audit trail; el resultado de fondo (aceptación de la muestra H-10) lo re-expresa E1-3. **No se re-emite** (E1-3 la reemplaza). |
| `-024` / `-025` | 2026-08-31 16:36 | **`e10fc3a969e2`** (artefacto distinto, no resoluble desde el audit trail: `data` mínimo, sin `resolved_target_ids`) | **NO_RECONCILIABLE** (justificada) | Evento de firma ARTIFACT_VERSION sobre un artefacto que el audit trail no identifica y que no está en el ledger. Sin `decision_ref` ni `resolved_target_ids` en el evento. **Se documenta como NO_RECONCILIABLE**: no hay base para re-emitir sin saber el target; el audit trail lo preserva. |
| `-026` / `-027` / `-028` | 2026-08-31 16:36–17:03 | **`46758dfa79fa`** (otro artefacto, idem: no resoluble) | **NO_RECONCILIABLE** (justificada) | Idem. Tres eventos (propose + confirm + ¿re-propose?) sobre `46758dfa79fa`. No en el ledger, no identificable. Preservados en el audit trail. |
| `-029` / `-030` | 2026-08-31 19:20 | `84c54618` (muestra H-10) | **HISTÓRICA_SIN_PERSISTENCIA** + **DUPLICADA** | Otra firma E1 sobre la misma muestra H-10 (el hand-edit revertido llevaba E1-3 con `verdict_set_sha256 7c905e2…`, hash antiguo). Supersedida por `-022/-023` (2026-09-01, `vss 4e23a146…`). No se re-emite. |
| `-031` / `-032` | 2026-08-31 19:41 | `84c54618` (muestra H-10) | **HISTÓRICA_SIN_PERSISTENCIA** + **DUPLICADA** | Firma E1_ACCEPTANCE previa sobre la misma muestra. Supersedida por `-024/-025` (2026-09-01). No se re-emite. |

---

## Resumen

- **En el ledger y correcto (GOBERNADA_Y_RECUPERABLE):** `-022`..`-025` del **2026-09-01**
  (E1-3 + E1_ACCEPTANCE). **Nada que re-emitir** — es el estado autoritativo.
- **HISTÓRICA_SIN_PERSISTENCIA (audit trail only, revertidas):** los `022..023`, `029..032`
  del 2026-08-31 (firmas E1 previas sobre la misma muestra H-10, supersedidas por E1-3).
- **NO_RECONCILIABLE (justificada):** `024..028` del 2026-08-31 (`tsh e10fc3a969e2` y
  `46758dfa79fa`) — artefactos no identificables desde el audit trail (`data` mínimo).
  Preservados en el audit trail; sin base para re-emisión.
- **DUPLICADA:** los pares 2026-08-31 sobre `84c54618` que E1-3/E1_ACCEPTANCE del 2026-09-01
  ya cubren.

## Re-emisión por Mission Control

**Ninguna necesaria.** El estado gobernado vigente (`-022`..`-025` de 2026-09-01) es correcto
y completo para E1-3 + E1_ACCEPTANCE. Las entradas históricas del audit trail son evidencia
append-only, no se re-escriben. La **única** anomalía es la **colisión de `instance_id`**
(`F4_id_collision_analysis.md`), que se corrige a nivel del **generador** (`decision_store_v2.
next_instance_id`), no reescribiendo el ledger.

## Pendiente para F5 / Capa 9

- Aplicar la corrección gobernada del generador de IDs (`F4_id_collision_analysis.md` §3).
- Confirmar (Capa 9) que E1-2, E1_ACCEPTANCE(08-31), y los artefactos `e10fc3a969e2` /
  `46758dfa79fa` **NO** requieren re-firma en el ledger nuevo (el estado 2026-09-01 los
  supersede / no eran parte del alcance E1 vigente).
