# 04 — Gobernanza de Datos

## `decisions_v2.jsonl`

213 líneas al momento de esta auditoría. Distribución por familia
(`decision_family`), contada en vivo:

| Familia | Instancias |
|---|---|
| D2 | 68 |
| D1 | 59 |
| ARTIFACT_VERSION | 18 |
| PILOT_EXECUTION | 18 |
| LEGACY_UNMAPPED | 9 |
| SOURCE_CURRENCY | 8 |
| RECORD_ANNOTATION | 7 |
| APPLICABILITY_MATRIX | 6 |
| D4 | 4 |
| SOURCE_REGISTRATION | 4 |
| SOURCE_ORIGIN_VERIFICATION | 4 |
| AUDIT_EXCEPTION | 2 |
| CORPUS_AUTHORIZATION | 2 |
| EMBED_EXECUTION | 2 |
| D3 | 1 |
| D5 | 1 |

Las dos instancias `EMBED_EXECUTION` corresponden al commit `c2c06bb`
(familia nueva de esta corrida). Las dos últimas instancias del archivo
(`PILOT_EXECUTION-2026-017`/`-018`) fueron **append** puro por el commit
`99f36c3` — ninguna línea previa fue reescrita.

**Qué fue append:** las 2 líneas nuevas de `PILOT_EXECUTION` en
`decisions_v2.jsonl`. El esquema es append-only por diseño
(`decision_record_v1`): cada instancia tiene su propio
`decision_instance_id`, y una corrección se modela como una **nueva
instancia** que referencia `confirms_instance_id` o
`supersedes_instance_id` — nunca se edita una línea existente in place.

## `review_queue.jsonl`

34 líneas al momento de esta auditoría. Distribución por `status`:

| status | Entradas |
|---|---|
| pending | 12 |
| superseded | 10 |
| approved | 6 |
| rejected | 3 |
| confirmed | 2 |
| returned | 1 |

El commit `99f36c3` tocó esta cola de dos formas distintas:

**Append puro (6 líneas nuevas, `status: pending`):** entradas nuevas para
RW-0005 sobre `21_CFR_11.10(e)` — runs `chunked-2678358a06b3`,
`chunked-e6994ea8e953`, `chunked-d9b5bc77c9db`, `chunked-c2c7dff6900c`,
`chunked-e8208618982a` (5 corridas nuevas) más la sexta que corresponde a la
mutación descrita abajo.

**Mutación controlada (1 línea, `pending` → `confirmed`):**
`finding-chunked-50534e75927c-21_CFR_11.10(e)`. El diff real
(`git show 99f36c3`) muestra que la línea completa fue reemplazada — no es
un archivo append-only estricto a nivel de línea, sino un JSONL donde cada
`rc_id` tiene como máximo una línea "viva" que se reescribe al cambiar de
estado. La reescritura agregó:
```
"status": "confirmed"
"reviewer": "cesar"
"reviewed_at": "2026-08-12T21:13:14.973790+00:00"
"human_confirmed_evidence": {"page": null, "quote": "mejora",
  "confirmed_by": "cesar", "confirmed_at": "2026-08-12T21:13:14.973790+00:00"}
```

**Justificación de la mutación:** es la firma humana de Cesar sobre un
hallazgo pendiente — el mecanismo de revisión previsto (`POST
/review/findings/{rc_id}/decide`), no una edición arbitraria. El propio
sistema de gobernanza reconoce una limitación sobre esta firma específica:
la entrada `RECORD_ANNOTATION-2026-007` en `decisions_v2.jsonl` (7ª de esa
familia) declara por escrito que `human_confirmed_evidence.quote="mejora"`
**no constituye una cita de evidencia real** — la conclusión original era
`EVALUATION_INCOMPLETE` bloqueada por `CONTRADICTION_BLOCKED_POSITIVE_CONCLUSION`,
un tipo de conclusión donde "confirmar" significa aceptar el bloqueo, nunca
confirmar evidencia. La anotación declara explícitamente que esta entrada
**no debe entrar al Golden Dataset** bajo ninguna forma. La entrada original
en `review_queue.jsonl` nunca se reescribió para ocultar esto — la
corrección vive como una anotación separada, append-only, que referencia el
`rc_id` original.

## `w5_human_decisions.jsonl`

7 líneas. D1–D5 originales (2026-07-29), una corrección de D1
(`reverification_cadence_months` 1→3, con `correction_reason` explícito y
`supersedes_recorded_at` apuntando a la entrada original — la original
**no** se borró) y D6 (2026-08-13, commit `d224b24`, auditada en esta
corrida).

**Qué fue append:** las 7 líneas son append puro — incluida la corrección de
D1, que se modela como una nueva línea con `record_type: correction` y
`corrected_fields` explícito, no como edición de la línea original.

**Qué fue mutación controlada:** ninguna en este archivo — es el único de
los tres estrictamente append-only a nivel de línea en esta auditoría.

## Justificación general

El patrón observado en los tres archivos es consistente con la regla
permanente "el documento original es la fuente maestra — nunca se
sobrescribe" (`CLAUDE.md`): incluso donde `review_queue.jsonl` reescribe una
línea completa al cambiar de estado, el sistema mantiene un rastro de
auditoría paralelo (`RECORD_ANNOTATION`) que documenta cualquier limitación
o corrección sobre esa mutación, en vez de dejarla como un hecho silencioso.
Ninguna corrección de esta auditoría requirió tocar código de gobernanza —
la anotación correctiva ya existía, escrita durante R3-T1.8.
