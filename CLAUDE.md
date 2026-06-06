# GMP AI Copilot — Fase 2: Implementar endpoints pendientes

## Contexto y restricciones ABSOLUTAS

**Servidor:** `ing_cpmo@ivr-ia` — Proyecto en `/home/ing_cpmo`

### LO QUE YA ESTÁ FUNCIONANDO — NO TOCAR
- `gmp-api` (Up, responde `/health`)
- `gmp-postgres` (Up, healthy)
- `gmp-redis` (Up, healthy)
- `aria-ollama` (Up 24h — Ollama del proyecto ARIA, **no tocar**)
- Contenedores `aria-*` y `hotelbot-*` — **PROHIBIDO modificar**
- Docker, PostgreSQL, Redis, UFW, systemd, backups — **ya configurados**

### RESTRICCIONES TÉCNICAS OBLIGATORIAS
1. **NO** instalar `ollama` Python package — usar `httpx` directo a la API REST de Ollama
2. **NO** instalar Torch CUDA — usar `torch --index-url https://download.pytorch.org/whl/cpu`
3. **NO** reinstalar infraestructura de ningún tipo
4. **SÍ** reconstruir `gmp-api` si y solo si se modifica código Python
5. **NO** mostrar contenido del `.env`

### LO QUE FALTA IMPLEMENTAR (los 6 WARN del status.sh)
```
POST /api/v1/query              → 404  actualmente
GET  /api/v1/knowledge/stats    → 404  actualmente
GET  /api/v1/audit/verify       → 404  actualmente
GET  /api/v1/protocol-template/IQ → 404  actualmente
knowledge/retriever.py          → no existe
tests/test_agents.py            → no existe
```

## Flujo de trabajo para esta sesión

**REGLA DE ORO:** Leer antes de escribir. Siempre.

```
1. /gmp-read-evidence  ← OBLIGATORIO PRIMERO: leer toda la evidencia
2. /gmp-implement      ← implementar basado en lo que se leyó
```

## Archivos de evidencia disponibles

```
/home/ing_cpmo/logs/evidence/claude_evidence_*/
├── app_main.py           ← código actual del contenedor
├── project_files.txt     ← archivos .py existentes
├── python_packages_key.log ← packages en el contenedor
├── docker-compose.yml    ← config de volúmenes y variables
├── endpoints_check.log   ← detalle de los 404
├── ollama_connectivity.log ← modelos y URL de Ollama
└── CLAUDE_SERVER_EVIDENCE.md ← reporte manual del servidor
```

## Variables de entorno esperadas en gmp-api

```bash
# Verificar con: docker inspect gmp-api | python3 -c "..."
OLLAMA_BASE_URL=...      # URL del Ollama accesible desde el contenedor
OLLAMA_MODEL=...         # modelo a usar
CHROMA_PERSIST_DIR=...   # donde guardar ChromaDB
DATABASE_URL=...          # PostgreSQL
REDIS_URL=...             # Redis
AUDIT_LOG_DIR=...         # directorio de audit logs
```

## Reglas de comportamiento de Claude Code

- Leer evidencia → deducir → implementar (nunca al revés)
- Si un archivo existe: leerlo completo antes de modificar
- Si el contenedor tiene un package: usarlo (no reinstalar)
- Antes de `docker compose build`: confirmar qué cambió
- Después de rebuild: esperar 90 segundos antes de verificar
- Ante duda sobre Ollama URL: `docker exec gmp-api env | grep OLLAMA`
