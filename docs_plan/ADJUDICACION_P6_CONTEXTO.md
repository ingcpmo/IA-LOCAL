# Contexto para adjudicación humana — 2 hallazgos P6 pendientes

**Estado**: documento de contexto, NO adjudicación. Ninguna clasificación
de salida sugerida — eso es decisión exclusiva de Cesar/QA. Preparado
según `docs_plan/CONTINUACION_CIERRE_ESTRATEGICO.md` Bloque 2.

## Las 2 entradas reales en `factory/layer9/review_queue.jsonl`

Ambas `status: pending`, sin `decision_origin` (higiene de gobernanza
verificada — ningún campo de decisión humana fabricado, ver `RISK_
REGISTER.md`/reporte de ejecución).

### Entrada 1

```json
{
  "rc_id": "finding-chunked-554544f4090f-21_CFR_211.68(b)",
  "project_id": "RW-0011",
  "enqueued_at": "2026-08-15T00:53:41Z",
  "requirement_id": "21_CFR_211.68(b)",
  "agent_id": "fda_cgmp_211_agent",
  "conclusion": "PROVISIONAL_GAP",
  "review_flags": ["SOURCE_PENDING_REVERIFICATION",
                    "BASELINE_GAP_PENDING_HUMAN_REVIEW_KNOWN_PARAPHRASE_LIMIT"],
  "evidence_quote": ""
}
```

Corresponde a la corrida REAL sin aislar (chunk original con la tabla de
señales I/O presente, texto completo tal como lo produce el pipeline de
producción hoy).

### Entrada 2

```json
{
  "rc_id": "finding-chunked-510444cedc9b-21_CFR_211.68(b)",
  "project_id": "RW-0011",
  "enqueued_at": "2026-08-15T01:16:17Z",
  "requirement_id": "21_CFR_211.68(b)",
  "agent_id": "fda_cgmp_211_agent",
  "conclusion": "PROVISIONAL_GAP",
  "review_flags": ["SOURCE_PENDING_REVERIFICATION",
                    "BASELINE_GAP_PENDING_HUMAN_REVIEW_KNOWN_PARAPHRASE_LIMIT"],
  "evidence_quote": ""
}
```

Corresponde al EXPERIMENTO C (mismo requisito, mismo documento, texto
con la tabla removida y la prosa en contexto narrativo limpio).

## Contexto que la corrida generó (no una recomendación)

Ambas entradas son el MISMO requisito (`21_CFR_211.68(b)`) sobre el
MISMO documento (RW-0011, página 12/13) y el MISMO pasaje real:
*"with the proper credentials, the input points can be simulated for
calibration or other maintenance activities."* — verificado por lectura
directa del PDF.

El Experimento C acaba de demostrar, con evidencia real (checkpoints
`chunked-8e2b20bfa511` y `chunked-510444cedc9b`), que el modelo de
juicio **no reconoció esta evidencia ni siquiera cuando se le presentó
aislada de cualquier ruido tabular** — mismo resultado con y sin la
tabla presente. Esto es consistente con el mismo patrón ya confirmado
para P2/P5 (evidencia perfectamente aislada, juicio sin cambio, R2).

**Nota para tu revisión** (contexto, no conclusión): estas 2 entradas
tienen probabilidad elevada de ser un *miss* de reconocimiento del
modelo sobre evidencia real presente en el documento, no necesariamente
una brecha documental genuina. Al mismo tiempo — hallazgo adicional de
esta misma corrida (`docs_plan/CONTINUACION_CIERRE_ESTRATEGICO.md`
Bloque 0) — el Evidence Pack real de `21_CFR_211.68(b)` para este agente
exige 7 criterios amplios (control técnico de cambios en registros
maestros, identificación de personal autorizado, exactitud de I/O,
etc.), de los cuales la oración de calibración/credenciales solo toca
uno tangencialmente. Es decir: **incluso si el modelo hubiera "visto"
la evidencia, es razonable que la mayoría de los 7 criterios siguieran
sin cumplirse** — no se puede descartar que `PROVISIONAL_GAP` sea, en
efecto, una lectura correcta de evidencia genuinamente insuficiente
frente a un requisito amplio, no solo un fallo de recuperación.

Recomendación de proceso (no de resultado): revisar el texto de la
página 12/13 de RW-0011 directamente contra los 7 criterios reales antes
de confirmar cualquiera de las 2 entradas como brecha o como falso
positivo del modelo.

## Candidatos de fusión

`"candidates": []` en ambas entradas — no hay candidatos adicionales de
recuperación registrados en este despacho (el chunk usado fue
pre-seleccionado a mano para el experimento, no vino de una búsqueda de
fusión top-k real).
