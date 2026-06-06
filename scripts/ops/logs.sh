#!/bin/bash
# GMP AI Copilot — Logs helper
# Uso:
#   bash scripts/ops/logs.sh api
#   bash scripts/ops/logs.sh postgres
#   bash scripts/ops/logs.sh redis
#   bash scripts/ops/logs.sh service
#   bash scripts/ops/logs.sh backup

set -euo pipefail

export PATH="$PATH:/usr/sbin:/sbin"

TARGET="${1:-api}"

case "$TARGET" in
    api)
        docker logs --tail=120 -f gmp-api
        ;;
    postgres)
        docker logs --tail=120 -f gmp-postgres
        ;;
    redis)
        docker logs --tail=120 -f gmp-redis
        ;;
    service)
        tail -n 120 -f /home/ing_cpmo/logs/gmp-copilot.log
        ;;
    service-error)
        tail -n 120 -f /home/ing_cpmo/logs/gmp-copilot-error.log
        ;;
    backup)
        tail -n 120 -f /home/ing_cpmo/logs/backup.log
        ;;
    *)
        echo "Uso: bash scripts/ops/logs.sh [api|postgres|redis|service|service-error|backup]"
        exit 1
        ;;
esac
