"""WP-B -- Contrato de adecuación de EXTRACCIÓN (frontera de ingesta).

docs_plan/PLAN_HARDENING_ANALIZADOR_GMP_LOCAL_V2.md §4.1 ; docs_plan/ADR_HARDENING_V2.md.

Separa `EXTRACTION_COMPLETE` (el proceso terminó) de `ANALYZABLE` (el resultado
representa al documento). El verdict es un ARTEFACTO DE LIMITACIÓN DEL ANÁLISIS
(`analysis_coverage.json`), NO un Finding GMP: no entra en `all_findings`, no recibe
`risk`, no genera `RemediationDirective`.

Señales TÉCNICAS de adecuación de extracción (NO requisitos GMP): sections_total,
toc_anchored, claims_per_page, tables_total, n_paginas, tipo. Umbrales en
`requirement_catalog/extraction_adequacy_thresholds.yaml` (`status: DRAFT_UNSIGNED`,
HEURÍSTICAS a validar).

Modo OBSERVE (WP-B ahora): clasifica y etiqueta. 0 supresiones, 0 Findings GMP nuevos.
Modo ENFORCE (decisión posterior de Capa 9): usa `assert_signed()` -- fail-closed.

Único criterio DECISIVO = piso absoluto independiente del rol. Medianas/bandas por rol
son OBSERVACIONALES mientras el corpus no dé muestra suficiente (6 docs, ~1 por rol).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml as _yaml

from factory.regulatory.canonical.persistence import STORE_DIR as _CANON_DIR, CanonicalStore

_THRESHOLDS_PATH = (Path(__file__).resolve().parent.parent
                    / "requirement_catalog" / "extraction_adequacy_thresholds.yaml")

VERDICTS = ("ANALYZABLE", "DEGRADED", "NOT_ANALYZABLE")


class AdequacyThresholdsError(RuntimeError):
    pass


class AdequacyThresholdsNotSignedError(AdequacyThresholdsError):
    """Las heurísticas siguen DRAFT_UNSIGNED -- no usables como gate ENFORCE."""


@lru_cache(maxsize=2)
def _load_raw(path_str: str) -> dict:
    path = Path(path_str)
    if not path.is_file():
        raise FileNotFoundError(path)
    data = _yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "absolute_floor" not in data:
        raise AdequacyThresholdsError(f"{path.name}: sin bloque 'absolute_floor'")
    return data


def load_thresholds(path: Path | None = None) -> dict:
    return _load_raw(str(path or _THRESHOLDS_PATH))


def status(path: Path | None = None) -> str:
    return str(load_thresholds(path).get("status", "")).upper()


def is_signed(path: Path | None = None) -> bool:
    return status(path) == "SIGNED"


def assert_signed(path: Path | None = None) -> None:
    """Fail-closed para la ruta de gate ENFORCE. En OBSERVE NO se llama."""
    if not is_signed(path):
        raise AdequacyThresholdsNotSignedError(
            f"extraction_adequacy_thresholds en estado {status(path) or 'DRAFT_UNSIGNED'!r} "
            f"-- no usable como gate ENFORCE (requiere status: SIGNED de Capa 9).")


# ── señales del store ────────────────────────────────────────────────────
def document_signals(document_id: str, canon_dir: Path | None = None) -> dict:
    cdir = Path(canon_dir) if canon_dir is not None else _CANON_DIR
    with CanonicalStore(document_id, store_dir=cdir) as cs:
        counts = cs.counts()
        toc = bool(cs.get_meta("toc_anchored", False))
        docs = cs.all("document")
    doc = docs[0] if docs else {}
    n_pag = int(doc.get("n_paginas") or 0)
    claims = int(counts.get("claim", 0))
    return {
        "document_id": document_id,
        "tipo": doc.get("tipo"),
        "n_paginas": n_pag,
        "sections_total": int(counts.get("section", 0)),
        "claims_total": claims,
        "tables_total": int(counts.get("table_obj", 0)),
        "toc_anchored": toc,
        "claims_per_page": round(claims / n_pag, 3) if n_pag > 0 else 0.0,
    }


def classify(signals: dict, thresholds: dict | None = None) -> dict:
    """Verdict + regla que lo decidió + observaciones (no decisivas)."""
    t = thresholds or load_thresholds()
    af = t["absolute_floor"]
    sr = t.get("structure_recovery", {})
    secs = int(signals.get("sections_total", 0))
    toc = bool(signals.get("toc_anchored", False))
    n_pag = int(signals.get("n_paginas", 0))
    claims = int(signals.get("claims_total", 0))
    cpp = float(signals.get("claims_per_page", 0.0))

    no_structure = (af.get("require_zero_sections", True) and secs == 0
                    and af.get("require_no_toc_anchor", True) and not toc)
    thin = (n_pag < int(af.get("thin_if_pages_below", 5))
            or claims < int(af.get("thin_if_claims_below", 150)))

    # --- DECISIVO: sin estructura recuperada Y documento delgado (role-independiente) ---
    if no_structure and thin:
        verdict, rule = "NOT_ANALYZABLE", "absolute_floor:no_structure_and_thin"
    # --- DEGRADED: recuperación de estructura incompleta (role-independiente) ---
    elif no_structure and sr.get("degraded_if_no_structure_recovered", True):
        verdict, rule = "DEGRADED", "structure_recovery:no_structure_recovered"
    elif not toc and secs > 0 and sr.get("degraded_if_no_toc_anchor", True):
        verdict, rule = "DEGRADED", "structure_recovery:no_toc_anchor"
    else:
        verdict, rule = "ANALYZABLE", "none"

    return {
        "verdict": verdict,
        "decisive_rule": rule,
        "signals": signals,
        "observational": {
            "note": ("relativo por rol NO decide -- muestra insuficiente "
                     "(ver SAMPLE_SIZE_LIMITATIONS)"),
            "claims_per_page": cpp,
        },
        "thresholds_signed": is_signed(),
    }


def assess_corpus(document_ids: list[str], canon_dir: Path | None = None,
                  thresholds: dict | None = None) -> dict:
    t = thresholds or load_thresholds()
    out: dict = {}
    for did in document_ids:
        try:
            sig = document_signals(did, canon_dir)
            out[did] = classify(sig, t)
        except Exception as e:  # noqa: BLE001 -- un doc sin store no aborta el análisis
            out[did] = {"verdict": "NOT_ANALYZABLE", "decisive_rule": "store_unreadable",
                        "signals": {"document_id": did, "error": f"{type(e).__name__}: {e}"},
                        "observational": {}, "thresholds_signed": is_signed()}
    # observacional: mediana por rol + n (NO decide)
    by_role: dict[str, list[float]] = {}
    for r in out.values():
        tp = (r.get("signals") or {}).get("tipo")
        if tp:
            by_role.setdefault(tp, []).append(float((r.get("signals") or {}).get("claims_per_page", 0.0)))
    role_stats = {}
    min_n = int((t.get("observational") or {}).get("per_role_sample_min_for_use", 5))
    for role, vals in by_role.items():
        vals_sorted = sorted(vals)
        n = len(vals_sorted)
        median = vals_sorted[n // 2] if n else 0.0
        role_stats[role] = {"n": n, "claims_per_page_median": round(median, 3),
                            "usable_as_criterion": n >= min_n}
    return {
        "mode": None,  # lo fija el runtime (OBSERVE / ENFORCE)
        "thresholds_artifact": _THRESHOLDS_PATH.name,
        "thresholds_signed": is_signed(),
        "by_document": out,
        "role_stats_observational": role_stats,
        "verdicts": {d: r["verdict"] for d, r in out.items()},
    }


def coverage_statement(assessment: dict) -> str:
    v = assessment.get("verdicts", {})
    not_ok = [d for d, x in v.items() if x != "ANALYZABLE"]
    if not not_ok:
        return ("Todos los documentos del análisis pasaron el contrato de adecuación de extracción "
                "(ANALYZABLE). Ninguna conclusión está limitada por la ingesta.")
    parts = "; ".join(f"{d}={v[d]}" for d in not_ok)
    return (f"LIMITACIÓN DE COBERTURA (extracción): {parts}. Las conclusiones derivadas de AUSENCIA "
            f"(evidence_basis=ABSENCE_DEPENDENT) cuya región dependa de estos documentos NO son "
            f"sólidas -- ver coverage_dependencies[*].would_degrade. Modo OBSERVE: nada suprimido. "
            f"Umbrales = HEURÍSTICAS DRAFT_UNSIGNED, no requisitos GMP.")
