# Skill: gmp-status

Ejecuta el script de status y verifica que el sistema GMP tenga PASS=17 WARN=0 FAIL=0.

## Instrucciones

1. Ejecutar: `bash /home/ing_cpmo/logs/evidence/$(ls -t /home/ing_cpmo/logs/evidence/ | grep -v tar | head -1)/status.sh 2>/dev/null || bash /home/ing_cpmo/scripts/status.sh`
2. Si el script no existe, ejecutar checks manuales:
   ```bash
   curl -s localhost:8000/health
   curl -s -o /dev/null -w "%{http_code}" -X POST localhost:8000/api/v1/query -H "Content-Type: application/json" -d '{"question":"test"}'
   curl -s -o /dev/null -w "%{http_code}" localhost:8000/api/v1/knowledge/stats
   curl -s -o /dev/null -w "%{http_code}" localhost:8000/api/v1/audit/verify
   curl -s -o /dev/null -w "%{http_code}" localhost:8000/api/v1/protocol-template/IQ
   ```
3. Reportar cuántos PASS/WARN/FAIL hay

## Target

PASS=17, WARN=0, FAIL=0
