"""WP-E.4 -- Muestra adjudicada del corpus real -> rango reportable de cada gate.

docs_plan/PLAN_HARDENING_ANALIZADOR_GMP_LOCAL_V2.md WP-E.4:
"subconjunto de findings reales etiquetado por un humano, que produzca por primera
vez TP/FN/FP sobre datos reales y, con ello, el rango reportable de cada gate."

`sample_for_adjudication()` toma una muestra DETERMINISTA y estratificada de una
corrida `v2_runtime` persistida y escribe una hoja de etiquetado (`label: PENDING`).
Un adjudicador humano (QA/Validation, NO la máquina) rellena las etiquetas.
`score_sheet()` calcula TP/FN/FP + rango reportable (Wilson) + declaración de
contaminación, envuelto en `metric_envelope`.

Hasta que haya etiquetas -> `REPORTABLE_RANGE = UNKNOWN`. Sin LLM, sin red.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml as _yaml

from factory.regulatory.validation_v2 import metric_envelope as me

LABELS = ("TP", "FP", "FN", "TN", "COVERAGE_LIMITED", "PENDING")
_SHEET_ARTIFACT = "real_corpus_adjudication"


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


def sample_for_adjudication(run_dir: str | Path, *, n: int = 40, seed: int = 0) -> dict:
    """Muestra estratificada (por class+subtype) y DETERMINISTA. Prioriza los
    findings marcados `would_degrade` (WP-B) porque son los que más informan el
    rango reportable."""
    run_dir = Path(run_dir)
    findings, cov = _load_run(run_dir)
    if not findings:
        raise FileNotFoundError(f"sin *_findings.json en {run_dir}")

    would_degrade = {c["finding_id"] for c in cov.get("coverage_dependencies", [])
                     if c.get("would_degrade")}
    cov_by_fid = {c["finding_id"]: c for c in cov.get("coverage_dependencies", [])}

    # orden determinista: (no-would_degrade primero? no -> would_degrade primero),
    # luego por hash estable con la semilla.
    def _key(f):
        h = hashlib.sha256(f"{seed}:{f['finding_id']}".encode()).hexdigest()
        return (0 if f["finding_id"] in would_degrade else 1, h)

    strata: dict[tuple, list] = {}
    for f in findings:
        strata.setdefault((f["class"], f["subtype"]), []).append(f)
    for k in strata:
        strata[k].sort(key=_key)

    # reparto proporcional con al menos 1 por estrato no vacío
    picked: list[dict] = []
    keys = sorted(strata)
    per = max(1, n // max(1, len(keys)))
    for k in keys:
        picked += strata[k][:per]
    # completar hasta n con el resto, orden determinista global
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
            "label": "PENDING",     # <- el adjudicador humano rellena: TP|FP|FN|TN|COVERAGE_LIMITED
            "adjudicator_note": "",
        })

    sheet = {
        "artifact": _SHEET_ARTIFACT,
        "version": "0.1-draft",
        "status": "DRAFT_UNSIGNED",
        "adjudicator": None,                    # QA/Validation humano; NO la máquina
        "adjudicated_at": None,
        "source_run_dir": str(run_dir),
        "source_input_config_fingerprint": None,
        "sample_size": len(cases),
        "seed": seed,
        "label_options": [x for x in LABELS if x != "PENDING"],
        "notes": ("COVERAGE_LIMITED = el finding no es sólidamente evaluable en este corpus "
                  "(p.ej. depende de la mitad de prueba vacía). Se excluye del numerador y "
                  "denominador de recall/precisión y se reporta aparte."),
        "cases": cases,
    }
    # anclar el fingerprint de la corrida si está
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


def score_sheet(sheet: dict | str | Path) -> dict:
    if isinstance(sheet, (str, Path)):
        sheet = load_sheet(sheet)
    cases = sheet.get("cases", [])
    pending = [c for c in cases if c.get("label", "PENDING") == "PENDING"]
    counts = {k: 0 for k in LABELS if k != "PENDING"}
    for c in cases:
        lbl = c.get("label", "PENDING")
        if lbl in counts:
            counts[lbl] += 1

    if pending:
        rr = "UNKNOWN"
        recall = precision = None
        note = f"adjudicación pendiente: {len(pending)}/{len(cases)} casos con label PENDING"
    else:
        tp, fp, fn = counts["TP"], counts["FP"], counts["FN"]
        denom_recall = tp + fn
        denom_prec = tp + fp
        recall = round(tp / denom_recall, 4) if denom_recall else None
        precision = round(tp / denom_prec, 4) if denom_prec else None
        rr = me.wilson_interval(tp, denom_recall) if denom_recall else "UNKNOWN"
        note = (f"{counts['COVERAGE_LIMITED']} casos COVERAGE_LIMITED excluidos del cálculo "
                f"(no sólidamente evaluables en este corpus).")

    envelope = me.wrap(
        "REAL_CORPUS_RECALL_ADJUDICATED", recall,
        suite_version=f"{sheet.get('artifact')}@{sheet.get('version')} ({sheet.get('status')})",
        size={"sample": len(cases), "labeled": len(cases) - len(pending),
              "coverage_limited": counts["COVERAGE_LIMITED"]},
        definition=("TP/FP/FN según etiqueta humana. COVERAGE_LIMITED excluido de numerador y "
                    "denominador. recall = TP/(TP+FN) sobre casos etiquetados y evaluables."),
        reportable_range=rr,
        contamination_statement=(
            f"Muestra determinista (seed={sheet.get('seed')}) de {sheet.get('source_run_dir')}; "
            f"fingerprint {sheet.get('source_input_config_fingerprint')}. Etiquetado por adjudicador "
            f"humano ({sheet.get('adjudicator')}), NO por la máquina. "
            f"{'PENDIENTE -- rango no publicable.' if pending else note}"),
        label_counts=counts, precision=precision,
    )
    return {"labeled": not pending, "counts": counts, "recall": recall,
            "precision": precision, "reportable_range": rr, "metric_envelope": envelope}
