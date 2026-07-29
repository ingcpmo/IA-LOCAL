# W5 V2 — Estado de PAUSA de los efectos de D1–D5

**Fecha de la pausa:** 2026-07-29 (UTC)
**Autorizado por:** Cesar (Capa 9)
**Registrado por:** Claude Code (Capa 8), corrida de solo lectura
**Commit del árbol al momento de escribir:** `bd70506`

> Este documento es un **documento de estado**. NO es un registro de decisión y
> NO se escribe en `factory/layer9/decisions/w5_human_decisions.jsonl` ni en
> `factory/audit/factory_audit.jsonl`. Las decisiones ya registradas quedan
> intactas.

---

## 1. Alcance de la pausa

Quedan **PAUSADOS los efectos** de las cinco decisiones D1–D5:

| decision_id | Efecto pausado |
|---|---|
| `D1_regulatory_sources` | No se reverifica ninguna fuente; no se corrigen URLs; no se cambia `regulatory_currency_status` |
| `D2_evidence_packs` | No se promueve, congela ni aprueba ningún Requirement Evidence Pack; `pack_lifecycle_status` permanece `DRAFT` |
| `D3_T039` | No se aplica la adjudicación de RW-0008; el allowlist conserva `processing_state: HUMAN_REVIEW_REQUIRED` |
| `D4_corpus_execution` | No se inicia el corpus; ALCOA+ permanece congelada; no se invoca Ollama |
| `D5_regenerate_qa_package` | No se regenera el paquete QA de 9 artefactos |

**Motivo:** evaluación de cobertura regulatoria previa a la ejecución.

**Condición de reanudación:** decisión de Cesar sobre el assessment de cobertura
(`REGULATORY_COVERAGE_ASSESSMENT_W5.md`) y, si procede, sobre los adendos
`D1-A` / `D2-A` (`W5V2_D1A_D2A_ADDENDUM_DRAFT.md`).

---

## 2. Las decisiones registradas NO se revierten

Las cinco decisiones fueron registradas el **2026-07-29 entre 00:15:15 y
00:15:59 UTC**, todas con `decision=APPROVE`, `approved_by="cesar"`,
`decision_origin="human_confirmed"`.

Fichero: `factory/layer9/decisions/w5_human_decisions.jsonl`
SHA-256: `5bdd0f29c323510f9db4292d531002b8b2d11eb7c2f7b4ceaeab0c9b87dadf19`

| decision_id | decision | approved_by | recorded_at (UTC) |
|---|---|---|---|
| `D1_regulatory_sources` | APPROVE | cesar | 2026-07-29T00:15:15.595879+00:00 |
| `D2_evidence_packs` | APPROVE | cesar | 2026-07-29T00:15:27.138934+00:00 |
| `D3_T039` | APPROVE | cesar | 2026-07-29T00:15:41.175454+00:00 |
| `D4_corpus_execution` | APPROVE | cesar | 2026-07-29T00:15:50.091840+00:00 |
| `D5_regenerate_qa_package` | APPROVE | cesar | 2026-07-29T00:15:59.263828+00:00 |

D1 registró además: `approved_source_ids="ALL"`,
`reverification_cadence_months=1`, `reverification_authority="cesar"`.

Ninguna de estas líneas se edita, revierte ni elimina. La pausa es
**operativa**: las decisiones siguen aprobadas; lo que no se ejecuta son sus
consecuencias.

---

## 3. Estado parcial previo — qué se había ejecutado antes de la pausa

**Resultado de la verificación: NADA de D1–D5 se ejecutó.** Los cinco efectos
están en estado cero. Evidencia comprobada, no asumida:

### 3.1 El contrato ya declaraba efectos nulos por diseño

El evento de auditoría del endpoint de decisiones emite literalmente
`side_effects_applied: false`
(`factory/docs/W5V2_CONTRATO_DECISIONES_IMPLEMENTADO.md`, commit `96812a3`):
registrar una decisión no reverifica fuentes, no promueve packs, no lanza
corridas, no descongela ALCOA+ y no cambia ningún estado regulatorio.

### 3.2 D1 — fuentes: sin reverificar

`factory/regulatory/sources/registry.json`
(SHA-256 `6c48dd1d84750bbfaf24c7000ba86e4527b5bd71f9fba10e9d3a026fbb17268a`)
mantiene las 3 fuentes normativas con:

- `regulatory_currency_status: pending_reverification` (las 3)
- `last_checked` / `reverification_due`: `null`
- URL de `mhra_gxp_di_guidance_2018` sigue apuntando a la página de aterrizaje
  `https://www.gov.uk/government/publications/guidance-on-gxp-data-integrity`,
  no al PDF — la corrección de URL prevista en D1 **no se aplicó**.

### 3.3 D2 — packs: siguen en DRAFT

`factory/regulatory/requirement_catalog/requirements.yaml`
(SHA-256 `6486405abecd729d85e32ec4a9af03cd13ad144162ebcb300ee9d25016202b8d`),
19/19 entradas con:

- `pack_lifecycle_status: DRAFT`
- `evidence_pack_status: human_drafted_provisional`
- `source_verification_status: PENDING_REVERIFICATION`
- `ready_for_regulatory_use: false`
- `production_eligibility: BLOCKED`

### 3.4 D3 — T-039: sin adjudicar

`factory/regulatory/scope/source_baseline_allowlist.yaml`
(SHA-256 `ddaca09324a2bb432643565374114f6d9fc338beab175f3fd72080cec0d6a96d`):
RW-0008 conserva `processing_state: HUMAN_REVIEW_REQUIRED` y
`doc_type: OTHER`. La adjudicación **no está aplicada**; el resto de este
assessment usa la clasificación vigente, como exige el punto 1.1 de las
instrucciones.

### 3.5 D4 — corpus: no se ejecutó; ALCOA+ sigue congelada

- El programador de ALCOA+ estaba fijado para `2026-07-29T01:05:46Z`
  (`START_EPOCH=1785287146`). **No arrancó.** El log del programador
  (`logs/execution_snapshots/alcoa_fsv12_11_20260728/scheduler.log`) registra:
  `[2026-07-28T13:26:06Z] CONGELADA por peticion de Cesar: scheduler 3344717
  detenido con SIGTERM.`
- `logs/fsv12_alcoa_20260729/` está **vacío** (0 ficheros).
- No hay proceso de corrida vivo (`ps`), ni entrada en `at` (no instalado), ni
  timer de systemd asociado, ni línea en `crontab` (solo las 4 tareas de
  operación: health, logs, RAM y backup).
- El snapshot congelado permanece intacto en el commit `c2d58e8`.

**Escritura reciente que NO es una corrida de corpus:** entre las 00:36 y las
01:06 UTC del 2026-07-29 se escribieron 71 ficheros en
`factory/regulatory/validation_evidence/`. Se inspeccionaron: **todos proceden
de la suite de pruebas**, no de una corrida real. Prueba directa:

| Modelo declarado | Ficheros | Naturaleza |
|---|---|---|
| `golden-dataset-fake` | 63 | Golden Dataset |
| `fake-model` / `fake-model-v1` | 78 | Dobles de prueba |
| `qwen2.5:7b-instruct-q4_K_M` | 18 | Nombre real, **proveedor simulado** |

Los 18 con nombre de modelo real llevan `model_digest: sha256:fake` /
`sha256:default-path`, `ollama_version: 0.0.0-test`, `document_sha256`
sintético (`sha-test`, `bbbb…`) y `wall_clock_ms` entre 0,0 y 1,5 ms. Una
llamada real a Ollama sobre estos documentos tarda minutos, no milisegundos.
**Cero llamadas a Ollama.**

### 3.6 D5 — paquete QA: no regenerado

El paquete más reciente es
`factory/qa_packages/PKG-FS-V1-2-REAL-CONTROLLED/v1/20260728/` (9 artefactos,
commit `d69a2f6`), **anterior** a las decisiones. No existe ningún directorio
`.../20260729/`.

### 3.7 Árbol de trabajo

`git status --short` no muestra modificado ningún artefacto de estado
regulatorio: la única entrada ` M` es
`factory/layer9/missions/r6_change_control.yaml`, preexistente y ajena a
D1–D5.

---

## 4. Consecuencia

`PARTIAL_EXECUTION_BEFORE_PAUSE_DOCUMENTED = false` — **no hubo ejecución
parcial que documentar**. La pausa se aplica sobre un estado limpio: las cinco
decisiones están aprobadas y ninguno de sus efectos se ha materializado.

Esto es favorable para la reanudación: si Cesar adopta los adendos D1-A/D2-A,
no hay trabajo ya ejecutado que haya que descartar por cambio de
`catalog_sha256`.
