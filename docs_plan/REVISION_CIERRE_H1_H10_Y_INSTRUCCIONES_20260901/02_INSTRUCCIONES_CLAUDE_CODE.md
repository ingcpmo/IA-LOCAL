# 02 — INSTRUCCIONES PARA CLAUDE CODE (próxima sesión)

Leer antes de tocar nada:
- `.claude/skills/gmp-recall-pipeline/SKILL.md` (regla dura: nunca invocar la config
  ganadora por script ad hoc; nunca aflojar validadores).
- `docs_plan/REPORTE_B4B_MEDICION_RECALL_V2.md` (estado vigente de R2; el roadmap está stale).
- `00_REVISION_DE_CIERRE.md` y `01_EVIDENCIAS.md` de este directorio.
- `CLAUDE.md` (LOCAL-ONLY; no commit sin diff + aprobación en corridas de documentación/diseño).

## Reglas de esta ventana

1. **NO consumir llamadas LLM** hasta que Capa 9 apruebe `PILOT_EXECUTION-2026-035`
   (`03_PROPUESTA_PILOT_EXECUTION_035.md`). Presupuesto total autorizado: **20**.
2. **NO editar a mano** `factory/layer9/decisions/decisions_v2.jsonl`. Toda decisión de
   gobernanza se registra por Mission Control / governance service. Si el árbol de trabajo
   trae líneas con `recorded_by: null` y `proposed_by_id` distinto de `mission_control_ui`,
   son hand-edits no gobernados → revertir solo ese archivo a HEAD y avisar.
3. **NO tocar** ningún artefacto `ARTIFACT_VERSION` ni ningún prompt gobernado
   (`prompts/**/*.yaml`) sin proposal + firma de Cesar por el canal correcto.
4. **NO reabrir** FASE 3 ni la integración del modelo híbrido (PARKED por Capa 9). El
   prototipo en `factory/prototypes/semantic_hybrid_poc/` no se modifica sin nueva decisión.
5. **NO cerrar** E1-3/E1-ACC/E2/E3-A por código. Ya se firman por Mission Control.

## Orden de trabajo

### T1 — Higiene de trazabilidad (sin LLM, sin gobernanza nueva)
- **P3:** actualizar `docs_plan/E1_SIGNATURE_HISTORY.md` (append-only) con:
  - E1-3 · `sample_sha256 77e8324f…` · `verdict_set_sha256 4e23a146…` · 66/67 CORRECT ·
    ledger `ARTIFACT_VERSION-2026-022` (propose) + `-023` (confirm, Cesar) · 2026-09-01.
  - E1_ACCEPTANCE = PASS · ledger `-024` (propose) + `-025` (confirm, Cesar) · 2026-09-01 ·
    basis "66/67 CORRECT, 0 WRONG_NODE, 0 SPURIOUS, 1 AMBIGUOUS por truncación OCR no
    atribuible a H-10" · RC-2 RESOLVED · RC-3 RESOLVED.
  - No borrar E1-1/E1-2. No reescribir.
- **P4:** con OK explícito de Capa 9, `git add factory/layer9/decisions/decisions_v2.jsonl`
  y commit (mensaje: "chore(gov): persistir en git firmas E1-3 + E1_ACCEPTANCE de Mission
  Control (ARTIFACT_VERSION-2026-022..025)"). Verificar antes: las 4 líneas nuevas son las
  del servicio y nada más difiere.
- Commit T1 (docs + ledger) y push.

### T2 — E2 / E3-A (bloquea a Capa 9, no a Claude)
- Recordar a Capa 9: firmar **E2** (`gate-e2`, ref `E2-RPAR-20260831`) y **E3-A**
  (`gate-e3a`, ref `E3A-CLEANBASE-20260831`) en
  `http://localhost:9000/ui/mission_control.html` → Gobernanza.
- Cuando estén firmadas: aplicar el mismo T1 (append a un historial si existe, persistir el
  ledger). No hacer nada más con ellas.

### T3 — R2 medición diagnóstica (SOLO tras aprobación de `PILOT_EXECUTION-2026-035`)
- Ver `03_PROPUESTA_PILOT_EXECUTION_035.md` para baseline, fixture, `evaluation_profile`,
  retrieval activo, métrica PRE y criterio PASS/FAIL.
- Proponer `PILOT_EXECUTION-2026-035` (`agent_proposed`) con `hard_call_cap = 20`.
  Capa 9 confirma por Mission Control.
- Ejecutar SOLO por el flujo real (no script ad hoc). Registrar `run_id`, llamadas
  consumidas, `stop_reason`, `DOCUMENT_EGRESS`, latencias.
- Reportar: recall PRE/POST por sub-criterio (`SATISFIES|PARTIAL` rate), regresiones,
  llamadas consumidas, y la decisión que habilita (Palanca C permanente vs avenida en paso A).
- **Detente** al completar T3 o al consumir 20 llamadas, lo que ocurra primero. No avanzar a
  ninguna fase posterior sin aprobación de Capa 9.

### Fuera de alcance de esta ventana (requieren decisión nueva de Capa 9)
- Probar un modelo local mayor (32B/72B quant) en el paso B → qualification de modelo.
- Few-shot en `step_b_criterion_mapping` → nuevo `prompt_version` + firma.
- D5-D2 → requiere autora independiente real (Maria Torres).
- Cualquier cosa que dependa de `PRODUCTION_ENABLEMENT` (sigue `BLOCKED` /
  `NOT_ENABLED`) o de `REGULATORY_COMPLIANCE` (`NOT_DETERMINED_BY_SYSTEM`).

## Estado de gates (referencia rápida)

| Gate | Estado | Nota |
|---|---|---|
| H1 = APPROVE_REMEDIATION_V1_2 | ✅ REGISTRADA (2026-09-01) | metadata + commit `24549a3`; downstream: D5-D2 |
| D5-D2 | ⏸ DEFERRED / NON_BLOCKING_FOR_DEVELOPMENT | sigue requerido para cualificación final |
| E1-3 | ✅ FIRMADA (Mission Control, 2026-09-01) | 66/67 CORRECT |
| E1_ACCEPTANCE | ✅ PASS (Mission Control, 2026-09-01) | RC-2 / RC-3 RESOLVED |
| E2 | ⛔ PENDIENTE | `gate-e2` |
| E3-A | ⛔ PENDIENTE | `gate-e3a` |
| FASE 2 híbrido | ✅ CERRADA = PASS / PARKED | no FASE 3, no integración |
| R2 recall juicio | 🔴 TECHO (0–2/7, 6 vías) | decisión enmarcada: Palanca C permanente |
| FUNCTIONAL (B8b) | ✅ 16/16 · FP 0/16 | determinista, independiente del techo |
| PRODUCTION_ENABLEMENT | 🔒 BLOCKED / NOT_ENABLED | — |
| REGULATORY_COMPLIANCE | ❔ NOT_DETERMINED_BY_SYSTEM | — |
