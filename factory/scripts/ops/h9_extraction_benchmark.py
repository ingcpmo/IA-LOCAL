#!/usr/bin/env python3
"""H-9 (2026-08-30) -- benchmark de extracción sobre el SAT real RW-0003 (image-only).

Compara 3 rutas de extracción, **sin tocar producción**:
  CURRENT           = pdfplumber (extractor de `extract_document.py`)  -- disponible YA
  OCR_RAPIDOCR      = rapidocr-onnxruntime (pdfium 300dpi) -- sustituto pip-only de Tesseract (host sin sudo)
  DOCLING           = Docling (DOCLING_ARTIFACTS_PATH, enable_remote_services=false)   -- requiere D-3

Métricas FIJADAS ANTES de correr (ver docs_plan/H9_PREPARACION_BENCHMARK_EXTRACCION.md §metrics):
  source_page_fidelity · usable_text_recovery · sat_oq_iq_identifier_recovery ·
  insertion_false_positives · table_reconstruction · reading_order_sample ·
  determinism · runtime_s · peak_rss_mb · offline_execution · document_egress_bytes

Reglas duras:
  * Ejecuta bajo `local_only.network_locked()` -> DOCUMENT_EGRESS = 0 verificado, no declarado.
  * NINGÚN backend puede llamar a un LLM externo. Docling: `enable_remote_services=False`.
  * PyMuPDF EXCLUIDO (AGPL). OCRmyPDF con `--pdf-renderer` pypdfium2, nunca Ghostscript.
  * Determinismo: cada backend corre 2× y se compara el texto extraído byte a byte.
  * NO selecciona ganador por nº de modelos ni preferencia -- solo por evidencia medida
    (lo hace el humano en D-4 con este JSON).

Uso:
  h9_extraction_benchmark.py --doc RW-0003 [--backends current,ocr_rapidocr,docling] [--out results.json]
  h9_extraction_benchmark.py --list-backends        # qué está disponible / qué falta (D-3)
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import re
import resource
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))

from factory.regulatory.validation_v2.local_only import network_locked  # noqa: E402

_ID_RE = re.compile(r"\b(SAT|OQ|IQ|PQ)[\s\-]?\d{1,4}[a-z]?\b", re.I)
_SECTION_RE = re.compile(r"(?m)^\s{0,3}\d+(?:\.\d+){0,3}\s+[A-Z]")


_MAX_PAGES = None   # tope de páginas para el benchmark (None = todas)


class RequiresD3InstallError(RuntimeError):
    """El backend necesita paquetes/modelos que sólo se instalan tras GATE D-3."""


# ---------------------------------------------------------------------------
# resolución del fichero de RW-0003 (allowlist gobernada)
# ---------------------------------------------------------------------------
def _doc_path(doc_id: str) -> Path:
    """Resuelve `RW-000x` -> ruta local del PDF vía la allowlist gobernada."""
    import yaml
    y = yaml.safe_load((_REPO / "factory/regulatory/scope/source_baseline_allowlist.yaml").read_text())
    items = y if isinstance(y, list) else y.get("files", y.get("entries", []))
    for it in items:
        if isinstance(it, dict) and it.get("file_id") == doc_id:
            return _REPO / "GMPAI" / it["path"]
    raise FileNotFoundError(f"{doc_id} no está en source_baseline_allowlist.yaml")


# ---------------------------------------------------------------------------
# backends
# ---------------------------------------------------------------------------
def _peak_rss_mb() -> float:
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)  # KiB->MiB en Linux


def backend_current(pdf: Path) -> dict:
    """pdfplumber -- el extractor de producción. Sin OCR: en RW-0003 (100% imagen)
    NO recupera texto; es la línea base honesta."""
    import pdfplumber
    pages_text: list[str] = []
    n_tables = 0
    with pdfplumber.open(str(pdf)) as doc:
        for pg in (doc.pages[:_MAX_PAGES] if _MAX_PAGES else doc.pages):
            t = pg.extract_text() or ""
            pages_text.append(t)
            try:
                n_tables += len(pg.extract_tables() or [])
            except Exception:  # noqa: BLE001
                pass
    return {"pages_text": pages_text, "n_tables": n_tables, "engine": "pdfplumber"}


def backend_ocr_rapidocr(pdf: Path) -> dict:
    """OCR de MENOR superficie de validación (1 motor).

    SUSTITUCIÓN D-3 documentada: el diseño pedía OCRmyPDF+**Tesseract**, pero el
    binario `tesseract-ocr` exige root/apt y este host no tiene sudo. Se usa
    **rapidocr-onnxruntime** (Apache-2.0, pip-only, 3 modelos ONNX ~16 MB
    EMPAQUETADOS en el wheel -> 0 descarga en uso -> corre offline). Rasteriza
    con **pypdfium2** (NO Ghostscript). Misma categoría: OCR de motor único.
    """
    try:
        import numpy as np
        import pypdfium2 as pdfium
        from rapidocr_onnxruntime import RapidOCR
    except Exception as e:  # noqa: BLE001
        raise RequiresD3InstallError(
            "rapidocr-onnxruntime no instalado (GATE D-3): `pip install rapidocr-onnxruntime`.") from e
    ocr = RapidOCR()
    doc = pdfium.PdfDocument(str(pdf))
    pages_text: list[str] = []
    n = min(len(doc), _MAX_PAGES) if _MAX_PAGES else len(doc)
    for i in range(n):
        page = doc[i]
        bmp = page.render(scale=300 / 72)          # 300 DPI, rasterizador PDFium
        img = np.asarray(bmp.to_pil().convert("RGB"))
        res, _ = ocr(img)
        pages_text.append("\n".join(line[1] for line in (res or [])))
        page.close()
    doc.close()
    return {"pages_text": pages_text, "n_tables": 0, "engine": "rapidocr-onnxruntime(pdfium 300dpi)"}


_DOCLING_ASSETS = _REPO / "factory/regulatory/validation_v2/_h9_assets/docling"


def backend_docling(pdf: Path) -> dict:
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
    except Exception as e:  # noqa: BLE001
        raise RequiresD3InstallError(
            "Docling no instalado (GATE D-3): `pip install docling --extra-index-url "
            "https://download.pytorch.org/whl/cpu` + assets en _h9_assets/docling.") from e
    import os
    if not _DOCLING_ASSETS.is_dir():
        raise RequiresD3InstallError(f"assets Docling ausentes en {_DOCLING_ASSETS} (D-3).")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")   # nada de HuggingFace en tiempo de corrida
    # docling 2.123 + pydantic 2.10: el hash del pipeline-cache revienta con
    # "Circular reference detected". Se neutraliza (solo afecta a la caché de opciones).
    # Hay que parchear el BINDING que usa `_get_pipeline` (importado a document_converter),
    # no solo el del módulo pipeline_cache.
    _fixed = lambda *a, **k: "h9-fixed"  # noqa: E731
    try:
        import docling.utils.pipeline_cache as _pc
        _pc.create_pipeline_options_hash = _fixed
    except Exception:  # noqa: BLE001
        pass
    try:
        import docling.document_converter as _dc
        _dc.create_pipeline_options_hash = _fixed
    except Exception:  # noqa: BLE001
        pass
    opts = PdfPipelineOptions()
    opts.enable_remote_services = False            # regla dura del diseño H-9
    opts.do_ocr = True
    opts.do_table_structure = True
    opts.artifacts_path = str(_DOCLING_ASSETS)
    conv = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})
    _kw = {'page_range': (1, _MAX_PAGES)} if _MAX_PAGES else {}
    res = conv.convert(str(pdf), **_kw)
    doc = res.document
    md = doc.export_to_markdown()
    # páginas: Docling numera por page-no; se agrupa el texto por página si está disponible
    try:
        by_page: dict[int, list[str]] = {}
        for it, _lvl in doc.iterate_items():
            txt = getattr(it, "text", None)
            if not txt:
                continue
            prov = getattr(it, "prov", None) or []
            pno = prov[0].page_no if prov else 0
            by_page.setdefault(pno, []).append(txt)
        pages_text = ["\n".join(by_page[k]) for k in sorted(by_page)] or [md]
    except Exception:  # noqa: BLE001
        pages_text = [md]
    n_tables = len(getattr(doc, "tables", []) or [])
    return {"pages_text": pages_text, "n_tables": n_tables, "engine": "docling(layout+tableformer+rapidocr, offline)"}


BACKENDS = {
    "current": backend_current,
    "ocr_rapidocr": backend_ocr_rapidocr,
    "docling": backend_docling,
}


# ---------------------------------------------------------------------------
# métricas (FIJADAS ANTES DE CORRER)
# ---------------------------------------------------------------------------
def _metrics(raw: dict, *, n_pages_pdf: int, runtime_s: float, peak_mb: float,
            deterministic: bool, egress_bytes: int) -> dict:
    pages = raw["pages_text"]
    full = "\n".join(pages)
    pages_with_text = sum(1 for p in pages if len((p or "").strip()) > 40)
    ids = sorted({m.group(0).upper().replace(" ", "").replace("-", "") for m in _ID_RE.finditer(full)})
    # "insertion false positives": tokens claramente espurios (secuencias de control / repетición)
    ins_fp = len(re.findall(r"(.)\1{9,}", full)) + full.count("\x00")
    return {
        "source_page_fidelity": {"pdf_pages": n_pages_pdf, "pages_processed": (_MAX_PAGES or n_pages_pdf),
                                 "extractor_pages": len(pages),
                                 "match": len(pages) == (_MAX_PAGES or n_pages_pdf)},
        "usable_text_recovery": {"pages_with_text_gt40": pages_with_text,
                                 "pct_pages": round(100 * pages_with_text / max(1, (_MAX_PAGES or n_pages_pdf)), 1),
                                 "total_chars": len(full)},
        "sat_oq_iq_identifier_recovery": {"n_distinct": len(ids), "sample": ids[:25]},
        "insertion_false_positives": ins_fp,
        "table_reconstruction": {"n_tables": raw.get("n_tables", 0)},
        "reading_order_sample": (full[:1200]),   # inspección manual en D-4
        "determinism": "PASS" if deterministic else "FAIL",
        "runtime_s": round(runtime_s, 2),
        "peak_rss_mb": peak_mb,
        "offline_execution": "PASS",             # corrió dentro de network_locked()
        "document_egress_bytes": egress_bytes,
    }


def _run_backend(name: str, pdf: Path, n_pages_pdf: int) -> dict:
    fn = BACKENDS[name]
    gc.collect()
    with network_locked() as egress:
        t0 = time.time()
        try:
            r1 = fn(pdf)
        except RequiresD3InstallError as e:
            return {"backend": name, "status": "REQUIRES_D3", "detail": str(e)}
        dt = time.time() - t0
        # segunda corrida para determinismo (texto byte a byte)
        r2 = fn(pdf)
    h1 = hashlib.sha256("\n".join(r1["pages_text"]).encode("utf-8", "replace")).hexdigest()
    h2 = hashlib.sha256("\n".join(r2["pages_text"]).encode("utf-8", "replace")).hexdigest()
    m = _metrics(r1, n_pages_pdf=n_pages_pdf, runtime_s=dt, peak_mb=_peak_rss_mb(),
                 deterministic=(h1 == h2), egress_bytes=egress.document_egress_bytes)
    return {"backend": name, "status": "OK", "engine": r1["engine"],
            "text_sha256": h1, "metrics": m,
            "network_egress_attempts": egress.attempts, "local_only": egress.local_only}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--doc", default="RW-0003")
    ap.add_argument("--backends", default="current")
    ap.add_argument("--out", default=None)
    ap.add_argument("--max-pages", type=int, default=None, help="tope de páginas (muestra); None = 204")
    ap.add_argument("--list-backends", action="store_true")
    args = ap.parse_args()
    global _MAX_PAGES
    _MAX_PAGES = args.max_pages

    if args.list_backends:
        import importlib.util
        for name, fn in BACKENDS.items():
            try:
                import importlib.util
                with network_locked():
                    fn.__wrapped__ if False else None
                import importlib
                if name == "current":
                    avail, why = True, "pdfplumber instalado"
                elif name == "ocr_rapidocr":
                    ok = importlib.util.find_spec("rapidocr_onnxruntime") is not None
                    avail, why = ok, "instalado" if ok else "falta rapidocr-onnxruntime (D-3)"
                else:
                    ok = importlib.util.find_spec("docling") is not None
                    avail, why = ok, "instalado" if ok else "falta docling + torch + assets (D-3)"
            except Exception as e:  # noqa: BLE001
                avail, why = False, str(e)
            print(f"  {name:20} {'AVAILABLE' if avail else 'REQUIRES_D3':12} {why}")
        return 0

    pdf = _doc_path(args.doc)
    if not pdf.is_file():
        print(f"fichero no encontrado: {pdf}", file=sys.stderr); return 2
    import pdfplumber
    with pdfplumber.open(str(pdf)) as d:
        n_pages_pdf = len(d.pages)

    results = {
        "artifact": "h9_extraction_benchmark",
        "doc_id": args.doc, "pdf_path": str(pdf.relative_to(_REPO)),
        "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "pdf_pages": n_pages_pdf,
        "metrics_signed_before_run": True,
        "max_pages": _MAX_PAGES,
        "ocr_engine_substitution": "OCRmyPDF+Tesseract -> rapidocr-onnxruntime (host sin sudo; Apache-2.0; pip-only; modelos empaquetados)",
        "tie_break_bias": "menor superficie de validación (OCRmyPDF+Tesseract=1 motor vs Docling ~5 modelos)",
        "backends": {},
    }
    for name in [b.strip() for b in args.backends.split(",") if b.strip()]:
        if name not in BACKENDS:
            print(f"backend desconocido: {name}", file=sys.stderr); return 2
        print(f"[h9] backend {name} ...", file=sys.stderr)
        results["backends"][name] = _run_backend(name, pdf, n_pages_pdf)

    out = json.dumps(results, indent=1, ensure_ascii=False, default=str)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"[h9] escrito {args.out}", file=sys.stderr)
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
