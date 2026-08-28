# CIERRE FASE 12 — Costo computacional local (V2, arquitectura final)

**Fecha:** 2026-08-28. **Autoridad:** Capa 9 = Cesar.
**Arquitectura medida:** V2 en su variante EJECUTABLE adoptada — Regulatory Tier-1 /
Palanca C + Functional determinista + Technical determinista (B6b v1+v2, artefacto
`technical_completeness_rules.yaml` v1.1 SIGNED). **CERO LLM.**

## 1. Hardware disponible (medido 2026-08-28)

```
CPU   : 12 núcleos
RAM   : 19 815 MB total, ~12 650 MB disponibles en reposo
GPU   : ninguna  ->  VRAM = 0
Ollama: CPU-only (no se usa en el camino determinista)
```

## 2. Costo del runtime DETERMINISTA (camino adoptado)

Corrida E2E real: `v2_runtime.run_v2_pipeline` sobre 5 documentos reales
(RW-0005 FS 1409 claims, RW-0006 URS, RW-0011/0012/0014 DS), canonical_store ya
poblado (B1). Incluye grafo (B2) + retrieval BM25 (B3) + Tier-1 regulatory +
functional + technical + risk + remediación (8 borradores) + reporte + persistencia
+ hashes + manifest + package + zip.

| Recurso | Valor medido |
|---|---|
| **wall-clock** | **~5.5 s** (E2E completo, 5 docs) |
| **CPU** | single-thread dominante; 76 % de 1 núcleo; los 11 restantes libres |
| **RAM (peak RSS)** | **~42 MB** (`/usr/bin/time -v` = 41 700 KB; `ru_maxrss` coincide) — sin librerías ML cargadas |
| **VRAM** | **0** (no hay GPU ni se necesita) |
| **LLM calls** | **0** |
| **tokens** | **0** |
| **embedding calls** | **0** (retrieval = BM25 stdlib; NO se usa `nomic-embed-text`) |
| **disco — índices regenerables** | `canonical_store/` 3.9 MB + `graph_store/` 3.8 MB (6 docs) |
| **disco — por corrida (artifact growth)** | **~1.9 MB / corrida E2E** (`regulatory_findings.json` ~548 KB + `compliance_matrices/` ~712 KB + `functional_findings.json` ~128 KB + `evidence_provenance.json` ~132 KB + informe ~136 KB + zip ~132 KB) |
| **DOCUMENT_EGRESS** | **0 bytes** (bajo `network_locked()`) |

Shadow mode determinista: ~3 s wall, ~16 KB por corrida, 0 LLM, 0 egress.

**Conclusión:** `HARDWARE_FEASIBLE = SÍ` con enorme margen. El camino determinista
cabe en cualquier hardware; el cuello de botella histórico (latencia del 7B) **no
aplica** porque no se invoca ningún LLM.

## 3. Runtime local-LLM — NO aplica a la arquitectura adoptada

La contingencia adoptada (Palanca C / Tier-1) es **0 LLM**. Por tanto el
`local-LLM runtime` de FASE 12 es **N/A** para la variante ejecutable.

Si una decisión FUTURA de Capa 9 re-habilitara juicio LLM (B4 2-pasos o B6b HYBRID),
el costo ya medido en arcos previos (`docs_plan/PAQUETE_DECISION_ESTRATEGICA.md`,
`ROADMAP_ANALIZADOR_GMP.md`) se mantiene como referencia:

| Recurso | local-LLM (qwen2.5:7b-instruct-q4_K_M, CPU) — REFERENCIA, no activo |
|---|---|
| RAM adicional | ~5 GB (modelo 7B en RAM) + ~0.3 GB embeddings — cabe en 19 GB |
| VRAM | 0 (CPU-only) |
| latencia por llamada | ~250–600 s; 2-pasos + Critic ≈ 2–3× |
| corrida de corpus | días de background, gobernada por `PILOT_EXECUTION` |
| recall medido | 0/7 (estricto y no-estricto) — por eso NO se adopta |

## 4. OPTIONAL_INFRASTRUCTURE (no requerido)

| Opción | Requiere | Fallback ejecutable en hardware actual |
|---|---|---|
| Juicio LLM local ≥32B | GPU ≥24–48 GB VRAM (no cabe en 19 GB RAM CPU) | Tier-1 determinista (variante adoptada) |
| Reranker cross-encoder | pull ~80 MB | reranker léxico determinista / fusión directa |
| Capa semántica de embeddings | `nomic-embed-text` (~275 MB, ya instalado) | BM25 stdlib (variante adoptada) |
| Servicio de grafo (Neo4j) | contenedor + 1–2 GB RAM | SQLite (`graph_store/`, variante adoptada) |

Ninguna opción `OPTIONAL` es prerrequisito. Cada una tiene fallback ejecutable.

## 5. Veredicto FASE 12

```
HARDWARE_FEASIBLE      = SÍ   (runtime determinista: ~5.5 s wall, ~42 MB RSS, 0 GPU)
LOCAL_ONLY_FEASIBLE    = SÍ   (network_locked(), DOCUMENT_EGRESS = 0)
LLM_RUNTIME            = N/A  (arquitectura adoptada = 0 LLM)
DISCO / CORRIDA        = ~1.9 MB (E2E) ; índices regenerables ~7.7 MB
OPTIONAL_INFRASTRUCTURE= sin requerir; variante ejecutable conservada
```
