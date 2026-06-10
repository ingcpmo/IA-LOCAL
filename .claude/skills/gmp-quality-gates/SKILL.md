---
name: gmp-quality-gates
description: Los 14 quality gates obligatorios para validar cualquier solucion custom de GMP AI Factory antes de release o deploy, con los comandos exactos. USAR SIEMPRE que la tarea mencione quality gates, validacion de solucion, release, deploy, pruebas de solucion custom, o verificacion previa a aprobacion humana.
---

# Quality Gates GMP AI Factory (14 obligatorios)

Ejecutar via factory/core/quality_gate_runner.py o manualmente en orden.
Salida: quality_gates_report.json con {gate, status, evidence, timestamp}.
Registrar hash del reporte en factory/audit/factory_audit.jsonl.

G01 Sintaxis compose:   docker compose -f <compose> config -q
G02 Puertos:            validar contra factory/registry/ports.yaml y
                        ss -tlnp | grep <puerto>  (debe estar libre o ser
                        el propio servicio)
G03 Health:             curl -s http://localhost:<api_port>/health
G04 RAG stats:          curl -s -H "X-Api-Key: $KEY"
                        http://localhost:<api_port>/api/v1/knowledge/stats
G05 Min chunks:         cada coleccion del manifest >= 60 chunks (de G04)
G06 Routing:            POST /api/v1/query con preguntas de prueba y
                        verificar effective agent correcto
G07 Preguntas heredadas: baterias base de cada agente heredado responden
                        con contenido valido (no vacio, cita corpus)
G08 Preguntas nuevas:   baterias de agentes/perfiles creados cumplen sus
                        criterios de aceptacion del manifest
G09 Audit chain:        curl -s -H "X-Api-Key: $KEY"
                        http://localhost:<api_port>/api/v1/audit/verify
G10 UI carga:           curl -s -o /dev/null -w "%{http_code}"
                        http://localhost:<api_port>/  → 200
G11 Key no expuesta:    grep -r "$KEY" <workspace>/app/static/ → vacio
G12 Git limpio:         git -C <workspace> status --short (todo añadido)
G13 Diff archivado:     git -C <workspace> diff (y diff --stat) guardados
                        en el reporte y mostrados al humano
G14 Aprobacion:         approval.json existe y status=approved
                        (OBLIGATORIO solo para deploy; release puede
                        generarse en estado pending_approval)

Gates adicionales de recursos antes de deploy:
- soluciones custom activas < max_active_custom_solutions (docker ps)
- free -m y df -h dentro de umbrales razonables (documentar en reporte)

Regla final: si CUALQUIER gate falla → no hay release ni deploy; se
reporta el fallo, se corrige en workspace y se re-ejecuta TODO el set.
