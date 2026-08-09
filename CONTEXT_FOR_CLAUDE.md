# Contexto extendido para Claude Code

## Estado verificado en vivo — 2026-08-09

Fase 2 (endpoints base `gmp-api`) está **COMPLETADA**. Verificación hecha
en esta fecha, no en el momento de la evidencia capturada (2026-06-05, ver
sección histórica abajo):

- `curl` en vivo a los 4 endpoints (`POST /api/v1/query`,
  `GET /api/v1/knowledge/stats`, `GET /api/v1/audit/verify`,
  `GET /api/v1/protocol-template/IQ`) responde **401** (falta `X-API-Key`),
  no 404 — es decir, están implementados y protegidos por auth, no
  ausentes.
- `knowledge/retriever.py` y `tests/test_agents.py` existen en
  `/home/ing_cpmo/`.
- `md5sum` de `app/main.py` coincide entre host y contenedor `gmp-api` →
  el contenedor corre el código actual, sin rebuild pendiente.
- `docker exec gmp-api pip list` confirma `chromadb`/`chroma-hnswlib`
  instalados (la nota de junio decía que no lo estaban — quedó obsoleta).
- Endpoints adicionales en producción, no listados en el plan original:
  `GET /api/v1/agents`, `GET /api/v1/rules/evaluate`,
  `POST /api/v1/stream` (SSE), `POST /api/v1/ingest`.
- Contenedores vivos: `gmp-api`, `gmp-postgres`, `gmp-redis` (Up ~37h,
  healthy), `aria-*` y `hotelbot-*` intactos.

**Nuevo objetivo principal del proyecto:** consolidar el copiloto/factory
como **analizador documental GMP**. Ver `CLAUDE.md` (sección "Nuevo
objetivo principal") y `docs_plan/ROADMAP_ANALIZADOR_GMP.md` para el
roadmap R0-R5.

---

## Evidencia histórica (capturada 2026-06-05 — desactualizada, se conserva como referencia)

La sección siguiente es el snapshot original de evidencia que motivó el
plan de Fase 2. **No representa el estado actual del código** — se
mantiene por trazabilidad, no como fuente de verdad. Para el estado real,
usar la sección "Estado verificado en vivo" arriba.

### app/main.py (snapshot 2026-06-05 — versión mínima, ya superada)
```python
import os
import time
import httpx
import redis
import asyncpg
from fastapi import FastAPI
from pydantic import BaseModel

APP_NAME = os.getenv("APP_NAME", "GMP AI Copilot")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral:7b-instruct-q4_K_M")
DATABASE_URL = os.getenv("DATABASE_URL", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

app = FastAPI(title=APP_NAME)


class QueryRequest(BaseModel):
    question: str


@app.get("/")
async def root():
    return {
        "app": APP_NAME,
        "status": "running",
        "ollama_model": OLLAMA_MODEL,
    }


@app.get("/health")
async def health():
    status = {
        "api": "ok",
        "postgres": "unknown",
        "redis": "unknown",
        "ollama": "unknown",
        "timestamp": int(time.time()),
    }

    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("SELECT 1")
        await conn.close()
        status["postgres"] = "ok"
    except Exception as exc:
        status["postgres"] = f"error: {type(exc).__name__}"

    try:
        r = redis.from_url(REDIS_URL, socket_connect_timeout=3)
        r.ping()
        status["redis"] = "ok"
    except Exception as exc:
        status["redis"] = f"error: {type(exc).__name__}"

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/version")
            response.raise_for_status()
            status["ollama"] = "ok"
    except Exception as exc:
        status["ollama"] = f"error: {type(exc).__name__}"

    return status


@app.post("/ask")
async def ask(payload: QueryRequest):
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": payload.question,
                "stream": False,
            },
        )
        response.raise_for_status()
        data = response.json()

    return {
        "question": payload.question,
        "model": OLLAMA_MODEL,
        "answer": data.get("response", ""),
    }
```

### Packages en el contenedor gmp-api (snapshot 2026-06-05)
```
fastapi           0.115.6
httpx             0.28.1
pydantic          2.10.4
pydantic_core     2.27.2
```

NOTA (histórica, ya superada): en 2026-06-05 LangChain, ChromaDB y
sentence-transformers NO estaban instalados. Verificado en 2026-08-09 que
`chromadb`/`chroma-hnswlib` sí están presentes en el contenedor actual.

### Variables de entorno en el contenedor gmp-api (snapshot 2026-06-05)
```
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=mistral:7b-instruct-q4_K_M
OLLAMA_MAX_TOKENS=2048
OLLAMA_TIMEOUT=180
REDIS_URL=redis://redis:6379/0
DATABASE_URL=postgresql://gmp_user:gmp_pass@postgres:5432/gmp_copilot
AUDIT_LOG_DIR=./data/audit_logs
AUDIT_LOG_HASH_ALGO=sha256
DATABASE_POOL_SIZE=5
CHROMA_PERSIST_DIR=./data/chroma
CHROMA_FDA_COLLECTION=gmp_fda_regulations
CHROMA_IQ_COLLECTION=gmp_iq_oq_pq
```

### Archivos Python del proyecto GMP en /home/ing_cpmo/ (snapshot 2026-06-05)
```
/home/ing_cpmo/app/__init__.py
/home/ing_cpmo/app/main.py
```

Estado 2026-08-09: se agregaron `app/audit.py`, `app/orchestrator.py`,
`app/rules.py`, `app/agents/base.py`, `knowledge/retriever.py`,
`tests/test_agents.py` — todos existentes y en uso por el `main.py` actual.

### Modelos Ollama disponibles en localhost:11434
```
llama3.2:latest (2.0GB)
mistral:7b-instruct-q4_K_M (4.4GB)
```

### Dockerfile (snapshot 2026-06-05)
```dockerfile
FROM python:3.11-slim

LABEL description="FDA Qualification Platform"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Endpoints — histórico de lo que faltaba (snapshot 2026-06-05, ver arriba estado real 2026-08-09)
```
POST /api/v1/query              → 404 en 2026-06-05 — implementado en 2026-08-09
GET  /api/v1/knowledge/stats    → 404 en 2026-06-05 — implementado en 2026-08-09
GET  /api/v1/audit/verify       → 404 en 2026-06-05 — implementado en 2026-08-09
GET  /api/v1/protocol-template/IQ → 404 en 2026-06-05 — implementado en 2026-08-09
knowledge/retriever.py          → no existía en 2026-06-05 — existe en 2026-08-09
tests/test_agents.py            → no existía en 2026-06-05 — existe en 2026-08-09
```

### Estructura de directorios del proyecto (snapshot 2026-06-05)
```
/home/ing_cpmo/
├── app/
│   ├── __init__.py
│   └── main.py           ← código fuente (montado en /app/app/ dentro del contenedor)
├── data/
│   ├── audit_logs/       ← AUDIT_LOG_DIR
│   └── chroma/           ← CHROMA_PERSIST_DIR
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

### requirements.txt (snapshot 2026-06-05)
```
fastapi==0.115.6
uvicorn[standard]==0.34.0
httpx==0.28.1
redis==5.2.1
asyncpg==0.30.0
pydantic==2.10.4
python-dotenv==1.0.1

sentence-transformers==3.3.1
chromadb==0.5.23
langchain==0.3.13
langchain-community==0.3.13
```

### docker-compose.yml (resumen relevante, snapshot 2026-06-05)
```yaml
# api service usa:
#   build: context=. dockerfile=Dockerfile
#   env_file: .env
#   environment: OLLAMA_BASE_URL, DATABASE_URL, REDIS_URL
#   extra_hosts: host.docker.internal:host-gateway
#   ports: 8000:8000
# NO hay volúmenes montados para el código — se copia en el build
```
