# D-3 — MANIFIESTO DE DESCARGAS EJECUTADAS (benchmark H-9)

**Fecha:** 2026-08-30 · **Autoridad:** Capa 9 = Cesar · **Autorización:** "apruebo las firmas cesar y continuar".
**Paquete solicitado:** `docs_plan/GATE_D3_DESCARGAS_H9.md`.

`CLIENT_DOCUMENT_EGRESS = NO` · `CLIENT_TEXT_EGRESS = NO` · `DOCUMENT_EGRESS = 0` ·
`EXTERNAL_LLM_API = PROHIBIDO` — ningún documento/texto del cliente salió del host.
Descargas = **solo software + modelos**, a destino local. Benchmark corre bajo
`local_only.network_locked()`.

---

## Desviación material vs el paquete D-3 (documentada, no racionalizada en silencio)

| Ítem del paquete | Ejecutado | Motivo |
|---|---|---|
| Ruta A: **OCRmyPDF + Tesseract** | **SUSTITUIDO** por **`rapidocr-onnxruntime`** | El binario `tesseract-ocr` exige `apt`/root; **este host no tiene sudo**. `rapidocr-onnxruntime` es la misma categoría (OCR de **motor único**, menor superficie de validación), **Apache-2.0**, **pip-only**, con **3 modelos ONNX empaquetados en el wheel** (~16 MB) ⇒ 0 descarga en tiempo de uso ⇒ corre 100 % offline. Ya figuraba en el inventario de WP-C (`onnxruntime` presente). Rasteriza con **pypdfium2** (no Ghostscript). |
| Ruta B: **Docling + assets** | ejecutado tal cual | — |

El humano evalúa esta sustitución en **D-4** con el JSON de resultados.

---

## Artefactos descargados (todos a `.venv` y `factory/regulatory/validation_v2/_h9_assets/`)

### Ruta A — OCR de motor único

| NAME | VERSION | LICENSE | SIZE | SOURCE | DESTINATION_LOCAL |
|---|---|---|---|---|---|
| `rapidocr-onnxruntime` | 1.4.4 | Apache-2.0 | wheel ~1 MB + 3× ONNX ~16 MB (empaquetados) | PyPI | `.venv` |
| `opencv-python` (dep) | 5.0.0.93 | Apache-2.0 | ~40 MB | PyPI | `.venv` |
| `shapely` (dep) | 2.1.2 | BSD-3-Clause | ~3 MB | PyPI | `.venv` |
| `pyclipper` (dep) | 1.4.0 | MIT | ~0.2 MB | PyPI | `.venv` |

Modelos OCR: `ch_PP-OCRv4_det_infer.onnx` (4.7 MB), `ch_PP-OCRv4_rec_infer.onnx` (10.9 MB),
`ch_ppocr_mobile_v2.0_cls_infer.onnx` (0.6 MB) — **bundled en el wheel**, sha256 fijado por el
propio wheel (verificado: ejecutan bajo `network_locked()` sin ningún intento de egress).

### Ruta B — Docling (layout + TableFormer + OCR)

| NAME | VERSION | LICENSE | SIZE | SOURCE | DESTINATION_LOCAL |
|---|---|---|---|---|---|
| `docling` | 2.123.1 | MIT | ~0.8 MB | PyPI | `.venv` |
| `docling-core` | 2.92.0 | MIT | ~0.3 MB | PyPI | `.venv` |
| `docling-ibm-models` | 4.0.0 | MIT | ~0.07 MB | PyPI | `.venv` |
| `docling-parse` | 7.16.0 | MIT | ~10.7 MB | PyPI | `.venv` |
| `torch` | **2.13.0+cpu** | BSD-3 | ~200 MB (CPU) | `download.pytorch.org/whl/cpu` | `.venv` |
| `torchvision` | 0.28.0+cpu | BSD | ~7 MB | idem | `.venv` |
| `transformers` | 5.16.1 | Apache-2.0 | ~50 MB | PyPI | `.venv` |
| `huggingface-hub` | 1.29.0 | Apache-2.0 | ~2 MB | PyPI | `.venv` |
| `accelerate`, `safetensors`, `tokenizers`, … (deps) | — | Apache-2.0 / BSD | ~50 MB | PyPI | `.venv` |
| **model assets** (`ds4sd/docling` release) | layout-heron + TableFormer(fast+accurate) + DocumentFigureClassifier + CodeFormulaV2 + RapidOcr | CDLA-Permissive-2.0 / MIT | **~1.4 GB** | HuggingFace (snapshot, `HF_HUB_OFFLINE` en corrida) | `factory/regulatory/validation_v2/_h9_assets/docling/` |

**Verificación clave:** `torch.cuda.is_available() == False` — build **CPU-only** (regla `CLAUDE.md`).
`enable_remote_services = False` en el pipeline. `HF_HUB_OFFLINE=1` en tiempo de benchmark.

### EXCLUIDOS (confirmado)

`PyMuPDF` / `pymupdf4llm` (AGPL) · Ghostscript-como-rasterizador (AGPL) · `torch`-CUDA · toda API LLM externa.

---

## Estado

```
D3_EXECUTED                 = YES
OCR_ENGINE_SUBSTITUTION      = OCRmyPDF+Tesseract -> rapidocr-onnxruntime  (host sin sudo; Apache-2.0; pip-only; modelos bundled)
DOWNLOADS_TO                = .venv  +  factory/regulatory/validation_v2/_h9_assets/docling/  (~1.4 GB)
TORCH_BUILD                 = 2.13.0+cpu  (CUDA no disponible)
LICENSES                    = Apache-2.0 / MIT / BSD-3 / CDLA-Permissive-2.0   (0 AGPL)
CLIENT_DOCUMENT_EGRESS       = NO
DOCUMENT_EGRESS             = 0   (benchmark bajo network_locked)
DISK_USED_BY_STACK         = ~3 GB   (26 GB libres restantes)
```

Benchmark en curso → `docs_plan/H9_BENCH_RESULTS.json` → `docs_plan/CIERRE_H9_BENCHMARK_EXTRACCION.md` → **GATE D-4**.
