# W5 Ciclo 1 (v2) — Fase 0: Inventario y confirmación del sistema objetivo

Fecha: 2026-07-17. Solo lectura, sin modificaciones de código.

## 1. Sistema objetivo confirmado

**El motor real es `factory/engines/gmpai_integrity/`** (chunked_engine.py,
ollama_client.py, models.py, prompts/), git-trackeado, ejecutado dentro del
contenedor **`factory-api`** (host `9000` → contenedor `8000`), NO en 8101 ni
8102.

- `8101` = `lab_qc_project_api` — solución custom distinta, sin relación con
  FS_v1.2/C1-C4.
- `8102` = `oos_hplc_investigator_api` — solución custom distinta, sin
  relación con FS_v1.2/C1-C4.
- `aria-ollama` (11434) es el servidor Ollama compartido real usado por el
  motor vía `FACTORY_OLLAMA_BASE_URL` (no `localhost:11434` en producción —
  ese es solo el default del código para ejecución fuera de contenedor).

Los identificadores C1-C4 (contradicciones internas resueltas por Cesar,
`decision_id ff640643`) aparecen en `fs_v1_2_status.json`,
`changelog_FS_v1_2_v3.json`, `technical_error_log_FS_v1_2.json` y los
`agent_reports/*.json` de cada run en
`GMPAI/reports/gmpai_document_validation/<run_id>/` — todos producidos por
este motor sobre `215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf`.

## 2. Llamadas a Ollama (ruta + función + línea)

`factory/engines/gmpai_integrity/ollama_client.py`:
- `generate()` (línea 23): `POST {OLLAMA_BASE_URL}/api/generate`,
  `format: "json"` (string simple, **NO** JSON Schema completo — discrepancia
  vs plan, ver §6), `temperature=0.0`, `num_ctx=8192`, `num_predict=1024`.
- `show_digest()` (línea 48): `GET {OLLAMA_BASE_URL}/api/tags` (ya corregido
  post-mortem Autoclave URS: `/api/show` dejó de traer `digest` en Ollama
  ≥0.21).
- `ollama_version()` (línea 77): `GET {OLLAMA_BASE_URL}/api/version`.

`OLLAMA_BASE_URL` / `OLLAMA_MODEL` vienen de `FACTORY_OLLAMA_BASE_URL` /
`FACTORY_OLLAMA_MODEL` (env vars del contenedor `factory-api`), default
`http://localhost:11434` / `qwen2.5:7b-instruct-q4_K_M`.

## 3. Catálogo REAL de clasificaciones en uso (extraído del código)

`chunked_engine.py:58` y `models.py:11` (idénticos, duplicados
intencionalmente — ver nota):

```python
_VALID_ESTADOS = {"cumple", "cumple_parcialmente", "no_cumple", "evidencia_insuficiente", "no_aplica"}
```

**Discrepancia estructural real con el plan (P3, importante para Fase 2/3)**:
el modelo (LLM) hoy emite directamente `estado` a nivel de CHUNK con los
mismos 5 valores que el finding consolidado a nivel de DOCUMENTO —
`cumple`/`no_cumple`/`cumple_parcialmente` ya son "conclusiones", no meras
observaciones (`observed`/`not_observed_in_chunk` como propone el plan). El
único valor puramente observacional que existe hoy es el flag interno
derivado `has_evidence=False` → tratado como `not_observed_in_chunk` en la
consolidación (`chunked_engine.py:410-422`), pero **no es lo que el LLM
devuelve** — es una interpretación posterior del pipeline sobre la ausencia
de `evidencia_exacta`. El LLM nunca ve ni emite un enum `chunk_observation`
separado de `estado`. Aplicar P3 tal como está escrito en el plan requiere
**cambiar el contrato del prompt y el schema del LLM**, no solo agregar un
schema nuevo al lado del existente.

`no_aplica` está en el enum del motor pero el plan lo prohíbe a nivel LLM
(P5: la aplicabilidad del sistema no la decide el LLM). Es otra discrepancia
a resolver explícitamente en Fase 2/3, no ignorable.

## 4. Estructura real del chunk

`build_page_chunks()` (`chunked_engine.py` ~línea 173) devuelve, por chunk:
```python
{"text": str, "page_start": int, "page_end": int}
```
No hay campo de tipo documental, ni de sección con nombre, ni de confianza de
extracción. `chunk_index` se deriva por posición en la lista al iterar
(`chunks[start_index:]`), no es un campo propio del dict del chunk.

## 5. Origen del tipo documental — RESPUESTA: no existe como concepto

`document_type` (FS/URS/IQ/OQ/PQ/SAT) **no es un campo ni un parámetro en
ningún punto del motor actual**. `evaluate_chunked()` recibe `documento`
(nombre de archivo, string libre) y `sistema` (string libre), pero ningún
componente clasifica ni almacena "esto es un FS" de forma estructurada — esa
distinción vive únicamente en el TEXTO NARRATIVO de los reportes generados
manualmente (ej. `matriz_aplicabilidad_FS_v1_2_v5.json`), construidos fuera
del motor, en los scripts de reporte del piloto B. **No hay campo de
confianza de tipo documental porque no hay campo de tipo documental.**
Esto determina el Bloque 3.4 del plan: cualquier `document_type` que Fase 2/3
introduzca es un campo NUEVO, sin migración de datos existentes que
preservar, y su origen (humano/inferido/fijo) es una decisión de diseño
abierta, no algo que se pueda "leer" del código actual.

## 6. IDs de requisitos regulatorios hoy referenciados

Definidos en YAML de prompts (`factory/engines/gmpai_integrity/prompts/`):
`part11_prompts.yaml` (21_CFR_11.10(a/d/g) et al.), `annex11_prompts.yaml`
(ANNEX11_7.1, ANNEX11_12, etc.), `alcoa_prompts.yaml` (ALCOA_ATTRIBUTABLE,
ALCOA_CONSISTENT, ALCOA_AVAILABLE, etc.), `traceability_prompts.yaml` (piloto
A/URS, agente `requirements_traceability_agent`, no usado en el piloto B de
FS_v1.2). Cada YAML define `checkpoints: [{req_id, label}, ...]`,
`common_contract` (el prompt compartido), `prompt_version`,
`verifier_version`.

## 7. Ubicación de los registros reales de C1–C4

- `factory/docs/gmpai_reanalysis/fs_v1_2/fs_v1_2_status.json` →
  `contradicciones[]`, con `resolucion.tipo` (`falso_positivo` /
  `diferencia_de_alcance`) por cada una de las 4.
- `changelog_FS_v1_2_v3.json` → narrativa de C1/C3 (citas trasladadas).
- `GMPAI/reports/gmpai_document_validation/<run_id>/agent_reports/
  {fda_part11_agent,eu_annex11_agent,alcoa_plus_agent}.json` → `checkpoints[]`
  con `chunk_executions[]` reales por chunk (el dato crudo, previo a
  consolidación) — es la fuente correcta para reconstruir el Golden Dataset
  en Fase 4 sin fabricar nada.
- `factory/layer9/decisions/decisions.jsonl` → registro de la decisión
  humana `ff640643` (Cesar, `conditional_approve`).

## 8. Estado de `jsonschema` en el entorno objetivo

```
$ docker exec factory-api python3 -c "import jsonschema"
ModuleNotFoundError: No module named 'jsonschema'
$ docker exec factory-api pip show jsonschema
WARNING: Package(s) not found: jsonschema
```

**No está instalado.** No aparece en `factory/requirements.txt` (verificado).
`factory-api` tiene volumen hot-reload de `/home/ing_cpmo/factory` →
`/app/factory` (confirmado en sesión previa, `docker inspect`), por lo que
`docker exec factory-api pip install jsonschema` persiste hasta que el
contenedor se recree (no hasta rebuild de imagen) — consistente con el
Bloque 1.1 del plan. **Pendiente de decisión de Cesar** en el Checkpoint A:
instalar ahora vs. diferir a próximo rebuild planificado.

## 9. Discrepancias entre el plan y lo que existe (resumen accionable)

| # | Plan asume | Realidad confirmada | Impacto |
|---|---|---|---|
| 1 | LLM emite `chunk_observation` (observed/partially_observed/not_observed_in_chunk), separado de conclusiones de ausencia | LLM emite `estado` con 5 valores que YA incluyen conclusiones (`cumple`/`no_cumple`/`cumple_parcialmente`/`no_aplica`) | El nuevo schema `finding_llm_v1` (Fase 1) NO es aditivo — requiere reescribir el contrato del prompt YAML para que el modelo deje de decidir cumplimiento y solo observe. Alcance real de P3 es mayor al descrito. |
| 2 | Runtime en 8101/8102 o "gmpai_integrity" sin más precisión | Runtime confirmado: `factory/engines/gmpai_integrity/` dentro de `factory-api` (puerto 9000) | Ninguno — coincide con la hipótesis principal del plan, solo se descartan 8101/8102. |
| 3 | `document_type` con posible campo de confianza | No existe como campo en ningún punto del motor | Bloque 3.4 debe diseñarse desde cero, no "detectar el origen" de algo inexistente. |
| 4 | `format` del `call_ollama_controlled` de ejemplo pasa el JSON Schema completo a Ollama | Motor actual pasa `format: "json"` (string), no un schema | Cambio real de comportamiento en Fase 1 Bloque 1.5, no cosmético — Ollama debe soportar `format` como objeto JSON Schema (Ollama ≥0.5 lo soporta; confirmar versión real del servidor, ver `ollama_version()`). |
| 5 | `jsonschema` disponible o fácil de instalar | No instalado, no en requirements.txt | Requiere Checkpoint A explícito antes de Fase 1 Bloque 1.1 (autorizado por Cesar en el mismo mensaje que este plan — ver Fase 1). |
| 6 | `no_aplica` no mencionado a nivel LLM | Existe en el enum actual del motor, y el plan (P5) lo prohíbe explícitamente a nivel LLM | El nuevo `finding_llm_v1` no debe incluir `no_aplica`; la migración debe decidir qué pasa con datos históricos que ya lo usan (ninguno de los runs de FS_v1.2 lo usó — confirmado, los 19 findings usan solo cumple/cumple_parcialmente/no_cumple/evidencia_insuficiente). |

## 10. Checkpoint A

Cesar autorizó explícitamente, en el mismo mensaje que instruye este
inventario, avanzar a Fase 1 sin pausa adicional — se toma como conformidad
con: (a) sistema objetivo = `factory/engines/gmpai_integrity/` en
`factory-api`, (b) adaptaciones necesarias documentadas arriba (§9,
especialmente #1 y #4, que amplían el alcance real de P3 y del Bloque 1.5
más allá de lo literal del plan), (c) instalación de `jsonschema` ahora
(`pip install` en el contenedor, hot-reload, sin rebuild) — ejecutada en
Fase 1 Bloque 1.1.
