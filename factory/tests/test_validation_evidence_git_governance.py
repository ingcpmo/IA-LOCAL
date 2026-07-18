"""W5.3 Fase 5.4.4 (gobernanza) -- firewall de Git para
factory/regulatory/validation_evidence/: falla si CUALQUIER archivo
distinto de la allowlist queda tracked (protege contra un futuro
`git add -f` que se salte el .gitignore), y falla si el CONTENIDO de un
archivo tracked contiene alguna de las claves/patrones prohibidos incluso
si el nombre de archivo pasa la allowlist.

Corre contra el estado real del índice de Git del repo (no un tmp_path) --
es, deliberadamente, el mismo tipo de chequeo que correría en CI sobre la
rama actual."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = "factory/regulatory/validation_evidence"

_ALLOWED_EXACT = {f"{EVIDENCE_DIR}/.gitignore", f"{EVIDENCE_DIR}/README.md"}
_ALLOWED_PATTERN = re.compile(rf"^{re.escape(EVIDENCE_DIR)}/manifests/[a-zA-Z0-9_.\-]+\.manifest\.json$")

_FORBIDDEN_CONTENT_SUBSTRINGS = (
    "raw_response", "source_text", "_by_req_candidates",
)
# Mismos patrones de secretos que factory/core/report_sanitizer.py (Fase W4.1) --
# reutilizados, no reinventados, para mantener un unico lugar de verdad
# sobre que "parece" un secreto.
_SECRET_KEY_RE = re.compile(r"(api[_-]?key|password|secret|token|credential)", re.IGNORECASE)
_ANTHROPIC_KEY_RE = re.compile(r"sk-ant-[A-Za-z0-9_-]+")


def _tracked_files_under_evidence_dir() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", EVIDENCE_DIR],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def test_only_allowlisted_files_are_tracked_under_validation_evidence():
    tracked = _tracked_files_under_evidence_dir()
    offending = [
        f for f in tracked
        if f not in _ALLOWED_EXACT and not _ALLOWED_PATTERN.match(f)
    ]
    assert offending == [], (
        f"Archivo(s) NO permitidos tracked en {EVIDENCE_DIR}: {offending} -- "
        f"solo se permiten .gitignore, README.md y manifests/*.manifest.json"
    )


def test_tracked_manifest_content_never_contains_forbidden_substrings():
    tracked = _tracked_files_under_evidence_dir()
    manifests = [f for f in tracked if _ALLOWED_PATTERN.match(f)]
    for rel_path in manifests:
        content = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
        for forbidden in _FORBIDDEN_CONTENT_SUBSTRINGS:
            assert forbidden not in content, f"{rel_path} contiene '{forbidden}'"
        assert not _ANTHROPIC_KEY_RE.search(content), f"{rel_path} contiene un patron de API key"
        # _SECRET_KEY_RE opera sobre NOMBRES de clave JSON, no sobre
        # cualquier substring -- un manifiesto legitimo no deberia tener
        # ninguna clave que matchee este patron en absoluto.
        import json
        data = json.loads(content)

        def _walk(node):
            if isinstance(node, dict):
                for k, v in node.items():
                    assert not _SECRET_KEY_RE.search(k), (
                        f"{rel_path}: clave sospechosa de secreto '{k}'"
                    )
                    _walk(v)
            elif isinstance(node, list):
                for v in node:
                    _walk(v)
        _walk(data)


def test_readme_and_gitignore_are_tracked():
    """Confirma que la gobernanza documentada (README) y la exclusion
    (.gitignore) SI estan versionadas -- si no lo estan, la gobernanza no
    viaja con el repo."""
    tracked = set(_tracked_files_under_evidence_dir())
    assert f"{EVIDENCE_DIR}/.gitignore" in tracked
    assert f"{EVIDENCE_DIR}/README.md" in tracked
