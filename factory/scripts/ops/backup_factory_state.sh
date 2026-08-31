#!/bin/bash
# ============================================================================
# H-6F (2026-08-29) -- Backup del ESTADO GOBERNADO de GMP AI Factory.
#
#   * NO usa PostgreSQL pg_dump (eso es H-6B; Factory no usa PostgreSQL).
#   * NO respalda material secreto en claro -> SECRETS_MANIFEST.json + flag
#     SECRET_BACKUP_MECHANISM_MISSING=YES (decisión pendiente de Capa 9).
#   * Genera: <tar>.tar.zst  +  <tar>.tar.zst.sha256  +  MANIFEST.json  +
#     SHA256SUMS  +  SECRETS_MANIFEST.json ; y una línea a backup_events.jsonl
#     (log operativo SEPARADO de la cadena de auditoría gobernada).
#
# Uso:  factory/scripts/ops/backup_factory_state.sh [DEST_DIR]
#   DEST_DIR por defecto: <repo>/backups/factory/state
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
DEST_DIR="${1:-$REPO_ROOT/backups/factory/state}"
PY="${PYTHON:-$REPO_ROOT/.venv/bin/python}"
[ -x "$PY" ] || PY="python3"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/factory_state_backup_${TS}.XXXXXX")"
STAGE="$WORK/factory_state_$TS"
MANIFEST_DIR="$STAGE/_backup_meta"
mkdir -p "$STAGE" "$MANIFEST_DIR" "$DEST_DIR"

echo "[backup] repo=$REPO_ROOT dest=$DEST_DIR ts=$TS"
echo "[backup] staging estado gobernado (excluye regenerables y secretos)..."

# --- copia de los ficheros clasificados REQUIRED_FOR_RECOVERY & no-secretos --
COUNT=0
while IFS= read -r rel; do
    [ -z "$rel" ] && continue
    src="$REPO_ROOT/$rel"
    dst="$STAGE/$rel"
    mkdir -p "$(dirname "$dst")"
    cp -p "$src" "$dst"
    COUNT=$((COUNT+1))
done < <("$PY" "$SCRIPT_DIR/factory_state_manifest.py" filelist "$REPO_ROOT")
echo "[backup] $COUNT ficheros en staging"

# --- MANIFEST.json + SHA256SUMS (hash por fichero) --------------------------
"$PY" "$SCRIPT_DIR/factory_state_manifest.py" manifest "$REPO_ROOT" "$STAGE" "$MANIFEST_DIR/MANIFEST.json"
# mover MANIFEST/SHA fuera del set hasheado no: se dejan dentro del tar pero
# SHA256SUMS solo cubre el estado, no a sí mismo (se regenera en verificación).
mv "$MANIFEST_DIR/SHA256SUMS" "$MANIFEST_DIR/SHA256SUMS" 2>/dev/null || true

# --- SECRETS_MANIFEST.json (naturaleza, NO contenido) ----------------------
"$PY" "$SCRIPT_DIR/factory_state_manifest.py" secrets "$REPO_ROOT" "$MANIFEST_DIR/SECRETS_MANIFEST.json"

# --- tar.zst + sha256 del propio tar --------------------------------------
TARBALL="$DEST_DIR/factory_state_$TS.tar.zst"
tar -C "$WORK" -cf - "factory_state_$TS" | zstd -19 -q -o "$TARBALL"
TAR_SHA="$(sha256sum "$TARBALL" | awk '{print $1}')"
echo "$TAR_SHA  $(basename "$TARBALL")" > "$TARBALL.sha256"

# --- copia de MANIFEST/SECRETS junto al tar (acceso sin descomprimir) -----
cp "$MANIFEST_DIR/MANIFEST.json"         "$DEST_DIR/factory_state_$TS.MANIFEST.json"
cp "$MANIFEST_DIR/SHA256SUMS"            "$DEST_DIR/factory_state_$TS.SHA256SUMS"
cp "$MANIFEST_DIR/SECRETS_MANIFEST.json" "$DEST_DIR/factory_state_$TS.SECRETS_MANIFEST.json"

# --- verify_chain sobre la cadena viva (resumen para el evento) -----------
CHAIN_JSON="$("$PY" - "$REPO_ROOT" <<'PYEOF'
import json, sys
from pathlib import Path
root = Path(sys.argv[1]); sys.path.insert(0, str(root))
try:
    from factory.core import audit_writer as aw
    af = root/"factory"/"audit"/"factory_audit.jsonl"
    fb = root/"factory"/"audit"/"fork_baseline.json"
    rep = aw.verify_chain()
    print(json.dumps({
        "verified": rep.get("verified"), "log_count": rep.get("log_count"),
        "hash_errors": rep.get("hash_errors"), "chain_errors": rep.get("chain_errors"),
        "historical_fork_count": len(aw.known_fork_entry_ids(fb)),
        "new_forks_since_baseline": list(aw.new_forks_since_baseline(af, fb)),
    }))
except Exception as e:
    print(json.dumps({"error": f"{type(e).__name__}: {e}"}))
PYEOF
)"

# --- evento operativo (log SEPARADO, nunca la cadena Part 11) -------------
EVENTS="$DEST_DIR/backup_events.jsonl"
GIT_HEAD="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo UNKNOWN)"
printf '{"ts":"%s","event":"FACTORY_STATE_BACKUP_CREATED","tarball":"%s","tar_sha256":"%s","file_count":%s,"git_head":"%s","audit_chain":%s,"secret_backup_status":"BLOCKED_PENDING_HUMAN_DECISION"}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(basename "$TARBALL")" "$TAR_SHA" "$COUNT" "$GIT_HEAD" "$CHAIN_JSON" \
    >> "$EVENTS"

rm -rf "$WORK"

echo "[backup] OK"
echo "  tarball : $TARBALL"
echo "  sha256  : $TAR_SHA"
echo "  manifest: $DEST_DIR/factory_state_$TS.MANIFEST.json"
echo "  secrets : $DEST_DIR/factory_state_$TS.SECRETS_MANIFEST.json  (SECRET_BACKUP_STATUS=BLOCKED_PENDING_HUMAN_DECISION)"
echo "  event   : $EVENTS"
echo "$TARBALL"
