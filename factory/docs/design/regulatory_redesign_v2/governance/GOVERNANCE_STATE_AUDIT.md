# GOVERNANCE_STATE_AUDIT — §1 del plan W5V2_ARQ_GOBERNANZA_DECISIONES

**Fecha de la auditoría:** 2026-07-29
**Naturaleza:** SOLO LECTURA. No se registró ninguna decisión, no se
reverificó ninguna fuente, no se invocó Ollama, no se ejecutó corpus, no se
modificó la auditoría histórica, no se cambió código ni estados.
**Método:** lectura directa de artefactos en disco + ejecución read-only de
`verify_chain()` + recomputación entrada por entrada de la cadena + `grep`
sobre el árbol de código. Cada valor lleva su evidencia (archivo:línea,
`entry_id` de auditoría, `decision_id`, o hash calculado en el momento).

---

## 0. Resumen ejecutivo — el hallazgo que reorienta el plan

El plan parte de que *"Part 211 ingresó al registry y NO está cubierta por
una decisión"*. **Eso es inexacto y la corrección importa**, porque cambia
dónde está el agujero.

La fábrica tiene **dos sistemas de decisiones que no se conocen entre sí**:

| | **Sistema A** | **Sistema B** |
|---|---|---|
| Módulo | `factory/layer9/decision_log.py` | `factory/services/w5_human_decisions.py` |
| Almacén | `factory/layer9/decisions/decisions.jsonl` (9 registros) | `factory/layer9/decisions/w5_human_decisions.jsonl` (5 registros) |
| Identificadores | **abiertos** — `action` es texto libre, `decision_id` UUID4 (o literal como `MC-0001`) | **cerrados** — tupla `DECISION_IDS` de 5 elementos (l.54-60) |
| Ciclo | **proponer → confirmar (humano) → aplicar** | registrar (1 por id) / corregir |
| Trazabilidad | `decision_origin`, `recorded_by`, `decided_by`, `confirms_decision_id` | `decision_origin`, `approved_by`, `supersedes_recorded_at` |
| **Enforcement** | **SÍ** — `apply_source_registration()` (l.212-222) **rechaza** si la decisión no es `human_confirmed` + `approve` | **NO** — cero lectores en todo el árbol |
| Superficie humana | ninguna (se opera desde código/agente) | UI Mission Control |
| Propietario del fichero | `ing_cpmo` (proceso del host) | `root` (proceso del contenedor) |

**Part 211 entró por el Sistema A y entró bien:** propuesta `fcf933e7-…`
(`agent_proposed`, 02:25:06.473Z) → confirmación **`caa2421d-…` firmada por
`Cesar`, `decision_origin=human_confirmed`, 02:25:06.513Z** → aplicación, que
solo procedió porque encontró esa confirmación. El evento de auditoría
`db3df1f1-…` (02:25:06.554Z) es posterior a la confirmación por 41 ms.

**Lo que Part 211 NO tiene es cobertura por D1**, que vive en el Sistema B y
es una decisión **distinta**: no autoriza el alta, sino la *cadencia y la
autoridad de reverificación*. D1 dice `"ALL"` sobre un registry que en el
momento de la firma tenía tres fuentes.

> **Enunciado corregido del problema raíz:** no es "una fuente entró sin
> decisión". Es que **la fábrica tiene dos modelos de decisión con
> propiedades opuestas** —uno extensible y con enforcement pero sin
> superficie humana; otro con superficie humana pero cerrado y sin
> enforcement— y **ninguna decisión de uno es visible para el otro**. Part
> 211 es el primer caso donde esa desconexión produce un hueco real de
> cobertura; no será el último mientras existan los dos.

Todo lo demás de la auditoría se lee a la luz de esto.

---

## 1. Evento que registró `ecfr_21cfr_part211`

### 1.1 Cadena completa de decisiones (Sistema A)

`factory/layer9/decisions/decisions.jsonl`, líneas 6-9:

| línea | `decision_id` | `decision_origin` | `decided_by` | timestamp | contenido |
|---|---|---|---|---|---|
| 6 | `d5f72735-5b04-4468-b403-1009223e0084` | `agent_proposed` | `layer8_agent` | `2026-07-29T02:11:29.258853Z` | propuesta nº1 — `canonical_file` en ruta absoluta de scratchpad |
| 7 | `786464e0-dd57-444b-ba85-cd867509a2eb` | **`human_confirmed`** | **`Cesar`** | `2026-07-29T02:11:29.299184Z` | confirma `d5f72735-…` |
| 8 | `fcf933e7-5823-422c-9c0e-a246fe561e40` | `agent_proposed` | `layer8_agent` | `2026-07-29T02:25:06.473544Z` | propuesta nº2 — *"REHACE el alta tras corregir `repo_relative()`: la primera ejecucion escribio canonical_path absoluto del host, que no resuelve dentro de factory-api. Mismo fichero, mismo hash, misma decision de Capa 9"* |
| 9 | `caa2421d-d56b-4f23-927d-5d7d752e02d7` | **`human_confirmed`** | **`Cesar`** | `2026-07-29T02:25:06.513205Z` | confirma `fcf933e7-…` |

### 1.2 Eventos de auditoría correspondientes

| línea | timestamp | `entry_id` | `data.decision_id` |
|---|---|---|---|
| `factory/audit/factory_audit.jsonl:18571` | `2026-07-29T02:22:23.949473Z` | `6407dabb-c94f-493e-9cf1-92dfb01e8124` | `786464e0-…` |
| `factory/audit/factory_audit.jsonl:18574` | `2026-07-29T02:25:06.554118Z` | `db3df1f1-5d5c-4100-93a1-fe14a85ab986` | `caa2421d-…` |

Ambos declaran `sha256_copy =
ecd9f8ba39e59c7713be98c293f1da4b125a68706d32ce4c77a0b579797423e3`,
`regulatory_currency_status = pending_reverification`,
`schema_validated = source_registry_entry_v1`. El registry conserva el
`canonical_path` **relativo** — el del segundo ciclo.

**`data.decision_id` NO es un UUID de operación: resuelve a una decisión
humana real del Sistema A.** Los dos altas son un intento fallido por ruta
absoluta y su rehacer, cada uno con su propia confirmación de Cesar. Nada se
borró.

### 1.3 Herramienta y actor

**Herramienta:** `factory/regulatory/human_source_registration.py`, único
emisor de `regulatory_source_registered` (l.328). Tres pasos deliberadamente
separados:

- `propose_source_registration()` (l.120-168) — valida campos declarados,
  rechaza campos derivados, comprueba unicidad, escribe una propuesta
  `agent_proposed`. **No copia, no hashea, no toca el registry.**
- `confirm_source_registration()` (l.176-198) — exige que el `decision_id`
  sea una propuesta `agent_proposed` de esa misma `action`, exige
  `confirmed_by` no vacío, escribe la confirmación `human_confirmed` con
  `confirms_decision_id`. **Sigue sin escribir el registry.**
- `apply_source_registration()` (l.204+) — **único punto de escritura**.
  Rechaza si la decisión no es `human_confirmed` + `approve` + de la `action`
  correcta (l.217-222); revalida unicidad *después* de la propuesta (l.229);
  exige que el fichero exista (l.236); **recalcula el SHA-256 y aborta si no
  coincide con el declarado** (l.244-249); rechaza declarar
  `VERIFIED_AGAINST_PRIOR_KNOWN_HASH` en una primera ingesta (l.252-257);
  exige que `supersedes` resuelva (l.260-264).

**Actor:** `Cesar`, con identidad real, en ambos ciclos.

> **Hallazgo A-1 (positivo, y es el modelo a extender):** el alta de fuentes
> ya implementa exactamente lo que §2 y §3 del plan piden — identificadores
> extensibles, propuesta/confirmación humana separadas, y un punto de
> aplicación que **falla cerrado** sin decisión humana. No hay que inventar
> el modelo: hay que **generalizarlo** y hacer que D1–D5 vivan en él.

---

## 2. Decisión utilizada para el registro, y el hueco real

**Para el ALTA:** `caa2421d-d56b-4f23-927d-5d7d752e02d7`, `Cesar`,
`human_confirmed`. **Existe y es válida.**

**Para la COBERTURA D1:** ninguna.

`factory/layer9/decisions/w5_human_decisions.jsonl` contiene **5 líneas**,
todas del 2026-07-29 entre `00:15:15Z` y `00:15:59Z`, todas firmadas por
`cesar`, todas `APPROVE`, **ninguna posterior y ningún registro de
corrección**.

```json
{"decision_id":"D1_regulatory_sources","decision":"APPROVE","approved_by":"cesar",
 "decision_date":"2026-07-29T00:15:15.595831+00:00","decision_origin":"human_confirmed",
 "notes":"","recorded_at":"2026-07-29T00:15:15.595879+00:00",
 "approved_source_ids":"ALL","reverification_cadence_months":1,
 "reverification_authority":"cesar"}
```

**Aritmética decisiva:** D1 se firmó a las `00:15:15Z`. Part 211 se propuso a
las `02:11:29Z`, se confirmó a las `02:25:06Z` y se copió (`copied_at`) a las
`02:25:06.536379Z`. **Part 211 entró al registry 2 h 10 min después de que se
firmara la D1 que dice `"ALL"`.**

En el momento de la firma, el registry contenía tres fuentes —
`ecfr_21cfr_part11`, `eu_gmp_annex11`, `mhra_gxp_di_guidance_2018`, todas con
`copied_at = 2026-07-17T19:32:45Z`. Ese trío, y solo ese trío, es lo que
`"ALL"` designaba.

> **Hallazgo A-2 (el hueco, con su nombre exacto):** Part 211 está
> **autorizada para existir** en el registry y **no autorizada para ser
> reverificada bajo ninguna cadencia ni autoridad**. El acto de alta tiene
> gobernanza; el ciclo de vida posterior no. Y como D1 no tiene lectores
> (§4), esa falta de cobertura hoy **no bloquea absolutamente nada**: es un
> hueco silencioso.

---

## 3. Estado real y elegibilidad de Part 211

De `factory/regulatory/sources/registry.json`:

```
source_id                  = ecfr_21cfr_part211
official_source_url        = https://www.ecfr.gov/api/versioner/v1/full/2026-07-01/title-21.xml?part=211
sha256_original            = ecd9f8ba39e59c7713be98c293f1da4b125a68706d32ce4c77a0b579797423e3
sha256_copy                = idéntico  → hashes_match = True   (RECALCULADO por apply_, no declarado)
size_bytes                 = 96680
local_integrity_status     = PASS
official_origin_status     = FIRST_INGESTION_NO_PRIOR_KNOWN_HASH_TO_COMPARE
regulatory_currency_status = pending_reverification
version                    = NO_DISPONIBLE
effective_date             = NO_DISPONIBLE
reverification_due         = None
```

Las tres fuentes antiguas declaran
`official_origin_status = VERIFIED_AGAINST_PRIOR_KNOWN_HASH_2026-07-06_INGESTION`;
Part 211 declara `FIRST_INGESTION_NO_PRIOR_KNOWN_HASH_TO_COMPARE`, y no por
descuido: `apply_source_registration()` l.252-257 **habría abortado el alta**
si se hubiera intentado declarar lo contrario. Es una declaración honesta
forzada por código.

En el catálogo, el único requisito que la usa (`21_CFR_211.68(b)`):

```
source_verification_status         = PENDING_REVERIFICATION
pack_lifecycle_status              = DRAFT
content_review_status              = PENDING_HUMAN_INTERPRETATION
runtime_eligibility                = ENABLED_REVIEW_ONLY
baseline_eligibility               = PROVISIONAL_ONLY
positive_conclusion_eligibility    = PROVISIONAL_ONLY
draft_remediation_eligibility      = BLOCKED
clean_candidate_eligibility        = BLOCKED
release_eligibility                = BLOCKED
production_eligibility             = BLOCKED
ready_for_regulatory_use           = False
evidence_min_criteria              = 0 elementos
exclusion_criteria                 = 0 elementos
weak_keywords                      = 0 elementos
```

---

## 4. Consumidores reales de `approved_source_ids` y de las decisiones W5

`grep -rn "approved_source_ids"` sobre todo el árbol (excluyendo `.venv` y
`node_modules`): **17 ocurrencias en 4 archivos, todas de escritura,
transporte o prueba. Cero lecturas para autorizar.**

| Archivo | Rol | ¿Autoriza? |
|---|---|---|
| `factory/services/w5_human_decisions.py:255,290-300,333,382` | valida presencia y persiste | no |
| `factory/api/routes/layer9.py:1225,1256,1276,1295` | transporta body→servicio | no |
| `factory/ui/js/mission_control/w5_decisions.js:218` | lo construye desde el `<select>` | no |
| `factory/tests/test_w5_human_decisions.py` (6 refs) | pruebas de validación de entrada | no |

Búsqueda complementaria — `grep -rn "recorded_decisions\|w5_human_decisions\|
decision_history" --include=*.py factory/` fuera de `factory/tests/`:
**únicamente** el router `factory/api/routes/layer9.py` y el propio servicio.

Contraste con el Sistema A, cuyos lectores sí existen:

| Lector de `decisions.jsonl` | Qué exige |
|---|---|
| `factory/regulatory/human_source_registration.py:212-222` | `human_confirmed` + `approve` + `action` correcta, **o aborta el alta** |
| `factory/regulatory/human_source_update.py:75,99` | mismo patrón para modificaciones de fuente |
| `factory/services/gmpai_artifact_service.py:510-518` | resuelve un `decision_id` para el registro de cierre de FS_v1.2 |

> **Hallazgo A-3 (confirma el hecho 3 del plan, acotado):** los cinco
> consumidores nombrados en §3 del plan — reverificación
> (`factory/regulatory/source_currency_checker.py`), elegibilidad de packs
> (`requirement_catalog_loader.py`, `provisional_evidence_model.py`),
> planificador (`verified_pipeline.py`), baseline
> (`tools/build_source_baseline_allowlist.py`), release gate
> (`core/quality_gate_runner.py`, `core/release_manager.py`) — **no leen
> ninguno de los dos sistemas de decisiones.** El enforcement del Sistema A
> cubre el *acto de alta* y termina ahí; nada protege el uso posterior.

---

## 5. Consumidores de estados de fuentes

Sí existen, pero son tres módulos y ninguno consulta cobertura humana:

| Consumidor | Qué lee | Qué hace |
|---|---|---|
| `factory/regulatory/requirement_catalog/provisional_evidence_model.py:90-160` | `source_verification_status` | `_NEVER_PASS_STATES = {NOT_EVALUATED, NOT_DETERMINED, PENDING_REVERIFICATION}`; restringe resultados vía `ALLOWED_RESULTS_WHILE_PENDING_REVERIFICATION`; emite `limitation_code=SOURCE_PENDING_REVERIFICATION` |
| `factory/regulatory/requirement_catalog/provisional_evidence_model.py:225-245` | ídem | exige `== LOCAL_CANONICAL_COPY_VERIFIED` para el criterio `source_verification_status_verificado` |
| `factory/services/gap_assessment_finding_mapper.py:248,282` | ídem | degrada la autoridad del hallazgo a `PROVISIONAL` |

`provisional_evidence_model.py:193-194` declara explícitamente que **a
propósito NO evalúa `source_verification_status`** en la elegibilidad de
*ejecución* — decisión deliberada para que `PENDING_REVERIFICATION` no
bloqueara el trabajo provisional. Coherente con el diseño provisional, pero
implica que **nada impide ejecutar sobre una fuente no cubierta**; solo se
impide *concluir formalmente*.

---

## 6. Gates que consultan decisiones

| Gate / módulo | Campo de decisión que lee |
|---|---|
| `factory/regulatory/model_qualification_gate.py` | ninguno — compara *fingerprints* (`catalog_sha256`, `model_digest`, `prompt_versions`, `schema_sha256`, `num_ctx`…), no decisiones |
| `factory/core/quality_gate_runner.py` (14 gates) | ninguno — gates de construcción/runtime de solución |
| `factory/regulatory/applicability.py` + `applicability_matrix.yaml:54-58` | `approval.decision_id: "MC-0001"` **como texto declarativo en el YAML**, no como lectura del almacén |
| `factory/scripts/ops/factory_selfcheck.sh` (Gate 0) | ninguno |

**Ningún gate resuelve un `decision_id` contra `decisions.jsonl` para decidir
si algo procede.** La única resolución real de `decision_id` en todo el árbol
ocurre dentro de las herramientas de alta/modificación de fuentes y en
`gmpai_artifact_service`, no en un gate.

---

## 7. UI y endpoints disponibles hoy

### Endpoints (`factory/api/routes/layer9.py`)

| Método | Ruta | Semántica |
|---|---|---|
| GET | `/api/v1/layer9/w5-decisions` (l.1232) | solo lectura; no escribe auditoría |
| POST | `/api/v1/layer9/w5-decisions/{decision_id}` (l.1243) | 1 evento; **409** si ya existe; **422** identidad genérica |
| POST | `/api/v1/layer9/w5-decisions/{decision_id}/correct` (l.1284) | 1 evento; **404** si no hay original; **422** si no cambia nada |

`W5CorrectionBody` (l.1272-1281) **sí acepta** `approved_source_ids`,
`reverification_cadence_months`, `reverification_authority`,
`approved_pack_ids`.

**No existe ningún endpoint HTTP para el Sistema A.** `decision_log`,
`human_source_registration` y `human_source_update` se operan desde código.
El paso `confirm_*(confirmed_by="Cesar")` fue ejecutado por Capa 8 escribiendo
el nombre de Cesar — con su instrucción, pero **sin que un humano tocara una
superficie propia**.

> **Hallazgo A-4:** la confirmación humana del Sistema A es *humana por
> convención, no por construcción*. `confirm_source_registration()` solo
> valida que `confirmed_by` no esté vacío (l.191-192) — **no aplica la lista
> `RESERVED_IDENTITIES`** que el Sistema B sí aplica (`w5_human_decisions.py`
> l.46-50, 238-245). Un `confirmed_by="human"` sería aceptado por el Sistema
> A y rechazado con 422 por el Sistema B. Las dos superficies tienen
> **estándares de identidad distintos para el mismo tipo de acto**.

### UI (`factory/ui/js/mission_control/w5_decisions.js`)

- **Alta de D1** (l.88-90): `<select>` de valor único — `ALL` o **una**
  `source_id`. `submitW5Decision` (l.218):
  `body.approved_source_ids = val('w5-d1-sources')==='ALL' ? 'ALL' :
  [val('w5-d1-sources')]`. **Estructuralmente incapaz de enviar tres ids.**
- **Corrección de D1** (l.73-83; `submitW5Correction` l.125-148): expone
  **solo** cadencia, motivo y firmante. Body enviado:
  `{corrected_by, reason, reverification_cadence_months}`. **Ningún control
  para `approved_source_ids`.**

> **Hallazgo A-5 (matiz que corrige el hecho 4 del plan):** la limitación es
> **de UI, no de API**. `POST …/correct` acepta hoy `approved_source_ids` con
> lista explícita, y `record_correction()` lo persiste y lo registra en
> `corrected_fields`. La Corrección D1 con snapshot de tres fuentes es
> técnicamente registrable **por API hoy mismo**; lo que falta es la
> superficie humana — y firmar una decisión regulatoria por `curl` no es una
> vía de gobernanza aceptable. El trabajo pendiente es de UI (§9.A), no de
> backend.

---

## 8. Estado real de la cadena de auditoría

`verify_chain()` ejecutado read-only sobre
`/home/ing_cpmo/factory/audit/factory_audit.jsonl`:

```json
{"verified": false, "is_fork": true, "assessment": "WARN",
 "log_count": 19818, "verified_count": 19817,
 "hash_errors": 0, "chain_errors": 1, "failed_count": 1,
 "hash_algo": "sha256", "part11_compliant": true}
```

### 8.1 Localización exacta del fork (recomputada entrada por entrada)

```
LÍNEA 108 de 19 818
  timestamp  = 2026-06-15T13:54:43.350825+00:00
  event_type = gates_executed
  project_id = lab_qc_project
  entry_id   = ab689c7c-3e0a-4c77-936b-152851f51a30
  prev_entry_hash DECLARADO = sha256:20b262690f5b1c0c3cd0a13504c23744d765cde20c14e62cb6ff489f82f6622b
  prev_entry_hash REAL      = sha256:a46ca408a4e70721b218e8e1ad0bc72e2d432f6ac52db3ee54e8ed2cf72ce97a
  entrada anterior (línea 107):
      timestamp  = 2026-06-15T13:51:32.834011+00:00
      event_type = layer8_stop_condition_triggered
      entry_id   = 6a680163-f4b0-4c50-9c1c-ec79f433b94b
```

**Exactamente UNA ruptura, en la línea 108, fechada el 2026-06-15.** Las
19 710 entradas posteriores encadenan correctamente. El fork es inequívocamente
**histórico**: 44 días anterior a esta auditoría y anterior a todo W5 V2.

`hash_errors = 0` en las 19 818 entradas: **ningún contenido fue alterado**.
Lo roto es el enlace, no el dato. El hash declarado
(`20b26269…`) no corresponde a ninguna entrada presente en el fichero — el
escritor concurrente encadenó contra un estado que otra escritura ya había
sustituido.

### 8.2 El colapso de dimensiones

`factory/core/audit_writer.py:270-278` computa
`is_fork = hash_errors == 0 and chain_errors > 0` y emite
`assessment="WARN"`, `part11_compliant=True` y el texto *"Contenido auténtico,
Part-11 cumplido."*

> **Hallazgo A-6:** el sistema **se autodeclara conforme a Part 11** sobre
> una cadena que él mismo reporta como `verified=false`. Es una
> autodeclaración de cumplimiento sin acto humano, precisamente lo que §7.1
> del plan prohíbe. `part11_compliant` no es un hecho computable: es una
> conclusión regulatoria y exige una excepción humana registrada.

### 8.3 Mecanismo de escritura y ventana de concurrencia real

`factory/core/audit_writer.py:22,174-212`: `write_event` toma
`fcntl.flock(lock_fh, fcntl.LOCK_EX)`, invalida el cache
`_last_entry_hash = None` **dentro** del lock, relee `prev_hash`, escribe y
libera. Correcto contra concurrencia inter-proceso **sobre el mismo inodo**.

Evidencia de que hay más de un escritor con identidad distinta:

```
-rw-r--r-- ing_cpmo  factory/layer9/decisions/decisions.jsonl        (host)
-rw-r--r-- root      factory/layer9/decisions/w5_human_decisions.jsonl (contenedor)
```

El almacén de decisiones W5 lo escribe **root desde dentro de `factory-api`**;
el otro lo escribe el proceso del host. Ambos llaman a `write_event()` sobre
el mismo `factory_audit.jsonl` montado. `flock` es advisory y **sí** funciona
a través del bind-mount siempre que sea el mismo inodo, de modo que el
mecanismo actual probablemente cierra la ventana; pero el fork del 2026-06-15
es anterior a este patrón o lo produjo un escritor que no pasa por
`write_event`. Determinarlo con certeza exige arqueología de commits que
**no** forma parte de esta corrida: se traslada a §7 como insumo obligatorio
del paquete de excepción (la causa raíz debe estar establecida **antes** de
que Cesar acepte la excepción, no después).

---

## 9. Estado de artefactos versionados

| Artefacto | Versión declarada | Hash real (calculado ahora) | Referencia | Veredicto |
|---|---|---|---|---|
| `factory/regulatory/requirement_catalog/requirements.yaml` | `catalog_version: 1.0` | `a83c81682309af41615a86f93498a2d31b7b2316a2e30ad56fdcfb3b8a9e55ae` | `6486405abecd729d85e32ec4a9af03cd13ad144162ebcb300ee9d25016202b8d` (congelado en `qualification_record.json:16`) | **INCONSISTENTE** — hash distinto, versión igual |
| `factory/regulatory/applicability_matrix.yaml` | `matrix_version: "2.1"` (l.49) | — | `MC-0001.metadata.matrix_version = "2.0"` | **INCONSISTENTE** — la aprobación cubre explícitamente la **2.0** |
| `factory/regulatory/model_qualification/qualification_record.json` | `QUALIFIED_FOR_VALIDATION_ONLY`, `evaluated_at 2026-07-28T13:32:46Z` | — | `fingerprint.catalog_sha256 = 6486405a…` | **INVALIDADA** — el catálogo vigente es `a83c8168…` |
| Evidence Pack `21_CFR_211.68(b)` | `pack_version: 1.0-draft` | — | — | **INCOMPLETO** — 0 criterios de todo tipo |

El propio archivo de la matriz lo admite (l.50-52): *"v2.1 (2026-07-29): se
agregan las filas de 21_CFR_211.68(b)… **MC-0001 NO las cubre** — estan
marcadas PROPUESTO y requieren una confirmacion humana nueva."* Y en l.44-47
fija la regla que incumple: *"Cualquier fila que se agregue o edite DESPUÉS
de esta aprobación debe marcarse # PROPUESTO de nuevo hasta la siguiente
confirmación explícita."*

La fila **sí** está marcada. Lo que **no** se retiró es el bloque
`approval.status: "human_confirmed"`, que sigue aplicando **al archivo
entero**.

> **Hallazgo A-7:** `applicability_matrix.yaml` declara aprobación de **grano
> de archivo** sobre contenido cuya aprobación es de **grano de fila**.
> `MC-0001` dice literalmente `matrix_version: "2.0"` en su metadata; el
> archivo dice `2.1`. Un lector automático que consulte `approval.status`
> obtiene `human_confirmed` para las filas de 211. El comentario humano dice
> lo correcto y el dato máquina dice lo contrario — **y el dato máquina es el
> que un gate leería.**

---

## 10. `MC-0001` y `MC-0002`

**`MC-0001` existe y es real**: `factory/layer9/decisions/decisions.jsonl`
línea 5 —
`decided_by: "Cesar"`, `decision_origin: "human_confirmed"`,
`recorded_by: "claude_code_session"`,
`timestamp: 2026-07-17T16:26:33.561688Z`,
`action: "w5v2_applicability_matrix_approval"`,
`metadata: {checkpoint: "W5v2_Ciclo1_Checkpoint_B", matrix_version: "2.0",
requirements_approved: 19, tests_passing_at_approval: 61,
commits_reviewed: [cd69207, 4ca0c29, a8f9d94]}`.

Nota de forma: `decision_log.write_decision()` genera `decision_id` con
`uuid.uuid4()` (l.62) y **no admite un id impuesto**. `MC-0001` es una cadena
literal, luego **no fue escrita por esa función**: se añadió por otra vía. No
invalida la decisión —tiene identidad, origen y metadata completos— pero
significa que el almacén acepta escrituras fuera de su API.

**`MC-0002` no existe.** `grep -rn "MC-0002\|MC_0002"` devuelve 3
ocurrencias, **todas en documentos**:

- `factory/docs/design/regulatory_redesign_v2/W5V2_D1A_D2A_ADDENDUM_DRAFT.md:247`
- `factory/docs/W5V2_RESUMEN_SESION_2026-07-29.md:130`
- el propio `docs_plan/W5V2_ARQ_GOBERNANZA_DECISIONES.md`

`factory/layer9/missions/` contiene 6 misiones y ninguna lo referencia.

> **Hallazgo A-8:** MC-0002 es un identificador **propuesto en un borrador y
> nunca creado**. La "unificación D2-A / MC-0002" de §5.2 del plan no es la
> fusión de dos sistemas vivos: es la decisión de **no crear el segundo**.
> La aprobación de packs debe registrarse como una `action` del Sistema A,
> igual que `w5v2_applicability_matrix_approval`.

---

## 11. Alcance 210 vs. 211 — **ya resuelto por Capa 9**

### 11.1 Evidencia documental del catálogo

Los 20 requisitos, por `source_id`:

| `source_id` | nº | requirement_ids |
|---|---|---|
| `mhra_gxp_di_guidance_2018` | 9 | `ALCOA_*` |
| `ecfr_21cfr_part11` | 5 | `21_CFR_11.10(a)`, `(d)`, `(e)`, `(g)`, `21_CFR_11.50_11.70` |
| `eu_gmp_annex11` | 5 | `ANNEX11_4`, `7.1`, `9`, `12`, `17` |
| `ecfr_21cfr_part211` | 1 | `21_CFR_211.68(b)` |
| **`ecfr_21cfr_part210`** | **0** | **—** |

Part 210 no está en el registry, no tiene copia local, no tiene pack y no
sustenta ningún requisito.

### 11.2 Evidencia decisional — la decisión ya está firmada

`decisions.jsonl` línea 6, `rationale` de la propuesta que Cesar confirmó:

> *"Regla predicado que falta para determinar `predicate_rule_id` /
> `part11_scope_status` en los 5 requisitos de Part 11 (assessment de
> cobertura 2026-07-29). **Alcance reducido decidido por Capa 9: solo Part
> 211.**"*

Y línea 8, la propuesta que rehace el alta:

> *"…Mismo fichero, mismo hash, **misma decision de Capa 9 (alcance reducido:
> solo Part 211)**."*

Ambas confirmadas por `Cesar` / `human_confirmed` (líneas 7 y 9).

> **Hallazgo A-9:** **§6.3 del plan ya está resuelto y no requiere una
> decisión nueva de Cesar.** El alcance "solo Part 211" está registrado en el
> almacén de decisiones, firmado, y es coherente con la evidencia del
> catálogo (0 requisitos apoyados en Part 210). Lo que falta no es decidir:
> es **hacer visible** esa decisión —hoy vive enterrada en el campo
> `rationale` de un texto libre, no en un campo estructurado consultable— y
> **corregir los documentos que siguen diciendo "210/211"**.

Documentos a corregir (ruta y línea):

| Ruta | Línea | Texto |
|---|---|---|
| `factory/docs/design/regulatory_redesign_v2/W5V2_D1A_D2A_ADDENDUM_DRAFT.md` | 88 | `… (+ Part 210: .../part-210)` en la fila "URL oficial primaria" |
| `factory/docs/design/regulatory_redesign_v2/REGULATORY_COVERAGE_ASSESSMENT_W5.md` | 157 | `### 2.1 FDA-CFR-210-211 — 21 CFR Parts 210 y 211` |

**Se excluye** `factory/docs/gmpai_reanalysis/scada_asdata_corpus_evaluation.json:50`:
ahí "Part 210" describe el **contenido de un documento Rockwell**, no el
alcance de la fábrica. Corregirlo sería falsear una observación. No tocar.

---

## 12. Estado del plan anterior — `W5V2_EVALUACION_COBERTURA_FUENTES.md`

| Sección | Estado | Evidencia |
|---|---|---|
| Ingesta de Part 211 al registry | **EJECUTADA Y GOBERNADA** | decisiones `fcf933e7`→`caa2421d`; eventos `18571`/`18574`; entrada en `registry.json` |
| Decisión de alcance (solo 211) | **EJECUTADA** | `rationale` de `d5f72735` y `fcf933e7`, confirmadas |
| Fila `21_CFR_211.68(b)` en el catálogo | **EJECUTADA (estructura)** | requisito presente, `minc=0` |
| Filas de 211 en la matriz → v2.1 | **EJECUTADA, SIN APROBAR** | `matrix_version: "2.1"`, filas `# PROPUESTO`, `MC-0001` cubre 2.0 |
| Agente `fda_cgmp_211_agent` + `cgmp211_prompts.yaml` | **EJECUTADA** | cabecera de la matriz l.22-31; `factory/tests/test_cgmp211_agent.py` |
| Interpretación humana del pack 211 | **NO EJECUTADA** | `content_review_status=PENDING_HUMAN_INTERPRETATION` |
| Registro de D1-A | **NO EJECUTADA** | imposible en Sistema B (tupla cerrada); posible en Sistema A pero nunca se hizo |
| Registro de D2-A | **NO EJECUTADA** | ídem |
| Reverificación de las 4 fuentes | **NO EJECUTADA** | las 4 en `pending_reverification` |
| Versionado del catálogo | **NO EJECUTADA** | `1.0` con hash cambiado |
| Recalificación del modelo | **NO EJECUTADA** | fingerprint desalineado |

**Se absorbe aquí** todo lo NO EJECUTADO. **La pausa de efectos D1–D5 se
mantiene** (`W5V2_PAUSE_STATE.md` vigente, no se tocó).

Los borradores `W5V2_D1A_D2A_ADDENDUM_DRAFT.md` quedan **supersedidos** por
`EXTENSIBLE_DECISION_MODEL_SPEC.md`. La nota de supersesión se añade como
bloque nuevo al inicio de ese archivo, **sin borrar ni editar su contenido**
— pendiente para la fase de implementación; esta corrida no modifica archivos
existentes.

---

## 13. Bloque de reporte §1

```
PART211_REGISTRATION_EVENT = DOS ciclos completos propuesta→confirmación→alta:
    Ciclo 1 (ruta absoluta, fallido en el contenedor):
      decisión propuesta  d5f72735-5b04-4468-b403-1009223e0084 @ 02:11:29.258853Z (agent_proposed)
      decisión confirmada 786464e0-dd57-444b-ba85-cd867509a2eb @ 02:11:29.299184Z (Cesar, human_confirmed)
      evento auditoría    entry_id=6407dabb-c94f-493e-9cf1-92dfb01e8124 @ 02:22:23.949473Z
                          (factory_audit.jsonl:18571)
    Ciclo 2 (ruta relativa, el que quedó vigente):
      decisión propuesta  fcf933e7-5823-422c-9c0e-a246fe561e40 @ 02:25:06.473544Z (agent_proposed)
      decisión confirmada caa2421d-d56b-4f23-927d-5d7d752e02d7 @ 02:25:06.513205Z (Cesar, human_confirmed)
      evento auditoría    entry_id=db3df1f1-5d5c-4100-93a1-fe14a85ab986 @ 02:25:06.554118Z
                          (factory_audit.jsonl:18574)
    Motivo del rehacer, textual: "la primera ejecucion escribio canonical_path
    absoluto del host, que no resuelve dentro de factory-api".

PART211_REGISTERED_BY = Cesar (decided_by="Cesar", decision_origin="human_confirmed",
    recorded_by="Cesar") en ambos ciclos. Propuesto por layer8_agent.
    Herramienta: factory/regulatory/human_source_registration.py
    (propose_ → confirm_ → apply_; apply_ rechaza sin human_confirmed, l.217-222).
    SALVEDAD: confirm_source_registration() solo exige confirmed_by no vacío
    (l.191-192); NO aplica RESERVED_IDENTITIES. La identidad es correcta aquí,
    pero el control que la garantiza no existe en esta superficie. Ver A-4.

PART211_REGISTRATION_DECISION = caa2421d-d56b-4f23-927d-5d7d752e02d7
    (action="regulatory_source_registration", decision="approve",
     human_confirmed por Cesar, confirms_decision_id=fcf933e7-…).
    EXISTE Y ES VÁLIDA. Autoriza el ALTA. No es, ni pretende ser, cobertura D1.

PART211_D1_COVERAGE = false. D1 (Sistema B) se firmó a las 00:15:15.595831Z
    con approved_source_ids="ALL" sobre un registry de 3 fuentes
    {ecfr_21cfr_part11, eu_gmp_annex11, mhra_gxp_di_guidance_2018}, todas con
    copied_at=2026-07-17T19:32:45Z. ecfr_21cfr_part211 se aplicó 2 h 10 min
    después (copied_at=2026-07-29T02:25:06.536379Z). Bajo la regla
    ALL→snapshot (§2.3), no está cubierta.
    NOTA CRÍTICA: la falta de cobertura hoy NO BLOQUEA NADA, porque D1 no
    tiene lectores. Es un hueco silencioso, no un freno operativo.

PART211_REVERIFICATION_ALLOWED = false (por gobernanza; NO por control).
    Hoy nada lo impediría técnicamente: source_currency_checker.py no lee
    ninguna decisión.

PART211_PACK_USE_ALLOWED = false. Doble bloqueo:
    (a) gobernanza — sin cobertura D1 (sin efecto operativo, ver arriba);
    (b) contenido — pack_lifecycle_status=DRAFT,
        content_review_status=PENDING_HUMAN_INTERPRETATION,
        0 evidence_min_criteria / 0 exclusion_criteria / 0 weak_keywords.
    (b) SÍ tiene efecto real: el gate bloquea la llamada y el requisito sale
    NO EVALUADO sin gastar inferencia.

PART211_FORMAL_USE_ALLOWED = false.
    ready_for_regulatory_use=False, release_eligibility=BLOCKED,
    production_eligibility=BLOCKED, baseline_eligibility=PROVISIONAL_ONLY,
    positive_conclusion_eligibility=PROVISIONAL_ONLY.

APPROVED_SOURCE_IDS_CONSUMERS = NINGUNO OPERATIVO.
    Escritura:    factory/services/w5_human_decisions.py (l.290-300, 382)
    Transporte:   factory/api/routes/layer9.py (l.1225, 1256, 1276, 1295)
    UI:           factory/ui/js/mission_control/w5_decisions.js (l.218)
    Tests:        factory/tests/test_w5_human_decisions.py (6 refs)
    Lecturas para autorizar: 0 archivos.

D1_OPERATIONALLY_ENFORCED = false. Ninguno de los 5 consumidores previstos
    importa w5_human_decisions ni resuelve un decision_id.
    CONTRASTE: el Sistema A sí tiene enforcement, pero solo en el acto de alta
    y modificación de fuentes (human_source_registration.py:212-222,
    human_source_update.py:75,99). Ningún gate, planner, baseline o release
    consulta decisión alguna.

D1_CORRECTION_UI_SUPPORTS_EXPLICIT_SOURCE_IDS = false (UI) / true (API).
    UI: el form de corrección expone SOLO cadencia+motivo+firmante
        (w5_decisions.js:73-83, 125-148); el select de alta es de valor único
        (l.88-90, 218) — no puede emitir una lista de 3 ids.
    API: W5CorrectionBody (layer9.py:1272-1281) acepta approved_source_ids y
        record_correction() lo persiste con su diff en corrected_fields
        (w5_human_decisions.py:380-403). El faltante es de UI, no de backend.

D1_A_REGISTRABLE = false EN EL SISTEMA B / true-en-principio EN EL SISTEMA A.
    Sistema B: DECISION_IDS (w5_human_decisions.py:54-60) es una tupla cerrada
      de 5; record_decision() rechaza con 422 cualquier id fuera de ella
      (l.265-266). Además NO existe el concepto de ADDENDUM: solo "original"
      (1 por id, 409 al repetir, l.273-278) y "corrección" (hereda y
      reemplaza, no amplía, l.380-394).
    Sistema A: decision_log.write_decision() acepta cualquier `action`; una
      D1-A podría registrarse hoy como
      action="w5v2_source_reverification_coverage_addendum". Nunca se hizo, y
      no habría UI para ello ni lector que la consuma.

D2_A_REGISTRABLE = false. Misma tupla cerrada en el Sistema B. MC-0002 —el
    vehículo que los borradores asumían— NO EXISTE (0 apariciones fuera de
    documentos de diseño; 0 misiones; sin almacén). MC-0001 SÍ existe
    (decisions.jsonl:5, Cesar, human_confirmed, 2026-07-17T16:26:33Z) y cubre
    explícitamente matrix_version "2.0", no la 2.1 vigente.

D4_A_REGISTRABLE = false. Misma tupla cerrada; y aunque se abriera, D4-A
    depende de un número de criterios que aún no existe (el pack 211 tiene 0).
```

---

## 14. Hallazgos consolidados

| id | Hallazgo | Severidad | Se resuelve en |
|---|---|---|---|
| **A-1** | El Sistema A (`decision_log` + alta de fuentes) **ya implementa** el modelo que §2/§3 piden: ids extensibles, propuesta/confirmación, aplicación fail-closed. Hay que generalizarlo, no inventarlo | *positivo* | §2 — el modelo se construye **sobre** él |
| **A-2** | Part 211 está **autorizada para existir** y **no cubierta para su ciclo de vida**; y la falta de cobertura no bloquea nada porque D1 no tiene lectores | **crítica** | §3 + §4 |
| **A-3** | Autorización sin enforcement: 0 lectores de decisiones en los 5 consumidores (reverificación, packs, planner, baseline, release) | **crítica** | §3 `DecisionScopeResolver` |
| **A-4** | Dos estándares de identidad para el mismo tipo de acto: el Sistema A acepta cualquier `confirmed_by` no vacío; el B aplica `RESERVED_IDENTITIES` y devuelve 422 | **alta** | §2 (validación única) |
| **A-5** | La incapacidad de registrar la Corrección D1 con snapshot es **de UI**, no de API | media | §9.A (menor esfuerzo del previsto) |
| **A-6** | `verify_chain()` autodeclara `part11_compliant=true` sobre una cadena `verified=false` | **alta** | §7.1 |
| **A-7** | `applicability_matrix.yaml` declara aprobación de grano de archivo (`human_confirmed`) sobre filas que `MC-0001` explícitamente no cubre (`matrix_version: "2.0"` vs. archivo `2.1`) | **alta** | §5 + §6 |
| **A-8** | MC-0002 no existe: nunca se creó. La "unificación" es la decisión de no crearlo | media | §5.2 |
| **A-9** | **El alcance "solo Part 211" YA está decidido y firmado por Cesar** — enterrado en un campo `rationale` de texto libre en vez de un campo estructurado | media | §6.3 — no requiere decisión nueva, requiere visibilidad + corrección de 2 documentos |
| **A-10** | `MC-0001` no pudo escribirlo `write_decision()` (genera `uuid4`, no admite id impuesto): el almacén acepta escrituras fuera de su propia API | media | §2 (validación de escritura) |
| **A-11** | Dos escritores con identidad de SO distinta (`root` desde el contenedor, `ing_cpmo` desde el host) sobre la misma cadena de auditoría | media | §7.2 (single writer) |

---

## 15. Confirmación de no-efectos

- Archivos creados: solo `.md` bajo
  `factory/docs/design/regulatory_redesign_v2/governance/`.
- Archivos modificados: **ninguno**.
- **Decisiones registradas: 0.** `w5_human_decisions.jsonl` sigue con 5
  líneas; `decisions.jsonl` con 9. Verificado tras cerrar la corrida.
- Ollama: **no invocado**.
- **Eventos de auditoría — matiz honesto.** La auditoría en sí es read-only:
  `verify_chain()` no escribe y las lecturas de artefactos tampoco. Pero
  §10.3 del plan exige *"Gate 0 PASS"*, y `factory_selfcheck.sh` ejecuta la
  suite completa, cuyos tests **sí** emiten eventos:

  | momento | `log_count` | `hash_errors` | `chain_errors` |
  |---|---|---|---|
  | inicio de la auditoría | 19 818 | 0 | 1 |
  | tras Gate 0 | 19 922 | 0 | 1 |

  **+104 eventos, todos de la suite de tests, ninguna ruptura nueva**
  (`NEW_FORKS_SINCE_BASELINE = 0`). No son eventos de gobernanza: ninguno
  registra una decisión, promueve un estado ni toca el corpus. Los conteos
  citados en §8 (19 818 entradas, fork en la línea 108) son la medición del
  inicio y siguen siendo el dato de referencia del fork, cuya posición no
  cambió.
- `CORPUS_READY = false` · `PRODUCTION_ENABLEMENT = BLOCKED` ·
  `REGULATORY_COMPLIANCE = NOT_DETERMINED`.
