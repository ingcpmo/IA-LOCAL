"""
W5 — Fuente única de rutas de evidencia para la capa de servicios.

Los servicios referencian estos valores como atributos de módulo
(paths.DESIGNS_BASE, nunca `from paths import DESIGNS_BASE`) para que los
tests puedan redirigirlos con monkeypatch.setattr(paths, ...) en un solo
punto, igual que hacía la suite con las constantes _X de routes/layer9.py.
"""

from pathlib import Path

FACTORY_ROOT = Path(__file__).parent.parent          # /home/ing_cpmo/factory

DESIGNS_BASE = FACTORY_ROOT / "designs"
RC_BASE = FACTORY_ROOT / "release_candidates"
DEP_BASE = FACTORY_ROOT / "deployments"
WS_BASE = FACTORY_ROOT / "workspaces"
AUDIT_FILE = FACTORY_ROOT / "audit" / "factory_audit.jsonl"
TEST_CATALOGS_DIR = FACTORY_ROOT / "test_catalogs"
TEST_RESULTS_DIR = FACTORY_ROOT / "test_results"

MAX_FILE_BYTES = 256 * 1024  # límite de lectura de archivos del visor W3

FILTER_PARTS = frozenset({
    ".pytest_cache", "__pycache__", ".pyc", ".env", ".claude",
    "data/chroma", "backups", ".ssh", ".key", ".pem", "credentials",
})
