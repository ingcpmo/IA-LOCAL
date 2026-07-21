# LANGUAGE_AND_TECHNICAL_QUALITY_GATES — Validación de sugerencias

Diseño únicamente. Cierra el hallazgo NOT_VALIDATED de
`CURRENT_STATE_AUDIT.md` §7: hoy ningún módulo valida calidad de redacción,
coherencia o ausencia de afirmaciones no demostradas en el `proposed_content`
de un `RemediationChange`.

## 1. Los 6 controles exigidos por el objetivo, mapeados a mecanismos reales o nuevos

| Control | Mecanismo | Estado |
|---|---|---|
| Validez regulatoria | `regulatory_catalog_entry_id` existe en el catálogo + `citation_text_sha256` recalculado | **YA EXISTE** — `remediation_package_schemas.validate_regulatory_citation_reference` |
| Validez técnica | El cambio no inventa una capacidad del sistema/documento que no está descrita en otra parte del propio documento evaluado | **NUEVO** — ver §2 |
| Claridad y calidad de redacción | Gramática, ortografía, ambigüedad, terminología consistente con el documento | **NUEVO** — ver §3 |
| Coherencia con el resto del documento | El texto insertado no contradice otra sección ya existente | **NUEVO** — ver §4 |
| Trazabilidad | requisito→evidencia→hallazgo→gap/desviación→cambio→ubicación | **YA EXISTE** — modelo de `GAP_AND_DEVIATION_MODEL.md` §3, campos ya presentes en `RemediationChange` |
| Ausencia de afirmaciones no demostradas | El texto propuesto no dice "el sistema garantiza X" cuando X no tiene evidencia de implementación | **NUEVO** — ver §5 |

## 2. Validez técnica — detector de capacidad inventada

Regla determinista, no generativa (mismo espíritu que `evidence_verifier.py`,
que ya usa comparación de texto, no juicio del LLM, para decidir PASS/FAIL):

```
si proposed_content afirma una capacidad del sistema/documento evaluado
   (verbos como "el sistema garantiza", "el sistema asegura",
    "el sistema valida automáticamente")
   Y esa capacidad no aparece descrita en ningún chunk/sección del
   documento fuente original (verificable por búsqueda de texto sobre la
   extracción ya existente, mismo mecanismo que evidence_verifier usa para
   anclar citas)
        → CHANGE_NOT_APPLIED, HUMAN_INPUT_REQUIRED
```

Ejemplo real de los 3 casos de esta sesión que SÍ pasarían este control: los
3 `proposed_content` (`COR-5`, `COR-2`, `COR-1`) usan verbos de
**recomendación** ("Agregar...", "Incluir...", "Detallar..."), no de
afirmación de capacidad ya implementada — coherente con la regla de §5.

## 3. Claridad y calidad de redacción — gates deterministas, no un juicio del LLM

Para no reintroducir el mismo problema que motivó separar HALLAZGO de
DESVIACIÓN (juicio implícito no auditable), los gates de redacción deben ser
**verificables mecánicamente**, no una opinión del modelo:

- Longitud mínima/máxima razonable por cambio (evitar fragmentos de una
  palabra o párrafos de 2000 palabras).
- Verbo inicial de `proposed_content` pertenece a un vocabulario controlado
  de acción documental (mismo patrón ya validado en
  `gap_assessment_finding_mapper._derive_change_type`: "Agregar", "Incluir",
  "Detallar", "Reemplazar", "Corregir", "Sustituir" — hoy solo 7 verbos
  reconocidos; `FSV12-12` ya demostró en vivo que un verbo fuera de esta
  lista ("Detallar" — espera, ese SÍ está en la lista, el rechazo real de
  `FSV12-12` fue por "Detallar" no estando mapeado a `change_type`, ver
  `CURRENT_STATE_AUDIT.md` — corregir la lista de verbos reconocidos es
  trabajo de implementación, no de este diseño).
- Terminología consistente: el texto propuesto no introduce un término que
  no aparece en ninguna parte del documento original cuando existe un
  término equivalente ya usado (ej. no proponer "backup" si el documento
  siempre dice "respaldo" — verificable por comparación léxica simple contra
  la extracción del documento fuente).
- Ortografía/gramática: verificador determinista de idioma (herramienta
  externa tipo LanguageTool, ejecutada localmente, sin llamada a Ollama —
  respeta la restricción de esta auditoría de "no llamar a Ollama" y,
  además, mantiene el principio de "determinista, no generativo" ya usado en
  todo el pipeline verificado).

**Explícitamente fuera de este diseño**: un juicio de "calidad" hecho por el
LLM sobre su propia redacción. Eso reintroduciría exactamente el patrón que
`evidence_verifier.py` fue construido para evitar (el LLM nunca es el
verificador de su propia salida).

## 4. Coherencia con el resto del documento

```
para cada RemediationChange nuevo:
   buscar (misma técnica de anclaje que evidence_verifier.match_citation)
   si el proposed_content contradice literalmente una afirmación ya
   presente en otra sección del documento (ej. el documento dice en
   la sección 3 "no aplica retención" y el cambio en la sección 7
   agrega una política de retención sin referenciar/reconciliar la
   sección 3)
        → CHANGE_NOT_APPLIED, HUMAN_INPUT_REQUIRED
```

Este control depende de la representación intermedia con estructura
preservada de `DOCUMENT_REMEDIATION_SPEC.md` §2 — no es ejecutable hoy
porque esa representación no existe todavía.

## 5. Ausencia de afirmaciones de implementación no demostradas

Regla de redacción obligatoria, ya practicada manualmente en los 3
`proposed_content` reales de esta sesión (todos usan verbo de recomendación,
ninguno afirma "ya implementado") — se formaliza como gate automático:

```
proposed_content NUNCA puede usar tiempo verbal que implique que el cambio
ya fue verificado/implementado técnicamente (ej. "el sistema ahora
garantiza", "se ha verificado que") — el cambio documental es siempre una
PROPUESTA para el borrador candidato, nunca una declaración de estado
verificado. Mismo principio que el encabezado obligatorio ya usado en
gmpai_docx_draft.py y dossier_generator_service.py ("DRAFT", "SIN VALOR
REGULATORIO").
```

## 6. Salida de los controles: dos estados únicos, sin intermedios

Por instrucción explícita del objetivo:

```
CHANGE_NOT_APPLIED     — el cambio no se incorpora al candidato
HUMAN_INPUT_REQUIRED   — se marca para revisión humana en vez de aplicarse
                          automáticamente
```

No existe un tercer estado "aplicado con advertencia" — un cambio que no
supera cualquiera de los 6 controles queda fuera del candidato hasta
revisión humana, coherente con el principio ya vigente de revisión humana
al final del ciclo (BATCH_AND_EXCEPTION: excepción HIGH_RISK, lote
MEDIUM_RISK, decisión de paquete — todos humanos, nunca automáticos).

## 7. Relación con `claim_verifier.py` (pipeline W7, no reutilizable directo)

`factory/services/claim_verifier.py` ya implementa un patrón cercano
(`unverified_reference`, detección de relevancia temática) pero opera sobre
citas de **agentes de dossier** (W6.5.1, corpus declarado por perfil de
agente), no sobre `RemediationChange` de BATCH_AND_EXCEPTION. Su diseño
(advisory, determinista, nunca bloquea el flujo sino que señala al revisor)
es el patrón correcto a replicar aquí — no el código en sí, que depende de
`corpus_available`/`corpus_pending`, conceptos que no existen en el flujo de
remediación de documentos.
