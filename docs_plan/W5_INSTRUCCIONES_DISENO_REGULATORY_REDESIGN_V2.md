# W5 V2 — REDISEÑO REGULATORIO, RUNTIME HÍBRIDO Y GENERACIÓN OBLIGATORIA
# DE DOCUMENTOS CORREGIDOS — GMP AI FACTORY
# PLAN CONSOLIDADO (integra W5 original + instrucciones adicionales V2)
#
# Archivo de instrucciones para Claude Code
# Destino en servidor: docs_plan/W5_INSTRUCCIONES_DISENO_REGULATORY_REDESIGN_V2.md
# Ejecutar: cd /home/ing_cpmo && claude
# Fecha de planificación: 2026-07-22
#
# AUTORIDAD
# Capa 9: Cesar.
# Claude Code opera como Capa 8: inspección, diseño, desarrollo futuro,
# pruebas y mantenimiento. Claude Code NO forma parte del runtime permanente.

──────────────────────────────────────────────────────────────────────────────
0. RELACIÓN CON W5 ORIGINAL Y RESOLUCIÓN DE CONTRADICCIONES
──────────────────────────────────────────────────────────────────────────────

Este documento CONSOLIDA y REEMPLAZA operativamente a
docs_plan/W5_INSTRUCCIONES_DISENO_REGULATORY_REDESIGN.md para efectos de
ejecución. El W5 original NO se modifica ni se borra; queda como registro de
planificación. Todo objetivo, control y entregable de W5 está incorporado
aquí, ampliado por las instrucciones V2.

Resoluciones explícitas (V2 prevalece donde hay conflicto):

R-1 MODO DE EJECUCIÓN. W5 tenía 5 checkpoints con pausa. V2 exige una sola
    ejecución continua sin aprobaciones intermedias. PREVALECE V2 para esta
    corrida de diseño. Solo detenerse ante: (a) secretos detectados;
    (b) riesgo de modificar originales; (c) contradicción técnica que impida
    un diseño coherente; (d) decisión de alcance no resoluble desde el
    código. En los demás casos: registrar la limitación y continuar.

R-2 MODELO DE APROBACIÓN HUMANA. W5 exigía aprobación humana por cada gap y
    por cada texto antes de entrar al candidato. V2 lo sustituye por revisión
    por excepción: cambios LOW_RISK que aprueben TODOS los gates entran al
    borrador como AUTO_APPLIED_TO_DRAFT; la decisión humana se concentra en
    el paquete final de QA y en las excepciones. PREVALECE V2. Este cambio NO
    debilita la gobernanza porque: el candidato es un BORRADOR, nunca un
    documento liberado; toda aplicación automática queda auditada con
    change_id y trazabilidad completa; la conformidad documental y la
    liberación siguen siendo decisiones exclusivamente humanas
    (decision_origin=human_confirmed, approved_by real, 422 para identidades
    genéricas, 409 para doble aprobación). Aprobación humana ANTICIPADA solo
    para: fuente nueva/actualizada, nueva versión de Evidence Pack, cambio
    material de aplicabilidad, documento sin procedencia, excepción crítica
    que impida un candidato coherente.

R-3 COMMITS. W5 permitía proponer commits con aprobación. V2 prohíbe todo
    commit en esta ejecución. PREVALECE V2: cero commits; los commits futuros
    solo se PROPONEN en el cierre.

R-4 ENTREGABLES Y RUTA. W5 producía 11 documentos en
    factory/docs/design/regulatory_redesign_v1/. V2 produce 18 documentos en
    factory/docs/design/regulatory_redesign_v2/. PREVALECE V2. Los 11 de W5
    están contenidos en los 18 (algunos renombrados/divididos).

R-5 FASES. W5 definía fases A–I (9). V2 define A–P (16) con mayor
    granularidad. PREVALECE V2. Mapeo obligatorio en el roadmap:
    W5-A→V2-A | W5-B→V2-B+C | W5-C→V2-E | W5-D→V2-F+G | W5-E→V2-H |
    W5-F→V2-I | W5-G→V2-J+K+L+M+N | W5-H→V2-O | W5-I→V2-G+P.
    V2-D (ModelProvider/runtime) es alcance NUEVO sin equivalente en W5.

R-6 SANITIZACIÓN DEL REPORTE URS v2.1. Bloque 0.2 de W5 (verificación del
    reporte de validación) SE CONSERVA como verificación de solo lectura
    dentro de esta corrida; el commit de documentación queda solo PROPUESTO.

Alcance NUEVO aportado por V2 (sin contradicción, se integra):
runtime independiente de Claude Code; abstracción ModelProvider; servicio de
inferencia compartido; salida LLM estructurada con reparación única;
clasificación de riesgo y autoaplicación gobernada; generación OBLIGATORIA
del documento corregido completo por formato (DOCX/PDF/XLSX/DOCM);
CORRECTED_DOCUMENT_GENERATION_GATE; fail-closed; Model Qualification Gate;
controles de rendimiento; paquete final QA con 4 decisiones; auditoría del
runtime actual de agentes.

──────────────────────────────────────────────────────────────────────────────
1. OBJETIVO
──────────────────────────────────────────────────────────────────────────────

Diseñar (sin implementar) una solución que:

- analice de forma gobernada todos los documentos originales de Rockwell;
- los compare contra fuentes regulatorias oficiales, verificadas y
  versionadas;
- identifique hallazgos, gaps y desviaciones con explicación de por qué el
  contenido no atiende el requisito;
- genere correcciones documentales trazables;
- incorpore automáticamente al borrador las correcciones suficientemente
  validadas (revisión humana por excepción);
- produzca OBLIGATORIAMENTE, por cada documento remediable, una nueva
  versión completa del documento corregido más su paquete de artefactos.

El resultado operativo futuro NO puede limitarse a reportes,
recomendaciones, fragmentos, matrices o Markdown. Por documento remediable:

1. Documento candidato completo con correcciones validadas.
2. Redline completo frente al original.
3. Reporte de hallazgos, gaps y desviaciones.
4. Matriz de trazabilidad.
5. Reseña de cambios y fundamento regulatorio.
6. Paquete de excepciones.
7. Manifest con hashes y fingerprint.
8. Reporte de revalidación independiente.
9. Reporte de calidad final.
10. Paquete completo para decisión humana de QA.

Cada corrección indica: qué se modificó, por qué, cómo atiende
documentalmente el requisito, qué regulación y numeral la sustentan y la URL
oficial de la fuente.

La solución produce conformidad documental DEMOSTRABLE y trazable. NUNCA
declara automáticamente cumplimiento regulatorio integral ni libera
documentos. La decisión final permanece en QA humana autorizada.

──────────────────────────────────────────────────────────────────────────────
2. REGLAS PARA ESTA EJECUCIÓN DE CLAUDE CODE
──────────────────────────────────────────────────────────────────────────────

Esta ejecución es EXCLUSIVAMENTE de auditoría y diseño.

PROHIBIDO:
- implementar código;
- llamar a Ollama;
- descargar regulaciones;
- generar documentos candidatos Rockwell reales;
- modificar archivos originales;
- modificar paquetes ni auditoría histórica;
- realizar commits;
- modificar el W5 original;
- ejecutar macros de archivos DOCM;
- escribir dentro de /home/ing_cpmo/GMPAI/source/Rockwell/.

PERMITIDO:
- inspeccionar código y artefactos reales en modo lectura;
- ejecutar comandos de inventario, búsqueda, hashes y validación de solo
  lectura;
- crear documentos Markdown de diseño en
  factory/docs/design/regulatory_redesign_v2/;
- proponer componentes, schemas, pruebas, fases y commits futuros.

Todo el diseño en UNA SOLA ejecución. Sin pausas intermedias salvo las 4
condiciones de R-1. Todos los entregables deben pasar el criterio de
sanitización (sección 3.2) antes del cierre.

PRODUCTION_ENABLEMENT = BLOCKED
REGULATORY_COMPLIANCE = NOT_DETERMINED

──────────────────────────────────────────────────────────────────────────────
3. BASELINE TÉCNICO CONFIRMADO Y PRECONDICIONES
──────────────────────────────────────────────────────────────────────────────

## 3.1 Hechos aceptados (no re-auditar salvo contradicción con archivo,
## función, línea y contenido)

1. Ollama usa httpx únicamente contra endpoints locales (/api/generate,
   /api/tags). Sin salida a internet.
2. Ollama no navega, no abre URLs, no descarga regulaciones.
3. La gestión/descarga de fuentes regulatorias ocurre en componentes
   separados de la inferencia: factory/regulatory/sources/, catálogo
   regulatorio, matriz de aplicabilidad, conectores, evidence_verifier.py.
4. Las 121 llamadas del URS = 11 requirement_id × 11 chunks.
5. Ollama recibió principalmente requirement_id + descripción breve +
   fragmento del URS.
6. No recibió texto normativo canónico completo ni Evidence Pack completo.
7. evidence_verifier.py valida existencia literal de la cita en el
   documento; no demuestra suficiencia regulatoria.
8. ANNEX11_4: falso positivo semántico confirmado — "GAMP5 A Risk-Based
   Approach" en lista de referencias no demuestra gestión de riesgos.
9. PIPELINE_QUALITY_IMPROVED = PARTIAL (2 sustantivas, 6 de proceso, 1
   falso positivo probable, 1 limitación compartida).
10. Pendientes: 25 review_required; 3 rejected_by_verifier; baseline
    formal; documento corregido completo; revalidación completa.
    FORMAL_BASELINE_READY=false; SAFE_TO_USE_AS_BASELINE=false;
    REGULATORY_COMPLIANCE=NOT_DETERMINED.
11. Claude Code es herramienta de desarrollo. Los agentes desplegados deben
    funcionar con Claude Code cerrado.

## 3.2 Verificación de sanitización (conservada de W5, solo lectura)

Sobre factory/docs/gmpai_reanalysis/urs_v2_1/
VALIDACION_STATUS_URS_V2_1_2026-07-22.md:

```bash
F=factory/docs/gmpai_reanalysis/urs_v2_1/VALIDACION_STATUS_URS_V2_1_2026-07-22.md
ls -la "$F" && sha256sum "$F"
grep -nEi 'sk-ant|GMP_API_KEY|FACTORY_API_KEY|ANTHROPIC_API_KEY|POSTGRES_PASSWORD|api[_-]?key|password|token' "$F" || echo "SIN_PATRONES_DE_SECRETOS"
grep -nEi 'raw_response|"response"\s*:|BEGIN RAW' "$F" || echo "SIN_RAW_RESPONSES"
```

Confirmar además por inspección: sin citas Rockwell extensas (>25 palabras
contiguas), sin raw responses de Ollama, sin credenciales embebidas.
Resultado: REPORT_SANITIZED = true | false | REQUIRES_HUMAN_REVIEW.
Si false o REQUIRES_HUMAN_REVIEW con secretos: DETENERSE (condición R-1a).
Si true: incluir en el cierre la PROPUESTA (no ejecución) de un commit
independiente de documentación, separado de los entregables W5 V2.

El mismo criterio de sanitización aplica a los 18 entregables generados.

──────────────────────────────────────────────────────────────────────────────
4. AUDITORÍA DEL RUNTIME ACTUAL
──────────────────────────────────────────────────────────────────────────────

Entregable: CURRENT_AGENT_RUNTIME_AUDIT.md

Inspecciona el código real para determinar:
- cuántos agentes están realmente implementados;
- cuáles existen solo como perfiles, documentos o diseño;
- cuáles son deterministas, cuáles llaman a Ollama, cuáles híbridos;
- qué runner, API u orquestador los ejecuta;
- si funcionan con Claude Code cerrado;
- qué lógica está acoplada directamente a Ollama;
- qué componentes pueden reutilizarse en W5 V2.

Revisar inicialmente (y cualquier otro agente encontrado en código):
doc_inventory_version_agent; doc_classification_agent; fda_part11_agent;
eu_annex11_agent; alcoa_plus_agent; requirements_traceability_agent;
compliance_risk_agent; final_review_agent.

Clasificación por implementación:
IMPLEMENTED | PARTIALLY_IMPLEMENTED | CONFIGURED_ONLY | DESIGN_ONLY

Clasificación por runtime:
DETERMINISTIC | HYBRID | LLM_BACKED | HYBRID_INDEPENDENT | HUMAN_ROLE

Matriz obligatoria (cada fila con referencia de archivo real; PROHIBIDO
declarar implementado lo que solo existe en documentación):

AGENTE ACTUAL → ARCHIVO → RESPONSABILIDAD REAL → TIPO DE RUNTIME → USA LLM
→ ORQUESTADOR → AGENTE W5 DESTINO → CAPACIDAD REUTILIZABLE → CAPACIDAD
FALTANTE

──────────────────────────────────────────────────────────────────────────────
5. ARQUITECTURA OBJETIVO DE 11 AGENTES + QA HUMANA
──────────────────────────────────────────────────────────────────────────────

Entregables: AGENT_RESPONSIBILITY_ARCHITECTURE.md y
TARGET_REGULATORY_PIPELINE_ARCHITECTURE.md

| agent_id | Responsabilidad | Runtime objetivo |
|---|---|---|
| AGT-INV | Inventario, procedencia, hashes, duplicados, allowlist | DETERMINISTIC |
| AGT-APP | Aplicabilidad documento × tipo documental × requirement_id | HYBRID |
| AGT-RSG | Gobernanza de fuentes regulatorias (URL, versión, vigencia, SHA-256) | DETERMINISTIC |
| AGT-REP | Construcción de Requirement Evidence Packs | DETERMINISTIC |
| AGT-EVD | Localización y contextualización de evidencia documental | HYBRID |
| AGT-VER | Validación de anclaje, fuente, semántica y suficiencia (A/B/C/D) | HYBRID |
| AGT-GAP | Clasificación de hallazgos, gaps, desviaciones, contradicciones | HYBRID |
| AGT-REM | Generación de correcciones documentales trazables | HYBRID |
| AGT-QLT | Validación regulatoria, técnica, lógica, lingüística, terminológica | HYBRID |
| AGT-DOC | Documento candidato completo + artefactos | HYBRID |
| AGT-RVL | Revalidación independiente original vs. candidato | HYBRID_INDEPENDENT |
| QA-HUM | Rol humano final: conformidad y liberación | HUMAN_ROLE |

Reglas de arquitectura:
- Prohibido concentrar la solución en un único agente.
- Los híbridos usan LLM SOLO cuando la tarea requiera comprensión semántica,
  comparación contextual o redacción.
- AGT-RVL nunca comparte lógica de decisión con AGT-REM ni consume sus
  conclusiones intermedias; solo compara artefactos finales contra baseline.
- AGT-RSG opera FUERA de la inferencia (descargas asíncronas aprobadas por
  humano).
- Ningún agente escribe en source/Rockwell/. Todo acceso a rutas vía
  factory/core/path_policy.py (sin superficies de path paralelas).
- Separación Reader/Executor: endpoints GET jamás escriben en la cadena de
  auditoría; POST audita exactamente un evento con run_by real.

Para CADA agente definir: agent_id; agent_version; responsabilidad;
entradas; salidas; input_schema; output_schema (con schema_version);
dependencias; permisos (rutas lectura/escritura vía path_policy);
herramientas autorizadas; función determinista; función de la LLM; estados
permitidos; estados prohibidos; validadores; eventos de auditoría (nombre +
payload mínimo); fallback; criterios de aceptación.

Pipeline objetivo (TARGET_REGULATORY_PIPELINE_ARCHITECTURE.md):

```
AGT-INV → AGT-APP → AGT-RSG ⇢ AGT-REP → AGT-EVD → AGT-VER(A,B,C,D)
  → AGT-GAP → AGT-REM → AGT-QLT → AGT-DOC → AGT-RVL
  → paquete final → QA-HUM
```

Con: puntos de bloqueo determinista; puntos de aprobación humana anticipada
(solo los 5 casos de R-2); artefactos intermedios y ubicación; componentes
actuales reutilizados (según sección 4); flujo de excepciones (sección 13).

──────────────────────────────────────────────────────────────────────────────
6. RUNTIME INDEPENDIENTE DE CLAUDE CODE
──────────────────────────────────────────────────────────────────────────────

Se documenta en MODEL_PROVIDER_AND_LOCAL_AI_RUNTIME_SPEC.md y en la
arquitectura de pipeline.

Los agentes deben poder ejecutarse mediante: API; runner CLI; Mission
Control; orquestador interno; ejecución batch; tarea programada.

Claude Code PUEDE: diseñar, implementar, probar, depurar, mantener,
preparar commits.

Claude Code NO PUEDE: ser necesario para ejecutar una corrida; conservar el
estado de producción; ser necesario para checkpoint o resume; ser proveedor
LLM obligatorio; decidir conformidad; liberar documentos.

Resultado obligatorio: CLAUDE_CODE_REQUIRED_AT_RUNTIME = false

──────────────────────────────────────────────────────────────────────────────
7. MODELPROVIDER Y PORTABILIDAD ENTRE MODELOS
──────────────────────────────────────────────────────────────────────────────

Entregable: MODEL_PROVIDER_AND_LOCAL_AI_RUNTIME_SPEC.md

Interfaz desacoplada:

```
ModelProvider
├── OllamaProvider
├── OpenAICompatibleProvider
├── AnthropicProvider (solo con autorización explícita de Capa 9)
└── LocalCompatibleProvider
```

La lógica regulatoria de los agentes NO se acopla a Ollama.

Configuración por perfil: provider; endpoint; model_name; model_digest;
context_window; timeout; max_tokens; temperature; seed (cuando exista);
retry_policy; fallback_policy; prompt_version; schema_version.

NO crear 11 instancias ni 11 contenedores de Ollama. Diseñar un SERVICIO DE
INFERENCIA COMPARTIDO con: cola; prioridades; concurrencia configurable;
límites por modelo; timeout; checkpoint; resume; retry limitado; circuit
breaker; métricas; trazabilidad por llamada.

Cambiar de modelo NO requiere reprogramar el agente. Requiere: nuevo
fingerprint; ejecución del Golden Dataset; comparación contra baseline;
reporte de regresión; aprobación del nuevo perfil.

La especialización se denomina CONFIGURACIÓN Y VALIDACIÓN DEL AGENTE. No
llamarla fine-tuning cuando solo existan prompts, schemas, reglas, Evidence
Packs y validadores.

──────────────────────────────────────────────────────────────────────────────
8. USO DE IA LOCAL Y AUTORIDAD DETERMINISTA
──────────────────────────────────────────────────────────────────────────────

La IA local fortalece: comprensión semántica; comparación norma↔documento;
relación entre documentos; detección de contradicciones conceptuales;
explicación de gaps; generación de correcciones; revisión técnica y
lingüística; reseñas regulatorias; resumen ejecutivo.

El código determinista conserva autoridad sobre: inventario; hashes;
procedencia; duplicados; rutas; fuentes autorizadas; vigencia; schemas;
anclaje literal; cobertura; estados; manifests; consistencia; bloqueos;
auditoría.

NO llamar a una LLM para: calcular SHA-256; contar archivos; detectar
duplicados exactos; validar JSON; crear IDs; comprobar rutas; comparar
texto literal; calcular cobertura; ensamblar manifests básicos.

La LLM NUNCA puede: aprobar una fuente; alterar una fuente canónica;
inventar requirement_id; declarar aplicabilidad final sin reglas; declarar
cumplimiento regulatorio; liberar documentos; modificar originales; emitir
estados terminales sin validadores.

Toda salida LLM es un insumo estructurado y verificable, jamás un veredicto.

──────────────────────────────────────────────────────────────────────────────
9. ALCANCE COMPLETO DE ROCKWELL
──────────────────────────────────────────────────────────────────────────────

Entregable: ROCKWELL_SOURCE_INVENTORY_AND_SCOPE_SPEC.md

Reconocimiento de solo lectura permitido en esta corrida:

```bash
find /home/ing_cpmo/GMPAI/source/Rockwell/ -type f | wc -l
find /home/ing_cpmo/GMPAI/source/Rockwell/ -type f -printf '%p|%s\n' | sort
find /home/ing_cpmo/GMPAI/source/Rockwell/ -type f -exec sha256sum {} \; > /tmp/rockwell_sha_preview.txt
```

Registrar en el spec: total de archivos, extensiones, tamaños, duplicados
evidentes por SHA-256, formatos que requerirán OCR, presencia de DOCM.

SOURCE_BASELINE_ALLOWLIST cerrada. Formato propuesto (no crear todavía):
factory/regulatory/scope/source_baseline_allowlist.yaml

```yaml
- file_id: RW-0001
  path: <ruta relativa a source/Rockwell/>
  name: <nombre>
  extension: <ext>
  version: <declarada | NO_DISPONIBLE>
  size_bytes: <int>
  sha256: <hash>
  provenance: <origen declarado | NO_DISPONIBLE>
  doc_type: URS|FS|DS|SOP|PROTOCOL|REPORT|DRAWING|OTHER
  origin_class: ORIGINAL | DERIVED
  duplicate_of: <file_id | null>
  extraction_capability: TEXT_NATIVE | OCR_REQUIRED | NOT_EXTRACTABLE
  processing_state: <enum abajo>
  applicability: <enum abajo>
  related_requirements: [<requirement_id>...]
  justification: <obligatoria si NOT_APPLICABLE o EXCLUDED>
```

Estados permitidos (enum cerrado):
ORIGINAL_SOURCE_CONFIRMED | ORIGINAL_SOURCE_UNCONFIRMED | APPLICABLE |
NOT_APPLICABLE_WITH_JUSTIFICATION | DUPLICATE | OCR_REQUIRED |
PROCESSING_BLOCKED | HUMAN_REVIEW_REQUIRED | DERIVED_DOCUMENT_EXCLUDED

Reglas deterministas:
- Todo archivo del find aparece EXACTAMENTE una vez con un estado terminal.
  Test: count(find) == count(allowlist); diferencia > 0 ⇒ FAIL.
- Prohibido omitir archivos silenciosamente.
- Excluir como originales (DERIVED_DOCUMENT_EXCLUDED, con patrones de
  detección documentados por ruta/nombre/metadatos): reportes previos, JSON
  de findings, candidatos, redlines, manifests derivados, checkpoints, raw
  responses, reportes de remediación, documentos generados por Claude,
  resultados de Ollama, temporales (~$, .tmp, .bak, .swp).
- Todos los originales son INMUTABLES. Verificación periódica de SHA-256;
  divergencia ⇒ SOURCE_INTEGRITY_VIOLATION + bloqueo del pipeline + evento
  de auditoría. Escritura en source/Rockwell/ prohibida vía path_policy.
- NO ejecutar macros de archivos DOCM.

──────────────────────────────────────────────────────────────────────────────
10. GOBERNANZA DE FUENTES REGULATORIAS
──────────────────────────────────────────────────────────────────────────────

Entregable: REGULATORY_SOURCE_GOVERNANCE_SPEC.md

Registro regulatorio (evolución de factory/regulatory/sources/):

```yaml
- source_id: FDA-OOS-2022
  body: FDA
  regulation: "Investigating Out-of-Specification (OOS) Test Results"
  version: "2022"
  effective_date: <fecha>
  official_url: <URL oficial primaria>
  local_copy: factory/regulatory/sources/canonical/<source_id>/<archivo>
  sha256: <hash de la copia local>
  retrieved_at: <timestamp>
  retrieved_by: <identidad real>
  status: <enum abajo>
  supersedes: <source_id | null>
  reverification_due: <fecha>
  history: [<entradas inmutables de cambios aprobados>]
```

Solo fuentes oficiales primarias (FDA.gov, USP, ICH.org, ISPE/GAMP según
licencia). Corpus JAMÁS fabricado: si el PDF no está, estado
SOURCE_UNAVAILABLE + estructura de ingesta con PENDING_DOCUMENT.

Estados:
OFFICIAL_SOURCE_VERIFIED | LOCAL_CANONICAL_COPY_VERIFIED |
PENDING_REVERIFICATION | SUPERSEDED | REGULATORY_SOURCE_UNVERIFIED |
SOURCE_UNAVAILABLE

Reglas deterministas:
- La inferencia trabaja con copias locales gobernadas; Ollama sin internet.
- Conclusión positiva SOLO con fuente en LOCAL_CANONICAL_COPY_VERIFIED.
- Fuente no verificada ⇒ EVALUATION_INCOMPLETE + COMPLIANCE_NOT_DETERMINED
  para todos los requisitos dependientes; análisis bloqueado.
- Nueva versión detectada ⇒ PENDING_REVERIFICATION; NUNCA sustitución
  automática. Cambio de URL/versión/hash requiere aprobación humana
  (approved_by real) + entrada en history + auditoría.
- Copias canónicas inmutables (misma verificación de hash que Rockwell).
- Descargas fuera del proceso de inferencia.

──────────────────────────────────────────────────────────────────────────────
11. REQUIREMENT EVIDENCE PACK
──────────────────────────────────────────────────────────────────────────────

Entregable: REQUIREMENT_EVIDENCE_PACK_SPEC.md

Paquete obligatorio por requirement_id:

```yaml
evidence_pack:
  pack_version: <semver>
  requirement_id: <id>
  body: <organismo emisor>
  regulation: <nombre>
  regulation_version: <versión>
  clause: <numeral>
  canonical_text: <texto normativo canónico literal>
  context_before: <texto>
  context_after: <texto>
  governed_interpretation: <interpretación aprobada por humano>
  evidence_min_criteria: [<criterios de evidencia válida>]
  exclusion_criteria: [<qué NO cuenta como evidencia>]
  typical_insufficient_evidence: [<patrones típicos insuficientes>]
  weak_keywords: [<palabras que solas NO demuestran el requisito>]
  expected_doc_types: [URS|FS|SOP|...]
  applicability: <regla desde matriz de aplicabilidad>
  official_url: <URL>
  source_sha256: <hash de la copia canónica>
  source_status: <estado sección 10>
```

Regla dura (corrige baseline 3.1.5-6): una LLM NUNCA recibe únicamente
requirement_id + descripción breve.

El prompt regulatorio incluye obligatoriamente: texto normativo canónico;
contexto regulatorio suficiente; criterios mínimos; criterios de exclusión;
fragmento documental; ubicación exacta; SHA-256 del documento; schema de
salida; prohibición de inventar implementación; prohibición de declarar
cumplimiento; instrucción de responder INSUFFICIENT_CONTEXT cuando el
fragmento no alcance.

──────────────────────────────────────────────────────────────────────────────
12. VALIDACIÓN A/B/C/D Y SALIDA ESTRUCTURADA DE LA LLM
──────────────────────────────────────────────────────────────────────────────

Entregable: SEMANTIC_EVIDENCE_VERIFICATION_SPEC.md

## 12.1 Cuatro validaciones independientes

```
A. DOCUMENT_ANCHOR_VERIFICATION
   La cita existe literalmente en el documento original, anclada a
   página/sección/tabla/celda. (Evolución del evidence_verifier actual.)

B. REGULATORY_SOURCE_VERIFICATION
   El requisito, numeral y texto invocados existen en la copia canónica
   verificada (match contra canonical_text + clause del pack).

C. SEMANTIC_REQUIREMENT_VERIFICATION
   La evidencia responde realmente al requisito. La LLM asiste, pero reglas
   deterministas rechazan automáticamente:
   - weak_keywords aisladas;
   - menciones en listas de referencias/estándares (regla ANNEX11_4);
   - contenido fuera de contexto;
   - criterios de exclusión activados;
   - evidencia de otro documento;
   - inferencias sin soporte.
   Discrepancia regla-vs-LLM ⇒ SUPPORTING_EVIDENCE_UNDER_REVIEW (nunca
   aprobación).

D. SUFFICIENCY_VERIFICATION
   Cada evidence_min_criteria clasificado MET | NOT_MET | NOT_ASSESSABLE,
   con anclaje individual.

Evidencia sustantiva aceptada ⇔ A ∧ B ∧ C ∧ D.
```

## 12.2 Pruebas negativas obligatorias (Golden Dataset mínimo)

- ANNEX11_4: "GAMP5 A Risk-Based Approach" en lista de referencias ⇒ FAIL
  en C; jamás DOCUMENTED_AND_SUPPORTED.
- Cita inventada ⇒ FAIL en A.
- Evidencia de otro archivo (hash no coincide) ⇒ FAIL en A.
- Numeral inexistente ⇒ FAIL en B.
- Evidencia parcial ⇒ FAIL en D ⇒ máximo PARTIALLY_DOCUMENTED.
- Contradicción entre secciones ⇒ contradicción abierta, bloquea conclusión
  positiva.
- Ausencia con cobertura incompleta ⇒ EVALUATION_INCOMPLETE, nunca
  DOCUMENTATION_GAP.
- Evidencia fuera de contexto ⇒ FAIL en C.

## 12.3 Salida estructurada de la LLM

Toda llamada devuelve JSON validado por schema. Campos mínimos:
assessment; evidence_quote; evidence_location; matched_criteria;
unmet_criteria; exclusion_criteria_triggered; semantic_reasoning_summary;
contradictions; confidence_band; proposed_next_state; limitations.

- No solicitar ni almacenar cadena privada de razonamiento.
- semantic_reasoning_summary: breve, verificable, apto para auditoría.
- Salida inválida ⇒ LLM_OUTPUT_INVALID → UN único intento de reparación →
  EXCEPTION_REQUIRED si falla de nuevo.
- proposed_next_state es una PROPUESTA; solo los validadores deterministas
  emiten estados.

──────────────────────────────────────────────────────────────────────────────
13. HALLAZGOS, CONCLUSIONES, RIESGO Y AUTOMATIZACIÓN POR EXCEPCIÓN
──────────────────────────────────────────────────────────────────────────────

Entregable: GAP_DEVIATION_AND_REMEDIATION_MODEL.md

## 13.1 Taxonomía estricta

HALLAZGO (observación objetiva anclada) | GAP (requisito aplicable sin
evidencia suficiente) | DESVIACIÓN (evidencia que contradice el requisito o
el propio documento) | RECOMENDACIÓN (mejora no obligatoria) |
CAMBIO_DOCUMENTAL (modificación trazable a un gap/desviación).

## 13.2 Registro por documento × requisito aplicable

Campos: documento; SHA-256; ubicación; requirement_id; regulación; numeral;
cita normativa; URL; evidencia encontrada; cobertura (procesados/total);
hallazgo; gap; desviación; explicación de insuficiencia; impacto;
criticidad (CRITICAL/MAJOR/MINOR); recomendación; corrección propuesta;
limitaciones; evidencia de implementación pendiente; estado de validación.

Nunca declarar "no cumple" sin: requisito aplicable + evidencia revisada +
elemento faltante + razón de insuficiencia + cambio propuesto + fuente
regulatoria + evidencia de implementación pendiente.

## 13.3 Modelo de conclusiones (reglas deterministas)

DOCUMENTED_AND_SUPPORTED | PARTIALLY_DOCUMENTED |
SUPPORTING_EVIDENCE_UNDER_REVIEW | DOCUMENTATION_GAP |
DEVIATION_IDENTIFIED | IMPLEMENTATION_EVIDENCE_MISSING |
EVALUATION_INCOMPLETE | NOT_APPLICABLE | COMPLIANCE_NOT_DETERMINED

DOCUMENTATION_GAP solo cuando TODAS: fuente verificada
(LOCAL_CANONICAL_COPY_VERIFIED); aplicabilidad aprobada; cobertura
completa; 0 registros rechazados pendientes; 0 revisiones pendientes; 0
contradicciones abiertas; ausencia consolidada determinísticamente.

Separación permanente (nunca colapsar):
DOCUMENT_CONFORMANCE | IMPLEMENTATION_VERIFICATION | REGULATORY_COMPLIANCE
(la última, solo juicio humano).

## 13.4 Flujo automatizado con revisión humana por excepción

```
AGT-INV → AGT-APP → AGT-RSG → AGT-REP → AGT-EVD → AGT-VER → AGT-GAP
  → AGT-REM → AGT-QLT → AGT-DOC → AGT-RVL → paquete final → QA-HUM
```

NO exigir aprobación humana por cada gap ni por cada corrección (R-2).

Estado terminal de cada cambio:
AUTO_APPLIED_TO_DRAFT | PROPOSED_NOT_APPLIED | EXCEPTION_REQUIRED |
REJECTED_BY_VALIDATOR

AUTO_APPLIED_TO_DRAFT requiere TODAS: fuente verificada; aplicabilidad
aprobada; cobertura completa; A∧B∧C∧D; gates técnicos y lingüísticos;
trazabilidad completa; sin contradicciones; sin capacidades inventadas; sin
afirmaciones de implementación no demostradas.

Cuando falle un gate:
1. Registrar el fallo.
2. Ejecutar UN único ciclo AGT-REM → AGT-QLT.
3. Revalidar.
4. Si continúa fallando: EXCEPTION_REQUIRED.
5. Continuar con los demás cambios. No bloquear toda la corrida por un
   fallo individual recuperable.

Clasificación de riesgo:
- LOW_RISK: incorporación automática si todos los gates aprueban.
- MEDIUM_RISK: incorporación marcada o agrupación en lote para decisión
  final de QA.
- HIGH_RISK: NUNCA autoaplicar; presentar como excepción sin bloquear el
  resto.

El spec debe definir criterios deterministas de asignación de riesgo
(mínimo: criticidad del gap, tipo documental, alcance del cambio —
adición vs. eliminación vs. modificación de requisito —, sección afectada,
confidence_band).

Aprobación humana ANTICIPADA solo para: fuente nueva/actualizada; nueva
versión de Evidence Pack; cambio material de aplicabilidad; documento sin
procedencia; excepción crítica que impida un candidato coherente.

──────────────────────────────────────────────────────────────────────────────
14. GENERACIÓN OBLIGATORIA DEL DOCUMENTO CORREGIDO
──────────────────────────────────────────────────────────────────────────────

Entregable: CORRECTED_DOCUMENT_GENERATION_AND_FORMAT_SPEC.md

El pipeline operativo futuro NO está completo hasta generar una nueva
versión ÍNTEGRA del documento remediado. El original nunca se sobrescribe.

Ruta objetivo (integrar a path_policy en implementación):
factory/generated_documents/<run_id>/<document_id>/

Metadatos conservados: SHA-256 original y candidato; versión original y
candidata; run_id; fingerprint; fecha; agentes participantes; modelo y
digest; fuentes regulatorias utilizadas.

El candidato conserva, según formato: portada; título; código; versión;
control de cambios; índice; estructura; numeración; encabezados; secciones;
subsecciones; tablas; figuras; notas; referencias cruzadas; terminología;
idioma; estilo técnico; formato general.

NO es válido entregar únicamente: resumen; listado de sugerencias;
fragmentos; Markdown; reporte sin documento corregido; instrucciones
manuales de modificación.

Estrategia por formato:
- DOCX: DOCX candidato + PDF de revisión + redline.
- PDF con fuente editable autorizada: modificar copia editable; generar
  candidato editable y PDF.
- PDF sin fuente editable: reconstruir versión editable cuando sea
  técnicamente seguro; generar DOCX y PDF candidatos; registrar
  limitaciones de fidelidad; BLOQUEAR la generación cuando no pueda
  conservarse el contenido con confiabilidad suficiente.
- XLSX: XLSX nuevo; preservar hojas, fórmulas, tablas y rangos; registrar
  cambios por hoja y celda (redline como registro celda a celda).
- DOCM: NO ejecutar macros; preservar original; documentar limitaciones y
  método seguro de generación.
- Formatos no soportados: DOCUMENT_GENERATION_BLOCKED; continuar con otros
  documentos; registrar la excepción.

El candidato limpio incorpora SOLO cambios AUTO_APPLIED_TO_DRAFT. Los
cambios PROPOSED_NOT_APPLIED / EXCEPTION_REQUIRED / REJECTED_BY_VALIDATOR
van al paquete de excepciones; jamás se incorporan silenciosamente.

Registro por corrección aplicada: change_id; document_id; SHA-256 original;
ubicación; texto original; texto corregido; tipo de cambio; hallazgo; gap o
desviación; requirement_id; regulación; versión; numeral; cita normativa;
URL; SHA-256 regulatorio; explicación de insuficiencia; explicación de cómo
el cambio atiende el requisito; agente redactor; agente validador;
resultado de gates; resultado de revalidación; evidencia de implementación
pendiente.

Respeto del propósito documental (regla anti-fabricación):
URS expresa requisitos; FS comportamiento funcional previsto; DS diseño;
SOP procedimientos; PROTOCOLO pruebas planificadas; REPORTE resultados
observados. PROHIBIDO convertir una capacidad requerida en una capacidad
supuestamente implementada.

AGT-QLT revisa el DOCUMENTO COMPLETO (no solo fragmentos): coherencia
global; consistencia; terminología; numeración; referencias cruzadas;
tablas; abreviaturas; definiciones; duplicaciones; contradicciones;
ortografía; gramática; claridad; precisión; estilo profesional.

Nota de contenido obligatoria en todo candidato/reporte: los agentes no
reemplazan decisiones de QA/QC y no liberan lotes ni documentos
automáticamente. sanitize_for_report() aplica a todo render.

──────────────────────────────────────────────────────────────────────────────
15. ARTEFACTOS OBLIGATORIOS POR DOCUMENTO
──────────────────────────────────────────────────────────────────────────────

Entregable: PROFESSIONAL_DOCUMENT_PACKAGE_SPEC.md

AGT-DOC genera simultáneamente y de forma consistente:

1. DOCUMENTO_CANDIDATO_COMPLETO
2. DOCUMENTO_REDLINE
3. REPORTE_DE_HALLAZGOS_GAPS_Y_DESVIACIONES
4. MATRIZ_DE_TRAZABILIDAD
5. RESEÑA_DE_CAMBIOS_Y_FUNDAMENTO_REGULATORIO
6. PAQUETE_DE_EXCEPCIONES
7. MANIFEST (todos los artefactos + SHA-256 + run_id + fingerprint)
8. REPORTE_DE_REVALIDACIÓN
9. REPORTE_DE_CALIDAD_FINAL

Matriz: requirement_id → evidencia → hallazgo → gap/desviación → change_id
→ sección → revalidación.

Reseña, por cambio: change_id; sección; contenido anterior; contenido
nuevo; hallazgo; gap/desviación; motivo; regulación; numeral; cita; URL;
evidencia; resultado de revalidación; implementación pendiente. Narrativa:
qué estaba incompleto → por qué era insuficiente → qué se modificó → cómo
atiende el requisito → fuente oficial → qué queda pendiente.

La reseña puede ir al final del candidato o como anexo controlado, según
formato y política documental (definir la regla en el spec).

──────────────────────────────────────────────────────────────────────────────
16. CORRECTED_DOCUMENT_GENERATION_GATE
──────────────────────────────────────────────────────────────────────────────

PASS únicamente cuando: existe el candidato completo; puede abrirse; no
está vacío; no está truncado; conserva la estructura requerida; tiene
versión nueva; tiene SHA-256 nuevo; el original permanece intacto; todos
los cambios aplicados tienen change_id; todos los change_id están en la
matriz; el redline coincide con el candidato; el manifest incluye todos los
artefactos; la reseña está completa; la revalidación fue ejecutada; el
reporte de calidad existe.

FAIL ⇒ DOCUMENT_PACKAGE_INCOMPLETE; SAFE_TO_DELIVER=false;
PRODUCTION_ENABLEMENT=BLOCKED.

Estados finales por documento:
CORRECTED_DOCUMENT_GENERATED | CORRECTED_DOCUMENT_GENERATED_WITH_EXCEPTIONS
| DOCUMENT_GENERATION_PARTIAL | DOCUMENT_GENERATION_BLOCKED

PROHIBIDO usar REGULATORY_COMPLIANCE_CONFIRMED como resultado automático.

──────────────────────────────────────────────────────────────────────────────
17. REVALIDACIÓN INDEPENDIENTE DEL DOCUMENTO COMPLETO
──────────────────────────────────────────────────────────────────────────────

Entregable: CANDIDATE_REVALIDATION_SPEC.md

AGT-RVL (independiente de AGT-REM) analiza BASELINE_ORIGINAL vs.
DOCUMENTO_CANDIDATO_COMPLETO. No se limita a fragmentos modificados.

Por cada gap: CLOSED | PARTIALLY_CLOSED | OPEN | NEW_GAP_INTRODUCED |
IMPLEMENTATION_VERIFICATION_REQUIRED

Comprueba: cada cambio incorporado; ubicación correcta; sin truncamiento;
responde al requisito (re-ejecuta B/C/D sobre el texto nuevo); referencia
regulatoria correcta; coherencia global del documento; sin nuevos gaps; sin
eliminación de contenido requerido; sin capacidades inventadas; redline,
matriz, reseña, reporte y manifest coinciden; el archivo final abre; todos
los hashes válidos.

Un gap NO puede clasificarse CLOSED por la sola existencia de una
propuesta: el texto debe estar incorporado y validado dentro del candidato.
Cualquier inconsistencia ⇒ corrida NO liberable.

──────────────────────────────────────────────────────────────────────────────
18. RENDIMIENTO, ORQUESTACIÓN E IDENTIDAD DE CORRIDA
──────────────────────────────────────────────────────────────────────────────

Entregable: PERFORMANCE_AND_INFERENCE_ORCHESTRATION_SPEC.md

NO diseñar por defecto "todos los chunks × todos los requisitos"
(corrige el patrón 121 llamadas del baseline).

Antes de llamar a la LLM aplicar: matriz de aplicabilidad; tipo documental;
índice de secciones; filtros deterministas; búsqueda textual; recuperación
semántica; deduplicación; selección de contexto.

Diseñar: cola central; concurrencia configurable; prioridades; batching
seguro; checkpoint; resume; retry limitado; cache por fingerprint;
deduplicación de prompts; timeout; circuit breaker; métricas.

Invalidación de cache — NO reutilizar resultados cuando cambie: documento o
SHA-256; regulación o SHA-256; Evidence Pack; prompt; schema; modelo o
digest; matriz; chunking.

Cada llamada registra: run_id; task_id; agent_id; agent_version;
document_sha256; requirement_id; provider; model; model_digest;
prompt_version; schema_version; Evidence Pack version; timestamps;
duración; validación.

run_id y fingerprint persistidos desde el inicio, incluyendo: documentos +
SHA-256; commit; modelo + digest; prompt_version; schema_version; agent_id
+ agent_version (todos); Evidence Pack versions; catálogo (versión+hash);
matriz de aplicabilidad (versión+hash); regulaciones + hashes; parámetros;
chunking; fecha; responsable (identidad real). Reanudación con fingerprint
distinto ⇒ RECHAZADA + auditada; se inicia corrida nueva.

FALLBACK FAIL-CLOSED cuando la LLM no esté disponible:
- no inventar resultados; no degradar a coincidencias de palabras;
- conservar checkpoint; continuar tareas deterministas;
- marcar LLM_SERVICE_UNAVAILABLE; reanudar al volver el servicio;
- impedir conclusiones positivas incompletas;
- NO cambiar automáticamente a un proveedor externo.

──────────────────────────────────────────────────────────────────────────────
19. CALIFICACIÓN DE MODELOS
──────────────────────────────────────────────────────────────────────────────

Model Qualification Gate (documentar en
MODEL_PROVIDER_AND_LOCAL_AI_RUNTIME_SPEC.md) con métricas:

schema_valid_rate; citation_anchor_precision; semantic_precision;
semantic_recall; false_positive_rate; false_negative_rate;
contradiction_detection_rate; remediation_acceptance_rate;
unsupported_claim_rate; latency_p50; latency_p95; tokens_per_task;
retry_rate.

Prioridades: 1) cero citas inventadas; 2) menor tasa de falsos positivos;
3) menor tasa de falsos negativos críticos; 4) cumplimiento de schema;
5) estabilidad; 6) calidad de remediación; 7) rendimiento.

NO elegir el modelo solo por velocidad. Cambio de modelo = nuevo
fingerprint + Golden Dataset + comparación baseline + reporte de regresión
+ aprobación del perfil (sección 7).

──────────────────────────────────────────────────────────────────────────────
20. PAQUETE FINAL PARA QA
──────────────────────────────────────────────────────────────────────────────

Entregable: QA_FINAL_PACKAGE_AND_DECISION_SPEC.md

QA-HUM recibe el paquete completo cuando los agentes terminan: candidato;
redline; reporte; matriz; manifest; reseña; cambios autoaplicados; cambios
no aplicados; excepciones; riesgos; gaps cerrados/parciales/abiertos;
implementación pendiente; reporte de calidad; recomendación automática NO
vinculante.

Decisiones humanas: APPROVE_CLEAN | APPROVE_WITH_EXCEPTIONS |
REQUEST_CHANGES | REJECT

Reglas: aceptación de conformidad documental SEPARADA de la liberación; sin
aprobación humana individual por cada gap o cambio; identidad real
(approved_by, 422 para genéricas); idempotencia (409 doble aprobación);
decision_origin=human_confirmed; evento de auditoría por decisión.

──────────────────────────────────────────────────────────────────────────────
21. ROADMAP DE IMPLEMENTACIÓN (FASES A–P)
──────────────────────────────────────────────────────────────────────────────

Entregable: IMPLEMENTATION_ROADMAP.md

```
A  Inventario Rockwell y allowlist                       (W5-A)
B  Gobernanza de fuentes                                 (W5-B parcial)
C  Requirement Evidence Packs                            (W5-B parcial)
D  ModelProvider y runtime independiente                 (NUEVO V2)
E  Inyección de texto regulatorio                        (W5-C)
F  Validación A/B/C/D                                    (W5-D parcial)
G  Golden Dataset y calificación del modelo              (W5-D/I parcial)
H  Baseline formal                                       (W5-E)
I  Hallazgos, gaps y remediación                         (W5-F)
J  Motor de generación por formato                       (W5-G ampliado)
K  Aplicación gobernada de cambios                       (W5-G ampliado)
L  Generación del documento candidato completo           (W5-G ampliado)
M  Redline, matriz, reseña y manifest                    (W5-G ampliado)
N  Validación de apertura, estructura e integridad       (NUEVO V2)
O  Revalidación independiente                            (W5-H)
P  Paquete final para QA                                 (W5-I ampliado)
```

Para cada fase: objetivo; código reutilizable (desde sección 4); archivos a
crear o modificar; agentes; schemas; tests; riesgos; criterios de
aceptación; evidencia de cierre; dependencias; rollback; impacto de
rendimiento; estado inicial; estado final. Fases pequeñas, auditables,
reversibles. Cada fase cierra con Gate 0 (factory_selfcheck) en verde y
checkpoint de Cesar (los checkpoints aplican a la IMPLEMENTACIÓN futura, no
a esta corrida de diseño).

──────────────────────────────────────────────────────────────────────────────
22. GATES DE ACEPTACIÓN
──────────────────────────────────────────────────────────────────────────────

Entregable: ACCEPTANCE_AND_VALIDATION_GATES.md

Mínimo:
- 100% de archivos Rockwell inventariados; 0 omitidos.
- 100% de originales con SHA-256 y procedencia; 0 originales sobrescritos.
- 100% de requisitos con fuente gobernada.
- 100% de prompts con Evidence Pack (texto normativo canónico incluido).
- 100% de fuentes con URL, versión y SHA-256.
- 100% de evidencias con anclaje documental.
- 100% de conclusiones positivas con A/B/C/D.
- 0 citas inventadas; 0 coincidencias léxicas aisladas aceptadas.
- 0 DOCUMENTATION_GAP con cobertura incompleta.
- 0 cambios sin requisito, evidencia, explicación y fuente oficial.
- 0 cambios con redacción inválida; 0 capacidades inventadas.
- 0 afirmaciones de implementación sin evidencia.
- 0 dependencias runtime de Claude Code.
- 100% de agentes híbridos con ModelProvider.
- 0 llamadas LLM para tareas deterministas.
- 100% de salidas LLM validadas por schema.
- 100% de llamadas con run_id y task_id.
- 0 cambios automáticos a proveedor externo.
- 0 HIGH_RISK autoaplicados.
- 0 fallos recuperables bloqueando toda la corrida.
- 100% de excepciones dentro del paquete QA.
- 100% de documentos remediables con candidato completo generado.
- 100% de candidatos con SHA-256 nuevo.
- 100% de candidatos con redline, matriz, reseña y manifest.
- 100% de candidatos revalidados como documento completo.
- 0 diferencias no explicadas entre candidato y redline.
- 0 cambios rechazados incorporados silenciosamente.
- 0 candidatos entregados como fragmentos.
- 0 paquetes entregables sin documento candidato.
- 0 divergencias entre artefactos.
- 0 liberaciones automáticas; aprobación QA obligatoria.

Para cada gate especificar: cómo se mide; script o test previsto; momento
de ejecución; condición PASS; condición FAIL; evento de auditoría; efecto
sobre el pipeline; integración a Gate 0.

──────────────────────────────────────────────────────────────────────────────
23. ENTREGABLES DE DISEÑO (18)
──────────────────────────────────────────────────────────────────────────────

Generar en factory/docs/design/regulatory_redesign_v2/:

1.  W5_V2_EXECUTION_SUMMARY.md  (resumen de esta corrida; el presente
    archivo de instrucciones ya existe en docs_plan/ y no se regenera)
2.  REGULATORY_SOLUTION_GAP_ASSESSMENT.md
3.  CURRENT_AGENT_RUNTIME_AUDIT.md
4.  ROCKWELL_SOURCE_INVENTORY_AND_SCOPE_SPEC.md
5.  AGENT_RESPONSIBILITY_ARCHITECTURE.md
6.  TARGET_REGULATORY_PIPELINE_ARCHITECTURE.md
7.  MODEL_PROVIDER_AND_LOCAL_AI_RUNTIME_SPEC.md
8.  REGULATORY_SOURCE_GOVERNANCE_SPEC.md
9.  REQUIREMENT_EVIDENCE_PACK_SPEC.md
10. SEMANTIC_EVIDENCE_VERIFICATION_SPEC.md
11. GAP_DEVIATION_AND_REMEDIATION_MODEL.md
12. CORRECTED_DOCUMENT_GENERATION_AND_FORMAT_SPEC.md
13. PROFESSIONAL_DOCUMENT_PACKAGE_SPEC.md
14. CANDIDATE_REVALIDATION_SPEC.md
15. PERFORMANCE_AND_INFERENCE_ORCHESTRATION_SPEC.md
16. QA_FINAL_PACKAGE_AND_DECISION_SPEC.md
17. IMPLEMENTATION_ROADMAP.md
18. ACCEPTANCE_AND_VALIDATION_GATES.md

REGULATORY_SOLUTION_GAP_ASSESSMENT.md consolida: estado actual (baseline
3.1 + auditoría sección 4) vs. diseño objetivo; por brecha: componente, qué
falta, agente responsable, fase que la cierra, riesgo si no se cierra. Es
el puente entre la corrida URS v2.1 y el rediseño.

Todos son documentos de diseño, no código.

──────────────────────────────────────────────────────────────────────────────
24. CIERRE DE ESTA EJECUCIÓN
──────────────────────────────────────────────────────────────────────────────

Confirmar: no se modificó código; no se modificaron originales; no se llamó
a Ollama; no se descargaron fuentes; no se generaron candidatos reales; no
se realizaron commits; no se incluyeron secretos; no se incluyeron raw
responses; no se reprodujo innecesariamente texto Rockwell restringido;
`git status` muestra SOLO archivos .md nuevos; Gate 0 sigue en verde
(ejecutar factory/scripts/ops/factory_selfcheck.sh y reportar).

Finalizar con el bloque de estado (valores reales):

```
REPORT_SANITIZED =
CURRENT_REAL_AGENT_COUNT =
CURRENT_IMPLEMENTED_AGENTS =
CURRENT_DESIGN_ONLY_AGENTS =
CURRENT_DETERMINISTIC_AGENTS =
CURRENT_LLM_OR_HYBRID_AGENTS =
CURRENT_CLAUDE_CODE_RUNTIME_DEPENDENCY =
TARGET_LOGICAL_AGENT_COUNT = 11
CLAUDE_CODE_REQUIRED_AT_RUNTIME = false
MODEL_PROVIDER_ABSTRACTION_DESIGNED =
AGENTS_PORTABLE_BETWEEN_MODELS =
LLM_USED_ONLY_FOR_SEMANTIC_TASKS =
DETERMINISTIC_AUTHORITY_PRESERVED =
ROCKWELL_FOLDER_FULLY_IN_SCOPE =
ORIGINAL_FILES_ACCOUNTED_FOR =
ORIGINAL_DOCUMENTS_IMMUTABLE = true
TRUSTED_SOURCE_CHAIN_DESIGNED =
REGULATORY_TEXT_IN_PROMPT_DESIGNED =
SEMANTIC_VERIFICATION_DESIGNED =
PER_GAP_HUMAN_APPROVAL_REQUIRED = false
PER_CHANGE_HUMAN_APPROVAL_REQUIRED = false
EXCEPTION_BASED_REVIEW_DESIGNED =
HUMAN_BOTTLENECK_REDUCED =
FULL_CORRECTED_DOCUMENT_REQUIRED = true
SOURCE_FORMAT_PRESERVATION_DESIGNED =
FORMAT_SPECIFIC_GENERATION_DESIGNED =
CORRECTED_DOCUMENT_GENERATION_GATE_DESIGNED =
CORRECTED_DOCUMENT_OUTPUT_PATH_DESIGNED =
UNVALIDATED_CHANGES_EXCLUDED =
REDLINE_REQUIRED = true
TRACEABILITY_MATRIX_REQUIRED = true
REGULATORY_RATIONALE_REQUIRED = true
FULL_DOCUMENT_REVALIDATION_REQUIRED = true
DOCUMENT_PACKAGE_DESIGNED =
MODEL_QUALIFICATION_GATE_DESIGNED =
PERFORMANCE_BOTTLENECK_CONTROLS_DESIGNED =
EXPECTED_DOCUMENT_CAPABILITY =
DESIGN_RUN_GENERATES_REAL_DOCUMENT = false
TARGET_RUNTIME_GENERATES_FULL_CORRECTED_DOCUMENT = true
SAFE_TO_IMPLEMENT_PHASE_A =
SAFE_TO_GENERATE_DOCUMENT = false
SAFE_TO_DECLARE_DOCUMENT_CONFORMANCE = false
SAFE_TO_DECLARE_REGULATORY_COMPLIANCE = false
SAFE_TO_DELIVER = false
PRODUCTION_ENABLEMENT = BLOCKED
```

Presentar al final: resumen ejecutivo; brechas críticas; mapa de agentes
actuales → agentes W5 V2; arquitectura propuesta; archivos generados;
riesgos pendientes; propuesta de commits futuros (incluida la del reporte
URS v2.1 si REPORT_SANITIZED=true, como commit separado); orden recomendado
de implementación.

NO realizar commits. Detenerse tras completar todo el diseño y esperar
aprobación de Cesar para la Fase A.
