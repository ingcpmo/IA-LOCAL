# CUTOVER CONTROLADO — Analizador V2 (FASE 11 / B9b)

**Fecha:** 2026-08-28. **Autoridad:** Capa 9 = Cesar. **Estado:** EJECUTADO (reversible).

## Decisiones de Capa 9 (2026-08-28)

| | Decisión | Efecto |
|---|---|---|
| **A** | Adoptar **Regulatory Tier-1 / Palanca C** como modalidad regulatoria de V2 | En `routing=v2`, la clase Regulatory opera determinista (eco léxico anclado + revisión humana con cobertura declarada). NUNCA aprobación automática. Sustituye el criterio `REGULATORY_POSITIVE ≥ 6/7` de un LLM (medido 0/7 → ADR §10). |
| **B** | Aceptar **EXC-1..EXC-5** como excepciones documentadas | `docs_plan/DEUDA_REGRESION_EXCEPCION_CAPA9.md`. Deuda de clon `/home/ing_cpmo` + servicios en vivo; 0 impacto V2. Re-verificar en el entorno de origen. |
| **C** | Autorizar el **controlled cutover** | Flag `cutover.routing_mode()` = `v2`. |

## Ejecución

```
cutover.set_routing_mode("v2", actor="Capa 9 (Cesar)", reason="Controlled cutover 2026-08-28 ...")
  from=current  to=v2  at=2026-08-28T04:06:41Z  current_retained_as_rollback=true
```

- Flag: `factory/regulatory/validation_v2/routing.txt` = `v2` (operativo, gitignored).
- Historial append-only: `factory/regulatory/validation_v2/routing_history.jsonl` (gitignored).
- Dispatcher cableado: `factory/regulatory/validation_v2/analyzer_router.py::analyze()`
  enruta según `routing_mode()`:
  - `v2`      → `v2_runtime.run_v2_pipeline` (determinista, 0 LLM, persiste bajo
                `GMPAI/reports/gmpai_document_validation/<run_id>/`).
  - `current` → `CurrentEngineHandoff` (el motor CURRENT se invoca por su camino
                existente; el dispatcher NO lo duplica).
  - `shadow`  → V2 sin efectos + comparación.

## Verificación post-cutover

```
routing_mode = v2 ; active_engine = V2 ; regulatory_modality = REGULATORY_TIER1_PALANCA_C
analyze(RW-0005/0006/0011/0012/0014) -> V2 pipeline:
  reg=285  func=90  tech=24 ; llm_calls=0 ; document_egress_bytes=0 ; human_gate_intact=True
Artefactos MACHINE GENERATED / NOT_QA_APPROVED ; human_state=UNREVIEWED en todos.
```

## Rollback (probado)

```
cutover.set_routing_mode("current", actor=..., reason="rollback")
  -> active_engine=CURRENT ; analyze() -> CurrentEngineHandoff (CURRENT intacto, no duplicado)
cutover.set_routing_mode("v2", ...)   -> restaurado
```
CURRENT permanece **intacto y seleccionable**. El env `V2_ANALYZER_ROUTING` gana sobre
el archivo si está definido (rollback de emergencia sin tocar el archivo).

## Estado GMP tras el cutover (sin cambios respecto a las reglas permanentes)

- Ninguna aprobación automática. `human_state` nace `UNREVIEWED`, inmutable desde código IA.
- Sin declaración de cumplimiento final. Sin cierre de CAPA. Sin liberación de lote.
- Estados prohibidos (`QA_APPROVED/RELEASED/CAPA_CLOSED/FINAL_GMP_APPROVAL`) bloqueados.
- `DOCUMENT_EGRESS = 0`. Sin LLM. Sin API externa.
