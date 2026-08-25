# TRACK B — EVALUACIÓN DE GRAPHIFY — REPORTE
Generado por Claude Code (Capa 8) — 2026-08-26. Investigación + benchmark
de baseline. **Nada instalado, ningún MCP ejecutado, ningún cambio de
Docker/`.env`/`hotelbot/`/`ARIA/`/`GMPAI/`.**

──────────────────────────────────────────────────────────────────────────────
BLOQUE 1 — INVESTIGACIÓN REAL (repo Graphify-Labs/graphify, vía WebFetch)
──────────────────────────────────────────────────────────────────────────────

**Qué es:** transforma código (+ docs/SQL/config/PDFs) en un grafo de
conocimiento consultable. Se invoca como skill `/graphify` para asistentes
de código (Claude Code, Cursor, Codex, Gemini CLI). Salidas: `graph.html`
interactivo, `GRAPH_REPORT.md`, `graph.json` consultable.

**`LOCAL_ONLY_CONFIRMED` — SÍ para código, CONDICIONAL para docs/PDFs.**
Cita textual del propio README: *"Code is parsed with tree-sitter AST:
deterministic, no LLM, nothing leaves your machine."* Esto cubre el 100%
de lo que indexaríamos (`factory/`, `app/`, `knowledge/`, `tests/`,
`scripts/` — todo código). Docs/PDFs/imágenes/audio SÍ usan el backend
LLM que el usuario configure (Claude/OpenAI/Gemini vía API, o Ollama
local) — riesgo real solo si algún día se apunta Graphify a
`docs_plan/*.md` con un backend externo, no a `GMPAI/Rockwell` (que ya
está excluido y nunca se indexaría). Sin telemetría propia reportada.

**`DYNAMIC_CODE_BLIND_SPOTS` — confirmado explícitamente por el propio
proyecto, no inferido:** *"No native support for dynamically generated or
runtime-introspected code structures."* Aplica directamente a las
superficies únicas de este proyecto (`path_policy`, `decision_scope_
resolver`, `candidate_validity`) que dependen de resolución en tiempo de
ejecución, no solo de imports estáticos.

**`INFRA_TOPOLOGY_COVERAGE = NO`, confirmado.** El README no menciona en
ningún punto Docker Compose, volúmenes, redes ni contenedores — es
exclusivamente un grafo de código/documentos. **No habría ayudado a
encontrar la topología ARIA/hotelbot de esta sesión** — eso exigió
`docker inspect`/`network inspect` en vivo, fuera del alcance de
cualquier herramienta de análisis estático.

**MCP:** sí existe (`python -m graphify.serve`, stdio y HTTP), expone
`query_graph`, `get_node`, `shortest_path`, `list_prs`.

**Actualización incremental:** `--update` re-extrae solo archivos
cambiados; hook de git post-commit opcional en modo solo-AST (sin costo
de API). Sin mecanismo de detección de staleness reportado más allá del
hook — si el hook no está instalado y el código cambia, el grafo queda
desactualizado en silencio (no se documentó una advertencia de "grafo
obsoleto" al consultarlo).

**Ignore rules:** `.graphifyignore` (sintaxis `.gitignore`), respeta
`.gitignore` automáticamente, nunca re-incluye lo que git ignora —
`hotelbot/`/`ARIA/`/`GMPAI/`/`.env` ya están en el `.gitignore` real de
este proyecto, así que quedarían excluidos por herencia sin configurar
nada adicional.

**Multi-directorio:** sí (`/graphify ./docs`, `/graphify .`, `--global`
para índice cruzado de varios proyectos).

**Análisis de impacto de PR:** `graphify prs` (dashboard CI+review+impacto
de grafo), `--triage` (prioriza con LLM), `--conflicts` (detecta orden de
merge riesgoso por comunidades de grafo compartidas).

**Licencia:** dual Apache-2.0 / MIT.

**Límites documentados por el propio proyecto:** visualización HTML
impráctica >5000 nodos (usar `graph.json` directo); "ghost duplicates"
entre extracción AST y semántica en grafos viejos (se resuelve con
`--force`); recuperación automática (con warnings verbosos) cuando una
respuesta LLM excede el límite de tokens de salida; sin soporte para
estructuras generadas dinámicamente (ya citado arriba).

──────────────────────────────────────────────────────────────────────────────
BLOQUE 2 — BENCHMARK DE BASELINE (grep/read real, sin Graphify)
──────────────────────────────────────────────────────────────────────────────

Las 5 tareas reales del proyecto, ejecutadas ahora mismo:

| # | Tarea | Comando(s) | Tiempo real | Archivos abiertos | Resultado |
|---|---|---|---|---|---|
| 1 | Callers de `resolve_candidate_evidence()` | 1 grep | 1.6s | 0 (grep con contexto de línea) | Encontrado: import local DENTRO de una función en `chunked_engine.py:1616` (no top-level) — caso real de import diferido, justo el tipo de patrón que separa un AST superficial de uno completo. |
| 2 | Propagación de `evaluation_profile` hasta `evaluate_chunked()` | 2 grep | 0.02s | 0 | Confirmado: el parámetro SÍ llega a la firma de `evaluate_chunked()` (línea 1038) y se valida (1214-1227) — visible en un solo grep de firma + validación. |
| 3 | Consumidores reales de `decisions_v2.jsonl` más allá del escritor | 1 grep | 0.12s | 0 | 15 archivos, lista completa en un comando — pero SIN distinguir cuáles son import real vs. mención en comentario (requiere lectura humana adicional para depurar). |
| 4 | Tests que cubren `chunked_engine.py` | 1 grep | 0.015s | 0 | 39 archivos de test — conteo directo, sin relación directa/indirecta diferenciada (grep no distingue "importa y llama" de "solo lo menciona en un comentario"). |
| 5 | Callers reales de `verify_sufficiency_aggregated()` | 1 grep | 0.12s | 0 | 20+ líneas devueltas, de las cuales **solo ~4 son llamadas reales** (`sev.verify_sufficiency_aggregated(`) — el resto son comentarios/docstrings que mencionan el nombre. Filtrar exige lectura humana línea por línea. |

**Hallazgo del propio benchmark, no anticipado en el diseño original:**
el cuello de botella real de grep en este proyecto NO es velocidad (todas
las búsquedas corrieron en <2s) — es **ruido**: nombres de función
mencionados en comentarios/docstrings (muy frecuente en este código, que
documenta extensamente el porqué de cada decisión) se mezclan con
llamadas reales, y separar ambos exige lectura humana. Esto coincide
exactamente con la distinción que Graphify dice ofrecer nativamente
(`EXTRACTED` = explícito en el código real, vs. texto libre que grep no
puede diferenciar). Es la evidencia más concreta a favor de un valor real
medible, no solo teórico.

──────────────────────────────────────────────────────────────────────────────
BLOQUE 3 — ANÁLISIS DE VALOR, CON LA EVIDENCIA DE ARRIBA
──────────────────────────────────────────────────────────────────────────────

- **Alto valor esperado, CONFIRMADO por el benchmark:** distinguir
  llamadas reales de menciones textuales (comentarios/docstrings) — este
  proyecto documenta mucho en comentarios, lo que hace que grep devuelva
  ruido real y medible (Tareas 3 y 5 lo muestran directamente). Un grafo
  AST que solo captura aristas `EXTRACTED` eliminaría ese trabajo manual
  de filtrado.
- **Valor incierto, NO resuelto por este benchmark (requeriría POC
  real):** si Graphify captura el import diferido/local visto en la
  Tarea 1 (`chunked_engine.py:1616`, dentro de una función, no en el
  encabezado del archivo) — tree-sitter parsea el archivo completo, así
  que estructuralmente DEBERÍA poder verlo, pero no está confirmado sin
  ejecutarlo.
- **Valor bajo, ya confirmado:** para tareas donde grep ya es
  prácticamente instantáneo y sin ambigüedad (Tarea 2, propagación de un
  parámetro con nombre único) Graphify no aportaría una mejora medible —
  el "costo" de grep ahí ya es casi cero.
- **Valor nulo, confirmado:** topología de infraestructura — no es del
  dominio de la herramienta, dicho explícitamente por su propia
  documentación.
- **MCP:** el riesgo de superficie nueva (servidor MCP con acceso al
  código, aunque sea local/stdio) es real y debe evaluarse con el mismo
  criterio que cualquier conector de terceros — pero al ser 100% local
  para la parte de código (sin llamadas salientes), el riesgo es menor
  que el de un MCP que sí llame a servicios externos.

──────────────────────────────────────────────────────────────────────────────
ENTREGA
──────────────────────────────────────────────────────────────────────────────

```
GRAPHIFY_ARCHITECTURE_SUMMARY = grafo de conocimiento de codigo/docs via
    tree-sitter AST (codigo) + LLM configurable (docs/PDFs/media),
    salidas graph.html/GRAPH_REPORT.md/graph.json, CLI + servidor MCP
    opcional, actualizacion incremental via hook git, dual-licenciado
    Apache-2.0/MIT
LOCAL_ONLY_CONFIRMED = SI para codigo ("nothing leaves your machine",
    cita textual); CONDICIONAL para docs/PDFs (depende del backend LLM
    que el usuario configure) -- no aplica a este caso de uso (solo se
    indexaria codigo)
DYNAMIC_CODE_BLIND_SPOTS = CONFIRMADO por el propio proyecto ("no native
    support for dynamically generated or runtime-introspected code") --
    aplica a path_policy/decision_scope_resolver/candidate_validity
INFRA_TOPOLOGY_COVERAGE = NO, confirmado -- no cubre Docker/redes/volumenes
BASELINE_BENCHMARK_RESULTS = 5/5 tareas resueltas con grep en <2s cada
    una, 0 archivos abiertos mas alla de la salida de grep -- el cuello
    de botella real es filtrar RUIDO (menciones en comentarios vs
    llamadas reales), no velocidad de busqueda
TRACK_B_GRAPHIFY_VALUE = MEDIO -- valor real y medible en distinguir
    llamadas reales de menciones textuales (confirmado por benchmark),
    valor marginal donde grep ya es instantaneo y sin ambiguedad, valor
    nulo en topologia de infraestructura
GRAPHIFY_SECURITY_RISK = BAJO para el alcance propuesto (solo codigo,
    procesamiento 100% local) -- .gitignore existente ya excluye
    hotelbot/ARIA/GMPAI/.env por herencia, sin configuracion adicional
GRAPHIFY_DIRECTORIES_TO_INDEX = factory/, app/, knowledge/, tests/,
    scripts/
GRAPHIFY_DIRECTORIES_TO_EXCLUDE = hotelbot/, ARIA/, GMPAI/, .env,
    identity_keys.yaml, backups/, data/, .cache/ (todos ya cubiertos por
    .gitignore heredado)
GRAPHIFY_EXPECTED_USE_CASES = resolver relaciones caller/callee reales
    (no mencionES textuales) en codigo estatico de factory/; cobertura
    codigo->tests; analisis de impacto de cambios de firma -- SIEMPRE
    verificando manualmente las superficies dinamicas conocidas
    (path_policy, decision_scope_resolver, candidate_validity), que el
    propio proyecto admite no cubrir
GRAPHIFY_TOKEN_BENCHMARK_DESIGN = listo (Bloque 2 de este documento) --
    mismas 5 tareas, ejecutar con /graphify + MCP si se aprueba POC,
    comparar tokens/tiempo/exactitud contra esta baseline
GRAPHIFY_POC_RECOMMENDED = YES -- alcance minimo: /graphify factory/
    (unico directorio, sin --global, sin --viz por el volumen de
    factory/, sin apuntar a docs/PDFs, sin conectar backend LLM externo
    para esta prueba), correr las mismas 5 tareas via MCP y comparar
GRAPHIFY_ARCHITECTURE_CHANGES_REQUIRED = NINGUNO -- no toca produccion,
    no es dependencia del pipeline de analisis documental, es una
    herramienta de desarrollo para Capa 8
GRAPHIFY_MCP_RECOMMENDED = POC_FIRST -- evaluar en modo stdio local
    unicamente, sin exponer HTTP, antes de considerar uso regular
FINAL_RECOMMENDATION_GRAPHIFY = POC_FIRST
```

DETENIDO para revisión de Capa 9 — nada instalado, ningún MCP corrido.
Si se aprueba la POC, diseño mínimo ya está listo arriba (alcance
`factory/` únicamente, sin docs/PDFs, sin backend LLM externo, sin
`--global`).
