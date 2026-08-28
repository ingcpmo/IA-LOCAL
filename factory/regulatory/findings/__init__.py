"""Taxonomía de hallazgos V2 (B5) --
docs_plan/ARQUITECTURA_OBJETIVO_ANALIZADOR_GMP_LOCAL_V2.md FASE 7.

7 clases INDEPENDIENTES de Finding (Regulatory / Functional / Technical /
Traceability / DataIntegrity / Security / TestCoverage), cada una con
campos mínimos + `machine_state` / `human_state` SEPARADOS.

Reglas duras:
  - `human_state` inicia SIEMPRE `UNREVIEWED` y NINGÚN código de IA lo
    cambia -- solo `set_human_state(finding, ..., reviewer=<nombre real>)`.
  - La IA puede producir `MACHINE_CONFIRMED_FINDING`,
    `MACHINE_DEVIATION_CANDIDATE`, `MACHINE_REMEDIATION_PROPOSAL`,
    `MACHINE_INCONCLUSIVE` -- NUNCA `QA_APPROVED` / `RELEASED` /
    `CAPA_CLOSED` / `FINAL_GMP_APPROVAL`.
  - Provenance obligatorio (mismo criterio que el modelo canónico B1):
    un Finding sin `document·page·source_text·source_hash` no se construye.
  - El `Risk` es DETERMINISTA (tabla RPN gobernada, `risk_matrix.yaml`),
    nunca un número del LLM.

B5 es determinista, sin LLM, sin gobernanza nueva. CURRENT intacto
(`tier1_report.py` sin tocar; el render V2 vive en `report_v2.py`).
"""
