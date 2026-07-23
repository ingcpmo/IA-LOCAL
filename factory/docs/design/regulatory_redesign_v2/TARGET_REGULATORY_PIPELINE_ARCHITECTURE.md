# TARGET_REGULATORY_PIPELINE_ARCHITECTURE

## 1. Pipeline objetivo

```
AGT-INV → AGT-APP → AGT-RSG ⇢ AGT-REP → AGT-EVD → AGT-VER(A,B,C,D)
  → AGT-GAP → AGT-REM → AGT-QLT → AGT-DOC → AGT-RVL
  → paquete final → QA-HUM
```

`⇢` indica que AGT-RSG opera fuera del flujo síncrono de inferencia
(descargas/aprobaciones asíncronas); su resultado (catálogo gobernado) es
consumido por AGT-REP como precondición, no como paso bloqueante en tiempo
real del pipeline por documento.

## 2. Puntos de bloqueo determinista

| Punto | Condición de bloqueo | Efecto |
|---|---|---|
| Tras AGT-INV | archivo sin estado terminal, o count(find)≠count(allowlist) | pipeline no avanza a AGT-APP |
| Tras AGT-RSG | fuente en `SOURCE_UNAVAILABLE` o `REGULATORY_SOURCE_UNVERIFIED` | todos los requisitos dependientes ⇒ `EVALUATION_INCOMPLETE`, `COMPLIANCE_NOT_DETERMINED` |
| Tras AGT-VER | discrepancia regla-vs-LLM en validación C | `SUPPORTING_EVIDENCE_UNDER_REVIEW`, nunca aprobación |
| Tras AGT-REM | gate técnico/lingüístico falla 2 veces (1 ciclo de reintento) | `EXCEPTION_REQUIRED`, continúa con los demás cambios |
| Tras AGT-DOC | `CORRECTED_DOCUMENT_GENERATION_GATE` FAIL | `DOCUMENT_PACKAGE_INCOMPLETE`, `SAFE_TO_DELIVER=false` |
| Tras AGT-RVL | inconsistencia entre candidato/redline/matriz/manifest | corrida NO liberable |
| LLM no disponible en cualquier etapa híbrida | fail-closed (sección 18 del plan) | `LLM_SERVICE_UNAVAILABLE`, checkpoint conservado, reanuda al volver el servicio |

## 3. Puntos de aprobación humana anticipada (únicos 5 casos, R-2)

1. Fuente nueva/actualizada (AGT-RSG).
2. Nueva versión de Evidence Pack (AGT-REP).
3. Cambio material de aplicabilidad (AGT-APP).
4. Documento sin procedencia (AGT-INV → `ORIGINAL_SOURCE_UNCONFIRMED` no
   resuelto).
5. Excepción crítica que impida un candidato coherente (cualquier etapa).

Ningún otro punto exige aprobación humana individual por gap o por cambio —
la revisión humana se concentra en QA-HUM (paquete final) y en estas 5
excepciones anticipadas.

## 4. Artefactos intermedios y ubicación

| Artefacto | Generado por | Ubicación propuesta |
|---|---|---|
| `source_baseline_allowlist.yaml` | AGT-INV | `factory/regulatory/scope/` |
| Matriz de aplicabilidad | AGT-APP | `factory/regulatory/matrix/` |
| Catálogo regulatorio | AGT-RSG | `factory/regulatory/sources/canonical/` |
| Evidence Packs | AGT-REP | `factory/regulatory/evidence_packs/<requirement_id>/` |
| Veredictos A/B/C/D | AGT-VER | `factory/generated_documents/<run_id>/verifications/` |
| Registro de hallazgos/gaps | AGT-GAP | `factory/generated_documents/<run_id>/findings/` |
| Cambios propuestos/aplicados | AGT-REM | `factory/generated_documents/<run_id>/changes/` |
| Reporte de calidad | AGT-QLT | `factory/generated_documents/<run_id>/<document_id>/quality_report.md` |
| Documento candidato + paquete | AGT-DOC | `factory/generated_documents/<run_id>/<document_id>/` |
| Reporte de revalidación | AGT-RVL | `factory/generated_documents/<run_id>/<document_id>/revalidation_report.md` |
| Paquete final QA | ensamblado | `factory/generated_documents/<run_id>/<document_id>/qa_package/` |

## 5. Componentes actuales reutilizados (resumen, ver CURRENT_AGENT_RUNTIME_AUDIT.md)

- AGT-INV ← `inventory_agent.py`, `version_selection.py`.
- AGT-APP ← `classification_agent.py` (parcial).
- AGT-EVD/AGT-VER ← `llm_integrity_engine.py`, `chunked_engine.py`
  (candidato principal, hoy no wireado a producción).
- AGT-GAP ← `risk_agent.py` (fórmula de riesgo).
- QA-HUM (patrón) ← `final_review_agent.py`.
- AGT-REP, AGT-RSG, AGT-REM, AGT-QLT, AGT-DOC, AGT-RVL: sin código
  reutilizable directo — brechas de implementación completas (ver
  `REGULATORY_SOLUTION_GAP_ASSESSMENT.md`).

## 6. Flujo de excepciones

Todo cambio que no llegue a `AUTO_APPLIED_TO_DRAFT` (por fallo de gate no
recuperable, riesgo `HIGH_RISK`, o discrepancia regla-vs-LLM) se enruta al
**paquete de excepciones** (artefacto 6 de
`PROFESSIONAL_DOCUMENT_PACKAGE_SPEC.md`), nunca se descarta ni se aplica
silenciosamente. El paquete de excepciones viaja íntegro hasta QA-HUM junto
con el candidato limpio, de modo que la decisión humana vea tanto lo
aplicado automáticamente como lo pendiente.

## 7. Separación Reader/Executor (transversal a todos los agentes)

Todo endpoint GET expuesto sobre estos artefactos (lectura de estado,
reportes, manifest) es de solo lectura y no genera eventos de auditoría de
ejecución. Todo endpoint POST que dispare una etapa del pipeline audita
exactamente un evento con `run_by` real, `run_id`, `task_id` y timestamp —
sin excepciones, siguiendo el patrón ya usado en `gmp_report_service.py` y
`gmpai_artifact_service.py` (que hoy son deliberadamente solo-lectura).
