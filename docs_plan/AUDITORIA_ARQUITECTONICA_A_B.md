# AUDITORÍA ARQUITECTÓNICA — DOS PISTAS INDEPENDIENTES
# Pista A: Representación documental (prioridad real)
# Pista B: Adopción de patrones ECC (disciplina de Capa 8)
#
# Archivo de instrucciones para Claude Code
# Destino: docs_plan/AUDITORIA_ARQUITECTONICA_A_B.md
# Ejecutar: cd /home/ing_cpmo && claude
#
# AUTORIDAD: Capa 9 = Cesar. Claude Code = Capa 8.
#
# FASE EXCLUSIVA DE AUDITORÍA Y DISEÑO. PROHIBIDO: implementar código;
# agregar dependencias; cambiar prompts, agentes, pipeline, validadores,
# corpus o reglas GMP; hacer commits de código; instalar plugins.
#
# PRODUCTION_ENABLEMENT = BLOCKED. CORPUS_READY = false.

──────────────────────────────────────────────────────────────────────────────
0. HALLAZGO PREVIO QUE ESTRUCTURA ESTA AUDITORÍA (verificado, no asumido)
──────────────────────────────────────────────────────────────────────────────

ECC (github.com/affaan-m/ECC) fue inspeccionado directamente antes de
redactar estas instrucciones. Hechos verificados:

- ECC es un "agent harness operating system" para Claude Code: 284 skills,
  68 agentes, 94 comandos, 4 hooks, 2 plugins, 2 workflows.
- Es TOOLING DE DESARROLLO. NO es un sistema de procesamiento documental.
- Capacidades documentales en 284 skills: únicamente
  `nutrient-document-processing` (wrapper de SDK comercial) y
  `visa-doc-translate`. CERO extracción de PDF, kerning, tablas u OCR.

CONSECUENCIA ESTRUCTURAL: buscar en ECC soluciones para §5-§16 del brief
(normalización documental, PDF, tablas, OCR, DOM) devolverá vacío. Ese
trabajo es genuino y urgente, pero debe diseñarse de forma INDEPENDIENTE.

Por eso esta auditoría corre en DOS PISTAS que no se bloquean entre sí.
Si al inspeccionar ECC encuentras capacidad documental real que esta nota
no detectó, repórtala con archivo y ruta — pero NO fuerces conexiones
para llenar la matriz. Una celda "ECC no aporta aquí" es un resultado
válido y valioso.

──────────────────────────────────────────────────────────────────────────────
PISTA A — REPRESENTACIÓN DOCUMENTAL (prioridad; independiente de ECC)
──────────────────────────────────────────────────────────────────────────────

## A.1 Análisis de pérdida de información (§10 del brief)

Recorrer el pipeline REAL y documentar, transición por transición, qué se
pierde — con evidencia del código y de los checkpoints ya existentes, no
por especulación:

ORIGINAL → EXTRACCIÓN → NORMALIZACIÓN → CHUNKING → RETRIEVAL → LLM →
VALIDACIÓN

Por cada transición: pérdida de texto / estructura / posición / contexto /
relaciones / tablas / referencias / provenance / semántica.

Usar casos REALES ya medidos como evidencia:
- "wheneve r" (kerning) — pérdida de texto en extracción
- U+F0B7 (viñetas de fuente privada) — ruido de formato
- P3: chunk 45-46 mezcla retención con Historian/Audit Trail — pérdida de
  cohesión temática por chunking
- P6/P7: prosa real diluida en chunk multipágina dominado por tablas de
  I/O — pérdida de relación fila→columna→encabezado→valor
- Evidencia distribuida entre páginas (motivo de B3)

## A.2 Diagnóstico del cuello de botella (§13, §23 — pregunta central)

Determinar CON EVIDENCIA, no por suposición, cuánto del fallo en
P2/P4/P5/P7 proviene de: extracción / representación / chunking /
retrieval / contexto / ausencia de estructura / el LLM.

Dato ya disponible que acota la respuesta: la fusión BM25+embeddings
alcanzó 7/7 at_5 — es decir, la RECUPERACIÓN ya no es el cuello. P2 y P5
llegaron al top-5 del pool y el modelo AUN ASÍ no los reconoció (0/2,
PILOT_EXECUTION-2026-012). Eso acota el problema a: representación del
contexto entregado al modelo, o límite del modelo.

Hipótesis a evaluar con los datos ya pagados (checkpoints históricos,
cero llamadas LLM): ¿el chunk que recibió el modelo en P6/P7 contenía la
oración de prosa relevante sepultada en ruido tabular? Si sí, una
representación estructurada que aísle esa oración como EvidenceUnit
podría cambiar el resultado SIN cambiar el modelo. Cuantificar la señal:
ratio de tokens relevantes vs. ruido en los chunks de los casos fallidos.

## A.3 Diseño del Document Object Model y EvidenceUnit (§9, §11)

Evaluar y proponer (no implementar) la representación intermedia:
Document / Section / Paragraph / List / Table / TableRow / TableCell /
Figure / Heading / Reference / EvidenceUnit.

Criterio de decisión: cada entidad se justifica SOLO si mejora
medibliemente retrieval, anclaje, manejo de tablas o trazabilidad. Las
que no, se descartan — regla anti-sobreingeniería (§27).

Provenance obligatorio por unidad: document_id, original_sha256, page,
section_id, position, content_type, derived_sha256, source_location.

RESTRICCIÓN DURA: la validación A (anclaje literal) debe seguir
funcionando. Si el texto se reestructura, el anclaje debe poder
verificarse contra el ORIGINAL, no solo contra la representación
derivada — de lo contrario se rompe el principio "cita anclada al
documento original". Diseñar el mapeo derivado→original que lo garantice.

## A.4 Tablas (§14, caso P6)

Diseñar la representación tabular que preserve encabezado/fila/columna/
celda/unidad/posición/página. Evaluar cómo un agente consulta esa
estructura (¿la tabla se serializa para el prompt? ¿se consulta por celda?
¿se genera una descripción textual derivada con provenance?).

## A.5 Formatos y OCR (§8, §15)

Estrategia por formato (PDF texto / PDF escaneado / DOCX / XLSX / CSV /
PPTX / HTML). Estados: extraction_success, extraction_partial,
OCR_REQUIRED, OCR_COMPLETED, EXTRACTION_UNCERTAIN, DOCUMENT_UNREADABLE.
OCR nunca se presenta como evidencia fiable sin declarar su provenance y
limitación.

## A.6 Evaluación de conversores (§7)

Comparar conceptualmente A) extractor actual, B) MarkItDown, C)
extracción estructurada, D) híbrida, E) representación propia — contra
los criterios del §7 del brief. Recordar el hallazgo ya documentado:
MarkItDown pierde límites de página, y todo el anclaje del sistema es por
página; sin mapeo página↔unidad no es adoptable.

## A.7 Quinta validación (§17)

Evaluar si "E. Evidence provenance / contextual validity" se justifica.
Criterio: solo se añade si cubre un fallo real que A/B/C/D no cubren, con
un caso concreto del proyecto que lo demuestre. Si no hay caso, se
rechaza explícitamente. NO debilitar A/B/C/D bajo ninguna circunstancia.

## A.8 NO_SIGNAL (§11, restricción explícita de Cesar)

NO eliminar NO_SIGNAL porque exista alternativa. Si se propone una
arquitectura de Evidence Graph que lo reemplace, DEMOSTRAR primero —con
los casos reales de B3 y con los negativos N1/N2— que no introduce falsos
positivos. Sin esa demostración, NO_SIGNAL permanece.

──────────────────────────────────────────────────────────────────────────────
PISTA B — ADOPCIÓN DE PATRONES ECC (alcance honesto: Capa 8)
──────────────────────────────────────────────────────────────────────────────

## B.1 Inspección dirigida (no exhaustiva de 284 skills)

Inspeccionar en profundidad SOLO los patrones con relevancia plausible
para este proyecto. Candidatos identificados en la inspección previa:

| Skill/patrón ECC | Por qué es candidato |
|---|---|
| `delivery-gate` | Stop hook con checks DETERMINISTAS (sin inferencia IA) que bloquea declarar trabajo terminado — alineado con la filosofía de gates del proyecto |
| `ai-regression-testing` | "guards fixed bugs from returning" — directo a la cadena B3→B4→B5 |
| `eval-harness` | EDD, pass@k, suites de regresión — formaliza el fixture set 7P+2N |
| `verification-loop` | Verificación sistemática antes de declarar completo — atacaría los 3 falsos cierres de R3-T1 |
| `agent-self-evaluation` | Autoevaluación en 5 ejes con evidencia por criterio |
| `contract-first` | Previene drift de schema entre productor y consumidor — el defecto de contrato de prompt (Causa 2) |
| `iterative-retrieval` | Refinamiento progresivo de contexto — evaluar contra la fusión ya medida 7/7 |
| `agent-architecture-audit` / `workspace-surface-audit` | Patrones de auditoría de superficies — relacionado con el hallazgo de rutas duplicadas |
| `hooks/memory-persistence` | Persistencia de contexto entre sesiones |

Ampliar la lista SOLO si la inspección revela otros con caso de uso claro.
No inventariar los 284.

## B.2 Matriz de adopción (§4 del brief)

| Componente ECC | Qué hace | Fortaleza | Equivalente GMP actual | ADOPTAR/ADAPTAR/INSPIRAR/RECHAZAR | Beneficio | Riesgo | Ubicación propuesta | Prioridad P0-P3/REJECT |

Regla de evaluación obligatoria por fila (§24): "¿esto fortalece el
PRODUCTO GMP o solo hace más sofisticado el entorno de desarrollo?"
Si es lo segundo, puede seguir siendo valioso (la disciplina de desarrollo
ha sido el cuello de botella real del proyecto) — pero se etiqueta como
tal, sin disfrazarlo de mejora de producto.

## B.3 PROHIBICIÓN DE INSTALACIÓN MAYORISTA (riesgo de gobernanza)

PROHIBIDO ejecutar `/plugin marketplace add` o `/plugin install ecc@ecc`.
Motivo: inyectaría 284 skills y 68 agentes en el contexto de Claude Code
dentro de un sistema GMP bajo control de cambios, con riesgo de:
- interferencia con los skills propios del proyecto (gmp-recall-pipeline,
  gmp-implement, gmp-read-evidence, gmp-status, gmp-layer8-agent);
- alteración impredecible del comportamiento del agente a mitad de un
  arco de trabajo;
- dependencia externa no auditada en el entorno que construye un sistema
  regulado.
La adopción, si Cesar la aprueba, es SIEMPRE reescribiendo el patrón como
skill propio del proyecto, con su origen citado (licencia MIT) y adaptado
a las reglas GMP. Nunca copia mayorista.

## B.4 Filtro de gobernanza IA (§19)

Todo patrón de ECC relacionado con memoria, auto-mejora, hooks,
automatización o modificación automática se evalúa contra: ningún
mecanismo automático puede aprobar cumplimiento, aprobar un hallazgo,
modificar el corpus, modificar una decisión humana, firmar, impersonar un
aprobador, generar una RemediationDirective, ni modificar el original.
Cualquier patrón que roce esto ⇒ RECHAZAR o ADAPTAR con el control
explícito que lo impida.

──────────────────────────────────────────────────────────────────────────────
EXPERIMENTO A/B/C (§21) — DISEÑO, NO EJECUCIÓN
──────────────────────────────────────────────────────────────────────────────

Diseñar el experimento con el fixture 7P+2N, mismo modelo, mismos
prompts, mismo corpus:
  A: extractor actual → retrieval actual → LLM
  B: nueva normalización → retrieval actual → mismo LLM
  C: representación estructurada → evidence units → retrieval/reranking →
     mismo LLM

Métricas: extraction fidelity, structure preservation, retrieval recall,
evidence recall, criterion recall, anchoring, semantic validation,
conclusión final, falsos positivos, falsos negativos.

CRITERIO INVIOLABLE: N1 (ANNEX11_4) y N2 (weak keyword) DEBEN seguir
rechazándose. Una mejora que sube recall y rompe los negativos NO es una
mejora — se descarta.

DIMENSIONAMIENTO HONESTO: calcular el costo en llamadas LLM de cada brazo
(A ya está medido; B y C requieren corridas nuevas). Aplicar el patrón ya
probado del proyecto: cuánto se puede responder por REPLAY sobre
checkpoints ya pagados antes de gastar una sola llamada nueva. Proponer
el experimento en fases (barato primero), nunca como corrida única larga.

──────────────────────────────────────────────────────────────────────────────
ENTREGABLES (§25)
──────────────────────────────────────────────────────────────────────────────

En docs_plan/AUDITORIA_ARQUITECTONICA_2026-08/:

Pista A (prioridad):
  B. DOCUMENT_NORMALIZATION_ARCHITECTURE.md
  C. EVIDENCE_ARCHITECTURE.md
  + INFORMATION_LOSS_ANALYSIS.md (A.1 — no estaba en la lista del brief
    pero es la base de todo lo demás)
  + BOTTLENECK_DIAGNOSIS.md (A.2 — la conclusión explícita del §23)

Pista B:
  A. ECC_ADOPTION_MATRIX.md
  D. CONTEXT_ENGINEERING_ARCHITECTURE.md

Transversales:
  E. EXPERIMENT_PLAN.md
  F. IMPLEMENTATION_PLAN.md
  G. DO_NOT_TOUCH.md
  H. TEST_PLAN.md
  I. RISK_REGISTER.md
  J. TARGET_ARCHITECTURE.md

DO_NOT_TOUCH.md debe incluir como mínimo: gmp-api:8000 completo;
path_policy.py; decision_scope_resolver.py; candidate_validity.py;
evidence_verifier.py (validación A); semantic_evidence_verification.py
(C y D); los prompts YAML gobernados; requirements.yaml; el corpus
regulatorio; decisions_v2.jsonl; la cadena de auditoría; los originales
de GMPAI/source/Rockwell/.

──────────────────────────────────────────────────────────────────────────────
NOTA SOBRE EL BRIEF: DATO FALTANTE
──────────────────────────────────────────────────────────────────────────────

El §2 del brief tiene un marcador sin rellenar:
"[COLOCAR AQUÍ LA URL REAL DEL REPOSITORIO GMP AI FACTORY]".
El repositorio GMP vive localmente en /home/ing_cpmo (no hay URL remota
conocida). Usar el árbol local como fuente de verdad y decirlo así en los
entregables — no inventar una URL ni asumir un remoto.

──────────────────────────────────────────────────────────────────────────────
ENTREGA Y CIERRE
──────────────────────────────────────────────────────────────────────────────

```
ECC_NATURE_CONFIRMED =        (agent harness / tooling — o corrección
                              si la inspección encuentra otra cosa)
ECC_DOC_PROCESSING_VALUE =    (esperado: NINGUNO — confirmar o refutar)
INFORMATION_LOSS_MAP =        (por transición, con casos reales)
BOTTLENECK_CONCLUSION =       (A/B/C/D/E/F del §23, CON EVIDENCIA)
DOM_JUSTIFIED_ENTITIES =      (cuáles sí, cuáles se descartan y por qué)
ANCHORING_PRESERVED_DESIGN =  (cómo la validación A sobrevive al DOM)
TABLE_REPRESENTATION =        (diseño para P6)
FIFTH_VALIDATION_E =          (justificada con caso real / rechazada)
NO_SIGNAL_STATUS =            (permanece salvo demostración contraria)
ECC_ADOPTION_MATRIX =         (nº P0/P1/P2/P3/REJECT)
ECC_PRODUCT_VS_TOOLING =      (cuántos fortalecen producto vs. entorno)
PLUGIN_INSTALL =              NEVER (prohibido; adopción por reescritura)
EXPERIMENT_COST =             (llamadas por brazo; qué se responde gratis)
DELIVERABLES =                (12 documentos)
CODE_CHANGED =                0
DEPENDENCIES_ADDED =          0
COMMITS =                     0 (salvo el commit de documentación, propuesto)
```

DETENERSE tras entregar los 12 documentos. Ninguna implementación
comienza sin aprobación explícita de Cesar. La prioridad absoluta es
fortalecer GMP AI Factory sin perder ningún control, trazabilidad,
principio de gobernanza ni autoridad humana existente.
