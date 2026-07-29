# G1 — Invariantes para el checkpoint humano

**Fecha:** 2026-07-29 · **Fase:** G1 completa (G1.1–G1.17)
**Rango de revisión:** `bcf9344` … `70b8508` (12 commits)
**Estado del sistema:** Gate 0 `PASS=6 WARN=2 FAIL=0` · suite `1876 passed / 1 skipped / 1 xfailed`

**Nada se ha migrado.** `factory/layer9/decisions/decisions_v2.jsonl` y
`factory/registry/artifact_versions.jsonl` **no existen**, y hay dos tests que
congelan esa ausencia. La migración (`--apply`) es lo primero de G2.

Este documento no repite los specs. Enumera lo que el sistema **garantiza
hoy**, dónde se aplica cada garantía y qué test la sostiene, para que la
revisión pueda comprobarla en vez de creerla. La sección §8 es la más
importante: lo que **no** está garantizado.

---

## 1. Cómo verificar cada fila

Cada invariante trae `archivo:símbolo` y el test que la prueba. Para una
comprobación rápida de que la garantía es real y no documental:

```bash
# 1. correr el guardián de una invariante concreta
.venv/bin/python3 -m pytest factory/tests/<test> -q -k "<nombre>"

# 2. mutar la línea que la implementa y ver que el test cae
```

Es como se verificó cada fase: **48 mutaciones a lo largo de G1** (3 en G1.10,
45 en G1.11–G1.17). **Tres sobrevivieron** —dos en G1.12 y una en G1.14— y las
tres destaparon huecos reales en mis tests, no en el código; están cerradas
(§11).

---

## 2. Modelo de decisión — invariantes de registro

Se aplican en `factory/services/decision_store_v2.py::validate_record`, que
**no lanza**: devuelve el detalle. El resolver la usa para marcar un registro
`INVALID` sin descartarlo en silencio; el escritor la usa para rechazar con 422.

| # | Invariante | Dónde | Test |
|---|---|---|---|
| I-0 | El registro valida contra `decision_record_v1.json`, y si no, no se sigue comprobando nada más (leería campos ausentes) | `validate_record` l.202 | `test_decision_model_v2.py` |
| I-1 | La familia está declarada en `decision_families.yaml` | l.211 | ídem |
| I-2 | El `selection_mode` está permitido para esa familia (D2 prohíbe `ALL_SNAPSHOT` **a propósito**) | l.214 | ídem |
| I-3 | Una decisión ACTIVE declara su alcance: `resolved_target_ids` no vacía | l.231 | ídem |
| I-4 | `target_set_hash` **recomputa** sobre `resolved_target_ids` | l.234 | ídem |
| I-5 | `ORIGINAL` no supersede a nada y tiene `amendment_sequence=0` | l.239 | ídem |
| I-6 | `CORRECTION`/`SUPERSESSION`/`REVOCATION` exigen `supersedes_instance_id` **resoluble**, de la **misma familia**, y `reason` no vacío | l.245 | ídem |
| I-7 | `ADDENDUM` **amplía, no supersede**: no puede referenciar `supersedes_*`, y exige `amendment_sequence>=1` | l.262 | ídem |
| I-8 | `human_confirmed` exige identidad real (ver §6) | l.269 | `test_governance_endpoints.py` |
| I-9 | `agent_proposed` **no puede traer** `approved_by_id` — una propuesta no firma | l.276 | ídem |
| I-10 | `RECONSTRUCTED_SNAPSHOT` exige `reconstruction_evidence` | l.279 | `test_source_lifecycle.py` |
| I-11 | `decision_instance_id` tiene la forma `<FAMILIA>-<año>-<nnn>` y empieza por su propia familia | l.282 | `test_decision_model_v2.py` |
| I-12 | Escribir un registro emite **exactamente un** evento y `audit_event_id` apunta a él | `append_record` l.338 | `test_governance_endpoints.py::test_u2_*` |

**Reglas estructurales del almacén, no negociables:**

- **Append-only.** `status` nunca se edita in situ. La vigencia se **deriva**
  recorriendo el JSONL (`project_status`) y se regenera idéntica desde cero.
  Nada puede depender de una proyección persistida que no se pueda rederivar.
- **`"ALL"` no se almacena jamás.** `resolved_target_ids` siempre
  materializada. Ese comodín abierto es la causa próxima de que Part 211
  quedara fuera de una D1 que decía cubrirlo todo.
- **Excepción declarada:** la familia `LEGACY_UNMAPPED` (`never_authorizes:
  true`) está exenta de I-3 e I-8. No es una puerta trasera — el resolver
  deniega esa familia antes de mirar ningún registro. Existe para que cuatro
  decisiones históricas que no son de gobernanza del corpus sigan siendo
  **legibles** sin obligar a inventarles un alcance que nadie firmó.

---

## 3. Resolver — la única superficie de lectura

`factory/core/decision_scope_resolver.py`. Mismo patrón que `path_policy`:
todos preguntan aquí, nadie implementa su propia versión.

| # | Regla | Cómo se garantiza |
|---|---|---|
| R-1 | **Estar en un registry NO concede autorización** | `resolve()` compara contra conjuntos materializados, nunca contra el registry |
| R-2 | Fuente no cubierta ⇒ no reverificable ∧ pack no usable ∧ conclusión formal no permitida | los cinco consumidores (§4) |
| R-3 | Ningún consumidor implementa su propia lectura | `test_decision_resolver_no_bypass.py::test_t23` |
| R-4 | **Fail-closed.** Almacén ausente, JSON ilegible, invariante violada o familia desconocida ⇒ `authorized=False`, sin excepción que un `try/except` del llamador pueda convertir en "siga adelante" | `test_t09_missing_store_denies_without_raising` |
| R-5 | **Read-only absoluto.** No escribe auditoría, no muta, no cachea en disco | `test_resolver_never_writes_audit` (por AST: el módulo no importa `audit_writer`) |
| R-6 | **No interpreta intenciones.** No infiere que `"ALL"` incluya lo posterior, no deduce por semejanza de ids, no aplica prefijos | `test_t01_source_registered_after_all_snapshot_is_not_covered` |
| R-7 | **No conoce a sus consumidores.** Cero ramas `if caller == ...` | la política vive en el registro de familias |

**Lo que otorga cobertura, y sólo eso** (`GRANTING_DECISIONS`):

```
status == ACTIVE
  ∧ decision_origin == human_confirmed
  ∧ decision_type ∈ {ORIGINAL, CORRECTION, ADDENDUM, SUPERSESSION}
  ∧ decision       ∈ {APPROVE, PARTIAL}          ← añadido en G1.15
  ∧ provenance     != RECONSTRUCTED_SNAPSHOT     (reconstruir ≠ tener la firma)
  − los ids retirados por cualquier REVOCATION vigente
```

> **Defecto real cerrado en G1.15.** Hasta entonces el resolver miraba
> `decision_type` y **nunca** `decision`: un registro con `decision="REJECT"` y
> `decision_type="ORIGINAL"` pasaba las doce invariantes y **autorizaba**. Un
> rechazo firmado concedía exactamente lo que rechazaba.
> Test: `test_only_approve_and_partial_grant_coverage` (los cuatro veredictos).

`REVOCATION` es la única que **no** se filtra por `decision`: revocar
restringe, y restringir es la operación segura.

---

## 4. Los cinco consumidores — dónde se aplica de verdad

Un resolver que existe y nadie llama no protege nada. Ese era el estado que la
auditoría encontró: `approved_source_ids` con 17 ocurrencias en 4 archivos y
**cero lecturas para autorizar**.

| # | Consumidor | Qué exige | Si no está autorizado | Fase |
|---|---|---|---|---|
| C-1 | `source_currency_checker` | `D1(source_id)` **antes de `_http_get`** | `REVERIFICATION_NOT_AUTHORIZED`, `reachable=None` (no `False`: no se intentó) | G1.7 |
| C-2 | `requirement_catalog_loader` + `provisional_evidence_model` | `D2(requirement_id)` ∧ `D1(entry.source_id)` | el requisito sale **NO EVALUADO**, nunca incumplido | G1.8 |
| C-3 | `verified_pipeline` (planner) | cobertura **antes** de `pre_inference_filter` | `EVALUATION_INCOMPLETE`, **nunca `DOCUMENTATION_GAP`** | G1.9 |
| C-4 | `build_source_baseline_allowlist` | `D3(file_id)` ∧ `D1(cada fuente)` | entra a la baseline **provisional con su limitación declarada** | G1.10 |
| C-5 | `quality_gate_runner` (G15) + `release_manager` | `coverage_report(D1..D5).uncovered == ()` ∧ excepción por cada fork | **BLOCKED** con los ids listados; `DecisionCoverageBlocked` → HTTP 423 | G1.11 |

**Tres distinciones que conviene revisar por separado**, porque son lo que
diferencia este diseño de un simple "if autorizado":

1. **No estar autorizado a mirar ≠ incumplir.** C-3 emite
   `EVALUATION_INCOMPLETE` y nunca `DOCUMENTATION_GAP`. Un requisito que nadie
   nos autorizó a evaluar no es un requisito incumplido.
2. **El inventario no se gobierna; la baseline formal sí.** C-4 sigue
   inventariando sin consultar decisiones — negarse a enumerar qué ficheros
   existen dejaría a la fábrica sin saber qué hay. Lo gobernado es qué puede
   sustentar una conclusión **formal**.
3. **La cobertura se comprueba antes de la red y antes del presupuesto.** No
   después. Una fuente no autorizada no debe generar ni un byte de tráfico
   saliente ni consumir un token de inferencia.

**Guardias que impiden el bypass** (`test_decision_resolver_no_bypass.py`, todo
por AST — un `grep` se esquiva concatenando cadenas):

| T- | Qué impide |
|---|---|
| T-20/21 | Un consumidor declarado que no importa **y llama** al resolver |
| T-22 | Cualquier módulo fuera de `STORE_OWNERS` abriendo un almacén de decisiones |
| T-23 | Cualquier módulo definiendo su propia noción de "la decisión lo cubre" |
| T-24 | Que el registro de familias y los consumidores cableados diverjan |

T-24 sigue en `xfail(strict=True)` **a propósito**: quedan cinco consumidores
declarados sin módulo (§9). `strict` significa que en cuanto se cablee el
último, la suite **exigirá** retirar el marcador. Es un andamio que se retira
solo.

---

## 5. Fuentes, artefactos y auditoría — no colapsar dimensiones

El hilo común de G1.12–G1.14: **una dimensión en verde no es una conclusión.**

### 5.1 Ciclo de vida de fuente (G1.12)

```
FORMAL_USE_ELIGIBILITY = COPY_HASH_INTEGRITY        (sha256 RECALCULADO, no el campo)
                       ∧ OFFICIAL_ORIGIN_VERIFICATION
                       ∧ REGULATORY_CURRENCY
                       ∧ HUMAN_DECISION_COVERAGE
```

Ninguna de las cuatro por separado habilita una conclusión formal, y ninguna
combinación de tres tampoco. **Ninguna lee a otra** — verificado por AST
(`test_l01_no_dimension_function_calls_another`).

- Los valores son **enums, no booleanos**. El origen de Part 211 es **ámbar**
  (`NOT_COMPARABLE_FIRST_INGESTION`): en una primera ingesta no hay hash previo
  con el que comparar, y `apply_source_registration()` rechaza por código
  declarar lo contrario. **El ámbar se cura con una reverificación; el rojo de
  la cobertura, con una firma.** Aplanarlos a `False` perdería eso.
- **Orden de derivación deliberado:** la cobertura humana se evalúa **antes**
  que la vigencia. Invertido, una fuente sin firmar aterriza en
  `REVERIFICATION_EXPIRED` — un estado que invita a salir a la red por algo
  que nadie autorizó.
- **Estado real hoy:** las **cuatro** fuentes en
  `REGISTERED_PENDING_AUTHORIZATION`. La fábrica no tiene ninguna fuente
  formalmente autorizada; las tres antiguas lo parecían porque D1 decía `"ALL"`.

### 5.2 Versionado de artefactos (G1.13)

```
sha256 cambia  ⟺  version cambia  ⟺  existe una decisión ACTIVE que la aprueba
```

Las tres direcciones, con un caso real detrás de cada una:

| Dirección | Caso |
|---|---|
| hash cambia ⇒ versión cambia | `requirements.yaml` declara `1.0` con hash distinto del congelado en la calificación |
| versión cambia ⇒ hash cambia | "versionar" sin tocar nada para simular una revisión |
| versión cambia ⇒ hay decisión | `matrix_version: "2.1"` mientras `MC-0001` sólo cubre la `2.0` |

- La tercera **pregunta al resolver**, no al campo `approved_by_decision` del
  propio registro: un registro puede nombrar una decisión revocada, superada o
  nunca confirmada, y fiarse del campo sería dejar que el artefacto declare su
  propia aprobación.
- El hash es **semántico** (`yaml.safe_load` + `sort_keys`), y el campo de
  versión **siempre se excluye** — si no, cambiarlo cambiaría el hash y la
  invariante sería trivialmente cierta.
- **`enumerate_artifacts()` enumera el mundo, nunca una lista congelada.** Es
  el único patrón que ya había funcionado: el glob de
  `model_qualification_gate` es la razón de que el fingerprint dejara de
  coincidir solo cuando apareció `cgmp211_prompts.yaml`.
- **Punto de revisión:** el hash canónico **difiere a propósito** del hash
  crudo (`a83c8168…`) que usa el fingerprint de calificación. Responden a
  preguntas distintas — "¿cambió el fichero?" vs "¿cambió lo que significa?".
  Hay un test que lo declara para que nadie "arregle" uno para que cuadre con
  el otro.

### 5.3 Cadena de auditoría (G1.14)

Cinco dimensiones separadas. `part11_compliant` pasó de `bool` a **enum**:

```
COMPLIANT                            hash_errors=0 ∧ chain_errors=0 ∧ log_count>0
ACCEPTED_WITH_DOCUMENTED_EXCEPTION   fork conocido Y SOLO el conocido
                                       ∧ decisión AUDIT_EXCEPTION ACTIVE que lo cubre
NOT_DETERMINED                       cualquier otro caso, incluido hash_errors>0
```

> **La regla que se supersedió.** Antes: *"fork concurrente ⇒ contenido
> auténtico ⇒ Part-11 cumplido"*. Era **correcta en su análisis técnico** y
> **equivocada en su conclusión**: contenido auténtico es *una* de las
> condiciones de Part 11 (§11.10(e)); la continuidad verificable de la
> secuencia es otra, y está rota. Lo que esa regla debió producir es
> *"contenido auténtico, continuidad rota, conformidad no determinada"*.

- **Cambiar el TIPO era el punto.** Con `bool`, todo lector seguía compilando y
  mintiendo al revés, porque `"NOT_DETERMINED"` es *truthy*. Se encontraron
  **dos** lectores que ramificaban por veracidad y habrían pasado en silencio a
  "conforme": el emisor de riesgo de `api/routes/status.py` y el sello de
  Mission Control. Los dos corregidos a comparación exacta.
- **`hash_errors > 0` no es exceptuable por diseño**: es corrupción de
  contenido, no de enlace, y ninguna firma humana la convierte en otra cosa.
- **El baseline no puede ser una alfombra.** Meter un fork al JSON deja de
  contarlo como *nuevo* y pasa a contarlo como *conocido sin respaldo*.
  Silenciarlo exige una firma, no un editor de texto.
- **Estado real hoy:** `accepted_by_decision: null`. Nada aceptado.

---

## 6. Identidad — una sola lista (A-4)

`factory/core/identity_policy.py`, que **no importa nada de la fábrica** a
propósito: validar un nombre no puede exigir arrastrar `jsonschema`.

**Dos actos, dos validaciones, y no es una rendija:**

| Acto | Función | Regla |
|---|---|---|
| **Firmar** (autoriza) | `validate_identity` | rechaza la lista de 19 reservadas; `human` no identifica a nadie |
| **Proponer** (no autoriza) | `validate_actor` | sólo exige no vacío |

Un agente propone legítimamente, y `layer8_agent` **está** en la lista de
reservadas precisamente porque no puede firmar. Exigirle nombre humano al
proponente produciría un campo falso o un agente haciéndose pasar por una
persona; ninguna de las dos mejora la trazabilidad. **Lo que impide el bypass
es que una propuesta no otorga cobertura**, no que mienta sobre su autor.

> **Hallazgo de G1.15.** A-4 estaba **medio cerrado y parecía cerrado.** G1.1
> escribió la función canónica dentro de `decision_store_v2` con el comentario
> "se centraliza AQUI". No se centralizó: quedaban **ocho** conjuntos de
> identidades reservadas y **no coincidían** — `admin` se rechazaba al firmar en
> Capa 9 y se aceptaba al aprobar un deployment; `user` y `factory` sólo
> estaban reservados en la consola de pruebas.

---

## 7. Superficie humana — endpoints y UI

| # | Regla | Test |
|---|---|---|
| U-1 | Todo GET es de solo lectura: jamás escribe auditoría ni promueve nada | `test_u1_*` |
| U-2 | Cada POST emite **exactamente un** evento | `test_u2_*` |
| U-3 | 422 identidad genérica, con la función única | `test_u3_*` |
| U-4 | 409 por duplicación **y** por `state_hash` obsoleto | `test_u4_*` |
| U-5 | **Registrar ≠ ejecutar.** La leyenda viaja con los datos, no sólo en el HTML | `test_u5_*` |
| U-6 | Backup del frontend antes de tocarlo | `test_u6_*` (skip si falta el dir, que está gitignorado) |
| U-7 | Lo bloqueado se muestra **deshabilitado con el motivo**, jamás oculto | `test_u7_*` |
| U-8 | Todo valor de gobernanza viaja con su procedencia | los seis paneles |

**El control optimista merece atención en la revisión.** Dos pestañas abiertas
firmando sobre datos que ya no existen **es el fork de la cadena de auditoría
trasladado a la capa humana** — dos lectores con el estado cacheado, uno
escribe y el otro firma lo que recordaba. Un POST sin `state_hash` se rechaza:
es un cliente que no leyó, no uno al día.

**Rechazar añade el rechazo; nunca borra la propuesta.** Quien audite tiene que
poder ver qué se propuso y que se dijo que no.

**Los seis paneles renderizan, incluidos los cuatro cuyo gate no está abierto.**
Un panel ausente es un bloqueo inexplicable. «Aceptar» en la excepción de
auditoría está deshabilitado mientras falten 4 de las 5 medidas preventivas:
aceptar una excepción cuya prevención no está implementada es aceptar que
vuelva a pasar. «Rechazar» sí está habilitado — es un final legítimo.

---

## 8. Lo que NO está garantizado

Esta es la sección que conviene leer con más atención. Cada punto es una
limitación **real y declarada**, no un olvido.

1. **Ninguna fuente está formalmente autorizada.** Las cuatro en
   `REGISTERED_PENDING_AUTHORIZATION`. El resolver deniega todo, y eso es
   correcto: es el estado que el sistema debía haber reportado desde el
   principio. Se mueve con G2.
2. **G15 está en rojo y bloquea TODA release, no sólo la regulatoria.** Es el
   diseño entre G1.11 y G2, pero el radio de impacto alcanza a cualquier
   solución custom. Ya se avisó y no hubo objeción; si eso no es lo deseado,
   es una línea de código acotarlo.
3. **`PART11_COMPLIANCE = NOT_DETERMINED` indefinidamente** si el fork no se
   acepta. Es un final legítimo del proceso, no un fallo del diseño.
4. **28 artefactos sin `version_record`.** La invariante de versionado no puede
   detectar un cambio silencioso hasta que exista una línea base. El bootstrap
   es de G4 y está en dry-run.
5. **`flock` protege un solo host.** Si el almacén se compartiera por NFS, el
   diseño no basta. Supuesto explícito.
6. **Un escritor que no pase por `write_event()`** (script ad-hoc, `echo >>`)
   no está impedido. `writer_pid`/`writer_host` es de G7.
7. **`write_event` puede fallar en silencio** (`return {"error": ...}`). G7.
8. **El Golden Dataset se hashea por AST**, lo que es más estricto de lo
   necesario (renombrar una variable local dispara versión) y nunca más laxo.
   Limitación declarada en el código.
9. **D4 y D5 no tienen `target_registry`**, así que su cobertura no es
   comparable contra un conjunto. El gate lo declara
   `NO_REGISTRY_TO_COMPARE` en vez de darlas por cubiertas.

---

## 9. Deuda declarada y congelada por test

Se enumera en vez de ocultarse: la lista **es** el trabajo que queda, y
encogerla es el progreso. Cada una tiene un test que impide que crezca en
silencio.

| Deuda | Tamaño hoy | Se cierra en | Congelada por |
|---|---|---|---|
| Consumidores declarados sin módulo cableado | 5 | G1.16+/G8 | `test_t24_*` (`xfail(strict)`) |
| Superficies con lista de identidades propia | 5 | G8 | `test_u3_the_debt_list_only_shrinks` |
| Lectores directos del almacén legacy | 1 | G8 | `test_transitional_direct_readers_is_debt_not_a_loophole` |
| Vista W5 legacy conviviendo con la nueva | 1 | G8 | `test_the_legacy_w5_view_is_not_removed` |

Los cinco consumidores sin cablear: `model_qualification_gate`,
`package_regeneration`, `run_driver`, `source_registration_apply`,
`applicability_resolution`.

---

## 10. Gate 0 — los seis pasos y sus criterios

| Paso | FAIL cuando | WARN cuando |
|---|---|---|
| 1/6 py_compile | error de sintaxis | — |
| 2/6 pytest | cualquier test falla | resultado indeterminado |
| 3/6 audit chain | `hash_errors>0` · `new_forks>0` · fork histórico sin firma **desde G7** | fork histórico sin firma (hoy) · excepción vigente |
| 4/6 factory_status | hay FAILs | hay WARNs |
| 5/6 validation_evidence | contenido prohibido trackeado | — |
| 6/6 artifact versions | las tres inconsistencias de trazabilidad | artefacto sin `version_record` |

**Dos decisiones de calibración que conviene validar:**

- **`HISTORICAL_FORK_PRESENT` es WARN hasta G7, no FAIL.** Antes de G7 la
  excepción humana no puede existir, y dejar Gate 0 en rojo permanente hasta
  entonces garantiza que se deje de leer. Un gate siempre rojo no informa de
  nada. El cambio de fase es **una variable**
  (`FORK_HISTORICO_ES_FAIL`), y hay un test que la activa para probar que la
  promesa no es un comentario.
- **Sin `version_record` es WARN, no FAIL.** Hoy los 28 están sin registro y el
  bootstrap es de G4. Un FAIL sería rojo por una tarea pendiente, no por un
  defecto.

Los dos veredictos están extraídos a funciones bash y se prueban con valores
inyectados (`SELFCHECK_LIB_ONLY=1`): **un Gate 0 cuya rama de FAIL nadie ha
ejecutado nunca es un gate que nadie ha verificado.**

---

## 11. Defectos reales encontrados durante G1

Cuatro de los seis estaban en mi propio trabajo previo de esta misma serie.
Se listan porque son el mejor indicador de dónde mirar en la revisión.

| Fase | Defecto | Cómo salió |
|---|---|---|
| G1.10 | D3 declaraba `documents[].document_id`, estructura **inexistente** → `coverage_report(D3)` habría resuelto a nada en silencio | al implementar contra el artefacto real |
| G1.11 | Bloqueaba con `uncovered_ids`, pero `coverage_report` **resta** lo reconstruido y lo revocado → cobertura 100% reconstruida **pasaba el gate** | su propio test |
| G1.12 | `RECONSTRUCTED`→`COVERED` no rompía nada: el almacén real está vacío y **ningún test alcanzaba esa rama** | mutación superviviente |
| G1.14 | Arrastré `jsonschema` a `verify_chain()`, rompiendo los dos scripts de shell que lo llaman con el `python3` del sistema | **Gate 0** |
| G1.15 | **Un rechazo firmado otorgaba cobertura** | al construir el endpoint de rechazo |
| G1.15 | A-4 medio cerrado y con apariencia de cerrado: ocho listas en desacuerdo | al buscar dónde poner la validación |

**Dos tests míos también estaban mal**, y merecen la misma atención:

- El de escapado de la UI usaba una **regex sobre el fuente**: 21 falsos
  positivos y cero hallazgos reales. Sustituido por render con **payload
  hostil**. *Una guardia con falsos positivos estructurales se acaba borrando
  entera, y con ella la protección real.*
- El de backup U-6 afirmaba la presencia de un artefacto **gitignorado**:
  pasaba en esta máquina y fallaría en un clon limpio.

---

## 12. Qué se pide de esta revisión

1. **Confirmar o corregir la calibración de §10** (los dos WARN que podrían
   ser FAIL, y al revés).
2. **Decidir sobre el punto 2 de §8**: si G15 debe bloquear toda release o
   sólo las que empaquetan material regulatorio.
3. **Autorizar G2**, cuyo primer paso es `migrate_decisions_to_v2.py --apply`
   — la primera acción de toda la serie que **escribe** en el almacén nuevo.

Lo que **no** se pide en este checkpoint: aceptar la excepción de auditoría
(es G7, y sus medidas preventivas no están implementadas), ni aprobar ningún
Evidence Pack, ni versionar ningún artefacto.
