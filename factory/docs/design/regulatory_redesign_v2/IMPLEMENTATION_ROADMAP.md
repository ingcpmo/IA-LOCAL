# IMPLEMENTATION_ROADMAP (Fases A–P)

Mapeo con W5 original: W5-A→V2-A | W5-B→V2-B+C | W5-C→V2-E | W5-D→V2-F+G |
W5-E→V2-H | W5-F→V2-I | W5-G→V2-J+K+L+M+N | W5-H→V2-O | W5-I→V2-G+P.
V2-D (ModelProvider/runtime) es alcance NUEVO sin equivalente en W5.

Cada fase cierra con Gate 0 (`factory_selfcheck.sh`) en verde y checkpoint
de Cesar. Los checkpoints aplican a la IMPLEMENTACIÓN futura, no a esta
corrida de diseño.

## A — Inventario Rockwell y allowlist

- **Objetivo**: `source_baseline_allowlist.yaml` cerrado, 14/14 archivos
  con estado terminal, duplicado FS_v1.2 resuelto, DOCM sin macros.
- **Código reutilizable**: `app/inventory_agent.py`, `app/version_selection.py`.
- **Archivos a crear**: `factory/regulatory/scope/source_baseline_allowlist.yaml`,
  `factory/core/path_policy.py` (si no cubre ya esta ruta).
- **Agentes**: AGT-INV.
- **Riesgos**: OCR del PDF escaneado de 136.8 MB; relación real entre
  RW-0007 (DOCM) y RW-0008 (PDF) sin determinar.
- **Criterios de aceptación**: count(find)==count(allowlist); 0 omisiones.
- **Rollback**: allowlist es artefacto nuevo, sin efecto sobre originales —
  rollback trivial (borrar archivo generado).

## B — Gobernanza de fuentes

- **Objetivo**: catálogo regulatorio formal con schema completo (sección
  10 del plan) sobre `factory/regulatory/sources/`.
- **Código reutilizable**: PDFs con hash ya existentes en
  `factory/regulatory/sources/sha256/`.
- **Agentes**: AGT-RSG.
- **Riesgos**: fuentes oficiales que cambien de versión sin detección.
- **Dependencias**: ninguna de A.

## C — Requirement Evidence Packs

- **Objetivo**: Evidence Pack completo por requirement_id (schema sección
  11), reemplazando el patrón "requirement_id + descripción breve".
- **Código reutilizable**: `compliance_agents.py` checkpoints (como
  insumo de contenido, no de patrón).
- **Agentes**: AGT-REP.
- **Dependencias**: B.

## D — ModelProvider y runtime independiente (NUEVO V2)

- **Objetivo**: interfaz `ModelProvider` + servicio de inferencia
  compartido, migración de los 5 puntos de acoplamiento directo a Ollama.
- **Código a modificar**: `llm_integrity_engine.py`,
  `llm_traceability_agent.py`, `llm_part11_agent.py`,
  `llm_annex11_agent.py`, `llm_alcoa_agent.py`,
  `factory/engines/gmpai_integrity/chunked_engine.py`.
- **Riesgo de regresión**: alto (refactor de imports en 6+ archivos) —
  requiere Golden Dataset como red de seguridad.
- **Dependencias**: ninguna, puede correr en paralelo con B/C.

## E — Inyección de texto regulatorio

- **Objetivo**: prompts regulatorios con contenido completo del Evidence
  Pack (canonical_text, contexto, criterios), no solo requirement_id.
- **Dependencias**: C, D.

## F — Validación A/B/C/D

- **Objetivo**: implementar las 4 validaciones independientes con reglas
  deterministas de exclusión (anti-ANNEX11_4).
- **Código reutilizable**: `evidence_verifier.py` (validación A),
  `chunked_engine.py` (candidato principal).
- **Dependencias**: D, E.

## G — Golden Dataset y calificación del modelo

- **Objetivo**: Golden Dataset mínimo (sección 12.2 del plan) + Model
  Qualification Gate operativo.
- **Dependencias**: F.

## H — Baseline formal

- **Objetivo**: `FORMAL_BASELINE_READY = true` sobre una corrida real que
  cierre los 25 review_required + 3 rejected_by_verifier pendientes de la
  corrida URS v2.1 (adjudicación humana, gated por Cesar).
- **Dependencias**: F, G.

## I — Hallazgos, gaps y remediación

- **Objetivo**: taxonomía estricta + AGT-GAP con criterios deterministas
  de riesgo + primer AGT-REM funcional.
- **Código reutilizable**: `app/risk_agent.py`.
- **Dependencias**: H.

## J — Motor de generación por formato

- **Objetivo**: generadores DOCX/PDF/XLSX/DOCM según estrategia por
  formato (sección 14 del plan), aplicados primero a los 14 archivos de
  Rockwell.
- **Código reutilizable**: `generate_fs_v1_2_draft_docx.py` (patrón, no
  componente).
- **Dependencias**: I.

## K — Aplicación gobernada de cambios

- **Objetivo**: estados `AUTO_APPLIED_TO_DRAFT`/`PROPOSED_NOT_APPLIED`/
  `EXCEPTION_REQUIRED`/`REJECTED_BY_VALIDATOR` operativos con 1 ciclo de
  reintento AGT-REM→AGT-QLT.
- **Dependencias**: I, J.

## L — Generación del documento candidato completo

- **Objetivo**: AGT-DOC produce el candidato íntegro conservando
  estructura, con metadatos completos.
- **Dependencias**: J, K.

## M — Redline, matriz, reseña y manifest

- **Objetivo**: los 9 artefactos de `PROFESSIONAL_DOCUMENT_PACKAGE_SPEC.md`
  generados simultáneamente y consistentes.
- **Dependencias**: L.

## N — Validación de apertura, estructura e integridad (NUEVO V2)

- **Objetivo**: `CORRECTED_DOCUMENT_GENERATION_GATE` operativo (PASS/FAIL
  según sección 16 del plan).
- **Dependencias**: M.

## O — Revalidación independiente

- **Objetivo**: AGT-RVL operativo, independiente de AGT-REM.
- **Código reutilizable (patrón)**: `app/final_review_agent.py`.
- **Dependencias**: N.

## P — Paquete final para QA

- **Objetivo**: endpoint de decisión QA con las 4 decisiones, identidad
  real, idempotencia 409, `decision_origin=human_confirmed`.
- **Código reutilizable (patrón)**: `factory/api/routes/layer9.py`.
- **Dependencias**: O.

## Orden recomendado de implementación

`A → B → C → D → E → F → G → H (checkpoint humano obligatorio: adjudicar
25+3 pendientes URS v2.1) → I → J → K → L → M → N → O → P`

D puede ejecutarse en paralelo con B/C (sin dependencia directa) para no
alargar el camino crítico. H es el único punto donde el roadmap depende de
una decisión humana externa al código (adjudicación de Cesar) antes de
continuar — recomendable no iniciar I sin esa adjudicación, para no
construir remediación sobre un baseline aún no confirmado.
