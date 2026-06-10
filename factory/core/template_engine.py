"""
Motor de parametrización de plantillas.

TODO F2:
- load_manifest(manifest_path) → dict
- render_templates(manifest, templates_dir, output_dir)
  Sustituye {{variable}} en todos los archivos *.template usando string.Template o re
- Variables principales: project_id, api_port, postgres_port, redis_port,
  docker_project_name, base_product_tag, base_product_commit
"""
