# Factory Claude Bridge

Genera task packages (CLAUDE.md + settings.json + task.md) por workspace desde las políticas YAML.

## Modo A (actual — manual-asistido)
1. La fábrica genera el task package para el proyecto.
2. Cesar ejecuta: `cd /home/ing_cpmo/factory/workspaces/<project_id> && claude`
3. Claude Code lee CLAUDE.md automáticamente al arrancar.
4. Cesar referencia o pega `task.md` para iniciar la tarea.

## Modo B (futuro — headless)
`claude -p "$(cat task.md)" --output-format json`
Solo habilitar después de validar el Modo A en al menos 1 proyecto piloto completo con auditoría.

## Enforcement
- `CLAUDE.md` → Claude Code lo lee automáticamente; contiene restricciones duras
- `.claude/settings.json` → permisos deny nativos de Claude Code
- Las políticas YAML son la fuente documental; CLAUDE.md y settings.json son su materialización ejecutable
- El bridge los genera DESDE los YAML para que nunca diverjan
