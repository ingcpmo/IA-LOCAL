"""Carga schemas regulatorios versionados (W5 Ciclo 1 v2, Fase 1). Política
fail-closed (P1): si `jsonschema` no está disponible, el arranque del módulo
falla explícito en vez de degradar a una validación parcial o inexistente."""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

try:
    import jsonschema
except ImportError as exc:  # pragma: no cover - falla deliberada, no se prueba
    raise RuntimeError(
        "jsonschema es obligatorio para validacion regulatoria. "
        "Ejecucion detenida (politica fail-closed, P1). Instalar antes de "
        "continuar: pip install jsonschema"
    ) from exc

SCHEMAS_DIR = Path(__file__).parent / "schemas"


@lru_cache(maxsize=16)
def load_schema(name: str) -> dict:
    path = SCHEMAS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Schema no encontrado: {name} (buscado en {path})")
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=16)
def schema_sha256(name: str) -> str:
    path = SCHEMAS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Schema no encontrado: {name} (buscado en {path})")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_against(payload: dict, schema_name: str) -> tuple[bool, list[str]]:
    """(ok, errors). Sin fallback parcial (P1): un payload que no valida
    produce una lista de errores, nunca un 'best effort' silencioso."""
    validator = jsonschema.Draft7Validator(
        load_schema(schema_name),
        resolver=jsonschema.RefResolver(base_uri=f"{SCHEMAS_DIR.as_uri()}/", referrer=load_schema(schema_name)),
    )
    errors = [
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(payload)
    ]
    return (len(errors) == 0, errors)
