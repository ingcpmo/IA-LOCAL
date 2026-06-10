"""
Motor de parametrización de plantillas para GMP AI Factory.

Sustituye {{variable}} en archivos *.template usando los valores del manifest.
Sin dependencias externas pesadas — solo re, yaml, pathlib.
"""

import re
import yaml
import shutil
from pathlib import Path
from datetime import datetime, timezone


TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def load_manifest(manifest_path: str | Path) -> dict:
    with open(manifest_path, "r") as f:
        return yaml.safe_load(f)


def _flatten_manifest(manifest: dict) -> dict:
    """Aplana el manifest en un dict plano de variables para sustitución."""
    p = manifest.get("project", {})
    d = manifest.get("deployment", {})
    s = manifest.get("source", {})
    return {
        "project_id":          p.get("id", ""),
        "project_name":        p.get("name", ""),
        "project_description": p.get("description", ""),
        "created_at":          p.get("created_at", datetime.now(timezone.utc).isoformat()),
        "api_port":            str(d.get("api_port", "")),
        "postgres_port":       str(d.get("postgres_port", "")),
        "redis_port":          str(d.get("redis_port", "")),
        "docker_project_name": d.get("docker_project_name", p.get("id", "")),
        "ollama_model":        d.get("ollama_model", "mistral:7b-instruct-q4_K_M"),
        "db_password":         d.get("db_password", "CAMBIAR_PASSWORD"),
        "base_product_tag":    s.get("base_product_tag", ""),
        "base_product_commit": s.get("base_product_commit", ""),
        "factory_commit":      s.get("factory_commit", ""),
        "agents_inherited":    str(manifest.get("agents", {}).get("inherited", [])),
    }


def render_string(content: str, variables: dict) -> str:
    """Sustituye todas las ocurrencias de {{key}} por su valor."""
    def replacer(match):
        key = match.group(1).strip()
        return str(variables.get(key, match.group(0)))  # deja sin cambiar si no existe
    return re.sub(r"\{\{(\w+)\}\}", replacer, content)


def render_templates(manifest: dict, output_dir: str | Path,
                     templates_dir: str | Path = TEMPLATES_DIR) -> list[Path]:
    """
    Procesa todos los archivos *.template de templates_dir,
    sustituye variables y escribe los resultados en output_dir.
    Retorna lista de archivos generados.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    templates_dir = Path(templates_dir)

    variables = _flatten_manifest(manifest)
    generated = []

    for tmpl in sorted(templates_dir.glob("*.template*")):
        content = tmpl.read_text()
        rendered = render_string(content, variables)

        # Nombre de salida: quitar .template del nombre
        out_name = tmpl.name.replace(".template", "")
        out_path = output_dir / out_name
        out_path.write_text(rendered)
        generated.append(out_path)

    return generated


def render_manifest(manifest: dict, output_dir: str | Path) -> Path:
    """Genera manifest.yaml final en output_dir a partir del dict en memoria."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "manifest.yaml"
    with open(out_path, "w") as f:
        yaml.dump(manifest, f, allow_unicode=True, sort_keys=False)
    return out_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Uso: python3 template_engine.py <manifest.yaml> <output_dir>")
        sys.exit(1)
    m = load_manifest(sys.argv[1])
    generated = render_templates(m, sys.argv[2])
    for p in generated:
        print(f"  Generado: {p}")
