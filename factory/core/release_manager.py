"""
Gestión de releases inmutables de soluciones custom.

TODO F4:
- create_release(project_id, version, workspace_path, gates_report_path, approval_path)
  Empaqueta workspace → <project_id>_vX.Y.Z.tar.gz
  Copia manifest.yaml, quality_gates_report.json, approval.json
  Genera SHA256SUMS
  Escribe en factory/releases/<project_id>/vX.Y.Z/ (inmutable: si versión existe → error)
  Registra release_created en factory_audit.jsonl
- list_releases(project_id) → lista de versiones disponibles
"""
