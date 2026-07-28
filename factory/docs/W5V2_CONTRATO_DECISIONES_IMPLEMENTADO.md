# W5 V2 — Contrato IMPLEMENTADO de las decisiones D1–D5

> **Esto NO es el documento de autoridad.** El documento citado como autoridad,
> `docs_plan/W5V2_EJECUCION_DECISIONES_Y_CORPUS.md`, **no existe**: no está en
> disco, nunca estuvo en git (`docs_plan/` entero está fuera de control de
> versiones) y no aparece en el respaldo completo del árbol del 2026-07-28
> 16:48. No hay nada desde donde restaurarlo, y **no se ha inventado**: un
> documento de autoridad regulatoria fabricado sería peor que su ausencia.
>
> Este fichero describe **lo que está implementado hoy**, para que la
> comparación contra el documento de autoridad sea mecánica en cuanto
> aparezca. `W5_CONTRACT_ALIGNED` no puede evaluarse hasta entonces.

**Commit:** `96812a3` · **Fecha:** 2026-07-28

## Endpoints

| Método | Ruta | Auditoría | Notas |
|---|---|---|---|
| `GET` | `/api/v1/layer9/w5-decisions` | **ninguna** | Solo lectura. Verificado en vivo: 3 llamadas seguidas, 17654 → 17654 eventos |
| `POST` | `/api/v1/layer9/w5-decisions/{decision_id}` | **1 evento** | `layer9_decision_recorded`, `scope=w5_human_decision` |

## Identificadores

`D1_regulatory_sources` · `D2_evidence_packs` · `D3_T039` ·
`D4_corpus_execution` · `D5_regenerate_qa_package`

## Cuerpo del POST

| Campo | Tipo | Obligatorio | Aplica a |
|---|---|---|---|
| `decision` | `APPROVE` \| `PARTIAL` \| `REJECT` | sí | todas |
| `approved_by` | string, identidad real | sí | todas |
| `notes` | string | no | todas |
| `decision_date` | ISO-8601 | no (default: ahora UTC) | todas |
| `approved_source_ids` | `"ALL"` \| lista de `source_id` | **sí** | D1 |
| `reverification_cadence_months` | int | **sí** | D1 |
| `reverification_authority` | string | **sí** | D1 |
| `approved_pack_ids` | `"ALL"` \| lista | no | D2 |

Campos añadidos por el servidor, no aceptados del cliente:
`decision_origin="human_confirmed"`, `recorded_at`.

## Códigos de respuesta

| Código | Causa |
|---|---|
| `200` | Decisión registrada |
| `422` | Identidad genérica o vacía; `decision` inválida; `decision_id` desconocido; falta un campo obligatorio de D1 |
| `409` | Ya existe una decisión registrada para ese `decision_id` |
| `500` | Fallo inesperado |

Identidades rechazadas (`RESERVED_IDENTITIES`): vacío, `human`, `humano`,
`agent`, `agente`, `layer8_agent`, `auto`, `system`, `sistema`, `admin`,
`user`, `usuario`, `factory`, `capa8`, `capa9`, `layer8`, `layer9`, `claude`,
`qa`.

## Almacenamiento

`factory/layer9/decisions/w5_human_decisions.jsonl`, append-only, una línea
por decisión. **No existe hasta que se registre la primera** — el `GET` no lo
crea.

## Evento de auditoría

```json
{"event_type": "layer9_decision_recorded",
 "project_id": "gmpai_document_validation",
 "data": {"scope": "w5_human_decision", "decision_id": "...",
          "decision": "APPROVE|PARTIAL|REJECT", "approved_by": "...",
          "decision_origin": "human_confirmed", "decision_date": "...",
          "side_effects_applied": false}}
```

`side_effects_applied: false` es literal: registrar **no** reverifica fuentes,
no promueve packs, no lanza corridas, no descongela ALCOA+ y no cambia ningún
estado regulatorio. Ejecutar las consecuencias es un paso posterior y separado.

## Interfaz

Vista propia `Gobierno → Decisiones W5` (`#v-w5`), separada de la cola de
release candidates. La tarjeta D1 muestra, por cada una de las 3 fuentes:
`source_id`, regulación, URL oficial, versión, SHA-256 y estado actual; más
selector de fuentes aprobadas, cadencia, autoridad, firmante y notas, con
botones `APPROVE` / `PARTIAL` / `REJECT`.

## Diferencias a verificar cuando aparezca el documento de autoridad

1. Nombres exactos de los 5 `decision_id`.
2. Vocabulario de `decision` (¿solo APPROVE/PARTIAL/REJECT?).
3. Si D2–D5 exigen campos propios como D1.
4. Si el evento de auditoría debe tener un `event_type` propio en vez de
   reutilizar `layer9_decision_recorded`.
5. Si se exige firma doble o segunda revisión para alguna decisión.
6. Si `PARTIAL` en D1 debe forzar lista explícita de `approved_source_ids`
   (hoy se acepta `ALL` con cualquier `decision`).
