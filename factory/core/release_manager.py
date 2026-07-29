"""Gestión de releases inmutables de soluciones custom."""

import hashlib
import json
import shutil
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import write_event

RELEASES_DIR = Path(__file__).parent.parent / "releases"


class DecisionCoverageBlocked(RuntimeError):
    """Una release exige cobertura de decisión humana y no la tiene.

    W5 V2 G1.11 (consumidor C-5). Es una excepcion propia y no un `ValueError`
    porque un llamador tiene que poder distinguir "esta release ya existe" de
    "nadie autorizo el material de esta release". La segunda no se arregla
    cambiando el numero de version.
    """

    def __init__(self, evidence: str):
        self.evidence = evidence
        super().__init__(
            "Release BLOCKED — gate G15_decision_coverage en FAIL. "
            "El material regulatorio no tiene cobertura de decision humana:\n"
            f"{evidence}"
        )


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def create_release(project_id: str, version: str, workspace_path: str | Path,
                   *, decision_store_file: Path | None = None,
                   audit_file: Path | None = None) -> dict:
    """Crea una release inmutable.

    W5 V2 G1.11: la cobertura de decisiones (G15) se comprueba ANTES de
    cualquier efecto secundario. Una release bloqueada no debe dejar un
    directorio a medias ni un tar huerfano: si no se puede liberar, no se
    empieza a liberar.
    """
    # Import local: quality_gate_runner importa audit_writer y port_registry,
    # y a nivel de modulo esto crearia un ciclo con la ruta de releases.
    from factory.core.quality_gate_runner import g15_decision_coverage

    # Ambos parametros son inyeccion de "donde vive el estado de gobernanza",
    # no interruptores: por defecto (None) apuntan al almacen y a la cadena
    # reales, y ningun llamador de produccion los pasa. Existen porque un test
    # que no puede construir el estado cubierto acaba probando el mock.
    gate = g15_decision_coverage(decision_store_file=decision_store_file,
                                 audit_file=audit_file)
    if gate["status"] != "PASS":
        write_event("release_blocked", project_id, {
            "version": version,
            "gate": "G15",
            "reason": "decision_coverage",
            "evidence": gate["evidence"],
        })
        raise DecisionCoverageBlocked(gate["evidence"])

    ws = Path(workspace_path)
    release_dir = RELEASES_DIR / project_id / version
    if release_dir.exists():
        raise ValueError(f"Release {project_id}/{version} ya existe — crea una nueva versión")
    release_dir.mkdir(parents=True)

    tar_name = f"{project_id}_{version}.tar.gz"
    tar_path = release_dir / tar_name
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(ws, arcname=project_id)

    tar_hash = _sha256(tar_path)
    sums_path = release_dir / "SHA256SUMS"
    sums_path.write_text(f"{tar_hash}  {tar_name}\n")

    for artifact in ("manifest.yaml", "quality_gates_report.json", "approval.json"):
        src = ws / artifact
        if src.exists():
            shutil.copy2(src, release_dir / artifact)

    meta = {
        "project_id": project_id,
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tar_hash": f"sha256:{tar_hash}",
        "status": "pending_approval",
    }
    (release_dir / "release_meta.json").write_text(json.dumps(meta, indent=2))

    write_event("release_created", project_id, {
        "version": version,
        "release_dir": str(release_dir),
        "tar_hash": f"sha256:{tar_hash}",
    })
    return meta


def list_releases(project_id: str | None = None) -> list[dict]:
    if not RELEASES_DIR.exists():
        return []
    results = []
    search = [RELEASES_DIR / project_id] if project_id else list(RELEASES_DIR.iterdir())
    for proj_dir in search:
        if not proj_dir.is_dir():
            continue
        for ver_dir in sorted(proj_dir.iterdir()):
            meta_path = ver_dir / "release_meta.json"
            if meta_path.exists():
                results.append(json.loads(meta_path.read_text()))
    return results


def get_release(project_id: str, version: str) -> dict | None:
    meta_path = RELEASES_DIR / project_id / version / "release_meta.json"
    if not meta_path.exists():
        return None
    return json.loads(meta_path.read_text())
