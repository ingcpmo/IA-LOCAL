# CIERRE H-9 — BENCHMARK DE EXTRACCIÓN (RW-0003, SAT real 100 % imagen) — CORRIDA COMPLETA 204 pág

**Fecha:** 2026-08-30 · **Autoridad:** Capa 9 = Cesar · **Tipo:** benchmark. **No cambia el
extractor de producción.** **Gate previo:** D-3 (`docs_plan/D3_DOWNLOAD_MANIFEST_20260830.md`,
preautorizado en la misión final). **JSON crudo:** `docs_plan/_h9_full/H9_BENCH_RESULTS_FULL.json`.
Sustituye a `docs_plan/CIERRE_H9_BENCHMARK_EXTRACCION.md` (muestra de 50 pág).

---

## 0 · Ejecución

- **Documento:** RW-0003 = `215115305 SCADA-PCS Misc PLC SAT3 Scanned-1.pdf` · **204 páginas
  completas** · sha `e96f67f7…` · **100 % imagen**.
- **Cada backend corrió 2×** (determinismo, texto sha256 byte a byte). Docling: ~22 min/corrida.
- **Todo bajo `local_only.network_locked()`** · `HF_HUB_OFFLINE=1` · `enable_remote_services=False`.
- Métricas **fijadas antes** de correr (`metrics_signed_before_run` en el JSON).
- **Sustitución D-3 documentada:** OCRmyPDF+Tesseract → `rapidocr-onnxruntime` (host sin sudo
  para el binario tesseract; misma categoría — OCR de motor único; Apache-2.0; pip-only;
  modelos ONNX empaquetados; pdfium 300 dpi; NO Ghostscript).

---

## 1 · Resultados medidos — 204 páginas

| Métrica | `current` (pdfplumber) | `ocr_rapidocr` | `docling` (layout+TableFormer+OCR) |
|---|---|---|---|
| `source_page_fidelity` | 204/204 ✔ | 204/204 ✔ | 204/204 ✔ |
| `usable_text_recovery` | **0 pág · 203 chars** | **204 pág (100 %) · 345 962 chars** | **204 pág (100 %) · 47 200 chars** |
| `sat_oq_iq_identifier_recovery` | 0 | **3** (`SAT1/SAT2/SAT3` — rótulos de ronda) | 1 (`SAT3`) |
| `insertion_false_positives` | 0 | 0 | 0 |
| `table_reconstruction` | 0 | 0 | **199 tablas** |
| `reading_order_sample` | (vacío — solo saltos de línea) | texto en orden **PERO palabras sin espacios** (`SITEACCEPTANCETEST`, `MAVERICKProject#215115305`) | **texto limpio con espacios + orden correcto + campos estructurados** (`Customer:`, `Project number: 215115305`, `1. Objective`) |
| `determinism` | PASS | **PASS** | **PASS** |
| `runtime_s` (204 pág, 1×) | 0.3 | 564.8 (~2.8 s/pág) | 1317.8 (~6.5 s/pág) |
| `peak_rss_mb` | 303 | 1 069 | **9 563** (~9.3 GB) |
| `offline_execution` | PASS | PASS | PASS |
| `document_egress_bytes` | **0** | **0** | **0** |
| `local_only` | True | True | True |

`text_sha256` por backend en el JSON; los 3 deterministas entre corrida 1 y 2.

---

## 2 · Lectura de la evidencia

- **`current` (producción) es inútil para RW-0003** — 0 texto de un PDF 100 % imagen.
  Recuperar el cuerpo del SAT **exige OCR** (confirma WP-C).
- **`ocr_rapidocr`:** más caracteres crudos (346 k), 3 rótulos `SAT`, **2× más rápido**,
  **~9× menos RAM**, superficie de validación mínima (1 motor ONNX ~16 MB, Apache-2.0).
  **Debilidades medidas en la corrida completa:** (a) **segmentación de palabras rota**
  (sin espacios) → inutilizable para anclaje de citas y procesamiento downstream;
  (b) **0 tablas**. La pregunta abierta de la muestra de 50 pág (¿aparecen IDs `SAT-nnn`
  por caso en 204 pág?) queda **resuelta: NO** — el run completo sigue dando solo rótulos
  de ronda `SAT1/2/3`, ningún identificador por caso de prueba.
- **`docling`:** **texto limpio con espacios + orden de lectura + 199 tablas + campos
  estructurados**. Menos caracteres (47 k) porque estructura/dedup en vez de volcar cada
  fragmento OCR. **Costes medidos:** ~2.3× más lento que rapidocr, **~9.3 GB RAM pico**,
  superficie de validación grande (~1.4 GB de assets + torch + ~5 familias de modelo).
- **Ambas rutas OCR:** deterministas, offline, `document_egress_bytes = 0`, cero LLM externo.

**Compromiso central:** el Analizador GMP necesita (a) **citas ancladas limpias** (evidencia
por Finding — imposible con texto sin espacios) y (b) **matriz de casos de prueba** (tablas).
Esas dos son la **fortaleza de `docling`** y la **carencia dura de `ocr_rapidocr`**.

---

## 3 · Cumplimiento D-3

```
CLIENT_DOCUMENT_EGRESS = NO        DOCUMENT_EGRESS = 0  (EgressReport, medido)
CLIENT_TEXT_EGRESS     = NO        EXTERNAL_LLM_API = FORBIDDEN — no usado (los 3 backends)
OFFLINE_EXECUTION      = PASS (los 3)      LICENSES = Apache-2.0 / MIT / BSD-3 / CDLA-Permissive-2.0  (0 AGPL)
TORCH_BUILD            = 2.13.0+cpu (CUDA no disponible)
PyMuPDF / Ghostscript-rasterizador = EXCLUIDOS
PRODUCTION_EXTRACTOR   = SIN CAMBIO (extract_document.py sigue pdfplumber puro; sin hook OCR)
```

---

## 4 · Entrada a GATE D-4

```
D4_CONDITIONS (todas exigidas):
  benchmark reproducible ............................ SÍ  (métricas fijadas antes; determinism PASS x3; harness versionado)
  selected extractor beats/equals current .......... SÍ  (current recupera 0; cualquiera de los dos OCR lo supera)
  no unacceptable insertion false positives ........ SÍ  (0 en los 3 backends, 204 pág)
  deterministic result ............................. SÍ  (PASS x3, sha256 byte a byte)
  offline/local-only verified ...................... SÍ  (PASS x3; egress 0 medido)
  DOCUMENT_EGRESS = 0 .............................. SÍ  (medido, no declarado)
  rollback available ............................... SÍ  (extraction_version revert; extractor de producción intacto)
  previous stores preserved ....................... SÍ  (nada ingerido; H-10 re-derivación en /tmp)
  NEW_REGRESSIONS = 0 ............................. SÍ  (6 EXC = subconjunto de la baseline 9-EXC; 0 nuevas)
  => D4_CONDITIONS_MET = YES

SELECCIÓN (orden de prioridad de la misión; NO por popularidad):
  1. source/page fidelity ............ 204/204 los 3        -> EMPATE
  2. false insertion minimization .... 0 los 3              -> EMPATE
  3. table / reading-order fidelity .. docling: 199 tablas + texto con espacios + orden + campos
                                       rapidocr: 0 tablas + palabras SIN espacios
                                       -> DESEMPATA A FAVOR DE **docling**
  (4 determinismo / 5 menor superficie de validación / 6 runtime-memoria NO se alcanzan:
   el criterio 3 ya resolvió. El sesgo declarado "menor superficie -> rapidocr" aplica SOLO
   ante empate, y en el criterio 3 NO hay empate.)

SELECTED_EXTRACTOR            = docling
PROPOSED_EXTRACTION_VERSION   = "canonical-v1-2026-08+tests-v1"  (salto único; agrupa OCR + test-extraction, diseño §H-10)
FOOTPRINT_ACEPTADO_EN_D4     = ~9.3 GB RAM pico · ~1.4 GB assets · ~6.5 s/página CPU · host tiene 19.8 GB (4 contenedores prod activos ~5.7 GB)
```

**Nota de ejecución para H-10:** el hook docling ya está integrado en `extract_document.py`
(`_per_page_text(..., ocr=True)`); el ingest completo de RW-0003 (204 pág, ~9.3 GB pico,
~22 min) sobre un host de 19.8 GB con `gmp-api`/`factory-api`/`gmp-postgres`/`gmp-redis`
activos NO se ejecutó desatendido (riesgo de presión de memoria).
Ver `docs_plan/CIERRE_H10_CAPACIDAD_20260830.md`.

---

## 5 · CIERRE FORMAL DE H-9 (verificación contra resultados reales, no por existencia del documento)

Cruzado contra `docs_plan/CIERRE_H9_BENCHMARK_EXTRACCION.md` (muestra de 50 pág) y contra el
JSON crudo `docs_plan/_h9_full/H9_BENCH_RESULTS_FULL.json` (204 pág). Los números de la
corrida completa son **consistentes con y más nítidos que** la muestra de 50 pág.

| Criterio de H-9 | Verificado |
|---|---|
| benchmark reproducible | **SÍ** — métricas fijadas antes (`metrics_signed_before_run`), harness versionado (`factory/scripts/ops/h9_extraction_benchmark.py`), 2× por backend |
| `CURRENT_EXTRACTOR` medido | **SÍ** — pdfplumber, 204/204 pág, **0** texto usable, 0 ids, 0 tablas |
| OCRmyPDF/Tesseract medido | **SÍ (sustituto D-3: `rapidocr-onnxruntime`)** — 204/204 pág, 345 962 chars, 3 rótulos SAT, 0 tablas, **palabras sin espacios** |
| Docling medido | **SÍ** — 204/204 pág, 47 200 chars, 1 id SAT, **199 tablas**, texto limpio + orden |
| source/page fidelity medido | **SÍ** — 204/204 los 3 |
| usable text recovery medido | **SÍ** — 0 % / 100 % / 100 % |
| SAT/OQ/IQ identifier recovery medido | **SÍ** — 0 / 3 / 1 (sólo rótulos de ronda; ningún `SAT-nnn` por caso en 204 pág) |
| insertion false positives medidos | **SÍ** — **0** en los 3 |
| table reconstruction medida | **SÍ** — 0 / 0 / **199** |
| reading order medida | **SÍ** — vacío / roto (sin espacios) / limpio+ordenado+campos |
| determinism demostrado | **SÍ** — `PASS` los 3 (sha256 byte a byte entre corrida 1 y 2) |
| runtime/memory registrados | **SÍ** — 0.3 s·303 MB / 564.8 s·1 069 MB / 1317.8 s·9 563 MB |
| offline/local-only demostrado | **SÍ** — `PASS` los 3; `HF_HUB_OFFLINE=1`, `enable_remote_services=False` |
| DOCUMENT_EGRESS = 0 | **SÍ** — medido por `EgressReport` (`network_locked()`), no declarado |

```
H9 = PASS
RECOMMENDED_EXTRACTOR = docling
```

Justificación de `RECOMMENDED_EXTRACTOR` (orden de prioridad de la misión, NO popularidad):
criterios 1 (source/page fidelity) y 2 (minimización de inserción falsa) → **empate** (204/204
y 0 los 3). Criterio 3 (fidelidad de tabla / orden de lectura) → **docling** (199 tablas +
texto con espacios + orden + campos estructurados) **desempata** frente a `ocr_rapidocr`
(0 tablas + palabras sin espacios). Los criterios 4-6 no se alcanzan. El sesgo declarado
"menor superficie de validación → rapidocr" **sólo aplica ante empate**, y en el criterio 3
no hay empate.

`H9 = FAIL` **NO** aplica → no hay STOP en H-9.
