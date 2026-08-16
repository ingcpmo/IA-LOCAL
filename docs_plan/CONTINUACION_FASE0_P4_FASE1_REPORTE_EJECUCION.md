# REPORTE DE EJECUCIÓN — CONTINUACIÓN POST-AUDITORÍA
# FASE 0 + CIERRE DE P4 + FASE 1 MECÁNICA (+ EXPERIMENTO C REAL)

**Instrucciones origen**: `docs_plan/CONTINUACION_FASE0_P4_FASE1.md`
**Fuente**: `docs_plan/AUDITORIA_ARQUITECTONICA_2026-08/` (12 documentos)
**Ejecutado**: 2026-08-14/15. Cada bloque con aprobación explícita
separada de Cesar (diff mostrado antes de tocar `DO_NOT_TOUCH.md`,
confirmación explícita antes de cada llamada LLM real).

Este documento consolida en un solo lugar lo que en los entregables de
la auditoría quedó repartido por tema (`BOTTLENECK_DIAGNOSIS.md`,
`RISK_REGISTER.md`, `EXPERIMENT_PLAN.md`, `CONTEXT_ENGINEERING_
ARCHITECTURE.md`). Esos documentos siguen siendo la fuente detallada;
este es el resumen de ejecución.

──────────────────────────────────────────────────────────────────────
BLOQUE 0 — CIERRE GRATIS DE P4 (cero LLM)
──────────────────────────────────────────────────────────────────────

**Resultado**: P4 (ALCOA_ATTRIBUTABLE) y P6 (21_CFR_211.68(b)) comparten
literalmente el mismo chunk fuente (RW-0011, página 12/13) — confirmado
por re-extracción real vía `pdfplumber` dentro de `factory-api`. Mismo
texto de 2427 caracteres, misma tabla "Table 4-8: Vaporized Hydrogen
Peroxide Signals", misma oración de prosa relevante (110 caracteres,
4.53% de la página).

**R8 (RISK_REGISTER.md) → CERRADO.** P4 queda en el mismo bucket de
hipótesis que P6 (dilución tabular), sin costo experimental adicional.

──────────────────────────────────────────────────────────────────────
BLOQUE 1 — FIX DE FURNITURE SIMÉTRICO
──────────────────────────────────────────────────────────────────────

**Hallazgo**: `evidence_verifier.py` limpiaba el membrete de página
(furniture) de la plantilla Rockwell solo en la ruta de VERIFICACIÓN,
nunca en el texto que efectivamente veía el LLM — asimetría real,
diagnosticada en `INFORMATION_LOSS_ANALYSIS.md`.

**Diseño de reuso** (superficie única): `chunked_engine.build_page_
chunks()` reutiliza `evidence_verifier.strip_page_furniture` (alias
público nuevo de la función privada `_strip_page_furniture` ya
existente) — precedente ya presente en el archivo (`chunked_engine.py`
ya importaba `load_requirement_terms` del mismo módulo).

**Diff aprobado y aplicado**: 2 líneas en `chunked_engine.py` + alias de
1 línea en `evidence_verifier.py`.

**Efecto colateral real medido, no buscado a propósito**: el furniture
diluía las frecuencias de término de BM25 — al quitarlo, P2
(`21_CFR_11.10(g)`) entra al top-5 de retrieval (rank 4, antes fuera del
top-5). `retrieval_recall_at_5` sube de 4/7 a 5/7.

**Regresión encontrada y corregida**: el re-chunking global (menos
furniture ⇒ más texto cabe por chunk) renumeró TODO `chunk_index` de
RW-0005 (29 → 25 chunks), rompiendo el replay hardcodeado de
`PILOT_EXECUTION-2026-010/012` en `test_r2_3_p2_p5_judgment_replay.py`.
Remapeado por página (no por número), metodología documentada en el
propio test.

**Tests**: 4 nuevos + 2 asserts de retrieval actualizados (con
justificación documentada) + regresión completa (119/119 determinista +
2/2 replay) + golden dataset de 8 negativos sin regresión (N1/N2 siguen
rechazados).

**Commit**: `e271488`.

──────────────────────────────────────────────────────────────────────
BLOQUE 2 — VERIFICACIÓN MECÁNICA (Fase 1 del experimento, cero LLM)
──────────────────────────────────────────────────────────────────────

`pdfplumber.extract_tables()` sobre las páginas reales de P4/P6/P7:

- **P4/P6** (RW-0011 p.12): la tabla de señales I/O se separa
  LIMPIAMENTE de la prosa relevante — confirmado mecánicamente.
- **P7** (RW-0012 p.13, documento real distinto): **hallazgo nuevo no
  buscado** — su página NO tiene ninguna tabla de contenido real (solo
  el bloque de cabecera). La agrupación previa "P6/P7 = misma
  hipótesis" de la auditoría original era incorrecta — P7 se recalifica
  al mismo bucket que P2/P5 (límite de modelo, no representación).

**Costo real de Bloques 0+2: 0 llamadas LLM.**

──────────────────────────────────────────────────────────────────────
BLOQUE 3 — CONTRATO FORMAL CHECKPOINT→FINDING (cero LLM)
──────────────────────────────────────────────────────────────────────

**Corrección al diagnóstico original de la auditoría**: el contrato
formal (JSON Schema) YA EXISTÍA (`checkpoint_llm_response_v1.json`,
`finding_llm_v1.json`, versionados, validados vía `schema_loader`) — no
había que construirlo.

**El gap real**: `verified_pipeline_adapter.candidate_to_llm_output()`
— el único traductor checkpoint→finding activo en producción real
("Ruta B verificada") — construía el `llm_output` a mano y nunca se
validaba contra `finding_llm_v1` antes de usarse. Misma clase de
defecto que causó B3→B4→B5 ("no parchear el segundo sitio"), localizada
en el sitio real.

**Cerrado con**: `factory/tests/test_checkpoint_finding_contract.py`
(11 tests) — pin de hash de ambos schemas (fuerza `_v2.json` nuevo ante
cualquier cambio real) + round-trip real del traductor de producción
contra `finding_llm_v1` para los 5 `estado` reales + 2 tests de control
que confirman que el schema detecta drift sintético de verdad.

**Commit**: `fa25c9d`.

──────────────────────────────────────────────────────────────────────
EXPERIMENTO C REAL (autorizado en corrida separada, tras Bloques 0-3)
──────────────────────────────────────────────────────────────────────

**Primera corrida (2 llamadas, `PILOT_EXECUTION-2026-010`)**: por error
de ejecución, se revalidó P4/P6 con el pipeline ya corregido (furniture
fix) pero SIN aislar la prosa de la tabla — mismo chunk mixto de
siempre. Resultado: ambos `evidencia_insuficiente`, sin cita — mismo
patrón histórico. Checkpoints: `chunked-5a439f3fde11` (P4),
`chunked-554544f4090f` (P6).

**Segunda corrida (2 llamadas más, mismo `PILOT_EXECUTION-2026-010`,
corrección del error)**: se construyó de verdad la representación
aislada — tabla de señales I/O y cabecera/pie de plantilla removidas a
mano, prosa relevante en su posición narrativa natural (sin reordenar,
una sola variable manipulada). Texto final: 1670 caracteres (vs. 2427
originales), ratio de señal 6.6% (vs. 4.5%). Verificación mecánica
previa (0 llamadas) confirmó la separación antes de gastar la llamada.
Checkpoints: `chunked-8e2b20bfa511` (P4 aislado),
`chunked-510444cedc9b` (P6 aislado).

**RESULTADO: IDÉNTICO al de la corrida sin aislar.** Ambos
`evidencia_insuficiente`, `evidencia_exacta=""`, todos los criterios
`NOT_MET`/`NOT_ASSESSABLE`. Remover la tabla por completo y dejar la
prosa en contexto limpio **no cambió el juicio del modelo**.

### Conclusión final (responde §23 de la auditoría original con evidencia directa)

La hipótesis de dilución tabular para P4/P6 queda **REFUTADA por
experimento real**, no solo sin confirmar. Sumado a R2 (P2/P5, evidencia
perfectamente aislada, juicio sin cambio) y a la recalificación de P7:
**los 5 casos positivos fallidos del fixture 7P+2N (P2, P4, P5, P6, P7)
comparten la misma causa raíz — el techo de juicio del modelo de 7B, no
representación, extracción, chunking ni recuperación.** Ninguna mejora
de pipeline (kerning, furniture, fusión semántica, aislamiento tabular)
movió el resultado en ningún caso medido.

**Consecuencia de diseño**: construir `Table`/`EvidenceUnit` para
atacar recall de juicio ya NO se justifica con la evidencia disponible
— quedan como diseño válido solo si aparece un caso futuro distinto al
ya medido.

──────────────────────────────────────────────────────────────────────
CIERRE — bloque ENTREGA real (vs. el plantilla de CONTINUACION_FASE0_P4_FASE1.md)
──────────────────────────────────────────────────────────────────────

```
P4_DIAGNOSED             = dilución tabular (mismo chunk que P6) — R8 cerrado
R8_CLOSED                = sí
SINGLE_SURFACE_REUSE      = alias público strip_page_furniture (evidence_verifier.py),
                            importado por chunked_engine.build_page_chunks()
FASE0_DIFF_APPROVED       = sí
FASE0_TESTS               = 4 nuevos + regresión completa verde (119/119 + 2/2 replay)
FASE0_GOLDEN_DATASET      = 8/8 sin regresión (N1/N2 intactos)
FASE0_COMMIT              = e271488
FASE1_MECHANICAL_RESULT   = P4/P6: separación limpia (4.53%→6.6% tras aislar).
                            P7: sin tabla real, recalificado al bucket de P2/P5
FASE3_JUSTIFIED           = sí (ejecutada, ver Experimento C)
CHECKPOINT_PRESERVATION   = cumplido — 4 checkpoints reales preservados en
                            factory/regulatory/pilot_run/checkpoints/
CONTRATO_FORMAL_STATUS    = implementado, 11 tests, commit fa25c9d
EXPERIMENTO_C_RESULTADO   = REFUTADA la hipótesis de dilución tabular —
                            resultado idéntico con y sin tabla
BOTTLENECK_CONCLUSION     = F (el modelo/LLM), confirmado para los 5 casos
                            positivos fallidos del fixture, no solo P2/P5
LLM_CALLS_TOTAL           = 4 (todas bajo PILOT_EXECUTION-2026-010, de 25
                            autorizadas; ninguna PILOT_EXECUTION nueva propuesta)
GATE_0                    = único fallo propio ya resuelto (test_runtime_identity,
                            limpio tras commit); resto ajeno (playwright/live,
                            decision-store en vivo, no relacionado)
CODE_CHANGED              = chunked_engine.py, evidence_verifier.py (Bloque 1);
                            factory/tests/test_checkpoint_finding_contract.py (Bloque 3)
DEPENDENCIES_ADDED        = 0
COMMITS                   = e271488, fa25c9d, 2a218b1 (docs), 5e876e5 (review_queue)
PRODUCTION_ENABLEMENT     = BLOCKED (sin cambio)
```

**Pendiente explícito para Cesar**: 2 hallazgos reales de P6 quedaron en
`factory/layer9/review_queue.jsonl` como `PROVISIONAL_GAP`, pendientes
de adjudicación humana — fuera de alcance de esta corrida.
