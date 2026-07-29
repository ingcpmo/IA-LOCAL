# W5 V2 — Assessment de cobertura regulatoria

**Fecha:** 2026-07-29 (UTC) · **Autoridad:** Capa 9 = Cesar · **Ejecutor:** Capa 8
**Naturaleza:** corrida de **solo lectura**. Cero descargas, cero llamadas a
Ollama, cero cambios de estado.
**Commit del árbol:** `bd70506` · **Gate 0:** PASS=5 FAIL=0

```
ASSESSMENT_CONFIDENCE = SCOPE_LEVEL_PRELIMINARY
CLAUSE_LEVEL_MAPPING  = PENDING_CANONICAL_COPIES
REGULATORY_COMPLIANCE = NOT_DETERMINED
PRODUCTION_ENABLEMENT = BLOCKED
```

> **Límite metodológico declarado.** Ninguna de las 8 fuentes candidatas tiene
> copia canónica local verificada. Por tanto **todo** este documento opera en
> **Nivel 1 — mapeo de alcance**: se razona sobre la materia que cada
> regulación gobierna, no sobre su texto. **No se cita ningún numeral como
> texto canónico verificado.** Las referencias a numerales que aparecen abajo
> son *punteros de localización esperada para la verificación futura*, no
> citas. El mapeo a nivel de numeral (Nivel 2) exige
> `LOCAL_CANONICAL_COPY_VERIFIED` y queda marcado
> `CLAUSE_MAPPING = PENDING_CANONICAL_COPY` en cada ficha.

---

## 1. Insumos verificados

Todo lo que sigue se leyó de artefactos reales en esta corrida.

| # | Insumo | Ruta | SHA-256 |
|---|---|---|---|
| 1 | Allowlist (14 documentos) | `factory/regulatory/scope/source_baseline_allowlist.yaml` | `ddaca093…0d6a96d` |
| 2 | Matriz de aplicabilidad v2.0 (`MC-0001`, human_confirmed) | `factory/regulatory/applicability_matrix.yaml` | `ac4590c3…fcc2218b` |
| 3 | Catálogo de 19 requisitos | `factory/regulatory/requirement_catalog/requirements.yaml` | `6486405a…16202b8d` |
| 4 | Registry de fuentes normativas | `factory/regulatory/sources/registry.json` | `6c48dd1d…6fbb17268a` |
| 5 | Registry de fuentes de casos (conectores) | `factory/regulatory/source_registry.yaml` | `39c6f8b7…ed224a2f` |
| 6 | Plan W5 V2 (objetivo y gates) | `docs_plan/W5_INSTRUCCIONES_DISENO_REGULATORY_REDESIGN_V2.md` | `d636379e…ac7106c6` |
| 7 | Plan de corridas del corpus | `factory/docs/W5V2_PLAN_CORRIDAS_CORPUS.md` | `253f4ab4…bc7a61db` |
| 8 | Decisiones D1–D5 | `factory/layer9/decisions/w5_human_decisions.jsonl` | `5bdd0f29…b87dadf19` |

### 1.1 Allowlist — 14 documentos, tipos y estados vigentes

T-039 (`D3_T039`, APPROVE) está **registrada pero no aplicada** (ver
`W5V2_PAUSE_STATE.md` §3.4). Se usa la clasificación vigente y se anota.

| file_id | Documento | doc_type | processing_state | ¿Analizable hoy? |
|---|---|---|---|---|
| RW-0001 | 215115305 MCCPDC PLC Panel Rev 0 | DRAWING | OCR_REQUIRED | No |
| RW-0002 | SCADA-PCS Misc PLC SI Prop | OTHER | ORIGINAL_SOURCE_CONFIRMED | No (tipo fuera de matriz) |
| RW-0003 | SCADA-PCS Misc PLC SAT3 Scanned-1 | REPORT | OCR_REQUIRED | No |
| RW-0004 | SCADA-PCS Misc PLC System FS_v1.2-2 | FS | **DUPLICATE** de RW-0005 | No |
| **RW-0005** | SCADA-PCS Misc PLC System FS_v1.2 | **FS** | ORIGINAL_SOURCE_CONFIRMED | **Sí** |
| **RW-0006** | SCADA-PCS Misc PLC System URS v2.1 | **URS** | ORIGINAL_SOURCE_CONFIRMED | **Sí** |
| RW-0007 | T-039 Design Docs (.docm) | OTHER | ORIGINAL_SOURCE_CONFIRMED | No (es un *transmittal*) |
| RW-0008 | T-039 Design Docs (.pdf) | OTHER | **HUMAN_REVIEW_REQUIRED** | No (bloqueado; D3 sin aplicar) |
| RW-0009 | T-041 SAT3 Completed | REPORT | ORIGINAL_SOURCE_CONFIRMED | No |
| RW-0010 | 215115305_SYS_ARCH | DRAWING | ORIGINAL_SOURCE_CONFIRMED | No |
| **RW-0011** | MCCPDC EMS Control Block Narrative revB | **DS** | ORIGINAL_SOURCE_CONFIRMED | **Sí** |
| **RW-0012** | MCCPDC PCS Signal Interface Control Block Narrative | **DS** | ORIGINAL_SOURCE_CONFIRMED | **Sí** |
| RW-0013 | PCS-CP01 Alarms Hard Soft IO Listing revH | OTHER | ORIGINAL_SOURCE_CONFIRMED | No |
| **RW-0014** | MCCPDC WFI Control Block Narrative revB | **DS** | ORIGINAL_SOURCE_CONFIRMED | **Sí** |

Tipos documentales presentes en la allowlist: **FS, URS, DS** (modelados) +
DRAWING, REPORT, OTHER (no modelados). **Ausentes por completo: CS, RA, IQ,
OQ, PQ, SOP** — hecho decisivo para clasificar varias candidatas.

### 1.2 Las 19 requirement_id y su fuente

| Bloque | requirement_id | source_id | binding_status |
|---|---|---|---|
| Part 11 (5) | `21_CFR_11.10(a)`, `(d)`, `(e)`, `(g)`, `21_CFR_11.50_11.70` | `ecfr_21cfr_part11` | binding_regulation |
| Annex 11 (5) | `ANNEX11_4`, `7.1`, `9`, `12`, `17` | `eu_gmp_annex11` | binding_requirement |
| ALCOA+ (9) | `ALCOA_ATTRIBUTABLE`, `LEGIBLE`, `CONTEMPORANEOUS`, `ORIGINAL`, `ACCURATE`, `COMPLETE`, `CONSISTENT`, `ENDURING`, `AVAILABLE` | `mhra_gxp_di_guidance_2018` | non_binding_guidance |

Las 19 están en `review_status: covered`, `pack_lifecycle_status: DRAFT`,
`source_verification_status: PENDING_REVERIFICATION`,
`production_eligibility: BLOCKED`.

### 1.3 Fuentes actuales del registry — **discrepancia con "tres"**

`ACTUAL_CURRENT_SOURCE_COUNT` no es un número único: **existen dos registries
distintos** y el enunciado de "tres fuentes" solo describe a uno.

**Registry normativo** (`factory/regulatory/sources/registry.json`, v1.1) — el
que sustenta los 19 requisitos: **3 fuentes**.

| source_id | normative_type | jurisd. | integridad local | vigencia |
|---|---|---|---|---|
| `ecfr_21cfr_part11` | regulation | US | PASS | `pending_reverification` |
| `eu_gmp_annex11` | official_guidance | EU | PASS | `pending_reverification` |
| `mhra_gxp_di_guidance_2018` | official_guidance | UK | PASS | `pending_reverification` |

**Registry de fuentes de casos** (`factory/regulatory/source_registry.yaml`,
v3) — feeds de *enforcement/casos*, no de requisitos: **9 entradas**, 3
`connected` (`openfda_enforcement`, `openfda_device_enforcement`,
`openfda_food_enforcement`) y 6 `not_connected` (`fda_warning_letters`,
`fda_483_public`, `fda_data_dashboard`, `eudragmdp_nc`, `ema_gmp_public`,
`internal_docs`).

**Reporte de la discrepancia:** el conteo total de entradas de fuente
registradas en la fábrica es **12**, no 3. La afirmación "las tres fuentes" es
correcta **solo** para el registry normativo. Ninguna de las 9 entradas del
registry de casos aporta requisitos: son datos de enforcement, no texto
normativo, y **ninguna es sustituto de una fuente candidata**. El assessment
continúa sobre las 3 reales del registry normativo, como exige el punto 1.4
de las instrucciones.

Coherencia adicional verificada: `eu_gmp_annex11` está en el registry
normativo, mientras `ema_gmp_public` (registry de casos) apunta a páginas
públicas de EMA — no se confundan; la candidata `EU-GMP-CH4` no está cubierta
por ninguna de las dos.

### 1.4 Objetivo y gates de W5 V2 (marco de la decisión)

Del §1 del plan (`d636379e…`): analizar de forma gobernada **los documentos
originales de Rockwell**, compararlos contra fuentes oficiales verificadas y
versionadas, y producir por documento remediable un **paquete de 9–10
artefactos** con documento candidato completo. El §1 cierra: *"NUNCA declara
automáticamente cumplimiento regulatorio integral"*.

**Este es el criterio de corte de todo el assessment**: una fuente es
`REQUIRED_FOR_W5` solo si sin ella un documento **de la allowlist** queda sin
poder evaluarse contra un requisito exigible **en ese objetivo** — no en el
universo GMP.

### 1.5 Plan de corridas vigente y una reconciliación necesaria

`W5V2_PLAN_CORRIDAS_CORPUS.md`: 147 llamadas, ~34,3 h, 5/14 documentos
analizables, base empírica **5,8 min por cada 1 000 tokens de `num_predict`**
(corrida real de `eu_annex11_agent` sobre FS_v1.2: 27 chunks / 481 min).

Al recontar la matriz contra el plan aparece una diferencia que conviene dejar
escrita, porque afecta a los números revisados de §6:

| Tipo | Celdas `expected` + `cross_reference_expected` | + `optional` | Cifra del plan |
|---|---|---|---|
| FS | 18 | 19 | **18** |
| URS | 10 | 11 | **10** |
| DS | 4 | 6 | **4** |

El plan **excluye las celdas `optional`** del conteo de requisitos aplicables
(FS: `21_CFR_11.50_11.70`; URS: idem; DS: `ALCOA_LEGIBLE`,
`ALCOA_CONSISTENT`). Es una convención defendible —la ausencia de un
`optional` no genera gap— pero significa que **hoy no se evalúa la presencia**
de firma electrónica en FS/URS ni de legibilidad/consistencia en los DS.
No se cambia nada; se registra y se hereda la misma convención en §6 para que
las cifras sean comparables.

---

## 2. Fichas de evaluación por fuente

Ocho fichas. En todas: `CONFIDENCE = SCOPE_LEVEL_PRELIMINARY`,
`CLAUSE_MAPPING = PENDING_CANONICAL_COPY`.

### 2.1 FDA-CFR-210-211 — 21 CFR Parts 210 y 211

```
SOURCE_ID = FDA-CFR-210-211
DOCUMENT_TYPES_AFFECTED = FS, URS, DS
CURRENT_REQUIREMENT_IDS_COVERED = 21_CFR_11.10(a), 21_CFR_11.10(d),
    21_CFR_11.10(e), 21_CFR_11.10(g), 21_CFR_11.50_11.70   (los 5 de Part 11)
NEW_REQUIREMENT_IDS_REQUIRED = NR-01
REGULATORY_GAP_CLOSED = ver abajo (brecha demostrable en artefacto)
REQUIRED_FOR_W5 = true            <-- clasificación principal
SUPPORTING_BUT_NOT_REQUIRED = false
CONDITIONAL = false
DEFER_TO_W6 = false
LICENSE_OR_ACCESS_RESTRICTION = false  (eCFR, texto público, misma vía ya
    usada para ecfr_21cfr_part11)
IMPACT_ON_EVIDENCE_PACKS = re-versionar 5 (los de Part 11) + 1 pack nuevo (NR-01)
IMPACT_ON_GOLDEN_DATASET = +3 casos (ver §5)
IMPACT_ON_CALL_COUNT = +58 llamadas
IMPACT_ON_RUNTIME = +2,9 h
CONFIDENCE = SCOPE_LEVEL_PRELIMINARY
CLAUSE_MAPPING = PENDING_CANONICAL_COPY
```

**La brecha, medida en el artefacto y no argumentada.** Las 5 entradas de
Part 11 del catálogo declaran hoy:

```
predicate_rule_id   = NOT_DETERMINED   (las 5)
part11_scope_status = NOT_DETERMINED   (las 5)
system_environment  = NOT_DETERMINED   (las 5)
```

21 CFR Part 11 se aplica a registros electrónicos **exigidos por una regla
predicado**; sin la regla predicado identificada, la aplicabilidad de los 5
requisitos a un documento concreto de Rockwell no puede sustentarse — y **no
existe en el registry ninguna fuente capaz de determinarla**: las 3 fuentes
actuales son el propio Part 11, Annex 11 (EU) y MHRA DI (UK). Ninguna es una
regla predicado de la FDA.

Esto no es relevancia general: es un campo del catálogo, hoy en
`NOT_DETERMINED`, que **ninguna fuente registrada puede rellenar**. Afecta a
5 de los 19 requisitos, es decir a **5 de las 18 filas del FS, 5 de las 10 del
URS y 1 de las 4 de cada DS** (§3).

**NR-01 propuesto** — *Controles de equipos automatizados* (localización
esperada: 21 CFR 211.68(b); a verificar contra copia canónica). Contenido
esperado a nivel de alcance: respaldo de registros, verificación de exactitud
de entrada/salida de datos y control de cambios de software en equipos
automatizados. Tipos: FS, DS, URS. Justificación de brecha: los documentos
analizables son especificaciones de un sistema SCADA/PLC —exactamente el
objeto de 211.68— y **ningún requisito del catálogo evalúa hoy el respaldo ni
la verificación de exactitud de E/S**; `ANNEX11_7.1` cubre almacenamiento y
protección desde la óptica EU, no el control de equipo automatizado bajo
cGMP US.

*Nota de alcance:* solo se propone la parte de Part 211 que toca directamente
a los documentos de la allowlist. Registros de lote, producción y laboratorio
(211.100, 211.188, 211.194) **no** generan requisitos en W5: no hay documento
de esos tipos en la allowlist.

---

### 2.2 EU-GMP-CH4 — EU GMP Chapter 4 (Documentation)

```
SOURCE_ID = EU-GMP-CH4
DOCUMENT_TYPES_AFFECTED = FS, URS, DS
CURRENT_REQUIREMENT_IDS_COVERED = ANNEX11_17 (refuerzo parcial: retención)
NEW_REQUIREMENT_IDS_REQUIRED = NR-02
REGULATORY_GAP_CLOSED = ver abajo
REQUIRED_FOR_W5 = true            <-- clasificación principal
SUPPORTING_BUT_NOT_REQUIRED = false
CONDITIONAL = false
DEFER_TO_W6 = false
LICENSE_OR_ACCESS_RESTRICTION = false  (EudraLex Vol. 4, publicación oficial
    gratuita de la Comisión Europea — misma vía que eu_gmp_annex11)
IMPACT_ON_EVIDENCE_PACKS = 0 a re-versionar + 1 pack nuevo (NR-02)
IMPACT_ON_GOLDEN_DATASET = +2 casos
IMPACT_ON_CALL_COUNT = +58 llamadas
IMPACT_ON_RUNTIME = +2,9 h
CONFIDENCE = SCOPE_LEVEL_PRELIMINARY
CLAUSE_MAPPING = PENDING_CANONICAL_COPY
```

**La brecha, medida en el artefacto.** El objetivo de W5 (§1 del plan) obliga
a producir **una nueva versión completa del documento corregido**. Un
documento GMP versionado exige identificación unívoca, versión, estado de
aprobación y revisión — y **ninguno de los 19 requisitos evalúa el control
documental del documento analizado**. Los 19 evalúan el *contenido técnico*
(integridad de datos, audit trail, accesos), nunca el *continente*.

Evidencia en el allowlist, no supuesta: **RW-0012 es un DS analizable con
`version: NO_DISPONIBLE`** — el extractor no encontró versión declarable. Hoy
ese documento pasaría las 4 filas de la matriz DS sin que ningún requisito
señale que carece de identificación de versión. Lo mismo aplica a RW-0002,
RW-0007, RW-0008, RW-0009, RW-0010 (todos `NO_DISPONIBLE`), aunque esos aún no
son analizables.

**NR-02 propuesto** — *Control documental: identificación, versión, aprobación
y revisión* (localización esperada: EU GMP Cap. 4, §§4.1–4.3 y 4.9; a
verificar). Tipos: URS, FS, DS. Sin NR-02, el paquete de 9 artefactos puede
generar un documento candidato corregido **sin control de versión evaluable**,
que es precisamente lo que el objetivo declarado promete entregar.

*Límite honesto:* NR-02 **no** desbloquea los documentos DRAWING / REPORT /
OTHER. Esos tipos no están en `document_types` de la matriz y siguen cayendo a
`default: review_required` hasta que AGT-APP les asigne aplicabilidad. Añadir
la fuente no sustituye esa asignación.

---

### 2.3 EU-GMP-ANNEX15 — EU GMP Annex 15 (Qualification and Validation)

```
SOURCE_ID = EU-GMP-ANNEX15
DOCUMENT_TYPES_AFFECTED = URS, FS, DS
CURRENT_REQUIREMENT_IDS_COVERED = 21_CFR_11.10(a) (solapamiento parcial:
    trazabilidad requisito<->prueba<->resultado), ANNEX11_4 (parcial)
NEW_REQUIREMENT_IDS_REQUIRED = NR-03, NR-04
REGULATORY_GAP_CLOSED = ver abajo
REQUIRED_FOR_W5 = true            <-- clasificación principal
SUPPORTING_BUT_NOT_REQUIRED = false
CONDITIONAL = false
DEFER_TO_W6 = false
LICENSE_OR_ACCESS_RESTRICTION = false  (EudraLex Vol. 4, publicación oficial
    gratuita)
IMPACT_ON_EVIDENCE_PACKS = 0 a re-versionar + 2 packs nuevos (NR-03, NR-04)
IMPACT_ON_GOLDEN_DATASET = +4 casos
IMPACT_ON_CALL_COUNT = +58 llamadas
IMPACT_ON_RUNTIME = +3,3 h
CONFIDENCE = SCOPE_LEVEL_PRELIMINARY
CLAUSE_MAPPING = PENDING_CANONICAL_COPY
```

**La brecha, medida en el artefacto.** De los 5 documentos analizables, **3
son DS** (RW-0011, RW-0012, RW-0014). Para un DS la matriz aprobada solo
declara 4 requisitos con evidencia esperada:

```
21_CFR_11.10(e)  cross_reference_expected
ANNEX11_7.1      expected
ANNEX11_17       cross_reference_expected
ALCOA_ORIGINAL   cross_reference_expected
```

Tres de esos cuatro son **cross-referencias**: la evidencia primaria vive en
otro documento. Es decir, el análisis de 3 de los 5 documentos analizables se
reduce hoy a **un solo requisito con evidencia primaria esperada**
(`ANNEX11_7.1`). Un DS de bloques de control evaluado contra un único criterio
de almacenamiento de datos no produce el "reporte de hallazgos, gaps y
desviaciones" que el objetivo exige; produce un informe casi vacío. Esa es la
brecha concreta: **documento (RW-0011, RW-0012, RW-0014) × requisito
(inexistente: adecuación del diseño y trazabilidad)**.

Annex 15 es la fuente oficial que gobierna URS, especificaciones de diseño y
su trazabilidad hacia la calificación, y es la contraparte europea vinculante
del V-model sobre el que la propia matriz dice haberse razonado.

**NR-03 propuesto** — *Trazabilidad URS → FS → DS → pruebas* (localización
esperada: Annex 15 §§2–3). Tipos: URS, FS, DS.
**NR-04 propuesto** — *Contenido mínimo de la URS: requisitos verificables,
criterios de aceptación y requisitos críticos identificados por riesgo*
(localización esperada: Annex 15 §2). Tipo: URS.

*Solapamiento declarado, no ocultado:* `21_CFR_11.10(a)` ya incluye entre sus
`evidence_min_criteria` la trazabilidad requisito↔prueba↔resultado, pero la
matriz lo marca `cross_reference_expected` en URS y FS y **no lo declara
aplicable a DS**; además su ámbito es la validación del sistema, no la
adecuación del documento de diseño. NR-03 debe redactarse acotado a la
trazabilidad **documental** entre especificaciones, y la deduplicación
requisito↔requisito es una tarea explícita del adendo D2-A.

---

### 2.4 FDA-DI-2018 — FDA Data Integrity and Compliance With Drug CGMP

```
SOURCE_ID = FDA-DI-2018
DOCUMENT_TYPES_AFFECTED = FS, URS, DS
CURRENT_REQUIREMENT_IDS_COVERED = los 9 ALCOA_* + 21_CFR_11.10(e)
NEW_REQUIREMENT_IDS_REQUIRED = NINGUNO
REGULATORY_GAP_CLOSED = ninguna brecha de cobertura; cierra una brecha de
    ANCLAJE JURISDICCIONAL (ver abajo)
REQUIRED_FOR_W5 = false
SUPPORTING_BUT_NOT_REQUIRED = true   <-- clasificación principal
CONDITIONAL = false
DEFER_TO_W6 = false
LICENSE_OR_ACCESS_RESTRICTION = false  (guidance pública FDA)
IMPACT_ON_EVIDENCE_PACKS = 9 a re-versionar SOLO si Cesar la adopta
    (añadiría fuente secundaria a los packs ALCOA); 0 packs nuevos
IMPACT_ON_GOLDEN_DATASET = 0 (no añade requisitos evaluables)
IMPACT_ON_CALL_COUNT = +0
IMPACT_ON_RUNTIME = +0 h
CONFIDENCE = SCOPE_LEVEL_PRELIMINARY
CLAUSE_MAPPING = PENDING_CANONICAL_COPY
```

**Por qué no es REQUIRED.** Los 9 requisitos ALCOA+ ya existen y ya tienen
fuente (`mhra_gxp_di_guidance_2018`, citas `exact` salvo
`ALCOA_CONTEMPORANEOUS` que es `normalized`). FDA-DI-2018 no añadiría ningún
`requirement_id` ni desbloquearía ningún documento: ningún gate de W5 falla
sin ella. Cae exactamente en la definición de SUPPORTING.

**Por qué sí conviene registrarla.** 9 de los 19 requisitos —casi la mitad del
catálogo— descansan hoy en una guía **UK y `non_binding_guidance`**. Para un
proyecto que se evalúa también contra 21 CFR Part 11, disponer de la guía DI
de la FDA daría un anclaje interpretativo en la misma jurisdicción que la
regla predicado. Es fortalecimiento de criterio, no cobertura nueva.

---

### 2.5 ICH-Q9-R1 — ICH Q9(R1) Quality Risk Management

```
SOURCE_ID = ICH-Q9-R1
DOCUMENT_TYPES_AFFECTED = URS, FS  (solo por cross-referencia)
CURRENT_REQUIREMENT_IDS_COVERED = ANNEX11_4
NEW_REQUIREMENT_IDS_REQUIRED = NINGUNO
REGULATORY_GAP_CLOSED = ninguna dentro del alcance W5
REQUIRED_FOR_W5 = false
SUPPORTING_BUT_NOT_REQUIRED = true   <-- clasificación principal
CONDITIONAL = false
DEFER_TO_W6 = false
LICENSE_OR_ACCESS_RESTRICTION = false  (ICH publica sus guidelines sin coste)
IMPACT_ON_EVIDENCE_PACKS = 1 a re-versionar SOLO si se adopta (ANNEX11_4);
    0 nuevos
IMPACT_ON_GOLDEN_DATASET = 0
IMPACT_ON_CALL_COUNT = +0
IMPACT_ON_RUNTIME = +0 h
CONFIDENCE = SCOPE_LEVEL_PRELIMINARY
CLAUSE_MAPPING = PENDING_CANONICAL_COPY
```

**Razón determinante:** `ANNEX11_4` (gestión de riesgo) tiene evidencia
primaria esperada en `RA` — y **no hay ningún documento RA en la allowlist**.
En URS y FS la matriz lo marca `cross_reference_expected`, es decir, solo se
exige que el documento *referencie* el análisis de riesgo, no que lo
contenga. Verificar esa referencia no requiere el texto de Q9. La fuente
enriquecería la interpretación del pack de `ANNEX11_4`; ningún gate falla sin
ella.

---

### 2.6 ICH-Q10 — ICH Q10 Pharmaceutical Quality System

```
SOURCE_ID = ICH-Q10
DOCUMENT_TYPES_AFFECTED = NINGUNO de los presentes en la allowlist
CURRENT_REQUIREMENT_IDS_COVERED = ninguno
NEW_REQUIREMENT_IDS_REQUIRED = NINGUNO dentro del alcance W5
REGULATORY_GAP_CLOSED = ninguna dentro del alcance W5
REQUIRED_FOR_W5 = false
SUPPORTING_BUT_NOT_REQUIRED = false
CONDITIONAL = false
DEFER_TO_W6 = true                 <-- clasificación principal
LICENSE_OR_ACCESS_RESTRICTION = false
IMPACT_ON_EVIDENCE_PACKS = 0 / 0
IMPACT_ON_GOLDEN_DATASET = 0
IMPACT_ON_CALL_COUNT = +0
IMPACT_ON_RUNTIME = +0 h
CONFIDENCE = SCOPE_LEVEL_PRELIMINARY
CLAUSE_MAPPING = PENDING_CANONICAL_COPY
```

**Razón determinante:** Q10 gobierna el sistema de calidad farmacéutico
(gestión del conocimiento, revisión por la dirección, mejora continua,
gestión del cambio a nivel de PQS). Sus objetos documentales naturales son
SOP, políticas y registros de PQS — **ninguno presente en la allowlist**.
Relevante para el programa; sin brecha documento×requisito en W5.

---

### 2.7 FDA-PV-2011 — FDA Process Validation: General Principles and Practices

```
SOURCE_ID = FDA-PV-2011
DOCUMENT_TYPES_AFFECTED = NINGUNO de los presentes en la allowlist
CURRENT_REQUIREMENT_IDS_COVERED = ninguno
NEW_REQUIREMENT_IDS_REQUIRED = NINGUNO dentro del alcance W5
REGULATORY_GAP_CLOSED = ninguna dentro del alcance W5
REQUIRED_FOR_W5 = false
SUPPORTING_BUT_NOT_REQUIRED = false
CONDITIONAL = false
DEFER_TO_W6 = true                 <-- clasificación principal
LICENSE_OR_ACCESS_RESTRICTION = false
IMPACT_ON_EVIDENCE_PACKS = 0 / 0
IMPACT_ON_GOLDEN_DATASET = 0
IMPACT_ON_CALL_COUNT = +0
IMPACT_ON_RUNTIME = +0 h
CONFIDENCE = SCOPE_LEVEL_PRELIMINARY
CLAUSE_MAPPING = PENDING_CANONICAL_COPY
```

**Razón determinante:** gobierna la validación **de proceso** (etapas 1–3:
diseño de proceso, calificación del proceso, verificación continuada). Los
documentos de la allowlist son de **sistema computarizado** (SCADA/PLC): URS,
FS, DS de automatización. La calificación de equipos/sistemas la gobierna
Annex 15, ya evaluada en §2.3. Confundir ambas produciría requisitos que
ningún documento del corpus puede satisfacer — y por diseño eso se traduce en
falsos `DOCUMENTATION_GAP`.

---

### 2.8 GAMP-5-ED2 — GAMP 5 (2ª edición)

**Verificación de copia autorizada, ejecutada en esta corrida:**

```
find . -iname "*gamp*"  (excluyendo .git, node_modules, cachés)
→ 0 resultados
```

Se buscó específicamente en `factory/regulatory/sources/` (contiene únicamente
los 3 SHA-256 de las fuentes normativas registradas) y en el árbol del
proyecto. **No existe copia autorizada de GAMP 5 en el servidor.**

```
SOURCE_ID = GAMP-5-ED2
DOCUMENT_TYPES_AFFECTED = URS, FS, DS   (solo a nivel de alcance)
CURRENT_REQUIREMENT_IDS_COVERED = ninguno de forma directa; es interpretativa
    sobre 21_CFR_11.10(a) y ANNEX11_4
NEW_REQUIREMENT_IDS_REQUIRED = NINGUNO (ver nota de naturaleza)
REGULATORY_GAP_CLOSED = no evaluable sin copia; a nivel de alcance se solapa
    con EU-GMP-ANNEX15 (§2.3), que SÍ es fuente oficial y accesible
REQUIRED_FOR_W5 = false
SUPPORTING_BUT_NOT_REQUIRED = false
CONDITIONAL = true                 <-- clasificación principal
    CONDICIÓN: (a) Cesar acredita copia con licencia ISPE en el servidor, Y
    (b) Cesar amplía el alcance de W5 para admitir guías de industria como
    fuente interpretativa registrada.
DEFER_TO_W6 = false
LICENSE_OR_ACCESS_RESTRICTION = true
    Detalle: GAMP 5 es una guía de la industria con copyright de ISPE,
    distribuida bajo licencia de pago. No hay copia en el servidor. PROHIBIDO
    descargarla u obtenerla por vías no autorizadas (regla de esta corrida y
    del §2 del plan W5 V2).
IMPACT_ON_EVIDENCE_PACKS = no evaluable sin copia
IMPACT_ON_GOLDEN_DATASET = no evaluable sin copia
IMPACT_ON_CALL_COUNT = +0 (no adoptable hoy)
IMPACT_ON_RUNTIME = +0 h
CONFIDENCE = SCOPE_LEVEL_PRELIMINARY
CLAUSE_MAPPING = PENDING_CANONICAL_COPY
```

**Nota de naturaleza, relevante para la decisión:** GAMP 5 **no es una
regulación ni una guía de autoridad**. Registrarla como fuente normativa
—junto a eCFR, Annex 11 y MHRA— cambiaría el significado de
`binding_status` en el catálogo. Si Cesar la adopta, debería entrar con un
`normative_type` propio (p. ej. `industry_guidance`) y **nunca** como
sustento único de un `requirement_id`. La mayor parte de lo que GAMP 5 aporta
al V-model de estos documentos está cubierta por Annex 15, que sí es oficial,
gratuita y verificable.

---

## 3. Matriz de cobertura

Convención (heredada del plan, §1.5): se listan las combinaciones con
`expected` o `cross_reference_expected`. `SUFFICIENT` significa *sustento
razonable a nivel de alcance* — nunca vigencia verificada: las 3 fuentes están
en `pending_reverification`, así que **toda** fila lleva implícita
`CONFIDENCE = SCOPE_LEVEL_PRELIMINARY`.

### 3.1 RW-0005 — FS_v1.2 (tipo FS) — 18 filas

| # | requirement_id | Fuente actual + estado | Cobertura | Brecha | Fuente adicional |
|---|---|---|---|---|---|
| 1 | `21_CFR_11.10(a)` | `ecfr_21cfr_part11` · pending_reverification | **INSUFFICIENT** | `predicate_rule_id=NOT_DETERMINED`: no se puede sustentar que el FS documente registros exigidos por regla predicado | FDA-CFR-210-211 (§2.1) |
| 2 | `21_CFR_11.10(d)` | idem | **INSUFFICIENT** | idem | FDA-CFR-210-211 |
| 3 | `21_CFR_11.10(e)` | idem | **INSUFFICIENT** | idem | FDA-CFR-210-211 |
| 4 | `21_CFR_11.10(g)` | idem | **INSUFFICIENT** | idem | FDA-CFR-210-211 |
| 5 | `ANNEX11_4` | `eu_gmp_annex11` · pending_reverification | SUFFICIENT | N/A (cross-ref al RA; el RA no está en la allowlist — limitación de corpus, no de fuente) | NINGUNA |
| 6 | `ANNEX11_7.1` | idem | SUFFICIENT | N/A | NINGUNA |
| 7 | `ANNEX11_9` | idem | SUFFICIENT | N/A | NINGUNA |
| 8 | `ANNEX11_12` | idem | SUFFICIENT | N/A | NINGUNA |
| 9 | `ANNEX11_17` | idem | SUFFICIENT | N/A | NINGUNA |
| 10 | `ALCOA_ATTRIBUTABLE` | `mhra_gxp_di_guidance_2018` · pending_reverification | SUFFICIENT | N/A (anclaje UK/non-binding: ver FDA-DI-2018, SUPPORTING) | NINGUNA |
| 11 | `ALCOA_LEGIBLE` | idem | SUFFICIENT | N/A | NINGUNA |
| 12 | `ALCOA_CONTEMPORANEOUS` | idem | SUFFICIENT | N/A (cita `normalized`, no `exact`) | NINGUNA |
| 13 | `ALCOA_ORIGINAL` | idem | SUFFICIENT | N/A | NINGUNA |
| 14 | `ALCOA_ACCURATE` | idem | SUFFICIENT | N/A | NINGUNA |
| 15 | `ALCOA_COMPLETE` | idem | SUFFICIENT | N/A | NINGUNA |
| 16 | `ALCOA_CONSISTENT` | idem | SUFFICIENT | N/A | NINGUNA |
| 17 | `ALCOA_ENDURING` | idem | SUFFICIENT | N/A | NINGUNA |
| 18 | `ALCOA_AVAILABLE` | idem | SUFFICIENT | N/A | NINGUNA |
| **N1** | *NR-02 (propuesto)* | — | **UNSUPPORTED** | Ningún requisito evalúa control documental del propio FS | EU-GMP-CH4 (§2.2) |
| **N2** | *NR-03 (propuesto)* | — | **UNSUPPORTED** | Ningún requisito evalúa trazabilidad URS→FS→DS a nivel documental | EU-GMP-ANNEX15 (§2.3) |
| **N3** | *NR-01 (propuesto)* | — | **UNSUPPORTED** | Ningún requisito evalúa respaldo / verificación de exactitud de E/S del equipo automatizado | FDA-CFR-210-211 (§2.1) |

### 3.2 RW-0006 — URS v2.1 (tipo URS) — 10 filas

| # | requirement_id | Fuente actual + estado | Cobertura | Brecha | Fuente adicional |
|---|---|---|---|---|---|
| 1 | `21_CFR_11.10(a)` | `ecfr_21cfr_part11` · pending_reverification | **INSUFFICIENT** | `predicate_rule_id=NOT_DETERMINED` | FDA-CFR-210-211 |
| 2 | `21_CFR_11.10(d)` | idem | **INSUFFICIENT** | idem | FDA-CFR-210-211 |
| 3 | `21_CFR_11.10(e)` | idem | **INSUFFICIENT** | idem | FDA-CFR-210-211 |
| 4 | `21_CFR_11.10(g)` | idem | **INSUFFICIENT** | idem | FDA-CFR-210-211 |
| 5 | `ANNEX11_4` | `eu_gmp_annex11` · pending_reverification | SUFFICIENT | N/A | NINGUNA |
| 6 | `ANNEX11_9` | idem | SUFFICIENT | N/A | NINGUNA |
| 7 | `ANNEX11_12` | idem | SUFFICIENT | N/A | NINGUNA |
| 8 | `ALCOA_ATTRIBUTABLE` | `mhra_gxp_di_guidance_2018` · pending_reverification | SUFFICIENT | N/A | NINGUNA |
| 9 | `ALCOA_CONTEMPORANEOUS` | idem | SUFFICIENT | N/A | NINGUNA |
| 10 | `ALCOA_ACCURATE` | idem | SUFFICIENT | N/A | NINGUNA |
| **N1** | *NR-04 (propuesto)* | — | **UNSUPPORTED** | Ningún requisito evalúa si la URS declara requisitos verificables y criterios de aceptación — el contenido nuclear de una URS | EU-GMP-ANNEX15 |
| **N2** | *NR-03 (propuesto)* | — | **UNSUPPORTED** | Trazabilidad URS→FS→DS | EU-GMP-ANNEX15 |
| **N3** | *NR-02 (propuesto)* | — | **UNSUPPORTED** | Control documental | EU-GMP-CH4 |
| **N4** | *NR-01 (propuesto)* | — | **UNSUPPORTED** | Controles de equipo automatizado | FDA-CFR-210-211 |

### 3.3 RW-0011, RW-0012, RW-0014 (tipo DS) — 4 filas × 3 documentos = 12

Las tres filas son idénticas por tipo; se anota lo específico de cada
documento en la última columna.

| # | requirement_id | Fuente actual + estado | Cobertura | Brecha | Fuente adicional |
|---|---|---|---|---|---|
| 1 | `21_CFR_11.10(e)` (cross-ref) | `ecfr_21cfr_part11` · pending_reverification | **INSUFFICIENT** | `predicate_rule_id=NOT_DETERMINED` | FDA-CFR-210-211 |
| 2 | `ANNEX11_7.1` | `eu_gmp_annex11` · pending_reverification | SUFFICIENT | N/A — **única fila con evidencia primaria esperada en todo el tipo DS** | NINGUNA |
| 3 | `ANNEX11_17` (cross-ref) | idem | SUFFICIENT | N/A | NINGUNA |
| 4 | `ALCOA_ORIGINAL` (cross-ref) | `mhra_gxp_di_guidance_2018` · pending_reverification | SUFFICIENT | N/A | NINGUNA |
| **N1** | *NR-03 (propuesto)* | — | **UNSUPPORTED** | El DS no se evalúa contra ninguna exigencia de adecuación de diseño ni trazabilidad. Con 3 de 4 filas en cross-referencia, el análisis de un DS se apoya hoy en **un solo requisito** | EU-GMP-ANNEX15 |
| **N2** | *NR-02 (propuesto)* | — | **UNSUPPORTED** | Control documental. **RW-0012 tiene `version: NO_DISPONIBLE`** y hoy nada lo señala | EU-GMP-CH4 |
| **N3** | *NR-01 (propuesto)* | — | **UNSUPPORTED** | Controles de equipo automatizado (los DS describen bloques de control EMS/WFI/PCS) | FDA-CFR-210-211 |

*Aplica por igual a RW-0011 (EMS Control Block Narrative revB), RW-0012 (PCS
Signal Interface Control Block Narrative), RW-0014 (WFI Control Block
Narrative revB).*

### 3.4 Documentos sin requisitos aplicables — NOT_APPLICABLE

| file_id | doc_type | Cobertura | Brecha | Fuente adicional |
|---|---|---|---|---|
| RW-0001 | DRAWING | NOT_APPLICABLE | Tipo fuera de `document_types`; además OCR_REQUIRED | NINGUNA — requiere AGT-APP + OCR |
| RW-0002 | OTHER | NOT_APPLICABLE | Tipo fuera de `document_types` | NINGUNA — requiere AGT-APP |
| RW-0003 | REPORT | NOT_APPLICABLE | Tipo fuera de `document_types`; OCR_REQUIRED (136,8 MB escaneado) | NINGUNA — requiere AGT-APP + OCR |
| RW-0007 | OTHER | NOT_APPLICABLE | Contenido real = transmittal | NINGUNA — requiere AGT-APP |
| RW-0008 | OTHER | NOT_APPLICABLE | `HUMAN_REVIEW_REQUIRED`; **D3 aprobada pero no aplicada** | NINGUNA — requiere aplicar D3 + AGT-APP |
| RW-0009 | REPORT | NOT_APPLICABLE | Tipo fuera de `document_types` | NINGUNA — requiere AGT-APP |
| RW-0010 | DRAWING | NOT_APPLICABLE | Tipo fuera de `document_types` | NINGUNA — requiere AGT-APP |
| RW-0013 | OTHER | NOT_APPLICABLE | `.xlsx` de alarmas/IO; tipo fuera de `document_types` | NINGUNA — requiere AGT-APP |
| RW-0004 | FS | EXCLUIDO | `DUPLICATE` (SHA-256 idéntico a RW-0005) | N/A |

**Advertencia explícita:** ninguna de las 8 fuentes candidatas desbloquea
estos 8 documentos. Su bloqueo es de **aplicabilidad y de extracción**, no de
fuente regulatoria. Añadir fuentes no sustituye a AGT-APP ni al OCR.

### 3.5 Resumen de la matriz

| Verdicto | Filas | Fuente que la cierra |
|---|---|---|
| SUFFICIENT | 26 | — |
| INSUFFICIENT | 14 | FDA-CFR-210-211 (las 14) |
| UNSUPPORTED (nuevos) | 13 | EU-GMP-ANNEX15 (6), EU-GMP-CH4 (5), FDA-CFR-210-211 (5)* |
| NOT_APPLICABLE | 8 documentos | — |

\* Las 13 filas UNSUPPORTED se reparten por documento (FS 3, URS 4, DS 3×2 en
la tabla condensada = 6 filas efectivas ×3 documentos). Cada una traza a la
ficha de §2 que la cierra. **No queda ninguna brecha sin fuente candidata
identificada** — nada que escalar a Cesar por ausencia de fuente.

---

## 4. Conjunto mínimo de fuentes adicionales

```
MINIMUM_ADDITIONAL_SOURCE_SET_FOR_W5 = { FDA-CFR-210-211,
                                         EU-GMP-CH4,
                                         EU-GMP-ANNEX15 }
```

Las tres son oficiales, públicas y gratuitas, obtenibles por la misma vía ya
usada para las 3 fuentes actuales. Ninguna tiene restricción de licencia.

| Clasificación | Fuentes |
|---|---|
| `REQUIRED_FOR_W5` | FDA-CFR-210-211, EU-GMP-CH4, EU-GMP-ANNEX15 |
| `SUPPORTING_BUT_NOT_REQUIRED` | FDA-DI-2018, ICH-Q9-R1 |
| `CONDITIONAL` | GAMP-5-ED2 |
| `DEFER_TO_W6` | ICH-Q10, FDA-PV-2011 |

**Respuesta directa a las dos preguntas de fondo:**

- ¿Las 3 fuentes actuales bastan para los 19 requisitos? **Parcialmente.**
  Bastan para 14 (Annex 11 y ALCOA+). **No bastan para los 5 de Part 11**,
  cuya aplicabilidad depende de una regla predicado que ninguna fuente
  registrada puede determinar.
- ¿Bastan para el alcance Rockwell completo? **No.** El corpus está compuesto
  por documentos del V-model (URS/FS/DS) y el catálogo solo cubre integridad
  de datos y controles de registro electrónico. No cubre adecuación de diseño,
  trazabilidad entre especificaciones ni control documental.

---

## 5. Impacto consolidado

### 5.1 Nuevos requisitos propuestos

| id prov. | Título | Fuente | Tipos | Criterios est. |
|---|---|---|---|---|
| NR-01 | Controles de equipos automatizados (respaldo, verificación de exactitud de E/S, control de cambios de software) | FDA-CFR-210-211 | FS, DS, URS | 4 |
| NR-02 | Control documental: identificación, versión, aprobación y revisión | EU-GMP-CH4 | URS, FS, DS | 5 |
| NR-03 | Trazabilidad documental URS → FS → DS → pruebas | EU-GMP-ANNEX15 | URS, FS, DS | 4 |
| NR-04 | Contenido mínimo de la URS: requisitos verificables y criterios de aceptación | EU-GMP-ANNEX15 | URS | 4 |

Catálogo resultante: **19 → 23 requisitos**.

### 5.2 Evidence Packs

- **A re-versionar: 5** — `21_CFR_11.10(a)`, `(d)`, `(e)`, `(g)`,
  `21_CFR_11.50_11.70`. Motivo: `predicate_rule_id`, `part11_scope_status` y
  `system_environment` pasan de `NOT_DETERMINED` a determinados, lo que cambia
  el contenido interpretativo del pack.
- **Nuevos: 4** — uno por NR-01…NR-04, todos naciendo con
  `evidence_pack_status = structure_only_pending_human_interpretation` y
  `CLAUSE_MAPPING = PENDING_CANONICAL_COPY`.
- Los 5 de Annex 11 y los 9 de ALCOA+ **no requieren re-versión** con el
  conjunto mínimo (solo la requerirían si Cesar adopta FDA-DI-2018 o
  ICH-Q9-R1, ambas SUPPORTING).

### 5.3 Golden Dataset

Actual: **14 casos** (`factory/regulatory/golden_dataset/semantic_verification_golden_dataset.py`).

| Adición | Casos |
|---|---|
| NR-01: positivo + negativo + regla predicado no determinada rechazada | 3 |
| NR-02: positivo + negativo (documento sin versión declarada) | 2 |
| NR-03: positivo + negativo (trazabilidad rota) | 2 |
| NR-04: positivo + negativo (URS sin criterios de aceptación) | 2 |
| Anti-fabricación: cita atribuida a Part 211 inexistente | 1 |
| **Total** | **+10 → 24 casos** |

Estos casos deben existir **antes** de la corrida, no después: son la única
defensa contra que un requisito nuevo con pack recién escrito produzca
`DOCUMENTATION_GAP` falsos en masa.

### 5.4 Recálculo del plan de corridas — el cálculo, no solo el número

**Método (idéntico al del plan vigente, §2 de `W5V2_PLAN_CORRIDAS_CORPUS.md`):**

```
llamadas_documento = chunks_tras_filtrado × nº de agentes cuyos checkpoints aplican
tiempo_llamada     = 5,8 min por cada 1 000 tokens de num_predict
num_predict        = output_token_budget() derivado del contrato del prompt
```

**Chunks por documento (del plan, sin recalcular):** RW-0005 = 27 · RW-0006 = 9
· RW-0014 = 8 · RW-0011 = 7 · RW-0012 = 7. **Total 58 chunks.**

**Agentes nuevos.** Cada fuente nueva implica un agente nuevo (un agente por
fuente, patrón vigente: `fda_part11`, `eu_annex11`, `alcoa_plus`):

| Agente nuevo | Fuente | Requisitos | Aplica a |
|---|---|---|---|
| `fda_cgmp_211` | FDA-CFR-210-211 | NR-01 | FS, URS, DS |
| `eu_gmp_ch4` | EU-GMP-CH4 | NR-02 | FS, URS, DS |
| `eu_annex15` | EU-GMP-ANNEX15 | NR-03 (+ NR-04 solo en URS) | FS, URS, DS |

Los tres aplican a los tres tipos analizables ⇒ **+3 agentes sobre los 58
chunks**.

```
LLAMADAS NUEVAS = 58 chunks × 3 agentes = 174
REVISED_CALL_COUNT = 147 + 174 = 321
```

**Presupuesto de salida por agente nuevo** (mismo criterio del motor: el
presupuesto escala con el número de criterios del contrato):

| Agente | Documento | Requisitos activos | Criterios | `num_predict` | min/llamada |
|---|---|---|---|---|---|
| `fda_cgmp_211` | todos | 1 | 4 | 512 | 2,97 |
| `eu_gmp_ch4` | todos | 1 | 5 | 512 | 2,97 |
| `eu_annex15` | FS, DS | 1 (NR-03) | 4 | 512 | 2,97 |
| `eu_annex15` | URS | 2 (NR-03+NR-04) | 8 | 1024 | 5,94 |

**Tiempo adicional:**

| Documento | Cálculo | min | h |
|---|---|---|---|
| RW-0005 (FS, 27) | 27 × 2,97 × 3 agentes | 240,6 | 4,01 |
| RW-0006 (URS, 9) | 9×2,97 + 9×2,97 + 9×5,94 | 106,9 | 1,78 |
| RW-0014 (DS, 8) | 8 × 2,97 × 3 | 71,3 | 1,19 |
| RW-0011 (DS, 7) | 7 × 2,97 × 3 | 62,4 | 1,04 |
| RW-0012 (DS, 7) | 7 × 2,97 × 3 | 62,4 | 1,04 |
| **Total** | | **543,6** | **9,06** |

```
REVISED_RUNTIME_ESTIMATE = 34,3 h + 9,1 h = 43,4 h   (+26 %)
```

**Verificación del método contra el plan vigente:** RW-0005 / `fda_part11`,
`num_predict=3584` ⇒ 27 × 5,8 × 3,584 = 561 min = 9,36 h. El plan declara
9,4 h. El método reproduce sus cifras.

**Salvedades honestas del recálculo:**

1. Los `num_predict` de los agentes nuevos se derivan de un número **estimado**
   de criterios (4–5 por requisito, el rango observado en los packs actuales:
   2–9). Cuando Cesar apruebe la redacción real de los packs, el presupuesto
   —y por tanto el tiempo— cambiará proporcionalmente.
2. No se re-chunkea: se reutilizan los conteos de chunks del plan. Añadir
   requisitos **no** cambia el chunking, que depende del documento.
3. `+26 %` es el techo si se adopta el conjunto mínimo completo. Adoptar solo
   FDA-CFR-210-211 costaría +58 llamadas / +2,9 h (`REVISED_CALL_COUNT` 205,
   ~37,2 h).

### 5.5 Invalidación de fingerprint

Incorporar fuentes o packs **cambia `requirements.yaml` ⇒ cambia
`catalog_sha256` ⇒ cambia `run_fingerprint`**. Consecuencias, ya establecidas
en §4 del plan de corridas y que aquí se confirman:

- todos los checkpoints existentes quedan invalidados; ninguna corrida previa
  es reanudable;
- la corrida de Annex 11 ya cerrada (27/27, FS_v1.2, 2026-07-28) queda como
  **diagnóstico**, no como evidencia formal contra el catálogo nuevo;
- cualquier caché de inferencia queda inservible.

```
FINGERPRINT_INVALIDATION_ON_ADOPTION = true
```

**Lectura estratégica:** como §3 de `W5V2_PAUSE_STATE.md` demuestra que **nada
se ejecutó** tras D1–D5, este es el momento de coste mínimo para adoptar
fuentes. Adoptarlas después de las 34,3 h costaría repetirlas.

---

## 6. Bloque de estado

```
D1_D5_EFFECTS_PAUSED = true
PARTIAL_EXECUTION_BEFORE_PAUSE_DOCUMENTED = false
    (no hubo ejecución parcial; verificado en W5V2_PAUSE_STATE.md §3)
ACTUAL_CURRENT_SOURCE_COUNT = 3 normativas (registry.json v1.1)
    + 9 entradas de fuentes de casos (source_registry.yaml v3, 3 connected)
    = 12 entradas registradas en total  [DISCREPANCIA REPORTADA, §1.3]
CURRENT_THREE_SOURCES_SUFFICIENT_FOR_19_REQUIREMENTS = false
    (suficientes para 14/19; insuficientes para los 5 de Part 11 por
     predicate_rule_id = NOT_DETERMINED)   [CONFIDENCE: SCOPE_LEVEL_PRELIMINARY]
CURRENT_THREE_SOURCES_SUFFICIENT_FOR_FULL_ROCKWELL_SCOPE = false
    [CONFIDENCE: SCOPE_LEVEL_PRELIMINARY]
MINIMUM_ADDITIONAL_SOURCE_SET_FOR_W5 = [FDA-CFR-210-211, EU-GMP-CH4,
                                        EU-GMP-ANNEX15]
SOURCES_SUPPORTING_NOT_REQUIRED = [FDA-DI-2018, ICH-Q9-R1]
SOURCES_CONDITIONAL = [GAMP-5-ED2]
SOURCES_DEFERRED_TO_W6 = [ICH-Q10, FDA-PV-2011]
GAMP5_AUTHORIZED_COPY_EXISTS = false   (verificado por búsqueda en el árbol)
NEW_REQUIREMENTS_REQUIRED = [NR-01, NR-02, NR-03, NR-04]
EVIDENCE_PACKS_TO_VERSION = 5  [21_CFR_11.10(a), (d), (e), (g),
                                21_CFR_11.50_11.70]
NEW_EVIDENCE_PACKS_REQUIRED = 4  [NR-01, NR-02, NR-03, NR-04]
D1_CORRECTIVE_ADDENDUM_REQUIRED = true
D2_CORRECTIVE_ADDENDUM_REQUIRED = true
GOLDEN_DATASET_ADDITIONS_REQUIRED = true  (+10 casos: 14 -> 24)
FINGERPRINT_INVALIDATION_ON_ADOPTION = true
REVISED_CALL_COUNT = 321        (vs. 147)
REVISED_RUNTIME_ESTIMATE = 43,4 h   (vs. ~34,3 h)
ASSESSMENT_CONFIDENCE = SCOPE_LEVEL_PRELIMINARY
CLAUSE_LEVEL_MAPPING = PENDING_CANONICAL_COPIES
REGULATORY_COMPLIANCE = NOT_DETERMINED
PRODUCTION_ENABLEMENT = BLOCKED
```

---

## 7. Lo que este assessment NO dice

- No dice que las 3 fuentes actuales estén mal elegidas. Están bien elegidas y
  bien gobernadas; son **incompletas** para el corpus real.
- No dice que ninguna fuente candidata sea obligatoria por su importancia
  regulatoria. Las tres `REQUIRED` lo son por una brecha
  documento × requisito localizable en un artefacto de este repositorio.
- No dice nada a nivel de numeral. Ningún numeral citado aquí está verificado
  contra copia canónica; todos son punteros de localización esperada.
- No declara conformidad. `REGULATORY_COMPLIANCE = NOT_DETERMINED`,
  `PRODUCTION_ENABLEMENT = BLOCKED`.
- No aprueba nada. La adopción del conjunto mínimo, de los adendos D1-A/D2-A y
  la reanudación de D1–D5 son decisiones de Capa 9.
