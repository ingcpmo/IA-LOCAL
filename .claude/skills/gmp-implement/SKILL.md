# Skill: gmp-implement

Implementa los 6 items pendientes del GMP AI Copilot. SIEMPRE ejecutar /gmp-read-evidence antes de este skill.

## Prerequisito obligatorio

Antes de escribir una sola línea de código, verificar que se leyó la evidencia.
Si no se hizo, ejecutar /gmp-read-evidence primero.

## Los 6 items a implementar

```
POST /api/v1/query              → agregar a app/main.py
GET  /api/v1/knowledge/stats    → agregar a app/main.py
GET  /api/v1/audit/verify       → agregar a app/main.py
GET  /api/v1/protocol-template/IQ → agregar a app/main.py
app/knowledge/retriever.py      → crear nuevo archivo
tests/test_agents.py            → crear nuevo archivo
```

## Restricciones técnicas ABSOLUTAS

- NO instalar `ollama` Python package — usar `httpx` directo a `OLLAMA_BASE_URL`
- NO instalar Torch CUDA — si se necesita torch: `--index-url https://download.pytorch.org/whl/cpu`
- Usar solo packages que estén en requirements.txt
- NO modificar docker-compose.yml, Dockerfile (a menos que sea agregar packages a requirements.txt)
- NO tocar contenedores aria-* ni hotelbot-*

## Variables de entorno disponibles (ya en el contenedor)

```
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=mistral:7b-instruct-q4_K_M
OLLAMA_TIMEOUT=180
DATABASE_URL=postgresql://gmp_user:gmp_pass@postgres:5432/gmp_copilot
REDIS_URL=redis://redis:6379/0
AUDIT_LOG_DIR=./data/audit_logs
AUDIT_LOG_HASH_ALGO=sha256
CHROMA_PERSIST_DIR=./data/chroma
CHROMA_FDA_COLLECTION=gmp_fda_regulations
CHROMA_IQ_COLLECTION=gmp_iq_oq_pq
```

## Pasos de implementación

1. Modificar `/home/ing_cpmo/app/main.py` para agregar los 4 endpoints `/api/v1/*`
2. Crear `/home/ing_cpmo/app/knowledge/retriever.py` con ChromaDB retriever
3. Crear `/home/ing_cpmo/tests/test_agents.py` con tests básicos
4. Confirmar qué cambió antes de rebuild
5. Ejecutar: `cd /home/ing_cpmo && docker compose build api 2>&1 | tail -20`
6. Ejecutar: `docker compose up -d api`
7. Esperar 90 segundos
8. Verificar con: `curl -s localhost:8000/health | python3 -m json.tool`

## Diseño de los endpoints

### POST /api/v1/query
- Recibe: `{"question": str, "context_type": str = "general"}`
- Flujo: recuperar contexto de ChromaDB → construir prompt → llamar Ollama → devolver respuesta
- Devuelve: `{"answer": str, "sources": list, "model": str}`

### GET /api/v1/knowledge/stats
- Consulta ChromaDB y devuelve estadísticas de las colecciones FDA e IQ/OQ/PQ
- Devuelve: `{"fda_collection": {"count": int}, "iq_collection": {"count": int}}`

### GET /api/v1/audit/verify
- Lee audit logs de AUDIT_LOG_DIR, verifica hashes SHA256
- Devuelve: `{"verified": bool, "log_count": int, "hash_algo": str}`

### GET /api/v1/protocol-template/IQ
- Devuelve template de protocolo IQ (Installation Qualification) en formato GMP
- Devuelve: `{"protocol_type": "IQ", "template": {...}}`
