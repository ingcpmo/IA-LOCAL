"""SCTA v1 -- JSON Schema del Semantic Context Assessment (subset POC, suficiente
para validacion fail-closed y para usar como `format` de Ollama). FASE 2, aislado."""

SCHEMA_VERSION = "semantic_context_assessment_v1"

# El schema se pasa a Ollama como `format` (gramatica de decodificacion restringida)
# Y se incluye en el prompt (R4: el modelo no ve `format` como contexto).
SCTA_V1: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "required_elements", "semantic_coverage", "contradictory_evidence",
        "supporting_evidence", "auditor_explanation", "limitations",
    ],
    "properties": {
        "required_elements": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["element_id", "verdict", "supporting_quote"],
                "properties": {
                    "element_id": {"type": "string"},
                    "verdict": {"enum": ["PRESENT", "ABSENT", "CONTRADICTORY", "UNCLEAR"]},
                    "supporting_quote": {"type": ["string", "null"]},
                    "quote_section_hint": {"type": ["string", "null"]},
                },
            },
        },
        "semantic_coverage": {
            "enum": ["SUPPORTED", "PARTIAL", "UNSUPPORTED", "INDETERMINATE"]
        },
        "contradictory_evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["quote", "explanation"],
                "properties": {
                    "quote": {"type": "string"},
                    "explanation": {"type": "string"},
                },
            },
        },
        "supporting_evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["quote", "note"],
                "properties": {
                    "quote": {"type": "string"},
                    "note": {"type": "string"},
                },
            },
        },
        "auditor_explanation": {"type": "string"},
        "limitations": {"type": "array", "items": {"type": "string"}},
    },
}
