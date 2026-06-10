# TAREA FACTORY — {{project_id}}

## Requerimiento
{{requirement_text}}

## Alcance
- Agentes a heredar: {{agents_to_inherit}}
- Perfiles derivados: {{derived_profiles}}
- Agentes nuevos: {{new_agents}} (requieren aprobación humana previa)

## Restricciones
- Trabajas ÚNICAMENTE en este workspace: `/home/ing_cpmo/factory/workspaces/{{project_id}}/`
- Todo lo prohibido está en `.claude/settings.json` (deny rules) y en `CLAUDE.md`
- Referencia: skills `gmp-factory`, `gmp-agent-design`, `gmp-quality-gates`
- PROHIBIDO tocar: `app/`, `docker-compose.yml` base, `.env` base, `data/`, `backups/`, `aria-*`, `hotelbot-*`
- PROHIBIDO commitear sin aprobación humana explícita

## Criterios de aceptación
{{acceptance_criteria}}

## Pruebas obligatorias
- Quality gates G01-G13 deben pasar (G14 queda pendiente hasta deploy)
- Baterías de preguntas: {{test_battery_summary}}

## Entregables
- [ ] `manifest.yaml` completo
- [ ] `docker-compose.yml` generado y validado (G01)
- [ ] `.env.example` (sin valores reales)
- [ ] Corpus custom con fuentes regulatorias citables
- [ ] Baterías de prueba con criterios de aceptación
- [ ] `quality_gates_report.json`

## Formato de reporte al terminar
1. `tree . -L 3` del workspace
2. `git status --short` del workspace
3. `git diff --stat` del workspace
4. Resumen de quality gates (PASS/FAIL/SKIPPED)
5. Confirmación de base intacto: `curl -s http://localhost:8000/health`

## Prohibiciones absolutas
- No commitear
- No hacer deploy
- No tocar el producto base
- No exponer la API key en el frontend
