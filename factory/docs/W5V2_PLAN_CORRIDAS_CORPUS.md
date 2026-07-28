# W5 V2 — Plan realista de corridas del corpus restante

**Fecha:** 2026-07-28 · **Autoridad:** §9, §18 y §19 del plan W5 V2.
**Nada de esto se ejecutó.** ALCOA+ sigue congelada; no se invocó Ollama.

## 0. Por qué se descarta la estimación "13 documentos × 12–15 h"

Esa cifra (156–195 h) asume el patrón que §18 del plan **prohíbe
explícitamente**: "NO diseñar por defecto todos los chunks × todos los
requisitos". Aplicando los filtros que el propio plan exige —allowlist, tipo
documental, matriz de aplicabilidad, exclusión de duplicados y de no
aplicables, separación de OCR— el trabajo real es **147 llamadas y ~34 h**,
un 80 % menos.

## 1. Filtros aplicados, y qué elimina cada uno

| Filtro | Efecto medido |
|---|---|
| Allowlist (`processing_state`) | RW-0004 es `DUPLICATE` de RW-0005 ⇒ **excluido**. RW-0001 y RW-0003 son `OCR_REQUIRED` ⇒ **fuera de este alcance**. RW-0008 está en `HUMAN_REVIEW_REQUIRED` ⇒ **bloqueado hasta decisión** (ver §C del paquete de decisiones) |
| Matriz de aplicabilidad v2.0 (aprobada `MC-0001`) | `DRAWING`, `REPORT` y `OTHER` no están en `document_types`; los 19 requisitos caen a `default: review_required` ⇒ **0 requisitos con evidencia esperada** ⇒ RW-0002, RW-0007, RW-0009, RW-0010, RW-0013 **no se analizan** hasta que AGT-APP les asigne aplicabilidad |
| Aplicabilidad por tipo | FS 18/19 requisitos · URS 10/19 · **DS solo 4/19** |
| Selección de agente | Un agente solo corre si alguno de SUS checkpoints aplica. En DS, `alcoa_plus` aporta 1 requisito y `fda_part11` 1 |
| Presupuesto derivado del contrato | `output_token_budget()` cae de 4096 (ALCOA completo) a **512** en DS, donde solo aplica 1 requisito con 2 criterios |

**Resultado: de 14 documentos, solo 5 son analizables hoy**, y uno de ellos
(RW-0005) ya tiene un agente completo.

## 2. Base de la estimación (empírica, no inventada)

Corrida real de `eu_annex11_agent` sobre FS_v1.2 el 2026-07-28: **27 chunks en
481 min con `num_predict=3072`**, 0 fallos técnicos. De ahí:
**5,8 min por cada 1 000 tokens de presupuesto de salida**. El tiempo se escala
por `num_predict` porque la generación domina; los chunks reales del motor
(27) superan en ~17 % la estimación por caracteres (23), factor ya aplicado.

## 3. Plan por documento

| document_id | Formato | Págs/hojas | Tipo | Req. aplicables | Chunks tras filtrado | Llamadas LLM | Tiempo est. | OCR | ¿Genera candidato? | Prioridad | Dependencias |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **RW-0005** | .pdf | 58 | FS | 18 | 27 | **54** (annex11 ya completo) | **20,1 h** | No | Sí (ya tiene paquete de 9 artefactos) | **1** | ALCOA+ congelada; packs |
| **RW-0006** | .pdf | 24 | URS | 10 | 9 | **27** | **6,7 h** | No | Sí | **2** | Packs; baseline histórica ya adjudicada |
| **RW-0014** | .pdf | 18 | DS | 4 | 8 | **24** | **2,8 h** | No | Sí | 3 | Packs |
| **RW-0011** | .pdf | 14 | DS | 4 | 7 | **21** | **2,3 h** | No | Sí | 3 | Packs |
| **RW-0012** | .pdf | 14 | DS | 4 | 7 | **21** | **2,3 h** | No | Sí | 3 | Packs |
| RW-0002 | .pdf | 60 | OTHER | **0** | — | 0 | — | No | No | — | Requiere AGT-APP |
| RW-0013 | .xlsx | 5 hojas | OTHER | **0** | — | 0 | — | No | No | — | Requiere AGT-APP |
| RW-0009 | .pdf | 2 | REPORT | **0** | — | 0 | — | No | No | — | Requiere AGT-APP |
| RW-0010 | .pdf | 1 | DRAWING | **0** | — | 0 | — | No | No | — | Requiere AGT-APP |
| RW-0007 | .docm | 3 | OTHER | **0** | — | 0 | — | No | No | — | Requiere AGT-APP |
| RW-0008 | .pdf | 3 | OTHER | **0** | — | 0 | — | No | **Bloqueado** | — | Decisión T-039 |
| RW-0004 | .pdf | 58 | FS | — | — | 0 | — | No | No | — | `DUPLICATE` de RW-0005 |
| RW-0001 | .pdf | 24 | DRAWING | — | — | 0 | — | **Sí** | No | — | 0 chars extraíbles |
| RW-0003 | .pdf | ? | REPORT | — | — | 0 | — | **Sí** | No | — | 136,8 MB escaneado |

**Totales tras filtrado: 147 llamadas LLM · ~34,3 h.**

Desglose de RW-0005 (el más caro): `fda_part11` 4 req / 22 crit / `num_predict`
3584 → 9,4 h; `alcoa_plus` 9 req / 25 crit / 4096 → 10,7 h. `eu_annex11`
(8,0 h) **ya ejecutado y cerrado 27/27**.

## 4. Costo de ejecutar ANTES de las aprobaciones

Este es el punto decisivo, y no es simétrico.

Toda corrida queda atada a un `run_fingerprint` que **incluye el hash del
catálogo** (`catalog_sha256`). Aprobar los Evidence Packs implica firmar —y muy
probablemente ajustar— los `evidence_min_criteria`. Cualquier cambio en
`requirements.yaml`:

1. cambia `catalog_sha256` ⇒ **invalida todos los checkpoints** y ningún run
   previo es reanudable;
2. cambia el número de criterios ⇒ cambia `num_predict` ⇒ cambia el contrato
   de salida;
3. deja los resultados anteriores como producidos contra un catálogo que ya no
   es el vigente — utilizables como diagnóstico, **no como evidencia formal**.

⇒ **Ejecutar antes de aprobar cuesta repetirlo entero: ~34 h perdidas.**
A la inversa, esperar no cuesta nada más que el calendario.

Lo mismo aplica a la reverificación de fuentes: mientras
`source_verification_status = PENDING_REVERIFICATION`, toda conclusión sale
como `PROVISIONAL_ONLY` por diseño (`provisional_evidence_model.py`), así que
la corrida no puede producir baseline formal aunque termine perfecta.

## 5. Recomendación sobre ALCOA+ (FSV12-11)

**DESPUÉS de las aprobaciones, no antes.**

- ALCOA+ es el agente más caro del documento más caro: 27 llamadas, 10,7 h.
- Sus 9 requisitos dependen **todos** de `mhra_gxp_di_guidance_2018`, una de
  las 3 fuentes pendientes — y es la única cuya URL registrada apunta a una
  página de aterrizaje, no al PDF.
- El snapshot congelado (`c2d58e8`) tiene preflight fail-closed 21/21 probado
  por mutación y sigue relanzable con `schedule_alcoa.sh`. Esperar no lo
  degrada.
- Ejecutarla ahora produciría 9 conclusiones `PROVISIONAL_ONLY` sobre una
  fuente sin reverificar, que habría que repetir tras aprobar los packs.

**Excepción defendible:** si el objetivo fuera puramente diagnóstico —confirmar
que el fix de presupuesto se comporta igual con `num_predict=4096` que con
3072—, bastaría **1 chunk**, no los 27.

## 6. Orden recomendado

1. Decisiones humanas (§A y §B del paquete de decisiones) — sin costo de cómputo.
2. Corregir las 2 URLs y reverificar las 3 fuentes con `run_by` real.
3. RW-0005: `fda_part11` + `alcoa_plus` (20,1 h) ⇒ cierra el primer documento completo.
4. RW-0006 (URS, 6,7 h) ⇒ sustituye la baseline histórica del motor anterior.
5. Los 3 DS (7,4 h en total).
6. AGT-APP sobre los 5 documentos `OTHER`/`REPORT`/`DRAWING`, y decisión T-039.
7. OCR de RW-0001 y RW-0003 — alcance propio, no estimado aquí.
