---
name: gmp-factory
description: Arquitectura, reglas y restricciones duras de GMP AI Factory (capas 7-9) y del producto base GMP AI Copilot (capas 1-6). USAR SIEMPRE que la tarea mencione factory, fabrica, workspace, release, deployment, solucion custom, cliente nuevo, manifest, plantilla base, Docker independiente, capa 7, capa 8, capa 9, o cualquier trabajo dentro de /home/ing_cpmo/factory/. Tambien usar antes de tocar cualquier archivo del servidor para verificar si la ruta esta permitida o prohibida.
---

# GMP AI Factory — Reglas operativas

## Mapa del sistema
- DOCKER 1 (base, puerto 8000): gmp-api, gmp-postgres, gmp-redis,
  aria-ollama. Capas 1-6. PRODUCTO ESTABLE EN MODO REAL. NO MODIFICAR.
- DOCKER 2 (factory, puerto 9000): factory-api + UI. Capas 7-9.
- DOCKER 3..N (custom, puertos 8101+): soluciones independientes generadas
  por la fabrica desde el tag base.

## Restricciones DURAS (violarlas invalida la tarea)
NUNCA modificar: /home/ing_cpmo/app/, docker-compose.yml base, Dockerfile
base, .env base, data/chroma, data/audit_logs, backups/.
NUNCA tocar contenedores aria-* ni hotelbot-*.
NUNCA hacer commit, release o deploy sin aprobacion humana explicita.
NUNCA exponer API keys en frontend ni commitear .env.
NUNCA borrar workspaces sin backup previo (tar.gz en backups/factory/).
Trabajar UNICAMENTE dentro del workspace asignado:
  /home/ing_cpmo/factory/workspaces/<project_id>/

## Flujo obligatorio
requerimiento → registro de proyecto → analisis de alcance →
propuesta tecnica → workspace aislado → generacion → quality gates →
diff presentado → aprobacion humana → release inmutable → deployment.
Cada paso se registra en factory/audit/factory_audit.jsonl (hash chain
SHA-256, mismo patron que app/audit.py del base).

## Plantilla base
La plantilla de codigo se obtiene SIEMPRE de un git tag del base:
  git archive base-vX.Y.Z | tar -x -C <workspace>
Nunca copiar app/ en vivo. Registrar tag y commit en manifest.source.

## Puertos
Fuente unica de verdad: factory/registry/ports.yaml.
Reservados intocables: 8000, 9000, 11434, 5432, 6379.
Rangos custom: api 8101-8199, postgres 5433-5499, redis 6380-6449.
Validar con ss -tlnp antes de asignar y antes de deploy.

## Ollama compartido
Las soluciones custom usan aria-ollama central via:
  extra_hosts: ["host.docker.internal:host-gateway"]
  OLLAMA_BASE_URL=http://host.docker.internal:11434
Maximo 2 soluciones custom activas a la vez (resource_policy.yaml).
Limites obligatorios: api 768m/1cpu, postgres 512m, redis 128m.

## Releases
Inmutables: tar.gz + manifest.yaml + SHA256SUMS + quality_gates_report.json
+ approval.json en factory/releases/<id>/vX.Y.Z/. Nunca editar un release;
correcciones generan nueva version.

## Al terminar cualquier tarea de fabrica, mostrar SIEMPRE:
tree factory -L 4 (o de la subcarpeta tocada), git status --short,
git diff --stat, y esperar aprobacion antes de commitear.
