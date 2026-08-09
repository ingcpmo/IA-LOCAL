# R1.5 — Reporte final (Parte 7 del ARQ, `docs_plan/R1_5_PRODUCTIZACION_H2H4.md`)

**Fecha:** 2026-08-09. **Estado:** DEMO/validación, sin commit, sin aprobar.

```
PROBLEMA CONFIRMADO:
  El smoke de R1 usó config baseline; H2+H4 nunca se llevó a
  run_pilot_sample_batch/chunked_engine — vivía solo en scripts de
  diagnóstico (h2_experiment.py/h4_experiment.py, scratchpad, nunca
  versionados).

CAUSA RAÍZ:
  H2+H4 solo en scripts ad hoc; producción en baseline (confirmado en
  código antes de tocar nada).

DISEÑO DE CORRECCIÓN:
  evaluation_profile configurable en evaluate_chunked() (default
  "BASELINE", cero cambio de comportamiento para llamadores existentes).
  "H2H4" filtra meta["checkpoints"] a target_requirement_ids ANTES de
  evidence_pack_gate/build_prompt/output_token_budget/build_run_fingerprint
  — reutiliza el prompt/schema GOBERNADO real sin editarlo (reproduce H2
  fielmente). run_pilot_sample_batch gana kwarg evaluation_profile, usa
  unit.requirement_id (ya existía, antes solo documental) cuando se pide
  H2H4.

QUÉ CAMBIA:
  Motor: nuevo modo H2H4 (filtrado de checkpoints por requirement_id,
  antes de todo lo demás). run_fingerprint/preflight_metadata registran
  el perfil — cambiar de perfil invalida cache de checkpoint (test
  dedicado que lo confirma). corpus_runner: nuevo kwarg
  evaluation_profile, threading de unit.requirement_id.

QUÉ NO CAMBIA:
  Validadores A/C/D (evidence_verifier, semantic_evidence_verification)
  intactos. Umbral fuzzy sin tocar. Contrato BASELINE byte-a-byte
  idéntico (test dedicado). Fix de viñetas (_strip_bullet_markers) sin
  tocar. NO se reprodujo el schema mínimo de H4 al pie de la letra —
  vive en contenido gobernado (prompts YAML); documentado como nota
  honesta de alcance en el docstring y en el skill nuevo. La ganancia de
  recall medida es 100% atribuible a H2, no al schema (confirmado en
  W5V2_RECALL_EXPERIMENTS_RESULTADOS.md: H4 sobre H2 dio el mismo 2/7).

VALIDACIÓN EJECUTADA:
  Checkpoint 1: 10 tests nuevos (factory/tests/test_evaluation_profile_h2h4.py)
  + 104 de regresión (chunked_engine/corpus_runner/pilot/qualification),
  todos verdes. Gate 0 completo (venv del host): 2257 passed, 10 failed
  — los 10 investigados uno por uno: 4 conocidos (decisions_v2.jsonl sin
  commit) + 3 Playwright (timeout de browser, ambiental, ya excluido en
  sesiones previas) + 2 test_runtime_identity.py (esperado:
  chunked_engine.py sin commit, mismo patrón que los 4 conocidos) + 1
  test_w5_human_decisions.py (esperado: la cola de revisión real ya no
  está vacía por el encolado del smoke de R1). Ningún fallo real
  atribuible al código nuevo.

  Bloque 3: 1 llamada real, run_id chunked-596f70cc4520, 387.4s (vs
  1660.8s del baseline — 4.3x más rápido, consistente con lo medido en
  H2). Instancia usada: PILOT_EXECUTION-2026-006 (seleccionada
  automáticamente, co-cubridora -004) — NO se propuso ninguna nueva.

RESULTADO COMPARADO CON H2+H4:
  El modelo SÍ ancló: estado="cumple_parcialmente", evidencia_exacta =
  cita real y literal sobre la función de firma electrónica de
  FactoryTalk View SE (página 45) — verificada independientemente con
  evidence_verifier.match_citation() real: ("normalized", 1.0), score
  perfecto. chunked_engine._is_anchored() sobre el chunk real también da
  True. La cita ES genuina y SÍ ancla.

  Pero el checkpoint final (verified_records_by_req) igual reporta
  "not_observed_in_chunk" / evidence_quote vacía. CAUSA RESIDUAL
  ENCONTRADA (no maquillada, detalle completo en CAUSA_RESIDUAL.md):
  chunked_engine._is_topically_relevant() rechaza la cita por mismatch de
  IDIOMA — el label del checkpoint está en español
  ("Contemporaneous — registrado en el momento") y el documento/cita
  reales están en inglés, así que la heurística de palabras significativas
  del label nunca puede encontrar coincidencia. Los scripts h2_experiment.py
  /h4_experiment.py nunca ejercieron este gate (llaman a _is_anchored o
  match_citation directo) — por eso "ancló limpio" en el experimento pero
  no en producción. Incluso una productización perfecta de H2+H4 iba a
  chocar con este mismo rechazo.

RIESGOS:
  El hallazgo de _is_topically_relevant() es potencialmente sistémico
  (todos los labels de los prompts YAML están en español; cualquier
  documento fuente en inglés puede sufrir el mismo rechazo falso, no
  verificado sistemáticamente). NO se tocó — cambiar un validador
  existente está fuera del alcance autorizado de esta corrida ("no R2";
  la prohibición central de no aflojar validadores aplica aunque esto
  parezca un bug genuino, no una relajación deliberada — necesita
  decisión explícita de Cesar y, probablemente, revalidación contra el
  fixture set completo incluyendo ANNEX11_4 antes de tocarlo).

GIT STATUS (relevante a esta corrida):
   M factory/engines/gmpai_integrity/chunked_engine.py
   M factory/regulatory/corpus_runner.py
   M docs_plan/ROADMAP_ANALIZADOR_GMP.md (nota D4-A agregada)
   M factory/layer9/decisions/decisions_v2.jsonl (ya modificado antes)
   M factory/layer9/review_queue.jsonl (ya modificado antes, R1)
  ?? factory/tests/test_evaluation_profile_h2h4.py
  ?? .claude/skills/gmp-recall-pipeline/
  ?? docs_plan/R1_5_PRODUCTIZACION_H2H4.md
  ?? docs_plan/R1_SPEC_CONTRATO_ANALIZADOR.md (de corrida anterior, R1)
  ?? factory/tests/test_pilot_execution_selection.py (de corrida anterior, R1)
  ?? factory/regulatory/pilot_run/r1_5_h2h4_chunked-596f70cc4520/ (esta carpeta)

DIFF_RESUMEN: chunked_engine.py +89/-0 líneas netas; corpus_runner.py
  +149/-25. Sin tocar prompts YAML, evidence_verifier.py, ni ningún
  validador.

MEMORY_UPDATED: project_w5_v2_regulatory_redesign.md (sección nueva
  "Reenfoque a Analizador Documental GMP + Piloto de recall + R1/R1.5",
  frontmatter description actualizado) + MEMORY.md (índice actualizado).

SKILL_CREATED: .claude/skills/gmp-recall-pipeline/SKILL.md — sí, con
  todo el contenido pedido (arquitectura, evaluation_profile, fixture
  set, prohibición central, gobernanza PILOT_EXECUTION, estado del
  roadmap, diferidos).

D4A_RECALC_NOTED: sí, en ROADMAP_ANALIZADOR_GMP.md sección R1.5 ("Impacto
  en D4-A") — ritmo real ahora medido (387.4s/llamada H2H4 vs 1660.8s
  baseline), no recalculado ni propuesto, solo anotado.

PENDIENTE DE APROBACIÓN:
  1. Diff completo para commit (chunked_engine.py, corpus_runner.py,
     tests, roadmap, memoria, skill, R1_5_PRODUCTIZACION_H2H4.md, esta
     carpeta de artefactos).
  2. Cierre de R1.5: la productización FUNCIONA (probado: 10/10 tests,
     Gate 0 limpio, plumbing correcto por flujo real) pero el caso P5
     SIGUE sin llegar a "observed" en el pipeline verificado — no por
     falta de anclaje real, sino por el defecto de _is_topically_relevant
     recién descubierto. ¿Se considera R1.5 cerrado (la productización de
     H2+H4 en sí está completa y correcta) con este hallazgo nuevo como
     un R1.6/hallazgo separado? ¿O R1.5 sigue abierto hasta que P5
     efectivamente llegue a "observed"?
  3. Habilitación de R2: NO recomendable todavía — P5 no llegó a
     "observed" en el pipeline real, aunque ahora se sabe exactamente
     por qué (no es un problema de recall del modelo, es un defecto de
     un gate posterior).
  4. Decisión nueva, no anticipada por el ARQ original: ¿autorizar
     investigar/corregir _is_topically_relevant() (mismatch de idioma
     label-español vs documento-inglés) como su propia corrida acotada,
     con el fixture set completo (incluido ANNEX11_4) como criterio de
     no-regresión?
```

## Contenido de esta carpeta

| Archivo | Contenido |
|---|---|
| `checkpoint.json` | Checkpoint real completo del Bloque 3 (`run_id=chunked-596f70cc4520`), incluye `fingerprint` con `evaluation_profile="H2H4"` |
| `manifest.json` | Manifest del batch |
| `raw_response/` | Respuesta cruda completa del modelo, sin truncar |
| `CAUSA_RESIDUAL.md` | Análisis completo del hallazgo de `_is_topically_relevant()`, con evidencia paso a paso |
| `REPORTE_FINAL.md` | Este archivo |
