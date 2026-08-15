# C. Arquitectura de evidencia (A.3 EvidenceUnit/anclaje, A.4 tablas, A.7, A.8)

**Estado**: propuesta de diseño. No implementa nada.

## Diseño de EvidenceUnit y preservación del anclaje literal (A.3)

Restricción dura del brief: la validación A (anclaje literal) debe seguir
funcionando contra el documento ORIGINAL, no solo contra una
representación derivada.

**Mecanismo real hoy**: `evidence_verifier.match_citation()` (líneas
124-154) compara la cita devuelta por el LLM contra `chunk['text']`
(texto plano). Este es el objeto de verdad para el anclaje.

**Diseño propuesto**: si se introduce cualquier capa DOM/EvidenceUnit,
esta debe ser **una vista adicional para construir el prompt**, nunca el
objeto contra el que se verifica. Cada `EvidenceUnit` cargaría:

```
document_id, original_sha256, page, section_id, position,
content_type, derived_sha256, source_location (char_offset en el
string plano original), citation_text
```

`match_citation()` seguiría comparando contra el mismo `chunk['text']`
plano de siempre — el `EvidenceUnit` solo indicaría DÓNDE dentro de ese
string vive la unidad que se aisló para el prompt. Esto garantiza que
introducir estructura nunca debilita el anclaje: la verificación sigue
siendo contra el original, la estructura es puramente aditiva.

**Invariante de test propuesto** (no implementado, solo diseñado): un
`EvidenceUnit.citation_text` debe ser siempre un substring exacto (o
normalizado por los mismos fixes de kerning/furniture/viñetas ya
existentes) de `chunk['text']` en `source_location`. Si no lo es, el
`EvidenceUnit` se rechaza en construcción, nunca se propaga al prompt.

## A.4 — Representación tabular (caso P6)

No existe hoy extractor de tabla estructurada (confirmado en
`DOCUMENT_NORMALIZATION_ARCHITECTURE.md`). Diseño conceptual:

```
Table {
  page, position,
  headers: [...],
  rows: [[celda, celda, ...], ...]
}
```

Vía `pdfplumber.extract_tables()` (dependencia ya instalada, cero
paquete nuevo).

**Dos opciones de serialización para el prompt**, ninguna implementada:

1. **Markdown-table compacta**: más corta, más barata en tokens, pero
   pierde granularidad de provenance por celda.
2. **Lista de aserciones `celda(fila_header, col_header) = valor`**: más
   verbosa, pero permite que un `EvidenceUnit` cite una celda específica
   con provenance fila/columna — útil si Cesar aprueba correr el
   experimento C de `EXPERIMENT_PLAN.md` sobre P6/P7.

**Decisión de secuencia**: no construir el parser de tabla completo antes
del experimento C. Ver `BOTTLENECK_DIAGNOSIS.md` — el ratio de ruido
tabular es real y medido, pero no hay confirmación causal de que
aislarlo cambie el resultado del modelo (mismo riesgo que ya se
materializó en P2/P5, donde evidencia perfectamente aislada no cambió el
juicio).

## A.7 — Quinta validación (Evidence provenance / contextual validity)

**Búsqueda exhaustiva realizada**: grep de "contextual validity" /
"evidence provenance" / "quinta validación" / "validation E" sobre
`docs_plan/*.md` y `factory/regulatory/*.py`. Único resultado: el propio
archivo de instrucciones de esta auditoría.

**Cero casos reales documentados** donde las validaciones A/B/C/D hayan
fallado y una quinta validación de provenance/contexto lo hubiera
detectado.

**FIFTH_VALIDATION_E = RECHAZADA explícitamente**, consistente con la
regla del propio brief (§A.7: "si no hay caso, se rechaza
explícitamente"). No se debilita A/B/C/D. Si en el futuro aparece un caso
real que A/B/C/D no cubran, esta decisión se reabre — no antes.

## A.8 — NO_SIGNAL

**Hallazgo de nomenclatura, no de arquitectura**: el string literal
`"NO_SIGNAL"` **no existe en ningún archivo** de `factory/` ni
`docs_plan/` (grep vacío). Es un concepto del brief, no un símbolo real
del código.

El estado funcionalmente equivalente en producción es
`"DOCUMENTATION_GAP"` (`absence_consolidator.py:123`), que solo se
asigna DESPUÉS de descartar explícitamente todas las precondiciones de
bloqueo:

- `ABSENCE_BLOCKED_BY_PENDING_REVIEW` (línea 110)
- `ABSENCE_BLOCKED_BY_PARTIAL_COVERAGE` (línea 118)
- `ABSENCE_BLOCKED_BY_REJECTED_CHUNKS` (línea 121)
- `APPLICABILITY_UNRESOLVED` (línea 130)

Es decir, ya está diseñado fail-closed contra falsos positivos de
ausencia: nunca afirma "no hay evidencia" mientras existan chunks
pendientes, parciales o rechazados sin resolver.

**NO_SIGNAL_STATUS = permanece**, sin cambio, consistente con la
restricción explícita de Cesar (§A.8 del brief). Ninguna arquitectura de
Evidence Graph propuesta en este documento lo reemplaza — no se demostró
(ni se intentó demostrar, por estar fuera de alcance de esta auditoría de
diseño) que un reemplazo no introduzca falsos positivos sobre B3/N1/N2.

**Recomendación de redacción para futuros documentos**: usar
`DOCUMENTATION_GAP` como el nombre real del código al referirse a este
mecanismo, y anotar `NO_SIGNAL` como su alias conceptual del brief — para
no crear una referencia fantasma a un símbolo que no existe.
