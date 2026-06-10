"""
Orquestador del ciclo completo de la Capa 8 (análisis → workspace → generación → gates).

TODO F3/F5:
- run_cycle(project_id) → coordina agent_designer, workspace_manager, quality_gate_runner
- Modo A (manual-asistido): genera task package y espera que Cesar abra Claude Code
- Modo B (headless, futuro): invoca claude -p "$(cat task.md)" (solo tras validar Modo A)
"""
