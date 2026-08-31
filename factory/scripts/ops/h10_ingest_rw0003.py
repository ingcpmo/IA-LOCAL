#!/usr/bin/env python3
"""H-10 -- ingesta CONTROLADA EN MEMORIA de RW-0003 (SAT real, 204 pág, 100% imagen).

`extract_document(..., ocr=True, extract_tests=True)` con docling **por lotes de
páginas** (`_DOCLING_BATCH_PAGES`, liberación explícita entre lotes). Destino: el
store paralelo `canonical_store_v2/` (v1 intacto). Reporta RSS pico y conteos.

Uso:  h10_ingest_rw0003.py [--dest factory/regulatory/canonical_store_v2]
"""
from __future__ import annotations

import argparse
import json
import resource
import sys
import threading
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))

from factory.regulatory.canonical.extract_document import extract_document  # noqa: E402
from factory.regulatory.canonical.persistence import CanonicalStore  # noqa: E402
from factory.regulatory.validation_v2.local_only import network_locked  # noqa: E402

_PDF = _REPO / "GMPAI/source/Rockwell/215115305 SCADA-PCS Misc PLC SAT3 Scanned-1.pdf"


def _rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _watch(stop: threading.Event, peak: list):
    import os
    while not stop.is_set():
        try:
            with open(f"/proc/{os.getpid()}/status") as f:
                for ln in f:
                    if ln.startswith("VmRSS:"):
                        kb = int(ln.split()[1]); peak[0] = max(peak[0], kb / 1024)
        except Exception:
            pass
        time.sleep(2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=str(_REPO / "factory/regulatory/canonical_store_v2"))
    args = ap.parse_args()
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)

    peak = [0.0]
    stop = threading.Event()
    th = threading.Thread(target=_watch, args=(stop, peak), daemon=True)
    th.start()

    t0 = time.time()
    with network_locked() as egress:
        res = extract_document(_PDF, "RW-0003", tipo="SAT", store_dir=dest,
                               extract_tests=True, ocr=True)
    dt = time.time() - t0
    stop.set()

    with CanonicalStore("RW-0003", store_dir=dest) as s:
        doc = s.all("document")[0]
        tests = s.all("test")
        with_ref = [t for t in tests if t.get("verifies_requirement_ids")]
        tabs = s.all("table_obj")
        summary = {
            "document_id": "RW-0003",
            "extraction_version": doc.get("extraction_version"),
            "n_paginas": doc.get("n_paginas"),
            "claims": len(s.all("claim")),
            "sections": len(s.all("section")),
            "tables": len(tabs),
            "system_component": len(s.all("system_component")),
            "actor": len(s.all("actor")),
            "TEST_OBJECTS_RW0003": len(tests),
            "TESTS_WITH_REQUIREMENT_REF": len(with_ref),
            "TESTS_WITHOUT_REQUIREMENT_REF": len(tests) - len(with_ref),
            "sample_tests": [
                {"id": t["identificador"], "page": (t.get("provenance") or {}).get("page"),
                 "refs": t.get("verifies_requirement_ids"),
                 "resultado": t.get("resultado"),
                 "descripcion": (t.get("descripcion") or "")[:160],
                 "source_hash": (t.get("provenance") or {}).get("source_hash")}
                for t in tests[:15]
            ],
        }
    out = {
        "runtime_s": round(dt, 1),
        "peak_rss_mb": round(max(peak[0], _rss_mb()), 1),
        "document_egress_bytes": egress.document_egress_bytes,
        "local_only": egress.local_only,
        "dest": str(dest),
        "summary": summary,
    }
    (_REPO / "docs_plan/_h9_full/H10_RW0003_INGEST.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
