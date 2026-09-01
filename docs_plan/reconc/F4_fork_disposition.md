# F4 — D7: disposición del fork histórico `FORK-2026-06-15-001`

**Plan de reconciliación v1.1 · FASE 4 · acción 4 · READ-ONLY. La cadena de auditoría NO se reescribe.**

## Estado real (leído de `factory/audit/fork_baseline.json`)

```json
"known_forks": [{
  "fork_id": "FORK-2026-06-15-001",
  "entry_id": "ab689c7c-3e0a-4c77-936b-152851f51a30",
  "timestamp": "2026-06-15T13:54:43...",
  "event_type": "gates_executed",  "project_id": "lab_qc_project",
  "root_cause": "stale_in_process_head_cache",
  "root_cause_detail": "Dos procesos (factory_cleanup y lab_qc_project) con _last_entry_hash
                        cacheado; factory_cleanup avanzó la cabeza real, lab_qc_project escribió
                        sin releerla. 3 min 10 s entre escrituras -> era la cache, no la simultaneidad.",
  "fixed_by_commit": "8c033fa",  "fixed_at": "2026-06-15T14:21:43...",
  "accepted_by_decision": "AUDIT_EXCEPTION-2026-002",
  "accepted_by_id": "cesar",
  "accepted_at": "2026-07-30T14:21:22...",
  "acceptance_note": "ACEPTADO por decision humana AUDIT_EXCEPTION-2026-002 (Capa 9).
                      CHAIN_CONTINUITY pasa a ACCEPTED_WITH_DOCUMENTED_EXCEPTION y NUNCA a
                      VERIFIED: la ruptura sigue ahi, documentada y aceptada, no corregida."
}]
```

`AUDIT_EXCEPTION-2026-002` en el ledger: `decision=APPROVE`, `status=ACTIVE`, `approved_by_id=cesar`,
`2026-07-30T14:21:22`.

## Determinación D7

**El fork YA está gobernado.** Tiene:
- **causa raíz establecida** (`stale_in_process_head_cache`) y **fix commiteado** (`8c033fa`, 27 min después);
- **aceptación humana registrada**: `AUDIT_EXCEPTION-2026-002` (Capa 9 / Cesar, `ACTIVE`), que
  cubre **ese `entry_id` y sólo ese** (`AUDIT_FORK_REMEDIATION_SPEC.md` F-03);
- `CHAIN_CONTINUITY = ACCEPTED_WITH_DOCUMENTED_EXCEPTION` (nunca `VERIFIED`) — la cadena
  **no se reescribió**, la ruptura sigue ahí, documentada.

### Sobre `frozen_by_is_human_acceptance: false` (nivel raíz)

Ese flag es del **freeze del baseline** (`frozen_by: "Capa 8 (W5 V2 G1.14)"`,
`frozen_at: 2026-07-29`), NO de la aceptación del fork. Significa "la congelación del baseline
la hizo Capa 8 midiendo la cadena, no fue un acto de aceptación humana". Es **correcto que
siga `false`** — el spec (`AUDIT_FORK_REMEDIATION_SPEC.md:442`) lo dice explícitamente:
*"`frozen_by` NO cambia y `frozen_by_is_human_acceptance` sigue [false]"*. La aceptación
humana del fork vive en el campo **por-fork** `accepted_by_decision`, que **sí** está poblado
(`AUDIT_EXCEPTION-2026-002`).

## VEREDICTO D7

**D7 = NO REQUIERE ACCIÓN.** El fork `FORK-2026-06-15-001` está formalmente aceptado por
`AUDIT_EXCEPTION-2026-002` (Capa 9, ACTIVE). La cadena no se reescribe. El flag de nivel raíz
`frozen_by_is_human_acceptance: false` es semánticamente correcto (concierne al freeze del
baseline, no a la aceptación del fork) y **no debe tocarse**.

D7 en la lista de discrepancias del plan ("fork histórico sin aceptación humana registrada")
**se cierra por evidencia**: la aceptación humana SÍ está registrada.
