# Post-mortem — truncamiento silencioso por `num_predict` en `evaluate_chunked()`

**Fecha:** 2026-07-28
**Corrida afectada:** `/home/ing_cpmo/logs/fsv12_reeval_20260727/` (re-evaluación de FS_v1.2 para recuperar trazabilidad de D en FSV12-07 / FSV12-11)
**Estado:** corrida abortada por decisión de Cesar tras 1 h 56 min. Causa raíz identificada y confirmada con evidencia directa.
**Severidad:** ALTA — el modo de fallo sesga sistemáticamente el resultado hacia "sin evidencia".

---

## 1. Qué ocurrió

La corrida se lanzó a las 23:20 UTC del 2026-07-27 sobre el agente `eu_annex11_agent`
(27 chunks). A las 01:16 UTC llevaba 12 chunks ejecutados:

| chunks | resultado |
|---|---|
| 0, 1, 2 | `ok=True` |
| 3 – 11 | `technical_execution_failure` (9 de 12, **100 % desde el chunk 3**) |

El log del motor decía, para los nueve:

> `technical_execution_failure: respuesta del modelo no es JSON valido o no cumple el esquema esperado (tras reparacion acotada)`

Ese mensaje es incorrecto en su implicación: sugiere que el modelo devolvió una
respuesta defectuosa. **No fue eso lo que pasó.**

## 2. Qué falló realmente

El script de diagnóstico `logs/fsv12_reeval_20260727/diag_chunk.py` reprodujo el
chunk 3 exacto (mismo PDF, mismo `build_page_chunks`, mismo `build_prompt`)
capturando la respuesta cruda que el motor descarta. Metadata devuelta por Ollama:

```
done_reason      = "length"     ← la generación se CORTÓ, no terminó
eval_count       = 1024         ← exactamente NUM_PREDICT
prompt_eval_count= 3903
```

La respuesta termina literalmente así, a media estructura:

```json
        },
        {
            "req_id": "ANNEX11_9",
```

Alcanzó a emitir **2 de 5 checkpoints completos** (`ANNEX11_4`, `ANNEX11_7.1`) y
murió al abrir el tercero. El `Expecting ',' delimiter (línea 92 col 10)` que
reporta el parser no es JSON mal formado: es JSON **incompleto**. `_repair_json()`
no puede rescatarlo — solo quita comas colgantes, y aquí falta más de la mitad
del documento.

**Causa raíz:** `factory/engines/gmpai_integrity/ollama_client.py:20` →
`NUM_PREDICT = 1024`, insuficiente para el contrato de salida que el prompt exige
desde la ampliación D de la Fase F (2026-07-25), que añadió `criterion_assessments`
(un objeto de 7 campos por cada criterio mínimo de evidencia).

`NUM_PREDICT` no se ajustó cuando creció el contrato de salida.

## 3. Por qué esto es peor que una corrida fallida

El chunk 0 se ejecutó como control. **Pasó**, y el motivo por el que pasó es el
hallazgo importante:

| | chunk 0 (OK) | chunk 3 (falló) |
|---|---|---|
| `done_reason` | `stop` | `length` |
| `eval_count` | 609 | 1024 (tope) |
| checkpoints emitidos | 5 / 5 | 2,1 / 5 |
| `criterion_assessments` | **0 criterios evaluados** | 8 criterios evaluados |
| `estado` de los 5 | todos `evidencia_insuficiente` | contenido real |
| `evidencia_exacta` | todos `""` | citas reales |

El chunk 0 cupo en el presupuesto **porque no encontró nada**: cinco checkpoints
vacíos, sin una sola cita, sin un solo criterio evaluado, 609 tokens. El chunk 3
se pasó del presupuesto **porque sí encontró contenido**: citas textuales,
justificaciones, ocho criterios evaluados.

De ahí la conclusión que gobierna todo lo demás:

> **El presupuesto de salida solo alcanza cuando el modelo no hace trabajo real.
> Todo chunk que se involucra con el contenido del documento se trunca y se
> descarta; todo chunk que no encuentra nada pasa la validación.**

Para una herramienta de cumplimiento esto es el peor modo de fallo posible: no
produce ruido aleatorio, produce un **sesgo sistemático hacia "no hay evidencia"**.
El patrón de la corrida lo confirma — los chunks 0-2 son portada, índice e
introducción; el contenido técnico empieza en la página 7, que es exactamente
donde empieza el chunk 3 y donde empiezan los fallos.

### 3.1 Qué habría pasado si se dejaba terminar

La gobernanza fail-closed **sí funcionó**: `chunked_engine.py:829-848` marca la
consolidación como `PROVISIONAL (technical_execution_failure_pending)` cuando hay
fallos técnicos sin resolver, y `verified_pipeline_adapter.rejected_record()`
registra cada (chunk, requisito) no respondido. No se habría emitido un veredicto
falso presentado como definitivo.

Pero el resultado igual habría sido inservible, y además caro: los chunks con
`technical_execution_failure` **no se reintentan al reanudar** (quedan ya
registrados en `chunk_executions`, y `start_index` los salta). Las ~7 h de CPU
restantes se habrían gastado para llegar a un dossier PROVISIONAL con la mayoría
del documento en blanco.

### 3.2 El agente ALCOA habría sido peor

La corrida tenía un segundo agente pendiente. Comparación de contratos de salida:

| agente | checkpoints | criterios totales |
|---|---|---|
| `eu_annex11_agent` | 5 | 20 |
| `alcoa_plus_agent` | 9 | **25** |

`alcoa_plus_agent` exige aproximadamente el doble de salida que Annex 11 con el
mismo `NUM_PREDICT = 1024`. Habría fallado en prácticamente todos los chunks con
contenido.

## 4. Defectos de ingeniería identificados

Cuatro defectos reales, independientes de la configuración:

**D-1 — El motor tenía la señal del truncamiento y la tiró.**
`done_reason: "length"` viene en la misma respuesta de Ollama que el motor ya
parsea. `chunked_engine.py:640-647` lo colapsa en un mensaje genérico que
conflaciona tres fallos distintos e incompatibles entre sí: (a) no hay ningún
`{...}` en la respuesta, (b) hay JSON pero no parsea, (c) parsea pero viola
`checkpoint_llm_response_v1`. Un truncamiento por presupuesto de tokens es un
**error de configuración del operador**, no un fallo del modelo, y es trivialmente
distinguible. Nueve chunks se marcaron sin que el log dijera lo que el motor ya
sabía. Esto es lo que hizo falta un script de diagnóstico dedicado para algo que
debió leerse del log.

**D-2 — La respuesta cruda se descarta.**
`_extract_json()` (`chunked_engine.py:170-189`) devuelve `None` en los tres casos
y no conserva el `raw`. Sin él no hay forma de diagnosticar post-hoc, ni de
auditar qué dijo realmente el modelo en un run regulatorio. Nótese que
`generate_controlled()` (`ollama_client.py:210`) **sí** devuelve `raw_response` —
pero esa función no está cableada a `evaluate_chunked()`.

**D-3 — Fail-closed a nivel de chunk entero desperdicia trabajo válido.**
`_validate_checkpoint_schema()` (`chunked_engine.py:216-220`) invalida los 5
checkpoints si uno solo falla. En el chunk 3, `ANNEX11_4` y `ANNEX11_7.1` estaban
**completos y bien formados** — 10 minutos de CPU de análisis real — y se
descartaron enteros. El criterio fail-closed es correcto como doctrina; lo que no
es correcto es aplicarlo sin registrar lo que se descartó.

**D-4 — `NUM_PREDICT` está hardcodeado.**
`NUM_CTX` es ajustable por entorno (`FACTORY_OLLAMA_NUM_CTX`), `NUM_PREDICT` no.
No se puede corregir la corrida sin tocar código y, por tanto, sin rebuild.

**D-5 (latente, NO se disparó aquí) — La rama `no_cumple` no propaga
`technical_execution_failure_pending`.**
En `chunked_engine.py:800-815`, cuando no hay candidatos pero sí hay
`not_observed`, el motor emite un Finding `estado="no_cumple"`, `severidad="mayor"`
**sin** el flag `technical_execution_failure_pending`, a diferencia de la rama
`else` inmediatamente siguiente, que sí lo marca. Un documento donde unos chunks
devuelven `no_cumple` sin cita y otros fallan técnicamente produciría un
incumplimiento mayor presentado como definitivo, con la mitad del documento sin
evaluar. En esta corrida no se disparó (los chunks 0-2 dieron
`evidencia_insuficiente`, que no entra en `by_req`, así que cayó en la rama
PROVISIONAL correcta). Es un hueco real, no un hallazgo teórico.

## 5. Impacto sobre la trazabilidad de FSV12-07 / FSV12-11

Ninguno recuperado. El objetivo de la corrida —que D (A∧B∧C∧D) se evaluara sobre
`ANNEX11_7.1` y `ALCOA_ATTRIBUTABLE`— **no se cumplió**. El único chunk que evaluó
`ANNEX11_7.1` con criterios reales es el chunk 3, y su resultado se descartó.

`FORMAL_RELEASE_GATE` sigue BLOCKED. La deuda de trazabilidad de FSV12-07/FSV12-11
sigue abierta.

## 6. Evidencia

Todo bajo `/home/ing_cpmo/logs/fsv12_reeval_20260727/`:

```
diag_chunk.py                       script de diagnóstico (separa los 3 fallos)
diagnostico/chunk3_raw.txt          respuesta cruda truncada (5181 chars)
diagnostico/chunk3_ollama_meta.json done_reason=length, eval_count=1024
diagnostico/chunk3_diagnostico.json etapa exacta del fallo
diagnostico/chunk0_*                control: done_reason=stop, eval_count=609
checkpoints/chunked-005909c83aee.checkpoint.json   los 12 chunks ejecutados
```

El checkpoint de la corrida abortada se conserva intacto. **No debe reanudarse**:
sus 9 chunks fallidos no se reintentarían.

## 7. Solución

Ver `factory/designs/num_predict_budget/DESIGN.md`.
