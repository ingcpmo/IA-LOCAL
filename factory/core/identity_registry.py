"""Registro de identidades humanas autenticadas -- W5 V2, Paquete 2
(cierra hallazgo M de EVALUACION_FINAL_ANALIZADOR_GMP_Y_PLAN_CIERRE.md).

EL DEFECTO QUE CIERRA
----------------------
Hasta este modulo, `decided_by`/`approved_by`/`reviewer`/`authored_by_id`
en los endpoints de gobernanza eran texto libre puesto por el CLIENTE.
`factory-api` solo tiene UNA credencial compartida (`FACTORY_API_KEY`,
`factory/api/main.py`) que autoriza el acceso a la API, pero no distingue
QUIEN entre todos los que la conocen hace una llamada dada. Cualquiera con
esa key podia escribir `approved_by_id="Cesar"` y el sistema lo aceptaba
como si Cesar hubiera firmado -- `identity_policy.validate_identity()`
solo rechazaba nombres genericos/reservados, nunca verificaba que quien
escribe el nombre sea esa persona.

Este modulo resuelve una SEGUNDA credencial (`X-Identity-Key`, distinta de
`FACTORY_API_KEY`) contra un registro de {hash de la key -> nombre real},
provisionado fuera de banda por Capa 9. El nombre devuelto reemplaza el
campo de identidad que antes venia del body -- el cliente deja de poder
declarar libremente quien decide.

DECISION DE ALCANCE (Cesar, 2026-08-18, autorizacion Paquete 2)
-----------------------------------------------------------------
- Sin login/password/JWT: una key larga por persona, generada una vez
  fuera de este sistema (`openssl rand -hex 32`) y comparada por hash.
- Sin modo de transicion: el campo de identidad se ELIMINA del body de
  los endpoints migrados, no se mantiene en paralelo para validar
  coincidencia. Rompe a cualquier llamador que mandara el campo viejo --
  autorizado explicitamente, el sistema no esta en uso productivo real.
- Registro inicial: solo Cesar. Anadir una persona es anadir una entrada
  al archivo de registro (fuera de git), nunca un cambio de codigo.

POR QUE UN ARCHIVO FUERA DE GIT, NO EN EL ALMACEN DE DECISIONES
------------------------------------------------------------------
Mismo patron que `FACTORY_API_KEY` en `.env`: un secreto de autenticacion
no es un dato de negocio versionable. El archivo (`factory/config/
identity_keys.yaml` por defecto, o `IDENTITY_KEYS_FILE` si se quiere otra
ruta) esta en `.gitignore`; solo se versiona `identity_keys.yaml.example`
como plantilla sin secretos reales.

FAIL-CLOSED, NO FAIL-OPEN
---------------------------
Un registro vacio o inexistente no autoriza a nadie: `resolve_identity`
sin key -> error explicito (falta autenticacion); con key desconocida ->
error explicito (autenticacion invalida). Nunca hay un nombre por
defecto ni un bypass "si no hay registro, aceptar cualquier string".
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = REPO_ROOT / "factory" / "config" / "identity_keys.yaml"


class IdentityKeyError(ValueError):
    """`X-Identity-Key` ausente, desconocida, o registro sin provisionar.

    `ValueError` a proposito, mismo patron que `IdentityValidationError`
    en `identity_policy.py`: las superficies HTTP la traducen a 401
    (no autenticado -- distinto del 422 de `identity_policy`, que es
    "autenticado pero el nombre no sirve para firmar").
    """


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def registry_path() -> Path:
    override = os.getenv("IDENTITY_KEYS_FILE", "").strip()
    return Path(override) if override else DEFAULT_REGISTRY_PATH


def load_registry(path: Path | None = None) -> dict[str, str]:
    """{key_sha256: nombre_real}. Vacio si el archivo no existe o esta
    vacio -- el fail-closed lo aplica `resolve_identity`, no la carga: un
    registro vacio es un estado real y valido (recien desplegado, nadie
    provisionado todavia), no un error de lectura."""
    p = path or registry_path()
    if not p.is_file():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    result: dict[str, str] = {}
    for entry in data.get("identities", []) or []:
        name = (entry.get("name") or "").strip()
        key_hash = (entry.get("key_sha256") or "").strip().lower()
        if name and key_hash:
            result[key_hash] = name
    return result


def resolve_identity(raw_key: str, registry: dict[str, str]) -> str:
    """Header -> nombre real, o lanza `IdentityKeyError`.

    Ausencia y desconocimiento son dos fallos distintos con mensajes
    distintos a proposito -- un 401 mudo no le dice a un humano real si
    olvido la cabecera o si su key no fue provisionada."""
    clean = (raw_key or "").strip()
    if not clean:
        raise IdentityKeyError(
            "X-Identity-Key ausente: este endpoint exige una identidad "
            "humana autenticada, ya no acepta un nombre de texto libre "
            "en el body."
        )
    name = registry.get(_hash_key(clean))
    if name is None:
        raise IdentityKeyError(
            "X-Identity-Key desconocida: no resuelve a ninguna identidad "
            "provisionada en el registro de factory-api."
        )
    return name
