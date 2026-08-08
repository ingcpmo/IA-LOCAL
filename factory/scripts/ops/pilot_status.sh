#!/usr/bin/env bash
# pilot_status.sh — estado de solo lectura de un piloto W5 V2 (plan
# W5V2_PILOTO_DIAGNOSTICO_PRECORPUS.md §2.5.3). Ejecutable desde cualquier
# sesion SSH nueva, sin depender de Claude Code ni de tmux/systemd-run
# seguir "conectados" a nada -- solo lee ficheros ya en disco.
#
# Uso: factory/scripts/ops/pilot_status.sh <run_id>
#
# NUNCA escribe auditoria, NUNCA reintenta ni reanuda nada por su cuenta.
set -euo pipefail

RUN_ID="${1:-}"
if [[ -z "$RUN_ID" ]]; then
    echo "uso: $0 <run_id>" >&2
    exit 2
fi

FACTORY_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
STATUS_FILE="$FACTORY_DIR/regulatory/pilot_run/status/${RUN_ID}.json"
CHECKPOINT_DIR="$FACTORY_DIR/regulatory/pilot_run/checkpoints"
TMUX_LOG="/tmp/pilot_${RUN_ID}.log"

echo "=== Piloto ${RUN_ID} ==="

if [[ -f "$STATUS_FILE" ]]; then
    PID=$(python3 -c "import json;print(json.load(open('$STATUS_FILE')).get('pid',''))" 2>/dev/null || echo "")
    STATUS=$(python3 -c "import json;print(json.load(open('$STATUS_FILE')).get('status',''))" 2>/dev/null || echo "DESCONOCIDO")
    echo "estado declarado: $STATUS"
    if [[ -n "$PID" ]]; then
        if kill -0 "$PID" 2>/dev/null; then
            echo "PID $PID: VIVO"
        else
            echo "PID $PID: NO esta corriendo (proceso terminado)"
        fi
    fi
    python3 - "$STATUS_FILE" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
for k in ("started_at", "finished_at", "units_planned", "calls_planned",
          "total_calls_made", "stop_reason", "manifest_path", "error"):
    if k in d:
        print(f"{k}: {d[k]}")
PYEOF
else
    echo "sin status file en $STATUS_FILE (¿run_id correcto? ¿arranco todavia?)"
fi

echo
echo "--- checkpoints reales (${CHECKPOINT_DIR}) ---"
if [[ -d "$CHECKPOINT_DIR" ]]; then
    for f in "$CHECKPOINT_DIR"/*.checkpoint.json; do
        [[ -e "$f" ]] || continue
        NAME=$(basename "$f")
        MTIME=$(date -r "$f" -Iseconds 2>/dev/null || echo "?")
        N_CHUNKS=$(python3 -c "import json;print(len(json.load(open('$f')).get('chunk_executions',[])))" 2>/dev/null || echo "?")
        COMPLETED=$(python3 -c "import json;print(json.load(open('$f')).get('completed', False))" 2>/dev/null || echo "?")
        echo "  $NAME -- chunks=$N_CHUNKS completed=$COMPLETED ultima_escritura=$MTIME"
    done
else
    echo "  (directorio de checkpoints no existe todavia)"
fi

echo
echo "--- ultimas 5 lineas de log ---"
if command -v journalctl >/dev/null 2>&1 && systemctl status "w5v2-pilot-${RUN_ID}" >/dev/null 2>&1; then
    journalctl -u "w5v2-pilot-${RUN_ID}" -n 5 --no-pager
elif [[ -f "$TMUX_LOG" ]]; then
    tail -n 5 "$TMUX_LOG"
else
    echo "  (sin unidad systemd w5v2-pilot-${RUN_ID} ni log en $TMUX_LOG)"
fi

echo
if [[ -f "$STATUS_FILE" ]]; then
    REPORT=$(python3 -c "
import json
d = json.load(open('$STATUS_FILE'))
if d.get('status') in ('COMPLETED', 'FAILED'):
    print(d.get('manifest_path') or '(sin manifest)')
" 2>/dev/null || echo "")
    if [[ -n "$REPORT" ]]; then
        echo "terminado. manifest: $REPORT"
    fi
fi
