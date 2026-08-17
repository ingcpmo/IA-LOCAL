# Paquete de revisión — V2 (top-k fusion, juicio requisito-céntrico)

**Estado**: documento de revisión, NO ejecución. V2 ya está EJECUTADO y
COMPLETO (`stop_reason: BATCH_COMPLETE`, 0 errores). Nada de este paquete
dispara una llamada nueva ni un commit — solo organiza lo ya hecho para
la decisión de Cesar. Documentos fuente completos:
`docs_plan/V2_DISCREPANCY_REPORT_20260817.md` (bloqueo original),
`docs_plan/V2_DISCREPANCY_REPORT_20260817_ADENDA.md` (verificación de la
decisión arquitectónica), `docs_plan/V2_RESULTADO_FINAL_20260817.md`
(resultado crudo completo + ADRs).

──────────────────────────────────────────────────────────────────────
1. QUÉ SE EJECUTÓ (real, con presupuesto firmado por Cesar)
──────────────────────────────────────────────────────────────────────

| Autorización | Firma | Consumo |
|---|---|---|
| `PILOT_EXECUTION-2026-022` | Cesar, 2026-08-17T16:34:49Z | 24/25 llamadas de juicio |
| `EMBED_EXECUTION-2026-004` | Cesar, 2026-08-17T18:12:18Z | 8/10 consultas de embedding |
| Recalificación runtime 7B | — (técnica, previa a la 1ª llamada) | 2 llamadas |

Diseño ejecutado: `k=3` candidatos por requisito, evaluados de forma
independiente (sin agrupar en un solo prompt — corrige la ambigüedad de
atribución cruzada detectada en el diseño original), agregación
determinista vía `verify_sufficiency_aggregated()` ya existente. Sin
early-stop: los 3 candidatos completos por requisito quedan registrados.

──────────────────────────────────────────────────────────────────────
2. RESULTADO — tabla completa (8 triples, 7P+2N)
──────────────────────────────────────────────────────────────────────

| Caso | Requisito / Documento | Evidencia real encontrada | Estado |
|---|---|---|---|
| P1+N2 | `21_CFR_11.10(e)` RW-0005 | **SÍ** — cita de audit trail anclada | `EVALUATION_INCOMPLETE` (positivo, pendiente de anclaje A/B/C/D completo) |
| P3 | `ANNEX11_17` RW-0005 | **SÍ** — caso que motivó M2 (retención/Data) | `EVALUATION_INCOMPLETE` (positivo, pendiente de anclaje) |
| P2 | `21_CFR_11.10(g)` RW-0005 | No, en los 3 candidatos evaluados | `EVIDENCE_NOT_LOCATED_IN_CANDIDATES` — encolado |
| P4 | `ALCOA_ATTRIBUTABLE` RW-0011 | No | `EVIDENCE_NOT_LOCATED_IN_CANDIDATES` — encolado |
| P5 | `ALCOA_CONTEMPORANEOUS` RW-0005 | No | `EVIDENCE_NOT_LOCATED_IN_CANDIDATES` — encolado |
| P6 | `21_CFR_211.68(b)` RW-0011 | No | `EVIDENCE_NOT_LOCATED_IN_CANDIDATES` — encolado |
| P7 | `21_CFR_211.68(b)` RW-0012 | No | `EVIDENCE_NOT_LOCATED_IN_CANDIDATES` — encolado |
| N1 | `ANNEX11_4` RW-0005 | No (correcto, es negativo) | `CROSS_REFERENCE_MISSING` — rechazado, sin encolar |

**Recall de juicio real: 2/7 (P1, P3)** — idéntico al techo ya confirmado
por Palanca A (2026-08-15, [[project-bottleneck-confirmado-r4]]), ahora
con la arquitectura de recuperación ya corregida (M2/M3,
`retrieval_recall_at_5=7/7` en V1). Esto es una **réplica**, no una
mejora ni un empeoramiento.

**N2 — limitación de diseño, no resultado**: comparte triple con P1 por
decisión de ahorro de presupuesto tomada al firmar
`PILOT_EXECUTION-2026-021`. No hay forma de leer del resultado si el
sistema habría rechazado N2 evaluado por separado. El criterio "2/2
negativos rechazados" queda como "N1: 1/1 verificable, rechazado
correctamente; N2: no medible con este diseño".

──────────────────────────────────────────────────────────────────────
3. HALLAZGOS PENDIENTES DE ADJUDICACIÓN HUMANA (4, en `review_queue.jsonl`)
──────────────────────────────────────────────────────────────────────

Ninguno auto-cerrado, ninguno auto-confirmado — cada uno trae los 3
candidatos recuperados (BM25+embeddings+fusión) con su cita, pero
**ningún candidato tiene anclaje A/B/C/D**, marcado explícitamente en
cada entrada (`candidates_honesty_note`).

- `finding-chunked-ead024e9ec9a-21_CFR_11.10(g)` — RW-0005, P2
- `finding-chunked-e857bb63e15b-ALCOA_CONTEMPORANEOUS` — RW-0005, P5
- `finding-chunked-13b0c79be584-21_CFR_211.68(b)` — RW-0011, P6
- `finding-chunked-ced9f8de62e7-21_CFR_211.68(b)` — RW-0012, P7

Acción requerida de Cesar por cada uno: confirmar si alguno de los 3
candidatos mostrados contiene la evidencia real (revisión manual del
documento) o si el gap es real y se abre NCR/CAPA candidate.

──────────────────────────────────────────────────────────────────────
4. LO QUE ESTE RESULTADO CIERRA Y LO QUE ABRE
──────────────────────────────────────────────────────────────────────

**Cierra**: la hipótesis de que el problema era de recuperación/pipeline.
M2 (chunking por sección) + M3/V1 (fusión BM25+embeddings, top-k) ya
llevan el chunk correcto al modelo en 7/7 casos. Con el chunk correcto
presente, el modelo 7B solo lo reconoce en 2/7. **No hay más palanca de
pipeline que probar sin cambiar el modelo o el prompt de juicio mismo.**

**Abre**: la decisión ya empaquetada en
`docs_plan/PAQUETE_DECISION_ESTRATEGICA.md` (Palancas A/B/C, 2026-08-15)
sigue siendo la decisión real pendiente — este resultado de V2 es
evidencia adicional que la refuerza (tercera confirmación del mismo
techo, con la arquitectura de recuperación ya descartada como causa),
no reemplaza esas opciones.

──────────────────────────────────────────────────────────────────────
5. ESTADO DEL REPOSITORIO — sin commit
──────────────────────────────────────────────────────────────────────

Sin commitear, esperando aprobación explícita:

```
M  factory/layer9/decisions/decisions_v2.jsonl        (4 decisiones: -021/-022/-003/-004)
M  factory/layer9/review_queue.jsonl                  (4 hallazgos nuevos encolados)
M  factory/regulatory/model_qualification/qualification_record.json   (recalificación real 7B)
M  factory/regulatory/model_qualification/runtime_calibration_record.json
?? docs_plan/V2_DISCREPANCY_REPORT_20260817.md
?? docs_plan/V2_DISCREPANCY_REPORT_20260817_ADENDA.md
?? docs_plan/V2_RESULTADO_FINAL_20260817.md
?? docs_plan/PAQUETE_REVISION_V2_20260817.md
?? factory/docs/design/regulatory_redesign_v2/v2_top_k_fusion_judgment_measurement.py
?? factory/regulatory/pilot_run/v2_top_k_fusion_20260817/   (checkpoints, raw_responses, resultado)
```

**Nota aparte, no relacionada con V2**: 4 archivos `.docx` bajo
`factory/regulatory/pilot_run/dry_run_validation_r4_t1_1v2/` aparecen
modificados (mismo tamaño en bytes, sin diff de contenido legible — probable
metadata interna del .docx) desde ANTES de esta sesión de V2. No los toqué
ni sé el origen del cambio — señalado para que Cesar decida si investigar
o descartar.

──────────────────────────────────────────────────────────────────────
DECISIÓN REQUERIDA DE CESAR
──────────────────────────────────────────────────────────────────────

1. ¿Adjudicar ahora los 4 hallazgos pendientes en `review_queue.jsonl`,
   o dejarlos para otra sesión?
2. ¿Commitear el estado actual (decisiones, resultado, review_queue,
   documentos) tal cual, en un solo commit "V2: ejecución real +
   resultado + ADRs"?
3. ¿Avanzar sobre Palancas A/B/C (`PAQUETE_DECISION_ESTRATEGICA.md`) con
   este resultado como tercera confirmación, o mantener en pausa?

Sin acción hasta recibir instrucción explícita sobre estos 3 puntos.
