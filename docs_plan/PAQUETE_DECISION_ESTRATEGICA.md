# Paquete de decisión estratégica — Palancas A/B/C

**Estado**: documento de decisión, NO ejecución. Ninguna de las tres
palancas se activa por este documento. Preparado según `docs_plan/
CONTINUACION_CIERRE_ESTRATEGICO.md` Bloque 3, tras confirmar con
evidencia real (4 casos por experimento directo) que el cuello de
botella es el modelo de 7B, no el pipeline (ver `docs_plan/
AUDITORIA_ARQUITECTONICA_2026-08/BOTTLENECK_DIAGNOSIS.md`).

Presentadas sin recomendación sesgada, mismo criterio que rigió cada
decisión de rumbo anterior del proyecto (D1/D2/D3, Tier-1, etc.). **C no
bloquea A ni B** — se puede operar hoy con alcance reducido mientras A o
B se evalúan en paralelo, en cualquier orden o combinación.

──────────────────────────────────────────────────────────────────────
PALANCA A — Modelo local más grande (GPU)
──────────────────────────────────────────────────────────────────────

**Qué es**: reemplazar `qwen2.5:7b-instruct-q4_K_M` por un modelo local
mayor (ej. Llama 3.1 70B) sobre GPU dedicada, vía la misma
`OllamaProvider` ya construida (`factory/engines/gmpai_integrity/
model_provider.py`) — cero cambio de arquitectura de software, el
`ModelProvider` Protocol ya es agnóstico al tamaño del modelo.

**Costo de hardware**: NO estimado en esta corrida — fuera de alcance
técnico de Capa 8 en este momento (requiere cotización real de GPU
compatible con el servidor `ivr-ia` o infraestructura nueva).

**Lo que SÍ está listo hoy**: el fixture set 7P+2N
(`docs_plan/W5V2_RECALL_FIXTURE_SET_DRAFT.md`) es un instrumento de
calificación inmediato — el día que el hardware exista, correr el
mismo fixture contra el modelo nuevo (mismo criterio de éxito: recall
≥6/7 positivos + 2/2 negativos rechazados) da una respuesta objetiva sin
diseño adicional.

**Honestidad de alcance**: el recall resultante de un modelo más grande
no es demostrable sin probar — no hay forma de estimarlo desde la
evidencia ya medida (el techo confirmado es de este modelo específico,
no necesariamente de todos los modelos locales).

──────────────────────────────────────────────────────────────────────
PALANCA B — AnthropicProvider (modelo API externo)
──────────────────────────────────────────────────────────────────────

**Qué es**: implementar `AnthropicProvider` contra el `ModelProvider`
Protocol ya diseñado (`factory/engines/gmpai_integrity/
model_provider.py:26-100`) — actualmente solo existe `OllamaProvider`;
`AnthropicProvider` está documentado como extensión futura, nunca
implementado, y requiere autorización explícita de Cesar (ya declarado
así desde la Fase D de W5 V2).

**Qué viajaría por llamada** (confirmado leyendo el código real, no
supuesto): el `prompt` que construye `chunked_engine.build_prompt()` —
UN chunk de hasta `CHUNK_MAX_CHARS=6000` caracteres + el Evidence Pack
gobernado del requisito (criterios, `citation_text` regulatorio) +
instrucciones del prompt YAML. **Nunca el corpus completo, nunca el
documento entero** — el mismo tipo de fragmento que ya usa el pipeline
local hoy, solo que la llamada de inferencia saldría del servidor hacia
una API externa en vez de quedarse en `aria-ollama`.

**Circuito de gobernanza que exigiría** (ninguno construido todavía):
- Decisión formal separada (misma familia de gravedad que
  `PILOT_EXECUTION`/`EMBED_EXECUTION`, nunca las sustituye).
- Recalificación del modelo contra el mismo fixture 7P+2N antes de
  cualquier uso real (mismo `model_qualification_gate.py` ya existente,
  extendido a un provider no-Ollama).
- `model_digest`/fingerprint propio (el campo ya existe en el runtime
  fingerprint, pero un modelo API no tiene un digest local descargable —
  requiere decidir qué identificador lo sustituye, ej. version string de
  la API).
- Presupuesto propio, gobernado igual que `PILOT_EXECUTION`/
  `EMBED_EXECUTION` — nunca comparte contador con las llamadas locales.
- Evaluación de confidencialidad formal (fuera de alcance técnico de
  esta corrida — es una decisión de política, no de código): documentos
  Rockwell son propiedad de un cliente real; enviar fragmentos a una API
  externa requiere su propia autorización, separada de la técnica.

**Sin ejecutar nada** — este documento solo informa la decisión, no la
toma ni la prepara técnicamente más allá de lo ya diseñado en
`model_provider.py`.

──────────────────────────────────────────────────────────────────────
PALANCA C — Tier-1 de alcance reducido (ya construido)
──────────────────────────────────────────────────────────────────────

**Qué es**: operar el sistema tal como existe HOY, con el alcance
explícitamente acotado a lo que está medido y confiable:

- **Confirmación automática de eco léxico** (P1, ya demostrado en
  producción real — cita literal o casi literal, ancla y se confirma).
- **Rechazo de falsos positivos** (N1/N2, 3 mecanismos deterministas
  independientes: `detect_reference_list_context`, umbral fuzzy 0.93,
  filtro de relevancia — todos verificados contra el golden dataset de 8
  casos, 8/8 PASS).
- **Recuperación semántica que entrega candidatos enriquecidos al
  revisor** (fusión BM25+embeddings, `retrieval_recall_at_5=7/7` medido,
  R2) — el revisor humano ve los candidatos correctos al frente, aunque
  el modelo no los confirme solo.
- **Todo lo demás (paráfrasis) a revisión humana con cobertura
  declarada** — nunca detección automática de paráfrasis, documentado
  como límite conocido, no oculto.

**Costo de esta palanca**: cero — es el sistema tal como existe, con la
honestidad ya incorporada (Tier-1 asistido, D2 firmado 2026-08-11) de
que la paráfrasis está fuera de su alcance actual, ahora respaldado por
evidencia definitiva (4 casos por experimento directo) en vez de
sospecha.

**Lo que Palanca C NO resuelve**: el mismo techo que A/B atacan
directamente — evidencia parafraseada o evidencia insuficiente frente a
criterios amplios (P7, ver `docs_plan/AUDITORIA_ARQUITECTONICA_2026-08/
BOTTLENECK_DIAGNOSIS.md`) sigue yendo a revisión humana, no se
automatiza.

──────────────────────────────────────────────────────────────────────
Relación entre las tres
──────────────────────────────────────────────────────────────────────

```
Palanca C ──────── operable HOY, sin bloquear nada ───────┐
                                                             │
Palanca A ── evaluar cuando exista cotización de GPU ──────┤── decisiones
                                                             │   independientes,
Palanca B ── evaluar cuando exista autorización de       ──┘   combinables
              confidencialidad + decisión de gobernanza
```

Ninguna de las tres es mutuamente excluyente. C puede operar en
producción mientras A y/o B se evalúan en paralelo, sin que ninguna
bloquee a las otras.
