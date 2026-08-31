# GATE **D-3** — AUTORIZACIÓN DE DESCARGAS PARA EL BENCHMARK H-9

**Fecha:** 2026-08-30 · **Autoridad:** Capa 9 = Cesar · **Gate:** **D-3** (NO preautorizado — STOP).
**Contexto:** la instrucción de continuación autónoma **preautoriza D-3 condicionalmente**
("después de cerrar H-8 y exclusivamente para ejecutar el benchmark H-9"). H-8 aún no está
cerrado (métricas pendientes de D-5). Este paquete deja D-3 **listo para firmar** en cuanto
Capa 9 lo decida; **nada se descarga hasta entonces**.

**Alcance de lo que se pide autorizar:** descargar **solo software/modelos** para comparar
extractores en local. **NINGÚN** documento ni texto del cliente sale del host.

```
CLIENT_DOCUMENT_EGRESS = NO
CLIENT_TEXT_EGRESS     = NO
DOCUMENT_EGRESS        = 0
EXTERNAL_LLM_API       = PROHIBIDO
INSTALL_MODE           = local install / cache (pip + apt + HuggingFace snapshot a DESTINATION_LOCAL)
BENCHMARK_MODE         = local, bajo network_locked(), determinismo 2×
```

Si **cualquier** dependencia exigiera enviar documentos/texto a un servicio externo:
`NOT_AUTHORIZED` · STOP.

---

## Artefactos a descargar (registro previo — nada bajado aún)

### A · OCRmyPDF + Tesseract  (ruta de menor superficie — recomendada evaluar primero)

| Campo | Valor |
|---|---|
| **NAME** | `ocrmypdf` (PyPI) · `pytesseract` (PyPI) · `tesseract-ocr` + `tesseract-ocr-eng` (apt / paquete .deb) |
| **VERSION** | `ocrmypdf` última 16.x · `pytesseract` 0.3.x · `tesseract` 5.x (`eng.traineddata` de tessdata_fast) |
| **SOURCE** | `https://pypi.org/simple/ocrmypdf/` · `https://pypi.org/simple/pytesseract/` · repos Debian (`http://deb.debian.org`) para el binario · `https://github.com/tesseract-ocr/tessdata_fast` para `eng.traineddata` |
| **LICENSE** | OCRmyPDF **MPL-2.0** · pytesseract **Apache-2.0** · Tesseract **Apache-2.0** · `eng.traineddata` **Apache-2.0** — todas compatibles, sin AGPL |
| **SIZE** | `ocrmypdf`+deps ~15 MB · binario tesseract ~5 MB · `eng.traineddata` (fast) ~2 MB → **~25 MB** |
| **SHA256** | se registra en el momento de la descarga (pip `--require-hashes`; `sha256sum` del `.deb` y del `.traineddata`) → anexo `D3_DOWNLOAD_MANIFEST.json` |
| **DESTINATION_LOCAL** | venv del proyecto (`.venv`) para los wheels · binario tesseract vía apt (sistema) · `eng.traineddata` → `factory/regulatory/validation_v2/_h9_assets/tessdata/` |
| **RESTRICCIÓN** | OCRmyPDF DEBE usar `--pdf-renderer hocr` (rasterizado por **pypdfium2**), **nunca Ghostscript** (AGPL). No se instala `ghostscript` como dependencia de esta ruta. |

### B · Docling + assets de modelo

| Campo | Valor |
|---|---|
| **NAME** | `docling` (PyPI) → arrastra `docling-core`, `docling-ibm-models`, `torch` (CPU), `transformers`, `easyocr`/`rapidocr-onnxruntime` opcional · **assets:** modelo de layout + **TableFormer** (HuggingFace `ds4sd/docling-models`) |
| **VERSION** | `docling` última 2.x · `torch` **CPU-only** (índice `https://download.pytorch.org/whl/cpu`, sin CUDA — regla `CLAUDE.md`) · assets: release fijado de `ds4sd/docling-models` |
| **SOURCE** | `https://pypi.org/simple/docling/` (+ deps) · `torch` desde `https://download.pytorch.org/whl/cpu` · assets desde `https://huggingface.co/ds4sd/docling-models` (snapshot con `revision` fijada) |
| **LICENSE** | Docling **MIT** · docling-ibm-models **MIT** · torch **BSD-3** · transformers **Apache-2.0** · `ds4sd/docling-models` **CDLA-Permissive-2.0** — sin AGPL |
| **SIZE** | `torch` CPU ~800 MB · `transformers`+deps ~200 MB · assets layout+TableFormer ~0.5–1 GB → **~1.5–2 GB** |
| **SHA256** | pip `--require-hashes` para los wheels · `huggingface_hub snapshot_download` con `revision` + verificación de `sha256` por fichero → `D3_DOWNLOAD_MANIFEST.json` |
| **DESTINATION_LOCAL** | wheels → `.venv` · assets → `factory/regulatory/validation_v2/_h9_assets/docling/` y `export DOCLING_ARTIFACTS_PATH=<esa ruta>` |
| **RESTRICCIÓN** | `PdfPipelineOptions.enable_remote_services = False` (regla dura del diseño). Verificar que `rapidocr`/`easyocr` **no** descargan modelos fuera de la caché durante la corrida (correr bajo `network_locked()`; si intenta egress → `EgressBlocked` y el backend se marca FAIL). |

### EXCLUIDOS explícitamente

| Artefacto | Motivo |
|---|---|
| **PyMuPDF / pymupdf4llm** | **AGPL** — prohibido en producción sin decisión (y no aporta sobre las 2 rutas anteriores). |
| **Ghostscript** como rasterizador de OCRmyPDF | **AGPL** — se usa pypdfium2. |
| Cualquier **API de LLM externa** (OpenAI/Anthropic/Google/…) | El benchmark es 100 % local. Docling VLM remoto = `enable_remote_services=False`. |
| `torch` con CUDA | `CLAUDE.md`: solo `--index-url .../whl/cpu`. |

---

## Procedimiento tras la firma de D-3

1. Descargar con manifiesto: `pip download --require-hashes` / `apt-get download` / `huggingface_hub snapshot_download(revision=…)` → `D3_DOWNLOAD_MANIFEST.json` (NAME·VERSION·SHA256·SIZE·DESTINATION por artefacto).
2. Instalar en `.venv` + `_h9_assets/`. `export DOCLING_ARTIFACTS_PATH`.
3. `python3 factory/scripts/ops/h9_extraction_benchmark.py --doc RW-0003 --backends current,ocrmypdf_tesseract,docling --out docs_plan/H9_BENCH_RESULTS.json` (corre bajo `network_locked()`; determinismo 2×).
4. Generar `docs_plan/CIERRE_H9_BENCHMARK_EXTRACCION.md` con las 3 columnas medidas y la
   selección **basada solo en evidencia** (sesgo de desempate declarado).
5. Presentar **GATE D-4** (`RECOMMENDED_EXTRACTOR` + `PROPOSED_EXTRACTION_VERSION` + impacto +
   rollback) y **STOP**.

---

## Resumen para Capa 9

```
GATE                         = D-3   (preautorizado CONDICIONAL: tras cerrar H-8; hoy H-8 pendiente de D-5)
DOWNLOADS_REQUESTED           = 2 rutas: (A) OCRmyPDF+Tesseract ~25 MB  ·  (B) Docling+torch-CPU+assets ~1.5–2 GB
LICENSES                      = A: MPL-2.0 / Apache-2.0   ·   B: MIT / BSD-3 / Apache-2.0 / CDLA-Permissive-2.0   (0 AGPL)
CLIENT_DOCUMENT_EGRESS        = NO
CLIENT_TEXT_EGRESS           = NO
DOCUMENT_EGRESS              = 0
EXTERNAL_LLM_API             = PROHIBIDO
DESTINATION_LOCAL            = .venv  +  factory/regulatory/validation_v2/_h9_assets/{tessdata,docling}/
EXCLUDED                     = PyMuPDF (AGPL) · Ghostscript-como-rasterizador (AGPL) · torch-CUDA · toda API LLM
NOTHING_DOWNLOADED_YET        = TRUE
```

**STOP en D-3.** Nada se descarga ni se instala hasta la firma de Capa 9.
