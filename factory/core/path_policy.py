"""
Política de rutas server-side compartida para workspaces y deployments.

Funciones puras (sin fastapi) que validan project_id antes de cualquier
operación de sistema de archivos, previniendo path traversal.
"""

from pathlib import Path


def resolve_workspace(project_id: str, ws_base: Path) -> Path:
    """
    Valida project_id y retorna la ruta resuelta del workspace.

    Raises:
        ValueError: project_id contiene caracteres de traversal o es vacío.
        FileNotFoundError: el workspace no existe bajo ws_base.
    """
    if not project_id or "/" in project_id or "\\" in project_id or ".." in project_id:
        raise ValueError(f"project_id inválido: {project_id!r}")
    ws = (ws_base / project_id).resolve()
    if not ws.is_relative_to(ws_base.resolve()):
        raise ValueError(f"project_id fuera del directorio de workspaces: {project_id!r}")
    if not ws.exists():
        raise FileNotFoundError(f"Workspace '{project_id}' no encontrado")
    return ws
