"""WP-E.3 -- Corpus held-out (técnico): loader + builder SEPARADO + runner de match ESTRUCTURAL.

docs_plan/PLAN_HARDENING_ANALIZADOR_GMP_LOCAL_V2.md WP-E.

Elimina el acoplamiento de validez de constructo del `technical_suite_c` (D-3):
  * el ground truth (`held_out_technical_corpus.yaml`) describe QUÉ encontrar por
    (class, subtype, document, page_band) -- NUNCA la frase que el builder inserta;
  * el builder del corpus (`build_seed_corpus`) vive aquí, separado del runner de
    Suite C;
  * `assert_usable_as_gate()` exige `status: SIGNED` **y** autor != autor de
    `technical_completeness_rules.yaml` (fail-closed).

DRAFT_UNSIGNED por default -> `run_held_out_dry()` produce números INDICATIVOS
envueltos en un metric_envelope con `reportable_range = NOT_A_GATE`.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml as _yaml

from factory.regulatory.canonical import model as m
from factory.regulatory.canonical.persistence import CanonicalStore
from factory.regulatory.graph import build as gb
from factory.regulatory.validation_v2 import metric_envelope as me

_ARTIFACT = (Path(__file__).resolve().parent.parent
             / "requirement_catalog" / "held_out_technical_corpus.yaml")
_RULES = (Path(__file__).resolve().parent.parent
          / "requirement_catalog" / "technical_completeness_rules.yaml")

PROJECT_ID = "HELD-OUT-TECH"
HO_URS, HO_FS, HO_FSOK, HO_DS = "HO-URS", "HO-FS", "HO-FSOK", "HO-DS"
_EXT_VER = m.EXTRACTION_VERSION
PROVENANCE_TAGS = ("REG", "DOM", "ADV")


class HeldOutCorpusError(RuntimeError):
    pass


class HeldOutNotUsableAsGateError(HeldOutCorpusError):
    """DRAFT_UNSIGNED, o autor == autor de las reglas -> no es un gate."""


@lru_cache(maxsize=2)
def _load(path_str: str) -> dict:
    p = Path(path_str)
    data = _yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "cases" not in data:
        raise HeldOutCorpusError(f"{p.name}: sin bloque 'cases'")
    for i, c in enumerate(data["cases"]):
        if "case_id" not in c or "provenance_tag" not in c or "expected" not in c or "match" not in c:
            raise HeldOutCorpusError(f"{p.name} caso {i}: faltan campos obligatorios")
        if c["provenance_tag"] not in PROVENANCE_TAGS:
            raise HeldOutCorpusError(f"{p.name}/{c['case_id']}: provenance_tag inválido {c['provenance_tag']!r}")
        if c["provenance_tag"] == "REG" and not (c.get("source_clause") or "").strip():
            raise HeldOutCorpusError(f"{p.name}/{c['case_id']}: REG sin source_clause")
        if c["provenance_tag"] == "ADV" and c.get("human_approved") is not True:
            raise HeldOutCorpusError(f"{p.name}/{c['case_id']}: ADV sin human_approved: true")
    return data


def load(path: Path | None = None) -> dict:
    return _load(str(path or _ARTIFACT))


def _rules_author() -> str:
    try:
        r = _yaml.safe_load(_RULES.read_text(encoding="utf-8"))
        return str(r.get("signed_by") or "").strip()
    except Exception:
        return ""


def status(path: Path | None = None) -> str:
    return str(load(path).get("status", "")).upper()


def is_usable_as_gate(path: Path | None = None) -> bool:
    d = load(path)
    if str(d.get("status", "")).upper() != "SIGNED":
        return False
    author = str(d.get("author") or "").strip()
    if not author:
        return False
    excluded = set(d.get("excluded_authors") or []) | {_rules_author()}
    return author not in excluded


def assert_usable_as_gate(path: Path | None = None) -> None:
    if not is_usable_as_gate(path):
        d = load(path)
        raise HeldOutNotUsableAsGateError(
            f"held_out_technical_corpus no usable como gate: status={d.get('status')!r} "
            f"author={d.get('author')!r} (debe estar SIGNED por un autor != {_rules_author()!r} "
            f"y != {d.get('excluded_authors')}).")


# ── builder del corpus (SEPARADO del runner de Suite C) ──────────────────
def _c(store, doc_id, page, text, tipo="function"):
    store.put(m.build_claim(doc_id, page, text, tipo, text[:180]))


def build_seed_corpus(canon_dir: Path, graph_dir: Path) -> dict:
    """Construye la SEMILLA sintética. El texto lo redacta ESTE builder; el ground
    truth del yaml solo dice class/subtype/document/page_band -> sin acoplamiento."""
    with CanonicalStore(HO_URS, store_dir=canon_dir) as s:
        s.put(m.Document(document_id=HO_URS, sha256="0" * 64, tipo="URS",
                         titulo="Held-out URS", n_paginas=8))
        _c(s, HO_URS, 1, "UR-HO-01 The system shall maintain a complete audit trail.", "control")
        _c(s, HO_URS, 2, "UR-HO-02 The system shall protect data through role based access.", "control")

    with CanonicalStore(HO_FS, store_dir=canon_dir) as s:
        s.put(m.Document(document_id=HO_FS, sha256="f" * 64, tipo="FS",
                         titulo="Held-out FS (con brechas)", n_paginas=30))
        # brechas deliberadas -- la REDACCIÓN la elige el builder, no el yaml
        _c(s, HO_FS, 12, "An audit log table exists in the application database.")               # HO-T-001
        _c(s, HO_FS, 13, "The operator can trigger a manual export of records.")                 # ruido
        _c(s, HO_FS, 14, "System data is copied to a network share periodically.")               # HO-T-002
        _c(s, HO_FS, 15, "Three named roles are available in the configuration screen.")         # HO-T-003 / HO-T-004
        _c(s, HO_FS, 16, "The workstation runs a supported operating system version.")           # ruido

    with CanonicalStore(HO_FSOK, store_dir=canon_dir) as s:
        s.put(m.Document(document_id=HO_FSOK, sha256="c" * 64, tipo="FS",
                         titulo="Held-out FS conforme", n_paginas=20))
        _c(s, HO_FSOK, 3, "The audit trail records the user identity, timestamp, the previous "
                          "value and the new value for every change, and cannot be modified or "
                          "disabled by any role including administrators.")                       # HO-T-N01

    return gb.build_project_graph(
        PROJECT_ID, [(HO_URS, "URS"), (HO_FS, "FS"), (HO_FSOK, "FS")],
        canon_dir=canon_dir, graph_dir=graph_dir)


# ── runner de match ESTRUCTURAL ─────────────────────────────────────────
def _match(case: dict, findings) -> bool:
    exp = case["expected"]
    if not exp.get("finding"):
        return False
    mt = case["match"]
    band = mt.get("page_band") or [1, 10 ** 6]
    tol = int(load().get("match_policy", {}).get("page_band_tolerance", 3))
    lo, hi = band[0] - tol, band[1] + tol
    for f in findings:
        if (f.finding_class == exp["finding_class"] and f.subtype == exp["subtype"]
                and f.document == mt["document"] and lo <= (f.page or 0) <= hi):
            return True
    return False


def run_held_out_dry(canon_dir: Path | None = None, graph_dir: Path | None = None) -> dict:
    """Ejecuta el analizador técnico determinista sobre la semilla held-out y
    mide por MATCH ESTRUCTURAL. INDICATIVO mientras status != SIGNED."""
    import tempfile

    from factory.regulatory.findings.technical_findings import graph_technical_findings
    from factory.regulatory.validation_v2.local_only import network_locked

    cdir = Path(canon_dir) if canon_dir else Path(tempfile.mkdtemp(prefix="ho-canon-"))
    gdir = Path(graph_dir) if graph_dir else Path(tempfile.mkdtemp(prefix="ho-graph-"))
    d = load()

    with network_locked() as egress:
        build_seed_corpus(cdir, gdir)
        findings = graph_technical_findings(
            PROJECT_ID, [HO_URS, HO_FS, HO_FSOK], extraction_version=_EXT_VER,
            run_id="held-out-dry", canon_dir=cdir, graph_dir=gdir)

    pos = [c for c in d["cases"] if c["expected"].get("finding")]
    neg = [c for c in d["cases"] if not c["expected"].get("finding")]
    tp = [c["case_id"] for c in pos if _match(c, findings)]
    fn = [c["case_id"] for c in pos if not _match(c, findings)]
    # FP: findings emitidos sobre un documento que un caso NEGATIVO declara limpio.
    neg_docs = {c["match"]["document"] for c in neg}
    fp = [f.finding_id for f in findings if f.document in neg_docs]

    recall = round(len(tp) / len(pos), 4) if pos else None
    by_tag = {}
    for c in pos:
        by_tag.setdefault(c["provenance_tag"], {"n": 0, "tp": 0})
        by_tag[c["provenance_tag"]]["n"] += 1
        if c["case_id"] in tp:
            by_tag[c["provenance_tag"]]["tp"] += 1

    usable = is_usable_as_gate()
    rr = me.wilson_interval(len(tp), len(pos)) if (usable and pos) else "NOT_A_GATE"
    envelope = me.wrap(
        "HELD_OUT_TECHNICAL_RECALL", recall,
        suite_version=f"{d.get('artifact')}@{d.get('version')} ({d.get('status')})",
        size={"positives": len(pos), "negatives": len(neg)},
        definition=("TP = un finding con (finding_class, subtype, document) esperados y page dentro "
                    "de page_band±tol. Match ESTRUCTURAL: el ground truth no aporta texto."),
        reportable_range=rr,
        contamination_statement=(
            "Autor del held-out != autor de technical_completeness_rules.yaml (excluded_authors + "
            f"signed_by={_rules_author()!r}). Match estructural -> sin acoplamiento de frase. "
            f"status={d.get('status')} -> {'GATE' if usable else 'INDICATIVO, NO ES GATE'}. "
            "Semilla SINTÉTICA -- se reemplaza por casos reales al firmar."),
        by_provenance_tag=by_tag,
    )
    return {
        "usable_as_gate": usable,
        "TP": tp, "FN": fn, "FP_count": len(fp),
        "recall_indicative": recall,
        "n_positives": len(pos), "n_negatives": len(neg),
        "by_provenance_tag": by_tag,
        "metric_envelope": envelope,
        "local_only": egress.local_only,
        "document_egress_bytes": egress.document_egress_bytes,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run_held_out_dry(), indent=1, ensure_ascii=False, default=str))
