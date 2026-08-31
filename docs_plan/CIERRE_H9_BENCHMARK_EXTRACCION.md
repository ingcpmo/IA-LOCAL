# CIERRE H-9 — BENCHMARK DE EXTRACCIÓN (RW-0003, el SAT real image-only)

**Fecha:** 2026-08-30 · **Autoridad:** Capa 9 = Cesar · **Tipo:** benchmark. **No cambia el
extractor de producción.** **Gate previo:** D-3 (`docs_plan/D3_DOWNLOAD_MANIFEST_20260830.md`).
**Preparación:** `docs_plan/H9_PREPARACION_BENCHMARK_EXTRACCION.md` (métricas firmadas ANTES).
**JSON crudo:** `docs_plan/H9_BENCH_RESULTS.json`.

---

## 0 · Ejecución

- **Documento:** RW-0003 = `215115305 SCADA-PCS Misc PLC SAT3 Scanned-1.pdf` · 204 páginas ·
  sha `e96f67f7…` · **100 % imagen**.
- **Muestra:** primeras **50 páginas** (bounded; el SAT completo son 204 — ver §4 nota).
- **Cada backend corrió 2×** (determinismo, texto sha256 byte a byte).
- **Todo bajo `local_only.network_locked()`** · `HF_HUB_OFFLINE=1` · `enable_remote_services=False`.
- **Sustitución D-3 documentada:** OCRmyPDF+**Tesseract** → **`rapidocr-onnxruntime`**
  (host sin sudo para el binario tesseract; misma categoría — OCR de motor único; Apache-2.0;
  pip-only; 3 modelos ONNX ~16 MB empaquetados; pdfium 300 dpi; NO Ghostscript).

---

## 1 · Resultados medidos (métricas fijadas antes de correr)

| Métrica | `current` (pdfplumber) | `ocr_rapidocr` | `docling` (layout+TableFormer+OCR) |
|---|---|---|---|
| `source_page_fidelity` | 50/50 ✔ | 50/50 ✔ | 50/50 ✔ |
| `usable_text_recovery` | **0 páginas · 49 chars** | **50 páginas (100 %) · 76 664 chars** | **50 páginas (100 %) · 17 293 chars** |
| `sat_oq_iq_identifier_recovery` | 0 | **3** (`SAT1/SAT2/SAT3`) | 1 (`SAT3`) |
| `insertion_false_positives` | 0 | 0 | 0 |
| `table_reconstruction` | 0 | 0 | **45 tablas** |
| `reading_order_sample` | (vacío) | texto en orden, **PERO palabras sin espacios** (`SITEACCEPTANCETEST`, `MAVERICKProject#215115305`) | **texto limpio + orden correcto + campos estructurados** (`Customer:`, `Project number: 215115305`) |
| `determinism` | PASS | **PASS** | **PASS** |
| `runtime_s` (50 pág, 1×) | 0.08 | 117.6 (~2.4 s/pág) | 256.2 (~5.1 s/pág) |
| `peak_rss_mb` | 167 | 979 | **5 321** |
| `offline_execution` | PASS | PASS | PASS |
| `document_egress_bytes` | **0** | **0** | **0** |
| `local_only` | True | True | True |

---

## 2 · Lectura de la evidencia (SIN elegir ganador — eso es D-4)

- **`current` (producción) es inútil para RW-0003** — 0 texto de un PDF 100 % imagen. Confirma
  WP-C: recuperar el cuerpo del SAT **exige OCR**.
- **`ocr_rapidocr`:** más caracteres crudos, más aciertos `SAT`, **2× más rápido**, **5× menos
  RAM**, superficie de validación mínima (1 motor ONNX, ~16 MB, Apache-2.0). **Debilidad
  medida:** segmentación de palabras rota (sin espacios) → mala para anclaje de citas /
  procesamiento downstream; **0 tablas**.
- **`docling`:** **texto limpio con espacios + orden de lectura correcto + 45 tablas
  reconstruidas + campos estructurados**. Menos caracteres (17 k) porque estructura/dedup en
  vez de volcar cada fragmento OCR. **Costes medidos:** ~2× más lento, **5.3 GB de RAM pico**,
  superficie de validación grande (~1.4 GB de assets + torch + 5 familias de modelo).
- **Ambas rutas OCR:** deterministas, offline, `document_egress_bytes = 0`. Ninguna llamó a un
  LLM externo.

**Compromiso central (para D-4):** el Analizador GMP necesita (a) **citas ancladas limpias**
(evidencia por Finding) y (b) **matriz de casos de prueba** (tablas) → esas dos son la
**fortaleza de `docling`** y la **carencia de `ocr_rapidocr`**. El sesgo de desempate declarado
(menor superficie de validación → `ocr_rapidocr`) **solo aplica ante empate**, y aquí **no hay
empate** en calidad de texto ni en tablas.

**Inclinación basada en evidencia:** `docling` para la ingesta de RW-0003 — con la reserva de
footprint (RAM/tamaño) y la pregunta abierta de si un run completo de 204 páginas cambia
`sat_oq_iq_identifier_recovery` (la regex solo casó rótulos de ronda, no IDs por caso, en la
muestra de 50).

---

## 3 · Cumplimiento de restricciones D-3

```
CLIENT_DOCUMENT_EGRESS = NO        DOCUMENT_EGRESS = 0 (medido por EgressReport, no declarado)
EXTERNAL_LLM_API       = no usado  OFFLINE_EXECUTION = PASS (los 3 backends)
LICENSES              = Apache-2.0 / MIT / BSD-3 / CDLA-Permissive-2.0   (0 AGPL)
TORCH_BUILD            = 2.13.0+cpu (CUDA no disponible)
PyMuPDF / Ghostscript-rasterizador = EXCLUIDOS
PRODUCTION_EXTRACTOR   = SIN CAMBIO (extract_document.py sigue pdfplumber)
```

---

## 4 · GATE **D-4** — decisión de Capa 9 (NO preautorizado)

```
RECOMMENDED_EXTRACTOR         = docling   (inclinación por evidencia: texto limpio + orden + 45 tablas + campos
                                           estructurados; supera a ocr_rapidocr en calidad de anclaje y en tablas)
                                ALTERNATIVA = ocr_rapidocr  (2× más rápido, 5× menos RAM, superficie mínima;
                                           pero segmentación de palabras rota y 0 tablas)
EVIDENCE                      = docs_plan/H9_BENCH_RESULTS.json (§1). Los 3 backends deterministas y offline.
PROPOSED_EXTRACTION_VERSION   = "canonical-v2-2026-08"  (salto único gobernado desde "canonical-v1-2026-08")
CANONICAL_REDERIVATION_REQUIRED = YES  (re-extraer RW-0003 con el extractor elegido; los 5 legibles NO se re-extraen
                                        salvo que se valide no-regresión — pdfplumber sigue siendo su extractor)
GRAPH_REDERIVATION_REQUIRED    = YES  (graph_store se reconstruye desde el canonical_store nuevo)
FINDINGS_IMPACT               = con RW-0003 ingerido y `tested_by` habilitado (H-10), los ~70 REQUIREMENT_NOT_TESTED
                                + 8 ORPHAN_DESIGN_ELEMENT hoy `would_degrade`/degradados en ENFORCE podrían resolverse
                                a hallazgos con evidencia real o desaparecer. FINDINGS_FINGERPRINT CAMBIARÁ -> nueva baseline.
QA40_IMPACT                   = la muestra QA40 (SHA 02b6d3d0…) se re-evalúa: los casos siguen direccionados por
                                finding_record_id; si un finding desaparece por la nueva evidencia, su caso pasa a
                                "SUPERSEDED_BY_EXTRACTION_V2" (no se re-muestrea salvo razón gobernada).
ROLLBACK                      = `extraction_version` vuelve a "canonical-v1-2026-08"; los stores v1 (canonical/graph)
                                se conservan intactos (no se sobrescriben); revertir el flag re-deriva a v1.
FOOTPRINT_NOTE (docling)      = ~5.3 GB RAM pico · ~1.4 GB de assets en disco · ~5 s/página CPU. Aceptar o no
                                es parte de D-4.
OPEN_QUESTION                = ¿run completo de 204 páginas antes de decidir? (la muestra de 50 puede infra-contar
                                identificadores SAT-xxx por caso).
```

**STOP en D-4.** No se cambia `EXTRACTION_VERSION`. No se ingiere RW-0003. No se ejecuta H-10.
Sin commit, sin push. Producción sin tocar.
