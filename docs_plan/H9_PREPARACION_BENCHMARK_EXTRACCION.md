# H-9 — PREPARACIÓN DEL BENCHMARK DE EXTRACCIÓN (pre-D-3, pre-D-5)

**Fecha:** 2026-08-30 · **Autoridad:** Capa 9 = Cesar · **Tipo:** preparación. **No toca producción.
No descarga nada. No cruza ningún gate.**
**Diseño:** `docs_plan/DISENO_H1_H10_ACTUALIZADO_R0_R5_20260829 (1).md` §H-9.
**Antecedente:** `docs_plan/WP_C_BENCHMARK_EXTRACCION_20260828.md` (reconocimiento: extractores de
capa de texto sobre RW-0009; RW-0003 identificado como el SAT real image-only).

Se prepara TODO lo que no requiere autorización, para que tras **D-3** (descargas) y **D-5**
(adjudicación H-8) el benchmark + las métricas sean un paso rápido. Aquí **no** se calcula
ninguna métrica de H-8 ni se ejecutan las rutas OCR/Docling.

---

## 1 · Fixture — RW-0003 (el SAT real)

| Campo | Valor |
|---|---|
| `file_id` | `RW-0003` (`factory/regulatory/scope/source_baseline_allowlist.yaml`) |
| Ruta local | `GMPAI/source/Rockwell/215115305 SCADA-PCS Misc PLC SAT3 Scanned-1.pdf` |
| Tamaño / páginas | 136 863 151 bytes · **204 páginas** |
| `sha256` | `e96f67f7eadc3062530e…` (verificado presente en el clon) |
| Naturaleza | **100 % imagen** — 0 caracteres de texto en capa; el cuerpo de casos SAT solo es recuperable por **OCR** |
| RW-0009 (transmittal) | `215115305-T-041 SAT3 Completed.pdf`, 2 páginas — **NO** es el SAT; su `NOT_ANALYZABLE` es correcto |

No hay egress de documento: RW-0003 nunca sale del host (benchmark 100 % local).

---

## 2 · Métricas — FIJADAS Y FIRMADAS ANTES DE CORRER (criterio duro del diseño)

Definición operacional exacta, la MISMA para los 3 backends. **Se firman ahora; no se tocan
después de ver resultados.**

| Métrica | Definición operacional (determinista) |
|---|---|
| `source_page_fidelity` | `extractor_pages == pdf_pages` (204). Página perdida/duplicada ⇒ FAIL. |
| `usable_text_recovery` | nº de páginas con `len(strip(texto)) > 40` · % sobre 204 · total de caracteres. |
| `sat_oq_iq_identifier_recovery` | nº de identificadores DISTINTOS que casan `\b(SAT\|OQ\|IQ\|PQ)[\s-]?\d{1,4}[a-z]?\b` (normalizados sin espacios/guiones). |
| `insertion_false_positives` | nº de secuencias de 10+ caracteres repetidos + nº de `\x00`. Proxy de basura/alucinación de layout. |
| `table_reconstruction` | nº de tablas que el backend reconstruye (pdfplumber: `extract_tables`; Docling: filas markdown; OCRmyPDF: n/a=0). |
| `reading_order_sample` | primeros 1 200 caracteres del texto extraído — **inspección manual humana en D-4**. |
| `determinism` | el backend corre **2×**; `sha256(texto_run1) == sha256(texto_run2)` ⇒ PASS. |
| `runtime_s` | tiempo de pared de la 1ª corrida. |
| `peak_rss_mb` | `ru_maxrss` del proceso tras la corrida. |
| `offline_execution` | el backend corre DENTRO de `local_only.network_locked()` ⇒ PASS si no lanzó `EgressBlocked`. |
| `document_egress_bytes` | bytes que el backend intentó enviar afuera (medido por `EgressReport`, no declarado). |

**Sesgo de desempate DECLARADO (del diseño):** ante empate en la evidencia medida se prefiere
**menor superficie de validación** — OCRmyPDF+Tesseract (1 motor) sobre Docling (~5 modelos).
**Prohibido** elegir por nº de modelos, novedad o preferencia previa. La recomendación la fija
el humano en **D-4** leyendo el JSON de resultados.

`METRICS_SIGNED_BEFORE_RUN = YES` (este documento + `metrics_signed_before_run: true` en el
JSON del harness).

---

## 3 · Harness — `factory/scripts/ops/h9_extraction_benchmark.py`

Backends enchufables, misma métrica para los 3, corrida bajo `network_locked()`:

| Backend | Estado | Notas |
|---|---|---|
| `current` | **AVAILABLE** | pdfplumber (extractor de `extract_document.py`). Sin OCR. |
| `ocrmypdf_tesseract` | **REQUIRES_D3** | `pip install ocrmypdf pytesseract` + binario `tesseract-ocr` + `tesseract-ocr-eng`. OCRmyPDF con `--pdf-renderer` **pypdfium2/hocr**, NUNCA Ghostscript (AGPL). |
| `docling` | **REQUIRES_D3** | `pip install docling` (+ torch CPU, transformers, docling-ibm-models) + assets layout/TableFormer en `DOCLING_ARTIFACTS_PATH`. `enable_remote_services=False`. Verificar que `rapidocr` no descarga fuera de caché. |

`PyMuPDF` / `pymupdf4llm` **EXCLUIDOS** (AGPL). Cualquier backend que intente egress → el
`network_locked()` lo bloquea y `document_egress_bytes > 0` lo delata.

Uso tras D-3:
```
python3 factory/scripts/ops/h9_extraction_benchmark.py \
    --doc RW-0003 --backends current,ocrmypdf_tesseract,docling \
    --out docs_plan/H9_BENCH_RESULTS.json
```

---

## 4 · Línea base ejecutada AHORA — backend `current` sobre RW-0003 (nuestro código, sin descarga)

```
source_page_fidelity          = {pdf_pages: 204, extractor_pages: 204, match: true}
usable_text_recovery          = {pages_with_text_gt40: 0, pct_pages: 0.0, total_chars: 203}
sat_oq_iq_identifier_recovery  = {n_distinct: 0}
table_reconstruction          = {n_tables: 0}
insertion_false_positives     = 0
determinism                   = PASS
runtime_s                     = 0.16
peak_rss_mb                   = ~303
offline_execution             = PASS
document_egress_bytes         = 0     (local_only = True, egress_attempts = [])
```

**Interpretación (no es una conclusión de H-9):** el extractor de producción recupera **cero
texto usable** de RW-0003 — coherente con WP-C (204 páginas-imagen). Es la línea base contra la
que se medirán OCRmyPDF+Tesseract y Docling **tras D-3**. La conclusión y la recomendación de
extractor son de **D-4**, con las 3 columnas medidas.

---

## 5 · Qué falta (gates)

| Ítem | Gate | Bloqueo |
|---|---|---|
| Descargar OCRmyPDF+Tesseract y Docling+assets | **D-3** | `docs_plan/GATE_D3_DESCARGAS_H9.md` (paquete listo) |
| Ejecutar el benchmark de las 3 columnas + `docs_plan/CIERRE_H9_BENCHMARK_EXTRACCION.md` | tras D-3 | — |
| `RECOMMENDED_EXTRACTOR` + salto de `EXTRACTION_VERSION` | **D-4** | requiere el JSON de resultados que aún no existe |
| Métricas reales H-8 (`REAL_RECALL`/`REAL_SPECIFICITY`/`QA40_SAMPLE_PRECISION`) | **D-5** | `docs_plan/PAQUETE_D5_ADJUDICACION_H8.md` |

H-9 **preparación completa**. H-9 **benchmark** = pendiente de D-3. Sin commit, sin push, sin
cambios de producción.
