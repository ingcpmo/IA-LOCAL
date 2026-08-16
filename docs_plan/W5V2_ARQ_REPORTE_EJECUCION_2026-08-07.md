# W5 V2 ARQ — Reporte de ejecución, sesión de continuación 2026-08-07

Reporte generado por Claude Code al cierre de la sesión. Cubre desde el
punto de retomar "recalificación del modelo" hasta el cierre del roadmap de
infraestructura (calificación + calibración + runner del corpus). No cubre
las fases A-P (roadmap regulatorio, cerradas el 2026-07-23) ni los bloques
1-6 de gobernanza de la sesión ARQ previa del mismo día (G1-G8, D4-A,
CORPUS_AUTHORIZATION) — ver `project_w5_v2_regulatory_redesign.md` para esa
historia completa.

Estado de entrada a esta sesión de continuación: modelo en
`QUALIFIED_FOR_VALIDATION_ONLY` (commit `57c9f79`), suite sin verificar tras
el cierre anterior, mecanismo de medición de rendimiento real declarado
`NOT_IMPLEMENTED_YET`, runner del corpus declarado `NOT_IMPLEMENTED_YET`.

---

## 1. Verificación de la suite heredada

**Incidente real, sin impacto en código**: el primer intento de correr la
suite completa (`timeout 590 pytest ... | tail -40`) se cortó en silencio —
`timeout` mató el pipeline antes de que `tail` bufferizara ninguna línea,
dejando un log vacío ("Terminated"). Reintentado con `nohup ... &` + espera
por PID: **2213 passed, 4 skipped, 1 xfailed, 3 failed**. Los 3 fallos eran
`test_governance_catalog_version_playwright.py` — el flag
`--ignore=test_governance_catalog_version_playwright.py` no apuntaba a la
ruta completa y pytest lo ignoró en silencio. Reintentado con la ruta
correcta (`--ignore=factory/tests/test_governance_catalog_version_playwright.py`):
**0 fallos reales**.

**Lección operativa registrada**: nunca envolver una corrida larga de
pytest con `timeout N | tail`; usar `nohup ... &` redirigido a archivo y
esperar por el PID (con `Monitor` en este entorno).

---

## 2. Mecanismo de medición real de rendimiento

### 2.1 Decisión

Cesar confirmó explícitamente construir el mecanismo antes de seguir con el
runner (pregunta directa, no una decisión ya tomada de antemano).

### 2.2 Construcción — commit `4586f01`

`factory/regulatory/model_requalification_calibration.py` (nuevo):

- Reutiliza `chunked_engine.evaluate_chunked()` — el mismo camino de
  producción real, nunca uno paralelo — contra 2 páginas sintéticas de
  texto regulatorio real (`ACCESS_CRITERIA` del Golden Dataset, mismo
  patrón que el caso 6 `_case_contradiction_between_sections`).
- `DEFAULT_PROVIDER` (Ollama real) envuelto en `_InstrumentedProvider`,
  que captura latencia y tokens (`eval_count`/`prompt_eval_count`) por
  llamada sin modificar `chunked_engine.py` ni `ollama_client.py`.
- Exige `require_inference_authorized(status, call_type=INFERENCE,
  run_context='model_requalification', target=GOLDEN_DATASET_TARGET)`
  ANTES de la primera llamada real — la única excepción que el gate G6
  permite sin `QUALIFIED` pleno.
- `model_qualification_gate.evaluate_model_qualification()` modificado para
  incorporar `latency_p50`/`latency_p95`/`tokens_per_task`/`retry_rate`
  SOLO si el `fingerprint` de una calibración persistida coincide EXACTO
  con el de la evaluación actual (misma doctrina que
  `QUALIFICATION_INVALIDATED`).

### 2.3 Desvío real durante la construcción, corregido

Intento de renombrar `_ACCESS_CRITERIA` → `ACCESS_CRITERIA` (privado a
público) en el Golden Dataset para evitar importar un nombre con guion
bajo. Efecto no anticipado: cambió el AST del archivo y por tanto su
`golden_dataset_sha256` (hash canónico de `artifact_version_guard`),
rompiendo `test_q08_all_five_preconditions_are_closed_today` (precondición
G6 gobernada). Revertido íntegro (el Golden Dataset queda sin diff); en su
lugar, `model_requalification_calibration.py` importa el nombre privado
explícitamente. **Lección registrada**: cualquier rename dentro del Golden
Dataset o de los YAML de prompts gobernados cambia el fingerprint de
calificación — verificar `artifact_version_guard.guard_report()` tras
cualquier edición ahí.

6 tests nuevos (`test_model_requalification_calibration.py`, provider falso
determinista, sin llamadas a Ollama real). Suite completa tras el commit:
**2217 passed, 0 fallos**.

### 2.4 Corrida real — commit `c210330`

Con autorización explícita de Cesar, `run_runtime_calibration(persist=True)`
ejecutada contra `aria-ollama` real (`qwen2.5:7b-instruct-q4_K_M`,
confirmado disponible vía `/api/tags`). Duración real: **~44 minutos** (2
llamadas secuenciales, ~23-32 min cada una).

**Resultado real medido**:

| Métrica | Valor |
|---|---|
| `latency_p50` | 1656,6 s (~27,6 min) |
| `latency_p95` | 1902,0 s (~31,7 min) |
| `tokens_per_task` | 3134,5 |
| `retry_rate` | 0,0 (0 fallos técnicos, ambas respuestas `done_reason=stop`, ninguna truncada) |

Persistido en `factory/regulatory/model_qualification/runtime_calibration_record.json`.

### 2.5 Recalificación resultante

`evaluate_model_qualification(persist=True)` con la calibración incorporada:
**las 13 métricas del spec quedan medidas, 0 fallidas — `status=QUALIFIED`
pleno** (primera vez desde que existe el gate; antes tope en
`QUALIFIED_FOR_VALIDATION_ONLY`). Persistido en `qualification_record.json`.

**Efecto real sobre el gating**: `require_inference_authorized()` ya no
bloquea `run_context='production'`.

Suite completa reverificada tras esto: **2217 passed, 0 fallos**. Ningún
endpoint expone `qualification.status` en vivo hoy — no hizo falta
`docker restart factory-api` para este commit de datos.

---

## 3. Runner real de la corrida del corpus

### 3.1 Decisión

Cesar pidió construirlo directamente ("construye el runner del corpus"),
sin pregunta de alcance previa.

### 3.2 Diagnóstico previo (antes de escribir código)

Se identificaron **dos pipelines reales distintos** en el código, ambos
basados en `generate_controlled()`/contrato `chunk_observation`
(`run_validation_evidence.py`, `verified_pipeline.py`) — explícitamente
documentados como NO wireados a los prompts gobernados vigentes (que usan
el contrato `estado`, no `chunk_observation`). El pipeline real que sí usan
los 4 agentes gobernados (`part11`/`cgmp211`/`annex11`/`alcoa`) es
`chunked_engine.evaluate_chunked()`, con `use_verified_pipeline=True` +
`document_type` para el filtro de aplicabilidad post-hoc (Fase 3). Esta
distinción evitó construir el runner sobre el pipeline equivocado.

### 3.3 Construcción — commit `761a5bd`

`factory/regulatory/corpus_runner.py` (nuevo):

**3 guardias fail-closed, todas antes de la primera llamada real**:

1. `CORPUS_AUTHORIZATION` vigente y con cobertura coherente — todos los
   `document_ids` del lote deben compartir la misma decisión firmada
   (`covering_instances` única).
2. `require_inference_authorized(status, call_type=INFERENCE,
   run_context='production')` — exige `QUALIFIED` pleno (ya cumplido).
3. Hard stops de D4-A (`compute_d4a()`, nunca un número escrito a mano) —
   una unidad (documento, agente) nunca arranca si su costo esperado no
   cabe en el presupuesto restante. El corte real es SIEMPRE entre
   unidades: `evaluate_chunked()` no acepta un tope de llamadas dentro de
   una misma invocación.

**Resume real**: `CheckpointStore` compartido entre unidades (por
SHA-256 + agente + `run_fingerprint`, mecanismo ya existente de
`chunked_engine.py`).

**Verificación de rutas reales**: cada documento se resuelve contra
`source_baseline_allowlist.yaml` y su SHA-256 se recalcula en el momento
contra el archivo real en disco (nunca se confía en el hash del YAML sin
recomprobar) — `CorpusDocumentDriftError` si no coincide.

### 3.4 Bug real encontrado y corregido durante la construcción

Primer diseño de "llamadas nuevas por invocación": usaba
`preflight_metadata['resumed_chunk_count']` (cuántos chunks YA estaban
checkpointeados al empezar) como equivalente a "cuántos se reusaron sin
ninguna llamada nueva". Es incorrecto: un chunk con
`retry_technical_failures=True` puede figurar en ese conteo Y de todas
formas recibir una llamada real nueva (el reintento dirigido). Detectado
con un test que simula 1 fallo técnico de 2 chunks: la segunda invocación
reportaba `calls_made_this_invocation=0` cuando debía ser 1. Corregido
restando `retried_chunk_indices` (ya expuesto en preflight desde Fase F) de
`resumed_chunk_count`.

### 3.5 Verificación real fuerte

`plan_corpus_units()` corrido contra el allowlist real y los 5 PDF reales
de Rockwell reproduce **exactamente `max_calls=232`** — coincide 1:1 con
`D4-2026-003` ya firmado:

| documento | tipo | agente | llamadas esperadas |
|---|---|---|---|
| RW-0005 | FS | fda_part11_agent, eu_annex11_agent, alcoa_plus_agent, fda_cgmp_211_agent | 27 × 4 = 108 |
| RW-0006 | URS | (los mismos 4 agentes) | 9 × 4 = 36 |
| RW-0011 | DS | (los mismos 4 agentes) | 7 × 4 = 28 |
| RW-0012 | DS | (los mismos 4 agentes) | 7 × 4 = 28 |
| RW-0014 | DS | (los mismos 4 agentes) | 8 × 4 = 32 |
| **total** | | **20 unidades** | **232** |

Congelado en `test_plan_corpus_units_real_reproduce_d4a_232_llamadas`
(integración real, sin Ollama, sin mocks de rutas).

Nuevo evento de auditoría `corpus_run_batch_completed` agregado al
whitelist fail-closed de `audit_writer.py`. 10 tests nuevos
(`test_corpus_runner.py`). Suite completa tras el commit: **2227 passed,
0 fallos**. `factory-api` reiniciado y verificado por endpoint (200).

---

## 4. Estado de gates y commits al cierre

```
G1 CERRADO   G2 CERRADO   G3 LISTO   G4 LISTO
G5 LISTO     G6 LISTO     G7 CERRADO G8 LISTO
```

Calificación del modelo: **`QUALIFIED`** (pleno, 13/13 métricas medidas, 0
fallidas). `CORPUS_AUTHORIZATION-2026-002`: `AUTHORIZED_AWAITING_RUNNER` →
el runner ya existe. `require_inference_authorized()` ya no bloquea
`run_context='production'`.

Commits de esta sesión de continuación (orden cronológico):

| commit | contenido |
|---|---|
| `4586f01` | mecanismo de calibración real (construcción) |
| `c210330` | corrida real de calibración + recalificación a `QUALIFIED` |
| `761a5bd` | runner real de la corrida del corpus |

Suite completa verificada 4 veces a lo largo de la sesión, siempre en
verde tras cada commit (2217 → 2217 → 2227 passed, 0 fallos reales en
ninguna corrida final).

---

## 5. Lo que NO se hizo (a propósito)

- **La corrida real del corpus no se ejecutó.** El runner está construido
  y probado (con providers falsos, nunca Ollama real), pero
  `run_corpus_batch()` nunca se invocó contra `DEFAULT_PROVIDER`. Costo
  real estimado: 232 llamadas, entre ~34,3 h (estimado) y 71,42 h (hard
  stop de tiempo) de Ollama real corriendo sin interrupción — un
  compromiso muy superior a los ~44 minutos de la calibración, y por eso
  se dejó como decisión aparte, pendiente de autorización explícita de
  Cesar.
- No se decidió todavía CÓMO correrla (una sola invocación en background
  de larga duración, por sesiones sucesivas usando el resume del
  checkpoint, o por lotes explícitos acotando `units` a un subconjunto de
  documentos por invocación).

---

## 6. Punto de retomar

Ver `project_w5_v2_regulatory_redesign.md` (memoria de sesión), sección
"Runner del corpus" → "RETOMAR AQUÍ (vigente)": preguntar a Cesar si
autoriza lanzar `corpus_runner.run_corpus_batch()` y decidir el modo de
ejecución. No queda ninguna pieza de infraestructura pendiente en el
roadmap W5 V2 ARQ — solo la ejecución real, que es cara en tiempo, no en
diseño.
