# Verificación del objetivo — Analizador Documental GMP

**Fecha:** 2026-08-27 · **Repo:** `/home/cmay/ivr-ia` · **Rama:** `fix/clon-local-validacion`
**Modo:** solo lectura + *replay offline* (cero llamadas nuevas a Ollama, cero gobernanza consumida).
**Objetivo evaluado (literal):** *"Determinar si el sistema realmente cumple su objetivo de analizar documentos GMP mediante su arquitectura multiagente y producir hallazgos técnicos, funcionales y regulatorios trazables."*

> Esto es una **determinación con evidencia**, no una garantía de cumplimiento. Regla GMP: el sistema no emite declaración de cumplimiento final.

---

## Veredicto por dimensión del objetivo

| # | Dimensión del objetivo | Veredicto | Evidencia en vivo |
|---|---|---|---|
| V1 | **Arquitectura multiagente** | ✅ **CUMPLE** | 4 agentes regulatorios gobernados + trazabilidad; routing real por tipo documental |
| V2 | **Analiza documentos GMP (pipeline E2E)** | ✅ **CUMPLE** | `chunked_engine → ollama_client → evidence_verifier → absence_consolidator → human_review_queue` ensambla y corrió sobre documentos reales |
| V3a | **Hallazgos regulatorios** | ✅ **CUMPLE** | 4 marcos: 21 CFR Part 11, 21 CFR 211, EU GMP Annex 11, ALCOA+ |
| V3b | **Hallazgos técnicos y funcionales (clase propia)** | ❌ **NO CUMPLE** | El motor es *requirement-centric*; no hay clase de hallazgo técnico/funcional independiente |
| V4 | **Trazabilidad de cada hallazgo** | 🟡 **CUMPLE PARCIAL** | Cuando el modelo ancla: cita textual + página + `req_id` + riesgo + recomendación + fundamento. Cobertura limitada por recall del modelo (1–2/7) |
| V5 | **Auditoría Part 11 sobre el flujo** | 🟡 **CUMPLE CON EXCEPCIÓN DOCUMENTADA** | `hash_errors=0`, `content_hash_integrity=VERIFIED`, 1 fork histórico aceptado con excepción |
| V6 | **Recall del juicio (gate ≥6/7)** | ❌ **NO ALCANZADO** | Replay offline P2/P5 = **0/2 anclado** — reproduce la medición firmada R2.2/R2.3 |

**Conclusión global: PARCIAL.** El sistema **sí** analiza documentos GMP mediante una arquitectura multiagente real y **sí** produce hallazgos **regulatorios trazables** con evidencia anclada — pero con **cobertura de detección baja y declarada** (recall de juicio 1–2/7), y **no** produce hallazgos "técnicos" ni "funcionales" como clases propias distintas de la regulatoria. El estado documental vigente `REGULATORY_COMPLIANCE = NOT_DETERMINED` se mantiene.

---

## V1 — Arquitectura multiagente · ✅ CUMPLE

**No es un solo prompt.** Cuatro agentes regulatorios, cada uno con prompt YAML gobernado + delta de composición de contrato + `sha256` esperado:

| agent_id | Prompt gobernado | Marco |
|---|---|---|
| `fda_part11_agent` | `factory/engines/gmpai_integrity/prompts/part11_prompts.yaml` | 21 CFR Part 11 |
| `fda_cgmp_211_agent` | `cgmp211_prompts.yaml` | 21 CFR 211 (cGMP) |
| `eu_annex11_agent` | `annex11_prompts.yaml` | EU GMP Annex 11 |
| `alcoa_plus_agent` | `alcoa_prompts.yaml` | ALCOA+ (integridad de datos) |
| `requirements_traceability_agent` | `traceability_prompts.yaml` | Trazabilidad URS↔FS↔diseño |

- **Routing real:** `factory/regulatory/corpus_plan.py::resolve_document_agent_plan(document_type)` decide qué agentes corren según (1) matriz de aplicabilidad gobernada, (2) cobertura de decisión `D2` real, (3) `FORMAL_USE_ELIGIBILITY` de la fuente. Un agente sin requisitos aplicables no genera llamadas.
- **Composición de contrato:** `common_contract_base.yaml` + `common_contract_composer.py` + deltas por agente con `expected_sha256` — cambiarlo exige ciclo de gobernanza.
- **Confirmado por corrida real** (`fase5_result.json`, `corpus_run_20260821T010645Z.json`): los 4 agentes corrieron sobre RW-0005, RW-0011, RW-0012 — **158 llamadas, 12 unidades COMPLETED**, `run_id` propio por (documento × agente).

## V2 — Pipeline de análisis de punta a punta · ✅ CUMPLE

Trazado sobre `run_id` reales existentes:

```
build_page_chunks (con strip_page_furniture simétrico)
  → chunked_engine.evaluate_chunked (evaluation_profile=H2H4, 1 requirement/llamada)
    → ollama_client.generate  (mistral:7b / qwen2.5:7b, timeouts reales)
      → evidence_verifier  (validación A: cita textual anclada obligatoria)
        → semantic_evidence_verification  (validación C: relevancia, señal suave post-R1.7)
          → absence_consolidator  (EVIDENCE_NOT_LOCATED_IN_CANDIDATES / EVALUATION_INCOMPLETE)
            → layer9/human_review_queue  (RC + findings a revisión humana)
```

- Ensambla completo: sí (R1 CLOSED, smoke E2E 2026-08-09).
- Cada gate deja traza: `checkpoint.json` por corrida con `raw_response` + `raw_response_full_sha256`, `verified_records_by_req`, `fingerprint`, `preflight_metadata`.
- **Persistencia de recuperación:** BM25 + embeddings `nomic-embed-text` fusionados por RRF (`retrieval_recall_at_5 = 7/7` sobre el fixture). Los candidatos van al revisor marcados "RECUPERACIÓN, no evidencia validada".

## V3 — Clases de hallazgo · regulatorio ✅ / técnico-funcional ❌

**Lo que produce (motor actual, `pilot_run/**/unified_reports/`):** hallazgo por requisito regulatorio con campos:
`requirement_id · estado · página/sección · riesgo (p.ej. HIGH_RISK: evidence_status, gxp_impact) · recomendación (texto a agregar) · fundamento (por qué el requisito lo exige)`.

Ejemplo real (`P2_21_CFR_11.10(g)_unified_v2.md`, `run chunked-f6e3d96c6dfd`):
> 21_CFR_11.10(g) · Necesita revisión humana · HIGH_RISK · Recomendación: *"The system shall perform an authority check against the authenticated user's assigned FactoryTalk Security role…"* · Fundamento: *"documenta el control de authority-check que exige 21 CFR 11.10(g)…"*

**Lo que NO produce:** una categoría de hallazgo **"técnico"** (p.ej. defecto de arquitectura del sistema descrito) o **"funcional"** (p.ej. inconsistencia de comportamiento especificado) como clase propia con su taxonomía. El motor legacy (`GMPAI/reports/*.json`, **apagado**) tampoco las separa: 582 brechas, todas clasificadas por `requisito` regulatorio + `severidad`. El agente de trazabilidad cubre coherencia URS↔FS↔diseño, que es lo más cercano a "funcional", pero no se expone como clase de hallazgo en el informe unificado.

## V4 — Trazabilidad del hallazgo · 🟡 PARCIAL

**Cuando el modelo ancla, la trazabilidad es real y completa.** Verificado directamente en checkpoints del motor actual — 9 registros `status=verified` con cita textual no vacía, p.ej.:

| req_id | Cita anclada (real, del documento) | run_id |
|---|---|---|
| `21_CFR_11.10(e)` | *"UR3.3.1 Every time a critical alarm threshold is modified and audit trail record…"* | `chunked-ff6bd88a4987` |
| `ANNEX11_17` | *"F11.00: Databases and Historical Logging. This function implements the following…"* | `chunked-194352714f4d` |

- El verificador **rechaza correctamente** los `cumple_parcialmente` sin cita y los `evidencia_exacta:""` — esa parte del sistema funciona (es la prohibición central del roadmap: no relajar el verificador).
- **Límite:** la cobertura. Recall de juicio 1–2/7 sobre el fixture 7P+2N. Los hallazgos donde el modelo no ancla **no se pierden ni se convierten en GAP falso**: van a `human_review_queue` como `EVIDENCE_NOT_LOCATED_IN_CANDIDATES` con `evidence_quote:"" · page:None`, flag `ABSENCE_BLOCKED_BY_PARTIAL_COVERAGE`.

## V5 — Auditoría Part 11 · 🟡 CUMPLE CON EXCEPCIÓN DOCUMENTADA

`GET :9000/api/v1/audit/verify` (en vivo, 2026-08-27):
```
content_hash_integrity : VERIFIED     hash_errors  : 0
chain_continuity       : ACCEPTED_WITH_DOCUMENTED_EXCEPTION
part11_compliant       : ACCEPTED_WITH_DOCUMENTED_EXCEPTION
log_count 78010 · verified 78009 · chain_errors 1 (fork histórico concurrente)
```
El contenido es auténtico y la integridad de hash se sostiene. Hay **1 ruptura de enlace histórica** (fork concurrente, sin error de hash) aceptada por excepción documentada — es la misma excepción B4 del reporte de validación de clon, **no es corrupción**.

## V6 — Recall del juicio (gate bloqueante ≥6/7) · ❌ NO ALCANZADO

**Replay offline ejecutado hoy** (`scratchpad/v6_replay.py`, reusa la lógica de `test_r2_3_p2_p5_judgment_replay.py` corrigiendo la ruta hardcodeada B9; cero llamadas a Ollama, respuestas reales de `PILOT_EXECUTION-2026-012` persistidas):

```
P2 (21_CFR_11.10(g))     → conclusion=EVALUATION_INCOMPLETE  → evidencia anclada: NO
P5 (ALCOA_CONTEMPORANEOUS)→ conclusion=EVALUATION_INCOMPLETE  → evidencia anclada: NO
RESULTADO: 0/2 anclado  (esperado por R2.2/R2.3: 0/2)  ✔ reproduce la medición firmada
```

El techo de 1–2/7 está **confirmado por 4 vías independientes** (R2: BM25 solo, fusión semántica con pool perfecto, criterio pre-fijado de Cesar; R4: dilución tabular P4/P6). Es límite del modelo de 7B sobre evidencia parafraseada/diluida, **no** del pipeline ni del verificador. Por eso R3–R5 (tal como se diseñaron) no se activan.

---

## Qué falta para que el objetivo se cumpla en su totalidad

| Brecha | Qué exige | Palanca |
|---|---|---|
| Recall de juicio < 6/7 | Cruzar el gate bloqueante de R2 | `PAQUETE_DECISION_ESTRATEGICA.md` — Palanca A (modelo local mayor / `qwen2.5:7b`), B (`AnthropicProvider`), C (Tier-1 reducido). Decisión de Capa 9. |
| Sin clase de hallazgo técnico/funcional | Definir taxonomía y agente(s) para hallazgos de arquitectura y de comportamiento funcional, más allá del cumplimiento por requisito | Diseño nuevo — no está en el roadmap R0–R5 actual |
| `REGULATORY_COMPLIANCE = NOT_DETERMINED` | Piloto 2 aprobado + Golden Dataset ampliado + firma de Cesar (R4/R5) | Bloqueado por el gate de recall |

---

## Anexos verificados

- `factory/registry/agents_catalog.yaml`, `factory/regulatory/corpus_plan.py`
- `factory/regulatory/pilot_run/fase5_produccion_real_fixture7p2n_20260820/fase5_result.json`
- `factory/regulatory/pilot_run/tier1_rw0005/{report_raw.json,informe_tier1.md}`
- `factory/regulatory/pilot_run/fase2_3_informe_unificado_20260820/unified_reports/*_v2.md`
- `factory/regulatory/pilot_run/checkpoints/chunked-596f70cc4520.checkpoint.json` (+ 8 checkpoints con cita anclada)
- `GET http://localhost:9000/api/v1/audit/verify` (en vivo)
- Replay: `scratchpad/v6_replay.py` → 0/2 (reproduce R2.2/R2.3)

*Ningún artefacto de esta verificación se commiteó. Ninguna llamada a Ollama. Ninguna descarga.*
