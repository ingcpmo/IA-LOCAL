"""Dependencia HTTP de identidad autenticada -- factory-api (Paquete 2,
cierra hallazgo M). Ver `factory/core/identity_registry.py` para el
diseno completo.

Vive fuera de `main.py` a proposito: los tests de router existentes
(`test_finding_review_decision_endpoint.py`, `test_remediation_directive_endpoint.py`,
etc.) montan `layer9.router` en una `FastAPI()` propia, sin pasar por
`main.py` ni por `verify_api_key` -- si `require_identity` viviera solo
como dependencia de router en `main.py`, esos tests (y produccion, si
algun router se monta distinto) no la verian. Al inyectarse como
`Depends(require_identity)` en la FIRMA de cada endpoint migrado, la
identidad se exige sin importar como se monte el router.
"""
from __future__ import annotations

from fastapi import Header, HTTPException

from factory.core.identity_registry import IdentityKeyError, load_registry, resolve_identity

# Cargado una vez al importar el modulo, mismo patron que FACTORY_API_KEY en
# main.py. Los tests lo sobreescriben con monkeypatch.setattr(auth, "_REGISTRY", {...})
# -- nunca releen el archivo real de disco.
_REGISTRY: dict[str, str] = load_registry()


async def require_identity(x_identity_key: str = Header(default="")) -> str:
    """Resuelve la identidad humana autenticada detras de `X-Identity-Key`.

    El nombre devuelto es el UNICO valor valido para `decided_by`/
    `approved_by`/`reviewer`/`authored_by_id` en los endpoints migrados --
    reemplaza por completo el campo equivalente que antes aceptaba el
    body del cliente."""
    try:
        return resolve_identity(x_identity_key, _REGISTRY)
    except IdentityKeyError as e:
        raise HTTPException(status_code=401, detail=str(e))
