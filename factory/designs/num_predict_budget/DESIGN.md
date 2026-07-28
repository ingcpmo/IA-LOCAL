# Diseño — presupuesto de tokens de salida gobernado en `evaluate_chunked()`

**Fecha:** 2026-07-28
**Motiva:** `factory/docs/W5v2_POSTMORTEM_TRUNCAMIENTO_NUM_PREDICT.md`
**Estado:** PROPUESTO — requiere aprobación de Cesar antes de implementar
**Alcance:** `factory/engines/gmpai_integrity/{ollama_client,chunked_engine}.py`
**Fuera de alcance:** los YAML de prompts y `checkpoint_llm_response_v1.json` NO
se tocan (artefactos gobernados: exigen bump de versión + aprobación humana).

---

## 1. Problema en una frase

El presupuesto de tokens de salida (`NUM_PREDICT = 1024`) solo alcanza cuando el
modelo no encuentra evidencia; todo chunk que analiza contenido real se trunca a
media respuesta y se descarta entero, produciendo un sesgo sistemático hacia
"sin evidencia" que el log presenta como un fallo genérico del modelo.

## 2. Principio de diseño

> El presupuesto de salida no es una constante mágica: es una **función del
> contrato de salida**, que a su vez se deriva del catálogo de requisitos. Si el
> catálogo crece, el presupuesto debe crecer solo — y si no cabe en el contexto,
> la corrida debe fallar **antes** de gastar la primera llamada, no 10 minutos
> después y por chunk.

Esto es lo que evita que el defecto se repita: hoy `NUM_PREDICT` quedó atrás
porque la ampliación D de la Fase F añadió `criterion_assessments` y nadie
recalculó una constante que vivía en otro archivo.

## 3. Mediciones reales (base del dimensionamiento)

Todas medidas en vivo el 2026-07-28 contra `qwen2.5:7b-instruct-q4_K_M`, Ollama
0.21.2, host CPU (sin GPU):

| magnitud | valor medido |
|---|---|
| velocidad de generación | **3,33 tok/s** (1024 tok en 307,1 s) |
| velocidad de prompt eval | **15,9 tok/s** (3903 tok en 245,4 s) |
| ratio caracteres/token | 3,95 (prompt) / 5,06 (salida JSON) |
| chunks del documento | 27 (máx. 6430 chars) |
| prompt Annex 11 (chunk máximo) | 15 347 chars ≈ **3885 tok** |
| prompt ALCOA+ (chunk máximo) | 15 875 chars ≈ **4019 tok** |
| salida real medida | 8 criterios + 2 envelopes ≈ 1000 tok → **~110 tok/criterio** |

Contrato de salida por agente:

| agente | checkpoints | criterios | salida estimada |
|---|---|---|---|
| `eu_annex11_agent` | 5 | 20 | ~2400 tok |
| `alcoa_plus_agent` | 9 | 25 | ~3000 tok |

## 4. Decisiones

### D1 — `num_predict` derivado del catálogo, por agente (no constante global)

Nueva función en `ollama_client.py`:

```python
TOKENS_PER_CRITERION = 130      # 110 medido + 18 % de margen
TOKENS_PER_CHECKPOINT = 60      # envelope: estado/evidencia/brecha/recomendacion
TOKENS_JSON_OVERHEAD = 120

def output_token_budget(n_checkpoints: int, n_criteria: int) -> int:
    """Presupuesto de salida derivado del contrato REAL del prompt.
    Redondeado a múltiplo de 512 hacia arriba."""
```

Resultado (verificado ejecutando la función, no estimado a mano):
Annex 11 → 120 + 5×60 + 20×130 = 3020 → **3072**;
ALCOA+ → 120 + 9×60 + 25×130 = 3910 → **4096**.

`chunked_engine.evaluate_chunked()` lo calcula una vez, del `meta` ya cargado y
del catálogo (`_lookup_evidence_min_criteria`, que ya usa para construir el
prompt), y lo pasa al provider. **Ningún número se escribe a mano.**

`NUM_PREDICT = 1024` se conserva solo como fallback para llamadas que no declaran
contrato, y pasa a ser ajustable por entorno (`FACTORY_OLLAMA_NUM_PREDICT`),
cerrando D-4 — hoy `NUM_CTX` es ajustable y `NUM_PREDICT` no, asimetría sin razón.

### D2 — `num_ctx` a 16384, con guardia de preflight que falla temprano

Con los presupuestos de D1:

La guardia estima el prompt a **3,6 chars/token** —deliberadamente por debajo del
3,95 medido, porque sobreestimar el prompt hace la guardia más estricta, que es el
lado seguro— y la aplica al **peor chunk** del documento, no al promedio.
Ejecutada contra `FS_v1.2.pdf` real:

| agente | prompt est. (peor chunk) | + salida | total | ¿cabe en 8192? |
|---|---|---|---|---|
| Annex 11 | 4264 | 3072 | 7336 | sí, 856 tok de margen |
| ALCOA+ | 4410 | 4096 | **8506** | **NO** (verificado: lanza `TokenBudgetError`) |

`num_ctx = 8192` es insuficiente para ALCOA+. Se sube a **16384**, que deja 7878
tokens de margen en el peor caso.

Esto no basta por sí solo: hace falta la guardia. Si `prompt + num_predict >
num_ctx`, Ollama **trunca el prompt** para que quepa — y lo que se pierde es el
principio del prompt, donde viven `common_contract` y la lista de `req_id`. Ese
fallo sería **silencioso**: el modelo respondería algo bien formado sobre un
contrato mutilado. Es estrictamente peor que el defecto actual, que al menos hace
ruido.

Por eso, en el preflight de `evaluate_chunked()` —donde ya se captura la metadata
de reproducibilidad, antes de la primera inferencia—:

```python
worst_prompt_tokens = max(estimación sobre TODOS los chunks)
if worst_prompt_tokens + num_predict > num_ctx:
    raise TokenBudgetError(...)   # antes de gastar una sola llamada
```

Falla explícito, con los tres números en el mensaje, y con el chunk culpable
identificado.

### D3 — Distinguir el truncamiento y conservar el raw (cierra D-1 y D-2)

`_extract_json()` pasa a devolver `(parsed | None, reason)` donde `reason` es una
de cuatro causas explícitas, no un mensaje único:

| causa | significado | de quién es el problema |
|---|---|---|
| `output_truncated` | `done_reason == "length"` | **configuración del operador** |
| `no_json_object` | no hay `{...}` en la respuesta | modelo |
| `json_parse_failed` | hay `{...}` pero no parsea | modelo |
| `schema_validation_failed` | parsea pero viola el schema | modelo/contrato |

`output_truncated` se decide con `done_reason`, que ya viene en la respuesta de
Ollama que el motor parsea — no requiere heurística ninguna.

Además, el `raw` se persiste siempre en el `chunk_execution` (truncado a un tope
razonable, p. ej. 8 KB, para no inflar el checkpoint). Sin raw no hay diagnóstico
post-hoc ni auditoría de lo que el modelo realmente dijo en un run regulatorio;
hoy hizo falta un script dedicado y ~20 min de CPU para recuperar algo que el
motor tuvo en la mano y tiró.

Nota: `generate_controlled()` ya devuelve `raw_response`. Esto alinea el camino
de `evaluate_chunked()` con ese contrato, sin cablear `generate_controlled()`
(que sigue BLOCKED para producción y exige la reescritura del consolidador).

### D4 — Reintento dirigido de chunks con fallo técnico al reanudar (cierra 3.1)

Hoy un chunk con `technical_execution_failure` queda en `chunk_executions` y
`start_index` lo salta para siempre: un error de configuración se convierte en
pérdida de datos permanente, y la única salida es descartar la corrida entera.

Se añade parámetro explícito `retry_technical_failures: bool = False` (default
`False` = cero cambio de comportamiento para todo llamador existente). Con `True`,
al reanudar se reejecutan **solo** los chunks marcados, se reemplaza su entrada en
`chunk_executions` y se purgan sus `verified_records_by_req` correspondientes por
`record_id` (`vrec-{task_id}-{req_id}`) para no duplicar registros.

Requisito de gobernanza: el reintento **cambia el fingerprint efectivo** de la
corrida. El `chunk_execution` reemplazado debe conservar el intento anterior en
`superseded_attempts[]` — nunca se borra evidencia de que hubo un fallo; se
registra que se resolvió. Un run con reintentos queda marcado en
`preflight_metadata` para que el dossier lo declare.

### D5 — Propagar `technical_execution_failure_pending` a la rama `no_cumple`

`chunked_engine.py:800-815` emite un Finding `no_cumple` / `severidad="mayor"` sin
el flag, mientras la rama `else` contigua sí lo marca. Se añade el mismo
tratamiento (flag + prefijo `PROVISIONAL` en `brecha` + recomendación de
reintentar) a la rama `not_observed`.

Es un hueco latente que no se disparó en esta corrida, pero un incumplimiento
mayor presentado como definitivo con la mitad del documento sin evaluar es
exactamente el tipo de salida que el fail-closed de la Fase F existe para impedir.

## 5. Opciones evaluadas y descartadas

**Recortar `criterion_text` del contrato de salida.** El eco literal del criterio
es el 18 % de la salida (955 de 5181 chars medidos) y el motor ya conoce el texto
por `criterion_index`. **Descartada:** `semantic_evidence_verification.py:200-215`
lo usa como control anti-alucinación, exigiendo coincidencia EXACTA contra el
criterio real del catálogo en esa posición. Quitarlo ahorra ~18 % de tokens a
cambio de eliminar una verificación real. Mal negocio, y además tocaría un schema
gobernado.

**Una llamada por requisito en vez de una por chunk.** Reduciría la salida por
llamada por debajo de 1024. **Descartada:** el texto del documento se re-evaluaría
en cada llamada. Annex 11 pasaría de 3885 a ~5×2200 = 11 000 tokens de prompt por
chunk; a 15,9 tok/s eso son 690 s solo de prompt eval frente a 244 s actuales. La
salida total no baja. Es más lento y más caro.

**Subir `NUM_PREDICT` a un número redondo grande (p. ej. 8192) y olvidarse.**
**Descartada:** no cabe en contexto junto al prompt sin subir `num_ctx` mucho más,
y sobre todo no resuelve la causa estructural — vuelve a ser una constante que
quedará atrás la próxima vez que crezca el catálogo.

## 6. Costo — esto no es gratis y hay que decidirlo

Con los presupuestos de D1, a las velocidades medidas, **en el peor caso** (el
modelo agota el presupuesto en todos los chunks):

| agente | prompt eval | generación | por chunk | × 27 chunks |
|---|---|---|---|---|
| Annex 11 | 244 s | 922 s (3072 tok) | ~19 min | **8,8 h** |
| ALCOA+ | 253 s | 1230 s (4096 tok) | ~25 min | **11,1 h** |
| | | | | **≈ 20 h** |

Es el techo, no la media: los chunks sin contenido generan mucho menos (el chunk 0
generó 609 tokens, no 3584) y terminan por `stop`. Una estimación realista, con
~40 % de chunks de bajo contenido, es **12–15 h** para los dos agentes.

Aun así es un salto grande frente a las ~10 min/chunk de la corrida abortada.
`num_ctx = 16384` añade además presión de memoria y algo de lentitud de atención
en CPU. **Esta es la decisión que necesita el visto bueno de Cesar**, porque
cambia el costo de toda corrida futura del motor, no solo de esta re-evaluación.

Si el costo no es aceptable, la palanca honesta es reducir el número de agentes o
de checkpoints por corrida — no recortar el presupuesto, que es exactamente cómo
se llegó a este defecto.

## 7. Plan de verificación

1. **Test unitario de `output_token_budget()`** — casos Annex 11 (5/20) y ALCOA+
   (9/25) contra los valores esperados; monotonicidad frente al nº de criterios.
2. **Test de la guardia de preflight** — un `num_ctx` deliberadamente pequeño debe
   lanzar `TokenBudgetError` **sin ninguna llamada al provider** (verificable con
   un `ModelProvider` falso que cuente invocaciones; debe quedar en 0).
3. **Test de clasificación de causas** — provider falso que devuelve
   `done_reason="length"` → `output_truncated`; JSON basura → `json_parse_failed`;
   JSON válido fuera de schema → `schema_validation_failed`. Hoy los tres caen en
   el mismo mensaje.
4. **Test de reintento dirigido** — checkpoint sembrado con un chunk fallido;
   reanudar con `retry_technical_failures=True` debe reejecutar exactamente ese
   chunk, dejar `superseded_attempts` poblado y no duplicar `verified_records`.
5. **Test de regresión de D5** — Finding `no_cumple` con fallos técnicos presentes
   debe traer `technical_execution_failure_pending=True`.
6. **Validación real, un solo chunk primero** — reejecutar el chunk 3 con el
   presupuesto nuevo y confirmar `done_reason == "stop"` y 5 checkpoints válidos
   **antes** de lanzar las ~12 h de corrida completa. Este paso es obligatorio:
   la corrida abortada demuestra el costo de no hacerlo.
7. Suite completa (1313) + Gate 0 + Golden Dataset 14/14 sin regresión.

## 8. Secuencia de implementación

| # | paso | depende de |
|---|---|---|
| 1 | `output_token_budget()` + `FACTORY_OLLAMA_NUM_PREDICT` (D1, D-4) | — |
| 2 | Guardia de preflight + `num_ctx` 16384 (D2) | 1 |
| 3 | Causas explícitas + persistencia del raw (D3) | — |
| 4 | Propagación en rama `no_cumple` (D5) | — |
| 5 | Reintento dirigido al reanudar (D4) | 3 |
| 6 | Validación de un chunk real (§7.6) | 1,2,3 |
| 7 | Corrida completa FS_v1.2, dos agentes | 6 |

Los pasos 1-5 son cambio de código Python en el motor → no requieren rebuild de
`gmp-api` (el motor vive en `factory/`, fuera del contenedor), pero sí suite +
Gate 0 antes de commit.

## 9. Qué necesito aprobado antes de implementar

1. **El costo de §6** (12–15 h realistas, techo 22 h, por corrida de dos agentes).
2. **`num_ctx = 16384`** en el host compartido — conviene confirmar que no
   compite con `aria-ollama` ni con el resto de servicios en memoria.
3. **D4 (reintento dirigido)**: si prefieres no añadirlo ahora, la alternativa es
   descartar y relanzar limpio cada vez que haya un fallo técnico. Es más simple y
   más caro; con la guardia de preflight de D2 los fallos técnicos deberían pasar
   a ser raros, así que es una postura defendible.
4. Confirmar que la corrida abortada (`fsv12_reeval_20260727`) se **descarta**
   entera y no se reanuda. Su checkpoint se conserva como evidencia del defecto.

## 10. Desviaciones reales durante la implementación (2026-07-28)

Tres cosas no salieron como el diseño las planteaba. Se documentan aquí en
vez de reescribir el diseño para que parezca que siempre fue así.

**10.1 — Los presupuestos eran 3584/4608 en el diseño; son 3072/4096.**
Los primeros números no salían de las constantes declaradas en §4/D1. Al
ejecutar la función real: Annex 11 = 120 + 5×60 + 20×130 = 3020 → 3072;
ALCOA+ = 120 + 9×60 + 25×130 = 3910 → 4096. Corregidos §4 y §6 con los
valores reales. La conclusión no cambia: ALCOA+ sigue sin caber en 8192
(verificado ejecutando la guardia, que lanza `TokenBudgetError`).

**10.2 — `context_window` NO entró en el Protocol `ModelProvider`.**
El diseño asumía declararlo como miembro. Al hacerlo, `test_model_provider.
py::test_fake_provider_is_instance_of_protocol` falló: `ModelProvider` es
`runtime_checkable`, así que añadir un miembro hace que toda implementación
existente deje de satisfacer `isinstance()`. Romper providers válidos por un
dato que la mayoría no puede conocer es un precio que el diseño no había
considerado.

Resuelto como extensión **opcional**, leída con `getattr`. Consecuencia de
diseño más importante: un provider que no declara ventana **no se somete a la
guardia** en vez de someterse a una supuesta. Suponer 8192 bloqueó 8 casos
del Golden Dataset —corridas legítimas— por un número inventado. No se puede
verificar un límite que no se conoce; se declara
(`token_budget.context_window_declared`) y se sigue. La guardia queda
plenamente activa donde importa, porque `OllamaProvider` sí declara la suya
(test explícito para que eso no se pierda).

**10.3 — El reintento dirigido no funcionaba para runs COMPLETADOS.**
`CheckpointStore.find_resumable()` filtra por `not completed`, así que el
reintento solo habría servido para runs interrumpidos. Pero desde que existe
la marca `technical_execution_failure_pending`, el caso normal es un run que
**termina** con fallos técnicos — exactamente el que había que poder reabrir.
Se añadió `include_completed_with_failures` (default `False`), que solo
reabre un run completado **si tiene fallos técnicos**. Un run limpio no se
re-analiza nunca, ni pidiéndolo (test explícito).

## 11. Estado de implementación

| # | paso | estado |
|---|---|---|
| 1 | `output_token_budget()` + `FACTORY_OLLAMA_NUM_PREDICT` | hecho |
| 2 | Guardia de preflight + `num_ctx` 16384 | hecho |
| 3 | Causas explícitas + persistencia del raw | hecho |
| 4 | Propagación en rama `no_cumple` (D-5) | hecho |
| 5 | Reintento dirigido al reanudar | hecho |
| 6 | Validación de un chunk real | en curso |
| 7 | Corrida completa FS_v1.2 | pendiente de §9 |

Verificación: **48 tests nuevos** (`test_output_token_budget.py`,
`test_retry_technical_failures.py`), suite completa **1361 passed / 1
skipped** (antes 1313), Gate 0 **PASS=5 FAIL=0**, Golden Dataset 14/14.
Sin commit todavía.
