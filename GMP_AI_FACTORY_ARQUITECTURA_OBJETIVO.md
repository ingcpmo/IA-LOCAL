
# GMP AI FACTORY — ENMIENDA ARQUITECTÓNICA (Palanca A) + PLAN DE IMPLEMENTACIÓN
## Documento 2 de 2: incorpora evidencia nueva y convierte la arquitectura en fases ejecutables

**Rol:** Arquitecto Principal (Claude, Anthropic)
**Autoridad de aprobación:** Capa 9 = Cesar
**Documento base:** `GMP_AI_FACTORY_ARQUITECTURA_OBJETIVO.md`
**Evidencia nueva incorporada:** `PALANCA_A_14B_7P2N_RUN.log` — corrida real,
Qwen2.5 14B-instruct-q4_K_M, GPU Tesla T4, fixture 7P+2N, runner exact-page,
perfil H2H4, `PILOT_EXECUTION-2026-020`, 9/9 llamadas completadas.
**Estado:** DISEÑO + PLAN. Cero código implementado. Requiere aprobación de
Capa 9 fase por fase.

---

# PARTE I — ENMIENDA: IMPACTO DE PALANCA A

## 1. Qué demuestra esta corrida que ninguna auditoría anterior demostraba

`[EJEC-VIVO — corrida real de Cesar]` El runner exact-page entregó al
modelo **una sola página como documento completo** (la página conocida
correcta de cada caso: 45, 39, 44…) — el nivel de contexto quirúrgico más
alto posible, superior al que mi AD-2 (top-k de recuperación) puede
garantizar en todos los casos. Con Qwen 14B (el doble de parámetros que el
7B calificado) sobre ese contexto ideal: **recall 2/7, idéntico al 7B**.

Y un matiz que agrava el resultado: de los 2 "observed" (P1, P5), ambos
quedan con `substantive_evidence_accepted=False` / `review_required` — es
decir, la lectura rigurosa no es 2/7, es **0/7 evidencia sustantiva
plenamente aceptada**. 2/7 es ya la interpretación favorable.

## 2. Revisión de mi propio diagnóstico (Parte I, §3.3 del documento base)

Mi problema **P-3** afirmaba: *"el LLM hace dos trabajos en una llamada
—buscar y juzgar— y eso es lo que falla"*. Esa hipótesis predecía que
darle al modelo solo el pasaje correcto (sin buscar) mejoraría el recall.
**Palanca A la contradice directamente**: contexto ya aislado a una
página, y el recall no se mueve. Retracto P-3 en su forma original y la
reformulo:

**P-3 (revisado) — el techo es de correspondencia semántica
evidencia↔criterio, no de ruido de contexto.** Confirmado con dos tamaños
de modelo (7B, 14B) bajo el mismo contrato liviano (H2H4) y con el
contexto más limpio posible. `[INFERENCIA]` fundamentada: el problema vive
en cómo el contrato de juicio le pide al modelo mapear lenguaje operativo/
procedimental o parafraseado contra el lenguaje de un criterio regulatorio
formal — no en cuánto ruido hay alrededor.

## 3. Lo que NO cambia

**P-1 (presupuesto de salida) sigue siendo real y sigue siendo corregible.**
Es un defecto distinto, medido en L4 bajo perfil BASELINE (contrato
verboso de 20 criterios). Palanca A corrió con H2H4 (contrato liviano) y
no muestra truncamiento — lo que en realidad **confirma que son dos
limitaciones independientes**: un artefacto de configuración (P-1, barato
de arreglar, AD-4 se mantiene) y un techo de reconocimiento semántico
(P-3 revisado, mucho más difícil).

Los componentes C1-C9 (verificación determinista, fail-closed, gobernanza)
no se tocan por esta evidencia — siguen siendo el activo correcto del
sistema.

## 4. Defecto instrumental encontrado (registrar, no bloqueante)

El runner exact-page persiste `evidence_page=1` para toda unidad,
independientemente de la página real de origen (45→1, 39→1, 44→1). Es
pérdida de trazabilidad del instrumento de medición, no del pipeline de
producción. Se corrige en la Fase M1 (barata) sin repetir las 9 llamadas
— el resultado ya es válido tal como está.

## 5. Qué cambia en la arquitectura objetivo

**Se mantiene sin cambios:** AD-2 (recuperación en producción), AD-4
(presupuesto de salida dimensionado), AD-5/AD-6 (contrato único, agentes
como perfiles), AD-7/AD-9/AD-10/AD-11. Todos se justifican por costo,
trazabilidad o seguridad — independientemente del resultado de recall.

**Se revisa: AD-1.** Sigue siendo la decisión correcta (81→~20 llamadas,
elimina P-1), pero **se retira la expectativa de que por sí sola resuelva
el recall**. Se documenta explícitamente como optimización de costo y
arquitectura, no como solución al problema central.

**Se añade: AD-12 — Rediseño del contrato de juicio (semántico, no de
formato).** Palanca A + el propio análisis de Cesar apuntan en la misma
dirección: antes de comprar más hardware, investigar si el contrato de
evaluación (`criterion_assessments`, comparación directa texto↔criterio)
es la causa. Diseño experimental: **descomposición en dos preguntas**
separadas por llamada — (1) "¿qué dice este pasaje, en términos
operativos?" (extracción neutra, sin mencionar el criterio regulatorio) y
(2) "¿lo que se describe en el paso (1) satisface el criterio X?"
(mapeo semántico explícito, con el criterio y la extracción neutra como
únicos insumos). Hipótesis: la traducción intermedia a lenguaje neutro
puede tender el puente semántico que el modelo no cruza en un solo paso.
**No implementado — es la Fase V2b, ver §7.**

**Se pospone explícitamente:** cualquier decisión de modelo 32B/70B/72B o
proveedor externo. `[INFERENCIA]` La hipótesis "un modelo mucho mayor
resuelve esto" queda **no demostrada, no falsificada** — Palanca A solo
descarta 14B. Gastar en más hardware antes de V2b sería exactamente lo que
el propio análisis de Cesar advierte evitar.

## 6. Secuencia de validación revisada

```
ANTES (documento base):                DESPUÉS (esta enmienda):
V0 → M0/M1 → M2/V1 → M3 → V2           V0 → M0/M1(+fix instrumento) → M2/V1
  (V2: recall≥5/7 esperado)              → M3 → V2 (recall: SIN expectativa
                                          de éxito; objetivo real = costo +
                                          confirmar/refutar el techo con
                                          retrieval real vs exact-page)
                                            ↓
                                          V2b — rediseño de contrato
                                          (la apuesta real para recall)
                                            ↓
                                          Paquete de decisión Capa 9
                                          (modelo mayor / externo / alcance
                                          reducido) — informado por V2b,
                                          no por intuición
```

---

# PARTE II — PLAN DE IMPLEMENTACIÓN EJECUTABLE

## Reglas de gobernanza para TODA fase (aplican sin excepción)

1. Cada fase se entrega a Claude Code (o Devin) como una instrucción
   independiente — no ejecutar la fase N+1 sin cierre y aprobación
   explícita de la fase N por Capa 9.
2. Mostrar diff completo antes de tocar cualquier archivo. Sin commit sin
   aprobación.
3. Ninguna fase con costo LLM arranca sin verificar el remanente de una
   `PILOT_EXECUTION` vigente seleccionable por el resolver, o sin proponer
   una nueva y esperar firma — nunca gastar sin autorización explícita.
4. NO tocar bajo ninguna circunstancia: `evidence_verifier.py`,
   `semantic_evidence_verification.py`, `absence_consolidator.py`,
   `candidate_validity.py`, `audit_writer.py`, `decision_store_v2.py`,
   `path_policy.py`, prompts YAML gobernados, `requirements.yaml`, corpus
   regulatorio, `GMPAI/source/Rockwell/`.
5. Toda corrida con llamadas LLM en background: `systemd-run`/`tmux`,
   verificación de supervivencia a cierre de SSH ANTES de dejarla sola,
   script de estado de solo lectura.
6. N1/N2 (negativos del fixture) deben seguir rechazándose después de
   CUALQUIER cambio que toque recuperación, chunking o juicio — bloqueante,
   sin excepción.
7. Fingerprint: todo cambio de perfil/contrato/chunking/representación
   invalida cache. Resultados de fingerprints distintos nunca se mezclan.
8. Cada fase termina con Gate 0 corrido desde el HOST (no desde el
   contenedor) y su conteo real reportado.

---

## FASE V0 — Cuantificar el artefacto de truncamiento (gratis, primero)

**Objetivo:** saber cuánto del "recall 2/7" histórico bajo perfil
BASELINE es artefacto de P-1 (truncamiento) y no límite genuino del
modelo, antes de tocar nada más.

**Instrucción técnica exacta:**
1. Recorrer `factory/regulatory/pilot_run/checkpoints/` y cualquier
   `raw_responses/*.txt.gz` de corridas históricas bajo
   `evaluation_profile=BASELINE` (incluida la corrida original del fixture
   7P+2N y la corrida de la campaña de validación si sus raw quedaron
   persistidos).
2. Para cada raw response: parsear el campo `done_reason`. Contar cuántos
   son `'length'` (truncados) vs `'stop'` (completos).
3. Cruzar contra el resultado final de esa unidad: ¿el truncamiento
   coincidió con una degradación a `evidencia_insuficiente`/
   `EVALUATION_INCOMPLETE`?
4. Producir tabla: unidad × perfil × `done_reason` × resultado final ×
   ¿el hallazgo se hubiera aceptado sin el corte?

**Archivos leídos (sin modificar):**
`factory/regulatory/pilot_run/checkpoints/`,
`factory/regulatory/pilot_run/*/raw_responses/`.

**Costo LLM:** 0.

**Test real post-fase:** ninguno de ejecución — el resultado ES el
producto de la fase. Criterio de calidad: cada fila de la tabla debe
citar `run_id`/`task_id` real, no estimación.

**Qué demuestra y cómo sirve a la misión:** separa con evidencia el
artefacto de configuración del límite genuino del modelo. Si una fracción
significativa de "no observado" bajo BASELINE resulta ser truncamiento,
la magnitud real del problema de recall es menor de lo declarado — dato
que cambia la urgencia relativa de V2b frente a M4.

---

## FASE M0 — Cimientos de seguridad y limpieza (sin LLM)

**Objetivo:** cerrar P-5 (auth fail-open) y la deuda estructural (P-10)
antes de tocar el motor de análisis.

**Instrucciones técnicas exactas:**
1. `factory/api/main.py::verify_api_key` y su equivalente en `app/main.py`:
   cambiar de `if FACTORY_API_KEY and x_api_key != FACTORY_API_KEY` a
   fail-closed: si `FACTORY_API_KEY`/`GMP_API_KEY` no están definidas o
   están vacías, el servicio **rechaza arrancar** (excepción en startup,
   no runtime silencioso). Mismo patrón para `GMP_API_KEY` del Copilot.
2. Eliminar clúster muerto confirmado (7 módulos, 319 LOC):
   `factory/agents/agent_designer.py`, `layer8_code_agent.py`,
   `prompt_designer.py`, `rag_designer.py`,
   `factory/core/docker_generator.py`,
   `factory/layer8/code_generation_manager.py`,
   `factory/layer9/approval_matrix.py`. Verificar de nuevo con AST +
   grep de referencias dinámicas antes de borrar (no confiar solo en la
   auditoría previa — repetir la verificación en el commit actual).
3. Eliminar `factory/ui/index.html.bak`.
4. Consolidar los 3 generadores PDF (`pdf_report.py`, `pdf_report_robust.py`,
   `gmpai_pdf_report.py`) en uno — mantener la variante más robusta,
   verificar con los tests existentes de cada uno antes de decidir cuál.
5. Añadir `model_digest` obligatorio (no opcional) a todo
   `chunk_execution` nuevo — fail-closed si el provider no lo reporta.

**Tests reales post-fase (todos deterministas, 0 LLM):**
- Servicio rechaza arrancar sin API key configurada (test de arranque,
  no de request).
- Suite completa + Gate 0 desde el host: mismo conteo o mejor que el
  baseline conocido (2.332 passed / 38 failed / 12 errors — confirmar que
  los fallos restantes son los ya caracterizados, no regresión nueva).
- Grep de referencias a los 7 módulos eliminados: cero coincidencias
  fuera de `.git` history.

**Qué demuestra y cómo sirve a la misión:** cierra la brecha de seguridad
más severa (R1/P-5) y reduce la superficie de mantenimiento antes de
tocar el motor — riesgo bajo, beneficio inmediato, no depende de ninguna
decisión de recall.

---

## FASE M1 — Presupuesto de salida dimensionado + fix del instrumento (sin LLM para implementar)

**Objetivo:** eliminar P-1 como clase de fallo (AD-4) y corregir el
defecto de trazabilidad de página del runner exact-page.

**Instrucciones técnicas exactas:**
1. En `factory/engines/gmpai_integrity/ollama_client.py` (o donde viva
   el cálculo de `num_predict` por agente): sustituir el tope fijo por
   agente por una función `estimate_output_budget(n_checkpoints,
   n_criteria, schema_verbosity)` que calcule el presupuesto necesario
   con margen, y extender `_assert_token_budget_fits` (preflight) para
   verificar TAMBIÉN la salida esperada, no solo la entrada — fail-closed
   antes de gastar la llamada si el presupuesto estimado no alcanza para
   el contrato completo del agente.
2. Localizar el runner exact-page (usado en Palanca A;
   `factory/regulatory/corpus_runner.py` o el módulo que construye el
   excerpt de una página) y corregir la persistencia de `evidence_page`:
   debe registrar la página ORIGINAL real (45, 39, 44…), no `1`. El
   excerpt de una página sigue siendo válido como input al modelo; solo
   la metadata de provenance debe reflejar el origen real.
3. Test-first: reproducir el caso real de L4 (chunk que truncó por
   `num_predict=3072` con contrato de 20 criterios) usando el
   `raw_response` YA PERSISTIDO — confirmar que con el cálculo nuevo el
   presupuesto estimado hubiera sido suficiente, sin gastar una llamada
   nueva.

**Tests reales post-fase (0 LLM, replay sobre datos ya pagados):**
- Caso L4 replay: el presupuesto estimado ≥ presupuesto que hubiera
  evitado el truncamiento real observado.
- Caso sintético: contrato de 1 criterio (agente cgmp211) recibe
  presupuesto menor que contrato de 20 criterios (annex11) — el cálculo
  escala, no es un valor fijo disfrazado.
- Runner exact-page: unidad sintética con `page_indices=(45,)` persiste
  `evidence_page=45`, no `1`.
- Regresión: fixture 7P+2N por replay — ningún resultado cambia (esta
  fase no toca juicio, solo presupuesto y metadata).

**Qué demuestra y cómo sirve a la misión:** cierra P-1 de forma
verificable con datos ya pagados, sin gastar presupuesto nuevo. Corrige
la trazabilidad que Palanca A señaló como defecto — cualquier corrida
futura con el runner exact-page queda auditable por página real.

---

## FASE M2 + V1 — Contrato único + chunking por sección (sin LLM para implementar)

**Objetivo:** AD-5 (superficie única de contrato) y AD-11 (chunking
consciente de estructura), medidos contra el fixture antes de tocar
juicio.

**Instrucciones técnicas exactas:**
1. Auditar los 4 `common_contract` reales (`factory/engines/gmpai_
   integrity/prompts/*.yaml`) y extraer el texto compartido real (no
   asumido) vs. las diferencias genuinas por agente.
2. Refactorizar a `common_contract_base.yaml` + `deltas/<agente>.yaml`
   (o el mecanismo de composición que el formato YAML del proyecto
   permita sin romper el versionado por `prompt_version` ya existente).
   Cambiar el contrato es contenido gobernado: requiere `prompt_version`
   nuevo y aprobación de Cesar — no se toca el texto sin ese ciclo.
3. Conectar `factory/regulatory/document_structure_extractor.py` (ya
   construido, hoy desconectado) como fuente de límites de sección para
   `build_page_chunks()` — chunking por sección real cuando `toc_anchored=
   true`; fallback al chunking actual por tamaño cuando no hay ToC
   (fail-visible, ya es el comportamiento del extractor).

**Tests reales post-fase:**
- Los 4 contratos reconstruidos desde base+deltas producen el mismo
  `common_contract_sha256` que los YAML actuales para cada agente (test
  de no-regresión textual).
- Caso P3 (RW-0005, chunk que mezclaba retención con Historian/Audit
  Trail): con chunking por sección, verificar mecánicamente (0 LLM) que
  el nuevo chunk que contiene el pasaje de P3 ya NO mezcla las secciones
  no relacionadas — comparar longitud y contenido del chunk antes/después.
- **V1 — recuperación (0 LLM):** re-indexar BM25+embeddings sobre el
  corpus con chunking nuevo; medir `retrieval_recall_at_5` sobre el
  fixture completo. Criterio: ≥7/7 (no degradar el 7/7 ya medido) y
  negativos 2/2 fuera — bloqueante.

**Qué demuestra y cómo sirve a la misión:** reduce el overhead
estructural (P-4) y mejora la cohesión temática de los chunks sin tocar
juicio ni gastar LLM. V1 es el primer punto de parada real: si la
recuperación degrada, no se avanza a M3.

---

## FASE M3 — Recuperación en el camino de producción (sin LLM)

**Objetivo:** AD-2 — conectar `judgment.py`/la fusión RRF (hoy
diagnóstico, declarado explícitamente como no productizado) al runner de
producción, como **modo paralelo** seleccionable por perfil.

**Instrucciones técnicas exactas:**
1. En `factory/regulatory/corpus_runner.py` (o el punto de entrada real
   del camino de producción `run_context='production'`): añadir un modo
   `retrieval_mode` versionado (`full_chunk` = comportamiento actual,
   `top_k_fusion` = nuevo) que, cuando está activo, construye el prompt
   con los top-k candidatos de `factory/regulatory/retrieval/fusion.py`
   en vez de barrer todos los chunks del documento.
2. El modo nuevo NO se activa por defecto — requiere selección explícita
   de perfil, mismo patrón que `evaluation_profile`.
3. `retrieval_mode` entra al fingerprint de corrida.

**Tests reales post-fase (0 LLM):**
- Modo `full_chunk` (default) produce exactamente el mismo comportamiento
  que hoy para cualquier llamador existente — test de no-regresión.
- Modo `top_k_fusion`: para cada requisito del fixture, verificar que el
  top-k construido coincide con la medición ya conocida de
  `retrieval_recall_at_5` (7/7) — mismo resultado, ahora servido por el
  camino de producción real, no por el script de diagnóstico.
- Fingerprint cambia entre modos — verificar que el cache no se reutiliza
  entre ellos.

**Qué demuestra y cómo sirve a la misión:** el sistema deja de tener una
capacidad de recuperación de clase mundial (7/7) atrapada en un script de
diagnóstico. Es la pieza que hace posible V2 sin gastar en re-implementar
nada.

---

## FASE V2 — Medición decisiva de juicio requisito-céntrico (costo acotado)

**Objetivo:** medir AD-1 (1 llamada/requisito con top-k de M3) contra el
fixture completo — con la expectativa RECALIBRADA por Palanca A.

**Criterio de éxito, revisado (fijado ANTES de medir):**
- **Costo/arquitectura (se espera PASE):** llamadas totales ≈ 20 (vs. 81
  del baseline por documento equivalente); cero truncamientos
  (`done_reason='length'`) gracias a M1.
- **Recall (SIN expectativa de éxito — Palanca A ya lo puso en duda):**
  registrar el número real. Si ≥5/7: la arquitectura SÍ aporta recall
  además de costo (bienvenida sorpresa, investigar por qué difiere del
  exact-page de Palanca A — probablemente porque top-k puede incluir
  MÁS de un candidato por requisito, dándole al modelo alternativas que
  un solo excerpt no da). Si ~2/7 (como Palanca A predice): CONFIRMA que
  el techo es de contrato/semántica, no de contexto — refuerza la
  prioridad de V2b sobre cualquier gasto en modelo mayor.
- Negativos 2/2 rechazados: bloqueante sin excepción, cualquier resultado
  de recall que lo rompa se descarta.

**Instrucción técnica exacta:**
1. Proponer autorización de presupuesto (verificar `PILOT_EXECUTION`
   vigente con remanente antes de proponer una nueva) — tope ~25
   llamadas (20 esperadas + margen de reintento).
2. DETENERSE para firma de Capa 9 antes de la primera llamada.
3. Ejecutar en background con checkpoint por requisito.
4. Reportar el resultado CRUDO — sin ajustar la narrativa al resultado
   esperado.

**Qué demuestra y cómo sirve a la misión:** cierra con evidencia (no con
intuición) si el problema de recall es de arquitectura de entrega de
contexto o de capacidad semántica del modelo — la pregunta que ha
perseguido al proyecto desde el Piloto 1.

---

## FASE V2b — Rediseño del contrato de juicio (semántico, la apuesta real de recall)

**Objetivo:** AD-12 — probar si la descomposición en dos preguntas
(extracción neutra → mapeo semántico) cruza el puente que el contrato
actual no cruza. Es el experimento que el propio análisis de Cesar señala
como el correcto antes de invertir en más hardware.

**Instrucción técnica exacta:**
1. Diseñar dos prompts nuevos y versionados (contenido gobernado, requiere
   aprobación de Capa 9 antes de usarse):
   - Prompt 1 (extracción neutra): dado el pasaje, "describe en términos
     operativos qué hace/registra/controla el sistema descrito, sin
     referencia a ningún requisito regulatorio" — salida: texto libre
     corto, sin JSON de cumplimiento.
   - Prompt 2 (mapeo semántico): dado el criterio regulatorio Y la
     descripción neutra del paso 1 (NUNCA el pasaje original directamente
     en este paso — fuerza el mapeo a través de la traducción intermedia),
     "¿esta descripción satisface el criterio?" — salida: JSON de
     cumplimiento igual que hoy.
2. Ejecutar sobre el MISMO fixture 7P+2N, mismos casos que V2/Palanca A,
   para comparabilidad directa.
3. Guardián obligatorio: la cita/evidencia final que respalda cualquier
   `observed` sigue siendo el pasaje ORIGINAL, verificado por
   `evidence_verifier` sin cambios — el paso 1 es un insumo de
   razonamiento, nunca la evidencia citable.

**Tests reales post-fase:**
- Recall del esquema de dos pasos vs. el esquema de un paso (V2/Palanca
  A) sobre los mismos 7 casos — comparación directa, misma tabla.
- Negativos 2/2 — bloqueante.
- Costo: 2 llamadas por requisito en vez de 1 — documentar el trade-off
  costo/recall explícitamente, nunca ocultarlo.
- Verificar que ninguna cita del paso 2 aparece sin anclaje real contra
  el documento original (el paso 1 no puede convertirse en un canal para
  fabricar evidencia).

**Qué demuestra y cómo sirve a la misión:** es la prueba de la hipótesis
de mayor valor esperado según la evidencia acumulada. Si funciona, resuelve
el problema central del producto sin GPU adicional ni proveedor externo.
Si falla, dirige con evidencia (no con intuición) hacia modelo
mayor/externo — que entonces se prueba informado, no especulativo.

---

## FASE M4 — Ausencia en dos niveles (sin LLM para el mecanismo; marginal con LLM)

**Objetivo:** AD-3, condicionada a que M3 esté operativo. Solo se ejecuta
tras la decisión de Capa 9 sobre V2/V2b (§ Paquete de decisión).

**Instrucción técnica exacta:**
1. En el consumidor de `absence_consolidator.py`: cuando el modo
   `top_k_fusion` está activo, el criterio de "cobertura completa" pasa
   de "todos los chunks fueron juzgados por LLM" a "el documento completo
   fue indexado y buscado determinísticamente (BM25+embeddings) para este
   requisito, Y ningún candidato superó el umbral gobernado". Registrar en
   el finding: umbral usado, ranking completo, candidatos descartados.
2. Umbral como contenido gobernado, versionado, calibrado contra el
   fixture: partir del punto donde `retrieval_recall_at_5=7/7` se sigue
   cumpliendo (ningún positivo real cae bajo el umbral).
3. NO modificar `absence_consolidator.py` en su regla dura ("el LLM nunca
   emite el gap") — la fuente de la señal de cobertura cambia, la
   autoridad de emisión no.

**Tests reales post-fase:**
- Replay sobre el fixture: los 2 negativos, con el umbral calibrado,
  siguen sin superar el umbral (siguen sin evidencia falsa).
- Los 7 positivos: verificar que NINGUNO cae bajo el umbral en el ranking
  real (si alguno cayera, el umbral está mal calibrado — ajustar antes de
  aceptar la fase).
- Caso sintético de ausencia genuina (requisito sin evidencia real en el
  documento): el finding resultante declara `DOCUMENTATION_GAP` con el
  ranking y candidatos descartados visibles — auditable.

**Qué demuestra y cómo sirve a la misión:** preserva la capacidad de
declarar ausencia (68% de los findings históricos) bajo la arquitectura
nueva, con una base más defendible ante inspección (búsqueda determinista
y reproducible en el 100% del documento) que la actual.

---

## FASES M5-M9 (diseño ya detallado en el documento base, sin cambios por Palanca A)

Ejecutar en el orden y con las instrucciones ya especificadas en
`GMP_AI_FACTORY_ARQUITECTURA_OBJETIVO.md` §11: M5 (validación semántica
gobernada, AD-8, con guardianes de N1/N2), M6/M7 (índice de trazabilidad,
AD-7), M8 (identidad individual + firma ligada a hash, AD-9 — subir a P0
si Capa 9 confirma objetivo de uso GxP inspeccionable), M9 (Copilot:
contexto real, router semántico, KB oficial, audit con lock). Ninguna
depende del resultado de V2/V2b — pueden ejecutarse en paralelo a la
decisión de recall.

---

# PARTE III — PAQUETE DE DECISIÓN (tras V2 + V2b)

No ejecutar sin el resultado real de ambas fases. Presentar a Capa 9:

| Resultado V2 | Resultado V2b | Recomendación |
|---|---|---|
| ≥5/7 | — | Adoptar AD-1 tal cual; recall resuelto por arquitectura, sin costo de hardware adicional |
| ~2/7 | ≥5/7 | Adoptar AD-1 + AD-12 (contrato de dos pasos); costo 2× llamadas pero recall resuelto sin hardware nuevo |
| ~2/7 | ~2/7 | El techo es de familia de modelo. Paquete de las tres palancas ya documentado en el diseño base §14: modelo mayor NO PROBADO (32B/70B), proveedor externo (evaluación de confidencialidad pendiente), o Tier-1 de alcance reducido operando HOY con lo demostrado (eco léxico + rechazo de falsos positivos + recuperación entregando candidatos a revisión humana) |

**Ninguna corrida de modelo mayor ni proveedor externo se autoriza sin
que V2b haya corrido primero con resultado real.** Es la secuencia que la
propia evidencia de Palanca A recomienda.

---

# CIERRE

```
ENMIENDA_INCORPORADA        = Palanca A (14B, exact-page, H2H4, 2/7)
HIPÓTESIS_RETRACTADA        = P-3 original ("ruido de contexto es la causa")
HIPÓTESIS_REVISADA          = P-3 revisado (techo semántico contrato↔criterio)
DECISIÓN_NUEVA              = AD-12 (contrato de dos pasos, V2b)
EXPECTATIVA_V2_RECALIBRADA  = costo: éxito esperado; recall: sin expectativa
DEFECTO_INSTRUMENTAL        = evidence_page persistido incorrecto (fix M1)
FASES                       = V0, M0, M1, M2+V1, M3, V2, V2b, M4, M5-M9
FASES_SIN_COSTO_LLM         = V0, M0, M1, M2+V1, M3, M4(mecanismo), M5-M9
FASES_CON_COSTO_LLM         = V2 (~25 llamadas), V2b (~14-25×2 llamadas)
DECISIÓN_DE_HARDWARE_MAYOR  = pospuesta hasta V2b con resultado real
CODE_CHANGED                = 0
PRODUCTION_ENABLEMENT       = BLOCKED (sin cambio)
```

Cada fase se entrega como instrucción independiente a Claude Code/Devin,
con diff mostrado y aprobación de Capa 9 antes de ejecutar la siguiente.
Ninguna fase de costo LLM arranca sin autorización de presupuesto firmada.

