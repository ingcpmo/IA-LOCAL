"""
W6 — Tests del servicio read-only de vistas MODO DISEÑO
(tareas operativas, fuentes regulatorias, memoria de casos).

Garantías que fijan estos tests:
  - lectura tolerante: archivo ausente/corrupto → estado vacío, nunca excepción
  - design_mode=True y executor/connectors_implemented=False siempre en W6
  - la búsqueda es local (substring) y no requiere red
  - el módulo NO importa httpx ni audit_writer (read-only estructural)
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.services import design_mode_service as svc
from factory.services import paths as svc_paths


@pytest.fixture()
def design_files(tmp_path, monkeypatch):
    """Redirige los 3 archivos de diseño a tmp; devuelve sus rutas."""
    tasks = tmp_path / "tasks.yaml"
    registry = tmp_path / "source_registry.yaml"
    cases = tmp_path / "cases.jsonl"
    monkeypatch.setattr(svc_paths, "AGENT_TASKS_FILE", tasks)
    monkeypatch.setattr(svc_paths, "SOURCE_REGISTRY_FILE", registry)
    monkeypatch.setattr(svc_paths, "CASE_MEMORY_FILE", cases)
    return tasks, registry, cases


# ── Agent tasks ───────────────────────────────────────────────────────────────

def test_agent_tasks_missing_file(design_files):
    out = svc.read_agent_tasks()
    assert out["design_mode"] is True
    assert out["executor_implemented"] is False
    assert out["tasks"] == []


def test_agent_tasks_reads_specs(design_files):
    tasks, _, _ = design_files
    tasks.write_text(
        "executor_implemented: false\n"
        "tasks:\n"
        "  - task_id: t1\n    status: draft_design\n    agent_id: qa\n"
        "  - task_id: t2\n    status: draft_design\n    agent_id: capa\n",
        encoding="utf-8",
    )
    out = svc.read_agent_tasks()
    assert [t["task_id"] for t in out["tasks"]] == ["t1", "t2"]
    assert out["executor_implemented"] is False


def test_agent_task_by_id_and_404(design_files):
    tasks, _, _ = design_files
    tasks.write_text("tasks:\n  - task_id: t1\n    agent_id: qa\n", encoding="utf-8")
    assert svc.read_agent_task("t1")["agent_id"] == "qa"
    assert svc.read_agent_task("nope") is None


def test_agent_tasks_corrupt_yaml(design_files):
    tasks, _, _ = design_files
    tasks.write_text(":::: not yaml [", encoding="utf-8")
    out = svc.read_agent_tasks()
    assert out["tasks"] == []


def test_real_tasks_file_all_draft_design():
    """El tasks.yaml real del repo: todo draft_design, ejecutor no implementado."""
    out = svc.read_agent_tasks()
    assert out["executor_implemented"] is False
    assert len(out["tasks"]) >= 1
    assert all(t["status"] == "draft_design" for t in out["tasks"])
    assert all(t["audit"] is True for t in out["tasks"])


# ── Source registry ───────────────────────────────────────────────────────────

def test_source_registry_missing_file(design_files):
    out = svc.read_source_registry()
    assert out["design_mode"] is True
    assert out["connectors_implemented"] is False
    assert out["sources"] == []


def test_real_source_registry_connectors():
    """El registry real: 9 fuentes (W6.3 + W9 Bloque 3), SOLO los 3 conectores
    openFDA connected — conectar cualquier otra requiere aprobación humana
    explícita."""
    out = svc.read_source_registry()
    assert out["connectors_implemented"] is True
    assert len(out["sources"]) == 9
    connected = {s["source_id"] for s in out["sources"] if s["status"] == "connected"}
    assert connected == {"openfda_enforcement", "openfda_device_enforcement",
                         "openfda_food_enforcement"}
    assert all(s["status"] == "not_connected" for s in out["sources"]
               if s["source_id"] not in connected)
    assert out["default_policy"]["store_full_documents"] is False


# ── Case memory ───────────────────────────────────────────────────────────────

def test_case_memory_empty(design_files):
    out = svc.read_case_memory()
    assert out["count"] == 0 and out["cases"] == []
    assert "memoria vacía" in out["note"]


def test_case_memory_reads_and_limits(design_files):
    _, _, cases = design_files
    lines = [json.dumps({"case_id": f"c{i}", "summary": f"caso {i}"}) for i in range(5)]
    cases.write_text("\n".join(lines) + "\ngarbage-not-json\n", encoding="utf-8")
    out = svc.read_case_memory(limit=3)
    assert out["count"] == 5                       # el corrupto se omite
    assert [c["case_id"] for c in out["cases"]] == ["c2", "c3", "c4"]


def test_case_memory_search(design_files):
    _, _, cases = design_files
    cases.write_text("\n".join([
        json.dumps({"case_id": "a", "summary": "OOS en HPLC assay",
                    "tags": ["oos"], "keywords": ["hplc"], "case_type": "483"}),
        json.dumps({"case_id": "b", "summary": "data integrity backup",
                    "tags": ["alcoa"], "keywords": [], "case_type": "warning_letter"}),
    ]), encoding="utf-8")
    assert [c["case_id"] for c in svc.search_case_memory("hplc")["results"]] == ["a"]
    assert [c["case_id"] for c in svc.search_case_memory("WARNING_LETTER")["results"]] == ["b"]
    assert svc.search_case_memory("")["results"] == []
    assert svc.search_case_memory("zzz")["count"] == 0


# ── Read-only estructural ─────────────────────────────────────────────────────

def test_module_never_talks_outbound_or_audits():
    """El servicio no importa httpx ni audit_writer: read-only por construcción."""
    import ast
    tree = ast.parse(Path(svc.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported.update(a.name for a in node.names)
    assert not any("httpx" in name for name in imported)
    assert not any("audit" in name for name in imported)
    assert "write_event" not in imported
