# EVIDENCE_PACK_GOVERNANCE_AND_D2A_SPEC — §5 del plan

**Estado:** DISEÑO. No implementado. No aprueba ningún pack.
**Cierra:** A-7 (aprobación de grano de archivo sobre contenido de grano de
fila), A-8 (MC-0002 no existe).
**Depende de:** `EXTENSIBLE_DECISION_MODEL_SPEC.md`,
`DECISION_SCOPE_RESOLVER_SPEC.md`, `SOURCE_LIFECYCLE_SPEC.md`.

---

## 1. Un hallazgo previo que reordena las precedencias

Los **cinco** requisitos de Part 11 del catálogo declaran:

```
21_CFR_11.10(a)     predicate_rule_id = 21_CFR_211.68(b)   part11_scope_status = IN_SCOPE
21_CFR_11.10(d)     predicate_rule_id = 21_CFR_211.68(b)   part11_scope_status = IN_SCOPE
21_CFR_11.10(e)     predicate_rule_id = 21_CFR_211.68(b)   part11_scope_status = IN_SCOPE
21_CFR_11.10(g)     predicate_rule_id = 21_CFR_211.68(b)   part11_scope_status = IN_SCOPE
21_CFR_11.50_11.70  predicate_rule_id = 21_CFR_211.68(b)   part11_scope_status = IN_SCOPE
```

> **Hallazgo B-1:** el pack incompleto de `21_CFR_211.68(b)` no afecta a un
> requisito: es la **regla predicado de los cinco requisitos de Part 11**.
> Mientras ese pack esté en `PENDING_HUMAN_INTERPRETATION` con 0 criterios,
> la aplicabilidad de Part 11 se apoya en una regla predicado que el sistema
> no puede evaluar. Es coherente con el `rationale` de la decisión de alta
> (*"Regla predicado que falta para determinar `predicate_rule_id` /
> `part11_scope_status` en los 5 requisitos de Part 11"*), pero **eleva la
> prioridad del pack 211**: no es 1 requisito de 20, es la base declarada de
> 6 de los 20.

Consecuencia sobre el orden: el pack 211 no puede aprobarse "cuando toque".
Es el primero de G4.

---

## 2. Superficie de edición gobernada — sin YAML manual

### 2.1 Campos bajo gobierno

Un pack completo tiene ~30 campos. Solo **seis** son juicio regulatorio
humano y por tanto entran en este flujo:

| Campo | Qué es | Ejemplo real (`21_CFR_11.10(a)`) |
|---|---|---|
| `evidence_min_criteria` | criterios mínimos que la evidencia debe satisfacer | *"Criterios de aceptacion definidos antes de la ejecucion."* |
| `exclusion_criteria` | lo que **no** cuenta como evidencia | *"'Sistema validado' sin protocolo ni criterios de aceptacion."* |
| `weak_keywords` | términos que por sí solos no prueban nada | `[validado, validated, compliant, cumple]` |
| `typical_insufficient_evidence` | patrones observados de evidencia insuficiente | *"Cita del numero de norma sin describir como se cumple."* |
| `governed_interpretation` | la lectura regulatoria del texto canónico | párrafo de interpretación |
| `expected_doc_types` | dónde se espera encontrar la evidencia | `[URS, FS, PROTOCOL, REPORT]` |

El resto (`citation`, `context_before/after`, `source_id`, `normative_type`,
`binding_status`, los 8 campos de elegibilidad, `pack_version`, hashes) es
**derivado o determinista** y no se edita: se calcula.

### 2.2 Los tres actores

```
PROPONE   Claude / LLM
    entrada: texto canónico de la fuente verificada + context_before/after
             + el pack de un requisito análogo ya aprobado, como referencia de forma
    salida:  borrador ESTRUCTURADO POR CAMPO, cada criterio con su justificación
             y su anclaje al texto canónico (offset de carácter)
    prohibido: escribir en requirements.yaml; proponer sobre una fuente que
               no esté LOCAL_CANONICAL_COPY_VERIFIED

VALIDA    deterministas (sin LLM, sin juicio)
    V1  schema completo — los 6 campos presentes
    V2  ningún campo vacío ni con lista de 0 elementos
    V3  sin duplicados dentro de un campo (normalizados: minúsculas, sin acentos, sin puntuación final)
    V4  weak_keywords ∩ evidence_min_criteria = ∅   (un término débil no puede ser un criterio mínimo)
    V5  la cita literal del requisito (citation.citation_text) ancla al
        texto canónico REAL de la fuente verificada. REDEFINIDO (decisión
        Opción A, Cesar, 2026-08-05): antes exigía que evidence_min_criteria
        y exclusion_criteria (paráfrasis interpretativa, nunca pensada como
        cita textual) anclaran contra la norma -- imposible por diseño,
        bloqueaba D2A_READY para todo requisito real sin importar el
        progreso. citation.citation_text SÍ es la cita literal real (Fase C,
        ya verificada con match_type exacto/normalizado para los 20
        requisitos) -- es lo que V5 debe anclar. Los criterios
        interpretativos siguen sin exigir coincidencia textual (no lo son
        por naturaleza); se evalúan por V1-V4/V6-V7 y por juicio humano en
        APRUEBA.
    V6  expected_doc_types ⊆ document_types de applicability_matrix.yaml
    V7  ningún criterio es idéntico a un criterio de otro requisito distinto
        (cierra el defecto ya conocido de req_id duplicado que sobrescribía en silencio)
    V8  hash del pack: sha256 del subconjunto de campos gobernados, canonicalizado
    V9  la fuente del pack está en LOCAL_CANONICAL_COPY_VERIFIED
    V10 resolve("D1", pack.source_id).authorized == True
    salida: PackValidationReport {passed: bool, failures: [{code, campo, detalle}]}

APRUEBA   humano — UI §9.C
    aprobar                    → decisión D2, decision_type ADDENDUM
    devolver con comentario    → el borrador vuelve a PROPONE con el comentario
    rechazar                   → el borrador se descarta; queda registrado el rechazo
```

**El usuario nunca edita YAML a mano.** La UI presenta un campo por criterio,
con el texto canónico anclado al lado. `requirements.yaml` se escribe **solo**
como consecuencia de una aprobación, por un aplicador que exige el
`decision_instance_id` — mismo patrón que `apply_source_registration()`.

### 2.3 Por qué VALIDA va entre medias y no después

Si el humano aprueba primero y se valida después, un fallo de validación deja
una aprobación firmada sobre contenido que no se puede aplicar — y la única
salida es una corrección, que ensucia el histórico por un error de forma. Con
VALIDA antes, el humano solo ve borradores que ya pasan los 10 validadores; lo
que aprueba es juicio regulatorio, no ortografía de schema.

Corolario: **VALIDA no puede fallar después de APRUEBA.** Si entre la
validación y la aprobación cambia el texto canónico o el estado de la fuente,
la aprobación se rechaza con **409** y hay que revalidar. Misma lógica que
`apply_source_registration()` l.229 revalidando unicidad *después* de la
propuesta.

---

## 3. Versionado por aprobación

Cada aprobación produce:

```yaml
pack_version: <semver>          # 1.0-draft → 2.0 ; 2.1-draft → 2.1
pack_sha256: <hash de los 6 campos gobernados, canonicalizados>
previous_pack_sha256: <hash anterior | null>
approved_by_decision: <decision_instance_id>   # ej. D2-2026-002
approved_at: <ISO-8601 UTC>
```

E invariante, verificada por test:
**`pack_sha256` cambia ⟺ `pack_version` cambia ⟺ existe una decisión D2
`ACTIVE` que aprueba esa versión.** Es la misma invariante de
`ARTIFACT_VERSIONING_SPEC.md` §2 aplicada al grano del pack.

### 3.1 Grano de la aprobación — cierra A-7

**Un pack, una decisión, un `requirement_id` en `resolved_target_ids`.**

Nunca "los 20 packs" en un solo registro, y nunca una aprobación de grano de
archivo como la de `applicability_matrix.yaml` (`approval.status:
human_confirmed` a nivel de fichero mientras el propio comentario reconoce que
`MC-0001` no cubre las filas de 211).

Consecuencia práctica: `resolve("D2", "21_CFR_11.10(a)")` y
`resolve("D2", "21_CFR_211.68(b)")` dan respuestas **independientes**. Un pack
aprobado no arrastra a los demás, y un pack pendiente no bloquea a los demás.
La cobertura efectiva de D2 es la unión de los `requirement_id` aprobados —
exactamente el modelo de §5.2 del spec extensible.

---

## 4. Unificación D2-A / MC-0002

### 4.1 Qué es MC-0002 hoy

**Nada.** `grep -rn "MC-0002\|MC_0002"` sobre todo el árbol devuelve 3
ocurrencias, **todas en documentos de diseño**:

- `W5V2_D1A_D2A_ADDENDUM_DRAFT.md:247` — *"se requiere una nueva confirmación
  explícita de Cesar (`MC-0002` o …)"*
- `factory/docs/W5V2_RESUMEN_SESION_2026-07-29.md:130`
- el propio plan

Cero apariciones en código, datos, auditoría o misiones. **MC-0002 es un
identificador propuesto y nunca creado.**

`MC-0001` **sí** existe: `decisions.jsonl:5`, `decided_by: "Cesar"`,
`decision_origin: "human_confirmed"`, `2026-07-17T16:26:33.561688Z`,
`action: "w5v2_applicability_matrix_approval"`,
`metadata.matrix_version: "2.0"`, `requirements_approved: 19`.

### 4.2 La decisión de diseño

> **No se unifican dos sistemas: se decide no crear el segundo.**

La aprobación de packs se registra como **familia `D2` del modelo extensible**,
`decision_type=ADDENDUM`, un registro por pack. `MC-0002` **no se crea**.

Y un paso más, coherente con el resto: `MC-0001` se migra a la familia
`APPLICABILITY_MATRIX` (`MIGRATED_FROM_SYSTEM_A`, `resolved_target_ids:
["2.0"]`, `payload.legacy_decision_id: "MC-0001"`). Mission Control deja de
tener un espacio de identificadores propio; pasa a ser **superficie de UI** que
emite decisiones del modelo único.

| | Antes | Después |
|---|---|---|
| Identificadores | `MC-000X` (Mission Control) + `D1..D5` (W5) + UUID4 (Sistema A) | `<FAMILIA>-<año>-<secuencia>` |
| Almacenes | `decisions.jsonl` + `w5_human_decisions.jsonl` | `decisions_v2.jsonl` |
| Lectura | ninguna para autorizar | `DecisionScopeResolver`, único |
| Aprobación de packs | `D2_evidence_packs` (sin objetivo) **o** `MC-0002` (inexistente) | `D2-<año>-<n>` ADDENDUM, un `requirement_id` |

**Sin doble fuente de verdad: un evento, un registro, una lectura vía
resolver.**

### 4.3 Migración de la aprobación de la matriz

`applicability_matrix.yaml` conserva su bloque `approval` como **metadato
legible**, y se le añade la marca de que no es autoritativo:

```yaml
approval:
  status: "human_confirmed"
  decision_id: "MC-0001"
  approved_by: "Cesar"
  approved_at_utc: "2026-07-17T16:26:33Z"
  covers_matrix_version: "2.0"          # ← NUEVO: explicita el grano real
  authoritative: false                  # ← NUEVO: la autoridad es el resolver
  resolver_family: APPLICABILITY_MATRIX
```

`covers_matrix_version: "2.0"` frente a `matrix_version: "2.1"` hace que la
inconsistencia sea **legible por máquina**, no solo por un humano que lea el
comentario. Y `authoritative: false` impide que un gate futuro lea
`approval.status` y concluya que la 2.1 está aprobada.

La matriz v2.1 requiere entonces su propia decisión
`APPLICABILITY_MATRIX-2026-002` con `resolved_target_ids: ["2.1"]`, que es
precisamente la *"confirmacion humana nueva"* que el comentario de la matriz
(l.50-52) ya pedía.

---

## 5. Precondiciones de D2-A

`D2_A_READY` es **calculado**, nunca declarado a mano:

```python
def d2a_ready(requirement_id: str) -> D2AReadiness:
    entry  = catalog[requirement_id]
    source = registry[entry.source_id]
    return D2AReadiness(
        source_verified   = lifecycle_state(source) == "LOCAL_CANONICAL_COPY_VERIFIED",
        source_covered    = resolve("D1", entry.source_id).authorized,
        pack_complete     = validate_pack(entry).passed,
        matrix_approved   = resolve("APPLICABILITY_MATRIX", matrix_version).authorized,
        catalog_versioned = version_guard(catalog).consistent,
        ready             = all(...),
    )
```

Estado hoy, requisito por requisito:

| Precondición | `21_CFR_211.68(b)` | Los otros 19 |
|---|---|---|
| fuente en `LOCAL_CANONICAL_COPY_VERIFIED` | ❌ `pending_reverification` | ❌ las 3 igual |
| fuente cubierta por D1 | ❌ `NOT_COVERED` | ❌ `RECONSTRUCTED_PENDING_FORMAL_CORRECTION` |
| pack completo | ❌ 0 criterios de 3 tipos | ✅ 2–9 `evidence_min_criteria` cada uno |
| matriz aprobada | ❌ `MC-0001` cubre 2.0, vigente 2.1 | ❌ igual |
| catálogo versionado | ❌ `1.0` con hash `a83c8168…` ≠ `6486405a…` | ❌ igual |
| **`D2_A_READY`** | **false** | **false** |

**Ningún requisito está listo hoy**, y por razones distintas: los 19 antiguos
solo fallan por precondiciones de entorno (fuente, matriz, catálogo); el 211
falla además por contenido propio.

### 5.1 Orden derivado

```
G3  reverificación de las 4 fuentes          → source_verified ✅
G4a interpretación humana del pack 211       → pack_complete ✅ (211)
G4b aprobación de la matriz v2.1             → matrix_approved ✅
G4c versionado del catálogo → 2.0            → catalog_versioned ✅
     ↓
G5  D2 ADDENDUM por cada requirement_id
```

G4a, G4b y G4c son **paralelizables** entre sí; los tres dependen de G3 y los
tres bloquean G5.

Nota sobre G4c: versionar el catálogo cambia `catalog_sha256`, lo que invalida
todo checkpoint de corrida. Por eso G4c va **antes** de cualquier ejecución y
después de todos los cambios de contenido — y por eso G4a debe cerrarse antes
que G4c: aprobar el pack 211 cambia `requirements.yaml` y movería otra vez el
hash.

---

## 6. Tests

`factory/tests/test_evidence_pack_governance.py`

| id | Test |
|---|---|
| P-01 | V1…V10 fallan cada uno por separado con un pack construido para violarlo |
| P-02 | `weak_keywords ∩ evidence_min_criteria ≠ ∅` ⇒ rechazo (V4) con caso real: `"validado"` como criterio mínimo |
| P-03 | criterio sin anclaje al texto canónico ⇒ rechazo (V5) |
| P-04 | criterio idéntico entre dos `requirement_id` ⇒ rechazo (V7) |
| P-05 | el pack real `21_CFR_211.68(b)` de hoy ⇒ **falla V1, V2** (fixture del estado actual) |
| P-06 | los 19 packs reales de hoy ⇒ **pasan V1–V8** y **fallan V9, V10** (fuente no verificada, no cubierta) |
| P-07 | aprobar sin `decision_instance_id` ⇒ el aplicador rechaza |
| P-08 | `pack_sha256` cambia sin `pack_version` ⇒ Gate 0 lo detecta |
| P-09 | aprobación de un pack **no** autoriza otro (`resolve("D2", …)` independiente) |
| P-10 | cambio del texto canónico entre VALIDA y APRUEBA ⇒ **409** |
| P-11 | `d2a_ready()` de los 20 requisitos hoy ⇒ los 20 `false`, con los motivos exactos de §5 |
| P-12 | `applicability_matrix.yaml` con `authoritative: false` ⇒ ningún consumidor lo usa para autorizar |

P-05 y P-06 son fixtures del **estado real de hoy**: si algún día pasan
cuando no deben, es que alguien cambió los datos sin pasar por el flujo.

---

## 7. Lo que este diseño NO hace

- No aprueba ningún pack ni redacta ningún criterio.
- No modifica `requirements.yaml` ni `applicability_matrix.yaml`.
- No crea `MC-0002` — decide explícitamente no crearlo.
- No invoca ningún LLM: el paso PROPONE se diseña aquí y se ejecuta en G4a,
  y es además la **primera inferencia** que tocaría el texto de Part 211, lo
  que exige que G3 haya cerrado antes.
