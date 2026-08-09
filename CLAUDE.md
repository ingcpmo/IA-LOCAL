# GMP AI Copilot / GMP AI Factory — Consolidación como Analizador Documental GMP

## Contexto y restricciones ABSOLUTAS

**Servidor:** `ing_cpmo@ivr-ia` — Proyecto en `/home/ing_cpmo`
**Autoridad:** Capa 9 = Cesar. Claude Code = Capa 8.

### LO QUE YA ESTÁ FUNCIONANDO — NO TOCAR
- `gmp-api` (Up, responde `/health`) — producto base, puerto 8000
- `factory-api` (Up) — GMP AI Factory capas 7-9, puerto 9000
- `gmp-postgres` (Up, healthy)
- `gmp-redis` (Up, healthy)
- `aria-ollama` (Up — Ollama del proyecto ARIA, **no tocar**)
- Contenedores `aria-*` y `hotelbot-*` — **PROHIBIDO modificar**
- Docker, PostgreSQL, Redis, UFW, systemd, backups — **ya configurados**

### RESTRICCIONES TÉCNICAS OBLIGATORIAS
1. **NO** instalar `ollama` Python package — usar `httpx` directo a la API REST de Ollama
2. **NO** instalar Torch CUDA — usar `torch --index-url https://download.pytorch.org/whl/cpu`
3. **NO** reinstalar infraestructura de ningún tipo
4. **SÍ** reconstruir el contenedor correspondiente si y solo si se modifica código Python
5. **NO** mostrar contenido del `.env`

### Separación arquitectónica (permanente)
- `gmp-api` (:8000) = producto base GMP AI Copilot (query/RAG/audit/agents).
- `factory-api` (:9000) = GMP AI Factory, capas 7-9 (packs, evidence_verifier,
  chunked_engine, estados, decisiones, gobernanza).
- Proyectos custom = generados por la Factory dentro de `factory/workspaces/`.

## Fase 2 (endpoints base gmp-api) — ESTADO: COMPLETADA

Verificado en vivo el 2026-08-09 (ver `docs_plan/` para el detalle de la
corrida). Los 4 endpoints que el plan original marcaba como pendientes ya
están implementados y en producción, protegidos con auth `X-API-Key`:

```
POST /api/v1/query                  → implementado (401 sin key = correcto, no 404)
GET  /api/v1/knowledge/stats        → implementado (401 sin key = correcto, no 404)
GET  /api/v1/audit/verify           → implementado (401 sin key = correcto, no 404)
GET  /api/v1/protocol-template/{tipo} → implementado (401 sin key = correcto, no 404)
knowledge/retriever.py              → existe
tests/test_agents.py                → existe
```

Verificación técnica: hash MD5 de `app/main.py` en el host y dentro del
contenedor coincide (sin rebuild pendiente). Endpoints adicionales no
previstos en el plan original, también en producción: `GET /api/v1/agents`,
`GET /api/v1/rules/evaluate`, `POST /api/v1/stream` (SSE), `POST /api/v1/ingest`.
Arquitectura multicapa activa: Auth → Orchestrator → Rules → RAG → LLM → Audit
(21 CFR Part 11).

**No hay trabajo pendiente de Fase 2.** El foco del proyecto pasa al nuevo
objetivo principal descrito abajo.

## NUEVO OBJETIVO PRINCIPAL: Analizador Documental GMP

Consolidar GMP AI Copilot / GMP AI Factory como un **analizador documental
GMP** que:

1. Lee y analiza documentos técnicos/GMP contra regulación y gobernanza.
2. Identifica anomalías, brechas, desviaciones documentales, NCR
   potenciales, CAPA candidates y change control candidates.
3. Genera informe de hallazgos con: qué está mal; por qué no cumple;
   requisito/regulación/gobernanza usada; evidencia anclada del documento
   original; riesgo; acción recomendada.
4. Genera versión corregida como **borrador controlado**, nunca aprobado
   automáticamente.
5. Mantiene auditoría, evidencia anclada y revisión humana.

Roadmap de implementación: `docs_plan/ROADMAP_ANALIZADOR_GMP.md` (fases
R0-R5). Riesgo central declarado: el recall del modelo (2/7 medido) — un
analizador que no encuentra evidencia presente produce NCRs falsos; R2 del
roadmap existe para resolver esto y es gate bloqueante de R3-R5.

## Reglas GMP permanentes (no negociables)

- El documento original es la fuente maestra — nunca se sobrescribe.
- Todo hallazgo requiere evidencia anclada; **sin evidencia vacía ni citas
  no ancladas**.
- **Sin declaración de cumplimiento final** por parte del sistema.
- **Sin aprobación automática de documentos.**
- **Sin cierre automático de CAPA.**
- **Sin liberación de lote.**
- La IA no sustituye a QA. Decide QA / Cesar / Capa 9.

## Nota de estado — track W5 V2 (recall del modelo)

Gates de gobernanza avanzados y funcionando. Capacidad de detección de
evidencia positiva **limitada por el modelo actual** (recall 2/7 medido
sobre el fixture set 7P+2N, configuración H2+H4). Es el riesgo central del
analizador documental; el roadmap R2 (`docs_plan/ROADMAP_ANALIZADOR_GMP.md`)
lo ataca directamente. El plan de remediación previo
(`docs_plan/W5V2_REMEDIACION_RECALL_MODELO.md`) queda **ON_HOLD** — ver
cabecera de ese documento para condición de reactivación.

## Flujo de trabajo para esta sesión

**REGLA DE ORO:** Leer antes de escribir. Siempre.

```
1. /gmp-read-evidence  ← leer evidencia antes de tocar código
2. /gmp-implement      ← implementar basado en lo que se leyó
```

## Archivos de evidencia disponibles

```
/home/ing_cpmo/logs/evidence/claude_evidence_*/
├── app_main.py           ← código del contenedor en el momento de la captura
├── project_files.txt     ← archivos .py existentes
├── python_packages_key.log ← packages en el contenedor
├── docker-compose.yml    ← config de volúmenes y variables
├── endpoints_check.log   ← detalle de checks de endpoints
├── ollama_connectivity.log ← modelos y URL de Ollama
└── CLAUDE_SERVER_EVIDENCE.md ← reporte manual del servidor
```

**Nota:** la evidencia capturada tiene fecha — verificar siempre contra el
estado en vivo (`curl`, `docker exec`) antes de asumir que sigue vigente;
la evidencia de 2026-06-05 quedó desactualizada frente al código real.

## Variables de entorno esperadas en gmp-api

```bash
# Verificar con: docker exec gmp-api env | grep -E "OLLAMA|CHROMA|AUDIT|DATABASE|REDIS"
OLLAMA_BASE_URL=...      # URL del Ollama accesible desde el contenedor
OLLAMA_MODEL=...         # modelo a usar
CHROMA_PERSIST_DIR=...   # donde guardar ChromaDB
DATABASE_URL=...          # PostgreSQL
REDIS_URL=...             # Redis
AUDIT_LOG_DIR=...         # directorio de audit logs
GMP_API_KEY=...           # requerido por los endpoints /api/v1/*
```

## Reglas de comportamiento de Claude Code

- Leer evidencia → deducir → implementar (nunca al revés)
- Si un archivo existe: leerlo completo antes de modificar
- Si el contenedor tiene un package: usarlo (no reinstalar)
- Antes de `docker compose build`: confirmar qué cambió
- Después de rebuild: esperar 90 segundos antes de verificar
- Ante duda sobre Ollama URL: `docker exec gmp-api env | grep OLLAMA`
- Ante cualquier corrida marcada como "documentación + diseño": prohibido
  implementar código, cambiar endpoints/Docker/infraestructura, o commitear
  sin mostrar diff y recibir aprobación explícita de Cesar.
