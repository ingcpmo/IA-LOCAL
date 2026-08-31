"""R2.3 §2 (docs_plan/R2_3_CONSOLIDACION_Y_TIER1.md, 2026-08-11) --
consistencia del re-etiquetado de checkpoints históricos de modo JUICIO
que quedaron con conclusión de familia gap (DOCUMENTATION_GAP/
PROVISIONAL_GAP) por una condición de carrera de sesión: el fix de R2.2
§2 (full_document_coverage=False) se escribió en judgment.py DESPUÉS de
que estos runs ya habían corrido con el proceso previamente importado.

Barrido real (2026-08-11, sin re-ejecutar ninguna llamada LLM, sin tocar
ningún checkpoint original -- solo lectura de
factory/regulatory/pilot_run/checkpoints/*.checkpoint.json +
absence_consolidator.consolidate() puro + un append a
factory/layer9/review_queue.jsonl por caso):

  - chunked-f47c70f73118 (P2, 21_CFR_11.10(g))          -- SUPERSEDED por chunked-2c3e4b52c953
  - chunked-2e28195523f9 (P5, ALCOA_CONTEMPORANEOUS)    -- SUPERSEDED por chunked-b15b14db5163
  - chunked-04210f062b48 (P6, 21_CFR_211.68(b), RW-0011) -- sin re-medición más nueva
  - chunked-5077df33d5ae (P7, 21_CFR_211.68(b), RW-0012) -- sin re-medición más nueva

Este test no repite el barrido (no vuelve a llamar a consolidate()) --
verifica que el REGISTRO PERSISTIDO en review_queue.jsonl, que es lo que
un humano o un consumidor futuro realmente lee, quedó consistente: misma
familia de conclusión que las entradas ya correctas de P2/P5 producidas
por PILOT_EXECUTION-2026-012 (chunked-2c3e4b52c953,
chunked-b15b14db5163) -- ver test_gmpai_chunked_engine.py para la
cobertura de la REGLA en sí (full_document_coverage=False)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

#: Fichero productivo -- solo se COPIA, nunca se lee/escribe directo desde un test.
_PRODUCTIVE_REVIEW_QUEUE = Path(__file__).parent.parent / "layer9" / "review_queue.jsonl"


@pytest.fixture()
def review_queue_copy(tmp_path) -> Path:
    """H-2b (2026-08-29): estos tests verifican el estado PERSISTIDO del
    re-etiquetado histórico de 2026-08-11. Necesitan leer las entradas reales,
    pero NUNCA deben tocar el fichero productivo: se trabaja sobre una COPIA en
    tmp. `PRODUCTIVE_REVIEW_QUEUE_CHANGED_BY_TESTS = NO` por construcción.
    """
    dst = tmp_path / "review_queue.jsonl"
    if _PRODUCTIVE_REVIEW_QUEUE.exists():
        shutil.copy2(_PRODUCTIVE_REVIEW_QUEUE, dst)
    else:
        dst.write_text("", encoding="utf-8")
    return dst


_RELABELED_RUN_IDS = {
    "chunked-f47c70f73118",  # P2 viejo, superseded
    "chunked-2e28195523f9",  # P5 viejo, superseded
    "chunked-04210f062b48",  # P6
    "chunked-5077df33d5ae",  # P7
}
_CORRECT_FRESH_RUN_IDS = {
    "chunked-2c3e4b52c953",  # P2, PILOT_EXECUTION-2026-012
    "chunked-b15b14db5163",  # P5, PILOT_EXECUTION-2026-012
}


def _load_entries(queue: Path) -> list[dict]:
    entries = []
    for line in queue.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entries.append(json.loads(line))
    return entries


def test_all_four_relabeled_runs_present_in_queue(review_queue_copy):
    entries = _load_entries(review_queue_copy)
    run_ids_present = {e["summary"]["run_id"] for e in entries if "run_id" in e.get("summary", {})}
    missing = _RELABELED_RUN_IDS - run_ids_present
    assert not missing, f"faltan en la cola: {missing}"


def test_relabeled_entries_never_use_gap_family_conclusion(review_queue_copy):
    entries = _load_entries(review_queue_copy)
    relabeled = [e for e in entries if e["summary"].get("run_id") in _RELABELED_RUN_IDS]
    assert len(relabeled) == len(_RELABELED_RUN_IDS)
    for e in relabeled:
        s = e["summary"]
        assert s["conclusion"] == "EVIDENCE_NOT_LOCATED_IN_CANDIDATES", s
        assert s["conclusion"] not in ("PROVISIONAL_GAP", "DOCUMENTATION_GAP")
        assert "ABSENCE_BLOCKED_BY_PARTIAL_COVERAGE" in s["review_flags"]
        assert any(f.startswith("RELABELED_FROM_DOCUMENTATION_GAP_SESSION_RACE_CONDITION")
                   for f in s["review_flags"])


def test_relabeled_entries_same_conclusion_family_as_fresh_correct_runs(review_queue_copy):
    """La garantía central: un checkpoint viejo re-etiquetado y un run
    fresco corrido ya con el fix (full_document_coverage=False desde el
    arranque) producen exactamente la misma familia de conclusión para el
    mismo tipo de resultado (not_observed bajo cobertura parcial)."""
    entries = _load_entries(review_queue_copy)
    relabeled = [e for e in entries if e["summary"].get("run_id") in _RELABELED_RUN_IDS]
    fresh = [e for e in entries if e["summary"].get("run_id") in _CORRECT_FRESH_RUN_IDS]
    assert len(fresh) == len(_CORRECT_FRESH_RUN_IDS)
    conclusions = {e["summary"]["conclusion"] for e in relabeled + fresh}
    assert conclusions == {"EVIDENCE_NOT_LOCATED_IN_CANDIDATES"}


def test_superseded_entries_declare_the_newer_run(review_queue_copy):
    entries = _load_entries(review_queue_copy)
    by_run = {e["summary"]["run_id"]: e for e in entries if "run_id" in e.get("summary", {})}
    p2_old = by_run["chunked-f47c70f73118"]
    p5_old = by_run["chunked-2e28195523f9"]
    assert "SUPERSEDED_BY_NEWER_CORRECT_RUN=chunked-2c3e4b52c953" in p2_old["summary"]["review_flags"]
    assert "SUPERSEDED_BY_NEWER_CORRECT_RUN=chunked-b15b14db5163" in p5_old["summary"]["review_flags"]


def test_p6_and_p7_have_no_superseding_run_flag(review_queue_copy):
    """P6/P7 no tienen re-medición más nueva -- a diferencia de P2/P5
    viejos, no deben llevar SUPERSEDED_BY_NEWER_CORRECT_RUN."""
    entries = _load_entries(review_queue_copy)
    by_run = {e["summary"]["run_id"]: e for e in entries if "run_id" in e.get("summary", {})}
    for run_id in ("chunked-04210f062b48", "chunked-5077df33d5ae"):
        flags = by_run[run_id]["summary"]["review_flags"]
        assert not any(f.startswith("SUPERSEDED_BY_NEWER_CORRECT_RUN") for f in flags), run_id
