"""W5.3 Fase 5.2 -- escritor de evidencia de validación (_by_req_candidates
y datos afines), parámetros aprobados por el usuario en Fase 5.2 (control
#7 de Fase 5.0). Cableado en evaluate_chunked() queda para Fase 5.4 -- este
módulo es el mecanismo de escritura, listo y probado, sin invocar todavía
desde el motor de producción.

Deliberadamente esta módulo NO expone ninguna función de borrado/expiración
-- la retención es "sin expiración automática", cualquier borrado es una
decisión humana explícita fuera de este módulo."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from factory.core.path_policy import (
    VALIDATION_EVIDENCE_MAX_BYTES, resolve_validation_evidence,
)

VALIDATION_EVIDENCE_BASE = Path(__file__).parent / "validation_evidence"
FILE_PERMISSIONS = 0o640


class EvidenceTooLargeError(Exception):
    """El contenido excede VALIDATION_EVIDENCE_MAX_BYTES -- fail-closed:
    nunca se trunca el texto para que quepa (mismo principio ya aplicado
    en el generador de reportes de FS_v1.2, W5v2)."""


class ProductionEvidenceWriteError(Exception):
    """write_validation_evidence() invocado con run_context != 'validation'."""


def write_validation_evidence(
    run_id: str, document_sha256: str, run_context: str, content: dict,
    evidence_base: Path | None = None,
) -> Path:
    """Escribe evidencia de validación de forma fail-closed:
      1. run_context DEBE ser 'validation' (nunca 'production' -- mismo
         gate que generate_controlled()/evaluate_chunked()).
      2. run_id y document_sha256 se exigen en el nombre de archivo
         (via resolve_validation_evidence) Y dentro del contenido
         (doble anclaje) -- un archivo sin ambos coincidentes se
         considera corrupto.
      3. Tamaño verificado ANTES de escribir -- EvidenceTooLargeError si
         excede el límite, nunca truncamiento silencioso.
      4. content_sha256 calculado sobre el JSON final y embebido -- mismo
         patrón no-circular usado en package_receipt.json (W5v2): se
         calcula, se agrega al dict, y ESE es el que se escribe (no se
         recalcula después contra un archivo ya escrito con el campo
         adentro, evitando la paradoja de "el hash de sí mismo").
      5. Permisos 0o640 al escribir.

    Retención: sin función de borrado expuesta en este módulo (ver
    docstring del módulo)."""
    if run_context != "validation":
        raise ProductionEvidenceWriteError(
            f"write_validation_evidence() bloqueado para run_context={run_context!r} "
            f"-- solo 'validation' está habilitado."
        )

    base = evidence_base or VALIDATION_EVIDENCE_BASE
    base.mkdir(parents=True, exist_ok=True)
    # Fase 5.4.4 (gobernanza): directorio 0o750 -- el contenedor corre como
    # root y create el directorio con umask de root si no existia; se fuerza
    # el modo explicito en cada llamada (idempotente, barato) en vez de
    # confiar en que quedo bien la primera vez.
    os.chmod(base, DIR_PERMISSIONS)
    target = resolve_validation_evidence(run_id, base)

    payload = {
        "run_id": run_id,
        "document_sha256": document_sha256,
        "run_context": run_context,
        "classification": "INTERNAL_VALIDATION_EVIDENCE",
        "content": content,
    }
    # content_sha256 se calcula sobre el payload SIN el propio campo
    # content_sha256 (no puede incluirse a sí mismo) -- patrón no-circular.
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    payload["content_sha256"] = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    final_bytes = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
    if len(final_bytes) > VALIDATION_EVIDENCE_MAX_BYTES:
        raise EvidenceTooLargeError(
            f"Evidencia de {run_id} pesa {len(final_bytes)} bytes, excede el límite "
            f"de {VALIDATION_EVIDENCE_MAX_BYTES} bytes -- no se trunca, no se escribe."
        )

    _atomic_write(target, final_bytes, base)
    return target


DIR_PERMISSIONS = 0o750


def _atomic_write(target: Path, data: bytes, base: Path) -> None:
    """Fase 5.4.4 (gobernanza, corrige de raiz el incidente de Fase 5.4.3/
    5.4.4 de archivos root:root que ing_cpmo no podia leer):
      1. Escritura atomica: se escribe primero a un '.tmp<pid>' en el MISMO
         directorio (mismo filesystem, os.replace() es atomico en POSIX) --
         nunca un archivo parcial visible con el nombre final.
      2. Propietario/grupo heredados del directorio ya autorizado (NUNCA un
         UID/GID hardcodeado en el codigo -- el chown manual aplicado en
         sesiones anteriores era un parche por corrida, no una correccion;
         esto es la correccion real). Si el proceso no tiene privilegio
         para chown (no es root y el archivo ya nacio con el UID correcto),
         se seguir sin fallar -- el modo 0640 sigue aplicado de todas formas."""
    tmp = target.with_name(f"{target.name}.{os.getpid()}.tmp")
    tmp.write_bytes(data)
    os.chmod(tmp, FILE_PERMISSIONS)
    try:
        dir_stat = base.stat()
        os.chown(tmp, dir_stat.st_uid, dir_stat.st_gid)
    except PermissionError:
        pass
    os.replace(tmp, target)
