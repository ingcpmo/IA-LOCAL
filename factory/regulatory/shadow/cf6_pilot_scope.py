"""SHADOW · CF-6 v1.2 · CF6-2.G — gate PILOT_SCOPE_MATCH_CF6 (sin LLM).

Verifica, contra el ledger de decisiones (`factory/layer9/decisions/decisions_v2.jsonl`),
si la PILOT_EXECUTION vigente autoriza EXPLÍCITAMENTE el alcance de CF-6 (§6):

  (a) el nuevo composer_prompt_version  (shadow-cf6-composer-struct-v2)
  (b) la ejecución CF6-2.5 (piloto de calidad)
  (c) la ejecución CF6-3 (corrida completa post-gate)
  (d) el nuevo TIPO de ejecución del Composer (emisión de estructura JSON, no el
      juicio/prosa libre que -035/-036 autorizó para SHADOW_G4E)

Además: REMAINING_BUDGET_SUFFICIENT · ACTIVE · NOT_SUPERSEDED.

Regla (§6): TODOS deben ser YES → proceder. CUALQUIERA NO → STOP; el mecanismo
correcto (ampliar scope vía canal gobernado o nueva PILOT) lo decide Capa 9.

CERO LLM · CERO red · solo lectura del ledger. No muta nada.
"""
from __future__ import annotations

import json
from pathlib import Path

COMPOSER_PROMPT_VERSION = "shadow-cf6-composer-struct-v2"
_DEFAULT_LEDGER = Path("factory/layer9/decisions/decisions_v2.jsonl")

# marcadores que, de aparecer en el scope firmado, cubrirían cada ítem CF-6
_SCOPE_TOKENS = {
    "a_composer_prompt_version": (COMPOSER_PROMPT_VERSION, "cf6-composer-struct", "cf6_composer_structured"),
    "b_cf6_2_5": ("CF6-2.5", "cf6_2_5", "quality pilot", "human_quality_gate"),
    "c_cf6_3": ("CF6-3", "cf6_3", "corrida completa cf6", "full cf6"),
    "d_execution_type_json_structure": ("json structure", "estructura json", "structured_composer",
                                        "composer_structured", "cf6"),
}


def _iter_records(ledger: Path):
    for line in ledger.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def latest_pilot(ledger: Path = _DEFAULT_LEDGER) -> dict | None:
    """Última pareja propose/confirm de PILOT_EXECUTION en el ledger."""
    pilots = []
    for r in _iter_records(ledger):
        blob = json.dumps(r, ensure_ascii=False)
        if "PILOT_EXECUTION-2026-" in blob or (r.get("payload") or {}).get("scope"):
            iid = r.get("instance_id") or r.get("decision_instance_id") or r.get("confirms_instance_id")
            if iid and "PILOT_EXECUTION" in str(iid):
                pilots.append(r)
    if not pilots:
        return None
    confirms = [p for p in pilots if p.get("confirms_instance_id")]
    return (confirms or pilots)[-1]


def evaluate(ledger: Path = _DEFAULT_LEDGER, *, g4_calls_used: int = 481) -> dict:
    pilot = latest_pilot(ledger)
    scope_blob = json.dumps(pilot or {}, ensure_ascii=False).lower()

    def covered(tokens) -> bool:
        return any(t.lower() in scope_blob for t in tokens if t and t != "cf6")

    checks = {k: ("YES" if covered(v) else "NO") for k, v in _SCOPE_TOKENS.items()}
    pilot_scope_match = "YES" if all(v == "YES" for v in checks.values()) else "NO"

    payload = (pilot or {}).get("payload") or {}
    max_calls = payload.get("max_calls")
    remaining = (max_calls - g4_calls_used) if isinstance(max_calls, int) else None
    budget_sufficient = "YES" if (remaining is not None and remaining >= 10) else ("NO" if remaining is not None else "UNKNOWN")
    status = str((pilot or {}).get("status") or "").upper()
    active = "YES" if status == "ACTIVE" else "NO"
    not_superseded = "NO" if (pilot or {}).get("supersedes_instance_id") or (pilot or {}).get("superseded_by") else "YES"
    if (pilot or {}).get("invalid_reason"):
        active = "NO"

    all_yes = (pilot_scope_match == "YES" and budget_sufficient == "YES"
               and active == "YES" and not_superseded == "YES")

    return {
        "schema": "SHADOW_CF6_2_G_PILOT_SCOPE_MATCH/v1",
        "gate": "CF6-2.G",
        "llm_calls": 0,
        "ledger": str(ledger),
        "pilot_instance": (pilot or {}).get("confirms_instance_id")
                          or (pilot or {}).get("instance_id")
                          or (pilot or {}).get("decision_instance_id"),
        "pilot_scope_summary": payload.get("scope") if isinstance(payload.get("scope"), list) else None,
        "PILOT_SCOPE_MATCH_CF6": pilot_scope_match,
        "scope_checks": checks,
        "REMAINING_BUDGET_SUFFICIENT": budget_sufficient,
        "remaining_calls": remaining,
        "ACTIVE": active,
        "NOT_SUPERSEDED": not_superseded,
        "GATE_RESULT": "PASS" if all_yes else "FAIL",
        "decision": ("proceder a CF6-2.5" if all_yes else
                     "STOP — no proceder con la PILOT existente; Capa 9 decide el mecanismo "
                     "(ampliar scope vía canal gobernado o nueva PILOT). Claude Code NO propone "
                     "una nueva PILOT automáticamente (§6)."),
    }


if __name__ == "__main__":  # pragma: no cover
    import sys
    led = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT_LEDGER
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
        "docs_plan/shadow_llm/CF6/CF6_2_G_PILOT_SCOPE_MATCH.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    res = evaluate(led)
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print("WROTE", out)
    print(json.dumps({k: res[k] for k in (
        "PILOT_SCOPE_MATCH_CF6", "scope_checks", "REMAINING_BUDGET_SUFFICIENT",
        "remaining_calls", "ACTIVE", "NOT_SUPERSEDED", "GATE_RESULT", "decision")},
        indent=1, ensure_ascii=False))
