"""
Bridge que genera task packages por workspace desde las políticas YAML.

TODO F3:
- generate_task_package(project_id, manifest_path, workspace_path)
  Lee las políticas YAML (code_agent_policy, docker_policy, security_policy)
  Genera en <workspace_path>/:
    - task.md          (desde claude_task_template.md + manifest)
    - CLAUDE.md        (desde claude_md_template.md + políticas)
    - .claude/settings.json (desde settings_template.json + políticas)
  Registra task_dispatched en factory_audit.jsonl
  REGLA: CLAUDE.md y settings.json deben generarse DESDE los YAML para que
         política y enforcement nunca diverjan
"""
