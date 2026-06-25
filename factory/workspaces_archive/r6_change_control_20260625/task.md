# Task R6: Validación y Reporte del Módulo GMP Change Control

## Contexto
Eres el agente headless de Capa 8. La misión r6_change_control está aprobada por humano.
El código del módulo ya fue generado por el orquestador. Tu tarea es:

1. Leer todos los archivos Python en app/ y tests/ del workspace actual
2. Verificar que los siguientes puntos están cubiertos:
   - [ ] GET /health retorna status 200 con pending_documents listados
   - [ ] ALCOA+ audit trail: write_audit_entry registra actor, timestamp, data_hash SHA256
   - [ ] CR lifecycle: DRAFT → UNDER_REVIEW → APPROVED/REJECTED
   - [ ] CAPA linkage en approve endpoint cuando capa_required=true
   - [ ] knowledge/stats retorna corpus_ready=false y go_live_blocked=true
   - [ ] NO existe texto regulatorio fabricado (verificar que "PENDING_DOCUMENT" aparece en outputs)
   - [ ] tests/test_change_control.py tiene tests de los 8 endpoints principales
3. Escribir el archivo `validation_report.md` en la raíz del workspace con:
   - Checklist de puntos verificados (✓ o ✗)
   - Lista de PENDING_DOCUMENT encontrados en el código
   - Resumen de cobertura de tests
   - Sección "Issues encontrados" (vacía si no hay issues)
   - Firma: "Generado por: Capa 8 Headless / Misión: r6_change_control"

## Restricciones ABSOLUTAS
- NO inventar texto regulatorio
- NO modificar archivos en app/ ni tests/
- SOLO escribir validation_report.md
- Workspace confinado a /home/ing_cpmo/factory/workspaces/r6_change_control/
- Solo operaciones: Read, Write (en workspace), ls, grep, find, cat

## Entregable
Un archivo `validation_report.md` en la raíz del workspace.
