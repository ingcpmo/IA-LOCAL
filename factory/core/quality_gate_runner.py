"""
Ejecutor de los 14 quality gates obligatorios de GMP AI Factory.

TODO F3:
- run_all_gates(manifest, workspace_path, compose_path) → quality_gates_report.json
- Gates G01-G14 según factory/policies y skill gmp-quality-gates:
  G01: docker compose config -q
  G02: puertos libres y registrados (port_registry + ss -tlnp)
  G03: /health de la solución
  G04: /api/v1/knowledge/stats responde
  G05: min_chunks_per_collection >= 60
  G06: routing de agentes correcto
  G07: preguntas base heredadas responden con contenido válido
  G08: preguntas nuevas cumplen criterios de aceptación
  G09: /api/v1/audit/verify OK
  G10: UI carga (HTTP 200 en /)
  G11: API key NO presente en frontend
  G12: git status limpio en workspace
  G13: diff presentado y archivado
  G14: approval.json presente y status=approved (solo para deploy)
- Gates de runtime (G03-G10) pueden marcarse SKIPPED con motivo si la solución no está levantada
- Salida: {gate, status: PASS/FAIL/SKIPPED, evidence, timestamp}
- Registra gates_executed + hash del reporte en factory_audit.jsonl
"""
