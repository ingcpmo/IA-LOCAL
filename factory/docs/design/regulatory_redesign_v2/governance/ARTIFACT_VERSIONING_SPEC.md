# ARTIFACT_VERSIONING_SPEC — §6 del plan (+ resolución 210/211)

**Estado:** DISEÑO. No implementado. No cambia ninguna versión.
**Cierra:** A-7 (grano de aprobación), A-9 (alcance ya decidido pero
invisible).

---

## 1. La inconsistencia actual, medida

| Artefacto | Versión declarada | Hash real (calculado 2026-07-29) | Hash de referencia | Veredicto |
|---|---|---|---|---|
| `factory/regulatory/requirement_catalog/requirements.yaml` | `catalog_version: 1.0` | `a83c81682309af41615a86f93498a2d31b7b2316a2e30ad56fdcfb3b8a9e55ae` | `6486405abecd729d85e32ec4a9af03cd13ad144162ebcb300ee9d25016202b8d` | **hash cambiado, versión igual** |
| `factory/regulatory/applicability_matrix.yaml` | `matrix_version: "2.1"` | — | `MC-0001.metadata.matrix_version = "2.0"` | **versión cambiada, aprobación no** |
| `factory/engines/gmpai_integrity/prompts/cgmp211_prompts.yaml` | `prompt_version: "1.0.0"` | — | **ausente** del fingerprint calificado | **artefacto nuevo fuera de la calificación** |
| `factory/regulatory/model_qualification/qualification_record.json` | `QUALIFIED_FOR_VALIDATION_ONLY` | — | fingerprint de `2026-07-28T13:32:46Z` | **invalidada** por los tres anteriores |

### 1.1 Sobre `cgmp211_prompts.yaml` — el gate funciona

`model_qualification_gate.py:144-148` enumera los prompts por **glob**
dinámico:

```python
prompts = Path(__file__).parent.parent / "engines/gmpai_integrity/prompts"
for name in sorted(p.name for p in prompts.glob("*_prompts.yaml")):
    prompt_versions[name] = ce.load_prompt_meta(prompts / name).get("prompt_version")
```

El registro congelado el 2026-07-28 lista **cuatro** prompts (`alcoa` 1.1.0,
`annex11` 1.1.0, `part11` 1.1.0, `traceability` 1.0.0). En disco hay
**cinco**: se añadió `cgmp211_prompts.yaml` 1.0.0 el 2026-07-29 junto con el
agente de Part 211.

> **Hallazgo C-1 (positivo):** el fingerprint recomputado hoy **no coincide**
> con el almacenado, por dos causas independientes —`catalog_sha256` y
> `prompt_versions`— y el gate por tanto reporta `QUALIFICATION_INVALIDATED`
> correctamente. Es la primera pieza del sistema que **sí** detectó un cambio
> material sin que nadie se lo recordara. El glob dinámico es la razón: si la
> lista fuera estática, añadir un prompt habría pasado inadvertido. **Ese
> patrón —enumerar el mundo, no una lista congelada— es el que este spec
> generaliza a los cinco artefactos.**

---

## 2. Regla general de versionado

Se aplica a **cinco** clases de artefacto: catálogo, matriz de aplicabilidad,
evidence packs, prompts y Golden Dataset.

```yaml
version_record:
  artifact: catalog | applicability_matrix | evidence_pack | prompt | golden_dataset
  artifact_id: <id>                 # ruta relativa, o requirement_id para packs
  version: <semver>
  sha256: <hash del contenido canonicalizado>
  previous_version: <semver | null>
  previous_sha256: <hash | null>
  approved_by_decision: <decision_instance_id>
  created_at: <ISO-8601 UTC>
```

Almacén: `factory/registry/artifact_versions.jsonl`, append-only, mismo
patrón que el almacén de decisiones.

### 2.1 La invariante

```
sha256 cambia  ⟺  version cambia  ⟺  existe una decisión ACTIVE que la aprueba
```

Es una **triple** equivalencia y las tres direcciones importan:

| Dirección | Qué previene | Caso real que lo motiva |
|---|---|---|
| hash cambia ⇒ versión cambia | cambiar contenido en silencio | `requirements.yaml` con `1.0` y hash `a83c8168…` |
| versión cambia ⇒ hash cambia | "versionar" sin cambiar nada, para simular revisión | — |
| versión cambia ⇒ hay decisión | versionar sin aprobación humana | `matrix_version: "2.1"` con `MC-0001` cubriendo la 2.0 |

### 2.2 Canonicalización

El hash se calcula sobre el **contenido semántico**, no sobre los bytes
crudos: reordenar claves de un YAML o cambiar un comentario no debe disparar
una versión nueva, y añadir un criterio sí.

| Artefacto | Se hashea |
|---|---|
| `catalog` | `yaml.safe_load` → JSON con `sort_keys=True`, `separators=(',',':')`, excluyendo `catalog_version`, `generated_at` y `run_context` |
| `applicability_matrix` | ídem, excluyendo `matrix_version`, `approval` y comentarios |
| `evidence_pack` | los 6 campos gobernados del pack (§2.1 de `EVIDENCE_PACK_GOVERNANCE_AND_D2A_SPEC.md`) |
| `prompt` | el YAML completo excluyendo `prompt_version` |
| `golden_dataset` | la lista de casos, ordenada por `case_id` |

Excluir el propio campo de versión es obligatorio: si no, cambiar la versión
cambiaría el hash y la invariante sería trivialmente cierta y por tanto
inútil.

### 2.3 Guardia de Gate 0

`factory/scripts/ops/factory_selfcheck.sh`, paso nuevo:

```
7/7  artifact version consistency
     para cada artefacto de las 5 clases:
       h := sha256_canonico(archivo)
       v := version_declarada(archivo)
       r := ultimo version_record de ese artifact_id
       FAIL si h != r.sha256 y v == r.version         ← "hash cambiado con versión igual"
       FAIL si v != r.version y h == r.sha256         ← "versión cambiada sin contenido"
       FAIL si v != r.version y no existe decisión ACTIVE que apruebe v
       WARN si el artefacto no tiene ningún version_record   ← estado inicial
```

Los tres primeros son `FAIL` desde el día uno: son corrupción de trazabilidad.
El cuarto es `WARN` hasta G4, porque hoy **ningún** artefacto tiene
`version_record` — el almacén no existe. El bootstrap (§4) los crea.

---

## 3. Corrección de la inconsistencia del catálogo

### 3.1 Qué cambió entre `6486405a…` y `a83c8168…`

El hash de referencia se congeló en `qualification_record.json` el
`2026-07-28T13:32:46Z`. Después, el 2026-07-29, se añadió el requisito
`21_CFR_211.68(b)` (20 requisitos ahora, 19 antes) con su bloque de citación,
contexto y estados de elegibilidad.

**El cambio es material:** añade una regla predicado de la que dependen los 5
requisitos de Part 11 (`predicate_rule_id = 21_CFR_211.68(b)`), y añade un
`source_id` nuevo al catálogo.

### 3.2 Versión propuesta: **2.0**

| Opción | Argumento a favor | Argumento en contra | Veredicto |
|---|---|---|---|
| `1.1` | "solo se añadió un requisito" | el requisito añadido es la regla predicado de otros 5; además incorpora un `source_id` nuevo al catálogo. No es retrocompatible: un checkpoint de `1.0` no es reanudable | descartada |
| **`2.0`** | cambio material que invalida checkpoints, calificación y contratos de salida (`num_predict` deriva del número de criterios) | ninguno | **elegida** |
| `1.0` (mantener) | — | es el estado defectuoso actual | descartada |

Criterio semántico general para el catálogo, para que la próxima vez no haya
que deliberar:

```
MAYOR  se añade/retira un requisito, un source_id, o cambia una regla predicado
       ⇒ invalida checkpoints y calificación
MENOR  cambian criterios interpretativos de un pack existente
       ⇒ invalida checkpoints (num_predict cambia), no invalida el alcance
PATCH  correcciones de texto sin efecto en criterios ni en el contrato de salida
       ⇒ no invalida nada, pero SIGUE exigiendo version_record y decisión
```

### 3.3 El `version_record` resultante

```yaml
artifact: catalog
artifact_id: factory/regulatory/requirement_catalog/requirements.yaml
version: "2.0"
sha256: a83c81682309af41615a86f93498a2d31b7b2316a2e30ad56fdcfb3b8a9e55ae
previous_version: "1.0"
previous_sha256: 6486405abecd729d85e32ec4a9af03cd13ad144162ebcb300ee9d25016202b8d
approved_by_decision: ARTIFACT_VERSION-2026-001
created_at: <fecha de la firma>
```

> **Advertencia de orden, y es la que más cuesta si se ignora:** el hash
> `a83c8168…` es el del catálogo **de hoy**, con el pack 211 todavía vacío.
> Cuando G4a apruebe los criterios interpretativos del pack 211, el catálogo
> **volverá a cambiar de hash**. Versionar a 2.0 ahora obligaría a versionar a
> 2.1 inmediatamente después.
>
> **Recomendación:** el versionado del catálogo (G4c) se ejecuta **después**
> de G4a (interpretación del pack 211), no antes. La inconsistencia actual se
> deja **declarada** —con un `version_record` provisional que la documenta— y
> se cierra con un solo salto `1.0 → 2.0` cuando el contenido esté estable.
> Versionar dos veces en 48 h no añade trazabilidad; añade ruido.

### 3.4 El catálogo `1.0` histórico

Queda **inmutable y direccionable**. Se congela una copia en:

```
factory/regulatory/requirement_catalog/versions/requirements-1.0-6486405a.yaml
```

La copia se genera desde `git show` del commit donde el hash era `6486405a…`,
**no** desde el archivo vivo. Si ese commit no existe (el catálogo pudo
cambiar sin commitear), se declara explícitamente
`historical_copy: UNAVAILABLE_NOT_COMMITTED` en el `version_record` en vez de
fabricar una reconstrucción. Un hueco declarado es trazabilidad; una
reconstrucción sin evidencia es fabricación.

---

## 4. Bootstrap del almacén

`factory/scripts/ops/bootstrap_artifact_versions.py`

Recorre las 5 clases, calcula el hash canónico de cada artefacto y emite un
`version_record` inicial con:

```yaml
approved_by_decision: null
bootstrap: true
bootstrap_note: >
  Registro inicial del estado observado el <fecha>. NO representa una
  aprobación humana. Los artefactos con approved_by_decision=null no
  habilitan conclusiones formales.
```

`approved_by_decision: null` es deliberado: el bootstrap **fotografía**, no
aprueba. Y la guardia de Gate 0 trata `null` como `WARN`, no como aprobación.

Artefactos que fotografía hoy: 1 catálogo + 1 matriz + 20 packs + 5 prompts +
1 Golden Dataset = **28 `version_record`**, de los cuales **28 con
`approved_by_decision: null`**.

---

## 5. Alcance 210 vs. 211 — **ya resuelto**

### 5.1 Evidencia decisional

`factory/layer9/decisions/decisions.jsonl:6`, `rationale` de la propuesta
`d5f72735-5b04-4468-b403-1009223e0084`, confirmada por Cesar en `786464e0`:

> *"Regla predicado que falta para determinar `predicate_rule_id` /
> `part11_scope_status` en los 5 requisitos de Part 11 (assessment de
> cobertura 2026-07-29). **Alcance reducido decidido por Capa 9: solo Part
> 211.**"*

`decisions.jsonl:8`, `rationale` de `fcf933e7-…`, confirmada en `caa2421d-…`:

> *"…Mismo fichero, mismo hash, **misma decision de Capa 9 (alcance reducido:
> solo Part 211)**."*

Dos propuestas independientes, ambas confirmadas por Cesar con
`decision_origin=human_confirmed`. **La decisión existe, está firmada y está
en la cadena de auditoría.**

### 5.2 Evidencia documental corroborante

Los 20 requisitos del catálogo por `source_id`:

| `source_id` | nº requisitos |
|---|---|
| `mhra_gxp_di_guidance_2018` | 9 |
| `ecfr_21cfr_part11` | 5 |
| `eu_gmp_annex11` | 5 |
| `ecfr_21cfr_part211` | 1 |
| **`ecfr_21cfr_part210`** | **0** |

Part 210 no está en el registry, no tiene copia local, no tiene pack, no
tiene prompt, no tiene agente y no sustenta ningún requisito. Añadirlo al
camino crítico costaría un registro de fuente + cobertura D1-A +
reverificación **sin habilitar un solo requisito**.

### 5.3 Resolución

```
SCOPE_210_VS_211_RESOLVED = SÍ — alcance = 21 CFR Part 211 ÚNICAMENTE.
Decidido por Capa 9 (Cesar) y registrado en decisions.jsonl:
  propuesta d5f72735-… → confirmación 786464e0-… (2026-07-29T02:11:29Z)
  propuesta fcf933e7-… → confirmación caa2421d-… (2026-07-29T02:25:06Z)
Corroborado por el catálogo: 0 requisitos apoyados en Part 210.
NO se requiere una decisión nueva de Cesar sobre este punto.
```

### 5.4 Lo que sí falta: visibilidad y limpieza

**El problema no es la decisión: es dónde vive.** El alcance está enterrado en
un campo `rationale` de texto libre. Ningún gate, ningún resolver y ninguna UI
pueden leerlo. Si mañana alguien propone ingerir Part 210, nada le dirá que ya
se decidió lo contrario.

**Acción 1 — estructurar.** El `payload` de la decisión migrada
`SOURCE_REGISTRATION-2026-002` gana:

```yaml
payload:
  scope_decision:
    regulation_family: "21 CFR cGMP"
    parts_in_scope: ["211"]
    parts_explicitly_excluded: ["210"]
    exclusion_rationale: >
      21 CFR 210 es ámbito y definiciones; ningún requisito del catálogo se
      apoya en él. Incorporarlo no habilitaría ningún requisito nuevo.
    decided_by: "Cesar"
    decided_at: "2026-07-29T02:11:29.299184+00:00"
    legacy_evidence: "rationale de d5f72735-… y fcf933e7-…"
```

Y el resolver expone `resolve("SOURCE_REGISTRATION", "ecfr_21cfr_part210")`
⇒ `authorized=False`, `denial_reason="excluido del alcance por decisión de
Capa 9 del 2026-07-29"`. Una futura propuesta de ingesta choca contra la
decisión existente en vez de ignorarla.

**Acción 2 — corregir los documentos.** Dos archivos, dos líneas:

| Ruta | Línea | Texto actual | Corrección |
|---|---|---|---|
| `factory/docs/design/regulatory_redesign_v2/W5V2_D1A_D2A_ADDENDUM_DRAFT.md` | 88 | `… (+ Part 210: .../part-210)` | eliminar el paréntesis; añadir nota de que Part 210 está excluido por decisión |
| `factory/docs/design/regulatory_redesign_v2/REGULATORY_COVERAGE_ASSESSMENT_W5.md` | 157 | `### 2.1 FDA-CFR-210-211 — 21 CFR Parts 210 y 211` | `### 2.1 FDA-CFR-211 — 21 CFR Part 211` + nota de alcance |

**No tocar** `factory/docs/gmpai_reanalysis/scada_asdata_corpus_evaluation.json:50`:
ahí "Part 210" aparece dentro de una nota que describe **contra qué normas
evalúa un documento del corpus del cliente**, no el alcance de la fábrica.
Corregirlo falsearía una observación sobre un documento real. Esta distinción
es exactamente la que un `sed` masivo destruiría.

---

## 6. Tests

`factory/tests/test_artifact_versioning.py`

| id | Test |
|---|---|
| VZ-01 | hash cambia + versión igual ⇒ guardia **FAIL** (fixture: `requirements.yaml` real de hoy vs. `6486405a…`) |
| VZ-02 | versión cambia + hash igual ⇒ **FAIL** |
| VZ-03 | versión cambia sin decisión `ACTIVE` ⇒ **FAIL** (fixture: matriz 2.1 con `MC-0001` cubriendo 2.0) |
| VZ-04 | canonicalización: reordenar claves del YAML ⇒ **mismo** hash |
| VZ-05 | canonicalización: cambiar un comentario ⇒ **mismo** hash |
| VZ-06 | canonicalización: añadir un `evidence_min_criteria` ⇒ hash **distinto** |
| VZ-07 | excluir el campo de versión del hash: cambiar solo `catalog_version` ⇒ mismo hash |
| VZ-08 | bootstrap emite `approved_by_decision: null` y Gate 0 lo trata como `WARN`, nunca como aprobación |
| VZ-09 | un prompt nuevo en el directorio ⇒ el fingerprint recomputado difiere (regresión de C-1: protege el glob dinámico contra volver a una lista estática) |
| VZ-10 | `resolve("SOURCE_REGISTRATION", "ecfr_21cfr_part210")` ⇒ `authorized=False` con el motivo del alcance |
| VZ-11 | los 28 artefactos reales de hoy producen 28 `version_record` deterministas (dos ejecuciones ⇒ mismos hashes) |

VZ-09 es el más valioso a largo plazo: el glob dinámico es lo único que hoy
detecta un artefacto nuevo, y es exactamente el tipo de código que una
"optimización" futura convertiría en una tupla congelada.

---

## 7. Lo que este diseño NO hace

- No cambia ninguna versión ni escribe ningún `version_record`.
- No congela la copia histórica del catálogo `1.0` (eso es G4c).
- No corrige los dos documentos con "210/211" (eso es G4c).
- No decide el alcance: ya está decidido; lo hace legible por máquina.
