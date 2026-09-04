# CF6_2_5_v3_run1 — EXECUTION_STATUS: INVALID

Primera corrida de CF6-2.5 v3 (2026-09-03/04). **No es un piloto válido para adjudicar
el HUMAN_QUALITY_GATE** por dos defectos de EJECUCIÓN del runner (no de seguridad):

- **A** — 10 llamadas LLM para 7 secciones: el runner tenía un bucle de reintento
  (`for attempt in (1,2)`) que contradice CF-6 v1.2 §3.1 ("el Composer interviene una
  sola vez por sección").
- **B** — orden de ejecución de la deduplicación: `validate_structure_contract` rechazaba
  las citas duplicadas ANTES de que `normalize_evidence_observed` pudiera corregirlas
  (sec-0016 cayó a SAFE_MODE sin que la dedup actuara).

Corregido en `cf6_pilot_runner_v3.py` (Fix A + Fix B). La corrida válida ocupa los
artefactos `CF6_2_5_v3_*` (sin sufijo). Estos `_run1_` se conservan sólo para auditoría.
Resultado run1: 4 RENDERED / 3 SAFE_MODE, 10 llamadas.
