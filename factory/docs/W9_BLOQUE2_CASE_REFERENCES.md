# W9 Bloque 2 (Opción A) — Dossier cita análisis de casos por ID+versión

**Estado:** implementado y verificado en vivo (2026-07-10). Aprobado por
Cesar en chat: "apruebo la Opción A: el dossier debe referenciar análisis
de casos por ID y versión, no copiar ni adaptar el texto dentro del
dossier", con 8 campos mínimos exigidos explícitamente.

## Qué resuelve

Hasta W8 Bloque 1, un análisis de caso `accepted` (W7/W7.1) quedaba
aislado: informativo, sin poder citarse desde ninguna sección del dossier
de validación (W6.2). Este bloque conecta ambos flujos **sin fusionarlos**:
el dossier puede ahora citar un análisis aceptado, pero:

- el dossier sigue aprobándose con `approve` (formal, Part 11);
- el caso sigue decidiéndose con `accept`/`reject`/`request_changes` (ya
  existente, más liviano);
- **son dos auditorías separadas** — la cita nunca reescribe ni copia el
  evento `case_analysis_decision` original, solo guarda su `entry_hash`
  para verificación cruzada.

## Diseño (Opción A, aprobada — se descartó Opción B explícitamente)

`documents[doc_id].case_references` en `dossier.yaml`: una lista de
punteros verificables, nunca el texto del análisis. Cada referencia trae
exactamente los 8 campos mínimos exigidos por Cesar + 2 de gobierno de la
propia acción de citar:

| Campo | Contenido |
|---|---|
| `case_id` | id del caso en `case_memory` |
| `analysis_version` | versión del registro citado |
| `mission_id` | `project_id` del dossier (mismo scope, no cruza misiones) |
| `status` | siempre `"accepted"` — único estado citable |
| `analysis_pointer` | ruta lógica a `regulatory/case_analyses/<mission>/<case>/vNN.json` |
| `analysis_sha256` | SHA-256 real del archivo `vNN.json` — integridad |
| `decided_at` / `decided_by` / `decision` | decisión humana original (`accept`) |
| `audit_event_hash` | `entry_hash` real del evento `case_analysis_decision` — cross-check contra la cadena |
| `linked_at` / `linked_by` | quién citó y cuándo (acto propio, auditado aparte) |

Cero texto: el objeto no tiene ni `response` ni `prompt`. Fuente de verdad
del contenido del análisis sigue siendo únicamente
`regulatory/case_analyses/`.

## Implementación

- `factory/services/dossier_case_reference_service.py` (nuevo) —
  `link_case_reference(project_id, doc_id, case_id, analysis_version,
  linked_by)`. Reglas duras: solo análisis `accepted` (422 si no); doc
  debe existir y estar generado (404/409); idempotente por
  `(case_id, analysis_version)` (409 en duplicado); nunca toca
  `content_sha256`/`status`/`approved_by` del documento citado; falla
  (500, sin escribir) si no encuentra el evento de auditoría exacto de la
  decisión `accept` — nunca crea una referencia no verificable.
- `factory/core/audit_writer.py` — nuevo evento válido
  `dossier_case_reference_linked`.
- `factory/api/routes/layer9.py` — `POST
  /missions/{project_id}/validation-package/documents/{doc_id}/case-references`.
  Lectura reutiliza el `GET .../documents/{doc_id}` ya existente (el campo
  nuevo simplemente aparece en `meta.case_references`, sin endpoint nuevo).
- `factory/tests/test_dossier_case_reference.py` (nuevo, 10 tests): estado
  no-accepted rechazado, campos completos, hash real, duplicado 409, doc
  inexistente/no-generado, nombre reservado 422, aprobación del documento
  intacta, exactamente 1 evento de auditoría sin reescribir el original,
  lectura vía `read_document`.

## Verificación en vivo (no solo tests)

Citado real: `openfda_enforcement:D-0546-2026` v1 (accepted en Bloque 1) →
`oos_hplc_investigator` / `data_integrity_assessment`.

- `POST .../case-references` → 200, referencia con los 10 campos.
- `audit_event_hash` de la referencia verificado **byte a byte** contra el
  `entry_hash` real del evento `case_analysis_decision` en
  `factory_audit.jsonl` — coinciden.
- Duplicado del mismo `(case_id, version)` → 409.
- `GET .../data_integrity_assessment` tras citar: `status` y
  `content_sha256` **idénticos** a antes de citar (`needs_human_review`,
  `a35ddef3…`), `agent_proposal` (W6.5) intacto, `case_references` con 1
  entrada — la citación no tocó nada del modelo de aprobación existente.
- Cadena de auditoría: 319 → 320 (+1 `dossier_case_reference_linked`).
- `factory_selfcheck.sh` → PASS=4 FAIL=0, pytest 451 passed (441 + 10
  nuevos, sin regresiones). `aria-*`/`hotelbot-*` intactos.
- `cases.jsonl` y los eventos `case_analysis_decision` originales:
  intactos (nunca reescritos).

## Fuera de alcance de este bloque (según lo aprobado)

No se implementa Opción B (incorporación de texto). No se toca el modelo
de aprobación del dossier ni el de decisión de casos. No hay endpoint de
"deslinkeo" (unlink) — no fue pedido; si se necesita, es un cambio
pequeño y separado. No se avanza a Bloque 3 (segunda fuente regulatoria).
