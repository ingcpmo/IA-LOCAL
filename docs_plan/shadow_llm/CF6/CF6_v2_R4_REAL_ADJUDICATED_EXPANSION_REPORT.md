# CF-6 v2.0 · R4 — Ampliación de REAL_ADJUDICATED (autorizada por Capa 9, 2026-09-05)

**Instrucción:** "autoriza ampliar REAL_ADJUDICATED antes de recalibrar" — respuesta al
hallazgo de R4 (el óptimo hallado contra el fixture sintético, incluso su versión v2, queda por
encima de los `weighted_ratio` de los 2 únicos candidatos reales confirmados `RELEVANT`; n=27
es insuficiente para decidir nada). **0 llamadas LLM.**

## Qué se hizo

`factory/regulatory/shadow/real_adjudicated_pool_builder.py` (10 tests) — reutiliza
`relevance_model.classify_entry()` (sin modificarlo) sobre las citas YA ANCLADAS en L2
(`FINAL_GMP_CORPUS_FINDINGS.json`, 457 findings, corpus completo) de las **60 secciones dentro
de alcance** (con `decomposition.yaml`) — no solo las 7 de la muestra congelada de R2. Los
candidatos son reales (extraídos de documentos reales, nunca fabricados); solo la clasificación
es determinista y ya existente.

```
n_secciones_en_alcance         = 60  (de 66 totales; 6 fuera por falta de decomposition.yaml
                                       o sin regulación asociada)
n_candidatos_totales           = 294  (antes: 27)
n_ya_adjudicados_preservados   = 27  (mismo human_label exacto que en R2, verificado en test --
                                       nunca se re-etiquetan)
n_pendientes_de_adjudicación   = 267
```

**Subconjunto prioritario para etiquetado práctico**: 100 candidatos (de los 267 pendientes),
ordenados por cercanía al umbral actual (0.12) + máximo 3 por combinación documento×requisito
(para no concentrar la muestra en un solo caso). Cobertura: **5 documentos** (RW-0005: 23,
RW-0006: 21, RW-0011: 16, RW-0012: 21, RW-0014: 19) y **11 requisitos distintos** — mucho más
representativo que los 2 requisitos (`21_CFR_11.10(d)`, `21_CFR_11.50_11.70`) que agotaban la
muestra de 27.

Artefacto completo: `docs_plan/shadow_llm/CF6/CF6_v2_R4_REAL_ADJUDICATED_EXPANDED_POOL.json`
(294 candidatos completos + subconjunto prioritario de 100, ambos con `human_label: null` donde
no hay adjudicación previa).

## Los 10 candidatos más cercanos al umbral (mayor valor informativo)

| documento | requisito | ratio | veredicto modelo | cita (recortada) |
|---|---|---|---|---|
| RW-0005 | 21_CFR_11.10(e) | 0.1196 | INCONCLUSIVE | "The Critical Alarm Audit Trail entry will contain the follow..." |
| RW-0005 | 21_CFR_11.10(e) | 0.1196 | INCONCLUSIVE | "The Critical Alarm Threshold Change Audit Trail entry will c..." |
| RW-0005 | 21_CFR_11.10(e) | 0.1196 | INCONCLUSIVE | "The Critical Alarm Threshold Change Audit Trail entry will c..." |
| RW-0006 | 21_CFR_11.10(e) | 0.1196 | INCONCLUSIVE | "3.3.1 Every time a critical alarm threshold is modified an a..." |
| RW-0012 | 21_CFR_11.50_11.70 | 0.1212 | **PARTIALLY_RELEVANT** | "This is an uncontrolled document and shall be considered obs..." |
| RW-0011 | 21_CFR_11.10(e) | 0.1216 | **PARTIALLY_RELEVANT** | "The operator can acknowledge an alarm" |
| RW-0012 | 21_CFR_11.10(e) | 0.1216 | **PARTIALLY_RELEVANT** | "previously, with the proper credentials, the input points ca..." |
| RW-0014 | 21_CFR_11.10(e) | 0.1216 | **PARTIALLY_RELEVANT** | "The operator can request water delivery (for sample) by pres..." |
| RW-0005 | 21_CFR_11.10(d) | 0.1231 | **PARTIALLY_RELEVANT** | "runtime security restricts graphical user interface access a..." |
| RW-0005 | ALCOA_CONTEMPORANEOUS | 0.1132 | INCONCLUSIVE | "Gray – General meaning is 'Not Operating' (e.g., motor not r..." |

Nota sin interpretar por Claude Code: 4 de estos 10 candidatos con mayor ratio son
`21_CFR_11.10(e)` (audit trail) — un requisito NUNCA representado en los 27 originales
(que solo cubrían `21_CFR_11.10(d)` y `21_CFR_11.50_11.70`). Esta ampliación introduce, por
primera vez, casos de audit trail cerca del umbral para que Capa 9 los adjudique.

## Qué no cambia

`decomposition.yaml`, `relevance_model.py`, `FINAL_GMP_CORPUS_FINDINGS.json` (L2), el prompt
firmado y `CONFIG_R4` — sin tocar (verificado por hash en test). 0 llamadas LLM. Los 27 pares ya
adjudicados en R2 conservan su etiqueta exacta.

## STOP

No se recalibró nada. No se etiquetó nada nuevo (Claude Code no adjudica). Queda pendiente de
Capa 9/QA: adjudicar el subconjunto prioritario (100 candidatos, o el tamaño que Capa 9 decida)
antes de recalcular `evidence_relevance_accuracy` y considerar cualquier recalibración.
