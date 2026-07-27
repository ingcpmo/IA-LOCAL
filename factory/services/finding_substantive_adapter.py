"""Adaptador `Finding` -> narrative JSON: transporte del veredicto
sustantivo A^B^C^D (deuda I-1 del roadmap W5 V2, cerrada 2026-07-27).

Problema que cierra
-------------------
El veredicto sustantivo (`substantive_support`, derivado de
`substantive_evidence_accepted` = A^B^C^D==MET) vivia solo en
`chunked_engine.Finding`. El pipeline de remediacion
(`gap_assessment_finding_mapper.py`) no consume `Finding`: consume un
narrative JSON. Un consumidor que armara ese narrative por su cuenta
perdia D por el camino y caia en la heuristica de texto de
`_derive_coverage_status()`, que podia emitir `FULL_COVERAGE` sobre un
positivo cuya evidencia sustantiva nunca fue aceptada.

Este modulo NO es una segunda autoridad de decision (regla explicita del
roadmap): copia los 4 campos ABCD tal como el `Finding` los trae y los
lee de vuelta. Nunca re-evalua D, nunca deriva `substantive_support` a
partir de `d_sufficiency`, nunca rellena un campo ausente.

La unica regla propia de este modulo es de COHERENCIA, no de derivacion:
un narrative que afirma `substantive_support='SUPPORTED'` mientras
`substantive_evidence_accepted` no es `True` se contradice a si mismo, y
una contradiccion se rechaza -- no se resuelve eligiendo un lado.
"""
from __future__ import annotations

from dataclasses import dataclass

# Los 4 campos que viajan del Finding al narrative. Orden irrelevante;
# el conjunto es el contrato.
SUBSTANTIVE_FIELDS = (
    "d_sufficiency",
    "substantive_evidence_accepted",
    "operational_result",
    "substantive_support",
)

# Valores validos de substantive_support (espejo de
# chunked_engine.SUBSTANTIVE_SUPPORT_VALUES, sin 'UNKNOWN': ese valor
# existe solo como cubeta del resumen agregado, nunca como veredicto de
# un Finding individual).
_VALID_SUPPORT = frozenset({"SUPPORTED", "NOT_SUPPORTED", "NOT_APPLICABLE"})

# Estados del veredicto que autorizan a la heuristica de texto a seguir
# evaluando cobertura. NOT_APPLICABLE entra aqui a proposito: un estado no
# positivo (no_cumple/evidencia_insuficiente/no_aplica) no es sujeto de
# sustento sustantivo -- exigirle un SUPPORTED rechazaria justamente los
# gaps, que son la razon de ser del pipeline de remediacion.
PERMITS_COVERAGE_EVALUATION = frozenset({"SUPPORTED", "NOT_APPLICABLE"})


@dataclass(frozen=True)
class SubstantiveVerdict:
    """status:
      SUPPORTED / NOT_SUPPORTED / NOT_APPLICABLE -- veredicto real del Finding.
      ABSENT       -- el narrative no trae ningun campo ABCD.
      INCOMPLETE   -- trae algunos campos pero no el veredicto.
      INVALID      -- substantive_support con un valor fuera del catalogo.
      INCONSISTENT -- el veredicto contradice a substantive_evidence_accepted.
    """
    status: str
    reason: str
    fields: dict


def substantive_block(finding) -> dict:
    """Bloque ABCD de un `Finding`, copiado verbatim. Acepta el dataclass
    o su `to_dict()`. Un campo ausente en el origen queda ausente aqui --
    nunca se inventa `None` como si fuera un veredicto."""
    src = finding if isinstance(finding, dict) else finding.__dict__
    return {k: src[k] for k in SUBSTANTIVE_FIELDS if k in src}


def attach_substantive_verdict(narrative_finding: dict, finding) -> dict:
    """Nuevo narrative con el bloque ABCD incorporado. No muta la entrada
    (P1: el artefacto original nunca se altera en sitio)."""
    return {**narrative_finding, **substantive_block(finding)}


def _verdict_for_legacy_narrative(narrative_finding: dict) -> SubstantiveVerdict:
    """Narrative anterior a Fase F: no trae el bloque ABCD porque el motor
    aun no lo producia. No se rechaza en bloque ni se le inventa un
    veredicto -- se aplica la MISMA autoridad que usa el motor
    (chunked_engine.compute_substantive_support, importada, no copiada)
    sobre el estado real del agente, con substantive_evidence_accepted
    ausente => None.

    Consecuencia fail-closed y buscada: un estado positivo
    (cumple/cumple_parcialmente) de un narrative historico da NOT_SUPPORTED
    -- D nunca se evaluo para el, y eso es exactamente lo que la deuda I-1
    describia como el agujero real. Un estado no positivo da
    NOT_APPLICABLE y sigue mapeando como siempre: un gap no es sujeto de
    sustento sustantivo."""
    estado = narrative_finding.get("estado_agente_original")
    if estado is None:
        return SubstantiveVerdict(
            "ABSENT",
            "el narrative no transporta el veredicto sustantivo "
            f"({', '.join(SUBSTANTIVE_FIELDS)}) ni 'estado_agente_original' del que "
            "derivarlo con la autoridad del motor -- ver finding_substantive_adapter.py",
            {},
        )
    from factory.engines.gmpai_integrity.chunked_engine import compute_substantive_support

    support = compute_substantive_support(estado, None)
    return SubstantiveVerdict(
        support,
        f"narrative sin bloque ABCD (anterior a W5 V2 Fase F): "
        f"compute_substantive_support(estado_agente_original='{estado}', "
        f"substantive_evidence_accepted=None) -> '{support}' (fail-closed, D nunca evaluada)",
        {"estado_agente_original": estado},
    )


def read_substantive_verdict(narrative_finding: dict) -> SubstantiveVerdict:
    """Lee el veredicto ya transportado. Determinista, sin LLM, sin
    recalcular D."""
    present = {k: narrative_finding[k] for k in SUBSTANTIVE_FIELDS if k in narrative_finding}
    if not present:
        return _verdict_for_legacy_narrative(narrative_finding)

    support = present.get("substantive_support")
    if support is None:
        return SubstantiveVerdict(
            "INCOMPLETE",
            f"campos ABCD parcialmente transportados ({sorted(present)}) pero sin "
            "'substantive_support': el veredicto no se deriva aqui, debe venir del Finding",
            present,
        )
    if support not in _VALID_SUPPORT:
        return SubstantiveVerdict(
            "INVALID",
            f"substantive_support='{support}' fuera del catalogo {sorted(_VALID_SUPPORT)}",
            present,
        )
    if support == "SUPPORTED" and present.get("substantive_evidence_accepted") is not True:
        return SubstantiveVerdict(
            "INCONSISTENT",
            "substantive_support='SUPPORTED' con substantive_evidence_accepted="
            f"{present.get('substantive_evidence_accepted')!r}: el narrative se contradice a si mismo "
            "(A^B^C^D==MET es la unica base de SUPPORTED)",
            present,
        )

    return SubstantiveVerdict(
        support,
        f"veredicto sustantivo transportado desde el Finding: substantive_support='{support}'"
        + (f", d_sufficiency='{present.get('d_sufficiency')}'" if "d_sufficiency" in present else ""),
        present,
    )
