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
      `score_recall()` PROPONE candidatos estructurales por (class, subtype, document,
      page_band) pero el TP de recall depende de la CONFIRMACIÓN HUMANA de la
      correspondencia (`matched_finding_id` + `match_confirmed_by` + `match_note`),
      nunca de la inferencia estructural. Matching UNO-A-UNO. FAIL-CLOSED (recall
      UNKNOWN) mientras el yaml esté DRAFT_UNSIGNED o vacío.
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
        prov = f.get("provenance") or {}
        risk = f.get("risk") or {}
        cases.append({
            "case_id": _det_case_id(f["finding_id"]),
            # --- H-3: direccionamiento INEQUÍVOCO (finding_id colisiona, finding_record_id no) ---
            "finding_record_id": f.get("finding_record_id"),
            "finding_id": f["finding_id"],
            "finding_class": f["class"],
            "subtype": f["subtype"],
            # --- criterio / sub-criterio regulatorio ---
            "criterion": f.get("requirement"),
            "subcriterion_ref": prov.get("subcriterion_ref"),
            "regulatory_basis": f.get("regulatory_basis"),
            "technical_basis": f.get("technical_basis"),
            # --- ancla de evidencia REPRODUCIBLE (documento / sección / página / hash) ---
            "document": f["document"],
            "section": f.get("section"),
            "page": f["page"],
            "source_hash": f.get("source_hash"),
            "anchored_quote": f.get("source_text") or "",          # texto exacto, SIN truncar
            "evidence_ids": (f.get("evidence") or {}).get("evidence_ids", []),
            # --- estado de cobertura / epistemología ---
            "evidence_basis": f.get("evidence_basis"),
            "would_degrade": f["finding_id"] in would_degrade,
            "coverage_status": cd.get("coverage_status"),
            "coverage_required_capabilities": cd.get("required_capabilities"),
            # --- referencia al grafo (H-4), cuando aplica ---
            "graph_path": prov.get("graph_path"),
            # --- hallazgo de máquina PROPUESTO (para que el humano lo juzgue, no lo adopte) ---
            "proposed_machine_finding": {
                "severity": f.get("severity"),
                "risk_band": risk.get("band"),
                "risk_band_pre_enforce": risk.get("band_pre_enforce"),
                "risk_mode": risk.get("mode"),
                "machine_state": f.get("machine_state"),
                "confidence": f.get("confidence"),
                "rationale": f.get("rationale"),
            },
            # --- procedencia held-out (la asigna QA: REG | DOM | ADV) ---
            "held_out_provenance_tag": None,   # <- QA
            # --- adjudicación humana (vacío = PENDING; la IA NO rellena) ---
            "label": "PENDING",     # <- QA humano: TP | FP | COVERAGE_LIMITED
            "adjudicator_note": "",
            "human_evidence_anchor": "",   # <- QA: cita/página exacta que sustenta su decisión
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
# Campos obligatorios que QA debe completar en cada oportunidad de detección.
OPPORTUNITY_REQUIRED_FIELDS = (
    "opportunity_id", "expected_class", "expected_subtype", "document", "page_band",
    "expected_topic_or_requirement", "human_evidence_anchor", "basis", "reviewer_note",
)
NEGATIVE_UNIT_REQUIRED_FIELDS = (
    "unit_id", "analysis_unit", "document", "scope", "expected_class", "expected_subtype",
    "human_evidence_anchor", "basis", "reviewer_note",
)
# Campos que QA rellena al ADJUDICAR la correspondencia oportunidad<->finding.
# El scorer PROPONE candidatos estructurales; el TP de recall depende de ESTA confirmación
# humana, nunca de la inferencia estructural automática.
MATCH_CONFIRMATION_FIELDS = ("matched_finding_id", "match_confirmed_by", "match_note")
# Política de coincidencia de página del PROTOCOLO -- explícita, no un ±N implícito.
# SOLO gobierna la PROPUESTA de candidatos estructurales, no el TP.
DEFAULT_PAGE_MATCH_POLICY = {"tolerance_pages": 0}   # 0 = la página debe caer DENTRO del page_band humano


def load_opportunities(path: Path | None = None) -> dict:
    p = Path(path or _OPPORTUNITIES_ARTIFACT)
    if not p.is_file():
        return {"status": "ABSENT", "opportunities": [], "negative_units": [],
                "page_match_policy": dict(DEFAULT_PAGE_MATCH_POLICY)}
    d = _yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    d.setdefault("opportunities", [])
    d.setdefault("negative_units", [])
    pmp = d.get("page_match_policy") or {}
    d["page_match_policy"] = {"tolerance_pages": int(pmp.get("tolerance_pages", 0))}
    return d


def _opps_signed(d: dict) -> bool:
    return str(d.get("status", "")).upper() == "SIGNED" and bool(d.get("adjudicator"))


def _validate_page_range(val: object, *, field: str, owner: str) -> None:
    """[int, int] con start <= end y ambos > 0. Fail-closed en cualquier otro caso."""
    if not (isinstance(val, (list, tuple)) and len(val) == 2):
        raise AdjudicationMethodError(f"{owner}: `{field}` debe ser [int, int]; se obtuvo {val!r}")
    a, b = val
    if isinstance(a, bool) or isinstance(b, bool) or not (isinstance(a, int) and isinstance(b, int)):
        raise AdjudicationMethodError(f"{owner}: `{field}` debe contener enteros; se obtuvo {val!r}")
    if a <= 0 or b <= 0:
        raise AdjudicationMethodError(f"{owner}: `{field}` debe ser > 0; se obtuvo {val!r}")
    if a > b:
        raise AdjudicationMethodError(f"{owner}: `{field}` requiere start <= end; se obtuvo {val!r}")


def _validate_opportunities(opps: list[dict]) -> None:
    for i, o in enumerate(opps):
        oid = o.get("opportunity_id")
        missing = [k for k in OPPORTUNITY_REQUIRED_FIELDS
                   if o.get(k) in (None, "", []) and k != "page_band"]
        if missing:
            raise AdjudicationMethodError(
                f"oportunidad #{i} ({oid}): faltan campos {missing}. "
                f"`human_evidence_anchor` y `basis` los completa QA, no la IA.")
        _validate_page_range(o.get("page_band"), field="page_band",
                             owner=f"oportunidad #{i} ({oid})")
        # los campos de confirmación humana del match van juntos: un match declarado sin
        # confirmante (o un confirmante sin finding) es inválido.
        mfid, by = o.get("matched_finding_id"), o.get("match_confirmed_by")
        if bool(mfid) ^ bool(by):
            raise AdjudicationMethodError(
                f"oportunidad #{i} ({oid}): `matched_finding_id` y `match_confirmed_by` "
                f"deben ir juntos -- el TP de recall exige confirmación humana explícita.")


def _validate_negative_units(neg: list[dict]) -> None:
    for i, u in enumerate(neg):
        uid = u.get("unit_id")
        missing = [k for k in NEGATIVE_UNIT_REQUIRED_FIELDS if u.get(k) in (None, "", [])]
        if missing:
            raise AdjudicationMethodError(
                f"negative_unit #{i} ({uid}): faltan campos {missing} "
                f"(unidad de análisis definida + anclaje humano obligatorios).")
        _validate_page_range(u.get("scope"), field="scope", owner=f"negative_unit #{i} ({uid})")


def _page_hit(page: object, band: list, tol: int) -> bool:
    try:
        p = int(page)
    except (TypeError, ValueError):
        return False
    return (band[0] - tol) <= p <= (band[1] + tol)


def score_recall(run_dir: str | Path, opportunities_path: Path | None = None) -> dict:
    """Cruza el conjunto humano de oportunidades de detección contra los findings
    EMITIDOS de `run_dir`.

    El TP de recall depende de la **confirmación humana** de la correspondencia
    (`matched_finding_id` + `match_confirmed_by` en cada oportunidad), NO de la
    inferencia estructural automática. El scorer solo PROPONE candidatos
    estructurales (`structural_candidate_finding_ids`) por
    (class, subtype, document, página dentro de [page_band ± tolerance_pages]).

    Matching UNO-A-UNO: un `finding_id` confirmado no puede acreditar dos
    oportunidades (fail-closed). FAIL-CLOSED además si: el yaml no está SIGNED,
    está vacío, falta un campo obligatorio, un `page_band` no es [int,int] válido,
    o un `matched_finding_id` confirmado no existe entre los findings emitidos.
    TN/especificidad SOLO con `negative_units` explícitas, firmadas y con unidad de
    análisis definida; en otro caso UNKNOWN."""
    d = load_opportunities(opportunities_path)
    findings, _ = _load_run(Path(run_dir))
    tol = int(d["page_match_policy"]["tolerance_pages"])

    # índice de findings emitidos por (class, subtype, document)
    by_key: dict[tuple, list[dict]] = {}
    for f in findings:
        by_key.setdefault((f["class"], f["subtype"], f["document"]), []).append(f)
    for k in by_key:
        by_key[k].sort(key=lambda x: (x.get("page") or 0, x.get("finding_id") or ""))
    emitted_ids = {f.get("finding_id") for f in findings}

    signed = _opps_signed(d)
    opps = list(d.get("opportunities", []))
    neg = list(d.get("negative_units", []))

    tp = fn = 0
    matched_pairs: list[dict] = []
    unmatched: list[str] = []
    per_opportunity: list[dict] = []
    recall = None
    recall_rr = "UNKNOWN"

    if signed and opps:
        _validate_opportunities(opps)
        opps.sort(key=lambda o: str(o.get("opportunity_id")))

        # --- paso 1: matches CONFIRMADOS POR QA (única fuente del TP de recall) ---
        confirmed_by_finding: dict[str, str] = {}
        for o in opps:
            oid = o.get("opportunity_id")
            mfid = o.get("matched_finding_id") or None
            if not mfid:
                continue
            if mfid not in emitted_ids:
                raise AdjudicationMethodError(
                    f"oportunidad {oid!r}: matched_finding_id={mfid!r} no existe entre los "
                    f"findings emitidos de la corrida -- QA no puede confirmar un match inexistente.")
            if mfid in confirmed_by_finding:
                raise AdjudicationMethodError(
                    f"matching NO uno-a-uno: el finding {mfid!r} fue confirmado por "
                    f"{confirmed_by_finding[mfid]!r} y {oid!r}. Un finding acredita a lo sumo UNA "
                    f"oportunidad.")
            confirmed_by_finding[mfid] = oid

        # --- paso 2: candidatos ESTRUCTURALES (propuesta) + resultado por confirmación ---
        for o in opps:
            oid = o.get("opportunity_id")
            key = (o.get("expected_class"), o.get("expected_subtype"), o.get("document"))
            band = list(o.get("page_band"))
            plausible = [f["finding_id"] for f in by_key.get(key, [])
                         if _page_hit(f.get("page"), band, tol)]
            cands = [fid for fid in plausible
                     if fid not in confirmed_by_finding or confirmed_by_finding[fid] == oid]
            mfid = o.get("matched_finding_id") or None
            by = o.get("match_confirmed_by") or None
            if mfid:
                tp += 1
                matched_pairs.append({
                    "opportunity_id": oid, "finding_id": mfid,
                    "match_confirmed_by": by, "match_note": o.get("match_note") or "",
                    "within_structural_candidates": mfid in plausible})
                outcome = "TP_CONFIRMED"
            else:
                fn += 1
                unmatched.append(oid)
                outcome = "FN"
            per_opportunity.append({
                "opportunity_id": oid, "outcome": outcome,
                "confirmed_finding_id": mfid, "match_confirmed_by": by,
                "structural_candidate_finding_ids": cands})
        recall = round(tp / (tp + fn), 4) if (tp + fn) else None
        recall_rr = me.wilson_interval(tp, tp + fn) if (tp + fn) else "UNKNOWN"

    tn = specificity = None
    specificity_rr = "UNKNOWN"
    if signed and neg:
        _validate_negative_units(neg)
        emitted_keys = {(f["class"], f["subtype"], f["document"]) for f in findings}
        emitted_pages = by_key
        clean = 0
        for u in neg:
            key = (u.get("expected_class"), u.get("expected_subtype"), u.get("document"))
            band = list(u.get("scope"))
            emitted_here = any(_page_hit(f.get("page"), band, tol)
                               for f in emitted_pages.get(key, []))
            if not emitted_here:
                clean += 1
        tn = clean
        specificity = round(clean / len(neg), 4) if neg else None
        specificity_rr = me.wilson_interval(clean, len(neg)) if neg else "UNKNOWN"

    env = me.wrap(
        "REAL_CORPUS_RECALL_ADJUDICATED", recall,
        suite_version=f"real_corpus_opportunities@{d.get('version', 'n/a')} ({d.get('status', 'ABSENT')})",
        size={"opportunities": len(opps), "negative_units": len(neg),
              "page_tolerance_pages": tol},
        definition=("recall = TP/(TP+FN) sobre oportunidades de detección enumeradas por QA sobre el "
                    "CORPUS. TP = oportunidad con correspondencia a un finding CONFIRMADA POR QA "
                    "(matched_finding_id + match_confirmed_by); la coincidencia estructural "
                    f"(class, subtype, document, page dentro de [page_band ± {tol}]) solo PROPONE "
                    "candidatos, no cuenta como TP. Matching UNO-A-UNO: un finding confirmado "
                    "acredita a lo sumo UNA oportunidad."),
        reportable_range=recall_rr if (signed and opps) else "UNKNOWN",
        contamination_statement=(
            f"Conjunto de oportunidades status={d.get('status', 'ABSENT')}; "
            f"adjudicador={d.get('adjudicator')}; page_match_policy.tolerance_pages={tol}. "
            f"TP por confirmación humana ({len(matched_pairs)} confirmados). "
            + ("" if (signed and opps) else
               "FAIL-CLOSED: RECALL_REPORTABLE = UNKNOWN hasta que QA pueble y firme "
               "real_corpus_opportunities.yaml con los campos obligatorios por oportunidad.")),
        matched_pairs=matched_pairs, fn_opportunity_ids=unmatched)

    return {
        "opportunities_status": d.get("status", "ABSENT"),
        "usable": bool(signed and opps),
        "page_match_policy": d["page_match_policy"],
        "human_match_confirmation_required": True,
        "TP": tp, "FN": fn, "recall": recall,
        "RECALL_REPORTABLE": recall_rr if (signed and opps) else "UNKNOWN",
        "matched_pairs": matched_pairs,
        "confirmed_match_count": len(matched_pairs),
        "per_opportunity": per_opportunity,
        "fn_opportunity_ids": unmatched,
        "one_to_one": len({m["finding_id"] for m in matched_pairs}) == len(matched_pairs),
        "TN": tn, "specificity": specificity,
        "SPECIFICITY_REPORTABLE": specificity_rr if (signed and neg) else "UNKNOWN",
        "metric_envelope": env,
    }
