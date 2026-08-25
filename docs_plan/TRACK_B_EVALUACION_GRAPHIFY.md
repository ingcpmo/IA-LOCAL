# TRACK B — EVALUACIÓN DE GRAPHIFY PARA GMP AI FACTORY
# Archivo de instrucciones para Claude Code
# Destino: docs_plan/TRACK_B_EVALUACION_GRAPHIFY.md
# Ejecutar: cd /home/ing_cpmo && claude
#
# Autoridad: Capa 9 = Cesar. Independiente de Track A — no depende de él,
# no se usa para justificarlo, no lo bloquea.
#
# NO instalar Graphify. NO ejecutar MCP. NO modificar Docker. NO modificar
# .env. NO tocar hotelbot/, ARIA/, GMPAI/source/Rockwell/, secrets,
# identity_keys, audit trail, backups/logs/cache. Solo investigación +
# diseño de benchmark + recomendación.

────────────────────────────────────────────────────────────────────────────
BLOQUE 0 — ENCUADRE (antes de investigar nada)
────────────────────────────────────────────────────────────────────────────

0.1 Raíz canónica confirmada para esta evaluación: `/home/ing_cpmo`
    (`factory/`, `app/`, `knowledge/`, `docs_plan/`, `tests/`, `scripts/`).
    `hotelbot/` queda excluido de cualquier indexación — es LEGACY/ARIA,
    no código canónico GMP (confirmado en la corrección de topología ya
    cerrada).
0.2 Distinguir desde el inicio: Graphify, sea lo que sea, es
    HERRAMIENTA DE DESARROLLO para Capa 8 (ayuda a Claude Code a navegar
    el repositorio) — NO es parte del producto GMP AI Factory, no toca el
    pipeline de análisis documental, no requiere gobernanza de decisiones
    ni presupuesto LLM. Esta distinción condiciona todo el resto: la
    pregunta no es "¿mejora el analizador?" sino "¿mejora la eficiencia
    de las sesiones de Capa 8 que trabajan sobre este código?".

────────────────────────────────────────────────────────────────────────────
BLOQUE 1 — INVESTIGACIÓN REAL (no asumir nada del nombre/README ajeno)
────────────────────────────────────────────────────────────────────────────

1.1 Clonar o leer directamente `https://github.com/Graphify-Labs/graphify`
    (repo real, no memoria): README, arquitectura, changelog, licencia,
    CLI, servidor MCP, mecanismo de extracción AST, actualización
    incremental, reglas de ignore, soporte multi-grafo/multi-directorio,
    análisis de impacto de PR, límites documentados.
1.2 Verificar EXPLÍCITAMENTE (no dar por sentado):
    - ¿Corre 100% local, o envía código/metadata a algún servicio externo?
      Esto es lo primero a descartar dado que este proyecto maneja
      documentos regulatorios confidenciales — aunque `GMPAI/Rockwell`
      quede excluido de la indexación, cualquier telemetría/llamada
      externa del propio Graphify sobre el código de `factory/` merece
      escrutinio antes de instalar nada.
    - ¿Qué hace con Python dinámico? Este proyecto usa mucho despacho
      dinámico y superficies únicas (`path_policy`, `decision_scope_
      resolver`, `candidate_validity`) — el análisis AST estático puede
      tener puntos ciegos reales ahí. Documentar la limitación esperada,
      no descubrirla después de instalar.
    - ¿Entiende relaciones de infraestructura (Docker Compose, volúmenes,
      redes)? Respuesta esperada: NO — es un grafo de código, no de
      infraestructura. Esto acota el valor: NO habría ayudado a encontrar
      la topología ARIA/hotelbot (eso fue `docker inspect`, no AST).
      Dejarlo explícito para no sobrevender la herramienta.
    - Costo de mantenimiento: ¿watch/hook obligatorio, o el grafo se
      regenera bajo demanda? ¿Qué pasa si el código cambia y el grafo no
      se actualiza — falla silenciosa (peor) o detección de staleness?

────────────────────────────────────────────────────────────────────────────
BLOQUE 2 — BENCHMARK CON TAREAS REALES DE ESTE PROYECTO (el corazón de la evaluación)
────────────────────────────────────────────────────────────────────────────

No usar tareas hipotéticas — usar preguntas que YA tuvimos que responder
en este proyecto, donde conocemos la respuesta correcta y podemos medir
si Graphify la hubiera dado más rápido y más completa que grep/read:

1. "¿Quién llama a `candidate_validity.resolve_candidate_evidence()`?"
   (superficie única — verificar que el grafo captura TODAS las rutas,
   no solo las obvias).
2. "¿`run_corpus_batch()` propaga `evaluation_profile` hasta
   `evaluate_chunked()`?" (la pregunta que expuso el gap de H2H4 nunca
   conectado al runner formal — un caso real donde grep manual sí lo
   encontró, pero costó una sesión completa).
3. "¿Qué consume `decisions_v2.jsonl` con efecto productivo, más allá del
   escritor?" (verificación de gobernanza ya hecha a mano).
4. "Desde `factory/regulatory/chunked_engine.py`, ¿qué tests lo cubren
   directa e indirectamente?" (relación código→tests).
5. "Si cambio la firma de `verify_sufficiency_aggregated()`, ¿qué se
   rompe?" (análisis de impacto).

Para cada tarea, correr BASELINE_SIN_GRAPHIFY (grep/find/read manual,
tiempo real, nº de archivos abiertos) — esto se puede hacer YA, sin
instalar nada. GRAPHIFY_CLI y GRAPHIFY_MCP_CLAUDE quedan como diseño de
benchmark a ejecutar SOLO si Bloque 3 recomienda POC.

Métricas: tokens consumidos, archivos abiertos, búsquedas grep/find
necesarias, tiempo, exactitud (¿encontró todas las relaciones reales,
incluidas las dinámicas del punto 1.2?), falsos positivos, relaciones
omitidas.

────────────────────────────────────────────────────────────────────────────
BLOQUE 3 — QUÉ LE APORTARÍA VALOR AL CÓDIGO ACTUAL (análisis directo)
────────────────────────────────────────────────────────────────────────────

Responder con evidencia del Bloque 1-2, no en abstracto:

- **Alto valor esperado:** navegación estructural y caller/callee en
  código ESTÁTICO (la mayoría de `factory/` fuera de las superficies
  dinámicas) — reduciría directamente el patrón de "grep repetido para
  reconstruir relaciones" que este proyecto ha pagado muchas veces.
- **Valor incierto, a confirmar con el benchmark:** análisis de impacto
  de PR y relación código→API→services→tests — depende de qué tan bien
  Graphify maneja la arquitectura real (agentes como perfiles de
  configuración, no como módulos con imports directos entre sí — ver
  AD-6 del rediseño arquitectónico).
- **Valor bajo o nulo, ya anticipado:** cualquier cosa relacionada con
  topología Docker/infraestructura, y cualquier relación que dependa de
  despacho dinámico no resoluble por AST estático — NO reemplaza
  `docker inspect` ni la disciplina de verificación en vivo que este
  proyecto ya tiene.
- **Integración MCP:** evaluar el ahorro de tokens/contexto en sesiones
  largas de Claude Code (como esta) contra el riesgo de una superficie
  MCP nueva corriendo con acceso al código — aplicar el mismo criterio de
  cautela ya usado para cualquier conector MCP de terceros.

────────────────────────────────────────────────────────────────────────────
ENTREGA
────────────────────────────────────────────────────────────────────────────

```
GRAPHIFY_ARCHITECTURE_SUMMARY =
LOCAL_ONLY_CONFIRMED = (sí/no, con evidencia)
DYNAMIC_CODE_BLIND_SPOTS = (confirmados con ejemplos reales del proyecto)
INFRA_TOPOLOGY_COVERAGE = NO (esperado, confirmar)
BASELINE_BENCHMARK_RESULTS = (5 tareas, tiempo/tokens/archivos reales)
TRACK_B_GRAPHIFY_VALUE =
GRAPHIFY_SECURITY_RISK =
GRAPHIFY_DIRECTORIES_TO_INDEX = factory/, app/, knowledge/, tests/,
    scripts/ (canónico, sin hotelbot/ARIA/GMPAI/secrets)
GRAPHIFY_DIRECTORIES_TO_EXCLUDE = hotelbot/, ARIA/, GMPAI/, .env,
    identity_keys.yaml, backups/, data/, .cache/
GRAPHIFY_EXPECTED_USE_CASES =
GRAPHIFY_TOKEN_BENCHMARK_DESIGN = (Bloque 2, listo para ejecutar si POC)
GRAPHIFY_POC_RECOMMENDED = YES/NO
GRAPHIFY_ARCHITECTURE_CHANGES_REQUIRED =
GRAPHIFY_MCP_RECOMMENDED = YES/NO
FINAL_RECOMMENDATION_GRAPHIFY = INSTALL / POC_FIRST / DO_NOT_INSTALL
```

DETENERSE para revisión de Capa 9. No instalar nada. Si se recomienda
POC, diseñarla según el punto 6 de las instrucciones originales (snapshot
separado, solo código, sin hook/watch/servicio HTTP, sin Rockwell ni
secretos) — pero no ejecutarla en esta corrida.
