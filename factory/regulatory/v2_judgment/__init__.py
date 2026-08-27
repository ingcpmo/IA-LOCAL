"""Juicio V2 -- 2 pasos + Critic + Adjudicator (B4).

docs_plan/ARQUITECTURA_OBJETIVO_ANALIZADOR_GMP_LOCAL_V2.md FASE 6 +
docs_plan/PROPUESTA_PROMPTS_JUICIO_V2_B4.md.

B4a (este código): orquestación + Critic + Adjudicator, con los prompts
como BORRADOR (prompts/v2_draft/, DRAFT_UNSIGNED). Los tests corren por
replay offline con el ModelProvider MOCKEADO -- CERO llamadas reales,
cero gobernanza. CURRENT intacto (módulo nuevo, ningún consumidor).

B4b (corrida real de medición contra el fixture 7P+2N) NO arranca sin:
  - firma de Capa 9 sobre los 3 prompts, y
  - una PILOT_EXECUTION firmada.

Guardarraíles (FASE 6.2, no negociables):
  - la cita citable es SIEMPRE Claim.source_text literal (evidence_verifier
    sin cambios); el paso A (descripción neutra) nunca es evidencia.
  - el paso B nunca ve el pasaje original, solo la descripción neutra.
  - el Critic solo DEGRADA (AGREE/DISAGREE/CANNOT_CONFIRM), nunca promueve.
  - EVIDENCE_NOT_FOUND por sí solo nunca => DOCUMENTATION_GAP (eso es
    consolidación a nivel de requisito, B5).
"""
