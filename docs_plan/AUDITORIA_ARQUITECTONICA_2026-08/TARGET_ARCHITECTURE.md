# J. Arquitectura objetivo consolidada

**Estado**: síntesis de los 11 documentos anteriores. Condicionada por
completo a aprobación de Cesar. No es un compromiso de construcción.

## Vista de conjunto

```
                         ┌─────────────────────────────┐
                         │   ORIGINAL (Rockwell PDF)    │  ← nunca se sobrescribe
                         └──────────────┬───────────────┘
                                        │ pdfplumber (sin cambio de conversor)
                         ┌──────────────▼───────────────┐
                         │  EXTRACCIÓN (ya corregida:    │
                         │  kerning, viñetas U+F0B7)     │
                         │  + fix nuevo: furniture        │
                         │  simétrico LLM/verificador     │  ← Fase 0
                         └──────────────┬───────────────┘
                                        │
                    ┌───────────────────┴────────────────────┐
                    │                                         │
        ┌───────────▼───────────┐              ┌──────────────▼─────────────┐
        │ CHUNKING actual        │              │ Table/EvidenceUnit          │
        │ (build_page_chunks,    │              │ CONDICIONADO al resultado   │
        │  sin cambio salvo fix) │              │ del Experimento C (Fase 1)  │  ← solo si
        └───────────┬───────────┘              └──────────────┬─────────────┘     se justifica
                    │                                         │
                    └───────────────────┬─────────────────────┘
                                        │
                         ┌──────────────▼───────────────┐
                         │  RETRIEVAL — ya resuelto (R2)  │
                         │  BM25 + embeddings, RRF, 7/7   │  ← NO TOCAR, ya cerrado
                         └──────────────┬───────────────┘
                                        │
                         ┌──────────────▼───────────────┐
                         │  LLM de juicio (Ollama)        │
                         │  contrato formal prompt↔        │  ← Fase 3, P1
                         │  verificador (JSON Schema)      │
                         └──────────────┬───────────────┘
                                        │
                         ┌──────────────▼───────────────┐
                         │  VALIDACIÓN A (anclaje literal) │
                         │  evidence_verifier.py — NUNCA   │  ← intocable
                         │  reemplazada por el DOM         │
                         └──────────────┬───────────────┘
                                        │
                         ┌──────────────▼───────────────┐
                         │  B/C/D + DOCUMENTATION_GAP      │
                         │  (NO_SIGNAL real) — sin cambio   │  ← intocable
                         └──────────────┬───────────────┘
                                        │
                         ┌──────────────▼───────────────┐
                         │  Revisión humana (QA/Cesar)     │  ← siempre humana
                         └─────────────────────────────┘
```

## Principio arquitectónico central de este documento

**El DOM/EvidenceUnit es siempre una vista adicional sobre el texto
plano, nunca un reemplazo del objeto de verdad.** `evidence_verifier.
match_citation()` sigue comparando contra `chunk['text']` sin importar
cuántas capas de estructura se agreguen encima para construir el prompt
o para servir de provenance. Esto es lo que garantiza que ninguna
"mejora de representación" pueda debilitar accidentalmente el anclaje
literal — la restricción dura del brief (A.3) queda satisfecha por
construcción, no por disciplina.

## Dos ejes independientes, explícitamente no fusionados

1. **Eje de recuperación/extracción** — RESUELTO (R2, retrieval 7/7).
   No se toca.
2. **Eje de juicio del modelo sobre evidencia parafraseada (P2/P5)** —
   confirmado como límite del modelo, no de pipeline. No se ataca con
   arquitectura de representación — cualquier intento de "resolver" esto
   con un DOM repetiría el error de diseño ya corregido en R2.
3. **Eje de dilución tabular (P6/P7)** — causa DISTINTA, no confirmada,
   con ratio de ruido medido real (~95%+ tabla en la página de P6). Único
   eje donde el DOM tiene una hipótesis de trabajo razonable, sujeta al
   experimento barato de `EXPERIMENT_PLAN.md` antes de construir nada.

Tratar estos tres ejes como uno solo ("mejorar la representación mejora
el recall") fue exactamente el error de diseño que R2 corrigió para
recuperación vs. juicio — este documento aplica la misma disciplina para
no repetirlo entre P2/P5 y P6/P7.

## Capa de disciplina de Capa 8 (paralela, no bloqueante)

Contrato formal (P1, toca producto vía prevención de defectos de
integración) + disciplina de sesión adaptada de ECC (P2-P3, entorno,
nunca producto) — corre en paralelo a la Pista A, sin dependencia mutua.

## Bloque de cierre (§25)

```
ECC_NATURE_CONFIRMED       = agent harness / tooling de desarrollo — confirmado, no corregido
ECC_DOC_PROCESSING_VALUE   = NINGUNO — confirmado
INFORMATION_LOSS_MAP       = 6 transiciones documentadas; furniture asimétrico CORREGIDO (Bloque 1,
                              commit e271488); dilución tabular P4/P6/P7 REFUTADA como causa (ver abajo)
BOTTLENECK_CONCLUSION      = F (el modelo/LLM) para los 5 casos positivos fallidos del fixture
                              (P2, P4, P5, P6, P7) — CONFIRMADO, no hipótesis. P2/P5 vía R2 (3
                              mediciones independientes); P4/P6 vía experimento C real ejecutado
                              2026-08-15 (tabla removida por completo, prosa en contexto limpio
                              1670 chars/6.6%, mismo resultado que con tabla presente); P7
                              recalificado al mismo bucket (sin tabla real en su página). Ninguna
                              mejora de pipeline movió el resultado en ningún caso medido.
DOM_JUSTIFIED_ENTITIES     = Document/Section/Paragraph (ya existen, uso ya vigente en Fase 4 de
                              generación de candidato). Table/EvidenceUnit: NO JUSTIFICADAS para
                              atacar recall de juicio — experimento real las refutó para P4/P6/P7,
                              y P2/P5 ya las había refutado (evidencia perfecta, juicio sin cambio).
                              Quedan como diseño válido SOLO si aparece un caso futuro distinto,
                              nunca como inversión justificada por la evidencia ya medida.
                              Figure/Heading/Reference: descartadas, sin caso real.
ANCHORING_PRESERVED_DESIGN = DOM como vista aditiva sobre chunk['text'], match_citation() sin cambio
                              (diseño preservado aunque su justificación de negocio cayó)
TABLE_REPRESENTATION       = pdfplumber.extract_tables() (sin dependencia nueva) — diseño válido,
                              construcción NO recomendada dado el resultado del experimento C real
FIFTH_VALIDATION_E         = RECHAZADA — cero casos reales encontrados
NO_SIGNAL_STATUS           = permanece; nombre real en código es DOCUMENTATION_GAP
ECC_ADOPTION_MATRIX        = 1 ADOPTAR / 2 ADAPTAR / 3 INSPIRAR / 3 RECHAZAR (9 evaluados)
ECC_PRODUCT_VS_TOOLING     = 1 de 9 fortalece producto (contract-first); 8 de 9 son entorno
PLUGIN_INSTALL              = NEVER — reafirmado, adopción siempre por reescritura
EXPERIMENT_COST             = 4 llamadas LLM reales ejecutadas en total (P4/P6 sin aislar +
                              P4/P6 aislado, todas bajo PILOT_EXECUTION-2026-010, checkpoints
                              preservados), sobre un máximo de 25 autorizadas en esa instancia.
                              Sin nueva PILOT_EXECUTION propuesta.
DELIVERABLES                = 12 documentos, este incluido
CODE_CHANGED                = chunked_engine.py + evidence_verifier.py (Bloque 1, commit e271488);
                              factory/tests/test_checkpoint_finding_contract.py (Bloque 3, commit
                              fa25c9d); ningún archivo de DO_NOT_TOUCH.md modificado como objeto
                              de verificación/gobernanza (solo aditivo)
DEPENDENCIES_ADDED          = 0
COMMITS                     = 2 reales (e271488 Bloque 1, fa25c9d Bloque 3) + este documento y sus
                              actualizaciones, pendientes de decisión de commit de documentación
```

Auditoría original DETENIDA tras entregar los 12 documentos, según lo
pactado. Los Bloques 0-3 de `docs_plan/CONTINUACION_FASE0_P4_FASE1.md`
(cierre de P4, fix de furniture, verificación mecánica, contrato formal,
y el experimento C real que responde la pregunta central §23 de la
auditoría original) se ejecutaron en corridas posteriores, cada paso con
aprobación explícita separada de Cesar, según el protocolo ya
establecido. Ninguna implementación adicional (DOM, `Table`,
`EvidenceUnit`, Tier-1, o cualquier otra línea de `IMPLEMENTATION_PLAN.md`)
comienza sin nueva aprobación explícita.
