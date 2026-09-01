# F1 — VEREDICTO: reconciliación de `document_structure_extractor.py`

**Plan de reconciliación v1.1 · FASE 1 · discrepancia D2 · PRECONDICIÓN: F0 PASS ✅**

## 1. El cambio

```diff
-_HEADING_RE  = re.compile(r"^(\d{1,2})\s+([A-Za-z]...{1,90})$")
+_HEADING_RE  = re.compile(r"^(\d{1,2})\.?\s+([A-Za-z]...{1,90})$")
-_TOC_ENTRY_RE = re.compile(r"^(\d{1,2})\s+([A-Za-z]...{1,90}?)\s*\.{3,}\s*[\d ]+$")
+_TOC_ENTRY_RE = re.compile(r"^(\d{1,2})\.?\s+([A-Za-z]...{1,90}?)\s*\.{3,}\s*[\d ]+$")
```
Un único punto opcional (`\.?`) entre el número de sección y el título. Nada más.
HEAD `285300c943b3` → WT `56236c1ace28`.

## 2. Ground truth (congelado ANTES de medir)

`F1_ground_truth_headings.md` / `.json` · `GROUND_TRUTH_SHA256 = 2f7a00dc9aad66bca7ee7195f9a19518fa0228bb0e5430a43fef772ab0b28f39`.
Derivado mecánicamente del cuerpo + TOC de los 3 PDF reales (`F1_measure.py::build_ground_truth`).
Los 3 DS (plantilla MAVERICK "Control Block Narrative") numeran **`N. TÍTULO`** (con punto), en
TOC y cuerpo. 8 encabezados de nivel 1 cada uno. Ningún encabezado del cuerpo fuera del TOC.

## 3. Medición HEAD-limpio vs WT — contra el ground truth

`F1_measure.py` monkeypatchea ambas versiones de las 2 regex y corre `extract_structure` sobre el
mismo `per_page_text` de cada PDF. `F1_extractor_before_after.json`.

| Documento | GT (nº sec.) | HEAD-limpio | WT con-cambio | Δ (WT−HEAD) | veredicto |
|---|---:|---|---|---:|---|
| RW-0011 `MCCPDC EMS Control Block Narrative revB.pdf` | 8 | `toc_anchored=False`, **0 sec.** | `toc_anchored=True`, **8 sec.** (= GT exacto) | **+8** | **CORRECCIÓN** |
| RW-0012 `MCCPDC PCS Signal Interface Control Block Narrative.pdf` | 8 | `toc_anchored=False`, **0 sec.** | `toc_anchored=True`, **8 sec.** (= GT exacto) | **+8** | **CORRECCIÓN** |
| RW-0014 `MCCPDC WFI Control Block Narrative revB.pdf` | 8 | `toc_anchored=False`, **0 sec.** | `toc_anchored=True`, **8 sec.** (= GT exacto) | **+8** | **CORRECCIÓN** |

**HEAD-limpio pierde TODA la estructura de los 3 DS** (0 secciones, `toc_anchored=False`):
la regex de HEAD exige `dígito(s) + espacio` sin punto, así que `"1. OBJECTIVE"` no matchea ni en
el TOC (no se ancla) ni en el cuerpo (no se detecta) → 0.

**WT reproduce el ground truth exacto** (números `1..8`, títulos idénticos) en los 3.

## 4. Guarda contra sobre-segmentación (verificada)

`test_heading_with_period_does_not_match_subsection_numbers`: `"4.1 Process Description..."`
sigue siendo párrafo, NO una repetición de la sección 4. El `\.?` es un único punto opcional
seguido OBLIGATORIAMENTE de espacio; en `"4.1"` el carácter tras el punto es un dígito → no
matchea. El fix **no amplía** el match a subsecciones.

## 5. Impacto aguas abajo (contexto, no acción de F1)

`factory/regulatory/canonical/extract_document.py:212` llama `dse.extract_structure(per_page)` y
`normalize_claims.extract_claims_for_section` adjunta los claims a `section_id`. Con el extractor
de HEAD, re-extraer los 3 DS produciría **0 secciones** → claims sin adjuntar a sección → el
join sección↔claims que consume el analizador queda roto para RW-0011/0012/0014.

**Hallazgo para F2 (no se toca aquí):** el `canonical_store/RW-0012.sqlite3` en disco tiene
**13 secciones = 8 (contenido WFI, de RW-0014) + 5 (contenido PCS Signal Interface, real de
RW-0012)**. Es un store CONTAMINADO / doblemente materializado. El CÓDIGO del extractor (WT) es
correcto — produce las 8 reales de RW-0012 ("PCS SIGNAL INTERFACE CONTROL DESCRIPTION"). F2
(rematerialización limpia de stores) debe reconciliar el store.

## 6. Tests

`factory/tests/test_document_structure_extractor.py` → **11 passed, 1 skipped** (el skip es el
test pre-existente de RW-0005 con ruta absoluta `/home/ing_cpmo/...`, no atribuible a este fix).
- `test_heading_with_period_after_number_is_recognized` (nuevo, WT) — forma `N. TÍTULO`.
- `test_heading_with_period_does_not_match_subsection_numbers` (nuevo, WT) — guarda subsección.
- `test_maverick_control_block_narratives_reproduce_8_level1_sections` (nuevo, F1 regression
  guard) — corre `extract_structure_from_pdf` sobre los 3 PDF reales y valida 8 secciones =
  ground truth congelado. PASÓ (encontró los PDF en `GMPAI/source/Rockwell/`).

## 7. VEREDICTO

**CORRECCIÓN en los 3 documentos.** El cambio acerca la extracción al ground truth humano
(0 → 8, coincidencia exacta) sin sobre-segmentar. Reproducible desde git (`F1_measure.py`
monkeypatchea ambas versiones). Tests verdes.

→ **Commitear SOLO** `document_structure_extractor.py` + `test_document_structure_extractor.py`
+ los docs `F1_*`. NO se toca el store (F2). NO `ARCHITECTURAL_ASSUMPTION_FAIL` (sólo se
dispararía si AMBOS extractores fallaran contra el documento real — HEAD falla, WT acierta).

---

## 8. REPORTE FORMATO OBLIGATORIO — F1

```
FASE            = F1 (reconciliación document_structure_extractor.py)
PRE_COMMIT      = 3749569  (HEAD tras reconc-F0)
POST_COMMIT     = <commit reconc-F1>
WORKTREE_PRE    = 15 M / 73 ??  (extractor + su test ya modificados desde antes de la mesa)
WORKTREE_POST   = extractor + test commiteados (salen de "M"); docs_plan/reconc/F1_* añadidos;
                  resto del working tree intacto (14 M / 73 ??)
DIFF            = document_structure_extractor.py (4 líneas: 2 regex) ;
                  test_document_structure_extractor.py (+3 tests: 2 unit + 1 regression guard) ;
                  docs_plan/reconc/F1_*  (docs + F1_measure.py)
COMMANDS        = PYTHONPATH=. .venv/bin/python docs_plan/reconc/F1_measure.py ;
                  PYTHONPATH=. .venv/bin/python -m pytest -q factory/tests/test_document_structure_extractor.py
TEST_RESULTS    = 11 passed, 1 skipped, 3.31s  (número REAL)
INPUT_HASHES    = PDFs: RW-0011 13bc6f50…, RW-0012 de7b70c2…, RW-0014 8a67414d… (byte, de F0/F1_measure)
                  GROUND_TRUTH_SHA256 = 2f7a00dc9aad66bca7ee7195f9a19518fa0228bb0e5430a43fef772ab0b28f39
OUTPUT_HASHES   = extractor WT sha256 (post-commit, se registra abajo) ; F1_extractor_before_after.json
FINGERPRINTS    = n/a en F1 (F5)
ARTIFACTS       = docs_plan/reconc/{F1_measure.py, F1_ground_truth_headings.{md,json},
                  F1_extractor_before_after.json, F1_verdict.md}
GOVERNANCE_EVENTS = ninguno
DEVIATIONS      = ninguna. El "ground truth humano" se derivó mecánicamente del documento real
                  (reproducible); la revisión humana propiamente dicha queda para el gate F1.
EXPECTED_VS_ACTUAL:
  EXPECTED: HEAD-limpio pierde secciones, WT las recupera contra ground truth, reproducible.
  ACTUAL:   HEAD-limpio = 0/8 en los 3 DS ; WT = 8/8 exacto en los 3 ; reproducible por
            F1_measure.py ; guarda de subsección verificada ; 11 passed / 1 skipped.
PROPOSED_VERDICT = PASS  (veredicto CORRECCIÓN respaldado por ground truth + reproducible + tests verdes)
```

Devin (F1): desde clon limpio `reconc-F1` corre `F1_measure.py` y reproduce
0-secciones-HEAD / 8-secciones-WT y el `GROUND_TRUTH_SHA256`; el resultado NO depende del
worktree sucio.
