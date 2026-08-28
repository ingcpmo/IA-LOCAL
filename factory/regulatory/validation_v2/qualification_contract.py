"""WP-F -- Contrato de cualificación: artefacto declarativo + checker RE-EJECUTABLE.

docs_plan/PLAN_HARDENING_ANALIZADOR_GMP_LOCAL_V2.md WP-F. Motiva D-5.
Precondición: WP-A (fingerprint) y WP-E (independencia de medición) cerrados.

El contrato (`requirement_catalog/qualification_contract.yaml`) liga, por caso:
  intended_use -> requirement -> test_objective -> acceptance_criterion ->
  FUENTE AUTORIZADA del valor esperado (cita, NUNCA literal) -> test_artifact ->
  actual_result -> evidence (ruta+sha) -> reviewer -> status.

El checker RE-EJECUTA las suites, LEE cada umbral de su fuente citada, calcula
`found/expected/delta`, y REPRODUCE el fingerprint declarado (WP-A). Si el
fingerprint no coincide, o un disparador de requalification cambió de SHA, o un
caso falla -> FAIL.

REGLAS DURAS (fail-closed en el loader / checker):
  * ningún caso lleva `expected_value` literal -> solo `expected_value_source`.
  * todo nace DRAFT.
  * el sistema NUNCA se auto-cualifica: `qualified_version` / "QUALIFIED" solo los
    fija un humano firmando el YAML.
  * el contrato NO declara cumplimiento -- solo estado de gates y contingencias.
  * `found/expected/delta` viven aquí (evidencia del caso), no en la taxonomía GMP.

Sin LLM, sin red (las suites corren bajo `network_locked`).
"""
from __future__ import annotations

import hashlib
import importlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml as _yaml

_REPO = Path(__file__).resolve().parents[3]
_CONTRACT = _REPO / "factory" / "regulatory" / "requirement_catalog" / "qualification_contract.yaml"

_OPS = {
    ">=": lambda a, e: a >= e,
    "<=": lambda a, e: a <= e,
    "==": lambda a, e: a == e,
    ">":  lambda a, e: a > e,
    "<":  lambda a, e: a < e,
    "is_true": lambda a, e: a is True,
    "is_false": lambda a, e: a is False,
}


class QualificationContractError(RuntimeError):
    pass


# ── carga + reglas duras ────────────────────────────────────────────────
def load_contract(path: Path | None = None) -> dict:
    p = Path(path or _CONTRACT)
    d = _yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(d, dict):
        raise QualificationContractError("contrato no es un mapping")
    if d.get("system_never_self_qualifies") is not True:
        raise QualificationContractError("contrato sin `system_never_self_qualifies: true`")
    if not d.get("requalification_triggers"):
        raise QualificationContractError("contrato sin `requalification_triggers`")
    for c in d.get("qualification_cases", []):
        if "expected_value" in c:
            raise QualificationContractError(
                f"{c.get('case_id')}: valor esperado LITERAL prohibido -- usa `expected_value_source`")
        for k in ("case_id", "expected_value_source", "test_artifact", "acceptance"):
            if k not in c:
                raise QualificationContractError(f"{c.get('case_id')}: falta `{k}`")
        if c.get("status", "DRAFT") not in ("DRAFT", "REVIEWED", "SIGNED"):
            raise QualificationContractError(f"{c['case_id']}: status inválido {c.get('status')!r}")
    return d


# ── resolución de la FUENTE AUTORIZADA del valor esperado ───────────────
def resolve_expected(src: dict) -> tuple[object, str]:
    """Devuelve (valor, cita_textual). Nunca un literal sin procedencia."""
    if not isinstance(src, dict):
        raise QualificationContractError(f"expected_value_source inválido: {src!r}")
    if src.get("zero") is True:
        auth = src.get("authority")
        if not auth:
            raise QualificationContractError("expected_value_source.zero sin `authority`")
        return 0, f"0 autorizado por: {auth}"
    if "assertion" in src:
        auth = src.get("authority")
        if not auth:
            raise QualificationContractError("expected_value_source.assertion sin `authority`")
        return None, f"aserción: {src['assertion']} [autoridad: {auth}]"
    if "const_module" in src and "const" in src:
        mod = importlib.import_module(src["const_module"])
        if not hasattr(mod, src["const"]):
            raise QualificationContractError(
                f"{src['const_module']}.{src['const']} no existe")
        return getattr(mod, src["const"]), f"{src['const_module']}.{src['const']}"
    if "yaml" in src and "key" in src:
        yp = _REPO / src["yaml"]
        data = _yaml.safe_load(yp.read_text(encoding="utf-8"))
        node = data
        for part in str(src["key"]).split("."):
            node = node[part]
        return node, f"{src['yaml']}::{src['key']}"
    raise QualificationContractError(f"expected_value_source no reconocido: {src!r}")


# ── SHA de artefactos + disparadores de requalification ─────────────────
def _sha(rel: str) -> str:
    fp = _REPO / rel
    return hashlib.sha256(fp.read_bytes()).hexdigest() if fp.is_file() else "ABSENT"


def requalification_status(contract: dict) -> dict:
    recorded = contract.get("qualified_against", {}).get("artifact_sha256", {}) or {}
    out = []
    any_changed = False
    for name, rel in contract["requalification_triggers"].items():
        cur = _sha(rel) if isinstance(rel, str) else "N/A"
        rec = recorded.get(name)
        changed = (rec is not None and rec != cur)
        any_changed = any_changed or changed
        out.append({"trigger": name, "artifact": rel, "recorded_sha256": rec,
                    "current_sha256": cur,
                    "changed": changed if rec is not None else "UNKNOWN (contrato DRAFT)"})
    return {"triggers": out, "any_changed_since_qualified": any_changed}


# ── ejecución de casos ─────────────────────────────────────────────────
def _callable(dotted: str):
    mod, fn = dotted.split(":")
    return getattr(importlib.import_module(mod), fn)


def _pluck(result: dict, key: str):
    """`key` admite: 'a.b', 'gate:NAME:value', 'gate:NAME:passed'."""
    if key.startswith("gate:"):
        _, name, field = key.split(":")
        for g in (result.get("gates") or []):
            if g.get("name") == name:
                return g.get(field)
        raise QualificationContractError(f"gate {name!r} no está en el resultado")
    node = result
    for part in key.split("."):
        node = node[part]
    return node


# adaptadores para runners que necesitan args -- viven AQUÍ, no en las suites
_DOCS_6 = ["RW-0005", "RW-0006", "RW-0009", "RW-0011", "RW-0012", "RW-0014"]


def _run_technical_suite_c() -> dict:
    from factory.regulatory.validation_v2.technical_suite_c import run_suite_c_formal
    return run_suite_c_formal()


def _run_functional_defect_corpus() -> dict:
    from factory.regulatory.validation_v2.defect_corpus import run_suite_b
    a = Path(tempfile.mkdtemp(prefix="qf-canon-"))
    b = Path(tempfile.mkdtemp(prefix="qf-graph-"))
    return run_suite_b(a, b)


def _run_v2_audit() -> dict:
    from factory.regulatory.validation_v2.v2_runtime import run_v2_pipeline
    base = Path(tempfile.mkdtemp(prefix="qc-e2e-"))
    r = run_v2_pipeline(_DOCS_6, project_id="QC-CONTRACT", run_id="qc", report_base=base)
    a = json.loads((Path(r["run_dir"]) / "audit_summary" / "audit_metadata.json").read_text())
    a["adequacy_rw0009_not_analyzable"] = (
        a.get("adequacy_verdicts", {}).get("RW-0009") == "NOT_ANALYZABLE")
    return a


def _run_reproducibility() -> dict:
    from factory.regulatory.validation_v2.v2_runtime import run_v2_pipeline
    base = Path(tempfile.mkdtemp(prefix="qc-repro-"))
    fps = []
    for i in (1, 2):
        r = run_v2_pipeline(_DOCS_6, project_id="QC-REPRO", run_id=f"r{i}", report_base=base)
        a = json.loads((Path(r["run_dir"]) / "audit_summary" / "audit_metadata.json").read_text())
        fps.append((a["input_config_fingerprint"], a["findings_fingerprint"]))
    return {"fingerprints_reproducible": fps[0] == fps[1], "run1": fps[0], "run2": fps[1]}


_ADAPTERS = {
    "factory.regulatory.validation_v2.qualification_contract:_run_technical_suite_c": _run_technical_suite_c,
    "factory.regulatory.validation_v2.qualification_contract:_run_functional_defect_corpus": _run_functional_defect_corpus,
    "factory.regulatory.validation_v2.qualification_contract:_run_v2_audit": _run_v2_audit,
    "factory.regulatory.validation_v2.qualification_contract:_run_reproducibility": _run_reproducibility,
}


def run_case(case: dict) -> dict:
    from factory.regulatory.validation_v2 import metric_envelope as me

    runner = _ADAPTERS.get(case["test_artifact"]) or _callable(case["test_artifact"])
    result = runner()
    actual = _pluck(result, case["acceptance"]["actual_key"])
    expected, citation = resolve_expected(case["expected_value_source"])
    op = case["acceptance"]["op"]
    if op not in _OPS:
        raise QualificationContractError(f"{case['case_id']}: op inválido {op!r}")
    passed = bool(_OPS[op](actual, expected))
    delta = None
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        delta = round(actual - expected, 6)

    env_cfg = case.get("metric_envelope", {})
    envelope = me.wrap(
        case["case_id"], actual,
        suite_version=case.get("suite_version", case["test_artifact"]),
        size=env_cfg.get("size", 1),
        definition=case.get("test_objective", case["case_id"]),
        reportable_range=env_cfg.get("reportable_range", "SYNTHETIC_ONLY"),
        contamination_statement=env_cfg.get(
            "contamination_statement",
            "sin held-out firmado ni muestra real adjudicada (WP-E) -> SYNTHETIC_ONLY"),
        expected_value=expected, expected_value_source=citation, op=op, delta=delta,
    )
    return {
        "case_id": case["case_id"],
        "intended_use": case.get("intended_use"),
        "requirement": case.get("requirement"),
        "acceptance_criterion": f"{case['acceptance']['actual_key']} {op} {citation}",
        "expected_value": expected, "expected_value_source": citation,
        "found_value": actual, "delta": delta,
        "status": "PASS" if passed else "FAIL",
        "case_status_human": case.get("status", "DRAFT"),
        "reviewer": case.get("reviewer"),
        "evidence": {"test_artifact": case["test_artifact"],
                     "produced_at": datetime.now(timezone.utc).isoformat()},
        "metric_envelope": envelope,
    }


# ── fingerprint (WP-A) ────────────────────────────────────────────────
def verify_fingerprint(contract: dict) -> dict:
    from factory.regulatory.validation_v2.v2_runtime import run_v2_pipeline
    docs = contract.get("dataset", {}).get("document_ids") or _DOCS_6
    base = Path(tempfile.mkdtemp(prefix="qc-fp-"))
    r = run_v2_pipeline(docs, project_id="QC-FP", run_id="fp", report_base=base)
    a = json.loads((Path(r["run_dir"]) / "audit_summary" / "audit_metadata.json").read_text())
    cur = {"input_config_fingerprint": a["input_config_fingerprint"],
           "findings_fingerprint": a["findings_fingerprint"]}
    decl = contract.get("qualified_against", {}).get("fingerprints") or {}
    if not decl:
        return {"declared": None, "current": cur,
                "match": "N/A (contrato DRAFT -- captura de baseline)"}
    match = all(decl.get(k) == cur.get(k) for k in cur)
    return {"declared": decl, "current": cur, "match": match}


# ── orquestación ─────────────────────────────────────────────────────
def decide_overall(cases: list[dict], reqal: dict, fp: dict, *, signed: bool) -> str:
    """Decisión pura, testeable sin re-ejecutar suites. NUNCA devuelve 'QUALIFIED'."""
    any_case_fail = any(x["status"] == "FAIL" for x in cases)
    fp_declared_mismatch = (fp.get("match") is False)
    triggers_changed = reqal.get("any_changed_since_qualified", False)
    if any_case_fail or fp_declared_mismatch or triggers_changed:
        return "FAIL_REQUALIFICATION_REQUIRED"
    if signed and fp.get("match") is True:
        return "GATES_MET_AS_QUALIFIED"          # NUNCA "QUALIFIED" -- eso lo firma un humano
    return "DRAFT_BASELINE"


def run_contract(path: Path | None = None) -> dict:
    c = load_contract(path)
    cases = [run_case(x) for x in c.get("qualification_cases", [])]
    reqal = requalification_status(c)
    fp = verify_fingerprint(c)
    signed = str(c.get("status", "DRAFT")).upper() == "SIGNED"
    overall = decide_overall(cases, reqal, fp, signed=signed)

    return {
        "contract": c.get("artifact"),
        "contract_version": c.get("version"),
        "contract_status": c.get("status", "DRAFT"),
        "system_never_self_qualifies": True,
        "qualified_version": c.get("qualified_version"),           # null salvo firma humana
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fingerprint": fp,
        "requalification": reqal,
        "cases": cases,
        "gates_status": {x["case_id"]: x["status"] for x in cases},
        "contingencies": c.get("contingencies", []),
        "structural_assertions": c.get("structural_assertions", []),
        "overall": overall,
        "note": ("El sistema NO se auto-cualifica ni declara cumplimiento. `qualified_version` y "
                 "cualquier estado QUALIFIED los fija exclusivamente un humano firmando el YAML. "
                 "Este reporte solo dice: estado de gates + contingencias + si hace falta requalification."),
    }


if __name__ == "__main__":
    print(json.dumps(run_contract(), indent=1, ensure_ascii=False, default=str))
