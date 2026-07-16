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
    # Fix TE-01 (post-mortem FS_v1.2 v3): distingue "evidencia_insuficiente
    # por ausencia real" de "evidencia_insuficiente porque uno o mas chunks
    # relevantes tuvieron un fallo tecnico de ejecucion sin reintento
    # agotado". True == esta clasificacion es PROVISIONAL, requiere
    # reintentar los chunks fallidos antes de tratarla como definitiva.
    technical_execution_failure_pending: bool = False

    def to_dict(self) -> dict:
        return self.__dict__.copy()
