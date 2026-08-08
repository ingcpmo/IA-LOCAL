#!/usr/bin/env python3
"""Entrypoint del piloto de diagnóstico pre-corpus (plan
`W5V2_PILOTO_DIAGNOSTICO_PRECORPUS.md` §2.5). Pensado para arrancar
DESACOPLADO de la sesión interactiva (`systemd-run`/`tmux`, nunca hijo de
Claude Code) -- no importa nada de la sesión de Claude Code, solo del
paquete `factory`.

Uso real (Piloto 1, muestra de representatividad):
    python -m factory.scripts.ops.run_corpus_pilot --sample --plan /tmp/pilot_plan_<run_id>.json

`--plan` es un JSON con una lista de unidades
`{document_id, document_type, agent_id, requirement_id, page_indices,
selection_reason}` -- EXACTAMENTE la tabla documentada en §3.1 antes de
ejecutar, nunca generada en runtime.

Escribe un marcador de estado en
`factory/regulatory/pilot_run/status/<run_id>.json` desde el arranque
(PID + plan) hasta el cierre (COMPLETED/FAILED + ruta del manifest) -- es
lo que `pilot_status.sh` lee desde cualquier sesión SSH nueva, sin
depender de que Claude Code siga corriendo."""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from factory.regulatory import corpus_runner as runner  # noqa: E402

STATUS_DIR = runner.PILOT_CHECKPOINT_DIR.parent / "status"


def _status_path(run_id: str) -> Path:
    return STATUS_DIR / f"{run_id}.json"


def _write_status(run_id: str, payload: dict) -> None:
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    path = _status_path(run_id)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _load_plan(plan_path: Path) -> list[dict]:
    data = json.loads(plan_path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError(f"{plan_path}: el plan debe ser una lista JSON no vacía")
    return data


def run_sample(plan_path: Path, *, run_id: str, decision_store_file: Path | None) -> int:
    units = [
        runner.PilotSampleUnit(
            document_id=u["document_id"], document_type=u["document_type"],
            agent_id=u["agent_id"], requirement_id=u["requirement_id"],
            page_indices=tuple(u["page_indices"]), selection_reason=u["selection_reason"],
        )
        for u in _load_plan(plan_path)
    ]
    _write_status(run_id, {
        "run_id": run_id, "pid": os.getpid(), "kind": "sample",
        "status": "RUNNING", "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "plan_path": str(plan_path), "units_planned": len(units),
        "calls_planned": sum(len(u.page_indices) for u in units),
    })
    try:
        summary = runner.run_pilot_sample_batch(units, decision_store_file=decision_store_file)
    except Exception as e:  # noqa: BLE001 -- se registra el fallo, nunca se traga
        _write_status(run_id, {
            "run_id": run_id, "pid": os.getpid(), "kind": "sample", "status": "FAILED",
            "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc(),
        })
        raise
    _write_status(run_id, {
        "run_id": run_id, "pid": os.getpid(), "kind": "sample", "status": "COMPLETED",
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stop_reason": summary.stop_reason, "total_calls_made": summary.total_calls_made,
        "manifest_path": summary.manifest_path,
    })
    return 0 if summary.stop_reason == "CORPUS_COMPLETE" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--sample", action="store_true", help="Piloto 1 (representatividad, §3)")
    parser.add_argument("--plan", required=True, type=Path, help="Ruta al plan JSON (§3.1)")
    parser.add_argument("--run-id", default=None, help="Default: pilot-<fecha>-<pid>")
    parser.add_argument("--decision-store", default=None, type=Path)
    args = parser.parse_args(argv)

    run_id = args.run_id or f"pilot-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{os.getpid()}"
    if args.sample:
        return run_sample(args.plan, run_id=run_id, decision_store_file=args.decision_store)
    parser.error("modo --chain (Piloto 2) aún no implementado en este entrypoint")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
