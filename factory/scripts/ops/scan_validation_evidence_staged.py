#!/usr/bin/env python3
"""W5.3 Fase 5.4.4 (gobernanza) -- escaneo de pre-commit/CI para
factory/regulatory/validation_evidence/.

Bloquea un commit si algo staged bajo ese directorio:
  1. No está en la allowlist (.gitignore, README.md, manifests/*.manifest.json)
     -- protege contra `git add -f` saltándose el .gitignore local.
  2. Contiene raw_response / source_text / _by_req_candidates.
  3. Contiene un patrón de credencial/API key (mismos patrones que
     factory/core/report_sanitizer.py).

Uso:
  - Como hook: instalar via factory/scripts/ops/install_git_hooks.sh
    (.git/hooks/ no es versionable, por eso el hook real es un wrapper
    delgado que invoca este script tracked).
  - Como paso de CI: `python3 factory/scripts/ops/scan_validation_evidence_staged.py --ci`
    (en `--ci` escanea el árbol trackeado completo via `git ls-files` en vez
    del índice staged, para detectar una regresión ya fusionada a la rama).

Exit code 0 = limpio, 1 = violación encontrada (mensaje explicito a stderr).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = "factory/regulatory/validation_evidence"

_ALLOWED_EXACT = {f"{EVIDENCE_DIR}/.gitignore", f"{EVIDENCE_DIR}/README.md"}
_ALLOWED_PATTERN = re.compile(rf"^{re.escape(EVIDENCE_DIR)}/manifests/[a-zA-Z0-9_.\-]+\.manifest\.json$")

_FORBIDDEN_CONTENT_SUBSTRINGS = ("raw_response", "source_text", "_by_req_candidates")
# Mismos patrones que factory/core/report_sanitizer.py -- reutilizados
# deliberadamente, un solo lugar de verdad sobre "que parece un secreto".
_SECRET_KEY_RE = re.compile(r"(api[_-]?key|password|secret|token|credential)", re.IGNORECASE)
_ANTHROPIC_KEY_RE = re.compile(r"sk-ant-[A-Za-z0-9_-]+")


def _staged_files_under_evidence_dir() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM", "--", EVIDENCE_DIR],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def _tracked_files_under_evidence_dir() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", EVIDENCE_DIR],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def _read_staged_content(rel_path: str) -> str:
    result = subprocess.run(
        ["git", "show", f":{rel_path}"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    return result.stdout


def scan(files: list[str], *, from_index: bool) -> list[str]:
    violations = []
    for rel_path in files:
        if rel_path not in _ALLOWED_EXACT and not _ALLOWED_PATTERN.match(rel_path):
            violations.append(f"{rel_path}: NO esta en la allowlist "
                               f"(.gitignore, README.md, manifests/*.manifest.json)")
            continue
        if rel_path.endswith(".gitignore") or rel_path.endswith("README.md"):
            continue
        try:
            content = _read_staged_content(rel_path) if from_index else (REPO_ROOT / rel_path).read_text(encoding="utf-8")
        except subprocess.CalledProcessError:
            continue
        for forbidden in _FORBIDDEN_CONTENT_SUBSTRINGS:
            if forbidden in content:
                violations.append(f"{rel_path}: contiene la subcadena prohibida '{forbidden}'")
        if _ANTHROPIC_KEY_RE.search(content):
            violations.append(f"{rel_path}: contiene un patron de API key (sk-ant-...)")
        for m in _SECRET_KEY_RE.finditer(content):
            violations.append(f"{rel_path}: contiene patron sospechoso de credencial cerca de '{m.group(0)}'")
    return violations


def main() -> int:
    ci_mode = "--ci" in sys.argv
    files = _tracked_files_under_evidence_dir() if ci_mode else _staged_files_under_evidence_dir()
    violations = scan(files, from_index=not ci_mode)
    if violations:
        print("BLOQUEADO -- factory/regulatory/validation_evidence/ tiene contenido no permitido:",
              file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
