"""
Política de rutas server-side compartida para workspaces, designs, RC artifacts y deployments.

Funciones puras (sin fastapi) que validan project_id y rutas relativas antes de cualquier
operación de sistema de archivos, previniendo path traversal y exposición de secretos.
"""

import re
from pathlib import Path

# ── Patrones bloqueados globalmente ──────────────────────────────────────────

_SECRET_PARTS = frozenset({
    ".env", "env.example", ".claude", ".ssh", "credentials",
    "__pycache__", ".pytest_cache", ".pyc", ".pem", ".key",
    "id_rsa", "id_ed25519",
})

# Extensiones permitidas por categoría
_DESIGN_EXTS     = frozenset({".yaml", ".yml", ".md"})
_RC_EXTS         = frozenset({".json", ".log", ".txt", ".md"})
_DEPLOY_EXTS     = frozenset({".py", ".yml", ".yaml", ".md", ".json", ".txt", ".toml", ".cfg", ".ini"})

# Prefijos de directorios bloqueados en deployments
_DEPLOY_BLOCKED  = frozenset({"data/", "knowledge/corpus/", "releases/"})


# ── Helpers internos ─────────────────────────────────────────────────────────

def _check_project_id(project_id: str) -> None:
    if not project_id or "/" in project_id or "\\" in project_id or ".." in project_id:
        raise ValueError(f"project_id inválido: {project_id!r}")


def _check_relative_path(relative_path: str, allowed_exts: frozenset[str]) -> None:
    if ".." in relative_path or relative_path.startswith("/") or "\\" in relative_path:
        raise ValueError(f"relative_path inválido: {relative_path!r}")
    rel = Path(relative_path)
    for part in rel.parts:
        if any(blocked in part.lower() for blocked in _SECRET_PARTS):
            raise PermissionError(f"Path bloqueado por política: {relative_path!r}")
    if rel.suffix.lower() not in allowed_exts:
        raise PermissionError(f"Extensión no permitida: {rel.suffix!r}")


# ── API pública ───────────────────────────────────────────────────────────────

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


def resolve_design(
    project_id: str, designs_base: Path, relative_path: str | None = None
) -> Path:
    """
    Valida project_id y retorna designs_base/project_id o un archivo dentro.
    Extensiones permitidas: .yaml, .yml, .md

    Raises:
        ValueError: project_id o relative_path inválido.
        PermissionError: extensión o nombre bloqueado por política.
        FileNotFoundError: directorio de design no existe.
    """
    _check_project_id(project_id)
    base = designs_base.resolve()
    design_dir = (base / project_id).resolve()
    if not design_dir.is_relative_to(base):
        raise ValueError(f"project_id fuera del directorio de designs: {project_id!r}")
    if not design_dir.exists():
        raise FileNotFoundError(f"Design dir '{project_id}' no encontrado")
    if relative_path is None:
        return design_dir
    _check_relative_path(relative_path, _DESIGN_EXTS)
    target = (design_dir / relative_path).resolve()
    if not target.is_relative_to(design_dir):
        raise ValueError(f"relative_path escapa del design dir: {relative_path!r}")
    return target


def resolve_rc_artifact(
    project_id: str, rc_id: str, rc_base: Path, relative_path: str | None = None
) -> Path:
    """
    Valida project_id y rc_id, retorna rc_base/project_id/rc_id o un artefacto.
    Extensiones permitidas: .json, .log, .txt, .md
    relative_path no puede escapar del directorio del rc_id solicitado.

    Raises:
        ValueError: project_id, rc_id o relative_path inválido.
        PermissionError: extensión bloqueada.
        FileNotFoundError: directorio RC no existe.
    """
    _check_project_id(project_id)
    if not rc_id or "/" in rc_id or "\\" in rc_id or ".." in rc_id:
        raise ValueError(f"rc_id inválido: {rc_id!r}")
    base = rc_base.resolve()
    rc_dir = (base / project_id / rc_id).resolve()
    if not rc_dir.is_relative_to(base):
        raise ValueError(f"Ruta fuera del RC base: {project_id!r}/{rc_id!r}")
    if not rc_dir.exists():
        raise FileNotFoundError(f"RC dir '{project_id}/{rc_id}' no encontrado")
    if relative_path is None:
        return rc_dir
    _check_relative_path(relative_path, _RC_EXTS)
    target = (rc_dir / relative_path).resolve()
    if not target.is_relative_to(rc_dir):
        raise ValueError(f"relative_path escapa del RC dir: {relative_path!r}")
    return target


def resolve_deployment(
    project_id: str, dep_base: Path, relative_path: str | None = None
) -> Path:
    """
    Valida project_id y retorna dep_base/project_id o un archivo permitido.
    Política más estricta que workspaces: bloquea .env, data/, knowledge/corpus/, releases/.
    Extensiones permitidas: .py, .yml, .yaml, .md, .json, .txt, .toml, .cfg, .ini

    Raises:
        ValueError: project_id o relative_path inválido.
        PermissionError: path o extensión bloqueada por política.
        FileNotFoundError: directorio de deployment no existe.
    """
    _check_project_id(project_id)
    base = dep_base.resolve()
    dep_dir = (base / project_id).resolve()
    if not dep_dir.is_relative_to(base):
        raise ValueError(f"project_id fuera del directorio de deployments: {project_id!r}")
    if not dep_dir.exists():
        raise FileNotFoundError(f"Deployment dir '{project_id}' no encontrado")
    if relative_path is None:
        return dep_dir
    if ".." in relative_path or relative_path.startswith("/") or "\\" in relative_path:
        raise ValueError(f"relative_path inválido: {relative_path!r}")
    rel_lower = relative_path.lower()
    # Bloquear prefijos de directorios sensibles
    for prefix in _DEPLOY_BLOCKED:
        if rel_lower.startswith(prefix):
            raise PermissionError(f"Directorio bloqueado por política de deployment: {relative_path!r}")
    # Bloquear partes con patrones de secretos
    for part in Path(relative_path).parts:
        if any(blocked in part.lower() for blocked in _SECRET_PARTS):
            raise PermissionError(f"Path bloqueado por política: {relative_path!r}")
    target = (dep_dir / relative_path).resolve()
    if not target.is_relative_to(dep_dir):
        raise ValueError(f"relative_path escapa del deployment dir: {relative_path!r}")
    if target.suffix.lower() not in _DEPLOY_EXTS:
        raise PermissionError(f"Extensión no permitida en deployments: {target.suffix!r}")
    return target


# ── W5.3 Fase 5.2/5.3 -- evidencia de validación (_by_req_candidates) ───────

# Fase 5.3, opción (a): el run_id REAL que genera evaluate_chunked()
# (chunked_engine.py) es 'chunked-<12 hex>', no 'w5v3-validation-<12 hex>'
# -- ese segundo patrón solo lo emite el runner standalone de Fase 5.0
# (run_validation_evidence.py). En vez de inventar un segundo identificador
# correlacionado a mano para la evidencia de validación del motor real, se
# amplía el patrón aceptado a los DOS formatos reales conocidos -- ambos
# son identificadores opacos generados por código tracked, ninguno permite
# traversal (uuid hex fijo).
_VALIDATION_EVIDENCE_RUN_ID_RE = re.compile(
    r"^(w5v3-validation|chunked)-[0-9a-f]{12}$"
)
VALIDATION_EVIDENCE_EXT = frozenset({".json"})
VALIDATION_EVIDENCE_MAX_BYTES = 10_000_000  # 10 MB, control #7 aprobado


def resolve_validation_evidence(run_id: str, evidence_base: Path) -> Path:
    """
    Valida run_id y retorna evidence_base/{run_id}.json -- mismo patrón que
    resolve_workspace/resolve_rc_artifact (confinamiento + regex + solo
    .json). Parámetros aprobados (Fase 5.0 control #7, confirmados por el
    usuario en Fase 5.2):

    - Patrón de run_id: 'w5v3-validation-<12 hex>' (runner standalone de
      Fase 5.0) O 'chunked-<12 hex>' (run_id real de evaluate_chunked(),
      chunked_engine.py -- aceptado desde Fase 5.3 para no inventar un
      segundo identificador correlacionado a mano) -- cualquier otro
      formato es traversal potencial o un run_id ajeno al pipeline de
      validación, se rechaza.
    - Extensión única permitida: .json.
    - Tamaño máximo: VALIDATION_EVIDENCE_MAX_BYTES (10 MB) -- verificado
      por el caller ANTES de escribir (ver
      factory/regulatory/validation_evidence_writer.py), nunca truncado en
      silencio.
    - Retención: sin expiración automática -- ninguna función de borrado
      se expone en este módulo ni en validation_evidence_writer.py; el
      borrado, si alguna vez se necesita, es una decisión humana explícita
      registrada como evento de auditoría, nunca un cron/TTL.
    - Permisos: 0o640 al escribir (ver validation_evidence_writer.py).
    - Exclusión de paquetes productivos: evidence_base vive bajo
      factory/regulatory/validation_evidence/, un árbol completamente
      distinto de GMPAI/reports/<run_id>/ (la raíz real que empaqueta
      gmpai_document_validation, ver package_v5.py/package_v_*.py de
      W5v2) -- por construcción, ningún paquete final de esa fábrica
      puede incluir evidencia de validación sin un cambio explícito de
      alcance.

    Raises:
        ValueError: run_id no matchea el patrón esperado.
    """
    if not _VALIDATION_EVIDENCE_RUN_ID_RE.match(run_id):
        raise ValueError(
            f"run_id inválido para evidencia de validación: {run_id!r} "
            f"(esperado 'w5v3-validation-<12 hex>' o 'chunked-<12 hex>')"
        )
    base = evidence_base.resolve()
    target = (base / f"{run_id}.json").resolve()
    if not target.is_relative_to(base):
        raise ValueError(f"run_id produce una ruta fuera de evidence_base: {run_id!r}")
    return target
