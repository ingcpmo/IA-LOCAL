# F1 — REPORTE FINAL CORRECTIVO (cierre con ground truth humano-aprobado)

**Plan de reconciliación v1.1 · FASE 1 · discrepancia D2.**
**Corrige el cierre procedimental:** el ground truth ahora está **declarado y aprobado por
Capa 9 ANTES de la re-medición** (corrección 10). El veredicto de fondo NO cambia.

---

## 1. Secuencia de cierre ejecutada (orden obligatorio de Capa 9)

| # | Acción | Commit / tag | Estado |
|---|---|---|---|
| — | Fix del extractor (`\.?` en 2 regex) + tests + medición mecánica | `09656e1` · tag **`reconc-F1`** (histórico, **NO se mueve**) | intacto |
| 1 | Registrar aprobación humana de Capa 9 en `F1_HUMAN_GROUND_TRUTH_REVIEW.md` (fecha/hora + hashes de los 3 PDF) | incluido en commit 1 | ✅ |
| 2 | **COMMIT de la aprobación humana, SIN medir** | **`e77dab7`** | ✅ (medición NO ejecutada antes de este commit) |
| 3 | Re-ejecutar `F1_measure.py` contra el ground truth ya congelado | — (solo genera artefactos) | ✅ |
| 4 | Verificar PRE-fix 0/8 y POST-fix 8/8 exacto, sin sobre-segmentación de nivel 1 | este reporte §3 | ✅ PASS |
| 5 | Reporte final correctivo + **segundo commit** | este archivo · **commit 2** | ✅ |
| 6 | **Tag nuevo `reconc-F1-r1`** sobre el cierre corregido (NO se toca `reconc-F1`) | **`reconc-F1-r1`** | ✅ |
| 7 | **NO ejecutar F2** — detenerse | — | ✅ STOP |

---

## 2. Aprobación humana registrada

```
GROUND_TRUTH_F1_HUMAN_APPROVED = SÍ
CORRECCIONES                   = ninguna
APROBADO_POR                   = Capa 9 (Cesar)
FECHA_HORA                     = 2026-09-01T18:48:28Z
ALCANCE                        = F1 valida ÚNICAMENTE los 8 encabezados de NIVEL 1 por documento.
                                 Subencabezados N.M / N.M.N legítimos -> EXPLÍCITAMENTE FUERA
                                 DEL ALCANCE de F1 (decisión de Capa 9).
```

PDF verificados en el momento de la aprobación (sin cambio vs F0):

| doc_id | filename | SHA256 | páginas |
|---|---|---|---:|
| RW-0011 | `MCCPDC EMS Control Block Narrative revB.pdf` | `13bc6f50c4cee50211d6877249cbacd19e797b0cb93e58e3579c037be68fbf53` | 14 |
| RW-0012 | `MCCPDC PCS Signal Interface Control Block Narrative.pdf` | `de7b70c297f0fbf1269d47e334a7575d4de3429bff6ed797fc663b85fea15c71` | 14 |
| RW-0014 | `MCCPDC WFI Control Block Narrative revB.pdf` | `8a67414d90ba28c8ee3cf9939d3be0d670ed7c8794a61f049b07ebe07ebf4ccb` | 18 |

**Ground truth humano-aprobado** (8 encabezados de nivel 1 por documento — CORRECCIONES = ninguna):

| # | RW-0011 | RW-0012 | RW-0014 |
|---|---|---|---|
| 1 | OBJECTIVE | OBJECTIVE | OBJECTIVE |
| 2 | TERMINOLOGY | TERMINOLOGY | TERMINOLOGY |
| 3 | INPUT CONSIDERATIONS | INPUT CONSIDERATIONS | INPUT CONSIDERATIONS |
| 4 | EMS CONTROL DESCRIPTION | PCS SIGNAL INTERFACE CONTROL DESCRIPTION | WFI CONTROL DESCRIPTION |
| 5 | SOFTWARE PERMISSIVES | SOFTWARE PERMISSIVES | SOFTWARE PERMISSIVES |
| 6 | INTER-NETWORK RELATIONSHIPS | INTER-NETWORK RELATIONSHIPS | INTER-NETWORK RELATIONSHIPS |
| 7 | HARDWARE INTERLOCKS | HARDWARE INTERLOCKS | HARDWARE INTERLOCKS |
| 8 | REFERENCES | REFERENCES | REFERENCES |

```
GROUND_TRUTH_SHA256 = 2f7a00dc9aad66bca7ee7195f9a19518fa0228bb0e5430a43fef772ab0b28f39
```
Idéntico al que registró `reconc-F1` — el ground truth humano coincide **exactamente** con el
derivado mecánicamente (CORRECCIONES = ninguna, confirmado por Capa 9).

---

## 3. Re-medición POST-aprobación (paso 3-4) — reproducible

`F1_measure.py` ejecutado **después** del commit `e77dab7`. Monkeypatchea las 2 regex a la
versión de HEAD (sin `\.?`) y a la del working tree (con `\.?`) y corre `extract_structure`
sobre el mismo `per_page_text` de cada PDF. Artefactos byte-idénticos a los de `reconc-F1`
(deterministas — `git status` de `docs_plan/reconc/` vacío tras re-correr).

| Documento | PRE-fix (HEAD, sin `\.?`) | POST-fix (WT, con `\.?`) | ¿POST == ground truth humano? | sobre-segmentación nivel 1 |
|---|---|---|---|---|
| RW-0011 | `toc_anchored=False` · **0 / 8** | `toc_anchored=True` · **8 / 8** · números `1..8` | **SÍ, exacto** | **NO** (exactamente 8) |
| RW-0012 | `toc_anchored=False` · **0 / 8** | `toc_anchored=True` · **8 / 8** · números `1..8` | **SÍ, exacto** | **NO** (exactamente 8) |
| RW-0014 | `toc_anchored=False` · **0 / 8** | `toc_anchored=True` · **8 / 8** · números `1..8` | **SÍ, exacto** | **NO** (exactamente 8) |

```
VERIFICACIÓN GLOBAL = PASS — PRE = 0/8 en los 3 · POST = 8/8 exacto en los 3 · sin sobre-segmentación de nivel 1
```

**Guarda de subsección (fuera de alcance F1 pero verificada):**
`test_heading_with_period_does_not_match_subsection_numbers` — `"4.1 Process Description…"` NO
se trata como repetición de la sección 4 (el `\.?` es un único punto seguido OBLIGATORIAMENTE
de espacio; en `"4.1"` el carácter tras el punto es dígito → no matchea). El fix **no** captura
los subencabezados N.M que Capa 9 declaró fuera de alcance.

---

## 4. Tests (número real)

`PYTHONPATH=. .venv/bin/python -m pytest -q factory/tests/test_document_structure_extractor.py`
→ **11 passed, 1 skipped, 3.12s**

- skip = `test_real_fs_v1_2_pdf_reproduces_toc_section_numbering` (pre-existente, ruta absoluta
  `/home/ing_cpmo/…`, no atribuible a este fix).
- `test_maverick_control_block_narratives_reproduce_8_level1_sections` (F1 regression guard)
  → PASÓ: corre `extract_structure_from_pdf` sobre los 3 PDF reales y valida 8 secciones =
  ground truth humano-aprobado.

Extractor (sin cambios desde `09656e1`):
`sha256 = 56236c1ace2800ed32c5be9712a0761a2084c969cb6527954c6f64104552a11a`

---

## 5. VEREDICTO F1 (definitivo)

**CORRECCIÓN en los 3 documentos**, ahora respaldada por **ground truth humano-aprobado por
Capa 9** (2026-09-01T18:48:28Z, CORRECCIONES = ninguna):

- HEAD-limpio pierde TODA la estructura de nivel 1 de RW-0011/0012/0014 (`0/8`, `toc_anchored=False`).
- El fix `\.?` recupera exactamente los 8 encabezados de nivel 1 humano-aprobados por documento
  (`8/8`), sin sobre-segmentar.
- Reproducible desde git (`F1_measure.py`, artefactos deterministas).
- Tests verdes (11p/1s).
- `ARCHITECTURAL_ASSUMPTION_FAIL` NO aplica (sólo si AMBOS extractores fallaran contra el
  documento real).

**PROPOSED_VERDICT F1 = PASS.**

---

## 6. Hallazgo pendiente para F2 (NO se toca en F1)

`canonical_store/RW-0012.sqlite3` en disco = **13 secciones** = 8 (contenido **WFI**, de
RW-0014) + 5 (**PCS Signal Interface**, real de RW-0012). Store **contaminado / doblemente
materializado**. El **código** del extractor es correcto (WT produce las 8 reales de RW-0012:
`PCS SIGNAL INTERFACE CONTROL DESCRIPTION`). F2 (rematerialización limpia de stores) debe
reconciliar el store.

---

## 7. REPORTE FORMATO OBLIGATORIO — F1 (cierre corregido)

```
FASE            = F1 (cierre procedimental corregido — ground truth humano-aprobado)
PRE_COMMIT      = e77dab7  (commit 1: aprobación humana registrada, SIN medir)
POST_COMMIT     = <commit 2 de este reporte>  ·  tag reconc-F1-r1
WORKTREE_PRE    = docs_plan/reconc/F1_HUMAN_GROUND_TRUTH_REVIEW.md ya commiteado en e77dab7
WORKTREE_POST   = + docs_plan/reconc/F1_FINAL_CORRECTIVE_REPORT.md ; resto del working tree intacto
DIFF            = solo docs_plan/reconc/F1_FINAL_CORRECTIVE_REPORT.md
                  (F1_measure.py re-ejecutado -> artefactos byte-idénticos -> git status limpio)
COMMANDS        = git commit (e77dab7, aprobación) ; PYTHONPATH=. .venv/bin/python docs_plan/reconc/F1_measure.py ;
                  PYTHONPATH=. .venv/bin/python -m pytest -q factory/tests/test_document_structure_extractor.py
TEST_RESULTS    = 11 passed, 1 skipped, 3.12s
INPUT_HASHES    = PDFs 13bc6f50… / de7b70c2… / 8a67414d… (byte, re-verificados)
                  GROUND_TRUTH_SHA256 = 2f7a00dc9aad66bca7ee7195f9a19518fa0228bb0e5430a43fef772ab0b28f39
OUTPUT_HASHES   = extractor 56236c1ace2800ed32c5be9712a0761a2084c969cb6527954c6f64104552a11a
                  F1_extractor_before_after.json (byte-idéntico a reconc-F1 — determinista)
FINGERPRINTS    = n/a en F1 (F5)
ARTIFACTS       = docs_plan/reconc/{F1_HUMAN_GROUND_TRUTH_REVIEW.md (aprobado), F1_FINAL_CORRECTIVE_REPORT.md,
                  F1_measure.py, F1_ground_truth_headings.{md,json}, F1_extractor_before_after.json, F1_verdict.md}
GOVERNANCE_EVENTS = ninguno
DEVIATIONS      = ninguna. Orden obligatorio de Capa 9 respetado: aprobación commiteada (e77dab7)
                  ANTES de la re-medición.
EXPECTED_VS_ACTUAL:
  EXPECTED: aprobación humana congelada antes de medir ; PRE 0/8 ; POST 8/8 exacto vs ground
            truth humano ; sin sobre-segmentación ; reproducible ; tags: reconc-F1 intacto +
            nuevo reconc-F1-r1.
  ACTUAL:   e77dab7 antes de F1_measure.py ; PRE 0/8 (x3) ; POST 8/8 exacto (x3) == ground truth
            humano (CORRECCIONES ninguna) ; sin sobre-segmentación ; artefactos deterministas ;
            11p/1s ; reconc-F1 intacto, reconc-F1-r1 creado.
PROPOSED_VERDICT = PASS
```

Devin (F1-r1): desde clon limpio `reconc-F1-r1` corre `F1_measure.py` y reproduce PRE 0/8 /
POST 8/8 y el `GROUND_TRUTH_SHA256`; verifica que `e77dab7` (aprobación) precede a la medición
en el historial; el resultado NO depende del worktree sucio.

---

## 8. Entregables

| | valor |
|---|---|
| Commit 1 (aprobación humana, sin medir) | `e77dab7` |
| Commit 2 (reporte final correctivo) | *(este commit)* |
| Tag histórico (NO movido) | `reconc-F1` → `09656e1` |
| Tag del cierre corregido | `reconc-F1-r1` → *(commit 2)* |
| PDF hashes | RW-0011 `13bc6f50c4cee502…` · RW-0012 `de7b70c297f0fbf1…` · RW-0014 `8a67414d90ba28c8…` |
| GROUND_TRUTH_SHA256 | `2f7a00dc9aad66bca7ee7195f9a19518fa0228bb0e5430a43fef772ab0b28f39` |
| Extractor sha256 | `56236c1ace2800ed32c5be9712a0761a2084c969cb6527954c6f64104552a11a` |
| Tests | 11 passed, 1 skipped |
| Veredicto F1 | **CORRECCIÓN · PROPOSED_VERDICT = PASS** |
| F2 | **NO ejecutada — STOP** |
