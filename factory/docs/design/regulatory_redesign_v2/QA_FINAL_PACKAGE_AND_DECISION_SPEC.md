# QA_FINAL_PACKAGE_AND_DECISION_SPEC

## 1. Contenido del paquete final

QA-HUM recibe el paquete completo cuando los agentes terminan: candidato;
redline; reporte; matriz; manifest; reseña; cambios autoaplicados; cambios
no aplicados; excepciones; riesgos; gaps cerrados/parciales/abiertos;
implementación pendiente; reporte de calidad; recomendación automática NO
vinculante.

## 2. Decisiones humanas (enum cerrado)

`APPROVE_CLEAN` | `APPROVE_WITH_EXCEPTIONS` | `REQUEST_CHANGES` | `REJECT`

## 3. Reglas

- Aceptación de **conformidad documental** SEPARADA de la **liberación**
  (nunca colapsar los dos conceptos — consistente con la separación
  permanente `DOCUMENT_CONFORMANCE` | `IMPLEMENTATION_VERIFICATION` |
  `REGULATORY_COMPLIANCE` de `GAP_DEVIATION_AND_REMEDIATION_MODEL.md`).
- Sin aprobación humana individual por cada gap o cambio (R-2 del plan) —
  la decisión es sobre el paquete completo.
- Identidad real: `approved_by` obligatorio; `422` para identidades
  genéricas (p.ej. "admin", "system", vacío).
- Idempotencia: `409` en doble aprobación del mismo paquete.
- `decision_origin = human_confirmed` en todo evento de decisión.
- Evento de auditoría por decisión, con payload mínimo: `run_id`,
  `document_id`, `decision`, `approved_by`, `timestamp`,
  `decision_origin`.

## 4. Relación con el precedente real de gobernanza

`factory/api/routes/layer9.py` ya implementa un patrón de endpoints de
misión/decisión/RC/aprobación para el ciclo de vida de soluciones de la
fábrica — es el precedente arquitectónico más cercano a este endpoint de
decisión QA, aunque gobierna misiones/RC de Capa 9, no directamente
paquetes de documentos remediados. Se recomienda evaluar en Fase P si el
endpoint de decisión QA se modela como una extensión de `layer9.py` o como
un router nuevo (`factory/api/routes/qa_decisions.py`) — decisión de diseño
pendiente, no resuelta en esta corrida (no bloquea el diseño global).

## 5. Recomendación automática no vinculante

El paquete puede incluir una recomendación generada (p.ej. "0 excepciones
HIGH_RISK, 2 MEDIUM_RISK pendientes de revisión agrupada") pero esta
recomendación nunca determina la decisión — es texto informativo para
acelerar la lectura humana del paquete, explícitamente marcado como no
vinculante en el propio artefacto.

## 6. Estado actual y brecha

No existe hoy un endpoint ni modelo de datos para las 4 decisiones de esta
sección aplicadas a un paquete de remediación documental. El patrón de
"nunca autoaprobar" y de identidad real ya existe en otras partes de Capa 9
(`layer9.py`) y debe reutilizarse como convención, no reinventarse. Brecha
de implementación gated a Fase P del roadmap.
