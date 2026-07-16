"""Modelo compartido de hallazgo (Finding) — idéntico en contrato al que
usaban los agentes de integridad del workspace gmpai_document_validation
(fda_part11_agent, eu_annex11_agent, alcoa_plus_agent,
requirements_traceability_agent). Movido aquí (git-trackeado) para que el
motor de chunking no dependa del workspace gitignorado."""

from __future__ import annotations

from dataclasses import dataclass

STATUSES = ("cumple", "cumple_parcialmente", "no_cumple", "evidencia_insuficiente", "no_aplica")


@dataclass
class Finding:
    sistema: str
    documento: str
    version: str
    archivo: str
    pagina_o_seccion: str
    requisito_regulatorio: str
    evidencia_exacta: str
    estado: str
    brecha: str
    severidad: str
    riesgo: str
    recomendacion: str
    confianza: str
    agente_responsable: str
    revision_humana_requerida: bool
    agent_version: str | None = None
    prompt_version: str | None = None
    model: str | None = None
    verifier_version: str | None = None

    def to_dict(self) -> dict:
        return self.__dict__.copy()
