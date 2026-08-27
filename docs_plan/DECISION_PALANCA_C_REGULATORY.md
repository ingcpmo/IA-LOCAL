# DECISIÓN — Palanca C (Tier-1) permanente para la clase Regulatory

**Fecha:** 2026-08-27. **Autoridad:** Capa 9 = Cesar. **Estado:** ADOPTADA.
**Base:** `docs_plan/REPORTE_B4B_MEDICION_RECALL_V2.md` §7-9; contingencia pre-fijada en
`docs_plan/ADR_ANALIZADOR_GMP_LOCAL_V2.md` §10 y `R2_2_CIERRE_Y_CAPA_SEMANTICA.md` §1.

---

## 1. Qué se decidió

La medición B4b (fixture 7P+2N por el flujo V2, dos variantes del paso B, autorizadas y
firmadas por Capa 9) dio **`REGULATORY_POSITIVE = 0/7` en ambas**. Con seis vías de medición
independientes convergiendo en el mismo techo (H1-H4, qwen2.5:14b, fusión, R2, B4b estricto,
B4b no estricto), el criterio pre-fijado (`≤ 2/7 ⇒ Palanca C`) se activa.

**El analizador NO automatiza el juicio regulatorio de paráfrasis.** La clase Regulatory opera
en **modo Tier-1** de forma permanente:

| Situación (por sub-criterio, decomposition v1.1) | Salida automática |
|---|---|
| Eco léxico anclado por el verificador determinista (validación A / relevancia alta) | `RegulatoryFinding: REGULATORY_COMPLIANT_EVIDENCE`, `MACHINE_CONFIRMED_FINDING` — **candidato a confirmación humana rápida, NUNCA aprobación** |
| Todo lo demás (paráfrasis, evidencia indirecta, sin candidato claro) | `RegulatoryFinding: REGULATORY_INCONCLUSIVE`, `MACHINE_INCONCLUSIVE` — a revisión humana, con los candidatos del `EvidenceBundle` adjuntos marcados "RECUPERACIÓN, no evidencia validada" |

- **Cero llamadas LLM** para la clase Regulatory. Determinista.
- **Ningún validador se relaja.** `evidence_verifier`, umbral fuzzy 0.93, exigencia de cita
  anclada — intactos.
- **`human_state` de todo finding nace `UNREVIEWED`** y ningún path lo cambia.
- **Sin declaración de cumplimiento final. Sin aprobación automática. Sin cierre de CAPA. Sin
  liberación de lote.**
- **Declaración de cobertura explícita** en cada finding (`regulatory_tier1.COVERAGE_STATEMENT`):
  la detección automática de evidencia parafraseada NO está incluida.

## 2. Implementación

`factory/regulatory/findings/regulatory_tier1.py` — `regulatory_tier1_findings(document_id,
requirement_ids, ...)`. Reusa `EvidenceBundle` (B3), `evidence_verifier` (A/relevancia),
taxonomía B5 y `Risk` determinista. Sin `model_provider`, sin `judgment_v2`. Tests:
`test_regulatory_tier1.py` (4).

El juicio V2 en 2 pasos (`judgment_v2`, prompts firmados) **queda en el repo pero desactivado
para producción de la clase Regulatory** — su medición está cerrada. Puede reactivarse solo si
un modelo genuinamente distinto (no probado) lo justifica, con nueva medición contra el fixture.

## 3. Qué NO cambia esta decisión

- Las clases **FUNCTIONAL / TECHNICAL / TRACEABILITY / TEST_COVERAGE** — salen del grafo
  determinista (B6a) y de la taxonomía, no del juicio de paráfrasis. Su validación (suites B/C,
  B8b) sigue abierta e independiente.
- La infraestructura determinista de V2 (modelo canónico, extracción de tablas, grafo,
  descomposición firmada, cadena de remediación verificada, harness de gates, `DOCUMENT_EGRESS
  = 0` verificado bajo carga) — toda en pie y en uso.
- El estado documental: `REGULATORY_COMPLIANCE = NOT_DETERMINED` sigue vigente; el sistema
  nunca lo determina.

## 4. Registro

```
DECISION            = Palanca C (Tier-1) PERMANENTE para la clase Regulatory
FIRMADA_POR         = Capa 9 (Cesar), 2026-08-27
BASE_DE_MEDICION    = B4b: 0/7 estricto + 0/7 no estricto (PILOT_EXECUTION-2026-032/-034,
                      human_confirmed por Cesar)
VALIDADORES         = intactos (ninguno relajado)
JUICIO_V2_REGULATORY = DESACTIVADO para producción (código conservado)
CLASES_FUNCTIONAL_TECHNICAL = no afectadas
```
