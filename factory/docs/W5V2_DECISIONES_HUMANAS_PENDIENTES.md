# W5 V2 — Paquetes de decisión humana pendientes

**Fecha:** 2026-07-28 · **Autoridad:** `docs_plan/W5_INSTRUCCIONES_DISENO_REGULATORY_REDESIGN_V2.md`
**Naturaleza:** preparación de evidencia. **Nada aquí está aprobado, descargado ni promovido.**

```
ALCOA_FROZEN = true
FORMAL_RELEASE_GATE = BLOCKED
REGULATORY_COMPLIANCE = NOT_DETERMINED
PRODUCTION_ENABLEMENT = BLOCKED
SOURCE_VERIFICATION_STATUS = PENDING_REVERIFICATION (3/3)
```

---

## A. Fuentes regulatorias — paquete de reverificación

Comprobación en vivo del 2026-07-28 con `check_source()` (función pura: no
escribe en el log append-only ni en la cadena de auditoría).
`check_all_governed_sources()` **no** se ejecutó: exige `run_by` real y
persiste evento, lo que es identidad humana.

| Campo | `ecfr_21cfr_part11` | `eu_gmp_annex11` | `mhra_gxp_di_guidance_2018` |
|---|---|---|---|
| Organismo | eCFR / FDA (US) | Comisión Europea (EU) | MHRA (UK) |
| Tipo normativo | regulation | official_guidance | official_guidance |
| URL oficial registrada | `.../current/title-21/.../part-11` | `health.ec.europa.eu/.../annex11_01-2011_en_0.pdf` | `gov.uk/government/publications/guidance-on-gxp-data-integrity` |
| Copia local | `sources/sha256/e41aa1b3…/OFFICIAL_ECFR_21CFR_part11.txt` | `sources/sha256/8ec11211…/OFFICIAL_EU_GMP_ANNEX11.pdf` | `sources/sha256/e05dda11…/OFFICIAL_MHRA_GXP_DI_…pdf` |
| Versión | `NO_DISPONIBLE` (texto consolidado) | `revision 1` | `Revision 1` |
| effective_date | `NO_DISPONIBLE` | `2011-06-30` | `2018-03` |
| SHA-256 local | `e41aa1b3…d82c21e` | `8ec11211…7e4aebbb` | `e05dda11…cf7ebd0d` |
| Tamaño | 16 508 B | 22 461 B | 456 031 B |
| `local_integrity_status` | PASS | PASS | PASS |
| **Resultado de comparación** | **No verificable por hash, nunca** | **COINCIDE byte a byte** | **COINCIDE byte a byte** |
| ¿URL requiere corrección? | **Sí** | No | **Sí** |

**Detalle de los dos defectos de URL:**

- **`ecfr_21cfr_part11`** — la copia gobernada es un artefacto **derivado**: texto
  ensamblado con cabecera propia del proyecto (`"Fuente oficial: eCFR … vigente al
  2026-07-01"`), no una descarga oficial. La URL sirve HTML (~10 KB) contra un
  `.txt` de 16 KB: **ningún hash puede coincidir jamás**. Alternativa verificable
  comprobada en vivo: `https://www.ecfr.gov/api/versioner/v1/full/2026-07-01/title-21.xml?part=11`
  responde 200 XML (20 474 B) y contiene 11.10.
- **`mhra_gxp_di_guidance_2018`** — el PDF oficial **coincide byte a byte**, pero
  `official_source_url` apunta a la página de aterrizaje de GOV.UK (76 KB de HTML),
  no al PDF. El enlace real es
  `assets.publishing.service.gov.uk/media/5aa2b9ede5274a3e391e37f3/MHRA_GxP_data_integrity_guide_March_edited_Final.pdf`.

**Propuesta de cadencia** (a aprobar, no aplicada): regulación federal viva
(eCFR) trimestral; guías oficiales publicadas como PDF estable (Annex 11, MHRA)
anual, más verificación ad-hoc ante cualquier aviso de enmienda.
**Responsable propuesto:** Cesar (Capa 9) como autoridad declarante;
ejecución técnica por AGT-RSG en batch asíncrono, fuera de la inferencia.

**Pasos exactos de reverificación** (ninguno ejecutado):
1. Corregir las 2 URLs en `registry.json` (MHRA → PDF directo; eCFR → API con fecha fijada).
2. Ejecutar `check_all_governed_sources(run_by="<identidad real>")`, que escribe
   evento en `source_currency_log.jsonl`.
3. Registrar la declaración humana de vigencia por fuente.

**Cambios de estado que ocurrirían tras la aprobación:** `source_verification_status`
de los 19 packs pasaría de `PENDING_REVERIFICATION` a `LOCAL_CANONICAL_COPY_VERIFIED`;
gate 3 pasaría de FAIL a evaluable. **Ver §3 del informe de cierre: esto NO exige
ampliar ningún enum** — el estado destino ya existe en
`requirement_catalog_entry_v1.json`.

---

## B. Evidence Packs — matriz de los 19

Ninguno aprobado ni promovido. Los 19 están en `evidence_pack_status =
human_drafted_provisional`, `pack_lifecycle_status = DRAFT`,
`ready_for_regulatory_use = false`, `baseline_eligibility = PROVISIONAL_ONLY`.

| # | requirement_id | Fuente | Numeral | crit. mín. | crit. exclusión | weak_keywords | expected_doc_types | source_status | Decisión humana requerida |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `21_CFR_11.10(a)` | eCFR 21 CFR Part 11 | § 11.10, paragraph (a) | 5 | 4 | 4 | URS,FS,PROTOCOL,REPORT | PENDING_REVERIFICATION | Aprobar criterios |
| 2 | `21_CFR_11.10(d)` | eCFR 21 CFR Part 11 | § 11.10, paragraph (d) | 5 | 6 | 4 | URS,FS,DS,SOP | PENDING_REVERIFICATION | Aprobar criterios |
| 3 | `21_CFR_11.10(e)` | eCFR 21 CFR Part 11 | § 11.10, paragraph (e) | 9 | 6 | 4 | FS,DS,PROTOCOL,REPORT | PENDING_REVERIFICATION | Aprobar criterios |
| 4 | `21_CFR_11.10(g)` | eCFR 21 CFR Part 11 | § 11.10, paragraph (g) | 3 | 3 | 3 | FS,DS,PROTOCOL | PENDING_REVERIFICATION | Aprobar criterios |
| 5 | `21_CFR_11.50_11.70` | eCFR 21 CFR Part 11 | § 11.50, paragraph (a)(1)-(3) | 4 | 4 | 6 | FS,DS,SOP,PROTOCOL | PENDING_REVERIFICATION | Aprobar criterios |
| 6 | `ANNEX11_4` | EU GMP Annex 11 | Section 4 (Validation), paragraph 4.1 | 3 | 3 | 6 | RISK_ASSESSMENT,VALIDATION_PLAN,URS,FS,DS,SOP,PROTOCOL,REPORT | PENDING_REVERIFICATION | Aprobar criterios |
| 7 | `ANNEX11_7.1` | EU GMP Annex 11 | Section 7 (Data Storage), paragraph 7.1 | 5 | 5 | 5 | DS,SOP,RISK_ASSESSMENT,REPORT | PENDING_REVERIFICATION | Aprobar criterios |
| 8 | `ANNEX11_9` | EU GMP Annex 11 | Section 9 (Audit Trails) | 5 | 4 | 4 | RISK_ASSESSMENT,FS,DS,SOP,PROTOCOL,REPORT | PENDING_REVERIFICATION | Aprobar criterios |
| 9 | `ANNEX11_12` | EU GMP Annex 11 | Section 12 (Security), paragraph 12.1 | 3 | 3 | 4 | DS,SOP,RISK_ASSESSMENT | PENDING_REVERIFICATION | Aprobar criterios |
| 10 | `ANNEX11_17` | EU GMP Annex 11 | Section 17 (Archiving) | 4 | 3 | 5 | SOP,DS,RISK_ASSESSMENT,REPORT | PENDING_REVERIFICATION | Aprobar criterios |
| 11 | `ALCOA_ATTRIBUTABLE` | MHRA GxP DI 2018 | p.8, ALCOA definitions list | 5 | 4 | 7 | URS,FS,DS,SOP | PENDING_REVERIFICATION | Aprobar criterios |
| 12 | `ALCOA_LEGIBLE` | MHRA GxP DI 2018 | p.8, ALCOA definitions list | 3 | 3 | 3 | DS,SOP | PENDING_REVERIFICATION | Aprobar criterios |
| 13 | `ALCOA_CONTEMPORANEOUS` | MHRA GxP DI 2018 | p.5, ALCOA acronym expansion | 3 | 4 | 6 | FS,SOP,PROTOCOL | PENDING_REVERIFICATION | Aprobar criterios |
| 14 | `ALCOA_ORIGINAL` | MHRA GxP DI 2018 | p.8, ALCOA definitions list | 2 | 2 | 4 | SOP,REPORT | PENDING_REVERIFICATION | Aprobar criterios |
| 15 | `ALCOA_ACCURATE` | MHRA GxP DI 2018 | p.4, ALCOA acronym expansion | 2 | 2 | 3 | FS,DS,SOP | PENDING_REVERIFICATION | Aprobar criterios |
| 16 | `ALCOA_COMPLETE` | MHRA GxP DI 2018 | p.8, ALCOA+ definitions list | 4 | 3 | 3 | SOP,PROTOCOL,REPORT | PENDING_REVERIFICATION | Aprobar criterios |
| 17 | `ALCOA_CONSISTENT` | MHRA GxP DI 2018 | p.8, ALCOA+ definitions list | 2 | 3 | 3 | SOP,REPORT | PENDING_REVERIFICATION | Aprobar criterios |
| 18 | `ALCOA_ENDURING` | MHRA GxP DI 2018 | p.8, ALCOA+ definitions list | 2 | 2 | 3 | SOP,DS,RISK_ASSESSMENT | PENDING_REVERIFICATION | Aprobar criterios |
| 19 | `ALCOA_AVAILABLE` | MHRA GxP DI 2018 | p.8, ALCOA+ definitions list | 2 | 2 | 4 | SOP,REPORT | PENDING_REVERIFICATION | Aprobar criterios |

**Decisión humana requerida sobre los 19:** confirmar que los
`evidence_min_criteria` redactados provisionalmente son los criterios que QA
acepta como evidencia válida de cada requisito, con revisor identificado y
fecha. Esa aprobación, **más** la reverificación de la fuente (§A), es lo que
permite salir de `PROVISIONAL_ONLY`. Ninguna de las dos por separado basta.

**Observación objetiva, no bloqueante:** los 19 packs traen `exclusion_criteria`
y `weak_keywords` no vacíos y `expected_doc_types` poblado — el pack está
estructuralmente completo para el prompt (gate 4 lo verifica en cada llamada
desde el commit `41156f2`). Lo que falta no es contenido: es la firma humana.

---

## C. T-039 — DOCM vs PDF

Comparación objetiva. El DOCM se leyó como paquete OOXML (zip + XML);
**no se ejecutó ninguna macro**.

| | `215115305-T-039 … .docm` (RW-0007) | `215115305-T-039 … .pdf` (RW-0008) |
|---|---|---|
| Tamaño | 155 571 B | 291 392 B |
| SHA-256 | `12f6d2bb…8767bf45e` | `84e7b4db…f7f6db352` |
| Estado en allowlist | `ORIGINAL_SOURCE_CONFIRMED` | **`HUMAN_REVIEW_REQUIRED`** |
| Páginas | 3 (`docProps/app.xml`) | 3 |
| Autor | `Scott, Melissa` | `Scott, Melissa` |
| Última modificación por | `Scott Buol` | — |
| Creado | `2021-07-21T23:42:00Z` | `2023-03-27 17:44:42 -05:00` |
| Revisión | 20 | — |
| Productor / Creador | (plantilla Word con macros) | **`Acrobat PDFMaker 20 for Word`** / `Adobe PDF Library 20.5.233` |
| Título embebido | — | `Transmittal Form` |
| Contenido textual | 131 párrafos, 3 778 chars | 5 587 chars |
| `vbaProject.bin` | **16 384 B presente, NO ejecutado** | n/a |

**Relación probable — evidencia convergente, no suposición:**

1. El PDF declara `Creator: "Acrobat PDFMaker 20 for Word"` — fue **generado
   desde Word**, no escaneado ni creado aparte.
2. Mismo autor, mismo número de páginas (3), mismo tipo de documento
   (`Transmittal Form`).
3. La primera línea de contenido del DOCM es `Date: March 27, 2023`, **la misma
   fecha** en que se creó el PDF.

⇒ El PDF es, con alta probabilidad, la **renderización derivada** del DOCM para
ese transmittal concreto. Los 3 778 vs 5 587 chars se explican porque el DOCM es
una plantilla de formulario cuyos valores se materializan al renderizar
(cabeceras, pies, numeración de página, tablas).

**Riesgos de decidir mal:**
- Tratar el PDF como **original independiente** ⇒ se analiza dos veces el mismo
  contenido y se duplican hallazgos sobre un documento que no es fuente propia.
- Tratar el DOCM como **derivado** ⇒ se descarta el único artefacto editable,
  que es el que conserva la trazabilidad de revisión (rev. 20).
- Ejecutar la macro para "confirmar" ⇒ prohibido por §9 del plan y por política.

**Decisión humana necesaria:** clasificar RW-0008 (PDF) como
`DERIVED_DOCUMENT_EXCLUDED` con `duplicate_of: RW-0007`, o mantenerlo como
original independiente. El estado terminal actual es `HUMAN_REVIEW_REQUIRED` y
**no se ha cambiado**. Recomendación técnica, sujeta a tu decisión: `DERIVED_DOCUMENT_EXCLUDED`.

---

**Ninguna de las tres decisiones fue tomada.** No se descargó ninguna fuente, no
se marcó ninguna como verificada, no se aprobó ni promovió ningún pack, no se
alteró ningún estado del allowlist, no se ejecutó ninguna macro.
