# AUDIT_FORK_REMEDIATION_SPEC — §7 del plan

**Estado:** DISEÑO. No modifica ningún evento histórico. No registra ninguna
excepción.
**Cierra:** A-6 (autodeclaración de `part11_compliant`), A-11 (dos escritores).
**Novedad respecto al plan:** la causa raíz del fork **queda establecida con
evidencia en esta corrida** (§3). El plan la daba por pendiente de
arqueología; no lo está.

---

## 1. Reporte separado por dimensión

`factory/core/audit_writer.py:270-278` colapsa hoy tres cosas distintas en un
booleano:

```python
is_fork = hash_errors == 0 and chain_errors > 0
...
assessment = "WARN"
detail = "Fork concurrente: … Contenido auténtico, Part-11 cumplido."
part11_compliant = hash_errors == 0 and chain_errors == 0 and total > 0
```

El resultado real de ejecutarlo hoy:

```json
{"verified": false, "is_fork": true, "assessment": "WARN",
 "log_count": 19818, "verified_count": 19817,
 "hash_errors": 0, "chain_errors": 1, "part11_compliant": true}
```

`verified: false` y `part11_compliant: true` en el mismo objeto. **El sistema
se declara conforme a Part 11 sobre una cadena que él mismo reporta como no
verificada.**

### 1.1 La supersesión de la regla anterior

> **Regla anterior (superseded):** *"fork concurrente ⇒ WARN con
> `part11_compliant=true`; contenido auténtico, Part-11 cumplido"*
> — `audit_writer.py:222-228`.
>
> **Regla nueva:** **PROHIBIDO** declarar `part11_compliant=true` mientras
> `verify_chain=false`, `chain_errors>0` o `is_fork=true`. La conformidad con
> Part 11 no es computable: es una **conclusión regulatoria** y exige una
> excepción humana registrada.
>
> **Motivo de la supersesión:** la regla anterior es correcta en su análisis
> técnico —un fork sin errores de hash **sí** deja el contenido auténtico— y
> equivocada en su conclusión. Que el contenido sea auténtico es *una* de las
> condiciones de Part 11 (§11.10(e): registros seguros, con sello de tiempo,
> que no oscurezcan información previa). La **continuidad verificable de la
> secuencia** es otra, y está rota. Un sistema no puede firmar su propio
> certificado de cumplimiento; menos aún sobre la dimensión que él mismo
> reporta como fallida. Lo que la regla anterior debió producir es
> *"contenido auténtico, continuidad rota, conformidad no determinada"*.

### 1.2 Estructura del reporte nuevo

```
CONTENT_HASH_INTEGRITY   = VERIFIED           (hash_errors == 0 sobre 19 818 entradas)
CHAIN_CONTINUITY         = BROKEN_HISTORICAL  (chain_errors == 1, en la línea 108)
HISTORICAL_FORK_PRESENT  = true               (event_id ab689c7c-…, 2026-06-15T13:54:43Z)
NEW_FORKS_SINCE_BASELINE = 0                  (debe ser 0 — ver §4)
PART11_COMPLIANCE        = NOT_DETERMINED     (hasta excepción humana registrada)
```

Cada dimensión se reporta por separado y **ninguna se deriva de otra**.
`CONTENT_HASH_INTEGRITY = VERIFIED` es una buena noticia real y debe poder
decirse sin que arrastre una conclusión de conformidad.

`verify_chain()` conserva su firma actual por retrocompatibilidad, pero
`part11_compliant` pasa a ser **siempre** uno de
`NOT_DETERMINED | ACCEPTED_WITH_DOCUMENTED_EXCEPTION | COMPLIANT`, nunca un
booleano. Cambiar el tipo es deliberado: obliga a que cada lector actual se
revise, en vez de seguir tratando el valor como un `bool` que ahora miente al
revés.

Estado alcanzable de cada valor:

| Valor | Condición |
|---|---|
| `COMPLIANT` | `hash_errors == 0` ∧ `chain_errors == 0` ∧ `log_count > 0` |
| `ACCEPTED_WITH_DOCUMENTED_EXCEPTION` | fork **conocido y solo el conocido** ∧ decisión `AUDIT_EXCEPTION` `ACTIVE` que lo cubre |
| `NOT_DETERMINED` | cualquier otro caso, incluido `hash_errors > 0` |

`ACCEPTED_WITH_DOCUMENTED_EXCEPTION` **nunca** se muestra como "sin errores".
En toda superficie que lo exponga viaja acompañado del `decision_instance_id`
de la excepción y de la fecha en que se aceptó.

---

## 2. Localización exacta del fork

Recomputación entrada por entrada de las 19 818 líneas:

```
LÍNEA 108
  timestamp  = 2026-06-15T13:54:43.350825+00:00
  event_type = gates_executed
  project_id = lab_qc_project
  entry_id   = ab689c7c-3e0a-4c77-936b-152851f51a30
  entry_hash = sha256:a1228396bc445b8036112c4…
  prev_entry_hash DECLARADO = sha256:20b262690f5b1c0c3cd0a13…
  prev_entry_hash REAL      = sha256:a46ca408a4e70721b218e8e…
```

**Una sola ruptura en 19 818 entradas.** `hash_errors = 0`: ningún contenido
fue alterado.

---

## 3. Causa raíz — establecida, no conjeturada

### 3.1 Las cuatro entradas relevantes

| línea | timestamp | `project_id` | `entry_hash` | `prev_entry_hash` |
|---|---|---|---|---|
| 105 | `13:47:55.678956` | `lab_qc_project` | `6a4ec47d…` | `dd940f3e…` |
| 106 | `13:47:55.679316` | `lab_qc_project` | **`20b26269…`** | `6a4ec47d…` |
| 107 | `13:51:32.834011` | `factory_cleanup` | `a46ca408…` | **`20b26269…`** |
| 108 | `13:54:43.350825` | `lab_qc_project` | `a1228396…` | **`20b26269…`** |

**Las líneas 107 y 108 declaran el mismo `prev_entry_hash`.** Ambas creyeron
estar encadenando a continuación de la línea 106.

### 3.2 El mecanismo

Dos procesos distintos —uno del proyecto `factory_cleanup`, otro de
`lab_qc_project`— tenían cada uno en memoria un `_last_entry_hash` apuntando
a la línea 106, cacheado a las `13:47:55`. `factory_cleanup` escribió primero
(`13:51:32`) y avanzó la cabeza real a `a46ca408…`. `lab_qc_project` escribió
**3 min 10 s después** (`13:54:43`) **sin releer la cabeza**, usando su valor
cacheado siete minutos antes.

No es una condición de carrera en sentido estricto —hay tres minutos entre
ambas escrituras— sino una **caché en memoria que nunca se invalidó**. Con
tres minutos de margen, ningún lock por sí solo lo habría evitado: el segundo
escritor habría tomado el lock sin problema y habría escrito el mismo
`prev_hash` obsoleto.

### 3.3 Por qué el arreglo actual sí lo cierra

`git log -S "fcntl.flock" -- factory/core/audit_writer.py` → commit
**`8c033fa`, 2026-06-15 14:21:43 +0000**.

**El fork ocurrió a las 13:54:43. El arreglo se commiteó a las 14:21:43 — 27
minutos después.** El fork pertenece inequívocamente a la era anterior al
arreglo.

Y el arreglo ataca la causa correcta. `audit_writer.py:188-191`:

```python
fcntl.flock(lock_fh, fcntl.LOCK_EX)
try:
    _last_entry_hash = None  # forzar re-lectura dentro del lock
    prev_hash = _get_prev_hash()
```

La línea que importa no es el `flock`: es **`_last_entry_hash = None` dentro
del lock**. El lock serializa; la invalidación de caché es lo que garantiza
que el escritor lea la cabeza **real** y no la que recordaba. Ambas cosas
juntas cierran exactamente el escenario de §3.2.

### 3.4 Verificación empírica

En las **19 710 entradas escritas después** del commit `8c033fa` (líneas
109-19 818, del 2026-06-15 al 2026-07-29, con escritores concurrentes desde el
host **y** desde el contenedor `factory-api`) **no hay ni una sola ruptura de
cadena**. Seis semanas de operación real con escritura concurrente y cero
forks nuevos.

> **Conclusión de causa raíz:** caché de cabeza de cadena en memoria de
> proceso, no invalidada, con dos procesos escritores concurrentes. Corregida
> el 2026-06-15T14:21:43Z por el commit `8c033fa`. Evidencia de eficacia:
> 19 710 entradas posteriores sin rupturas.

Esta sección es el insumo obligatorio del paquete de excepción (§6): Cesar no
debe aceptar una excepción cuya causa se desconozca.

---

## 4. Prevención de forks nuevos

### 4.1 Qué ya está resuelto

`flock` exclusivo + invalidación de caché dentro del lock. Es correcto para
escritores en el mismo host sobre el mismo inodo, incluidos los que escriben
desde dentro del contenedor a través del bind-mount (`flock` es advisory pero
funciona a través del mount porque el inodo es el mismo).

Evidencia de que hay escritores con identidad de SO distinta:

```
-rw-r--r-- ing_cpmo  factory/layer9/decisions/decisions.jsonl          (host)
-rw-r--r-- root      factory/layer9/decisions/w5_human_decisions.jsonl  (contenedor)
```

### 4.2 Qué falta

| Riesgo residual | Diseño |
|---|---|
| Un escritor que **no pase por `write_event()`** (script ad-hoc, `echo >>`, edición manual) | **Guardia de escritor único**: `write_event()` incluye en cada entrada `writer_pid`, `writer_host` y `writer_identity`. Test de Gate 0: toda entrada posterior al baseline los trae. Una entrada sin ellos = escritura fuera del canal. |
| El `flock` falla en silencio y `write_event` devuelve `{"error": ...}` (l.214-215: `except Exception → return {"error": str(e)}`) | **`write_event` nunca debe fallar en silencio.** Si no logra escribir, además de devolver el error emite a `stderr` y a `factory/logs/audit_write_failures.log`. Un evento perdido es peor que una excepción. |
| Escritura desde otro host sobre un almacenamiento compartido | fuera del alcance actual (todo es local). Se declara como supuesto explícito: **`flock` protege un solo host**. Si algún día el almacén se comparte por NFS, este diseño no basta. |
| Reintentos del lock | timeout de 5 s con 3 reintentos; agotados, **falla ruidosamente** y no escribe. Nunca escribir sin lock. |

### 4.3 Lo que NO se hace

**No se introduce un proceso escritor único (cola/daemon).** Se evaluó contra
el mecanismo existente y no compensa: añade un punto único de fallo y un modo
de degradación nuevo (cola llena, daemon caído ⇒ eventos perdidos) para
resolver un problema que `flock` + invalidación de caché ya cierra, con seis
semanas de evidencia. La complejidad adicional no está justificada por los
datos.

---

## 5. Baseline del fork histórico

Congelar el fork conocido para distinguirlo de cualquiera nuevo.

`factory/audit/fork_baseline.json`:

```json
{
  "baseline_version": 1,
  "frozen_at": "<fecha de congelación>",
  "frozen_by": "<identidad humana real>",
  "known_forks": [
    {
      "fork_id": "FORK-2026-06-15-001",
      "line_number": 108,
      "entry_id": "ab689c7c-3e0a-4c77-936b-152851f51a30",
      "timestamp": "2026-06-15T13:54:43.350825+00:00",
      "event_type": "gates_executed",
      "project_id": "lab_qc_project",
      "entry_hash": "sha256:a1228396bc445b8036112c4...",
      "prev_entry_hash_declared": "sha256:20b262690f5b1c0c3cd0a13...",
      "prev_entry_hash_actual": "sha256:a46ca408a4e70721b218e8e...",
      "competing_writer": {
        "line_number": 107,
        "entry_id": "6a680163-f4b0-4c50-9c1c-ec79f433b94b",
        "project_id": "factory_cleanup",
        "timestamp": "2026-06-15T13:51:32.834011+00:00"
      },
      "root_cause": "stale_in_process_head_cache",
      "fixed_by_commit": "8c033fa",
      "fixed_at": "2026-06-15T14:21:43+00:00"
    }
  ],
  "log_count_at_baseline": 19818,
  "hash_errors_at_baseline": 0,
  "chain_errors_at_baseline": 1
}
```

`line_number` es **informativo**, no identificador: si algún día el fichero se
rota, la línea cambia. El identificador estable es `entry_id` + `entry_hash`.

### 5.1 Detección de forks nuevos

```python
def new_forks_since_baseline() -> list[ForkRecord]:
    """Todos los forks detectados que NO están en fork_baseline.json,
    identificados por entry_id. Read-only."""
```

```
NEW_FORKS_SINCE_BASELINE = |{forks detectados} − {forks del baseline}|
```

Hoy: **0**.

Que el baseline no se convierta en una alfombra: **añadir un fork al baseline
exige su propia decisión `AUDIT_EXCEPTION`.** No se puede silenciar un fork
nuevo editando el JSON — el fichero se valida contra las excepciones
registradas, y un `known_fork` sin decisión que lo respalde hace **FAIL** el
Gate 0.

---

## 6. Alerta fail-closed

```
NEW_FORKS_SINCE_BASELINE > 0
  ⇒ bloqueo de corridas de corpus
  ⇒ bloqueo de registro de decisiones          ← incluido deliberadamente
  ⇒ bloqueo de release y deployment
  ⇒ alerta en Gate 0 (FAIL, no WARN)
  ⇒ alerta visible en la UI de Mission Control
```

Bloquear el **registro de decisiones** merece justificación: si la cadena está
rota *ahora*, una decisión registrada en este momento no tiene trazabilidad
demostrable. Registrar una decisión de gobernanza sobre una cadena que
acabamos de descubrir rota es producir un acto formal cuya prueba de
integridad está en duda. Se para todo, se investiga, se decide después.

Integración en Gate 0:

```
5/7  audit chain
     CONTENT_HASH_INTEGRITY   → FAIL si hash_errors > 0
     NEW_FORKS_SINCE_BASELINE → FAIL si > 0
     HISTORICAL_FORK_PRESENT  → WARN si true y hay excepción ACTIVE
                              → FAIL si true y NO hay excepción ACTIVE   (desde G7)
     PART11_COMPLIANCE        → informativo, nunca criterio de PASS por sí solo
```

`HISTORICAL_FORK_PRESENT` pasa de `WARN` a `FAIL` **solo a partir de G7**.
Antes de G7 la excepción todavía no puede existir, y dejar Gate 0 en rojo
permanente hasta entonces haría que se dejara de leer.

---

## 7. Paquete de excepción humana

Se registra como decisión de familia `AUDIT_EXCEPTION`,
`resolved_target_ids: ["ab689c7c-3e0a-4c77-936b-152851f51a30"]`.

```yaml
audit_exception_package:
  exception_id: AUDIT-EXC-2026-001
  fork_id: FORK-2026-06-15-001

  # 1. QUÉ
  finding: >
    Una ruptura de enlace de cadena en la entrada 108 de 19 818
    (entry_id ab689c7c-…, 2026-06-15T13:54:43Z). Las entradas 107 y 108
    declaran ambas prev_entry_hash=20b26269… (la cabeza de la línea 106).
    hash_errors = 0 en las 19 818 entradas: ningún contenido fue alterado.

  # 2. POR QUÉ
  root_cause: stale_in_process_head_cache
  root_cause_detail: >
    Dos procesos (factory_cleanup y lab_qc_project) mantenían en memoria un
    _last_entry_hash cacheado a las 13:47:55 apuntando a la línea 106.
    factory_cleanup escribió a las 13:51:32 y avanzó la cabeza real;
    lab_qc_project escribió a las 13:54:43 sin releerla. Con 3 min 10 s entre
    ambas escrituras, un lock por sí solo no lo habría evitado: el problema
    era la caché, no la simultaneidad.

  # 3. RIESGO
  risk_assessment:
    content_authenticity: NO_AFECTADA
      basis: "hash_errors = 0 en las 19 818 entradas, recomputado el 2026-07-29"
    sequence_verifiability: AFECTADA_LOCALMENTE
      basis: "el orden relativo de las líneas 107 y 108 no es demostrable
              criptográficamente; sus timestamps y su contenido sí son
              auténticos e íntegros"
    scope: >
      2 entradas de 19 818 (0,01 %), ambas del 2026-06-15, ambas del proyecto
      lab_qc_project / factory_cleanup en fase de despliegue. Ninguna entrada
      de W5, del corpus regulatorio, de decisiones de gobernanza ni de
      artefactos entregables está en el tramo afectado.
    regulatory_impact: >
      Ninguna conclusión regulatoria emitida se apoya en la secuencia de esas
      dos entradas. Ningún dossier, informe ni paquete QA las cita.

  # 4. MEDIDAS PREVENTIVAS — implementadas ANTES de pedir la aceptación
  preventive_measures:
    - measure: "flock exclusivo + invalidación de caché dentro del lock"
      status: IMPLEMENTADA
      commit: 8c033fa
      date: "2026-06-15T14:21:43+00:00"
      evidence: "19 710 entradas posteriores sin una sola ruptura"
    - measure: "writer_pid / writer_host / writer_identity en cada entrada"
      status: IMPLEMENTADA       # G7
      evidence: >
        En el cuerpo HASHEADO, no en `data`: una identidad editable sin
        invalidar el entry_hash no prueba nada. La violación —una entrada sin
        identidad DESPUÉS del ancla— se mide sobre la cadena real, y el ancla se
        DERIVA (primera entrada que trae los tres campos), no se declara en un
        fichero que se pudiera adelantar para esconder entradas.
    - measure: "fork_baseline.json congelado y validado contra excepciones"
      status: IMPLEMENTADA       # G1.14 lo congeló, G7 exige que el resolver responda
      evidence: >
        `unbacked_known_forks()` consulta al resolver de verdad. Que la función
        exista no basta: degrada a "todos sin respaldo" si el import falla, y en
        ese modo no está validando contra nada, solo negando todo.
    - measure: "NEW_FORKS_SINCE_BASELINE > 0 ⇒ FAIL en Gate 0"
      status: IMPLEMENTADA       # G1.17
      evidence: "`_verdict_audit_chain` trata el fork nuevo con `ko`, no con `warn`."
    - measure: "write_event nunca falla en silencio"
      status: IMPLEMENTADA       # G7
      evidence: >
        Lock con timeout de 5 s y 3 reintentos (`LOCK_NB`): agotados, lanza
        `AuditLockError` y NO escribe. `LOCK_EX` bloqueante esperaba para
        siempre — un cuelgue silencioso y un evento perdido en silencio son el
        mismo defecto. Todo fallo va a stderr y a
        `factory/logs/audit_write_failures.log`, que NO está encadenado a
        propósito: encadenar el registro de "no pude encadenar" es circular.

  # El estado de estas cinco medidas se DERIVA (`audit_writer.preventive_measures()`)
  # y viaja en `GET /governance/state`. Vivió como cinco literales `ok:false` en
  # `governance.js` para irlos flipando a mano, y de esa lista depende el botón
  # "Aceptar": un `true` escrito a mano habilitaba una firma regulatoria sobre una
  # prevención que podía no existir. Cada medida declara además su clase de
  # evidencia (DERIVED_FROM_CHAIN | SOURCE_INSPECTION), que no son equivalentes.
  #
  # Lo que NO se exige: que la cadena ya CONTENGA una entrada sellada. Eso creaba
  # un abrazo mortal — las entradas nuevas las produce la actividad gobernada, y
  # la actividad que faltaba era justo la firma que la medida bloquea.

  # 5. LO QUE SE PIDE
  requested_of_capa9: >
    Aceptar o rechazar que la dimensión CHAIN_CONTINUITY se reporte como
    ACCEPTED_WITH_DOCUMENTED_EXCEPTION para este fork concreto e
    identificado, dejando PART11_COMPLIANCE en un valor distinto de
    NOT_DETERMINED únicamente para el resto de la cadena.

  # 6. LO QUE NO SE PIDE
  explicitly_not_requested:
    - "Declarar la cadena íntegra: no lo está."
    - "Declarar part11_compliant=true de forma global."
    - "Aceptar forks futuros: la excepción cubre UN entry_id y solo uno."
    - "Reescribir, borrar o reordenar ningún evento."

  decision: PENDING            # APPROVE | REJECT — solo Cesar
  approved_by_id: null
  decision_date: null
```

### 7.1 Efecto de la aceptación

**Solo** con la excepción `ACTIVE`:

```
CHAIN_CONTINUITY = ACCEPTED_WITH_DOCUMENTED_EXCEPTION
                   (excepción AUDIT-EXC-2026-001, aceptada el <fecha> por <nombre>)
```

**Nunca** `CHAIN_CONTINUITY = VERIFIED` ni "sin errores". El texto de la
excepción viaja con el valor en toda superficie que lo exponga: informe, API,
UI y dossier.

Si Cesar **rechaza**, `PART11_COMPLIANCE` permanece `NOT_DETERMINED`
indefinidamente y el release gate sigue bloqueado. Es un final legítimo del
proceso, no un fallo del diseño.

### 7.2 Alcance de la excepción

Cubre **un `entry_id`**. No cubre:

- forks futuros (`NEW_FORKS_SINCE_BASELINE` sigue debiendo ser 0);
- errores de hash (`hash_errors > 0` no es exceptuable por diseño: es
  corrupción de contenido, no de enlace);
- ningún otro fork histórico que apareciera en una rotación o migración del
  fichero.

---

## 8. Cero reescritura

| Prohibido | Por qué |
|---|---|
| Editar `prev_entry_hash` de la línea 108 | falsificaría la cadena; sería exactamente lo que Part 11 prohíbe |
| Reordenar las líneas 107 y 108 | ídem |
| Recomputar la cadena desde el genesis y reescribir el fichero | destruiría la evidencia de la desviación |
| Borrar y regenerar `factory_audit.jsonl` | ídem, agravado |
| Suprimir el fork del reporte | el sistema dejaría de detectarlo |

**El fork se queda donde está, para siempre.** La remediación es contable, no
correctiva: se documenta, se explica, se previene su repetición y un humano
decide si lo acepta.

---

## 9. Tests

`factory/tests/test_audit_fork_governance.py`

| id | Test |
|---|---|
| F-01 | `part11_compliant` nunca es `True` con `chain_errors > 0` (fixture: la cadena real de hoy) |
| F-02 | las 5 dimensiones se reportan por separado; ninguna se deriva de otra |
| F-03 | `ACCEPTED_WITH_DOCUMENTED_EXCEPTION` requiere una decisión `AUDIT_EXCEPTION` `ACTIVE` que cubra ese `entry_id` |
| F-04 | sin excepción ⇒ `PART11_COMPLIANCE = NOT_DETERMINED` |
| F-05 | excepción de **otro** `entry_id` ⇒ no cubre el fork conocido |
| F-06 | `new_forks_since_baseline()` == 0 sobre la cadena real |
| F-07 | inyectar un fork sintético ⇒ `NEW_FORKS_SINCE_BASELINE == 1` ⇒ Gate 0 **FAIL** |
| F-08 | `known_fork` en el baseline **sin** decisión que lo respalde ⇒ Gate 0 **FAIL** |
| F-09 | `hash_errors > 0` ⇒ `NOT_DETERMINED` **aunque** exista una excepción (no exceptuable) |
| F-10 | dos escrituras concurrentes reales (2 procesos, 500 eventos cada uno) ⇒ 1 000 entradas, `chain_errors == 0` — regresión del arreglo `8c033fa` |
| F-11 | escritura con caché forzada obsoleta ⇒ el lock la invalida y la cadena queda íntegra (reproduce §3.2 y prueba el arreglo) |
| F-12 | `verify_chain()` es read-only: `log_count` idéntico tras 100 llamadas |
| F-13 | `write_event` que no logra el lock ⇒ falla ruidosamente y **no** escribe |

F-11 es el test que reproduce la causa raíz establecida en §3 y demuestra que
el arreglo la cierra. Sin él, la afirmación *"corregido por `8c033fa`"* queda
apoyada solo en la ausencia de forks posteriores, que es evidencia de
correlación, no de mecanismo.
