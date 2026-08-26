"""Autorización de liberación -- Decisión 2 (2026-08-26).

EL DEFECTO QUE CIERRA
----------------------
`require_identity` (`factory/api/auth.py`) prueba QUIÉN es la identidad
detrás de una llamada -- nunca QUÉ puede hacer. Antes de este módulo, no
existía ningún control de que una identidad real y autenticada estuviera
además autorizada específicamente a liberar un documento. Verificado por
inspección: `identity_keys.yaml`/`identity_registry.py` solo mapean
`key_sha256 -> nombre`, sin ningún campo de rol/scope/permiso; ningún otro
módulo de la fábrica declara un concepto de "quién puede liberar".

CONTROL MÍNIMO, NO UN SISTEMA DE ROLES
----------------------------------------
Una lista explícita de nombres, provisionada fuera de banda por Capa 9
(mismo criterio que `identity_keys.yaml`: edición manual del archivo, no
un endpoint que la modifique). Vacío o ausente = NADIE autorizado --
fail-closed, nunca "todos". Sin datos sensibles (nombres, no claves) --
a diferencia de `identity_keys.yaml`, este archivo SÍ se versiona en git:
el historial queda como registro auditable de quién fue autorizado a
liberar y desde cuándo.

Vive en `core/` y no importa nada de la fábrica, mismo motivo que
`identity_policy.py`: validar autorización no puede arrastrar
`schema_loader`/`jsonschema` a superficies que no los tienen."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RELEASE_AUTHORIZED_PATH = (
    REPO_ROOT / "factory" / "config" / "release_authorized_identities.yaml")


def release_authorized_path() -> Path:
    override = os.getenv("RELEASE_AUTHORIZED_IDENTITIES_FILE", "").strip()
    return Path(override) if override else DEFAULT_RELEASE_AUTHORIZED_PATH


def load_release_authorized_identities(path: Path | None = None) -> frozenset[str]:
    """{nombres reales autorizados a liberar}. Vacío si el archivo no
    existe, está vacío, o no declara `authorized_identities` -- un
    registro vacío es fail-closed (nadie autorizado), no un error de
    lectura silencioso convertido en "todos permitidos"."""
    p = path or release_authorized_path()
    if not p.is_file():
        return frozenset()
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    names = data.get("authorized_identities") or []
    return frozenset((n or "").strip() for n in names if (n or "").strip())


def is_authorized_to_release(name: str, *, path: Path | None = None) -> bool:
    """Comparación EXACTA (sensible a mayúsculas, mismo criterio que el
    nombre real devuelto por `resolve_identity` -- nunca normalizado)
    contra la lista cargada. `name` debe ser ya la identidad RESUELTA por
    el sistema (`require_identity`), nunca un string crudo del cliente."""
    return (name or "").strip() in load_release_authorized_identities(path=path)
