"""
Generador de docker-compose.yml y Dockerfile para soluciones custom.

TODO F2/F4:
- generate_compose(manifest, template_path, output_path)
  Delega a template_engine para sustituir variables
  Incluye: extra_hosts host-gateway, mem_limit/cpus de resource_policy,
  red <project_id>_net, volúmenes propios
- validate_compose(compose_path) → subprocess docker compose config -q (G01)
"""
