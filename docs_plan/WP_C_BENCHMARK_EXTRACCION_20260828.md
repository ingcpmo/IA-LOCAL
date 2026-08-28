# WP-C — BENCHMARK DE EXTRACCIÓN (documento problema RW-0009 + 5 controles)

**Fecha:** 2026-08-28 · **Autoridad:** Capa 9 = Cesar · **Tipo:** BENCHMARK. No cambia el extractor de producción.
**Baseline de código:** `fix/clon-local-validacion` @ `d84a7c2` (WP-B OBSERVE cerrado).
**Alcance:** comparar extractores/OCR **disponibles localmente** sobre RW-0009 (problema) usando los otros
5 documentos como control de no-regresión. **No se descargan modelos/dependencias/recursos externos.**

---

## 1. MÉTRICAS Y CRITERIO DE DECISIÓN (fijados ANTES de ejecutar — PLAN §WP-C)

| Métrica | Definición operacional |
|---|---|
| texto/cuerpo recuperado | nº de páginas con texto (> 40 chars) · total de caracteres · chars/página |
| secciones | nº de secciones nivel-1 detectadas (heurística `^\d+(\.\d+)* [A-Z]`) vs TOC impreso |
| tablas | nº de tablas reconstruidas por el extractor |
| identificadores SAT/OQ/IQ/PQ/Test | nº de ids distintos `\b(SAT|OQ|IQ|PQ)[\s-]?\d{1,4}[a-z]?\b` recuperados |
| reading order | inspección manual de una muestra (orden lógico del texto extraído) |
| provenance página/bbox | ¿el extractor da página + bounding box por token/char? |
| contenido real de pruebas | revisión humana: ¿el texto extraído contiene la matriz de casos de prueba / resultados? |
| regresión sobre los 5 legibles | ¿algún candidato pierde páginas/chars/tablas vs `pdfplumber` en RW-0005/0006/0011/0012/0014? |

**CRITERIO (PLAN):** se adopta un extractor nuevo **solo si** recupera el cuerpo de pruebas verificado a
mano **Y** no regresa la extracción de los 5 documentos que hoy funcionan.

---

## 2. EXTRACTORES / OCR DISPONIBLES LOCALMENTE (inventario, sin descargar nada)

| Herramienta | Versión | Capacidad | Estado |
|---|---|---|---|
| **pdfplumber** | 0.11.10 | texto + **tablas** + bbox por char/word | INSTALADO (extractor de producción actual) |
| pdfminer.six | 20260107 | texto con layout + bbox | INSTALADO |
| pypdf | 4.3.1 | texto (sin tablas, sin bbox) | INSTALADO |
| pypdfium2 | 5.13.0 | texto (PDFium) + render de página + detección de objetos imagen | INSTALADO |
| poppler `pdftotext` | (poppler-utils) | texto `-layout` / raw | INSTALADO (`pdftotext`, `pdfinfo`, `pdftoppm` presentes) |
| ghostscript `gs` | 10.02.1 | rasterización | INSTALADO |
| onnxruntime | 1.29.0 | runtime ONNX (backend de RapidOCR) | INSTALADO (sin modelos OCR) |
| **tesseract** | — | OCR | **NO INSTALADO** (ni binario, ni `pytesseract`, ni tessdata, ni .deb cacheado) |
| **Docling** | — | layout + tabla + OCR (VLM) | **NO INSTALADO** (ni paquete, ni `torch`/`transformers`, ni assets de modelo) |
| PyMuPDF / pymupdf4llm | — | texto/markdown + OCR (Tesseract) | **NO INSTALADO** — además AGPL (excluido de producción sin decisión) |
| easyocr / rapidocr / paddleocr | — | OCR | **NO INSTALADO** (sin modelos) |

**Conclusión de inventario:** hay **cinco extractores de capa de texto** locales para comparar. **No hay
ningún motor OCR local.** Cualquier ruta OCR/Docling exige descarga (ver §5).

---

## 3. RESULTADOS

### 3.1 RW-0009 — `215115305-T-041 SAT3 Completed.pdf` (310 387 bytes) — DOCUMENTO PROBLEMA

| Extractor | n_páginas | páginas c/texto | total chars | chars/pág | tablas | ids test | secciones |
|---|---|---|---|---|---|---|---|
| pdfplumber (baseline) | **2** | 2 | 3 812 | 1 906 | 6 | 1 (`SAT3`) | 0 |
| pdfminer.six | — | — | 4 276 | — | — | 1 | 0 |
| pypdf | **2** | 2 | 4 189 | — | — | 1 | 0 |
| pypdfium2 | **2** | 2 | 3 910 | — | — | 1 | 0 |
| pdftotext -layout | — | — | 9 367 | — | — | 1 | 0 |
| pdftotext raw | — | — | 3 865 | — | — | 1 | 0 |

**Hallazgo determinante — revisión humana del texto extraído (idéntico en los 5 extractores):**
RW-0009 **es una carta de TRANSMITTAL de 2 páginas**, no el protocolo SAT. Su propio texto lo dice:

> *"Doc. Type: pdf · Qty: 1 · Drawing #/Document #: **215115305 SCADA-PCS Misc PLC SAT3 Scanned.pdf** ·
> Revision A · Description: **SCADA PCS-CP01 Misc PLC Site Acceptance Test 3 completed document (with all
> signatures) scanned.**"*

- Los **4 contadores de páginas coinciden: el PDF tiene 2 páginas.** No hay páginas ocultas, no hay
  páginas-imagen sin extraer: las 2 páginas rinden ~1 900 chars/página (densidad normal).
- El **cuerpo de pruebas NO está en este archivo** — está en un archivo separado: `SAT3 Scanned.pdf`.
- Ese archivo es **RW-0003** (`215115305 SCADA-PCS Misc PLC SAT3 Scanned-1.pdf`, **136 MB**), verificado:
  **204 páginas, 0 caracteres de texto, todas páginas-imagen → 100% escaneado.** RW-0003 **no está** en
  el conjunto de 6 documentos del análisis.
- `ids test` = 1 en todos los extractores = únicamente `SAT3` (del nombre/título). **Cero casos de
  prueba** (`SAT-001`…).

**Ningún extractor de capa de texto recupera "más" de RW-0009 porque no hay más que recuperar.**
OCR tampoco ayudaría a RW-0009: no tiene páginas-imagen. El defecto es de **procedencia del corpus**
(se ingirió el transmittal en lugar del cuerpo), no de extracción.

### 3.2 Controles — RW-0005 / RW-0006 / RW-0011 / RW-0012 / RW-0014 (no-regresión)

| Doc | pdfplumber (baseline) | pdfminer | pypdf | pypdfium2 | pdftotext -layout | Δ vs baseline |
|---|---|---|---|---|---|---|
| RW-0005 FS | 58 p · 132 335 ch · **89 tablas** · 219 sec-hits | 138 856 ch · 54 | 136 171 ch | 136 444 ch | 166 774 ch · 219 | sin regresión; solo pdfplumber da tablas |
| RW-0006 URS | 24 p · 45 929 ch · **35 tablas** · 162 | 49 204 ch · 135 | 47 557 ch | 48 655 ch | 98 094 ch · 159 | idem |
| RW-0011 EMS | 14 p · 30 682 ch · **37 tablas** · 33 | 32 459 ch · 30 | 31 927 ch | 31 982 ch | 58 757 ch · 33 | idem |
| RW-0012 PCS | 14 p · 32 073 ch · **35 tablas** · 57 | 33 772 ch · 52 | 33 715 ch | 32 868 ch | 57 532 ch · 57 | idem |
| RW-0014 WFI | 18 p · 40 409 ch · **40 tablas** · 38 | 42 681 ch · 35 | 42 101 ch | 42 136 ch | 77 925 ch · 38 | idem |

- Todos los extractores recuperan **todas las páginas con texto** en los 5 controles (paridad de páginas y
  de orden de magnitud de caracteres).
- `pdftotext -layout` produce ~1.5–2× más caracteres = **relleno de whitespace de layout**, no más
  contenido; y **no reconstruye tablas**.
- **Solo `pdfplumber` reconstruye tablas** (89/35/37/35/40). Cambiar a cualquier alternativa local
  **perdería la extracción de tablas** → regresión sobre los 5 documentos.
- provenance página+bbox: `pdfplumber` (char/word bbox), `pdfminer` (layout bbox), `pypdfium2` (charbox)
  → sí; `pypdf` → no. El baseline la conserva.
- reading order (muestra manual): equivalente entre pdfplumber / pdfminer / pypdfium2 en los controles.

---

## 4. DECISIÓN WP-C

| Campo | Valor |
|---|---|
| BEST_CANDIDATE | **`pdfplumber` (baseline, sin cambio)** — es el único local que reconstruye tablas; ningún alternativo local recupera más contenido en RW-0009 (no hay más) ni mejora los 5 controles. |
| PRODUCTION_CHANGE_RECOMMENDED | **NO** — no hay extractor local que justifique tocar `extract_document.py`. |
| RW-0009 | El `NOT_ANALYZABLE` de WP-B es **correcto**: RW-0009 es un transmittal de 2 páginas, no un SAT analizable. WP-B ya lo declara honestamente (`analysis_coverage.json`) y marca `would_degrade` los 70 `REQUIREMENT_NOT_TESTED` + 8 `ORPHAN_DESIGN_ELEMENT` dependientes de la mitad de prueba vacía. |
| Cuerpo real del SAT | Vive en **RW-0003** (`SAT3 Scanned-1.pdf`, 204 p, 100% imagen). No está en el corpus de análisis. Recuperarlo exige **OCR** (no disponible local) **y** una decisión de corpus de Capa 9 (ingerir RW-0003). |

---

## 5. DESCARGAS REQUERIDAS (documentado; NO ejecutado)

Ninguna descarga es necesaria para la conclusión de WP-C. Solo serían necesarias **si Capa 9 decide
ingerir RW-0003** (el SAT escaneado real):

| Ruta OCR | Qué falta localmente | Tamaño aprox. | Origen |
|---|---|---|---|
| **Tesseract** | binario `tesseract-ocr` + `tesseract-ocr-eng` (o `pip install pytesseract` + binario) | ~5 MB pkg + ~15 MB `eng.traineddata` | apt / tessdata repo |
| **RapidOCR** (onnxruntime YA presente) | `pip install rapidocr-onnxruntime` + modelos ONNX det/rec | ~1 MB pkg + ~25 MB modelos | PyPI + CDN de RapidOCR |
| **Docling** | `pip install docling` (arrastra `docling-core`, `docling-ibm-models`, **`torch` CPU ~800 MB**, `transformers`, …) + assets: layout model + TableFormer (~0.5–1 GB, HuggingFace) + OCR opcional | ~1.5–2 GB total | PyPI + HuggingFace Hub |
| PyMuPDF / pymupdf4llm | `pip install pymupdf4llm` (+ Tesseract para OCR) | ~20 MB + OCR aparte | PyPI — **AGPL, excluido de producción sin decisión** |

Recomendación mínima si se aprueba: **Tesseract** (menor footprint, licencia Apache-2.0, sin `torch`),
evaluado en un WP-C-bis aislado sobre RW-0003 antes de cualquier cambio de `EXTRACTION_VERSION`.

---

## 6. IMPACTO EN WP-D

WP-D (etapa de extracción de objetos `Test` + linker requisito↔test) tiene **dos dependencias
independientes**, y WP-C aclara cuál está resuelta:

- **D-1 (estructural):** `extract_document.py` no tiene etapa de extracción de `Test`. **NO depende de
  WP-C** — es trabajo interno; puede diseñarse e implementarse validado contra un fixture sintético / un
  protocolo legible.
- **Corpus real:** para que WP-D produzca `tested_by > 0` **sobre este corpus** hace falta un SAT legible.
  RW-0009 no lo es (transmittal). El único SAT real (RW-0003) es 100% imagen → **bloqueado en**: (a)
  decisión de Capa 9 de ingerir RW-0003, (b) autorización de descarga OCR, (c) salto de
  `EXTRACTION_VERSION` con re-derivación (NG-7).

`WP_D_READY = NO` para validación sobre corpus real. WP-D puede avanzar como **diseño + implementación de
la etapa de extracción de `Test`** con gate contra fixture/otro protocolo legible, declarando
explícitamente "sin evidencia sobre el corpus RW actual" hasta que se resuelva RW-0003.

---

*BENCHMARK. Sin cambio del extractor de producción. Sin descargas. Sin commit de código de extracción.
Harness en scratchpad (`wpc_bench.py`); resultados crudos en `wpc_results.json`.*
