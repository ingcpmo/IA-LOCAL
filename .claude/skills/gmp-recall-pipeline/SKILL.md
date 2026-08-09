---
name: gmp-recall-pipeline
description: Conocimiento operativo del pipeline de evaluación LLM del Analizador Documental GMP (chunked_engine → Ollama → evidence_verifier), la configuración evaluation_profile H2H4 que productiza el recall medido, el fixture set de recall como único instrumento de medición, y la prohibición central de nunca aflojar los validadores para inflar métricas. USAR SIEMPRE que la tarea toque recall, chunked_engine, corpus_runner, evidence_verifier, fixture set, evaluation_profile, PILOT_EXECUTION, o el roadmap del analizador GMP (docs_plan/ROADMAP_ANALIZADOR_GMP.md).
---

# GMP recall pipeline — conocimiento operativo

## Qué es esto

El pipeline de evaluación LLM que usa el Analizador Documental GMP para
juzgar si un documento cumple un requisito regulatorio. Vive en `factory`
(:9000) — separado de `gmp-api` (:8000, producto base de consulta
conversacional). Nunca se cruzan: el analizador no toca `gmp-api`, y
`gmp-api` no tiene ninguna de estas piezas.

## Dónde vive cada pieza (rutas reales)

| Pieza | Ruta |
|---|---|
| Motor de evaluación por chunks | `factory/engines/gmpai_integrity/chunked_engine.py` |
| Cliente Ollama (timeouts reales, ~1200s+ piso) | `factory/engines/gmpai_integrity/ollama_client.py` |
| Verificador determinista de citas ancladas (validación A) | `factory/regulatory/evidence_verifier.py` |
| Catálogo de requisitos (Evidence Pack) | `factory/regulatory/requirement_catalog/requirements.yaml` |
| Orquestación de corridas piloto | `factory/regulatory/corpus_runner.py` |
| Fixture set de recall (instrumento único de medición) | `docs_plan/W5V2_RECALL_FIXTURE_SET_DRAFT.md` |
| Resultados de experimentos H1-H4 | `docs_plan/W5V2_RECALL_EXPERIMENTS_RESULTADOS.md` |
| Plan de remediación (ON_HOLD) | `docs_plan/W5V2_REMEDIACION_RECALL_MODELO.md` |
| Roadmap del analizador (R0-R5) | `docs_plan/ROADMAP_ANALIZADOR_GMP.md` |
| Spec del contrato de R1 | `docs_plan/R1_SPEC_CONTRATO_ANALIZADOR.md` |
| Productización de H2+H4 (R1.5) | `docs_plan/R1_5_PRODUCTIZACION_H2H4.md` |

## La lección estructural (por qué existe este skill)

El 2026-08-09, el smoke E2E de R1 corrió por el flujo real de producción
y el caso P5 (que SÍ había anclado en un experimento) **no ancló**. Causa:
la configuración H2+H4 (la única que midió recall >0 en `W5V2_RECALL_
EXPERIMENTS_RESULTADOS.md`) vivía solo en scripts de diagnóstico aislados
(`h2_experiment.py`/`h4_experiment.py`, scratchpad de sesión, nunca
versionados) — nunca se llevó al motor real. **Nadie lo había notado**
porque los experimentos corrieron fuera de `corpus_runner`.

**Regla derivada, sin excepción**: ninguna configuración "ganadora"
medida en un script ad hoc se asume heredada por producción. Toda config
que mejora una métrica real se **productiza y se revalida por el flujo
real** (el mismo camino que usará en producción) antes de construir
cualquier cosa encima. Medir en un script y suponer que el motor real
hace lo mismo es exactamente el defecto que causó este hallazgo.

## evaluation_profile — qué es, cómo se invoca

`chunked_engine.evaluate_chunked(..., evaluation_profile="BASELINE"|"H2H4",
target_requirement_ids=[...])` y `corpus_runner.run_pilot_sample_batch(...,
evaluation_profile="H2H4")` (usa `PilotSampleUnit.requirement_id`
automáticamente).

- **BASELINE** (default, sin cambios): todos los checkpoints admitidos del
  agente en una sola llamada por chunk. Midió **0/7** de recall.
- **H2H4**: filtra `meta["checkpoints"]` a `target_requirement_ids` ANTES
  de `evidence_pack_gate`/`build_prompt`/`output_token_budget`/
  `build_run_fingerprint` — reutiliza el prompt/schema GOBERNADO real sin
  tocarlo (reproduce fielmente H2, la parte que realmente subió el recall
  a **2/7**). El perfil se registra en `run_fingerprint`/
  `preflight_metadata`; cambiar de perfil invalida cualquier cache de
  checkpoint por diseño.

**Nota honesta de alcance, no confundir**: esta implementación **no**
reproduce el schema mínimo de H4 al pie de la letra — eso vive en el
`common_contract` gobernado de cada prompt YAML
(`factory/engines/gmpai_integrity/prompts/*.yaml`), y cambiarlo es
contenido gobernado (prompt_version nuevo, aprobación de Cesar), no
código. Según `W5V2_RECALL_EXPERIMENTS_RESULTADOS.md`, la ganancia de
recall de H4 sobre H2 fue **cero** ("mismos dos casos que H2: P1 y P5 —
exactamente igual") — solo velocidad (2.4x). Por eso `evaluation_profile`
reproduce el recall real medido aunque no reproduzca el schema mínimo:
filtrar a 1 requirement ya reduce `output_token_budget()` automáticamente
(escala con `n_checkpoints` y `n_criteria`, ambos menores), así que se
obtiene la mayor parte de la velocidad de H4 sin tocar contenido
gobernado.

**Nunca invocar la config ganadora por script ad hoc otra vez.** Si un
experimento futuro (H5/H6/H7 u otro) mejora el recall, el mismo principio
aplica: productizar como perfil configurable, revalidar por flujo real,
antes de construir nada encima.

## El fixture set 7P+2N — único instrumento de medición

`docs_plan/W5V2_RECALL_FIXTURE_SET_DRAFT.md`. 7 positivos verificados a
mano (documento, página real, requirement_id, pasaje exacto a anclar) + 2
negativos (`ANNEX11_4` en lista de referencias; tabla de contenidos con
mención superficial). **Criterio de éxito de cualquier configuración**:

```
recall >= 6/7 positivos con cita anclada válida (validación A en verde)
AND 2/2 negativos rechazados
AND schema_valid_rate = 100%
AND latencia por llamada registrada
```

Todo experimento de recall se mide contra ESTE set. Ningún otro conjunto
de casos sustituye esta medición.

## Ojo con confundir "rechazo por idioma" con "fallo de recall del modelo" (R1.6, 2026-08-09)

Antes de concluir que el modelo no encontró evidencia (recall bajo),
verificar si el rechazo real viene de un GATE posterior, no del modelo.
Hallazgo real: `chunked_engine._is_topically_relevant()` (línea ~595) es
un pre-filtro de relevancia PROPIO de `evaluate_chunked()`, distinto y
más crudo que la validación C real del sistema
(`semantic_evidence_verification.verify_semantic_relevance()`, que usa
`requirement_terms.yaml` — language-agnostic — y degrada a
`review_required` en vez de rechazar duro). Compara palabras del `label`
del checkpoint contra la cita citada; varios labels (familia ALCOA) usan
el patrón bilingüe `"Término inglés — glosa en español"` y el código
original descartaba la mitad en inglés (`label.split("—", 1)[-1]`) —
contra un documento fuente en inglés (todo Rockwell lo es), ninguna
palabra española puede aparecer nunca en una cita literal inglesa, así
que el gate rechazaba evidencia genuina y anclada (score 1.0 de
`match_citation`) SIN que el modelo hubiera fallado en nada. Fix aplicado
en R1.6: usar ambas mitades del label bilingüe (nunca se resta
vocabulario). **Persiste un límite más profundo, sin corregir**: la
coincidencia léxica LITERAL sigue siendo demasiado estricta para un
`cumple_parcialmente` parafraseado por el modelo (caso real: P5 sigue sin
llegar a `observed` incluso tras el fix, porque su cita real no repite
NINGUNA palabra gobernada) — decisión pendiente de Cesar sobre si
convertir este pre-filtro en señal suave (como ya hace `verify_llm_output`
V5) en vez de rechazo duro. Detalle completo:
`docs_plan/R1_6_VALIDADOR_RELEVANCIA_IDIOMA.md`,
`docs_plan/ROADMAP_ANALIZADOR_GMP.md` sección R1.6.

**R1.7 (autorizado y aplicado, 2026-08-09)**: el pre-filtro de
rechazo-duro se convirtió en señal-suave, PERO SOLO para el pipeline
verificado (el legacy sigue igual, no tiene consumidor downstream capaz
de manejarla). Ahora el pipeline verificado solo rechaza duro por
`semantic_evidence_verification.detect_reference_list_context()`
(estructural, ya probado por el golden dataset); la relevancia léxica ya
no bloquea antes de tiempo — fluye a `verify_llm_output` V5 (sin tocar
ningún umbral) y de ahí a `absence_consolidator`, que ya sabe convertirla
en `SUPPORTING_EVIDENCE_UNDER_REVIEW` sin promoverla nunca a una
conclusión positiva confirmada. **Resultado real, confirmado con la
respuesta ya persistida del modelo (replay offline, cero llamadas
nuevas)**: P5 pasa de `chunks_observed=0` a `chunks_observed=1`,
`conclusion="SUPPORTING_EVIDENCE_UNDER_REVIEW"` — visible y trazable,
flageada para revisión humana, nunca aprobada en silencio. **No confundir
esto con "R1.7 no resolvió nada"**: el objetivo nunca fue que P5 llegara
a una aprobación automática (eso violaría "sin declaración de
cumplimiento final", `CLAUDE.md`) — el objetivo era que dejara de
perderse silenciosamente, y eso sí se logró y se verificó. Detalle:
`docs_plan/ROADMAP_ANALIZADOR_GMP.md` sección R1.7,
`.claude/plans/sharded-riding-turing.md`.

**Regla derivada**: antes de atribuir un `not_observed_in_chunk` a
"el modelo no encontró la evidencia", revisar si algún gate posterior a
la respuesta del modelo (hoy: `detect_reference_list_context` en el
pipeline verificado, `_is_topically_relevant` en el legacy) descartó una
cita que SÍ ancló — y si una `SUPPORTING_EVIDENCE_UNDER_REVIEW` con
`chunks_observed>0` no es lo mismo que "no encontró nada": es evidencia
real esperando confirmación humana, no una ausencia. La medición 2/7 de
H1-H4 quedó potencialmente sesgada a la baja por el pre-filtro previo a
R1.7 — no re-medida todavía (alcance de R2, que sigue en espera).

## Prohibición central (sin excepción, de cualquier iniciativa futura)

El problema de recall es del MODELO, nunca de la estrictez del
verificador. Prohibido:
- relajar la exigencia de cita anclada (validación A);
- aceptar checkpoints con `evidencia_exacta` vacía;
- bajar umbrales de C/D ni eliminar criterios de los Evidence Packs;
- convertir `NOT_ASSESSABLE` en `observed` por interpretación;
- subir `temperature` "para que encuentre más".

`ANNEX11_4` (GAMP5 en lista de referencias numeradas) es el **test
negativo obligatorio**: cualquier cambio que suba recall debe demostrar
simultáneamente que ese caso sigue rechazado. El verificador que descartó
los falsos "cumple_parcialmente sin cita" es la parte del sistema que
FUNCIONÓ — se queda intacto siempre.

## Gobernanza: PILOT_EXECUTION

Cualquier llamada real a Ollama en contexto de diagnóstico/piloto exige
`PILOT_EXECUTION` firmada (`human_confirmed`) — familia de decisión
SEPARADA de `CORPUS_AUTHORIZATION`/`D4`, nunca la satisface. Ver
`factory/regulatory/pilot_execution.py`.

**Selección determinista (2026-08-09, `corpus_runner.
_select_pilot_execution_instance`)**: si más de una `PILOT_EXECUTION`
vigente cubre el mismo lote de documentos, el resolver elige — nunca
falla cerrado por ambigüedad benigna, ni tampoco requiere que Capa 8
proponga una autorización nueva (eso solo aumentaría el conflicto). Regla
de selección: vigente ∧ cubre todos los documentos del lote ∧
`max_calls>0` ∧ `decision_date` más reciente (desempate estable).

**Nunca proponer una `PILOT_EXECUTION` nueva si ya existe una vigente con
presupuesto** — usar la que el resolver seleccione. Proponer una nueva sin
necesidad es lo que generó el conflicto real de gobernanza documentado en
`ROADMAP_ANALIZADOR_GMP.md` (`-002`/`-004`/`-006`/`-007`/`-008`, varias
siguen como registros permanentes sin poder retirarse — el almacén es
append-only, Part 11).

## Estado del roadmap R0-R5 y dependencias

- **R0**: CLOSED (verdad documental).
- **R1**: CLOSED (2026-08-09) — spec aprobada + smoke E2E ensambló de
  punta a punta (el criterio de cierre nunca fue "el smoke ancla
  evidencia").
- **R1.5** (agregado 2026-08-09, no estaba en el roadmap original):
  productización de `evaluation_profile=H2H4` — **CLOSED** (commit
  `484d103`). Funciona y está probada; P5 ancló de verdad por el flujo
  real (score 1.0). El hallazgo de que el checkpoint final igual lo
  reportaba como no observado se separó como R1.6 (no era un defecto de
  la productización).
- **R1.6** (agregado 2026-08-09): defecto de idioma en
  `_is_topically_relevant()` — investigado, corrección real aplicada
  (labels bilingües). Se resuelve junto con R1.7, no cierra por separado.
- **R1.7** (agregado 2026-08-09, autorizado por Cesar): pre-filtro de
  rechazo-duro del pipeline verificado convertido en señal-suave,
  reutilizando `verify_llm_output` V5 + `absence_consolidator` (ambos ya
  probados, sin tocar ningún umbral). P5 llega a `chunks_observed=1`,
  `conclusion=SUPPORTING_EVIDENCE_UNDER_REVIEW` (confirmado con replay
  offline de la respuesta real). ANNEX11_4 sigue en `chunks_observed=0`
  por el mecanismo estructural correcto. **Pendiente de aprobación de
  Cesar para commitear** — implementado y con no-regresión confirmada,
  pero sin commit todavía. **R2 sigue en espera** hasta cierre formal.
- **R2**: recuperación determinista de evidencia — bloqueada por
  R1.6/R1.7.
- **R3-R5**: sin empezar, dependen de que R2 alcance ≥6/7 (gate
  bloqueante).

## Qué está diferido (y su condición de reactivación)

- **H5** (modelo alternativo) / **H6** (caracterización de
  no-determinismo a temperature=0.0, hallazgo ya documentado) — se
  reactivan si R2 no alcanza ≥6/7.
- **H7** (MarkItDown, entrada documental más limpia) — se reactiva si R2
  muestra que el ruido de entrada sigue pesando.
- **Corpus formal W5** (232 llamadas, `D4-2026-004` propuesta sin
  confirmar) — se retoma cuando el analizador esté consolidado (R5
  cerrado) y Cesar decida.
- **Limpieza superseding formal de `PILOT_EXECUTION-2026-002/-007/-008`**
  — ya no urgente (el resolver no se bloquea por ellas), pendiente de
  decisión de Cesar sin fecha.
