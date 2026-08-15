# B. Arquitectura de normalización documental (A.3, A.5, A.6)

**Estado**: propuesta de diseño. No implementa nada. Toda entidad debe
justificarse con evidencia real (§27, regla anti-sobreingeniería) o se
descarta explícitamente.

## Estado actual real (lo que ya existe, no lo que se imagina)

Existe una representación estructurada PARCIAL, ya construida pero **no
conectada** al pipeline de evaluación:
`factory/regulatory/document_structure_extractor.py` produce
`Document/Section/Paragraph` (secciones nivel 1 ancladas por Tabla de
Contenido real, líneas 121-157), usada hoy solo para la generación de
documento candidato (Fase 4 del roadmap `document_remediation_evolution`).
Su propio docstring (líneas 1-7) declara explícitamente: "NO existe hoy
en el pipeline [de evaluación]... aplana deliberadamente todo a texto
plano". Este es un hecho arquitectónico central: **el sistema ya tiene la
mitad de un DOM construido, y la decisión de diseño no es "construir un
DOM desde cero" sino "decidir si conectar el que ya existe al pipeline de
evaluación, y con qué alcance"**.

## A.3 — Entidades del DOM: cuáles se justifican

Criterio aplicado: cada entidad se acepta SOLO si un caso real (no
hipotético) del proyecto demuestra que su ausencia causó pérdida medible.

| Entidad | Estado | Justificación |
|---|---|---|
| Document | Ya existe (`document_structure_extractor.py`) | Base necesaria para cualquier provenance |
| Section / Paragraph | Ya existe y funciona | Construido y en uso (Fase 4). Límite conocido y documentado: subsecciones sin numeración propia no se distinguen — no bloqueante para el alcance de evaluación |
| Table / TableRow / TableCell | **No existe ningún extractor de tabla estructurada** en el código inspeccionado (solo texto plano intercalado) | Justificada CONDICIONALMENTE por el ratio de ruido medido en A.2 (~95%+ de la página de P6 es tabla) — pero sin experimento causal que confirme que separarla cambia el resultado. Ver `EXPERIMENT_PLAN.md` brazo C antes de construir el parser completo |
| Figure | Descartada | Sin evidencia de pérdida ligada a figuras en ningún caso P1-P7/N1-N2 documentado |
| Heading | Parcialmente cubierta por Section ya existente | No se justifica como entidad nueva separada |
| Reference | Descartada como entidad DOM nueva | El caso real que la tocaría (ANNEX11_4, GAMP5 dentro de lista de referencias numeradas) ya está resuelto por una regla determinista existente (`detect_reference_list_context`, ver `EVIDENCE_ARCHITECTURE.md` A.8) — construir una entidad `Reference` completa sería sobreingeniería sobre un problema ya cerrado |
| EvidenceUnit | Candidato más fuerte, pero con advertencia real | Encapsularía la oración de prosa aislada de la tabla circundante, con provenance. Advertencia: R2 demostró que evidencia perfectamente aislada (P2/P5) no cambió el juicio del modelo — el mismo riesgo aplica aquí. No construir sin antes correr el experimento C |

**Regla de secuencia obligatoria**: no construir `Table`/`TableRow`/
`TableCell`/`EvidenceUnit` completos antes de correr el brazo C del
`EXPERIMENT_PLAN.md` sobre P6/P7. Construir primero y medir después
invertiría el patrón "diagnosticar antes de construir" ya validado
repetidamente en el proyecto (ver memoria `project_w5_v2_regulatory_
redesign`).

## A.5 — Formatos y OCR

Corpus real confirmado (`factory/regulatory/scope/source_baseline_
allowlist.yaml`): 14 archivos — 12 PDF, 1 XLSX, 1 DOCM.
`SAT3 Scanned-1.pdf` (204 páginas) ya clasificado `OCR_REQUIRED` por
muestreo real (0 chars extraídos en 5 páginas espaciadas, evitando pagar
el costo de extraer las 204).

Esta auditoría **no verificó** en esta sesión si ya existe una máquina de
estados formal a nivel de schema
(`extraction_success`/`extraction_partial`/`OCR_REQUIRED`/
`OCR_COMPLETED`/`EXTRACTION_UNCERTAIN`/`DOCUMENT_UNREADABLE`) más allá del
campo `processing_state` ya usado en el allowlist. **Recomendación**:
antes de diseñar esta máquina de estados desde cero, grep directo de
`processing_state` en `source_baseline_allowlist.yaml` y su schema
asociado — es altamente probable que ya cubra la mayoría de estos
estados bajo otro nombre (mismo patrón repetido en cada fase de W5 V2:
"diagnosticar antes de construir" encontró infraestructura ya construida
en 8 de 12 fases con código).

OCR nunca se presenta como evidencia fiable sin declarar su provenance y
limitación — esto ya es una regla explícita del proyecto (`CLAUDE.md`),
no una propuesta nueva.

## A.6 — Evaluación de conversores

Extractor actual confirmado: **pdfplumber**
(`document_structure_extractor.py:38-40`, y `evidence_verifier.py`
docstring línea 38: "mismo extractor ya usado y verificado para las 3
fuentes regulatorias").

| Opción | Evaluación |
|---|---|
| A) pdfplumber (actual) | En uso, verificado contra 3 fuentes regulatorias, soporta `page.extract_tables()` (no invocado hoy, cero dependencia nueva si se activa) |
| B) MarkItDown | **No adoptable sin mapeo página↔unidad**: pierde límites de página, y TODO el anclaje del sistema (evidence_verifier, requirement_catalog, matching) es por página. Confirmado: no aparece en ningún `requirements.txt` ni import del código inspeccionado |
| C) Extracción estructurada (activar `pdfplumber.extract_tables()`) | Ya es la misma dependencia, cero paquete nuevo — es la ruta de menor riesgo para resolver A.4 (tablas) SI el experimento C del `EXPERIMENT_PLAN.md` justifica construirlo |
| D) Híbrida | Prematura de evaluar sin resultado del experimento C |
| E) Representación propia completa | Rechazada por sobreingeniería — no hay caso que justifique reinventar extracción de tabla cuando pdfplumber ya la soporta nativamente |

**Conclusión A.6**: no cambiar de extractor. Si se decide construir la
entidad `Table`, usar `pdfplumber.extract_tables()` — no introducir
MarkItDown ni una librería nueva.
