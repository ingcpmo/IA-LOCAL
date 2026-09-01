"""F1 — medición reproducible: HEAD-limpio vs con-cambio del extractor,
contra un ground truth de encabezados DERIVADO MECÁNICAMENTE del documento real.

READ-ONLY sobre los PDFs y el código. No modifica nada. Salida a stdout + JSON.
Plan de reconciliación v1.1, FASE 1. Ejecutar:  PYTHONPATH=. .venv/bin/python docs_plan/reconc/F1_measure.py
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pdfplumber

from factory.regulatory import document_structure_extractor as dse

DS_DOCS = {
    "RW-0011": "GMPAI/source/Rockwell/MCCPDC EMS Control Block Narrative revB.pdf",
    "RW-0012": "GMPAI/source/Rockwell/MCCPDC PCS Signal Interface Control Block Narrative.pdf",
    "RW-0014": "GMPAI/source/Rockwell/MCCPDC WFI Control Block Narrative revB.pdf",
}

# Regex de HEAD (416f2da) — SIN el `\.?` opcional
HEAD_HEADING_RE = re.compile(r"^(\d{1,2})\s+([A-Za-z][A-Za-z0-9 ,;:/\-\(\)'\.]{1,90})$")
HEAD_TOC_RE = re.compile(
    r"^(\d{1,2})\s+([A-Za-z][A-Za-z0-9 ,;:/\-\(\)'\.]{1,90}?)\s*\.{3,}\s*[\d ]+$"
)
# Regex del working tree (4c492a7) — CON `\.?`
WT_HEADING_RE = re.compile(r"^(\d{1,2})\.?\s+([A-Za-z][A-Za-z0-9 ,;:/\-\(\)'\.]{1,90})$")
WT_TOC_RE = re.compile(
    r"^(\d{1,2})\.?\s+([A-Za-z][A-Za-z0-9 ,;:/\-\(\)'\.]{1,90}?)\s*\.{3,}\s*[\d ]+$"
)

# Ground truth: patrón AMPLIO para localizar candidatos a encabezado numerado en
# el CUERPO del documento (no solo el TOC). Deliberadamente permisivo: captura
# "N Titulo" y "N. Titulo" con inicial mayúscula. La lista se congela y se revisa.
GT_BODY_RE = re.compile(r"^(\d{1,2})\.?\s+([A-Z][A-Za-z0-9 ,;:/\-\(\)'&\.]{2,90})\s*$")
GT_TOC_RE = re.compile(r"^(\d{1,2})\.?\s+(.+?)\s*\.{3,}\s*([\divxlIVXL ]+)\s*$")


def per_page_text(pdf_path: Path) -> list[str]:
    with pdfplumber.open(pdf_path) as pdf:
        return [(p.extract_text() or "") for p in pdf.pages]


def build_ground_truth(pages: list[str]) -> dict:
    """Deriva mecánicamente del documento real: (a) entradas de TOC con líder de
    puntos; (b) líneas del cuerpo que parecen encabezado numerado. Nivel 1 =
    número entero secuencial. Se congela para revisión humana en el gate F1."""
    toc_entries = []            # (numero, titulo, pagina_declarada, page_found)
    body_headings = []          # (numero, titulo, page_found)
    contents_pages = []
    for pg, text in enumerate(pages, start=1):
        low = (text or "").lower()
        if re.search(r"^\s*contents\s*$", low, re.M) or "table of contents" in low:
            contents_pages.append(pg)
        for raw in (text or "").splitlines():
            line = raw.strip()
            if not line:
                continue
            m = GT_TOC_RE.match(line)
            if m:
                toc_entries.append({"numero": int(m.group(1)),
                                    "titulo": " ".join(m.group(2).split()),
                                    "pagina_declarada": m.group(3).strip(),
                                    "page_found": pg})
                continue
            m = GT_BODY_RE.match(line)
            if m:
                body_headings.append({"numero": int(m.group(1)),
                                      "titulo": " ".join(m.group(2).split()),
                                      "page_found": pg, "raw": line})
    # nivel-1 secuencial a partir del TOC (1,2,3,...)
    seq = {}
    for e in toc_entries:
        seq.setdefault(e["numero"], e["titulo"])
    level1_from_toc = [{"numero": n, "titulo": seq[n]} for n in sorted(seq) if n >= 1]
    return {
        "contents_pages": contents_pages,
        "toc_entries": toc_entries,
        "body_heading_candidates": body_headings,
        "level1_from_toc_sequential": level1_from_toc,
    }


def run_with(regexes, pages):
    h_re, t_re = regexes
    old_h, old_t = dse._HEADING_RE, dse._TOC_ENTRY_RE
    dse._HEADING_RE, dse._TOC_ENTRY_RE = h_re, t_re
    try:
        return dse.extract_structure(pages)
    finally:
        dse._HEADING_RE, dse._TOC_ENTRY_RE = old_h, old_t


def summarize(res: dict) -> dict:
    return {
        "toc_anchored": res["toc_anchored"],
        "n_secciones": len(res["secciones"]),
        "secciones": [{"numero": s["numero"], "titulo": s["titulo"],
                       "pagina_inicio": s["pagina_inicio"],
                       "n_parrafos": len(s["parrafos"])} for s in res["secciones"]],
        "n_lineas_pre_primera_seccion": len(res["texto_previo_a_primera_seccion"]),
    }


def main():
    out = {"doc_extractor_head_re": "no `\\.?`", "doc_extractor_wt_re": "con `\\.?`", "docs": {}}
    for doc, path in DS_DOCS.items():
        p = Path(path)
        pages = per_page_text(p)
        pdf_sha = hashlib.sha256(p.read_bytes()).hexdigest()
        gt = build_ground_truth(pages)
        head = summarize(run_with((HEAD_HEADING_RE, HEAD_TOC_RE), pages))
        wt = summarize(run_with((WT_HEADING_RE, WT_TOC_RE), pages))
        out["docs"][doc] = {
            "pdf_path": path, "pdf_sha256": pdf_sha, "n_paginas": len(pages),
            "ground_truth": gt,
            "HEAD": head, "WT": wt,
            "delta_n_secciones": wt["n_secciones"] - head["n_secciones"],
            "delta_toc_anchored": (head["toc_anchored"], wt["toc_anchored"]),
        }
        print(f"\n===== {doc}  ({path})  sha256={pdf_sha[:16]}  paginas={len(pages)} =====")
        print(f"  GT: contents_pages={gt['contents_pages']}  "
              f"level1_from_toc={[ (e['numero'], e['titulo']) for e in gt['level1_from_toc_sequential'] ]}")
        print(f"  GT body-heading candidates ({len(gt['body_heading_candidates'])}):")
        for b in gt["body_heading_candidates"]:
            print(f"       p{b['page_found']:>2}  {b['raw']}")
        print(f"  HEAD-limpio : toc_anchored={head['toc_anchored']}  n_secciones={head['n_secciones']}  "
              f"-> {[ (s['numero'], s['titulo']) for s in head['secciones'] ]}")
        print(f"  WT con-cambio: toc_anchored={wt['toc_anchored']}  n_secciones={wt['n_secciones']}  "
              f"-> {[ (s['numero'], s['titulo']) for s in wt['secciones'] ]}")
        print(f"  DELTA n_secciones (WT - HEAD) = {out['docs'][doc]['delta_n_secciones']}")

    Path("docs_plan/reconc/F1_extractor_before_after.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False))
    gt_only = {d: out["docs"][d]["ground_truth"] for d in out["docs"]}
    gt_canon = json.dumps(gt_only, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    gt_sha = hashlib.sha256(gt_canon.encode()).hexdigest()
    Path("docs_plan/reconc/F1_ground_truth_headings.json").write_text(
        json.dumps(gt_only, indent=2, ensure_ascii=False))
    print(f"\nGROUND_TRUTH_SHA256 = {gt_sha}")
    print("escrito: F1_extractor_before_after.json , F1_ground_truth_headings.json")


if __name__ == "__main__":
    main()
