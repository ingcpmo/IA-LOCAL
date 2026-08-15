# E. Plan de experimento A/B/C (§21) — DISEÑO, NO EJECUCIÓN

**Estado**: diseño puro. Ninguna llamada LLM autorizada por este
documento. Requiere `PILOT_EXECUTION` firmada (`human_confirmed`) antes
de cualquier ejecución real — familia de decisión separada de
`CORPUS_AUTHORIZATION`/D4 (ver skill `gmp-recall-pipeline`). **Nunca
proponer una `PILOT_EXECUTION` nueva si ya existe una vigente con
presupuesto** — usar la que el resolver seleccione.

## Objetivo

Determinar si una representación estructurada (Table/EvidenceUnit)
cambia el resultado de juicio sobre P6/P7 (dilución tabular), sin repetir
el error de diseño ya corregido en R2 (asumir que resolver una etapa del
pipeline automáticamente resuelve el juicio final).

## Brazos, mismo fixture 7P+2N, mismo modelo, mismos prompts gobernados, mismo corpus

- **A — baseline actual**: extractor actual (pdfplumber) → chunking por
  página fija (`build_page_chunks`) → retrieval actual (fusión
  BM25+embeddings) → LLM. **Ya medido, costo cero** — es el estado
  R2/R1.7 ya cerrado. No requiere llamadas nuevas.
- **B — nueva normalización sin DOM**: aplica la corrección de la
  asimetría furniture LLM/verificador (ver `INFORMATION_LOSS_ANALYSIS.md`)
  antes del chunking, sin construir ninguna entidad DOM nueva. Mismo
  retrieval, mismo LLM. Barato: solo requiere re-chunking + re-run de
  juicio sobre los casos afectados.
- **C — representación estructurada**: extrae `Table` vía
  `pdfplumber.extract_tables()` para las páginas de P6/P7, separa la
  prosa relevante como `EvidenceUnit` aislado del contenido tabular
  circundante, construye el prompt con la prosa aislada al frente (mismo
  patrón que ya se usó para el pool de fusión perfecto en
  `PILOT_EXECUTION-2026-012`). Retrieval y LLM sin cambio.

## Métricas (mismas para los 3 brazos)

extraction fidelity, structure preservation, retrieval recall, evidence
recall, criterion recall, anchoring (validación A), semantic validation
(B/C/D), conclusión final, falsos positivos, falsos negativos.

## Criterio inviolable

N1 (ANNEX11_4) y N2 (weak keyword, tabla de contenidos) DEBEN seguir
rechazándose en los 3 brazos. Una mejora que sube recall pero rompe
alguno de los dos negativos **no es una mejora** — se descarta sin
excepción, mismo criterio ya aplicado en R2.

## Dimensionamiento honesto — replay antes de gastar llamadas nuevas

Patrón ya validado en el proyecto (R2: 3 mediciones independientes, la
mayoría replay sobre checkpoints pagados):

| Fase | Qué responde | Costo LLM | Prerequisito |
|---|---|---|---|
| 0 | Brazo A — ya medido, replay total | **0 llamadas** | Ninguno — ya cerrado |
| 1 | Extraer `Table` real de P6/P7 vía `pdfplumber.extract_tables()`, medir si la tabla realmente se separa limpiamente de la prosa (validación puramente mecánica, sin LLM) | **0 llamadas** | Ninguno |
| 2 | Brazo B — re-chunking con fix de furniture, replay de juicio SOLO si existe un checkpoint reejecutable ya pagado que cubra los casos afectados; si no existe, requiere llamadas nuevas mínimas (estimar: 1 llamada por checkpoint, 2 checkpoints conocidos = P3 y el caso de furniture) | 0-2 llamadas nuevas | `PILOT_EXECUTION` vigente con presupuesto |
| 3 | Brazo C — construir `EvidenceUnit` aislado para P6/P7 específicamente (2 casos), 1 llamada de juicio por caso | **2 llamadas nuevas como máximo** | `PILOT_EXECUTION` vigente con presupuesto; Fase 1 debe confirmar primero que la tabla se separa limpiamente — si no, no tiene sentido gastar las 2 llamadas |

**Total máximo de llamadas nuevas para responder la pregunta de esta
auditoría: 2** (brazo C, solo P6/P7). Todo lo demás es mecánico o replay.
Nunca proponer una corrida única larga — el orden de fases existe
precisamente para poder detenerse si la Fase 1 (gratis) ya muestra que la
tabla no se separa limpiamente, o si Fase 2 (barata) ya resuelve el caso
sin necesitar Fase 3.

## Resultado esperado de este documento

`EXPERIMENT_COST = 0 llamadas garantizadas (Fases 0-1) + hasta 2 llamadas
condicionadas a que Fase 1 confirme separación limpia y exista
PILOT_EXECUTION vigente con presupuesto`. Ninguna ejecución comienza sin
aprobación explícita de Cesar sobre cuál `PILOT_EXECUTION` usar (o si se
requiere una nueva — decisión suya, no de Capa 8).

## ACTUALIZACIÓN 2026-08-14 — Fase 1 EJECUTADA (mecánica, 0 llamadas LLM)

Ejecutada vía `CONTINUACION_FASE0_P4_FASE1.md` Bloque 2, dentro de
`factory-api` (pdfplumber ya instalado, solo lectura, sin tocar código).

**Resultado por caso**:

- **P4/P6** (RW-0011 p.12, mismo chunk): `extract_tables()` separa
  limpiamente la tabla de señales I/O (3 filas) de la prosa relevante
  (110 caracteres, fuera de cualquier `Table.rows`). **Fase 3 JUSTIFICADA
  para este caso.**

  **CORRECCIÓN 2026-08-15**: P4 (`alcoa_plus_agent`, prompt ALCOA) y P6
  (`fda_cgmp_211_agent`, prompt cGMP 211) son AGENTES/PROMPTS distintos —
  `evaluate_chunked()` toma un solo `prompt_path` por llamada, así que
  aunque comparten el mismo chunk fuente, requieren **2 llamadas LLM
  separadas** (una por agente), no 1 como se afirmó originalmente aquí.
  Gobernanza verificada (`corpus_runner._select_pilot_execution_instance`,
  sin proponer ninguna `PILOT_EXECUTION` nueva): `RW-0011` autorizado,
  resolver selecciona `PILOT_EXECUTION-2026-010` (ACTIVE, `max_calls=25`,
  `authorizes_corpus=False`) — presupuesto de sobra para 2 llamadas.
  `PILOT_EXECUTION-2026-004` (ACTIVE, `max_calls=60`) co-cubre el mismo
  lote y lista P6 explícitamente en su scope declarado.
- **P7** (RW-0012 p.13, documento real distinto): `extract_tables()` no
  encuentra ninguna tabla de contenido real en esta página (solo el
  bloque de cabecera). La prosa relevante ya vive en contexto limpio, sin
  dilución tabular. **Fase 3 NO se justifica para P7 bajo este diseño**
  — no hay nada que aislar. Ver `BOTTLENECK_DIAGNOSIS.md` (recalificado al
  bucket de P2/P5, límite de modelo, no representación).

**Costo real de llamadas LLM de esta corrida (Bloque 0 + Bloque 2):
0** — confirmado, todo el diagnóstico fue mecánico/replay de extracción,
sin invocar Ollama ni consumir presupuesto de ninguna `PILOT_EXECUTION`.

**Ajuste al presupuesto de Fase 3**: máximo **1 llamada LLM** (P4+P6 en
el mismo prompt), no 2 — el caso P7 queda fuera de alcance de este
experimento tabular. Sigue pendiente de aprobación de Cesar antes de
ejecutarse, y de la verificación de qué `PILOT_EXECUTION` vigente
seleccionaría el resolver.

`CHECKPOINT_PRESERVATION`: comprometido para cuando la Fase 3 real se
ejecute — no aplica todavía porque Fase 3 no se ha corrido en esta
sesión (cero llamadas LLM realizadas).
