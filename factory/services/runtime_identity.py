"""Identidad verificable del runtime desplegable (W5 V2, cierre de la
reproducibilidad de Fase D).

Problema real que cierra: la migración del motor legacy a `ModelProvider`
(Fase D ampliada, 2026-07-25) vive en
`factory/workspaces/gmpai_document_validation/app/`, que `factory/.gitignore`
excluye con `workspaces/*`. Un runtime cuyo código no se puede identificar
contra un commit no es reproducible, y un análisis regulatorio que no se
puede reproducir no es defendible.

Qué se verificó antes de escribir esto (no supuesto -- medido sobre los
scripts de las corridas reales):

  - Las corridas reales importan `factory.engines.gmpai_integrity.
    chunked_engine`, que **sí** está git-trackeado. El motor legacy del
    workspace NO es lo que ejecuta producción.
  - La única dependencia real del workspace en el camino de ejecución es
    `app/extraction.py` (lectura de PDF/DOCX/DOCM/XLSX). No hay equivalente
    trackeado.

Por eso la solución mínima compatible con la arquitectura existente NO es
mover el workspace al repositorio ni duplicar su código: es **declarar y
verificar** la identidad de las dos partes con el mismo mecanismo que el
snapshot congelado de ALCOA+ ya usó de forma ad-hoc en
`logs/execution_snapshots/alcoa_fsv12_11_20260728/build_manifest.py` --
commit + hash de los ficheros del motor + hash del árbol del workspace --
pero como módulo trackeado y probado, reutilizable por cualquier corrida.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = REPO_ROOT / "factory" / "engines" / "gmpai_integrity"
WORKSPACE_APP_DIR = (
    REPO_ROOT / "factory" / "workspaces" / "gmpai_document_validation" / "app"
)

# Ficheros del motor que las corridas reales importan. Son git-trackeados: su
# identidad se ancla al commit, no a un hash suelto.
ENGINE_FILES = ("chunked_engine.py", "ollama_client.py", "model_provider.py")


class RuntimeIdentityError(RuntimeError):
    """No se puede establecer la identidad del runtime desplegable."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def sha256_tree(root: Path) -> str:
    """Hash estable de un árbol (ruta relativa + contenido de cada fichero),
    para poder declarar la identidad de un directorio que git no versiona.
    Misma función que usó el snapshot de ALCOA+; se ignora `__pycache__`
    porque no es fuente."""
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            h.update(str(p.relative_to(root)).encode())
            h.update(sha256_file(p).encode())
    return h.hexdigest()


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeIdentityError(f"git {' '.join(args)} falló: {result.stderr.strip()}")
    return result.stdout.strip()


def engine_files_tracked() -> dict[str, bool]:
    """Qué ficheros del motor están realmente bajo control de versiones."""
    tracked = set(_git("ls-files", "--", str(ENGINE_DIR.relative_to(REPO_ROOT))).splitlines())
    return {
        name: str((ENGINE_DIR / name).relative_to(REPO_ROOT)) in tracked
        for name in ENGINE_FILES
    }


def engine_files_match_head() -> dict[str, bool]:
    """Si el contenido en disco de cada fichero del motor coincide con el del
    commit actual. False = el runtime en disco NO es el del commit, y
    declarar el commit como su identidad sería falso."""
    result = {}
    for name in ENGINE_FILES:
        rel = str((ENGINE_DIR / name).relative_to(REPO_ROOT))
        try:
            blob_sha = _git("rev-parse", f"HEAD:{rel}")
            disk_sha = _git("hash-object", rel)
        except RuntimeIdentityError:
            result[name] = False
            continue
        result[name] = blob_sha == disk_sha
    return result


def runtime_identity() -> dict:
    """Identidad completa y verificable del runtime desplegable.

    `reproducible` es True solo si las dos mitades quedan ancladas: los
    ficheros del motor trackeados y coincidentes con HEAD, y el árbol del
    workspace con hash declarado. Nunca se declara reproducible por defecto.
    """
    tracked = engine_files_tracked()
    matches = engine_files_match_head()
    workspace_present = WORKSPACE_APP_DIR.is_dir()

    identity = {
        "commit_sha": _git("rev-parse", "HEAD"),
        "engine_files_tracked": tracked,
        "engine_files_match_head": matches,
        "engine_files_sha256": {
            name: sha256_file(ENGINE_DIR / name)
            for name in ENGINE_FILES if (ENGINE_DIR / name).is_file()
        },
        # El workspace es gitignorado por diseño (factory/.gitignore
        # 'workspaces/*'). No se versiona aquí ni se fuerza con `git add -f`:
        # se declara su hash de árbol, que es lo que permite demostrar
        # después que una corrida usó exactamente este contenido.
        "workspace_app_dir": str(WORKSPACE_APP_DIR.relative_to(REPO_ROOT)),
        "workspace_app_present": workspace_present,
        "workspace_app_tree_sha256": (
            sha256_tree(WORKSPACE_APP_DIR) if workspace_present else None
        ),
        "workspace_versioning": "GITIGNORED_DECLARED_BY_TREE_HASH",
    }
    identity["reproducible"] = (
        all(tracked.values()) and all(matches.values())
        and workspace_present and identity["workspace_app_tree_sha256"] is not None
    )
    return identity


def assert_runtime_reproducible() -> dict:
    """Fail-closed para un runner de corrida: aborta antes de gastar una sola
    inferencia si el runtime no es identificable contra un commit."""
    identity = runtime_identity()
    if not identity["reproducible"]:
        untracked = [n for n, ok in identity["engine_files_tracked"].items() if not ok]
        drifted = [n for n, ok in identity["engine_files_match_head"].items() if not ok]
        raise RuntimeIdentityError(
            "runtime no reproducible: "
            f"ficheros del motor sin trackear={untracked}; "
            f"ficheros que no coinciden con HEAD={drifted}; "
            f"workspace presente={identity['workspace_app_present']}"
        )
    return identity
