# W5.3 — Subfase 5.1.1 (copia inmutable de fuentes + resolución del gap de extracción)

Fecha: 2026-07-17. Estado: **sin commit** (pendiente tu revisión). Continúa
directamente de `factory/docs/W5_3_FASE5_0_5_1_CIERRE.md` (Fase 5.0/5.1),
cuyo nombre de archivo se corrigió en esta subfase (control #9 — el nombre
anterior, `W5v3_...`, mezclaba notación de versión con el identificador de
fase; el ciclo se llama **W5.3**, no una v3 de nada).

## 1-2. Identificación y copia inmutable (sin modificar bytes)

Los 3 archivos oficiales, identificados explícitamente antes de copiar
(mismos localizados en Fase 5.1):

| source_id | Ruta original |
|---|---|
| `ecfr_21cfr_part11` | `factory/workspaces/lab_qc_project/data/regulations/official/OFFICIAL_ECFR_21CFR_part11.txt` |
| `eu_gmp_annex11` | `factory/workspaces/lab_qc_project/data/regulations/official/OFFICIAL_EU_GMP_ANNEX11.pdf` |
| `mhra_gxp_di_guidance_2018` | `factory/workspaces/lab_qc_project/data/regulations/official/OFFICIAL_MHRA_GXP_DI_GUIDANCE_2018.pdf` |

Copiados con `shutil.copy2` (preserva bytes + metadata) a
`factory/regulatory/sources/sha256/<sha256>/<nombre_original>` — el nombre
del directorio ES el hash del contenido, por lo que el almacén es
inmutable por construcción (cualquier cambio de contenido produce otra
ruta, nunca sobrescribe). Ningún workspace de otro proyecto fue tocado;
los originales quedaron con su `mtime` sin cambios (verificado:
`Jul 6 22:01`, igual que antes de esta subfase).

## 3-4. Registro + verificación de integridad (hash original == hash copia)

`factory/regulatory/sources/registry.json`:

| source_id | sha256_original | sha256_copy | ¿coinciden? | tamaño |
|---|---|---|---|---|
| `ecfr_21cfr_part11` | `e41aa1b3...2c21e` | `e41aa1b3...2c21e` | ✅ | 16,508 B |
| `eu_gmp_annex11` | `8ec11211...4aebbb` | `8ec11211...4aebbb` | ✅ | 22,461 B |
| `mhra_gxp_di_guidance_2018` | `e05dda11...f7ebd0d` | `e05dda11...f7ebd0d` | ✅ | 456,031 B |

Los 3 hashes originales, ADEMÁS, se verificaron contra el valor
independientemente conocido desde Fase 5.1 (`REGULATORY_SOURCE_CHECK.json`
para los dos primeros, `ingest_manifest.yaml` tracked para MHRA) — el
script (`copy_sources_5_1_1.py`, ejecutado, no commiteado todavía porque
vive en el patrón de scripts ad-hoc de esta sesión) estaba programado para
**abortar y no conservar la copia** si algún hash no coincidía en
cualquiera de las dos comparaciones. Ninguna discrepancia ocurrió — las 3
copias son bit-a-bit idénticas a los originales y a los valores conocidos
previamente por dos fuentes independientes.

Por cada fuente, registro completo con los 12 campos pedidos
(`source_id`, `original_path`, `canonical_path`, `official_source_url`,
`sha256_original`, `sha256_copy`, `size_bytes`, `normative_type`,
`jurisdiction`, `local_integrity_status=PASS`,
`official_origin_status=VERIFIED_AGAINST_PRIOR_KNOWN_HASH_2026-07-06_INGESTION`,
`regulatory_currency_status=pending_reverification`) — ver
`factory/regulatory/sources/registry.json` para el JSON completo.

## 5. Artefacto derivado de extracción (pdfplumber, nunca sobre la fuente)

`factory/regulatory/sources/derived/<sha256_fuente>/pdfplumber_extraction_v1.json`,
uno por fuente PDF (Part 11 ya es texto plano, no requiere extracción —
`SKIP` explícito, no un artefacto vacío fingiendo trabajo):

| Campo | `eu_gmp_annex11` | `mhra_gxp_di_guidance_2018` |
|---|---|---|
| `extractor` | pdfplumber | pdfplumber |
| `extractor_version` | 0.11.10 | 0.11.10 |
| `source_sha256` | `8ec11211...4aebbb` | `e05dda11...f7ebd0d` |
| `extraction_params` | `{layout: false, x_tolerance: 3, y_tolerance: 3}` | ídem |
| `page_count` | 5 | 21 |
| `extracted_text_sha256` | `f5d77595...` | `6dca264b...` |

`pdfplumber` se instaló vía `pip install` (contenedor + venv host, mismo
patrón que `jsonschema` en Fase 1) — no se agregó a `requirements.txt`
todavía porque esta subfase es exploratoria/inventario, no un cambio de
runtime de producción; si Fase 5.2 confirma que se necesita
permanentemente, se agrega ahí con justificación explícita.

## 6-7. Re-ejecución del localizador sobre los 19 requisitos

Mismo mecanismo de Fase 5.1 (`citation_locator.py`, reutiliza
`match_citation()` del verificador de producción — sin vara especial para
el catálogo), esta vez leyendo el **artefacto derivado de pdfplumber** en
vez de la extracción directa de `pypdf` para las 2 fuentes PDF.

### Resultado: 19/19 EXACT o NORMALIZED

| requirement_id | match_type | score | página | Fuente |
|---|---|---|---|---|
| 21_CFR_11.10(a) | exact | 1.0000 | 1 | ecfr_21cfr_part11 |
| 21_CFR_11.10(d) | exact | 1.0000 | 1 | ecfr_21cfr_part11 |
| 21_CFR_11.10(e) | exact | 1.0000 | 1 | ecfr_21cfr_part11 |
| 21_CFR_11.10(g) | exact | 1.0000 | 1 | ecfr_21cfr_part11 |
| 21_CFR_11.50_11.70 | exact | 1.0000 | 1 | ecfr_21cfr_part11 |
| **ANNEX11_4** | **exact** | **1.0000** | **2** | eu_gmp_annex11 |
| **ANNEX11_7.1** | **exact** | **1.0000** | **3** | eu_gmp_annex11 |
| ANNEX11_9 | exact | 1.0000 | 4 | eu_gmp_annex11 |
| ANNEX11_12 | exact | 1.0000 | 4 | eu_gmp_annex11 |
| **ANNEX11_17** | **exact** | **1.0000** | **5** | eu_gmp_annex11 |
| ALCOA_ATTRIBUTABLE | exact | 1.0000 | 8 | mhra_gxp_di_guidance_2018 |
| ALCOA_LEGIBLE | exact | 1.0000 | 8 | mhra_gxp_di_guidance_2018 |
| ALCOA_CONTEMPORANEOUS | normalized | 1.0000 | 5 | mhra_gxp_di_guidance_2018 |
| ALCOA_ORIGINAL | exact | 1.0000 | 8 | mhra_gxp_di_guidance_2018 |
| ALCOA_ACCURATE | exact | 1.0000 | 4 | mhra_gxp_di_guidance_2018 |
| ALCOA_COMPLETE | normalized | 1.0000 | 4 | mhra_gxp_di_guidance_2018 |
| ALCOA_CONSISTENT | exact | 1.0000 | 8 | mhra_gxp_di_guidance_2018 |
| ALCOA_ENDURING | exact | 1.0000 | 5 | mhra_gxp_di_guidance_2018 |
| ALCOA_AVAILABLE | exact | 1.0000 | 8 | mhra_gxp_di_guidance_2018 |

**19/19 `COVERED`** (antes: 16/19, con los 3 en negrita antes marcados
`NEEDS_REVISION`).

## 7 (detalle). Los 3 requisitos que estaban pendientes

Confirmación explícita de texto, página, tipo de match y score — antes
(`pypdf`, Fase 5.1) vs. ahora (`pdfplumber`, esta subfase):

**ANNEX11_4** — cita: *"The validation documentation and reports should
cover the relevant steps of the life"*
- Antes (`pypdf`): `not_found`, score 0.869, página no determinada.
- Causa raíz confirmada: `pypdf` insertaba `"reports s hould cover"` (espacio
  espurio dentro de "should") — visible en la extracción cruda inspeccionada
  manualmente en Fase 5.1.
- Ahora (`pdfplumber`): **`exact`, score 1.0000, página 2**. `pdfplumber`
  no introduce ese artefacto de espaciado en este documento.

**ANNEX11_7.1** — cita: *"Data should be secured by both physical and
electronic means against damage."*
- Antes: `fuzzy`, score 0.9737, página 3 (sobre el umbral 0.93, pero el
  catálogo exige `exact`/`normalized`, más estricto que el runtime).
- Causa raíz: `"physical a nd electronic"` (mismo patrón de espacio
  espurio, esta vez en "and").
- Ahora: **`exact`, score 1.0000, página 3**.

**ANNEX11_17** — cita: *"Data may be archived. This data should be checked
for accessibility, readability and integrity."*
- Antes: `fuzzy`, score 0.9368, página 5.
- Causa raíz: `"should be ch ecked for accessibility, read ability"` (dos
  artefactos de espaciado en la misma oración).
- Ahora: **`exact`, score 1.0000, página 5**.

**Conclusión verificada, no asumida**: el gap no era de contenido ni de
fuente — era 100% un artefacto de la librería de extracción (`pypdf`) sobre
este PDF específico. `pdfplumber` lo resuelve limpiamente para los 3 casos,
confirmado con hash de la extracción completa (`extracted_text_sha256`) y
re-ejecución completa del mismo mecanismo de verificación usado en
producción.

## 8. Lo que NO se hizo (según instrucción explícita)

- **NO se construyó `requirements.yaml` definitivo** — sigue existiendo
  solo el inventario (`inventory_draft_v1.json` de Fase 5.1 +
  `inventory_draft_v2_pdfplumber.json` de esta subfase, ambos explícitamente
  marcados `draft`).
- **NO se modificó ningún prompt YAML de producción**
  (`part11_prompts.yaml`/`annex11_prompts.yaml`/`alcoa_prompts.yaml`
  intactos).
- **NO se cableó nada en `chunked_engine.py`** más allá de lo ya hecho en
  Fase 5.0 (`run_context` obligatorio).

## Diff (archivos nuevos, nada modificado en código de producción)

```
 factory/docs/W5_3_FASE5_0_5_1_CIERRE.md                    [renombrado, antes W5v3_...]
 factory/docs/W5_3_FASE5_1_1_CIERRE.md                      [nuevo, este documento]
 factory/regulatory/sources/registry.json                   [nuevo]
 factory/regulatory/sources/sha256/e41aa1b3.../OFFICIAL_ECFR_21CFR_part11.txt        [nuevo, copia inmutable]
 factory/regulatory/sources/sha256/8ec11211.../OFFICIAL_EU_GMP_ANNEX11.pdf           [nuevo, copia inmutable]
 factory/regulatory/sources/sha256/e05dda11.../OFFICIAL_MHRA_GXP_DI_GUIDANCE_2018.pdf [nuevo, copia inmutable]
 factory/regulatory/sources/derived/8ec11211.../pdfplumber_extraction_v1.json        [nuevo]
 factory/regulatory/sources/derived/e05dda11.../pdfplumber_extraction_v1.json        [nuevo]
 factory/regulatory/requirement_catalog/inventory_draft_v2_pdfplumber.json           [nuevo]
```

Ningún archivo de código de producción (`chunked_engine.py`,
`ollama_client.py`, prompts YAML, `applicability_matrix.yaml`,
`requirement_terms.yaml`) tocado en esta subfase.

## Gate 0

- Suite completa en el contenedor: **584 passed**, 60 fallos — **idénticos
  al baseline `262917e`** por nombre y causa exacta (`diff` sin salida,
  verificado dos veces: al cierre de Fase 5.1 y de nuevo tras esta
  subfase).
- Selfcheck host: `PASS=4 FAIL=0`.
- `hash_errors=0`, fork de auditoría preexistente sin cambios.

## Checkpoint D1.1 — antes de Fase 5.2

Con el gap de extracción resuelto y las fuentes ahora versionadas de forma
inmutable, quedan 2 de las 4 preguntas originales del Checkpoint D1 ya
resueltas por esta subfase (#1 copia autorizada y ejecutada; #2
`pdfplumber` confirmado y usado). Siguen abiertas:

3. `official_origin_status`/`regulatory_currency_status` — ¿confirmas que
   quedan `pending_reverification` (terminología que adoptaste, ya
   aplicada) para Fase 5.2, o quieres una re-verificación contra la fuente
   oficial en internet antes de construir `requirements.yaml`?
4. ¿Confirmas los parámetros de persistencia de `_by_req_candidates`
   (control #7 de Fase 5.0, sin implementar) tal como quedaron definidos?

No avanzo a Fase 5.2 sin tu confirmación.
