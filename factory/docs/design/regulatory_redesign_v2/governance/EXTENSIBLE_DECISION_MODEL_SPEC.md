# EXTENSIBLE_DECISION_MODEL_SPEC — §2 del plan

**Estado:** DISEÑO. No implementado. No registra ninguna decisión.
**Supersede:** `factory/docs/design/regulatory_redesign_v2/W5V2_D1A_D2A_ADDENDUM_DRAFT.md`
(anotación de supersesión pendiente de añadir a ese archivo como bloque
nuevo, sin borrar su contenido).
**Depende de:** `GOVERNANCE_STATE_AUDIT.md` §0, A-1, A-4, A-8, A-10.

---

## 1. Principio, y su consecuencia inmediata

Las familias de decisión se definen en un **registro de familias** —un
archivo de datos versionado— y nunca en una constante de código. Agregar una
familia o un adendo jamás debe requerir tocar una tupla.

Pero la auditoría cambia el punto de partida. **No hay que construir el
modelo desde cero: hay que unificar dos que ya existen.**

| | Sistema A (`decision_log.py`) | Sistema B (`w5_human_decisions.py`) |
|---|---|---|
| Extensibilidad | ✅ `action` es texto libre | ❌ tupla cerrada de 5 |
| Propuesta/confirmación | ✅ dos actos separados | ❌ un solo acto |
| Enforcement | ✅ en el punto de aplicación | ❌ ninguno |
| Identidad estricta | ❌ solo "no vacío" | ✅ `RESERVED_IDENTITIES` → 422 |
| Superficie humana | ❌ ninguna | ✅ UI Mission Control |
| Snapshot del objetivo | ❌ no existe el concepto | ❌ `"ALL"` como comodín abierto |
| Adendos | ❌ no existe | ❌ no existe |
| Correcciones | ❌ no existe (se re-propone) | ✅ append + `supersedes_recorded_at` |

**El modelo objetivo es la unión de las columnas ✅ más lo que ninguno
tiene** (snapshot, adendos, hash del registry, resolver).

Regla dura, literal del plan: **prohibido "resolver" el problema añadiendo
nombres a `DECISION_IDS`.** Si el diseño de una fase futura propone eso, esa
fase está mal diseñada.

---

## 2. Registro de familias — `factory/registry/decision_families.yaml`

Ubicación elegida: `factory/registry/`, junto a `ports.yaml`,
`agents_catalog.yaml` y `ollama_host.yaml`, que es donde la fábrica ya pone
sus fuentes únicas de verdad declarativas.

```yaml
# factory/registry/decision_families.yaml
registry_version: 1
sha256_self: <se calcula sobre el archivo sin este campo>

families:

  D1:
    label: "Fuentes regulatorias — cadencia y autoridad de reverificación"
    target_kind: source_id
    target_registry: factory/regulatory/sources/registry.json
    selection_modes: [EXPLICIT_LIST, ALL_SNAPSHOT]
    payload_schema: decision_payload_d1_v1
    consumers:                       # los que DEBEN preguntar al resolver
      - source_reverification
      - source_lifecycle_transition
    requires_human_confirmation: true

  D2:
    label: "Evidence Packs — criterios interpretativos"
    target_kind: requirement_id
    target_registry: factory/regulatory/requirement_catalog/requirements.yaml
    selection_modes: [EXPLICIT_LIST]     # ALL_SNAPSHOT prohibido: cada pack
                                         # se aprueba por su contenido
    payload_schema: decision_payload_d2_v1
    consumers: [evidence_pack_eligibility, corpus_planner, formal_baseline]
    requires_human_confirmation: true

  D3:
    label: "Clasificación documental (T-039 y sucesores)"
    target_kind: document_id
    target_registry: factory/regulatory/scope/source_baseline_allowlist.yaml
    selection_modes: [EXPLICIT_LIST]
    payload_schema: decision_payload_d3_v1
    consumers: [corpus_planner]
    requires_human_confirmation: true

  D4:
    label: "Ejecución de corpus — presupuesto y límites duros"
    target_kind: run_scope
    target_registry: null                # el objetivo es un plan, no un id de registry
    selection_modes: [EXPLICIT_LIST]
    payload_schema: decision_payload_d4_v1
    consumers: [corpus_planner, run_driver]
    requires_human_confirmation: true

  D5:
    label: "Regeneración de paquetes QA"
    target_kind: package_id
    target_registry: factory/remediation_packages/
    selection_modes: [EXPLICIT_LIST]
    payload_schema: decision_payload_d5_v1
    consumers: [package_regeneration]
    requires_human_confirmation: true

  SOURCE_REGISTRATION:
    label: "Alta de fuente regulatoria en el registry"
    target_kind: source_id
    target_registry: factory/regulatory/sources/registry.json
    selection_modes: [EXPLICIT_LIST]
    payload_schema: decision_payload_source_registration_v1
    consumers: [source_registration_apply]
    requires_human_confirmation: true
    legacy_action: regulatory_source_registration   # ver §5

  APPLICABILITY_MATRIX:
    label: "Aprobación de la matriz de aplicabilidad documental"
    target_kind: matrix_version
    target_registry: factory/regulatory/applicability_matrix.yaml
    selection_modes: [EXPLICIT_LIST]
    payload_schema: decision_payload_matrix_v1
    consumers: [applicability_resolution, corpus_planner]
    requires_human_confirmation: true
    legacy_action: w5v2_applicability_matrix_approval

  ARTIFACT_VERSION:
    label: "Aprobación de una versión de artefacto gobernado"
    target_kind: artifact_id
    target_registry: null
    selection_modes: [EXPLICIT_LIST]
    payload_schema: decision_payload_artifact_version_v1
    consumers: [version_guard, model_qualification_gate, release_gate]
    requires_human_confirmation: true

  AUDIT_EXCEPTION:
    label: "Excepción humana sobre una anomalía de la cadena de auditoría"
    target_kind: audit_event_id
    target_registry: factory/audit/factory_audit.jsonl
    selection_modes: [EXPLICIT_LIST]
    payload_schema: decision_payload_audit_exception_v1
    consumers: [audit_reporting, release_gate]
    requires_human_confirmation: true
```

**Añadir una familia = añadir un bloque a este YAML + su `payload_schema`
en `factory/regulatory/schemas/`.** Cero cambios de código.

### 2.1 Por qué D1-A no es una familia

`D1-A` **no aparece** en el registro, y es deliberado. `D1-A` no es una
familia nueva: es un **ADDENDUM de la familia D1**
(`decision_type=ADDENDUM`, `amendment_sequence=1`). Modelar cada adendo como
familia es exactamente el error que llevó a la tupla cerrada. Lo mismo para
`D2-A` y `D4-A`.

---

## 3. Schema del registro de decisión

`factory/regulatory/schemas/decision_record_v1.json` (JSON Schema; aquí en
YAML por legibilidad):

```yaml
decision_record:
  # --- identidad ---
  schema_version: decision_record_v1
  decision_family: <clave del registro de familias>       # validado contra el YAML
  decision_instance_id: "<familia>-<año>-<secuencia>"     # ej. D1-2026-002
  decision_type: ORIGINAL | CORRECTION | ADDENDUM | SUPERSESSION | REVOCATION
  amendment_sequence: <int>          # 0 = ORIGINAL; +1 por registro de la familia
  supersedes_event_id: <entry_id | null>
  supersedes_instance_id: <decision_instance_id | null>

  # --- alcance, siempre materializado ---
  selection_mode: EXPLICIT_LIST | ALL_SNAPSHOT
  resolved_target_ids: [<ids>]                            # NUNCA "ALL"; ver §4
  target_set_hash: <sha256 de resolved_target_ids ordenada, separador \n>
  registry_hash_at_decision: <sha256 del target_registry en el instante de la firma>
  families_registry_hash: <sha256 de decision_families.yaml en ese instante>

  # --- acto humano ---
  decision: APPROVE | PARTIAL | REJECT | DEFER
  decision_origin: agent_proposed | human_confirmed
  proposed_by_id: <identidad del proponente>              # agent_proposed
  confirms_instance_id: <decision_instance_id | null>     # human_confirmed
  approved_by_id: <identidad real>                        # 422 si genérica
  approved_by_display_name: <nombre>
  recorded_by: <identidad del proceso que escribe>
  decision_date: <ISO-8601 UTC>
  recorded_at: <ISO-8601 UTC>
  reason: <texto — obligatorio en CORRECTION/REVOCATION/SUPERSESSION>

  # --- vigencia y contenido propio ---
  status: ACTIVE | SUPERSEDED | REVOKED
  payload: {<según payload_schema de la familia>}

  # --- procedencia ---
  provenance: NATIVE | RECONSTRUCTED_SNAPSHOT | MIGRATED_FROM_SYSTEM_A | MIGRATED_FROM_SYSTEM_B
  audit_event_id: <entry_id del evento único emitido>
```

### 3.1 Invariantes del schema (todas verificables por test)

| # | Invariante |
|---|---|
| I-1 | `decision_family` ∈ claves de `decision_families.yaml`. Si no, **422**. |
| I-2 | `selection_mode` ∈ `families[family].selection_modes`. Si no, **422**. |
| I-3 | `resolved_target_ids` **nunca vacía** y **nunca contiene la cadena `"ALL"`**. |
| I-4 | `target_set_hash == sha256("\n".join(sorted(resolved_target_ids)))`. Recomputado en cada lectura; discrepancia ⇒ registro corrupto ⇒ **no autorizado** (§3 del resolver). |
| I-5 | `decision_type=ORIGINAL` ⇒ `amendment_sequence == 0` ∧ `supersedes_* is null`. |
| I-6 | `decision_type ∈ {CORRECTION, SUPERSESSION, REVOCATION}` ⇒ `supersedes_instance_id` resuelve a un registro `ACTIVE` de la **misma familia**, y `reason` no vacía. |
| I-7 | `decision_type=ADDENDUM` ⇒ `supersedes_* is null` ∧ `amendment_sequence == max(familia) + 1`. |
| I-8 | `decision_origin=human_confirmed` ⇒ `approved_by_id` pasa `RESERVED_IDENTITIES`. **Una sola función de validación para ambos sistemas** (cierra A-4). |
| I-9 | `decision_origin=agent_proposed` ⇒ `approved_by_id is null` ∧ `status=ACTIVE` pero **no confiere autorización** (el resolver ignora las propuestas). |
| I-10 | `families[family].requires_human_confirmation` ⇒ ningún consumidor autoriza sin un registro `human_confirmed` que lo cubra. |
| I-11 | `decision_instance_id` es **único** en todo el almacén. Colisión ⇒ **409**. |
| I-12 | Un registro escrito emite **exactamente un** evento de auditoría, y `audit_event_id` apunta a él. |

> I-11 cierra A-10: el id deja de ser un `uuid4()` incontrolado y pasa a ser
> derivado y verificable. `MC-0001` se migra como `APPLICABILITY_MATRIX-2026-001`
> con `provenance=MIGRATED_FROM_SYSTEM_A` y su id original preservado en
> `payload.legacy_decision_id`.

---

## 4. Regla ALL → snapshot en la firma

`selection_mode=ALL_SNAPSHOT` **resuelve el conjunto en el instante de la
firma** y lo persiste en `resolved_target_ids` + `target_set_hash` +
`registry_hash_at_decision`. `"ALL"` no se almacena jamás como comodín
abierto.

```
firmar(family=D1, selection_mode=ALL_SNAPSHOT):
    registry            := leer(families[D1].target_registry)
    resolved_target_ids := sorted(ids de registry)          # materializado AQUÍ
    target_set_hash     := sha256("\n".join(resolved_target_ids))
    registry_hash_at_decision := sha256(bytes del registry)
```

**Consecuencia formal, y es el caso Part 211 exactamente:** un id incorporado
al registry *después* de la firma **no está cubierto**. No hay
interpretación, no hay ambigüedad, no hay que reconstruir intenciones — el
conjunto está escrito.

### 4.1 Lo que esto le habría hecho al caso real

D1 se firmó a las `00:15:15.595831Z` del 2026-07-29. Bajo esta regla habría
persistido:

```yaml
selection_mode: ALL_SNAPSHOT
resolved_target_ids:
  - ecfr_21cfr_part11
  - eu_gmp_annex11
  - mhra_gxp_di_guidance_2018
target_set_hash: <sha256 de esas tres, ordenadas>
registry_hash_at_decision: <sha256 de registry.json a las 00:15:15Z>
```

Y a las `02:25:06Z`, cuando `apply_source_registration()` añadió
`ecfr_21cfr_part211`, el `registry_hash_at_decision` habría dejado de
coincidir con el registry vigente. Eso **no invalida la decisión** —una
decisión firmada es un hecho histórico— pero **sí** dispara la señal que hoy
no existe:

```
REGISTRY_DRIFT_SINCE_DECISION = true
UNCOVERED_TARGET_IDS = [ecfr_21cfr_part211]
```

Esa señal es la que el resolver (§3 del plan) expone y la que la UI (§9.B)
muestra como *"1 fuente en el registry sin cobertura de decisión"*. El
sistema habría detectado el hueco **el mismo 29 de julio a las 02:25**, no
en una auditoría posterior.

### 4.2 `ALL_SNAPSHOT` no es reutilizable como plantilla

Firmar una segunda decisión `ALL_SNAPSHOT` de la misma familia **no** hereda
el snapshot anterior: vuelve a resolver contra el registry vigente en su
propio instante. Dos decisiones `ALL_SNAPSHOT` de fechas distintas pueden y
deben tener `resolved_target_ids` distintos.

---

## 5. Correcciones, adendos, supersesiones, revocaciones

### 5.1 Semántica

| Tipo | Qué hace | Efecto sobre la anterior | `resolved_target_ids` |
|---|---|---|---|
| **ORIGINAL** | primera decisión de la familia | — | conjunto inicial |
| **CORRECTION** | reemplaza el contenido de una decisión previa (un valor firmado por error) | la previa pasa a `SUPERSEDED` | **reemplaza** el conjunto |
| **ADDENDUM** | amplía el conjunto autorizado sin tocar la previa | la previa **sigue `ACTIVE`** | **se suma** al conjunto |
| **SUPERSESSION** | nueva ORIGINAL que reemplaza toda la familia | **todas** las previas pasan a `SUPERSEDED` | conjunto completamente nuevo |
| **REVOCATION** | retira cobertura de ids específicos | la previa sigue `ACTIVE`; los ids revocados salen de la cobertura efectiva | conjunto a **restar** |

### 5.2 Cobertura efectiva de una familia

```
cobertura(familia) =
      ⋃ { r.resolved_target_ids : r ∈ registros(familia)
                                  ∧ r.status == ACTIVE
                                  ∧ r.decision_origin == human_confirmed
                                  ∧ r.decision_type ∈ {ORIGINAL, CORRECTION,
                                                       ADDENDUM, SUPERSESSION} }
    − ⋃ { r.resolved_target_ids : r ∈ registros(familia)
                                  ∧ r.status == ACTIVE
                                  ∧ r.decision_origin == human_confirmed
                                  ∧ r.decision_type == REVOCATION }
```

Unión primero, resta después. Una `REVOCATION` gana siempre sobre un
`ADDENDUM` del mismo id, con independencia del orden cronológico — retirar
autorización es la operación segura y por tanto la que domina.

### 5.3 El histórico jamás se reescribe

`status` **no se edita in situ**. Cambiar una decisión previa a `SUPERSEDED`
se materializa como una **proyección derivada**, no como una modificación del
almacén append-only:

```
factory/layer9/decisions/decisions_v2.jsonl        ← append-only, inmutable
factory/layer9/decisions/_projection_v2.json       ← derivado, regenerable, .gitignored
```

La proyección se reconstruye desde cero recorriendo el JSONL. Si se borra, se
regenera idéntica. **Nada del sistema puede depender de la proyección para
autorizar sin poder rederivarla** — ese es el test de que no se convirtió en
una segunda fuente de verdad.

---

## 6. Ciclo propuesta → confirmación → aplicación

Se conserva el ciclo del Sistema A, ahora obligatorio para **todas** las
familias con `requires_human_confirmation: true`:

```
propose(family, targets, payload, rationale, proposed_by)
    → registro decision_origin=agent_proposed, status=ACTIVE
    → NO confiere autorización (invariante I-9)
    → NO escribe el artefacto objetivo

confirm(instance_id, confirmed_by)
    → valida que instance_id es agent_proposed de esa familia
    → valida confirmed_by contra RESERVED_IDENTITIES        ← nuevo (cierra A-4)
    → registro decision_origin=human_confirmed,
               confirms_instance_id=instance_id
    → resuelve el snapshot AQUÍ (§4) — no en la propuesta   ← nuevo
    → SIGUE sin escribir el artefacto objetivo

apply(instance_id)
    → exige human_confirmed + APPROVE + familia correcta
    → revalida precondiciones contra el estado ACTUAL
    → único punto de escritura
```

> **Por qué el snapshot se resuelve en `confirm` y no en `propose`:** la
> propuesta puede quedarse pendiente indefinidamente. Lo que el humano
> autoriza es lo que existe **cuando firma**, no lo que existía cuando el
> agente redactó. Si el registry cambió entre ambos, `confirm` debe mostrar
> el diff y exigir reconfirmación explícita. Es la misma lógica de
> `apply_source_registration()` l.229, que revalida unicidad *después* de la
> propuesta con el comentario *"entre la propuesta y la aplicacion el
> registry pudo cambiar"*.

---

## 7. Compatibilidad con decisiones históricas

### 7.1 Adaptador de lectura

Un adaptador proyecta los registros históricos de **ambos** sistemas al
schema nuevo. **No reescribe nada**; vive en
`factory/services/decision_legacy_adapter.py`.

#### Sistema A → schema nuevo

| Campo legacy | Campo nuevo | Regla |
|---|---|---|
| `action` | `decision_family` | vía `families[*].legacy_action`; sin mapeo ⇒ familia `LEGACY_UNMAPPED`, que **no autoriza nada** |
| `decision_id` | `payload.legacy_decision_id` | preservado literal |
| — | `decision_instance_id` | derivado `<familia>-<año>-<secuencia por timestamp>` |
| `decision` (`approve`/`reject`/`defer`/`conditional_approve`) | `decision` | `approve→APPROVE`, `reject→REJECT`, `defer→DEFER`, `conditional_approve→PARTIAL` |
| `decision_origin` | `decision_origin` | idéntico |
| `decided_by` | `approved_by_id` | solo si `human_confirmed` |
| `metadata.confirms_decision_id` | `confirms_instance_id` | resuelto al id nuevo |
| `metadata.source_id` | `resolved_target_ids` | lista de un elemento |
| — | `selection_mode` | `EXPLICIT_LIST` |
| — | `provenance` | `MIGRATED_FROM_SYSTEM_A` |

Los 9 registros mapean así:

| legacy | familia | tipo | targets |
|---|---|---|---|
| `03852b43` (test_dry_run, `agent_design`) | `LEGACY_UNMAPPED` | — | — (no autoriza) |
| `8661eebc` (`deploy` lab_qc) | `LEGACY_UNMAPPED` | — | — |
| `37646550` (corrección retroactiva de `8661eebc`) | `LEGACY_UNMAPPED` | CORRECTION | — |
| `ff640643` (`fs_v1_2_contradiction_resolution`) | `LEGACY_UNMAPPED` | — | — |
| **`MC-0001`** | `APPLICABILITY_MATRIX` | ORIGINAL | `["2.0"]` |
| `d5f72735` | `SOURCE_REGISTRATION` | ORIGINAL (`agent_proposed`) | `["ecfr_21cfr_part211"]` |
| `786464e0` | `SOURCE_REGISTRATION` | ORIGINAL (`human_confirmed`) | `["ecfr_21cfr_part211"]` |
| `fcf933e7` | `SOURCE_REGISTRATION` | CORRECTION (`agent_proposed`) | `["ecfr_21cfr_part211"]` |
| `caa2421d` | `SOURCE_REGISTRATION` | CORRECTION (`human_confirmed`) | `["ecfr_21cfr_part211"]` |

`LEGACY_UNMAPPED` es deliberado: cuatro decisiones históricas son de
despliegue y resolución de contradicciones, no de gobernanza del corpus.
Forzarlas a una familia sería fabricar cobertura. **Se proyectan como
legibles y no autorizantes.**

> Nota sobre `fcf933e7`/`caa2421d`: se tipifican como `CORRECTION` de
> `d5f72735`/`786464e0` porque su propio `rationale` dice *"REHACE el alta
> tras corregir `repo_relative()`"*. Esto cierra A-7 de la auditoría: los dos
> ciclos dejan de ser dos hechos sueltos y pasan a ser uno corregido.

#### Sistema B → schema nuevo

| legacy | familia | tipo | `selection_mode` | `resolved_target_ids` |
|---|---|---|---|---|
| `D1_regulatory_sources` | `D1` | ORIGINAL | `ALL_SNAPSHOT` | **reconstruido**, ver §7.2 |
| `D2_evidence_packs` | `D2` | ORIGINAL | `EXPLICIT_LIST` | ⚠ `approved_pack_ids` ausente ⇒ **conjunto vacío** |
| `D3_T039` | `D3` | ORIGINAL | `EXPLICIT_LIST` | ⚠ ausente ⇒ vacío |
| `D4_corpus_execution` | `D4` | ORIGINAL | `EXPLICIT_LIST` | ⚠ ausente ⇒ vacío |
| `D5_regenerate_qa_package` | `D5` | ORIGINAL | `EXPLICIT_LIST` | ⚠ ausente ⇒ vacío |

> **Hallazgo del ejercicio de migración (nuevo):** D2, D3, D4 y D5 se
> registraron **sin ningún objetivo**. `record_decision()` solo exige
> `approved_source_ids` para D1 (l.289-300); `approved_pack_ids` es opcional
> (l.301-302) y no se envió; D3/D4/D5 no tienen campo de objetivo en
> absoluto. Los cuatro registros dicen `APPROVE` **sin decir sobre qué**.
> Bajo el modelo nuevo, `resolved_target_ids` vacía viola I-3 y el registro
> **no es válido**. Consecuencia práctica: **la migración no puede validarlos**
> y los cuatro deben re-firmarse con objetivo explícito. Esto **amplía el
> camino crítico**: no basta con D1 + D1-A; D2/D3/D4/D5 también carecen de
> alcance materializado. Se refleja en G2' del plan de implementación.

### 7.2 Reconstrucción del snapshot de D1

La D1 histórica dice `"ALL"` sin snapshot. Se proyecta con
`selection_mode=ALL_SNAPSHOT` y `resolved_target_ids` **reconstruidos desde
el estado del registry en la fecha de la firma**, con evidencia:

```yaml
resolved_target_ids: [ecfr_21cfr_part11, eu_gmp_annex11, mhra_gxp_di_guidance_2018]
provenance: RECONSTRUCTED_SNAPSHOT
reconstruction_evidence:
  decision_signed_at: "2026-07-29T00:15:15.595831+00:00"
  method: "ids del registry con copied_at < decision_signed_at"
  registry_entries_considered:
    - {source_id: ecfr_21cfr_part11,          copied_at: "2026-07-17T19:32:45.681367+00:00"}
    - {source_id: eu_gmp_annex11,             copied_at: "2026-07-17T19:32:45.681973+00:00"}
    - {source_id: mhra_gxp_di_guidance_2018,  copied_at: "2026-07-17T19:32:45.689035+00:00"}
    - {source_id: ecfr_21cfr_part211,         copied_at: "2026-07-29T02:25:06.536379+00:00"}  # EXCLUIDO: posterior
  corroborating_audit_events:
    - "factory_audit.jsonl:18574 — regulatory_source_registered ecfr_21cfr_part211 @ 02:25:06.554118Z"
  confidence: HIGH
  confidence_basis: >
    Los cuatro copied_at son inequívocos y el margen es de 2 h 10 min, no de
    segundos. Ningún evento de auditoría registra alta o baja de fuente entre
    2026-07-17T19:32:45Z y 2026-07-29T02:11:29Z.
```

**La reconstrucción NO sustituye a la Corrección D1 formal (§9.A).** Sirve
para *leer el histórico sin ambigüedad*; la cobertura operativa sigue
exigiendo el acto humano. El resolver marca todo lo que se apoye en
`provenance=RECONSTRUCTED_SNAPSHOT` con
`coverage_basis=RECONSTRUCTED_PENDING_FORMAL_CORRECTION`, que **no** habilita
conclusiones formales.

---

## 8. Migración de datos

### 8.1 Script

`factory/scripts/ops/migrate_decisions_to_v2.py`

```
python3 -m factory.scripts.ops.migrate_decisions_to_v2 --dry-run    # por defecto
python3 -m factory.scripts.ops.migrate_decisions_to_v2 --apply --confirmed-by "<nombre real>"
```

| Propiedad | Garantía |
|---|---|
| Entradas | `decisions.jsonl` (9), `w5_human_decisions.jsonl` (5) |
| Salida | `decisions_v2.jsonl` (**archivo nuevo**) |
| Escritura sobre las entradas | **cero** — se abren en modo lectura |
| Idempotencia | re-ejecutar produce un fichero byte-idéntico |
| Eventos de auditoría | **uno solo**: `layer9_decision_store_migrated` con `{source_files, sha256 de cada uno, registros_migrados, registros_LEGACY_UNMAPPED, registros_invalidos, sha256_salida}` |
| Modo por defecto | `--dry-run`: imprime el resultado y **no escribe nada** |

### 8.2 Verificación

| # | Verificación | Criterio |
|---|---|---|
| V-1 | Conteo | `14 registros de entrada → 14 proyectados`, ninguno perdido |
| V-2 | Integridad de entradas | sha256 de `decisions.jsonl` y `w5_human_decisions.jsonl` **idénticos antes y después** |
| V-3 | Invariantes | los 14 proyectados pasan I-1…I-12, **salvo los 4 documentados en §7.1** (D2/D3/D4/D5 sin targets), que se emiten con `status=INVALID_PENDING_RESIGNATURE` y **no autorizan nada** |
| V-4 | Cobertura | `cobertura(D1) == {part11, annex11, mhra}` y `ecfr_21cfr_part211 ∉ cobertura(D1)` |
| V-5 | Determinismo | dos ejecuciones consecutivas ⇒ mismo sha256 de salida |
| V-6 | Reversibilidad de la proyección | borrar `_projection_v2.json` y regenerarlo ⇒ idéntico |

### 8.3 Rollback

```
rm factory/layer9/decisions/decisions_v2.jsonl
rm factory/layer9/decisions/_projection_v2.json
```

Es todo. Las entradas nunca se tocaron, así que el rollback es la eliminación
de dos ficheros derivados. El evento `layer9_decision_store_migrated` queda en
la cadena (correcto: la migración ocurrió y se revirtió; ambos son hechos).
Se registra la reversión con un segundo evento
`layer9_decision_store_migration_reverted` — **nunca** borrando el primero.

### 8.4 Convivencia durante la transición

Durante las fases G1–G2 conviven los tres almacenes. Regla de precedencia,
**fail-closed**:

```
autorización = resolver(decisions_v2.jsonl)
```

y **solo eso**. Los almacenes legacy quedan como fuente de la migración y
como histórico legible. Ningún consumidor nuevo los lee directamente. Los
escritores legacy (`decision_log.write_decision`,
`w5_human_decisions.record_decision`) se marcan `@deprecated` y emiten un
`DeprecationWarning`; se retiran en la fase G8, no antes — retirarlos mientras
la UI vieja siga viva rompería la única superficie humana existente.

---

## 9. Qué cierra este diseño, punto por punto

| Hallazgo | Cómo lo cierra |
|---|---|
| A-1 | Generaliza el ciclo propose/confirm/apply a todas las familias |
| A-2 | `ALL_SNAPSHOT` materializado + `REGISTRY_DRIFT_SINCE_DECISION` |
| A-4 | `RESERVED_IDENTITIES` en una única función, aplicada por I-8 a ambos sistemas |
| A-8 | La aprobación de packs es familia `D2`, no un `MC-0002` nuevo |
| A-9 | El alcance "solo Part 211" pasa de `rationale` libre a `payload.scope_decision` estructurado |
| A-10 | `decision_instance_id` derivado y único (I-11), no `uuid4()` libre |
| **nuevo** | D2/D3/D4/D5 sin objetivo quedan expuestos como `INVALID_PENDING_RESIGNATURE` en vez de pasar por aprobados |

## 10. Lo que este diseño NO hace

- No registra ninguna decisión.
- No migra nada: el script se diseña aquí y se ejecuta en G1.
- No borra ni edita `decisions.jsonl` ni `w5_human_decisions.jsonl`.
- No decide el alcance 210/211 — ya está decidido (A-9); solo lo hace visible.
- No sustituye la Corrección D1 formal: la reconstrucción es para leer, no
  para autorizar.
