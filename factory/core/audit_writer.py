"""
Escritor de auditoría de fábrica — JSONL con hash chain SHA-256.

TODO F3:
- Patrón replicado de app/audit.py del base (LEERLO antes de implementar, no modificarlo)
- write_event(event_type, data) → append a factory/audit/factory_audit.jsonl
  Eventos: project_created, requirement_registered, workspace_created,
           task_dispatched, gates_executed, diff_presented,
           approval_granted, approval_rejected, release_created,
           deployment_created, deployment_started
- verify_chain() → bool (verifica integridad SHA-256 de toda la cadena)
"""
