#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/home/ing_cpmo"

usage() {
  echo "Uso: $0 <tag_base> <workspace_dir>"
  echo "  Exporta el código base desde un git tag hacia un workspace destino."
  exit 1
}

[[ $# -ne 2 ]] && usage

TAG="$1"
WORKSPACE_DIR="$2"

# Validar que el tag existe
if ! git -C "$REPO_DIR" tag -l | grep -qx "$TAG"; then
  echo "ERROR: El tag '$TAG' no existe en el repositorio." >&2
  echo "Tags disponibles:" >&2
  git -C "$REPO_DIR" tag -l >&2
  exit 2
fi

# Crear workspace si no existe
mkdir -p "$WORKSPACE_DIR"

# Validar que el directorio esté vacío (solo se permite .source_info previo)
EXISTING=$(ls -A "$WORKSPACE_DIR" 2>/dev/null | grep -v '^\.source_info$' || true)
if [[ -n "$EXISTING" ]]; then
  echo "ERROR: El directorio destino '$WORKSPACE_DIR' no está vacío." >&2
  echo "Contenido encontrado: $EXISTING" >&2
  exit 3
fi

# Exportar el tag al workspace
echo "Exportando $TAG → $WORKSPACE_DIR ..."
git -C "$REPO_DIR" archive "$TAG" | tar -x -C "$WORKSPACE_DIR"

# Obtener commit hash del tag
COMMIT_HASH=$(git -C "$REPO_DIR" rev-list -n 1 "$TAG")

# Registrar .source_info
cat > "$WORKSPACE_DIR/.source_info" <<EOF
base_product_tag: $TAG
base_product_commit: $COMMIT_HASH
exported_at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
exported_by: factory/core/template_export.sh
EOF

echo "OK — Exportado $TAG ($COMMIT_HASH) en $WORKSPACE_DIR"
echo "Archivos exportados: $(find "$WORKSPACE_DIR" -type f | wc -l)"
