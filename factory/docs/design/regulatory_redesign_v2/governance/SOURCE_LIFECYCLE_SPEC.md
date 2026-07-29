# SOURCE_LIFECYCLE_SPEC — §4 del plan (+ desviación DEV-W5-001)

**Estado:** DISEÑO. No implementado. No promueve ningún estado.
**Depende de:** `DECISION_SCOPE_RESOLVER_SPEC.md`.
**Cierra:** A-2 (fuente autorizada para existir pero no para su ciclo de
vida), y da nombre formal a lo ocurrido con Part 211.

---

## 1. Estados hoy y por qué no bastan

`factory/regulatory/sources/registry.json` maneja hoy tres campos
independientes que se leen como si fueran uno:

```
local_integrity_status     = PASS            (las 4 fuentes)
official_origin_status     = VERIFIED_AGAINST_PRIOR_KNOWN_HASH_2026-07-06_INGESTION   (3)
                           | FIRST_INGESTION_NO_PRIOR_KNOWN_HASH_TO_COMPARE           (part211)
regulatory_currency_status = pending_reverification    (las 4)
```

Y el catálogo de requisitos maneja un cuarto, derivado a mano:

```
source_verification_status = PENDING_REVERIFICATION | LOCAL_CANONICAL_COPY_VERIFIED
```

El problema no es que haya cuatro campos: es que **ninguno expresa la
cobertura humana**, y que `source_verification_status` se usa como si fuera
un veredicto global cuando solo refleja la vigencia regulatoria. Part 211
tiene `local_integrity_status=PASS` —su hash se recalculó y coincide— y eso
en un informe se lee como "verificada", cuando lo único demostrado es que el
fichero no se corrompió desde que se copió.

---

## 2. Cinco dimensiones ortogonales

**Nunca colapsarlas en un solo flag.** Cada una responde a una pregunta
distinta y puede estar en verde con las demás en rojo.

| Dimensión | Pregunta | Cómo se determina | Valor hoy (Part 211) | Valor hoy (las otras 3) |
|---|---|---|---|---|
| `COPY_HASH_INTEGRITY` | ¿la copia local sigue siendo la que se ingirió? | recalcular sha256 del fichero canónico vs. `sha256_copy` | **VERDE** | **VERDE** |
| `OFFICIAL_ORIGIN_VERIFICATION` | ¿proviene de la URL oficial primaria y se comparó contra algo? | `official_origin_status` | **ÁMBAR** — `FIRST_INGESTION_NO_PRIOR_KNOWN_HASH_TO_COMPARE`: no hubo nada contra qué comparar | **VERDE** |
| `REGULATORY_CURRENCY` | ¿el texto sigue vigente hoy? | `source_currency_checker.check_source()` + `reverification_due` | **ROJO** — `pending_reverification`, `reverification_due=None` | **ROJO** |
| `HUMAN_DECISION_COVERAGE` | ¿un humano firmó que esta fuente se use, con qué cadencia y bajo qué autoridad? | `resolve("D1", source_id)` | **ROJO** — `NOT_COVERED` | **ROJO** — `RECONSTRUCTED_PENDING_FORMAL_CORRECTION` |
| `FORMAL_USE_ELIGIBILITY` | ¿puede sustentar una conclusión formal? | **conjunción de las cuatro** | **ROJO** | **ROJO** |

```
FORMAL_USE_ELIGIBILITY = COPY_HASH_INTEGRITY
                       ∧ OFFICIAL_ORIGIN_VERIFICATION
                       ∧ REGULATORY_CURRENCY
                       ∧ HUMAN_DECISION_COVERAGE
```

`FORMAL_USE_ELIGIBILITY=true` es la **única** condición que habilita
conclusiones formales sobre esa fuente. Ninguna de las cuatro por separado lo
hace, y ninguna combinación de tres tampoco.

### 2.1 Por qué `OFFICIAL_ORIGIN_VERIFICATION` de Part 211 es ámbar y no rojo

`apply_source_registration()` (l.252-257) **rechaza** declarar
`VERIFIED_AGAINST_PRIOR_KNOWN_HASH` en una primera ingesta:

> *"official_origin_status afirma … pero es una fuente NUEVA: no existe hash
> previo gobernado con el que comparar. Valor honesto para una primera
> ingesta: FIRST_INGESTION_NO_PRIOR_KNOWN_HASH_TO_COMPARE"*

El valor es **honesto y forzado por código**, no un descuido. La fuente vino
de la URL oficial de la API versioner de eCFR con fecha fijada
(`2026-07-01`), lo que es una procedencia mejor que la de un texto
consolidado sin versión. Lo que falta es un **segundo punto de comparación en
el tiempo**, que solo puede existir tras la primera reverificación. Por eso
es ámbar: se resuelve solo con el paso del tiempo y una reverificación, no
con una corrección.

### 2.2 Regla anti-colapso

Ningún informe, endpoint, UI o artefacto puede exponer un único booleano
"fuente verificada". Si un consumidor necesita un resumen, expone las cinco.
Test: `test_no_collapsed_source_verified_flag` — ningún módulo define un
campo cuyo nombre case `r"^(source_)?verified$"` sobre una entrada de
registry.

---

## 3. Máquina de estados única

Los cinco valores anteriores son *dimensiones*. El **estado** es una etiqueta
única derivada de ellas, para que exista un solo vocabulario.

```
REGISTERED_PENDING_AUTHORIZATION    en registry, sin decisión que la cubra
AUTHORIZED_PENDING_REVERIFICATION   cubierta por D1/D1-A, sin verificar vigencia
LOCAL_CANONICAL_COPY_VERIFIED       las cuatro dimensiones en verde
SOURCE_UNAVAILABLE                  la URL oficial no responde o cambió de estructura
REVERIFICATION_EXPIRED              reverification_due < hoy
REVOKED                             cobertura retirada por REVOCATION
```

### 3.1 Derivación (determinista, sin juicio)

```
si resolve("D1", sid).coverage_basis == REVOKED        → REVOKED
si ¬COPY_HASH_INTEGRITY                                 → SOURCE_UNAVAILABLE   (¹)
si ¬HUMAN_DECISION_COVERAGE                             → REGISTERED_PENDING_AUTHORIZATION
si REGULATORY_CURRENCY == EXPIRED                       → REVERIFICATION_EXPIRED
si ¬REGULATORY_CURRENCY                                 → AUTHORIZED_PENDING_REVERIFICATION
si las cuatro en verde                                  → LOCAL_CANONICAL_COPY_VERIFIED
```

(¹) Una copia local corrupta es un incidente, no un estado de ciclo de vida
ordinario: emite además una alerta y bloquea todo uso de la fuente,
provisional incluido.

**Orden deliberado:** la cobertura humana se evalúa **antes** que la
vigencia. Una fuente no autorizada no debe siquiera preguntarse si está
vigente — preguntarlo implica salir a la red por algo que nadie firmó que se
pudiera usar.

### 3.2 Transiciones y quién las dispara

| De → A | Disparador | Actor | Efecto secundario |
|---|---|---|---|
| (no existe) → `REGISTERED_PENDING_AUTHORIZATION` | `apply_source_registration()` | **humano** (`SOURCE_REGISTRATION` confirmada) + agente aplica | evento `regulatory_source_registered` |
| `REGISTERED_PENDING_AUTHORIZATION` → `AUTHORIZED_PENDING_REVERIFICATION` | registro de D1 / D1-A que incluya el `source_id` | **humano** | ninguno — registrar ≠ ejecutar |
| `AUTHORIZED_PENDING_REVERIFICATION` → `LOCAL_CANONICAL_COPY_VERIFIED` | `check_source()` con acceso real y hash coincidente | **determinista**, lanzado por humano con `run_by` real | evento + entrada en `source_currency_log.jsonl` |
| `LOCAL_CANONICAL_COPY_VERIFIED` → `REVERIFICATION_EXPIRED` | `reverification_due < hoy` | **determinista** (reloj) | ninguno |
| cualquiera → `SOURCE_UNAVAILABLE` | URL no responde / estructura cambiada | **determinista** | alerta |
| cualquiera → `REVOKED` | decisión `REVOCATION` de familia D1 | **humano** | ninguno |
| `REVOKED` → `AUTHORIZED_PENDING_REVERIFICATION` | nuevo `ADDENDUM` que la re-incluya | **humano** | — |

**Ninguna transición hacia un estado más permisivo es automática.** Las tres
que aumentan permisos (`→ AUTHORIZED`, `→ VERIFIED`, `→ des-revocación`)
exigen o un acto humano o un chequeo determinista lanzado con identidad
humana real. Las que restringen (`→ EXPIRED`, `→ UNAVAILABLE`) sí son
automáticas: restringir es seguro.

### 3.3 Tabla de migración desde los estados actuales

| Estado actual | Fuente | Estado nuevo | Justificación |
|---|---|---|---|
| `pending_reverification` + cubierta por D1 reconstruida | `ecfr_21cfr_part11` | `REGISTERED_PENDING_AUTHORIZATION` | la reconstrucción **no autoriza** (§7.2 del modelo); pasa a `AUTHORIZED_PENDING_REVERIFICATION` en cuanto se registre la Corrección D1 |
| ídem | `eu_gmp_annex11` | ídem | ídem |
| ídem | `mhra_gxp_di_guidance_2018` | ídem | ídem |
| `pending_reverification` sin cobertura | `ecfr_21cfr_part211` | `REGISTERED_PENDING_AUTHORIZATION` | sin D1-A |

> **Las cuatro fuentes aterrizan en el mismo estado**, y conviene decirlo sin
> suavizarlo: hoy la fábrica **no tiene ninguna fuente formalmente
> autorizada**. Las tres antiguas lo parecían porque D1 decía `"ALL"`; el
> modelo nuevo hace visible que ese `"ALL"` nunca se materializó. G2 (la
> Corrección D1) mueve tres de golpe; G3 (la reverificación) las mueve a
> `LOCAL_CANONICAL_COPY_VERIFIED`.

La migración de campos es **aditiva**: se añade `lifecycle_state` y las cinco
dimensiones al schema `source_registry_entry_v1` → `_v2`. Los campos actuales
(`local_integrity_status`, `official_origin_status`,
`regulatory_currency_status`) **se conservan**: son las entradas de las
dimensiones, no sus sustitutos. `registry.json` no se reescribe: se genera
`registry_v2.json` derivado y verificable, con rollback = borrarlo.

---

## 4. DEV-W5-001 — Desviación técnica formal

```yaml
deviation_id: DEV-W5-001
title: >
  Fuente regulatoria (21 CFR Part 211) incorporada al registry sin cobertura
  de la decisión de gobernanza que rige el ciclo de vida de fuentes (D1)
opened: 2026-07-29
opened_by: Capa 8 (auditoría de gobernanza W5 V2)
status: OPEN
severity: MEDIA
classification: DESVIACIÓN DE PROCESO, sin impacto en datos ni en conclusiones
```

### 4.1 Qué pasó

| Hora (2026-07-29 UTC) | Hecho | Evidencia |
|---|---|---|
| `00:15:15.595831` | Cesar firma D1 con `approved_source_ids="ALL"`, cadencia 1 mes, autoridad `cesar`. El registry tiene **3** fuentes. | `w5_human_decisions.jsonl:1` |
| `02:11:29.258853` | Capa 8 propone el alta de `ecfr_21cfr_part211` (`agent_proposed`) | `decisions.jsonl:6` (`d5f72735`) |
| `02:11:29.299184` | Cesar confirma (`human_confirmed`) | `decisions.jsonl:7` (`786464e0`) |
| `02:22:23.949473` | Alta aplicada — `canonical_path` **absoluto**, no resoluble dentro de `factory-api` | `factory_audit.jsonl:18571` |
| `02:25:06.473544` | Capa 8 propone rehacer el alta tras corregir `repo_relative()` | `decisions.jsonl:8` (`fcf933e7`) |
| `02:25:06.513205` | Cesar confirma el rehacer | `decisions.jsonl:9` (`caa2421d`) |
| `02:25:06.554118` | Alta aplicada con ruta relativa — la vigente | `factory_audit.jsonl:18574` |

**El alta estuvo correctamente gobernada.** Cesar firmó, dos veces, con
identidad real, sobre una propuesta concreta con hash declarado que el código
recalculó y verificó.

**Lo que faltó fue el paso siguiente:** ninguna decisión extendió la cobertura
de D1 —cadencia y autoridad de reverificación— a la fuente nueva. Y no faltó
por olvido de nadie en concreto: **el sistema no ofrecía forma de hacerlo**
(`DECISION_IDS` cerrada, sin concepto de ADDENDUM) ni forma de notarlo (D1 sin
lectores).

### 4.2 Por qué la gobernanza no lo impidió — cuatro causas concurrentes

| # | Causa | Evidencia |
|---|---|---|
| **1** | `"ALL"` almacenado como comodín abierto en vez de snapshot materializado | `w5_human_decisions.py:298` — `record["approved_source_ids"] = approved_source_ids` tal cual |
| **2** | Ningún lector de D1 en los 5 consumidores ⇒ ninguna forma de detectar el hueco | A-3 de la auditoría |
| **3** | `DECISION_IDS` tupla cerrada ⇒ D1-A no registrable ni aunque alguien lo hubiera notado | `w5_human_decisions.py:54-60, 265-266` |
| **4** | Dos sistemas de decisiones que no se leen entre sí: el alta se autorizó en el A, la cobertura vive en el B | §0 de la auditoría |

La causa 4 es la de raíz. Las otras tres son sus manifestaciones.

### 4.3 Impacto

| Ámbito | Impacto | Justificación |
|---|---|---|
| Integridad de datos | **NINGUNO** | `sha256_original == sha256_copy`, recalculado por `apply_` (l.244-249). El fichero es el que dice ser. |
| Procedencia | **NINGUNO** | URL oficial de eCFR con fecha fijada; `official_origin_status` honesto y forzado por código |
| Conclusiones regulatorias emitidas | **NINGUNO** | `21_CFR_211.68(b)` tiene `pack_lifecycle_status=DRAFT`, `content_review_status=PENDING_HUMAN_INTERPRETATION` y **0 criterios**. El gate bloquea la llamada: el requisito sale NO EVALUADO. **Ninguna inferencia se ejecutó jamás contra Part 211.** |
| Corridas de corpus | **NINGUNO** | ninguna corrida incluyó el requisito |
| Auditoría | **NINGUNO** | los 4 eventos de decisión y los 2 de alta están en la cadena, con hash correcto |
| **Gobernanza** | **REAL** | una fuente en el registry sin cobertura de ciclo de vida, y el sistema incapaz de decirlo |

**El impacto es exclusivamente de gobernanza.** Ningún dato, ninguna
conclusión y ningún artefacto entregado se ven afectados. Esto no reduce la
gravedad de la desviación: la reduce a su ámbito real, que es el correcto
para dimensionar la corrección.

### 4.4 Corrección

| Acción | Gate | Estado |
|---|---|---|
| Registrar Corrección D1 con snapshot explícito de las 3 fuentes originales | G2 | pendiente |
| Registrar D1-A (ADDENDUM) para `ecfr_21cfr_part211` con cadencia y autoridad | G2 | pendiente |
| Implementar `DecisionScopeResolver` y conectar los 5 consumidores | G1 | pendiente |
| Regla `ALL_SNAPSHOT` materializada en la firma | G1 | pendiente |
| `coverage_report()` con `uncovered_ids` visible en UI | G1 | pendiente |
| Test `test_source_registered_after_all_snapshot_is_not_covered` con Part 211 **como fixture real** | G1 | pendiente |

### 4.5 Qué NO se hace

- **No se borra ni reescribe nada.** Ni los eventos de auditoría, ni las
  decisiones, ni la entrada del registry, ni el fichero canónico.
- **No se da de baja Part 211.** Está correctamente ingerida; lo que falta es
  cobertura, y la cobertura se añade, no se resuelve dando de baja.
- **No se retroactiva la D1.** Lo firmado el 29 de julio a las 00:15 es un
  hecho histórico. Se le superpone una corrección firmada.

### 4.6 Criterio de cierre

`DEV-W5-001` pasa a `CLOSED` cuando, simultáneamente:

1. `resolve("D1", "ecfr_21cfr_part211").authorized == True`
2. `coverage_report("D1").uncovered_ids == ()`
3. `test_source_registered_after_all_snapshot_is_not_covered` **PASA** (es
   decir: el sistema sigue sabiendo detectar el caso, con Part 211 ya
   cubierta, sobre un id nuevo de fixture)
4. Los 5 consumidores llaman al resolver (T-20…T-24 en verde)

El punto 3 es el que importa: cerrar la desviación **no** es hacer que el
test deje de aplicar. La desviación es evidencia de que el sistema ahora lo
detecta, y esa capacidad debe sobrevivir al cierre.

---

## 5. Secuencia obligatoria

```
G2  Corrección D1 (snapshot de las 3 originales) + D1-A (Part 211)
      → las 4 pasan a AUTHORIZED_PENDING_REVERIFICATION
      ↓  (bloqueante)
G3  Reverificación real de las 4 fuentes
      → las que pasen: LOCAL_CANONICAL_COPY_VERIFIED
      ↓  (bloqueante)
G5  D2-A: aprobación de Evidence Packs
```

**La reverificación ocurre DESPUÉS de G2 y ANTES de G5.** No es una
preferencia de orden: reverificar una fuente no autorizada es ejecutar un
acceso a red sobre algo que nadie firmó, y aprobar un pack cuya fuente no
está verificada es firmar criterios interpretativos sobre un texto cuya
vigencia se desconoce.

El resolver lo hace estructural, no documental: C-1
(`source_currency_checker.py`) pregunta `resolve("D1", source_id)` **antes de
cualquier acceso HTTP**, y C-2 exige `FORMAL_USE_ELIGIBILITY` de la fuente
antes de admitir la aprobación de su pack. Si alguien intenta G3 antes de G2,
el resolver lo deniega; si intenta G5 antes de G3, el validador lo deniega.
No hace falta que nadie recuerde el orden.

### 5.1 Reflejo en la UI

El panel §9.B muestra la secuencia como checklist con dependencias
explícitas, y el botón de reverificación aparece **deshabilitado con motivo
visible** (*"requiere Corrección D1 + D1-A registradas"*) hasta que G2 cierre.
Deshabilitado y explicado, no oculto: ocultarlo haría el bloqueo
inexplicable.

---

## 6. Tests

`factory/tests/test_source_lifecycle.py`

| id | Test |
|---|---|
| L-01 | las 5 dimensiones se computan de forma independiente; ninguna lee a otra |
| L-02 | `FORMAL_USE_ELIGIBILITY` es falso si **cualquiera** de las cuatro lo es (4 casos) |
| L-03 | `COPY_HASH_INTEGRITY` verde + resto rojo ⇒ `FORMAL_USE_ELIGIBILITY` falso |
| L-04 | derivación del estado: los 6 estados alcanzables desde combinaciones reales |
| L-05 | la cobertura humana se evalúa antes que la vigencia (mock de red: **cero llamadas HTTP** si no hay cobertura) |
| L-06 | ninguna transición hacia estado más permisivo ocurre sin acto humano |
| L-07 | `REVERIFICATION_EXPIRED` y `SOURCE_UNAVAILABLE` sí son automáticas |
| L-08 | tabla de migración: las 4 fuentes reales aterrizan en `REGISTERED_PENDING_AUTHORIZATION` |
| L-09 | `test_no_collapsed_source_verified_flag` (§2.2) |
| L-10 | `registry.json` no se modifica al derivar `registry_v2.json` (sha256 idéntico) |

L-05 es el test con más valor operativo: prueba que una fuente no autorizada
**no genera tráfico saliente**. Es verificable, es barato y protege contra la
regresión más probable — que alguien mueva la comprobación de cobertura a
después del `httpx.get`.
