# GMP AI Factory — Workspace {{project_id}}

## Identificación
- **Proyecto:** {{project_id}}
- **Base tag:** {{base_product_tag}}
- **Base commit:** {{base_product_commit}}
- **Generado por:** factory_layer_8_claude_code_agent
- **Modo:** manual_assisted

## Tu alcance en este workspace
Trabajas ÚNICAMENTE en este workspace:
`/home/ing_cpmo/factory/workspaces/{{project_id}}/`

Todo cambio fuera de este directorio es una violación que invalida la tarea.

## Skills disponibles (leer antes de empezar)
- `gmp-factory` — arquitectura, restricciones duras, puertos, Ollama, releases
- `gmp-agent-design` — árbol de decisión para agentes y perfiles
- `gmp-quality-gates` — 14 gates obligatorios con comandos exactos

## Restricciones duras
NUNCA modificar:
- `/home/ing_cpmo/app/`
- `/home/ing_cpmo/docker-compose.yml`
- `/home/ing_cpmo/Dockerfile`
- `/home/ing_cpmo/.env`
- `/home/ing_cpmo/data/`
- `/home/ing_cpmo/backups/`

NUNCA tocar contenedores: `aria-*`, `hotelbot-*`

NUNCA commitear sin aprobación humana explícita.
NUNCA hacer deploy sin que `approval.json` tenga `status=approved`.
NUNCA exponer la API key en el frontend.

## Regla de cierre de sesión
Antes de terminar, mostrar SIEMPRE:
1. `tree . -L 3`
2. `git status --short`
3. `git diff --stat`
4. Resumen de quality gates
5. `curl -s http://localhost:8000/health` (confirmar base intacto)
