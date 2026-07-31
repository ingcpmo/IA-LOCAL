# GOVERNANCE_UI_SPEC — §9 del plan

**Estado:** DISEÑO. Sin implementar. Ningún archivo de `factory/ui/` fue
modificado en esta corrida.
**Ubicación:** `factory/ui/mission_control.html` + módulo nuevo
`factory/ui/js/mission_control/governance.js`, junto a los 20 módulos
existentes. Backend: `factory-api`, **puerto 9000** (`factory/registry/ports.yaml:3`).

---

## 1. Reglas transversales

| # | Regla |
|---|---|
| U-1 | **Todo GET es de solo lectura.** Jamás escribe auditoría, jamás promueve un estado. Mismo contrato que `get_decisions_state()`. |
| U-2 | **Cada POST genera exactamente UN evento** de auditoría. |
| U-3 | **422** identidad inválida o genérica — `RESERVED_IDENTITIES` en una única función compartida por todas las superficies (cierra A-4). |
| U-4 | **409** duplicación, y también cuando el estado cambió entre la lectura y el POST (control optimista por hash). |
| U-5 | **Ninguna decisión ejecuta automáticamente sus efectos.** Registrar ≠ ejecutar. Leyenda visible y permanente en cada panel. |
| U-6 | Respetar `factory/registry/ports.yaml`. **Backup de `index.html` y `mission_control.html` a `backups/frontend/` antes de cualquier cambio futuro.** |
| U-7 | Toda acción bloqueada se muestra **deshabilitada con el motivo visible**, nunca oculta. Un botón ausente es un bloqueo inexplicable. |
| U-8 | Todo valor de gobernanza se muestra con su **procedencia**: `decision_instance_id`, fecha, firmante. Ningún estado aparece sin decir quién lo produjo. |
| U-9 | **Ninguna prueba automatizada del ciclo de firma usa una identidad inventada contra el backend de producción**, ni siquiera para diagnóstico. Ver §1.2. |

### 1.1 Control optimista (U-4)

Cada GET devuelve un `state_hash`. Cada POST lo reenvía. Si el estado cambió
entre medias, **409** con el diff. Sin esto, dos pestañas abiertas producen
decisiones firmadas sobre datos que ya no existen — precisamente el escenario
que originó el fork de la cadena, trasladado a la capa humana.

### 1.2 Prohibición de firmas de prueba en producción (U-9)

**Incidente real (2026-07-30):** diagnosticando por qué un panel no
completaba la firma, el agente reprodujo el ciclo `propose`→`confirm`
contra el backend REAL con la identidad `claude_probe`, asumiendo que
`RESERVED_IDENTITIES` la rechazaría por contener "claude". El chequeo hacía
match exacto, no por prefijo: `D2-2026-003` quedó `human_confirmed`/`ACTIVE`
con una aprobación fabricada por el propio agente — ver
`RECORD_ANNOTATION-2026-005`/`-006` en `factory/layer9/decisions/decisions_v2.jsonl`
y `docs_plan/W5V2_FIX_FIRMA_SILENCIOSA.md`.

**Regla en vigor desde entonces:** ninguna prueba del ciclo de firma —
manual (curl, script ad-hoc) o automatizada (Playwright) — envía un POST de
`propose`/`confirm`/`reject` con una identidad real o inventada contra el
backend de producción. Las superficies permitidas para probar el ciclo
completo:

- **Tests unitarios/integración Python** contra un `store_file` temporal
  (`tmp_path`), como ya hace toda la suite de `test_governance_*.py`.
- **Tests de UI con Playwright** interceptando la red (`page.route()`) para
  servir fixtures controladas — cero tráfico de escritura llega al backend
  real (ver `test_governance_ui_stale_state_playwright.py`).
- **Sondas de diagnóstico contra el backend real**, si son estrictamente
  necesarias, usan SIEMPRE una identidad de la lista reservada (`human`,
  `admin`, etc.) en el paso de `/confirm`, para que el servidor la rechace
  con 422 y no se convierta en una firma — nunca un string "casi reservado"
  sin verificar primero contra `identity_policy.is_reserved()`.

---

## 2. Rutas

```
/mission_control.html#gobierno                     índice de los seis paneles
/mission_control.html#gobierno/d1-correccion       A
/mission_control.html#gobierno/d1a                 B
/mission_control.html#gobierno/pack-211            C
/mission_control.html#gobierno/d2a                 D
/mission_control.html#gobierno/excepcion-auditoria E
/mission_control.html#gobierno/d4a                 F
```

Índice: seis tarjetas, cada una con su gate (G2…G8), su estado
(`BLOQUEADO` / `LISTO` / `REGISTRADA`) y **las precondiciones que faltan**.
Una tarjeta bloqueada dice por qué en la propia tarjeta.

---

## 3. Endpoints comunes

```
GET  /api/v1/layer9/governance/state
     → { families: {…}, coverage: {…}, artifacts: {…}, audit: {…},
         critical_path: [G1..G8], state_hash }
     Solo lectura. Es el GET que alimenta el índice.

GET  /api/v1/layer9/governance/coverage/{family}
     → CoverageReport (§5 de DECISION_SCOPE_RESOLVER_SPEC.md)

POST /api/v1/layer9/governance/decisions/{family}/propose
     → registro agent_proposed. NO autoriza nada.

POST /api/v1/layer9/governance/decisions/{instance_id}/confirm
     → registro human_confirmed. Resuelve el snapshot AQUÍ.
     422 identidad genérica · 409 state_hash obsoleto · 404 propuesta inexistente

POST /api/v1/layer9/governance/decisions/{instance_id}/return
     → devuelve la propuesta al proponente con comentario. 1 evento.

POST /api/v1/layer9/governance/decisions/{instance_id}/reject
     → rechazo registrado. 1 evento. La propuesta NO se borra.
```

Los seis paneles usan estos endpoints. No hay un endpoint por panel: el panel
es una vista sobre la familia, no un sistema aparte. Es la traducción a HTTP
de "un modelo, un almacén, una lectura".

---

## 4. Panel A — Corrección D1

**Ruta:** `#gobierno/d1-correccion` · **Gate:** G2 · **Familia:** `D1`,
`decision_type=CORRECTION`

### 4.1 Qué muestra

```
┌─ Corrección D1 — Fuentes regulatorias ────────────────────────────────┐
│                                                                        │
│ DECISIÓN VIGENTE (se supersede)                                        │
│   D1-2026-001 · APPROVE · cesar · 2026-07-29 00:15:15Z                 │
│   approved_source_ids: "ALL"        ⚠ comodín abierto, sin snapshot    │
│   cadencia: 1 mes · autoridad: cesar                                   │
│   evento de auditoría: <entry_id>                                      │
│                                                                        │
│ SNAPSHOT EXPLÍCITO — el registry a la hora de la firma original        │
│   ☑ ecfr_21cfr_part11          copied_at 2026-07-17 19:32:45Z          │
│   ☑ eu_gmp_annex11             copied_at 2026-07-17 19:32:45Z          │
│   ☑ mhra_gxp_di_guidance_2018  copied_at 2026-07-17 19:32:45Z          │
│   ☐ ecfr_21cfr_part211         copied_at 2026-07-29 02:25:06Z          │
│     └ POSTERIOR a la firma de D1. No pertenece a este snapshot.        │
│       Se cubre en el panel B (D1-A), como adendo separado.             │
│                                                                        │
│   target_set_hash: <sha256 de los tres marcados>                       │
│                                                                        │
│ CADENCIA        [ 1 ] meses    (heredada; editable)                    │
│ AUTORIDAD       [ ................ ]                                    │
│ MOTIVO *        [ ................ ]                                    │
│ FIRMA — id      [ ................ ]   nombre  [ ............... ]     │
│                                                                        │
│ ⓘ Registrar esta corrección NO reverifica ninguna fuente ni cambia su  │
│   estado. La reverificación (G3) es un paso posterior y separado.      │
│                                                                        │
│                          [ Registrar corrección ]                      │
└────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Decisiones de diseño

- **Los tres checkboxes vienen marcados y el cuarto desmarcado**, con la
  razón escrita al lado. Es el punto pedagógico del panel entero: el usuario
  ve *por qué* Part 211 no está ahí, en vez de tener que deducirlo.
- **Part 211 no se puede marcar desde aquí.** El checkbox está deshabilitado
  con el motivo. Mezclar la corrección del snapshot con la ampliación a una
  fuente nueva produciría un solo registro que hace dos cosas distintas — y
  la trazabilidad de "qué se corrigió" se perdería.
- **Se muestra el `target_set_hash` calculado en vivo.** Cambiar una casilla
  lo cambia. Hace visible que lo que se firma es un conjunto concreto.
- **Identidad en dos campos** (`id` y `nombre`): el registro histórico dice
  `approved_by: "cesar"`, que es un identificador, no un nombre. El schema
  nuevo separa `approved_by_id` de `approved_by_display_name`.

### 4.3 Backend

Ninguno nuevo: `record_correction()` ya acepta `approved_source_ids` con
lista explícita (`layer9.py:1272-1281`; `w5_human_decisions.py:380-403`).
**El trabajo es exclusivamente de UI** (hallazgo A-5), más el mapeo al modelo
nuevo.

| Error | Causa |
|---|---|
| 422 | identidad genérica, motivo vacío, cero fuentes marcadas |
| 409 | `state_hash` obsoleto (el registry cambió) |
| 404 | no hay D1 previa que corregir |

**Evento:** `layer9_decision_recorded`, `scope=governance_decision`,
`{family: D1, type: CORRECTION, target_set_hash, supersedes_instance_id,
side_effects_applied: false}`.

---

## 5. Panel B — D1-A

**Ruta:** `#gobierno/d1a` · **Gate:** G2 · **Familia:** `D1`,
`decision_type=ADDENDUM`

```
┌─ D1-A — Adendo de cobertura ──────────────────────────────────────────┐
│                                                                        │
│ COBERTURA ACTUAL DE LA FAMILIA D1                                      │
│   cubiertas: 3   ·   sin cobertura: 1   ·   drift del registry: SÍ     │
│                                                                        │
│ FUENTE A CUBRIR                                                        │
│   ☑ ecfr_21cfr_part211                                                 │
│     eCFR Title 21 Part 211 — Current Good Manufacturing Practice       │
│     for Finished Pharmaceuticals                                       │
│     sha256 ecd9f8ba…  ·  96 680 bytes  ·  local_integrity PASS         │
│     origen: FIRST_INGESTION_NO_PRIOR_KNOWN_HASH_TO_COMPARE             │
│     alta autorizada por caa2421d-… (Cesar, 2026-07-29 02:25:06Z)       │
│     desviación asociada: DEV-W5-001                                    │
│                                                                        │
│ ALCANCE (decisión previa, no editable aquí)                            │
│   Parts en alcance:   211                                              │
│   Excluida:           210 — "ámbito y definiciones; ningún requisito    │
│                       del catálogo se apoya en él"                     │
│   Decidido por Cesar el 2026-07-29 02:11:29Z (d5f72735 → 786464e0)     │
│                                                                        │
│ CADENCIA        [ ... ] meses                                          │
│ AUTORIDAD       [ ................ ]                                    │
│ MOTIVO *        [ ................ ]                                    │
│ FIRMA — id      [ ....... ]   nombre  [ ............... ]              │
│                                                                        │
│ ⓘ Un ADENDO amplía la cobertura sin tocar la Corrección D1: ambas      │
│   quedan ACTIVE y la cobertura efectiva es su unión.                   │
│ ⓘ Registrar NO reverifica: la fuente pasará a                          │
│   AUTHORIZED_PENDING_REVERIFICATION, no a VERIFIED.                    │
│                                                                        │
│                            [ Registrar D1-A ]                          │
└────────────────────────────────────────────────────────────────────────┘
```

**Part 210 no aparece como ítem.** §6.3 del plan lo condicionaba a la
resolución del alcance, y el alcance **ya está resuelto y firmado** (A-9). El
panel lo muestra como decisión previa **de solo lectura**, no como opción.
Reabrirlo como casilla marcable invitaría a re-decidir lo ya decidido.

Precondición: el panel está **deshabilitado** hasta que la Corrección D1
(panel A) esté registrada, con el motivo visible. Un adendo sobre un
snapshot que aún es un comodín abierto no tiene sentido.

---

## 6. Panel C — Revisión del pack 211

**Ruta:** `#gobierno/pack-211` · **Gate:** G4a · **Familia:** `D2`

```
┌─ Evidence Pack — 21_CFR_211.68(b) ────────────────────────────────────┐
│ ⚠ REGLA PREDICADO de los 5 requisitos de Part 11                      │
│   (11.10(a), 11.10(d), 11.10(e), 11.10(g), 11.50_11.70 declaran        │
│    predicate_rule_id = 21_CFR_211.68(b))                               │
│                                                                        │
│ TEXTO CANÓNICO — de la copia verificada, sha256 ecd9f8ba…              │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │ (contexto anterior, atenuado)                                     │ │
│  │ ▸ Appropriate controls shall be exercised over computer or        │ │
│  │   related systems to assure that changes in master production     │ │
│  │   and control records or other records are instituted only by     │ │
│  │   authorized personnel. …                                          │ │
│  │ (contexto posterior, atenuado)                                    │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│ INTERPRETACIÓN GOBERNADA          [ propuesta editable ]               │
│                                                                        │
│ CRITERIOS MÍNIMOS DE EVIDENCIA                                         │
│  1 [ ................................. ]  ancla → offset 1240  ✓      │
│  2 [ ................................. ]  ancla → offset 1388  ✓      │
│  + añadir criterio                                                     │
│                                                                        │
│ CRITERIOS DE EXCLUSIÓN            [ … ]                                │
│ TÉRMINOS DÉBILES                  [ … ]                                │
│ EVIDENCIA TÍPICAMENTE INSUFICIENTE[ … ]                                │
│ TIPOS DOCUMENTALES ESPERADOS      [ URS ][ FS ][ PROTOCOL ][ REPORT ]  │
│                                                                        │
│ VALIDADORES                                                            │
│   V1 schema completo                    ✓                              │
│   V2 sin campos vacíos                  ✓                              │
│   V3 sin duplicados                     ✓                              │
│   V4 weak_keywords ⊄ criterios mínimos  ✓                              │
│   V5 anclaje al texto canónico          ✓                              │
│   V6 tipos documentales en la matriz    ✓                              │
│   V7 sin colisión con otro requisito    ✓                              │
│   V8 hash del pack                      2f9a…                          │
│   V9 fuente LOCAL_CANONICAL_COPY_VERIFIED   ✗ pending_reverification    │
│   V10 resolve("D1", ecfr_21cfr_part211)     ✗ NOT_COVERED               │
│                                                                        │
│ MOTIVO *   [ ......... ]   FIRMA [ id ] [ nombre ]                     │
│                                                                        │
│  [ Aprobar ]   [ Devolver con comentario ]   [ Rechazar ]              │
│    ▲ deshabilitado: V9 y V10 en rojo. Requiere G2 y G3.                │
└────────────────────────────────────────────────────────────────────────┘
```

- Los 10 validadores están **siempre visibles**, en verde o rojo. `Aprobar` se
  habilita solo con los 10 en verde (U-7).
- El anclaje al texto canónico se muestra por criterio: al enfocar un
  criterio, el fragmento correspondiente se resalta en el panel de texto.
- `Devolver con comentario` y `Rechazar` **registran** su propio evento. Un
  rechazo es una decisión de gobernanza tanto como una aprobación.

---

## 7. Panel D — D2-A unificada

**Ruta:** `#gobierno/d2a` · **Gate:** G5 · **Familia:** `D2`

```
┌─ D2-A — Aprobación de Evidence Packs ─────────────────────────────────┐
│                                                                        │
│ PRECONDICIONES (calculadas, nunca declaradas)                          │
│   ☐ 4/4 fuentes en LOCAL_CANONICAL_COPY_VERIFIED   0/4     → G3        │
│   ☐ pack 21_CFR_211.68(b) completo                 0 crit. → G4a       │
│   ☐ matriz v2.1 aprobada        MC-0001 cubre 2.0          → G4b       │
│   ☐ catálogo versionado         1.0 con hash a83c8168…     → G4c       │
│   D2_A_READY = false                                                   │
│                                                                        │
│ PACKS                              ver.   hash      D2      acción      │
│   21_CFR_11.10(a)                  2.1-d  8c1f…   ✗ n/c    [revisar]   │
│   21_CFR_11.10(d)                  2.1-d  a04b…   ✗ n/c    [revisar]   │
│   …  (20 filas)                                                        │
│   21_CFR_211.68(b)                 1.0-d  —       ✗ n/c    [completar] │
│                                                                        │
│ MATRIZ DE APLICABILIDAD                                                │
│   vigente: 2.1   ·   aprobada: 2.0 (MC-0001, Cesar, 2026-07-17)        │
│   ⚠ approval.status dice "human_confirmed" a nivel de ARCHIVO;         │
│     MC-0001.metadata.matrix_version = "2.0". Las filas de 211 están     │
│     marcadas # PROPUESTO y no están cubiertas.        [aprobar v2.1]   │
│                                                                        │
│ CATÁLOGO                                                               │
│   catalog_version 1.0   ·   sha256 a83c8168…                           │
│   ⚠ hash cambiado sin cambio de versión (ref. 6486405a…)               │
│   propuesta: 2.0        (ejecutar DESPUÉS de G4a)     [versionar]      │
│                                                                        │
│ ⓘ Un pack, una decisión. Aprobar uno no aprueba los demás.             │
└────────────────────────────────────────────────────────────────────────┘
```

El checklist de precondiciones es **el mismo objeto** que devuelve
`d2a_ready()`. La UI no lo recalcula: lo muestra. Si algún día divergen, es
que la UI empezó a tener lógica propia — y eso es el defecto que este panel
existe para no repetir.

---

## 8. Panel E — Excepción de auditoría histórica

**Ruta:** `#gobierno/excepcion-auditoria` · **Gate:** G7 · **Familia:**
`AUDIT_EXCEPTION`

```
┌─ Excepción de auditoría — FORK-2026-06-15-001 ────────────────────────┐
│                                                                        │
│ ESTADO DE LA CADENA, POR DIMENSIÓN                                     │
│   CONTENT_HASH_INTEGRITY    VERIFIED           0 errores / 19 818      │
│   CHAIN_CONTINUITY          BROKEN_HISTORICAL  1 ruptura, línea 108    │
│   HISTORICAL_FORK_PRESENT   true               ab689c7c-…              │
│   NEW_FORKS_SINCE_BASELINE  0                                          │
│   PART11_COMPLIANCE         NOT_DETERMINED                             │
│                                                                        │
│ EL FORK                                                                │
│   2026-06-15 13:54:43.350825Z · gates_executed · lab_qc_project        │
│   entry_id  ab689c7c-3e0a-4c77-936b-152851f51a30                       │
│   prev declarado  20b26269…      prev real  a46ca408…                  │
│   escritor en conflicto: línea 107, factory_cleanup, 13:51:32Z         │
│                                                                        │
│ CAUSA RAÍZ — establecida, no conjeturada                               │
│   stale_in_process_head_cache. Las líneas 107 y 108 declaran el MISMO   │
│   prev_entry_hash (20b26269… = cabeza de la línea 106). Dos procesos    │
│   cachearon la cabeza a las 13:47:55 y ninguno la releyó.              │
│   Corregido por el commit 8c033fa el 2026-06-15 14:21:43Z — 27 min      │
│   DESPUÉS del fork.                                                    │
│                                                                        │
│ RIESGO                                                                 │
│   autenticidad del contenido    NO AFECTADA  (hash_errors = 0)         │
│   verificabilidad de secuencia  AFECTADA localmente (2 de 19 818)      │
│   conclusiones regulatorias     NINGUNA se apoya en ese tramo           │
│                                                                        │
│ MEDIDAS PREVENTIVAS                                                    │
│   ✓ flock + invalidación de caché dentro del lock   8c033fa            │
│     evidencia: 19 710 entradas posteriores, 0 rupturas                  │
│   ☐ writer_pid / writer_host / writer_identity por entrada             │
│   ☐ fork_baseline.json validado contra excepciones                     │
│   ☐ NEW_FORKS_SINCE_BASELINE > 0 ⇒ FAIL en Gate 0                      │
│   ☐ write_event nunca falla en silencio                                │
│                                                                        │
│ SE PIDE: reportar CHAIN_CONTINUITY como                                │
│   ACCEPTED_WITH_DOCUMENTED_EXCEPTION para ESTE entry_id.               │
│ NO SE PIDE: declarar la cadena íntegra, ni part11_compliant global,    │
│   ni aceptar forks futuros, ni reescribir nada.                        │
│                                                                        │
│ MOTIVO *  [ ......... ]   FIRMA [ id ] [ nombre ]                      │
│                     [ Aceptar ]        [ Rechazar ]                    │
└────────────────────────────────────────────────────────────────────────┘
```

`Aceptar` está deshabilitado hasta que las **cinco** medidas preventivas
estén en ✓. Aceptar una excepción cuya prevención no está implementada es
aceptar que vuelva a pasar.

---

## 9. Panel F — D4-A

**Ruta:** `#gobierno/d4a` · **Gate:** G8 · **Familia:** `D4`

```
┌─ D4-A — Presupuesto de ejecución del corpus ──────────────────────────┐
│                                                                        │
│ PRECONDICIONES                                                         │
│   ☐ pack 211 aprobado — nº final de criterios     → G4a                │
│   ☐ modelo recalificado — latencia p50/p95        → G6                 │
│   D4_A_READY = false                                                    │
│                                                                        │
│ ⚠ Las cifras siguientes son de CALIBRACIÓN, no el presupuesto.          │
│   Se calculan con el catálogo de HOY (pack 211 con 0 criterios) y       │
│   con min_per_1k_tokens = 5,8 medido en UNA sola corrida.              │
│                                                                        │
│ PLAN RESUELTO                                                          │
│   doc      tipo  req  chunks  llamadas   tiempo                        │
│   RW-0005  FS     18    27       54      20,1 h                        │
│   RW-0006  URS    10     9       27       6,7 h                        │
│   RW-0014  DS      4     8       24       2,8 h                        │
│   RW-0011  DS      4     7       21       2,3 h                        │
│   RW-0012  DS      4     7       21       2,3 h                        │
│   ────────────────────────────────────────────────                     │
│   total                        147      34,3 h                         │
│                                                                        │
│ D4-A — se calcula en G8                                                │
│   max_calls                  <pendiente>                               │
│   estimated_runtime min/likely/max   <pendiente> / <…> / <…>           │
│   hard_stop_calls            <max_calls × 1,25>                        │
│   hard_stop_wall_time        <runtime_max × 1,30>                      │
│   checkpoint_mode            per_document                              │
│   resume_fingerprint_required true                                     │
│   ventana de ejecución       [ desde ] [ hasta ]                       │
│                                                                        │
│ ⓘ Cada criterio añadido al pack 211 cuesta ≈ 20 min solo en RW-0005.   │
│ ⓘ Ejecutar antes de aprobar los packs cuesta repetirlo entero:          │
│   cambiar requirements.yaml mueve catalog_sha256 e invalida todos       │
│   los checkpoints.                                                     │
│                                                                        │
│                   [ Registrar D4-A ]  ← deshabilitado                  │
└────────────────────────────────────────────────────────────────────────┘
```

Los campos con `<pendiente>` **no son editables a mano**: los calcula el
backend con la fórmula de `MODEL_REQUALIFICATION_AND_D4A_SPEC.md` §5.2. La UI
no acepta que alguien escriba "40 h" — que es exactamente lo que §8.2 del
plan prohíbe.

---

## 10. Estados de error, comunes a los seis paneles

| Código | Cuándo | Qué muestra |
|---|---|---|
| **422** | identidad genérica/vacía, motivo vacío, conjunto objetivo vacío, validador en rojo | el campo concreto, resaltado, con el texto del validador |
| **409** | `state_hash` obsoleto, decisión ya registrada | diff entre lo leído y lo actual + botón `Recargar` |
| **404** | propuesta o decisión previa inexistente | mensaje y vuelta al índice |
| **500** | fallo del backend | el error crudo, sin maquillar, y **ningún** dato parcial |
| **precondición** | gate anterior abierto | botón deshabilitado + **cuál** precondición falta + enlace al panel que la cierra |

Regla sobre el 500: la UI **nunca** muestra un estado de gobernanza que no
pudo leer. Prefiere un error visible a un valor por defecto. Un
`FORMAL_USE_ELIGIBILITY` que aparece como `false` porque el backend cayó es
indistinguible de uno que es `false` de verdad — y ese es el tipo de
ambigüedad que este trabajo entero existe para eliminar.

---

## 11. Lo que este diseño NO hace

- No modifica ningún archivo de `factory/ui/`.
- No implementa ningún endpoint.
- No reemplaza la vista W5 actual (`w5_decisions.js`): convive durante la
  transición y se retira en G8.
- No añade una superficie de decisión nueva: es **la misma** familia/almacén/
  resolver, expuesta a un humano.
