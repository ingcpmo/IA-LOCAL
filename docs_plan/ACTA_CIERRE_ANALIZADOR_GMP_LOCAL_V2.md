# ACTA CONSOLIDADA DE CIERRE — Analizador Documental GMP LOCAL V2

**Fecha:** 2026-08-28. **Autoridad:** Capa 9 = Cesar. **Arquitecto:** Capa 8.
**Alcance:** cierre del plan original V2 (FASE 0 → FASE 12). Arquitectura V2 **congelada**.

---

## 1. Estado fase por fase

| Fase | Objeto | Estado | Evidencia |
|---|---|---|---|
| **FASE_0** | Verificación del objetivo / investigación | **CERRADA** | `docs_plan/VERIFICACION_OBJETIVO_ANALIZADOR_20260827.md` |
| **FASE_1** | Rediseño LOCAL-ONLY | **CERRADA** | `docs_plan/REDISENO_ANALIZADOR_GMP_LOCAL_V2.md` |
| **FASE_2** | Arquitectura objetivo | **CERRADA** | `docs_plan/ARQUITECTURA_OBJETIVO_ANALIZADOR_GMP_LOCAL_V2.md` |
| **FASE_3** | ADR (decisión + alternativas + rollback + gates) | **CERRADA** | `docs_plan/ADR_ANALIZADOR_GMP_LOCAL_V2.md` (§ preservadas abajo) |
| **FASE_4** | Matriz GAP CURRENT vs V2 | **CERRADA** | `docs_plan/MATRIZ_GAP_CURRENT_VS_V2.md` |
| **FASE_5** | Plan de implementación (B1–B9) | **CERRADA** | `docs_plan/PLAN_IMPLEMENTACION_ANALIZADOR_GMP_LOCAL_V2.md` |
| **FASE_6** | Plan de validación (Suites A/B/C + transversales) | **CERRADA** | `docs_plan/PLAN_VALIDACION_ANALIZADOR_GMP_LOCAL_V2.md` |
| **FASE_7** | Contenido gobernado (decomposition v1.1, prompts V2, risk_matrix, technical_completeness_rules v1.1) | **CERRADA / FIRMADO** | `requirement_catalog/decomposition.yaml`, `.../technical_completeness_rules.yaml` (SIGNED 1.1), `engines/.../v2_draft/*.yaml` |
| **FASE_8** | Implementación B1–B9 (canónico, grafo, retrieval, juicio V2, findings, remediación) | **CERRADA** | commits `259ea22..54ab089` + B6b v1/v2; cadena de remediación E2E |
| **FASE_9** | Propuestas de agentes/fixtures + decisiones (Palanca C, B8b, OD-1..OD-6) | **CERRADA** | `PROPUESTA_*`, `DECISION_PALANCA_C_REGULATORY.md`, `DECISION_B8B_SUITE_B.md`, fixture C v1.0-benchmark SIGNED |
| **FASE_10** | Validación integral (3 suites + transversales) | **CERRADA** (Regulatory FAIL con contingencia aceptada) | `docs_plan/CIERRE_FASE_10_ANALIZADOR_GMP_LOCAL_V2.md` |
| **FASE_11** | Migración: runtime V2 E2E + REPORTING_GAP + Mission Control + Shadow + **CUTOVER** | **CERRADA** (cutover EJECUTADO 2026-08-28, reversible) | `validation_v2/v2_runtime.py`, `v2_mission_control.py`, `shadow_run_v2.py`, `api/routes/v2_analyzer.py`, run `GMPAI/reports/gmpai_document_validation/v2e2e-20260828T035243Z/` (con .docx físicos) |
| **FASE_12** | Costo computacional local | **CERRADA** | `docs_plan/CIERRE_FASE_12_COSTO_COMPUTACIONAL_V2.md` |

**Deuda de regresión:** `docs_plan/DEUDA_REGRESION_EXCEPCION_CAPA9.md` — 3 corregidos,
5 (EXC-1..EXC-5) reproducidos/clasificados como deuda de clon/servicio-en-vivo,
pendientes de aceptación formal de excepción por Capa 9. **pytest exit code real = 1.**

---

## 2. ADR — secciones preservadas (resumen; detalle en `ADR_ANALIZADOR_GMP_LOCAL_V2.md`)

- **Context:** CURRENT (motor de juicio LLM) mide recall regulatorio 2/7; no tiene capa
  funcional ni técnica ni grafo de trazabilidad; el 7B no mapea paráfrasis a
  sub-criterios regulatorios (`SEMANTIC_JUDGMENT_FAILURE`, confirmado por 6 vías).
- **Decision:** construir V2 **al lado** de CURRENT: modelo canónico → grafo de evidencia
  → descomposición estática → EvidenceBundle → juicio 2 pasos + Critic + Adjudicator
  determinista → 7 clases de Finding → cadena de remediación verificada. LOCAL ONLY.
- **Alternatives considered:** (A) GPU local ≥32B; (B) `AnthropicProvider` externo;
  (C) Tier-1 de alcance reducido (Palanca C).
- **Rejected alternatives:** (A) no cabe en 19 GB RAM CPU, sin GPU; (B) **rechazada** —
  expondría datos del cliente a servidores externos (viola LOCAL ONLY / DOCUMENT_EGRESS=0).
- **Consequences:** V2 aporta Functional/Technical + trazabilidad + reporting; el recall
  regulatorio del LLM **no se resuelve** por rediseño → contingencia §10.
- **Security:** sin credenciales nuevas (0 API externa); `network_locked()` en toda
  corrida; artefactos marcados `MACHINE GENERATED -- BORRADOR, NO APROBADO`.
- **Privacy:** DOCUMENT_EGRESS = 0 bytes medido en todas las corridas; ningún documento
  del cliente sale del host.
- **GMP impact:** ninguna aprobación automática; `human_state` nace `UNREVIEWED` e
  inmutable desde código IA; sin declaración de cumplimiento final; sin cierre de CAPA;
  sin liberación de lote. Estados prohibidos (`QA_APPROVED/RELEASED/CAPA_CLOSED/
  FINAL_GMP_APPROVAL`) bloqueados por `taxonomy.FORBIDDEN_STATES` y `_guard_no_forbidden`.
- **Rollback:** CURRENT intacto; `cutover.routing_mode()` DEFAULT = `current`; flag
  reversible (env `V2_ANALYZER_ROUTING` / `routing.txt`); CURRENT retenido como fallback.
- **Acceptance gates (§10 contingencia):** `REGULATORY_POSITIVE ≥ 6/7` → V2_RESUELVE;
  `≤ 2/7` → **TECHO_NO_CRUZADO → Palanca C permanente**. Resultado medido: **0/7** →
  contingencia activada.

---

## 3. VEREDICTO FINAL

```
CURRENT_CAN_MEET_OBJECTIVE_WITHOUT_REDESIGN = NO
  (CURRENT no tiene capa funcional/técnica ni grafo de trazabilidad; su recall
   regulatorio LLM es 2/7. El objetivo -- hallazgos regulatorios + funcionales +
   técnicos TRAZABLES -- requiere la capa V2.)

REDESIGN_REQUIRED = YES (para Functional / Technical / trazabilidad / reporting)
  NOTA: el rediseño NO resuelve el recall regulatorio del LLM (techo del 7B,
        confirmado 6 vías) -> se adopta contingencia determinista (Palanca C).

ROOT_CAUSES =
  1. SEMANTIC_JUDGMENT_FAILURE del 7B sobre evidencia parafraseada -> recall
     regulatorio 0-2/7. NO resuelto por rediseño; mitigado por Regulatory Tier-1.
  2. CURRENT sin capa funcional/técnica ni grafo de trazabilidad -> RESUELTO por
     V2 determinista (B2 grafo + B6a funcional + B6b v1/v2 técnico).
  3. REPORTING_GAP: V2 devolvía findings solo en memoria, sin persistencia ni
     publicación -> RESUELTO por FASE 11 / B9b (v2_runtime + Mission Control).

COMPONENTS_KEPT =
  motor CURRENT completo (chunked_engine, prompts, evidence_verifier, absence
  consolidator, human_review_queue, review_queue), gmp-api (:8000), factory-api
  (:9000) capas 7-9, gobernanza append-only, gmpai_artifact_service,
  candidate_document_generator, Mission Control UI, toda la infraestructura
  (Docker/PostgreSQL/Redis/systemd/backups). V2 se construyó AL LADO.

COMPONENTS_MODIFIED (por esta misión, sin contar drift preexistente) =
  factory/api/main.py (registrar router v2_analyzer -- 2 líneas)
  factory/regulatory/validation_v2/fixtures.py (status/is_retired/is_signed)
  factory/tests/{test_artifact_type_mismatch_report,test_broken_link_report,
                 test_source_currency_checker}.py (ruta de clon en 3 guard-tests)
  factory/tests/{test_validation_v2,test_technical_findings,test_functional_findings}.py
  factory/regulatory/findings/technical_findings.py (B6b v1+v2, guarda de índice, scope)
  factory/regulatory/validation_v2/fixtures_draft/{technical_suite_c,functional_suite_b}.yaml
  factory/.gitignore ; .gitignore ; docs_plan/PLAN_IMPLEMENTACION_... (B9b + addenda)
  docs_plan/{REDISENO,ARQUITECTURA_OBJETIVO,ADR,MATRIZ_GAP,PLAN_VALIDACION}_...md (addenda)

COMPONENTS_CREATED (por esta misión) =
  factory/regulatory/requirement_catalog/{technical_completeness_rules.yaml (SIGNED 1.1),
                                          technical_completeness_loader.py}
  factory/regulatory/findings/technical_findings.py (nuevo módulo B6b)
  factory/regulatory/validation_v2/{technical_suite_c.py, real_corpus_technical.py,
                                    v2_runtime.py, v2_mission_control.py, shadow_run_v2.py}
  factory/api/routes/v2_analyzer.py
  factory/tests/{test_technical_findings.py, test_v2_analyzer_endpoints.py}
  docs_plan/{VALIDACION_TECNICA_CORPUS_REAL_RW, CIERRE_FASE_10_..., CIERRE_FASE_12_...,
             DEUDA_REGRESION_EXCEPCION_CAPA9, ACTA_CIERRE_...}.md
  (previo en el arco V2: canonical/*, graph/*, retrieval/*, v2_judgment/*, findings/*,
   defect_corpus.py, gates.py, local_only.py, cutover.py, shadow.py, shadow_compare.py,
   report_v2.py, remediation_v2.py, from_verdicts.py, regulatory_tier1.py, decomposition.yaml)

REGULATORY_GATE = FAIL
  positive recall = 0/7 ; negatives = 2/2 ; fabricated citations = 0.
  Contingencia determinista ACEPTADA: Regulatory Tier-1 / Palanca C (CERO LLM,
  eco léxico anclado -> revisión humana con cobertura declarada). NO es PASS.

FUNCTIONAL_GATE = PASS
  recall = 16/16 = 1.00 ; FP = 0/16 = 0.00 (fixture de inyección de defectos).
  Corpus real Rockwell: 0 findings, 0 FP.

TECHNICAL_GATE = PASS
  Benchmark Suite C (fixture v1.0-benchmark SIGNED): TP=9, FN=C07 (SEMANTIC),
  FP=0, recall=0.90. Transversales: FABRICATED_CITATIONS=0, TRACEABILITY_COMPLETE=YES,
  LOCAL_ONLY=YES, DOCUMENT_EGRESS=0. Ground truth NO modificado.

TRACEABILITY_COMPLETE = YES
  Grafo B2 poblado sobre el corpus real (implemented_by=1120, designed_by=204,
  regulated_by=20); queries trace/orphans operativas.

REMEDIATION_E2E = YES
  Cadena Finding -> RemediationDirective -> candidate -> redline -> manifest exigida
  y ejecutada (8 borradores en la corrida real). Todo marcado MACHINE GENERATED /
  NOT_QA_APPROVED. Nunca QA_APPROVED/RELEASED/CAPA_CLOSED/FINAL_GMP_APPROVAL
  (bloqueado por guardas). Materialización DOCX vía to_current_pipeline_change ->
  candidate_document_generator de CURRENT (reutilizable sin duplicar arquitectura).

REPORTING_GAP_CLOSED = YES
  v2_runtime.run_v2_pipeline persiste bajo el destino EXISTENTE
  GMPAI/reports/gmpai_document_validation/<run_id>/ :
  regulatory_findings.json, functional_findings.json, technical_findings.json,
  evidence_provenance.json, remediation/*, informe_hallazgos_v2.md,
  compliance_matrices/, audit_summary/audit_metadata.json, manifest.json,
  SHA256SUMS.txt, package_receipt.json, paquete_final.zip. Sin raíz nueva.

MISSION_CONTROL_V2_API_VISIBLE = YES ; MISSION_CONTROL_V2_UI_VISIBLE = NO
  API: endpoints read-only registrados en la app existente (sin segunda UI):
  /api/v1/v2-analyzer/runs , /runs/{id} , /runs/{id}/findings ,
  /runs/{id}/evidence , /runs/{id}/remediation , /runs/{id}/report.
  Exponen: findings regulatorios/funcionales/técnicos, evidencia/provenance, risk,
  propuestas de remediación (candidate/redline/manifest), human review state,
  informe final. Router registrado en factory/api/main.py, 2 tests verdes.
  UI: factory/ui/mission_control.html NO consume estos endpoints (0 llamadas fetch;
  es un mockup de diseño). NO se construye una segunda UI. Falta: cablear un panel V2
  en la UI existente -> decisión/priorización de Capa 9, fuera del alcance de esta misión.

SHADOW_CURRENT_VS_V2 = YES
  shadow_run_v2 ejecutado (RW-0005/0011/0012): mismo input, CURRENT (conclusiones
  documentadas 7P+2N) vs V2 determinista. Comparación por requisito: added/lost,
  contradictions, FP candidates, runtime (~3s, 0 LLM), resources, DOCUMENT_EGRESS=0,
  audit. Salida en pilot_run/v2_shadow/<run_id>/. NO efectos.

CURRENT_ROLLBACK_AVAILABLE = YES
  cutover.routing_mode() DEFAULT = "current"; flag reversible (env V2_ANALYZER_ROUTING
  / routing.txt); CURRENT intacto y retenido como fallback. changed_by_shadow = False.

HARDWARE_FEASIBLE = YES
  Runtime determinista: ~5.5 s wall (E2E, 5 docs reales), ~42 MB peak RSS, 0 GPU,
  0 LLM, 0 embeddings. Disco ~1.9 MB/corrida + ~7.7 MB de índices regenerables.

LOCAL_ONLY_FEASIBLE = YES
  network_locked() en B4b, Suite C formal, validación real, E2E y shadow.

DOCUMENT_EGRESS = 0  (bytes, medido en TODAS las corridas)

EXTERNAL_LLM_REQUIRED = NO
  Arquitectura adoptada = 0 LLM. Ninguna API externa. (Si Capa 9 re-habilitara
  juicio LLM sería LOCAL -- qwen2.5:7b en Ollama -- nunca externo.)

FULL_REGRESSION_STATUS = 2779 passed / 5 failed / 79 skipped / 1 xfailed
  pytest exit code REAL = 1  (no enmascarado por pipes).
  5 failed = EXC-1..EXC-5 (deuda de clon `/home/ing_cpmo` + servicios en vivo);
  0 de esos 5 toca el analizador V2. Pendiente: aceptación formal de excepción
  por Capa 9 (docs_plan/DEUDA_REGRESION_EXCEPCION_CAPA9.md).

READY_FOR_CONTROLLED_CUTOVER = YES  ->  CUTOVER EJECUTADO (2026-08-28, reversible)
  Capa 9 (2026-08-28) aprobó:
    A. Regulatory Tier-1 / Palanca C adoptada como modalidad regulatoria de V2 en cutover.
    B. EXC-1..EXC-5 aceptadas como excepciones documentadas (deuda de clon/servicio; 0 impacto V2).
    C. Controlled cutover autorizado.
  EJECUTADO: cutover.set_routing_mode('v2', actor='Capa 9 (Cesar)', ...) -> routing=v2,
    active_engine=V2, regulatory_modality=REGULATORY_TIER1_PALANCA_C. Dispatcher:
    analyzer_router.analyze(). Verificado post-cutover (285/90/24 findings, 0 LLM, 0 egress).
    Rollback probado: set_routing_mode('current') -> CURRENT vuelve a ser el activo.
  Registro: docs_plan/CUTOVER_CONTROLADO_V2_20260828.md ;
    routing_history.jsonl (append-only, gitignored).
  REVERSIBLE en cualquier momento: routing='current' (archivo) o env V2_ANALYZER_ROUTING
    (gana sobre el archivo). CURRENT intacto y retenido como fallback.
```

---

*Sin cutover ejecutado. CURRENT intacto. Sin commit/push durante el trabajo (regla de la
autorización). Arquitectura V2 congelada.*
