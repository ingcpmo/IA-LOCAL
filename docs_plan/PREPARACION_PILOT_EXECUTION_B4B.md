# Preparación de la `PILOT_EXECUTION` para B4b — medición de recall V2

**Fecha:** 2026-08-27. **Autor:** Capa 8. **Autoridad de firma:** Capa 9 = Cesar.
**Contexto:** los 3 prompts de juicio V2 quedaron **firmados** (`prompt_version 1.0`, commit `218b00c`).
Falta la `PILOT_EXECUTION` para autorizar las llamadas reales a Ollama del fixture 7P+2N por el
flujo V2. `docs_plan/PLAN_VALIDACION_ANALIZADOR_GMP_LOCAL_V2.md` FASE 10, Suite A.

---

## 1. ¿Se puede usar una `PILOT_EXECUTION` existente?

**No — por presupuesto, no por cobertura.** Hay una vigente:

```
PILOT_EXECUTION-2026-030   ACTIVE / human_confirmed   max_calls = 46
cubre RW-0005, RW-0011, RW-0012  (los 3 documentos del fixture)
```

`_select_pilot_execution_instance(['RW-0005','RW-0011','RW-0012'])` la selecciona. Pero
**46 llamadas no alcanzan** para la corrida V2 del fixture (ver §3). La regla dura del skill
`gmp-recall-pipeline` ("nunca proponer una nueva si ya existe vigente con presupuesto") **no
aplica aquí**: hay necesidad real: el presupuesto de `-2026-030` es insuficiente para este
alcance. Se propone una **nueva** instancia, dimensionada.

## 2. Alcance (`scope`) — lista explícita de unidades

El fixture 7P+2N (`W5V2_RECALL_FIXTURE_SET_DRAFT.md`), tal cual, sin re-etiquetar:

| # | case | document_id | agent_id | requirement_id | purpose | sub-criterios (decomposition v1.1) |
|---|---|---|---|---|---|---|
| 1 | P1 | RW-0005 | fda_part11_agent | 21_CFR_11.10(e) | sample | 9 |
| 2 | P2 | RW-0005 | fda_part11_agent | 21_CFR_11.10(g) | sample | 3 |
| 3 | P3 | RW-0005 | eu_annex11_agent | ANNEX11_17 | sample | 4 |
| 4 | P4 | RW-0011 | alcoa_plus_agent | ALCOA_ATTRIBUTABLE | sample | 5 |
| 5 | P5 | RW-0005 | alcoa_plus_agent | ALCOA_CONTEMPORANEOUS | sample | 3 |
| 6 | P6 | RW-0011 | fda_cgmp_211_agent | 21_CFR_211.68(b) | sample | 7 |
| 7 | P7 | RW-0012 | fda_cgmp_211_agent | 21_CFR_211.68(b) | sample | 7 |
| 8 | N1 | RW-0005 | eu_annex11_agent | ANNEX11_4 | sample | 3 |
| 9 | N2 | RW-0005 | fda_part11_agent | 21_CFR_11.10(e) | sample | 9 |

**Total: 50 sub-criterios** sobre 9 unidades, 3 documentos, 4 agentes.
`authorizes_corpus = false`, `authorizes_baseline = false` (diagnóstico, no corpus formal).

## 3. Dimensionamiento — `max_calls`

Por (sub-criterio × candidato del EvidenceBundle): **1 paso A + 1 paso B + (Critic solo si el
veredicto es SATISFIES/PARTIAL, ~30 % estimado)**. Tres niveles de profundidad de candidato:

| Profundidad | Qué mide | Llamadas (A+B) | + Critic (~30 %) | **max_calls sugerido (con ~20 % margen de reintento)** |
|---|---|---|---|---|
| **top-1 candidato/sub-criterio** | mínimo; riesgo: una miss de recuperación se ve como miss de juicio | ~100 | ~15 | **140** |
| **top-2 candidato/sub-criterio** | equilibrado | ~200 | ~30 | **280** |
| **top-3 candidato/sub-criterio** (= k de R2) | comparable directo con las mediciones R2/R4 | ~300 | ~45 | **420** |

**Recomendación de Capa 8: top-2, `max_calls = 280`.** Razón: top-1 puede subestimar el recall
por una miss de recuperación (el reranker léxico bilingüe pone el pasaje correcto en rank 1 o 2
en la mayoría de casos medidos, pero no siempre); top-3 duplica el coste sin señal adicional
clara sobre top-2. Si prefieres el comparable exacto con R2, top-3 / `max_calls = 420`.

## 4. Mecánica de la corrida (B4b)

- **Background con checkpoints**, mismo arnés que `judgment.run_judgment_batch` /
  `corpus_runner.run_pilot_sample_batch` — resumible, **hard-stop en `max_calls`** antes de
  gastar una llamada que lo excedería (nunca arranca una unidad a medias).
- Modelo: `qwen2.5:7b-instruct-q4_K_M` (el del analizador; ya instalado). `temperature = 0`.
- Cero egress: la corrida se ejecuta bajo el chequeo `validation_v2.local_only` (verificamos
  `DOCUMENT_EGRESS = 0` en la misma corrida).
- Salida: por caso `{case, kind, machine_state, anchored, fabricated_citation, schema_valid,
  latency_s}` → `validation_v2.gates.evaluate_regulatory` → `interpret_regulatory`.
- **Instrumento de éxito, sin relajar nada** (`PLAN_VALIDACION` §2): `REGULATORY_POSITIVE ≥ 6/7`
  con cita anclada · `REGULATORY_NEGATIVE = 2/2` (ANNEX11_4, N2 rechazados) ·
  `FABRICATED_CITATIONS = 0` · `SCHEMA_VALID_RATE = 100 %`.

## 5. Qué necesito de ti

1. **Elige la profundidad de candidato / `max_calls`**: top-1 (140) · **top-2 (280, recomendado)** · top-3 (420).
2. Con eso registro la propuesta `agent_proposed` (`pilot_execution.propose_pilot_execution`,
   scope de §2, `max_calls` elegido) y te la presento para tu **`confirm` (`human_confirmed`)** —
   ese es tu acto de firma.
3. Tras tu `confirm`, lanzo B4b en background y te reporto el resultado con la interpretación de
   `gates.interpret_regulatory` sin eufemismos.

**Hasta tu `confirm`: 0 llamadas reales a Ollama.**
