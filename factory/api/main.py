"""
GMP AI Factory — FastAPI principal (Docker 2, puerto 9000).

TODO F4:
- Servir factory/ui/index.html en GET /
- GET /health público
- Auth por header X-Api-Key (key en factory/.env, generada con openssl rand -hex 16)
- Montar rutas: projects, workspaces, agents, releases, deployments, approvals
- Toda acción relevante registra evento en factory/audit/factory_audit.jsonl
"""
