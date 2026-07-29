# MODEL_REQUALIFICATION_AND_D4A_SPEC — §8 del plan

**Estado:** DISEÑO. No recalifica nada. No invoca Ollama. No fija ninguna
cifra de D4-A como definitiva.

---

## 1. Estado real de la calificación vigente

`factory/regulatory/model_qualification/qualification_record.json`,
`evaluated_at: 2026-07-28T13:32:46+00:00`:

```
status            = QUALIFIED_FOR_VALIDATION_ONLY
golden_dataset    = {total: 14, passed: 14, failed: 0}
failed_metrics    = []
unmeasured_metrics= [latency_p50, latency_p95, tokens_per_task, retry_rate]
blocking_reason   = "4 de 13 metricas sin medir …: habilita run_context='validation',
                     NUNCA produccion."
previous_fingerprint = null
```

9 de 13 métricas medidas y en umbral; 4 declaradas `NOT_MEASURED` sin
inventar un número. Es el comportamiento correcto y conviene reconocerlo: el
gate se niega a decir lo que no midió.

### 1.1 Por qué está invalidada — **dos causas independientes**

| # | Campo del fingerprint | Congelado (2026-07-28) | Real (2026-07-29) |
|---|---|---|---|
| 1 | `catalog_sha256` | `6486405abecd729d85e32ec4a9af03cd13ad144162ebcb300ee9d25016202b8d` | `a83c81682309af41615a86f93498a2d31b7b2316a2e30ad56fdcfb3b8a9e55ae` |
| 2 | `prompt_versions` | 4 entradas (`alcoa` 1.1.0, `annex11` 1.1.0, `part11` 1.1.0, `traceability` 1.0.0) | **5** — se añadió `cgmp211_prompts.yaml` 1.0.0 |

`model_qualification_gate.py:144-148` enumera los prompts por **glob**, de
modo que recomputar el fingerprint hoy incluye el quinto y difiere por dos
motivos a la vez.

```
QUALIFICATION_STATUS = QUALIFICATION_INVALIDATED
INVALIDATED_BY = [
  "catalog_sha256: 6486405a… → a83c8168… (alta del requisito 21_CFR_211.68(b),
   2026-07-29)",
  "prompt_versions: +cgmp211_prompts.yaml 1.0.0 (agente fda_cgmp_211_agent,
   2026-07-29)"
]
INVALIDATED_AT = 2026-07-29
```

`previous_fingerprint: null` significa que **no hay calificación anterior a
la que caer**. No es una degradación de `QUALIFIED` a `QUALIFIED_FOR_VALIDATION_ONLY`:
es la ausencia de cualquier calificación válida.

> El gate hizo su trabajo. Fue implementado el 2026-07-28 precisamente porque
> la auditoría maestra encontró que se habían cambiado `num_predict` y
> `num_ctx` y corrido una re-evaluación completa **sin que nada exigiera
> recalificar** (cabecera de `model_qualification_gate.py`, l.1-27). Al día
> siguiente detectó el cambio siguiente. Esto es lo que un control que
> funciona parece.

---

## 2. Precondiciones de recalificación (orden estricto)

La recalificación **solo** es ejecutable después de:

| # | Precondición | Gate | Estado hoy |
|---|---|---|---|
| 1 | Las 4 fuentes en `LOCAL_CANONICAL_COPY_VERIFIED` | G3 | ❌ las 4 en `pending_reverification` |
| 2 | Pack `21_CFR_211.68(b)` aprobado | G4a | ❌ 0 criterios |
| 3 | Matriz v2.1 aprobada | G4b | ❌ `MC-0001` cubre 2.0 |
| 4 | Catálogo versionado con decisión | G4c | ❌ `1.0` con hash cambiado |
| 5 | Golden Dataset aprobado y versionado | G6 | ❌ sin `version_record` ni decisión |

**Todas fallan hoy.** Recalificar ahora produciría un fingerprint que quedaría
invalidado en cuanto se cerrara cualquiera de las cinco.

### 2.1 El orden no es una preferencia

Cada precondición mueve un campo del fingerprint:

```
G3  → no mueve el fingerprint, pero sin ella el Golden Dataset se apoya en
       textos cuya vigencia se desconoce
G4a → mueve catalog_sha256 (criterios nuevos en el pack 211)
G4b → mueve la resolución de aplicabilidad usada por el Golden Dataset
G4c → mueve catalog_version
G6  → mueve golden_dataset_sha256
```

Recalificar antes de que las cinco cierren es garantizar repetirlo. Y como
recalificar exige la primera inferencia autorizada (§4), repetirlo cuesta
tiempo de máquina real.

---

## 3. Golden Dataset

`factory/regulatory/golden_dataset/semantic_verification_golden_dataset.py`,
14 casos, 14/14 en la última evaluación.

Estado de gobernanza: **el dataset existe y funciona; no está aprobado ni
versionado.** No tiene `version_record`, no tiene decisión que lo apruebe, y
su hash no está en el fingerprint de la calificación —solo lo está el
`schema_sha256` del contrato de salida.

> **Hallazgo D-1:** el Golden Dataset es el **patrón de referencia** contra el
> que se mide el modelo, y hoy puede cambiarse sin que nada lo note. Un
> patrón de referencia mutable invalida la medición que se apoya en él. Es el
> mismo defecto que el catálogo, sobre el artefacto que más importa que sea
> estable.

Diseño requerido (G6):

```yaml
artifact: golden_dataset
artifact_id: factory/regulatory/golden_dataset/semantic_verification_golden_dataset.py
version: "1.0"
sha256: <hash canónico de la lista de casos, ordenada por case_id>
approved_by_decision: <decision_instance_id>
```

Y `golden_dataset_sha256` se **añade al fingerprint** de la calificación. Sin
eso, la equivalencia *"mismo fingerprint ⇒ misma calificación válida"* es
falsa: dos calificaciones con el mismo fingerprint podrían haberse medido
contra datasets distintos.

Los 14 casos deben además revisarse antes de aprobarse: ninguno cubre
`21_CFR_211.68(b)` ni el agente `fda_cgmp_211_agent`. Aprobar el dataset tal
cual calificaría un modelo para un requisito que el dataset no ejercita.
**Recomendación:** añadir al menos un caso de Part 211 antes de aprobar —
decisión de Cesar en G6.

---

## 4. Metadata vs. inferencia

Distinción operativa, no retórica:

| | **CONSULTA DE METADATA** | **INFERENCIA** |
|---|---|---|
| Qué es | `GET /api/tags`, `POST /api/show` de Ollama | `POST /api/generate` / `/api/chat` |
| Devuelve | nombre, `digest`, `context window`, familia, cuantización | texto generado por el modelo |
| Coste | milisegundos, sin GPU/CPU de generación | minutos por chunk |
| Determinismo | total | dependiente del modelo |
| **Permitida** | **siempre**, incluido ahora | **no** hasta la recalificación |

`model_digest` y `num_ctx` del fingerprint provienen de metadata. Consultarlos
para **detectar** que el modelo cambió es obligatorio y no viola la pausa: no
genera un solo token.

**La recalificación misma es la primera inferencia autorizada**, y va **contra
el Golden Dataset**, no contra documentos Rockwell. Esa corrida mide las 4
métricas hoy `NOT_MEASURED` (`latency_p50`, `latency_p95`, `tokens_per_task`,
`retry_rate`) — las únicas que exigen generación real.

### 4.1 Guardia

```
if not qualification.status == QUALIFIED and call_type == INFERENCE
   and run_context != "model_requalification":
       → bloqueado, fail-closed
```

`run_context="model_requalification"` es la **única** excepción, solo válida
contra el Golden Dataset, y emite su propio evento de auditoría. Test:
`test_inference_blocked_unless_qualified_or_requalifying`.

---

## 5. D4-A — la fórmula, parametrizada

### 5.1 Prohibición explícita

**PROHIBIDO** usar 34,3 h, 40,0 h ni ninguna otra cifra como definitiva hasta
conocer el número final de criterios del pack. La cifra de
`factory/docs/W5V2_PLAN_CORRIDAS_CORPUS.md` (**147 llamadas · ~34,3 h**) es
un cálculo **correcto para el catálogo de hoy**, en el que
`21_CFR_211.68(b)` tiene **0 criterios** y por tanto **no consume nada**.
Cuando G4a le dé criterios, las tres cosas cambian: número de llamadas,
`num_predict` y tiempo.

El registro `D4_corpus_execution` del 2026-07-29 refleja además el problema
de fondo: se firmó `APPROVE` **sin `resolved_target_ids`**, es decir, sin
declarar qué corridas autoriza (§7.1 de `EXTENSIBLE_DECISION_MODEL_SPEC.md`).
No hay un presupuesto aprobado; hay un "sí" sin objeto.

### 5.2 La fórmula

```
Para cada (documento d, agente a):

  R(d,a)     = requisitos aplicables al tipo documental de d,
               que pertenecen al agente a,
               con resolve("D2", req).authorized == True
               y FORMAL_USE_ELIGIBILITY(source(req)) == True

  C(d,a)     = Σ_{req ∈ R(d,a)} |evidence_min_criteria(req)|

  budget(d,a)= tokens_per_criterion × C(d,a)
             + tokens_per_checkpoint × |R(d,a)|
             + json_overhead
               [clamp al contrato: budget + prompt_tokens ≤ num_ctx]

  chunks(d)  = chunks tras filtrado por matriz de aplicabilidad
  calls(d,a) = chunks(d) × |agentes con R(d,a) ≠ ∅|

  time(d,a)  = calls(d,a) × (budget(d,a) / 1000) × min_per_1k_tokens
```

Constantes, todas **medidas**, no supuestas:

```yaml
tokens_per_criterion:  130     # qualification_record.fingerprint.output_token_budget_formula
tokens_per_checkpoint:  60     # ídem
json_overhead:         120     # ídem
num_ctx:             16384     # ídem
min_per_1k_tokens:     5.8     # corrida real eu_annex11 sobre FS_v1.2, 2026-07-28:
                               # 27 chunks / 481 min / num_predict=3072, 0 fallos técnicos
chunk_correction:      1.17    # chunks reales del motor (27) vs. estimados por caracteres (23)
```

`min_per_1k_tokens = 5,8` es el parámetro más frágil: procede de **una** sola
corrida, de **un** agente, sobre **un** documento. La recalificación (§4)
medirá `latency_p50` y `latency_p95` y **debe sustituirlo** por un valor con
dispersión conocida. Hasta entonces se usa con banda de incertidumbre
explícita.

### 5.3 Bloque D4-A — parametrizado, sin llenar

```yaml
# D4-A — SE CALCULA EN G8, DESPUÉS DEL PACK FINAL. NO LLENAR ANTES.
max_calls:               <Σ calls(d,a) sobre el plan resuelto>
estimated_runtime_min:   <Σ time con min_per_1k_tokens = p50_medido × 0.85>
estimated_runtime_likely:<Σ time con min_per_1k_tokens = p50_medido>
estimated_runtime_max:   <Σ time con min_per_1k_tokens = p95_medido>
hard_stop_calls:         <max_calls × 1.25, redondeado hacia arriba>
hard_stop_wall_time:     <estimated_runtime_max × 1.30>
checkpoint_mode:         per_document
resume_fingerprint_required: true
```

Márgenes justificados:

- **`hard_stop_calls = max_calls × 1,25`**: cubre reintentos dirigidos de
  fallos técnicos (el mecanismo ya existe, commit `c2d58e8`). Un 25 % es
  holgado frente a los 0 fallos técnicos de la corrida Annex 11 (27/27), y
  ese es el punto: el tope duro debe ser inalcanzable en operación normal y
  disparar solo ante un comportamiento anómalo.
- **`hard_stop_wall_time = estimated_runtime_max × 1,30`**: sobre el p95, no
  sobre el p50. Un tope de tiempo calculado sobre la mediana se dispara en la
  mitad de las corridas y deja de significar nada.

### 5.4 Referencia calibratoria

Aplicando la fórmula al catálogo de **hoy** (pack 211 con 0 criterios) se
reproduce el plan existente:

| documento | tipo | req. aplicables | chunks | llamadas | tiempo |
|---|---|---|---|---|---|
| RW-0005 | FS | 18 | 27 | 54 | 20,1 h |
| RW-0006 | URS | 10 | 9 | 27 | 6,7 h |
| RW-0014 | DS | 4 | 8 | 24 | 2,8 h |
| RW-0011 | DS | 4 | 7 | 21 | 2,3 h |
| RW-0012 | DS | 4 | 7 | 21 | 2,3 h |
| **total** | | | | **147** | **34,3 h** |

Que la fórmula reproduzca el plan es la **verificación de la fórmula**, no una
estimación de D4-A. La cifra real de D4-A será mayor: el pack 211 pasará de 0
a *n* criterios y arrastra a los 5 requisitos de Part 11 que lo declaran como
`predicate_rule_id`.

### 5.5 Sensibilidad al pack 211

Con `tokens_per_criterion = 130` y `min_per_1k_tokens = 5,8`, cada criterio
añadido al pack 211 cuesta aproximadamente:

```
Δtiempo ≈ chunks_del_documento × (130 / 1000) × 5,8 min ≈ chunks × 0,754 min
```

Para RW-0005 (27 chunks): **≈ 20 min por criterio**. Un pack de 5 criterios
—el tamaño típico de los packs existentes— añade **≈ 1,7 h solo en RW-0005**,
más su parte proporcional en los otros cuatro documentos analizables.

Se ofrece como orden de magnitud para que Cesar dimensione la decisión de G4a
**antes** de firmarla, no como una cifra a aprobar. La cifra sale en G8.

---

## 6. Coste de ejecutar antes de aprobar — y su asimetría

Toda corrida queda atada a un `run_fingerprint` que **incluye
`catalog_sha256`**. Aprobar los packs implica firmar y muy probablemente
ajustar los `evidence_min_criteria`. Cualquier cambio de `requirements.yaml`:

1. cambia `catalog_sha256` ⇒ **invalida todos los checkpoints**; ningún run
   previo es reanudable;
2. cambia el número de criterios ⇒ cambia `num_predict` ⇒ cambia el contrato
   de salida;
3. deja los resultados anteriores como producidos contra un catálogo que ya
   no es el vigente: utilizables como diagnóstico, **nunca como evidencia
   formal**.

**Ejecutar antes de aprobar cuesta repetirlo entero. Esperar no cuesta más
que calendario.** La asimetría es total, y por eso el orden G3→G4→G6→G8 no
admite atajos.

---

## 7. Tests

`factory/tests/test_model_requalification_and_d4a.py`

| id | Test |
|---|---|
| Q-01 | fingerprint recomputado hoy ≠ almacenado ⇒ `QUALIFICATION_INVALIDATED` |
| Q-02 | `INVALIDATED_BY` nombra **ambas** causas (`catalog_sha256` y `prompt_versions`) |
| Q-03 | un prompt nuevo en el directorio ⇒ fingerprint distinto (protege el glob dinámico) |
| Q-04 | `previous_fingerprint: null` ⇒ no hay calificación a la que caer |
| Q-05 | consulta de metadata permitida con `QUALIFICATION_INVALIDATED` |
| Q-06 | inferencia **bloqueada** con `QUALIFICATION_INVALIDATED`, salvo `run_context="model_requalification"` |
| Q-07 | `run_context="model_requalification"` solo válido contra el Golden Dataset |
| Q-08 | recalificar con cualquiera de las 5 precondiciones abierta ⇒ **bloqueado** |
| Q-09 | `golden_dataset_sha256` presente en el fingerprint (cierra D-1) |
| Q-10 | la fórmula de §5.2 reproduce 147 llamadas y 34,3 h ± 5 % con el catálogo de hoy |
| Q-11 | añadir *n* criterios al pack 211 ⇒ `max_calls` y tiempo crecen según §5.5 |
| Q-12 | `hard_stop_calls > max_calls` y `hard_stop_wall_time > estimated_runtime_max`, siempre |
| Q-13 | D4-A con algún campo `<placeholder>` sin resolver ⇒ **no registrable** |
| Q-14 | `resolve("D4", scope)` sobre el registro histórico sin targets ⇒ `INVALID_RECORD` |

Q-10 es el test de la fórmula: si deja de reproducir el plan conocido, o la
fórmula cambió o los parámetros medidos cambiaron, y en ambos casos hay que
mirar antes de seguir.

---

## 8. Lo que este diseño NO hace

- No recalifica el modelo ni invoca Ollama.
- No aprueba el Golden Dataset ni le añade casos.
- No fija ninguna cifra de D4-A: deja la fórmula y los parámetros.
- No autoriza ninguna corrida de corpus.
- No modifica `qualification_record.json`.
