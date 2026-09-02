"""SHADOW — capa aditiva de interpretación sobre findings deterministas L2.

Arco de diseño v1.1 (`docs_plan/shadow_llm/DESIGN_LLM_INTERPRETATION_LAYER_v1.1.md`).
Todo lo que vive aquí es ADITIVO y NUNCA muta L2: no toca
class/subtype/severity/risk/requirement_id/machine_state/human_state/related_finding_ids
de ningún Finding, no mueve `FINDINGS_FINGERPRINT`, no llama a ningún modelo.

Fase G1: `router` — routing determinista primario exclusivo (457) + `cross_domain_flag`.
"""
