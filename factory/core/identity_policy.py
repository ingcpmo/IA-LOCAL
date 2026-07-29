"""Política de identidad de la fábrica — W5 V2 G1.15 (cierra A-4).

UNA sola lista de identidades reservadas y UNA sola función que la aplica.

EL DEFECTO QUE CIERRA
---------------------
La auditoría encontró OCHO conjuntos distintos de identidades reservadas
repartidos por el árbol, y no coincidían entre sí:

    layer9/mission_control.py          human agent layer8_agent auto system ""
    api/routes/approvals.py            human agent layer8_agent auto system
    api/routes/layer9.py  (x2)         human agent system admin capa8 capa9 layer8
    layer8/release_candidate_builder   human agent layer8 system capa8 capa9
    services/test_console_service.py   human agent system admin user factory
    core/quality_gate_runner.py        human agent layer8_agent auto system "" None
    services/decision_store_v2.py      (la lista larga)
    services/w5_human_decisions.py     (la lista larga, duplicada)

La consecuencia no es cosmética: `admin` se rechazaba al firmar en un panel
de Capa 9 y se aceptaba al aprobar un deployment; `user` y `factory` solo
estaban reservados en la consola de pruebas. El mismo nombre identificaba a
nadie en una superficie y a alguien en otra.

G1.1 ya había escrito la función canónica dentro de `decision_store_v2` con
el comentario "se centraliza AQUI". No se centralizó: las otras siete
superficies siguieron con su copia. Es la misma forma que el defecto de
raíz de todo este trabajo -- algo correcto existe y nadie lo llama.

POR QUE VIVE EN core/ Y NO EN EL ALMACEN
----------------------------------------
Validar un nombre no puede exigir importar el almacén de decisiones. Ese
import arrastra `schema_loader`, que exige `jsonschema` de forma fail-closed,
y hay superficies (scripts de ops con el `python3` del sistema, el runner de
gates) que no lo tienen. G1.14 ya tropezó con exactamente esa cadena. Este
módulo NO importa nada de la fábrica a propósito.

LA LISTA ES LA UNION, NO LA INTERSECCION
----------------------------------------
Consolidar hacia la unión endurece algunas superficies: `admin` deja de valer
como aprobador en sitios donde valía. Es la dirección correcta -- una
identidad que no identifica a nadie no debe firmar nada, y elegir la
intersección habría aflojado ocho sitios para no tocar uno.
"""
from __future__ import annotations

RESERVED_IDENTITIES = frozenset({
    "", "human", "humano", "agent", "agente", "layer8_agent", "auto",
    "system", "sistema", "admin", "user", "usuario", "factory", "capa8",
    "capa9", "layer8", "layer9", "claude", "qa",
})


class IdentityValidationError(ValueError):
    """Identidad genérica, vacía o reservada.

    `ValueError` a propósito: las superficies HTTP la traducen a 422 y las de
    servicio la dejan propagar. No define su propia jerarquía porque tener dos
    jerarquías para el mismo rechazo es cómo se llegó a las ocho listas.
    """


def is_reserved(name: str | None) -> bool:
    return (name or "").strip().lower() in RESERVED_IDENTITIES


def validate_identity(name: str | None, *, field: str = "identidad") -> str:
    """Devuelve el nombre limpio o lanza. UNICA validación de la fábrica.

    No normaliza a minúsculas el valor devuelto: `Cesar` se guarda como
    `Cesar`. Solo la COMPARACION es insensible a mayúsculas, para que
    `Human`, `HUMAN` y `human` se rechacen los tres.
    """
    clean = (name or "").strip()
    if is_reserved(clean):
        raise IdentityValidationError(
            f"{field}={name!r} es una identidad generica, vacia o reservada. "
            "Un acto de gobernanza exige el nombre real de quien lo firma."
        )
    return clean


def validate_actor(name: str | None, *, field: str = "actor") -> str:
    """Valida a quien PROPONE, que puede no ser una persona.

    La distincion no es una rendija en la regla anterior: es que son dos
    preguntas distintas. `validate_identity` protege la FIRMA -- el acto que
    autoriza -- y ahi "human" no identifica a nadie. Una PROPUESTA la hace
    legitimamente un agente, y exigirle un nombre humano solo produce una de
    dos cosas malas: un campo falso, o un agente haciendose pasar por una
    persona. Ninguna mejora la trazabilidad; las dos la empeoran.

    Lo que si se exige es que sea especifico y no vacio. Y lo que impide que
    esto sea un bypass no vive aqui, sino en el resolver: una propuesta tiene
    `decision_origin="agent_proposed"` y NO otorga cobertura, la firme quien
    la firme.
    """
    clean = (name or "").strip()
    if not clean:
        raise IdentityValidationError(
            f"{field} vacio: una propuesta tiene que decir quien la hace.")
    return clean
