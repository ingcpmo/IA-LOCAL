"""WP-E.4 -- Adjudicación humana sobre el corpus real.

docs_plan/PLAN_HARDENING_ANALIZADOR_GMP_LOCAL_V2.md WP-E.4 ;
docs_plan/WP_E_INDEPENDENCIA_MEDICION_20260828.md.

DOS conjuntos humanos, metodológicamente distintos:

  (A) EMITTED_FINDINGS_REVIEW  -- `sample_for_adjudication()` muestrea findings EMITIDOS
      de una corrida `v2_runtime`. QA los etiqueta TP / FP / COVERAGE_LIMITED.
      Permite medir DIRECTAMENTE: TP, FP, PRECISION/PPV, proporción COVERAGE_LIMITED.
      **NO permite medir recall / FN / TN** -- una muestra de findings emitidos no
      contiene información sobre desviaciones que deberían haberse detectado y NO se
      emitieron. `score_emitted_review()` es FAIL-CLOSED ante etiquetas FN/TN y
      declara `RECALL_REPORTABLE = UNKNOWN`.

  (B) DETECTION_OPPORTUNITIES  -- `real_corpus_opportunities.yaml` (DRAFT_UNSIGNED).
      QA revisa el CORPUS (no los findings) y enumera las desviaciones / oportunidades
      de detección que DEBERÍAN existir, con su base (cláusula / juicio del revisor).
      `score_recall()` cruza esas oportunidades contra los findings emitidos -> TP/FN
      -> recall. FAIL-CLOSED (recall UNKNOWN) mientras el yaml esté DRAFT_UNSIGNED o vacío.
      TN/especificidad SOLO si hay `negative_units` explícitas y firmadas.

Sin LLM, sin red. Ninguna etiqueta la pone la máquina.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml as _yaml

from factory.regulatory.validation_v2 import metric_envelope as me

# --- conjunto A: revisión de findings emitidos ---
EMITTED_REVIEW_LABELS = ("TP", "FP", "COVERAGE_LIMITED", "PENDING")
_INVALID_FOR_EMITTED = ("FN", "TN")          # no derivables de una muestra de findings emitidos
_SHEET_ARTIFACT = "real_corpus_adjudication"
SAMPLE_TYPE_EMITTED = "EMITTED_FINDINGS_REVIEW"
SAMPLE_TYPE_OPPORTUNITIES = "DETECTION_OPPORTUNITIES"

_OPPORTUNITIES_ARTIFACT = (Path(__file__).resolve().parent.parent
                           / "requirement_catalog" / "real_corpus_opportunities.yaml")


class AdjudicationMethodError(RuntimeError):
    """Se intentó derivar recall/FN/TN de una muestra que no lo permite."""


def _det_case_id(finding_id: str) -> str:
    return "ADJ-" + hashlib.sha256(finding_id.encode()).hexdigest()[:10]


def _load_run(run_dir: Path) -> tuple[list[dict], dict]:
    findings: list[dict] = []
    for name in ("regulatory_findings.json", "functional_findings.json", "technical_findings.json"):
        p = run_dir / name
        if p.is_file():
            findings += json.loads(p.read_text(encoding="utf-8"))
    cov = {}
    cp = run_dir / "analysis_coverage.json"
    if cp.is_file():
        cov = json.loads(cp.read_text(encoding="utf-8"))
    return findings, cov


# ===========================================================================
# (A) EMITTED_FINDINGS_REVIEW -- precision / PPV
# ===========================================================================
def sample_for_adjudication(run_dir: str | Path, *, n: int = 40, seed: int = 0) -> dict:
    """Muestra DETERMINISTA y estratificada (por class+subtype) de findings EMITIDOS.
    Prioriza `would_degrade` (WP-B). Todos los casos nacen `label: PENDING`.

    Esta hoja es de tipo EMITTED_FINDINGS_REVIEW: mide precision/PPV, NO recall."""
    run_dir = Path(run_dir)
    findings, cov = _load_run(run_dir)
    if not findings:
        raise FileNotFoundError(f"sin *_findings.json en {run_dir}")

    would_degrade = {c["finding_id"] for c in cov.get("coverage_dependencies", [])
                     if c.get("would_degrade")}
    cov_by_fid = {c["finding_id"]: c for c in cov.get("coverage_dependencies", [])}

    def _key(f):
        h = hashlib.sha256(f"{seed}:{f['finding_id']}".encode()).hexdigest()
        return (0 if f["finding_id"] in would_degrade else 1, h)

    strata: dict[tuple, list] = {}
    for f in findings:
        strata.setdefault((f["class"], f["subtype"]), []).append(f)
    for k in strata:
        strata[k].sort(key=_key)

    picked: list[dict] = []
    keys = sorted(strata)
    per = max(1, n // max(1, len(keys)))
    for k in keys:
        picked += strata[k][:per]
    if len(picked) < n:
        rest = [f for k in keys for f in strata[k][per:]]
        rest.sort(key=_key)
        picked += rest[: n - len(picked)]
    picked = picked[:n]

    cases = []
    for f in picked:
        cd = cov_by_fid.get(f["finding_id"], {})
        cases.append({
            "case_id": _det_case_id(f["finding_id"]),
            "finding_id": f["finding_id"],
            "finding_class": f["class"],
            "subtype": f["subtype"],
            "document": f["document"],
            "page": f["page"],
            "evidence_basis": f.get("evidence_basis"),
            "would_degrade": f["finding_id"] in would_degrade,
            "coverage_status": cd.get("coverage_status"),
            "anchored_quote": (f.get("source_text") or "")[:240],
            "label": "PENDING",     # <- QA humano rellena: TP | FP | COVERAGE_LIMITED
            "adjudicator_note": "",
        })

    sheet = {
        "artifact": _SHEET_ARTIFACT,
        "version": "0.2-draft",
        "status": "DRAFT_UNSIGNED",
        "sample_type": SAMPLE_TYPE_EMITTED,
        "adjudicator": None,
        "adjudicated_at": None,
        "source_run_dir": str(run_dir),
        "source_input_config_fingerprint": None,
        "sample_size": len(cases),
        "seed": seed,
        "label_options": [x for x in EMITTED_REVIEW_LABELS if x != "PENDING"],
        "methodology": (
            "Muestra de FINDINGS EMITIDOS. Mide DIRECTAMENTE: TP, FP, PRECISION/PPV, "
            "proporción COVERAGE_LIMITED. NO mide recall / FN / TN -- eso requiere el "
            "conjunto DETECTION_OPPORTUNITIES (real_corpus_opportunities.yaml), revisado "
            "por QA sobre el corpus, NO sobre los findings. Etiquetas FN/TN aquí = error de "
            "método -> score_emitted_review() falla cerrado."),
        "notes": ("COVERAGE_LIMITED = el finding no es sólidamente evaluable en este corpus "
                  "(p.ej. depende de la mitad de prueba vacía / RW-0009 NOT_ANALYZABLE). "
                  "Se excluye del numerador y denominador de precision."),
        "cases": cases,
    }
    ap = run_dir / "audit_summary" / "audit_metadata.json"
    if ap.is_file():
        sheet["source_input_config_fingerprint"] = json.loads(
            ap.read_text()).get("input_config_fingerprint")
    return sheet


def write_sheet(sheet: dict, path: str | Path) -> Path:
    path = Path(path)
    path.write_text(_yaml.safe_dump(sheet, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def load_sheet(path: str | Path) -> dict:
    return _yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def score_emitted_review(sheet: dict | str | Path) -> dict:
    """Puntúa una hoja EMITTED_FINDINGS_REVIEW. FAIL-CLOSED ante FN/TN.
    Devuelve PRECISION_REPORTABLE (intervalo o UNKNOWN) y RECALL_REPORTABLE = UNKNOWN."""
    if isinstance(sheet, (str, Path)):
        sheet = load_sheet(sheet)
    if sheet.get("sample_type") not in (SAMPLE_TYPE_EMITTED, None):
        raise AdjudicationMethodError(
            f"score_emitted_review no aplica a sample_type={sheet.get('sample_type')!r}")
    cases = sheet.get("cases", [])
    bad = sorted({c.get("label") for c in cases if c.get("label") in _INVALID_FOR_EMITTED})
    if bad:
        raise AdjudicationMethodError(
            f"etiquetas {bad} en una muestra de FINDINGS EMITIDOS: FN/TN no son derivables "
            f"de findings emitidos. Usa el conjunto DETECTION_OPPORTUNITIES para recall/FN, "
            f"y una unidad negativa explícita y adjudicada para TN.")

    pending = [c for c in cases if c.get("label", "PENDING") == "PENDING"]
    counts = {k: 0 for k in ("TP", "FP", "COVERAGE_LIMITED")}
    for c in cases:
        if c.get("label") in counts:
            counts[c["label"]] += 1

    labeled = len(cases) - len(pending)
    evaluable = counts["TP"] + counts["FP"]          # COVERAGE_LIMITED fuera del cálculo
    if pending:
        precision = None
        precision_rr = "UNKNOWN"
        note = f"adjudicación pendiente: {len(pending)}/{len(cases)} casos PENDING"
    elif evaluable == 0:
        precision = None
        precision_rr = "UNKNOWN"
        note = "sin casos evaluables (todo COVERAGE_LIMITED)"
    else:
        precision = round(counts["TP"] / evaluable, 4)
        precision_rr = me.wilson_interval(counts["TP"], evaluable)
        note = (f"PRECISION = TP/(TP+FP) sobre {evaluable} casos evaluables; "
                f"{counts['COVERAGE_LIMITED']} COVERAGE_LIMITED excluidos.")

    prop_cov_lim = round(counts["COVERAGE_LIMITED"] / labeled, 4) if labeled else None

    env_precision = me.wrap(
        "REAL_CORPUS_PRECISION_ADJUDICATED", precision,
        suite_version=f"{sheet.get('artifact')}@{sheet.get('version')} ({sheet.get('status')})",
        size={"sample": len(cases), "labeled": labeled, "evaluable": evaluable,
              "coverage_limited": counts["COVERAGE_LIMITED"]},
        definition="PRECISION/PPV = TP/(TP+FP) sobre casos etiquetados no-COVERAGE_LIMITED. "
                   "Muestra de FINDINGS EMITIDOS -> mide precision, NO recall.",
        reportable_range=precision_rr,
        contamination_statement=(
            f"Muestra determinista (seed={sheet.get('seed')}) de {sheet.get('source_run_dir')}; "
            f"fingerprint {sheet.get('source_input_config_fingerprint')}. Etiquetado HUMANO "
            f"({sheet.get('adjudicator')}). {'PENDIENTE.' if pending else note}"),
        proportion_coverage_limited=prop_cov_lim, label_counts=counts)

    env_recall = me.wrap(
        "REAL_CORPUS_RECALL_ADJUDICATED", None,
        suite_version=f"{sheet.get('artifact')}@{sheet.get('version')}",
        size={"opportunities": 0},
        definition="recall = TP/(TP+FN). NO calculable desde una muestra de findings emitidos.",
        reportable_range="UNKNOWN",
        contamination_statement=(
            "RECALL_REPORTABLE = UNKNOWN: requiere el conjunto humano independiente de "
            "oportunidades de detección (real_corpus_opportunities.yaml), revisado por QA "
            "sobre el corpus. Una muestra de findings emitidos no contiene FN."))

    return {
        "sample_type": SAMPLE_TYPE_EMITTED,
        "labeled": not pending,
        "counts": counts,
        "precision": precision,
        "PRECISION_REPORTABLE": precision_rr,
        "RECALL_REPORTABLE": "UNKNOWN",
        "proportion_coverage_limited": prop_cov_lim,
        "metric_envelope_precision": env_precision,
        "metric_envelope_recall": env_recall,
    }


# Compat: `score_sheet` delega en `score_emitted_review` (misma semántica corregida).
def score_sheet(sheet: dict | str | Path) -> dict:
    return score_emitted_review(sheet)


# ===========================================================================
# (B) DETECTION_OPPORTUNITIES -- recall / FN (y TN solo si hay unidad negativa)
# ===========================================================================
def load_opportunities(path: Path | None = None) -> dict:
    p = Path(path or _OPPORTUNITIES_ARTIFACT)
    if not p.is_file():
        return {"status": "ABSENT", "opportunities": [], "negative_units": []}
    d = _yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    d.setdefault("opportunities", [])
    d.setdefault("negative_units", [])
    return d


def _opps_signed(d: dict) -> bool:
    return str(d.get("status", "")).upper() == "SIGNED" and bool(d.get("adjudicator"))


def score_recall(run_dir: str | Path, opportunities_path: Path | None = None) -> dict:
    """Cruza el conjunto humano de oportunidades de detección contra los findings
    EMITIDOS de `run_dir`. FAIL-CLOSED: recall UNKNOWN mientras el yaml no esté
    SIGNED o esté vacío. TN/especificidad solo si hay `negative_units` firmadas."""
    d = load_opportunities(opportunities_path)
    findings, _ = _load_run(Path(run_dir))
    emitted = {(f["class"], f["subtype"], f["document"]) for f in findings}
    emitted_pages = {}
    for f in findings:
        emitted_pages.setdefault((f["class"], f["subtype"], f["document"]), []).append(f.get("page"))

    signed = _opps_signed(d)
    opps = d.get("opportunities", [])
    tp = fn = 0
    unmatched = []
    if signed and opps:
        for o in opps:
            key = (o.get("expected_class"), o.get("expected_subtype"), o.get("document"))
            pages = emitted_pages.get(key, [])
            band = o.get("page_band") or [1, 10 ** 9]
            hit = key in emitted and any(band[0] - 3 <= (p or 0) <= band[1] + 3 for p in pages)
            if hit:
                tp += 1
            else:
                fn += 1
                unmatched.append(o.get("opportunity_id"))
        recall = round(tp / (tp + fn), 4) if (tp + fn) else None
        recall_rr = me.wilson_interval(tp, tp + fn) if (tp + fn) else "UNKNOWN"
    else:
        recall = None
        recall_rr = "UNKNOWN"

    neg = d.get("negative_units", [])
    tn = specificity = None
    if signed and neg:
        clean = sum(1 for u in neg
                    if (u.get("expected_class"), u.get("expected_subtype"), u.get("document"))
                    not in emitted)
        tn = clean
        specificity = round(clean / len(neg), 4) if neg else None

    env = me.wrap(
        "REAL_CORPUS_RECALL_ADJUDICATED", recall,
        suite_version=f"real_corpus_opportunities@{d.get('version', 'n/a')} ({d.get('status', 'ABSENT')})",
        size={"opportunities": len(opps), "negative_units": len(neg)},
        definition="recall = TP/(TP+FN) sobre oportunidades de detección enumeradas por QA "
                   "sobre el CORPUS (no sobre los findings emitidos).",
        reportable_range=recall_rr if signed and opps else "UNKNOWN",
        contamination_statement=(
            f"Conjunto de oportunidades status={d.get('status', 'ABSENT')}; "
            f"adjudicador={d.get('adjudicator')}. "
            + ("" if (signed and opps) else
               "FAIL-CLOSED: RECALL_REPORTABLE = UNKNOWN hasta que QA pueble y firme "
               "real_corpus_opportunities.yaml.")),
        fn_opportunity_ids=unmatched)

    return {
        "opportunities_status": d.get("status", "ABSENT"),
        "usable": signed and bool(opps),
        "TP": tp, "FN": fn,
        "recall": recall,
        "RECALL_REPORTABLE": recall_rr if (signed and opps) else "UNKNOWN",
        "TN": tn, "specificity": specificity,   # None salvo negative_units firmadas
        "metric_envelope": env,
    }
