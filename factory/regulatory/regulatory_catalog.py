"""
Adaptador de nombres para RegulatoryCitationReference (BATCH_AND_EXCEPTION)
sobre el UNICO catalogo regulatorio canonico del proyecto:
factory/regulatory/requirement_catalog/requirements.yaml, cargado y
validado fail-closed por requirement_catalog_loader.py (source_id resuelto
contra source_registry.json, citation_sha256 recalculado y comparado,
review_status=covered solo si ambas condiciones se cumplen -- ver ese
modulo para el detalle de las 5 reglas de carga).

Este archivo NO parsea ningun otro origen (en particular, NO relee los
prompts YAML de los agentes -- esos son consumidores del mismo req_id, no
una fuente alternativa) y NO reconstruye ni cachea una copia propia de los
datos: cada funcion aqui delega directamente en requirement_catalog_loader,
asi que una unica fuente de verdad, un unico punto de fail-closed.

19 entradas vigentes (ver requirements.yaml, catalog_version 1.0,
subfase 5.2): 5 FDA 21 CFR Part 11 + 8 ALCOA+ + 5 EU Annex 11 (incluye
ALCOA_CONTEMPORANEOUS). El propio catalogo declara
`production_status: PRODUCTION_ENABLEMENT=BLOCKED -- este catalogo NO esta
cableado en chunked_engine.py ni en los prompts YAML de produccion` (ver
factory/docs/W5v2_CICLO1_CIERRE.md) -- BATCH_AND_EXCEPTION lo referencia
solo para validar RegulatoryCitationReference.regulatory_catalog_entry_id
en esta capa nueva, sin alterar ese estado ni destrabarlo.
"""
from __future__ import annotations

from factory.regulatory.requirement_catalog.requirement_catalog_loader import (
    CatalogValidationError,
    get_requirement,
    load_requirements,
)


class RegulatoryCatalogError(Exception):
    """Fail-closed: re-lanza CatalogValidationError del catalogo canonico
    con el nombre que espera remediation_package_schemas.py -- no agrega
    ninguna regla de validacion nueva, solo traduce la excepcion."""


def known_entry_ids() -> frozenset[str]:
    try:
        return frozenset(load_requirements()["requirements"].keys())
    except CatalogValidationError as e:
        raise RegulatoryCatalogError(str(e)) from e


def get_catalog_entry(entry_id: str) -> dict:
    """Devuelve EXACTAMENTE la entrada del catalogo canonico (mismo objeto
    que get_requirement) -- ninguna copia derivada, ningun campo agregado."""
    try:
        return get_requirement(entry_id)
    except CatalogValidationError as e:
        raise RegulatoryCatalogError(str(e)) from e
