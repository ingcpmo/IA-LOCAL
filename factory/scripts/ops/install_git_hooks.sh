#!/usr/bin/env bash
# W5.3 Fase 5.4.4 (gobernanza) -- instala el hook pre-commit que invoca
# scan_validation_evidence_staged.py. .git/hooks/ no es versionable, por
# eso este instalador (que SI es tracked) es el mecanismo reproducible:
# cualquier clone/checkout nuevo del repo debe correr este script una vez.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOK_PATH="${REPO_ROOT}/.git/hooks/pre-commit"

cat > "${HOOK_PATH}" <<'HOOK'
#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(git rev-parse --show-toplevel)"
python3 "${REPO_ROOT}/factory/scripts/ops/scan_validation_evidence_staged.py"
HOOK

chmod +x "${HOOK_PATH}"
echo "pre-commit hook instalado en ${HOOK_PATH}"
