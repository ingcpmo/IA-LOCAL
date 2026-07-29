# W5 V2 — Adendos correctivos D1-A y D2-A · **BORRADOR**

**Fecha:** 2026-07-29 (UTC) · **Redactado por:** Capa 8 · **Estado: PROPUESTO**

> ## Estos adendos NO están aprobados y NO se han aplicado
>
> - Ninguna identidad queda registrada como aprobadora. No hay `approved_by`.
> - Ningún estado cambia: registry, catálogo, matriz, packs, allowlist y
>   decisiones quedan exactamente como estaban.
> - No se registró nada en `factory/layer9/decisions/` ni en
>   `factory/audit/factory_audit.jsonl`.
> - Son **paquetes de decisión** para Cesar (Capa 9). Su adopción, total o
>   parcial, es la siguiente decisión de Capa 9.
>
> Base: `REGULATORY_COVERAGE_ASSESSMENT_W5.md` ·
> `ASSESSMENT_CONFIDENCE = SCOPE_LEVEL_PRELIMINARY` ·
> `CLAUSE_LEVEL_MAPPING = PENDING_CANONICAL_COPIES`

Relación con las decisiones ya registradas: `D1_regulatory_sources` y
`D2_evidence_packs` fueron **aprobadas** el 2026-07-29 (00:15 UTC) y **no se
revierten**. Estos adendos **amplían** su alcance; no lo sustituyen ni lo
corrigen. Si Cesar los rechaza, D1 y D2 siguen aprobadas tal cual y sus
efectos se reanudan sobre las 3 fuentes y los 19 packs actuales.

---

# D1-A — Adendo a fuentes regulatorias

## A.0 CORRECCIÓN — el registro sin copia canónica NO es posible

> **Corrección de Capa 8 (2026-07-29), tras leer los schemas reales.** La
> redacción original de A.1 decía que las fuentes entrarían "como
> `REGULATORY_SOURCE_UNVERIFIED` hasta su verificación humana", dando a
> entender que podían registrarse **sin copia local**. **Eso es falso** y no
> lo habría sido si hubiera leído el schema antes de redactar el adendo.

`factory/regulatory/schemas/source_registry_entry_v1.json` declara como
**obligatorios**:

```
canonical_path, sha256_original, sha256_copy, hashes_match, size_bytes,
version, effective_date, supersedes, reverification_due
```

con `hashes_match` fijado a `"const": true` y `regulatory_currency_status`
restringido a un enum de **un solo valor**: `pending_reverification`. No
existe ningún estado de registro "declarado pero sin copia".

Consecuencias, encadenadas:

1. **No se puede registrar `fda_cfr_210_211` sin ingerir primero el texto
   canónico** (descarga desde eCFR → almacén inmutable
   `factory/regulatory/sources/sha256/<hash>/` → SHA-256).
2. `predicate_rule_id` no puede rellenarse sin esa copia: el schema del
   catálogo dice literalmente *"'NOT_DETERMINED' es el único valor de
   placeholder aceptado antes de una evaluación real — **nunca se infiere**"*.
3. El pack de NR-01 exige `citation_text` real y `citation_sha256`
   **recalculado y verificado por el loader**, con `match_type` `exact` o
   `normalized` para poder quedar en `review_status: covered`. Sin texto
   canónico, NR-01 solo puede nacer en `review_required`.

**Además, no existe herramienta de alta de fuentes.**
`factory/regulatory/human_source_update.py` es el único punto de escritura
gobernado sobre `registry.json`, y solo permite modificar
`official_source_url`, `sha256_original` y `official_source_description` de
una fuente **ya existente** — con `_ALLOWED_FIELDS` fail-closed y exigiendo
que la fuente esté previamente marcada por `broken_link_report`. **Dar de alta
una fuente nueva no tiene camino gobernado hoy**: es una brecha de tooling que
esta adopción destapa y que hay que resolver antes de escribir el registry a
mano.

⇒ La adopción de A.1 **no es una edición de configuración**: implica descarga
real, ingesta al almacén inmutable y una herramienta de alta que no existe.

---

## A.1 Fuentes a incorporar al registry normativo (conjunto mínimo)

Las tres requieren copia canónica ingerida (ver A.0) y quedan en
`regulatory_currency_status = pending_reverification`, único valor admitido;
la reverificación de vigencia contra la fuente en línea es un paso humano
posterior con `run_by` real, igual que en las 3 fuentes actuales.

| Campo | FDA-CFR-210-211 |
|---|---|
| `source_id` | `fda_cfr_210_211` |
| Organismo | FDA (US) |
| URL oficial primaria | `https://www.ecfr.gov/current/title-21/chapter-I/subchapter-C/part-211` (+ Part 210: `.../part-210`) |
| `normative_type` | `regulation` |
| `jurisdiction` | `US` |
| `binding_status` esperado | `binding_regulation` |
| Versión objetivo | eCFR consolidado, fecha de copia declarada (mismo caveat de "texto vivo" ya registrado para `ecfr_21cfr_part11`) |
| Cadencia de reverificación | 1 mes (heredada de D1: `reverification_cadence_months=1`) |
| Autoridad de reverificación | cesar (heredada de D1) |
| Estado inicial | `REGULATORY_SOURCE_UNVERIFIED` |
| Alcance de ingesta | **Acotado**: subpartes relevantes a sistemas computarizados y registros (localización esperada 211.68 y 211.180). No se ingiere Part 211 completo — evita requisitos sin documento que los pueda satisfacer |

| Campo | EU-GMP-CH4 |
|---|---|
| `source_id` | `eu_gmp_ch4` |
| Organismo | Comisión Europea — EudraLex Volumen 4 |
| URL oficial primaria | `https://health.ec.europa.eu/document/download/e4b6ea9e-...chapter4_en.pdf` — **URL exacta a confirmar en la verificación humana**; punto de entrada oficial: `https://health.ec.europa.eu/medicinal-products/eudralex/eudralex-volume-4_en` |
| `normative_type` | `official_guidance` |
| `jurisdiction` | `EU` |
| `binding_status` esperado | `binding_requirement` (mismo criterio ya aplicado a `eu_gmp_annex11`) |
| Versión objetivo | Revisión vigente publicada en EudraLex Vol. 4 |
| Cadencia / autoridad | 1 mes / cesar |
| Estado inicial | `REGULATORY_SOURCE_UNVERIFIED` |

| Campo | EU-GMP-ANNEX15 |
|---|---|
| `source_id` | `eu_gmp_annex15` |
| Organismo | Comisión Europea — EudraLex Volumen 4, Anexo 15 |
| URL oficial primaria | Punto de entrada oficial: `https://health.ec.europa.eu/medicinal-products/eudralex/eudralex-volume-4_en` — **URL directa del PDF a confirmar en la verificación humana** |
| `normative_type` | `official_guidance` |
| `jurisdiction` | `EU` |
| `binding_status` esperado | `binding_requirement` |
| Versión objetivo | Revisión de 2015 (vigente según conocimiento general; **a confirmar contra la fuente oficial**) |
| Cadencia / autoridad | 1 mes / cesar |
| Estado inicial | `REGULATORY_SOURCE_UNVERIFIED` |

**Advertencia sobre las URLs.** Las tres URLs se declaran a nivel de punto de
entrada oficial. **En esta corrida no se abrió ninguna URL** (prohibido), así
que no están comprobadas. Es el mismo defecto ya conocido en
`mhra_gxp_di_guidance_2018`, cuya URL registrada apunta a una página de
aterrizaje en vez de al PDF. La verificación humana debe registrar la URL
directa del documento, no la de navegación.

## A.2 Fuentes SUPPORTING — registro opcional, sin efecto en el corpus

Si Cesar quiere el anclaje interpretativo, entrarían con el mismo estado
inicial y **sin generar `requirement_id` nuevos ni llamadas adicionales**.

| `source_id` | Fuente | Organismo | Punto de entrada oficial | Aporta |
|---|---|---|---|---|
| `fda_di_2018` | Data Integrity and Compliance With Drug CGMP | FDA (US) | `https://www.fda.gov/regulatory-information/search-fda-guidance-documents` | Anclaje US para los 9 packs ALCOA+ (hoy solo UK / non-binding) |
| `ich_q9_r1` | ICH Q9(R1) Quality Risk Management | ICH | `https://www.ich.org/page/quality-guidelines` | Refuerzo interpretativo de `ANNEX11_4` |

Si se adoptan, `EVIDENCE_PACKS_TO_VERSION` sube de 5 a 15 (9 ALCOA + 1
`ANNEX11_4`). **Recomendación de Capa 8: no adoptarlas en esta iteración** —
elevan el trabajo de packs un 200 % sin desbloquear ningún documento.

## A.3 Fuentes DEFER_TO_W6 — sección separada, para registro futuro

Se dejan escritas para que W6 no las redescubra. **No se registran ahora.**

| `source_id` prov. | Fuente | Por qué se difiere |
|---|---|---|
| `ich_q10` | ICH Q10 Pharmaceutical Quality System | Sus objetos documentales (SOP, políticas, registros de PQS) no existen en la allowlist Rockwell |
| `fda_pv_2011` | FDA Process Validation: General Principles and Practices | Gobierna validación de **proceso**; el corpus es de **sistema computarizado**. La calificación de sistemas la cubre Annex 15 |

## A.4 Fuente CONDITIONAL

| `source_id` prov. | Fuente | Condición para siquiera evaluarla |
|---|---|---|
| `gamp5_ed2` | GAMP 5, 2ª edición (ISPE) | (a) Cesar acredita copia con licencia en el servidor — **hoy no existe ninguna**, verificado; **y** (b) Cesar amplía el alcance de W5 para admitir guías de industria como fuente registrada |

Si se adopta: `normative_type` propio (p. ej. `industry_guidance`), **nunca**
como sustento único de un `requirement_id`, y nunca `binding_*`. Queda
**PROHIBIDO** obtenerla por vías no autorizadas.

## A.5 Corrección arrastrada de D1 (ya conocida, sigue sin aplicar)

Independientemente de este adendo, la reanudación de D1 debe corregir la URL
de `mhra_gxp_di_guidance_2018` (página de aterrizaje → PDF) antes de la
reverificación. Está pendiente desde antes de la pausa.

---

# D2-A — Adendo a Requirement Evidence Packs

## B.1 Packs existentes a re-versionar — 5

Todos son de Part 11. Motivo común: la incorporación de `fda_cfr_210_211`
permite determinar campos que hoy están en `NOT_DETERMINED`.

| requirement_id | Campos que cambian | Motivo |
|---|---|---|
| `21_CFR_11.10(a)` | `predicate_rule_id`, `part11_scope_status`, `system_environment` | Sin regla predicado identificada no puede sustentarse la aplicabilidad de Part 11 al documento analizado |
| `21_CFR_11.10(d)` | idem | idem |
| `21_CFR_11.10(e)` | idem | idem |
| `21_CFR_11.10(g)` | idem | idem |
| `21_CFR_11.50_11.70` | idem | idem |

Los 5 renacen con `pack_version` incrementada y
`evidence_pack_status = human_drafted_provisional` hasta que Cesar firme la
interpretación. **Los 5 de Annex 11 y los 9 de ALCOA+ no se tocan** con el
conjunto mínimo.

## B.2 Packs nuevos requeridos — 4 (uno por NEW_REQUIREMENT_ID)

Los cuatro nacen con:

```
pack_lifecycle_status       = DRAFT
evidence_pack_status        = structure_only_pending_human_interpretation
source_verification_status  = PENDING_REVERIFICATION
CLAUSE_MAPPING              = PENDING_CANONICAL_COPY
ready_for_regulatory_use    = false
production_eligibility      = BLOCKED
```

### NR-01 — Controles de equipos automatizados
- Fuente: `fda_cfr_210_211` · Localización esperada: 21 CFR 211.68(b)
- `expected_doc_types`: FS, DS, URS
- Alcance esperado (a redactar tras verificar la copia): respaldo de
  registros; verificación de exactitud de entrada/salida de datos; control de
  cambios de software.
- Celdas propuestas en la matriz: FS `expected` · DS `expected` ·
  URS `cross_reference_expected`
- Marca obligatoria `# PROPUESTO` en toda fila nueva de la matriz (regla del
  propio `applicability_matrix.yaml`: cualquier fila añadida tras `MC-0001`
  vuelve a `# PROPUESTO` hasta nueva confirmación explícita).

### NR-02 — Control documental: identificación, versión, aprobación y revisión
- Fuente: `eu_gmp_ch4` · Localización esperada: Cap. 4 §§4.1–4.3, 4.9
- `expected_doc_types`: URS, FS, DS
- Celdas propuestas: URS `expected` · FS `expected` · DS `expected`
- Caso motivador real: **RW-0012 tiene `version: NO_DISPONIBLE`** en el
  allowlist y hoy ningún requisito lo señala.

### NR-03 — Trazabilidad documental URS → FS → DS → pruebas
- Fuente: `eu_gmp_annex15` · Localización esperada: §§2–3
- `expected_doc_types`: URS, FS, DS
- Celdas propuestas: URS `expected` · FS `expected` · DS `expected`
- **Tarea obligatoria de deduplicación:** `21_CFR_11.10(a)` ya incluye entre
  sus `evidence_min_criteria` la "Trazabilidad requisito↔prueba↔resultado".
  NR-03 debe acotarse a la trazabilidad **entre especificaciones
  documentales**; si tras verificar la copia canónica el solapamiento resulta
  total, NR-03 se retira y se refuerza el pack de `21_CFR_11.10(a)`. Esta
  comprobación es **bloqueante** antes de escribir el pack.

### NR-04 — Contenido mínimo de la URS
- Fuente: `eu_gmp_annex15` · Localización esperada: §2
- `expected_doc_types`: URS
- Celdas propuestas: URS `expected` · FS/DS: no aplica
- Alcance esperado: requisitos verificables, criterios de aceptación,
  identificación de requisitos críticos por riesgo.

## B.3 Impacto en la matriz de aplicabilidad

Añadir NR-01…NR-04 **modifica `applicability_matrix.yaml`**, hoy
`human_confirmed` bajo `MC-0001`. Consecuencias:

- las filas nuevas se marcan `# PROPUESTO`;
- `matrix_version` pasa de `2.0` a `2.1`;
- se requiere una **nueva confirmación explícita de Cesar** (`MC-0002` o
  equivalente) para que las filas nuevas dejen de ser propuestas.

Esto **no está incluido** en la D2 ya aprobada, que solo cubría los 19 packs
existentes.

## B.4 Impacto en el fingerprint — explícito

Cualquier adopción de A.1 o B.1/B.2 **cambia `requirements.yaml`**, por tanto:

1. cambia `catalog_sha256` ⇒ cambia `run_fingerprint`;
2. **invalida todos los checkpoints**: ninguna corrida previa es reanudable;
3. **invalida cualquier caché** de inferencia;
4. la corrida Annex 11 cerrada 27/27 sobre FS_v1.2 (2026-07-28) pasa a ser
   **diagnóstico**, no evidencia formal contra el catálogo nuevo.

Momento óptimo: **ahora**. `W5V2_PAUSE_STATE.md` §3 demuestra que ninguno de
los efectos de D1–D5 se ejecutó, de modo que la invalidación no descarta
trabajo alguno. Adoptar estas fuentes después de las 34,3 h de corpus costaría
repetirlas íntegras.

## B.5 Impacto en el Golden Dataset — **antes** de la corrida

De 14 a 24 casos (`+10`), detalle en §5.3 del assessment. Añadirlos **antes**
de ejecutar es la única defensa contra que packs recién redactados generen
`DOCUMENTATION_GAP` falsos en masa. Se incluye un caso anti-fabricación
específico: cita atribuida a un numeral de Part 211 inexistente.

## B.6 Coste consolidado si se adopta el conjunto mínimo

| Concepto | Antes | Después |
|---|---|---|
| Fuentes normativas | 3 | 6 |
| requirement_id | 19 | 23 |
| Packs a re-versionar | — | 5 |
| Packs nuevos | — | 4 |
| Casos Golden | 14 | 24 |
| Llamadas LLM | 147 | **321** |
| Tiempo estimado | ~34,3 h | **~43,4 h** (+26 %) |
| `matrix_version` | 2.0 (`MC-0001`) | 2.1 (requiere nueva confirmación) |

**Alternativa de menor alcance**, si Cesar prefiere acotar: adoptar **solo
`fda_cfr_210_211`** cierra las 14 filas `INSUFFICIENT` —la única brecha que
afecta a requisitos **ya existentes**— por +58 llamadas y +2,9 h
(`REVISED_CALL_COUNT` 205, ~37,2 h). Las filas `UNSUPPORTED` (NR-02…NR-04)
seguirían abiertas y documentadas.

---

# B.7 DECISIÓN DE CAPA 9 — 2026-07-29: alcance reducido

**Cesar decide adoptar únicamente `fda_cfr_210_211`.**

Alcance adoptado:

| Elemento | Estado |
|---|---|
| `fda_cfr_210_211` | **ADOPTADA** (sujeta a A.0: requiere ingesta) |
| `eu_gmp_ch4` / `eu_gmp_annex15` | **NO adoptadas** — quedan documentadas en A.1 para decisión futura |
| `fda_di_2018` / `ich_q9_r1` (SUPPORTING) | **NO adoptadas** |
| `gamp5_ed2` (CONDITIONAL) | **NO adoptada** |
| `ich_q10` / `fda_pv_2011` | Diferidas a W6 (A.3) |

Efecto sobre el trabajo:

| Concepto | Antes | Con alcance reducido |
|---|---|---|
| Fuentes normativas | 3 | 4 |
| requirement_id | 19 | 20 (solo NR-01) |
| Packs a re-versionar | — | 5 (los de Part 11) |
| Packs nuevos | — | 1 (NR-01) |
| Casos Golden | 14 | 17 (+3, los de NR-01 y el anti-fabricación) |
| Llamadas LLM | 147 | **205** |
| Tiempo estimado | ~34,3 h | **~37,2 h** |
| `matrix_version` | 2.0 (`MC-0001`) | 2.1 — sigue exigiendo nueva confirmación por las filas de NR-01 |

Qué cierra y qué **no**:

- **Cierra** las 14 filas `INSUFFICIENT` de la matriz de cobertura — la única
  brecha que afecta a requisitos **ya existentes** (los 5 de Part 11 con
  `predicate_rule_id = NOT_DETERMINED`).
- **NO cierra** las filas `UNSUPPORTED` de NR-02 (control documental), NR-03
  (trazabilidad) ni NR-04 (contenido de la URS). Siguen abiertas y
  documentadas. En particular, los 3 documentos DS continúan analizándose
  contra **un solo requisito con evidencia primaria esperada**
  (`ANNEX11_7.1`), tal como describe §2.3 del assessment.
- **NO desbloquea** ningún documento `NOT_APPLICABLE`: eso depende de AGT-APP
  y de OCR, no de fuentes.

NR-03 pierde su fuente al no adoptarse Annex 15, así que la comprobación de
solapamiento con `21_CFR_11.10(a)` descrita en B.2 queda **suspendida**, no
resuelta.

---

# C. Decisiones que quedan en manos de Cesar

~~1. ¿Se adopta el conjunto mínimo completo, solo `fda_cfr_210_211`, o
ninguno?~~ **RESUELTA 2026-07-29: solo `fda_cfr_210_211` (ver B.7).**
~~2. ¿Se registran las 2 fuentes SUPPORTING?~~ **RESUELTA: no.**
~~3. ¿Se amplía el alcance de W5 para admitir GAMP 5 bajo licencia?~~
**RESUELTA: no en esta iteración.**

~~4. ¿Se autoriza la ingesta real de 21 CFR 210/211 desde eCFR?~~
**RESUELTA 2026-07-29: sí, solo Part 211** — ingerida como
`ecfr_21cfr_part211` desde la API versioner con fecha fijada.
~~5. ¿Cómo se da de alta una fuente nueva?~~ **RESUELTA:**
`factory/regulatory/human_source_registration.py`.

Abiertas:

4-bis. **`ecfr_21cfr_part211` NO está cubierta por D1.** Cesar precisó el
   2026-07-29 que el `approved_source_ids: "ALL"` registrado a las 00:15 UTC
   se refería **solo a las tres fuentes que existían entonces**. La cuarta
   queda por tanto **sin cadencia de reverificación aprobada y sin autoridad
   declarante asignada**: hereda `reverification_due: null`, que es el valor
   honesto. Antes de reverificarla hace falta una decisión adicional —o una
   que supersede a D1— que la incluya explícitamente. Esta precisión se
   registra aquí, en un documento de estado; **no** se editó
   `w5_human_decisions.jsonl`, cuyo contenido permanece tal como se aprobó.
6. ¿Se reanudan D1–D5 tras la adopción, o siguen pausados?
7. ¿Quién y cuándo redacta la interpretación humana de los 6 packs
   (5 re-versionados + NR-01)? Es la única tarea del camino crítico que no
   puede ejecutar Capa 8.

**Hasta que Cesar decida:** `PRODUCTION_ENABLEMENT = BLOCKED`,
`REGULATORY_COMPLIANCE = NOT_DETERMINED`, efectos de D1–D5 **pausados**.
