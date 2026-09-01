# Bake-off de modelos — capa semántica del modelo híbrido (POC, FASE 2)

**Fecha:** 2026-09-01
**Alcance:** Mesa de Diseño «Modelo Híbrido Determinista + Ollama», FASE 2 — prototipo aislado.
**Estado:** **FASE 2 CERRADA = PASS / PARKED** por Capa 9 (2026-09-01). No FASE 3,
no integración. Bake-off (2 corridas), H-4 (§8) y prueba de recall (§9,
**refutada**: 1/7 < 2/7). Foco activo → R1.5 / R2. Ver §10.
**No se modificó** producto, reglas, findings, provenance ni audit trail real.
**AI_RUNTIME:** LOCAL_ONLY · **DOCUMENT_EGRESS:** 0 · **EXTERNAL_LLM_API:** 0.

---

## 1. Qué se probó

Prototipo en `factory/prototypes/semantic_hybrid_poc/` (fuera de `app/` y de
`factory/regulatory/`). Pipeline de un `SemanticContextAssessment`:

```
finding determinista (v1.2)  ->  context_composer (store canónico, SOLO LECTURA)
  ->  pinned_client  (Ollama local, R3 pinning + R4 `format`=JSON Schema)
  ->  validator      (fail-closed, sin reparación heurística — R4)
  ->  citation_gate  (substring literal vs texto canónico, umbral 0.93 — R5)
  ->  resultado {assessment_status, semantic_coverage, required_elements[], grounded_quotes[]}
```

La capa **nunca** decide cumplimiento y **nunca** toca `machine_state / risk_band /
confidence / evidence_basis / finding / provenance`. Sólo produce contexto para el
auditor humano.

### Muestra estratificada

Findings **reales** de la corrida `postmejoras_v4_20260831` (r1), 6 documentos RW,
motor determinista v1.2. 2 findings por subtipo (los que había):

| Subtipo | Disponibles | Muestreados |
|---|---:|---:|
| AUTHORITY_CHECK_GAP | 4 | 2 |
| ACCESS_CONTROL_GAP | 2 | 2 |
| BACKUP_RECOVERY_GAP | 2 | 2 |
| AUDIT_TRAIL_DESIGN_GAP | 2 | 2 |
| AUDIT_TRAIL_INTEGRITY_GAP | 2 | 2 |
| ALCOA_ATTRIBUTABLE_GAP | 4 | 2 |
| REGULATORY_INCONCLUSIVE | 342 | 2 |
| REQUIREMENT_NOT_TESTED | **0** | **0** — sin instancias en el corpus; **no evaluado** |

**n = 14 assessments por modelo.** Modelos: `qwen2.5:7b-instruct-q4_K_M`
(digest `845dbda0ea48…`) y `mistral:7b-instruct-q4_K_M` (digest `1a85656b534f…`).
Ollama 0.33.0.

### Pinning aplicado (R3)

`temperature=0, seed=7, num_ctx=16384, num_predict=1500, top_p=0.9, top_k=40,
repeat_penalty=1.1`. Se registra `model_digest` (no el tag) e `input_fingerprint =
sha256(digest | prompt_version | prompt | options)`. `prompt_version = scta-poc-1.0`.

---

## 2. Resultados — tabla comparativa

Se ejecutaron **dos corridas**: (A) con el gate original y (B) con el gate
endurecido H-1/H-2/H-3 (§6-bis). Mismo prompt, mismo pinning, misma muestra.
Los crudos de (A) están en `bakeoff_results/pre_hardening_20260901/`.

| Métrica (n=14) | qwen — gate A | qwen — **gate B** | mistral — gate A | mistral — **gate B** |
|---|---:|---:|---:|---:|
| Cumplimiento de schema | 14/14 | **14/14** | 14/14 | **14/14** |
| `FAILED` | 0 | **0** | 0 | **0** |
| `COMPLETED` (evidencia anclada real) | 5 | **4** | 5 | **2** |
| `CONFIRMS_ABSENCE` (concuerda con el motor) | — | **7** | — | **0** |
| `INDETERMINATE` (sin señal útil) | 9 | **3** | 9 | **12** |
| **Findings con señal útil** (`COMPLETED` ∪ `CONFIRMS_ABSENCE`) | 5/14 (36 %) | **11/14 (79 %)** | 5/14 (36 %) | **2/14 (14 %)** |
| **Citas fabricadas que SOBREVIVEN al gate** | **0** | **0** | **0** | **0** |
| Citas fabricadas rechazadas (pre-gate) | 5 | 7 | 9 | 12 |
| Citas ancladas verificadas (literal) | 10 | 8 | 7 | 4 |
| `near_match` difusos rechazados por H-2 | n/a | 2 | n/a | 3 |
| Elementos `PRESENT/CONTRADICTORY` degradados a `UNCLEAR` por H-3 | n/a | 5 | n/a | 7 |
| `quote_verification_rate` (media entre COMPLETED) | 1.00 | 1.00 | 1.00 | 1.00 |
| Contradicciones señaladas | 0 | 0 | 0 | 0 |
| Latencia p50 / p95 / máx (s) | 112 / 221 / 238 | 125 / 267 / 272 | 107 / 273 / 299 | 127 / 309 / 334 |

### Reproducibilidad (N=3 repeticiones, sub-muestra de 3 findings, mismo input)

Medida en la corrida B. **No cambia respecto de A** — el gate es determinista y
ortogonal a la (in)estabilidad del modelo.

| | qwen2.5:7b-instruct | mistral:7b-instruct |
|---|---:|---:|
| Findings con salida **bit-idéntica** en 3/3 | 1/3 (0.33) | 2/3 (0.67) |
| Findings con **status idéntico** en 3/3 | 2/3 (0.67) | 3/3 (1.00) |

Patrón: la repetición 1 difiere de la 2, y luego 2 == 3 (arranque en frío /
estado de KV-cache en llama.cpp CPU). En qwen `ACCESS_CONTROL_GAP RW-0006 p.16`
el status **cambió** entre repeticiones (rep1 `INDETERMINATE` → rep2–3
`COMPLETED`). El endurecimiento **no** corrige esto — es lo que resuelve H-4
(verificación 2× + calentamiento). La deriva va **hacia / entre estados no
confiados**, nunca hacia una afirmación de cumplimiento.

### Cache (R7) — PASS

`RW-0012 p.5` y `RW-0014 p.5` (ambos `AUTHORITY_CHECK_GAP`) comparten
`source_hash = 3ebeb4b701a08918…` → `cache_key` idéntica
(`4bd9f67d9c5a2fff…`) → **1 sola inferencia** para el par. Confirmado por código
en las dos corridas.

---

## 3. Lectura de los resultados

### 3.1 Lo que funciona y es transferible a producción

1. **El `format` = JSON Schema de Ollama es sólido.** 28/28 respuestas (ambos
   modelos) validaron contra el schema al primer intento. Cero `FAILED`, cero
   reparación heurística. R4 se sostiene.
2. **El gate de citas R5 es la barrera efectiva anti-alucinación.** Sobre
   documentos reales, **ambos** modelos fabricaron citas — corrida A: qwen 5,
   mistral 9; corrida B (gate estricto): qwen 7, mistral 12. El gate determinista
   —`is_literally_anchored` + `match_citation` del propio proyecto— rechazó el
   **100 %** en las dos corridas. Ninguna cita no verificada llegó al resultado.
   Independiente del modelo y de su estabilidad.
3. **La degradación es fail-safe.** Cuando el modelo no puede anclar, el resultado
   es `INDETERMINATE` o `CONFIRMS_ABSENCE` (nunca una afirmación de cumplimiento).
   Con el gate endurecido: qwen 3 `INDETERMINATE` + 7 `CONFIRMS_ABSENCE`, mistral
   12 `INDETERMINATE`. El auditor recibe "sin evidencia semántica verificable" o
   "el modelo concuerda con la ausencia", nunca una afirmación sin respaldo.
4. **El cache por `source_hash` es real y mensurable.** En el corpus de 6
   documentos hay ~25 `source_hash` compartidos entre documentos → la capa
   semántica no re-infiere texto idéntico.

### 3.2 Hallazgos de endurecimiento

| # | Hallazgo | Estado | Acción |
|---|---|---|---|
| H-1 | `emitted=0 → INDETERMINATE` mezcla "el modelo confirma ausencia" con "el modelo no produjo evidencia". | **HECHO** (corrida B) | Estado `CONFIRMS_ABSENCE` distinto de `INDETERMINATE`. Rescató 7 findings en qwen. |
| H-2 | `verify_quote` aceptaba `method=fuzzy` ≥ 0.93 como "verificada"; R5 pide substring **literal**. | **HECHO** (corrida B) | Sólo `is_literally_anchored` cuenta; fuzzy ≥ 0.93 → `near_match`, descartada. Corrigió 1 falso `COMPLETED` en qwen, 2 en mistral. |
| H-3 | El gate no degradaba `verdict=PRESENT` con `supporting_quote=null`. | **HECHO** (corrida B) | `PRESENT`/`CONTRADICTORY` sin cita verificada → `UNCLEAR`. 5 elementos degradados en qwen, 7 en mistral. |
| H-4 | Deriva run-to-run con pinning completo (ver §2). El endurecimiento **no** lo corrige. | **HECHO** (§8) | `stability.py`: `warmup()` + `assess_stable(n=2)`. status/verdict discrepan entre corridas → `INDETERMINATE` + `stability_flag`. 3 tests. Marcó 2 inestables en §9. |
| H-5 | `contradictory_evidence` nunca se pobló (0/28, ambas corridas). | **PENDIENTE (FASE 3)** | Añadir a la muestra A/B ≥ 2 findings donde el documento sí describe el comportamiento. |
| H-6 | `REQUIREMENT_NOT_TESTED` no evaluado (0 instancias en el corpus). | **PENDIENTE (FASE 3)** | Evaluarlo cuando aparezca, o construir 1–2 casos sintéticos. |

### 3.3 Diferencias qwen vs mistral (bajo el gate endurecido B)

- **Señal útil:** qwen **11/14 (79 %)** — 4 `COMPLETED` con cita anclada + 7
  `CONFIRMS_ABSENCE` (concuerda con el motor determinista). mistral **2/14
  (14 %)**. Es la diferencia decisiva.
- **Por qué mistral colapsa bajo el gate correcto:** siempre emite exactamente 1
  cita, y ~⅔ de las veces es inventada. Al retirar H-2 (crédito por match difuso)
  y H-3 (crédito por `PRESENT` sin cita), mistral pierde casi toda su salida
  "positiva" → 12/14 `INDETERMINATE`. Y nunca gana `CONFIRMS_ABSENCE` porque su
  compulsión de citar le impide el patrón "todo ABSENT, sin citas".
- **qwen es disciplinado:** cuando no puede anclar, no cita → H-1 lo convierte en
  `CONFIRMS_ABSENCE`, señal directamente utilizable.
- **Calidad de evidencia:** qwen 8 citas ancladas verificadas vs mistral 4.
- **Estabilidad:** mistral algo más estable run-to-run (status 3/3; qwen 2/3) —
  su única ventaja, y no compensa lo anterior.

---

## 4. Recomendación de modelo

**`qwen2.5:7b-instruct-q4_K_M`** (digest `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`).

Motivos (reforzados por la corrida con gate endurecido):

1. **Señal útil 79 % vs 14 %.** Bajo el gate correcto (estricto), qwen produce
   algo accionable para el auditor en 11 de 14 findings; mistral en 2 de 14. El
   resto de mistral es `INDETERMINATE` — trabajo cero para el revisor.
2. `CONFIRMS_ABSENCE` es casi exclusivo de qwen (7 vs 0): concuerda de forma
   explícita y anclable-por-ausencia con el motor determinista.
3. Más evidencia anclada verificada (8 vs 4).
4. Su inestabilidad va **entre estados no confiados** (`INDETERMINATE` ↔
   `COMPLETED`), nunca hacia una afirmación de cumplimiento, y es **mitigable**
   con calentamiento + verificación 2× (H-4).
5. Es el digest ya fijado en el diseño de FASE 1 (`semantic_mode.yaml`, §9) y de
   la misma familia usada en el resto de la Factory — consistencia de pinning.
6. Igual cumplimiento de schema (1.00), cero `FAILED`.

La ligera ventaja de estabilidad de mistral no compensa que, con un gate que
respeta R5, produce casi nada utilizable.

### Vocabulario (R2)

La capa semántica se declara **`REPRODUCIBLE_UNDER_PINNED_CONDITIONS`**, nunca
`DETERMINISTIC`. Tasa de reproducibilidad **medida** (N=3, no asumida):
salida bit-idéntica 1/3 (qwen) · 2/3 (mistral); status idéntico 2/3 (qwen) ·
3/3 (mistral). El invariante de seguridad (`fabricated_evidence_surviving_gate =
0`) **sí** es determinista y se sostuvo en las 3 repeticiones de cada caso.

---

## 5. Presupuesto de latencia por corrida

- Alcance de la capa semántica (diseño FASE 1 §11): `QA40 sample ∪ (would_degrade)`
  ≈ **90–100 findings** por corrida documental.
- Dedup por `source_hash` (cache R7): ~25 hashes compartidos en el corpus de 6
  docs → **≈ 75–80 inferencias únicas**.
- qwen p50 ≈ 112–125 s/inferencia en esta máquina (CPU, sin GPU) — 112 s corrida
  A, 125 s corrida B; p95 ≈ 220–267 s.

| Configuración | Tiempo estimado |
|---|---|
| Serie, 1 worker, sin verificación 2× | ≈ 2.5–2.8 h |
| Serie, 1 worker, **con** verificación 2× (H-4) | ≈ 5–5.5 h |
| 3 workers en paralelo, con verificación 2× | ≈ 1.7–2 h |

Es un paso **batch/offline**, posterior al pase determinista y **previo** a la
cola de revisión humana. No es interactivo. Compatible con el diseño de FASE 1.

---

## 6. Criterio PASS/FAIL de FASE 2

| Criterio | Resultado |
|---|---|
| `fabricated_evidence = 0` tras el gate | **PASS** — 0 en las **dos** corridas (gate A y gate B), incl. 3× repeticiones. El endurecimiento sólo lo refuerza. |
| Cumplimiento de schema medido | **PASS** (1.00, ambas corridas, medido) |
| `reproducibility_rate` reportado (no asumido) | **PASS** (N=3; qwen 0.33 salida / 0.67 status, mistral 0.67 / 1.00 — valor bajo, lo ataca H-4) |
| Cache verificado (RW-0012/RW-0014 → 1 inferencia) | **PASS** (ambas corridas) |
| Test obligatorio: cita fabricada inyectada → gate la rechaza → `INDETERMINATE` | **PASS** (`test_poc.py`, 15/15) |
| Ninguna cita no verificada sobrevive al gate | **PASS** (incl. §10: 20 fabricadas pre-gate → 0 sobreviven) |
| H-4 gate de estabilidad | **PASS** — incorporado (§8), 3 tests, marca inestables → `INDETERMINATE` |
| Prueba de red de seguridad de recall (§9) | **REFUTADA** — 1/7 < 2/7 baseline. La capa NO arregla recall. |

**FASE 2 = PASS** en su alcance de seguridad y decision-support; **NEGATIVO** para
recall (§9). H-1/H-2/H-3/H-4 incorporados y medidos. La decisión de rol/modelo
es de Cesar (§9).

---

## 6-bis. Endurecimiento incorporado (2026-09-01, post-bake-off)

H-1, H-2 y H-3 se implementaron en el prototipo aislado. Cambios:

| Hallazgo | Antes | Ahora | Test |
|---|---|---|---|
| **H-2** | `verify_quote` marcaba `verified=True` con match difuso ≥ 0.93. | `verified=True` **solo** por `is_literally_anchored` (substring literal). El difuso ≥ 0.93 se reporta `near_match=True` y **se descarta** (no cuenta para `quote_verification_rate`). | `test_h2_fuzzy_match_is_never_marked_verified`, `test_h2_fuzzy_quote_does_not_count_toward_verification_rate` |
| **H-3** | Un `verdict=PRESENT/CONTRADICTORY` con `supporting_quote=null` sobrevivía. | Sin cita literal verificada ⇒ `verdict` se degrada a `UNCLEAR` (se guarda `verdict_original`). Contador `elements_forced_unclear`. | `test_h3_present_without_quote_is_forced_unclear`, `test_h3_contradictory_without_quote_is_forced_unclear` |
| **H-1** | `emitidas == 0` ⇒ siempre `INDETERMINATE` (mezclaba "modelo confirma ausencia" con "modelo falló"). | `emitidas == 0` **y** todos los elementos `ABSENT` (sin citas inventadas) ⇒ **`CONFIRMS_ABSENCE`** / `coverage=UNSUPPORTED` (coincide con el finding determinista). Cualquier otra combinación ⇒ `INDETERMINATE`. Un `ABSENT` con cita literal verificada sigue siendo `COMPLETED`. | `test_h1_all_absent_no_quotes_is_confirms_absence`, `test_h1_mixed_absent_and_unclear_is_indeterminate_not_confirms_absence`, `test_h1_confirms_absence_requires_at_least_one_element`, `test_h1_grounded_absence_stays_completed` |

Archivos tocados (todos dentro del workspace aislado):
`citation_gate.py` (lógica), `runner.py` (propaga `near_matches` /
`elements_forced_unclear`), `bakeoff.py` `_metrics` (nuevas columnas
`confirms_absence_rate`, `near_matches_total`, `elements_forced_unclear_total`),
`test_poc.py` (**7 → 15 tests, 15/15**), `pinned_client.py` (reintento ante caída
transitoria de Ollama — petición idéntica, no altera pinning).

**Re-medición HECHA (corrida B, 2026-09-01).** Efecto sobre qwen (14 findings):

| Movimiento | n | Hallazgo |
|---|---:|---|
| `INDETERMINATE` → `CONFIRMS_ABSENCE` | 7 | H-1 |
| `COMPLETED` → `INDETERMINATE` (cita era fuzzy, no literal) | 1 | H-2 |
| sin cambio (`COMPLETED` con cita literal / `INDETERMINATE` con cita fabricada) | 6 | — |

Resultado neto: la señal útil de qwen sube de **36 % → 79 %**; la de mistral baja
de 36 % → 14 % (el gate correcto destapa que su salida "positiva" se apoyaba en
citas difusas y `PRESENT` sin cita). `fabricated_evidence surviving_gate = 0` se
mantiene. Reproducibilidad: **sin cambio** respecto de la corrida A (el gate es
ortogonal a la estabilidad del modelo).

---

## 7. Artefactos

| Ruta | Contenido | Versionado |
|---|---|---|
| `factory/prototypes/semantic_hybrid_poc/*.py` | código del prototipo + `test_poc.py` (15/15) | **sí** |
| `…/bakeoff_results/bakeoff_summary.json` | resumen consolidado — **corrida B (gate endurecido)** | no (gitignored) |
| `…/bakeoff_results/bakeoff_{qwen,mistral}_*.json` | 14 assessments por modelo, corrida B (crudo + gated) | no (gitignored) |
| `…/bakeoff_results/bakeoff_reproducibility.json`, `…_cache_check.json`, `…_meta.json` | reproducibilidad, cache, pinning/digests | no (gitignored) |
| `…/bakeoff_results/pre_hardening_20260901/` | **corrida A** completa (gate previo) para comparación | no (gitignored) |
| `…/bakeoff_results/recall_probe_summary.json` | prueba de red de seguridad de recall (§9) | no (gitignored) |
| `factory/prototypes/semantic_hybrid_poc/stability.py`, `recall_probe.py` | H-4 + prueba dirigida | **sí** |
| `…/poc_log.jsonl`, `…/poc_log_pre_hardening.jsonl` | log propio del prototipo (NO es el audit trail real) | no (gitignored) |

Los resultados crudos citan texto del store canónico (texto de cliente) → quedan
fuera del repo público. El código y este informe no contienen citas verbatim.

---

## 8. H-4 — gate de estabilidad (incorporado)

`stability.py`: `warmup(model)` (inferencia trivial descartada, saca al modelo del
arranque en frío) + `assess_stable(finding, model, n=2)` — corre `assess` n veces;
si `assessment_status` o algún `verdict` por elemento discrepa entre corridas →
degrada a `INDETERMINATE` con `stability_flag=True` y conserva el crudo
(`assessment_status_raw`). **Nunca "elige" una corrida.** Tests: 3 nuevos en
`test_poc.py` (18/18). No corrige la deriva del modelo — la **contiene** en
dirección fail-safe.

---

## 9. La capa como RED DE SEGURIDAD DE RECALL — prueba dirigida (REFUTADA)

**Hipótesis:** para los findings donde el motor determinista marca GAP porque no
ancló evidencia que SÍ está en el documento (recall de juicio **2/7**), ¿un LLM
local pinneado + gate R5 recupera la cita literal?

**Instrumento:** el mismo fixture set del roadmap —
`docs_plan/W5V2_RECALL_FIXTURE_SET_DRAFT.md`, **7 positivos + 2 negativos**
(verif. 2026-08-08). Retrieval por **código**, overlap de términos a nivel de
**documento** (R9; el `pagina` del canonical store de este corpus es grueso),
top-40 claims. qwen, gate endurecido, H-4 con n=2. `recall_probe.py`.

| | Resultado |
|---|---|
| **Positivos recuperados** | **1 / 7** (solo P2, `21_CFR_11.10(g)`, con cita literal verificada: *"…protected through the FactoryTalk Security software"*) |
| vs. baseline pipeline de juicio | **2 / 7** — la capa recupera **menos** |
| Positivos perdidos | P1, P3, P4, P5, P6, P7 |
| **Negativos manejados OK** | **2 / 2** (N1 → `CONFIRMS_ABSENCE`; N2 → `INDETERMINATE`, **no** citó la línea del índice, **no** afirmó soporte falso) |
| Citas fabricadas (pre-gate) | 20 → **0 sobreviven** al gate R5 |
| Marcados inestables por H-4 | 2 (P6, N2) — ambos `status` oscilante → `INDETERMINATE` |

**Lectura:** la capa **NO** funciona como red de seguridad de recall. El modo de
fallo es consistente: qwen **parafrasea cuando se le pide citar literal**, el gate
R5 rechaza la paráfrasis (correcto) y el resultado degrada a `INDETERMINATE`. El
gate hace su trabajo (0 fabricaciones sobreviven, 2/2 negativos correctos), pero
"seguro" aquí significa "produce nada útil de forma segura" en 6 de 7 positivos.

Esto **confirma con el instrumento del propio roadmap** la lectura previa: la capa
semántica es un **filtro anti-fabricación / decision-support**, no un arreglo de
recall. La causa raíz (el modelo no copia substrings literales) es la misma que
está detrás del 2/7 de juicio. **R1.5 (productización H2+H4) y R2 siguen siendo
las únicas palancas de recall.**

Matices de justicia: retrieval por keyword simple (no el RRF BM25+embeddings del
`judgment_candidate_pool` real), n=2, una sola versión de prompt. Un retriever
mejor + un prompt que fuerce "copia exacta" podrían subir el número — pero no
convierten esto en una solución de recall.

---

## 10. Checkpoint — CERRADO por Capa 9 (2026-09-01)

**Decisión de Cesar (Capa 9), autorización "continuar ejecución" 2026-09-01:**

> Cierre del track híbrido en **FASE 2 = PASS / PARKED**. **No** iniciar FASE 3 ni
> integración del híbrido por ahora. Conservar prototipo, evidencia y resultados.
> **Priorizar R1.5 / R2** como trabajo activo para mejorar recall.

**Estado final FASE 2:**
- PASS en seguridad + decision-support: `format`=JSON Schema 1.00, 0 citas
  fabricadas sobreviven al gate R5 (2 corridas + repeticiones + §9), cache R7 OK,
  H-1..H-4 incorporados y medidos, `test_poc.py` 18/18.
- **NEGATIVO en recall** (§9): 1/7 < 2/7 baseline → la capa no arregla recall;
  es filtro anti-fabricación / decision-support.
- Modelo, si se retoma: `qwen2.5:7b-instruct-q4_K_M`. H-5/H-6 quedan sin evaluar.
- **PARKED**: no se toca más código del prototipo sin nueva decisión de Capa 9.

Commits `647b710` + `9d6c86f` pusheados. Prototipo aislado, sin artefacto
gobernado → sin panel de gobernanza (sólo se crearía en FASE 4, que no se hará).
