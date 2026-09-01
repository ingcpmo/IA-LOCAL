"""Prompt SCTA-POC-1.0 -- con el JSON Schema EMBEBIDO (R4: el modelo no ve `format`
como contexto). FASE 2, aislado."""
from __future__ import annotations

import json

from factory.prototypes.semantic_hybrid_poc.schema import SCTA_V1
from factory.prototypes.semantic_hybrid_poc.context_composer import REQUIRED_ELEMENTS, REG_INTENT

_SCHEMA_STR = json.dumps(SCTA_V1, indent=2, ensure_ascii=False)


def build_prompt(finding: dict, ctx: dict) -> str:
    subtype = finding["subtype"]
    elements = REQUIRED_ELEMENTS.get(subtype, [])
    intent = REG_INTENT.get(subtype, "")
    el_lines = "\n".join(f"  - {e['element_id']}: {e['description']}" for e in elements)

    # contexto: seccion local + vecinas, con su section_id
    ctx_blocks = []
    for sid, text in ctx["scope_texts"].items():
        ctx_blocks.append(f"[section {sid}]\n{text}")
    context_text = "\n\n".join(ctx_blocks)[:20000]

    return f"""Eres un asistente de revision de documentos de validacion GMP. NO decides cumplimiento.
Tu unica tarea: para cada ELEMENTO del comportamiento regulatorio requerido, decir si el
CONTEXTO DEL DOCUMENTO (abajo) lo describe, y respaldar cada veredicto con una CITA LITERAL
copiada palabra por palabra del contexto. Si no puedes citar literalmente, el veredicto NO
puede ser PRESENT.

REQUISITO REGULATORIO: {finding.get('technical_basis') or finding.get('criterion') or '(n/d)'}
INTENCION REGULATORIA: {intent}

ELEMENTOS A EVALUAR (usa exactamente estos element_id):
{el_lines}

FINDING DETERMINISTA (ya emitido por el motor; NO lo cuestionas, solo aportas contexto):
  clase/subtipo: {finding.get('finding_class') or finding.get('class') or 'Finding'} / {subtype}
  documento/pagina: {finding['document']} p.{finding.get('page')}
  cita anclada del motor: "{finding.get('source_text','')}"

CONTEXTO DEL DOCUMENTO (secciones reales; cita SOLO de aqui, palabra por palabra):
--------------------
{context_text}
--------------------

REGLAS DE SALIDA (obligatorias):
1. Responde SOLO con un objeto JSON que valide contra este schema:
{_SCHEMA_STR}
2. Cada `supporting_quote` debe ser una subcadena LITERAL del CONTEXTO de arriba. Si no hay
   cita literal posible para un elemento, pon supporting_quote=null y verdict ABSENT o UNCLEAR.
3. `semantic_coverage`:
   - SUPPORTED   = el contexto describe TODOS los elementos requeridos.
   - PARTIAL     = algunos si, otros no.
   - UNSUPPORTED = el contexto NO describe el comportamiento requerido.
   - INDETERMINATE = no hay evidencia suficiente para decidir.
4. `contradictory_evidence`: pasajes del contexto que CONTRADICEN la presencia del comportamiento
   (p.ej. describen una excepcion o un bypass). Vacio si no hay.
5. `auditor_explanation`: 2-4 frases neutras para un auditor humano, basadas SOLO en lo que citaste.
6. `limitations`: que no pudiste evaluar (p.ej. "el contexto no incluye la seccion de pruebas").
NO inventes citas. NO concluyas cumplimiento. NO añadas campos fuera del schema.
"""
