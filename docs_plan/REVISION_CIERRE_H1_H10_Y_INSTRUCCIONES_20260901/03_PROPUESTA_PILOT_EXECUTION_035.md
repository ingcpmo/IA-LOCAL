# 03 — PROPUESTA `PILOT_EXECUTION-2026-035` (diagnóstico R2, ≤ 20 llamadas)

**Estado:** PROPUESTA. `agent_proposed`. **NO ejecutada. 0 llamadas consumidas.**
Requiere confirmación de Capa 9 por Mission Control / governance service.

## Pregunta única

Las 6 vías (H1-H4 · 14B · fusión · R2 · B4b · B4b no-estricta) convergen en recall 0–2/7 con
**0 `SATISFIES` / 0 `PARTIAL`** en las 56 subcriterios. Lo que ninguna aisló:
**¿el fallo está en el paso A (descripción operativa neutra con pérdida) o en el paso B
(mapeo al sub-criterio, incapaz incluso con un buen insumo)?**

## Diseño

Diagnóstico, no cambio de producto. **Se salta el paso A**: a `step_b_criterion_mapping`
(prompt firmado, sin modificar) se le entrega una **descripción neutra ideal escrita a mano**
del pasaje de evidencia de cada positivo (fuente: el propio fixture 7P+2N), en vez de la
salida del 7B. Critic, `evidence_verifier` (A/B/C/D) y adjudicador, sin cambios.

## Parámetros

| Campo | Valor |
|---|---|
| **Baseline (PRE)** | `REGULATORY_POSITIVE = 0/7` (B4b, `b4b-20260827T201816Z`); paso B: **0 `SATISFIES` / 0 `PARTIAL`** en 56 subcriterios (idéntico en B4b no-estricta) |
| **Fixture** | `docs_plan/W5V2_RECALL_FIXTURE_SET_DRAFT.md`, sin re-etiquetar. Sub-muestra dirigida: **P1** (`21_CFR_11.10(e)`, LEXICAL_ECHO), **P2** (`21_CFR_11.10(g)`), **P5** (`ALCOA_CONTEMPORANEOUS`) + **N1** (`ANNEX11_4`, control negativo) |
| **evaluation_profile** | juicio V2 2-pasos firmado, con **paso A desactivado en el diagnóstico** (insumo = descripción ideal manual). El resto igual que B4b |
| **Retrieval activo** | `build_fusion_candidate_pool` (RRF BM25 + embeddings). Índice ya construido para RW-0005/0011/0012 (`EMBED_EXECUTION-2026-001/002`). 0 llamadas de embedding nuevas (consulta cacheada) o ≤ 4 si hay que recomputar — cuentan aparte, gobernadas por `EMBED_EXECUTION` |
| **Métrica PRE** | paso B `SATISFIES\|PARTIAL` rate = **0 / N** subcriterios sobre P1/P2/P5 |
| **Presupuesto** | `hard_call_cap = 20`. Estimado real: 3 unidades × (1–2 subcriterios que mapean al fixture + Critic) ≈ **8–12 llamadas**. `stop_reason` forzado a las 20 |
| **Criterio PASS/FAIL** | **PASS → el fallo es el paso A:** ≥ 1 `SATISFIES\|PARTIAL` en P1/P2/P5 con cita que pasa `evidence_verifier` (A+B+C) y Critic ≠ DISAGREE, **y** N1 sigue sin anclar. Implica avenida real: mejorar la extracción de descripción (posible modelo mayor solo para el paso A). **FAIL → el techo es el paso B:** 0 `SATISFIES\|PARTIAL` aun con descripción ideal. Confirma el techo estructural del 7B en el mapeo regulatorio → **Palanca C (Tier-1) permanente es la respuesta definitiva**, sin más experimentos de arquitectura |
| **Invariantes** | `AI_RUNTIME=LOCAL_ONLY` · `EXTERNAL_LLM_CALLS=0` · `DOCUMENT_EGRESS=0` · `network_locked()`. Ningún validador se relaja. Ningún prompt gobernado se modifica (la descripción ideal es un insumo de diagnóstico, no un cambio de `step_a`). Resultado se reporta tal cual |
| **Canal** | `PILOT_EXECUTION-2026-035` propose (Capa 8) → confirm por Capa 9 en Mission Control |

## Qué NO es esta propuesta

- No es un cambio de la variante del paso B (estricta vs no-estricta ya se midieron, ambas 0/7).
- No es probar un modelo mayor (eso es qualification de modelo, decisión aparte).
- No es few-shot (eso es contenido gobernado del prompt).
- No degrada ni relaja ningún validador.

## Alternativas si Capa 9 prefiere otro alcance

1. **Modelo local mayor en el paso B** (p.ej. `qwen2.5:32b-instruct` quant) sobre P1/P2/P5 —
   requiere `MODEL_QUALIFICATION` (familia de gobernanza distinta) + presupuesto mayor
   (7P × ~8 subcriterios ≫ 20).
2. **Cerrar sin más medición**: adoptar Palanca C permanente ya (B4b §6 opción A) y archivar
   la vía de juicio LLM para Regulatory. Cero llamadas.
